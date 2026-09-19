"""Lineage facts and append-only review records."""

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def now() -> datetime:
    return datetime.now(UTC)


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        CheckConstraint("state IN ('active','stale','superseded','rebased')"),
        CheckConstraint(
            "invalidation_policy IN ('hard_stale','review_required',"
            "'timing_revalidate','compatibility_check','notice_only','none')"
        ),
        Index("ix_lineage_upstream", "project_id", "upstream_type", "upstream_id"),
        Index("ix_lineage_downstream", "project_id", "downstream_type", "downstream_id"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    upstream_type: Mapped[str] = mapped_column(String, nullable=False)
    upstream_id: Mapped[str] = mapped_column(String, nullable=False)
    upstream_revision_ref: Mapped[str] = mapped_column(String, nullable=False)
    downstream_type: Mapped[str] = mapped_column(String, nullable=False)
    downstream_id: Mapped[str] = mapped_column(String, nullable=False)
    downstream_revision_ref: Mapped[str] = mapped_column(String, nullable=False)
    dependency_type: Mapped[str] = mapped_column(String, nullable=False)
    invalidation_policy: Mapped[str] = mapped_column(String, nullable=False)
    compatibility_validator: Mapped[str | None] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, nullable=False, default="active")
    stale_cause_ref: Mapped[str | None] = mapped_column(String)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("lineage_edges.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now, onupdate=now)


class ChangeProposal(Base):
    __tablename__ = "change_proposals"
    __table_args__ = (CheckConstraint("status IN ('proposed','accepted','rejected','superseded')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    origin_type: Mapped[str] = mapped_column(String)
    origin_id: Mapped[str] = mapped_column(String)
    origin_revision_ref: Mapped[str] = mapped_column(String)
    target_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[str] = mapped_column(String)
    target_base_revision_ref: Mapped[str] = mapped_column(String)
    proposal_kind: Mapped[str] = mapped_column(String)
    patch_json: Mapped[dict[str, object]] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="proposed")
    committed_ref: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ReviewAudit(Base):
    __tablename__ = "lineage_review_audits"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    subject_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(Text)
    details_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
