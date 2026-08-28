"""F04 L3 端到端测试：三视角过滤图查询跨组件全链路（entities+relations+perspectives）。

验证依据: docs/features.md F04（跨组件=是，L3 必须）+ perspectives/CONSTRAINTS.md —
    - E1 公开 HTTP 全链路：建世界 → 三视角查询 → 过滤结果 + 不泄露断言
    - E2 只读单一事实源：三视角查询前后经公开接口导出的数据快照逐字节一致
种子世界与期望视图见 docs/tests/F04_graph_perspective_query.md。
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _seed_world(client: TestClient) -> dict[str, str]:
    """经公开接口搭建测试世界（与 L2 _seed_world 同构，e2e 自含装配）。"""

    def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = client.post(path, json=payload)
        assert resp.status_code == 201, (
            f"【问题】{path} 创建失败: HTTP {resp.status_code} {resp.text}\n"
            "【原因】公开接口未按预期创建资源\n"
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
    for key, src, dst, known in [
        ("rel-1", "char-a", "char-b", ["char-a"]),
        ("rel-2", "char-a", "loc-l", ["char-a", "char-b"]),
        ("rel-3", "char-b", "event-e", ["char-b"]),
    ]:
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


def _export_snapshot(client: TestClient) -> str:
    """经公开接口导出全量数据快照（实体详情 + 全部关系），规范化 JSON 串。

    作用: E2 只读性断言的比对载体——覆盖实体的动态字段（known 标记/
        audience_known）与关系的 known_by/动态属性，任何写入都会造成差异。
    参数: client — 测试客户端。
    返回值: str（json.dumps sort_keys 规范化文本）。
    异常: AssertionError — 任一导出请求非 200。
    依赖: 公开 API /api/entities、/api/relations。
    """
    briefs = client.get("/api/entities", params={"q": ""})
    assert briefs.status_code == 200, f"实体列表导出失败: {briefs.text}"
    details = []
    for brief in briefs.json():
        detail = client.get(f"/api/entities/{brief['id']}")
        assert detail.status_code == 200, f"实体详情导出失败: {detail.text}"
        details.append(detail.json())
    relations = client.get("/api/relations")
    assert relations.status_code == 200, f"关系导出失败: {relations.text}"
    return json.dumps(
        {"entities": details, "relations": relations.json()}, ensure_ascii=False, sort_keys=True
    )


def test_graph_three_perspectives_full_flow(client: TestClient, memory_guard: None) -> None:
    """E1 全链路：公开 HTTP 建世界 → 三视角查询 → 断言过滤结果与不泄露。

    前置: 空库；动作: 建种子世界后依次以 author/audience/character 查询；
        预期: 三组节点/边集合与测试文档期望视图一致，character 视角不泄露。
    设计依据: 跨组件全链路主路径（entities 写入 × relations 写入 × perspectives 聚合）。
    """
    ids = _seed_world(client)

    author = client.get("/api/graph", params={"perspective": "author"})
    assert author.status_code == 200, f"author 查询失败: {author.text}"
    body = author.json()
    assert {n["id"] for n in body["nodes"]} == set(
        ids[k] for k in ("char-a", "char-b", "char-c", "item-x", "event-e", "loc-l")
    ), (
        f"【问题】author 节点集合不符: {[n['id'] for n in body['nodes']]}\n"
        "【原因】跨模块聚合或 author 直通逻辑异常\n"
        "【修复】检查 entities.search→get_many 聚合链路与 author 分支"
    )
    assert {e["id"] for e in body["edges"]} == {ids["rel-1"], ids["rel-2"], ids["rel-3"]}

    audience = client.get("/api/graph", params={"perspective": "audience"})
    assert audience.status_code == 200, f"audience 查询失败: {audience.text}"
    body = audience.json()
    assert {n["id"] for n in body["nodes"]} == {
        ids[k] for k in ("char-a", "char-c", "event-e", "loc-l")
    }, (
        f"【问题】audience 节点集合不符: {[n['id'] for n in body['nodes']]}\n"
        "【原因】audience_known 过滤条件在真实数据链路上未生效\n"
        "【修复】检查 audience 分支与实体字段的端到端传递"
    )
    assert {e["id"] for e in body["edges"]} == {ids["rel-2"]}, (
        "【问题】audience 边集合不符（双端可见规则未生效）\n"
        "【原因】边过滤缺少双端可见校验\n"
        "【修复】检查 audience 分支的 source/target 可见性校验"
    )

    char_a_view = client.get(
        "/api/graph", params={"perspective": "character", "character_id": ids["char-a"]}
    )
    assert char_a_view.status_code == 200, f"character 查询失败: {char_a_view.text}"
    body = char_a_view.json()
    assert {n["id"] for n in body["nodes"]} == {
        ids[k] for k in ("char-a", "char-b", "item-x", "loc-l")
    }, (
        f"【问题】char-a 视角节点集合不符: {[n['id'] for n in body['nodes']]}\n"
        "【原因】known 标记（seen_by）或关系端点推导在真实数据链路上未生效\n"
        "【修复】检查 character 分支的 visible 集合装配"
    )
    assert {e["id"] for e in body["edges"]} == {ids["rel-1"], ids["rel-2"]}
    for hidden in ("陆离", "夜探药庐"):
        assert hidden not in char_a_view.text, (
            f"【问题】character 视角泄露了被过滤实体名: {hidden}\n"
            "【原因】节点/边投影携带了不可见实体的名称或标记\n"
            "【修复】检查 GraphNode/GraphEdge 投影字段与过滤集合的一致性"
        )


def test_graph_queries_are_read_only(client: TestClient, memory_guard: None) -> None:
    """E2 只读单一事实源：三视角查询（含错误路径）前后数据快照逐字节一致。

    前置: 种子世界；动作: 导出快照 → 执行 author/audience/character×2 查询
        与缺参 403 路径 → 再次导出；预期: 两次快照完全一致。
    设计依据: perspectives/CONSTRAINTS「禁止写库/单一事实源」，
        映射表（docs/architecture_checks.md §2）F04 行的自动化检查。
    """
    _seed_world(client)
    before = _export_snapshot(client)

    for params in (
        {"perspective": "author"},
        {"perspective": "audience"},
        {"perspective": "character", "character_id": ""},
        {"perspective": "editor"},
    ):
        resp = client.get("/api/graph", params=params)
        assert resp.status_code in (200, 403, 422), (
            f"【问题】查询 {params} 返回异常状态 {resp.status_code}: {resp.text[:200]}\n"
            "【原因】非预期路径可能引入副作用\n"
            "【修复】检查该路径的参数校验与异常处理"
        )
    ids_resp = client.get("/api/graph", params={"perspective": "author"})
    char_a = next(n["id"] for n in ids_resp.json()["nodes"] if n["name"] == "周兰")
    for character_id in (char_a, "char-none"):
        resp = client.get(
            "/api/graph", params={"perspective": "character", "character_id": character_id}
        )
        assert resp.status_code in (200, 403), f"character 路径异常: {resp.text[:200]}"

    after = _export_snapshot(client)
    assert before == after, (
        "【问题】视角查询前后数据快照不一致（只读约束被违反）\n"
        f"【原因】查询路径引入了写入或状态变更: before={before[:300]} after={after[:300]}\n"
        "【修复】检查 perspectives 及其聚合链路是否存在任何写操作"
    )
