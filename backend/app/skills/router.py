"""Atomic Skill HTTP boundary."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.skills import service
from app.skills.schemas import CandidateDecision, CandidateRead, SkillExecute, SkillRead

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillRead])
async def list_skills() -> list[SkillRead]:
    return service.list_skills()


@router.post(
    "/{skill_id}/execute", response_model=CandidateRead, status_code=status.HTTP_201_CREATED
)
async def execute_skill(
    skill_id: str, payload: SkillExecute, session: AsyncSession = Depends(get_session)
) -> CandidateRead:
    return await service.execute(session, skill_id, payload)


@router.post("/candidates/{candidate_id}/accept", response_model=CandidateRead)
async def accept_candidate(
    candidate_id: str, payload: CandidateDecision, session: AsyncSession = Depends(get_session)
) -> CandidateRead:
    return await service.decide(session, candidate_id, payload.project_id, accept=True)


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateRead)
async def reject_candidate(
    candidate_id: str, payload: CandidateDecision, session: AsyncSession = Depends(get_session)
) -> CandidateRead:
    return await service.decide(session, candidate_id, payload.project_id, accept=False)
