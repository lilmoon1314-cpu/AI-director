"""perspectives 模块 service 层：视角可见性判定的唯一执行点（单一事实源）。

过滤规则（perspectives/ARCHITECTURE.md「过滤规则」）:
    - author: 实体/关系全量（外键完整性保证边端点必有节点）；
    - audience: 实体 audience_known=True；关系 audience_known=True 且双端实体可见
      （双端规则防止渲染出端点不可见的悬空边）；
    - character: 关系 known_by 含视角角色；实体 = 视角角色自身（恒可见）
      ∪ known 标记命中（event→properties.known_by、item→properties.seen_by）
      ∪ 可见关系端点推导。
只读约束: 本模块禁止写库（perspectives/CONSTRAINTS.md），不开启事务。
"""

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PerspectiveError
from app.core.observability import checkpoint
from app.entities import service as entities_service
from app.perspectives.schemas import GraphData, GraphEdge, GraphNode, Perspective
from app.relations import service as relations_service


class _EntityLike(Protocol):
    """实体数据的结构契约（不 import entities.schemas，模块解耦见 backend/CONSTRAINTS.md）。

    作用: 以结构化类型约束跨模块读取的字段需求，避免共享 DTO 的耦合。
        成员一律声明为只读 property（协变）——可变属性是不变的，
        EntityRead.type 的 Literal 类型将无法匹配 str。
    参数: 无（属性即契约）。返回值: 无（协议类）。异常: 无。依赖: typing.Protocol。
    """

    @property
    def id(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def aliases(self) -> list[str]: ...

    @property
    def audience_known(self) -> bool: ...

    @property
    def properties(self) -> dict[str, Any]: ...


class _RelationLike(Protocol):
    """关系数据的结构契约（不 import relations.schemas；成员只读，同上）。"""

    @property
    def id(self) -> str: ...

    @property
    def source(self) -> str: ...

    @property
    def target(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def known_by(self) -> list[str]: ...

    @property
    def audience_known(self) -> bool: ...


# 各实体类型的「角色知情标记」字段（位于 properties 内，蓝图 docs/data_struct_define.md §1；
# 未登记的类型无知情标记，仅经可见关系端点推导）
_KNOWN_MARKER_FIELDS: dict[str, str] = {"event": "known_by", "item": "seen_by"}


def _missing_character_id() -> PerspectiveError:
    """构造 character 视角缺参的三要素异常。

    作用: 统一缺参错误出口（detail.reason 供客户端定位）。
    参数: 无。返回值: PerspectiveError。异常: 无。依赖: 无。
    """
    return PerspectiveError(
        problem="character 视角必须指定 character_id",
        cause="perspective=character 时未提供视角角色的实体 id",
        fix="补全查询参数 character_id（character 视角的实体 id）",
        detail={"perspective": "character", "reason": "missing_character_id"},
    )


def _character_not_found(character_id: str) -> PerspectiveError:
    """构造视角角色不存在的三要素异常。

    作用: 统一角色缺失错误出口。
    参数: character_id — 未找到的实体 id。返回值: PerspectiveError。异常: 无。依赖: 无。
    """
    return PerspectiveError(
        problem="character 视角的角色不存在",
        cause=f"character_id '{character_id}' 未在实体库中",
        fix="先调用 GET /api/entities?q= 检索确认角色 id 后重试",
        detail={
            "perspective": "character",
            "reason": "character_not_found",
            "character_id": character_id,
        },
    )


def _not_character_type(character_id: str, entity_type: str) -> PerspectiveError:
    """构造视角角色类型不符的三要素异常。

    作用: character_id 指向非 character 实体时的统一错误出口。
    参数: character_id — 实体 id；entity_type — 实际类型。
    返回值: PerspectiveError。异常: 无。依赖: 无。
    """
    return PerspectiveError(
        problem="character 视角的 character_id 必须指向 character 类型实体",
        cause=f"id '{character_id}' 的类型为 '{entity_type}'，不是 character",
        fix="改传 character 类型实体的 id（可用 GET /api/entities?type=character 检索）",
        detail={
            "perspective": "character",
            "reason": "not_character_type",
            "character_id": character_id,
            "entity_type": entity_type,
        },
    )


def _is_known_by(entity: _EntityLike, character_id: str) -> bool:
    """判定实体是否被视角角色知情（known 标记命中）。

    作用: character 视角的实体可见性子规则——按实体类型查 properties 内的
        知情标记字段；标记值非列表（脏数据）不命中（读宽容容错）。
    参数: entity — 实体数据；character_id — 视角角色 id。
    返回值: bool。异常: 无。依赖: _KNOWN_MARKER_FIELDS。
    """
    marker = _KNOWN_MARKER_FIELDS.get(entity.type)
    if marker is None:
        return False
    value = entity.properties.get(marker)
    return isinstance(value, list) and character_id in value


@checkpoint
async def get_graph(
    session: AsyncSession,
    *,
    perspective: Perspective,
    character_id: str | None = None,
) -> GraphData:
    """三视角过滤图查询（模块唯一对外查询入口；只读，不开事务）。

    作用:
        聚合 entities/relations 全量数据后按视角规则过滤，输出轻量节点/边投影；
        视角可见性判定只发生在本函数（单一事实源的唯一执行点）。
    参数:
        session — 数据库会话（只读使用）；perspective — 视角枚举；
        character_id — character 视角的视角角色 id（其余视角忽略）。
    返回值: GraphData（nodes+edges）。
    异常:
        PerspectiveError — character 视角缺 character_id / 角色不存在 / 非 character 类型。
    依赖: app.entities.service、app.relations.service。
    """
    briefs = await entities_service.search(session)
    entities: list[_EntityLike] = list(
        await entities_service.get_many(session, [b.id for b in briefs])
    )
    relations: list[_RelationLike] = list(await relations_service.get_all(session))

    if perspective == "character":
        if not character_id:
            raise _missing_character_id()
        by_id = {e.id: e for e in entities}
        if character_id not in by_id:
            raise _character_not_found(character_id)
        if by_id[character_id].type != "character":
            raise _not_character_type(character_id, by_id[character_id].type)
        edges = [r for r in relations if character_id in r.known_by]
        visible = {character_id}
        visible.update(e.id for e in entities if _is_known_by(e, character_id))
        visible.update(node_id for r in edges for node_id in (r.source, r.target))
        nodes = [e for e in entities if e.id in visible]
    elif perspective == "audience":
        nodes = [e for e in entities if e.audience_known]
        visible = {e.id for e in nodes}
        edges = [
            r for r in relations if r.audience_known and r.source in visible and r.target in visible
        ]
    else:  # author
        nodes, edges = entities, relations

    return GraphData(
        nodes=[
            GraphNode(id=e.id, type=e.type, name=e.name, aliases=list(e.aliases)) for e in nodes
        ],
        edges=[GraphEdge(id=r.id, source=r.source, target=r.target, type=r.type) for r in edges],
    )
