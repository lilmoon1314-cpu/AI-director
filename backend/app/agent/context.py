"""Agent 对话上下文与滚动摘要 owner。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm, repository
from app.agent.budget import BudgetError, check_request
from app.agent.contracts import ContextFragment, ContextManifest, SourceRef
from app.agent.models import Conversation
from app.agent.prompts import (
    DocSectionRef,
    GraphDirectoryNode,
    assemble_messages,
    build_system_prompt,
    content_digest,
    render_doc_directory,
    render_graph_directory,
    wrap_data,
)
from app.agent.schemas import Perspective
from app.agent.scope import context_key, make_scope
from app.config import Settings
from app.core.observability import emit_event
from app.perspectives import service as perspectives_service
from app.projects import service as projects_service


async def _project_name(db_session: AsyncSession, project_id: str) -> str:
    """读取项目名；装饰性读取失败时保持原有 project_id 回退。"""
    try:
        project = await projects_service.get(db_session, project_id)
        return project.name
    except Exception:  # noqa: BLE001 - 项目名不应阻断对话
        return project_id


async def assemble_chat_context(
    db_session: AsyncSession,
    conversation: Conversation,
    *,
    perspective: Perspective,
    character_id: str,
    user_message: str,
    settings: Settings,
    exclude_message_id: str | None = None,
    tool_specs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """组装 system、可见项目数据、摘要、历史窗口与本轮输入。"""
    scope = make_scope(conversation.project_id, perspective, character_id)
    fragments: list[ContextFragment] = []
    graph = await perspectives_service.get_graph(
        db_session,
        perspective=perspective,
        character_id=character_id or None,
        project_id=conversation.project_id,
    )
    graph_directory = render_graph_directory(
        [
            GraphDirectoryNode(
                id=node.id,
                type=node.type,
                name=node.name,
                aliases=list(node.aliases),
            )
            for node in sorted(graph.nodes, key=lambda node: node.id)[
                : settings.agent_directory_page_size
            ]
        ]
    )

    graph_directory += "\n更多目录可用 list_context_directory 工具分页读取。"
    docs = (
        await repository.list_docs(db_session, conversation.project_id)
        if perspective == "author"
        else []
    )
    doc_dir_entries: list[dict[str, Any]] = []
    doc_sections: list[DocSectionRef] = []
    for doc in docs:
        sections = await repository.list_sections(db_session, doc.id)
        fragments.extend(
            ContextFragment(
                source=SourceRef(
                    scope=scope, kind="section", source_id=section.id, version=section.version
                ),
                reason="author guidance",
                estimated_tokens=len(section.content.encode("utf-8")),
                disposition="included",
                required=True,
            )
            for section in sections
        )
        doc_dir_entries.append(
            {
                "doc_id": doc.id,
                "title": doc.title,
                "sections": [
                    {
                        "seq": section.seq,
                        "title": section.title,
                        "digest": content_digest(section.content),
                    }
                    for section in sections
                ],
            }
        )
        doc_sections.extend(
            DocSectionRef(
                label=f"文档 {doc.id} 段 {section.id} v{section.version}《{doc.title}》"
                f"第{section.seq}段·{section.title}",
                title=section.title,
                digest=content_digest(section.content),
                content=section.content,
            )
            for section in sections
        )

    key = context_key(perspective, character_id)
    state = await repository.summary_partition(db_session, conversation, key)
    summary = state.summary if state else ""
    cursor = state.summary_until_id if state else None
    rows = [
        row
        for row in await repository.list_messages(db_session, conversation.id)
        if (getattr(row, "context_key", None) or "author") == key
    ]
    if exclude_message_id is not None:
        rows = [row for row in rows if row.id != exclude_message_id]
    if cursor is None:
        tail = rows
    else:
        cursor_index = next((index for index, row in enumerate(rows) if row.id == cursor), -1)
        tail = rows[cursor_index + 1 :]
    # Never drop uncovered messages just because summary maintenance failed.
    windowed_tail = tail
    history = [
        {
            "role": message.role if message.role != "summary" else "assistant",
            "content": wrap_data(f"历史消息 {message.id}", message.content),
        }
        for message in windowed_tail
    ]
    history.append({"role": "user", "content": user_message})
    if exclude_message_id:
        fragments.append(
            ContextFragment(
                source=SourceRef(scope=scope, kind="message", source_id=exclude_message_id),
                reason="current user input",
                estimated_tokens=len(user_message.encode("utf-8")),
                disposition="included",
                required=True,
            )
        )
    fragments.extend(
        ContextFragment(
            source=SourceRef(scope=scope, kind="message", source_id=row.id),
            reason="uncovered history",
            estimated_tokens=len(row.content.encode("utf-8")),
            disposition="included",
            required=True,
        )
        for row in tail
    )
    if summary:
        fragments.append(
            ContextFragment(
                source=SourceRef(scope=scope, kind="summary", source_id=f"{conversation.id}/{key}"),
                reason=f"summary cursor {cursor}",
                estimated_tokens=len(summary.encode("utf-8")),
                disposition="included",
                required=True,
            )
        )

    project_name = await _project_name(db_session, conversation.project_id)
    fragments.append(
        ContextFragment(
            source=SourceRef(
                scope=scope, kind="project_metadata", source_id=conversation.project_id
            ),
            reason="project identity",
            estimated_tokens=len(project_name.encode("utf-8")),
            disposition="included",
            required=True,
        )
    )
    compiled = assemble_messages(
        system=build_system_prompt(project_name=project_name),
        doc_sections=doc_sections,
        graph_directory=wrap_data("项目名称", project_name)
        + "\n"
        + wrap_data("上下文作用域", f"{conversation.project_id}/{key}")
        + "\n"
        + graph_directory,
        doc_directory=render_doc_directory(doc_dir_entries[: settings.agent_directory_page_size]),
        summary=wrap_data(f"分区 {key} 摘要，覆盖至 {cursor}", summary) if summary else "",
        history=history,
        budget=settings.agent_context_max_tokens,
    )
    directories_included = True
    try:
        input_tokens = check_request(compiled, tool_specs, settings)
    except BudgetError:
        # Directories can be recovered through a scoped paging tool; authored guidance cannot.
        compiled = assemble_messages(
            system=build_system_prompt(project_name=project_name),
            doc_sections=doc_sections,
            graph_directory=wrap_data(
                "项目名称与作用域", f"{project_name} / {conversation.project_id}/{key}"
            )
            + "\n目录因预算省略，可用 list_context_directory 分页读取。",
            doc_directory="目录因预算省略，可用 list_context_directory 分页读取。",
            summary=wrap_data(f"分区 {key} 摘要，覆盖至 {cursor}", summary) if summary else "",
            history=history,
            budget=settings.agent_context_max_tokens,
        )
        input_tokens = check_request(compiled, tool_specs, settings)
        directories_included = False
        emit_event(
            "agent_context_directory_omitted",
            component="app.agent.context",
            data={"conversation_id": conversation.id, "context_key": key},
        )
    fragments.append(
        ContextFragment(
            source=SourceRef(
                scope=scope, kind="graph_projection", source_id=conversation.project_id
            ),
            reason="visible directory page"
            if directories_included
            else "recoverable directory omitted",
            estimated_tokens=len(graph_directory.encode("utf-8")) if directories_included else 0,
            disposition="included" if directories_included else "omitted",
        )
    )
    manifest = ContextManifest(
        scope=scope,
        fragments=tuple(fragments),
        estimator="utf8-bytes-v1",
        input_tokens=input_tokens,
        output_reserve=settings.agent_output_reserve_tokens,
        budget=settings.agent_context_max_tokens,
    )
    emit_event(
        "agent_context_manifest",
        component="app.agent.context",
        data={"conversation_id": conversation.id, "manifest": manifest.model_dump()},
    )
    return compiled


async def maintain_rolling_summary(
    db_session: AsyncSession,
    conversation: Conversation,
    *,
    settings: Settings,
    perspective: Perspective = "author",
    character_id: str = "",
) -> None:
    """把历史窗口溢出增量压缩进摘要；失败或空结果保持原状态。"""
    key = context_key(perspective, character_id)
    state = await repository.summary_partition(db_session, conversation, key)
    cursor = state.summary_until_id if state else None
    rows = [
        row
        for row in await repository.list_messages(db_session, conversation.id)
        if (getattr(row, "context_key", None) or "author") == key
    ]
    if cursor is None:
        tail = rows
    else:
        cursor_index = next((index for index, row in enumerate(rows) if row.id == cursor), -1)
        tail = rows[cursor_index + 1 :]
    overflow_count = len(tail) - settings.agent_history_window_messages
    if overflow_count <= 0:
        return
    overflow = tail[:overflow_count]
    transcript = "\n".join(
        f"[{message.id}] {message.role}: {message.content}" for message in overflow
    )
    summary = state.summary if state else ""
    combined = (summary + "\n" if summary else "") + transcript
    instruction = (
        "把对话增量压缩为一段紧凑中文摘要，保留创作决策、作者意见、未决问题与关键设定；"
        "不要逐句复述。"
    )
    try:
        new_summary = await llm.summarize(combined, instruction)
    except Exception as exc:  # noqa: BLE001 - 摘要维护不阻断已完成对话轮
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": type(exc).__name__},
        )
        return
    if not new_summary.strip():
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": "EmptySummary"},
        )
        return
    if state is None:
        state = await repository.summary_partition(db_session, conversation, key, create=True)
    assert state is not None
    state.summary = new_summary
    state.summary_until_id = overflow[-1].id
    await repository.save_conversation(db_session, conversation)
