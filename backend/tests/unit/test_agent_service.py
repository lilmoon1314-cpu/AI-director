"""F10 L1 单元测试：agent 对话主链路（LLM 与仓储全 mock，内存执行）。

覆盖: stream_chat 事件序列/标题截断/工具循环配额与截断/合规拦截/
propose 校验/confirm 部分失败/滚动摘要维护。
用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import llm, repository, service
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.schemas import ConfirmItem, ConfirmRequest, ProposeRequest
from app.core import db
from app.core.exceptions import AgentError, NotFoundError, ValidationError
from app.perspectives import service as perspectives_service
from app.perspectives.schemas import GraphData
from app.projects import service as projects_service

pytestmark = pytest.mark.unit


class AgentSettingsStub:
    """agent 相关配置桩（窗口=2，工具配额=1，截断=50，合规默认关）。"""

    agent_context_max_tokens = 100000
    agent_history_window_messages = 2
    agent_max_tool_calls_per_turn = 1
    agent_tool_output_max_chars = 50
    agent_content_review_enabled = False
    agent_content_review_words = ""
    llm_model = "model-main"
    llm_model_light = "model-light"
    llm_timeout_seconds = 5
    llm_api_key = "sk-test"
    llm_base_url = "https://example.invalid/v1"


class ReviewSettingsStub(AgentSettingsStub):
    """开启合规词表的配置桩。"""

    agent_content_review_enabled = True
    agent_content_review_words = "违禁词, 另一个词"


class Store:
    """内存会话/消息存储（模拟 repository 语义 + flush 默认值）。"""

    def __init__(self) -> None:
        self.conversations: dict[str, Any] = {}
        self.messages: dict[str, list[Any]] = {}
        self.docs_by_project: dict[str, list[Any]] = {}
        self._n = 0

    def next_id(self, prefix: str) -> str:
        """确定性 id。"""
        self._n += 1
        return f"{prefix}-{self._n}"

    def add_conversation(self, conversation: Any) -> Any:
        """登记会话。"""
        self.conversations[conversation.id] = conversation
        return conversation

    def add_message(self, message: Any) -> Any:
        """登记消息（模拟 flush 默认值）。"""
        if message.created_at is None:
            message.created_at = datetime.now(UTC)
        self.messages.setdefault(message.conversation_id, []).append(message)
        return message


def _install(store: Store, monkeypatch: pytest.MonkeyPatch, settings: Any = None) -> None:
    """接线：repository mock + 空图谱 + 项目名 + 配置桩 + 自管理会话桩。"""

    async def fake_add_conversation(_s: Any, conversation: Any) -> Any:
        if conversation.created_at is None:
            conversation.created_at = datetime.now(UTC)
        if conversation.updated_at is None:
            conversation.updated_at = datetime.now(UTC)
        if conversation.summary is None:
            conversation.summary = ""
        return store.add_conversation(conversation)

    async def fake_get_conversation(_s: Any, conversation_id: str) -> Any:
        return store.conversations.get(conversation_id)

    async def fake_save_conversation(_s: Any, conversation: Any) -> Any:
        conversation.updated_at = datetime.now(UTC)
        store.conversations[conversation.id] = conversation
        return conversation

    async def fake_add_message(_s: Any, message: Any) -> Any:
        return store.add_message(message)

    async def fake_list_messages(_s: Any, conversation_id: str) -> list[Any]:
        return list(store.messages.get(conversation_id, []))

    async def fake_list_docs(_s: Any, project_id: str) -> list[Any]:
        return list(store.docs_by_project.get(project_id, []))

    async def fake_get_graph(_s: Any, **_: Any) -> GraphData:
        return GraphData()

    async def fake_project_get(_s: Any, _project_id: str) -> Any:
        return SimpleNamespace(name="测试项目", id=_project_id)

    async def fake_ensure_exists(_s: Any, _project_id: str) -> None:
        return None

    monkeypatch.setattr(repository, "add_conversation", fake_add_conversation)
    monkeypatch.setattr(repository, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(repository, "save_conversation", fake_save_conversation)
    monkeypatch.setattr(repository, "add_message", fake_add_message)
    monkeypatch.setattr(repository, "list_messages", fake_list_messages)
    monkeypatch.setattr(repository, "list_docs", fake_list_docs)
    monkeypatch.setattr(perspectives_service, "get_graph", fake_get_graph)
    monkeypatch.setattr(projects_service, "get", fake_project_get)
    monkeypatch.setattr(projects_service, "ensure_exists", fake_ensure_exists)
    monkeypatch.setattr(service, "get_settings", lambda: settings or AgentSettingsStub())


class _AsyncCtx:
    """async with 会话上下文桩。"""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, *_: Any) -> bool:
        return False


class SessionStub:
    """会话桩：仅 commit/rollback。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        """计数 commit。"""
        self.commits += 1

    async def rollback(self) -> None:
        """计数 rollback。"""
        self.rollbacks += 1


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Store:
    """内存存储 + 全量 mock（每个测试独享）。"""
    store = Store()
    _install(store, monkeypatch)
    stub = SessionStub()
    monkeypatch.setattr(db, "get_session_factory", lambda: lambda: _AsyncCtx(stub))
    store.session_stub = stub  # 暴露给用例断言 commit/rollback 计数
    return store


def _seed_conversation(store: Store, conversation_id: str = "conv-1", title: str = "") -> Any:
    """预置一个会话。"""
    return store.add_conversation(
        SimpleNamespace(
            id=conversation_id,
            project_id="proj-1",
            title=title,
            summary="",
            summary_until_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )


async def test_stream_chat_normal_flow(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """U23: 正常轮 → message_start/token/done 事件齐全，user+assistant 落库。

    设计依据: 等价类-有效会话轮。
    """
    _seed_conversation(store)

    async def fake_chat_turn(*_a: Any, **_k: Any) -> AssistantTurn:
        return AssistantTurn(content="你好，创作者。")

    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)
    events = [evt async for evt in service.stream_chat("conv-1", "介绍项目", perspective="author")]

    names = [e["event"] for e in events]
    assert names[0] == "message_start" and names[-1] == "done", f"事件首尾不符: {names}"
    assert "token" in names and "error" not in names, f"必须有 token 且无 error: {names}"
    token_text = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert token_text == "你好，创作者。", f"token 拼接必须还原全文: {token_text}"
    roles = [m.role for m in store.messages["conv-1"]]
    assert roles == ["user", "assistant"], f"两条消息必须落库: {roles}"


@pytest.mark.parametrize(
    ("first_message", "expected_title"),
    [("短标题", "短标题"), ("一" * 20, "一" * 20), ("一" * 21, "一" * 20)],
    ids=["短消息全取", "恰为上限20", "超上限截断到20"],
)
async def test_title_from_first_message_truncated(
    store: Store, monkeypatch: pytest.MonkeyPatch, first_message: str, expected_title: str
) -> None:
    """U27 参数化: 会话标题取首条用户消息截断（边界值-恰为上限/超 1）。"""

    async def fake_chat_turn(*_a: Any, **_k: Any) -> AssistantTurn:
        return AssistantTurn(content="ok")

    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)
    _seed_conversation(store)

    _ = [evt async for evt in service.stream_chat("conv-1", first_message, perspective="author")]

    assert store.conversations["conv-1"].title == expected_title, (
        f"标题截断不符: {store.conversations['conv-1'].title!r}"
    )


async def test_tool_loop_quota_then_plain_answer(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U16+U17: 工具配额=1 → 首轮允许工具，超限后撤下 tools 强制作答；工具
    输出截断后经注入分隔符进入作答轮 prompt（截断断言即 U17）。

    设计依据: 边界值-配额恰好/超 1（受控 ReAct 防循环）；边界值-输出长度上限。
    """
    _seed_conversation(store)
    calls: list[dict[str, Any]] = []

    async def fake_chat_turn(_system: str, _msgs: list[dict], **kwargs: Any) -> AssistantTurn:
        calls.append({"kwargs": kwargs, "messages": _msgs})
        if kwargs.get("tools"):
            return AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(call_id="call-1", name="search_entities", arguments='{"q": "周兰"}')
                ],
            )
        return AssistantTurn(content="根据检索结果作答。")

    async def fake_execute_tool(name: str, arguments: str, _ctx: Any) -> str:
        return "x" * 500  # 超长输出（上限 50），验证截断（U17）

    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)
    monkeypatch.setattr(service.tools, "execute_tool", fake_execute_tool)

    events = [evt async for evt in service.stream_chat("conv-1", "查周兰", perspective="author")]

    assert len(calls) == 2, f"配额 1 → 恰好两次调用（工具轮+收尾轮）: {len(calls)}"
    assert calls[0]["kwargs"].get("tools") and calls[1]["kwargs"].get("tools") is None, (
        "第二轮必须撤下工具定义（强制作答）"
    )
    # U17: 工具结果截断到上限并带标记，且经注入分隔符包裹（agent_tool_output_max_chars=50）
    tool_msg = next(m for m in calls[1]["messages"] if m.get("role") == "tool")
    marker = "\n[输出已截断：原文 500 字符，上限 50]"
    expected = service.wrap_data("工具 search_entities 结果", "x" * 50 + marker)
    assert tool_msg["content"] == expected, f"截断+包裹必须精确: {tool_msg['content'][:90]}…"
    names = [e["event"] for e in events]
    assert names.count("tool") == 2, f"tool 事件 start+done 各一: {names}"
    assert names[-1] == "done", f"正常收尾: {names}"


async def test_content_review_blocks_before_persist(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U28: 合规开关开启且命中 → error 事件（不落库）；关闭 → 正常（等价类-开关两态）。"""

    async def fake_chat_turn(*_a: Any, **_k: Any) -> AssistantTurn:
        return AssistantTurn(content="ok")

    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)

    _install(store, monkeypatch, settings=ReviewSettingsStub())
    _seed_conversation(store)
    events = [
        evt async for evt in service.stream_chat("conv-1", "包含违禁词的输入", perspective="author")
    ]
    assert events[-1]["event"] == "error", f"命中必须以 error 收尾: {events[-1]}"
    assert events[-1]["data"]["code"] == "CONTENT_REVIEW_BLOCKED", "错误码必须可识别"
    assert len(store.messages.get("conv-1", [])) == 0, "被拦截输入不得落库"

    _install(store, monkeypatch, settings=AgentSettingsStub())
    _seed_conversation(store, "conv-2")
    events2 = [
        evt async for evt in service.stream_chat("conv-2", "包含违禁词的输入", perspective="author")
    ]
    assert events2[-1]["event"] == "done", "开关关闭时同一输入必须正常通过"


async def test_stream_chat_unknown_conversation(store: Store) -> None:
    """U23 补充: 会话不存在 → NotFoundError（首个 yield 前抛出）。"""
    with pytest.raises(NotFoundError):
        _ = [evt async for evt in service.stream_chat("ghost", "hi", perspective="author")]


async def test_rolling_summary_overflow(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """U24: 超窗 → 溢出最旧消息增量压缩进摘要并推进游标（边界值-窗口两侧邻界）。"""

    async def fake_summarize(text: str, _instruction: str) -> str:
        return f"摘要[{text[:10]}]"

    async def fake_chat_turn(*_a: Any, **_k: Any) -> AssistantTurn:
        return AssistantTurn(content="ok")

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)

    conv = _seed_conversation(store)
    # 窗口=2：先造 2 条历史（不溢出），完成本轮后共 4 条 → 溢出 2 条最旧
    for i in range(2):
        store.add_message(
            SimpleNamespace(
                id=f"msg-old-{i}",
                conversation_id="conv-1",
                role="user",
                content=f"历史{i}",
                created_at=datetime.now(UTC),
            )
        )
    events = [evt async for evt in service.stream_chat("conv-1", "新输入", perspective="author")]

    assert events[-1]["event"] == "done", "摘要维护不得破坏正常收尾"
    assert conv.summary.startswith("摘要["), f"摘要必须被更新: {conv.summary!r}"
    assert conv.summary_until_id is not None and conv.summary_until_id.startswith("msg-old"), (
        f"游标必须推进到溢出段末尾: {conv.summary_until_id!r}"
    )


async def test_stream_chat_llm_failure_keeps_user_message(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U29: LLM 失败 → error 事件（三要素）收尾；用户消息已先行提交保留。

    设计依据: 等价类-无效-LLM 失败路径（用户输入是已发生的事实，不得回滚丢失）。
    """

    async def fake_boom(*_a: Any, **_k: Any) -> AssistantTurn:
        raise AgentError(problem="LLM 调用失败（APITimeoutError）", cause="超时", fix="重试")

    monkeypatch.setattr(llm, "chat_turn", fake_boom)
    _seed_conversation(store)
    events = [evt async for evt in service.stream_chat("conv-1", "写个开头", perspective="author")]

    names = [e["event"] for e in events]
    assert names[0] == "message_start" and names[-1] == "error", f"失败轮事件首尾不符: {names}"
    payload = events[-1]["data"]
    # E05 范式：code 与 problem 锁具体值（文案变异在此被杀）
    assert payload["code"] == "AGENT_FAILURE", f"错误码必须为 AgentError 默认码: {payload}"
    assert payload["problem"] == "LLM 调用失败（APITimeoutError）", f"problem 须锁全文: {payload}"
    assert payload["cause"] and payload["fix"], f"cause/fix 必须齐全: {payload}"
    roles = [m.role for m in store.messages["conv-1"]]
    assert roles == ["user"], f"LLM 失败后用户消息必须保留且无 assistant 行: {roles}"
    assert store.session_stub.rollbacks >= 1, "失败轮必须回滚未完成写"


async def test_stream_chat_injects_current_message_once(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U30: 本轮用户消息在 prompt 中恰好注入一次（历史行剔除，防双份注入）。

    设计依据: 边界值-注入次数恰 1（同事务可见的 flush 行 + 显式追加曾致双份）。
    """
    _seed_conversation(store)
    captured: list[list[dict[str, Any]]] = []

    async def fake_chat_turn(_system: str, messages: list[dict], **_k: Any) -> AssistantTurn:
        captured.append(messages)
        return AssistantTurn(content="ok")

    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)
    _ = [evt async for evt in service.stream_chat("conv-1", "独一无二的问题", perspective="author")]

    user_contents = [m.get("content") for m in captured[0] if m.get("role") == "user"]
    assert user_contents.count("独一无二的问题") == 1, (
        f"本轮用户消息必须恰好注入一次（当前 {user_contents.count('独一无二的问题')} 次）: "
        f"{user_contents}"
    )


async def test_rolling_summary_empty_result_keeps_state(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U31: 摘要返回空白 → 视为失败跳过（既有摘要与游标不得被清空/推进）。

    设计依据: 边界值-空串摘要（清空 summary 且推进游标会静默丢失被压缩历史）。
    """

    async def fake_summarize(_text: str, _instruction: str) -> str:
        return "   "

    async def fake_chat_turn(*_a: Any, **_k: Any) -> AssistantTurn:
        return AssistantTurn(content="ok")

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    monkeypatch.setattr(llm, "chat_turn", fake_chat_turn)

    conv = store.add_conversation(
        SimpleNamespace(
            id="conv-s",
            project_id="proj-1",
            title="t",
            summary="既有摘要",
            summary_until_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    for i in range(3):  # 窗口=2：3 条历史 + 本轮 2 条 → 溢出 3 条触发压缩
        store.add_message(
            SimpleNamespace(
                id=f"msg-h-{i}",
                conversation_id="conv-s",
                role="user",
                content=f"历史{i}",
                created_at=datetime.now(UTC),
            )
        )
    events = [evt async for evt in service.stream_chat("conv-s", "新输入", perspective="author")]

    assert events[-1]["event"] == "done", "空摘要不得破坏正常收尾"
    assert conv.summary == "既有摘要", f"既有摘要不得被空白覆盖: {conv.summary!r}"
    assert conv.summary_until_id is None, "摘要跳过时游标不得推进"


async def test_propose_builds_drafts(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """U25: 有效描述 → 草案列表（id 系统生成）；LLM 不可用 → AgentError。"""
    _seed_conversation(store)

    async def fake_complete_json(_system: str, _msgs: list[dict], **_k: Any) -> dict[str, Any]:
        return {
            "drafts": [
                {
                    "kind": "entity",
                    "payload": {"type": "character", "name": "周兰"},
                    "summary": "新增女主角",
                }
            ]
        }

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    response = await service.propose_drafts(
        SessionStub(),
        ProposeRequest(session_id="conv-1", message="加个女主角", perspective="author"),
    )
    assert len(response.drafts) == 1, f"必须产出 1 条草案: {response}"
    assert response.drafts[0].draft_id.startswith("draft-"), "草案 id 必须系统生成"
    assert response.drafts[0].payload["name"] == "周兰"

    async def fake_boom(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AgentError(problem="端点失败", cause="超时", fix="重试")

    monkeypatch.setattr(llm, "complete_json", fake_boom)
    with pytest.raises(AgentError):
        await service.propose_drafts(
            SessionStub(),
            ProposeRequest(session_id="conv-1", message="x", perspective="author"),
        )


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ({"drafts": "not-a-list"}, "drafts 非列表"),
        ({"drafts": [{"kind": "weapon", "payload": {}}]}, "kind 非法"),
        ({"drafts": [{"kind": "entity", "payload": "not-dict"}]}, "payload 非对象"),
    ],
    ids=["缺drafts列表", "kind白名单外", "payload类型错"],
)
async def test_propose_rejects_malformed_drafts(
    store: Store, monkeypatch: pytest.MonkeyPatch, raw: dict[str, Any], label: str
) -> None:
    """U25 补充参数化: 服务端基础校验拦截畸形草案（等价类-无效-schema 违约）。"""

    async def fake_complete_json(*_a: Any, **_k: Any) -> dict[str, Any]:
        return raw

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    _seed_conversation(store)
    with pytest.raises(ValidationError):
        await service.propose_drafts(
            SessionStub(),
            ProposeRequest(session_id="conv-1", message="x", perspective="author"),
        )
    assert label  # label 仅用于用例 id 可读性


async def test_confirm_write_partial_failure(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """U26: 确认项经 entities/relations service 落库；单项失败不阻断（failed 携带原因）。"""
    created_entities: list[dict[str, Any]] = []

    async def fake_entity_create(_s: Any, schema: Any) -> Any:
        if getattr(schema, "name", "") == "bad":
            raise ValidationError(problem="名称非法", cause="含禁用字符", fix="改名后重试")
        created_entities.append({"name": schema.name})
        return SimpleNamespace(id=f"ent-{len(created_entities)}", name=schema.name)

    async def fake_relation_create(_s: Any, schema: Any) -> Any:
        return SimpleNamespace(
            id="rel-1", type="ALLIES", source=schema.source, target=schema.target
        )

    monkeypatch.setattr(service.entities_service, "create", fake_entity_create)
    monkeypatch.setattr(service.relations_service, "create", fake_relation_create)

    response = await service.confirm_write(
        SessionStub(),
        ConfirmRequest(
            items=[
                ConfirmItem(
                    draft_id="d1",
                    kind="entity",
                    payload={"type": "character", "name": "周兰"},
                    confirmed=True,
                ),
                ConfirmItem(
                    draft_id="d2",
                    kind="entity",
                    payload={"type": "character", "name": "bad"},
                    confirmed=True,
                ),
                ConfirmItem(
                    draft_id="d3",
                    kind="relation",
                    payload={"type": "ALLIES", "source": "ent-1", "target": "ent-9"},
                    confirmed=True,
                ),
                ConfirmItem(
                    draft_id="d4",
                    kind="entity",
                    payload={"type": "character", "name": "放弃"},
                    confirmed=False,
                ),
            ]
        ),
    )

    assert [c.draft_id for c in response.created] == ["d1", "d3"], (
        f"成功项必须含实体与关系（放弃项跳过）: {response}"
    )
    assert len(response.failed) == 1 and response.failed[0].draft_id == "d2", (
        f"失败项必须单独折叠: {response.failed}"
    )
    assert "名称非法" in response.failed[0].reason, "失败原因必须三要素可读"


async def test_confirm_write_invalid_payloads_fail_closed(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U26 补充: 篡改/非法 payload 在服务端被构造 DTO 校验拦截（不信任前端）。"""

    async def fake_entity_create(_s: Any, schema: Any) -> Any:
        return SimpleNamespace(id="ent-x", name=schema.name)

    monkeypatch.setattr(service.entities_service, "create", fake_entity_create)
    response = await service.confirm_write(
        SessionStub(),
        ConfirmRequest(
            items=[
                ConfirmItem(
                    draft_id="d1",
                    kind="entity",
                    payload={"type": "not-a-type", "name": "x"},
                    confirmed=True,
                )
            ]
        ),
    )
    assert response.created == [], "非法类型不得落库"
    assert len(response.failed) == 1 and "校验" in response.failed[0].reason, (
        f"失败原因必须可读: {response.failed}"
    )
