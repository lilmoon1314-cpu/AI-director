"""Source-backed long-term project memory, conflict, and forgetting owner."""

import hashlib
import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import repository
from app.agent.models import ProjectMemory, ProjectMemorySource, ProjectMemoryTombstone, _utcnow
from app.agent.schemas import (
    ConversationMemoryDeletionPreview,
    MemoryDeletionPreview,
    ProjectMemoryCreate,
    ProjectMemoryDecision,
    ProjectMemoryRead,
    ProjectMemorySourceRead,
    ProjectMemoryUpdate,
    generate_project_memory_id,
    generate_project_memory_source_id,
    generate_project_memory_tombstone_id,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.projects import service as projects_service

ACTIVE_STATUSES = ("proposed", "accepted", "disputed")
_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("constraint", ("必须", "不要", "不能", "禁止", "只能")),
    ("decision", ("决定", "确定", "改为", "撤销", "取消")),
    ("preference", ("我喜欢", "我偏好", "我的偏好", "希望风格")),
    ("open_task", ("待定", "未决", "还没决定", "之后处理")),
)


def _normal(value: str) -> str:
    return " ".join(value.strip().lower().split())


def memory_fingerprint(context_key: str, kind: str, content: str) -> str:
    payload = f"{context_key}\n{kind}\n{_normal(content)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _subject_key(text: str, kind: str) -> str:
    normalized = _normal(text)
    cue_positions = [normalized.find(cue) for _, cues in _CUES for cue in cues if cue in normalized]
    prefix = normalized[: min(cue_positions)] if cue_positions else normalized
    prefix = re.sub(r"[，。！？,:;；\s]+$", "", prefix)
    return f"{kind}:{prefix[:80] or normalized[:80]}"


def _candidate_kind(text: str) -> str | None:
    for kind, cues in _CUES:
        if any(cue in text for cue in cues):
            return kind
    if re.search(r"[“\"「『][^”\"」』]{1,80}[”\"」』]|\d+(?:\.\d+)?", text):
        return "exact_reference"
    return None


async def _read(session: AsyncSession, row: ProjectMemory) -> ProjectMemoryRead:
    sources = await repository.list_project_memory_sources(session, row.id)
    return ProjectMemoryRead(
        id=row.id,
        project_id=row.project_id,
        context_key=row.context_key,
        kind=row.kind,
        subject_key=row.subject_key,
        content=row.content,
        status=row.status,
        origin=row.origin,
        version=row.version,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        sources=[
            ProjectMemorySourceRead(
                id=source.id,
                source_kind=source.source_kind,
                source_id=source.source_id,
                conversation_id=source.conversation_id,
                context_key=source.context_key,
                source_version=source.source_version,
            )
            for source in sources
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _not_found(memory_id: str) -> NotFoundError:
    return NotFoundError(
        problem="长期记忆不存在",
        cause=f"memory_id '{memory_id}' 未在库中",
        fix="刷新长期记忆列表后重试",
    )


async def _claim_version(session: AsyncSession, row: ProjectMemory, expected: int) -> None:
    if not await repository.claim_project_memory_version(session, row.id, expected, _utcnow()):
        await session.refresh(row)
        raise ConflictError(
            problem="长期记忆已被更新",
            cause=f"期望 v{expected}，当前为 v{row.version}",
            fix="刷新来源与状态后再决定",
            detail={"current_version": row.version},
        )
    await session.refresh(row)


async def list_memories(
    session: AsyncSession,
    project_id: str,
    *,
    context_key: str | None = None,
    status: str | None = None,
    query: str = "",
) -> list[ProjectMemoryRead]:
    resolved = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(session, resolved)
    statuses = (status,) if status else ("proposed", "accepted", "superseded", "disputed")
    rows = await repository.list_project_memories(
        session, resolved, context_key=context_key, statuses=statuses, query=query.strip()
    )
    return [await _read(session, row) for row in rows]


async def accepted_for_context(
    session: AsyncSession, project_id: str, context_key: str, *, now: datetime | None = None
) -> list[ProjectMemory]:
    if not hasattr(session, "scalars"):
        return []
    moment = now or _utcnow()
    rows = await repository.list_project_memories(
        session, project_id, context_key=context_key, statuses=("accepted",)
    )
    return [
        row
        for row in rows
        if (row.valid_from is None or row.valid_from <= moment)
        and (row.valid_until is None or row.valid_until > moment)
    ]


async def create_memory(session: AsyncSession, schema: ProjectMemoryCreate) -> ProjectMemoryRead:
    project_id = schema.project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(session, project_id)
    if schema.valid_from and schema.valid_until and schema.valid_from >= schema.valid_until:
        raise ValidationError(
            problem="长期记忆适用时间无效",
            cause="valid_from 必须早于 valid_until",
            fix="调整适用起止时间",
        )
    fingerprint = memory_fingerprint(schema.context_key, schema.kind, schema.content)
    existing = await repository.find_project_memory_by_fingerprint(
        session, project_id, schema.context_key, fingerprint
    )
    if existing is not None:
        if existing.status != "deleted":
            return await _read(session, existing)
        existing.kind = schema.kind
        existing.subject_key = _normal(schema.subject_key)
        existing.content = schema.content.strip()
        existing.status = "accepted"
        existing.origin = "author_decision"
        existing.valid_from = schema.valid_from
        existing.valid_until = schema.valid_until
        existing.version += 1
        existing.updated_at = _utcnow()
        await repository.add_project_memory_source(
            session,
            ProjectMemorySource(
                id=generate_project_memory_source_id(),
                memory_id=existing.id,
                source_kind="manual",
                source_id=f"manual:{existing.id}:v{existing.version}",
                context_key=existing.context_key,
            ),
        )
        await session.commit()
        return await _read(session, existing)
    row = ProjectMemory(
        id=generate_project_memory_id(),
        project_id=project_id,
        context_key=schema.context_key,
        kind=schema.kind,
        subject_key=_normal(schema.subject_key),
        content=schema.content.strip(),
        fingerprint=fingerprint,
        status="accepted",
        origin="author_decision",
        valid_from=schema.valid_from,
        valid_until=schema.valid_until,
    )
    await repository.add_project_memory(session, row)
    await repository.add_project_memory_source(
        session,
        ProjectMemorySource(
            id=generate_project_memory_source_id(),
            memory_id=row.id,
            source_kind="manual",
            source_id=f"manual:{row.id}",
            context_key=row.context_key,
        ),
    )
    conflicts = await repository.active_memories_for_subject(
        session, project_id, row.context_key, row.subject_key, exclude_id=row.id
    )
    if any(item.content != row.content for item in conflicts):
        row.status = "disputed"
        row.version += 1
        for item in conflicts:
            item.status = "disputed"
            item.version += 1
    await session.commit()
    return await _read(session, row)


async def extract_candidate(
    session: AsyncSession,
    *,
    project_id: str,
    conversation_id: str,
    context_key: str,
    source_message_id: str,
    content: str,
) -> ProjectMemoryRead | None:
    if not hasattr(session, "scalars"):
        return None
    kind = _candidate_kind(content)
    if kind is None:
        return None
    fingerprint = memory_fingerprint(context_key, kind, content)
    if await repository.has_memory_tombstone(session, project_id, context_key, fingerprint):
        return None
    existing = await repository.find_project_memory_by_fingerprint(
        session, project_id, context_key, fingerprint
    )
    if existing is not None:
        sources = await repository.list_project_memory_sources(session, existing.id)
        if not any(source.source_id == source_message_id for source in sources):
            await repository.add_project_memory_source(
                session,
                ProjectMemorySource(
                    id=generate_project_memory_source_id(),
                    memory_id=existing.id,
                    source_kind="message",
                    source_id=source_message_id,
                    conversation_id=conversation_id,
                    context_key=context_key,
                ),
            )
        return await _read(session, existing)
    row = ProjectMemory(
        id=generate_project_memory_id(),
        project_id=project_id,
        context_key=context_key,
        kind=kind,
        subject_key=_subject_key(content, kind),
        content=content.strip(),
        fingerprint=fingerprint,
        status="proposed",
        origin="model_suggestion",
    )
    await repository.add_project_memory(session, row)
    await repository.add_project_memory_source(
        session,
        ProjectMemorySource(
            id=generate_project_memory_source_id(),
            memory_id=row.id,
            source_kind="message",
            source_id=source_message_id,
            conversation_id=conversation_id,
            context_key=context_key,
        ),
    )
    return await _read(session, row)


async def accept_memory(
    session: AsyncSession, memory_id: str, schema: ProjectMemoryDecision
) -> ProjectMemoryRead:
    row = await repository.get_project_memory(session, memory_id)
    if row is None or row.status == "deleted":
        raise _not_found(memory_id)
    await _claim_version(session, row, schema.expected_version)
    conflicts = await repository.active_memories_for_subject(
        session, row.project_id, row.context_key, row.subject_key, exclude_id=row.id
    )
    if any(item.content != row.content for item in conflicts):
        row.status = "disputed"
        for item in conflicts:
            item.status = "disputed"
            item.version += 1
            item.updated_at = _utcnow()
    else:
        row.status = "accepted"
    row.updated_at = _utcnow()
    await session.commit()
    return await _read(session, row)


async def update_memory(
    session: AsyncSession, memory_id: str, schema: ProjectMemoryUpdate
) -> ProjectMemoryRead:
    row = await repository.get_project_memory(session, memory_id)
    if row is None or row.status == "deleted":
        raise _not_found(memory_id)
    if schema.valid_from and schema.valid_until and schema.valid_from >= schema.valid_until:
        raise ValidationError(
            problem="长期记忆适用时间无效",
            cause="valid_from 必须早于 valid_until",
            fix="调整适用起止时间",
        )
    new_fingerprint = memory_fingerprint(row.context_key, schema.kind, schema.content)
    duplicate = await repository.find_project_memory_by_fingerprint(
        session, row.project_id, row.context_key, new_fingerprint
    )
    if duplicate is not None and duplicate.id != row.id:
        raise ConflictError(
            problem="已有相同的长期记忆",
            cause=f"memory_id '{duplicate.id}' 内容相同",
            fix="使用已有记忆或先处理其状态",
            detail={"existing_memory_id": duplicate.id},
        )
    await _claim_version(session, row, schema.expected_version)
    old_fingerprint = row.fingerprint
    row.kind = schema.kind
    row.subject_key = _normal(schema.subject_key)
    row.content = schema.content.strip()
    row.fingerprint = new_fingerprint
    row.valid_from = schema.valid_from
    row.valid_until = schema.valid_until
    row.origin = "author_decision"
    row.status = "accepted"
    row.updated_at = _utcnow()
    if old_fingerprint != row.fingerprint and not await repository.has_memory_tombstone(
        session, row.project_id, row.context_key, old_fingerprint
    ):
        await repository.add_memory_tombstone(
            session,
            ProjectMemoryTombstone(
                id=generate_project_memory_tombstone_id(),
                project_id=row.project_id,
                context_key=row.context_key,
                fingerprint=old_fingerprint,
                reason="edited",
            ),
        )
    conflicts = await repository.active_memories_for_subject(
        session, row.project_id, row.context_key, row.subject_key, exclude_id=row.id
    )
    if any(item.content != row.content for item in conflicts):
        row.status = "disputed"
        for item in conflicts:
            item.status = "disputed"
            item.version += 1
    await session.commit()
    return await _read(session, row)


async def resolve_memory(
    session: AsyncSession, memory_id: str, schema: ProjectMemoryDecision
) -> ProjectMemoryRead:
    row = await repository.get_project_memory(session, memory_id)
    if row is None or row.status == "deleted":
        raise _not_found(memory_id)
    await _claim_version(session, row, schema.expected_version)
    related = await repository.active_memories_for_subject(
        session, row.project_id, row.context_key, row.subject_key, exclude_id=row.id
    )
    row.status = "accepted"
    row.origin = "author_decision"
    row.updated_at = _utcnow()
    for item in related:
        item.status = "superseded"
        item.version += 1
        item.valid_until = row.updated_at
        item.updated_at = row.updated_at
    await session.commit()
    return await _read(session, row)


async def deletion_preview(session: AsyncSession, memory_id: str) -> MemoryDeletionPreview:
    row = await repository.get_project_memory(session, memory_id)
    if row is None or row.status == "deleted":
        raise _not_found(memory_id)
    sources = await repository.list_project_memory_sources(session, row.id)
    return MemoryDeletionPreview(
        memory_id=row.id,
        source_count=len(sources),
        source_conversation_ids=sorted(
            {source.conversation_id for source in sources if source.conversation_id}
        ),
        effect="忘记该派生记忆并建立墓碑；原始会话和作品内容不删除。",
    )


async def forget_memory(
    session: AsyncSession, memory_id: str, schema: ProjectMemoryDecision
) -> None:
    row = await repository.get_project_memory(session, memory_id)
    if row is None or row.status == "deleted":
        raise _not_found(memory_id)
    await _claim_version(session, row, schema.expected_version)
    if not await repository.has_memory_tombstone(
        session, row.project_id, row.context_key, row.fingerprint
    ):
        await repository.add_memory_tombstone(
            session,
            ProjectMemoryTombstone(
                id=generate_project_memory_tombstone_id(),
                project_id=row.project_id,
                context_key=row.context_key,
                fingerprint=row.fingerprint,
                reason="explicit_forget",
            ),
        )
    row.status = "deleted"
    row.content = ""
    row.subject_key = "forgotten"
    row.updated_at = _utcnow()
    await session.commit()


async def conversation_deletion_preview(
    session: AsyncSession, conversation_id: str
) -> ConversationMemoryDeletionPreview:
    sources = await repository.list_memory_sources_for_conversation(session, conversation_id)
    accepted: list[str] = []
    derived: list[str] = []
    multi: list[str] = []
    for source in sources:
        row = await repository.get_project_memory(session, source.memory_id)
        if row is None or row.status == "deleted":
            continue
        all_sources = await repository.list_project_memory_sources(session, row.id)
        if len(all_sources) > 1:
            multi.append(row.id)
        elif row.status == "accepted":
            accepted.append(row.id)
        else:
            derived.append(row.id)
    return ConversationMemoryDeletionPreview(
        conversation_id=conversation_id,
        accepted_retained=sorted(set(accepted)),
        derived_deleted=sorted(set(derived)),
        multi_source_retained=sorted(set(multi)),
    )


async def prepare_conversation_delete(session: AsyncSession, conversation_id: str) -> None:
    if not hasattr(session, "scalars"):
        return
    sources = await repository.list_memory_sources_for_conversation(session, conversation_id)
    for source in sources:
        row = await repository.get_project_memory(session, source.memory_id)
        if row is None or row.status == "deleted":
            continue
        all_sources = await repository.list_project_memory_sources(session, row.id)
        other_sources = [item for item in all_sources if item.id != source.id]
        if other_sources or row.status == "accepted":
            await repository.delete_project_memory_source(session, source)
            continue
        if not await repository.has_memory_tombstone(
            session, row.project_id, row.context_key, row.fingerprint
        ):
            await repository.add_memory_tombstone(
                session,
                ProjectMemoryTombstone(
                    id=generate_project_memory_tombstone_id(),
                    project_id=row.project_id,
                    context_key=row.context_key,
                    fingerprint=row.fingerprint,
                    reason="source_conversation_deleted",
                ),
            )
        row.status = "deleted"
        row.content = ""
        row.subject_key = "forgotten"
        row.version += 1
