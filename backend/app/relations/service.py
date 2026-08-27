"""relations 模块 service 层：模块唯一对外接口（其他模块只允许 import 本层）。

事务边界: 本层自行 commit/rollback（backend/CONSTRAINTS.md「模块解耦与事务」）。
写入校验（relations/CONSTRAINTS.md）:
    - 端点存在性与 known_by 成员校验经 entities.service（禁止直查 entities 表）；
    - 自环关系、重复关系（同 source+target+type，有向）在本层拒绝。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.entities import service as entities_service
from app.relations import repository
from app.relations.models import Relationship, _utcnow
from app.relations.schemas import (
    RelationCreate,
    RelationRead,
    RelationUpdate,
    generate_relation_id,
)

# RelationUpdate 中可直接整体赋值的动态标量字段（known_by/properties 有专属语义单独处理）
_SCALAR_FIELDS = (
    "trust",
    "intimacy",
    "dependency",
    "resentment",
    "public_identity",
    "private_identity",
    "promise",
    "wants_from",
    "believes_other_wants",
    "leverage",
    "boundary",
    "status",
    "audience_known",
)


def _not_found(relation_id: str) -> NotFoundError:
    """构造关系不存在的三要素异常。

    作用: 统一 NotFoundError 的消息质量（三要素完整）。
    参数: relation_id — 未找到的关系 id。返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="关系不存在",
        cause=f"id '{relation_id}' 未在库中",
        fix="先调用 GET /api/relations 检索确认 id",
        detail={"relation_id": relation_id},
    )


def _self_loop(entity_id: str) -> ValidationError:
    """构造自环关系的三要素异常。

    作用: 自环拒绝的统一错误出口（relations/CONSTRAINTS.md）。
    参数: entity_id — source 与 target 重合的实体 id。
    返回值: ValidationError。异常: 无。依赖: 无。
    """
    return ValidationError(
        problem="自环关系被拒绝",
        cause=f"source 与 target 均为 '{entity_id}'，关系两端必须不同",
        fix="为 source 与 target 分别指定两个不同的实体 id",
        detail={"entity_id": entity_id, "rule": "no_self_loop"},
    )


def _endpoint_missing(field: str, entity_id: str) -> NotFoundError:
    """构造关系端点实体不存在的三要素异常。

    作用: 端点存在性校验失败的统一错误出口（detail 定位缺失端点字段）。
    参数: field — 缺失端点字段名（source/target）；entity_id — 缺失实体 id。
    返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="关系端点实体不存在",
        cause=f"'{field}' 指向的实体 '{entity_id}' 未在库中",
        fix="先经 POST /api/entities 创建端点实体，或用 GET /api/entities?q= 检索正确 id",
        detail={"field": field, "entity_id": entity_id},
    )


def _known_by_invalid(member: str, reason: str, entity_type: str | None = None) -> ValidationError:
    """构造 known_by 成员校验失败的三要素异常。

    作用: 视角标记完整性校验的统一错误出口（reason 区分缺失/非 character）。
    参数: member — 违规成员 id；reason — "missing" 或 "not_character"；
        entity_type — reason=not_character 时成员的实际类型。
    返回值: ValidationError。异常: 无。依赖: 无。
    """
    if reason == "missing":
        cause = f"成员 '{member}' 不是已存在的实体"
    else:
        cause = f"成员 '{member}' 的实体类型为 '{entity_type}'，不是 character"
    return ValidationError(
        problem="known_by 成员校验失败",
        cause=cause,
        fix="known_by 只能引用库中 character 类型实体的 id",
        detail={"member": member, "reason": reason, "entity_type": entity_type},
    )


def _duplicate(source: str, target: str, rel_type: str, existing_id: str) -> ConflictError:
    """构造重复关系的三要素异常。

    作用: 重复创建同 source+target+type（有向三元组）的统一错误出口。
    参数: source/target — 端点实体 id；rel_type — 关系类型；existing_id — 既有关系 id。
    返回值: ConflictError。异常: 无。依赖: 无。
    """
    return ConflictError(
        problem="重复关系被拒绝",
        cause=f"source='{source}' → target='{target}' 且 type='{rel_type}' 的关系已存在"
        f"（id='{existing_id}'）",
        fix=f"改用 PATCH /api/relations/{existing_id} 更新既有关系，或更换 type 建立新关系",
        detail={"source": source, "target": target, "type": rel_type, "existing_id": existing_id},
    )


def _new_relation(schema: RelationCreate) -> Relationship:
    """由请求模型构造 ORM 实例（id 系统生成，时间戳装配即填充）。

    作用: 创建路径的关系装配；时间戳在此填充而非依赖 flush 默认值，
        保证未落库状态（单元测试 mock）下响应模型可完整序列化。
    参数: schema — 已通过请求校验的创建载荷。
    返回值: Relationship（未入库）。异常: 无。依赖: app.relations.schemas。
    """
    now = _utcnow()
    return Relationship(
        id=generate_relation_id(),
        source=schema.source,
        target=schema.target,
        type=schema.type,
        trust=schema.trust,
        intimacy=schema.intimacy,
        dependency=schema.dependency,
        resentment=schema.resentment,
        public_identity=schema.public_identity,
        private_identity=schema.private_identity,
        promise=schema.promise,
        wants_from=schema.wants_from,
        believes_other_wants=schema.believes_other_wants,
        leverage=schema.leverage,
        boundary=schema.boundary,
        status=schema.status,
        known_by=list(schema.known_by),
        audience_known=schema.audience_known,
        properties=schema.properties,
        created_at=now,
        updated_at=now,
    )


async def _load_entity_types(session: AsyncSession, entity_ids: list[str]) -> dict[str, str]:
    """批量读取实体 id → type 映射（经 entities.service，缺失 id 不在结果中）。

    作用: 端点/known_by 校验的统一取数入口——单次批量查询替代逐个 get，
        且遵守「禁止直查 entities 表」约束。
    参数: session — 数据库会话；entity_ids — 去重后的实体 id 列表。
    返回值: dict[str, str]（存在的实体 id → type）。异常: 无。
    依赖: app.entities.service.get_many。
    """
    entities = await entities_service.get_many(session, entity_ids)
    return {e.id: e.type for e in entities}


def _require_members_valid(known_by: list[str], entity_types: dict[str, str]) -> None:
    """校验 known_by 成员均存在且为 character（基于已取回的 id→type 映射）。

    作用: 视角标记完整性校验（写入时防脏数据破坏视角过滤，backend/CONSTRAINTS.md）。
    参数: known_by — 待校验成员列表（允许重复，按首次出现顺序校验）；
        entity_types — _load_entity_types 取回的映射。
    返回值: 无（通过则静默返回）。
    异常: app.core.exceptions.ValidationError — 成员缺失或非 character。
    依赖: 无。
    """
    for member in dict.fromkeys(known_by):
        if member not in entity_types:
            raise _known_by_invalid(member, "missing")
        if entity_types[member] != "character":
            raise _known_by_invalid(member, "not_character", entity_types[member])


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


@checkpoint
async def create(session: AsyncSession, schema: RelationCreate) -> RelationRead:
    """创建关系（自环/端点/known_by/重复四重校验后入库）。

    作用: 关系创建的业务入口；id 由系统生成。
    参数: session — 数据库会话；schema — 创建载荷。
    返回值: RelationRead（含生成的 id 与时间戳）。
    异常:
        ValidationError — 自环关系；known_by 成员缺失或非 character。
        NotFoundError — source/target 端点实体不存在。
        ConflictError — 同 source+target+type 关系已存在。
    依赖: app.relations.repository、app.entities.service、app.relations.schemas。
    """
    if schema.source == schema.target:
        raise _self_loop(schema.source)

    entity_types = await _load_entity_types(
        session, list(dict.fromkeys([schema.source, schema.target, *schema.known_by]))
    )
    for field, endpoint in (("source", schema.source), ("target", schema.target)):
        if endpoint not in entity_types:
            raise _endpoint_missing(field, endpoint)
    _require_members_valid(schema.known_by, entity_types)

    existing = await repository.find_same(session, schema.source, schema.target, schema.type)
    if existing is not None:
        raise _duplicate(schema.source, schema.target, schema.type, existing.id)

    relation = await repository.add(session, _new_relation(schema))
    await session.commit()
    return RelationRead.model_validate(relation)


@checkpoint
async def get(session: AsyncSession, relation_id: str) -> RelationRead:
    """按 id 读取关系详情。

    作用: 详情查询的业务入口。
    参数: session — 数据库会话；relation_id — 关系 id。
    返回值: RelationRead。
    异常: NotFoundError — 关系不存在。
    依赖: app.relations.repository。
    """
    relation = await repository.get_by_id(session, relation_id)
    if relation is None:
        raise _not_found(relation_id)
    return RelationRead.model_validate(relation)


@checkpoint
async def update(session: AsyncSession, relation_id: str, schema: RelationUpdate) -> RelationRead:
    """局部更新关系动态属性（端点与 id/type 不可变由请求模型保证）。

    作用:
        局部更新业务入口；properties 为合并语义（同 entities），
        known_by 更新时重新执行成员校验（写入即校验，防脏数据）。
    参数: session — 数据库会话；relation_id — 关系 id；schema — 更新载荷。
    返回值: RelationRead（更新后状态）。
    异常: NotFoundError — 关系不存在；ValidationError — known_by 成员校验失败。
    依赖: app.relations.repository、app.entities.service。
    """
    relation = await repository.get_by_id(session, relation_id)
    if relation is None:
        raise _not_found(relation_id)

    for field in _SCALAR_FIELDS:
        value: Any = getattr(schema, field)
        if value is not None:
            setattr(relation, field, value)
    if schema.known_by is not None:
        entity_types = await _load_entity_types(session, list(dict.fromkeys(schema.known_by)))
        _require_members_valid(schema.known_by, entity_types)
        relation.known_by = list(schema.known_by)
    if schema.properties is not None:
        relation.properties = {**relation.properties, **schema.properties}

    relation = await repository.save(session, relation)
    await session.commit()
    return RelationRead.model_validate(relation)


@checkpoint
async def delete(session: AsyncSession, relation_id: str) -> None:
    """删除关系（关系表不被其他表引用，无前置引用校验）。

    作用: 删除业务入口——删除关系即解除对两端实体的引用，
        entities 侧删除防线（F02）随之对该实体放行。
    参数: session — 数据库会话；relation_id — 关系 id。
    返回值: 无。
    异常: NotFoundError — 关系不存在。
    依赖: app.relations.repository。
    """
    relation = await repository.get_by_id(session, relation_id)
    if relation is None:
        raise _not_found(relation_id)
    await repository.delete(session, relation)
    await session.commit()


@checkpoint
async def get_all(
    session: AsyncSession,
    *,
    source: str | None = None,
    target: str | None = None,
    rel_type: str | None = None,
) -> list[RelationRead]:
    """按端点/类型条件查询关系（无过滤条件返回全量，供 perspectives/sync 聚合）。

    作用: 条件查询业务入口；GET /api/relations 的数据源。
    参数: session — 数据库会话；source/target — 端点实体 id 过滤（可选）；
        rel_type — 关系类型过滤（可选）。
    返回值: list[RelationRead]。异常: 无。依赖: app.relations.repository。
    """
    relations = await repository.query(session, source=source, target=target, rel_type=rel_type)
    return [RelationRead.model_validate(r) for r in relations]
