"""C: additive confirmation idempotency and version baselines.

Revision ID: c184d5e6f7a8
Revises: b071c2d3e4f5
"""

import sqlalchemy as sa
from alembic import op

revision = "c184d5e6f7a8"
down_revision = "b071c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "entities",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("agent_pending_writes", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column("skill_candidates", sa.Column("base_revision_id", sa.String(), nullable=True))
    op.create_index(
        "uq_memory_docs_project_guide_kind",
        "memory_docs",
        ["project_id", "kind"],
        unique=True,
        sqlite_where=sa.text("kind IN ('positioning', 'style')"),
    )


def downgrade():
    raise RuntimeError("Data-preserving downgrade requires an explicit export/recovery plan")
