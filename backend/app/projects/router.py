"""projects 模块 HTTP 路由：参数解析、响应包装与跨模块级联编排。

路由总表见 backend/ARCHITECTURE.md §7（/api/projects 前缀）。
级联删除编排（组合层例外）:
    DELETE /api/projects/{id} 需要跨 projects / relations / entities / assets 四模块
    协作。projects 业务层零领域依赖（import-linter 契约），故编排位于本层——
    先校验（assert_deletable）→ 删关系（FK RESTRICT 先行）→ 删实体（收集 id）→
    projects.delete 原子提交主库 → assets 显式清扫（独立事务，失败由读取时
    孤儿清扫兜底，DECISIONS 2026-09-06）。业务规则仍在各模块 service。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import service as agent_service
from app.assets import service as assets_service
from app.core.db import get_session
from app.entities import service as entities_service
from app.projects import service
from app.projects.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from app.relations import service as relations_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, session: AsyncSession = Depends(get_session)
) -> ProjectRead:
    """创建项目（POST /api/projects）。

    作用: 参数解析 + 调用 service；id 由系统生成并随响应返回。
    参数: payload — 创建载荷；session — 请求级数据库会话（依赖注入）。
    返回值: ProjectRead（201）。异常: 422 由全局异常处理器统一出口。
    依赖: app.projects.service。
    """
    return await service.create(session, payload)


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectRead]:
    """列出全部项目（GET /api/projects，按最近活跃倒序）。

    作用: 项目首屏与顶栏切换器数据源。
    参数: session — 请求级数据库会话。
    返回值: list[ProjectRead]。异常: 无。
    依赖: app.projects.service。
    """
    return await service.list_projects(session)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, session: AsyncSession = Depends(get_session)) -> ProjectRead:
    """查询项目详情（GET /api/projects/{id}）。

    作用: 参数解析 + 调用 service。
    参数: project_id — 路径参数项目 id；session — 请求级数据库会话。
    返回值: ProjectRead。异常: 404 由全局异常处理器统一出口。
    依赖: app.projects.service。
    """
    return await service.get(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    """局部更新项目（PATCH /api/projects/{id}；id 与计数器不可变）。

    作用: 参数解析 + 调用 service；改名 / 描述更新。
    参数: project_id — 路径参数项目 id；payload — 更新载荷；session — 请求级会话。
    返回值: ProjectRead（更新后）。异常: 404/422 由全局异常处理器统一出口。
    依赖: app.projects.service。
    """
    return await service.update(session, project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    asset_session: AsyncSession = Depends(assets_service.get_assets_session),
) -> None:
    """删除项目并级联清理（DELETE /api/projects/{id}）。

    作用:
        跨模块级联编排（组合层，见模块 docstring）：校验 → 删该项目全部关系
        → 删该项目全部实体（收集实体 id）→ 删项目行并原子提交主库 →
        按实体 id 集合显式清扫资产库（记录 + 图片 + 物理文件）。
    参数:
        project_id — 路径参数项目 id；session — 主库会话；
        asset_session — 资产库会话（独立事务）。
    返回值: 无（204）。
    异常: 404（项目不存在）/ 422（默认项目受保护）由全局异常处理器统一出口；
        主库删除原子提交，资产清扫失败由读取时孤儿清扫兜底。
    依赖: app.projects.service、app.relations.service、app.entities.service、
        app.assets.service、app.agent.service（F10：会话与记忆文档清理）。
    """
    await service.assert_deletable(session, project_id)
    await relations_service.delete_by_project(session, project_id)
    entity_ids = await entities_service.delete_by_project(session, project_id)
    await agent_service.delete_project_data(session, project_id)
    await service.delete(session, project_id)
    if entity_ids:
        await assets_service.sweep_entity_assets(asset_session, entity_ids)
