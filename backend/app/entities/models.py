"""entities 模块 ORM 模型：实体表（唯一允许 import 本文件的是本模块 repository）。

表结构蓝图: docs/data_struct_define.md §1。
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    """当前 UTC 时间（ORM 默认值工厂）。

    作用: 为 created_at / updated_at 提供统一时间源。
    参数: 无。返回值: datetime（UTC aware）。异常: 无。依赖: datetime。
    """
    return datetime.now(UTC)


class Entity(Base):
    """实体 ORM 模型：所有类型共用一表，特有属性存 properties JSON。

    作用:
        承载 character/faction/location/item/skill/event/concept 七类实体；
        id 系统生成且创建后不可变（entities/CONSTRAINTS.md）。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    audience_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    properties: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )
