"""E acceptance: traceable summaries, explicit gaps, and scoped source recovery."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.agent import context, llm, tools
from app.agent.models import Conversation, Message, SummaryVersion
from app.agent.tools import ToolContext
from app.config import get_settings
from app.core import db


def seed(client):
    project = client.post("/api/projects", json={"name": "summary-e"}).json()["id"]
    conversation = client.post(
        "/api/agent/sessions", params={"project_id": project}, json={}
    ).json()["id"]
    return project, conversation


def test_repeated_compression_keeps_originals_and_verified_key_sources(client, monkeypatch):
    project_id, conversation_id = seed(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_history_window_messages", 2)
    monkeypatch.setattr(settings, "agent_summary_batch_messages", 2)

    async def fake_summary(text, _instruction):
        return "可追溯摘要：" + text[:200]

    monkeypatch.setattr(llm, "summarize", fake_summary)

    async def exercise():
        async with db.get_session_factory()() as session:
            conversation = await session.get(Conversation, conversation_id)
            assert conversation is not None
            base = datetime.now(UTC) - timedelta(minutes=10)
            texts = [
                "不要让林岚离开，船员必须保持 17 人。",
                "决定把港口改为『白沙港』。",
                "谁来保管编号 2048 的钥匙？",
                "撤销上一版结盟决定。",
                "工具失败：地图读取超时。",
                "继续保留长程约束。",
            ]
            for index, text in enumerate(texts):
                session.add(
                    Message(
                        id=f"msg-e-{index}",
                        conversation_id=conversation_id,
                        role="user" if index != 4 else "tool",
                        context_key="author",
                        content=text,
                        created_at=base + timedelta(seconds=index),
                    )
                )
            await session.commit()
            await context.maintain_rolling_summary(session, conversation, settings=settings)
            await session.commit()
            await context.maintain_rolling_summary(session, conversation, settings=settings)
            await session.commit()
            versions = list(
                await session.scalars(
                    select(SummaryVersion)
                    .where(SummaryVersion.conversation_id == conversation_id)
                    .order_by(SummaryVersion.version)
                )
            )
            messages = list(
                await session.scalars(
                    select(Message).where(Message.conversation_id == conversation_id)
                )
            )
            await session.refresh(conversation)
            compiled = await context.assemble_chat_context(
                session,
                conversation,
                perspective="author",
                character_id="",
                user_message="继续",
                settings=settings,
            )
            return (
                versions,
                messages,
                conversation.summary_version_id,
                json.dumps(compiled, ensure_ascii=False),
            )

    versions, messages, active_id, prompt = client.portal.call(exercise)
    assert [row.status for row in versions] == ["verified", "verified"]
    assert json.loads(versions[-1].source_ids_json) == [f"msg-e-{i}" for i in range(4)]
    items = json.loads(versions[-1].key_items_json)
    assert {item["kind"] for item in items} >= {"constraint", "decision", "open_task"}
    assert all(any(message.id == item["source_id"] for message in messages) for item in items)
    assert any("17" in item["exact_values"] for item in items)
    assert len(messages) == 6 and active_id == versions[-1].id
    assert "船员必须保持 17 人" in prompt and "谁来保管编号 2048" in prompt


def test_failed_attempt_and_corrupt_cursor_leave_active_summary_and_expose_gap(client, monkeypatch):
    _, conversation_id = seed(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_history_window_messages", 1)
    monkeypatch.setattr(settings, "agent_summary_batch_messages", 2)

    async def exercise():
        async with db.get_session_factory()() as session:
            conversation = await session.get(Conversation, conversation_id)
            assert conversation is not None
            for index in range(3):
                session.add(
                    Message(
                        id=f"msg-gap-{index}",
                        conversation_id=conversation_id,
                        role="user",
                        context_key="author",
                        content=f"必须保留约束 {index}",
                    )
                )
            await session.commit()

            async def good(*_args):
                return "旧摘要"

            monkeypatch.setattr(llm, "summarize", good)
            await context.maintain_rolling_summary(session, conversation, settings=settings)
            await session.commit()
            active_id = conversation.summary_version_id
            old_summary = conversation.summary
            conversation.summary_until_id = "missing-cursor"
            await session.commit()
            await context.maintain_rolling_summary(session, conversation, settings=settings)
            await session.commit()
            await session.refresh(conversation)
            active = await session.get(SummaryVersion, active_id)
            assert active is not None
            active.source_ids_json = '["missing-source"]'
            await session.commit()
            compiled = await context.assemble_chat_context(
                session,
                conversation,
                perspective="author",
                character_id="",
                user_message="继续",
                settings=settings,
            )
            versions = list(
                await session.scalars(
                    select(SummaryVersion)
                    .where(SummaryVersion.conversation_id == conversation_id)
                    .order_by(SummaryVersion.version)
                )
            )
            return active_id, old_summary, conversation, versions, compiled.disclosure

    active_id, old_summary, conversation, versions, disclosure = client.portal.call(exercise)
    assert conversation.summary_version_id == active_id and conversation.summary == old_summary
    assert conversation.summary_until_id == "msg-gap-1"
    assert versions[-1].status == "failed"
    assert versions[-1].validation_error == "CURSOR_NOT_FOUND"
    assert disclosure["coverage_gap"] is True


def test_source_recovery_tool_is_partition_scoped_and_paginated(client, monkeypatch):
    project_id, conversation_id = seed(client)
    monkeypatch.setattr(get_settings(), "agent_source_page_size", 1)

    async def exercise():
        async with db.get_session_factory()() as session:
            session.add_all(
                [
                    Message(
                        id="msg-author-secret",
                        conversation_id=conversation_id,
                        role="user",
                        context_key="author",
                        content="AUTHOR-SECRET",
                    ),
                    Message(
                        id="msg-audience-1",
                        conversation_id=conversation_id,
                        role="user",
                        context_key="audience",
                        content="VISIBLE-ONE",
                    ),
                    Message(
                        id="msg-audience-2",
                        conversation_id=conversation_id,
                        role="assistant",
                        context_key="audience",
                        content="VISIBLE-TWO",
                    ),
                ]
            )
            await session.commit()
            ctx = ToolContext(
                session=session,
                project_id=project_id,
                perspective="audience",
                conversation_id=conversation_id,
            )
            hidden = await tools.execute_tool(
                "read_conversation_sources", '{"source_ids":["msg-author-secret"]}', ctx
            )
            first = await tools.execute_tool("read_conversation_sources", "{}", ctx)
            second = await tools.execute_tool("read_conversation_sources", '{"offset":1}', ctx)
            return hidden, first, second

    hidden, first, second = client.portal.call(exercise)
    assert json.loads(hidden)["items"] == [] and "AUTHOR-SECRET" not in hidden
    assert json.loads(first)["items"][0]["content"] == "VISIBLE-ONE"
    assert json.loads(first)["next_offset"] == 1
    assert json.loads(second)["items"][0]["content"] == "VISIBLE-TWO"
