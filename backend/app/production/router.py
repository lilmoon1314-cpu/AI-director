"""Production document HTTP boundary."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.production import service
from app.production.schemas import ProductionDocumentCreate, ProductionDocumentRead

router = APIRouter(prefix="/api/production", tags=["production"])


@router.post(
    "/documents", response_model=ProductionDocumentRead, status_code=status.HTTP_201_CREATED
)
async def create_document(
    payload: ProductionDocumentCreate, session: AsyncSession = Depends(get_session)
) -> ProductionDocumentRead:
    return await service.create(session, payload)


@router.get("/documents/{document_id}", response_model=ProductionDocumentRead)
async def get_document(
    document_id: str, session: AsyncSession = Depends(get_session)
) -> ProductionDocumentRead:
    return await service.get(session, document_id)
