"""relations 模块数据访问层（F02 仅引用计数；CRUD 由 F03 扩展）。

事务约定: 本层不 commit/rollback（事务边界在 service 层）。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.relations.models import Relationship


async def count_by_entity(session: AsyncSession, entity_id: str) -> int:
    """统计实体被关系引用的次数（source 或 target 任一命中即计）。

    作用: 删除引用校验的取数入口。
    参数: session — 数据库会话；entity_id — 实体 id。
    返回值: int。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(func.count())
        .select_from(Relationship)
        .where((Relationship.source == entity_id) | (Relationship.target == entity_id))
    )
    return int(await session.scalar(stmt) or 0)
