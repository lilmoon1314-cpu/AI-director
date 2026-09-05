"""assets 模块 router 层：HTTP 路由（仅参数解析与响应包装，业务在 service 层）。

路由总表见模块 ARCHITECTURE.md；错误经全局异常处理器统一出口（三要素）。
同一请求可注入两个会话：assets（资产库）与 main（主库，实体数据）。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets import service
from app.assets.db import get_assets_session
from app.assets.schemas import (
    AssetCard,
    AssetImageRead,
    AssetRead,
    AssetScope,
    CoverSet,
    EntityAssetCard,
    GeneralAssetCreate,
    GeneralAssetUpdate,
)
from app.core.db import get_session

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/images", response_model=AssetImageRead, status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    scope: str = Form(...),
    owner_id: str = Form(...),
    session: AsyncSession = Depends(get_assets_session),
    main_session: AsyncSession = Depends(get_session),
) -> AssetImageRead:
    """上传图片（multipart：file + scope + owner_id）。

    作用: 图片上传路由——multipart 表单解析后委托 service（校验/写盘/入库）。
    参数: file — 图片文件；scope — 'general' | 'entity'；owner_id — 归属 id；
        session — 资产库会话；main_session — 主库会话。
    返回值: AssetImageRead（含静态访问 url）。
    异常: NotFoundError（404 归属不存在）/ ValidationError（422 类型或超限）。
    依赖: app.assets.service.upload_image、双会话依赖。
    """
    return await service.upload_image(
        session, main_session, scope=scope, owner_id=owner_id, upload=file
    )


@router.get("/images", response_model=list[AssetImageRead])
async def list_images(
    scope: AssetScope,
    owner_id: str,
    session: AsyncSession = Depends(get_assets_session),
) -> list[AssetImageRead]:
    """图片明细列表（按归属）。

    作用: 实体详情面板图片区/通用资产编辑表单的数据源路由。
    参数: scope — 'general' | 'entity'（Literal 校验）；owner_id — 归属 id；
        session — 资产库会话。
    返回值: list[AssetImageRead]。异常: ValidationError（422 scope 非法）。
    依赖: app.assets.service.list_images。
    """
    return await service.list_images(session, scope=scope, owner_id=owner_id)


@router.get("/file/{stored_name}")
async def get_image_file(
    stored_name: str,
    session: AsyncSession = Depends(get_assets_session),
) -> FileResponse:
    """图片文件访问（/api 同源路由，HTML 资产页内图片引用走此地址）。

    作用: 以 FileResponse 返回图片字节（mime 按扩展名推断）；路径穿越由
        storage.resolve_stored_path 防线拦截。
    参数: stored_name — 存储名；session — 资产库会话。返回值: FileResponse。
    异常: NotFoundError（404 文件不存在）/ ValidationError（422 路径非法）。
    依赖: app.assets.service.get_image_file。
    """
    path: Path = await service.get_image_file(session, stored_name)
    return FileResponse(path)


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    session: AsyncSession = Depends(get_assets_session),
) -> None:
    """删除图片（记录 + 物理文件 + 封面引用清理）。

    作用: 图片删除路由。
    参数: image_id — 图片 id；session — 资产库会话。返回值: 无（204）。
    异常: NotFoundError（404）。
    依赖: app.assets.service.delete_image。
    """
    await service.delete_image(session, image_id)


@router.get("/general", response_model=list[AssetCard])
async def list_general(
    category: str | None = None,
    session: AsyncSession = Depends(get_assets_session),
) -> list[AssetCard]:
    """通用资产卡片列表（可按分类过滤）。

    作用: 通用资产区数据源路由。
    参数: category — 分类过滤（可空）；session — 资产库会话。
    返回值: list[AssetCard]。异常: 无。
    依赖: app.assets.service.list_general。
    """
    return await service.list_general(session, category=category)


@router.post("/general", response_model=AssetRead, status_code=201)
async def create_general(
    payload: GeneralAssetCreate,
    session: AsyncSession = Depends(get_assets_session),
) -> AssetRead:
    """创建通用资产。

    作用: 通用资产创建路由。
    参数: payload — 创建载荷；session — 资产库会话。返回值: AssetRead。
    异常: ValidationError（422 字段校验）。
    依赖: app.assets.service.create_general。
    """
    return await service.create_general(session, payload)


@router.patch("/general/{asset_id}", response_model=AssetRead)
async def update_general(
    asset_id: str,
    payload: GeneralAssetUpdate,
    session: AsyncSession = Depends(get_assets_session),
) -> AssetRead:
    """局部更新通用资产。

    作用: 通用资产编辑路由。
    参数: asset_id — 资产 id；payload — 更新载荷；session — 资产库会话。
    返回值: AssetRead。异常: NotFoundError（404）。
    依赖: app.assets.service.update_general。
    """
    return await service.update_general(session, asset_id, payload)


@router.delete("/general/{asset_id}", status_code=204)
async def delete_general(
    asset_id: str,
    session: AsyncSession = Depends(get_assets_session),
) -> None:
    """删除通用资产（级联清理图片与文件）。

    作用: 通用资产删除路由。
    参数: asset_id — 资产 id；session — 资产库会话。返回值: 无（204）。
    异常: NotFoundError（404）。
    依赖: app.assets.service.delete_general。
    """
    await service.delete_general(session, asset_id)


@router.get("/general/{asset_id}", response_model=AssetRead)
async def get_general(
    asset_id: str,
    session: AsyncSession = Depends(get_assets_session),
) -> AssetRead:
    """通用资产详情（含图片明细）。

    作用: 编辑表单数据源路由（列表仅有摘要）。
    参数: asset_id — 资产 id；session — 资产库会话。返回值: AssetRead。
    异常: NotFoundError（404）。
    依赖: app.assets.service.get_general。
    """
    return await service.get_general(session, asset_id)


@router.get("/general/{asset_id}/page", response_class=HTMLResponse)
async def get_general_page(
    asset_id: str,
    session: AsyncSession = Depends(get_assets_session),
) -> HTMLResponse:
    """通用资产 HTML 页（内嵌查看器数据源）。

    作用: 返回存储的自包含 HTML 全文（text/html）。
    参数: asset_id — 资产 id；session — 资产库会话。返回值: HTMLResponse。
    异常: NotFoundError（404）。
    依赖: app.assets.service.get_general_page。
    """
    return HTMLResponse(content=await service.get_general_page(session, asset_id))


@router.put("/general/{asset_id}/cover", response_model=AssetRead)
async def set_cover(
    asset_id: str,
    body: CoverSet,
    session: AsyncSession = Depends(get_assets_session),
) -> AssetRead:
    """设置通用资产封面。

    作用: 卡片缩略图人工指定路由。
    参数: asset_id — 资产 id；body — 含 image_id；session — 资产库会话。
    返回值: AssetRead。异常: NotFoundError / ValidationError（归属不符）。
    依赖: app.assets.service.set_cover。
    """
    return await service.set_cover(session, asset_id, body.image_id)


@router.get("/entities", response_model=list[EntityAssetCard])
async def list_entity_cards(
    session: AsyncSession = Depends(get_assets_session),
    main_session: AsyncSession = Depends(get_session),
) -> list[EntityAssetCard]:
    """项目资产卡片列表（主库实体按类型分组；含孤儿清扫）。

    作用: 项目资产区数据源路由。
    参数: session — 资产库会话；main_session — 主库会话。
    返回值: list[EntityAssetCard]（类型序 + 名称序）。异常: 无。
    依赖: app.assets.service.list_entity_cards。
    """
    return await service.list_entity_cards(session, main_session)


@router.get("/entity/{entity_id}/page", response_class=HTMLResponse)
async def get_entity_page(
    entity_id: str,
    session: AsyncSession = Depends(get_assets_session),
    main_session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """实体资产 HTML 页（惰性生成/过期再生）。

    作用: 项目资产内嵌查看器数据源路由。
    参数: entity_id — 实体 id；session — 资产库会话；main_session — 主库会话。
    返回值: HTMLResponse。异常: NotFoundError（404 实体不存在）。
    依赖: app.assets.service.get_entity_page。
    """
    return HTMLResponse(content=await service.get_entity_page(session, main_session, entity_id))
