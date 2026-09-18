"""F long-term memory: provenance, recall, conflict, and forgetting acceptance."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import llm, service
from app.agent.llm import AssistantTurn, ToolCall
from app.config import get_settings

pytestmark = pytest.mark.integration


class Capture:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, system: str, messages: list[dict[str, Any]], **_kwargs: Any) -> Any:
        transcript = "\n".join(str(row.get("content", "")) for row in messages)
        self.prompts.append(system + "\n" + transcript)
        yield ("content_delta", "收到。")
        yield ("turn", AssistantTurn(content="收到。"))


class SourceCapture(Capture):
    def __init__(self, memory_id: str) -> None:
        super().__init__()
        self.memory_id = memory_id

    async def __call__(self, system: str, messages: list[dict[str, Any]], **_kwargs: Any) -> Any:
        transcript = "\n".join(str(row.get("content", "")) for row in messages)
        self.prompts.append(system + "\n" + transcript)
        if len(self.prompts) == 1:
            yield (
                "turn",
                AssistantTurn(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            call_id="memory-source-1",
                            name="read_conversation_sources",
                            arguments=f'{{"memory_id":"{self.memory_id}"}}',
                        )
                    ],
                ),
            )
            return
        yield ("content_delta", "已核对来源。")
        yield ("turn", AssistantTurn(content="已核对来源。"))


def _project(client: TestClient, name: str) -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


def _conversation(client: TestClient, project_id: str) -> str:
    response = client.post("/api/agent/sessions", params={"project_id": project_id}, json={})
    assert response.status_code == 201
    return str(response.json()["id"])


def _chat(
    client: TestClient,
    conversation_id: str,
    text: str,
    *,
    perspective: str = "author",
    character_id: str = "",
) -> None:
    response = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": conversation_id,
            "message": text,
            "perspective": perspective,
            "character_id": character_id,
        },
    )
    assert response.status_code == 200
    assert "event: done" in response.text, response.text


def test_candidate_requires_acceptance_before_cross_session_recall(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = Capture()
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    project_id = _project(client, "跨会话记忆")
    first = _conversation(client, project_id)
    second = _conversation(client, project_id)

    _chat(client, first, "结局必须保持开放。")
    memories = client.get("/api/agent/memories", params={"project_id": project_id}).json()
    assert len(memories) == 1
    proposed = memories[0]
    assert proposed["status"] == "proposed"
    assert proposed["origin"] == "model_suggestion"
    assert proposed["sources"][0]["conversation_id"] == first

    _chat(client, second, "当前应遵守什么结局约束？")
    assert "已接受的跨会话项目记忆" not in capture.prompts[-1]

    accepted = client.post(
        f"/api/agent/memories/{proposed['id']}/accept",
        json={"expected_version": proposed["version"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    stale = client.post(
        f"/api/agent/memories/{proposed['id']}/accept",
        json={"expected_version": proposed["version"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_version"] == accepted.json()["version"]

    source_capture = SourceCapture(proposed["id"])
    monkeypatch.setattr(llm, "stream_chat_turn", source_capture)
    roomy_settings = get_settings().model_copy(update={"agent_context_max_tokens": 12000})
    monkeypatch.setattr(service, "get_settings", lambda: roomy_settings)
    third = _conversation(client, project_id)
    _chat(client, third, "当前应遵守什么结局约束？")
    assert "已接受的跨会话项目记忆" in source_capture.prompts[0]
    assert "结局必须保持开放" in source_capture.prompts[0]
    assert proposed["sources"][0]["source_id"] in source_capture.prompts[0]
    assert "结局必须保持开放" in source_capture.prompts[1]


def test_conflict_is_disputed_until_author_resolves(client: TestClient) -> None:
    project_id = _project(client, "冲突记忆")
    base = {
        "project_id": project_id,
        "context_key": "author",
        "kind": "decision",
        "subject_key": "结局",
    }
    first = client.post("/api/agent/memories", json={**base, "content": "结局采用开放式。"}).json()
    second_response = client.post(
        "/api/agent/memories", json={**base, "content": "结局采用封闭式。"}
    )
    assert second_response.status_code == 201
    second = second_response.json()
    rows = client.get("/api/agent/memories", params={"project_id": project_id}).json()
    assert {row["status"] for row in rows} == {"disputed"}

    resolved = client.post(
        f"/api/agent/memories/{second['id']}/resolve",
        json={"expected_version": second["version"]},
    )
    assert resolved.status_code == 200
    rows = client.get("/api/agent/memories", params={"project_id": project_id}).json()
    by_id = {row["id"]: row for row in rows}
    assert by_id[second["id"]]["status"] == "accepted"
    assert by_id[first["id"]]["status"] == "superseded"


def test_forgetting_creates_tombstone_and_prevents_reextraction(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = Capture()
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    project_id = _project(client, "遗忘记忆")
    first = _conversation(client, project_id)
    text = "对白只能使用短句。"
    _chat(client, first, text)
    memory = client.get("/api/agent/memories", params={"project_id": project_id}).json()[0]

    preview = client.get(f"/api/agent/memories/{memory['id']}/deletion-preview")
    assert preview.status_code == 200
    assert preview.json()["source_count"] == 1
    deleted = client.delete(
        f"/api/agent/memories/{memory['id']}",
        params={"expected_version": memory["version"]},
    )
    assert deleted.status_code == 204

    second = _conversation(client, project_id)
    _chat(client, second, text)
    assert client.get("/api/agent/memories", params={"project_id": project_id}).json() == []


def test_conversation_delete_retains_accepted_but_removes_unaccepted_derivation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = Capture()
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    project_id = _project(client, "会话删除")

    proposed_conversation = _conversation(client, project_id)
    _chat(client, proposed_conversation, "场景必须发生在雨夜。")
    proposed = client.get("/api/agent/memories", params={"project_id": project_id}).json()[0]
    preview = client.get(
        f"/api/agent/sessions/{proposed_conversation}/memory-deletion-preview"
    ).json()
    assert preview["derived_deleted"] == [proposed["id"]]
    assert client.delete(f"/api/agent/sessions/{proposed_conversation}").status_code == 204
    assert client.get("/api/agent/memories", params={"project_id": project_id}).json() == []

    accepted_conversation = _conversation(client, project_id)
    _chat(client, accepted_conversation, "主角必须拒绝王位。")
    accepted = client.get("/api/agent/memories", params={"project_id": project_id}).json()[0]
    accepted = client.post(
        f"/api/agent/memories/{accepted['id']}/accept",
        json={"expected_version": accepted["version"]},
    ).json()
    assert client.delete(f"/api/agent/sessions/{accepted_conversation}").status_code == 204
    rows = client.get("/api/agent/memories", params={"project_id": project_id}).json()
    assert rows[0]["id"] == accepted["id"] and rows[0]["status"] == "accepted"
    assert rows[0]["sources"] == []


def test_project_and_character_scope_never_pollute_author_preference(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = Capture()
    monkeypatch.setattr(llm, "stream_chat_turn", capture)
    project_a = _project(client, "作用域甲")
    project_b = _project(client, "作用域乙")
    character = client.post(
        "/api/entities",
        json={"project_id": project_a, "type": "character", "name": "阿青"},
    ).json()
    conversation = _conversation(client, project_a)
    _chat(
        client,
        conversation,
        "我喜欢红色。",
        perspective="character",
        character_id=character["id"],
    )
    memory = client.get("/api/agent/memories", params={"project_id": project_a}).json()[0]
    assert memory["context_key"] == f"character:{character['id']}"
    accepted = client.post(
        f"/api/agent/memories/{memory['id']}/accept",
        json={"expected_version": memory["version"]},
    )
    assert accepted.status_code == 200
    assert client.get("/api/agent/memories", params={"project_id": project_b}).json() == []

    author_conversation = _conversation(client, project_a)
    _chat(client, author_conversation, "作者偏好是什么？")
    assert "我喜欢红色" not in capture.prompts[-1]
