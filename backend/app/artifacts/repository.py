"""Data access for Artifact Core; transaction ownership stays in service."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.models import (
    Artifact,
    ArtifactBlock,
    ArtifactBlockRevision,
    ArtifactRevision,
)


async def add(session: AsyncSession, row: object) -> None:
    session.add(row)
    await session.flush()


async def flush(session: AsyncSession) -> None:
    await session.flush()


async def advance_revision_if_current(
    session: AsyncSession,
    artifact_id: str,
    expected_no: int,
    next_no: int,
    updated_at: object,
) -> bool:
    """原子推进 current revision，防止两个编辑都从同一版本成功。"""
    result = await session.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id, Artifact.current_revision_no == expected_no)
        .values(current_revision_no=next_no, updated_at=updated_at)
        .execution_options(synchronize_session=False)
    )
    return bool(getattr(result, "rowcount", 0) == 1)


async def get_artifact(session: AsyncSession, artifact_id: str) -> Artifact | None:
    return await session.scalar(
        select(Artifact).where(Artifact.id == artifact_id).execution_options(populate_existing=True)
    )


async def lock_artifact(session: AsyncSession, artifact_id: str) -> None:
    """Serialize lifecycle confirmation with content revisions in SQLite."""
    await session.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id)
        .values(updated_at=Artifact.updated_at)
        .execution_options(synchronize_session=False)
    )


async def get_block(session: AsyncSession, block_id: str) -> ArtifactBlock | None:
    return await session.get(ArtifactBlock, block_id)


async def get_revision(session: AsyncSession, revision_id: str) -> ArtifactRevision | None:
    return await session.get(ArtifactRevision, revision_id)


async def get_revision_by_no(
    session: AsyncSession, artifact_id: str, revision_no: int
) -> ArtifactRevision | None:
    stmt = select(ArtifactRevision).where(
        ArtifactRevision.artifact_id == artifact_id,
        ArtifactRevision.revision_no == revision_no,
    )
    return await session.scalar(stmt)


async def list_revision_blocks(
    session: AsyncSession, revision_id: str
) -> list[tuple[ArtifactBlockRevision, ArtifactBlock]]:
    stmt = (
        select(ArtifactBlockRevision, ArtifactBlock)
        .join(ArtifactBlock, ArtifactBlock.id == ArtifactBlockRevision.block_id)
        .where(ArtifactBlockRevision.revision_id == revision_id)
        .order_by(ArtifactBlockRevision.position, ArtifactBlockRevision.block_id)
    )
    return list((await session.execute(stmt)).tuples())


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(sa_delete(Artifact).where(Artifact.project_id == project_id))
