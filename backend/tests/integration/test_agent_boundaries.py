"""B perspective, continuation, tool-limit and timeout acceptance through real components."""

import asyncio
import json

import pytest
from sqlalchemy import select

from app.agent import context, llm, tools
from app.agent.budget import request_tokens
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.models import Conversation, ConversationPartition
from app.config import get_settings
from app.core import db


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: pytest.fail("real model forbidden"))

    async def summarize(text, instruction):
        return text

    monkeypatch.setattr(llm, "summarize", summarize)
    # Permission/limit scenarios are independent of the default context size.
    monkeypatch.setattr(get_settings(), "agent_context_max_tokens", 100000)


def seed(client):
    project = client.post("/api/projects", json={"name": "partition-test"}).json()["id"]
    session = client.post("/api/agent/sessions", params={"project_id": project}, json={}).json()[
        "id"
    ]
    return project, session


def send(client, session, perspective="author", character_id="", text="continue"):
    response = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session,
            "message": text,
            "perspective": perspective,
            "character_id": character_id,
        },
    )
    assert response.status_code == 200
    return response.text


class Script:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.calls = []

    async def __call__(self, system, messages, **kwargs):
        # Snapshot; later tool appends must not modify captured evidence.
        self.calls.append(json.loads(json.dumps([system, messages, kwargs])))
        yield "turn", next(self.turns)


def tool_turn(name, arguments, call_id="call-1"):
    return AssistantTurn(
        content=None,
        tool_calls=[ToolCall(call_id=call_id, name=name, arguments=json.dumps(arguments))],
    )


def test_histories_and_summaries_partition_by_character_and_project(client, monkeypatch):
    project, session = seed(client)
    chars = [
        client.post(
            "/api/entities", json={"project_id": project, "type": "character", "name": name}
        ).json()["id"]
        for name in ("Alice", "Bob")
    ]
    monkeypatch.setattr(get_settings(), "agent_history_window_messages", 1)
    script = Script(
        [
            AssistantTurn(content=text)
            for text in [
                "SECRET-AUTHOR",
                "SECRET-ALICE",
                "bob",
                "audience",
                "alice-again",
                "other-project",
            ]
        ]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", script)
    assert "event: done" in send(client, session, text="SECRET-AUTHOR")
    assert "event: done" in send(client, session, "character", chars[0], "SECRET-ALICE")
    assert "event: done" in send(client, session, "character", chars[1])
    assert "event: done" in send(client, session, "audience")
    assert "event: done" in send(client, session, "character", chars[0])
    _, other_session = seed(client)
    assert "event: done" in send(client, other_session)
    for index in (1, 2, 3, 4, 5):
        assert "SECRET-AUTHOR" not in json.dumps(script.calls[index])
    for index in (2, 3, 5):
        assert "SECRET-ALICE" not in json.dumps(script.calls[index])
    assert "SECRET-ALICE" in json.dumps(script.calls[4])

    async def states():
        async with db.get_session_factory()() as sql:
            conv = await sql.get(Conversation, session)
            partitions = list(
                await sql.scalars(
                    select(ConversationPartition).where(
                        ConversationPartition.conversation_id == session
                    )
                )
            )
            return conv.summary, {row.context_key: row.summary for row in partitions}

    author, partitions = client.portal.call(states)
    assert "SECRET-AUTHOR" in author
    assert "SECRET-ALICE" not in author
    assert "SECRET-ALICE" in partitions[f"character:{chars[0]}"]
    assert "SECRET-ALICE" not in partitions[f"character:{chars[1]}"]


@pytest.mark.parametrize("name", ["read_doc_section", "write_doc_section", "create_memory_doc"])
def test_narrow_tools_cannot_leak_document_title_or_content(client, monkeypatch, name):
    project, session = seed(client)
    doc = client.post("/api/agent/memory-docs", params={"project_id": project}).json()
    section = doc["sections"][0]
    response = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        json={
            "content": "PRIVATE-DOCUMENT",
            "title": "PRIVATE-TITLE",
            "expected_version": section["version"],
        },
    )
    assert response.status_code == 200
    script = Script(
        [
            tool_turn(
                name,
                {
                    "doc_id": doc["id"],
                    "seq": section["seq"],
                    "kind": "positioning",
                    "content": "write",
                },
            ),
            AssistantTurn(content="done"),
        ]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", script)
    assert "event: done" in send(client, session, "audience")
    assert "PRIVATE-DOCUMENT" not in json.dumps(script.calls)
    assert "PRIVATE-TITLE" not in json.dumps(script.calls)
    assert client.get("/api/agent/pending-writes", params={"conversation_id": session}).json() == []


def test_hidden_entity_name_not_returned_in_update_error(client, monkeypatch):
    project, session = seed(client)
    entity = client.post(
        "/api/entities",
        json={"project_id": project, "type": "character", "name": "SECRET-HIDDEN-NAME"},
    ).json()
    script = Script(
        [
            tool_turn("update_entity", {"entity_id": entity["id"], "description": "patch"}),
            AssistantTurn(content="done"),
        ]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", script)
    assert "event: done" in send(client, session, "audience")
    assert "SECRET-HIDDEN-NAME" not in json.dumps(script.calls)


def test_result_continuation_is_scoped_and_lossless(client):
    project, _ = seed(client)

    async def exercise():
        async with db.get_session_factory()() as sql:
            ctx = tools.ToolContext(session=sql, project_id=project, perspective="author")
            original = "中文👩🏽‍💻END" * 20
            result = json.loads(tools.page_result(original, ctx, 50))["result"]
            text = result["content"]
            first_token = result["continuation"]
            while result["continuation"]:
                tail = await tools.execute_tool(
                    "continue_tool_result",
                    json.dumps({"continuation": result["continuation"]}),
                    ctx,
                )
                result = json.loads(tools.page_result(tail, ctx, 50))["result"]
                text += result["content"]
            assert text == original
            for other in [
                tools.ToolContext(session=sql, project_id="other", perspective="author"),
                tools.ToolContext(session=sql, project_id=project, perspective="audience"),
                tools.ToolContext(session=sql, project_id=project, perspective="author"),
            ]:
                refused = await tools.execute_tool(
                    "continue_tool_result", json.dumps({"continuation": first_token}), other
                )
                assert "工具执行失败" in refused
                assert "END" not in refused

    client.portal.call(exercise)


def test_tool_result_growth_is_checked_before_next_provider_call(client, monkeypatch):
    _, session = seed(client)
    settings = get_settings()

    async def first_size():
        async with db.get_session_factory()() as sql:
            conversation = await sql.get(Conversation, session)
            messages = await context.assemble_chat_context(
                sql,
                conversation,
                perspective="author",
                character_id="",
                user_message="continue",
                settings=settings,
                tool_specs=tools.specs_for("author"),
            )
            return request_tokens(messages, tools.specs_for("author"), settings)

    size = client.portal.call(first_size)
    monkeypatch.setattr(
        settings, "agent_context_max_tokens", size + settings.agent_output_reserve_tokens + 1
    )
    script = Script(
        [tool_turn("search_entities", {"q": "a"}), AssistantTurn(content="must not call")]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", script)

    async def large_result(*args):
        return "中" * 2000

    monkeypatch.setattr(tools, "execute_tool", large_result)
    response = send(client, session)
    assert "AGENT_CONTEXT_BUDGET" in response
    assert len(script.calls) == 1


def test_directory_pages_cover_visible_items_only(client, monkeypatch):
    project, _ = seed(client)
    monkeypatch.setattr(get_settings(), "agent_directory_page_size", 2)
    visible_ids = []
    for index in range(5):
        entity = client.post(
            "/api/entities",
            json={
                "project_id": project,
                "type": "character",
                "name": f"item-{index}",
                "audience_known": index < 4,
            },
        ).json()
        if index < 4:
            visible_ids.append(entity["id"])

    async def read_pages():
        async with db.get_session_factory()() as sql:
            ctx = tools.ToolContext(session=sql, project_id=project, perspective="audience")
            first = json.loads(
                await tools.execute_tool("list_context_directory", '{"kind":"graph"}', ctx)
            )
            assert len(first["items"]) == 2
            second = json.loads(
                await tools.execute_tool(
                    "list_context_directory",
                    json.dumps({"kind": "graph", "offset": first["next_offset"]}),
                    ctx,
                )
            )
            assert second["next_offset"] is None
            assert sorted(item["id"] for item in first["items"] + second["items"]) == sorted(
                visible_ids
            )
            denied = await tools.execute_tool("list_context_directory", '{"kind":"documents"}', ctx)
            assert "工具执行失败" in denied

    client.portal.call(read_pages)


@pytest.mark.parametrize(
    "mode",
    [
        "tool_timeout",
        "turn_timeout",
        "repeat_failure",
        "model_calls",
        "disabled_tools",
        "missing_turn",
    ],
)
def test_run_stops_on_limits_and_invalid_provider(client, monkeypatch, mode):
    _, session = seed(client)
    settings = get_settings()
    if mode == "tool_timeout":
        monkeypatch.setattr(settings, "agent_tool_timeout_seconds", 0.01)
    if mode == "turn_timeout":
        monkeypatch.setattr(settings, "agent_turn_timeout_seconds", 0.01)
    if mode == "model_calls":
        monkeypatch.setattr(settings, "agent_max_model_calls_per_turn", 1)
    if mode == "disabled_tools":
        monkeypatch.setattr(settings, "agent_max_tool_calls_per_turn", 0)
    calls = []
    executed = []

    async def provider(*args, **kwargs):
        calls.append(True)
        if mode == "missing_turn":
            return
        yield "turn", tool_turn("unknown", {}, f"call-{len(calls)}")

    async def execute(*args):
        executed.append(True)
        if "timeout" in mode:
            await asyncio.sleep(10)
        return "工具执行失败: invalid"

    monkeypatch.setattr(llm, "stream_chat_turn", provider)
    monkeypatch.setattr(tools, "execute_tool", execute)
    response = send(client, session)
    assert "event: error" in response
    assert "event: done" not in response
    assert len(calls) <= 3
    assert len(executed) <= 2
    if mode in {"disabled_tools", "missing_turn"}:
        assert executed == []
