"""Project-scoped impact, dependencies, proposals, and review audit HTTP boundary."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.lineage import service
from app.lineage.schemas import (
    AuditRead,
    EdgeCreate,
    EdgeRead,
    EdgeReview,
    ImpactRead,
    ImpactRequest,
    ProposalCreate,
    ProposalDecision,
    ProposalRead,
)

router = APIRouter(prefix="/api/projects/{project_id}/lineage", tags=["lineage"])


@router.post("/edges", response_model=EdgeRead, status_code=201)
async def create_edge(
    project_id: str, payload: EdgeCreate, session: AsyncSession = Depends(get_session)
) -> EdgeRead:
    return await service.create_edge(session, project_id, payload)


@router.get("/edges", response_model=list[EdgeRead])
async def list_edges(
    project_id: str, session: AsyncSession = Depends(get_session)
) -> list[EdgeRead]:
    return await service.list_edges(session, project_id)


@router.post("/impact", response_model=ImpactRead)
async def impact(
    project_id: str, payload: ImpactRequest, session: AsyncSession = Depends(get_session)
) -> ImpactRead:
    return await service.impact(session, project_id, payload)


@router.post("/edges/{edge_id}/review", response_model=EdgeRead)
async def review(
    project_id: str, edge_id: str, payload: EdgeReview, session: AsyncSession = Depends(get_session)
) -> EdgeRead:
    return await service.review_edge(session, project_id, edge_id, payload)


@router.get("/reviews", response_model=list[AuditRead])
async def reviews(
    project_id: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, object]]:
    return await service.list_audits(session, project_id)


@router.post("/proposals", response_model=ProposalRead, status_code=201)
async def create_proposal(
    project_id: str, payload: ProposalCreate, session: AsyncSession = Depends(get_session)
) -> ProposalRead:
    return await service.create_proposal(session, project_id, payload)


@router.get("/proposals", response_model=list[ProposalRead])
async def list_proposals(
    project_id: str, session: AsyncSession = Depends(get_session)
) -> list[ProposalRead]:
    return await service.list_proposals(session, project_id)


@router.post("/proposals/{proposal_id}/decision", response_model=ProposalRead)
async def decide(
    project_id: str,
    proposal_id: str,
    payload: ProposalDecision,
    session: AsyncSession = Depends(get_session),
) -> ProposalRead:
    return await service.decide_proposal(session, project_id, proposal_id, payload)
