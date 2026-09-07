"""F10 L1 单元测试：记忆文档段级模型与 HTML 渲染（repository mock，内存执行）。

覆盖: 模板建档/段级更新（用户与 agent）/CAS 冲突/HTML 全转义。
用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import repository
from app.agent import service as agent_service
from app.agent.rendering import render_doc_page
from app.agent.schemas import SectionUpdate
from app.core.exceptions import ConflictError, ValidationError
from app.projects import service as projects_service

pytestmark = pytest.mark.unit


class Store:
    """内存文档/段存储（模拟 repository 语义）。"""

    def __init__(self) -> None:
        self.docs: dict[str, SimpleNamespace] = {}
        self.sections: dict[str, SimpleNamespace] = {}
        self._counter = 0

    def next_id(self, prefix: str) -> str:
        """生成确定性 id（断言稳定用）。"""
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def add_doc(self, doc: SimpleNamespace) -> SimpleNamespace:
        """登记文档。"""
        self.docs[doc.id] = doc
        return doc

    def add_section(self, section: SimpleNamespace) -> SimpleNamespace:
        """登记段。"""
        self.sections[section.id] = section
        return section


def _apply_flush_defaults(obj: Any) -> None:
    """模拟 ORM flush 时的 Python 默认值填充（CommitStub 不触发真实 flush）。"""
    from datetime import UTC, datetime

    defaults: dict[str, Any] = {
        "content": "",
        "version": 1,
        "updated_by": "user",
        "title": "",
        "summary": "",
        "summary_until_id": None,
    }
    for name, value in defaults.items():
        if getattr(obj, name, "missing") is None:
            setattr(obj, name, value)
    if getattr(obj, "created_at", None) is None:
        obj.created_at = datetime.now(UTC)
    if getattr(obj, "updated_at", None) is None:
        obj.updated_at = datetime.now(UTC)


def _install(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """把内存存储接入 repository 全部读写口（async 语义与真仓一致）。"""

    async def fake_add_doc(_s: Any, doc: Any) -> Any:
        _apply_flush_defaults(doc)
        return store.add_doc(doc)

    async def fake_get_doc(_s: Any, doc_id: str) -> Any:
        return store.docs.get(doc_id)

    async def fake_list_docs(_s: Any, project_id: str) -> list[Any]:
        return [d for d in store.docs.values() if d.project_id == project_id]

    async def fake_add_section(_s: Any, section: Any) -> Any:
        _apply_flush_defaults(section)
        return store.add_section(section)

    async def fake_get_section(_s: Any, section_id: str) -> Any:
        return store.sections.get(section_id)

    async def fake_list_sections(_s: Any, doc_id: str) -> list[Any]:
        return sorted(
            (s for s in store.sections.values() if s.doc_id == doc_id), key=lambda x: x.seq
        )

    async def fake_save_section(_s: Any, section: Any) -> Any:
        store.sections[section.id] = section
        return section

    async def fake_ensure_exists(_s: Any, _project_id: str) -> None:
        return None

    monkeypatch.setattr(repository, "add_doc", fake_add_doc)
    monkeypatch.setattr(repository, "get_doc", fake_get_doc)
    monkeypatch.setattr(repository, "list_docs", fake_list_docs)
    monkeypatch.setattr(repository, "add_section", fake_add_section)
    monkeypatch.setattr(repository, "get_section", fake_get_section)
    monkeypatch.setattr(repository, "list_sections", fake_list_sections)
    monkeypatch.setattr(repository, "save_section", fake_save_section)
    monkeypatch.setattr(projects_service, "ensure_exists", fake_ensure_exists)


class CommitStub:
    """会话桩：commit/rollback 计数（事务在 service 层的约定验证）。"""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        """计数 commit。"""
        self.commits += 1

    async def rollback(self) -> None:
        """空操作。"""
        return None


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Store:
    """内存存储 + repository mock。"""
    store = Store()
    _install(store, monkeypatch)
    return store


@pytest.fixture
def db_session() -> CommitStub:
    """会话桩。"""
    return CommitStub()


@pytest.mark.parametrize(
    ("kind", "first_section_title"),
    [("positioning", "一句话定位"), ("style", "叙事视角")],
    ids=["模板-世界观定位", "模板-风格约定"],
)
async def test_create_doc_from_template(
    store: Store, db_session: CommitStub, kind: str, first_section_title: str
) -> None:
    """U18 参数化: 内置模板建档 → 初始段生成（等价类-有效模板）。"""
    doc = await agent_service.create_doc(db_session, "proj-1", kind)

    assert doc.kind == kind and doc.version == 1, f"文档元数据不符: {doc}"
    assert len(doc.sections) == 4, f"模板应生成 4 个初始段: {len(doc.sections)}"
    assert doc.sections[0].title == first_section_title, f"首段标题不符: {doc.sections[0]}"
    assert doc.sections[0].content == "" and doc.sections[0].version == 1, "初始段必须为空白 v1"
    assert db_session.commits == 1, "建档必须恰提交一次事务"


async def test_create_doc_unknown_kind(store: Store, db_session: CommitStub) -> None:
    """U18 补充: 未知模板 → ValidationError 三要素（等价类-无效-未知模板）。"""
    with pytest.raises(ValidationError) as excinfo:
        await agent_service.create_doc(db_session, "proj-1", "story_outline_v99")
    assert excinfo.value.problem and excinfo.value.fix, f"三要素必须齐全: {excinfo.value}"
    assert not store.docs, "失败建档不得留下半成品文档"


async def test_update_section_by_user_bumps_versions(store: Store, db_session: CommitStub) -> None:
    """U19: 用户段级保存 → 段 version+1/updated_by=user，文档 version 同步 +1。

    设计依据: 等价类-段级隔离写入（其余段不动）。
    """
    doc = await agent_service.create_doc(db_session, "proj-1", "style")
    other_seq = doc.sections[3]

    updated = await agent_service.update_section(
        db_session,
        doc.id,
        doc.sections[0].id,
        SectionUpdate(content="第一人称限制视角。", expected_version=1),
        updated_by="user",
    )

    assert updated.version == 2 and updated.updated_by == "user", f"段版本推进不符: {updated}"
    assert updated.content == "第一人称限制视角。"
    doc_after = await agent_service.get_doc(db_session, doc.id)
    assert doc_after.version == 2, f"文档 version 必须同步 +1: {doc_after.version}"
    assert other_seq.content == "" or True  # other_seq 是快照对象；以下用最新读取验证
    fresh_other = next(s for s in doc_after.sections if s.seq == 4)
    assert fresh_other.version == 1 and fresh_other.content == "", "其余段不得被波及"


async def test_agent_patch_cas_conflict_never_overwrites(
    store: Store, db_session: CommitStub
) -> None:
    """U20: agent patch CAS——版本一致落库 updated_by=agent；不一致 409 且原段不动。

    设计依据: 等价类-并发冲突两态（用户手改优先，绝不静默覆盖）。
    """
    doc = await agent_service.create_doc(db_session, "proj-1", "style")
    section = doc.sections[0]

    applied = await agent_service.update_section(
        db_session,
        doc.id,
        section.id,
        SectionUpdate(content="agent 产出的基调描述。", expected_version=1),
        updated_by="agent",
    )
    assert applied.version == 2 and applied.updated_by == "agent", "CAS 一致必须成功落库"

    with pytest.raises(ConflictError) as excinfo:
        await agent_service.update_section(
            db_session,
            doc.id,
            section.id,
            SectionUpdate(content="基于旧版本的过期 patch。", expected_version=1),
            updated_by="agent",
        )
    err = excinfo.value
    assert err.problem and err.cause and err.fix, f"冲突三要素必须齐全: {err}"
    assert err.detail["current_version"] == 2, f"冲突 detail 必须携带当前版本: {err.detail}"
    fresh = await agent_service.get_doc(db_session, doc.id)
    assert fresh.sections[0].content == "agent 产出的基调描述。", (
        "冲突后原段内容必须原样保留（绝不覆盖）"
    )


async def test_render_doc_page_escapes_and_self_contained(
    store: Store, db_session: CommitStub
) -> None:
    """U21: HTML 渲染自包含且全转义（等价类-无效-注入载荷）。"""
    sections = [
        SimpleNamespace(
            seq=1,
            title="禁忌</title><script>alert(1)</script>",
            content='正常 & <b>加粗</b> "引号"',
            updated_by="user",
            version=1,
        ),
        SimpleNamespace(seq=2, title="空段", content="  ", updated_by="agent", version=2),
    ]
    html_text = render_doc_page("风格约定", "风格约定", sections)

    assert html_text.startswith("<!DOCTYPE html>") and "<style>" in html_text, (
        "必须为自包含 HTML（内联样式）"
    )
    assert "<script>" not in html_text and "<script " not in html_text, (
        f"注入载荷必须被转义: {html_text[:400]}"
    )
    assert "&lt;script&gt;" in html_text, "转义后的实体必须出现在输出中"
    assert "（本段暂无内容）" in html_text, "空白段必须以占位样式呈现"
    assert "agent 更新 · v2" in html_text, "段元信息（更新者/版本）必须呈现"
