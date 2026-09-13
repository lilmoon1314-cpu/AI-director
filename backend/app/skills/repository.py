"""Atomic Skill candidate persistence."""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.skills.models import SkillCandidate


async def add(session: AsyncSession, row: SkillCandidate) -> None:
    session.add(row)
    await session.flush()


async def get(session: AsyncSession, candidate_id: str) -> SkillCandidate | None:
    return await session.get(SkillCandidate, candidate_id)


async def delete_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(delete(SkillCandidate).where(SkillCandidate.project_id == project_id))
