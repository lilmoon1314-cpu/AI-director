"""Persistent Atomic Skill candidate decisions."""

from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SkillCandidate(Base):
    __tablename__ = "skill_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    skill_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    candidate_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    impact_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    commit_action: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    committed_ref: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
