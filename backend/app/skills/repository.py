"""Atomic Skill candidate persistence."""

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.skills.models import SkillCandidate


async def add(session: AsyncSession, row: SkillCandidate) -> None:
    session.add(row)
    await session.flush()


async def get(session: AsyncSession, candidate_id: str) -> SkillCandidate | None:
    return await session.get(SkillCandidate, candidate_id)


async def claim(session: AsyncSession, candidate_id: str) -> bool:
    """原子取得候选决定权；deciding 只存在于未提交事务。"""
    result = await session.execute(
        update(SkillCandidate)
        .where(SkillCandidate.id == candidate_id, SkillCandidate.status == "pending")
        .values(status="deciding")
        .execution_options(synchronize_session=False)
    )
    return bool(getattr(result, "rowcount", 0) == 1)


async def save(session: AsyncSession, row: SkillCandidate) -> None:
    """刷新候选决定字段但不提交，供调用方原子收口。"""
    await session.flush()


async def delete_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(delete(SkillCandidate).where(SkillCandidate.project_id == project_id))
