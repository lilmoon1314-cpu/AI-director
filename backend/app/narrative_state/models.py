"""ORM models for temporal narrative state and perspective knowledge."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
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


class NarrativeTimepoint(Base):
    __tablename__ = "narrative_timepoints"
    __table_args__ = (UniqueConstraint("project_id", "sequence_no"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    series_id: Mapped[str | None] = mapped_column(String)
    episode_id: Mapped[str | None] = mapped_column(String)
    scene_id: Mapped[str | None] = mapped_column(String)
    beat_id: Mapped[str | None] = mapped_column(String)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    world_time: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class StateEvent(Base):
    __tablename__ = "state_events"
    __table_args__ = (CheckConstraint("operation IN ('set', 'add', 'remove', 'transition')"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attribute_key: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    before_json: Mapped[object | None] = mapped_column(JSON)
    after_json: Mapped[object | None] = mapped_column(JSON)
    timepoint_id: Mapped[str] = mapped_column(
        ForeignKey("narrative_timepoints.id"), nullable=False, index=True
    )
    cause_type: Mapped[str] = mapped_column(String, nullable=False)
    cause_ref: Mapped[str] = mapped_column(String, nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"), index=True)
    source_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_revisions.id"), index=True
    )
    compensates_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("state_events.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class StateCurrent(Base):
    __tablename__ = "state_current"
    __table_args__ = (
        UniqueConstraint("project_id", "subject_type", "subject_id", "attribute_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attribute_key: Mapped[str] = mapped_column(String, nullable=False)
    value_json: Mapped[object | None] = mapped_column(JSON)
    last_event_id: Mapped[str] = mapped_column(ForeignKey("state_events.id"), nullable=False)
    timepoint_id: Mapped[str] = mapped_column(ForeignKey("narrative_timepoints.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class StateSnapshot(Base):
    __tablename__ = "state_snapshots"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('scene_entry', 'scene_exit', 'episode_entry', 'episode_exit')"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[str] = mapped_column(String, nullable=False)
    timepoint_id: Mapped[str] = mapped_column(ForeignKey("narrative_timepoints.id"), nullable=False)
    snapshot_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    source_event_cursor: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (CheckConstraint("truth_status IN ('true', 'false', 'uncertain')"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    subject_ref: Mapped[str] = mapped_column(String, nullable=False)
    predicate: Mapped[str] = mapped_column(String, nullable=False)
    object_json: Mapped[object | None] = mapped_column(JSON)
    truth_status: Mapped[str] = mapped_column(String, nullable=False)
    author_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class KnowledgeState(Base):
    __tablename__ = "knowledge_states"
    __table_args__ = (
        CheckConstraint("knower_type IN ('character', 'audience')"),
        CheckConstraint("status IN ('unknown', 'suspects', 'believes', 'knows', 'misled')"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    knower_type: Mapped[str] = mapped_column(String, nullable=False)
    knower_id: Mapped[str | None] = mapped_column(String, index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    acquired_timepoint_id: Mapped[str] = mapped_column(
        ForeignKey("narrative_timepoints.id"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    superseded_by: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_states.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
