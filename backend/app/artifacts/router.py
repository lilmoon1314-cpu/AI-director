"""HTTP composition for Artifact Core public operations."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import service
from app.artifacts.schemas import (
    ArtifactCreate,
    ArtifactRead,
    ArtifactRevisionRead,
    BlockEdit,
    DependencyCreate,
    DependencyRead,
    RevisionDiffRead,
)
from app.core.db import get_session

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.post("", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    payload: ArtifactCreate, session: AsyncSession = Depends(get_session)
) -> ArtifactRead:
    return await service.create(session, payload)


@router.post("/dependencies", response_model=DependencyRead, status_code=status.HTTP_201_CREATED)
async def create_dependency(
    payload: DependencyCreate, session: AsyncSession = Depends(get_session)
) -> DependencyRead:
    return await service.create_dependency(session, payload)


@router.get("/dependencies/{dependency_id}", response_model=DependencyRead)
async def get_dependency(
    dependency_id: str, session: AsyncSession = Depends(get_session)
) -> DependencyRead:
    return await service.get_dependency(session, dependency_id)


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    artifact_id: str, session: AsyncSession = Depends(get_session)
) -> ArtifactRead:
    return await service.get(session, artifact_id)


@router.get("/{artifact_id}/revisions/{revision_id}", response_model=ArtifactRevisionRead)
async def get_revision(
    artifact_id: str,
    revision_id: str,
    session: AsyncSession = Depends(get_session),
) -> ArtifactRevisionRead:
    return await service.get_revision(session, artifact_id, revision_id)


@router.get("/{artifact_id}/diff", response_model=RevisionDiffRead)
async def get_diff(
    artifact_id: str,
    from_revision_id: str = Query(),
    to_revision_id: str = Query(),
    session: AsyncSession = Depends(get_session),
) -> RevisionDiffRead:
    return await service.diff(session, artifact_id, from_revision_id, to_revision_id)


@router.patch("/{artifact_id}/blocks/{block_id}", response_model=ArtifactRead)
async def edit_block(
    artifact_id: str,
    block_id: str,
    payload: BlockEdit,
    session: AsyncSession = Depends(get_session),
) -> ArtifactRead:
    return await service.edit_block(session, artifact_id, block_id, payload)
