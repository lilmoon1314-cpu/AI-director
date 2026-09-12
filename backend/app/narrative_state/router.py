"""REST boundary for Narrative State Core."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.narrative_state import service
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
)

router = APIRouter(prefix="/api/narrative-state", tags=["narrative-state"])


@router.post("/timepoints", response_model=TimepointRead, status_code=status.HTTP_201_CREATED)
async def create_timepoint(
    payload: TimepointCreate, session: AsyncSession = Depends(get_session)
) -> TimepointRead:
    return await service.create_timepoint(session, payload)


@router.post("/events", response_model=EventApplicationRead, status_code=status.HTTP_201_CREATED)
async def apply_event(
    payload: StateEventCreate, session: AsyncSession = Depends(get_session)
) -> EventApplicationRead:
    return await service.apply_event(session, payload)


@router.get("/events/{event_id}", response_model=StateEventRead)
async def get_event(event_id: str, session: AsyncSession = Depends(get_session)) -> StateEventRead:
    return await service.get_event(session, event_id)


@router.get("/current", response_model=StateCurrentRead)
async def get_current(
    project_id: str,
    subject_type: Literal["entity", "relationship"],
    subject_id: str,
    attribute_key: str,
    session: AsyncSession = Depends(get_session),
) -> StateCurrentRead:
    return await service.get_current(session, project_id, subject_type, subject_id, attribute_key)


@router.post("/snapshots", response_model=SnapshotRead, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    payload: SnapshotCreate, session: AsyncSession = Depends(get_session)
) -> SnapshotRead:
    return await service.create_snapshot(session, payload)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotRead)
async def get_snapshot(
    snapshot_id: str, session: AsyncSession = Depends(get_session)
) -> SnapshotRead:
    return await service.get_snapshot(session, snapshot_id)


@router.post("/claims", response_model=ClaimRead, status_code=status.HTTP_201_CREATED)
async def create_claim(
    payload: ClaimCreate, session: AsyncSession = Depends(get_session)
) -> ClaimRead:
    return await service.create_claim(session, payload)


@router.post(
    "/knowledge-states", response_model=KnowledgeStateRead, status_code=status.HTTP_201_CREATED
)
async def set_knowledge(
    payload: KnowledgeStateCreate, session: AsyncSession = Depends(get_session)
) -> KnowledgeStateRead:
    return await service.set_knowledge(session, payload)


@router.get("/knowledge-states/current", response_model=KnowledgeStateRead)
async def get_current_knowledge(
    project_id: str,
    claim_id: str,
    knower_type: Literal["character", "audience"],
    knower_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeStateRead:
    return await service.get_current_knowledge(
        session, project_id, claim_id, knower_type, knower_id
    )
