"""共享测试夹具：环境隔离（临时数据库/日志/资产目录）+ 应用客户端 + 内存守卫。

隔离策略:
    在导入 app 之前覆盖环境变量，把数据库、日志、资产目录全部指向临时目录，
    保证测试绝不污染真实的 data/ 与 logs/。
"""

import asyncio
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# ---- 环境隔离：必须在导入 app.* 之前执行（conftest 先于测试模块导入）----
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ai_director_test_"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP_ROOT / 'test.db').as_posix()}"
os.environ["ASSET_DB_URL"] = f"sqlite+aiosqlite:///{(_TMP_ROOT / 'assets.db').as_posix()}"
os.environ["ASSET_DIR"] = str(_TMP_ROOT / "assets")
os.environ["LOG_DIR"] = str(_TMP_ROOT / "logs")
os.environ["METRIC_SAMPLE_INTERVAL_SECONDS"] = "3600"  # 测试期关闭高频资源采样


async def _run_on_metadata(operation: str) -> None:
    """在测试临时库上执行建表/删表（不经过应用引擎单例）。

    作用: 为集成测试提供干净的表结构；独立引擎用后即弃，避免污染进程级单例。
        同时处理主库（Base）与资产库（AssetsBase，F08 起双库）。
    参数: operation — "create" 或 "drop"。返回值: 无。异常: 无。依赖: SQLAlchemy。
    """
    import app.assets.models  # noqa: F401 — 注册资产库元数据
    import app.entities.models  # noqa: F401 — 注册表元数据
    import app.relations.models  # noqa: F401 — 注册表元数据
    from app.assets.db import dispose_assets_engine
    from app.core.db import Base

    # 主库：独立引擎建/删表
    engine: AsyncEngine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            if operation == "create":
                await conn.run_sync(Base.metadata.create_all)
            else:
                await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()

    # 资产库：先释放单例引擎（避免跨用例残留连接），再独立引擎建/删表
    await dispose_assets_engine()
    assets_engine: AsyncEngine = create_async_engine(os.environ["ASSET_DB_URL"])
    try:
        async with assets_engine.begin() as conn:
            if operation == "create":
                await conn.run_sync(app.assets.models.AssetsBase.metadata.create_all)
            else:
                await conn.run_sync(app.assets.models.AssetsBase.metadata.drop_all)
    finally:
        await assets_engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """提供带完整生命周期与干净数据库的测试客户端。

    作用:
        以 with 语法驱动 FastAPI lifespan（建目录、初始化引擎、挂载静态资产）；
        每个用例独立建表/删表，保证用例间数据隔离；测试结束自动停机并释放引擎。
    参数: 无。
    返回值: TestClient（生成器 yield）。
    异常: 无。
    依赖: app.main.app、fastapi.testclient、app.core.db.Base。
    """
    asyncio.run(_run_on_metadata("create"))
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    asyncio.run(_run_on_metadata("drop"))


@pytest.fixture
def memory_guard() -> Iterator[None]:
    """内存回归守卫：用例执行前后采样进程 RSS，增长超阈值即失败。

    作用:
        测试侧内存回归防线（docs/testing.md §7）——增长超过
        memory_guard_threshold_mb（config）判失败，防内存泄漏进入主干。
        供 e2e/集成用例按需标注（F02 起就位）。
    参数: 无。
    返回值: None（生成器 yield）。
    异常: AssertionError — RSS 增长超阈值（失败消息含三要素）。
    依赖: psutil、app.config.get_settings。
    """
    import psutil

    from app.config import get_settings

    process = psutil.Process()
    rss_before = process.memory_info().rss
    yield
    growth_mb = (process.memory_info().rss - rss_before) / 1024 / 1024
    threshold = get_settings().memory_guard_threshold_mb
    assert growth_mb <= threshold, (
        f"【问题】测试期间进程 RSS 增长 {growth_mb:.1f}MB，超过阈值 {threshold}MB\n"
        f"【原因】被测代码路径可能存在内存泄漏（如未释放的连接/无界缓存）\n"
        "【修复】检查该用例覆盖的 service/repository 代码，定位累积分配并释放"
    )
