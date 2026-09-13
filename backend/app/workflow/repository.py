"""Workflow Core persistence operations; transaction ownership stays in service."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.workflow.models import (
    Episode,
    ExecutionRun,
    ExecutionStep,
    RequirementSpec,
    ScenePlan,
    WorkflowGate,
    WorkflowSeries,
)


async def add(session: AsyncSession, row: object) -> object:
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, model: type, row_id: str):  # type: ignore[no-untyped-def]
    return await session.get(model, row_id)


async def next_requirement_version(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(RequirementSpec.version)).where(RequirementSpec.project_id == project_id)
    )
    return int(value or 0) + 1


async def current_requirement(session: AsyncSession, project_id: str) -> RequirementSpec | None:
    return await session.scalar(
        select(RequirementSpec)
        .where(RequirementSpec.project_id == project_id)
        .order_by(RequirementSpec.version.desc())
        .limit(1)
    )


async def steps_for_run(session: AsyncSession, run_id: str) -> list[ExecutionStep]:
    return list(
        await session.scalars(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == run_id)
            .order_by(ExecutionStep.position)
        )
    )


async def delete_project(session: AsyncSession, project_id: str) -> None:
    for model in (ExecutionRun, WorkflowGate, ScenePlan, Episode, WorkflowSeries, RequirementSpec):
        await session.execute(delete(model).where(model.project_id == project_id))
