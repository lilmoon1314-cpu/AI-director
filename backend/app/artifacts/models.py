"""Artifact Core ORM models owned by the artifacts repository."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Artifact(Base):
    """Stable identity and current state of one structured creative artifact."""

    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("approval_status IN ('draft','review','approved','archived')"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    approval_status: Mapped[str] = mapped_column(
        String, nullable=False, default="draft", server_default="draft"
    )
    current_revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class ArtifactBlock(Base):
    """Stable block identity; mutable content lives only in revision snapshots."""

    __tablename__ = "artifact_blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    block_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class ArtifactRevision(Base):
    """Immutable aggregate revision of an artifact."""

    __tablename__ = "artifact_revisions"
    __table_args__ = (UniqueConstraint("artifact_id", "revision_no"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class ArtifactBlockRevision(Base):
    """Immutable content/order snapshot for one stable block in one artifact revision."""

    __tablename__ = "artifact_block_revisions"
    __table_args__ = (UniqueConstraint("revision_id", "block_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    block_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_json: Mapped[dict[str, object] | None] = mapped_column(JSON)


class ArtifactDependency(Base):
    """Frozen legacy dependency table; runtime reads/writes use Lineage after V4-R2."""

    __tablename__ = "artifact_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_block_id", "source_revision_id", "dependent_artifact_id", name="uq_artifact_dep"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    source_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_block_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependent_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependency_type: Mapped[str] = mapped_column(String, nullable=False, default="derived_from")
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )
