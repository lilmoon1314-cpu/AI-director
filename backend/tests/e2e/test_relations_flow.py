"""F03 L3 E2E 测试：关系完整用户路径（仅走公开 HTTP 接口，testing.md §6）。

跨组件理由: features.md F03 标注「是（entities+relations）」——
    E1 覆盖关系全生命周期（两模块协作建数据 → 增改查 → 删）；
    E2 覆盖 F02×F03 闭环（实体删除被关系引用阻断 → 删关系解除引用 → 删除放行）。
"""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _create_entity(client: TestClient, name: str, **extra: object) -> str:
    """经公开接口创建实体并返回系统生成的 id。

    作用: E2E 场景的前置装配（不直连数据库，保证用户路径真实性）。
    参数: client — 测试客户端；name — 实体名；extra — 追加载荷字段。
    返回值: str — 生成的实体 id。
    异常: AssertionError — 创建未按预期返回 201（三要素消息）。
    依赖: fastapi.testclient.TestClient。
    """
    payload: dict[str, object] = {"type": "character", "name": name}
    payload.update(extra)
    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == 201, (
        f"【问题】实体 {name} 创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/entities 未按预期创建资源\n"
        "【修复】检查请求载荷与 entities 实现"
    )
    return resp.json()["id"]


def test_relation_full_lifecycle_flow(client: TestClient, memory_guard: None) -> None:
    """E1 关系全生命周期：建实体→建关系→读→改→条件查→删，全程公开接口。

    前置: 空库；动作: 依次执行完整用户路径；预期: 每步状态符合契约，
        结束后关系不可再读、实体仍在（删关系不影响实体）。
    """
    zhou = _create_entity(client, "周兰", audience_known=True)
    li = _create_entity(client, "李乾", properties={"occupation": "镖师"})

    created = client.post(
        "/api/relations",
        json={
            "source": zhou,
            "target": li,
            "type": "mentor",
            "trust": 0.8,
            "public_identity": "师徒",
            "promise": "护她周全",
            "known_by": [zhou],
            "properties": {"dynamic_type": "互补型"},
        },
    )
    assert created.status_code == 201, f"关系创建失败: {created.status_code} {created.text}"
    relation = created.json()
    relation_id = relation["id"]

    detail = client.get(f"/api/relations/{relation_id}")
    assert detail.status_code == 200 and detail.json() == relation

    patched = client.patch(
        f"/api/relations/{relation_id}", json={"trust": 0.2, "status": "貌合神离"}
    )
    assert patched.status_code == 200, f"关系更新失败: {patched.text}"
    assert patched.json()["trust"] == 0.2
    assert patched.json()["status"] == "貌合神离"
    assert patched.json()["known_by"] == [zhou], "未提及字段应保留"

    searched = client.get("/api/relations", params={"source": zhou, "type": "mentor"})
    assert searched.status_code == 200
    assert [r["id"] for r in searched.json()] == [relation_id], "条件查询应命中唯一关系"

    deleted = client.delete(f"/api/relations/{relation_id}")
    assert deleted.status_code == 204, f"关系删除失败: {deleted.status_code} {deleted.text}"
    assert client.get(f"/api/relations/{relation_id}").status_code == 404

    assert client.get("/api/relations").json() == [], "删除后列表应为空"
    assert client.get(f"/api/entities/{zhou}").status_code == 200, "删关系不得影响实体"


def test_entity_delete_unblocked_after_relation_removed(
    client: TestClient, memory_guard: None
) -> None:
    """E2 引用阻断与解除闭环：被引用实体删除 409 → 删关系 → 删除放行。

    前置: 两实体 + 一条引用关系；动作: 删 source 实体（应 409）→ 删关系 →
        再删实体（应 204）；预期: F02 防线随关系删除对该实体放行。
    """
    a = _create_entity(client, "周兰")
    b = _create_entity(client, "李乾")
    relation_id = client.post(
        "/api/relations", json={"source": a, "target": b, "type": "ally"}
    ).json()["id"]

    blocked = client.delete(f"/api/entities/{a}")
    assert blocked.status_code == 409, (
        f"【问题】被引用实体的删除未被阻断: HTTP {blocked.status_code} {blocked.text}\n"
        "【原因】F02 应用层引用防线未随关系创建生效\n"
        "【修复】检查 entities.service.delete 与 relations.service.count_by_entity"
    )
    body = blocked.json()
    assert body["code"] == "REFERENTIAL_INTEGRITY"
    assert body["detail"]["reference_count"] == 1
    assert client.get(f"/api/entities/{a}").status_code == 200, "被阻断后实体必须仍在"

    assert client.delete(f"/api/relations/{relation_id}").status_code == 204

    released = client.delete(f"/api/entities/{a}")
    assert released.status_code == 204, (
        f"【问题】引用解除后删除仍被拒: HTTP {released.status_code} {released.text}\n"
        "【原因】引用计数未随关系删除同步减少\n"
        "【修复】检查 relations.repository.count_by_entity 的计数口径"
    )
    assert client.get(f"/api/entities/{a}").status_code == 404
    assert client.get(f"/api/entities/{b}").status_code == 200, "解除引用不应影响另一端实体"
