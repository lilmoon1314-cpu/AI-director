"""entities 模块 service 层：模块唯一对外接口（其他模块只允许 import 本层）。

事务边界: 本层自行 commit/rollback（backend/CONSTRAINTS.md「模块解耦与事务」）。
删除防线: 应用层 ReferentialError（友好提示）+ DB 层外键 RESTRICT（兜底）。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ReferentialError
from app.core.observability import checkpoint
from app.entities import repository
from app.entities.models import Entity, _utcnow
from app.entities.schemas import (
    EntityBrief,
    EntityCreate,
    EntityRead,
    EntityUpdate,
    generate_entity_id,
    validate_properties,
)
from app.relations import service as relations_service


def _not_found(entity_id: str) -> NotFoundError:
    """构造实体不存在的三要素异常。

    作用: 统一 NotFoundError 的消息质量（三要素完整）。
    参数: entity_id — 未找到的实体 id。返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="实体不存在",
        cause=f"id '{entity_id}' 未在库中",
        fix="先调用 GET /api/entities?q= 检索确认 id",
        detail={"entity_id": entity_id},
    )


def _referential(entity_id: str, ref_count: int) -> ReferentialError:
    """构造实体被关系引用的三要素异常。

    作用: 删除阻断提示（应用层防线，见 backend/CONSTRAINTS.md）。
    参数: entity_id — 实体 id；ref_count — 引用条数。返回值: ReferentialError。
    异常: 无。依赖: 无。
    """
    return ReferentialError(
        problem="实体被关系引用，无法删除",
        cause=f"实体 '{entity_id}' 仍被 {ref_count} 条关系引用",
        fix="先删除或解除引用该实体的关系，再执行删除",
        detail={"entity_id": entity_id, "reference_count": ref_count},
    )


def _new_entity(schema: EntityCreate) -> Entity:
    """由请求模型构造 ORM 实例（id 系统生成，时间戳装配即填充）。

    作用: 创建路径的实体装配；时间戳在此填充而非依赖 flush 默认值，
        保证未落库状态（单元测试 mock）下响应模型可完整序列化。
    参数: schema — 已通过 Pydantic 请求校验的创建载荷。
    返回值: Entity（未入库）。异常: 无。依赖: app.entities.schemas。
    """
    now = _utcnow()
    return Entity(
        id=generate_entity_id(schema.type),
        type=schema.type,
        name=schema.name,
        aliases=schema.aliases,
        description=schema.description,
        audience_known=schema.audience_known,
        properties=schema.properties,
        created_at=now,
        updated_at=now,
    )


@checkpoint
async def create(session: AsyncSession, schema: EntityCreate) -> EntityRead:
    """创建实体（校验 properties 类型后入库）。

    作用: 实体创建的业务入口；id 由系统生成。
    参数: session — 数据库会话；schema — 创建载荷。
    返回值: EntityRead（含生成的 id 与时间戳）。
    异常: ValidationError — properties 类型校验失败。
    依赖: app.entities.repository、app.entities.schemas。
    """
    validate_properties(schema.type, schema.properties)
    entity = await repository.add(session, _new_entity(schema))
    await session.commit()
    return EntityRead.model_validate(entity)


@checkpoint
async def get(session: AsyncSession, entity_id: str) -> EntityRead:
    """按 id 读取实体详情。

    作用: 详情查询的业务入口。
    参数: session — 数据库会话；entity_id — 实体 id。
    返回值: EntityRead。
    异常: NotFoundError — 实体不存在。
    依赖: app.entities.repository。
    """
    entity = await repository.get_by_id(session, entity_id)
    if entity is None:
        raise _not_found(entity_id)
    return EntityRead.model_validate(entity)


@checkpoint
async def update(session: AsyncSession, entity_id: str, schema: EntityUpdate) -> EntityRead:
    """局部更新实体（仅更新显式提供的字段；id 不可变由请求模型保证）。

    作用:
        局部更新业务入口；properties 为合并语义（浅合并后整体校验），
        JSON 字段一律整体替换新对象（SQLAlchemy 变更检测要求）。
    参数: session — 数据库会话；entity_id — 实体 id；schema — 更新载荷。
    返回值: EntityRead（更新后状态）。
    异常: NotFoundError — 实体不存在；ValidationError — 合并后 properties 类型不符。
    依赖: app.entities.repository、app.entities.schemas。
    """
    entity = await repository.get_by_id(session, entity_id)
    if entity is None:
        raise _not_found(entity_id)

    if schema.name is not None:
        entity.name = schema.name
    if schema.aliases is not None:
        entity.aliases = list(schema.aliases)
    if schema.description is not None:
        entity.description = schema.description
    if schema.audience_known is not None:
        entity.audience_known = schema.audience_known
    if schema.properties is not None:
        merged: dict[str, Any] = {**entity.properties, **schema.properties}
        validate_properties(entity.type, merged)
        entity.properties = merged  # 整体替换，保证 JSON 列变更可被检测

    entity = await repository.save(session, entity)
    await session.commit()
    return EntityRead.model_validate(entity)


@checkpoint
async def delete(session: AsyncSession, entity_id: str) -> None:
    """删除实体（先校验关系引用，命中则阻断）。

    作用:
        删除业务入口——应用层 ReferentialError 为前置防线，
        DB 层外键 RESTRICT 兜底防旁路写入。
    参数: session — 数据库会话；entity_id — 实体 id。
    返回值: 无。
    异常: NotFoundError — 实体不存在；ReferentialError — 被关系引用。
    依赖: app.entities.repository、app.relations.service。
    """
    entity = await repository.get_by_id(session, entity_id)
    if entity is None:
        raise _not_found(entity_id)

    ref_count = await relations_service.count_by_entity(session, entity_id)
    if ref_count > 0:
        raise _referential(entity_id, ref_count)

    await repository.delete(session, entity)
    await session.commit()


@checkpoint
async def search(
    session: AsyncSession, q: str = "", entity_type: str | None = None
) -> list[EntityBrief]:
    """按名称/别名检索实体（@ 实体选择器数据源）。

    作用: 检索业务入口；q 为空返回全量摘要。
    参数: session — 数据库会话；q — 关键字；entity_type — 类型过滤（可选）。
    返回值: list[EntityBrief]。异常: 无。依赖: app.entities.repository。
    """
    entities = await repository.search(session, q=q, entity_type=entity_type)
    return [EntityBrief.model_validate(e) for e in entities]


@checkpoint
async def get_many(session: AsyncSession, entity_ids: list[str]) -> list[EntityRead]:
    """按 id 列表批量读取实体（供 perspectives 聚合）。

    作用: 跨模块聚合读取的唯一入口；缺失 id 静默跳过（保持传入顺序）。
    参数: session — 数据库会话；entity_ids — 实体 id 列表。
    返回值: list[EntityRead]。异常: 无。依赖: app.entities.repository。
    """
    entities = await repository.get_many(session, entity_ids)
    return [EntityRead.model_validate(e) for e in entities]


@checkpoint
async def list_all(session: AsyncSession) -> list[EntityRead]:
    """读取全量实体（供 assets 项目资产卡片聚合）。

    作用: 跨模块全量读取入口（F08 资产管理）；无投影收窄——资产管理是
        作者侧管理面（DECISIONS 2026-08-28 视角作用面决策，不经过视角过滤）。
    参数: session — 数据库会话。
    返回值: list[EntityRead]（按名称排序）。
    异常: 无。依赖: app.entities.repository。
    """
    entities = await repository.search(session)
    return [EntityRead.model_validate(e) for e in entities]
