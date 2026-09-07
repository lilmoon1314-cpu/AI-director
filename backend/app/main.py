"""应用入口：应用工厂、生命周期管理、路由与中间件组装。

启动方式: make dev-backend（等价 uv run uvicorn app.main:app --reload）
API 文档: http://localhost:8000/docs（FastAPI 自动生成）
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agent import service as agent_service
from app.agent.router import router as agent_router
from app.assets import service as assets_service
from app.assets.router import router as assets_router
from app.config import get_settings
from app.core import db, observability
from app.entities.router import router as entities_router
from app.perspectives.router import router as perspectives_router
from app.projects import service as projects_service
from app.projects.router import router as projects_router
from app.relations.router import router as relations_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时初始化资源，停机时释放。

    作用:
        按序完成：发射 startup 事件 → 创建资产目录 → 预热数据库引擎（含 WAL/外键）→
        初始化资产库 → 幂等确保默认项目存在（F11）→ 挂载静态资产目录 →
        发射 ready 事件；停机时发射 shutdown 并释放双库引擎。
    参数:
        app — FastAPI 实例（用于挂载静态目录）。
    返回值:
        AsyncIterator[None]（asynccontextmanager 协议）。
    异常:
        无（初始化失败由全局异常体系兜底记录）。
    依赖:
        app.config、app.core.db、app.core.observability、app.projects.service。
    """
    settings = get_settings()
    observability.emit_lifecycle("startup")
    Path(settings.asset_dir).mkdir(parents=True, exist_ok=True)
    db.get_engine()
    await assets_service.init_database()
    async with db.get_session_factory()() as session:
        await projects_service.ensure_default_project(session)
    app.mount("/static/assets", StaticFiles(directory=settings.asset_dir), name="assets")
    observability.emit_lifecycle("ready", data={"asset_dir": settings.asset_dir})
    try:
        yield
    finally:
        observability.emit_lifecycle("shutdown")
        await agent_service.dispose_resources()
        await assets_service.shutdown_engine()
        await db.dispose_engine()


def create_app() -> FastAPI:
    """应用工厂：组装信号采集、跨域、生命周期与路由。

    作用:
        唯一的 FastAPI 组装点；领域模块路由（F02 起）在此挂载。
    参数: 无。
    返回值:
        FastAPI 实例。
    异常: 无。
    依赖:
        app.config.get_settings、app.core.observability。
    """
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # 信号采集（中间件 + 异常处理器 + 三路 JSONL 日志 + 资源采样）
    observability.setup(app, settings)

    # 跨域：允许前端开发服务器（http://localhost:5173）访问本 API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """健康检查端点（存活探针，供测试与运维验证服务可用）。"""
        return {"status": "ok"}

    # 领域模块路由挂载（entities/relations/perspectives/assets/projects/agent，F02~F10）
    app.include_router(entities_router)
    app.include_router(relations_router)
    app.include_router(perspectives_router)
    app.include_router(assets_router)
    app.include_router(projects_router)
    app.include_router(agent_router)

    return app


# uvicorn 入口：uvicorn app.main:app
app = create_app()
