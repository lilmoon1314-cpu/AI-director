"""Mandatory, conservative request admission and per-turn provider limits.

UTF-8 bytes bound ordinary byte-tokenized text conservatively. Protocol reserve is configurable;
this is an application budget, not a claim to know every compatible provider's exact tokenizer.
"""

import json
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.core.exceptions import AgentError


class BudgetError(AgentError):
    code = "AGENT_CONTEXT_BUDGET"


class LimitError(AgentError):
    code = "AGENT_TURN_LIMIT"


def request_tokens(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, settings: Settings
) -> int:
    payload: dict[str, Any] = {"messages": messages}
    if tools:
        payload["tools"] = tools
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        len(encoded.encode("utf-8")) + 16 * len(messages) + settings.agent_protocol_reserve_tokens
    )


def check_request(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, settings: Settings
) -> int:
    tokens = request_tokens(messages, tools, settings)
    if tokens + settings.agent_output_reserve_tokens > settings.agent_context_max_tokens:
        raise BudgetError(
            "本轮上下文超过安全预算，尚未发送模型请求",
            f"保守估算输入 {tokens}，输出预留 {settings.agent_output_reserve_tokens}，"
            f"容量 {settings.agent_context_max_tokens}；未静默丢弃历史约束",
            "缩短输入或开启新会话；长文档请分段处理，必要时核对模型容量后调整上下文预算",
        )
    return tokens


@dataclass
class TurnBudget:
    settings: Settings
    deadline: float
    calls: int = 0

    @classmethod
    def start(cls, settings: Settings) -> "TurnBudget":
        return cls(settings, time.monotonic() + settings.agent_turn_timeout_seconds)

    def remaining(self) -> float:
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise LimitError("本轮达到总时限", "已停止继续请求和工具调用", "缩小任务后重试")
        return seconds

    def admit(self) -> None:
        self.remaining()
        if self.calls >= self.settings.agent_max_model_calls_per_turn:
            raise LimitError("本轮模型请求次数已用完", "补全和摘要共享单轮额度", "缩小任务后重试")
        self.calls += 1


active_budget: ContextVar[TurnBudget | None] = ContextVar("agent_turn_budget", default=None)
