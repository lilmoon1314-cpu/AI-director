"""projects 模块 service 层：模块唯一对外接口（其他模块只允许 import 本层）。

事务边界: 常规写函数自行 commit/rollback；touch 为事务内辅助函数（不自行
commit——由调用方 entities / relations 的事务保证原子性，backend/CONSTRAINTS.md
「模块解耦与事务」的显式例外，见本模块 CONSTRAINTS.md）。
依赖方向: 本层仅依赖 core 与本模块内部层，零领域模块依赖（DECISIONS 2026-09-06；
跨模块级联删除的编排位于 router 组合层，避免 projects↔领域模块循环 import）。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.projects import repository
from app.projects.models import Project, _utcnow
from app.projects.schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    generate_project_id,
)

# 默认项目：固定 id；迁移把存量数据打包进默认项目（向后兼容），应用启动时
# 幂等确保其存在（lifespan 调 ensure_default_project）；不可删除、可改名。
DEFAULT_PROJECT_ID = "project-default"
DEFAULT_PROJECT_NAME = "默认项目"
DEFAULT_PROJECT_DESCRIPTION = "未指定项目的数据兜底归档（可改名用作正式项目）"


def _not_found(project_id: str) -> NotFoundError:
    """构造项目不存在的三要素异常。

    作用: 统一 NotFoundError 的消息质量（三要素完整，U8/I4 断言契约）。
    参数: project_id — 未找到的项目 id。返回值: NotFoundError。异常: 无。依赖: 无。
    """
    return NotFoundError(
        problem="项目不存在",
        cause=f"id '{project_id}' 未在库中",
        fix="先调用 GET /api/projects 检索确认项目 id",
        detail={"project_id": project_id},
    )


def _protected_default() -> ValidationError:
    """构造默认项目不可删除的三要素异常。

    作用: 删除保护规则的统一错误出口（U4/I5 断言契约）。
    参数: 无。返回值: ValidationError。异常: 无。依赖: 无。
    """
    return ValidationError(
        problem="默认项目不可删除",
        cause=(
            f"默认项目（id='{DEFAULT_PROJECT_ID}'）是不带 project_id 请求的兜底归属目标，"
            "删除后该类写入将失效"
        ),
        fix="可将其改名后作为正式项目使用；或先把其数据迁移到其他项目",
        detail={"project_id": DEFAULT_PROJECT_ID, "rule": "default_project_protected"},
    )


def _new_project(schema: ProjectCreate) -> Project:
    """由请求模型构造 ORM 实例（id 系统生成，时间戳与计数器装配即填充）。

    作用: 创建路径的项目装配；时间戳在此填充而非依赖 flush 默认值，
        保证未落库状态（单元测试 mock）下响应模型可完整序列化。
    参数: schema — 已通过请求校验的创建载荷。
    返回值: Project（未入库，计数器为 0）。异常: 无。依赖: app.projects.schemas。
    """
    now = _utcnow()
    return Project(
        id=generate_project_id(),
        name=schema.name,
        description=schema.description,
        entity_count=0,
        relation_count=0,
        created_at=now,
        updated_at=now,
    )


@checkpoint
async def ensure_default_project(session: AsyncSession) -> None:
    """幂等确保默认项目存在（应用 lifespan 启动时调用）。

    作用:
        为「无 project_id 请求落默认项目」的兜底语义提供不变量——
        无论库是 Alembic 迁移而来还是 create_all 建表（测试），默认项目恒存在。
    参数: session — 数据库会话。
    返回值: 无。
    异常: 无（已存在则静默返回）。
    依赖: app.projects.repository。
    """
    if await repository.get_by_id(session, DEFAULT_PROJECT_ID) is not None:
        return
    now = _utcnow()
    await repository.add(
        session,
        Project(
            id=DEFAULT_PROJECT_ID,
            name=DEFAULT_PROJECT_NAME,
            description=DEFAULT_PROJECT_DESCRIPTION,
            entity_count=0,
            relation_count=0,
            created_at=now,
            updated_at=now,
        ),
    )
    await session.commit()


@checkpoint
async def ensure_exists(session: AsyncSession, project_id: str) -> None:
    """校验项目存在（领域模块归属校验入口，如 entities/relations 创建时）。

    作用: 「写入按 project 维度校验归属」的统一出口；缺失即 404。
    参数: session — 数据库会话；project_id — 待校验项目 id。
    返回值: 无。
    异常: NotFoundError — 项目不存在。
    依赖: app.projects.repository。
    """
    if await repository.get_by_id(session, project_id) is None:
        raise _not_found(project_id)


@checkpoint
async def create(session: AsyncSession, schema: ProjectCreate) -> ProjectRead:
    """创建项目（id 系统生成，计数器从 0 起步）。

    作用: 项目创建的业务入口（项目首屏「新建项目」）。
    参数: session — 数据库会话；schema — 创建载荷（名称已经去空白校验）。
    返回值: ProjectRead。
    异常: 无（名称校验在请求层完成）。
    依赖: app.projects.repository。
    """
    project = await repository.add(session, _new_project(schema))
    await session.commit()
    return ProjectRead.model_validate(project)


@checkpoint
async def get(session: AsyncSession, project_id: str) -> ProjectRead:
    """按 id 读取项目详情。

    作用: 详情查询业务入口。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: ProjectRead。
    异常: NotFoundError — 项目不存在。
    依赖: app.projects.repository。
    """
    project = await repository.get_by_id(session, project_id)
    if project is None:
        raise _not_found(project_id)
    return ProjectRead.model_validate(project)


@checkpoint
async def list_projects(session: AsyncSession) -> list[ProjectRead]:
    """列出全部项目（按最近活跃倒序，供项目首屏与顶栏切换器）。

    作用: 列表查询业务入口（U7 排序契约：updated_at 倒序 + id 稳定序）。
    参数: session — 数据库会话。
    返回值: list[ProjectRead]。
    异常: 无。依赖: app.projects.repository。
    """
    return [ProjectRead.model_validate(p) for p in await repository.list_all(session)]


@checkpoint
async def update(session: AsyncSession, project_id: str, schema: ProjectUpdate) -> ProjectRead:
    """局部更新项目（改名 / 描述；id 与计数器不可变）。

    作用: 局部更新业务入口；更新同时刷新 updated_at（最近活跃）。
    参数: session — 数据库会话；project_id — 项目 id；schema — 更新载荷。
    返回值: ProjectRead（更新后状态）。
    异常: NotFoundError — 项目不存在。
    依赖: app.projects.repository。
    """
    project = await repository.get_by_id(session, project_id)
    if project is None:
        raise _not_found(project_id)
    if schema.name is not None:
        project.name = schema.name
    if schema.description is not None:
        project.description = schema.description
    project.updated_at = _utcnow()
    project = await repository.save(session, project)
    await session.commit()
    return ProjectRead.model_validate(project)


@checkpoint
async def assert_deletable(session: AsyncSession, project_id: str) -> None:
    """删除前置校验（存在 + 非默认项目）。

    作用: 级联删除编排（router）在执行任何数据删除前先行调用，保证
        「默认项目保护」判定先于领域数据删除发生（失败即整体未动）。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: 无。
    异常: NotFoundError — 项目不存在；ValidationError — 默认项目受保护。
    依赖: app.projects.repository。
    """
    if await repository.get_by_id(session, project_id) is None:
        raise _not_found(project_id)
    if project_id == DEFAULT_PROJECT_ID:
        raise _protected_default()


@checkpoint
async def delete(session: AsyncSession, project_id: str) -> None:
    """删除项目行并提交（级联删除主库部分的收口提交）。

    作用:
        router 级联编排的最后一步：此时该项目的关系 / 实体已在同一会话中
        删除（未提交），本函数的 commit 把「关系 + 实体 + 项目行」原子落库
        （跨库资产清扫在提交后独立执行，失败由读取时孤儿清扫兜底）。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: 无。
    异常: NotFoundError — 项目不存在；ValidationError — 默认项目受保护。
    依赖: app.projects.repository。
    """
    project = await repository.get_by_id(session, project_id)
    if project is None:
        raise _not_found(project_id)
    if project_id == DEFAULT_PROJECT_ID:
        raise _protected_default()
    await repository.delete(session, project)
    await session.commit()


@checkpoint
async def touch(
    session: AsyncSession,
    project_id: str,
    *,
    entity_delta: int = 0,
    relation_delta: int = 0,
) -> None:
    """事务内维护项目计数器与最近活跃时间（不自行 commit）。

    作用:
        反规范化计数器的唯一写入口——entities / relations 写路径在各自事务内
        调用（同库原子）；updated_at 刷新使首屏「最近编辑」反映真实活动。
        计数器钳制下界 0（边界值：删除流不应使计数为负，U6）。
    参数:
        session — 数据库会话（调用方事务）；project_id — 项目 id；
        entity_delta — 实体计数增量；relation_delta — 关系计数增量。
    返回值: 无。
    异常: NotFoundError — 项目不存在。
    依赖: app.projects.repository（本函数不 commit，由调用方事务提交）。
    """
    project = await repository.get_by_id(session, project_id)
    if project is None:
        raise _not_found(project_id)
    project.entity_count = max(0, project.entity_count + entity_delta)
    project.relation_count = max(0, project.relation_count + relation_delta)
    project.updated_at = _utcnow()
    await repository.save(session, project)
