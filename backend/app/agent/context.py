"""Agent 对话上下文与 versioned rolling-summary owner."""

import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm, memories, repository
from app.agent.budget import BudgetError, check_request
from app.agent.contracts import ContextFragment, ContextManifest, SourceRef, SummaryCoverage
from app.agent.models import Conversation, Message, SummaryVersion
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

SUMMARY_STRATEGY_VERSION = "traceable-summary-v1"


class CompiledContext(list[dict[str, Any]]):
    """List-compatible prompt plus a safe, user-visible provenance disclosure."""

    def __init__(self, messages: list[dict[str, Any]], disclosure: dict[str, Any]) -> None:
        super().__init__(messages)
        self.disclosure = disclosure


def _source_ids(version: SummaryVersion | None) -> list[str]:
    if version is None:
        return []
    try:
        value = json.loads(version.source_ids_json)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _key_items(version: SummaryVersion | None) -> list[dict[str, Any]]:
    if version is None:
        return []
    try:
        value = json.loads(version.key_items_json)
    except (TypeError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _coverage_valid(version: SummaryVersion, rows: list[Message]) -> bool:
    ids = _source_ids(version)
    ordered = [row.id for row in rows]
    return bool(
        version.status == "verified"
        and version.next_cursor
        and ids
        and ids == ordered[: len(ids)]
        and version.next_cursor == ids[-1]
    )


def _extract_key_items(rows: list[Message]) -> list[dict[str, Any]]:
    """Keep source-backed critical state; exact values are verified substrings."""
    items: list[dict[str, Any]] = []
    for row in rows:
        text = row.content.strip()
        if not text:
            continue
        exact_values = re.findall(r"\d+(?:\.\d+)?|[“\"「『][^”\"」』]{1,80}[”\"」』]", text)
        if row.role == "tool" or any(word in text for word in ("失败", "错误", "超时")):
            kind = "tool_failure"
        elif "?" in text or "？" in text or any(word in text for word in ("未决", "待定", "还没")):
            kind = "open_task"
        elif any(word in text for word in ("不要", "不能", "必须", "只", "禁止")):
            kind = "constraint"
        elif any(word in text for word in ("决定", "确定", "改为", "撤销", "取消")):
            kind = "decision"
        elif exact_values or any(word in text for word in ("叫", "名为", "编号", "引用")):
            kind = "exact_reference"
        else:
            continue
        items.append(
            {
                "kind": kind,
                "source_id": row.id,
                "text": text[:500],
                "exact_values": exact_values[:20],
            }
        )
    return items


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
) -> CompiledContext:
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
    accepted_memories = await memories.accepted_for_context(
        db_session, conversation.project_id, key
    )
    memory_sources = {
        row.id: await repository.list_project_memory_sources(db_session, row.id)
        for row in accepted_memories
    }
    memory_text = "\n".join(
        f"- {row.kind} / {row.subject_key} / {row.id} v{row.version}"
        f" / sources:{','.join(source.source_id for source in memory_sources[row.id]) or 'none'}"
        f": {row.content}"
        for row in accepted_memories
    )
    fragments.extend(
        ContextFragment(
            source=SourceRef(scope=scope, kind="memory", source_id=row.id, version=row.version),
            reason="author-accepted cross-session project memory",
            estimated_tokens=len(row.content.encode("utf-8")),
            disposition="included",
            required=True,
        )
        for row in accepted_memories
    )
    state = await repository.summary_partition(db_session, conversation, key)
    rows = [
        row
        for row in await repository.list_messages(db_session, conversation.id)
        if (getattr(row, "context_key", None) or "author") == key
    ]
    if exclude_message_id is not None:
        rows = [row for row in rows if row.id != exclude_message_id]
    version = (
        await repository.get_summary_version(db_session, getattr(state, "summary_version_id", ""))
        if state is not None and getattr(state, "summary_version_id", None)
        else None
    )
    summary = state.summary if state else ""
    cursor = state.summary_until_id if state else None
    coverage_gap = False
    if version is not None:
        if _coverage_valid(version, rows) and cursor == version.next_cursor:
            summary = version.summary
            cursor = version.next_cursor
        else:
            coverage_gap = True
    elif cursor is not None and cursor not in {row.id for row in rows}:
        coverage_gap = True

    if coverage_gap:
        # A damaged cursor never authorizes skipping. Refill critical sources and a bounded tail.
        summary = ""
        cursor = None
        critical_ids = {
            str(item.get("source_id"))
            for item in _key_items(version)[: getattr(settings, "agent_source_page_size", 12)]
        }
        recent_ids = {row.id for row in rows[-settings.agent_history_window_messages :]}
        included_ids = critical_ids | recent_ids
        tail = [row for row in rows if row.id in included_ids]
        omitted_rows = [row for row in rows if row.id not in included_ids]
        emit_event(
            "agent_summary_coverage_gap",
            component="app.agent.context",
            data={"conversation_id": conversation.id, "context_key": key},
        )
    else:
        cursor_index = next((index for index, row in enumerate(rows) if row.id == cursor), -1)
        tail = rows if cursor is None else rows[cursor_index + 1 :]
        omitted_rows = []

    windowed_tail = tail
    row_by_id = {row.id: row for row in rows}
    critical_rows = (
        []
        if coverage_gap
        else [
            row_by_id[source_id]
            for source_id in dict.fromkeys(
                str(item.get("source_id")) for item in _key_items(version)
            )
            if source_id in row_by_id
        ]
    )
    history = [
        {
            "role": message.role if message.role != "summary" else "assistant",
            "content": wrap_data(f"摘要关键原文 {message.id}", message.content),
        }
        for message in critical_rows
    ] + [
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
            reason="source-backed critical summary state",
            estimated_tokens=len(row.content.encode("utf-8")),
            disposition="included",
            required=True,
        )
        for row in critical_rows
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
    fragments.extend(
        ContextFragment(
            source=SourceRef(scope=scope, kind="message", source_id=row.id),
            reason="summary coverage gap; recoverable with read_conversation_sources",
            estimated_tokens=len(row.content.encode("utf-8")),
            disposition="omitted",
            required=False,
        )
        for row in omitted_rows
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
        summary=(wrap_data("已接受的跨会话项目记忆", memory_text) + "\n" if memory_text else "")
        + (wrap_data(f"分区 {key} 摘要，覆盖至 {cursor}", summary) if summary else ""),
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
            summary=(wrap_data("已接受的跨会话项目记忆", memory_text) + "\n" if memory_text else "")
            + (wrap_data(f"分区 {key} 摘要，覆盖至 {cursor}", summary) if summary else ""),
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
    disclosure = {
        "context_key": key,
        "summary_version": version.version if version is not None else None,
        "used_source_ids": [
            fragment.source.source_id
            for fragment in manifest.fragments
            if fragment.disposition == "included"
        ],
        "omitted_recoverable_source_ids": [
            fragment.source.source_id
            for fragment in manifest.fragments
            if fragment.disposition == "omitted"
        ],
        "coverage_gap": coverage_gap,
        "memory_ids": [row.id for row in accepted_memories],
    }
    return CompiledContext(compiled, disclosure)


async def maintain_rolling_summary(
    db_session: AsyncSession,
    conversation: Conversation,
    *,
    settings: Settings,
    perspective: Perspective = "author",
    character_id: str = "",
) -> None:
    """Create one bounded immutable summary attempt; advance only verified coverage."""
    key = context_key(perspective, character_id)
    state = await repository.summary_partition(db_session, conversation, key)
    cursor = state.summary_until_id if state else None
    rows = [
        row
        for row in await repository.list_messages(db_session, conversation.id)
        if (getattr(row, "context_key", None) or "author") == key
    ]
    active = (
        await repository.get_summary_version(db_session, getattr(state, "summary_version_id", ""))
        if state is not None and getattr(state, "summary_version_id", None)
        else None
    )
    previous_ids = _source_ids(active)
    failure: str | None = None
    if active is not None and not _coverage_valid(active, rows):
        failure = "ACTIVE_COVERAGE_INVALID"
    elif cursor is not None and cursor not in {row.id for row in rows}:
        failure = "CURSOR_NOT_FOUND"
    elif active is not None and cursor != active.next_cursor:
        failure = "CURSOR_VERSION_MISMATCH"
    if failure is not None:
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error=failure,
        )
        emit_event(
            "agent_summary_coverage_gap",
            component="app.agent.context",
            data={"conversation_id": conversation.id, "context_key": key, "error": failure},
        )
        if active is not None and _coverage_valid(active, rows):
            # The immutable version is sound: repair only the derived pointer, idempotently.
            assert state is not None
            state.summary = active.summary
            state.summary_until_id = active.next_cursor
            cursor = active.next_cursor
            previous_ids = _source_ids(active)
            await repository.save_conversation(db_session, conversation)
        else:
            # Rebuild from original messages without replacing the old active state until success.
            cursor = None
            active = None
            previous_ids = []

    cursor_index = next((index for index, row in enumerate(rows) if row.id == cursor), -1)
    tail = rows if cursor is None else rows[cursor_index + 1 :]
    overflow_count = len(tail) - settings.agent_history_window_messages
    if overflow_count <= 0:
        return
    summary = active.summary if active is not None else ""
    input_limit = getattr(settings, "agent_summary_input_max_chars", 24000)
    transcript_limit = input_limit - len(summary) - (1 if summary else 0)
    candidates = tail[: min(overflow_count, getattr(settings, "agent_summary_batch_messages", 20))]
    overflow: list[Message] = []
    transcript_parts: list[str] = []
    for message in candidates:
        part = f"[{message.id}] {message.role}: {message.content}"
        if sum(len(item) for item in transcript_parts) + len(part) > transcript_limit:
            break
        overflow.append(message)
        transcript_parts.append(part)
    if not overflow:
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error="SUMMARY_INPUT_TOO_LARGE",
        )
        return
    transcript = "\n".join(
        f"[{message.id}] {message.role}: {message.content}" for message in overflow
    )
    combined = (summary + "\n" if summary else "") + transcript
    if len(combined) > input_limit:
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error="SUMMARY_INPUT_TOO_LARGE",
            input_chars=len(combined),
        )
        return
    instruction = (
        "把对话增量压缩为一段紧凑中文摘要，保留创作决策、作者意见、未决问题与关键设定；"
        "不要逐句复述。"
    )
    try:
        new_summary = await llm.summarize(combined, instruction)
    except Exception as exc:  # noqa: BLE001 - 摘要维护不阻断已完成对话轮
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error=type(exc).__name__,
            input_chars=len(combined),
        )
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": type(exc).__name__},
        )
        return
    if not new_summary.strip():
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error="EMPTY_SUMMARY",
            input_chars=len(combined),
        )
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": "EmptySummary"},
        )
        return
    if len(new_summary) > getattr(settings, "agent_summary_output_max_chars", 4000):
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=previous_ids,
            key_items=_key_items(active),
            summary="",
            validation_error="SUMMARY_OUTPUT_TOO_LARGE",
            input_chars=len(combined),
            output_chars=len(new_summary),
        )
        return
    covered_ids = previous_ids + [message.id for message in overflow]
    coverage = SummaryCoverage(
        scope=make_scope(conversation.project_id, perspective, character_id),
        source_ids=tuple(covered_ids),
        previous_cursor=cursor,
        next_cursor=overflow[-1].id,
        strategy_version=SUMMARY_STRATEGY_VERSION,
        model=settings.llm_model_light,
        status="verified",
    )
    if not coverage.covers(tuple(row.id for row in rows[: len(covered_ids)])):
        await _record_summary_attempt(
            db_session,
            conversation,
            key=key,
            settings=settings,
            status="failed",
            previous_cursor=cursor,
            next_cursor=None,
            source_ids=covered_ids,
            key_items=_key_items(active),
            summary="",
            validation_error="SOURCE_RANGE_MISMATCH",
            input_chars=len(combined),
            output_chars=len(new_summary),
        )
        return
    key_items = [*_key_items(active), *_extract_key_items(overflow)]
    for item in key_items:
        source = next((row for row in rows if row.id == item.get("source_id")), None)
        if source is None or any(
            value not in source.content for value in item.get("exact_values", [])
        ):
            await _record_summary_attempt(
                db_session,
                conversation,
                key=key,
                settings=settings,
                status="failed",
                previous_cursor=cursor,
                next_cursor=None,
                source_ids=covered_ids,
                key_items=key_items,
                summary="",
                validation_error="KEY_ITEM_SOURCE_INVALID",
            )
            return
    if state is None:
        state = await repository.summary_partition(db_session, conversation, key, create=True)
    assert state is not None
    version = await _record_summary_attempt(
        db_session,
        conversation,
        key=key,
        settings=settings,
        status="verified",
        previous_cursor=cursor,
        next_cursor=overflow[-1].id,
        source_ids=covered_ids,
        key_items=key_items,
        summary=new_summary,
        validation_error=None,
        input_chars=len(combined),
        output_chars=len(new_summary),
    )
    state.summary = new_summary
    state.summary_until_id = overflow[-1].id
    state.summary_version_id = version.id
    await repository.save_conversation(db_session, conversation)


async def _record_summary_attempt(
    db_session: AsyncSession,
    conversation: Conversation,
    *,
    key: str,
    settings: Settings,
    status: str,
    previous_cursor: str | None,
    next_cursor: str | None,
    source_ids: list[str],
    key_items: list[dict[str, Any]],
    summary: str,
    validation_error: str | None,
    input_chars: int = 0,
    output_chars: int = 0,
) -> SummaryVersion:
    row = SummaryVersion(
        id=f"sumv-{uuid.uuid4().hex[:12]}",
        conversation_id=conversation.id,
        context_key=key,
        version=await repository.next_summary_version(db_session, conversation.id, key),
        status=status,
        summary=summary,
        previous_cursor=previous_cursor,
        next_cursor=next_cursor,
        source_ids_json=json.dumps(source_ids, ensure_ascii=False),
        key_items_json=json.dumps(key_items, ensure_ascii=False),
        strategy_version=SUMMARY_STRATEGY_VERSION,
        model=settings.llm_model_light,
        validation_error=validation_error,
        input_chars=input_chars,
        output_chars=output_chars,
    )
    return await repository.add_summary_version(db_session, row)
