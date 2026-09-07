"""agent 模块 LLM 客户端封装：OpenAI 兼容协议的进程级调用层。

职责边界:
    - 仅封装「怎么调」（客户端单例、超时、错误包装、usage 记录、JSON 修复重试、
      轻量模型路由）；「调什么」（prompt 组装、工具循环）在 prompts.py / service.py。
    - 所有配置来自 config（LLM_*，禁止硬编码）；失败一律包装为 AgentError（三要素），
      禁止未捕获异常冒泡（agent/CONSTRAINTS.md）。
"""

import json
from dataclasses import dataclass, field
from typing import Any

import openai

from app.config import get_settings
from app.core.exceptions import AgentError, ValidationError
from app.core.observability import emit_event

# JSON 修复重试上限（agent/CONSTRAINTS.md：禁止无限重试，最多 1 次）
_JSON_REPAIR_LIMIT = 1


@dataclass
class ToolCall:
    """规范化后的工具调用请求。

    作用: 把 SDK 返回的 tool_call 投影为模块内稳定结构，隔离 SDK 类型。
    参数: call_id — 工具调用 id（回传结果时使用）；name — 工具名；
        arguments — 已 JSON 解析的参数（解析失败为空串，由 tools 层校验）。
    返回值: 无（数据类）。异常: 无。依赖: 无。
    """

    call_id: str
    name: str
    arguments: str


@dataclass
class AssistantTurn:
    """一次补全的规范化结果：文本内容或工具调用二选一。

    作用: service 层的工具循环以 content / tool_calls 判定走向，
        不直接触碰 SDK 消息类型。
    参数: content — 文本回复（可能为 None）；tool_calls — 工具调用列表；
        raw — SDK 原始消息 dict（回传对话历史时使用，已剥无关字段）。
    返回值: 无（数据类）。异常: 无。依赖: dataclass。
    """

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


_client: openai.AsyncOpenAI | None = None


def _client_error(problem: str, cause: str, fix: str, **detail: Any) -> AgentError:
    """构造 LLM 调用失败的三要素异常（统一出口）。

    作用: 集中 AgentError 文案格式，保证三要素与 detail 结构一致。
    参数: problem/cause/fix — 三要素；detail — 结构化补充。
    返回值: AgentError。异常: 无。依赖: 无。
    """
    return AgentError(
        problem=problem,
        cause=cause,
        fix=fix,
        detail={"component": "app.agent.llm", **detail},
    )


def get_client() -> openai.AsyncOpenAI:
    """获取进程唯一的 LLM 异步客户端（懒加载）。

    作用: 首次调用创建 AsyncOpenAI（base_url/timeout 来自 config），
        重复调用返回同一实例；未配置 api_key 时快速失败。
    参数: 无。
    返回值: openai.AsyncOpenAI。
    异常:
        AgentError — LLM_API_KEY 未配置（502，提示补全配置）。
    依赖: app.config.get_settings。
    """
    global _client
    settings = get_settings()
    if not settings.llm_api_key:
        raise _client_error(
            problem="LLM 客户端不可用：API 密钥未配置",
            cause="环境变量 LLM_API_KEY 为空，无法向 LLM 端点发起认证请求",
            fix="在 backend/.env 中填入 LLM_API_KEY 后重启服务",
        )
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
    return _client


async def dispose_client() -> None:
    """释放 LLM 客户端连接（应用停机 / 测试清理时调用）。

    作用: 关闭底层 httpx 连接池并清空单例，允许下次以新配置重建。
    参数: 无。返回值: 无。异常: 无。依赖: openai.AsyncOpenAI.close。
    """
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _wrap_llm_error(exc: Exception, *, model: str) -> AgentError:
    """把 SDK/网络异常包装为三要素完整的 AgentError。

    作用: 统一超时、限流、端点错误、连接失败的出口，禁止原始异常冒泡。
    参数: exc — 捕获的异常；model — 本次调用的模型名（进入 detail）。
    返回值: AgentError。异常: 无。依赖: 无。
    """
    return _client_error(
        problem=f"LLM 调用失败（{type(exc).__name__}）",
        cause=f"模型 {model} 的补全请求未成功：{exc}",
        fix=(
            "检查 LLM_BASE_URL/LLM_API_KEY 配置与端点可用性后重试；"
            "持续失败可调大 LLM_TIMEOUT_SECONDS"
        ),
        model=model,
        error_type=type(exc).__name__,
    )


def _record_usage(model: str, usage: Any) -> None:
    """记录一次调用的 token 用量（成本观测，经 observability 统一出口）。

    作用: 解析 SDK usage 对象并发射 llm_usage 运行事件；provider 不返回
        usage（部分兼容端点）时跳过，不影响主流程。
    参数: model — 模型名；usage — SDK usage 对象（或 None）。
    返回值: 无。异常: 无。依赖: core.observability.emit_event。
    """
    if usage is None:
        return
    emit_event(
        "llm_usage",
        component="app.agent.llm",
        data={
            "model": model,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        },
    )


async def chat_turn(
    system: str,
    messages: list[dict[str, str]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> AssistantTurn:
    """执行一次（非流式）对话补全，返回规范化结果。

    作用:
        以 system 打头组装消息序列调用补全端点；tools 非空时启用工具调用
        （受控 ReAct 的检索轮）；响应归一化为 AssistantTurn，usage 记入
        运行事件，SDK/网络异常包装为 AgentError。
    参数:
        system — 系统提示词；messages — 对话消息（openai 格式 dicts）；
        tools — 工具定义（openai function 格式，None=不启用）；
        model — 模型名（None=主模型 config.llm_model）。
    返回值: AssistantTurn（content 与 tool_calls 至少其一非空）。
    异常:
        AgentError — API 密钥未配置 / 超时 / 端点失败 / 连接失败。
    依赖: get_client、app.config.get_settings、core.observability。
    """
    resolved_model = model or get_settings().llm_model
    client = get_client()
    chat_messages: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
    kwargs: dict[str, Any] = {"model": resolved_model, "messages": chat_messages}
    if tools:
        kwargs["tools"] = tools
    try:
        response = await client.chat.completions.create(**kwargs)
    except (openai.APITimeoutError, openai.APIError, openai.OpenAIError) as exc:
        raise _wrap_llm_error(exc, model=resolved_model) from exc

    _record_usage(resolved_model, response.usage)
    choice = response.choices[0]
    message = choice.message
    tool_calls = [
        ToolCall(
            call_id=tc.id,
            name=tc.function.name,
            arguments=tc.function.arguments if tc.function.arguments else "{}",
        )
        for tc in (message.tool_calls or [])
    ]
    raw: dict[str, Any] = {"role": "assistant", "content": message.content}
    if tool_calls:
        raw["tool_calls"] = [
            {
                "id": tc.call_id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in tool_calls
        ]
    return AssistantTurn(content=message.content, tool_calls=tool_calls, raw=raw)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON 文本为 dict（剔除 markdown 代码栅栏）。

    作用: 兼容模型把 JSON 包进 ```json ...``` 的常见行为（语言标记大小写
        不敏感）；解析失败抛 ValueError 由调用方决定重试或报错。
    参数: raw — 模型原始输出。
    返回值: dict[str, Any]。
    异常: ValueError — 剥栅栏后仍非合法 JSON 对象。
    依赖: json。
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip()
        if text[:4].lower() == "json":
            text = text[4:]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object, got {type(payload).__name__}")
    return payload


async def complete_json(
    system: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """请求 JSON 输出并解析为 dict；解析失败修复重试 1 次后报 ValidationError。

    作用:
        供 propose 等结构化产出场景：首轮以 JSON 语义请求；解析失败时把
        原始输出与修复指令追加进对话重试一次（agent/CONSTRAINTS.md 上限），
        仍失败抛 ValidationError（422，三要素完整）。
    参数:
        system — 系统提示词；messages — 对话消息；model — 模型名（None=主模型）。
    返回值: dict[str, Any] — 解析后的 JSON 对象。
    异常:
        ValidationError — 修复重试后仍无法解析为 JSON 对象。
        AgentError — 端点失败 / 超时 / 密钥未配置。
    依赖: chat_turn、_parse_json_payload。
    """
    history = list(messages)
    last_raw = ""
    for attempt in range(_JSON_REPAIR_LIMIT + 1):
        turn = await chat_turn(system, history, model=model)
        last_raw = turn.content or ""
        try:
            return _parse_json_payload(last_raw)
        except ValueError:
            if attempt >= _JSON_REPAIR_LIMIT:
                break
            history = [
                *messages,
                {"role": "assistant", "content": last_raw},
                {
                    "role": "user",
                    "content": "上面的输出不是合法的 JSON 对象。请只输出一个合法 JSON 对象，"
                    "不要包含任何解释文字或代码栅栏。",
                },
            ]
    raise ValidationError(
        problem="LLM 返回内容无法解析为 JSON 草案",
        cause=f"修复重试（{_JSON_REPAIR_LIMIT} 次）后输出仍非合法 JSON 对象",
        fix="重试一次；持续失败请调整任务描述复杂度或更换 LLM_MODEL",
        detail={"raw_prefix": last_raw[:200]},
    )


async def summarize(text: str, instruction: str) -> str:
    """以轻量模型压缩文本（会话滚动摘要等辅助任务的成本分级路由）。

    作用: 固定路由到 config.llm_model_light，把长历史压缩为摘要；
        端点失败包装为 AgentError（摘要失败不阻断主对话由调用方决定降级）。
    参数: text — 待压缩文本；instruction — 压缩要求（保留什么、输出格式）。
    返回值: str — 摘要文本。
    异常:
        AgentError — 密钥未配置 / 端点失败 / 超时。
    依赖: chat_turn、app.config.get_settings。
    """
    settings = get_settings()
    turn = await chat_turn(
        "你是助理，严格按指令压缩文本。",
        [{"role": "user", "content": f"{instruction}\n\n<text>\n{text}\n</text>"}],
        model=settings.llm_model_light,
    )
    return turn.content or ""
