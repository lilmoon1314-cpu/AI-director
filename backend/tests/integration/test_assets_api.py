"""F08 L2 集成测试：assets API 全链路（router→service→repository→真实双库）。

验证依据: docs/features.md F08 + docs/tests/F08_asset_management.md I1–I8 —
    - 图片上传（白名单/大小上限/uuid 重命名/落盘）经真实双库（主库 + assets.db）
    - 通用资产生命周期（创建/列表/HTML 页/更新/删除）与封面
    - 项目实体资产：分组卡片、惰性生成、过期再生、删除联动清扫
    - 错误响应统一三要素结构（code/problem/cause/fix/detail）
隔离: conftest 在导入前把 DATABASE_URL / ASSET_DB_URL / ASSET_DIR 指向临时目录，
    client fixture 每用例重建两库表结构。
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

# conftest 在导入阶段设置的环境变量（与被测应用共享同一临时目录）
_ASSET_DIR = os.environ["ASSET_DIR"]

# 最小 PNG 字节流（内容不参与图片解码，仅作上传载体）
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-data"


def _create_entity(client: TestClient, name: str = "周兰", entity_type: str = "character") -> dict:
    """经公开 API 创建实体（前置数据构造 helper）。

    参数: client — 测试客户端；name — 实体名；entity_type — 实体类型。
    返回值: dict — EntityRead。异常: AssertionError — 创建失败。
    """
    resp = client.post("/api/entities", json={"type": entity_type, "name": name})
    assert resp.status_code in (200, 201), f"实体创建失败: {resp.status_code} {resp.text}"
    return resp.json()


def _upload_image(
    client: TestClient,
    *,
    owner_id: str,
    scope: str = "entity",
    filename: str = "a.png",
    content: bytes = PNG_BYTES,
    content_type: str = "image/png",
) -> "object":
    """经公开 API 上传图片（multipart 表单）。

    参数: client — 测试客户端；owner_id — 归属 id；scope — 归属面；
        filename/content/content_type — 上传文件三元组。
    返回值: httpx.Response。异常: 无。
    """
    return client.post(
        "/api/assets/images",
        files={"file": (filename, content, content_type)},
        data={"scope": scope, "owner_id": owner_id},
    )


# ---------------- I1: 上传成功链路 ----------------


def test_upload_image_success(client: TestClient) -> None:
    """I1: 实体图片上传 → 201 元数据 + 文件落盘（双库链路）。"""
    entity = _create_entity(client)
    resp = _upload_image(client, owner_id=entity["id"])
    assert resp.status_code == 201, f"上传失败: {resp.text}"
    body = resp.json()
    assert body["scope"] == "entity" and body["owner_id"] == entity["id"], (
        f"【问题】图片元数据归属错误: {body}\n【原因】上传链路装配不符\n【修复】检查装配"
    )
    assert body["url"] == f"/api/assets/file/{body['stored_name']}", (
        "url 应由存储名派生（同源 /api 路由）"
    )
    on_disk = Path(_ASSET_DIR, body["stored_name"])
    assert on_disk.exists() and on_disk.read_bytes() == PNG_BYTES, (
        "【问题】上传文件未落盘或内容不符\n【原因】写盘/流式写入错误\n【修复】检查路径解析"
    )


# ---------------- I2: 上传无效参数化（422 三要素） ----------------


@pytest.mark.parametrize(
    ("upload_name", "content_type", "detail_kind"),
    [
        ("a.txt", "text/plain", "mime"),
        ("b.svg", "image/svg+xml", "extension"),
        ("c.exe", "image/png", "extension"),
    ],
    ids=["non-image-mime", "svg-reject", "ext-not-in-whitelist"],
)
def test_upload_image_rejections(
    client: TestClient, upload_name: str, content_type: str, detail_kind: str
) -> None:
    """I2: 上传无效（非图片 MIME / svg / 扩展名不在白名单）→ 422 三要素 + detail。

    detail 断言随 config 白名单动态构造（测试不钉死环境配置值）：
    mime 拒绝 → {"content_type": ...}；扩展名拒绝 → {"extension": ..., "allowed": [...]}。
    参数: upload_name/content_type — 上传三元组；detail_kind — 期望的拒绝维度。
    返回值: 无。异常: AssertionError — 错误结构不符。
    """
    from app.config import get_settings

    entity = _create_entity(client)
    resp = _upload_image(
        client, owner_id=entity["id"], filename=upload_name, content_type=content_type
    )
    assert resp.status_code == 422, f"应拒绝: {resp.text}"
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR", "错误码应为 VALIDATION_ERROR"
    assert body["problem"] and body["cause"] and body["fix"], (
        f"【问题】422 响应三要素缺失: {body}\n【原因】ValidationError 构造不全\n"
        "【修复】problem/cause/fix 构造必填"
    )
    if detail_kind == "mime":
        expected = {"content_type": content_type}
    else:
        expected = {
            "extension": upload_name.rsplit(".", 1)[-1],
            "allowed": get_settings().asset_allowed_type_list,
        }
    assert body["detail"] == expected, (
        f"【问题】detail 字典不符: {body['detail']} != {expected}\n"
        "【原因】校验器 detail 装配漂移\n【修复】钉死 detail 键值"
    )


# ---------------- I3: 通用资产全生命周期 ----------------


def test_general_asset_lifecycle(client: TestClient) -> None:
    """I3: 创建 → 列表 → HTML 页 → PATCH → 页面更新 → 封面 → 删除 → 404。"""
    created = client.post(
        "/api/assets/general",
        json={
            "category": "表情参考",
            "title": "愤怒",
            "description": "皱眉",
            "attributes": {"强度": 3},
        },
    )
    assert created.status_code == 201, created.text
    asset = created.json()

    # 列表（无图 → 无封面）
    cards = client.get("/api/assets/general").json()
    card = next(c for c in cards if c["id"] == asset["id"])
    assert card["title"] == "愤怒" and card["cover_url"] is None and card["image_count"] == 0

    # HTML 页
    page = client.get(f"/api/assets/general/{asset['id']}/page")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html"), "page 应为 text/html"
    assert "愤怒" in page.text and "强度" in page.text, "页面应含标题与属性键"

    # PATCH → 页面重渲染
    updated = client.patch(
        f"/api/assets/general/{asset['id']}", json={"title": "平静", "attributes": {"强度": 1}}
    )
    assert updated.status_code == 200 and updated.json()["title"] == "平静"
    page2 = client.get(f"/api/assets/general/{asset['id']}/page")
    assert "平静" in page2.text and "愤怒" not in page2.text, (
        "【问题】更新后页面未重渲染\n【原因】update_general 重渲缺失\n【修复】更新路径重调渲染器"
    )

    # 上传两图（首图自动封面）→ 显式换封面 → 卡片封面联动
    up1 = _upload_image(client, scope="general", owner_id=asset["id"], filename="f1.png")
    _upload_image(client, scope="general", owner_id=asset["id"], filename="f2.png")
    assert up1.status_code == 201
    card = next(c for c in client.get("/api/assets/general").json() if c["id"] == asset["id"])
    assert card["cover_url"] == up1.json()["url"] and card["image_count"] == 2, (
        "【问题】首图自动封面或计数不符\n【原因】自动封面/计数逻辑错误\n【修复】检查上传与卡片装配"
    )
    # 图片明细取自最近一次更新响应的 images（AssetRead 含明细）
    detail = client.patch(f"/api/assets/general/{asset['id']}", json={})
    images = detail.json()["images"]
    assert len(images) == 2, "AssetRead.images 应含两图明细"
    cover = client.put(
        f"/api/assets/general/{asset['id']}/cover", json={"image_id": images[1]["id"]}
    )
    assert cover.status_code == 200 and cover.json()["cover_image_id"] == images[1]["id"]
    card = next(c for c in client.get("/api/assets/general").json() if c["id"] == asset["id"])
    assert card["cover_url"] == f"/api/assets/file/{images[1]['stored_name']}", (
        "【问题】显式封面未联动到卡片\n【原因】set_cover/卡片装配不符\n【修复】检查封面推导顺序"
    )

    # 删除 → 页面 404
    assert client.delete(f"/api/assets/general/{asset['id']}").status_code == 204
    assert client.get(f"/api/assets/general/{asset['id']}/page").status_code == 404
    assert client.get("/api/assets/general").json() == []


# ---------------- I4: 项目资产分组卡片（跨库 join） ----------------


def test_entity_cards_grouped_with_cover(client: TestClient) -> None:
    """I4: 实体卡片=主库实体 + 资产库封面（跨库聚合），按类型序+名称序。"""
    e_char = _create_entity(client, name="周兰", entity_type="character")
    e_loc = _create_entity(client, name="沉星湖", entity_type="location")
    up = _upload_image(client, owner_id=e_char["id"])

    cards = client.get("/api/assets/entities").json()
    by_id = {c["id"]: c for c in cards}
    assert by_id[e_char["id"]]["cover_url"] == up.json()["url"], "实体卡片封面应来自资产库"
    assert by_id[e_char["id"]]["type"] == "character" and by_id[e_char["id"]]["name"] == "周兰"
    assert by_id[e_loc["id"]]["cover_url"] is None, "无图实体卡片封面应为空"
    ids = [c["id"] for c in cards]
    assert ids.index(e_char["id"]) < ids.index(e_loc["id"]), (
        f"【问题】卡片排序不符（character 应先于 location）: {ids}\n"
        "【原因】类型序装配错误\n【修复】检查 ENTITY_TYPE_ORDER 排序"
    )


# ---------------- I5: 实体页惰性生成 + 过期再生 ----------------


def test_entity_page_lazy_generate_and_regenerate(client: TestClient) -> None:
    """I5: 首次 GET 生成 HTML；实体 PATCH 后 GET 触发过期再生。"""
    entity = _create_entity(client, name="周兰")
    page1 = client.get(f"/api/assets/entity/{entity['id']}/page")
    assert page1.status_code == 200 and page1.headers["content-type"].startswith("text/html")
    assert "周兰" in page1.text, "页面应含实体名"

    client.patch(f"/api/entities/{entity['id']}", json={"name": "周岚"})
    page2 = client.get(f"/api/assets/entity/{entity['id']}/page")
    assert "周岚" in page2.text, (
        "【问题】实体更新后页面未过期再生\n【原因】staleness 阈值/再生链路失效\n"
        "【修复】检查 updated_at 比较与 get_entity_page 再生分支"
    )


# ---------------- I6: 实体删除联动清扫 ----------------


def test_entity_delete_sweeps_assets(client: TestClient) -> None:
    """I6: 删除实体后，卡片消失、资产页 404、图片物理文件被清扫。"""
    entity = _create_entity(client)
    up = _upload_image(client, owner_id=entity["id"])
    client.get(f"/api/assets/entity/{entity['id']}/page")  # 触发实体页记录生成

    assert client.delete(f"/api/entities/{entity['id']}").status_code == 204
    cards = client.get("/api/assets/entities").json()
    assert all(c["id"] != entity["id"] for c in cards), "已删实体的卡片应消失"
    assert not Path(_ASSET_DIR, up.json()["stored_name"]).exists(), (
        "【问题】孤儿图片物理文件未清扫\n【原因】list_entity_cards 清扫链路失效\n"
        "【修复】检查孤儿归属并集与文件删除"
    )
    assert client.get(f"/api/assets/entity/{entity['id']}/page").status_code == 404, (
        "已删实体的页面应 404（实体不存在经主库校验）"
    )


# ---------------- I7: 跨库实体存在性校验 ----------------


def test_upload_to_missing_entity_returns_404(client: TestClient) -> None:
    """I7: 上传目标实体不存在（主库校验经 entities.service）→ 404 三要素。"""
    resp = _upload_image(client, owner_id="char-ghost")
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert body["problem"] and body["cause"] and body["fix"], (
        f"【问题】404 响应三要素缺失: {body}\n【原因】异常构造不全\n【修复】补全三要素"
    )


# ---------------- I8: 静态访问与越径拒绝 ----------------


def test_static_access_and_traversal_rejected(client: TestClient) -> None:
    """I8: /static/assets/{stored_name} 可取回原文件；越径请求被拒绝。"""
    entity = _create_entity(client)
    stored = _upload_image(client, owner_id=entity["id"]).json()["stored_name"]

    fetched = client.get(f"/static/assets/{stored}")
    assert fetched.status_code == 200 and fetched.content == PNG_BYTES, "静态访问应返回上传原文"

    traversal = client.get("/static/assets/..%2f..%2fsecret.png")
    assert traversal.status_code in (400, 404), (
        f"【问题】越径请求未被拒绝: {traversal.status_code}\n"
        "【原因】StaticFiles 挂载/路径归一防线失效\n【修复】确认挂载仅覆盖 ASSET_DIR"
    )


# ---------------- I9: 图片明细列表（实体面板图片区数据源） ----------------


def test_list_images_by_owner(client: TestClient) -> None:
    """I9: 上传两张图后 GET /api/assets/images 返回按归属的明细（升序，含 url）。"""
    entity = _create_entity(client)
    up1 = _upload_image(client, owner_id=entity["id"], filename="f1.png")
    up2 = _upload_image(client, owner_id=entity["id"], filename="f2.png")
    assert up1.status_code == 201 and up2.status_code == 201

    listing = client.get("/api/assets/images", params={"scope": "entity", "owner_id": entity["id"]})
    assert listing.status_code == 200, listing.text
    images = listing.json()
    assert [i["id"] for i in images] == [up1.json()["id"], up2.json()["id"]], (
        f"【问题】图片明细不符: {images}\n【原因】list_images 归属过滤/排序错误\n"
        "【修复】检查 scope+owner_id 过滤与创建时间排序"
    )
    assert images[0]["url"] == f"/api/assets/file/{images[0]['stored_name']}", (
        "明细应含图片访问 url"
    )


# ---------------- I10: /api 同源图片访问路由 ----------------


def test_image_file_route_same_origin(client: TestClient) -> None:
    """I10: GET /api/assets/file/{stored_name} 返回图片字节（HTML 页内引用的同源地址）。"""
    entity = _create_entity(client)
    up = _upload_image(client, owner_id=entity["id"])
    stored = up.json()["stored_name"]

    fetched = client.get(f"/api/assets/file/{stored}")
    assert fetched.status_code == 200, f"同源图片路由失败: {fetched.status_code}"
    assert fetched.content == PNG_BYTES, "应返回上传原文"
    assert fetched.headers["content-type"].startswith("image/"), "mime 应为图片类型"

    missing = client.get("/api/assets/file/deadbeef.png")
    assert missing.status_code == 404, "不存在的存储名应 404"
