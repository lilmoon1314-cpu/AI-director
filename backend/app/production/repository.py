"""Production binding persistence; service owns transactions."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.production.models import ProductionDocument


async def add(session: AsyncSession, row: ProductionDocument) -> None:
    session.add(row)
    await session.flush()


async def get(session: AsyncSession, row_id: str) -> ProductionDocument | None:
    return await session.get(ProductionDocument, row_id)


async def get_by_artifact(session: AsyncSession, artifact_id: str) -> ProductionDocument | None:
    return await session.scalar(
        select(ProductionDocument).where(ProductionDocument.artifact_id == artifact_id)
    )


async def delete_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(
        delete(ProductionDocument).where(ProductionDocument.project_id == project_id)
    )
