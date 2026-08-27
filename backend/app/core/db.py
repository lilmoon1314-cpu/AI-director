"""数据库基础设施：异步引擎、会话工厂与 ORM 基类。

约定:
    - SQLite 每次新建连接自动启用 WAL 模式与外键约束（backend/CONSTRAINTS.md）。
    - 引擎为进程级单例（懒加载）；测试通过环境变量切换临时库实现隔离。
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

_SQLITE_PREFIX = "sqlite+aiosqlite:///"


class UTCDateTime(TypeDecorator):
    """以 UTC 规范存取的时间戳类型（SQLite 方言下保证 aware 往返一致）。

    作用:
        SQLite 不持久化时区信息：DateTime(timezone=True) 写入后读回为 naive，
        导致同一实体创建响应（+00:00/Z）与回读响应（无标记）序列化不一致。
        本类型在写入前归一化为 UTC，读取后将 naive 值标记回 UTC，
        保证 created_at/updated_at 全链路 aware 且语义统一。
    参数: 无（构造同 DateTime）。
    返回值: 无（类型类）。
    异常: 无。
    依赖: sqlalchemy.types.TypeDecorator、DateTime。
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        """写入前把任意时区的时间归一化为 UTC。

        参数: value — 待写入的 datetime；dialect — 数据库方言。
        返回值: datetime | None。异常: 无（naive 值视为已经是 UTC 存储）。
        """
        if value is None:
            return None
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        """读取后给丢失时区标记的值补上 UTC（aware 值直接归一化 UTC）。

        参数: value — 从数据库读出的 datetime；dialect — 数据库方言。
        返回值: datetime | None。异常: 无。
        """
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。

    作用: 汇总全部表元数据，供 Alembic 迁移自动比对生成（F02 起各模块 models.py 继承）。
    参数: 无。返回值: 无（基类）。异常: 无。依赖: SQLAlchemy 2.0。
    """


# 进程级单例（模块私有，经函数访问）
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def ensure_sqlite_dir(database_url: str) -> None:
    """确保 SQLite 数据库文件的父目录存在。

    作用: 相对路径连接串（默认 data/app.db）首次使用前自动建目录，避免连接失败。
    参数: database_url — 连接串。返回值: 无。异常: 无。依赖: pathlib。
    """
    if database_url.startswith(_SQLITE_PREFIX):
        db_path = Path(database_url.removeprefix(_SQLITE_PREFIX))
        if str(db_path) not in ("", ":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> AsyncEngine:
    """获取进程唯一的异步数据库引擎（懒加载）。

    作用:
        创建引擎并注册 SQLite PRAGMA 钩子（WAL + 外键）；重复调用返回同一实例。
    参数: 无。
    返回值: AsyncEngine。
    异常: 无（引擎创建失败由 SQLAlchemy 自行抛出，由全局异常处理器兜底）。
    依赖: app.config.get_settings、SQLAlchemy。
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        ensure_sqlite_dir(settings.database_url)
        _engine = create_async_engine(settings.database_url)
        # 在同步引擎层注册连接钩子：每次新连接自动启用 WAL 与外键
        event.listen(_engine.sync_engine, "connect", _set_sqlite_pragma)
    return _engine


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """每次新建 SQLite 连接时启用 WAL 与外键约束。

    作用: 满足 backend/CONSTRAINTS.md「SQLite 开启 WAL 模式与外键约束」。
    参数: dbapi_connection — 底层 DBAPI 连接；_connection_record — SQLAlchemy 内部记录。
    返回值: 无。异常: 无。依赖: SQLAlchemy 事件机制。
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取进程唯一的会话工厂。

    作用: 统一 AsyncSession 的创建参数（expire_on_commit=False 便于响应序列化）。
    参数: 无。返回值: async_sessionmaker[AsyncSession]。异常: 无。依赖: get_engine。
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动释放。

    作用: 作为路由的 Depends 注入点；会话生命周期与请求一致。
    参数: 无。返回值: AsyncSession（生成器 yield）。异常: 无。依赖: get_session_factory。
    """
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """关闭并清空进程级引擎与会话工厂（应用停机 / 测试清理时调用）。

    作用: 释放连接池资源，并允许下一次 get_engine 以新配置重建（测试隔离依赖此行为）。
    参数: 无。返回值: 无。异常: 无。依赖: SQLAlchemy。
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
