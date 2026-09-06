"""F11 L3 端到端测试：多项目隔离全链路（projects+entities+relations+perspectives+assets）。

验证依据: docs/features.md F11（跨组件=L3 必须）+ docs/tests/F11_multi_project_foundation.md E1–E2 —
    - E1 双项目全链路：建项目 → 各建实体/关系 → 图按项目隔离 → 删除 A → B 完好、A 数据消失
    - E2 向后兼容：旧调用（不带 project_id）全部落默认项目，行为与 F10 前一致
内存守卫: memory_guard fixture 随行（docs/testing.md §7）。
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e

_DEFAULT_ID = "project-default"


def _post(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """经公开接口创建资源并断言 201（e2e 自含装配）。"""
    resp = client.post(path, json=payload)
    assert resp.status_code == 201, (
        f"【问题】{path} 创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】公开接口未按预期创建资源\n"
        "【修复】检查请求载荷与对应路由/service 实现"
    )
    return resp.json()


def _seed_project_world(client: TestClient, project_name: str) -> dict[str, Any]:
    """在独立项目内搭建「双实体 + 一关系」的最小世界并返回关键 id。"""
    proj = _post(client, "/api/projects", {"name": project_name})
    a = _post(
        client,
        "/api/entities",
        {"type": "character", "name": f"{project_name}·甲", "project_id": proj["id"]},
    )
    b = _post(
        client,
        "/api/entities",
        {"type": "character", "name": f"{project_name}·乙", "project_id": proj["id"]},
    )
    rel = _post(
        client,
        "/api/relations",
        {
            "source": a["id"],
            "target": b["id"],
            "type": "mentor",
            "known_by": [a["id"]],
            "project_id": proj["id"],
        },
    )
    return {"project": proj, "a": a, "b": b, "rel": rel}


def test_dual_project_isolation_and_cascade_flow(client: TestClient, memory_guard: None) -> None:
    """E1 双项目全链路：隔离可见 → 级联删除 A → B 完好、A 数据消失。

    前置: 空库；动作: 建两项目世界 → 图隔离断言 → 删 A → 复查；
    预期: 删除前后项目边界稳定，级联清理完整。
    """
    world_a = _seed_project_world(client, "长安怪谈")
    world_b = _seed_project_world(client, "星海纪元")

    # —— 图按项目隔离（author 全知 × 项目维度正交叠加）——
    for world in (world_a, world_b):
        graph = client.get(
            "/api/graph",
            params={"perspective": "author", "project_id": world["project"]["id"]},
        )
        assert graph.status_code == 200
        node_ids = {n["id"] for n in graph.json()["nodes"]}
        assert node_ids == {world["a"]["id"], world["b"]["id"]}, (
            f"【问题】项目图节点集不符: {node_ids}\n"
            "【原因】图查询项目过滤失效或跨项目泄露\n"
            "【修复】检查 perspectives.get_graph 的 project 维度过滤"
        )
        assert len(graph.json()["edges"]) == 1

    # —— 计数器事务一致（项目卡片元信息）——
    projects = {p["id"]: p for p in client.get("/api/projects").json()}
    assert projects[world_a["project"]["id"]]["entity_count"] == 2
    assert projects[world_b["project"]["id"]]["relation_count"] == 1

    # —— 级联删除 A ——
    deleted = client.delete(f"/api/projects/{world_a['project']['id']}")
    assert deleted.status_code == 204

    assert client.get(f"/api/entities/{world_a['a']['id']}").status_code == 404
    assert client.get(f"/api/relations/{world_a['rel']['id']}").status_code == 404
    graph_a = client.get(
        "/api/graph",
        params={"perspective": "author", "project_id": world_a["project"]["id"]},
    )
    assert graph_a.status_code == 404, "已删项目的图查询应 404"

    # —— B 完好无损 ——
    assert client.get(f"/api/entities/{world_b['a']['id']}").status_code == 200
    graph_b = client.get(
        "/api/graph",
        params={"perspective": "author", "project_id": world_b["project"]["id"]},
    )
    assert graph_b.status_code == 200 and len(graph_b.json()["nodes"]) == 2
    assert world_a["project"]["id"] not in {p["id"] for p in client.get("/api/projects").json()}


def test_legacy_calls_fall_back_to_default_project_flow(
    client: TestClient, memory_guard: None
) -> None:
    """E2 向后兼容：不带 project_id 的旧调用全部落默认项目（迁移打包语义等价）。

    前置: 空库；动作: 旧式建实体/关系/查询；预期: 数据落默认项目且计数器正确。
    """
    a = _post(client, "/api/entities", {"type": "character", "name": "旧式甲"})
    b = _post(client, "/api/entities", {"type": "location", "name": "旧式地"})
    rel = _post(
        client,
        "/api/relations",
        {"source": a["id"], "target": b["id"], "type": "LIVES_AT", "known_by": []},
    )
    assert a["project_id"] == _DEFAULT_ID, "旧式实体应落默认项目"
    assert rel["project_id"] == _DEFAULT_ID

    graph = client.get("/api/graph", params={"perspective": "author"})
    assert graph.status_code == 200
    assert {n["id"] for n in graph.json()["nodes"]} == {a["id"], b["id"]}, (
        "【问题】缺省图查询未返回默认项目数据\n"
        "【原因】project 维度缺省解析与迁移打包语义不一致\n"
        "【修复】检查 perspectives.get_graph 的缺省归属"
    )

    projects = {p["id"]: p for p in client.get("/api/projects").json()}
    assert projects[_DEFAULT_ID]["entity_count"] == 2
    assert projects[_DEFAULT_ID]["relation_count"] == 1
