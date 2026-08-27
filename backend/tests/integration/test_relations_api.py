"""F03 L2 集成测试：relations API 全链路（router→service→repository→真实 SQLite 临时库）。

验证依据: docs/features.md F03 + docs/architecture_checks.md §2 —
    - CRUD 全链路与条件查询（公开 HTTP 接口）
    - 端点存在性校验（经 entities.service，缺失 404 定位字段）
    - 自环拒绝（422）/ 重复关系拒绝（409，有向三元组）
    - known_by 成员校验（存在且为 character，写入即校验）
    - 错误响应统一三要素结构（code/problem/cause/fix/detail）
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_entity(client: TestClient, name: str, **extra: Any) -> str:
    """经公开接口创建实体并返回系统生成的 id。

    作用: 集成用例的通用前置装配（实体存在是关系创建的前提）。
    参数: client — 测试客户端；name — 实体名；extra — 覆盖/追加的载荷字段。
    返回值: str — 生成的实体 id。
    异常: AssertionError — 创建未按预期返回 201 或 id 缺失（三要素消息）。
    依赖: fastapi.testclient.TestClient。
    """
    payload: dict[str, Any] = {"type": "character", "name": name}
    payload.update(extra)
    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == 201, (
        f"【问题】实体 {name} 创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/entities 未按预期创建资源\n"
        "【修复】检查请求载荷与 entities 路由/service 实现"
    )
    entity_id = resp.json().get("id")
    assert entity_id, "创建响应缺少系统生成的 id"
    return entity_id


def _create_relation(
    client: TestClient, source: str, target: str, rel_type: str = "mentor", **extra: Any
) -> dict[str, Any]:
    """经公开接口创建关系并返回响应体。

    作用: 集成用例的通用前置装配（创建成功是后续操作的前提）。
    参数: client — 测试客户端；source/target — 端点实体 id；rel_type — 关系类型；
        extra — 覆盖/追加的载荷字段。
    返回值: dict — 创建响应 JSON（含系统生成的 id）。
    异常: AssertionError — 创建未按预期返回 201（三要素消息）。
    依赖: fastapi.testclient.TestClient。
    """
    payload: dict[str, Any] = {"source": source, "target": target, "type": rel_type}
    payload.update(extra)
    resp = client.post("/api/relations", json=payload)
    assert resp.status_code == 201, (
        f"【问题】关系创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/relations 未按预期创建资源（或前置校验误拦截）\n"
        "【修复】检查请求载荷与 relations 路由/service 实现"
    )
    return resp.json()


def _assert_error_shape(body: dict[str, Any], expected_code: str) -> None:
    """断言错误响应体满足统一三要素结构。

    作用: 集中校验 code/problem/cause/fix 字段（docs/architecture_checks.md）。
    参数: body — 响应 JSON；expected_code — 期望的错误码。
    返回值: 无。异常: AssertionError — 结构缺失或码不符（三要素消息）。
    依赖: 无。
    """
    assert body.get("code") == expected_code, (
        f"【问题】错误响应结构不符: got code={body.get('code')!r}, 期望 {expected_code!r}\n"
        "【原因】响应体不是统一三要素结构或错误码映射错误\n"
        "【修复】检查 core/observability 异常处理器与 responses.error_response"
    )
    for key in ("problem", "cause", "fix"):
        assert isinstance(body.get(key), str) and body[key], (
            f"【问题】错误响应缺少三要素字段 '{key}': {body}\n"
            "【原因】错误构造时 problem/cause/fix 存在空缺\n"
            "【修复】检查异常构造处三要素填写是否完整"
        )


def test_create_and_read_back_full_chain(client: TestClient) -> None:
    """I1 创建→详情全链路：201 返回系统生成 id，动态字段完整，回读一致。

    前置: 两实体；动作: POST 后 GET 详情；预期: id 带 rel- 前缀、字段一致。
    """
    zhou = _create_entity(client, "周兰")
    li = _create_entity(client, "李乾")

    created = _create_relation(
        client,
        zhou,
        li,
        rel_type="mentor",
        trust=0.8,
        intimacy=0.3,
        public_identity="师徒",
        promise="护她周全",
        known_by=[zhou],
        audience_known=True,
        properties={"dynamic_type": "互补型"},
    )
    assert created["id"].startswith("rel-"), (
        f"【问题】生成的 id 未带 rel- 前缀: {created['id']}\n"
        "【原因】id 生成规则未装配前缀\n"
        "【修复】检查 schemas.generate_relation_id"
    )
    assert created["source"] == zhou and created["target"] == li and created["type"] == "mentor"
    assert created["trust"] == 0.8
    assert created["known_by"] == [zhou]
    assert created["audience_known"] is True
    assert created["properties"] == {"dynamic_type": "互补型"}
    assert created["created_at"] and created["updated_at"], "时间戳应完整序列化"

    read_back = client.get(f"/api/relations/{created['id']}").json()
    assert read_back == created, (
        f"【问题】创建后回读不一致:\n created={created}\n read_back={read_back}\n"
        "【原因】落库序列化或响应装配存在字段偏差\n"
        "【修复】对比 repository 写入与 RelationRead 反序列化的字段列表"
    )


def test_create_rejects_missing_endpoint_unified_404(client: TestClient) -> None:
    """I2 端点缺失：source/target 两例均 404 统一结构，库中无残留关系。

    前置: 仅一个实体；动作: POST 缺 source / 缺 target；预期: 404 NOT_FOUND +
        detail.field 定位缺失端点，且不产生残留数据。
    """
    only = _create_entity(client, "周兰")

    for field, payload in (
        ("source", {"source": "char-ghost", "target": only, "type": "mentor"}),
        ("target", {"source": only, "target": "char-ghost", "type": "mentor"}),
    ):
        resp = client.post("/api/relations", json=payload)
        assert resp.status_code == 404, f"端点缺失应 404: {resp.status_code} {resp.text}"
        body = resp.json()
        _assert_error_shape(body, "NOT_FOUND")
        assert body["detail"]["field"] == field, (
            f"【问题】端点错误未定位字段: {body['detail']}\n"
            "【原因】_endpoint_missing 的 field 传错\n"
            "【修复】检查 service.create 端点遍历顺序"
        )

    leftovers = client.get("/api/relations").json()
    assert leftovers == [], "校验失败的关系创建不应在库中留下任何数据"


def test_create_rejects_self_loop_unified_422(client: TestClient) -> None:
    """I3 自环拒绝：source == target 返回 422 统一三要素结构。

    前置: 一个实体；动作: POST source==target；预期: 422 VALIDATION_ERROR。
    """
    only = _create_entity(client, "周兰")
    resp = client.post("/api/relations", json={"source": only, "target": only, "type": "mentor"})
    assert resp.status_code == 422, f"自环关系必须 422: {resp.status_code} {resp.text}"
    body = resp.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert body["detail"]["rule"] == "no_self_loop"
    assert client.get("/api/relations").json() == [], "自环创建不得留下数据"


def test_create_rejects_duplicate_but_allows_reverse(client: TestClient) -> None:
    """I4 重复关系：同 source+target+type 二次创建 409 CONFLICT；反向组合 201。

    前置: 两实体 + 已有关系 a→b mentor；动作: 同三元组再 POST；预期: 409 +
        detail.existing_id；动作: b→a 同 type POST；预期: 201（有向语义）。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    first = _create_relation(client, a, b, rel_type="mentor")

    resp = client.post("/api/relations", json={"source": a, "target": b, "type": "mentor"})
    assert resp.status_code == 409, f"重复关系必须 409: {resp.status_code} {resp.text}"
    body = resp.json()
    _assert_error_shape(body, "CONFLICT")
    assert body["detail"]["existing_id"] == first["id"], (
        f"【问题】重复错误未指向既有关系: {body['detail']}\n"
        "【原因】ConflictError 构造时未携带 existing_id\n"
        "【修复】检查 service._duplicate 的 detail 构造"
    )

    reverse = _create_relation(client, b, a, rel_type="mentor")
    assert reverse["id"] != first["id"], "反向关系是独立资源，不得复用 id"


def test_create_rejects_invalid_known_by_members(client: TestClient) -> None:
    """I5 known_by 校验：缺失成员与非 character 成员两例均 422 且定位成员。

    前置: 两 character + 一 location；动作: POST known_by=[缺失 id] / [location id]；
        预期: 422 VALIDATION_ERROR，detail.member 与 reason 正确。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    mountain = _create_entity(client, "青云山", type="location")

    missing = client.post(
        "/api/relations",
        json={"source": a, "target": b, "type": "mentor", "known_by": ["char-ghost"]},
    )
    assert missing.status_code == 422, f"缺失成员必须 422: {missing.status_code} {missing.text}"
    body = missing.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert body["detail"]["member"] == "char-ghost"
    assert body["detail"]["reason"] == "missing"

    not_character = client.post(
        "/api/relations",
        json={"source": a, "target": b, "type": "mentor", "known_by": [mountain]},
    )
    assert not_character.status_code == 422
    body = not_character.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert body["detail"]["member"] == mountain
    assert body["detail"]["reason"] == "not_character"
    assert client.get("/api/relations").json() == [], "校验失败不得留下数据"


def test_conditional_query_filters(client: TestClient) -> None:
    """I6 条件查询：source/target/type 过滤各自生效且互不误报。

    前置: 三实体，关系 a→b mentor、a→b rival、b→c mentor；动作: 三组 GET 过滤；
        预期: source=a 命中 2 条；target=b 命中 2 条；type=rival 仅命中 1 条。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    c = _create_entity(client, "孙芊")

    r_mentor = _create_relation(client, a, b, rel_type="mentor")
    r_rival = _create_relation(client, a, b, rel_type="rival")
    _create_relation(client, b, c, rel_type="mentor")

    by_source = {r["id"] for r in client.get("/api/relations", params={"source": a}).json()}
    assert by_source == {r_mentor["id"], r_rival["id"]}, f"source 过滤误报: {by_source}"

    by_target = {r["id"] for r in client.get("/api/relations", params={"target": b}).json()}
    assert by_target == {r_mentor["id"], r_rival["id"]}, f"target 过滤误报: {by_target}"

    by_type = [r["id"] for r in client.get("/api/relations", params={"type": "rival"}).json()]
    assert by_type == [r_rival["id"]], f"type 过滤误报: {by_type}"

    everything = client.get("/api/relations").json()
    assert len(everything) == 3, "无参查询应返回全量"


def test_patch_updates_dynamic_fields_and_blocks_immutable(client: TestClient) -> None:
    """I7 PATCH 动态字段：更新生效且端点/id 不变；type 不可变被 422 拒绝。

    前置: 已有关系 trust=0.8；动作: PATCH(trust=0.1, promise) 后 PATCH(type)；
        预期: 前者 200 且仅动态字段变化；后者 422 且数据未动。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    created = _create_relation(client, a, b, rel_type="mentor", trust=0.8)

    resp = client.patch(
        f"/api/relations/{created['id']}",
        json={"trust": 0.1, "promise": "护她周全", "known_by": [a]},
    )
    assert resp.status_code == 200, f"PATCH 应成功: {resp.status_code} {resp.text}"
    updated = resp.json()
    assert updated["id"] == created["id"], "PATCH 不允许改变关系 id"
    assert updated["source"] == a and updated["target"] == b and updated["type"] == "mentor"
    assert updated["trust"] == 0.1
    assert updated["promise"] == "护她周全"
    assert updated["known_by"] == [a]

    immutable = client.patch(f"/api/relations/{created['id']}", json={"type": "enemy"})
    assert immutable.status_code == 422, f"携带 type 的 PATCH 必须 422: {immutable.text}"
    body = immutable.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert any("type" in str(e.get("loc", "")) for e in body["detail"]["errors"]), (
        f"【问题】校验错误未定位到 type 字段: {body['detail']}\n"
        "【原因】RelationUpdate 未把 type 列为不可变字段\n"
        "【修复】确认 RelationUpdate 未声明 type 且 extra=forbid"
    )

    after = client.get(f"/api/relations/{created['id']}").json()
    assert after["type"] == "mentor" and after["trust"] == 0.1, "被拒绝的更新不得改动任何数据"


def test_patch_rejects_out_of_range_scale_unified_422(client: TestClient) -> None:
    """I8 数值越界：trust=1.5 被 422 拒绝且响应为统一三要素结构。

    前置: 已有关系；动作: PATCH(trust=1.5)；预期: 422 + VALIDATION_ERROR +
        detail.errors 定位 trust 字段（请求级校验经全局处理器转换）。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    created = _create_relation(client, a, b, rel_type="mentor", trust=0.5)

    resp = client.patch(f"/api/relations/{created['id']}", json={"trust": 1.5})
    assert resp.status_code == 422, f"0-1 标度越界必须 422: {resp.status_code} {resp.text}"
    body = resp.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert any("trust" in str(e.get("loc", "")) for e in body["detail"]["errors"]), (
        f"【问题】越界错误未定位到 trust 字段: {body['detail']}\n"
        "【原因】RelationUpdate 的 trust 字段缺少 ge/le 约束\n"
        "【修复】检查 schemas.RelationUpdate 的标度约束"
    )
    assert client.get(f"/api/relations/{created['id']}").json()["trust"] == 0.5


def test_get_patch_delete_missing_relation_unified_404(client: TestClient) -> None:
    """I9 不存在关系：GET/PATCH/DELETE 均返回 404 统一三要素结构。

    前置: 空关系表；动作: 三方法访问不存在 id；预期: 404 + NOT_FOUND + 三要素。
    """
    for resp in (
        client.get("/api/relations/rel-missing"),
        client.patch("/api/relations/rel-missing", json={"trust": 0.5}),
        client.delete("/api/relations/rel-missing"),
    ):
        assert resp.status_code == 404, f"期望 404 实得 {resp.status_code}: {resp.text}"
        _assert_error_shape(resp.json(), "NOT_FOUND")


def test_delete_relation_then_gone(client: TestClient) -> None:
    """I10 删除成功链路：无下游引用的 DELETE 204 后 GET 转 404。

    前置: 两实体 + 一关系；动作: DELETE → GET；预期: 204 无响应体，随后 404。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    created = _create_relation(client, a, b, rel_type="mentor")

    resp = client.delete(f"/api/relations/{created['id']}")
    assert resp.status_code == 204 and resp.content == b"", (
        f"【问题】删除响应应为无内容的 204: {resp.status_code} {resp.content!r}\n"
        "【原因】路由状态码或响应体声明不符契约\n"
        "【修复】检查 router.delete_relation 的 status_code 配置"
    )
    assert client.get(f"/api/relations/{created['id']}").status_code == 404
