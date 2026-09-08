"""F10 L1 单元测试：agent LLM 客户端封装（SDK 全 mock，不触网络）。

mock 策略: 以 FakeClient 替换 openai.AsyncOpenAI——只验证 llm.py 的
错误包装/usage 记录/JSON 修复重试/模型路由逻辑。
用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
"""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import openai
import pytest

from app.agent import llm
from app.core.exceptions import AgentError, ValidationError

pytestmark = pytest.mark.unit


class _SettingsStub:
    """配置桩：LLM 相关字段的最小快照（避免触碰真实 .env）。"""

    llm_api_key = "sk-test"
    llm_base_url = "https://example.invalid/v1"
    llm_model = "model-main"
    llm_model_light = "model-light"
    llm_timeout_seconds = 5


class FakeCompletions:
    """补全端点桩：按序返回预设响应或抛出异常，并记录调用参数。"""

    def __init__(self) -> None:
        self.script: list[Any] = []
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeClient:
    """客户端桩：仅暴露 chat.completions 与 close。"""

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@dataclass
class LlmHarness:
    """单测夹具载荷：补全桩 + 运行事件捕获列表。"""

    completions: FakeCompletions
    events: list[dict[str, Any]] = field(default_factory=list)

    def push(self, *steps: Any) -> None:
        """向脚本队列追加响应或异常。

        参数: steps — 响应对象或异常实例（按调用顺序消费）。
        返回值: 无。异常: 无。依赖: 无。
        """
        self.completions.script.extend(steps)


def _response(content: str | None = "ok", *, tool_calls: list[Any] | None = None) -> Any:
    """构造最小补全响应对象（choices[0].message + usage）。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> LlmHarness:
    """注入 FakeClient 与事件捕获（chat_turn/complete_json/summarize 全走桩）。

    作用: 替换 llm.get_client / llm.get_settings / llm.emit_event，实现
        SDK 与配置完全隔离，并暴露调用参数与运行事件供断言。
    参数: monkeypatch — pytest 替换器。
    返回值: LlmHarness。异常: 无。依赖: app.agent.llm。
    """
    fake = FakeClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    monkeypatch.setattr(llm, "get_settings", lambda: _SettingsStub())
    state = LlmHarness(completions=fake.chat.completions)
    monkeypatch.setattr(
        llm,
        "emit_event",
        lambda event, **kw: state.events.append({"event": event, **kw}),
    )
    return state


def _tool_call(call_id: str = "call-1", name: str = "search_entities", args: str = "{}") -> Any:
    """构造最小 SDK tool_call 对象。"""
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=args))


async def test_chat_turn_success_records_usage(harness: LlmHarness) -> None:
    """U1: 有效调用 → 返回文本、usage 记入运行事件、system 打头（等价类-有效调用）。"""
    harness.push(_response("你好"))

    turn = await llm.chat_turn("sys-prompt", [{"role": "user", "content": "hi"}])

    assert turn.content == "你好", f"文本回复必须原样返回: {turn}"
    assert turn.tool_calls == [], "无工具调用的轮次 tool_calls 必须为空列表"
    usage_events = [e for e in harness.events if e["event"] == "llm_usage"]
    assert len(usage_events) == 1, f"usage 事件必须恰记录一次: {harness.events}"
    assert usage_events[0]["data"]["total_tokens"] == 15, "usage 事件必须携带 token 计数"
    first_message = harness.completions.calls[0]["messages"][0]
    assert first_message == {"role": "system", "content": "sys-prompt"}, (
        f"system 提示词必须打头（前缀缓存友好契约）: {first_message}"
    )


async def test_chat_turn_normalizes_tool_calls(harness: LlmHarness) -> None:
    """U1 补充: 工具调用轮 → 归一化为 ToolCall 列表且 raw 可回传历史（等价类-工具轮）。"""
    harness.push(_response(None, tool_calls=[_tool_call(args='{"q": "张三"}')]))

    turn = await llm.chat_turn("sys", [{"role": "user", "content": "查张三"}], tools=[{"t": 1}])

    assert len(turn.tool_calls) == 1, "工具调用必须被归一化收集"
    assert turn.tool_calls[0].name == "search_entities"
    assert turn.tool_calls[0].arguments == '{"q": "张三"}'
    assert harness.completions.calls[0]["tools"] == [{"t": 1}], "工具定义必须透传给端点"
    assert turn.raw["tool_calls"][0]["id"] == "call-1", "raw 必须可回传对话历史"


@pytest.mark.parametrize(
    ("exc", "label"),
    [
        (openai.APITimeoutError(request=None), "timeout"),  # type: ignore[arg-type]
        (openai.APIError(message="boom", request=None, body=None), "api_error"),  # type: ignore[arg-type]
        (openai.APIConnectionError(request=None), "connection"),  # type: ignore[arg-type]
    ],
)
async def test_chat_turn_wraps_failures_as_agent_error(
    harness: LlmHarness, exc: Exception, label: str
) -> None:
    """U2 参数化: 端点失败三型 → AgentError 三要素完整（等价类-无效-失败模式三分类）。"""
    harness.push(exc)
    with pytest.raises(AgentError) as excinfo:
        await llm.chat_turn("sys", [{"role": "user", "content": "hi"}])
    err = excinfo.value
    # E05 范式：problem 锁全文、detail 整体相等（文案/detail 变异在此被杀）
    assert err.problem == f"LLM 调用失败（{type(exc).__name__}）", f"[{label}] 须锁全文: {err}"
    assert err.cause and err.fix.startswith("检查 LLM_BASE_URL"), f"[{label}] cause/fix: {err}"
    assert err.detail == {
        "component": "app.agent.llm",
        "model": "model-main",
        "error_type": type(exc).__name__,
    }, f"[{label}] detail 必须整体相等: {err.detail}"


async def test_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """U2 补充: API 密钥未配置 → AgentError 指引补配置（等价类-无效-配置缺失）。"""

    class _NoKeySettings(_SettingsStub):
        llm_api_key = ""

    monkeypatch.setattr(llm, "get_settings", lambda: _NoKeySettings())
    monkeypatch.setattr(llm, "_client", None)
    with pytest.raises(AgentError) as excinfo:
        llm.get_client()
    err = excinfo.value
    assert "LLM_API_KEY" in err.fix, f"修复指引必须指向 LLM_API_KEY: {err.fix}"


async def test_complete_json_repairs_once(harness: LlmHarness) -> None:
    """U3: 首轮输出非 JSON → 修复重试恰 1 次后成功（边界值-重试恰 1 次）。"""
    harness.push(_response("我不是 JSON"), _response('```json\n{"a": 1}\n```'))

    payload = await llm.complete_json("sys", [{"role": "user", "content": "给个 JSON"}])

    assert payload == {"a": 1}, f"修复轮的合法 JSON（含栅栏）必须被解析: {payload}"
    assert len(harness.completions.calls) == 2, (
        f"修复重试必须恰好多调用一次（实际 {len(harness.completions.calls)} 次）"
    )
    repair_prompt = harness.completions.calls[1]["messages"][-1]["content"]
    assert "JSON" in repair_prompt, f"修复轮必须包含修复指令: {repair_prompt}"


@pytest.mark.parametrize(
    ("good_output", "label"),
    [
        ('{"a": 1}', "裸 JSON"),
        ('```json\n{"a": 1}\n```', "小写栅栏"),
        ('```JSON\n{"a": 1}\n```', "大写栅栏"),
        ('```\n{"a": 1}\n```', "无语言标记栅栏"),
    ],
)
async def test_complete_json_accepts_fenced_variants(
    harness: LlmHarness, good_output: str, label: str
) -> None:
    """U3 补充参数化: 首轮合法输出（栅栏语言标记大小写不敏感）直接解析。

    设计依据: 等价类-有效-输出形态四分类（边界值-语言标记大小写两态）。
    """
    harness.push(_response(good_output))

    payload = await llm.complete_json("sys", [{"role": "user", "content": "x"}])

    assert payload == {"a": 1}, f"[{label}] 必须解析成功: {good_output!r}"
    assert len(harness.completions.calls) == 1, f"[{label}] 合法输出不得触发修复轮"


@pytest.mark.parametrize(
    ("bad_output", "label"),
    [
        ("plain text", "纯文本"),
        ('["not", "an", "object"]', "JSON 数组"),
        ("```json\n{oops}\n```", "栅栏内坏 JSON"),
    ],
)
async def test_complete_json_exhausts_retry_raises_validation(
    harness: LlmHarness, bad_output: str, label: str
) -> None:
    """U4 参数化: 修复重试后仍非 JSON 对象 → ValidationError（边界值-重试上限+1）。"""
    harness.push(_response(bad_output), _response(bad_output))
    with pytest.raises(ValidationError) as excinfo:
        await llm.complete_json("sys", [{"role": "user", "content": "x"}])
    err = excinfo.value
    assert err.problem and err.cause and err.fix, f"[{label}] 三要素必须齐全: {err}"
    assert len(harness.completions.calls) == 2, (
        f"[{label}] 总调用必须为 1+修复 1 次（实际 {len(harness.completions.calls)}）"
    )


async def test_summarize_routes_to_light_model(harness: LlmHarness) -> None:
    """U5: 摘要任务路由到轻量模型（等价类-模型路由分支）。"""
    harness.push(_response("摘要结果"))

    summary = await llm.summarize("很长很长的历史", "压缩为一段话")

    assert summary == "摘要结果"
    assert harness.completions.calls[0]["model"] == "model-light", (
        f"摘要必须走 llm_model_light（实际 {harness.completions.calls[0]['model']}）"
    )


# ---- F13：stream_chat_turn 真流式生成器 ----


def _chunk(
    *,
    content: str | None = None,
    reasoning: str | None = None,
    tool_calls: list[Any] | None = None,
    usage: Any = None,
    empty_choices: bool = False,
) -> Any:
    """构造最小流式 chunk 对象（choices[0].delta + usage；usage-only 帧 choices 为空）。"""
    if empty_choices:
        return SimpleNamespace(choices=[], usage=usage)
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    if reasoning is not None:
        delta.reasoning_content = reasoning
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def _usage() -> Any:
    """构造最小 SDK usage 对象。"""
    return SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _frag(index: int, call_id: str | None, name: str | None, args: str | None) -> Any:
    """构造流式 tool_calls 分片（首片带 id/name，后续片仅增量 arguments）。"""
    return SimpleNamespace(
        index=index, id=call_id, function=SimpleNamespace(name=name, arguments=args)
    )


def _stream(*steps: Any) -> Any:
    """异步流桩：create 返回值——async for 逐个产出 chunk，异常步在迭代中抛出。"""

    async def _gen() -> Any:
        for step in steps:
            if isinstance(step, Exception):
                raise step
            yield step

    return _gen()


async def _collect(gen: Any) -> list[tuple[str, Any]]:
    """收集流式事件为列表。"""
    return [evt async for evt in gen]


async def test_stream_turn_content_deltas_and_turn(harness: LlmHarness) -> None:
    """F13-U1: 纯文本轮 → content_delta 逐片（与上游分片一一对应）+ 末尾聚合 turn。"""
    harness.push(
        _stream(
            _chunk(content="你"), _chunk(content="好"), _chunk(empty_choices=True, usage=_usage())
        )
    )
    events = await _collect(llm.stream_chat_turn("sys", [{"role": "user", "content": "hi"}]))

    kinds = [k for k, _ in events]
    assert kinds == ["content_delta", "content_delta", "usage", "turn"], f"事件序列: {kinds}"
    assert [p for k, p in events if k == "content_delta"] == ["你", "好"], "分片必须原样透传"
    turn = events[-1][1]
    assert turn.content == "你好" and turn.tool_calls == [], f"聚合产物: {turn}"
    assert turn.raw == {"role": "assistant", "content": "你好"}, f"raw 形状: {turn.raw}"
    kwargs = harness.completions.calls[0]
    assert kwargs["stream"] is True, "必须以流式发起"
    assert kwargs["stream_options"] == {"include_usage": True}, "必须请求 usage 块"


async def test_stream_turn_reasoning_precedes_content(harness: LlmHarness) -> None:
    """F13-U2: 思考+回答轮 → reasoning_delta 逐片先于 content_delta；思考不入正文。"""
    harness.push(
        _stream(
            _chunk(reasoning="想一"),
            _chunk(reasoning="想二"),
            _chunk(content="答"),
            _chunk(empty_choices=True, usage=_usage()),
        )
    )
    events = await _collect(llm.stream_chat_turn("sys", []))

    kinds = [k for k, _ in events]
    assert kinds == ["reasoning_delta", "reasoning_delta", "content_delta", "usage", "turn"], (
        f"思考必须先于正文逐片产出: {kinds}"
    )
    assert events[-1][1].content == "答", "聚合 content 不得混入思考文本"


async def test_stream_turn_reasoning_with_tool_calls(harness: LlmHarness) -> None:
    """F13-U3: 思考+工具调用轮 → 产出聚合 tool_calls 且 raw 携带历史回传形状。"""
    harness.push(
        _stream(
            _chunk(reasoning="先查"),
            _chunk(tool_calls=[_frag(0, "call-1", "search_entities", '{"q": 1}')]),
        )
    )
    events = await _collect(llm.stream_chat_turn("sys", []))

    turn = events[-1][1]
    assert (
        turn.tool_calls[0].call_id == "call-1" and turn.tool_calls[0].name == "search_entities"
    ), f"聚合工具调用: {turn.tool_calls}"
    assert turn.raw["tool_calls"] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "search_entities", "arguments": '{"q": 1}'},
        }
    ], f"raw 必须与 chat_turn 同形: {turn.raw}"


async def test_stream_turn_tool_fragments_aggregate_by_index(harness: LlmHarness) -> None:
    """F13-U4: 多工具分片按 index 聚合（id/name 取首片、arguments 增量拼接）。"""
    harness.push(
        _stream(
            _chunk(tool_calls=[_frag(0, "call-a", "search_entities", '{"q"')]),
            _chunk(tool_calls=[_frag(1, "call-b", "get_entity_detail", '{"id"')]),
            _chunk(tool_calls=[_frag(0, None, None, ': "周"}')]),
            _chunk(tool_calls=[_frag(1, None, None, ": 7}")]),
        )
    )
    events = await _collect(llm.stream_chat_turn("sys", []))

    turn = events[-1][1]
    assert [(tc.call_id, tc.name, tc.arguments) for tc in turn.tool_calls] == [
        ("call-a", "search_entities", '{"q": "周"}'),
        ("call-b", "get_entity_detail", '{"id": 7}'),
    ], f"按 index 聚合与拼接必须精确: {turn.tool_calls}"


async def test_stream_turn_blank_argument_fragments(harness: LlmHarness) -> None:
    """F13-U5: 空/缺失 arguments 分片 → 聚合结果不出现 None（空串兜底）。"""
    harness.push(
        _stream(
            _chunk(tool_calls=[_frag(0, "call-1", "search_entities", None)]),
            _chunk(tool_calls=[_frag(0, None, None, "")]),
        )
    )
    events = await _collect(llm.stream_chat_turn("sys", []))

    turn = events[-1][1]
    assert turn.tool_calls[0].arguments == "", f"缺失 arguments 必须按空串聚合: {turn.tool_calls}"


async def test_stream_turn_usage_payload_and_event(harness: LlmHarness) -> None:
    """F13-U6: usage 块 → ("usage", payload) 透传且 llm_usage 记入运行事件。"""
    harness.push(_stream(_chunk(content="好"), _chunk(empty_choices=True, usage=_usage())))
    events = await _collect(llm.stream_chat_turn("sys", []))

    usage = dict(next(p for k, p in events if k == "usage"))
    assert usage["prompt_tokens"] == 10 and usage["completion_tokens"] == 5, f"usage: {usage}"
    usage_events = [e for e in harness.events if e["event"] == "llm_usage"]
    assert usage_events and usage_events[0]["data"]["total_tokens"] == 15, "usage 必须记观测事件"


async def test_stream_turn_without_usage_block(harness: LlmHarness) -> None:
    """F13-U7: 端点无 usage 块 → 不产出 usage 事件，turn 正常（兼容等价类）。"""
    harness.push(_stream(_chunk(content="好"), _chunk(empty_choices=True, usage=None)))
    events = await _collect(llm.stream_chat_turn("sys", []))

    assert all(k != "usage" for k, _ in events), f"不得产出 usage 事件: {events}"
    assert events[-1][1].content == "好", "无 usage 不得影响聚合产物"


async def test_stream_turn_wraps_sdk_failure(harness: LlmHarness) -> None:
    """F13-U8: SDK 异常（发起失败与流中断两态）→ AgentError 三要素。"""
    harness.push(openai.OpenAIError("boom"))
    with pytest.raises(AgentError) as excinfo:
        await _collect(llm.stream_chat_turn("sys", []))
    assert excinfo.value.problem and excinfo.value.cause and excinfo.value.fix, "三要素必须齐全"

    harness.push(_stream(_chunk(content="半"), openai.OpenAIError("流中断")))
    with pytest.raises(AgentError):
        await _collect(llm.stream_chat_turn("sys", []))


async def test_stream_turn_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """F13-U9: 密钥未配置 → 首次迭代即 AgentError，不产出任何事件（快速失败）。"""

    class _NoKey(_SettingsStub):
        llm_api_key = ""

    monkeypatch.setattr(llm, "get_settings", lambda: _NoKey())
    monkeypatch.setattr(llm, "_client", None)
    with pytest.raises(AgentError):
        await _collect(llm.stream_chat_turn("sys", []))
