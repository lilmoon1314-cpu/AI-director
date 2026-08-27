"""relations 模块 ORM 模型：关系表（F02 建表；CRUD 由 F03 实现）。

表结构蓝图: docs/data_struct_define.md §2。
外键策略: source/target → entities.id，ON DELETE RESTRICT（backend/CONSTRAINTS.md
「幽灵节点双层防线」——应用层 ReferentialError 为前置校验，DB 层 RESTRICT 为兜底）。
静态属性（dynamic_type/element_interaction 等）并入 properties JSON 列
（见 relations/ARCHITECTURE.md「数据模型」）。
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    """当前 UTC 时间（ORM 默认值工厂）。

    作用: 为 created_at / updated_at 提供统一时间源。
    参数: 无。返回值: datetime（UTC aware）。异常: 无。依赖: datetime。
    """
    return datetime.now(UTC)


class Relationship(Base):
    """关系 ORM 模型：source/target 两实体间的有向关系。

    作用:
        承载关系类型与动态属性（信任度、身份、承诺等）；
        source/target 外键指向 entities.id 并声明 ON DELETE RESTRICT，
        从数据库层杜绝悬空引用（幽灵节点）。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)

    # 动态数值属性（0-1 标度，独立成列便于查询）
    trust: Mapped[float | None] = mapped_column(default=None)
    intimacy: Mapped[float | None] = mapped_column(default=None)
    dependency: Mapped[float | None] = mapped_column(default=None)
    resentment: Mapped[float | None] = mapped_column(default=None)

    # 动态文本属性
    public_identity: Mapped[str | None] = mapped_column(String, default=None)
    private_identity: Mapped[str | None] = mapped_column(String, default=None)
    promise: Mapped[str | None] = mapped_column(String, default=None)
    wants_from: Mapped[str | None] = mapped_column(String, default=None)
    believes_other_wants: Mapped[str | None] = mapped_column(String, default=None)
    leverage: Mapped[str | None] = mapped_column(String, default=None)
    boundary: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str | None] = mapped_column(String, default=None)

    # 视角可见性标记
    known_by: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    audience_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 静态属性（dynamic_type / element_interaction 等，见模块 docstring）
    properties: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )
