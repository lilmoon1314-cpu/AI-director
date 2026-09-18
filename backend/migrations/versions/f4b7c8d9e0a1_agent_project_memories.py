"""F: source-backed cross-conversation project memories and tombstones.

Revision ID: f4b7c8d9e0a1
Revises: e3a6f7b8c9d0
"""

import sqlalchemy as sa
from alembic import op

revision = "f4b7c8d9e0a1"
down_revision = "e3a6f7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_project_memories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("context_key", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("subject_key", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "context_key", "fingerprint"),
    )
    op.create_index(
        "ix_agent_project_memories_project_id", "agent_project_memories", ["project_id"]
    )
    op.create_index("ix_agent_project_memories_status", "agent_project_memories", ["status"])
    op.create_index(
        "ix_agent_project_memories_scope_status",
        "agent_project_memories",
        ["project_id", "context_key", "status"],
    )
    op.create_table(
        "agent_project_memory_sources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=True),
        sa.Column("context_key", sa.String(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["agent_project_memories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "source_kind", "source_id"),
    )
    op.create_index(
        "ix_agent_project_memory_sources_memory_id",
        "agent_project_memory_sources",
        ["memory_id"],
    )
    op.create_index(
        "ix_agent_project_memory_sources_source_id",
        "agent_project_memory_sources",
        ["source_id"],
    )
    op.create_index(
        "ix_agent_project_memory_sources_conversation_id",
        "agent_project_memory_sources",
        ["conversation_id"],
    )
    op.create_table(
        "agent_project_memory_tombstones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("context_key", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "context_key", "fingerprint"),
    )
    op.create_index(
        "ix_agent_project_memory_tombstones_project_id",
        "agent_project_memory_tombstones",
        ["project_id"],
    )


def downgrade():
    raise RuntimeError("Data-preserving downgrade requires an explicit export/recovery plan")

