"""D-slice evidence for durable chat runs, replay, idempotency, and cancellation."""

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import llm
from app.agent.llm import AssistantTurn

pytestmark = pytest.mark.integration


def _project_and_conversation(client: TestClient) -> str:
    project = client.post("/api/projects", json={"name": "D 阶段"}).json()
    response = client.post("/api/agent/sessions", params={"project_id": project["id"]}, json={})
    assert response.status_code == 201
    return str(response.json()["id"])


def _events(response_text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    event = ""
    for line in response_text.splitlines():
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            import json

            result.append({"event": event, "data": json.loads(line.removeprefix("data: "))})
    return result


def test_run_is_idempotent_queryable_and_replayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversation_id = _project_and_conversation(client)

    async def provider(*args: Any, **kwargs: Any):
        yield "content_delta", "持久回复"
        yield "turn", AssistantTurn(content="持久回复")

    monkeypatch.setattr(llm, "stream_chat_turn", provider)
    body = {
        "conversation_id": conversation_id,
        "request_id": "req-d-idempotent",
        "message": "只保存一次",
        "perspective": "author",
    }
    first = client.post("/api/agent/chat", json=body)
    assert first.status_code == 200
    frames = _events(first.text)
    assert frames[-1]["event"] == "done"
    assert [frame["data"]["seq"] for frame in frames] == list(range(1, len(frames) + 1))
    run_id = frames[0]["data"]["run_id"]
    assert all(frame["data"]["run_id"] == run_id for frame in frames)

    status = client.get(
        "/api/agent/runs/lookup",
        params={"conversation_id": conversation_id, "request_id": "req-d-idempotent"},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    replay = client.get(f"/api/agent/runs/{run_id}/events", params={"after_seq": 1}).json()
    assert replay and replay[0]["seq"] == 2

    second = client.post("/api/agent/chat", json=body)
    assert second.status_code == 200
    assert _events(second.text) == frames
    messages = client.get(f"/api/agent/sessions/{conversation_id}/messages").json()
    assert [(row["role"], row["content"]) for row in messages] == [
        ("user", "只保存一次"),
        ("assistant", "持久回复"),
    ]

    conflicting = client.post("/api/agent/chat", json={**body, "message": "不同内容"})
    assert conflicting.status_code == 409


def test_server_cancel_persists_terminal_state_and_closes_worker(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversation_id = _project_and_conversation(client)

    async def slow_provider(*args: Any, **kwargs: Any):
        import asyncio

        yield "content_delta", "部分"
        await asyncio.sleep(30)
        yield "turn", AssistantTurn(content="不应完成")

    monkeypatch.setattr(llm, "stream_chat_turn", slow_provider)
    result: dict[str, Any] = {}

    def post_chat() -> None:
        result["response"] = client.post(
            "/api/agent/chat",
            json={
                "conversation_id": conversation_id,
                "request_id": "req-d-cancel",
                "message": "停止它",
                "perspective": "author",
            },
        )

    thread = threading.Thread(target=post_chat, daemon=True)
    thread.start()
    run: dict[str, Any] | None = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/agent/sessions/{conversation_id}/runs/latest")
        if response.status_code == 200 and response.json() is not None:
            run = response.json()
            if run["status"] == "running":
                break
        time.sleep(0.02)
    assert run is not None and run["status"] == "running"

    cancelled = client.post(f"/api/agent/runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert _events(result["response"].text)[-1]["data"]["code"] == "RUN_CANCELLED"
    messages = client.get(f"/api/agent/sessions/{conversation_id}/messages").json()
    assert [(row["role"], row["content"]) for row in messages] == [("user", "停止它")]
