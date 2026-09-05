"""assets 模块 service 层：模块唯一对外接口（其他模块只允许 import 本层）。

事务边界: 本层自行 commit（backend/CONSTRAINTS.md「模块解耦与事务」）。
依赖方向: assets → entities 单向（经 entities.service）；实体删除的资产清理
    走读取时孤儿清扫（list_entity_cards），禁止实体写路径回调（DECISIONS 2026-09-05）。
双库约定: 参数名 session = 资产库会话（assets.db）；main_session = 主库会话（app.db）。
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.assets import db as assets_db
from app.assets import rendering, repository, storage
from app.assets.models import AssetImage, AssetRecord
from app.assets.schemas import (
    ENTITY_TYPE_ORDER,
    AssetCard,
    AssetImageRead,
    AssetRead,
    EntityAssetCard,
    GeneralAssetCreate,
    GeneralAssetUpdate,
    generate_asset_id,
    generate_image_id,
)
from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.entities import service as entities_service


def _not_found_asset(asset_id: str) -> NotFoundError:
    """构造通用资产不存在的三要素异常。

    作用: 统一 NotFoundError 消息质量。
    参数: asset_id — 资产 id。返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="资产不存在",
        cause=f"id '{asset_id}' 未在资产库中",
        fix="先调用 GET /api/assets/general 确认资产 id",
        detail={"asset_id": asset_id},
    )


def _not_found_image(image_id: str) -> NotFoundError:
    """构造图片不存在的三要素异常。

    作用: 统一 NotFoundError 消息质量。
    参数: image_id — 图片 id。返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="图片不存在",
        cause=f"id '{image_id}' 未在资产库中",
        fix="先调用 GET /api/assets/general/{id} 确认图片归属",
        detail={"image_id": image_id},
    )


def _now() -> datetime:
    """当前 UTC 时间（时间源统一出口，便于测试桩替换）。

    作用: 创建/更新时间戳。
    参数: 无。返回值: UTC aware datetime。异常: 无。依赖: 无。
    """
    return datetime.now(UTC)


@checkpoint
async def init_database() -> None:
    """资产库建表引导（应用启动组合根入口）。

    作用: main lifespan 经 service 层转发 db.init_assets_db——组合根禁止
        import 模块内部层（import-linter assets 契约），故在此收口。
    参数: 无。返回值: 无。异常: 无（DB 错误由全局异常处理器兜底）。
    依赖: app.assets.db。
    """
    await assets_db.init_assets_db()


@checkpoint
async def shutdown_engine() -> None:
    """释放资产库引擎（应用停机组合根入口）。

    作用: main lifespan 停机时释放资产库连接池（转发 db.dispose_assets_engine）。
    参数: 无。返回值: 无。异常: 无。依赖: app.assets.db。
    """
    await assets_db.dispose_assets_engine()


def _cover_url(record: AssetRecord | None, images: list[AssetImage]) -> str | None:
    """计算封面 url（显式封面优先，缺省回落首图——第一张图自动为封面）。

    作用: 卡片与详情响应的封面推导（assets 无封面记录时不展示缩略图）。
    参数: record — 资产记录（可空）；images — 该资产图片列表（创建时间升序）。
    返回值: str | None。异常: 无。依赖: 无。
    """
    if record is not None and record.cover_image_id is not None:
        for image in images:
            if image.id == record.cover_image_id:
                return f"/api/assets/file/{image.stored_name}"
    if images:
        return f"/api/assets/file/{images[0].stored_name}"
    return None


def _asset_read(record: AssetRecord, images: list[AssetImage]) -> AssetRead:
    """装配通用资产完整响应（含图片明细与封面）。

    作用: 创建/更新/详情的响应装配。
    参数: record — 资产记录；images — 图片列表（升序）。
    返回值: AssetRead。异常: 无。依赖: app.assets.schemas。
    """
    image_reads = [AssetImageRead.model_validate(img) for img in images]
    return AssetRead(
        id=record.id,
        kind="general",
        category=record.category,
        title=record.title,
        description=record.description,
        attributes=dict(record.attributes),
        cover_image_id=record.cover_image_id,
        cover_url=_cover_url(record, images),
        images=image_reads,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@checkpoint
async def upload_image(
    session: AsyncSession,
    main_session: AsyncSession,
    *,
    scope: str,
    owner_id: str,
    upload: Any,
) -> AssetImageRead:
    """上传图片（白名单/上限校验 → uuid 重命名 → 流式写盘 → 元数据入库）。

    作用:
        图片上传唯一业务入口。scope='entity' 时经 entities.service 校验实体存在
        （跨库校验）；scope='general' 时校验通用资产存在；首个上传图自动成为封面。
    参数:
        session — 资产库会话；main_session — 主库会话（实体存在性校验）；
        scope — 'general' | 'entity'；owner_id — 归属 id；upload — 上传对象（read 协议）。
    返回值: AssetImageRead。
    异常: NotFoundError — 归属对象不存在；ValidationError — 类型/大小校验失败。
    依赖: storage、repository、entities.service、app.config。
    """
    settings = get_settings()
    ext = storage.validate_upload(
        filename=upload.filename or "",
        content_type=upload.content_type or "",
        max_size_bytes=settings.asset_max_size_mb * 1024 * 1024,
        allowed_extensions=settings.asset_allowed_type_list,
    )
    if scope == "entity":
        await entities_service.get(main_session, owner_id)  # 不存在即 NotFound
    else:
        record = await repository.get_record(session, owner_id)
        if record is None or record.kind != "general":
            raise _not_found_asset(owner_id)

    stored_name = storage.build_stored_name(ext)
    dest = storage.resolve_stored_path(stored_name, settings.asset_dir)
    Path(settings.asset_dir).mkdir(parents=True, exist_ok=True)
    size = await storage.write_stream(upload, dest, settings.asset_max_size_mb * 1024 * 1024)

    now = _now()
    image = await repository.add_image(
        session,
        repository.new_image(
            image_id=generate_image_id(),
            scope=scope,
            owner_id=owner_id,
            filename_orig=upload.filename or stored_name,
            stored_name=stored_name,
            mime=upload.content_type or "application/octet-stream",
            size=size,
            now=now,
        ),
    )
    if scope == "general":
        record = await repository.get_record(session, owner_id)
        if record is not None and record.cover_image_id is None:
            record.cover_image_id = image.id
    await session.commit()
    return AssetImageRead.model_validate(image)


@checkpoint
async def list_images(session: AsyncSession, *, scope: str, owner_id: str) -> list[AssetImageRead]:
    """图片明细列表（按归属；实体详情面板图片区数据源）。

    作用: 单个归属对象的全部图片元数据（创建时间升序）。
    参数: session — 资产库会话；scope — 'general' | 'entity'；owner_id — 归属 id。
    返回值: list[AssetImageRead]。异常: 无。
    依赖: repository。
    """
    images = await repository.list_images(session, scope, owner_id)
    return [AssetImageRead.model_validate(img) for img in images]


@checkpoint
async def get_image_file(session: AsyncSession, stored_name: str) -> Path:
    """解析图片物理文件路径（图片访问路由的数据源）。

    作用: /api/assets/file/{stored_name} 的取数入口——路径经穿越防线解析，
        文件缺失返回 404 三要素；mime 由 FileResponse 按扩展名推断。
    参数: session — 资产库会话（预留：按需校验存储名登记状态）；stored_name — 存储名。
    返回值: Path — 物理文件路径。异常: NotFoundError — 文件不存在。
    依赖: storage、app.config。
    """
    path = storage.resolve_stored_path(stored_name, get_settings().asset_dir)
    if not path.exists():
        raise storage.not_found(stored_name)
    return path


@checkpoint
async def delete_image(session: AsyncSession, image_id: str) -> None:
    """删除图片（记录 + 物理文件 + 封面引用清空）。

    作用: 图片删除业务入口；任何记录的封面指向该图时一并置空。
    参数: session — 资产库会话；image_id — 图片 id。返回值: 无。
    异常: NotFoundError — 图片不存在。
    依赖: repository、storage、app.config。
    """
    image = await repository.get_image(session, image_id)
    if image is None:
        raise _not_found_image(image_id)
    storage.delete_stored_file(image.stored_name, get_settings().asset_dir)
    await repository.clear_cover_reference(session, image_id)
    await repository.delete_image(session, image)
    await session.commit()


@checkpoint
async def set_cover(session: AsyncSession, asset_id: str, image_id: str) -> AssetRead:
    """设置通用资产封面（图片必须归属该资产）。

    作用: 卡片缩略图的人工指定入口。
    参数: session — 资产库会话；asset_id — 资产 id；image_id — 图片 id。
    返回值: AssetRead（更新后状态）。
    异常: NotFoundError — 资产或图片不存在；ValidationError — 图片不归属该资产。
    依赖: repository。
    """
    record = await repository.get_record(session, asset_id)
    if record is None or record.kind != "general":
        raise _not_found_asset(asset_id)
    image = await repository.get_image(session, image_id)
    if image is None:
        raise _not_found_image(image_id)
    if image.scope != "general" or image.owner_id != asset_id:
        raise ValidationError(
            problem="封面图片归属不符",
            cause=f"图片 '{image_id}' 不属于资产 '{asset_id}'",
            fix="请先上传该资产名下的图片，再从其图片列表中选择封面",
            detail={"asset_id": asset_id, "image_id": image_id},
        )
    record.cover_image_id = image_id
    record = await repository.save_record(session, record)
    images = await repository.list_images(session, "general", asset_id)
    await session.commit()
    return _asset_read(record, images)


@checkpoint
async def create_general(session: AsyncSession, payload: GeneralAssetCreate) -> AssetRead:
    """创建通用资产（基础字段 + attributes 自由属性 → 模板渲染 HTML 存库）。

    作用: 通用资产业务入口；HTML 即存即渲（后续更新时重渲）。
    参数: session — 资产库会话；payload — 创建载荷。
    返回值: AssetRead（含生成的 id 与时间戳）。
    异常: ValidationError — 字段校验失败（Pydantic 层前置，此处兜底）。
    依赖: repository、rendering。
    """
    now = _now()
    record = await repository.add_record(
        session,
        repository.new_record(
            record_id=generate_asset_id(),
            kind="general",
            entity_id=None,
            category=payload.category,
            title=payload.title,
            description=payload.description,
            attributes=dict(payload.attributes),
            html=rendering.render_general_page(
                title=payload.title,
                category=payload.category,
                description=payload.description,
                attributes=payload.attributes,
                images=[],
                generated_at=now.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            ),
            now=now,
        ),
    )
    await session.commit()
    return _asset_read(record, [])


@checkpoint
async def update_general(
    session: AsyncSession, asset_id: str, payload: GeneralAssetUpdate
) -> AssetRead:
    """局部更新通用资产（仅显式字段；更新后重渲染 HTML）。

    作用: 通用资产编辑入口；attributes 为整体替换语义。
    参数: session — 资产库会话；asset_id — 资产 id；payload — 更新载荷。
    返回值: AssetRead（更新后状态）。
    异常: NotFoundError — 资产不存在。
    依赖: repository、rendering。
    """
    record = await repository.get_record(session, asset_id)
    if record is None or record.kind != "general":
        raise _not_found_asset(asset_id)

    if payload.category is not None:
        record.category = payload.category
    if payload.title is not None:
        record.title = payload.title
    if payload.description is not None:
        record.description = payload.description
    if payload.attributes is not None:
        record.attributes = dict(payload.attributes)

    record.updated_at = _now()
    images = await repository.list_images(session, "general", asset_id)
    record.html = rendering.render_general_page(
        title=record.title,
        category=record.category,
        description=record.description,
        attributes=dict(record.attributes),
        images=[AssetImageRead.model_validate(img) for img in images],
        generated_at=record.updated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    record = await repository.save_record(session, record)
    await session.commit()
    return _asset_read(record, images)


@checkpoint
async def delete_general(session: AsyncSession, asset_id: str) -> None:
    """删除通用资产（级联删除其图片记录与物理文件）。

    作用: 通用资产删除入口。
    参数: session — 资产库会话；asset_id — 资产 id。返回值: 无。
    异常: NotFoundError — 资产不存在。
    依赖: repository、storage、app.config。
    """
    record = await repository.get_record(session, asset_id)
    if record is None or record.kind != "general":
        raise _not_found_asset(asset_id)
    asset_dir = get_settings().asset_dir
    for image in await repository.list_images(session, "general", asset_id):
        storage.delete_stored_file(image.stored_name, asset_dir)
        await repository.delete_image(session, image)
    await repository.delete_record(session, record)
    await session.commit()


@checkpoint
async def list_general(session: AsyncSession, category: str | None = None) -> list[AssetCard]:
    """通用资产卡片列表（可按分类过滤）。

    作用: 资产管理页通用资产区数据源。
    参数: session — 资产库会话；category — 分类过滤（可空）。
    返回值: list[AssetCard]（updated_at 降序）。
    异常: 无。依赖: repository。
    """
    records = await repository.list_records(session, kind="general", category=category)
    images_by_owner = await repository.list_images_for_owners(
        session, "general", [r.id for r in records]
    )
    return [
        AssetCard(
            id=r.id,
            category=r.category,
            title=r.title,
            description=r.description,
            cover_url=_cover_url(r, images_by_owner.get(r.id, [])),
            image_count=len(images_by_owner.get(r.id, [])),
            updated_at=r.updated_at,
        )
        for r in records
    ]


@checkpoint
async def get_general(session: AsyncSession, asset_id: str) -> AssetRead:
    """读取通用资产详情（含图片明细与封面）。

    作用: 编辑表单/卡片进入编辑态的完整数据源（列表只有摘要）。
    参数: session — 资产库会话；asset_id — 资产 id。返回值: AssetRead。
    异常: NotFoundError — 资产不存在或非通用资产。
    依赖: repository。
    """
    record = await repository.get_record(session, asset_id)
    if record is None or record.kind != "general":
        raise _not_found_asset(asset_id)
    images = await repository.list_images(session, "general", asset_id)
    return _asset_read(record, images)


@checkpoint
async def get_general_page(session: AsyncSession, asset_id: str) -> str:
    """读取通用资产 HTML 页全文。

    作用: 内嵌查看器数据源（text/html）。
    参数: session — 资产库会话；asset_id — 资产 id。返回值: str — HTML 全文。
    异常: NotFoundError — 资产不存在或非通用资产。
    依赖: repository。
    """
    record = await repository.get_record(session, asset_id)
    if record is None or record.kind != "general":
        raise _not_found_asset(asset_id)
    return record.html


@checkpoint
async def list_entity_cards(
    session: AsyncSession, main_session: AsyncSession
) -> list[EntityAssetCard]:
    """项目资产卡片列表（主库实体按类型分组；调用时先孤儿清扫）。

    作用:
        资产管理页项目资产区数据源：实体来自 entities.service（跨库聚合），
        封面/计数来自资产库；实体已删除的残留记录与图片文件在此清扫
        （读取时孤儿清扫——实体写路径零回调，DECISIONS 2026-09-05）。
    参数: session — 资产库会话；main_session — 主库会话。
    返回值: list[EntityAssetCard]（按类型序 + 名称序）。
    异常: 无。
    依赖: entities.service、repository、storage、app.config。
    """
    entities = await entities_service.list_all(main_session)
    live_ids = [e.id for e in entities]

    records = await repository.list_records(session, kind="entity")
    record_by_eid = {r.entity_id: r for r in records if r.entity_id is not None}
    # 图片取数须覆盖「存活 + 记录残留」的归属并集：孤儿图片不进查询就永远无法被清扫
    all_owner_ids = sorted({*live_ids, *(eid for eid in record_by_eid if eid is not None)})
    images_by_owner = await repository.list_images_for_owners(session, "entity", all_owner_ids)

    # —— 孤儿清扫：实体已删除的记录/图片（记录+文件）即时清理 ——
    asset_dir = get_settings().asset_dir
    orphan_owners = (set(record_by_eid) | set(images_by_owner)) - set(live_ids)
    for owner_id in sorted(orphan_owners):
        for image in images_by_owner.get(owner_id, []):
            storage.delete_stored_file(image.stored_name, asset_dir)
            await repository.delete_image(session, image)
        record = record_by_eid.get(owner_id)
        if record is not None:
            await repository.delete_record(session, record)
    if orphan_owners:
        await session.commit()

    # —— 卡片装配：仅存活实体，按类型序 + 名称序 ——
    order = {t: i for i, t in enumerate(ENTITY_TYPE_ORDER)}
    cards: list[EntityAssetCard] = []
    for entity in entities:
        images = images_by_owner.get(entity.id, [])
        cover = _cover_url(record_by_eid.get(entity.id), images)
        cards.append(
            EntityAssetCard(
                id=entity.id,
                type=entity.type,
                name=entity.name,
                description=entity.description,
                cover_url=cover,
                image_count=len(images),
            )
        )
    cards.sort(key=lambda c: (order.get(c.type, len(ENTITY_TYPE_ORDER)), c.name))
    return cards


@checkpoint
async def get_entity_page(session: AsyncSession, main_session: AsyncSession, entity_id: str) -> str:
    """实体资产页惰性生成/过期再生并返回 HTML 全文。

    作用:
        内嵌查看器数据源：无记录即生成；entity.updated_at 或最新图片时间
        晚于记录更新时间即判定过期再生（assets/CONSTRAINTS.md 惰性生成约束）。
    参数: session — 资产库会话；main_session — 主库会话；entity_id — 实体 id。
    返回值: str — HTML 全文。
    异常: NotFoundError — 实体不存在（经 entities.service）。
    依赖: entities.service、repository、rendering。
    """
    entity = await entities_service.get(main_session, entity_id)
    images = await repository.list_images(session, "entity", entity_id)
    record = await repository.get_entity_record(session, entity_id)

    newest_image_at = max((img.created_at for img in images), default=None)
    threshold = entity.updated_at
    if newest_image_at is not None and newest_image_at > threshold:
        threshold = newest_image_at
    stale = record is None or record.updated_at < threshold
    if not stale and record is not None:
        return record.html

    now = _now()
    html = rendering.render_entity_page(
        entity=entity,
        images=[AssetImageRead.model_validate(img) for img in images],
        generated_at=now.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    if record is None:
        record = await repository.add_record(
            session,
            repository.new_record(
                record_id=generate_asset_id(),
                kind="entity",
                entity_id=entity_id,
                category="",
                title=entity.name,
                description=entity.description,
                attributes={},
                html=html,
                now=now,
            ),
        )
    else:
        record.title = entity.name
        record.description = entity.description
        record.html = html
        record.updated_at = now
        record = await repository.save_record(session, record)
    await session.commit()
    return html
