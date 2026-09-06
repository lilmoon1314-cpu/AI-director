"""projects 模块 ORM 模型：项目表（唯一允许 import 本文件的是本模块 repository）。

表结构蓝图: docs/data_struct_define.md §11.1（F11）。
计数器语义: entity_count / relation_count 为反规范化列，由 entities / relations
写路径在同库事务内经 projects.service.touch 维护（DECISIONS 2026-09-06——
projects 业务层零领域依赖，读取无需跨模块聚合）。
"""

from datetime import UTC, datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    """当前 UTC 时间（ORM 默认值工厂）。

    作用: 为 created_at / updated_at 提供统一时间源。
    参数: 无。返回值: datetime（UTC aware）。异常: 无。依赖: datetime。
    """
    return datetime.now(UTC)


class Project(Base):
    """项目 ORM 模型：一个影视世界观工作区的顶层归属容器。

    作用:
        承载多项目隔离的顶层维度；entities / relationships 以 project_id
        外键归属本项目；默认项目（固定 id，service 层常量）为不带
        project_id 请求的兜底目标，不可删除。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    # 反规范化计数器（事务内维护，见模块 docstring）；首屏卡片与删除确认后果清单的数据源
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )
