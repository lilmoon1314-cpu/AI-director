"""assets 模块数据库基础设施：独立资产库（assets.db）引擎、会话与建表引导。

约定:
    - 与主库（core.db）完全隔离的引擎/会话单例，连接串来自 config.asset_db_url。
    - 启动时 init_assets_db 幂等建表（create_all），不走 Alembic
      （DECISIONS 2026-09-05；schema 变更须向后兼容）。
    - SQLite 每次新建连接自动启用 WAL（资产库无跨表外键，无需外键 PRAGMA）。
"""

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.assets.models import AssetsBase
from app.config import get_settings

_SQLITE_PREFIX = "sqlite+aiosqlite:///"

# 进程级单例（模块私有，经函数访问；与主库 core.db 单例相互独立）
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def ensure_assets_dir(database_url: str) -> None:
    """确保资产库 SQLite 文件的父目录存在。

    作用: 相对路径连接串（默认 data/assets.db）首次使用前自动建目录。
    参数: database_url — 资产库连接串。返回值: 无。异常: 无。依赖: pathlib。
    """
    if database_url.startswith(_SQLITE_PREFIX):
        db_path = Path(database_url.removeprefix(_SQLITE_PREFIX))
        if str(db_path) not in ("", ":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)


def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
    """每次新建资产库连接时启用 WAL 模式。

    作用: 写并发下的读写互不阻塞（与主库 core.db 同策略）。
    参数: dbapi_connection — 底层 DBAPI 连接；_connection_record — SQLAlchemy 内部记录。
    返回值: 无。异常: 无。依赖: SQLAlchemy 事件机制。
    """
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_assets_engine() -> AsyncEngine:
    """获取资产库进程唯一的异步引擎（懒加载，与主库引擎相互独立）。

    作用: 资产库所有会话的底层引擎；重复调用返回同一实例。
    参数: 无。
    返回值: AsyncEngine。
    异常: 无（引擎创建失败由 SQLAlchemy 自行抛出，全局异常处理器兜底）。
    依赖: app.config.get_settings、SQLAlchemy。
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        ensure_assets_dir(settings.asset_db_url)
        _engine = create_async_engine(settings.asset_db_url)
        event.listen(_engine.sync_engine, "connect", _set_sqlite_pragma)
    return _engine


def get_assets_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取资产库进程唯一的会话工厂。

    作用: 统一 AsyncSession 创建参数（expire_on_commit=False 便于响应序列化）。
    参数: 无。返回值: async_sessionmaker。异常: 无。依赖: get_assets_engine。
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_assets_engine(), expire_on_commit=False)
    return _session_factory


async def get_assets_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个资产库会话，请求结束自动释放。

    作用: 资产路由的会话注入点（与主库 core.db.get_session 并存，
        同一请求可同时注入两个会话）。
    参数: 无。返回值: AsyncSession（生成器 yield）。异常: 无。依赖: get_assets_session_factory。
    """
    async with get_assets_session_factory()() as session:
        yield session


async def init_assets_db() -> None:
    """资产库建表引导（幂等，应用启动时调用）。

    作用:
        create_all 仅创建缺失的表，已存在的表与数据不受影响
        （DECISIONS 2026-09-05：资产库不走 Alembic，schema 变更须向后兼容）。
    参数: 无。返回值: 无。异常: 无（DB 错误由全局异常处理器兜底）。
    依赖: app.assets.models.AssetsBase、get_assets_engine。
    """
    engine = get_assets_engine()
    async with engine.begin() as conn:
        await conn.run_sync(AssetsBase.metadata.create_all)


async def dispose_assets_engine() -> None:
    """关闭并清空资产库引擎与会话工厂（应用停机/测试清理时调用）。

    作用: 释放连接池资源，并允许下一次 get_assets_engine 以新配置重建（测试隔离依赖此行为）。
    参数: 无。返回值: 无。异常: 无。依赖: SQLAlchemy。
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
