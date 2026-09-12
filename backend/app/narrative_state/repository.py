"""Data access for Narrative State Core; services own transactions."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.narrative_state.models import (
    Claim,
    KnowledgeState,
    NarrativeTimepoint,
    StateCurrent,
    StateEvent,
    StateSnapshot,
)


async def add(session: AsyncSession, row: object) -> None:
    session.add(row)
    await session.flush()


async def get_timepoint(session: AsyncSession, row_id: str) -> NarrativeTimepoint | None:
    return await session.get(NarrativeTimepoint, row_id)


async def get_timepoint_by_sequence(
    session: AsyncSession, project_id: str, sequence_no: int
) -> NarrativeTimepoint | None:
    stmt = select(NarrativeTimepoint).where(
        NarrativeTimepoint.project_id == project_id,
        NarrativeTimepoint.sequence_no == sequence_no,
    )
    return await session.scalar(stmt)


async def get_event(session: AsyncSession, row_id: str) -> StateEvent | None:
    return await session.get(StateEvent, row_id)


async def get_latest_event(session: AsyncSession, project_id: str) -> StateEvent | None:
    stmt = (
        select(StateEvent)
        .where(StateEvent.project_id == project_id)
        .order_by(StateEvent.created_at.desc(), StateEvent.id.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_current(
    session: AsyncSession,
    project_id: str,
    subject_type: str,
    subject_id: str,
    attribute_key: str,
) -> StateCurrent | None:
    stmt = select(StateCurrent).where(
        StateCurrent.project_id == project_id,
        StateCurrent.subject_type == subject_type,
        StateCurrent.subject_id == subject_id,
        StateCurrent.attribute_key == attribute_key,
    )
    return await session.scalar(stmt)


async def list_current(session: AsyncSession, project_id: str) -> list[StateCurrent]:
    stmt = (
        select(StateCurrent)
        .where(StateCurrent.project_id == project_id)
        .order_by(StateCurrent.subject_type, StateCurrent.subject_id, StateCurrent.attribute_key)
    )
    return list(await session.scalars(stmt))


async def get_snapshot(session: AsyncSession, row_id: str) -> StateSnapshot | None:
    return await session.get(StateSnapshot, row_id)


async def get_claim(session: AsyncSession, row_id: str) -> Claim | None:
    return await session.get(Claim, row_id)


async def get_current_knowledge(
    session: AsyncSession,
    project_id: str,
    claim_id: str,
    knower_type: str,
    knower_id: str | None,
) -> KnowledgeState | None:
    stmt = select(KnowledgeState).where(
        KnowledgeState.project_id == project_id,
        KnowledgeState.claim_id == claim_id,
        KnowledgeState.knower_type == knower_type,
        KnowledgeState.superseded_by.is_(None),
    )
    if knower_id is None:
        stmt = stmt.where(KnowledgeState.knower_id.is_(None))
    else:
        stmt = stmt.where(KnowledgeState.knower_id == knower_id)
    return await session.scalar(stmt)


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    # ORM-independent bulk deletion order keeps self references and restrictive FKs explicit.
    for model in (
        KnowledgeState,
        StateSnapshot,
        StateCurrent,
        StateEvent,
        Claim,
        NarrativeTimepoint,
    ):
        await session.execute(sa_delete(model).where(model.project_id == project_id))
