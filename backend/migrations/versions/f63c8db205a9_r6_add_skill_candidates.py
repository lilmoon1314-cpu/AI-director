"""R6 add persistent Atomic Skill candidates.

Revision ID: f63c8db205a9
Revises: e52b7a91f4c8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f63c8db205a9"
down_revision: str | None = "e52b7a91f4c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_candidates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String(), nullable=False),
        sa.Column("candidate_json", sa.JSON(), nullable=False),
        sa.Column("impact_json", sa.JSON(), nullable=False),
        sa.Column("commit_action", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("committed_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["execution_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    for column in ("project_id", "run_id", "skill_id", "scope_id"):
        op.create_index(
            f"ix_skill_candidates_{column}",
            "skill_candidates",
            [column],
            unique=column == "run_id",
        )


def downgrade() -> None:
    for column in ("scope_id", "skill_id", "run_id", "project_id"):
        op.drop_index(f"ix_skill_candidates_{column}", table_name="skill_candidates")
    op.drop_table("skill_candidates")
