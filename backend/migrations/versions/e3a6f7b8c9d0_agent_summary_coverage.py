"""E: versioned Agent summaries with traceable coverage.

Revision ID: e3a6f7b8c9d0
Revises: d295e6f7a8b9
"""

import sqlalchemy as sa
from alembic import op

revision = "e3a6f7b8c9d0"
down_revision = "d295e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("summary_version_id", sa.String(), nullable=True))
    op.add_column(
        "agent_conversation_partitions",
        sa.Column("summary_version_id", sa.String(), nullable=True),
    )
    op.create_table(
        "agent_summary_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("context_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("previous_cursor", sa.String(), nullable=True),
        sa.Column("next_cursor", sa.String(), nullable=True),
        sa.Column("source_ids_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("key_items_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("strategy_version", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("input_chars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_chars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "context_key", "version"),
    )
    op.create_index(
        "ix_agent_summary_versions_conversation_id",
        "agent_summary_versions",
        ["conversation_id"],
    )


def downgrade():
    raise RuntimeError("Data-preserving downgrade requires an explicit export/recovery plan")
