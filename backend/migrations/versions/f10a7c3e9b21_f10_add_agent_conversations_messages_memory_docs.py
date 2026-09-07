"""F10 add agent conversations, messages, memory docs tables

Revision ID: f10a7c3e9b21
Revises: b4e9a1c2d7f3
Create Date: 2026-09-06

F10 Agent 对话与确认写入（docs/data_struct_define.md §11.3 / DESIGN.md §8.3）:
- conversations：会话按项目隔离（FK projects.id），summary 承载滚动摘要；
- messages：会话内消息（FK CASCADE，会话删除随之清理）；
- memory_docs：项目工作上下文容器（HTML 分段模板，version 为文档级 ETag）；
- memory_doc_sections：段级存储单元（FK CASCADE，version 为段级 CAS 令牌）。
全部为新表，SQLite 下直接 create_table（无需 batch 重建）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f10a7c3e9b21'
down_revision: Union[str, None] = 'b4e9a1c2d7f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级到本版本：创建 agent 四表（会话/消息/记忆文档/文档段）。"""
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('summary_until_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    )
    op.create_index(op.f('ix_conversations_project_id'), 'conversations', ['project_id'],
                    unique=False)

    op.create_table(
        'messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'],
                    unique=False)

    op.create_table(
        'memory_docs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    )
    op.create_index(op.f('ix_memory_docs_project_id'), 'memory_docs', ['project_id'],
                    unique=False)

    op.create_table(
        'memory_doc_sections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('doc_id', sa.String(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['doc_id'], ['memory_docs.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_memory_doc_sections_doc_id'), 'memory_doc_sections', ['doc_id'],
                    unique=False)


def downgrade() -> None:
    """回退到上一版本：删除 agent 四表（会话与记忆数据丢失）。"""
    op.drop_index(op.f('ix_memory_doc_sections_doc_id'), table_name='memory_doc_sections')
    op.drop_table('memory_doc_sections')
    op.drop_index(op.f('ix_memory_docs_project_id'), table_name='memory_docs')
    op.drop_table('memory_docs')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_conversations_project_id'), table_name='conversations')
    op.drop_table('conversations')
