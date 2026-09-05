"""assets 模块 ORM 模型（独立资产库 assets.db，独立元数据体系）。

关键设计（DECISIONS 2026-09-05）:
    - 独立 DeclarativeBase（AssetsBase）：与主库 Base 元数据完全隔离，
      主库 Alembic 迁移不可见资产表；assets.db 由 lifespan 启动时
      create_all 幂等引导（backend/CONSTRAINTS.md「Alembic」例外条款）。
    - asset_records 与 asset_images 之间为应用层引用（cover_image_id），
      不声明跨表外键；一致性由 service 写路径维护。
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.db import UTCDateTime


class AssetsBase(DeclarativeBase):
    """资产库独立声明基类（与主库 core.db.Base 元数据隔离）。

    作用: 汇总资产库全部表元数据，供启动时 create_all 幂等引导使用；
        禁止被主库 Alembic env 收录。
    参数: 无。返回值: 无（基类）。异常: 无。依赖: SQLAlchemy 2.0。
    """


def _utcnow() -> datetime:
    """当前 UTC 时间（资产库时间戳统一时间源）。

    作用: 为 created_at / updated_at 提供默认值。
    参数: 无。返回值: UTC aware datetime。异常: 无。依赖: 无。
    """
    return datetime.now(UTC)


class AssetRecord(AssetsBase):
    """资产记录（通用资产页或实体资产页的 HTML 载体）。

    作用:
        kind='general' 为用户创建的通用资产（分类/标题/描述/attributes 自由属性）；
        kind='entity' 为主库实体的 HTML 资产页缓存（按 entity.updated_at 惰性再生，
        entity_id 指向主库实体 id，应用层引用无跨库外键）。
    """

    __tablename__ = "asset_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cover_image_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class AssetImage(AssetsBase):
    """图片元数据（文件落盘 data/assets/，库内仅存元数据与相对存储名）。

    作用:
        scope='general' 时 owner_id 指向 asset_records.id；
        scope='entity' 时 owner_id 指向主库实体 id（应用层引用，
        实体删除后的清理由孤儿清扫完成，见 service.list_entity_cards）。
    """

    __tablename__ = "asset_images"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filename_orig: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
