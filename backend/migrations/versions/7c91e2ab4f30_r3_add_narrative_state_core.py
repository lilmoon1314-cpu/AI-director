"""r3 add narrative state core

Revision ID: 7c91e2ab4f30
Revises: 4da706c0d824
Create Date: 2026-09-12 13:30:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision: str = "7c91e2ab4f30"
down_revision: str | None = "4da706c0d824"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "narrative_timepoints",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=True),
        sa.Column("episode_id", sa.String(), nullable=True),
        sa.Column("scene_id", sa.String(), nullable=True),
        sa.Column("beat_id", sa.String(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("world_time", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sequence_no"),
    )
    op.create_index("ix_narrative_timepoints_project_id", "narrative_timepoints", ["project_id"])
    op.create_table(
        "state_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("attribute_key", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("timepoint_id", sa.String(), nullable=False),
        sa.Column("cause_type", sa.String(), nullable=False),
        sa.Column("cause_ref", sa.String(), nullable=False),
        sa.Column("source_artifact_id", sa.String(), nullable=True),
        sa.Column("source_revision_id", sa.String(), nullable=True),
        sa.Column("compensates_event_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("operation IN ('set', 'add', 'remove', 'transition')"),
        sa.ForeignKeyConstraint(["compensates_event_id"], ["state_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["source_revision_id"], ["artifact_revisions.id"]),
        sa.ForeignKeyConstraint(["timepoint_id"], ["narrative_timepoints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "project_id",
        "subject_id",
        "timepoint_id",
        "source_artifact_id",
        "source_revision_id",
    ):
        op.create_index(f"ix_state_events_{column}", "state_events", [column])
    op.create_table(
        "state_current",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("attribute_key", sa.String(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("last_event_id", sa.String(), nullable=False),
        sa.Column("timepoint_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["last_event_id"], ["state_events.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["timepoint_id"], ["narrative_timepoints.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "subject_type", "subject_id", "attribute_key"),
    )
    op.create_index("ix_state_current_project_id", "state_current", ["project_id"])
    op.create_index("ix_state_current_subject_id", "state_current", ["subject_id"])
    op.create_table(
        "state_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String(), nullable=False),
        sa.Column("timepoint_id", sa.String(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_event_cursor", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('scene_entry', 'scene_exit', 'episode_entry', 'episode_exit')"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["timepoint_id"], ["narrative_timepoints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_state_snapshots_project_id", "state_snapshots", ["project_id"])
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("subject_ref", sa.String(), nullable=False),
        sa.Column("predicate", sa.String(), nullable=False),
        sa.Column("object_json", sa.JSON(), nullable=True),
        sa.Column("truth_status", sa.String(), nullable=False),
        sa.Column("author_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("truth_status IN ('true', 'false', 'uncertain')"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_project_id", "claims", ["project_id"])
    op.create_table(
        "knowledge_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("knower_type", sa.String(), nullable=False),
        sa.Column("knower_id", sa.String(), nullable=True),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("acquired_timepoint_id", sa.String(), nullable=False),
        sa.Column("source_ref", sa.String(), nullable=False),
        sa.Column("superseded_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("knower_type IN ('character', 'audience')"),
        sa.CheckConstraint("status IN ('unknown', 'suspects', 'believes', 'knows', 'misled')"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
        sa.ForeignKeyConstraint(["acquired_timepoint_id"], ["narrative_timepoints.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["superseded_by"], ["knowledge_states.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("superseded_by"),
    )
    for column in ("project_id", "knower_id", "claim_id"):
        op.create_index(f"ix_knowledge_states_{column}", "knowledge_states", [column])

    _backfill_relationship_state()


def _backfill_relationship_state() -> None:
    """Copy only populated trust/resentment into an auditable R3 baseline."""
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, project_id, trust, resentment, created_at FROM relationships "
            "WHERE trust IS NOT NULL OR resentment IS NOT NULL ORDER BY project_id, id"
        )
    ).mappings()
    grouped: dict[str, list[sa.RowMapping]] = {}
    for row in rows:
        grouped.setdefault(str(row["project_id"]), []).append(row)
    now = datetime.now(UTC)
    for project_id, relationships in grouped.items():
        token = sha256(project_id.encode()).hexdigest()[:20]
        timepoint_id = f"tp-r3base-{token}"
        connection.execute(
            sa.text(
                "INSERT INTO narrative_timepoints "
                "(id, project_id, sequence_no, created_at) "
                "VALUES (:id, :project_id, 0, :created_at)"
            ),
            {"id": timepoint_id, "project_id": project_id, "created_at": now},
        )
        for relationship in relationships:
            for attribute in ("trust", "resentment"):
                value = relationship[attribute]
                if value is None:
                    continue
                relation_id = str(relationship["id"])
                suffix = sha256(f"{relation_id}:{attribute}".encode()).hexdigest()[:20]
                event_id = f"ste-r3base-{suffix}"
                connection.execute(
                    sa.text(
                        "INSERT INTO state_events "
                        "(id, project_id, subject_type, subject_id, attribute_key, operation, "
                        "before_json, after_json, timepoint_id, cause_type, cause_ref, created_at) "
                        "VALUES (:id, :project_id, 'relationship', :subject_id, :attribute_key, "
                        "'set', NULL, :value, :timepoint_id, 'migration', "
                        "'r3_relationship_state_baseline', :created_at)"
                    ),
                    {
                        "id": event_id,
                        "project_id": project_id,
                        "subject_id": relation_id,
                        "attribute_key": attribute,
                        "value": value,
                        "timepoint_id": timepoint_id,
                        "created_at": relationship["created_at"] or now,
                    },
                )
                connection.execute(
                    sa.text(
                        "INSERT INTO state_current "
                        "(id, project_id, subject_type, subject_id, attribute_key, value_json, "
                        "last_event_id, timepoint_id, version) "
                        "VALUES (:id, :project_id, 'relationship', :subject_id, :attribute_key, "
                        ":value, :event_id, :timepoint_id, 1)"
                    ),
                    {
                        "id": f"cur-r3base-{suffix}",
                        "project_id": project_id,
                        "subject_id": relation_id,
                        "attribute_key": attribute,
                        "value": value,
                        "event_id": event_id,
                        "timepoint_id": timepoint_id,
                    },
                )


def downgrade() -> None:
    for column in ("claim_id", "knower_id", "project_id"):
        op.drop_index(f"ix_knowledge_states_{column}", table_name="knowledge_states")
    op.drop_table("knowledge_states")
    op.drop_index("ix_claims_project_id", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_state_snapshots_project_id", table_name="state_snapshots")
    op.drop_table("state_snapshots")
    op.drop_index("ix_state_current_subject_id", table_name="state_current")
    op.drop_index("ix_state_current_project_id", table_name="state_current")
    op.drop_table("state_current")
    for column in (
        "source_revision_id",
        "source_artifact_id",
        "timepoint_id",
        "subject_id",
        "project_id",
    ):
        op.drop_index(f"ix_state_events_{column}", table_name="state_events")
    op.drop_table("state_events")
    op.drop_index("ix_narrative_timepoints_project_id", table_name="narrative_timepoints")
    op.drop_table("narrative_timepoints")
