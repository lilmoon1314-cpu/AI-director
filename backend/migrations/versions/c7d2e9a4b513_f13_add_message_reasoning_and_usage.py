"""F13 add message reasoning and usage columns

Revision ID: c7d2e9a4b513
Revises: f10a7c3e9b21
Create Date: 2026-09-08

F13 Agent 对话体验升级（DESIGN.md §13.1）:
- messages.reasoning：思考过程文本（真流式 reasoning_content 聚合落库，前端回读可展开）；
- messages.prompt_tokens / completion_tokens：本轮 LLM usage（UsageBar 容量窗口数据源，
  会话累计由前端按消息求和派生）。
三列均可空（usage 缺失的兼容端点 / 旧数据不回填）；SQLite 直接 ALTER TABLE
ADD COLUMN（可空列无需 batch 重建）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7d2e9a4b513'
down_revision: Union[str, None] = 'f10a7c3e9b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级到本版本：messages 增 reasoning / prompt_tokens / completion_tokens 三可空列。"""
    op.add_column('messages', sa.Column('reasoning', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('prompt_tokens', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('completion_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    """回退到上一版本：移除三列。"""
    op.drop_column('messages', 'completion_tokens')
    op.drop_column('messages', 'prompt_tokens')
    op.drop_column('messages', 'reasoning')
