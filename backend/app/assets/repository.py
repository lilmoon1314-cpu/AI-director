"""assets 模块数据访问层：唯一允许 import 本模块 ORM 模型的层。

事务约定: 本层不 commit/rollback（事务边界在 service 层，backend/CONSTRAINTS.md）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import AssetImage, AssetRecord


async def get_record(session: AsyncSession, asset_id: str) -> AssetRecord | None:
    """按 id 查询资产记录。

    作用: 详情/更新/删除的取数入口。
    参数: session — 资产库会话；asset_id — 资产 id。返回值: AssetRecord 或 None。异常: 无。
    依赖: SQLAlchemy ORM。
    """
    return await session.get(AssetRecord, asset_id)


async def get_entity_record(session: AsyncSession, entity_id: str) -> AssetRecord | None:
    """按主库实体 id 查询实体资产页记录（kind=entity）。

    作用: 实体页惰性生成的现状读取。
    参数: session — 资产库会话；entity_id — 主库实体 id。
    返回值: AssetRecord 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(AssetRecord).where(
        AssetRecord.kind == "entity", AssetRecord.entity_id == entity_id
    )
    return (await session.scalars(stmt)).first()


async def list_records(
    session: AsyncSession, kind: str, category: str | None = None
) -> list[AssetRecord]:
    """按种类列出资产记录（通用资产可叠加分类过滤）。

    作用: 卡片列表取数入口。
    参数: session — 资产库会话；kind — 'general' | 'entity'；category — 分类过滤（可空）。
    返回值: list[AssetRecord]（updated_at 降序，通用）/(类型, 名称序由 service 排)。
    异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(AssetRecord).where(AssetRecord.kind == kind)
    if category is not None:
        stmt = stmt.where(AssetRecord.category == category)
    stmt = stmt.order_by(AssetRecord.updated_at.desc())
    return list(await session.scalars(stmt))


async def add_record(session: AsyncSession, record: AssetRecord) -> AssetRecord:
    """插入一条资产记录。

    作用: 创建路径落库（不提交事务）。
    参数: session — 资产库会话；record — 已填充字段的 ORM 实例。
    返回值: AssetRecord。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(record)
    await session.flush()
    return record


async def save_record(session: AsyncSession, record: AssetRecord) -> AssetRecord:
    """保存已修改的资产记录（updated_at 由 onupdate 自动刷新）。

    作用: 更新路径落库（不提交事务）。
    参数: session — 资产库会话；record — 已在内存中修改的 ORM 实例。
    返回值: AssetRecord。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return record


async def delete_record(session: AsyncSession, record: AssetRecord) -> None:
    """删除资产记录（不提交事务）。

    作用: 通用资产删除/孤儿清扫的记录清理。
    参数: session — 资产库会话；record — 待删除记录。返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(record)
    await session.flush()


async def get_image(session: AsyncSession, image_id: str) -> AssetImage | None:
    """按 id 查询图片元数据。

    作用: 图片删除/封面校验的取数入口。
    参数: session — 资产库会话；image_id — 图片 id。返回值: AssetImage 或 None。异常: 无。
    依赖: SQLAlchemy ORM。
    """
    return await session.get(AssetImage, image_id)


async def list_images(session: AsyncSession, scope: str, owner_id: str) -> list[AssetImage]:
    """按归属列出图片（创建时间升序，首图即候选封面）。

    作用: 单个资产的图片明细取数。
    参数: session — 资产库会话；scope — 'general' | 'entity'；owner_id — 归属 id。
    返回值: list[AssetImage]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(AssetImage)
        .where(AssetImage.scope == scope, AssetImage.owner_id == owner_id)
        .order_by(AssetImage.created_at.asc())
    )
    return list(await session.scalars(stmt))


async def list_images_for_owners(
    session: AsyncSession, scope: str, owner_ids: list[str]
) -> dict[str, list[AssetImage]]:
    """按归属批量列出图片并分组（列表场景一次取全，避免 N+1）。

    作用: 卡片列表的封面/计数取数。
    参数: session — 资产库会话；scope — 归属面；owner_ids — 归属 id 列表。
    返回值: dict[owner_id, list[AssetImage]]（每组按创建时间升序）。
    异常: 无。依赖: SQLAlchemy ORM。
    """
    if not owner_ids:
        return {}
    stmt = (
        select(AssetImage)
        .where(AssetImage.scope == scope, AssetImage.owner_id.in_(owner_ids))
        .order_by(AssetImage.created_at.asc())
    )
    grouped: dict[str, list[AssetImage]] = {}
    for image in await session.scalars(stmt):
        grouped.setdefault(image.owner_id, []).append(image)
    return grouped


async def add_image(session: AsyncSession, image: AssetImage) -> AssetImage:
    """插入一条图片元数据。

    作用: 上传路径落库（不提交事务）。
    参数: session — 资产库会话；image — 已填充字段的 ORM 实例。
    返回值: AssetImage。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(image)
    await session.flush()
    return image


async def delete_image(session: AsyncSession, image: AssetImage) -> None:
    """删除图片元数据（不提交事务；物理文件由 service 层清理）。

    作用: 图片删除/级联删除/孤儿清扫的记录清理。
    参数: session — 资产库会话；image — 待删除记录。返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(image)
    await session.flush()


async def clear_cover_reference(session: AsyncSession, image_id: str) -> None:
    """清空所有指向指定图片的封面引用（封面图被删时保持记录一致）。

    作用: 删除图片的应用层引用清理（跨记录，无外键兜底——必须显式执行）。
    参数: session — 资产库会话；image_id — 被删图片 id。返回值: 无。异常: 无。
    依赖: SQLAlchemy ORM。
    """
    await session.execute(
        update(AssetRecord)
        .where(AssetRecord.cover_image_id == image_id)
        .values(cover_image_id=None)
    )


async def count_images(session: AsyncSession, scope: str, owner_id: str) -> int:
    """统计归属下的图片数量（保留接口：单资产计数）。

    作用: 详情页图片计数。
    参数: session — 资产库会话；scope — 归属面；owner_id — 归属 id。
    返回值: int。异常: 无。依赖: SQLAlchemy ORM。
    """
    images = await list_images(session, scope, owner_id)
    return len(images)


def new_record(
    *,
    record_id: str,
    kind: str,
    entity_id: str | None,
    category: str,
    title: str,
    description: str,
    attributes: dict[str, Any],
    html: str,
    now: datetime,
) -> AssetRecord:
    """构造资产记录 ORM 实例（时间戳装配即填充，未落库状态可完整序列化）。

    作用: service 层创建路径的装配 helper（repository 唯一持有 ORM 构造）。
    参数: 各字段见 AssetRecord 模型；now — 创建时间。
    返回值: AssetRecord（未入库）。异常: 无。依赖: app.assets.models。
    """
    return AssetRecord(
        id=record_id,
        kind=kind,
        entity_id=entity_id,
        category=category,
        title=title,
        description=description,
        attributes=attributes,
        html=html,
        created_at=now,
        updated_at=now,
    )


def new_image(
    *,
    image_id: str,
    scope: str,
    owner_id: str,
    filename_orig: str,
    stored_name: str,
    mime: str,
    size: int,
    now: datetime,
) -> AssetImage:
    """构造图片元数据 ORM 实例（时间戳装配即填充）。

    作用: service 层上传路径的装配 helper。
    参数: 各字段见 AssetImage 模型；now — 创建时间。
    返回值: AssetImage（未入库）。异常: 无。依赖: app.assets.models。
    """
    return AssetImage(
        id=image_id,
        scope=scope,
        owner_id=owner_id,
        filename_orig=filename_orig,
        stored_name=stored_name,
        mime=mime,
        size=size,
        created_at=now,
    )
