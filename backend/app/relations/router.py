"""relations 模块 HTTP 路由：仅做参数解析与响应包装，不含业务逻辑。

路由总表见 backend/ARCHITECTURE.md §7（/api/relations 前缀）。
事务与业务逻辑全部在 service 层；本层不感知事务（backend/CONSTRAINTS.md）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.relations import service
from app.relations.schemas import RelationCreate, RelationRead, RelationUpdate

router = APIRouter(prefix="/api/relations", tags=["relations"])


@router.post("", response_model=RelationRead, status_code=status.HTTP_201_CREATED)
async def create_relation(
    payload: RelationCreate, session: AsyncSession = Depends(get_session)
) -> RelationRead:
    """创建关系（POST /api/relations）。

    作用: 参数解析 + 调用 service；id 由系统生成并随响应返回。
    参数: payload — 创建载荷；session — 请求级数据库会话（依赖注入）。
    返回值: RelationRead（201）。异常: 404/409/422 由全局异常处理器统一出口。
    依赖: app.relations.service。
    """
    return await service.create(session, payload)


@router.get("", response_model=list[RelationRead])
async def search_relations(
    source: str | None = None,
    target: str | None = None,
    # 参数名 type 与 API 契约（features.md F03 / 图可视化边过滤）保持一致
    type: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[RelationRead]:
    """条件查询关系（GET /api/relations?source=&target=&type=，无参返回全量）。

    作用: 参数解析 + 调用 service；按端点/类型过滤关系。
    参数: source/target — 端点实体 id（可选）；type — 关系类型（可选）；
        session — 请求级会话。
    返回值: list[RelationRead]。异常: 由全局异常处理器统一出口。
    依赖: app.relations.service。
    """
    return await service.get_all(session, source=source, target=target, rel_type=type)


@router.get("/{relation_id}", response_model=RelationRead)
async def get_relation(
    relation_id: str, session: AsyncSession = Depends(get_session)
) -> RelationRead:
    """查询关系详情（GET /api/relations/{id}）。

    作用: 参数解析 + 调用 service。
    参数: relation_id — 路径参数关系 id；session — 请求级会话。
    返回值: RelationRead。异常: 404 由全局异常处理器统一出口。
    依赖: app.relations.service。
    """
    return await service.get(session, relation_id)


@router.patch("/{relation_id}", response_model=RelationRead)
async def update_relation(
    relation_id: str,
    payload: RelationUpdate,
    session: AsyncSession = Depends(get_session),
) -> RelationRead:
    """局部更新关系动态属性（PATCH /api/relations/{id}；端点与 id/type 不可变）。

    作用: 参数解析 + 调用 service；仅更新显式提供的动态字段。
    参数: relation_id — 路径参数关系 id；payload — 更新载荷；session — 请求级会话。
    返回值: RelationRead（更新后）。异常: 404/422 由全局异常处理器统一出口。
    依赖: app.relations.service。
    """
    return await service.update(session, relation_id, payload)


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relation(relation_id: str, session: AsyncSession = Depends(get_session)) -> None:
    """删除关系（DELETE /api/relations/{id}；删除即解除对两端实体的引用）。

    作用: 参数解析 + 调用 service。
    参数: relation_id — 路径参数关系 id；session — 请求级会话。
    返回值: 无（204）。异常: 404 由全局异常处理器统一出口。
    依赖: app.relations.service。
    """
    await service.delete(session, relation_id)
