"""entities 模块数据访问层：唯一允许 import 本模块 ORM 模型的层。

事务约定: 本层不 commit/rollback（事务边界在 service 层，backend/CONSTRAINTS.md）。
"""

from sqlalchemy import delete as sa_delete
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.models import Entity


async def add(session: AsyncSession, entity: Entity) -> Entity:
    """插入一条实体记录。

    作用: 新建实体（不提交事务，由 service 层控制）。
    参数: session — 数据库会话；entity — 已填充字段的 ORM 实例。
    返回值: Entity（含默认字段生效后的状态）。异常: 无（约束冲突由 service 捕获处理）。
    依赖: SQLAlchemy ORM。
    """
    session.add(entity)
    await session.flush()
    return entity


async def get_by_id(session: AsyncSession, entity_id: str) -> Entity | None:
    """按 id 查询单个实体。

    作用: 详情/更新/删除的取数入口。
    参数: session — 数据库会话；entity_id — 实体 id。
    返回值: Entity 或 None（不存在）。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(Entity, entity_id)


async def get_many(session: AsyncSession, entity_ids: list[str]) -> list[Entity]:
    """按 id 列表批量查询实体（保持传入顺序，缺失的 id 静默跳过）。

    作用: 供 perspectives 聚合读取（模块外经 service.get_many 调用）。
    参数: session — 数据库会话；entity_ids — 实体 id 列表。
    返回值: list[Entity]。异常: 无。依赖: SQLAlchemy ORM。
    """
    if not entity_ids:
        return []
    rows = {
        row.id: row
        for row in await session.scalars(select(Entity).where(Entity.id.in_(entity_ids)))
    }
    return [rows[eid] for eid in entity_ids if eid in rows]


async def search(
    session: AsyncSession,
    q: str = "",
    entity_type: str | None = None,
    project_id: str | None = None,
) -> list[Entity]:
    """按名称/别名模糊检索实体（q 为空返回全量），可叠加类型与项目过滤。

    作用: @ 实体选择器的取数入口；别名为 JSON 列，用 json_each 相关子查询匹配。
        （join 表值函数无法隐式推导连接方向，EXISTS + 相关 json_each 是
        SQLite JSON1 下标准且有确定语义的模式。）
    参数: session — 数据库会话；q — 关键字（大小写不敏感子串）；
        entity_type — 类型过滤；project_id — 项目归属过滤（F11，None=不过滤）。
    返回值: list[Entity]（按 name 排序，保证结果稳定）。异常: 无。依赖: SQLAlchemy JSON1。
    """
    stmt = select(Entity)
    if q:
        pattern = f"%{q}%"
        # 相关子查询逐元素展开 aliases 匹配（内层仅引用外层 Entity.aliases，
        # SQLAlchemy 自动完成 correlation，子查询按当前行求值）
        alias_value = func.json_each(Entity.aliases).table_valued("value").c.value
        alias_matches = (
            select(1)
            .select_from(func.json_each(Entity.aliases))
            .where(func.lower(alias_value).ilike(pattern))
            .exists()
        )
        stmt = stmt.where(or_(Entity.name.ilike(pattern), alias_matches))
    if entity_type is not None:
        stmt = stmt.where(Entity.type == entity_type)
    if project_id is not None:
        stmt = stmt.where(Entity.project_id == project_id)
    return list(await session.scalars(stmt.order_by(Entity.name)))


async def save(session: AsyncSession, entity: Entity) -> Entity:
    """保存已修改的实体（UPDATE）。

    作用: 局部更新落库（不提交事务）。
    参数: session — 数据库会话；entity — 已在内存中修改的 ORM 实例。
    返回值: Entity。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return entity


async def delete(session: AsyncSession, entity: Entity) -> None:
    """删除实体记录（不提交事务；引用校验由 service 层先行完成）。

    作用: 物理删除；若仍被 relationships 引用，DB 层 RESTRICT 兜底抛 IntegrityError。
    参数: session — 数据库会话；entity — 待删除 ORM 实例。
    返回值: 无。异常: sqlalchemy.exc.IntegrityError — 外键约束兜底触发时。
    依赖: SQLAlchemy ORM。
    """
    await session.delete(entity)
    await session.flush()


async def exists_by_name(session: AsyncSession, name: str, entity_type: str) -> bool:
    """查询同类型同名实体是否已存在（保留接口，供后续唯一性策略使用）。

    作用: 名称重复检测的取数入口。
    参数: session — 数据库会话；name — 实体名；entity_type — 实体类型。
    返回值: bool。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(exists().where(Entity.name == name, Entity.type == entity_type))
    return bool(await session.scalar(stmt))


async def list_ids_by_project(session: AsyncSession, project_id: str) -> list[str]:
    """列出项目内全部实体 id（删项目级联的取数入口）。

    作用: 级联删除前收集实体 id 集合（供资产库显式清扫）；按 id 排序保证稳定。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: list[str]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(Entity.id).where(Entity.project_id == project_id).order_by(Entity.id)
    return list(await session.scalars(stmt))


async def delete_by_ids(session: AsyncSession, entity_ids: list[str]) -> None:
    """按 id 集合批量删除实体（不提交事务；级联编排收口提交）。

    作用: 删项目级联的执行入口——该项目的全部关系已先行删除（FK RESTRICT），
        批量删除经核心 delete 语句在同一事务内执行。
    参数: session — 数据库会话；entity_ids — 待删除实体 id 集合（非空）。
    返回值: 无。异常: sqlalchemy.exc.IntegrityError — 仍有关系引用时 DB 层兜底。
    依赖: SQLAlchemy ORM。
    """
    await session.execute(sa_delete(Entity).where(Entity.id.in_(entity_ids)))
