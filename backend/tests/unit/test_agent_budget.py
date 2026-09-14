"""B admission boundaries use fake SDKs only; exact-boundary and subsequent-call evidence."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent import llm
from app.agent.budget import (
    BudgetError,
    LimitError,
    TurnBudget,
    active_budget,
    check_request,
    request_tokens,
)
from app.config import Settings


@pytest.mark.parametrize("text", ["abc" * 20, "中" * 100, "👩🏽‍💻" * 50])
@pytest.mark.parametrize(
    "schemas", [None, [{"function": {"name": "tool", "description": "界" * 200}}]]
)
def test_exact_request_boundary_counts_utf8_schema_and_reserve(text, schemas):
    settings = Settings(_env_file=None)
    messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": text}]
    needed = request_tokens(messages, schemas, settings) + settings.agent_output_reserve_tokens
    settings.agent_context_max_tokens = needed
    assert (
        check_request(messages, schemas, settings) == needed - settings.agent_output_reserve_tokens
    )
    settings.agent_context_max_tokens -= 1
    with pytest.raises(BudgetError):
        check_request(messages, schemas, settings)


@pytest.mark.parametrize("path", ["chat", "stream", "summary"])
async def test_provider_not_even_created_for_overbudget_request(monkeypatch, path):
    settings = Settings(_env_file=None, agent_context_max_tokens=200)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    created = []

    def forbidden():
        created.append(True)
        raise AssertionError("must reject before SDK construction")

    monkeypatch.setattr(llm, "get_client", forbidden)
    with pytest.raises(BudgetError):
        if path == "chat":
            await llm.chat_turn("rules", [{"role": "user", "content": "中" * 8000}])
        elif path == "stream":
            _ = [
                event
                async for event in llm.stream_chat_turn(
                    "rules", [{"role": "user", "content": "中" * 8000}]
                )
            ]
        else:
            await llm.summarize("中" * 8000, "压缩")
    assert created == []


async def test_json_repair_is_rechecked_and_does_not_send_oversized_previous_output(monkeypatch):
    settings = Settings(_env_file=None, agent_context_max_tokens=3000)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    response = SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content="中" * 2000, tool_calls=[]))],
    )
    create = AsyncMock(return_value=response)
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    with pytest.raises(BudgetError):
        await llm.complete_json("rules", [{"role": "user", "content": "JSON"}])
    assert create.await_count == 1
    assert create.call_args.kwargs["max_tokens"] == settings.agent_output_reserve_tokens
    assert active_budget.get() is None


async def test_summary_uses_remaining_turn_call_quota(monkeypatch):
    settings = Settings(_env_file=None, agent_max_model_calls_per_turn=1)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    limiter = TurnBudget.start(settings)
    limiter.admit()
    token = active_budget.set(limiter)
    try:
        with pytest.raises(LimitError):
            await llm.summarize("short", "compress")
    finally:
        active_budget.reset(token)


async def test_stream_timeout_closes_provider(monkeypatch):
    import asyncio

    settings = Settings(_env_file=None, agent_turn_timeout_seconds=0.02)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    class Stream:
        closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(10)
            raise StopAsyncIteration

        async def close(self):
            self.closed = True

    stream = Stream()
    create = AsyncMock(return_value=stream)
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    with pytest.raises(llm.AgentError):
        _ = [event async for event in llm.stream_chat_turn("rules", [])]
    assert stream.closed
