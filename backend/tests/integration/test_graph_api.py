"""F04 L2 集成测试：graph API 全链路（router→service→entities/relations 聚合→真实 SQLite 临时库）。

验证依据: docs/features.md F04 + perspectives/CONSTRAINTS.md —
    - 三视角过滤（author 全量 / audience 双端可见 / character known 标记+端点推导）
    - character 视角缺参/角色不存在/类型不符 → 403 PerspectiveError（统一错误结构）
    - perspective 非法值 → 422 请求校验（detail.errors 定位 query 参数）
    - character 视角不泄露被过滤实体名（响应文本级断言）
种子世界与期望视图见 docs/tests/F04_graph_perspective_query.md。
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _seed_world(client: TestClient) -> dict[str, str]:
    """经公开接口搭建测试世界（6 实体 / 3 关系），返回语义 id 映射。

    作用: I 系列用例的通用前置装配（数据与测试文档「测试世界」一致）；
        先建角色再建带 marker 的实体（marker 须引用系统生成的真实 id）。
    参数: client — 测试客户端。
    返回值: dict[str, str]（语义键 → 系统 id，如 "char-a"）。
    异常: AssertionError — 任一创建未按预期返回 201（三要素消息）。
    依赖: 公开 API /api/entities、/api/relations。
    """

    def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = client.post(path, json=payload)
        assert resp.status_code == 201, (
            f"【问题】{path} 创建失败: HTTP {resp.status_code} {resp.text}\n"
            "【原因】公开接口未按预期创建资源（或前置校验误拦截）\n"
            "【修复】检查请求载荷与对应路由/service 实现"
        )
        return resp.json()

    ids: dict[str, str] = {}
    ids["char-a"] = _post(
        "/api/entities", {"type": "character", "name": "周兰", "audience_known": True}
    )["id"]
    ids["char-b"] = _post("/api/entities", {"type": "character", "name": "沈墨"})["id"]
    ids["char-c"] = _post(
        "/api/entities", {"type": "character", "name": "陆离", "audience_known": True}
    )["id"]
    ids["item-x"] = _post(
        "/api/entities",
        {"type": "item", "name": "青铜镜", "properties": {"seen_by": [ids["char-a"]]}},
    )["id"]
    ids["event-e"] = _post(
        "/api/entities",
        {
            "type": "event",
            "name": "夜探药庐",
            "audience_known": True,
            "properties": {"known_by": [ids["char-b"]]},
        },
    )["id"]
    ids["loc-l"] = _post(
        "/api/entities", {"type": "location", "name": "青云山", "audience_known": True}
    )["id"]

    relations = [
        ("rel-1", "char-a", "char-b", ["char-a"]),
        ("rel-2", "char-a", "loc-l", ["char-a", "char-b"]),
        ("rel-3", "char-b", "event-e", ["char-b"]),
    ]
    for key, src, dst, known in relations:
        ids[key] = _post(
            "/api/relations",
            {
                "source": ids[src],
                "target": ids[dst],
                "type": key.upper(),
                "known_by": [ids[m] for m in known],
                "audience_known": True,
            },
        )["id"]
    return ids


def _node_ids(body: dict[str, Any]) -> set[str]:
    return {n["id"] for n in body["nodes"]}


def _edge_ids(body: dict[str, Any]) -> set[str]:
    return {e["id"] for e in body["edges"]}


def _assert_error_shape(body: dict[str, Any], expected_code: str) -> None:
    """断言错误响应体满足统一三要素结构（与 F03 集成测试同规格）。"""
    assert body.get("code") == expected_code, (
        f"【问题】错误响应结构不符: got code={body.get('code')!r}, 期望 {expected_code!r}\n"
        "【原因】响应体不是统一三要素结构或错误码映射错误\n"
        "【修复】检查 core/observability 异常处理器与 responses.error_response"
    )
    for key in ("problem", "cause", "fix"):
        assert isinstance(body.get(key), str) and body[key], (
            f"【问题】错误响应缺少三要素字段 '{key}': {body}\n"
            "【原因】错误构造时 problem/cause/fix 存在空缺\n"
            "【修复】检查对应异常构造的三要素完整性"
        )


def test_graph_author_returns_full_world(client: TestClient) -> None:
    """I1 author 200 全量：6 节点 3 边。

    前置: 种子世界；动作: GET /api/graph?perspective=author；预期: 200 全量。
    设计依据: 等价类—perspective 有效-author。
    """
    ids = _seed_world(client)
    resp = client.get("/api/graph", params={"perspective": "author"})
    assert resp.status_code == 200, f"author 查询失败: {resp.status_code} {resp.text}"
    body = resp.json()
    assert _node_ids(body) == {
        ids[k] for k in ("char-a", "char-b", "char-c", "item-x", "event-e", "loc-l")
    }, (
        f"【问题】author 节点集合不符: {_node_ids(body)}\n"
        "【原因】author 分支错误套用了过滤规则\n"
        "【修复】检查 service.get_graph author 分支应直通全量数据"
    )
    assert _edge_ids(body) == {ids["rel-1"], ids["rel-2"], ids["rel-3"]}, (
        f"【问题】author 边集合不符: {_edge_ids(body)}\n"
        "【原因】author 分支错误套用了过滤规则\n"
        "【修复】检查 service.get_graph author 分支应直通全量数据"
    )


def test_graph_audience_filters_with_both_endpoint_rule(client: TestClient) -> None:
    """I2 audience 200 过滤：4 节点、仅 rel-2（双端可见规则排除 rel-1/rel-3）。

    设计依据: 等价类—perspective 有效-audience；含边可见性双端规则。
    """
    ids = _seed_world(client)
    resp = client.get("/api/graph", params={"perspective": "audience"})
    assert resp.status_code == 200, f"audience 查询失败: {resp.status_code} {resp.text}"
    body = resp.json()
    assert _node_ids(body) == {ids[k] for k in ("char-a", "char-c", "event-e", "loc-l")}, (
        f"【问题】audience 节点集合不符: {_node_ids(body)}\n"
        "【原因】audience_known 过滤条件未正确生效\n"
        "【修复】检查 service.get_graph audience 分支的实体过滤"
    )
    assert _edge_ids(body) == {ids["rel-2"]}, (
        f"【问题】audience 边集合不符: {_edge_ids(body)}\n"
        "【原因】边过滤缺少双端可见校验\n"
        "【修复】检查 audience 分支应同时校验 source/target 均在可见节点集内"
    )


@pytest.mark.parametrize(
    ("char_key", "node_keys", "edge_keys"),
    [
        ("char-a", {"char-a", "char-b", "item-x", "loc-l"}, {"rel-1", "rel-2"}),
        ("char-b", {"char-b", "char-a", "event-e", "loc-l"}, {"rel-2", "rel-3"}),
        ("char-c", {"char-c"}, set()),
    ],
    ids=["char-a-edges+item-marker", "char-b-edges+event-marker", "char-c-isolated"],
)
def test_graph_character_three_states(
    client: TestClient, char_key: str, node_keys: set[str], edge_keys: set[str]
) -> None:
    """I3 character 三态参数化：边+标记 / 边+事件标记 / 孤立仅自身。

    设计依据: 等价类—perspective 有效-character 三态。
    """
    ids = _seed_world(client)
    resp = client.get(
        "/api/graph", params={"perspective": "character", "character_id": ids[char_key]}
    )
    assert resp.status_code == 200, f"character 查询失败: {resp.status_code} {resp.text}"
    body = resp.json()
    assert _node_ids(body) == {ids[k] for k in node_keys}, (
        f"【问题】{char_key} 视角节点集合不符: {_node_ids(body)}\n"
        "【原因】known 标记命中或可见关系端点推导规则未正确生效\n"
        "【修复】检查 character 分支的 visible 集合装配"
    )
    assert _edge_ids(body) == {ids[k] for k in edge_keys}, (
        f"【问题】{char_key} 视角边集合不符: {_edge_ids(body)}\n"
        "【原因】关系 known_by 过滤条件未正确生效\n"
        "【修复】检查 character 分支应仅保留 known_by 含视角角色的关系"
    )


def test_graph_character_missing_id_returns_403(client: TestClient) -> None:
    """I4 character 缺 character_id → 403 PERSPECTIVE_DENIED（统一错误结构）。

    设计依据: 无效等价类—必选参数缺失；断言三要素结构。
    """
    _seed_world(client)
    resp = client.get("/api/graph", params={"perspective": "character"})
    assert resp.status_code == 403, (
        f"【问题】缺 character_id 应 403，实际 {resp.status_code}: {resp.text}\n"
        "【原因】PerspectiveError 未被正确抛出或状态码映射错误\n"
        "【修复】检查 service 缺参分支与异常处理器"
    )
    _assert_error_shape(resp.json(), "PERSPECTIVE_DENIED")
    assert resp.json()["detail"]["reason"] == "missing_character_id"


@pytest.mark.parametrize(
    ("bad_key", "reason"),
    [("missing", "character_not_found"), ("loc-l", "not_character_type")],
    ids=["entity-missing", "not-character-type"],
)
def test_graph_character_invalid_id_returns_403(
    client: TestClient, bad_key: str, reason: str
) -> None:
    """I5 character_id 不存在 / 非 character 类型 → 403，detail.reason 对应。

    设计依据: 无效等价类—角色不存在 / 角色类型不符。
    """
    ids = _seed_world(client)
    character_id = "char-none" if bad_key == "missing" else ids[bad_key]
    resp = client.get(
        "/api/graph", params={"perspective": "character", "character_id": character_id}
    )
    assert resp.status_code == 403, (
        f"【问题】无效 character_id 应 403，实际 {resp.status_code}: {resp.text}\n"
        "【原因】存在性/类型校验未拦截或状态码映射错误\n"
        "【修复】检查 character 分支的角色校验顺序"
    )
    _assert_error_shape(resp.json(), "PERSPECTIVE_DENIED")
    assert resp.json()["detail"]["reason"] == reason, (
        f"【问题】detail.reason 不符: {resp.json()['detail']}\n"
        f"【原因】校验分支与预期 {reason} 不一致\n"
        "【修复】检查角色存在性与类型校验的 reason 装配"
    )


@pytest.mark.parametrize("bad_perspective", ["editor", ""], ids=["enum-out", "empty"])
def test_graph_invalid_perspective_returns_422(client: TestClient, bad_perspective: str) -> None:
    """I6 perspective 非法值参数化 → 422 请求校验，detail.errors 定位 query 参数。

    设计依据: 无效等价类—Literal 枚举外；边界值—空串。
    """
    resp = client.get("/api/graph", params={"perspective": bad_perspective})
    assert resp.status_code == 422, (
        f"【问题】非法 perspective 应 422，实际 {resp.status_code}: {resp.text}\n"
        "【原因】查询参数未按 Literal 枚举校验\n"
        "【修复】检查路由的 perspective 参数类型声明"
    )
    errors = resp.json()["detail"]["errors"]
    assert any("perspective" in str(e.get("loc", "")) for e in errors), (
        f"【问题】校验错误未定位到 perspective 参数: {errors}\n"
        "【原因】请求校验响应的 loc 装配不符\n"
        "【修复】检查 responses.request_validation_error_response"
    )


def test_graph_character_view_does_not_leak_filtered_names(client: TestClient) -> None:
    """I7 不泄露断言：character 视角响应文本不含被过滤实体名（perspectives/CONSTRAINTS）。

    设计依据: 硬约束—character 视角禁止泄露被过滤实体名（边数据中也不得出现）。
    """
    _seed_world(client)
    resp = client.get("/api/graph", params={"perspective": "author"})
    author = resp.json()
    char_a = next(n["id"] for n in author["nodes"] if n["name"] == "周兰")
    resp = client.get("/api/graph", params={"perspective": "character", "character_id": char_a})
    assert resp.status_code == 200
    for hidden in ("陆离", "夜探药庐"):
        assert hidden not in resp.text, (
            f"【问题】character 视角泄露了被过滤实体名: {hidden}\n"
            "【原因】节点/边投影携带了不可见实体的名称或标记\n"
            "【修复】检查 GraphNode/GraphEdge 投影字段与过滤集合的一致性"
        )


def test_graph_empty_store_returns_empty_graph(client: TestClient) -> None:
    """I8 空库 → 200 空图。

    设计依据: 边界值—数据集空集。
    """
    for perspective in ("author", "audience"):
        resp = client.get("/api/graph", params={"perspective": perspective})
        assert resp.status_code == 200, f"{perspective} 空库查询失败: {resp.text}"
        body = resp.json()
        assert body == {"nodes": [], "edges": []}, (
            f"【问题】{perspective} 空库返回非空图: {body}\n"
            "【原因】空数据集聚合路径未正确短路\n"
            "【修复】检查 get_graph 对空查询结果的处理"
        )
