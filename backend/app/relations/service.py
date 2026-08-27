"""relations 模块 service 层：模块唯一对外接口（跨模块只允许 import 本层）。

F02 范围: 仅提供删除引用计数接口（entities.service 删除校验依赖）。
关系 CRUD 由 F03 实现（见 docs/features.md）。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import checkpoint
from app.relations import repository


@checkpoint
async def count_by_entity(session: AsyncSession, entity_id: str) -> int:
    """统计实体被关系引用的次数（source 或 target 任一命中即计）。

    作用:
        entities.service 删除前置校验的数据来源——引用数 > 0 时删除必须被
        ReferentialError 阻断（应用层防线；DB 层 RESTRICT 为兜底）。
    参数: session — 数据库会话；entity_id — 被引用实体 id。
    返回值: int — 引用该实体的关系条数。
    异常: 无（计数查询不抛业务异常）。
    依赖: app.relations.repository。
    """
    return await repository.count_by_entity(session, entity_id)
