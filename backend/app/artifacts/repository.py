"""Data access for Artifact Core; transaction ownership stays in service."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.models import (
    Artifact,
    ArtifactBlock,
    ArtifactBlockRevision,
    ArtifactDependency,
    ArtifactRevision,
)


async def add(session: AsyncSession, row: object) -> None:
    session.add(row)
    await session.flush()


async def flush(session: AsyncSession) -> None:
    await session.flush()


async def get_artifact(session: AsyncSession, artifact_id: str) -> Artifact | None:
    return await session.get(Artifact, artifact_id)


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


async def get_dependency(session: AsyncSession, dependency_id: str) -> ArtifactDependency | None:
    return await session.get(ArtifactDependency, dependency_id)


async def list_dependencies_for_blocks(
    session: AsyncSession, block_ids: list[str]
) -> list[ArtifactDependency]:
    if not block_ids:
        return []
    stmt = select(ArtifactDependency).where(
        ArtifactDependency.source_block_id.in_(block_ids),
        ArtifactDependency.is_stale.is_(False),
    )
    return list(await session.scalars(stmt))


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(sa_delete(Artifact).where(Artifact.project_id == project_id))
