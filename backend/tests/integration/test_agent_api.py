"""F10 L2 集成测试：agent API 全链路（真实临时库，LLM mock）。

验证依据: docs/features.md F10 + docs/tests/F10_agent_chat.md I1–I11 —
    - 会话/消息/记忆文档持久化与项目隔离
    - SSE 对话事件协议与消息落库
    - 视角过滤注入断言（三视角 prompt 捕获——关键安全用例）
    - propose → confirm 两段式落库（会话归属项目服务端注入）
    - 记忆文档段级 CAS（409）与 HTML 转义
    - 项目级联删除清理 agent 四表
    - LLM 降级路径（502 三要素）与工具检索轮
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import llm as agent_llm
from app.agent.llm import AssistantTurn, ToolCall

pytestmark = pytest.mark.integration


# ---- SSE 解析与 LLM mock 助手 ----


def _parse_sse(text: str) -> list[dict[str, Any]]:
    """把 SSE 响应文本解析为事件列表（event + data）。

    参数: text — 响应体全文。返回值: list[dict]。异常: AssertionError — 帧格式非法。
    """
    events: list[dict[str, Any]] = []
    event_name = ""
    for line in text.splitlines():
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            import json

            events.append({"event": event_name, "data": json.loads(line.removeprefix("data: "))})
    return events


class ChatCapture:
    """chat_turn 捕获桩：记录每次调用的 system/messages/tools，按脚本回放。"""

    def __init__(self, script: list[AssistantTurn]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, system: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> AssistantTurn:
        self.calls.append({"system": system, "messages": messages, **kwargs})
        return self.script.pop(0)

    def prompt_text(self, call_index: int = 0) -> str:
        """拼接某次调用的完整 prompt 文本（注入断言用）。"""
        call = self.calls[call_index]
        return (
            call["system"] + "\n" + "\n".join(str(m.get("content", "")) for m in call["messages"])
        )


@pytest.fixture
def llm_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """预留夹具位（各用例自行经 _install_chat_script 注入脚本）。"""
    return None


def _install_chat_script(
    monkeypatch: pytest.MonkeyPatch, script: list[AssistantTurn]
) -> ChatCapture:
    """把捕获桩接入 llm.chat_turn（service 经模块属性动态取用）。"""
    capture = ChatCapture(script)
    monkeypatch.setattr(agent_llm, "chat_turn", capture)
    return capture


def _create_project(client: TestClient, name: str) -> dict[str, Any]:
    """经公开接口创建项目。"""
    resp = client.post("/api/projects", json={"name": name})
    assert resp.status_code == 201, f"项目创建失败: {resp.status_code} {resp.text}"
    return resp.json()


def _create_entity(client: TestClient, name: str, project_id: str, **extra: Any) -> dict[str, Any]:
    """经公开接口创建实体。"""
    payload: dict[str, Any] = {"type": "character", "name": name, "project_id": project_id}
    payload.update(extra)
    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == 201, f"实体创建失败: {resp.status_code} {resp.text}"
    return resp.json()


def _create_session(client: TestClient, project_id: str) -> dict[str, Any]:
    """经公开接口创建会话。"""
    resp = client.post("/api/agent/sessions", params={"project_id": project_id}, json={})
    assert resp.status_code == 201, f"会话创建失败: {resp.status_code} {resp.text}"
    return resp.json()


# ---- 用例 ----


def test_sessions_project_isolation(client: TestClient) -> None:
    """I1: 会话创建 201 + 列表按项目隔离（双项目互不可见）。"""
    project_a = _create_project(client, "项目A")
    project_b = _create_project(client, "项目B")
    session_a = _create_session(client, project_a["id"])

    assert session_a["id"].startswith("conv-"), f"会话 id 必须系统生成: {session_a}"
    assert session_a["project_id"] == project_a["id"]

    list_a = client.get("/api/agent/sessions", params={"project_id": project_a["id"]}).json()
    list_b = client.get("/api/agent/sessions", params={"project_id": project_b["id"]}).json()
    assert [s["id"] for s in list_a] == [session_a["id"]], f"项目A 列表应含该会话: {list_a}"
    assert list_b == [], f"项目B 列表必须为空（项目隔离）: {list_b}"


def test_chat_sse_persists_messages(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """I2: SSE 全链路 → 事件流含 message_start/token/done，消息双行落库。"""
    project = _create_project(client, "剧本项目")
    session = _create_session(client, project["id"])
    capture = _install_chat_script(
        monkeypatch, [AssistantTurn(content="这是一个关于海难与救赎的故事。")]
    )

    resp = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "帮我起个故事头",
            "perspective": "author",
        },
    )
    assert resp.status_code == 200, f"chat 失败: {resp.status_code} {resp.text[:300]}"
    events = _parse_sse(resp.text)
    names = [e["event"] for e in events]

    assert names[0] == "message_start" and names[-1] == "done", f"事件首尾不符: {names}"
    assert "error" not in names, (
        f"正常链路不得出现 error: {[e for e in events if e['event'] == 'error']}"
    )
    token_text = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "海难" in token_text, f"token 流必须还原全文: {token_text}"

    messages = client.get(f"/api/agent/sessions/{session['id']}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"], (
        f"user+assistant 必须落库: {messages}"
    )
    # 本轮用户消息在 prompt 中恰好一次（flush 可见行 + 显式追加曾致双份注入）
    user_contents = [
        m.get("content") for m in capture.calls[0]["messages"] if m.get("role") == "user"
    ]
    assert user_contents.count("帮我起个故事头") == 1, f"本轮输入必须恰好注入一次: {user_contents}"
    # 首条消息回填标题（OQ-7）
    sessions = client.get("/api/agent/sessions", params={"project_id": project["id"]}).json()
    assert sessions[0]["title"].startswith("帮我起个故事头"), f"标题须取首条消息: {sessions[0]}"


def test_perspective_filters_prompt_injection_surface(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I3 参数化: 三视角下 prompt 的可见/排除集合（关键安全用例，E05 范式钉死）。

    世界: 项目 P；周兰（audience_known）与沈墨（秘密角色）、青云山（location）；
    关系 周兰-居住->青云山（known_by=[周兰]）；周兰为视角角色时：
    周兰/青云山可见，沈墨必须被排除。
    """
    project = _create_project(client, "视角项目")
    pid = project["id"]
    zhou = _create_entity(client, "周兰", pid, audience_known=True)
    _create_entity(client, "沈墨", pid)  # audience 不可见、周兰视角不可见
    _create_entity(client, "青云山", pid, type="location")
    rel_resp = client.post(
        "/api/relations",
        json={
            "type": "LIVES",
            "source": zhou["id"],
            "target": [
                e["id"]
                for e in client.get("/api/entities", params={"project_id": pid}).json()
                if e["name"] == "青云山"
            ][0],
            "known_by": [zhou["id"]],
            "project_id": pid,
        },
    )
    assert rel_resp.status_code == 201, f"关系创建失败: {rel_resp.text}"

    session = _create_session(client, pid)
    capture = _install_chat_script(monkeypatch, [AssistantTurn(content="ok")])

    resp = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "介绍当前局面",
            "perspective": "character",
            "character_id": zhou["id"],
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    character_prompt = capture.prompt_text(0)
    assert "周兰" in character_prompt, "视角角色自身必须可见"
    assert "青云山" in character_prompt, "known_by 命中的实体必须可见"
    assert "沈墨" not in character_prompt, (
        f"【问题】character 视角 prompt 泄露不可见实体\n"
        f"【原因】上下文组装未严格经视角过滤\n【修复】检查 perspectives 过滤链路\n"
        f"prompt: {character_prompt[:400]}"
    )

    # author 视角：全量可见
    _ = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "介绍当前局面",
            "perspective": "author",
        },
    )
    assert "沈墨" in capture.prompt_text(1), "author 视角必须包含秘密角色"

    # audience 视角：仅 audience_known
    _ = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "介绍当前局面",
            "perspective": "audience",
        },
    )
    audience_prompt = capture.prompt_text(2)
    assert "周兰" in audience_prompt and "沈墨" not in audience_prompt, (
        f"audience 视角只含 audience_known 实体: {audience_prompt[:400]}"
    )


def test_propose_then_confirm_writes_graph(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I4: propose → 草案 → confirm → 实体/关系真实落库（两段式闭环）。"""
    project = _create_project(client, "写入项目")
    pid = project["id"]
    session = _create_session(client, pid)
    zhou = _create_entity(client, "周兰", pid)

    async def fake_complete_json(_system: str, _msgs: list, **_: Any) -> dict[str, Any]:
        return {
            "drafts": [
                {
                    "kind": "entity",
                    "payload": {
                        "type": "character",
                        "name": "沈墨",
                        "description": "神秘船客",
                    },
                    "summary": "新增神秘船客",
                },
                {
                    "kind": "relation",
                    "payload": {
                        "type": "ALLIES",
                        "source": zhou["id"],
                        "target": "pending",
                    },
                    "summary": "结盟关系",
                },
            ]
        }

    monkeypatch.setattr(agent_llm, "complete_json", fake_complete_json)
    propose = client.post(
        "/api/agent/propose",
        json={
            "session_id": session["id"],
            "message": "加一个盟友",
            "perspective": "author",
        },
    )
    assert propose.status_code == 200, f"propose 失败: {propose.status_code} {propose.text[:300]}"
    drafts = propose.json()["drafts"]
    assert len(drafts) == 2 and drafts[0]["draft_id"].startswith("draft-"), f"草案不符: {drafts}"

    # 实体草案确认（payload 未带 project_id——服务端必须以会话归属项目注入）
    confirm = client.post(
        "/api/agent/confirm",
        json={
            "session_id": session["id"],
            "items": [
                {
                    "draft_id": drafts[0]["draft_id"],
                    "kind": "entity",
                    "payload": drafts[0]["payload"],
                    "confirmed": True,
                },
                {
                    "draft_id": drafts[1]["draft_id"],
                    "kind": "entity",
                    "payload": drafts[0]["payload"],
                    "confirmed": False,
                },
            ],
        },
    )
    assert confirm.status_code == 200, f"confirm 失败: {confirm.text[:300]}"
    result = confirm.json()
    assert len(result["created"]) == 1 and result["failed"] == [], f"确认结果不符: {result}"

    entities = client.get("/api/entities", params={"project_id": pid}).json()
    names = [e["name"] for e in entities]
    assert "沈墨" in names, f"确认后的实体必须落库到会话归属项目: {names}"


def test_confirm_rejects_tampered_payload_and_bad_kind(
    client: TestClient,
) -> None:
    """I5: 篡改 payload → 200+failed（服务端复核拒落库）；未知 kind → 422。"""
    project = _create_project(client, "复核项目")
    session = _create_session(client, project["id"])

    tampered = client.post(
        "/api/agent/confirm",
        json={
            "session_id": session["id"],
            "items": [
                {
                    "draft_id": "d-1",
                    "kind": "entity",
                    "payload": {"type": "not-a-type", "name": "越权实体"},
                    "confirmed": True,
                }
            ],
        },
    )
    assert tampered.status_code == 200, f"复核失败应折叠而非 5xx: {tampered.text[:300]}"
    result = tampered.json()
    assert result["created"] == [] and len(result["failed"]) == 1, f"必须拒落库: {result}"
    assert "校验" in result["failed"][0]["reason"] or "类型" in result["failed"][0]["reason"], (
        f"失败原因须可读: {result['failed']}"
    )
    entities = client.get("/api/entities", params={"project_id": project["id"]}).json()
    assert entities == [], "被篡改载荷绝不能落库"

    bad_kind = client.post(
        "/api/agent/confirm",
        json={
            "session_id": session["id"],
            "items": [{"draft_id": "d-2", "kind": "weapon", "payload": {}, "confirmed": True}],
        },
    )
    assert bad_kind.status_code == 422, f"未知 kind 必须被请求校验拦截: {bad_kind.status_code}"


def test_memory_doc_section_cas_conflict(client: TestClient) -> None:
    """I6: 文档模板建档 → 段 PATCH（版本递增）→ 旧版本 PATCH → 409 且内容不变。"""
    project = _create_project(client, "文档项目")
    create = client.post(
        "/api/agent/memory-docs",
        params={"project_id": project["id"]},
        json=None,
    )
    assert create.status_code == 201, f"建档失败: {create.text[:300]}"
    doc = create.json()
    assert doc["kind"] in ("positioning", "style") and len(doc["sections"]) >= 3, (
        f"模板初始段必须生成: {doc}"
    )
    kind = doc["kind"]

    listing = client.get("/api/agent/memory-docs", params={"project_id": project["id"]}).json()
    assert [d["id"] for d in listing] == [doc["id"]], f"列表应含新文档: {listing}"

    section = doc["sections"][0]
    patch = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        json={"content": "三部曲长篇，每部约 12 集。", "expected_version": section["version"]},
    )
    assert patch.status_code == 200, f"段更新失败: {patch.text[:300]}"
    updated = patch.json()
    assert updated["version"] == section["version"] + 1 and updated["updated_by"] == "user", (
        f"版本必须递增且 updated_by=user: {updated}"
    )

    stale = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        json={"content": "基于旧版本的覆盖。", "expected_version": section["version"]},
    )
    assert stale.status_code == 409, f"CAS 冲突必须 409: {stale.status_code} {stale.text[:200]}"
    fresh = client.get(f"/api/agent/memory-docs/{doc['id']}").json()
    assert fresh["sections"][0]["content"] == "三部曲长篇，每部约 12 集。", (
        "冲突后内容必须保持用户最新版（绝不覆盖）"
    )
    assert kind in ("positioning", "style")


def test_memory_doc_page_escapes_payload(client: TestClient) -> None:
    """I7: HTML 页端点返回 text/html 且注入载荷全转义。"""
    project = _create_project(client, "页面项目")
    doc = client.post(
        "/api/agent/memory-docs", params={"project_id": project["id"]}, json=None
    ).json()
    section = doc["sections"][0]
    client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/{section['id']}",
        json={"content": "<script>alert('xss')</script>", "expected_version": section["version"]},
    )

    page = client.get(f"/api/agent/memory-docs/{doc['id']}/page")
    assert page.status_code == 200, f"页面获取失败: {page.status_code}"
    assert page.headers["content-type"].startswith("text/html"), "必须以 text/html 返回"
    body = page.text
    assert "<script>" not in body and "&lt;script&gt;" in body, f"载荷必须全转义: {body[:300]}"


def test_project_delete_cascades_agent_data(client: TestClient) -> None:
    """I8: 删除项目 → 该项目会话/消息/记忆文档全部清理，他项目不受影响。"""
    keep = _create_project(client, "保留项目")
    victim = _create_project(client, "受害项目")
    session = _create_session(client, victim["id"])
    doc = client.post(
        "/api/agent/memory-docs", params={"project_id": victim["id"]}, json=None
    ).json()

    resp = client.delete(f"/api/projects/{victim['id']}")
    assert resp.status_code == 204, f"项目删除失败: {resp.text[:200]}"

    # 项目行已删：其列表端点 404（项目维度校验先于列表查询）
    sessions_resp = client.get("/api/agent/sessions", params={"project_id": victim["id"]})
    assert sessions_resp.status_code == 404, "项目删除后会话列表必须 404（项目不存在）"
    messages = client.get(f"/api/agent/sessions/{session['id']}/messages")
    assert messages.status_code == 404, "会话行删除后消息入口必须 404"
    doc_resp = client.get(f"/api/agent/memory-docs/{doc['id']}")
    assert doc_resp.status_code == 404, "记忆文档必须被级联清理"
    kept_sessions = client.get("/api/agent/sessions", params={"project_id": keep["id"]}).json()
    assert kept_sessions == [], "保留项目不受影响"


def test_agent_404s_for_missing_resources(client: TestClient) -> None:
    """I9: 不存在的会话/文档/段路径 → 404 三要素（无效等价类兜底）。"""
    missing_messages = client.get("/api/agent/sessions/conv-nope/messages")
    assert missing_messages.status_code == 404, "不存在会话必须 404"
    assert missing_messages.json()["problem"] == "会话不存在", (
        f"problem 须锁全文（E05）: {missing_messages.json()}"
    )

    missing_doc = client.get("/api/agent/memory-docs/mdoc-nope")
    assert missing_doc.status_code == 404, "不存在文档必须 404"
    assert missing_doc.json()["problem"] == "记忆文档不存在", (
        f"三要素必须齐全: {missing_doc.json()}"
    )

    project = _create_project(client, "404项目")
    doc = client.post(
        "/api/agent/memory-docs", params={"project_id": project["id"]}, json=None
    ).json()
    section = doc["sections"][0]
    cross = client.patch(
        f"/api/agent/memory-docs/{doc['id']}/sections/msec-other-doc",
        json={"content": "x", "expected_version": section["version"]},
    )
    assert cross.status_code == 404, f"段与文档不匹配必须 404: {cross.status_code}"
    assert cross.json()["problem"] == "文档段不存在", f"三要素必须齐全: {cross.json()}"


@pytest.mark.parametrize(
    ("failure", "label"),
    [
        ("missing_key", "LLM_API_KEY 未配置"),
        ("endpoint_down", "端点失败"),
    ],
    ids=["未配置降级", "端点失败降级"],
)
def test_llm_failure_degrades_with_three_elements(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: str, label: str
) -> None:
    """I10 参数化: LLM 降级两态 → propose 502 且三要素完整。"""
    from app.core.exceptions import AgentError

    if failure == "missing_key":

        class _NoKeySettings:
            llm_api_key = ""
            llm_base_url = "https://example.invalid/v1"
            llm_model = "m"
            llm_model_light = "m"
            llm_timeout_seconds = 5

        monkeypatch.setattr(agent_llm, "get_settings", lambda: _NoKeySettings())
    else:

        async def boom(*_a: Any, **_k: Any) -> AssistantTurn:
            raise AgentError(
                problem="LLM 调用失败（APITimeoutError）",
                cause="模型 m 的补全请求超时",
                fix="重试或调大 LLM_TIMEOUT_SECONDS",
            )

        monkeypatch.setattr(agent_llm, "chat_turn", boom)

    project = _create_project(client, f"降级项目-{label}")
    session = _create_session(client, project["id"])
    resp = client.post(
        "/api/agent/propose",
        json={"session_id": session["id"], "message": "x", "perspective": "author"},
    )
    assert resp.status_code == 502, f"[{label}] 降级必须 502: {resp.status_code} {resp.text[:200]}"
    body = resp.json()
    assert body["code"] == "AGENT_FAILURE", f"[{label}] 错误码必须为 AGENT_FAILURE: {body}"
    # E05 范式：problem 按分支锁具体文案（文案变异在此被杀）
    if failure == "missing_key":
        expected_problem = "LLM 客户端不可用：API 密钥未配置"
    else:
        expected_problem = "LLM 调用失败（APITimeoutError）"
    assert body["problem"] == expected_problem, f"[{label}] problem 须锁全文: {body}"
    assert body["cause"] and body["fix"], f"[{label}] cause/fix 必须齐全: {body}"


def test_chat_tool_round_with_real_retrieval(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I11: 工具检索轮 → tool 事件推送，真实检索结果进入后续 prompt。"""
    project = _create_project(client, "检索项目")
    pid = project["id"]
    _create_entity(client, "青铜镜", pid, type="item")
    session = _create_session(client, pid)

    capture = ChatCapture(
        [
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(call_id="call-1", name="search_entities", arguments='{"q": "青铜"}')
                ],
            ),
            AssistantTurn(content="找到了青铜镜。"),
        ]
    )
    monkeypatch.setattr(agent_llm, "chat_turn", capture)

    resp = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "项目里有什么道具？",
            "perspective": "author",
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    events = _parse_sse(resp.text)
    names = [e["event"] for e in events]
    assert names.count("tool") == 2, f"tool start/done 事件必须推送: {names}"
    tool_events = [e for e in events if e["event"] == "tool"]
    assert tool_events[0]["data"]["name"] == "search_entities", "工具名必须透出"

    assert len(capture.calls) == 2, f"工具轮+作答轮共两次调用: {len(capture.calls)}"
    second_prompt = capture.prompt_text(1)
    assert "青铜镜" in second_prompt and "工具 search_entities 结果" in second_prompt, (
        f"真实检索结果必须以数据块进入作答轮 prompt: {second_prompt[-400:]}"
    )
    assert names[-1] == "done", f"正常收尾: {names}"


def test_chat_llm_failure_error_event_keeps_user_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I12: chat LLM 失败 → SSE error 事件（三要素）+ 用户消息与标题回填保留。

    设计依据: 等价类-无效-LLM 失败路径（用户输入先行提交，回滚不得丢失）。
    """
    from app.core.exceptions import AgentError

    project = _create_project(client, "chat降级项目")
    session = _create_session(client, project["id"])

    async def boom(*_a: Any, **_k: Any) -> AssistantTurn:
        raise AgentError(problem="LLM 调用失败（APITimeoutError）", cause="超时", fix="重试")

    monkeypatch.setattr(agent_llm, "chat_turn", boom)
    resp = client.post(
        "/api/agent/chat",
        json={
            "conversation_id": session["id"],
            "message": "帮我写第一幕",
            "perspective": "author",
        },
    )
    assert resp.status_code == 200, "SSE 端点本身必须 200（失败以 error 事件承载）"
    events = _parse_sse(resp.text)
    assert events[0]["event"] == "message_start", f"首事件不符: {events[0]}"
    assert events[-1]["event"] == "error", f"失败轮必须以 error 收尾: {events[-1]}"
    payload = events[-1]["data"]
    assert payload["code"] == "AGENT_FAILURE", f"错误码必须为 AGENT_FAILURE: {payload}"
    assert payload["problem"] == "LLM 调用失败（APITimeoutError）", f"problem 须锁全文: {payload}"
    assert payload["cause"] and payload["fix"], f"cause/fix 必须齐全: {payload}"

    messages = client.get(f"/api/agent/sessions/{session['id']}/messages").json()
    assert [m["role"] for m in messages] == ["user"], f"用户消息必须保留: {messages}"
    sessions = client.get("/api/agent/sessions", params={"project_id": project["id"]}).json()
    assert sessions[0]["title"].startswith("帮我写第一幕"), f"标题回填必须已提交: {sessions[0]}"
