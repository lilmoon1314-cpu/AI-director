"""F08 L3 端到端测试：资产全链路（assets+entities 跨模块，公开 HTTP 接口）。

验证依据: docs/tests/F08_asset_management.md E1 —
    建实体 → 传图 → 通用资产 CRUD → 实体页 HTML 含名称与图片路径 →
    改实体名触发再生 → 删实体触发清扫（跨模块 + 双库一致性）。
内存守卫: memory_guard fixture 随行（docs/testing.md §7）。
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e

_ASSET_DIR = os.environ["ASSET_DIR"]
PNG_BYTES = b"\x89PNG\r\n\x1a\ne2e-png"


def test_assets_full_flow(client: TestClient, memory_guard: None) -> None:
    """E1: 实体→图片→通用资产→实体页→改名再生→删实体清扫 全链路。

    参数: client — 测试客户端（完整生命周期）；memory_guard — 内存回归守卫。
    返回值: 无。异常: AssertionError — 任一环节链路断裂。
    依赖: 公开 HTTP 接口（entities + assets）。
    """
    # 1. 建实体 + 传图
    entity = client.post("/api/entities", json={"type": "character", "name": "萧折玉"}).json()
    upload = client.post(
        "/api/assets/images",
        files={"file": ("portrait.png", PNG_BYTES, "image/png")},
        data={"scope": "entity", "owner_id": entity["id"]},
    )
    assert upload.status_code == 201, upload.text

    # 2. 实体页惰性生成：含名称 + 图片路径
    page = client.get(f"/api/assets/entity/{entity['id']}/page")
    assert page.status_code == 200
    assert "萧折玉" in page.text, "实体页应含实体名"
    assert upload.json()["stored_name"] in page.text, "实体页应引用上传图片路径"

    # 3. 通用资产：创建 → 列表可见 → 页面可读
    general = client.post(
        "/api/assets/general",
        json={"category": "风格参考", "title": "水墨风", "attributes": {"色调": "青灰"}},
    )
    assert general.status_code == 201
    cards = client.get("/api/assets/general?category=风格参考").json()
    assert any(c["id"] == general.json()["id"] for c in cards), "分类过滤应命中新建资产"
    assert "水墨风" in client.get(f"/api/assets/general/{general.json()['id']}/page").text

    # 4. 改实体名 → 页面过期再生
    client.patch(f"/api/entities/{entity['id']}", json={"name": "萧折玉·改"})
    page2 = client.get(f"/api/assets/entity/{entity['id']}/page")
    assert "萧折玉·改" in page2.text, "改名后实体页应再生反映新名"

    # 5. 删实体 → 孤儿清扫（卡片消失 + 文件清理）
    assert client.delete(f"/api/entities/{entity['id']}").status_code == 204
    assert all(c["id"] != entity["id"] for c in client.get("/api/assets/entities").json()), (
        "已删实体的资产卡片应消失"
    )
    assert not Path(_ASSET_DIR, upload.json()["stored_name"]).exists(), (
        "【问题】删实体后图片文件残留\n【原因】读取时孤儿清扫未生效\n"
        "【修复】检查 list_entity_cards 清扫分支"
    )

    # 6. 通用资产不受实体删除影响（隔离性）
    assert "水墨风" in client.get(f"/api/assets/general/{general.json()['id']}/page").text
