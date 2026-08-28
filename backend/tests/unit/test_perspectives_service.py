"""F04 L1 单元测试：perspectives service 三视角过滤逻辑（依赖全 mock，内存执行）。

mock 策略: 以内存种子替换 entities.service.search/get_many 与 relations.service.get_all
（perspectives 经 service 层聚合的唯一取数通道），只验证视角过滤/校验/投影逻辑，
不触数据库。种子世界与期望视图见 docs/tests/F04_graph_perspective_query.md。
"""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.exceptions import PerspectiveError
from app.entities import service as entities_service
from app.perspectives import schemas, service
from app.relations import service as relations_service

pytestmark = pytest.mark.unit

# service 只把 session 透传给 mock，无需真实会话
_SESSION = SimpleNamespace()


def _entity(
    eid: str,
    etype: str,
    name: str,
    *,
    audience: bool = False,
    props: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """构造协议结构一致的实体桩（字段契约见 service._EntityLike）。"""
    return SimpleNamespace(
        id=eid,
        type=etype,
        name=name,
        aliases=[],
        audience_known=audience,
        properties=props or {},
    )


def _relation(
    rid: str,
    source: str,
    target: str,
    *,
    known_by: list[str],
    audience: bool = False,
    rtype: str = "LINKS",
) -> SimpleNamespace:
    """构造协议结构一致的关系桩（字段契约见 service._RelationLike）。"""
    return SimpleNamespace(
        id=rid,
        source=source,
        target=target,
        type=rtype,
        known_by=known_by,
        audience_known=audience,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    entities: list[SimpleNamespace],
    relations: list[SimpleNamespace],
) -> None:
    """把内存种子注入 perspectives 的取数通道（search/get_many/get_all）。

    作用: 单元层完全隔离数据库；get_many 保持传入顺序、缺失跳过，
        与真实 repository 语义一致。
    参数: monkeypatch — pytest 替换器；entities/relations — 种子数据。
    返回值: 无。异常: 无。依赖: app.entities.service、app.relations.service。
    """

    async def fake_search(
        _session: Any, q: str = "", entity_type: str | None = None
    ) -> list[SimpleNamespace]:
        rows = [e for e in entities if entity_type is None or e.type == entity_type]
        return [SimpleNamespace(id=e.id) for e in sorted(rows, key=lambda x: x.name)]

    async def fake_get_many(_session: Any, ids: list[str]) -> list[SimpleNamespace]:
        by_id = {e.id: e for e in entities}
        return [by_id[i] for i in ids if i in by_id]

    async def fake_get_all(_session: Any, **_: Any) -> list[SimpleNamespace]:
        return list(relations)

    monkeypatch.setattr(entities_service, "search", fake_search)
    monkeypatch.setattr(entities_service, "get_many", fake_get_many)
    monkeypatch.setattr(relations_service, "get_all", fake_get_all)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> None:
    """安装测试文档定义的标准种子世界（6 实体 / 3 关系）。"""
    entities = [
        _entity("char-a", "character", "周兰", audience=True),
        _entity("char-b", "character", "沈墨"),
        _entity("char-c", "character", "陆离", audience=True),
        _entity("item-x", "item", "青铜镜", props={"seen_by": ["char-a"]}),
        _entity("event-e", "event", "夜探药庐", audience=True, props={"known_by": ["char-b"]}),
        _entity("loc-l", "location", "青云山", audience=True),
    ]
    relations = [
        _relation("rel-1", "char-a", "char-b", known_by=["char-a"], audience=True),
        _relation("rel-2", "char-a", "loc-l", known_by=["char-a", "char-b"], audience=True),
        _relation("rel-3", "char-b", "event-e", known_by=["char-b"], audience=True),
    ]
    _install(monkeypatch, entities, relations)


async def test_author_returns_everything(world: None) -> None:
    """U1 author 全量：6 节点 3 边，节点按 name 排序稳定。

    前置: 标准种子；动作: get_graph(author)；预期: 全量且排序稳定。
    设计依据: 等价类—perspective 有效-author。
    """
    data = await service.get_graph(_SESSION, perspective="author")
    assert {n.id for n in data.nodes} == {
        "char-a",
        "char-b",
        "char-c",
        "item-x",
        "event-e",
        "loc-l",
    }, (
        "【问题】author 视角未返回全量节点\n"
        "【原因】author 分支错误套用了过滤规则\n"
        "【修复】检查 service.get_graph author 分支应直通全量数据"
    )
    assert len(data.edges) == 3, (
        "【问题】author 视角未返回全部关系\n"
        "【原因】author 分支错误套用了过滤规则\n"
        "【修复】检查 service.get_graph author 分支应直通全量数据"
    )
    names = [n.name for n in data.nodes]
    assert names == sorted(names), (
        f"【问题】author 节点未按 name 排序: {names}\n"
        "【原因】聚合取数未保持 search 的 name 排序\n"
        "【修复】检查 get_graph 不应重排节点集合"
    )


async def test_audience_filters_and_requires_both_endpoints(world: None) -> None:
    """U2 audience 过滤：仅 audience_known 实体；边须 audience_known 且双端可见。

    前置: 标准种子；动作: get_graph(audience)；预期: 4 节点、仅 rel-2
        （rel-1/rel-3 虽 audience_known=True 但端点沈墨不可见，被双端规则排除）。
    设计依据: 等价类—perspective 有效-audience；含边可见性双端规则。
    """
    data = await service.get_graph(_SESSION, perspective="audience")
    assert {n.id for n in data.nodes} == {"char-a", "char-c", "event-e", "loc-l"}, (
        f"【问题】audience 节点集合不符: {[n.id for n in data.nodes]}\n"
        "【原因】audience_known 过滤条件未正确生效\n"
        "【修复】检查 service.get_graph audience 分支的实体过滤"
    )
    assert {e.id for e in data.edges} == {"rel-2"}, (
        f"【问题】audience 边集合不符: {[e.id for e in data.edges]}\n"
        "【原因】边过滤缺少双端可见校验（rel-1/rel-3 端点沈墨不可见仍被放行）\n"
        "【修复】检查 audience 分支应同时校验 source/target 均在可见节点集内"
    )


@pytest.mark.parametrize(
    ("character_id", "expected_nodes", "expected_edges"),
    [
        ("char-a", {"char-a", "char-b", "item-x", "loc-l"}, {"rel-1", "rel-2"}),
        ("char-b", {"char-b", "char-a", "event-e", "loc-l"}, {"rel-2", "rel-3"}),
        ("char-c", {"char-c"}, set()),
    ],
    ids=["char-a-edges+item-marker", "char-b-edges+event-marker", "char-c-isolated-self-only"],
)
async def test_character_view_three_states(
    world: None, character_id: str, expected_nodes: set[str], expected_edges: set[str]
) -> None:
    """U3 character 三态：边+标记推导 / 边+事件标记 / 孤立角色仅自身恒可见。

    前置: 标准种子；动作: get_graph(character, character_id)；预期: 节点/边集合。
    设计依据: 等价类—perspective 有效-character 三态（有关系+item 标记 /
        有关系+event 标记 / 无关系无标记仅自身）。
    """
    data = await service.get_graph(_SESSION, perspective="character", character_id=character_id)
    assert {n.id for n in data.nodes} == expected_nodes, (
        f"【问题】{character_id} 视角节点集合不符: {[n.id for n in data.nodes]}\n"
        "【原因】known 标记命中或可见关系端点推导规则未正确生效\n"
        "【修复】检查 character 分支的 visible 集合装配（自身 ∪ 标记 ∪ 端点）"
    )
    assert {e.id for e in data.edges} == expected_edges, (
        f"【问题】{character_id} 视角边集合不符: {[e.id for e in data.edges]}\n"
        "【原因】关系 known_by 过滤条件未正确生效\n"
        "【修复】检查 character 分支应仅保留 known_by 含视角角色的关系"
    )


@pytest.mark.parametrize("bad_id", [None, ""], ids=["none", "empty-string"])
async def test_character_requires_character_id(world: None, bad_id: str | None) -> None:
    """U4 character 缺 character_id（None/空串）→ PerspectiveError。

    前置: 标准种子；动作: get_graph(character, character_id=bad_id)；
        预期: PerspectiveError，reason=missing_character_id，三要素完整。
    设计依据: 无效等价类—必选参数缺失；边界值—空串视同缺失。
    """
    with pytest.raises(PerspectiveError) as exc_info:
        await service.get_graph(_SESSION, perspective="character", character_id=bad_id)
    exc = exc_info.value
    assert exc.detail == {"perspective": "character", "reason": "missing_character_id"}, (
        f"【问题】缺参错误 detail 不符: {exc.detail}\n"
        "【原因】缺 character_id 的判定分支未覆盖空值或 detail 结构漂移\n"
        "【修复】检查 character 分支应以 falsy 判定缺失且 detail 两键齐全"
    )
    assert exc.problem == "character 视角必须指定 character_id", (
        f"【问题】缺参错误 problem 不符: {exc.problem}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service._missing_character_id 文案"
    )
    assert exc.cause == "perspective=character 时未提供视角角色的实体 id", (
        f"【问题】缺参错误 cause 不符: {exc.cause}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service._missing_character_id 文案"
    )
    assert exc.fix == "补全查询参数 character_id（character 视角的实体 id）", (
        f"【问题】缺参错误 fix 不符: {exc.fix}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service._missing_character_id 文案"
    )


@pytest.mark.parametrize(
    ("bad_id", "reason", "problem", "cause", "fix", "extra_detail"),
    [
        (
            "char-none",
            "character_not_found",
            "character 视角的角色不存在",
            "character_id 'char-none' 未在实体库中",
            "先调用 GET /api/entities?q= 检索确认角色 id 后重试",
            {"character_id": "char-none"},
        ),
        (
            "loc-l",
            "not_character_type",
            "character 视角的 character_id 必须指向 character 类型实体",
            "id 'loc-l' 的类型为 'location'，不是 character",
            "改传 character 类型实体的 id（可用 GET /api/entities?type=character 检索）",
            {"character_id": "loc-l", "entity_type": "location"},
        ),
    ],
    ids=["entity-missing", "not-character-type"],
)
async def test_character_rejects_invalid_character_id(
    world: None,
    bad_id: str,
    reason: str,
    problem: str,
    cause: str,
    fix: str,
    extra_detail: dict[str, str],
) -> None:
    """U5 character_id 无效：不存在 / 非 character 类型 → PerspectiveError(403)。

    前置: 标准种子；动作: get_graph(character, character_id=bad_id)；
        预期: PerspectiveError 且三要素文案与 detail 结构钉死（变异测试补充）。
    设计依据: 无效等价类—角色不存在 / 角色类型不符。
    """
    with pytest.raises(PerspectiveError) as exc_info:
        await service.get_graph(_SESSION, perspective="character", character_id=bad_id)
    exc = exc_info.value
    assert exc.detail == {"perspective": "character", "reason": reason, **extra_detail}, (
        f"【问题】无效 character_id 的 detail 不符: {exc.detail}\n"
        f"【原因】存在性/类型校验分支与预期 {reason} 不一致或 detail 结构漂移\n"
        "【修复】检查 character 分支的角色存在性与类型校验及 detail 装配"
    )
    assert exc.problem == problem, (
        f"【问题】{reason} 的 problem 不符: {exc.problem}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service 异常构造函数文案"
    )
    assert exc.cause == cause, (
        f"【问题】{reason} 的 cause 不符: {exc.cause}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service 异常构造函数文案"
    )
    assert exc.fix == fix, (
        f"【问题】{reason} 的 fix 不符: {exc.fix}\n"
        "【原因】三要素文案漂移\n【修复】对齐 service 异常构造函数文案"
    )
    assert exc.http_status == 403


@pytest.mark.parametrize(
    ("target_entity", "expected_visible"),
    [
        (_entity("ev-1", "event", "事件A", props={"known_by": ["char-a"]}), True),
        (_entity("it-1", "item", "物件A", props={"seen_by": ["char-a"]}), True),
        (_entity("lo-1", "location", "地点A"), False),
        (_entity("ev-2", "event", "事件B", props={"known_by": []}), False),
        (_entity("ev-3", "event", "事件C", props={"known_by": "char-a"}), False),
        (_entity("ev-4", "event", "事件D", props={"known_by": ["char-b"]}), False),
    ],
    ids=[
        "event-known-by-hit",
        "item-seen-by-hit",
        "location-no-marker",
        "empty-marker-list",
        "dirty-marker-type",
        "marker-without-target",
    ],
)
async def test_character_known_marker_matrix(
    monkeypatch: pytest.MonkeyPatch, target_entity: SimpleNamespace, expected_visible: bool
) -> None:
    """U6 known 标记命中矩阵：类型映射 / 空表 / 脏数据 / 未含目标。

    前置: 世界仅含 char-a 与目标实体（无关系，纯标记判定）；
        动作: get_graph(character, char-a)；预期: 目标实体可见性与参数化预期一致。
    设计依据: 等价类—event→known_by / item→seen_by / 无标记类型；
        边界值—标记列表空 / 单元素未含目标 / 值为非列表脏数据（读宽容容错）。
    """
    char_a = _entity("char-a", "character", "周兰")
    _install(monkeypatch, [char_a, target_entity], [])
    data = await service.get_graph(_SESSION, perspective="character", character_id="char-a")
    visible = target_entity.id in {n.id for n in data.nodes}
    assert visible is expected_visible, (
        f"【问题】实体 {target_entity.id} 可见性应为 {expected_visible}\n"
        f"【原因】known 标记判定（类型映射/空表/脏数据容错）与规则不符\n"
        "【修复】检查 _is_known_by 的类型映射与 isinstance 容错逻辑"
    )


async def test_projection_is_lightweight(world: None) -> None:
    """U7 输出投影轻量：节点/边仅含渲染必需字段（不泄露通道）。

    前置: 标准种子；动作: get_graph(author)；预期: GraphNode 字段恰为
        {id,type,name,aliases}，GraphEdge 恰为 {id,source,target,type}。
    设计依据: 等价类—输出契约：轻量投影（不含 properties/description/known_by）。
    """
    data = await service.get_graph(_SESSION, perspective="author")
    assert data.nodes and data.edges, "前置失败：种子世界不应为空"
    assert set(data.nodes[0].model_dump()) == {"id", "type", "name", "aliases"}, (
        f"【问题】GraphNode 字段超集: {set(data.nodes[0].model_dump())}\n"
        "【原因】投影模型混入了动态细节字段（潜在泄露通道）\n"
        "【修复】检查 perspectives.schemas.GraphNode 只保留渲染必需字段"
    )
    assert set(data.edges[0].model_dump()) == {"id", "source", "target", "type"}, (
        f"【问题】GraphEdge 字段超集: {set(data.edges[0].model_dump())}\n"
        "【原因】投影模型混入了名称或动态细节字段\n"
        "【修复】检查 perspectives.schemas.GraphEdge 只保留 id 四元组"
    )


@pytest.mark.parametrize(
    "perspective", ["author", "audience"], ids=["author-empty", "audience-empty"]
)
async def test_empty_store_returns_empty_graph(
    monkeypatch: pytest.MonkeyPatch, perspective: str
) -> None:
    """U8 空库：author/audience 返回空图（character 视角空库由 U5 覆盖）。

    前置: 空种子；动作: get_graph(perspective)；预期: nodes/edges 均空。
    设计依据: 边界值—数据集空集。
    """
    _install(monkeypatch, [], [])
    data = await service.get_graph(_SESSION, perspective=perspective)
    assert data.nodes == [] and data.edges == [], (
        f"【问题】空库返回了非空图: {data.model_dump()}\n"
        "【原因】空数据集聚合路径未正确短路\n"
        "【修复】检查 get_graph 对空 search/get_all 结果的处理"
    )


def test_graph_data_defaults_are_empty_lists() -> None:
    """U9a GraphData 省略字段构造默认空集（变异测试 §9 补充）。

    前置: 无；动作: 无参构造 GraphData；预期: nodes/edges 均为空列表（非 None）。
    设计依据: §9 变异测试补充—default_factory=list 契约钉死（响应形状稳定）。
    """
    data = schemas.GraphData()
    assert data.nodes == [] and data.edges == [], (
        f"【问题】GraphData 默认值不符: {data.model_dump()}\n"
        "【原因】nodes/edges 默认值漂移（default_factory 丢失则序列化为 null）\n"
        "【修复】检查 perspectives.schemas.GraphData 的 default_factory"
    )


def test_graph_node_type_is_required() -> None:
    """U9b GraphNode.type 必填（变异测试 §9 补充）。

    前置: 无；动作: 缺 type 构造 GraphNode；预期: ValidationError。
    设计依据: §9 变异测试补充—type 无默认值契约（输出契约：类型必填）。
    """
    with pytest.raises(ValidationError):
        schemas.GraphNode(id="n1", name="无名", aliases=[])


@pytest.mark.parametrize(
    ("owner", "member"),
    [
        (service._EntityLike, n)
        for n in ("id", "type", "name", "aliases", "audience_known", "properties")
    ]
    + [
        (service._RelationLike, n)
        for n in ("id", "source", "target", "type", "known_by", "audience_known")
    ],
    ids=["entity-" + n for n in ("id", "type", "name", "aliases", "audience_known", "properties")]
    + ["relation-" + n for n in ("id", "source", "target", "type", "known_by", "audience_known")],
)
def test_protocol_members_are_readonly_properties(owner: type, member: str) -> None:
    """U9c 协议成员一律只读 property（变异测试 §9 补充，12 例参数化）。

    前置: 无；动作: 反射检查协议类成员；预期: 均为 property 实例。
    设计依据: §9 变异测试补充—service._EntityLike/_RelationLike docstring 契约
        （只读 property 保协变；可变属性是不变的，Literal 类型将无法匹配 str）。
    """
    assert isinstance(getattr(owner, member), property), (
        f"【问题】协议成员 {owner.__name__}.{member} 不是 property\n"
        "【原因】成员漂移为可写属性（类型协变契约破坏，mypy 将误放行）\n"
        "【修复】检查协议类成员保持 @property 只读声明"
    )


def test_get_graph_is_checkpoint_decorated() -> None:
    """U9d get_graph 保留 __wrapped__（checkpoint 装饰在位，变异测试 §9 补充）。

    前置: 无；动作: 反射检查 service.get_graph；预期: 有 __wrapped__
        （checkpoint 经 functools.wraps 包装，装饰被删则丢失）。
    设计依据: §9 变异测试补充—可观测性检查点契约（信号 2/3 采集依赖装饰在位）。
    """
    assert hasattr(service.get_graph, "__wrapped__"), (
        "【问题】get_graph 丢失 __wrapped__\n"
        "【原因】@checkpoint 装饰器被移除（信号 2/3 采集断链）\n"
        "【修复】检查 get_graph 保持 @checkpoint 装饰"
    )
