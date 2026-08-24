"""共享测试夹具：环境隔离（临时数据库/日志/资产目录）+ 应用客户端。

隔离策略:
    在导入 app 之前覆盖环境变量，把数据库、日志、资产目录全部指向临时目录，
    保证测试绝不污染真实的 data/ 与 logs/。
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---- 环境隔离：必须在导入 app.* 之前执行（conftest 先于测试模块导入）----
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ai_director_test_"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP_ROOT / 'test.db').as_posix()}"
os.environ["ASSET_DIR"] = str(_TMP_ROOT / "assets")
os.environ["LOG_DIR"] = str(_TMP_ROOT / "logs")
os.environ["METRIC_SAMPLE_INTERVAL_SECONDS"] = "3600"  # 测试期关闭高频资源采样


@pytest.fixture
def client() -> Iterator[TestClient]:
    """提供带完整生命周期的测试客户端。

    作用:
        以 with 语法驱动 FastAPI lifespan（建目录、初始化引擎、挂载静态资产），
        测试结束自动停机并释放引擎。
    参数: 无。
    返回值:
        TestClient（生成器 yield）。
    异常: 无。
    依赖:
        app.main.app、fastapi.testclient。
    """
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
