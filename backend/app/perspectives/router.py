"""perspectives 模块 HTTP 路由：三视角过滤图查询（/api/graph）。

路由总表见 backend/ARCHITECTURE.md §7。本模块只读不写、无事务概念；
本层仅做参数解析与响应包装，不含业务逻辑。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.perspectives import schemas, service

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("", response_model=schemas.GraphData)
async def get_graph(
    # perspective 必填（无默认值）：避免缺参时误入 author 全知视图
    perspective: schemas.Perspective = Query(
        description="视角：author 全知 / character 角色 / audience 观众"
    ),
    character_id: str | None = Query(
        default=None, description="character 视角必填：视角角色的实体 id"
    ),
    session: AsyncSession = Depends(get_session),
) -> schemas.GraphData:
    """三视角过滤图查询（GET /api/graph?perspective=author|character|audience）。

    作用: 参数解析 + 调用 service；过滤规则与可见性判定全部在 service 层。
    参数: perspective — 视角枚举（必填）；character_id — character 视角角色 id；
        session — 请求级数据库会话（依赖注入）。
    返回值: GraphData（nodes+edges）。异常: 403/422 由全局异常处理器统一出口。
    依赖: app.perspectives.service。
    """
    return await service.get_graph(session, perspective=perspective, character_id=character_id)
