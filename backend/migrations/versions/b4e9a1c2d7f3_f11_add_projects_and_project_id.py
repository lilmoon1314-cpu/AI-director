"""F11 add projects table and project_id columns

Revision ID: b4e9a1c2d7f3
Revises: e9a2e0f0a667
Create Date: 2026-09-06

F11 多项目底座（DESIGN.md §8 / DECISIONS 2026-09-06）:
- 新建 projects 表（含反规范化计数器列）；
- 插入默认项目（固定 id 'project-default'），计数器以存量数据回填；
- entities / relationships 增加 project_id（FK projects + 索引），
  存量数据打包进默认项目（向后兼容：不带 project_id 的旧客户端行为不变）。
SQLite 约束下加列/外键经 batch_alter_table（表重建）完成。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b4e9a1c2d7f3'
down_revision: Union[str, None] = 'e9a2e0f0a667'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PROJECT_ID = 'project-default'


def upgrade() -> None:
    """升级到本版本：建 projects 表 + 默认项目 + 双表 project_id 归属列。"""
    op.create_table(
        'projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('entity_count', sa.Integer(), nullable=False),
        sa.Column('relation_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # 默认项目：固定 id；计数器以存量行数回填（打包兼容）
    op.execute(
        "INSERT INTO projects (id, name, description, entity_count, relation_count, "
        "created_at, updated_at) "
        "SELECT 'project-default', '默认项目', "
        "'未指定项目的数据兜底归档（可改名用作正式项目）', "
        "IFNULL((SELECT COUNT(*) FROM entities), 0), "
        "IFNULL((SELECT COUNT(*) FROM relationships), 0), "
        "datetime('now'), datetime('now')"
    )

    # entities.project_id：先可空加列（batch 重建带外键）→ 回填 → 收紧非空 → 索引
    with op.batch_alter_table('entities') as batch:
        batch.add_column(sa.Column('project_id', sa.String(), nullable=True))
        batch.create_foreign_key('fk_entities_project_id', 'projects', ['project_id'], ['id'])
    op.execute(
        f"UPDATE entities SET project_id = '{_DEFAULT_PROJECT_ID}' WHERE project_id IS NULL"
    )
    with op.batch_alter_table('entities') as batch:
        batch.alter_column('project_id', existing_type=sa.String(), nullable=False)
    op.create_index(op.f('ix_entities_project_id'), 'entities', ['project_id'], unique=False)

    # relationships.project_id：同上
    with op.batch_alter_table('relationships') as batch:
        batch.add_column(sa.Column('project_id', sa.String(), nullable=True))
        batch.create_foreign_key(
            'fk_relationships_project_id', 'projects', ['project_id'], ['id']
        )
    op.execute(
        f"UPDATE relationships SET project_id = '{_DEFAULT_PROJECT_ID}' WHERE project_id IS NULL"
    )
    with op.batch_alter_table('relationships') as batch:
        batch.alter_column('project_id', existing_type=sa.String(), nullable=False)
    op.create_index(
        op.f('ix_relationships_project_id'), 'relationships', ['project_id'], unique=False
    )


def downgrade() -> None:
    """回退到上一版本：移除 project_id 列与 projects 表（项目维度数据丢失）。"""
    op.drop_index(op.f('ix_relationships_project_id'), table_name='relationships')
    with op.batch_alter_table('relationships') as batch:
        batch.drop_column('project_id')
    op.drop_index(op.f('ix_entities_project_id'), table_name='entities')
    with op.batch_alter_table('entities') as batch:
        batch.drop_column('project_id')
    op.drop_table('projects')
