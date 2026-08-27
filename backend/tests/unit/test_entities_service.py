"""F02 L1 单元测试：entities service 业务逻辑（依赖全部 mock，内存执行）。

mock 策略: 以内存字典替换 repository 数据访问、以桩函数替换 relations.service
引用计数、以最小会话桩承载 commit 空操作——只验证 service 层的校验/装配/异常
逻辑，不触数据库。
"""

from typing import Any

import pytest

from app.core.exceptions import (
    NotFoundError,
    ReferentialError,
    ValidationError,
)
from app.entities import repository, service
from app.entities.models import Entity
from app.entities.schemas import EntityCreate, EntityUpdate
from app.relations import service as relations_service

pytestmark = pytest.mark.unit

# relations 引用计数桩的当前返回值（默认 0 = 无引用）
_ref_count_stub = {"value": 0}


class SessionStub:
    """最小会话桩：仅支持 commit/rollback 空操作（单元层不触数据库）。"""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Entity]:
    """内存实体存储 + repository/relations 全量 mock。

    作用:
        用字典模拟数据库行（add/get_by_id/save/delete/search），
        并将 relations 引用计数桩注入，实现 service 层完全隔离。
    参数: monkeypatch — pytest 替换器。
    返回值: dict[str, Entity]（id → 实体）。
    异常: 无。
    依赖: app.entities.repository、app.relations.service。
    """
    entities: dict[str, Entity] = {}

    async def fake_add(_session: Any, entity: Entity) -> Entity:
        entities[entity.id] = entity
        return entity

    async def fake_get_by_id(_session: Any, entity_id: str) -> Entity | None:
        return entities.get(entity_id)

    async def fake_save(_session: Any, entity: Entity) -> Entity:
        entities[entity.id] = entity
        return entity

    async def fake_delete(_session: Any, entity: Entity) -> None:
        entities.pop(entity.id, None)

    async def fake_search(
        _session: Any, q: str = "", entity_type: str | None = None
    ) -> list[Entity]:
        rows = list(entities.values())
        if entity_type is not None:
            rows = [e for e in rows if e.type == entity_type]
        if q:
            needle = q.lower()
            rows = [
                e
                for e in rows
                if needle in e.name.lower() or any(needle in a.lower() for a in e.aliases)
            ]
        return sorted(rows, key=lambda e: e.name)

    async def fake_count(_session: Any, _entity_id: str) -> int:
        return _ref_count_stub["value"]

    monkeypatch.setattr(repository, "add", fake_add)
    monkeypatch.setattr(repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(repository, "save", fake_save)
    monkeypatch.setattr(repository, "delete", fake_delete)
    monkeypatch.setattr(repository, "search", fake_search)
    monkeypatch.setattr(relations_service, "count_by_entity", fake_count)
    _ref_count_stub["value"] = 0
    return entities


_SESSION = SessionStub()


async def test_create_generates_prefixed_id(store: dict[str, Entity]) -> None:
    """U1 创建成功：id 系统生成（类型前缀）、字段完整回填。

    前置: 空 store；动作: create(character)；预期: id 以 char- 开头且字段一致。
    """
    created = await service.create(
        _SESSION,
        EntityCreate(
            type="character",
            name="周兰",
            aliases=["兰儿"],
            description="女主角",
            audience_known=True,
            properties={"age": 19, "gender": "女", "outer_desire": "自由"},
        ),
    )
    assert created.id.startswith("char-"), (
        f"【问题】生成的 id 未带类型前缀: {created.id}\n"
        "【原因】id 生成未按类型前缀规则装配\n"
        "【修复】检查 schemas.generate_entity_id 的前缀映射"
    )
    assert created.name == "周兰"
    assert created.audience_known is True
    assert created.properties["age"] == 19
    assert created.id in store


async def test_create_rejects_invalid_properties_type(
    store: dict[str, Entity],
) -> None:
    """U2 创建校验：properties 已声明字段类型不符抛 ValidationError（三要素）。

    前置: 空 store；动作: create(gender=数字)；预期: ValidationError 且 detail 含字段名。
    """
    with pytest.raises(ValidationError) as exc_info:
        await service.create(
            _SESSION,
            EntityCreate(
                type="character",
                name="测试角色",
                properties={"gender": 19},  # gender 声明为 string，数字非法
            ),
        )
    assert exc_info.value.detail["field"] == "gender", (
        f"【问题】校验错误未定位到具体字段: {exc_info.value.detail}\n"
        "【原因】ValidationError 构造时未携带字段级 detail\n"
        "【修复】检查 schemas.validate_properties 的异常构造"
    )


async def test_create_keeps_unknown_properties_field(
    store: dict[str, Entity],
) -> None:
    """U3 读宽容：未声明字段保留（schema 演进后旧数据可写回）。

    前置: 空 store；动作: create(带未声明字段 legacy_field)；预期: 字段原样保留。
    """
    created = await service.create(
        _SESSION,
        EntityCreate(
            type="concept",
            name="灵石",
            properties={"concept_type": "flora", "legacy_field": "旧版本字段"},
        ),
    )
    assert created.properties["legacy_field"] == "旧版本字段", (
        "【问题】未声明字段在写入时被丢弃\n"
        "【原因】校验逻辑误删了 schema 未声明的字段（违反读宽容约束）\n"
        "【修复】检查 validate_properties 不得修改/裁剪 properties 字典"
    )


async def test_get_missing_entity_raises_not_found(
    store: dict[str, Entity],
) -> None:
    """U4 读取不存在实体抛 NotFoundError（三要素完整）。

    前置: 空 store；动作: get('char-x')；预期: NotFoundError。
    """
    with pytest.raises(NotFoundError) as exc_info:
        await service.get(_SESSION, "char-x")
    assert exc_info.value.fix, "错误消息缺少 fix 要素（三要素规范）"


async def test_update_changes_name_not_id(store: dict[str, Entity]) -> None:
    """U5 局部更新：name 变更不影响 id；仅更新显式提供的字段。

    前置: store 有一个 character；动作: update(name)；预期: name 更新、id 不变。
    """
    created = await service.create(_SESSION, EntityCreate(type="character", name="周兰"))
    updated = await service.update(_SESSION, created.id, EntityUpdate(name="周兰（成年）"))
    assert updated.id == created.id, (
        f"【问题】name 变更后 id 改变: {created.id} -> {updated.id}\n"
        "【原因】update 逻辑重建了实体而非局部修改\n"
        "【修复】检查 service.update 只更新显式字段、不触碰 id"
    )
    assert updated.name == "周兰（成年）"


async def test_update_rejects_id_field_in_payload() -> None:
    """U6 id 不可变：请求体携带 id 字段直接被请求模型拒绝。

    前置: 无；动作: 构造 EntityUpdate(id=...)；预期: pydantic ValidationError。
    """
    import pydantic

    with pytest.raises(pydantic.ValidationError) as exc_info:
        EntityUpdate(id="char-hacked")  # type: ignore[call-arg]
    assert any("id" in str(err) for err in exc_info.value.errors()), (
        "【问题】EntityUpdate 未拒绝 id 字段\n"
        "【原因】extra 策略未设置为 forbid，客户端可注入 id\n"
        "【修复】EntityUpdate model_config 设置 extra='forbid'"
    )


async def test_update_merges_properties(store: dict[str, Entity]) -> None:
    """U7 properties 合并语义：局部字段更新保留其余字段。

    前置: 已有实体含 {age: 19, gender: 女}；动作: update(properties={age: 20})；
        预期: age=20 且 gender 保留。
    """
    created = await service.create(
        _SESSION,
        EntityCreate(type="character", name="周兰", properties={"age": 19, "gender": "女"}),
    )
    updated = await service.update(_SESSION, created.id, EntityUpdate(properties={"age": 20}))
    assert updated.properties == {"age": 20, "gender": "女"}, (
        f"【问题】properties 更新未保留未提及字段: {updated.properties}\n"
        "【原因】update 使用整体替换而非合并语义\n"
        "【修复】service.update 中先合并旧 properties 再校验写回"
    )


async def test_delete_blocked_by_reference(store: dict[str, Entity]) -> None:
    """U8 删除校验：被关系引用时抛 ReferentialError（应用层防线）。

    前置: 实体存在且引用计数=2；动作: delete；预期: ReferentialError，实体仍在。
    """
    created = await service.create(_SESSION, EntityCreate(type="character", name="周兰"))
    _ref_count_stub["value"] = 2
    with pytest.raises(ReferentialError) as exc_info:
        await service.delete(_SESSION, created.id)
    assert exc_info.value.detail["reference_count"] == 2
    assert created.id in store, "引用阻断后实体不应被删除"


async def test_delete_without_reference_succeeds(store: dict[str, Entity]) -> None:
    """U9 删除成功：无引用时实体被物理删除。

    前置: 实体存在且引用计数=0；动作: delete；预期: 实体从 store 移除。
    """
    created = await service.create(_SESSION, EntityCreate(type="item", name="青铜镜"))
    await service.delete(_SESSION, created.id)
    assert created.id not in store


async def test_search_matches_name_and_alias(store: dict[str, Entity]) -> None:
    """U10 检索：名称与别名均可命中，type 过滤生效。

    前置: 两个实体（名称命中/别名命中）；动作: search(q)、search(q, type)；
        预期: 均命中；类型过滤排除不匹配项。
    """
    await service.create(_SESSION, EntityCreate(type="character", name="周兰", aliases=["兰儿"]))
    await service.create(_SESSION, EntityCreate(type="location", name="青云山"))
    by_name = await service.search(_SESSION, q="周")
    by_alias = await service.search(_SESSION, q="兰儿")
    assert len(by_name) == 1 and by_name[0].name == "周兰"
    assert len(by_alias) == 1 and by_alias[0].name == "周兰"
    typed = await service.search(_SESSION, q="", entity_type="location")
    assert all(b.type == "location" for b in typed) and len(typed) == 1
