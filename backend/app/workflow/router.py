"""Workflow Core HTTP composition."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.workflow import service
from app.workflow.schemas import (
    EpisodeCreate,
    EpisodeRead,
    GateCreate,
    GateEvaluate,
    GateEvaluationRead,
    MockExecute,
    RequirementCreate,
    RequirementRead,
    RunCreate,
    RunRead,
    ScenePlanCreate,
    ScenePlanRead,
    SeriesCreate,
    SeriesRead,
)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/requirements", response_model=RequirementRead, status_code=status.HTTP_201_CREATED)
async def create_requirement(
    payload: RequirementCreate, session: AsyncSession = Depends(get_session)
) -> RequirementRead:
    return await service.create_requirement(session, payload)


@router.get("/requirements/current", response_model=RequirementRead)
async def current_requirement(
    project_id: str = Query(), session: AsyncSession = Depends(get_session)
) -> RequirementRead:
    return await service.get_current_requirement(session, project_id)


@router.post("/series", response_model=SeriesRead, status_code=status.HTTP_201_CREATED)
async def create_series(
    payload: SeriesCreate, session: AsyncSession = Depends(get_session)
) -> SeriesRead:
    return await service.create_series(session, payload)


@router.post("/episodes", response_model=EpisodeRead, status_code=status.HTTP_201_CREATED)
async def create_episode(
    payload: EpisodeCreate, session: AsyncSession = Depends(get_session)
) -> EpisodeRead:
    return await service.create_episode(session, payload)


@router.post("/scene-plans", response_model=ScenePlanRead, status_code=status.HTTP_201_CREATED)
async def create_scene_plan(
    payload: ScenePlanCreate, session: AsyncSession = Depends(get_session)
) -> ScenePlanRead:
    return await service.create_scene_plan(session, payload)


@router.post("/gates", status_code=status.HTTP_201_CREATED)
async def create_gate(
    payload: GateCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    return {"id": await service.create_gate(session, payload)}


@router.post("/gates/{gate_id}/evaluate", response_model=GateEvaluationRead)
async def evaluate_gate(
    gate_id: str, payload: GateEvaluate, session: AsyncSession = Depends(get_session)
) -> GateEvaluationRead:
    return await service.evaluate_gate(session, gate_id, payload)


@router.post("/runs", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreate, session: AsyncSession = Depends(get_session)) -> RunRead:
    return await service.create_run(session, payload)


@router.post("/runs/{run_id}/mock-execute", response_model=RunRead)
async def mock_execute(
    run_id: str, payload: MockExecute, session: AsyncSession = Depends(get_session)
) -> RunRead:
    return await service.mock_execute(session, run_id, payload)
