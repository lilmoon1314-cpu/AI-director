"""F08 L1 单元测试：assets service 业务逻辑（repository mock + 真实 storage 于临时目录）。

mock 策略:
    以内存字典替换 repository 数据访问、以桩替换 entities.service 跨模块调用、
    以最小会话桩承载 commit——只验证 service/rendering/storage 的校验、装配、
    HTML 渲染、过期判定与清扫逻辑；文件操作落在 conftest 隔离的 ASSET_DIR。
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.assets import repository, service, storage
from app.assets.models import AssetImage, AssetRecord
from app.assets.schemas import GeneralAssetCreate, GeneralAssetUpdate
from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.entities import service as entities_service

pytestmark = pytest.mark.unit


class SessionStub:
    """最小会话桩：仅支持 commit 空操作（单元层不触数据库）。"""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeUpload:
    """上传对象桩（提供 async read(n) 协议，记录每次读取块数）。"""

    def __init__(self, data: bytes, filename: str, content_type: str) -> None:
        """初始化桩（参数与 fastapi UploadFile 对齐的字段子集）。

        参数: data — 文件内容；filename — 原始文件名；content_type — MIME。
        """
        self._data = data
        self.filename = filename
        self.content_type = content_type
        self.read_calls: list[int] = []

    async def read(self, size: int) -> bytes:
        """按块返回数据并记录读取（供流式断言）。"""
        self.read_calls.append(size)
        chunk = self._data[:size]
        self._data = self._data[size:]
        return chunk


def _asset_dir() -> str:
    """取当前测试隔离的资产目录。"""
    return get_settings().asset_dir


def _record(
    record_id: str = "asset-r1",
    *,
    kind: str = "general",
    entity_id: str | None = None,
    title: str = "表情参考",
    updated_at: datetime | None = None,
) -> AssetRecord:
    """构造资产记录桩（时间可注入，供过期判定）。"""
    now = updated_at or datetime.now(UTC)
    return AssetRecord(
        id=record_id,
        kind=kind,
        entity_id=entity_id,
        category="表情参考",
        title=title,
        description="",
        attributes={},
        html="<!doctype html><html>OLD</html>",
        created_at=now,
        updated_at=now,
    )


def _image(
    image_id: str = "img-1",
    *,
    scope: str = "general",
    owner_id: str = "asset-r1",
    stored_name: str = "aa11.png",
    created_at: datetime | None = None,
) -> AssetImage:
    """构造图片元数据桩。"""
    now = created_at or datetime.now(UTC)
    return AssetImage(
        id=image_id,
        scope=scope,
        owner_id=owner_id,
        filename_orig="原始.png",
        stored_name=stored_name,
        mime="image/png",
        size=10,
        created_at=now,
    )


def _entity(
    entity_id: str = "char-e1",
    *,
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    """构造实体数据桩（满足 rendering.EntityLike 结构契约）。"""
    return SimpleNamespace(
        id=entity_id,
        type="character",
        name="周兰",
        aliases=["兰儿"],
        description="主角",
        properties={"age": 24, "habits": {"quirks": "摸剑"}},
        updated_at=updated_at or datetime.now(UTC),
    )


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """内存资产存储（records/images 字典）+ repository 全量 mock + 清空资产目录。

    作用: 隔离 service 层——repository 操作内存字典；entities.service 桩可注入；
        资产目录内既有文件清空，物理文件断言直接读该目录。
    参数: monkeypatch — pytest 替换器。
    返回值: dict — {"records": {...}, "images": {...}, "deleted_files": [...],
        "entity_stub": 可变桩槽位}。
    异常: 无。
    依赖: app.assets.repository、app.entities.service。
    """
    records: dict[str, AssetRecord] = {}
    images: dict[str, AssetImage] = {}
    deleted_files: list[str] = []
    state: dict[str, Any] = {"entity": None, "entities": []}

    async def fake_get_record(_s: Any, asset_id: str) -> AssetRecord | None:
        return records.get(asset_id)

    async def fake_get_entity_record(_s: Any, entity_id: str) -> AssetRecord | None:
        return next((r for r in records.values() if r.entity_id == entity_id), None)

    async def fake_list_records(_s: Any, kind: str, category: str | None = None) -> list:
        rows = [r for r in records.values() if r.kind == kind]
        if category is not None:
            rows = [r for r in rows if r.category == category]
        return sorted(rows, key=lambda r: r.updated_at, reverse=True)

    async def fake_add_record(_s: Any, record: AssetRecord) -> AssetRecord:
        records[record.id] = record
        return record

    async def fake_save_record(_s: Any, record: AssetRecord) -> AssetRecord:
        records[record.id] = record
        return record

    async def fake_delete_record(_s: Any, record: AssetRecord) -> None:
        records.pop(record.id, None)

    async def fake_get_image(_s: Any, image_id: str) -> AssetImage | None:
        return images.get(image_id)

    async def fake_list_images(_s: Any, scope: str, owner_id: str) -> list[AssetImage]:
        rows = [i for i in images.values() if i.scope == scope and i.owner_id == owner_id]
        return sorted(rows, key=lambda i: i.created_at)

    async def fake_list_images_for_owners(
        _s: Any, scope: str, owner_ids: list[str]
    ) -> dict[str, list[AssetImage]]:
        wanted = set(owner_ids)
        grouped: dict[str, list[AssetImage]] = {}
        for image in images.values():
            if image.scope == scope and image.owner_id in wanted:
                grouped.setdefault(image.owner_id, []).append(image)
        return {k: sorted(v, key=lambda i: i.created_at) for k, v in grouped.items()}

    async def fake_list_images_by_scope(_s: Any, scope: str) -> list[AssetImage]:
        rows = [i for i in images.values() if i.scope == scope]
        return sorted(rows, key=lambda i: i.created_at)

    async def fake_add_image(_s: Any, image: AssetImage) -> AssetImage:
        images[image.id] = image
        return image

    async def fake_delete_image(_s: Any, image: AssetImage) -> None:
        images.pop(image.id, None)

    async def fake_clear_cover(_s: Any, image_id: str) -> None:
        for record in records.values():
            if record.cover_image_id == image_id:
                record.cover_image_id = None

    def fake_delete_file(stored_name: str, asset_dir: str) -> None:
        deleted_files.append(stored_name)
        Path(asset_dir, stored_name).unlink(missing_ok=True)

    async def fake_entity_get(_s: Any, entity_id: str) -> SimpleNamespace:
        entity = state["entity"]
        if entity is None or entity.id != entity_id:
            raise NotFoundError(
                problem="实体不存在", cause=f"id '{entity_id}' 未在库中", fix="检索确认 id"
            )
        return entity

    async def fake_entity_list_all(_s: Any) -> list[SimpleNamespace]:
        return list(state["entities"])

    monkeypatch.setattr(repository, "get_record", fake_get_record)
    monkeypatch.setattr(repository, "get_entity_record", fake_get_entity_record)
    monkeypatch.setattr(repository, "list_records", fake_list_records)
    monkeypatch.setattr(repository, "add_record", fake_add_record)
    monkeypatch.setattr(repository, "save_record", fake_save_record)
    monkeypatch.setattr(repository, "delete_record", fake_delete_record)
    monkeypatch.setattr(repository, "get_image", fake_get_image)
    monkeypatch.setattr(repository, "list_images", fake_list_images)
    monkeypatch.setattr(repository, "list_images_for_owners", fake_list_images_for_owners)
    monkeypatch.setattr(repository, "list_images_by_scope", fake_list_images_by_scope)
    monkeypatch.setattr(repository, "add_image", fake_add_image)
    monkeypatch.setattr(repository, "delete_image", fake_delete_image)
    monkeypatch.setattr(repository, "clear_cover_reference", fake_clear_cover)
    monkeypatch.setattr(storage, "delete_stored_file", fake_delete_file)
    monkeypatch.setattr(entities_service, "get", fake_entity_get)
    monkeypatch.setattr(entities_service, "list_all", fake_entity_list_all)

    # 清空资产目录残留（同进程内跨用例隔离）
    for stale in Path(_asset_dir()).glob("*"):
        stale.unlink(missing_ok=True)
    return {"records": records, "images": images, "deleted": deleted_files, "state": state}


# ---------------- U1: MIME 白名单（等价类） ----------------


@pytest.mark.parametrize(
    ("content_type", "filename", "valid"),
    [
        ("image/png", "a.png", True),
        ("image/jpeg", "b.jpg", True),
        ("image/webp", "c.webp", True),
        ("image/gif", "d.gif", True),
        ("text/plain", "e.txt", False),
        ("application/octet-stream", "f.exe", False),
        ("image/svg+xml", "g.svg", False),
    ],
    ids=["png-ok", "jpeg-ok", "webp-ok", "gif-ok", "txt-reject", "exe-reject", "svg-reject"],
)
def test_validate_upload_mime_whitelist(content_type: str, filename: str, valid: bool) -> None:
    """U1: MIME 白名单校验（有效图片类型通过，非图片与 svg 拒绝）。

    参数: content_type — 客户端 MIME；filename — 原始名；valid — 是否应通过。
    返回值: 无。异常: AssertionError — 白名单行为不符。
    依赖: app.assets.storage.validate_upload。
    """
    allowed = get_settings().asset_allowed_type_list
    if valid:
        ext = storage.validate_upload(
            filename=filename,
            content_type=content_type,
            max_size_bytes=1024,
            allowed_extensions=allowed,
        )
        assert ext == filename.rsplit(".", 1)[-1].lower(), (
            f"【问题】有效类型 {content_type} 未通过或扩展名归一错误\n"
            "【原因】白名单校验器行为不符\n【修复】检查 validate_upload 扩展名归一逻辑"
        )
    else:
        with pytest.raises(ValidationError) as exc_info:
            storage.validate_upload(
                filename=filename,
                content_type=content_type,
                max_size_bytes=1024,
                allowed_extensions=allowed,
            )
        message = str(exc_info.value.problem) + str(exc_info.value.cause) + str(exc_info.value.fix)
        assert all(message), (
            "【问题】ValidationError 三要素存在空缺\n"
            "【原因】异常构造未填全 problem/cause/fix\n【修复】补全三要素"
        )


# ---------------- U2: 大小上限（边界值，经 write_stream 强制） ----------------


@pytest.mark.parametrize(
    ("payload_size", "max_bytes", "valid"),
    [
        (97, 100, True),
        (100, 100, True),
        (101, 100, False),
    ],
    ids=["below-limit-ok", "at-limit-ok", "over-limit-reject"],
)
def test_write_stream_size_boundary(
    tmp_path: Path, payload_size: int, max_bytes: int, valid: bool
) -> None:
    """U2: 流式写入大小上限边界（上限/上限+1 严格截断在边界上）。

    参数: payload_size — 载荷字节数；max_bytes — 上限；valid — 是否应成功。
    返回值: 无。异常: AssertionError — 边界行为不符。
    依赖: app.assets.storage.write_stream。
    """
    dest = tmp_path / "u.png"
    upload = FakeUpload(b"x" * payload_size, "u.png", "image/png")
    if valid:
        written = _run(dest, upload, max_bytes)
        assert written == payload_size, (
            f"【问题】写入字节数 {written} != 载荷 {payload_size}\n"
            "【原因】write_stream 计数错误\n【修复】检查累计逻辑"
        )
    else:
        with pytest.raises(ValidationError):
            _run(dest, upload, max_bytes)
        assert not dest.exists(), (
            "【问题】超限后半成品文件残留\n"
            "【原因】write_stream 超限未清理 dest\n【修复】超限分支 unlink(missing_ok=True)"
        )


def _run(dest: Path, upload: FakeUpload, max_bytes: int) -> int:
    """同步驱动 async write_stream（单元层无事件循环夹具时的最小包装）。

    参数: dest — 目标路径；upload — 上传桩；max_bytes — 上限。
    返回值: int — 写入字节数。异常: 原样透传 ValidationError。
    """
    import asyncio

    return asyncio.run(storage.write_stream(upload, dest, max_bytes))


# ---------------- U3: uuid 重命名与路径穿越防护（等价类-无效） ----------------


@pytest.mark.parametrize(
    "evil_name",
    ["../../etc/passwd.png", "..\\..\\win.png", "C:\\evil\\x.png", "图 片.png"],
    ids=["dotdot-slash", "dotdot-backslash", "drive-letter", "unicode-space"],
)
def test_build_and_resolve_stored_name_rejects_user_input(evil_name: str) -> None:
    """U3: 存储名由 uuid 生成、用户输入零参与；路径解析越界被拒。

    参数: evil_name — 恶意/含空白原始文件名。
    返回值: 无。异常: AssertionError — 用户输入成分泄入存储路径。
    依赖: app.assets.storage.build_stored_name / resolve_stored_path。
    """
    stored = storage.build_stored_name(storage._ext_of(evil_name))
    assert evil_name not in stored, (
        f"【问题】存储名 {stored} 含用户输入成分 '{evil_name}'\n"
        "【原因】重命名未与用户文件名解耦（路径穿越风险）\n"
        "【修复】存储名只能由 build_stored_name 的 uuid 部分构成"
    )
    root = _asset_dir()
    resolved = storage.resolve_stored_path(stored, root)
    assert resolved.is_relative_to(Path(root).resolve()), (
        "【问题】解析路径越出资产目录\n【原因】resolve_stored_path 防线失效\n"
        "【修复】检查 is_relative_to 断言"
    )


def test_resolve_stored_path_rejects_traversal(tmp_path: Path) -> None:
    """U3 补充: 直接构造穿越存储名时 resolve_stored_path 必须拒绝。

    参数: tmp_path — 临时目录。返回值: 无。异常: ValidationError — 穿越。
    依赖: app.assets.storage.resolve_stored_path。
    """
    with pytest.raises(ValidationError):
        storage.resolve_stored_path("../escape.png", str(tmp_path))


# ---------------- U4: 流式分块写盘 ----------------


def test_write_stream_chunks_not_whole_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """U4: 写盘按块读取（内存防线），非整文件一次性读入。

    参数: monkeypatch — 缩小 CHUNK_SIZE 便于断言；tmp_path — 临时目录。
    返回值: 无。异常: AssertionError — 读取次数/大小不符。
    依赖: app.assets.storage.write_stream。
    """
    import asyncio

    monkeypatch.setattr(storage, "CHUNK_SIZE", 4)
    upload = FakeUpload(b"x" * 10, "u.png", "image/png")
    dest = tmp_path / "chunk.png"
    asyncio.run(storage.write_stream(upload, dest, 1024))
    assert max(upload.read_calls) <= 4 and dest.read_bytes() == b"x" * 10, (
        f"【问题】读取块序列 {upload.read_calls} 出现超块读取或内容不完整\n"
        f"【原因】write_stream 未按 CHUNK_SIZE={storage.CHUNK_SIZE} 循环读取（整读违反内存约束）\n"
        "【修复】保持 while + read(CHUNK_SIZE) 循环写入（末次空读终止循环为预期）"
    )


# ---------------- U5: 通用资产创建校验 ----------------


@pytest.mark.parametrize(
    ("payload_kwargs", "valid"),
    [
        ({"title": "表情参考", "category": "表情", "attributes": {"强度": 3}}, True),
        ({"title": "x" * 201}, False),
        ({"title": "ok", "attributes": "not-a-dict"}, False),
    ],
    ids=["valid-full", "title-over-length", "attributes-not-dict"],
)
def test_create_general_validation(payload_kwargs: dict, valid: bool) -> None:
    """U5: 通用资产创建载荷校验（等价类：有效全字段 / 无效超长与非 dict attributes）。

    参数: payload_kwargs — 创建载荷；valid — 是否应通过。
    返回值: 无。异常: pydantic.ValidationError — 无效载荷（Pydantic 层 422 前置）。
    依赖: app.assets.schemas.GeneralAssetCreate。
    """
    from pydantic import ValidationError as PydanticValidationError

    if valid:
        payload = GeneralAssetCreate(**payload_kwargs)
        assert payload.title, "有效载荷应可通过"
    else:
        with pytest.raises(PydanticValidationError):
            GeneralAssetCreate(**payload_kwargs)


async def test_create_general_renders_html(store: dict) -> None:
    """U5 补充: 创建通用资产后 HTML 即时渲染且含标题与 attributes 键。

    参数: store — 内存存储夹具。返回值: 无。异常: AssertionError — 渲染缺失。
    依赖: app.assets.service.create_general。
    """
    result = await service.create_general(
        SessionStub(),
        GeneralAssetCreate(
            title="愤怒表情",
            category="表情参考",
            description="皱眉",
            attributes={"类型": "愤怒", "强度": 3},
        ),
    )
    html = store["records"][result.id].html
    assert "愤怒表情" in html and "类型" in html and "表情参考" in html, (
        "【问题】资产 HTML 未包含标题/分类/属性键\n【原因】create_general 未渲染或渲染缺字段\n"
        "【修复】检查 render_general_page 调用与插值"
    )


# ---------------- U6: HTML 渲染（转义 + 图片引用） ----------------


def test_render_general_page_escapes_xss() -> None:
    """U6: 用户输入含 <script> 时必须被转义（XSS 防线）。"""
    from app.assets import rendering

    html = rendering.render_general_page(
        title="<script>alert(1)</script>",
        category="<b>风格</b>",
        description="<img src=x onerror=alert(2)>",
        attributes={"key": "<script>1</script>"},
        images=[],
        generated_at="2026-09-05",
    )
    assert "<script>" not in html and "<img src=x" not in html and "<b>" not in html, (
        "【问题】资产 HTML 未转义用户输入（XSS）\n"
        "【原因】渲染器存在未转义插值\n【修复】所有动态插值经 _esc"
    )
    assert "&lt;script&gt;" in html, "转义后实体应存在"


def test_render_entity_page_escapes_and_orders() -> None:
    """U6 补充: 实体页渲染——名称转义、类型中文化、属性按插入序出现。"""
    from app.assets import rendering

    entity = _entity()
    entity.name = "<b>周兰</b>"
    entity.properties = {"age": 24, "name_first": True, "extra": {"k": "v"}}
    html = rendering.render_entity_page(entity=entity, images=[], generated_at="2026-09-05")
    assert "<b>周兰</b>" not in html and "人物" in html, "实体页须转义并中文化类型"
    assert html.index("age") < html.index("name_first") < html.index("extra"), (
        "【问题】属性渲染未保持插入序\n【原因】渲染器对 dict 重排\n"
        "【修复】按 list(properties.items()) 顺序渲染"
    )


# ---------------- U7: 实体页过期判定（边界值） ----------------


@pytest.mark.parametrize(
    ("record_updated_delta", "image_delta", "expect_regenerate"),
    [
        (None, None, True),  # 无记录 → 生成
        (-10, None, True),  # 实体更新晚于记录 → 过期再生
        (0, None, False),  # 相等时刻 → fresh
        (10, None, False),  # 记录更新晚于实体 → fresh
        (10, 20, True),  # 图片晚于记录 → 过期再生
    ],
    ids=[
        "missing-record-generate",
        "entity-newer-regenerate",
        "equal-fresh",
        "record-newer-fresh",
        "image-newer-regenerate",
    ],
)
async def test_get_entity_page_staleness(
    store: dict, record_updated_delta: int | None, image_delta: int | None, expect_regenerate: bool
) -> None:
    """U7: 实体页惰性生成与过期判定（边界值：相等时刻视为 fresh）。

    参数: record_updated_delta — 记录更新时间相对实体的偏移秒（None=无记录）；
        image_delta — 最新图片时间相对记录的偏移秒；expect_regenerate — 是否应再生。
    返回值: 无。异常: AssertionError — 过期判定不符。
    依赖: app.assets.service.get_entity_page。
    """
    base = datetime.now(UTC)
    entity = _entity(updated_at=base)
    store["state"]["entity"] = entity

    if record_updated_delta is not None:
        record = _record(
            "asset-ent",
            kind="entity",
            entity_id=entity.id,
            updated_at=base + timedelta(seconds=record_updated_delta),
        )
        store["records"][record.id] = record
    if image_delta is not None:
        image = _image(
            "img-ent",
            scope="entity",
            owner_id=entity.id,
            created_at=base + timedelta(seconds=image_delta),
        )
        store["images"][image.id] = image

    html = await service.get_entity_page(SessionStub(), SessionStub(), entity.id)
    if expect_regenerate:
        assert "OLD" not in html and "周兰" in html, (
            "【问题】应再生但返回了旧 HTML 或未含实体名\n"
            "【原因】staleness 判定偏松\n【修复】检查 updated_at/图片时间阈值比较"
        )
    else:
        assert html == "<!doctype html><html>OLD</html>", (
            "【问题】fresh 记录被误再生\n【原因】staleness 判定偏紧（相等时刻应 fresh）\n"
            "【修复】比较使用严格小于"
        )


# ---------------- U8: 孤儿清扫 ----------------


async def test_list_entity_cards_sweeps_orphans(store: dict) -> None:
    """U8: 已删除实体的残留记录与图片被清扫，卡片仅含存活实体。

    参数: store — 内存存储夹具。返回值: 无。异常: AssertionError — 清扫不符。
    依赖: app.assets.service.list_entity_cards。
    """
    live = _entity("char-live")
    store["state"]["entities"] = [live]
    # 存活实体的记录+图片
    store["records"]["asset-live"] = _record("asset-live", kind="entity", entity_id="char-live")
    store["images"]["img-live"] = _image("img-live", scope="entity", owner_id="char-live")
    # 孤儿：实体已删，记录+图片残留
    store["records"]["asset-dead"] = _record("asset-dead", kind="entity", entity_id="char-dead")
    store["images"]["img-dead"] = _image("img-dead", scope="entity", owner_id="char-dead")

    cards = await service.list_entity_cards(SessionStub(), SessionStub())

    assert [c.id for c in cards] == ["char-live"], "卡片应仅含存活实体"
    assert set(store["records"]) == {"asset-live"}, "孤儿记录应被删除"
    assert set(store["images"]) == {"img-live"}, "孤儿图片记录应被删除"
    assert store["deleted"] == ["aa11.png"] or "aa11.png" in store["deleted"], (
        "【问题】孤儿图片物理文件未删除\n【原因】清扫漏调 delete_stored_file\n"
        "【修复】孤儿图片循环内逐个删文件"
    )
    assert cards[0].cover_url == "/api/assets/file/aa11.png", "存活实体封面应回落首图"


# ---------------- U9: 图片删除（文件 + 行 + 封面引用） ----------------


async def test_delete_image_clears_file_row_and_cover(store: dict, tmp_path: Path) -> None:
    """U9: 删除图片同步删物理文件、删记录、清空封面引用。

    参数: store — 内存存储夹具；tmp_path — 临时目录（构造真实文件）。
    返回值: 无。异常: AssertionError — 任一清理缺失。
    依赖: app.assets.service.delete_image。
    """
    record = _record()
    record.cover_image_id = "img-1"
    store["records"][record.id] = record
    image = _image("img-1")
    store["images"]["img-1"] = image
    real_file = Path(_asset_dir(), image.stored_name)
    real_file.parent.mkdir(parents=True, exist_ok=True)
    real_file.write_bytes(b"png")

    await service.delete_image(SessionStub(), "img-1")

    assert not real_file.exists(), "物理文件应被删除"
    assert "img-1" not in store["images"], "图片记录应被删除"
    assert store["records"][record.id].cover_image_id is None, (
        "【问题】封面引用未清空（悬空引用）\n【原因】delete_image 漏 clear_cover_reference\n"
        "【修复】删除前执行引用清理"
    )


# ---------------- U10: 通用资产删除级联 ----------------


async def test_delete_general_cascades_images(store: dict) -> None:
    """U10: 删除通用资产级联删除名下图片记录与文件。

    参数: store — 内存存储夹具。返回值: 无。异常: AssertionError — 级联缺失。
    依赖: app.assets.service.delete_general。
    """
    store["records"]["asset-r1"] = _record()
    store["images"]["img-1"] = _image("img-1", scope="general", owner_id="asset-r1")
    store["images"]["img-other"] = _image("img-other", scope="general", owner_id="asset-other")

    await service.delete_general(SessionStub(), "asset-r1")

    assert "asset-r1" not in store["records"], "资产记录应被删除"
    assert "img-1" not in store["images"], "名下图片应级联删除"
    assert "img-other" in store["images"], "他人图片不应被误删"


# ---------------- U11: 上传实体存在性校验（跨库） ----------------


async def test_upload_image_entity_not_found(store: dict) -> None:
    """U11: 上传实体图片时实体不存在 → NotFoundError（跨库校验经 entities.service）。

    参数: store — 内存存储夹具。返回值: 无。异常: NotFoundError。
    依赖: app.assets.service.upload_image。
    """
    store["state"]["entity"] = None
    upload = FakeUpload(b"png", "a.png", "image/png")
    with pytest.raises(NotFoundError):
        await service.upload_image(
            SessionStub(), SessionStub(), scope="entity", owner_id="char-x", upload=upload
        )


async def test_upload_image_general_auto_cover(store: dict) -> None:
    """U11 补充: 通用资产首图自动成为封面（无显式封面时）。

    参数: store — 内存存储夹具。返回值: 无。异常: AssertionError — 封面未设。
    依赖: app.assets.service.upload_image。
    """
    record = _record()
    store["records"][record.id] = record
    upload = FakeUpload(b"pngdata", "face.png", "image/png")
    result = await service.upload_image(
        SessionStub(), SessionStub(), scope="general", owner_id=record.id, upload=upload
    )
    assert store["records"][record.id].cover_image_id == result.id, (
        "【问题】首图未自动设为封面\n【原因】upload_image 自动封面分支缺失\n"
        "【修复】general 归属且 cover 为空时置首图"
    )
    assert result.url.startswith("/api/assets/file/"), "图片 url 前缀应为 /api/assets/file/"


async def test_upload_image_stores_file_on_disk(store: dict) -> None:
    """U11 补充: 上传后物理文件落盘且存储名与元数据一致。

    参数: store — 内存存储夹具。返回值: 无。异常: AssertionError — 文件缺失。
    依赖: app.assets.service.upload_image。
    """
    record = _record()
    store["records"][record.id] = record
    upload = FakeUpload(b"pngdata", "face.png", "image/png")
    result = await service.upload_image(
        SessionStub(), SessionStub(), scope="general", owner_id=record.id, upload=upload
    )
    on_disk = Path(_asset_dir(), result.stored_name)
    assert on_disk.exists() and on_disk.read_bytes() == b"pngdata", (
        "【问题】上传文件未落盘或内容不符\n【原因】write_stream/路径解析错误\n"
        "【修复】检查 dest 解析与写入"
    )


# ---------------- 通用资产更新与删除补充（U5/U10 链路） ----------------


async def test_update_general_rewrites_html(store: dict) -> None:
    """U5 补充: 更新后 HTML 反映新标题/attributes（重渲染）。"""
    record = _record()
    store["records"][record.id] = record
    result = await service.update_general(
        SessionStub(),
        record.id,
        GeneralAssetUpdate(title="平静表情", attributes={"强度": 1}),
    )
    html = store["records"][record.id].html
    assert result.title == "平静表情" and "平静表情" in html and "强度" in html, (
        "【问题】更新后 HTML 未反映新值\n【原因】update_general 未重渲染\n"
        "【修复】更新路径重调 render_general_page"
    )


async def test_get_general_page_not_found(store: dict) -> None:
    """U5 补充: 读取不存在资产的页面 → NotFoundError（三要素）。"""
    with pytest.raises(NotFoundError) as exc_info:
        await service.get_general_page(SessionStub(), "asset-ghost")
    assert exc_info.value.problem and exc_info.value.cause and exc_info.value.fix, (
        "【问题】NotFoundError 三要素缺失\n【原因】异常构造不完整\n【修复】补全三要素"
    )


# ---------------- 契约钉死（E05：错误文案精确相等；常量/约束钉死击杀声明类变异） ----------------


def test_orm_non_nullable_columns_pinned() -> None:
    """钉死 ORM 列 nullable 声明（除设计允许为空的两列外全部 NOT NULL）。"""
    from app.assets.models import AssetImage, AssetRecord

    nullable_allow = {"entity_id", "cover_image_id"}
    for model in (AssetRecord, AssetImage):
        for column in model.__table__.columns:
            expected = column.name in nullable_allow
            assert column.nullable == expected, (
                f"【问题】{model.__tablename__}.{column.name} nullable 声明漂移: "
                f"{column.nullable} != {expected}\n【原因】ORM 列约束被改动\n"
                "【修复】对照 docs/data_struct_define.md §10 恢复列声明"
            )


def test_table_names_and_columns_pinned() -> None:
    """钉死表名与列名（物理 schema 契约，create_all/查询自洽但外部可见）。"""
    assert AssetRecord.__tablename__ == "asset_records"
    assert AssetImage.__tablename__ == "asset_images"
    assert [c.name for c in AssetRecord.__table__.columns] == [
        "id",
        "kind",
        "entity_id",
        "category",
        "title",
        "description",
        "attributes",
        "html",
        "cover_image_id",
        "created_at",
        "updated_at",
    ]
    assert [c.name for c in AssetImage.__table__.columns] == [
        "id",
        "scope",
        "owner_id",
        "filename_orig",
        "stored_name",
        "mime",
        "size",
        "created_at",
    ]


def test_kind_scope_literals_and_order_pinned() -> None:
    """钉死资产种类/归属面 Literal 与实体类型序（枚举值即校验集合，禁止漂移）。"""
    from typing import get_args

    from app.assets.schemas import (
        ENTITY_TYPE_LABELS,
        ENTITY_TYPE_ORDER,
        AssetKind,
        AssetScope,
    )

    assert get_args(AssetKind) == ("general", "entity")
    assert get_args(AssetScope) == ("general", "entity")
    assert ENTITY_TYPE_ORDER == (
        "character",
        "faction",
        "location",
        "item",
        "skill",
        "event",
        "concept",
    )
    assert ENTITY_TYPE_LABELS == {
        "character": "人物",
        "faction": "门派",
        "location": "地点",
        "item": "物件",
        "skill": "功法",
        "event": "事件",
        "concept": "概念",
    }


def test_id_formats_pinned() -> None:
    """钉死 id 前缀与长度（asset-/img- + 12 位 hex）。"""
    import re

    from app.assets.schemas import generate_asset_id, generate_image_id

    assert re.fullmatch(r"asset-[0-9a-f]{12}", generate_asset_id())
    assert re.fullmatch(r"img-[0-9a-f]{12}", generate_image_id())


def test_image_url_and_cover_builder_pinned() -> None:
    """钉死图片规范地址前缀与封面回落顺序（/api 同源路由契约）。"""
    from app.assets.schemas import AssetImageRead

    record = _record()
    first = _image("img-a", stored_name="aaa.png")
    second = _image("img-b", stored_name="bbb.png")
    read = AssetImageRead.model_validate(first)
    assert read.url == "/api/assets/file/aaa.png", "图片规范地址前缀必须为 /api/assets/file/"
    assert service._cover_url(None, []) is None
    assert service._cover_url(None, [first, second]) == "/api/assets/file/aaa.png", (
        "无显式封面应回落首图（第一张图自动为封面）"
    )
    record.cover_image_id = "img-b"
    assert service._cover_url(record, [first, second]) == "/api/assets/file/bbb.png", (
        "显式封面优先于首图"
    )
    record.cover_image_id = "img-ghost"
    assert service._cover_url(record, [first, second]) == "/api/assets/file/aaa.png", (
        "封面指向缺失图片时回落首图"
    )


def test_chunk_size_pinned() -> None:
    """钉死流式块大小（内存防线参数：1MB）。"""
    assert storage.CHUNK_SIZE == 1024 * 1024


def test_db_sqlite_prefix_and_pragma_pinned() -> None:
    """钉死资产库连接串前缀与 WAL PRAGMA（连接基础设施契约）。"""
    from app.assets import db as assets_db

    assert assets_db._SQLITE_PREFIX == "sqlite+aiosqlite:///"

    executed: list[str] = []

    class CursorStub:
        def execute(self, sql: str) -> None:
            executed.append(sql)

        def close(self) -> None:
            return None

    class ConnStub:
        def cursor(self) -> CursorStub:
            return CursorStub()

    assets_db._set_sqlite_pragma(ConnStub(), None)
    assert executed == ["PRAGMA journal_mode=WAL"], (
        f"【问题】资产库连接 PRAGMA 漂移: {executed}\n【原因】WAL 约束语句被改动\n"
        "【修复】恢复 PRAGMA journal_mode=WAL"
    )


def test_error_messages_pinned_exact() -> None:
    """E05 范式：错误三要素文案精确相等 + detail 字典整体相等（文案是响应体行为契约）。"""
    err = service._not_found_asset("a1")
    assert (err.problem, err.cause, err.fix) == (
        "资产不存在",
        "id 'a1' 未在资产库中",
        "先调用 GET /api/assets/general 确认资产 id",
    )
    assert err.detail == {"asset_id": "a1"}

    err = service._not_found_image("i1")
    assert (err.problem, err.cause, err.fix) == (
        "图片不存在",
        "id 'i1' 未在资产库中",
        "先调用 GET /api/assets/general/{id} 确认图片归属",
    )
    assert err.detail == {"image_id": "i1"}

    err = storage.not_found("x.png")
    assert (err.problem, err.cause, err.fix) == (
        "图片文件不存在",
        "存储名 'x.png' 对应的文件不在资产目录中",
        "确认文件未被手动删除，或重新上传图片",
    )
    assert err.detail == {"stored_name": "x.png"}


def test_upload_validation_messages_pinned_exact() -> None:
    """E05 范式：上传校验错误文案与 detail 精确相等（含大小上限换算）。"""
    allowed = get_settings().asset_allowed_type_list
    with pytest.raises(ValidationError) as exc_info:
        storage.validate_upload(
            filename="a.png",
            content_type="text/plain",
            max_size_bytes=10 * 1024 * 1024,
            allowed_extensions=allowed,
        )
    err = exc_info.value
    assert err.problem == "上传文件类型不被接受"
    assert err.cause == "仅接受图片（MIME 需以 image/ 开头），实际收到 'text/plain'"
    assert err.fix == f"请上传图片文件，支持格式：{', '.join(allowed)}"
    assert err.detail == {"content_type": "text/plain"}

    with pytest.raises(ValidationError) as exc_info:
        storage.validate_upload(
            filename="a.exe",
            content_type="image/png",
            max_size_bytes=10 * 1024 * 1024,
            allowed_extensions=allowed,
        )
    err = exc_info.value
    assert err.problem == "上传文件扩展名不在白名单"
    assert err.cause == (f"扩展名 'exe' 不在允许列表 [{', '.join(allowed)}] 内")
    assert err.fix == f"请上传白名单内的图片格式：{', '.join(allowed)}"
    assert err.detail == {"extension": "exe", "allowed": allowed}


def test_write_stream_overflow_message_pinned(tmp_path: Path) -> None:
    """E05 范式：超限错误三要素精确相等 + 半成品文件清理。"""
    import asyncio

    dest = tmp_path / "over.png"
    upload = FakeUpload(b"x" * 6, "over.png", "image/png")
    with pytest.raises(ValidationError) as exc_info:
        asyncio.run(storage.write_stream(upload, dest, 5))
    err = exc_info.value
    assert err.problem == "上传文件超过大小上限"
    assert err.cause == "写入累计 6 字节，超过上限 5 字节"
    assert err.fix == "压缩或裁剪文件至 0MB 以内后重试"
    assert err.detail == {"written": 6, "max_size_bytes": 5}
    assert not dest.exists(), "超限后半成品文件必须清理"


def test_resolve_path_messages_pinned(tmp_path: Path) -> None:
    """E05 范式：路径防线错误文案精确相等。"""
    with pytest.raises(ValidationError) as exc_dir:
        storage.resolve_stored_path("a/b.png", str(tmp_path))
    assert exc_dir.value.problem == "资产存储名非法"
    assert exc_dir.value.cause == "存储名 'a/b.png' 含目录成分或相对路径片段"
    assert exc_dir.value.fix == (
        "存储名只能来自库内 asset_images.stored_name（uuid.ext），禁止拼接用户输入"
    )
    assert exc_dir.value.detail == {"stored_name": "a/b.png"}


def test_general_schema_bounds_pinned() -> None:
    """schemas 数值边界钉死（category 100 / description 20000 / title 200）。"""
    from pydantic import ValidationError as PydanticValidationError

    assert GeneralAssetCreate(title="t" * 200).title == "t" * 200
    with pytest.raises(PydanticValidationError):
        GeneralAssetCreate(title="t" * 201)
    assert GeneralAssetCreate(title="t", category="c" * 100).category == "c" * 100
    with pytest.raises(PydanticValidationError):
        GeneralAssetCreate(title="t", category="c" * 101)
    assert GeneralAssetCreate(title="t", description="d" * 20000).description == "d" * 20000
    with pytest.raises(PydanticValidationError):
        GeneralAssetCreate(title="t", description="d" * 20001)


def test_service_public_functions_checkpointed() -> None:
    """钉死关键 service 路径的 @checkpoint 标注（backend/CONSTRAINTS 观测性约束）。"""
    import inspect

    public_fns = [
        obj
        for name, obj in vars(service).items()
        if inspect.iscoroutinefunction(obj)
        and not name.startswith("_")
        and obj.__module__ == service.__name__
    ]
    assert public_fns, "service 公共 async 函数应存在"
    not_wrapped = [fn.__name__ for fn in public_fns if not hasattr(fn, "__wrapped__")]
    assert not not_wrapped, (
        f"【问题】以下 service 公共函数缺少 @checkpoint 标注: {not_wrapped}\n"
        "【原因】关键路径未接入信号采集（backend/CONSTRAINTS.md）\n"
        "【修复】为对应函数加 @checkpoint 装饰器"
    )


def test_router_prefix_and_tag_pinned() -> None:
    """钉死路由前缀与 tags（OpenAPI 契约，check-api-types 链的稳定锚点）。"""
    from app.assets.router import router

    assert router.prefix == "/api/assets"
    assert router.tags == ["assets"]


def test_set_cover_mismatch_message_pinned(store: dict) -> None:
    """E05 范式：封面归属不符错误三要素精确相等。"""
    record = _record()
    store["records"][record.id] = record
    store["images"]["img-other-asset"] = _image(
        "img-other-asset", scope="general", owner_id="asset-r2"
    )
    with pytest.raises(ValidationError) as exc_info:
        await_err = service.set_cover(SessionStub(), record.id, "img-other-asset")
        import asyncio

        asyncio.run(await_err)
    err = exc_info.value
    assert err.problem == "封面图片归属不符"
    assert err.cause == f"图片 'img-other-asset' 不属于资产 '{record.id}'"
    assert err.fix == "请先上传该资产名下的图片，再从其图片列表中选择封面"
    assert err.detail == {"asset_id": record.id, "image_id": "img-other-asset"}


# ---------------- 第二批击杀测试（models DDL / 存储边界 / 路由契约 / 服务分支） ----------------


def test_models_column_ddl_pinned() -> None:
    """钉死列 DDL 细节（类型/索引/唯一/默认值——物理 schema 契约）。"""
    from app.assets.models import AssetImage, AssetRecord

    r, i = AssetRecord.__table__, AssetImage.__table__
    # 索引列
    for col in ("kind", "entity_id"):
        assert r.c[col].index is True, f"asset_records.{col} 应有索引"
    for col in ("scope", "owner_id"):
        assert i.c[col].index is True, f"asset_images.{col} 应有索引"
    # 唯一列
    assert i.c["stored_name"].unique is True
    # 类型（Text 长文本 vs String）
    assert "TEXT" in str(r.c["html"].type).upper()
    assert "TEXT" in str(r.c["description"].type).upper()
    assert "VARCHAR" in str(r.c["title"].type).upper() or "TEXT" in str(r.c["title"].type).upper()
    assert "INT" in str(i.c["size"].type).upper()
    # 默认值
    for col in ("category", "description"):
        assert r.c[col].default is not None and r.c[col].default.arg == ""
    assert r.c["attributes"].default is not None
    for col in ("created_at", "updated_at"):
        assert r.c[col].default is not None and callable(r.c[col].default.arg)
    assert r.c["updated_at"].onupdate is not None, "updated_at 应有 onupdate 刷新"
    assert r.c["created_at"].onupdate is None, "created_at 不应有 onupdate"
    assert i.c["created_at"].default is not None


def test_ensure_assets_dir_behavior(tmp_path: Path) -> None:
    """ensure_assets_dir：普通路径建父目录；:memory: 不建任何目录。"""
    from app.assets.db import ensure_assets_dir

    target = tmp_path / "nested" / "assets.db"
    ensure_assets_dir(f"sqlite+aiosqlite:///{target.as_posix()}")
    assert target.parent.is_dir(), "普通路径应自动建父目录"

    before = {p.name for p in tmp_path.rglob("*")}
    ensure_assets_dir("sqlite+aiosqlite:///:memory:")
    assert {p.name for p in tmp_path.rglob("*")} == before, ":memory: 不应触发建目录"


@pytest.mark.parametrize(
    "filename", ["B.PNG", "photo.JPG", "pic.WebP"], ids=["png-upper", "jpg-upper", "webp-mixed"]
)
def test_ext_normalization_case_insensitive(filename: str) -> None:
    """扩展名归一化大小写不敏感（.lower 契约）。"""
    allowed = get_settings().asset_allowed_type_list
    ext = storage.validate_upload(
        filename=filename,
        content_type="image/png",
        max_size_bytes=1024,
        allowed_extensions=allowed,
    )
    assert ext == filename.rsplit(".", 1)[-1].lower()


def test_validate_upload_missing_ext_message_pinned() -> None:
    """无扩展名上传的错误文案钉死（'(缺失)' 回退分支）。"""
    allowed = get_settings().asset_allowed_type_list
    with pytest.raises(ValidationError) as exc_info:
        storage.validate_upload(
            filename="noext",
            content_type="image/png",
            max_size_bytes=1024,
            allowed_extensions=allowed,
        )
    assert exc_info.value.cause == (f"扩展名 '(缺失)' 不在允许列表 [{', '.join(allowed)}] 内")


def test_resolve_path_dotdot_inside_name_rejected(tmp_path: Path) -> None:
    """存储名内嵌 `..`（合法路径成分但属脏数据）必须被拒绝。"""
    with pytest.raises(ValidationError):
        storage.resolve_stored_path("a..b.png", str(tmp_path))


async def test_staleness_image_equal_boundary(store: dict) -> None:
    """U7 补充（边界值）：图片时间 == 记录时间 → fresh（严格大于才再生）。"""
    from datetime import UTC, datetime

    base = datetime.now(UTC)
    entity = _entity(updated_at=base)
    store["state"]["entity"] = entity
    record = _record("asset-ent", kind="entity", entity_id=entity.id, updated_at=base)
    store["records"][record.id] = record
    image = _image("img-ent", scope="entity", owner_id=entity.id, created_at=base)
    store["images"]["img-ent"] = image

    html = await service.get_entity_page(SessionStub(), SessionStub(), entity.id)
    assert html == "<!doctype html><html>OLD</html>", (
        "图片时间等于记录时间应判 fresh（阈值比较为严格大于）"
    )


async def test_orphan_sweep_union_semantics(store: dict) -> None:
    """U8 补充：仅记录残留 / 仅图片残留两类孤儿都必须被清扫（并集语义）。"""
    live = _entity("char-live")
    store["state"]["entities"] = [live]
    # 孤儿 A：仅记录（页面生成后图片全删）
    store["records"]["asset-dead-a"] = _record(
        "asset-dead-a", kind="entity", entity_id="char-dead-a"
    )
    # 孤儿 B：仅图片（传图后未生成页面）
    store["images"]["img-dead-b"] = _image("img-dead-b", scope="entity", owner_id="char-dead-b")

    cards = await service.list_entity_cards(SessionStub(), SessionStub())
    assert [c.id for c in cards] == ["char-live"], "卡片仅含存活实体"
    assert "asset-dead-a" not in store["records"], "仅记录残留的孤儿应被清扫"
    assert "img-dead-b" not in store["images"], "仅图片残留的孤儿应被清扫"


async def test_set_cover_wrong_kind_record_rejected(store: dict) -> None:
    """wrong-kind 防护（service 层）：entity 页记录不可作为通用资产操作目标。"""
    entity_record = _record("asset-ent", kind="entity", entity_id="char-e1")
    store["records"][entity_record.id] = entity_record
    with pytest.raises(NotFoundError):
        await service.update_general(SessionStub(), entity_record.id, GeneralAssetUpdate(title="x"))
    with pytest.raises(NotFoundError):
        await service.get_general(SessionStub(), entity_record.id)
    with pytest.raises(NotFoundError):
        await service.delete_general(SessionStub(), entity_record.id)
    with pytest.raises(NotFoundError):
        await service.get_general_page(SessionStub(), entity_record.id)


async def test_upload_general_owner_wrong_kind_rejected(store: dict) -> None:
    """wrong-kind 防护：scope=general 上传的 owner 是 entity 页记录 → NotFound。"""
    entity_record = _record("asset-ent", kind="entity", entity_id="char-e1")
    store["records"][entity_record.id] = entity_record
    upload = FakeUpload(b"png", "a.png", "image/png")
    with pytest.raises(NotFoundError):
        await service.upload_image(
            SessionStub(), SessionStub(), scope="general", owner_id=entity_record.id, upload=upload
        )


def test_generated_at_format_pinned() -> None:
    """页面生成时间戳格式钉死（strftime 契约）。"""
    from app.assets import rendering

    html = rendering.render_general_page(
        title="t",
        category="",
        description="",
        attributes={},
        images=[],
        generated_at="2026-09-05 10:08 UTC",
    )
    assert "生成于 2026-09-05 10:08 UTC" in html


def test_router_routes_pinned() -> None:
    """钉死路由注册面（方法+路径；防装饰器删除/status_code 漂移）。"""
    from app.assets.router import router

    paths = {r.path for r in router.routes}
    assert "/api/assets/images" in paths
    assert "/api/assets/images/{image_id}" in paths
    assert "/api/assets/general" in paths
    assert "/api/assets/general/{asset_id}" in paths
    assert "/api/assets/general/{asset_id}/page" in paths
    assert "/api/assets/general/{asset_id}/cover" in paths
    assert "/api/assets/entities" in paths
    assert "/api/assets/entity/{entity_id}/page" in paths
    assert "/api/assets/file/{stored_name}" in paths
    delete_route = next(
        r
        for r in router.routes
        if r.path == "/api/assets/images/{image_id}" and "DELETE" in r.methods
    )
    assert delete_route.status_code == 204
    del_asset = next(
        r
        for r in router.routes
        if r.path == "/api/assets/general/{asset_id}" and "DELETE" in r.methods
    )
    assert del_asset.status_code == 204
