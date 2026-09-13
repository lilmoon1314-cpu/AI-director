"""R4 add Workflow Core.

Revision ID: d8410ca2e6b7
Revises: 7c91e2ab4f30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8410ca2e6b7"
down_revision: str | None = "7c91e2ab4f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "requirement_specs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version"),
    )
    op.create_index("ix_requirement_specs_project_id", "requirement_specs", ["project_id"])
    op.create_table(
        "workflow_series",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_series_project_id", "workflow_series", ["project_id"])
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("outline", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["series_id"], ["workflow_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("series_id", "position"),
    )
    op.create_index("ix_episodes_project_id", "episodes", ["project_id"])
    op.create_index("ix_episodes_series_id", "episodes", ["series_id"])
    op.create_table(
        "scene_plans",
        sa.Column("id", sa.String(), nullable=False), sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("episode_id", sa.String(), nullable=False), sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("location_ref", sa.String(), nullable=True), sa.Column("time_context", sa.String(), nullable=False),
        sa.Column("characters_json", sa.JSON(), nullable=False), sa.Column("scene_goal", sa.Text(), nullable=False),
        sa.Column("character_goal", sa.Text(), nullable=False), sa.Column("conflict", sa.Text(), nullable=False),
        sa.Column("turn", sa.Text(), nullable=False), sa.Column("reveal", sa.Text(), nullable=False),
        sa.Column("exit_change", sa.Text(), nullable=False), sa.Column("target_duration", sa.Integer(), nullable=False),
        sa.Column("required_setup_json", sa.JSON(), nullable=False), sa.Column("required_payoff_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("episode_id", "position"),
    )
    op.create_index("ix_scene_plans_project_id", "scene_plans", ["project_id"])
    op.create_index("ix_scene_plans_episode_id", "scene_plans", ["episode_id"])
    op.create_table(
        "workflow_gates",
        sa.Column("id", sa.String(), nullable=False), sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False), sa.Column("scope_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False), sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_gates_project_id", "workflow_gates", ["project_id"])
    op.create_index("ix_workflow_gates_scope_id", "workflow_gates", ["scope_id"])
    op.create_table(
        "execution_runs",
        sa.Column("id", sa.String(), nullable=False), sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False), sa.Column("scope_id", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False), sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_runs_project_id", "execution_runs", ["project_id"])
    op.create_index("ix_execution_runs_scope_id", "execution_runs", ["scope_id"])
    op.create_table(
        "execution_steps",
        sa.Column("id", sa.String(), nullable=False), sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("kind", sa.String(), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["execution_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("run_id", "position"),
    )
    op.create_index("ix_execution_steps_run_id", "execution_steps", ["run_id"])


def downgrade() -> None:
    for table, indexes in (
        ("execution_steps", ["ix_execution_steps_run_id"]),
        ("execution_runs", ["ix_execution_runs_scope_id", "ix_execution_runs_project_id"]),
        ("workflow_gates", ["ix_workflow_gates_scope_id", "ix_workflow_gates_project_id"]),
        ("scene_plans", ["ix_scene_plans_episode_id", "ix_scene_plans_project_id"]),
        ("episodes", ["ix_episodes_series_id", "ix_episodes_project_id"]),
        ("workflow_series", ["ix_workflow_series_project_id"]),
        ("requirement_specs", ["ix_requirement_specs_project_id"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
