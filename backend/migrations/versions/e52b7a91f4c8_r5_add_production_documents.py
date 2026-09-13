"""R5 add semantic artifact blocks and production documents.

Revision ID: e52b7a91f4c8
Revises: d8410ca2e6b7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e52b7a91f4c8"
down_revision: str | None = "d8410ca2e6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("artifact_block_revisions", sa.Column("semantic_json", sa.JSON(), nullable=True))
    op.create_table(
        "production_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("episode_id", sa.String(), nullable=False),
        sa.Column("scene_id", sa.String(), nullable=True),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("source_document_id", sa.String(), nullable=True),
        sa.Column("source_artifact_id", sa.String(), nullable=True),
        sa.Column("source_block_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["production_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    for column in (
        "project_id",
        "episode_id",
        "scene_id",
        "artifact_id",
        "document_type",
        "source_document_id",
    ):
        op.create_index(f"ix_production_documents_{column}", "production_documents", [column])


def downgrade() -> None:
    for column in (
        "source_document_id",
        "document_type",
        "artifact_id",
        "scene_id",
        "episode_id",
        "project_id",
    ):
        op.drop_index(f"ix_production_documents_{column}", table_name="production_documents")
    op.drop_table("production_documents")
    op.drop_column("artifact_block_revisions", "semantic_json")
