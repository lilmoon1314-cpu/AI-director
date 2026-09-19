"""Lineage persistence; services own transactions."""

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.lineage.models import ChangeProposal, LineageEdge, ReviewAudit, now


async def add(session: AsyncSession, row: object) -> None:
    session.add(row)
    await session.flush()


async def lock_project(session: AsyncSession, project_id: str) -> None:
    """Acquire SQLite's write transaction before reading review/edge decision bases.

    Even an empty-match UPDATE starts a write transaction. No facts or timestamps change.
    This also prevents concurrent endpoint duplication and cycles without partial unique indexes
    that could reject preserved legacy dependency rows during migration.
    """
    await session.execute(
        update(LineageEdge)
        .where(LineageEdge.project_id == project_id)
        .values(updated_at=LineageEdge.updated_at)
        .execution_options(synchronize_session=False)
    )


async def edges(session: AsyncSession, project_id: str) -> list[LineageEdge]:
    return list(
        await session.scalars(
            select(LineageEdge)
            .where(LineageEdge.project_id == project_id)
            .order_by(LineageEdge.created_at, LineageEdge.id)
        )
    )


async def edge(session: AsyncSession, edge_id: str) -> LineageEdge | None:
    return await session.get(LineageEdge, edge_id)


async def proposal(session: AsyncSession, proposal_id: str) -> ChangeProposal | None:
    return await session.get(ChangeProposal, proposal_id)


async def proposals(session: AsyncSession, project_id: str) -> list[ChangeProposal]:
    return list(
        await session.scalars(
            select(ChangeProposal)
            .where(ChangeProposal.project_id == project_id)
            .order_by(ChangeProposal.created_at)
        )
    )


async def claim_proposal(session: AsyncSession, proposal_id: str, status: str) -> bool:
    result = await session.execute(
        update(ChangeProposal)
        .where(ChangeProposal.id == proposal_id, ChangeProposal.status == "proposed")
        .values(status=status, decided_at=now())
        .execution_options(synchronize_session=False)
    )
    return getattr(result, "rowcount", 0) == 1


async def audits(session: AsyncSession, project_id: str) -> list[ReviewAudit]:
    return list(
        await session.scalars(
            select(ReviewAudit)
            .where(ReviewAudit.project_id == project_id)
            .order_by(ReviewAudit.created_at, ReviewAudit.id)
        )
    )


async def delete_project(session: AsyncSession, project_id: str) -> None:
    for model in (ReviewAudit, ChangeProposal, LineageEdge):
        await session.execute(delete(model).where(model.project_id == project_id))
