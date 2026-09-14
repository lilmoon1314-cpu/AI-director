"""Agent streaming chat orchestration owner."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any

from app.agent import context, conversations, llm, repository, tools, writes
from app.agent.budget import LimitError, TurnBudget, active_budget, check_request
from app.agent.models import Message
from app.agent.prompts import wrap_data
from app.agent.schemas import Perspective, generate_message_id
from app.agent.scope import context_key
from app.config import Settings
from app.core import db
from app.core.exceptions import AgentError
from app.core.observability import emit_event

EVENT_MESSAGE_START = "message_start"
EVENT_TOKEN = "token"
EVENT_REASONING = "reasoning"
EVENT_USAGE = "usage"
EVENT_TOOL = "tool"
EVENT_DRAFT = "draft"
EVENT_DOC_PATCH = "doc_patch"
EVENT_ASK_USER = "ask_user"
EVENT_DONE = "done"
EVENT_ERROR = "error"


def _review_text(text: str, settings: Settings) -> str | None:
    if not settings.agent_content_review_enabled:
        return None
    for word in settings.agent_content_review_words.split(","):
        word = word.strip()
        if word and word in text:
            return word
    return None


async def stream_chat(
    conversation_id: str,
    message: str,
    *,
    perspective: Perspective,
    character_id: str = "",
    settings: Settings,
) -> AsyncIterator[dict[str, Any]]:
    """Run one durable, bounded streaming turn and yield the established SSE events."""
    factory = db.get_session_factory()
    async with factory() as db_session:
        conversation = await conversations.load_conversation(db_session, conversation_id)
        yield {"event": EVENT_MESSAGE_START, "data": {"conversation_id": conversation_id}}

        violation = _review_text(message, settings)
        if violation:
            yield {
                "event": EVENT_ERROR,
                "data": {
                    "code": "CONTENT_REVIEW_BLOCKED",
                    "problem": "输入未通过内容合规审核",
                    "cause": f"命中敏感词「{violation}」",
                    "fix": "调整表述后重发；如为误判可在 .env 调整敏感词表",
                },
            }
            return

        try:
            key = context_key(perspective, character_id)
        except AgentError as exc:
            yield {
                "event": EVENT_ERROR,
                "data": {
                    "code": exc.code,
                    "problem": exc.problem,
                    "cause": exc.cause,
                    "fix": exc.fix,
                },
            }
            return
        user_row = Message(
            id=generate_message_id(),
            conversation_id=conversation_id,
            role="user",
            context_key=key,
            content=message,
        )
        await repository.add_message(db_session, user_row)
        if not conversation.title:
            conversation.title = message[:20]
            await repository.save_conversation(db_session, conversation)
        await db_session.commit()

        limiter = TurnBudget.start(settings)
        budget_token = active_budget.set(limiter)
        try:
            async with asyncio.timeout(limiter.remaining()):
                messages = await context.assemble_chat_context(
                    db_session,
                    conversation,
                    perspective=perspective,
                    character_id=character_id,
                    user_message=message,
                    settings=settings,
                    exclude_message_id=user_row.id,
                    tool_specs=tools.specs_for(perspective)
                    if settings.agent_max_tool_calls_per_turn
                    else None,
                )
                tool_context = tools.ToolContext(
                    session=db_session,
                    project_id=conversation.project_id,
                    perspective=perspective,
                    character_id=character_id,
                    conversation_id=conversation_id,
                )
                used = 0
                failures: dict[str, int] = {}
                call_ids: set[str] = set()
                final_usage: dict[str, int | None] | None = None
                turn: llm.AssistantTurn | None = None
                while True:
                    enable_tools = used < settings.agent_max_tool_calls_per_turn
                    specs = tools.specs_for(perspective) if enable_tools else None
                    check_request(messages, specs, settings)
                    limiter.admit()
                    turn_reasoning: list[str] = []
                    turn = None
                    async with aclosing(
                        llm.stream_chat_turn(
                            messages[0]["content"],
                            messages[1:],
                            tools=specs,
                        )
                    ) as provider_stream:
                        async for kind, payload in provider_stream:
                            if kind == "reasoning_delta":
                                turn_reasoning.append(str(payload))
                                yield {"event": EVENT_REASONING, "data": {"text": payload}}
                            elif kind == "content_delta":
                                yield {"event": EVENT_TOKEN, "data": {"text": payload}}
                            elif kind == "usage":
                                final_usage = payload
                            elif kind == "turn":
                                turn = payload
                    if turn is None:
                        raise AgentError(
                            problem="LLM 流式响应中断",
                            cause="流式补全未产出聚合结果即结束",
                            fix="重试一次；持续出现请检查 LLM 端点稳定性",
                        )
                    if turn.tool_calls and not enable_tools:
                        raise LimitError(
                            "模型未遵守工具禁用要求", "没有执行额外调用", "简化任务后重试"
                        )
                    if turn.tool_calls and enable_tools:
                        ids = [call.call_id for call in turn.tool_calls]
                        if (
                            any(not call_id for call_id in ids)
                            or len(set(ids)) != len(ids)
                            or call_ids.intersection(ids)
                        ):
                            raise LimitError(
                                "模型工具调用标识无效",
                                "无法建立完整的调用与结果配对",
                                "重新发起本轮",
                            )
                        call_ids.update(ids)
                        messages.append(
                            {
                                "role": "assistant",
                                "content": turn.content,
                                "tool_calls": [
                                    {
                                        "id": call.call_id,
                                        "type": "function",
                                        "function": {
                                            "name": call.name,
                                            "arguments": call.arguments,
                                        },
                                    }
                                    for call in turn.tool_calls
                                ],
                            }
                        )
                        for call in turn.tool_calls:
                            if used >= settings.agent_max_tool_calls_per_turn:
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": call.call_id,
                                        "content": "TOOL_QUOTA_EXCEEDED: 未执行，工具额度已用完",
                                    }
                                )
                                continue
                            try:
                                normalized = json.dumps(json.loads(call.arguments), sort_keys=True)
                            except (ValueError, TypeError):
                                normalized = call.arguments
                            signature = call.name + ":" + normalized
                            if (
                                failures.get(signature, 0)
                                >= settings.agent_max_repeated_tool_failures
                            ):
                                raise LimitError(
                                    "工具连续失败，已停止本轮", "相同调用未能修复", "调整请求后重试"
                                )
                            yield {
                                "event": EVENT_TOOL,
                                "data": {"name": call.name, "phase": "start"},
                            }
                            used += 1
                            # Abort on timeout; pending flushes roll back without retry.
                            try:
                                async with asyncio.timeout(
                                    min(settings.agent_tool_timeout_seconds, limiter.remaining())
                                ):
                                    result = await tools.execute_tool(
                                        call.name, call.arguments, tool_context
                                    )
                            except TimeoutError as exc:
                                raise LimitError(
                                    "工具执行超时，本轮已停止",
                                    "没有自动重试写入",
                                    "缩小查询或重新读取状态后重试",
                                ) from exc
                            if result.startswith("工具执行失败"):
                                failures[signature] = failures.get(signature, 0) + 1
                            yield {
                                "event": EVENT_TOOL,
                                "data": {"name": call.name, "phase": "done", "calls_used": used},
                            }
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.call_id,
                                    "content": wrap_data(
                                        f"工具 {call.name} 结果",
                                        tools.page_result(
                                            result,
                                            tool_context,
                                            settings.agent_tool_output_max_chars,
                                        ),
                                    ),
                                }
                            )
                        continue
                    if turn.content is not None and turn.content.strip():
                        final_reasoning = "".join(turn_reasoning)
                        break
                    raise AgentError(
                        problem="LLM 返回了空回复",
                        cause="补全结果既无文本内容也无工具调用",
                        fix="重试一次；持续出现请更换 LLM_MODEL 或简化问题",
                    )

                assistant_row = Message(
                    id=generate_message_id(),
                    conversation_id=conversation_id,
                    role="assistant",
                    context_key=key,
                    content=turn.content or "",
                    reasoning=final_reasoning or None,
                    prompt_tokens=(final_usage or {}).get("prompt_tokens"),
                    completion_tokens=(final_usage or {}).get("completion_tokens"),
                )
                await repository.add_message(db_session, assistant_row)
                await context.maintain_rolling_summary(
                    db_session,
                    conversation,
                    settings=settings,
                    perspective=perspective,
                    character_id=character_id,
                )
                pending_payload: dict[str, Any] | None = None
                if tool_context.pending_writes:
                    pending_payload = {
                        "pending_writes": [
                            writes.pending_read(row).model_dump(mode="json")
                            for row in tool_context.pending_writes
                        ]
                    }
                await db_session.commit()
                if final_usage is not None:
                    prompt_tokens = final_usage.get("prompt_tokens") or 0
                    max_tokens = settings.agent_context_max_tokens
                    yield {
                        "event": EVENT_USAGE,
                        "data": {
                            "prompt_tokens": final_usage.get("prompt_tokens"),
                            "completion_tokens": final_usage.get("completion_tokens"),
                            "context_max_tokens": max_tokens,
                            "context_ratio": (
                                prompt_tokens / max_tokens if max_tokens > 0 else None
                            ),
                        },
                    }
                done_data: dict[str, Any] = {"message_id": assistant_row.id}
                if pending_payload is not None:
                    done_data.update(pending_payload)
                yield {"event": EVENT_DONE, "data": done_data}
        except Exception as exc:  # noqa: BLE001 - turn failures are SSE payloads
            await db_session.rollback()
            if isinstance(exc, TimeoutError):
                exc = LimitError("本轮达到总时限，已停止", "请求未在时限内完成", "缩小任务后重试")
            if isinstance(exc, llm.AgentError):
                payload = {
                    "code": exc.code,
                    "problem": exc.problem,
                    "cause": exc.cause,
                    "fix": exc.fix,
                }
            else:
                emit_event(
                    "agent_turn_failed",
                    component="app.agent.service",
                    data={"error": type(exc).__name__},
                )
                payload = {
                    "code": "AGENT_FAILURE",
                    "problem": "对话处理失败",
                    "cause": f"内部错误（{type(exc).__name__}），详情见服务端日志",
                    "fix": "重试；持续失败请检查服务端 runtime_error 日志",
                }
            yield {"event": EVENT_ERROR, "data": payload}
        finally:
            active_budget.reset(budget_token)
