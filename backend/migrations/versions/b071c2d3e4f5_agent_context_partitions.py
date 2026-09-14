"""B: additive perspective partitions; preserve legacy author content.

Revision ID: b071c2d3e4f5
Revises: f63c8db205a9
"""
from alembic import op
import sqlalchemy as sa

revision = "b071c2d3e4f5"
down_revision = "f63c8db205a9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("context_key", sa.String(), server_default="author", nullable=False))
    op.create_table(
        "agent_conversation_partitions",
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("context_key", sa.String(), primary_key=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("summary_until_id", sa.String(), nullable=True),
    )


def downgrade():
    # No automatic destructive downgrade: partition histories cannot be safely merged.
    raise RuntimeError("Data-preserving downgrade requires an explicit export/recovery plan")
