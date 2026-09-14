"""A-slice defects: strict xfail documents unmet acceptance, never a passing safety claim.

Run with --runxfail to see the original failures. All data uses conftest's disposable DB;
the provider is replaced and client creation is forbidden, including summary/repair calls.
"""

import json

import pytest

from app.agent import documents, llm, repository, tools
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.schemas import SectionUpdate
from app.config import get_settings
from app.core import db

pytestmark = pytest.mark.integration


class UnmetAcceptance(AssertionError):
    """Only the target defect may xfail; setup and unrelated assertions must fail normally."""


def require_acceptance(condition, reason):
    if not condition:
        raise UnmetAcceptance(reason)


class Capture:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.prompts = []

    async def __call__(self, system, messages, **kwargs):
        self.prompts.append(json.dumps([system, messages, kwargs], ensure_ascii=False))
        yield "turn", next(self.turns)


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    def forbidden():
        pytest.fail("real provider forbidden in reliability baseline")

    async def summary_failure(*args, **kwargs):
        raise TimeoutError("injected summary timeout")

    monkeypatch.setattr(llm, "get_client", forbidden)
    monkeypatch.setattr(llm, "summarize", summary_failure)


def seed(client):
    response = client.post("/api/projects", json={"name": "可靠性临时项目"})
    assert response.status_code == 201
    project = response.json()["id"]
    response = client.post("/api/agent/sessions", params={"project_id": project}, json={})
    assert response.status_code == 201
    return project, response.json()["id"]


def chat(client, conversation, text="继续", perspective="author"):
    response = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": conversation,
            "message": text,
            "perspective": perspective,
        },
    )
    assert response.status_code == 200
    return response.text


def test_author_history_does_not_enter_audience_prompt(client, monkeypatch):
    _, conversation = seed(client)
    capture = Capture([AssistantTurn(content="秘密口令-鹤鸣九号"), AssistantTurn(content="继续")])
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    assert "event: done" in chat(client, conversation)
    assert "event: done" in chat(client, conversation, perspective="audience")
    assert len(capture.prompts) == 2
    require_acceptance(
        "秘密口令-鹤鸣九号" not in capture.prompts[1], "author secret reached audience"
    )


def test_oversized_chinese_input_never_calls_provider(client, monkeypatch):
    _, conversation = seed(client)
    monkeypatch.setattr(get_settings(), "agent_context_max_tokens", 100)
    capture = Capture([AssistantTurn(content="不应调用")])
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    chat(client, conversation, "中" * 8000)
    require_acceptance(len(capture.prompts) == 0, "oversized request called provider once")


def test_batch_executes_only_allowed_tool_count(client, monkeypatch):
    _, conversation = seed(client)
    monkeypatch.setattr(get_settings(), "agent_max_tool_calls_per_turn", 1)
    calls = [
        ToolCall(call_id=f"call-{i}", name="search_entities", arguments='{"q":"a"}')
        for i in range(3)
    ]
    raw = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in calls
        ],
    }
    capture = Capture(
        [AssistantTurn(content=None, tool_calls=calls, raw=raw), AssistantTurn(content="完成")]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    executed = []

    async def execute(name, args, ctx):
        executed.append(name)
        return "empty"

    monkeypatch.setattr(tools, "execute_tool", execute)
    assert "event: done" in chat(client, conversation)
    require_acceptance(len(executed) == 1, f"executed {len(executed)} tools with quota 1")


def test_failed_summary_does_not_silently_hide_uncovered_requirement(client, monkeypatch):
    _, conversation = seed(client)
    monkeypatch.setattr(get_settings(), "agent_history_window_messages", 2)
    capture = Capture([AssistantTurn(content="收到") for _ in range(3)])
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    assert "event: done" in chat(client, conversation, "不可撤销的约束-主角不能杀人")
    assert "event: done" in chat(client, conversation, "场景二")
    response = chat(client, conversation, "场景三")
    assert len(capture.prompts) == 3
    # Either the constraint is included or the run explicitly refuses incomplete context.
    require_acceptance(
        "不可撤销的约束-主角不能杀人" in capture.prompts[2] or "event: error" in response,
        "uncovered constraint omitted without error",
    )


def test_failed_approval_persistence_does_not_leave_business_effect(client, monkeypatch):
    project, conversation = seed(client)
    call = ToolCall(
        call_id="create",
        name="create_entity",
        arguments='{"type":"character","name":"原子批准标记"}',
    )
    raw = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
        ],
    }
    capture = Capture(
        [AssistantTurn(content=None, tool_calls=[call], raw=raw), AssistantTurn(content="请批准")]
    )
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    assert "event: done" in chat(client, conversation)
    response = client.get("/api/agent/pending-writes", params={"conversation_id": conversation})
    assert response.status_code == 200
    pending = response.json()
    assert len(pending) == 1

    async def fail_save(*args):
        raise RuntimeError("injected failure after domain service returns")

    monkeypatch.setattr(repository, "save_pending", fail_save)
    response = client.post(
        "/api/agent/pending-writes/approve",
        json={
            "conversation_id": conversation,
            "ids": [pending[0]["id"]],
        },
    )
    assert response.status_code == 200
    assert len(response.json()["failed"]) == 1
    response = client.get("/api/entities", params={"project_id": project})
    assert response.status_code == 200
    require_acceptance("原子批准标记" not in response.text, "failed approval left entity committed")


def test_user_edit_between_read_and_registration_cannot_be_overwritten(client, monkeypatch):
    # Isolate the C-stage concurrency defect from B request-admission behavior.
    monkeypatch.setattr(get_settings(), "agent_context_max_tokens", 100000)
    project, conversation = seed(client)
    response = client.post("/api/agent/memory-docs", params={"project_id": project})
    assert response.status_code == 201
    doc = response.json()
    section = doc["sections"][0]
    calls = [
        ToolCall(
            call_id="read",
            name="read_doc_section",
            arguments=json.dumps(
                {
                    "doc_id": doc["id"],
                    "seq": section["seq"],
                }
            ),
        ),
        ToolCall(
            call_id="write",
            name="write_doc_section",
            arguments=json.dumps(
                {
                    "doc_id": doc["id"],
                    "seq": section["seq"],
                    "content": "模型依据旧版生成",
                }
            ),
        ),
    ]
    turns = [
        AssistantTurn(
            content=None,
            tool_calls=[call],
            raw={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                ],
            },
        )
        for call in calls
    ]
    monkeypatch.setattr(llm, "stream_chat_turn", Capture([*turns, AssistantTurn(content="请确认")]))
    original_execute = tools.execute_tool
    read_then_edited = []

    async def execute(name, arguments, ctx):
        result = await original_execute(name, arguments, ctx)
        if name == "read_doc_section":
            # A second real DB session commits the user edit after the model's read.
            async with db.get_session_factory()() as user_session:
                updated = await documents.update_section(
                    user_session,
                    doc["id"],
                    section["id"],
                    SectionUpdate(
                        content="用户刚刚保存的新版", expected_version=section["version"]
                    ),
                    updated_by="user",
                )
                read_then_edited.append(updated.version)
        return result

    monkeypatch.setattr(tools, "execute_tool", execute)
    assert "event: done" in chat(client, conversation)
    assert read_then_edited == [section["version"] + 1]
    pending_response = client.get(
        "/api/agent/pending-writes",
        params={
            "conversation_id": conversation,
        },
    )
    assert pending_response.status_code == 200
    pending = pending_response.json()
    if pending:
        response = client.post(
            "/api/agent/pending-writes/approve",
            json={
                "conversation_id": conversation,
                "ids": [item["id"] for item in pending],
            },
        )
        assert response.status_code == 200
    response = client.get(f"/api/agent/memory-docs/{doc['id']}")
    assert response.status_code == 200
    current = next(item for item in response.json()["sections"] if item["id"] == section["id"])
    require_acceptance(current["content"] == "用户刚刚保存的新版", "stale read overwrote user edit")
