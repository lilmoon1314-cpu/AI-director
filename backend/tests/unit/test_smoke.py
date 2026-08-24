"""L1 冒烟测试（F01）：证明配置加载与应用装配链路可用。

对应测试文档: docs/tests/F01_project_setup.md — 用例 U1。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings

pytestmark = pytest.mark.unit


def test_settings_load_from_env() -> None:
    """配置能从环境变量加载（conftest 已注入隔离环境）。

    失败含义:
        【问题】Settings 未读到 conftest 注入的 DATABASE_URL
        【原因】conftest.py 的环境隔离代码未在导入 app 前执行
        【修复】检查 tests/conftest.py 顶部环境变量覆盖逻辑
    """
    settings = Settings()
    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_app_factory_assembles_routes() -> None:
    """应用工厂完成装配（健康检查路由存在）。

    失败含义:
        【问题】create_app() 未挂载 /api/health 路由
        【原因】app/main.py 的路由注册被误删或改动
        【修复】在 create_app() 中恢复 health 端点注册
    """
    from app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/health" in paths


def test_health_endpoint_with_request_signal(client: TestClient) -> None:
    """健康检查端点返回 200，且请求信号中间件已注入 x-request-id。

    失败含义:
        【问题】/api/health 不可用或缺少 x-request-id 响应头
        【原因】应用未启动（lifespan 失败）或 RequestSignalMiddleware 未装配
        【修复】检查 app/main.py lifespan 与 app/core/observability.py setup()
    """
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers.get("x-request-id"), "请求信号中间件未注入 x-request-id"
