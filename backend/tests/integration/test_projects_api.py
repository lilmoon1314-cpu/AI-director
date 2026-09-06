"""F11 L2 集成测试：projects API 全链路 + 既有端点 project 维度（真实双库）。

验证依据: docs/features.md F11 + docs/tests/F11_multi_project_foundation.md I1–I10 —
    - 项目 CRUD 全链路（计数器随领域写入事务一致）
    - 名称边界值（空/纯空白/长度 1/上限/上限+1，参数化）
    - 级联删除（关系→实体→项目行原子；资产记录/图片/物理文件显式清扫）
    - 默认项目保护（422）与 lifespan 播种
    - entities / relations / graph / assets 端点的 project_id 过滤与跨项目拒绝
    - 通用资产恒全局（无项目维度）
"""

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

_DEFAULT_ID = "project-default"

# 最小 PNG 形态字节（服务端校验扩展名+MIME 白名单，不解码像素）
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _create_project(client: TestClient, name: str, **extra: Any) -> dict[str, Any]:
    """经公开接口创建项目并返回响应体。

    参数: client — 测试客户端；name — 项目名；extra — 追加载荷字段。
    返回值: dict（含系统生成的 id）。异常: AssertionError — 未按预期 201。
    """
    payload: dict[str, Any] = {"name": name}
    payload.update(extra)
    resp = client.post("/api/projects", json=payload)
    assert resp.status_code == 201, (
        f"【问题】项目创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/projects 未按预期创建资源\n"
        "【修复】检查载荷与 projects 路由/service 实现"
    )
    return resp.json()


def _create_entity(
    client: TestClient, name: str, project_id: str | None = None, **extra: Any
) -> dict[str, Any]:
    """经公开接口在指定项目（None=不带 project_id）创建实体。"""
    payload: dict[str, Any] = {"type": "character", "name": name}
    if project_id is not None:
        payload["project_id"] = project_id
    payload.update(extra)
    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == 201, (
        f"【问题】实体创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/entities 未按预期创建资源\n"
        "【修复】检查载荷与 entities 路由/service 实现"
    )
    return resp.json()


def _list_projects(client: TestClient) -> list[dict[str, Any]]:
    """列出全部项目。"""
    resp = client.get("/api/projects")
    assert resp.status_code == 200, f"项目列表失败: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------- I1: 创建链路（等价类-有效） ----------------


def test_create_project_returns_201_with_fields(client: TestClient) -> None:
    """I1 有效创建 → 201，ProjectRead 字段完整且计数为 0、id 带前缀。

    设计依据: 等价类-有效创建（响应契约完整性）。
    """
    created = _create_project(client, "长安怪谈", description="盛唐志怪世界")
    assert created["id"].startswith("project-")
    assert created["name"] == "长安怪谈"
    assert created["description"] == "盛唐志怪世界"
    assert created["entity_count"] == 0 and created["relation_count"] == 0
    assert created["created_at"] and created["updated_at"]


# ---------------- I2: 名称边界值（参数化） ----------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("", 422),
        (" ", 422),
        ("甲", 201),
        ("甲" * 64, 201),
        ("甲" * 65, 422),
    ],
    ids=["empty", "whitespace", "len-1", "len-64-max", "len-65-over"],
)
def test_create_project_name_boundaries(client: TestClient, name: str, expected: int) -> None:
    """I2 参数化 名称边界：空/纯空白 422；长度 1 与 64（上限）201；65（上限+1）422。

    设计依据: 边界值-长度两侧邻界（min_length/max_length 由 Pydantic 产生，仅 HTTP 层可杀）。
    """
    resp = client.post("/api/projects", json={"name": name})
    assert resp.status_code == expected, (
        f"【问题】名称 '{name[:8]}…'（长度 {len(name)}）期望 {expected}，"
        f"实际 {resp.status_code} {resp.text}\n"
        "【原因】名称长度/空白校验边界与契约不符\n"
        "【修复】对照 ProjectCreate 的 Field 约束与 _strip_name 校验器"
    )


# ---------------- I3: 列表与计数器（真实链路事务一致） ----------------


def test_list_includes_default_and_counters_track_writes(client: TestClient) -> None:
    """I3 列表含 lifespan 播种的默认项目；实体/关系写入后计数器事务一致增长。

    设计依据: 等价类-有效-聚合契约（反规范化计数器与真实写入一致）。
    """
    projects = {p["id"]: p for p in _list_projects(client)}
    assert _DEFAULT_ID in projects, "默认项目应由 lifespan 幂等播种"

    proj = _create_project(client, "星海纪元")
    a = _create_entity(client, "沈青梧", project_id=proj["id"])
    b = _create_entity(client, "裴照", project_id=proj["id"])
    rel = client.post(
        "/api/relations",
        json={
            "source": a["id"],
            "target": b["id"],
            "type": "mentor",
            "project_id": proj["id"],
        },
    )
    assert rel.status_code == 201, f"关系创建失败: {rel.status_code} {rel.text}"

    projects = {p["id"]: p for p in _list_projects(client)}
    assert projects[proj["id"]]["entity_count"] == 2, "实体计数应随写入事务内 +2"
    assert projects[proj["id"]]["relation_count"] == 1
    assert projects[_DEFAULT_ID]["entity_count"] == 0


# ---------------- I4: 改名与不存在（三要素契约） ----------------


def test_rename_and_missing_not_found(client: TestClient) -> None:
    """I4 PATCH 改名生效；不存在 id → 404 且三要素与 detail 整体相等（E05 范式）。

    设计依据: 等价类-有效改名 / 无效-不存在。
    """
    proj = _create_project(client, "雾都旧事")
    resp = client.patch(f"/api/projects/{proj['id']}", json={"name": "雾都新事"})
    assert resp.status_code == 200 and resp.json()["name"] == "雾都新事"

    missing = client.patch("/api/projects/project-ghost", json={"name": "任何名"})
    assert missing.status_code == 404, (
        f"【问题】不存在项目期望 404，实际 {missing.status_code}\n"
        "【原因】归属校验未拦截幽灵 id\n"
        "【修复】检查 projects.service.update 的存在性校验"
    )
    body = missing.json()
    assert body["code"] == "NOT_FOUND"
    assert body["problem"] == "项目不存在"
    assert body["cause"] == "id 'project-ghost' 未在库中"
    assert body["fix"] == "先调用 GET /api/projects 检索确认项目 id"
    assert body["detail"] == {"project_id": "project-ghost"}


# ---------------- I5: 级联删除与默认项目保护 ----------------


def test_delete_project_cascades_and_sweeps_assets(client: TestClient) -> None:
    """I5 删除项目 → 关系/实体 404、资产图片记录与物理文件清扫；默认项目删除 422。

    设计依据: 等价类-有效级联 / 无效-受保护资源（DESIGN §8.2 显式级联路径）。
    """
    proj = _create_project(client, "待删项目")
    a = _create_entity(client, "甲", project_id=proj["id"])
    b = _create_entity(client, "乙", project_id=proj["id"])
    assert (
        client.post(
            "/api/relations",
            json={"source": a["id"], "target": b["id"], "type": "rival", "project_id": proj["id"]},
        ).status_code
        == 201
    )
    upload = client.post(
        "/api/assets/images",
        files={"file": ("a.png", _PNG_BYTES, "image/png")},
        data={"scope": "entity", "owner_id": a["id"]},
    )
    assert upload.status_code == 201, f"图片上传失败: {upload.text}"
    stored_name = upload.json()["stored_name"]

    deleted = client.delete(f"/api/projects/{proj['id']}")
    assert deleted.status_code == 204, f"级联删除失败: {deleted.status_code} {deleted.text}"

    assert client.get(f"/api/entities/{a['id']}").status_code == 404
    assert client.get(f"/api/entities/{b['id']}").status_code == 404
    images = client.get("/api/assets/images", params={"scope": "entity", "owner_id": a["id"]})
    assert images.status_code == 200 and images.json() == [], "资产图片记录应被显式清扫"
    asset_file = Path(os.environ["ASSET_DIR"]) / stored_name
    assert not asset_file.exists(), (
        f"【问题】物理文件未清扫: {asset_file}\n"
        "【原因】级联清扫未删除物理文件\n"
        "【修复】检查 assets.service.sweep_entity_assets 的文件删除"
    )
    assert proj["id"] not in {p["id"] for p in _list_projects(client)}

    protected = client.delete(f"/api/projects/{_DEFAULT_ID}")
    assert protected.status_code == 422, "默认项目删除应被 422 拒绝"
    assert protected.json()["detail"] == {
        "project_id": _DEFAULT_ID,
        "rule": "default_project_protected",
    }


# ---------------- I6: 实体归属 scoping（参数化） ----------------


@pytest.mark.parametrize(
    ("explicit_project", "visible_in", "expected_code"),
    [
        ("given", "project", 201),
        ("omitted", "default", 201),
        ("ghost", None, 404),
    ],
    ids=["explicit", "default-fallback", "ghost-project"],
)
def test_entity_project_scoping(
    client: TestClient, explicit_project: str, visible_in: str | None, expected_code: int
) -> None:
    """I6 参数化 实体归属：显式项目隔离 / 缺省落默认项目 / 幽灵项目 404。

    设计依据: 等价类-有效-显式归属 / 有效-缺省兜底 / 无效-项目不存在。
    """
    proj = _create_project(client, "归属测试")
    payload: dict[str, Any] = {"type": "character", "name": "测试角色"}
    if explicit_project == "given":
        payload["project_id"] = proj["id"]
    elif explicit_project == "ghost":
        payload["project_id"] = "project-ghost"

    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == expected_code, (
        f"【问题】实体创建期望 {expected_code}，实际 {resp.status_code} {resp.text}\n"
        "【原因】project 维度归属校验与契约不符\n"
        "【修复】检查 entities.service.create 的归属解析与 ensure_exists"
    )
    if expected_code != 201:
        return

    entity_id = resp.json()["id"]
    if visible_in == "project":
        target, other = proj["id"], _DEFAULT_ID
    else:
        target, other = _DEFAULT_ID, proj["id"]
    visible = client.get("/api/entities", params={"project_id": target}).json()
    invisible = client.get("/api/entities", params={"project_id": other}).json()
    assert entity_id in {e["id"] for e in visible}, "实体应在归属项目可见"
    assert entity_id not in {e["id"] for e in invisible}, "实体不应跨项目可见"


# ---------------- I7: 图查询项目隔离 ----------------


def test_graph_project_isolation(client: TestClient) -> None:
    """I7 graph 按项目过滤：A 图不含 B 实体；缺省=默认项目；幽灵项目 404。

    设计依据: 等价类-项目维度与视角过滤正交叠加。
    """
    proj_a = _create_project(client, "图隔离A")
    proj_b = _create_project(client, "图隔离B")
    a1 = _create_entity(client, "A1", project_id=proj_a["id"])
    _create_entity(client, "B1", project_id=proj_b["id"])

    graph_a = client.get("/api/graph", params={"perspective": "author", "project_id": proj_a["id"]})
    assert graph_a.status_code == 200
    node_ids = {n["id"] for n in graph_a.json()["nodes"]}
    assert node_ids == {a1["id"]}, f"A 项目图应只含 A 实体，实际 {node_ids}"

    graph_default = client.get("/api/graph", params={"perspective": "author"})
    assert graph_default.status_code == 200
    assert a1["id"] not in {n["id"] for n in graph_default.json()["nodes"]}, (
        "缺省图（默认项目）不应泄露显式项目实体"
    )

    ghost = client.get("/api/graph", params={"perspective": "author", "project_id": "p-ghost"})
    assert ghost.status_code == 404


# ---------------- I8: 跨项目关系拒绝 ----------------


@pytest.mark.parametrize(
    ("violation",),
    [
        ("source-cross-project",),
        ("target-cross-project",),
        ("known-by-cross-project",),
    ],
    ids=["source", "target", "known_by"],
)
def test_relation_cross_project_rejected(client: TestClient, violation: str) -> None:
    """I8 参数化 跨项目引用（source/target/known_by 任一维度）→ 422。

    设计依据: 等价类-无效-跨项目关系（三维度同构断言，参数化）。
    """
    proj = _create_project(client, "关系项目A")
    proj_b = _create_project(client, "关系项目B")
    inside = _create_entity(client, "甲(A)", project_id=proj["id"])
    other = _create_entity(client, "乙(B)", project_id=proj_b["id"])
    inside2 = _create_entity(client, "丙(A)", project_id=proj["id"])

    payload: dict[str, Any] = {
        "type": "mentor",
        "project_id": proj["id"],
        "source": inside["id"],
        "target": inside2["id"],
        "known_by": [],
    }
    if violation == "source-cross-project":
        payload["source"] = other["id"]
    elif violation == "target-cross-project":
        payload["target"] = other["id"]
    else:  # known_by 跨项目（角色实体在 B）
        payload["known_by"] = [other["id"]]

    resp = client.post("/api/relations", json=payload)
    assert resp.status_code == 422, (
        f"【问题】跨项目关系（{violation}）期望 422，实际 {resp.status_code} {resp.text}\n"
        "【原因】同项目校验未覆盖该维度\n"
        "【修复】检查 relations.service.create 的跨项目校验"
    )
    assert resp.json()["detail"].get("rule") == "cross_project_reference"


# ---------------- I9: 资产卡片项目过滤 ----------------


def test_assets_entity_cards_project_scoped(client: TestClient) -> None:
    """I9 /api/assets/entities?project_id= 仅含当前项目实体；幽灵项目 404。

    设计依据: 等价类-项目资产随项目隔离（实体资产经实体间接归属）。
    """
    proj_a = _create_project(client, "资产A")
    proj_b = _create_project(client, "资产B")
    a1 = _create_entity(client, "资产甲", project_id=proj_a["id"])
    _create_entity(client, "资产乙", project_id=proj_b["id"])

    cards = client.get("/api/assets/entities", params={"project_id": proj_a["id"]})
    assert cards.status_code == 200
    card_ids = {c["id"] for c in cards.json()}
    assert card_ids == {a1["id"]}, f"项目资产卡片应只含 A 实体，实际 {card_ids}"

    ghost = client.get("/api/assets/entities", params={"project_id": "p-ghost"})
    assert ghost.status_code == 404


# ---------------- I10: 通用资产恒全局 ----------------


def test_general_assets_are_global_across_projects(client: TestClient) -> None:
    """I10 通用资产无项目维度：创建后列表行为不随项目参数变化（恒全局）。

    设计依据: 等价类-全局资源恒共享（DESIGN §8.2：kind=general 不加 project 字段）。
    """
    proj = _create_project(client, "通用库参照项目")
    created = client.post(
        "/api/assets/general",
        json={"title": "表情参考库", "category": "表情参考", "description": "眉眼嘴形"},
    )
    assert created.status_code == 201, f"通用资产创建失败: {created.text}"

    listing = client.get("/api/assets/general")
    assert listing.status_code == 200
    titles = {a["title"] for a in listing.json()}
    assert "表情参考库" in titles, "通用资产应在全局列表可见"

    # 项目维度过滤不改变通用库语义：通用资产绝不出现在项目资产卡片中
    cards = client.get("/api/assets/entities", params={"project_id": proj["id"]})
    assert cards.status_code == 200 and all(
        c["id"].startswith(("char-", "fct-", "loc-", "item-", "skill-", "event-", "cpt-"))
        for c in cards.json()
    ), "项目资产卡片只含实体，通用资产不得混入"
