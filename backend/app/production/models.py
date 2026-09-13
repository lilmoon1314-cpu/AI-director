"""Production document binding model."""

from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ProductionDocument(Base):
    __tablename__ = "production_documents"
    __table_args__ = (UniqueConstraint("artifact_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(String, index=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_documents.id", ondelete="CASCADE"), index=True
    )
    source_artifact_id: Mapped[str | None] = mapped_column(String)
    source_block_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
