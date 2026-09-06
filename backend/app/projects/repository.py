"""projects 模块数据访问层：唯一允许 import 本模块 ORM 模型的层。

事务约定: 本层不 commit/rollback（事务边界在 service 层，backend/CONSTRAINTS.md）。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project


async def add(session: AsyncSession, project: Project) -> Project:
    """插入一条项目记录。

    作用: 新建项目（不提交事务，由 service 层控制）。
    参数: session — 数据库会话；project — 已填充字段的 ORM 实例。
    返回值: Project。异常: 无（约束冲突由 service 捕获处理）。
    依赖: SQLAlchemy ORM。
    """
    session.add(project)
    await session.flush()
    return project


async def get_by_id(session: AsyncSession, project_id: str) -> Project | None:
    """按 id 查询单个项目。

    作用: 详情/更新/删除/归属校验的取数入口。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: Project 或 None（不存在）。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(Project, project_id)


async def list_all(session: AsyncSession) -> list[Project]:
    """查询全部项目（按最近活跃倒序）。

    作用: 项目首屏与顶栏切换器的数据源；updated_at 倒序让最近编辑的项目
        排在最前（DESIGN.md §5.1），id 作次序键保证同刻更新的顺序稳定。
    参数: session — 数据库会话。
    返回值: list[Project]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(Project).order_by(Project.updated_at.desc(), Project.id)
    return list(await session.scalars(stmt))


async def save(session: AsyncSession, project: Project) -> Project:
    """保存已修改的项目（UPDATE）。

    作用: 改名 / 计数器维护落库（不提交事务；touch 在调用方事务内执行）。
    参数: session — 数据库会话；project — 已在内存中修改的 ORM 实例。
    返回值: Project。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    """删除项目记录（不提交事务；级联编排见 router，主库删除原子提交于 service.delete）。

    作用: 物理删除项目行；项目内实体 / 关系已由级联编排先行删除。
    参数: session — 数据库会话；project — 待删除 ORM 实例。
    返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(project)
    await session.flush()
