"""Durable chat-run lifecycle, replay, cancellation, and restart reconciliation."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import chat, context, conversations, repository
from app.agent.models import AgentRun, AgentRunEvent, Message
from app.agent.schemas import (
    AgentRunEventRead,
    AgentRunRead,
    ChatRequest,
    generate_message_id,
    generate_run_event_id,
    generate_run_id,
)
from app.agent.scope import context_key
from app.config import Settings
from app.core import db
from app.core.exceptions import ConflictError, NotFoundError
from app.core.observability import emit_event

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_tasks: dict[str, asyncio.Task[None]] = {}
_event_locks: dict[str, asyncio.Lock] = {}


def _run_read(run: AgentRun) -> AgentRunRead:
    return AgentRunRead(
        id=run.id,
        conversation_id=run.conversation_id,
        project_id=run.project_id,
        request_id=run.request_id,
        status=run.status,
        user_message_id=run.user_message_id,
        final_message_id=run.final_message_id,
        error_code=run.error_code,
        error_problem=run.error_problem,
        error_fix=run.error_fix,
        cancel_requested=run.cancel_requested,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _event_read(row: AgentRunEvent) -> AgentRunEventRead:
    return AgentRunEventRead(
        run_id=row.run_id,
        seq=row.seq,
        event=row.event,
        data=json.loads(row.data_json),
        created_at=row.created_at,
    )


def run_not_found(run_id: str) -> NotFoundError:
    return NotFoundError(
        problem="Agent 运行不存在",
        cause=f"run_id '{run_id}' 未在库中",
        fix="重新加载会话并查询最近一次运行",
        detail={"run_id": run_id},
    )


async def create_or_get_run(db_session: AsyncSession, schema: ChatRequest) -> AgentRunRead:
    """Atomically save authored input and a queued, idempotent run."""
    conversation = await conversations.load_conversation(db_session, schema.conversation_id)
    key = context_key(schema.perspective, schema.character_id)
    existing = await repository.get_run_by_request(
        db_session, schema.conversation_id, schema.request_id
    )
    if existing is not None:
        user = await repository.get_message(db_session, existing.user_message_id)
        if (
            user is None
            or user.content != schema.message
            or existing.perspective != schema.perspective
            or existing.character_id != schema.character_id
        ):
            raise ConflictError(
                problem="请求幂等键已用于不同内容",
                cause="同一 conversation_id/request_id 不能代表两个聊天轮次",
                fix="为新消息生成新的 request_id",
            )
        return _run_read(existing)

    user = Message(
        id=generate_message_id(),
        conversation_id=conversation.id,
        role="user",
        context_key=key,
        content=schema.message,
    )
    await repository.add_message(db_session, user)
    if not conversation.title:
        conversation.title = schema.message[:20]
        await repository.save_conversation(db_session, conversation)
    run = AgentRun(
        id=generate_run_id(),
        conversation_id=conversation.id,
        project_id=conversation.project_id,
        request_id=schema.request_id,
        user_message_id=user.id,
        perspective=schema.perspective,
        character_id=schema.character_id,
        status="queued",
    )
    try:
        await repository.add_run(db_session, run)
        await db_session.commit()
    except IntegrityError as exc:
        await db_session.rollback()
        replay = await repository.get_run_by_request(
            db_session, schema.conversation_id, schema.request_id
        )
        if replay is not None:
            return _run_read(replay)
        raise ConflictError(
            problem="该会话已有运行中的回复",
            cause="服务端按会话串行执行聊天轮次",
            fix="等待当前回复完成或先取消，再发送新消息",
        ) from exc
    return _run_read(run)


async def get_run(db_session: AsyncSession, run_id: str) -> AgentRunRead:
    run = await repository.get_run(db_session, run_id)
    if run is None:
        raise run_not_found(run_id)
    return _run_read(run)


async def get_run_by_request(
    db_session: AsyncSession, conversation_id: str, request_id: str
) -> AgentRunRead:
    await conversations.load_conversation(db_session, conversation_id)
    run = await repository.get_run_by_request(db_session, conversation_id, request_id)
    if run is None:
        raise run_not_found(request_id)
    return _run_read(run)


async def get_latest_run(db_session: AsyncSession, conversation_id: str) -> AgentRunRead | None:
    await conversations.load_conversation(db_session, conversation_id)
    run = await repository.latest_run(db_session, conversation_id)
    return _run_read(run) if run is not None else None


async def get_events(
    db_session: AsyncSession, run_id: str, after_seq: int = 0
) -> list[AgentRunEventRead]:
    if await repository.get_run(db_session, run_id) is None:
        raise run_not_found(run_id)
    return [
        _event_read(row) for row in await repository.list_run_events(db_session, run_id, after_seq)
    ]


async def _persist_event(
    run_id: str,
    event: dict[str, Any],
    *,
    terminal_status: str | None = None,
) -> AgentRunEventRead | None:
    lock = _event_locks.setdefault(run_id, asyncio.Lock())
    async with lock:
        factory = db.get_session_factory()
        async with factory() as session:
            run = await repository.get_run(session, run_id)
            if run is None or run.status in TERMINAL_STATUSES:
                return None
            seq = await repository.next_run_event_seq(session, run_id)
            data = dict(event["data"])
            data.update({"run_id": run_id, "seq": seq})
            row = AgentRunEvent(
                id=generate_run_event_id(),
                run_id=run_id,
                seq=seq,
                event=event["event"],
                data_json=json.dumps(data, ensure_ascii=False),
            )
            await repository.add_run_event(session, row)
            if terminal_status is not None:
                run.status = terminal_status
                run.completed_at = datetime.now(UTC)
                if terminal_status == "completed":
                    run.final_message_id = str(data.get("message_id") or "") or None
                else:
                    run.error_code = str(data.get("code") or "AGENT_FAILURE")
                    run.error_problem = str(data.get("problem") or "对话未完成")
                    run.error_fix = str(data.get("fix") or "重新加载会话后重试")
            await session.commit()
            return _event_read(row)


async def _maintain_summary(run_id: str, settings: Settings) -> None:
    factory = db.get_session_factory()
    async with factory() as session:
        try:
            run = await repository.get_run(session, run_id)
            if run is None or run.status != "completed":
                return
            conversation = await conversations.load_conversation(session, run.conversation_id)
            await context.maintain_rolling_summary(
                session,
                conversation,
                settings=settings,
                perspective=run.perspective,  # type: ignore[arg-type]
                character_id=run.character_id,
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - maintenance never changes run outcome
            await session.rollback()
            emit_event(
                "agent_summary_maintenance_failed",
                component="app.agent.runs",
                data={"run_id": run_id, "error": type(exc).__name__},
            )


async def _worker(run_id: str, settings: Settings) -> None:
    factory = db.get_session_factory()
    try:
        async with factory() as session:
            run = await repository.get_run(session, run_id)
            if run is None:
                return
            claimed = await repository.claim_run(session, run_id, datetime.now(UTC))
            await session.commit()
            if not claimed:
                return
            run_data = _run_read(run)
            perspective = run.perspective
            character_id = run.character_id

        terminal = False
        async for event in chat.stream_chat(
            run_data.conversation_id,
            "",
            perspective=perspective,  # type: ignore[arg-type]
            character_id=character_id,
            settings=settings,
            existing_user_message_id=run_data.user_message_id,
            run_id=run_id,
            maintain_summary=False,
        ):
            status = None
            if event["event"] == chat.EVENT_DONE:
                status = "completed"
                terminal = True
            elif event["event"] == chat.EVENT_ERROR:
                status = "failed"
                terminal = True
            await _persist_event(run_id, event, terminal_status=status)
        if not terminal:
            await _persist_event(
                run_id,
                {
                    "event": chat.EVENT_ERROR,
                    "data": {
                        "code": "INTERRUPTED_RUN",
                        "problem": "对话流在完成前中断",
                        "fix": "重新加载会话后重试",
                    },
                },
                terminal_status="failed",
            )
        else:
            await _maintain_summary(run_id, settings)
    except asyncio.CancelledError:
        await _persist_event(
            run_id,
            {
                "event": chat.EVENT_ERROR,
                "data": {
                    "code": "RUN_CANCELLED",
                    "problem": "回复已由用户停止",
                    "fix": "已提交的操作仍以服务器状态为准；可重新发送消息",
                },
            },
            terminal_status="cancelled",
        )
    except Exception as exc:  # noqa: BLE001 - background task must persist a terminal state
        emit_event(
            "agent_run_worker_failed",
            component="app.agent.runs",
            data={"run_id": run_id, "error": type(exc).__name__},
        )
        await _persist_event(
            run_id,
            {
                "event": chat.EVENT_ERROR,
                "data": {
                    "code": "AGENT_FAILURE",
                    "problem": "对话处理失败",
                    "fix": "重新加载会话后重试",
                },
            },
            terminal_status="failed",
        )
    finally:
        _tasks.pop(run_id, None)


def ensure_started(run_id: str, settings: Settings) -> None:
    task = _tasks.get(run_id)
    if task is None or task.done():
        _tasks[run_id] = asyncio.create_task(_worker(run_id, settings), name=f"agent-run:{run_id}")


async def stream_events(
    run_id: str, settings: Settings, *, after_seq: int = 0
) -> AsyncIterator[dict[str, Any]]:
    """Replay persisted frames, then follow until the durable terminal state."""
    cursor = after_seq
    while True:
        factory = db.get_session_factory()
        async with factory() as session:
            run = await repository.get_run(session, run_id)
            if run is None:
                raise run_not_found(run_id)
            rows = await repository.list_run_events(session, run_id, cursor)
            status = run.status
        for row in rows:
            cursor = row.seq
            yield {"event": row.event, "data": json.loads(row.data_json)}
        if status in TERMINAL_STATUSES and not rows:
            return
        await asyncio.sleep(settings.agent_run_event_poll_seconds)


async def cancel_run(db_session: AsyncSession, run_id: str) -> AgentRunRead:
    run = await repository.get_run(db_session, run_id)
    if run is None:
        raise run_not_found(run_id)
    if run.status in TERMINAL_STATUSES:
        return _run_read(run)
    await repository.request_run_cancel(db_session, run_id)
    await db_session.commit()
    await _persist_event(
        run_id,
        {
            "event": chat.EVENT_ERROR,
            "data": {
                "code": "RUN_CANCELLED",
                "problem": "回复已由用户停止",
                "fix": "已提交的操作仍以服务器状态为准；可重新发送消息",
            },
        },
        terminal_status="cancelled",
    )
    task = _tasks.get(run_id)
    if task is not None:
        task.cancel()
    await db_session.refresh(run)
    return _run_read(run)


async def reconcile_interrupted_runs(settings: Settings) -> None:
    """On startup, fail active runs deterministically; never replay model or write calls."""
    factory = db.get_session_factory()
    async with factory() as session:
        ids = list(
            await session.scalars(
                select(AgentRun.id).where(AgentRun.status.in_(("queued", "running")))
            )
        )
    for run_id in ids:
        async with factory() as session:
            assistant = await repository.get_assistant_message_by_run(session, run_id)
        if assistant is not None:
            await _persist_event(
                run_id,
                {"event": chat.EVENT_DONE, "data": {"message_id": assistant.id}},
                terminal_status="completed",
            )
        else:
            await _persist_event(
                run_id,
                {
                    "event": chat.EVENT_ERROR,
                    "data": {
                        "code": "INTERRUPTED_RUN",
                        "problem": "服务重启前的回复未确认完成",
                        "fix": "原用户消息已保留；检查消息与待确认项后再重试",
                    },
                },
                terminal_status="failed",
            )
    async with factory() as session:
        cutoff = datetime.now(UTC) - timedelta(days=settings.agent_run_event_retention_days)
        await repository.delete_expired_run_events(session, cutoff)
        await session.commit()


async def dispose_tasks() -> None:
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()
    _event_locks.clear()
