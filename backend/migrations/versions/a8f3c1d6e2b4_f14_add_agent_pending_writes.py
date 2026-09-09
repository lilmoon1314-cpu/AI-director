"""F14 add agent_pending_writes

Revision ID: a8f3c1d6e2b4
Revises: c7d2e9a4b513
Create Date: 2026-09-08

F14 Agent 写入工具链（DESIGN.md §13.2，OQ-8 轮末统一确认）:
- agent_pending_writes 表：写入类工具执行仅登记（pending），轮末 done 携带
  清单，作者批准后 approve 二次校验落库（approved）/放弃（rejected）；
- conversation_id FK ON DELETE CASCADE——会话删除级联清理登记行，项目删除
  经会话级联传导；project_id FK 为归属快照（approve 复核）；
- baseline_json 承载 write_doc_section 段 CAS 基线（落库校验，用户手改优先）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a8f3c1d6e2b4'
down_revision: str | None = 'c7d2e9a4b513'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """升级到本版本：创建 agent_pending_writes 表（待写入登记）。"""
    op.create_table(
        'agent_pending_writes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column(
            'conversation_id',
            sa.String(),
            sa.ForeignKey('conversations.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('baseline_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_agent_pending_writes_conversation_id'),
        'agent_pending_writes',
        ['conversation_id'],
    )
    op.create_index(
        op.f('ix_agent_pending_writes_status'),
        'agent_pending_writes',
        ['status'],
    )


def downgrade() -> None:
    """回退到上一版本：删除 agent_pending_writes 表与索引。"""
    op.drop_index(op.f('ix_agent_pending_writes_status'), table_name='agent_pending_writes')
    op.drop_index(
        op.f('ix_agent_pending_writes_conversation_id'), table_name='agent_pending_writes'
    )
    op.drop_table('agent_pending_writes')
