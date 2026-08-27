"""Alembic 迁移环境（异步模板）。

作用: 连接应用配置中的数据库并执行迁移；表结构定义见各模块 models.py（F02 起）。
依赖: app.config（连接串唯一来源，禁止在此硬编码）、app.core.db.Base。
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

import app.entities.models  # noqa: F401 — 注册表元数据
import app.relations.models  # noqa: F401 — 注册表元数据
from app.config import get_settings
from app.core.db import Base, ensure_sqlite_dir

# Alembic Config 对象（提供 ini 中的配置访问）
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 数据库地址统一来自应用配置（.env / 环境变量）
_database_url = get_settings().database_url
ensure_sqlite_dir(_database_url)  # 首次迁移前确保 data/ 目录存在
config.set_main_option("sqlalchemy.url", _database_url)

# 目标元数据：供 autogenerate 比对生成迁移（F02 起各模块 models.py 继承 Base）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL 脚本不连接数据库。

    作用: 支持"先出 SQL、DBA 审核后执行"的发布流程。
    参数: 无。返回值: 无。异常: 无。依赖: alembic.context。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在给定连接上执行迁移。

    作用: 在线模式的实际执行体（由异步连接经 run_sync 调用）。
    参数: connection — 同步代理连接。返回值: 无。异常: 无。依赖: alembic.context。
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步执行迁移（aiosqlite）。

    作用: 以异步引擎连接数据库并跑迁移，与应用运行时保持同一驱动。
    参数: 无。返回值: 无。异常: 连接失败由 SQLAlchemy 抛出。依赖: sqlalchemy.ext.asyncio。
    """
    from sqlalchemy.ext.asyncio import async_engine_from_config

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口：连接数据库执行迁移。

    作用: `alembic upgrade head` 的默认路径。
    参数: 无。返回值: 无。异常: 无。依赖: asyncio。
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
