"""relations 模块数据访问层：唯一允许 import 本模块 ORM 模型的层。

F02 范围: 仅 count_by_entity（删除引用计数）；F03 扩展 CRUD 与条件查询。
事务约定: 本层不 commit/rollback（事务边界在 service 层，backend/CONSTRAINTS.md）。
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


async def add(session: AsyncSession, relation: Relationship) -> Relationship:
    """插入一条关系记录。

    作用: 新建关系（不提交事务，由 service 层控制）；端点/自环/重复校验
        已在 service 层先行完成，本层不再拦截。
    参数: session — 数据库会话；relation — 已填充字段的 ORM 实例。
    返回值: Relationship。异常: 无（外键冲突由 DB 层 RESTRICT 兜底抛出）。
    依赖: SQLAlchemy ORM。
    """
    session.add(relation)
    await session.flush()
    return relation


async def get_by_id(session: AsyncSession, relation_id: str) -> Relationship | None:
    """按 id 查询单条关系。

    作用: 详情/更新/删除的取数入口。
    参数: session — 数据库会话；relation_id — 关系 id。
    返回值: Relationship 或 None（不存在）。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(Relationship, relation_id)


async def save(session: AsyncSession, relation: Relationship) -> Relationship:
    """保存已修改的关系（UPDATE）。

    作用: 局部更新落库（不提交事务）。
    参数: session — 数据库会话；relation — 已在内存中修改的 ORM 实例。
    返回值: Relationship。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return relation


async def delete(session: AsyncSession, relation: Relationship) -> None:
    """删除关系记录（不提交事务）。

    作用: 物理删除关系；关系表不被其他表引用（MVP 范围），无前置校验需求。
    参数: session — 数据库会话；relation — 待删除 ORM 实例。
    返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(relation)
    await session.flush()


async def find_same(
    session: AsyncSession, source: str, target: str, rel_type: str
) -> Relationship | None:
    """查找同端点同类型的关系（source+target+type 三元组，有向语义）。

    作用: 重复关系拒绝的取数入口（命中即 ConflictError，见本模块 CONSTRAINTS）。
    参数: session — 数据库会话；source/target — 端点实体 id；rel_type — 关系类型。
    返回值: Relationship 或 None（不存在同三元组关系）。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(Relationship).where(
        Relationship.source == source,
        Relationship.target == target,
        Relationship.type == rel_type,
    )
    return (await session.scalars(stmt.limit(1))).first()


async def query(
    session: AsyncSession,
    *,
    source: str | None = None,
    target: str | None = None,
    rel_type: str | None = None,
) -> list[Relationship]:
    """按端点/类型条件查询关系（无过滤条件返回全量）。

    作用: GET /api/relations 条件查询与 perspectives 聚合的取数入口。
    参数: session — 数据库会话；source/target — 端点实体 id 过滤（可选）；
        rel_type — 关系类型过滤（可选）。
    返回值: list[Relationship]（按 id 排序，保证结果稳定）。异常: 无。
    依赖: SQLAlchemy ORM。
    """
    stmt = select(Relationship)
    if source is not None:
        stmt = stmt.where(Relationship.source == source)
    if target is not None:
        stmt = stmt.where(Relationship.target == target)
    if rel_type is not None:
        stmt = stmt.where(Relationship.type == rel_type)
    return list(await session.scalars(stmt.order_by(Relationship.id)))
