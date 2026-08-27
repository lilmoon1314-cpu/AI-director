"""entities 模块 HTTP 路由：仅做参数解析与响应包装，不含业务逻辑。

路由总表见 backend/ARCHITECTURE.md §7（/api/entities 前缀）。
事务与业务逻辑全部在 service 层；本层不感知事务（backend/CONSTRAINTS.md）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.entities import service
from app.entities.schemas import EntityBrief, EntityCreate, EntityRead, EntityUpdate

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: EntityCreate, session: AsyncSession = Depends(get_session)
) -> EntityRead:
    """创建实体（POST /api/entities）。

    作用: 参数解析 + 调用 service；id 由系统生成并随响应返回。
    参数: payload — 创建载荷；session — 请求级数据库会话（依赖注入）。
    返回值: EntityRead（201）。异常: 由全局异常处理器统一出口。
    依赖: app.entities.service。
    """
    return await service.create(session, payload)


@router.get("", response_model=list[EntityBrief])
async def search_entities(
    # 参数名 type 与 API 契约（features.md F02 / @ 选择器）保持一致
    q: str = "",
    type: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[EntityBrief]:
    """检索实体（GET /api/entities?q=&type=，@ 实体选择器数据源）。

    作用: 参数解析 + 调用 service；q 匹配名称/别名，type 过滤类型。
    参数: q — 关键字（空返回全量）；type — 实体类型（可选）；session — 请求级会话。
    返回值: list[EntityBrief]。异常: 由全局异常处理器统一出口。
    依赖: app.entities.service。
    """
    return await service.search(session, q=q, entity_type=type)


@router.get("/{entity_id}", response_model=EntityRead)
async def get_entity(entity_id: str, session: AsyncSession = Depends(get_session)) -> EntityRead:
    """查询实体详情（GET /api/entities/{id}）。

    作用: 参数解析 + 调用 service。
    参数: entity_id — 路径参数实体 id；session — 请求级数据库会话。
    返回值: EntityRead。异常: 404 由全局异常处理器统一出口。
    依赖: app.entities.service。
    """
    return await service.get(session, entity_id)


@router.patch("/{entity_id}", response_model=EntityRead)
async def update_entity(
    entity_id: str,
    payload: EntityUpdate,
    session: AsyncSession = Depends(get_session),
) -> EntityRead:
    """局部更新实体（PATCH /api/entities/{id}；id 不可变）。

    作用: 参数解析 + 调用 service；仅更新显式提供的字段。
    参数: entity_id — 路径参数实体 id；payload — 更新载荷；session — 请求级会话。
    返回值: EntityRead（更新后）。异常: 404/422 由全局异常处理器统一出口。
    依赖: app.entities.service。
    """
    return await service.update(session, entity_id, payload)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(entity_id: str, session: AsyncSession = Depends(get_session)) -> None:
    """删除实体（DELETE /api/entities/{id}；被引用时 409 阻断）。

    作用: 参数解析 + 调用 service。
    参数: entity_id — 路径参数实体 id；session — 请求级数据库会话。
    返回值: 无（204）。异常: 404/409 由全局异常处理器统一出口。
    依赖: app.entities.service。
    """
    await service.delete(session, entity_id)
