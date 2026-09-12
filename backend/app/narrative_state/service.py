"""Application boundary for Narrative State Core."""

from copy import deepcopy
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import service as artifacts_service
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.entities import service as entities_service
from app.narrative_state import repository
from app.narrative_state.models import (
    Claim,
    KnowledgeState,
    NarrativeTimepoint,
    StateCurrent,
    StateEvent,
    StateSnapshot,
)
from app.narrative_state.schemas import (
    ClaimCreate,
    ClaimRead,
    EventApplicationRead,
    KnowledgeStateCreate,
    KnowledgeStateRead,
    SnapshotCreate,
    SnapshotRead,
    StateCurrentRead,
    StateEventCreate,
    StateEventRead,
    TimepointCreate,
    TimepointRead,
    generate_id,
)
from app.projects import service as projects_service
from app.relations import service as relations_service

_STATEFUL_ATTRIBUTES: dict[str, set[str]] = {
    "entity": {"condition", "current_location"},
    "relationship": {"trust", "resentment"},
}


def _not_found(kind: str, row_id: str) -> NotFoundError:
    return NotFoundError(
        problem=f"{kind} 不存在",
        cause=f"id '{row_id}' 未在当前 Narrative State 数据中",
        fix="确认项目和资源 id 后重试",
        detail={"resource_type": kind, "resource_id": row_id},
    )


def _invalid(problem: str, cause: str, fix: str, **detail: object) -> ValidationError:
    return ValidationError(problem=problem, cause=cause, fix=fix, detail=detail)


async def _require_timepoint(
    session: AsyncSession, timepoint_id: str, project_id: str
) -> NarrativeTimepoint:
    row = await repository.get_timepoint(session, timepoint_id)
    if row is None:
        raise _not_found("timepoint", timepoint_id)
    if row.project_id != project_id:
        raise _invalid(
            "跨项目 timepoint 引用被拒绝",
            "timepoint 与请求的 project_id 不一致",
            "使用同一项目的 timepoint",
            timepoint_id=timepoint_id,
            project_id=project_id,
        )
    return row


async def _require_subject(
    session: AsyncSession, subject_type: str, subject_id: str, project_id: str
) -> None:
    if subject_type == "entity":
        subject_project_id = (await entities_service.get(session, subject_id)).project_id
    else:
        subject_project_id = (await relations_service.get(session, subject_id)).project_id
    if subject_project_id != project_id:
        raise _invalid(
            "跨项目 state subject 引用被拒绝",
            "subject 与 event 的 project_id 不一致",
            "使用同一项目内的 subject",
            subject_id=subject_id,
            project_id=project_id,
        )


async def _validate_provenance(session: AsyncSession, schema: StateEventCreate) -> None:
    if schema.source_artifact_id is None or schema.source_revision_id is None:
        return
    artifact = await artifacts_service.get(session, schema.source_artifact_id)
    if artifact.project_id != schema.project_id:
        raise _invalid(
            "跨项目 artifact provenance 被拒绝",
            "source artifact 与 state event 不属于同一项目",
            "使用同一项目的 artifact revision",
            artifact_id=artifact.id,
            project_id=schema.project_id,
        )
    await artifacts_service.get_revision(session, artifact.id, schema.source_revision_id)


def _reduce(operation: str, current: Any, value: Any, expected_before: Any) -> Any:
    if expected_before is not None and current != expected_before:
        raise ConflictError(
            problem="state transition 的前置值不匹配",
            cause="expected_before 与当前物化值不同",
            fix="读取最新 current/version 后创建新的 compensation 或 transition event",
            detail={"expected_before": expected_before, "current": current},
        )
    if operation in {"set", "transition"}:
        return deepcopy(value)
    if current is None:
        current = []
    if not isinstance(current, list):
        raise _invalid(
            "add/remove 只适用于列表状态",
            "当前物化值不是 list",
            "改用 set/transition，或先把属性设置为 list",
            current_type=type(current).__name__,
        )
    result = deepcopy(current)
    if operation == "add":
        if value not in result:
            result.append(deepcopy(value))
    elif value in result:
        result.remove(value)
    return result


@checkpoint
async def create_timepoint(session: AsyncSession, schema: TimepointCreate) -> TimepointRead:
    await projects_service.ensure_exists(session, schema.project_id)
    row = NarrativeTimepoint(id=generate_id("tp"), **schema.model_dump())
    try:
        await repository.add(session, row)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            problem="timepoint sequence 已存在",
            cause=f"项目内 sequence_no={schema.sequence_no} 必须唯一",
            fix="使用未占用的 project-local sequence_no",
            detail={"project_id": schema.project_id, "sequence_no": schema.sequence_no},
        ) from None
    return TimepointRead.model_validate(row)


@checkpoint
async def apply_event(session: AsyncSession, schema: StateEventCreate) -> EventApplicationRead:
    await projects_service.ensure_exists(session, schema.project_id)
    timepoint = await _require_timepoint(session, schema.timepoint_id, schema.project_id)
    await _require_subject(session, schema.subject_type, schema.subject_id, schema.project_id)
    allowed = _STATEFUL_ATTRIBUTES[schema.subject_type]
    if schema.attribute_key not in allowed:
        raise _invalid(
            "R3 attribute 尚未注册为 stateful",
            f"{schema.subject_type}.{schema.attribute_key} 不在 R3 有限迁移集合",
            f"本阶段可用属性: {', '.join(sorted(allowed))}",
            attribute_key=schema.attribute_key,
        )
    await _validate_provenance(session, schema)
    if schema.compensates_event_id is not None:
        compensated = await repository.get_event(session, schema.compensates_event_id)
        if compensated is None:
            raise _not_found("state event", schema.compensates_event_id)
        if compensated.project_id != schema.project_id:
            raise _invalid(
                "跨项目 compensation 被拒绝",
                "被纠正的 event 不属于当前项目",
                "选择同一项目内的 event",
            )

    current = await repository.get_current(
        session,
        schema.project_id,
        schema.subject_type,
        schema.subject_id,
        schema.attribute_key,
    )
    if current is not None:
        previous_timepoint = await _require_timepoint(
            session, current.timepoint_id, schema.project_id
        )
        if timepoint.sequence_no < previous_timepoint.sequence_no:
            raise _invalid(
                "state event 不能倒退 current 的故事时间",
                "event timepoint 早于当前物化状态的 timepoint",
                "使用同一或更晚的 timepoint；历史纠错仍应追加 compensation event",
                current_sequence=previous_timepoint.sequence_no,
                event_sequence=timepoint.sequence_no,
            )
    before = None if current is None else deepcopy(current.value_json)
    after = _reduce(schema.operation, before, schema.value, schema.expected_before)
    event = StateEvent(
        id=generate_id("ste"),
        project_id=schema.project_id,
        subject_type=schema.subject_type,
        subject_id=schema.subject_id,
        attribute_key=schema.attribute_key,
        operation=schema.operation,
        before_json=before,
        after_json=after,
        timepoint_id=schema.timepoint_id,
        cause_type=schema.cause_type,
        cause_ref=schema.cause_ref,
        source_artifact_id=schema.source_artifact_id,
        source_revision_id=schema.source_revision_id,
        compensates_event_id=schema.compensates_event_id,
    )
    await repository.add(session, event)
    if current is None:
        current = StateCurrent(
            id=generate_id("cur"),
            project_id=schema.project_id,
            subject_type=schema.subject_type,
            subject_id=schema.subject_id,
            attribute_key=schema.attribute_key,
            value_json=after,
            last_event_id=event.id,
            timepoint_id=schema.timepoint_id,
            version=1,
        )
        await repository.add(session, current)
    else:
        current.value_json = after
        current.last_event_id = event.id
        current.timepoint_id = schema.timepoint_id
        current.version += 1
        await session.flush()
    if schema.subject_type == "relationship":
        await relations_service.sync_stateful_projection(
            session, schema.subject_id, schema.attribute_key, after
        )
    await projects_service.touch(session, schema.project_id)
    await session.commit()
    return EventApplicationRead(
        event=StateEventRead.model_validate(event),
        current=StateCurrentRead.model_validate(current),
    )


async def sync_legacy_relationship_state(
    session: AsyncSession,
    project_id: str,
    relationship_id: str,
    values: dict[str, float],
) -> None:
    """Keep legacy relationship writes as event-backed compatibility projections."""
    if not values:
        return
    baseline = await repository.get_timepoint_by_sequence(session, project_id, 0)
    for attribute_key, value in values.items():
        current = await repository.get_current(
            session, project_id, "relationship", relationship_id, attribute_key
        )
        before = None if current is None else deepcopy(current.value_json)
        if before == value:
            continue
        if current is None and baseline is None:
            baseline = NarrativeTimepoint(
                id=generate_id("tp"),
                project_id=project_id,
                sequence_no=0,
                world_time=None,
            )
            await repository.add(session, baseline)
        if current is not None:
            event_timepoint_id = current.timepoint_id
        else:
            assert baseline is not None
            event_timepoint_id = baseline.id
        event = StateEvent(
            id=generate_id("ste"),
            project_id=project_id,
            subject_type="relationship",
            subject_id=relationship_id,
            attribute_key=attribute_key,
            operation="set",
            before_json=before,
            after_json=value,
            timepoint_id=event_timepoint_id,
            cause_type="user_edit",
            cause_ref="relations_api_compatibility",
        )
        await repository.add(session, event)
        if current is None:
            await repository.add(
                session,
                StateCurrent(
                    id=generate_id("cur"),
                    project_id=project_id,
                    subject_type="relationship",
                    subject_id=relationship_id,
                    attribute_key=attribute_key,
                    value_json=value,
                    last_event_id=event.id,
                    timepoint_id=event_timepoint_id,
                    version=1,
                ),
            )
        else:
            current.value_json = value
            current.last_event_id = event.id
            current.timepoint_id = event_timepoint_id
            current.version += 1
            await session.flush()


@checkpoint
async def get_event(session: AsyncSession, event_id: str) -> StateEventRead:
    row = await repository.get_event(session, event_id)
    if row is None:
        raise _not_found("state event", event_id)
    return StateEventRead.model_validate(row)


@checkpoint
async def get_current(
    session: AsyncSession,
    project_id: str,
    subject_type: str,
    subject_id: str,
    attribute_key: str,
) -> StateCurrentRead:
    row = await repository.get_current(session, project_id, subject_type, subject_id, attribute_key)
    if row is None:
        raise _not_found("current state", f"{subject_type}:{subject_id}:{attribute_key}")
    return StateCurrentRead.model_validate(row)


@checkpoint
async def create_snapshot(session: AsyncSession, schema: SnapshotCreate) -> SnapshotRead:
    await projects_service.ensure_exists(session, schema.project_id)
    await _require_timepoint(session, schema.timepoint_id, schema.project_id)
    current = await repository.list_current(session, schema.project_id)
    values = [
        {
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "attribute_key": row.attribute_key,
            "value": deepcopy(row.value_json),
            "version": row.version,
            "last_event_id": row.last_event_id,
            "timepoint_id": row.timepoint_id,
        }
        for row in current
    ]
    latest_event = await repository.get_latest_event(session, schema.project_id)
    cursor = None if latest_event is None else latest_event.id
    row = StateSnapshot(
        id=generate_id("snp"),
        snapshot_json=values,
        source_event_cursor=cursor,
        **schema.model_dump(),
    )
    await repository.add(session, row)
    await session.commit()
    return SnapshotRead.model_validate(row)


@checkpoint
async def get_snapshot(session: AsyncSession, snapshot_id: str) -> SnapshotRead:
    row = await repository.get_snapshot(session, snapshot_id)
    if row is None:
        raise _not_found("snapshot", snapshot_id)
    return SnapshotRead.model_validate(row)


@checkpoint
async def create_claim(session: AsyncSession, schema: ClaimCreate) -> ClaimRead:
    await projects_service.ensure_exists(session, schema.project_id)
    row = Claim(id=generate_id("clm"), **schema.model_dump())
    await repository.add(session, row)
    await projects_service.touch(session, schema.project_id)
    await session.commit()
    return ClaimRead.model_validate(row)


@checkpoint
async def set_knowledge(session: AsyncSession, schema: KnowledgeStateCreate) -> KnowledgeStateRead:
    await projects_service.ensure_exists(session, schema.project_id)
    claim = await repository.get_claim(session, schema.claim_id)
    if claim is None:
        raise _not_found("claim", schema.claim_id)
    if claim.project_id != schema.project_id:
        raise _invalid(
            "跨项目 claim knowledge 被拒绝",
            "claim 与 knowledge state 不属于同一项目",
            "使用同一项目内的 claim",
        )
    await _require_timepoint(session, schema.acquired_timepoint_id, schema.project_id)
    if schema.knower_type == "character":
        assert schema.knower_id is not None
        character = await entities_service.get(session, schema.knower_id)
        if character.project_id != schema.project_id or character.type != "character":
            raise _invalid(
                "knowledge knower 必须是同项目角色",
                "knower_id 不属于当前项目或不是 character",
                "选择同项目 character entity",
                knower_id=schema.knower_id,
            )
    previous = await repository.get_current_knowledge(
        session, schema.project_id, schema.claim_id, schema.knower_type, schema.knower_id
    )
    row = KnowledgeState(id=generate_id("knw"), superseded_by=None, **schema.model_dump())
    await repository.add(session, row)
    if previous is not None:
        previous.superseded_by = row.id
        await session.flush()
    await projects_service.touch(session, schema.project_id)
    await session.commit()
    return KnowledgeStateRead.model_validate(row)


@checkpoint
async def get_current_knowledge(
    session: AsyncSession,
    project_id: str,
    claim_id: str,
    knower_type: str,
    knower_id: str | None,
) -> KnowledgeStateRead:
    row = await repository.get_current_knowledge(
        session, project_id, claim_id, knower_type, knower_id
    )
    if row is None:
        raise _not_found("knowledge state", f"{knower_type}:{knower_id}:{claim_id}")
    return KnowledgeStateRead.model_validate(row)


@checkpoint
async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    await repository.delete_by_project(session, project_id)
