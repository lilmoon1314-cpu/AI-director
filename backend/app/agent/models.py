"""agent 模块 ORM 模型：会话 / 消息 / 记忆文档 / 记忆文档段。

表结构蓝图: docs/data_struct_define.md §11.3（规划随 F10 落地主库）。
唯一允许 import 本文件的是本模块 repository。
"""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    """当前 UTC 时间（ORM 默认值工厂）。

    作用: 为 created_at / updated_at 提供统一时间源。
    参数: 无。返回值: datetime（UTC aware）。异常: 无。依赖: datetime。
    """
    return datetime.now(UTC)


class Conversation(Base):
    """会话 ORM 模型：按项目隔离的对话容器（AgentHome 与 AgentDock 同一会话池）。

    作用:
        承载会话元数据与滚动摘要（summary 为超窗历史的增量压缩结果，
        L2 短期记忆的持久层）；项目级联删除时随项目清理。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    # 超窗历史的滚动摘要（轻量模型增量更新；空串=尚无摘要）
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 摘要覆盖游标：summary 已覆盖到该消息 id（含）；之后的消息仍以全文注入
    summary_until_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Message(Base):
    """消息 ORM 模型：会话内单条消息（SSE 流式完成后落库）。

    作用:
        L2 短期记忆持久层；role 区分 user/assistant/summary/tool，
        summary 角色行承载摘要事件（窗口裁剪的可追溯记录）。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # assistant 行的思考过程（真流式 reasoning_content 聚合；user/tool 行为 NULL）
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # 本轮 LLM usage（UsageBar 容量窗口数据源；端点不返回 usage 时为 NULL）
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)


class MemoryDoc(Base):
    """记忆文档 ORM 模型：项目工作上下文（HTML 分段模板，非世界观事实副本）。

    作用:
        L1 长期记忆的文档容器；kind 决定渲染模板（F10 内置世界观定位 /
        风格约定，故事大纲留给 F13）；version 为文档级 ETag（任意段变更 +1）。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "memory_docs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class MemoryDocSection(Base):
    """记忆文档段 ORM 模型：文档的段级存储单元（段级 patch 的 CAS 主体）。

    作用:
        段级读写使 LLM 与用户都只改一段不全文重写（token 经济与冲突
        收敛）；version 为段级 CAS 令牌——agent patch 携带期望版本，
        不一致即冲突拒绝（用户手改优先，绝不静默覆盖）。
    参数:
        无（ORM 模型，字段见下）。
    返回值: 无（模型类）。
    异常: 无。
    依赖: SQLAlchemy 2.0、app.core.db.Base。
    """

    __tablename__ = "memory_doc_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        ForeignKey("memory_docs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(String, nullable=False, default="user")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow, onupdate=_utcnow
    )
