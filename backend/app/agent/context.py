"""Agent 对话上下文与滚动摘要 owner。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm, repository
from app.agent.models import Conversation
from app.agent.prompts import (
    DocSectionRef,
    GraphDirectoryNode,
    assemble_messages,
    build_system_prompt,
    content_digest,
    render_doc_directory,
    render_graph_directory,
)
from app.agent.schemas import Perspective
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
) -> list[dict[str, str]]:
    """组装 system、可见项目数据、摘要、历史窗口与本轮输入。"""
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
            for node in graph.nodes
        ]
    )

    docs = await repository.list_docs(db_session, conversation.project_id)
    doc_dir_entries: list[dict[str, Any]] = []
    doc_sections: list[DocSectionRef] = []
    for doc in docs:
        sections = await repository.list_sections(db_session, doc.id)
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
                label=f"文档《{doc.title}》第{section.seq}段·{section.title}",
                title=section.title,
                digest=content_digest(section.content),
                content=section.content,
            )
            for section in sections
        )

    rows = await repository.list_messages(db_session, conversation.id)
    if exclude_message_id is not None:
        rows = [row for row in rows if row.id != exclude_message_id]
    if conversation.summary_until_id is None:
        tail = rows
    else:
        cursor_index = next(
            (index for index, row in enumerate(rows) if row.id == conversation.summary_until_id), -1
        )
        tail = rows[cursor_index + 1 :]
    windowed_tail = tail[-settings.agent_history_window_messages :]
    history = [
        {
            "role": message.role if message.role != "summary" else "assistant",
            "content": message.content,
        }
        for message in windowed_tail
    ]
    history.append({"role": "user", "content": user_message})

    project_name = await _project_name(db_session, conversation.project_id)
    return assemble_messages(
        system=build_system_prompt(project_name=project_name),
        doc_sections=doc_sections,
        graph_directory=graph_directory,
        doc_directory=render_doc_directory(doc_dir_entries),
        summary=conversation.summary,
        history=history,
        budget=settings.agent_context_max_tokens,
    )


async def maintain_rolling_summary(
    db_session: AsyncSession, conversation: Conversation, *, settings: Settings
) -> None:
    """把历史窗口溢出增量压缩进摘要；失败或空结果保持原状态。"""
    rows = await repository.list_messages(db_session, conversation.id)
    if conversation.summary_until_id is None:
        tail = rows
    else:
        cursor_index = next(
            (index for index, row in enumerate(rows) if row.id == conversation.summary_until_id), -1
        )
        tail = rows[cursor_index + 1 :]
    overflow_count = len(tail) - settings.agent_history_window_messages
    if overflow_count <= 0:
        return
    overflow = tail[:overflow_count]
    transcript = "\n".join(f"{message.role}: {message.content}" for message in overflow)
    combined = (conversation.summary + "\n" if conversation.summary else "") + transcript
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
    conversation.summary = new_summary
    conversation.summary_until_id = overflow[-1].id
    await repository.save_conversation(db_session, conversation)
