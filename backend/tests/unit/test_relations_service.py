"""F03 L1 单元测试：relations service 业务逻辑（依赖全部 mock，内存执行）。

mock 策略: 以内存字典替换 repository 数据访问、以桩函数替换 entities.service
批量读取——只验证 service 层的自环/端点/known_by/重复校验与装配逻辑，不触数据库。
"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.entities import service as entities_service
from app.relations import repository, service
from app.relations.models import Relationship
from app.relations.schemas import RelationCreate, RelationUpdate

pytestmark = pytest.mark.unit

# 内存实体表（id → type）：默认两个 character 供端点/known_by 校验使用
_ENTITIES: dict[str, str] = {"char-a": "character", "char-b": "character"}


class SessionStub:
    """最小会话桩：仅支持 commit/rollback 空操作（单元层不触数据库）。"""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Relationship]:
    """内存关系存储 + repository/entities.service 全量 mock。

    作用:
        用字典模拟关系表（add/get_by_id/save/delete/find_same/query），
        entities 批量读取按 _ENTITIES 桩返回，实现 service 层完全隔离。
    参数: monkeypatch — pytest 替换器。
    返回值: dict[str, Relationship]（id → 关系）。
    异常: 无。
    依赖: app.relations.repository、app.entities.service。
    """
    relations: dict[str, Relationship] = {}

    async def fake_add(_session: Any, relation: Relationship) -> Relationship:
        relations[relation.id] = relation
        return relation

    async def fake_get_by_id(_session: Any, relation_id: str) -> Relationship | None:
        return relations.get(relation_id)

    async def fake_save(_session: Any, relation: Relationship) -> Relationship:
        relations[relation.id] = relation
        return relation

    async def fake_delete(_session: Any, relation: Relationship) -> None:
        relations.pop(relation.id, None)

    async def fake_find_same(
        _session: Any, source: str, target: str, rel_type: str
    ) -> Relationship | None:
        for relation in relations.values():
            if (relation.source, relation.target, relation.type) == (source, target, rel_type):
                return relation
        return None

    async def fake_query(
        _session: Any,
        *,
        source: str | None = None,
        target: str | None = None,
        rel_type: str | None = None,
    ) -> list[Relationship]:
        rows = list(relations.values())
        if source is not None:
            rows = [r for r in rows if r.source == source]
        if target is not None:
            rows = [r for r in rows if r.target == target]
        if rel_type is not None:
            rows = [r for r in rows if r.type == rel_type]
        return sorted(rows, key=lambda r: r.id)

    async def fake_get_many(_session: Any, entity_ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(id=eid, type=_ENTITIES[eid]) for eid in entity_ids if eid in _ENTITIES
        ]

    monkeypatch.setattr(repository, "add", fake_add)
    monkeypatch.setattr(repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(repository, "save", fake_save)
    monkeypatch.setattr(repository, "delete", fake_delete)
    monkeypatch.setattr(repository, "find_same", fake_find_same)
    monkeypatch.setattr(repository, "query", fake_query)
    monkeypatch.setattr(entities_service, "get_many", fake_get_many)
    return relations


_SESSION = SessionStub()


async def test_create_generates_prefixed_id(store: dict[str, Relationship]) -> None:
    """U1 创建成功：id 系统生成（rel- 前缀）、动态字段与 known_by 完整装配。

    前置: 端点 char-a/char-b 与 known_by 成员均在 _ENTITIES；动作: create；
        预期: id 以 rel- 开头，动态属性/时间戳完整。
    """
    created = await service.create(
        _SESSION,
        RelationCreate(
            source="char-a",
            target="char-b",
            type="mentor",
            trust=0.8,
            promise="护她周全",
            known_by=["char-a"],
            audience_known=True,
        ),
    )
    assert created.id.startswith("rel-"), (
        f"【问题】生成的 id 未带 rel- 前缀: {created.id}\n"
        "【原因】id 生成未按前缀规则装配\n"
        "【修复】检查 schemas.generate_relation_id"
    )
    assert created.source == "char-a" and created.target == "char-b" and created.type == "mentor"
    assert created.trust == 0.8
    assert created.promise == "护她周全"
    assert created.known_by == ["char-a"]
    assert created.audience_known is True
    assert created.created_at and created.updated_at
    assert created.id in store


async def test_create_rejects_self_loop(store: dict[str, Relationship]) -> None:
    """U2 自环拒绝：source == target 抛 ValidationError（三要素）。

    前置: 端点存在于 _ENTITIES；动作: create(source=target=char-a)；预期: ValidationError。
    """
    with pytest.raises(ValidationError) as exc_info:
        await service.create(
            _SESSION, RelationCreate(source="char-a", target="char-a", type="mentor")
        )
    assert exc_info.value.detail["rule"] == "no_self_loop", (
        f"【问题】自环校验错误未携带规则标识: {exc_info.value.detail}\n"
        "【原因】ValidationError 构造时未填充 rule 字段\n"
        "【修复】检查 service._self_loop 的 detail 构造"
    )
    assert not store, "自环关系不得进入存储"


async def test_create_rejects_missing_endpoint(store: dict[str, Relationship]) -> None:
    """U3 端点缺失：抛 NotFoundError 且 detail 定位缺失端点字段。

    前置: char-b 不在 _ENTITIES（target 缺失）/ char-a 不在（source 缺失）；
        动作: create；预期: NotFoundError 且 detail.field 指向缺失端点。
    """
    _ENTITIES.pop("char-b")
    try:
        with pytest.raises(NotFoundError) as target_info:
            await service.create(
                _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
            )
        assert target_info.value.detail["field"] == "target", (
            f"【问题】端点校验错误未定位字段: {target_info.value.detail}\n"
            "【原因】_endpoint_missing 构造时 field 传错\n"
            "【修复】检查 create 中端点遍历的 (field, endpoint) 对"
        )
    finally:
        _ENTITIES["char-b"] = "character"

    _ENTITIES.pop("char-a")
    try:
        with pytest.raises(NotFoundError) as source_info:
            await service.create(
                _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
            )
        assert source_info.value.detail["field"] == "source"
    finally:
        _ENTITIES["char-a"] = "character"


async def test_create_rejects_duplicate(store: dict[str, Relationship]) -> None:
    """U4 重复关系拒绝：同 source+target+type 抛 ConflictError 且含 existing_id。

    前置: 已创建 a→b mentor；动作: 再次 create 同三元组；预期: ConflictError。
    """
    first = await service.create(
        _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
    )
    with pytest.raises(ConflictError) as exc_info:
        await service.create(
            _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
        )
    assert exc_info.value.detail["existing_id"] == first.id, (
        f"【问题】重复关系错误未指向既有关系: {exc_info.value.detail}\n"
        "【原因】ConflictError 构造时未携带 existing_id\n"
        "【修复】检查 service._duplicate 的 detail 构造"
    )

    # 反向组合（b→a 同 type）是有向语义下的新关系，应创建成功
    reverse = await service.create(
        _SESSION, RelationCreate(source="char-b", target="char-a", type="mentor")
    )
    assert reverse.id != first.id and len(store) == 2


async def test_create_rejects_missing_known_by_member(
    store: dict[str, Relationship],
) -> None:
    """U5 known_by 成员缺失：抛 ValidationError 且 detail 定位缺失成员。

    前置: known_by 含库中不存在的 id；动作: create；预期: ValidationError。
    """
    with pytest.raises(ValidationError) as exc_info:
        await service.create(
            _SESSION,
            RelationCreate(
                source="char-a", target="char-b", type="mentor", known_by=["char-ghost"]
            ),
        )
    assert exc_info.value.detail["member"] == "char-ghost", (
        f"【问题】known_by 校验错误未定位成员: {exc_info.value.detail}\n"
        "【原因】ValidationError 构造时未携带 member 字段\n"
        "【修复】检查 service._known_by_invalid 的 detail 构造"
    )


async def test_create_rejects_non_character_known_by_member(
    store: dict[str, Relationship],
) -> None:
    """U6 known_by 成员非 character：抛 ValidationError（reason=not_character）。

    前置: known_by 成员是 location 实体；动作: create；预期: ValidationError。
    """
    _ENTITIES["loc-x"] = "location"
    try:
        with pytest.raises(ValidationError) as exc_info:
            await service.create(
                _SESSION,
                RelationCreate(source="char-a", target="char-b", type="mentor", known_by=["loc-x"]),
            )
        assert exc_info.value.detail["reason"] == "not_character", (
            f"【问题】非 character 成员未被标注原因: {exc_info.value.detail}\n"
            "【原因】_known_by_invalid 的 reason 分支缺失\n"
            "【修复】检查成员类型比对逻辑"
        )
    finally:
        del _ENTITIES["loc-x"]


async def test_get_missing_relation_raises_not_found(
    store: dict[str, Relationship],
) -> None:
    """U7 读取不存在关系抛 NotFoundError（三要素完整）。

    前置: 空 store；动作: get('rel-x')；预期: NotFoundError。
    """
    with pytest.raises(NotFoundError) as exc_info:
        await service.get(_SESSION, "rel-x")
    assert exc_info.value.fix, "错误消息缺少 fix 要素（三要素规范）"


async def test_update_changes_dynamic_fields_only(
    store: dict[str, Relationship],
) -> None:
    """U8 局部更新：动态字段更新、端点与 id 不变、known_by 经重校验。

    前置: 已有关系（trust=0.8）；动作: update(trust=0.1, known_by=[char-a])；
        预期: 仅动态字段变化，known_by 装配新列表。
    """
    created = await service.create(
        _SESSION,
        RelationCreate(source="char-a", target="char-b", type="mentor", trust=0.8),
    )
    updated = await service.update(
        _SESSION,
        created.id,
        RelationUpdate(trust=0.1, status="决裂", known_by=["char-a"]),
    )
    assert updated.id == created.id, (
        f"【问题】更新后 id 改变: {created.id} -> {updated.id}\n"
        "【原因】update 逻辑重建了关系而非局部修改\n"
        "【修复】检查 service.update 只更新动态字段、不触碰 id"
    )
    assert updated.source == created.source and updated.target == created.target
    assert updated.type == created.type
    assert updated.trust == 0.1
    assert updated.status == "决裂"
    assert updated.known_by == ["char-a"]


async def test_update_rejects_immutable_fields_in_payload() -> None:
    """U9 端点不可变：请求体携带 id/source/target/type 均被请求模型拒绝。

    前置: 无；动作: 构造 RelationUpdate(各不可变字段)；预期: pydantic ValidationError。
    """
    import pydantic

    for field, value in (
        ("id", "rel-hacked"),
        ("source", "char-x"),
        ("target", "char-y"),
        ("type", "enemy"),
    ):
        with pytest.raises(pydantic.ValidationError) as exc_info:
            RelationUpdate(**{field: value})  # type: ignore[arg-type]
        assert any(field in str(err) for err in exc_info.value.errors()), (
            f"【问题】RelationUpdate 未拒绝 {field} 字段\n"
            "【原因】extra 策略未设置为 forbid，客户端可注入不可变字段\n"
            "【修复】RelationUpdate model_config 设置 extra='forbid'"
        )


async def test_delete_existing_and_missing(store: dict[str, Relationship]) -> None:
    """U10 删除：存在即从存储移除；不存在抛 NotFoundError。

    前置: 已有关系；动作: delete 后再 delete 同 id；预期: 第一次移除，第二次 NotFoundError。
    """
    created = await service.create(
        _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
    )
    await service.delete(_SESSION, created.id)
    assert created.id not in store

    with pytest.raises(NotFoundError):
        await service.delete(_SESSION, created.id)


async def test_get_all_passes_filters_and_returns_reads(
    store: dict[str, Relationship],
) -> None:
    """U11 条件查询：过滤参数原样透传 repository，结果装配 RelationRead。

    前置: 两条不同类型关系；动作: get_all(source=, rel_type=)；预期: 过滤生效
        且返回元素为 RelationRead（可访问响应字段）。
    """
    first = await service.create(
        _SESSION, RelationCreate(source="char-a", target="char-b", type="mentor")
    )
    second = await service.create(
        _SESSION, RelationCreate(source="char-a", target="char-b", type="rival")
    )

    by_type = await service.get_all(_SESSION, rel_type="mentor")
    assert [r.id for r in by_type] == [first.id], "类型过滤应只命中 mentor 关系"

    by_source = await service.get_all(_SESSION, source="char-a", target="char-b")
    assert {r.id for r in by_source} == {first.id, second.id}
    assert all(isinstance(r.id, str) and r.type for r in by_source), (
        "【问题】查询结果未装配为 RelationRead\n"
        "【原因】get_all 直接返回了 ORM 对象\n"
        "【修复】检查 service.get_all 的 model_validate 装配"
    )
