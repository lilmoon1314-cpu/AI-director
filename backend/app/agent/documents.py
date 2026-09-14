"""Agent 记忆文档 owner：模板建档、读取、CAS 更新与页面渲染。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import repository
from app.agent.models import MemoryDoc, MemoryDocSection, _utcnow
from app.agent.rendering import render_doc_page
from app.agent.schemas import (
    MemoryDocBrief,
    MemoryDocRead,
    MemoryDocSectionRead,
    SectionUpdate,
    generate_memory_doc_id,
    generate_memory_section_id,
)
from app.agent.templates import DOC_TEMPLATES, GUIDE_KINDS
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.projects import service as projects_service


def _doc_not_found(doc_id: str) -> NotFoundError:
    return NotFoundError(
        problem="记忆文档不存在",
        cause=f"doc_id '{doc_id}' 未在库中",
        fix="先调用 GET /api/agent/memory-docs 确认文档 id",
        detail={"doc_id": doc_id},
    )


async def _doc_read(db_session: AsyncSession, doc: MemoryDoc) -> MemoryDocRead:
    sections = await repository.list_sections(db_session, doc.id)
    return MemoryDocRead(
        id=doc.id,
        kind=doc.kind,
        title=doc.title,
        version=doc.version,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=[
            MemoryDocSectionRead(
                id=section.id,
                seq=section.seq,
                title=section.title,
                content=section.content,
                updated_by=section.updated_by,
                version=section.version,
                updated_at=section.updated_at,
            )
            for section in sections
        ],
    )


@checkpoint
async def create_doc(
    db_session: AsyncSession,
    project_id: str,
    kind: str,
    *,
    title: str | None = None,
    commit: bool = True,
) -> MemoryDocRead:
    """按模板建档；commit=False 时显式参与调用方的同库事务。"""
    template = DOC_TEMPLATES.get(kind)
    if template is None:
        raise ValidationError(
            problem="未知的记忆文档模板",
            cause=f"kind '{kind}' 不在内置模板中（{', '.join(sorted(DOC_TEMPLATES))}）",
            fix="改用内置模板 kind，或登记新模板",
            detail={"kind": kind},
        )
    resolved_project = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, resolved_project)
    if kind in GUIDE_KINDS:
        existing = await repository.find_doc_by_kind(db_session, resolved_project, kind)
        if existing is not None:
            raise ConflictError(
                problem=f"「{template['label']}」指导文档已存在（每项目仅一份）",
                cause=(
                    f"项目 '{resolved_project}' 下已存在同 kind（{kind}）的文档 "
                    f"'{existing.id}'，指导类文档项目内唯一"
                ),
                fix="直接编辑既有文档；确需重写请先删除原文档再新建",
                detail={
                    "project_id": resolved_project,
                    "kind": kind,
                    "existing_doc_id": existing.id,
                },
            )
    doc = MemoryDoc(
        id=generate_memory_doc_id(),
        project_id=resolved_project,
        kind=kind,
        title=title or str(template["title"]),
    )
    try:
        doc = await repository.add_doc(db_session, doc)
    except IntegrityError as exc:
        raise ConflictError(
            problem=f"「{template['label']}」指导文档已被并发创建",
            cause=f"项目 '{resolved_project}' 的 kind={kind} 已满足数据库唯一约束",
            fix="刷新文档目录并编辑已经创建的文档",
            detail={"project_id": resolved_project, "kind": kind},
        ) from exc
    for sequence, section_title in enumerate(template["sections"], start=1):
        await repository.add_section(
            db_session,
            MemoryDocSection(
                id=generate_memory_section_id(),
                doc_id=doc.id,
                seq=sequence,
                title=str(section_title),
            ),
        )
    if commit:
        await db_session.commit()
    return await _doc_read(db_session, doc)


@checkpoint
async def list_docs(db_session: AsyncSession, project_id: str) -> list[MemoryDocBrief]:
    """列出项目文档卡片及首个非空段预览。"""
    resolved = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, resolved)
    docs = await repository.list_docs(db_session, resolved)
    briefs: list[MemoryDocBrief] = []
    for doc in docs:
        sections = await repository.list_sections(db_session, doc.id)
        preview_source = next(
            (section.content for section in sections if section.content.strip()), ""
        )
        briefs.append(
            MemoryDocBrief(
                id=doc.id,
                kind=doc.kind,
                title=doc.title,
                version=doc.version,
                updated_at=doc.updated_at,
                preview=preview_source[:60],
            )
        )
    return briefs


@checkpoint
async def get_doc(db_session: AsyncSession, doc_id: str) -> MemoryDocRead:
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    return await _doc_read(db_session, doc)


@checkpoint
async def delete_doc(db_session: AsyncSession, doc_id: str) -> None:
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    await repository.delete_doc(db_session, doc)
    await db_session.commit()


@checkpoint
async def update_section(
    db_session: AsyncSession,
    doc_id: str,
    section_id: str,
    payload: SectionUpdate,
    *,
    updated_by: str,
    commit: bool = True,
) -> MemoryDocSectionRead:
    """数据库 CAS 更新段与文档版本；commit=False 时参与调用方事务。"""
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    section = await repository.get_section(db_session, section_id)
    if section is None or section.doc_id != doc_id:
        raise NotFoundError(
            problem="文档段不存在",
            cause=f"section_id '{section_id}' 不属于文档 '{doc_id}'",
            fix="先调用 GET /api/agent/memory-docs/{id} 确认段 id",
            detail={"doc_id": doc_id, "section_id": section_id},
        )
    now = _utcnow()
    changed = await repository.update_section_if_version(
        db_session,
        doc_id=doc_id,
        section_id=section_id,
        expected_version=payload.expected_version,
        content=payload.content,
        title=payload.title,
        updated_by=updated_by,
        updated_at=now,
    )
    if not changed:
        current = await repository.get_section(db_session, section_id)
        current_version = current.version if current is not None else section.version
        current_updater = current.updated_by if current is not None else section.updated_by
        raise ConflictError(
            problem="记忆文档段已被他人修改（版本冲突）",
            cause=(
                f"段当前版本为 v{current_version}（{current_updater} 更新），"
                f"请求基于 v{payload.expected_version}"
            ),
            fix="重新读取该段最新内容后再提交；agent 草案将基于新版本重新生成",
            detail={"doc_id": doc_id, "section_id": section_id, "current_version": current_version},
        )
    if commit:
        await db_session.commit()
    else:
        await db_session.flush()
    section.content = payload.content
    if payload.title is not None:
        section.title = payload.title
    section.version = payload.expected_version + 1
    section.updated_by = updated_by
    section.updated_at = now
    doc.version += 1
    doc.updated_at = now
    return MemoryDocSectionRead(
        id=section.id,
        seq=section.seq,
        title=section.title,
        content=section.content,
        updated_by=section.updated_by,
        version=section.version,
        updated_at=section.updated_at,
    )


@checkpoint
async def render_page(db_session: AsyncSession, doc_id: str) -> str:
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    sections = await repository.list_sections(db_session, doc_id)
    label = str(DOC_TEMPLATES.get(doc.kind, {}).get("label", doc.kind))
    return render_doc_page(doc.title, label, sections)
