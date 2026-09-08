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

    async def fake_delete_conversation(_s: Any, conversation: Any) -> None:
        store.conversations.pop(conversation.id, None)
        store.messages.pop(conversation.id, None)

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
    monkeypatch.setattr(repository, "delete_conversation", fake_delete_conversation)
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


def _scripted_stream(*turns: AssistantTurn) -> Any:
    """按脚本回放流式 LLM 事件；脚本耗尽后再被调用即抛 RuntimeError。

    作用: 为 stream_chat 提供有界判杀桩（F13 真流式路径）——每个
        AssistantTurn 展开为一轮流式事件：content 按小分片产出多个
        content_delta（模拟 SDK 逐 chunk），随后产出聚合 ("turn", …)。
        无限循环类变异体（如工具分支条件 and→or，T-20260907-02）会让循环
        反复调用 LLM，无界桩会挂死整个 mutmut 运行（Windows 无 SIGALRM，
        mutmut 超时机制失效）；耗尽即抛使此类变异体快速转为断言失败被杀。
    参数: turns — 按调用顺序回放的 AssistantTurn 序列。
    返回值: async 生成器工厂（签名与 llm.stream_chat_turn 一致）。
    异常: RuntimeError — 脚本耗尽仍被调用（测试基建守卫，非被测行为）。
    依赖: 无。
    """
    script = list(turns)

    async def _fake(*_a: Any, **_k: Any) -> Any:
        if not script:
            raise RuntimeError("LLM 流式桩脚本耗尽仍被调用（疑似无限循环变异体）")
        turn = script.pop(0)
        if turn.content:
            for i in range(0, len(turn.content), 6):
                yield ("content_delta", turn.content[i : i + 6])
        yield ("turn", turn)

    return _fake


def _delta_stream(*events: tuple[str, Any]) -> Any:
    """按给定事件序列精确回放一轮流式事件（U10/U11/U12 等精细断言用）。

    参数: events — ("reasoning_delta"|"content_delta"|"usage"|"turn", payload) 序列。
    返回值: async 生成器工厂（签名与 llm.stream_chat_turn 一致）。
    异常: 无（事件由用例给定）。依赖: 无。
    """

    async def _fake(*_a: Any, **_k: Any) -> Any:
        for kind, payload in events:
            yield (kind, payload)

    return _fake


async def test_stream_chat_normal_flow(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """U23: 正常轮 → message_start/token/done 事件齐全，user+assistant 落库。

    设计依据: 等价类-有效会话轮。
    """
    _seed_conversation(store)
    monkeypatch.setattr(
        llm, "stream_chat_turn", _scripted_stream(AssistantTurn(content="你好，创作者。"))
    )
    events = [evt async for evt in service.stream_chat("conv-1", "介绍项目", perspective="author")]

    names = [e["event"] for e in events]
    assert names[0] == "message_start" and names[-1] == "done", f"事件首尾不符: {names}"
    assert "token" in names and "error" not in names, f"必须有 token 且无 error: {names}"
    token_text = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert token_text == "你好，创作者。", f"token 拼接必须还原全文: {token_text}"
    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) >= 2, f"真流式：正文必须按上游分片多帧到达: {len(token_events)}"
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

    monkeypatch.setattr(llm, "stream_chat_turn", _scripted_stream(AssistantTurn(content="ok")))
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

    async def fake_stream(_system: str, _msgs: list[dict], **kwargs: Any) -> Any:
        calls.append({"kwargs": kwargs, "messages": _msgs})
        if len(calls) > 2:
            raise RuntimeError("工具配额桩被调用超过 2 次（疑似无限循环变异体）")
        if kwargs.get("tools"):
            yield (
                "turn",
                AssistantTurn(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            call_id="call-1", name="search_entities", arguments='{"q": "周兰"}'
                        )
                    ],
                ),
            )
            return
        yield ("content_delta", "根据检索结果")
        yield ("content_delta", "作答。")
        yield ("turn", AssistantTurn(content="根据检索结果作答。"))

    async def fake_execute_tool(name: str, arguments: str, _ctx: Any) -> str:
        return "x" * 500  # 超长输出（上限 50），验证截断（U17）

    monkeypatch.setattr(llm, "stream_chat_turn", fake_stream)
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

    monkeypatch.setattr(
        llm,
        "stream_chat_turn",
        _scripted_stream(AssistantTurn(content="ok"), AssistantTurn(content="ok")),
    )

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

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    monkeypatch.setattr(llm, "stream_chat_turn", _scripted_stream(AssistantTurn(content="ok")))

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

    async def fake_boom(*_a: Any, **_k: Any) -> Any:
        if False:
            yield  # pragma: no cover — 使本函数成为异步生成器以对接流式路径
        raise AgentError(problem="LLM 调用失败（APITimeoutError）", cause="超时", fix="重试")

    monkeypatch.setattr(llm, "stream_chat_turn", fake_boom)
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

    async def fake_stream(_system: str, messages: list[dict], **_k: Any) -> Any:
        captured.append(messages)
        if len(captured) > 1:
            raise RuntimeError("U30 桩仅允许一次调用（疑似无限循环变异体）")
        yield ("turn", AssistantTurn(content="ok"))

    monkeypatch.setattr(llm, "stream_chat_turn", fake_stream)
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

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    monkeypatch.setattr(llm, "stream_chat_turn", _scripted_stream(AssistantTurn(content="ok")))

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


# ---- F13：真流式 / reasoning / usage / 会话删除 ----


async def test_stream_chat_reasoning_usage_events_and_persist(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U10: 全事件序列 = message_start → reasoning×2 → token×3 → usage → done，
    思考与 usage 随 assistant 行落库。

    设计依据: 等价类-有效思考+正文+usage 轮（协议扩展核心路径）。
    """
    _seed_conversation(store)
    monkeypatch.setattr(
        llm,
        "stream_chat_turn",
        _delta_stream(
            ("reasoning_delta", "先想第一步。"),
            ("reasoning_delta", "再想第二步。"),
            ("content_delta", "答案一。"),
            ("content_delta", "答案二。"),
            ("content_delta", "答案三。"),
            ("usage", {"prompt_tokens": 1000, "completion_tokens": 200}),
            ("turn", AssistantTurn(content="答案一。答案二。答案三。")),
        ),
    )
    events = [evt async for evt in service.stream_chat("conv-1", "问题", perspective="author")]

    names = [e["event"] for e in events]
    assert names == [
        "message_start",
        "reasoning",
        "reasoning",
        "token",
        "token",
        "token",
        "usage",
        "done",
    ], f"事件序列必须逐片且有序: {names}"
    reasoning_text = "".join(e["data"]["text"] for e in events if e["event"] == "reasoning")
    assert reasoning_text == "先想第一步。再想第二步。", f"思考增量必须逐片透传: {reasoning_text}"
    usage = events[-2]["data"]
    assert usage["prompt_tokens"] == 1000 and usage["completion_tokens"] == 200, (
        f"usage 数值: {usage}"
    )
    assert usage["context_max_tokens"] == 100000, "容量上限必须来自 config"
    assert abs(usage["context_ratio"] - 0.01) < 1e-9, f"占比=prompt/max: {usage}"
    assistant = store.messages["conv-1"][-1]
    assert assistant.reasoning == "先想第一步。再想第二步。", (
        f"思考必须落库: {assistant.reasoning!r}"
    )
    assert assistant.prompt_tokens == 1000 and assistant.completion_tokens == 200, "usage 必须落库"
    assert assistant.content == "答案一。答案二。答案三。", "正文必须完整落库"


@pytest.mark.parametrize(
    ("prompt_tokens", "max_tokens", "expected"),
    [(0, 8000, 0.0), (4000, 8000, 0.5), (9000, 8000, 9000 / 8000)],
    ids=["零prompt", "恰半", "超上限原值透传"],
)
async def test_usage_context_ratio_boundaries(
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    prompt_tokens: int,
    max_tokens: int,
    expected: float,
) -> None:
    """F13-U11 参数化: 容量占比边界——0、半、超上限原值透传（钳制在展示层）。

    设计依据: 边界值分析；数据语义与展示语义分离。
    """
    _seed_conversation(store)
    monkeypatch.setattr(
        llm,
        "stream_chat_turn",
        _delta_stream(
            ("content_delta", "好"),
            ("usage", {"prompt_tokens": prompt_tokens, "completion_tokens": 1}),
            ("turn", AssistantTurn(content="好")),
        ),
    )

    class RatioStub(AgentSettingsStub):
        agent_context_max_tokens = max_tokens

    _install(store, monkeypatch, settings=RatioStub())
    events = [evt async for evt in service.stream_chat("conv-1", "问", perspective="author")]

    usage = next(e for e in events if e["event"] == "usage")
    assert usage["data"]["context_ratio"] == pytest.approx(expected), f"占比边界: {usage}"


async def test_stream_chat_without_usage_omits_event(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U12: 端点不返回 usage → 无 usage 事件，落库 tokens 为 None（兼容等价类）。"""
    _seed_conversation(store)
    monkeypatch.setattr(
        llm,
        "stream_chat_turn",
        _delta_stream(("content_delta", "好"), ("turn", AssistantTurn(content="好"))),
    )
    events = [evt async for evt in service.stream_chat("conv-1", "问", perspective="author")]

    names = [e["event"] for e in events]
    assert "usage" not in names and names[-1] == "done", f"无 usage 必须缺省事件: {names}"
    assistant = store.messages["conv-1"][-1]
    assert assistant.prompt_tokens is None and assistant.completion_tokens is None, (
        "缺失 usage 必须落库为 NULL"
    )
    assert assistant.reasoning is None, "无思考时 reasoning 必须为 NULL"


async def test_tool_round_reasoning_streams_final_reasoning_persists(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U13: 工具轮思考照常透传；落库 reasoning 取最终轮思考（答案前思考）。

    设计依据: 等价类-工具轮+思考组合轮。
    """
    _seed_conversation(store)

    async def fake_stream(_system: str, _msgs: list[dict], **kwargs: Any) -> Any:
        if kwargs.get("tools"):
            yield ("reasoning_delta", "中间思考：先查图谱。")
            yield (
                "turn",
                AssistantTurn(
                    content=None,
                    tool_calls=[ToolCall(call_id="c1", name="search_entities", arguments="{}")],
                ),
            )
            return
        yield ("reasoning_delta", "最终思考：组织答案。")
        yield ("content_delta", "最终答案。")
        yield ("turn", AssistantTurn(content="最终答案。"))

    async def fake_execute_tool(_name: str, _arguments: str, _ctx: Any) -> str:
        return "[]"

    monkeypatch.setattr(llm, "stream_chat_turn", fake_stream)
    monkeypatch.setattr(service.tools, "execute_tool", fake_execute_tool)
    events = [evt async for evt in service.stream_chat("conv-1", "查一下", perspective="author")]

    reasoning_text = "".join(e["data"]["text"] for e in events if e["event"] == "reasoning")
    assert reasoning_text == "中间思考：先查图谱。最终思考：组织答案。", (
        f"两轮思考必须都透传: {reasoning_text}"
    )
    assistant = store.messages["conv-1"][-1]
    assert assistant.reasoning == "最终思考：组织答案。", (
        f"落库 reasoning 必须取最终轮: {assistant.reasoning!r}"
    )
    assert [e["event"] for e in events].count("tool") == 2, "工具事件 start+done 各一"


async def test_stream_chat_empty_reply_errors(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U14: 流结束无正文且无工具调用 → error 事件三要素（既有防御语义回归）。"""
    _seed_conversation(store)
    monkeypatch.setattr(
        llm,
        "stream_chat_turn",
        _delta_stream(("turn", AssistantTurn(content="  "))),
    )
    events = [evt async for evt in service.stream_chat("conv-1", "问", perspective="author")]

    assert events[-1]["event"] == "error", f"空回复必须以 error 收尾: {events[-1]}"
    assert events[-1]["data"]["problem"] == "LLM 返回了空回复", "三要素 problem 必须锁值"
    assert events[-1]["data"]["cause"] and events[-1]["data"]["fix"], "cause/fix 必须齐全"


async def test_get_messages_readback_carries_reasoning_and_usage(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U15: get_messages 回读 assistant 行携带 reasoning/tokens（刷新后可展开）。

    设计依据: 回读契约（前端 ThinkingBlock 历史展开的数据源）。
    """
    _seed_conversation(store)
    store.add_message(
        SimpleNamespace(
            id="msg-a",
            conversation_id="conv-1",
            role="assistant",
            content="答",
            reasoning="思",
            prompt_tokens=11,
            completion_tokens=7,
            created_at=datetime.now(UTC),
        )
    )
    rows = await service.get_messages(SessionStub(), "conv-1")

    assistant = next(r for r in rows if r.id == "msg-a")
    assert assistant.reasoning == "思" and assistant.prompt_tokens == 11, f"回读字段: {assistant}"
    assert assistant.completion_tokens == 7, "completion_tokens 必须回读"


async def test_delete_conversation_cascades_messages(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13-U17: 删除存在会话 → 会话与消息一并清理（级联语义）。"""
    _seed_conversation(store)
    store.add_message(
        SimpleNamespace(
            id="msg-1",
            conversation_id="conv-1",
            role="user",
            content="hi",
            created_at=datetime.now(UTC),
        )
    )
    await service.delete_conversation(SessionStub(), "conv-1")

    assert "conv-1" not in store.conversations, "会话必须被删除"
    assert store.messages.get("conv-1") in (None, []), "消息必须级联清理"


async def test_delete_conversation_not_found_three_elements(store: Store) -> None:
    """F13-U18: 删除不存在会话 → NotFoundError 三要素齐全（无效等价类）。"""
    with pytest.raises(NotFoundError) as excinfo:
        await service.delete_conversation(SessionStub(), "ghost")
    assert excinfo.value.problem and excinfo.value.cause and excinfo.value.fix, (
        f"三要素必须齐全: {excinfo.value}"
    )


async def test_delete_conversation_isolated_per_project(store: Store) -> None:
    """F13-U19: 删除一项目会话不影响他项目会话（隔离性）。"""
    _seed_conversation(store, "conv-a")
    _seed_conversation(store, "conv-b")
    store.conversations["conv-b"].project_id = "proj-2"

    await service.delete_conversation(SessionStub(), "conv-a")

    assert "conv-a" not in store.conversations and "conv-b" in store.conversations, (
        "他项目会话必须完好"
    )
