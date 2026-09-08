"""F10 L3 E2E：agent 跨模块全链路（TestClient 公开接口，LLM mock）。

验证依据: docs/tests/F10_agent_chat.md E1–E2 —
    - E1: 对话 → 草案 → 确认 → 图谱查询全链路（agent+entities+relations+
      perspectives+projects 协作）
    - E2: 用户手改记忆文档后 agent 读到新内容；基于旧版本的 agent patch
      被冲突拒绝（记忆冲突边界语义端到端）
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import llm as agent_llm
from app.agent.llm import AssistantTurn

pytestmark = pytest.mark.e2e


class ChatCapture:
    """stream_chat_turn 捕获桩（与集成测试同型；e2e 内独立定义避免跨层 import）。

    脚本项 AssistantTurn 自动展开为 content_delta + turn 事件（F13 流式协议）。
    """

    def __init__(self, script: list[AssistantTurn]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, system: str, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        self.calls.append({"system": system, "messages": messages, **kwargs})
        turn = self.script.pop(0)
        if turn.content:
            yield ("content_delta", turn.content)
        yield ("turn", turn)

    def prompt_text(self, call_index: int = 0) -> str:
        """拼接某次调用的完整 prompt 文本。"""
        call = self.calls[call_index]
        return (
            call["system"] + "\n" + "\n".join(str(m.get("content", "")) for m in call["messages"])
        )


def _parse_events(text: str) -> list[dict[str, Any]]:
    """解析 SSE 响应为事件列表。"""
    import json

    events: list[dict[str, Any]] = []
    name = ""
    for line in text.splitlines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append({"event": name, "data": json.loads(line.removeprefix("data: "))})
    return events


def test_e1_chat_propose_confirm_graph_flow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E1: 对话→草案→确认→图谱全链路（跨组件：agent+entities+relations+perspectives+projects）。"""
    project = client.post("/api/projects", json={"name": "海难剧本"}).json()
    pid = project["id"]
    session = client.post("/api/agent/sessions", params={"project_id": pid}, json={}).json()

    # ① 对话：LLM 直接回答（流式桩）
    async def fake_chat(*_a: Any, **_k: Any) -> Any:
        yield ("content_delta", "建议补充一位船医角色。")
        yield ("turn", AssistantTurn(content="建议补充一位船医角色。"))

    monkeypatch.setattr(agent_llm, "stream_chat_turn", fake_chat)
    chat = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "主角团缺一个什么角色？",
            "perspective": "author",
        },
    )
    assert chat.status_code == 200, f"对话失败: {chat.text[:200]}"
    events = _parse_events(chat.text)
    assert events[-1]["event"] == "done", f"对话必须正常收尾: {events[-1]}"

    # ② propose：草案生成
    async def fake_complete_json(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "drafts": [
                {
                    "kind": "entity",
                    "payload": {"type": "character", "name": "周兰", "description": "船医"},
                    "summary": "新增船医周兰",
                }
            ]
        }

    monkeypatch.setattr(agent_llm, "complete_json", fake_complete_json)
    propose = client.post(
        "/api/agent/propose",
        json={"session_id": session["id"], "message": "就加周兰吧", "perspective": "author"},
    )
    assert propose.status_code == 200, f"propose 失败: {propose.text[:200]}"
    draft = propose.json()["drafts"][0]

    # ③ confirm：确认落库
    confirm = client.post(
        "/api/agent/confirm",
        json={
            "session_id": session["id"],
            "items": [
                {
                    "draft_id": draft["draft_id"],
                    "kind": draft["kind"],
                    "payload": draft["payload"],
                    "confirmed": True,
                }
            ],
        },
    )
    assert confirm.status_code == 200, f"confirm 失败: {confirm.text[:200]}"
    assert len(confirm.json()["created"]) == 1, f"必须成功写入: {confirm.json()}"

    # ④ 图谱反映新实体（author 视角）
    graph = client.get("/api/graph", params={"perspective": "author", "project_id": pid}).json()
    node_names = [n["name"] for n in graph["nodes"]]
    assert "周兰" in node_names, f"确认后的实体必须出现在图谱中: {node_names}"


def test_e2_user_edit_then_agent_reads_fresh_and_stale_patch_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2: 用户手改 → agent 下一轮读新内容；旧版本 patch → 409（冲突边界）。"""
    project = client.post("/api/projects", json={"name": "风格项目"}).json()
    pid = project["id"]
    doc = client.post(
        "/api/agent/memory-docs", params={"project_id": pid, "kind": "style"}, json={}
    ).json()
    section = doc["sections"][0]

    # ① 作者手改第一段
    new_content = "全片冷色调，参考《雾中帆影》。"
    patch = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        json={"content": new_content, "expected_version": section["version"]},
    )
    assert patch.status_code == 200, f"用户手改失败: {patch.text[:200]}"
    stale_version = section["version"]

    # ② agent 下一轮对话：prompt 必须以新内容为准
    session = client.post("/api/agent/sessions", params={"project_id": pid}, json={}).json()
    capture = ChatCapture([AssistantTurn(content="明白，冷色调。")])
    monkeypatch.setattr(agent_llm, "stream_chat_turn", capture)
    chat = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "我们定了什么视觉风格？",
            "perspective": "author",
        },
    )
    assert chat.status_code == 200, chat.text[:200]
    prompt = capture.prompt_text(0)
    assert new_content in prompt, (
        f"【问题】agent 读到过期记忆\n【原因】上下文未从库现读文档段\n"
        f"【修复】检查 _assemble_chat_context 的文档段装配\nprompt 尾部: {prompt[-400:]}"
    )

    # ③ 基于旧版本的 agent patch → 409，用户内容原样保留
    conflict = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        params={"updated_by": "agent"},
        json={"content": "agent 的过期改写。", "expected_version": stale_version},
    )
    assert conflict.status_code == 409, f"过期 patch 必须 409: {conflict.status_code}"
    fresh = client.get(f"/api/agent/memory-docs/{doc['id']}").json()
    assert fresh["sections"][0]["content"] == new_content, "用户手改必须原样保留"
    assert fresh["sections"][0]["updated_by"] == "user", "更新者必须仍是 user"
