"""F11 L1 单元测试：projects service 业务逻辑（依赖全部 mock，内存执行）。

mock 策略: 以内存字典替换 repository 数据访问——只验证 service 层的
校验/装配/计数器/默认项目保护/异常逻辑，不触数据库。
用例设计（等价类/边界值标注）见 docs/tests/F11_multi_project_foundation.md。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import NotFoundError, ValidationError
from app.projects import repository, service
from app.projects.models import Project
from app.projects.schemas import ProjectCreate, ProjectUpdate

pytestmark = pytest.mark.unit


class SessionStub:
    """最小会话桩：仅支持 commit/rollback 空操作（单元层不触数据库）。"""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


_SESSION = SessionStub()


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Project]:
    """内存项目存储 + repository 全量 mock。

    作用: 用字典模拟项目表（add/get_by_id/list_all/save/delete），实现
        service 层完全隔离。
    参数: monkeypatch — pytest 替换器。
    返回值: dict[str, Project]（id → 项目）。
    异常: 无。依赖: app.projects.repository。
    """
    projects: dict[str, Project] = {}

    async def fake_add(_session: Any, project: Project) -> Project:
        projects[project.id] = project
        return project

    async def fake_get_by_id(_session: Any, project_id: str) -> Project | None:
        return projects.get(project_id)

    async def fake_list_all(_session: Any) -> list[Project]:
        # 复刻仓储排序契约：updated_at 倒序（最近活跃在前），同刻以 id 升序稳定
        by_id = sorted(projects.values(), key=lambda p: p.id)
        return sorted(by_id, key=lambda p: p.updated_at, reverse=True)

    async def fake_save(_session: Any, project: Project) -> Project:
        projects[project.id] = project
        return project

    async def fake_delete(_session: Any, project: Project) -> None:
        projects.pop(project.id, None)

    monkeypatch.setattr(repository, "add", fake_add)
    monkeypatch.setattr(repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(repository, "list_all", fake_list_all)
    monkeypatch.setattr(repository, "save", fake_save)
    monkeypatch.setattr(repository, "delete", fake_delete)
    return projects


def _seed(
    store: dict[str, Project],
    project_id: str,
    *,
    name: str = "项目",
    entity_count: int = 0,
    relation_count: int = 0,
    updated_at: datetime | None = None,
) -> Project:
    """向内存库播种一个项目（返回 ORM 实例）。

    作用: 用例前置装配（计数器/活跃时间可控）。
    参数: store — 内存库；project_id/name/entity_count/relation_count/updated_at — 字段。
    返回值: Project。异常: 无。依赖: app.projects.models。
    """
    now = updated_at or datetime.now(UTC)
    project = Project(
        id=project_id,
        name=name,
        description="",
        entity_count=entity_count,
        relation_count=relation_count,
        created_at=now,
        updated_at=now,
    )
    store[project_id] = project
    return project


# ---------------- U1: 有效创建（等价类-有效） ----------------


async def test_create_generates_prefixed_id_and_zero_counters(
    store: dict[str, Project],
) -> None:
    """U1 创建成功：id 带 project- 前缀、计数器 0、字段完整回填。

    前置: 空 store；动作: create(有效载荷)；预期: id/计数器/时间戳完整。
    """
    created = await service.create(_SESSION, ProjectCreate(name="长安怪谈", description="盛唐志怪"))
    assert created.id.startswith("project-"), (
        f"【问题】生成的 id 未带 project- 前缀: {created.id}\n"
        "【原因】id 生成未按前缀规则装配\n"
        "【修复】检查 schemas.generate_project_id 的前缀"
    )
    assert created.name == "长安怪谈"
    assert created.description == "盛唐志怪"
    assert created.entity_count == 0 and created.relation_count == 0
    assert created.created_at is not None and created.updated_at is not None
    assert created.id in store


# ---------------- U2: 无效名称（等价类-无效：空/纯空白） ----------------


@pytest.mark.parametrize("blank_name", ["", "   "], ids=["empty", "whitespace-only"])
async def test_create_rejects_blank_names(blank_name: str) -> None:
    """U2 参数化 名称去空白后为空 → 请求模型构造即拒绝（422 来源）。

    设计依据: 等价类-无效（空串/纯空白同属一条校验规则的两个表现）。
    前置: 无；动作: 构造 ProjectCreate(name=blank)；预期: pydantic ValidationError。
    """
    with pytest.raises(PydanticValidationError):
        ProjectCreate(name=blank_name)


@pytest.mark.parametrize("blank_name", ["", "   "], ids=["empty", "whitespace-only"])
async def test_update_rejects_blank_names(blank_name: str) -> None:
    """U2 参数化（Update 面） 显式提供空白名 → 请求模型构造即拒绝。

    设计依据: 等价类-无效（与 Create 同一校验器，参数化覆盖两个模型面）。
    """
    with pytest.raises(PydanticValidationError):
        ProjectUpdate(name=blank_name)


# ---------------- U3: 改名（等价类-有效/无效-不存在） ----------------


async def test_rename_updates_name_and_missing_raises(store: dict[str, Project]) -> None:
    """U3 改名生效且活跃时间前进；目标不存在抛 NotFoundError（三要素+detail 整体相等）。

    设计依据: 等价类-有效改名 / 无效-资源不存在；错误断言按 E05 范式钉死完整契约。
    """
    seeded = _seed(
        store, "project-x", name="旧名", updated_at=datetime.now(UTC) - timedelta(hours=1)
    )
    old_updated = seeded.updated_at  # service.update 就地改写同一 ORM 实例，先捕获旧值
    renamed = await service.update(_SESSION, "project-x", ProjectUpdate(name="新名"))
    assert renamed.name == "新名"
    assert renamed.updated_at > old_updated, (
        "【问题】改名未刷新最近活跃时间\n"
        "【原因】update 未更新 updated_at\n"
        "【修复】检查 service.update 的时间戳维护"
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.update(_SESSION, "project-ghost", ProjectUpdate(name="任何名"))
    assert exc_info.value.problem == "项目不存在"
    assert exc_info.value.cause == "id 'project-ghost' 未在库中"
    assert exc_info.value.fix == "先调用 GET /api/projects 检索确认项目 id"
    assert exc_info.value.detail == {"project_id": "project-ghost"}


# ---------------- U4: 默认项目保护（等价类-无效-受保护资源） ----------------


@pytest.mark.parametrize("actor", ["delete", "assert_deletable"], ids=["delete", "precheck"])
async def test_default_project_delete_protected(store: dict[str, Project], actor: str) -> None:
    """U4 参数化 删除默认项目 → ValidationError（detail 整体相等，含 rule 标记）。

    设计依据: 等价类-无效-受保护资源（delete 与前置校验两个入口同一规则）。
    """
    _seed(store, service.DEFAULT_PROJECT_ID, name=service.DEFAULT_PROJECT_NAME)
    with pytest.raises(ValidationError) as exc_info:
        if actor == "delete":
            await service.delete(_SESSION, service.DEFAULT_PROJECT_ID)
        else:
            await service.assert_deletable(_SESSION, service.DEFAULT_PROJECT_ID)
    assert exc_info.value.problem == "默认项目不可删除"
    assert exc_info.value.detail == {
        "project_id": service.DEFAULT_PROJECT_ID,
        "rule": "default_project_protected",
    }


# ---------------- U5: 不存在项目（等价类-无效-不存在） ----------------


async def test_delete_and_get_missing_raise_not_found(store: dict[str, Project]) -> None:
    """U5 删除/读取不存在的项目 → NotFoundError（三要素文案 + detail 整体相等）。

    设计依据: 等价类-无效-不存在；错误断言按 E05 范式钉死完整契约。
    """
    with pytest.raises(NotFoundError) as delete_exc:
        await service.delete(_SESSION, "project-ghost")
    assert delete_exc.value.detail == {"project_id": "project-ghost"}
    assert delete_exc.value.fix == "先调用 GET /api/projects 检索确认项目 id"

    with pytest.raises(NotFoundError) as get_exc:
        await service.get(_SESSION, "project-ghost")
    assert get_exc.value.problem == "项目不存在"
    assert get_exc.value.cause == "id 'project-ghost' 未在库中"


# ---------------- U6: 计数器维护（边界值-下界 0 + 等价类-不存在） ----------------


async def test_touch_updates_counters_and_clamps_at_zero(
    store: dict[str, Project],
) -> None:
    """U6 计数器按增量更新、下界钳制 0、活跃时间刷新；目标不存在抛 NotFoundError。

    设计依据: 边界值-计数下界 0（负增量不得越界）+ 等价类-无效-不存在。
    """
    seeded = _seed(
        store, "project-x", entity_count=1, updated_at=datetime.now(UTC) - timedelta(hours=1)
    )

    await service.touch(_SESSION, "project-x", entity_delta=-1)
    assert seeded.entity_count == 0, "减量后计数应为 0"
    assert seeded.updated_at > datetime.now(UTC) - timedelta(hours=1)

    # 边界：计数已为 0 时再减不得为负（钳制）
    await service.touch(_SESSION, "project-x", entity_delta=-1)
    assert seeded.entity_count == 0, (
        f"【问题】计数器越过下界: {seeded.entity_count}\n"
        "【原因】touch 未对负增量钳制\n"
        "【修复】检查 touch 的 max(0, ...) 钳制逻辑"
    )

    await service.touch(_SESSION, "project-x", relation_delta=3)
    assert seeded.relation_count == 3

    with pytest.raises(NotFoundError) as exc_info:
        await service.touch(_SESSION, "project-ghost", entity_delta=1)
    assert exc_info.value.detail == {"project_id": "project-ghost"}


# ---------------- U7: 列表排序（等价类-多项目排序契约） ----------------


async def test_list_orders_by_recent_activity_then_id(store: dict[str, Project]) -> None:
    """U7 列表按 updated_at 倒序（最近活跃在前），同刻以 id 升序稳定。

    设计依据: 等价类-多项目排序契约（首屏卡片「最近编辑」语义）。
    """
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)
    _seed(store, "project-old", updated_at=base)
    _seed(store, "project-new", updated_at=base + timedelta(minutes=5))
    _seed(store, "project-tie-b", updated_at=base + timedelta(minutes=10))
    _seed(store, "project-tie-a", updated_at=base + timedelta(minutes=10))

    listed = await service.list_projects(_SESSION)
    assert [p.id for p in listed] == [
        "project-tie-a",
        "project-tie-b",
        "project-new",
        "project-old",
    ], (
        "【问题】项目列表顺序不符合「最近活跃倒序 + 同刻 id 升序」契约\n"
        "【原因】仓储 list_all 的排序子句或其 mock 契约漂移\n"
        "【修复】对照 repository.list_all 的 order_by 修正"
    )


# ---------------- U8: 详情完整字段（等价类-有效） ----------------


async def test_get_returns_full_fields(store: dict[str, Project]) -> None:
    """U8 读取详情 → 全字段完整（id/name/description/计数器/时间戳）。

    设计依据: 等价类-有效读取（响应契约完整性）。
    """
    _seed(
        store,
        "project-x",
        name="星海纪元",
        entity_count=7,
        relation_count=3,
    )
    got = await service.get(_SESSION, "project-x")
    assert (got.id, got.name, got.entity_count, got.relation_count) == (
        "project-x",
        "星海纪元",
        7,
        3,
    )
    assert got.created_at is not None and got.updated_at is not None


async def test_ensure_default_project_idempotent(store: dict[str, Project]) -> None:
    """U8 补充 ensure_default_project 幂等：重复调用不重复插入、字段符合常量。

    设计依据: 等价类-有效（lifespan 不变量）；边界值-重复调用（幂等）。
    """
    await service.ensure_default_project(_SESSION)
    await service.ensure_default_project(_SESSION)
    assert list(store) == [service.DEFAULT_PROJECT_ID], "默认项目应恰好一条"
    got = store[service.DEFAULT_PROJECT_ID]
    assert got.name == service.DEFAULT_PROJECT_NAME
    assert got.description == service.DEFAULT_PROJECT_DESCRIPTION
    assert got.entity_count == 0 and got.relation_count == 0
