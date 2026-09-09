"""agent 模块 service 层：对话主链路、记忆文档段级模型与写入确认。

职责:
    - 会话 CRUD 与消息读取（按项目隔离，projects.service 归属校验）；
    - stream_chat：SSE 事件流（受控 ReAct 工具循环 + 预算裁剪 + 滚动摘要，
      done 携带本轮待写入清单——F14 轮末统一确认）；
    - 记忆文档：模板建档、段级读写（CAS 乐观锁）、自包含 HTML 渲染；
    - 待写入登记：approve_pending_writes / reject_pending_writes（写入工具
      主路径的确认段，服务端二次校验批量落库）；
    - propose / confirm_write：草案两段式（F14 起标注 legacy，保留兼容）。
事务约定: 常规函数接收 AsyncSession 并在内部 commit；stream_chat 因流式
    生命周期自管理会话（连接于生成器内开启/释放）。
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm, repository, tools
from app.agent.models import (
    Conversation,
    MemoryDoc,
    MemoryDocSection,
    Message,
    PendingWrite,
    _utcnow,
)
from app.agent.prompts import (
    DocSectionRef,
    GraphDirectoryNode,
    assemble_messages,
    build_system_prompt,
    content_digest,
    render_doc_directory,
    render_graph_directory,
    truncate_output,
    wrap_data,
)
from app.agent.rendering import render_doc_page
from app.agent.schemas import (
    ApproveFailedItem,
    ApproveResponse,
    ApproveResultItem,
    ConfirmFailedItem,
    ConfirmRequest,
    ConfirmResponse,
    ConfirmResultItem,
    DraftItem,
    MemoryDocBrief,
    MemoryDocRead,
    MemoryDocSectionRead,
    MessageRead,
    PendingWriteActionRequest,
    PendingWriteRead,
    Perspective,
    ProposeRequest,
    ProposeResponse,
    RejectResponse,
    SectionUpdate,
    SessionCreate,
    SessionRead,
    generate_conversation_id,
    generate_draft_id,
    generate_memory_doc_id,
    generate_memory_section_id,
    generate_message_id,
)
from app.agent.templates import DOC_TEMPLATES, GUIDE_KINDS
from app.config import get_settings
from app.core import db
from app.core.exceptions import AgentError, ConflictError, NotFoundError, ValidationError
from app.core.observability import checkpoint, emit_event
from app.entities import service as entities_service
from app.perspectives import service as perspectives_service
from app.projects import service as projects_service
from app.relations import service as relations_service

# SSE 事件名（前后端契约；前端按事件类型白名单渲染）
EVENT_MESSAGE_START = "message_start"
EVENT_TOKEN = "token"
EVENT_REASONING = "reasoning"
EVENT_USAGE = "usage"
EVENT_TOOL = "tool"
EVENT_DRAFT = "draft"
EVENT_DOC_PATCH = "doc_patch"
EVENT_ASK_USER = "ask_user"
EVENT_DONE = "done"
EVENT_ERROR = "error"

# ---- 内部助手 ----


def _conversation_not_found(conversation_id: str) -> NotFoundError:
    """构造会话不存在的三要素异常。"""
    return NotFoundError(
        problem="会话不存在",
        cause=f"conversation_id '{conversation_id}' 未在库中",
        fix="先调用 GET /api/agent/sessions 确认会话 id",
        detail={"conversation_id": conversation_id},
    )


def _doc_not_found(doc_id: str) -> NotFoundError:
    """构造记忆文档不存在的三要素异常。"""
    return NotFoundError(
        problem="记忆文档不存在",
        cause=f"doc_id '{doc_id}' 未在库中",
        fix="先调用 GET /api/agent/memory-docs 确认文档 id",
        detail={"doc_id": doc_id},
    )


async def _load_conversation(db_session: AsyncSession, conversation_id: str) -> Conversation:
    """按 id 加载会话（不存在抛 404）。

    参数: db_session — 数据库会话；conversation_id — 会话 id。
    返回值: Conversation。异常: NotFoundError。依赖: app.agent.repository。
    """
    conversation = await repository.get_conversation(db_session, conversation_id)
    if conversation is None:
        raise _conversation_not_found(conversation_id)
    return conversation


def _session_read(conversation: Conversation) -> SessionRead:
    """Conversation ORM → SessionRead DTO。"""
    return SessionRead(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_read(message: Message) -> MessageRead:
    """Message ORM → MessageRead DTO（含思考与 usage 回读字段，F13）。"""
    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        reasoning=message.reasoning,
        prompt_tokens=message.prompt_tokens,
        completion_tokens=message.completion_tokens,
        created_at=message.created_at,
    )


async def _doc_read(db_session: AsyncSession, doc: MemoryDoc) -> MemoryDocRead:
    """MemoryDoc ORM + 段列表 → MemoryRead DTO（段按 seq 升序）。"""
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
                id=s.id,
                seq=s.seq,
                title=s.title,
                content=s.content,
                updated_by=s.updated_by,
                version=s.version,
                updated_at=s.updated_at,
            )
            for s in sections
        ],
    )


def _review_text(text: str) -> str | None:
    """内容合规 hook：命中敏感词返回该词，未启用/未命中返回 None。

    作用: 三防线的合规扩展位——MVP 为本地词表（config），预留外部审核 API
        替换位（替换本函数实现即可，agent/CONSTRAINTS.md）。
    参数: text — 待审文本。返回值: str | None。异常: 无。依赖: app.config。
    """
    settings = get_settings()
    if not settings.agent_content_review_enabled:
        return None
    for word in settings.agent_content_review_words.split(","):
        word = word.strip()
        if word and word in text:
            return word
    return None


async def _project_name(db_session: AsyncSession, project_id: str) -> str:
    """读取项目名（system 提示词用；读取失败回退为项目 id）。"""
    try:
        project = await projects_service.get(db_session, project_id)
        return project.name
    except Exception:  # noqa: BLE001 — 名称仅装饰性，失败不阻断对话
        return project_id


async def _assemble_chat_context(
    db_session: AsyncSession,
    conversation: Conversation,
    *,
    perspective: Perspective,
    character_id: str,
    user_message: str,
    exclude_message_id: str | None = None,
) -> list[dict[str, str]]:
    """组装对话上下文消息序列（system + 项目上下文 + 摘要 + 窗口内历史 + 本轮输入）。

    作用: chat 与 propose 共用的上下文装配器——图谱经视角过滤取目录投影，
        记忆文档取目录 + 段全文（预算内），历史按「摘要游标之后的尾部」
        截取最近 N 条（LLM 上下文视角过滤的唯一入口，agent/CONSTRAINTS.md）。
    参数: db_session — 数据库会话；conversation — 会话；perspective/character_id —
        视角；user_message — 本轮用户输入；exclude_message_id — 已单独作为
        user_message 注入的消息行 id（stream_chat 落库本轮输入后传入，防止双份注入）。
    返回值: list[dict] — openai 消息格式。异常: 无。依赖: perspectives/prompts。
    """
    settings = get_settings()
    graph = await perspectives_service.get_graph(
        db_session,
        perspective=perspective,
        character_id=character_id or None,
        project_id=conversation.project_id,
    )
    graph_directory = render_graph_directory(
        [
            GraphDirectoryNode(id=n.id, type=n.type, name=n.name, aliases=list(n.aliases))
            for n in graph.nodes
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
                    {"seq": s.seq, "title": s.title, "digest": content_digest(s.content)}
                    for s in sections
                ],
            }
        )
        doc_sections.extend(
            DocSectionRef(
                label=f"文档《{doc.title}》第{s.seq}段·{s.title}",
                title=s.title,
                digest=content_digest(s.content),
                content=s.content,
            )
            for s in sections
        )

    rows = await repository.list_messages(db_session, conversation.id)
    if exclude_message_id is not None:
        # 本轮用户输入已单独作为 user_message 注入——历史行中剔除，防双份
        rows = [r for r in rows if r.id != exclude_message_id]
    # 摘要游标之后的消息为「未覆盖尾部」；只注入其中最近 N 条
    if conversation.summary_until_id is None:
        tail = rows
    else:
        cursor_idx = next(
            (i for i, r in enumerate(rows) if r.id == conversation.summary_until_id), -1
        )
        tail = rows[cursor_idx + 1 :]
    windowed_tail = tail[-settings.agent_history_window_messages :]
    history = [
        {"role": m.role if m.role != "summary" else "assistant", "content": m.content}
        for m in windowed_tail
    ]
    history.append({"role": "user", "content": user_message})

    project_name = await _project_name(db_session, conversation.project_id)
    system = build_system_prompt(project_name=project_name)
    return assemble_messages(
        system=system,
        doc_sections=doc_sections,
        graph_directory=graph_directory,
        doc_directory=render_doc_directory(doc_dir_entries),
        summary=conversation.summary,
        history=history,
        budget=settings.agent_context_max_tokens,
    )


async def _maintain_rolling_summary(db_session: AsyncSession, conversation: Conversation) -> None:
    """超窗历史增量压缩进会话摘要（L2 短期记忆的溢出路径）。

    作用: 「摘要游标之后的尾部」超过窗口时，把最旧的溢出部分交给轻量模型
        增量压缩；摘要失败仅记事件不阻断（下轮自动补齐）。
    参数: db_session — 数据库会话；conversation — 会话（就地更新 summary/
        summary_until_id 并落库）。返回值: 无。
    异常: 无（内部消化 AgentError）。依赖: agent.llm.summarize。
    """
    settings = get_settings()
    rows = await repository.list_messages(db_session, conversation.id)
    if conversation.summary_until_id is None:
        tail = rows
    else:
        cursor_idx = next(
            (i for i, r in enumerate(rows) if r.id == conversation.summary_until_id), -1
        )
        tail = rows[cursor_idx + 1 :]
    overflow_count = len(tail) - settings.agent_history_window_messages
    if overflow_count <= 0:
        return
    overflow = tail[:overflow_count]
    transcript = "\n".join(f"{m.role}: {m.content}" for m in overflow)
    combined = (conversation.summary + "\n" if conversation.summary else "") + transcript
    instruction = (
        "把对话增量压缩为一段紧凑中文摘要，保留创作决策、作者意见、未决问题与关键设定；"
        "不要逐句复述。"
    )
    try:
        new_summary = await llm.summarize(combined, instruction)
    except Exception as exc:  # noqa: BLE001 — 摘要失败不阻断已完成的对话轮
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": type(exc).__name__},
        )
        return
    if not new_summary.strip():
        # 空摘要视为失败：清空 summary 且推进游标会静默丢失被压缩的历史
        emit_event(
            "agent_summary_skipped",
            component="app.agent.service",
            data={"conversation_id": conversation.id, "error": "EmptySummary"},
        )
        return
    conversation.summary = new_summary
    conversation.summary_until_id = overflow[-1].id
    await repository.save_conversation(db_session, conversation)


# ---- 会话 ----


@checkpoint
async def create_conversation(db_session: AsyncSession, schema: SessionCreate) -> SessionRead:
    """创建会话（按项目隔离；标题缺省为空，首条消息落库时回填）。

    参数: db_session — 数据库会话；schema — 创建载荷（project_id 空=默认项目）。
    返回值: SessionRead。异常: NotFoundError — project_id 不存在。
    依赖: app.agent.repository、app.projects.service。
    """
    project_id = schema.project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, project_id)
    conversation = Conversation(
        id=generate_conversation_id(),
        project_id=project_id,
        title=schema.title,
    )
    conversation = await repository.add_conversation(db_session, conversation)
    await db_session.commit()
    return _session_read(conversation)


@checkpoint
async def ensure_conversation(db_session: AsyncSession, conversation_id: str) -> SessionRead:
    """校验会话存在并返回元数据（SSE 端点流式开始前的 404 出口）。

    参数: db_session — 数据库会话；conversation_id — 会话 id。
    返回值: SessionRead。异常: NotFoundError。依赖: app.agent.repository。
    """
    conversation = await _load_conversation(db_session, conversation_id)
    return _session_read(conversation)


@checkpoint
async def list_conversations(db_session: AsyncSession, project_id: str) -> list[SessionRead]:
    """列出项目的全部会话（最近活跃在前）。

    参数: db_session — 数据库会话；project_id — 项目 id（空=默认项目）。
    返回值: list[SessionRead]。异常: NotFoundError — project_id 不存在。
    依赖: app.agent.repository、app.projects.service。
    """
    resolved = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, resolved)
    rows = await repository.list_conversations(db_session, resolved)
    return [_session_read(c) for c in rows]


@checkpoint
async def get_messages(db_session: AsyncSession, conversation_id: str) -> list[MessageRead]:
    """读取会话全部消息（时间正序；会话不存在抛 404）。

    参数: db_session — 数据库会话；conversation_id — 会话 id。
    返回值: list[MessageRead]。异常: NotFoundError。依赖: app.agent.repository。
    """
    await _load_conversation(db_session, conversation_id)
    rows = await repository.list_messages(db_session, conversation_id)
    return [_message_read(m) for m in rows]


@checkpoint
async def delete_conversation(db_session: AsyncSession, conversation_id: str) -> None:
    """删除会话（消息经 FK CASCADE 级联清理；不存在抛 404）。

    参数: db_session — 数据库会话；conversation_id — 会话 id。
    返回值: 无。异常: NotFoundError。依赖: app.agent.repository。
    """
    conversation = await _load_conversation(db_session, conversation_id)
    await repository.delete_conversation(db_session, conversation)
    await db_session.commit()


# ---- 对话（SSE 流式）----


async def stream_chat(
    conversation_id: str,
    message: str,
    *,
    perspective: Perspective,
    character_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """一次对话轮的 SSE 事件流（真流式 + 受控 ReAct + 滚动摘要维护，F13）。

    作用:
        事件序列 = message_start → (tool …)* → reasoning … token … → usage?
            → done | error。token/reasoning 逐 chunk 下发（llm.stream_chat_turn
            真流式，废除伪分块）；usage 在 done 前下发（prompt/completion
            tokens + 容量占比 = prompt_tokens ÷ AGENT_CONTEXT_MAX_TOKENS，
            端点未返回 usage 时整个事件缺省）。工具调用配额来自 config（超限
            后不再提供工具，强制作答）；user 消息先行落库（LLM 失败也不丢
            用户输入），assistant 消息（含最终轮思考 reasoning 与 usage）
            完成后落库并触发超窗摘要压缩。LLM 失败发 error 事件（三要素）
            正常收尾。
    参数:
        conversation_id — 会话 id；message — 用户输入；perspective — 视角；
        character_id — character 视角角色 id。
    返回值: AsyncIterator[dict] — {"event": str, "data": dict}（router 序列化）。
    异常:
        NotFoundError — 会话不存在（首个 yield 前抛出）。
        事件内错误 — error 事件承载（三要素完整）。
    依赖: agent.llm、agent.tools、agent.prompts、perspectives.service。
    """
    settings = get_settings()
    factory = db.get_session_factory()
    async with factory() as db_session:
        conversation = await _load_conversation(db_session, conversation_id)
        yield {"event": EVENT_MESSAGE_START, "data": {"conversation_id": conversation_id}}

        violation = _review_text(message)
        if violation:
            yield {
                "event": EVENT_ERROR,
                "data": {
                    "code": "CONTENT_REVIEW_BLOCKED",
                    "problem": "输入未通过内容合规审核",
                    "cause": f"命中敏感词「{violation}」",
                    "fix": "调整表述后重发；如为误判可在 .env 调整敏感词表",
                },
            }
            return

        user_row = Message(
            id=generate_message_id(),
            conversation_id=conversation_id,
            role="user",
            content=message,
        )
        await repository.add_message(db_session, user_row)
        if not conversation.title:
            conversation.title = message[:20]
            await repository.save_conversation(db_session, conversation)
        # 用户输入独立提交：LLM 失败（rollback）也不丢已发生的用户消息
        await db_session.commit()

        try:
            messages = await _assemble_chat_context(
                db_session,
                conversation,
                perspective=perspective,
                character_id=character_id,
                user_message=message,
                exclude_message_id=user_row.id,
            )
            tool_ctx = tools.ToolContext(
                session=db_session,
                project_id=conversation.project_id,
                perspective=perspective,
                character_id=character_id,
                conversation_id=conversation_id,
            )
            used = 0
            final_usage: dict[str, int | None] | None = None
            turn: llm.AssistantTurn | None = None
            while True:
                enable_tools = used < settings.agent_max_tool_calls_per_turn
                turn_reasoning: list[str] = []
                turn = None
                async for kind, payload in llm.stream_chat_turn(
                    messages[0]["content"],
                    messages[1:],
                    tools=tools.TOOL_SPECS if enable_tools else None,
                ):
                    if kind == "reasoning_delta":
                        turn_reasoning.append(str(payload))
                        yield {"event": EVENT_REASONING, "data": {"text": payload}}
                    elif kind == "content_delta":
                        yield {"event": EVENT_TOKEN, "data": {"text": payload}}
                    elif kind == "usage":
                        final_usage = payload
                    elif kind == "turn":
                        turn = payload
                if turn is None:
                    raise AgentError(
                        problem="LLM 流式响应中断",
                        cause="流式补全未产出聚合结果即结束",
                        fix="重试一次；持续出现请检查 LLM 端点稳定性",
                    )
                if turn.tool_calls and enable_tools:
                    messages.append(turn.raw)
                    for call in turn.tool_calls:
                        yield {
                            "event": EVENT_TOOL,
                            "data": {"name": call.name, "phase": "start"},
                        }
                        result = await tools.execute_tool(call.name, call.arguments, tool_ctx)
                        used += 1
                        yield {
                            "event": EVENT_TOOL,
                            "data": {"name": call.name, "phase": "done", "calls_used": used},
                        }
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.call_id,
                                "content": wrap_data(
                                    f"工具 {call.name} 结果",
                                    truncate_output(result, settings.agent_tool_output_max_chars),
                                ),
                            }
                        )
                    continue
                if turn.content is not None and turn.content.strip():
                    final_reasoning = "".join(turn_reasoning)
                    break
                raise AgentError(
                    problem="LLM 返回了空回复",
                    cause="补全结果既无文本内容也无工具调用",
                    fix="重试一次；持续出现请更换 LLM_MODEL 或简化问题",
                )

            assistant_row = Message(
                id=generate_message_id(),
                conversation_id=conversation_id,
                role="assistant",
                content=turn.content or "",
                reasoning=final_reasoning or None,
                prompt_tokens=(final_usage or {}).get("prompt_tokens"),
                completion_tokens=(final_usage or {}).get("completion_tokens"),
            )
            await repository.add_message(db_session, assistant_row)
            await _maintain_rolling_summary(db_session, conversation)
            # 本轮待写入清单在 commit 前解析为纯 dict（登记行随本事务提交；
            # done 事件携带清单驱动前端确认卡——F14 轮末统一确认）
            pending_payload: dict[str, Any] | None = None
            if tool_ctx.pending_writes:
                pending_payload = {
                    # mode="json"：datetime 等转 ISO 串（SSE 帧手工 json.dumps 可序列化）
                    "pending_writes": [
                        _pending_read(r).model_dump(mode="json") for r in tool_ctx.pending_writes
                    ]
                }
            await db_session.commit()
            if final_usage is not None:
                prompt_tokens = final_usage.get("prompt_tokens") or 0
                max_tokens = settings.agent_context_max_tokens
                yield {
                    "event": EVENT_USAGE,
                    "data": {
                        "prompt_tokens": final_usage.get("prompt_tokens"),
                        "completion_tokens": final_usage.get("completion_tokens"),
                        "context_max_tokens": max_tokens,
                        "context_ratio": (prompt_tokens / max_tokens) if max_tokens > 0 else None,
                    },
                }
            done_data: dict[str, Any] = {"message_id": assistant_row.id}
            if pending_payload is not None:
                done_data.update(pending_payload)
            yield {"event": EVENT_DONE, "data": done_data}
        except Exception as exc:  # noqa: BLE001 — 对话轮错误统一转 error 事件
            await db_session.rollback()
            if isinstance(exc, llm.AgentError):
                payload = {
                    "code": exc.code,
                    "problem": exc.problem,
                    "cause": exc.cause,
                    "fix": exc.fix,
                }
            else:
                emit_event(
                    "agent_turn_failed",
                    component="app.agent.service",
                    data={"error": type(exc).__name__},
                )
                payload = {
                    "code": "AGENT_FAILURE",
                    "problem": "对话处理失败",
                    "cause": f"内部错误（{type(exc).__name__}），详情见服务端日志",
                    "fix": "重试；持续失败请检查服务端 runtime_error 日志",
                }
            yield {"event": EVENT_ERROR, "data": payload}


# ---- 记忆文档 ----


@checkpoint
async def create_doc(
    db_session: AsyncSession,
    project_id: str,
    kind: str,
    *,
    title: str | None = None,
) -> MemoryDocRead:
    """按模板创建记忆文档（初始段生成，updated_by=user 语义的空白起点）。

    作用: F13 起指导类（GUIDE_KINDS）文档项目内唯一——同 kind 已存在即 409
        拒绝（每项目仅一份定位/风格文件），不覆盖既有文档；title 显式提供
        时覆盖模板默认标题（F14 写入工具 create_memory_doc 透传）。
    参数: db_session — 数据库会话；project_id — 项目 id（空=默认项目）；
        kind — 模板键（positioning/style）；title — 可选标题覆盖。
    返回值: MemoryDocRead。
    异常: ValidationError — 未知模板；NotFoundError — 项目不存在；
        ConflictError — 指导类文档项目内已存在同 kind。
    依赖: app.agent.repository、app.projects.service。
    """
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
    doc = await repository.add_doc(db_session, doc)
    for seq, sec_title in enumerate(template["sections"], start=1):
        await repository.add_section(
            db_session,
            MemoryDocSection(
                id=generate_memory_section_id(),
                doc_id=doc.id,
                seq=seq,
                title=str(sec_title),
            ),
        )
    await db_session.commit()
    return await _doc_read(db_session, doc)


@checkpoint
async def list_docs(db_session: AsyncSession, project_id: str) -> list[MemoryDocBrief]:
    """列出项目记忆文档卡片（名称+更新时间+首段预览）。

    参数: db_session — 数据库会话；project_id — 项目 id（空=默认项目）。
    返回值: list[MemoryDocBrief]。异常: NotFoundError — 项目不存在。
    依赖: app.agent.repository、app.projects.service。
    """
    resolved = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, resolved)
    docs = await repository.list_docs(db_session, resolved)
    briefs: list[MemoryDocBrief] = []
    for doc in docs:
        sections = await repository.list_sections(db_session, doc.id)
        preview_source = next((s.content for s in sections if s.content.strip()), "")
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
    """读取记忆文档全文（含段列表）。

    参数: db_session — 数据库会话；doc_id — 文档 id。
    返回值: MemoryDocRead。异常: NotFoundError。依赖: app.agent.repository。
    """
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    return await _doc_read(db_session, doc)


@checkpoint
async def delete_doc(db_session: AsyncSession, doc_id: str) -> None:
    """删除记忆文档（段经 CASCADE 清理）。

    参数: db_session — 数据库会话；doc_id — 文档 id。
    返回值: 无。异常: NotFoundError。依赖: app.agent.repository。
    """
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
) -> MemoryDocSectionRead:
    """段级更新（CAS 乐观锁：expected_version 不符即冲突拒绝）。

    作用:
        用户编辑与 agent patch 确认共用的唯一写入口；段 version 与文档
        version 同事务递增；版本冲突抛 ConflictError 且绝不覆盖——用户手改
        优先，agent 基于旧版本的 patch 一律作废（记忆冲突边界核心语义）。
    参数:
        db_session — 数据库会话；doc_id — 文档 id；section_id — 段 id；
        payload — 新内容 + 期望版本；updated_by — "user" | "agent"。
    返回值: MemoryDocSectionRead（更新后的段）。
    异常:
        NotFoundError — 文档或段不存在；ConflictError — 版本不一致。
    依赖: app.agent.repository。
    """
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
    if section.version != payload.expected_version:
        raise ConflictError(
            problem="记忆文档段已被他人修改（版本冲突）",
            cause=(
                f"段当前版本为 v{section.version}（{section.updated_by} 更新），"
                f"请求基于 v{payload.expected_version}"
            ),
            fix="重新读取该段最新内容后再提交；agent 草案将基于新版本重新生成",
            detail={"doc_id": doc_id, "section_id": section_id, "current_version": section.version},
        )
    section.content = payload.content
    if payload.title is not None:
        section.title = payload.title
    section.version += 1
    section.updated_by = updated_by
    section.updated_at = _utcnow()
    doc.version += 1
    await repository.save_section(db_session, section)
    await db_session.commit()
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
    """渲染记忆文档的自包含 HTML 页。

    参数: db_session — 数据库会话；doc_id — 文档 id。
    返回值: str — HTML 文本。异常: NotFoundError。依赖: agent.rendering。
    """
    doc = await repository.get_doc(db_session, doc_id)
    if doc is None:
        raise _doc_not_found(doc_id)
    sections = await repository.list_sections(db_session, doc_id)
    label = str(DOC_TEMPLATES.get(doc.kind, {}).get("label", doc.kind))
    return render_doc_page(doc.title, label, sections)


# ---- 草案两段式 ----


_PROPOSE_RULES = (
    "\n当前任务：根据上面的对话产出写入图谱的结构化草案。只输出一个 JSON 对象：\n"
    '{"drafts": [{"kind": "entity", "payload": {"type": "实体类型", "name": "名称", '
    '"aliases": ["别名"], "description": "简介", "audience_known": false, "properties": {}}, '
    '"summary": "给作者看的一句话说明"}]}。\n'
    "kind 取 entity 或 relation；relation 的 payload 至少含 type/source/target"
    '（source/target 为实体 id）。没有值得写入的内容时输出 {"drafts": []}。'
    "不要输出 JSON 以外的任何文字。"
)


@checkpoint
async def propose_drafts(db_session: AsyncSession, schema: ProposeRequest) -> ProposeResponse:
    """生成实体/关系写入草案（LLM JSON mode；服务端基础校验）。

    作用: 【legacy】F14 起对话内写入工具（登记 pending + 轮末统一确认）
        为主路径；本端点保留兼容既有草案卡交互，不再扩展能力。

    参数: db_session — 数据库会话；schema — 请求（会话/输入/视角）。
    返回值: ProposeResponse（draft_id 系统生成；payload 保持宽松 dict，
        严格校验发生在 confirm）。异常: NotFoundError / ValidationError / AgentError。
    依赖: agent.llm.complete_json、_assemble_chat_context。
    """
    conversation = await _load_conversation(db_session, schema.session_id)
    messages = await _assemble_chat_context(
        db_session,
        conversation,
        perspective=schema.perspective,
        character_id=schema.character_id,
        user_message=schema.message,
    )
    system = messages[0]["content"] + _PROPOSE_RULES
    payload = await llm.complete_json(system, messages[1:])
    raw_drafts = payload.get("drafts")
    if not isinstance(raw_drafts, list):
        raise ValidationError(
            problem="LLM 草案缺少 drafts 列表",
            cause=f"JSON 顶层键 drafts 缺失或类型为 {type(raw_drafts).__name__}",
            fix="重试一次；持续失败请简化输入描述",
        )
    drafts: list[DraftItem] = []
    for raw in raw_drafts:
        if not isinstance(raw, dict):
            raise ValidationError(
                problem="LLM 草案项格式非法",
                cause="drafts 中存在非对象元素",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        kind = raw.get("kind")
        if kind not in ("entity", "relation"):
            raise ValidationError(
                problem="LLM 草案 kind 非法",
                cause=f"kind 必须为 entity/relation，收到 {kind!r}",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        item_payload = raw.get("payload")
        if not isinstance(item_payload, dict):
            raise ValidationError(
                problem="LLM 草案 payload 非法",
                cause="payload 必须是对象",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        drafts.append(
            DraftItem(
                draft_id=generate_draft_id(),
                kind=kind,
                payload=item_payload,
                summary=str(raw.get("summary", "")),
            )
        )
    return ProposeResponse(session_id=schema.session_id, drafts=drafts)


def _format_failure(exc: Exception) -> str:
    """把落库异常折叠为失败原因文本（三要素优先）。"""
    from app.core.exceptions import AppError

    if isinstance(exc, AppError):
        return f"{exc.problem}；原因：{exc.cause}；修复：{exc.fix}"
    if isinstance(exc, PydanticValidationError):
        return f"草案 payload 未通过服务端校验：{exc.errors()[:3]}"
    return f"落库失败（{type(exc).__name__}），请检查 payload 字段"


@checkpoint
async def confirm_write(db_session: AsyncSession, schema: ConfirmRequest) -> ConfirmResponse:
    """确认草案并落库（无状态回传；服务端重新校验全部 payload，不信任前端）。

    作用:
        【legacy】F14 起写入主路径为待写入登记（approve_pending_writes）；
        本端点保留兼容既有草案卡。
        confirmed=True 的项经 entities/relations service 严格校验后落库
        （两段式第二段）；单项失败不阻断其他项（failed 列表携带三要素）。
        归属注入：session_id 可解析时，payload 的 project_id 一律以会话
        归属项目覆盖（草案不能把数据写进别的项目）；payload 由服务端重新
        构造输入 DTO 校验——篡改/过期载荷进入 failed 列表拒绝落库。
    参数: db_session — 数据库会话；schema — 确认请求。
    返回值: ConfirmResponse（created/failed 列表）。
    异常: NotFoundError — session_id 非空但会话不存在（单项失败折叠进 failed）。
    依赖: app.entities.service、app.relations.service、app.agent.repository。
    """
    created: list[ConfirmResultItem] = []
    failed: list[ConfirmFailedItem] = []
    project_id: str | None = None
    if schema.session_id:
        conversation = await _load_conversation(db_session, schema.session_id)
        project_id = conversation.project_id
    for item in schema.items:
        if not item.confirmed:
            continue
        payload = dict(item.payload)
        if project_id is not None:
            payload["project_id"] = project_id
        try:
            if item.kind == "entity":
                entity = await entities_service.create(
                    db_session, entities_service.EntityCreate(**payload)
                )
                created.append(
                    ConfirmResultItem(
                        draft_id=item.draft_id, kind="entity", target_id=entity.id, name=entity.name
                    )
                )
            else:
                relation = await relations_service.create(
                    db_session, relations_service.RelationCreate(**payload)
                )
                created.append(
                    ConfirmResultItem(
                        draft_id=item.draft_id,
                        kind="relation",
                        target_id=relation.id,
                        name=f"{relation.type}({relation.source}->{relation.target})",
                    )
                )
        except Exception as exc:  # noqa: BLE001 — 单项失败折叠，其余项继续
            failed.append(ConfirmFailedItem(draft_id=item.draft_id, reason=_format_failure(exc)))
    return ConfirmResponse(created=created, failed=failed)


# ---- 待写入登记（F14 轮末统一确认；写入工具主路径）----


def _pending_summary(kind: str, payload: dict[str, Any]) -> str:
    """从登记 payload 派生给作者看的一句话摘要。

    参数: kind — 写入类别；payload — 白名单化工具参数（含人读名称快照）。
    返回值: str。异常: 无。依赖: 无。
    """
    if kind == "create_entity":
        return f"新增实体「{payload.get('name', '?')}」（{payload.get('type', '?')}）"
    if kind == "update_entity":
        return f"更新实体「{payload.get('entity_name', payload.get('entity_id', '?'))}」"
    if kind == "create_relation":
        return (
            f"新增关系：{payload.get('source_name', '?')}"
            f" -[{payload.get('type', '?')}]-> {payload.get('target_name', '?')}"
        )
    if kind == "create_memory_doc":
        return f"新建文档「{payload.get('title', '?')}」（{payload.get('kind', '?')}）"
    doc_title = payload.get("doc_title", payload.get("doc_id", "?"))
    return f"写入《{doc_title}》第 {payload.get('seq', '?')} 段"


def _pending_read(row: PendingWrite) -> PendingWriteRead:
    """PendingWrite ORM → PendingWriteRead DTO（payload/baseline 反序列化）。

    参数: row — 登记行。返回值: PendingWriteRead。异常: 无。依赖: 无。
    """
    payload = json.loads(row.payload_json)
    baseline = json.loads(row.baseline_json) if row.baseline_json else None
    # kind/status 的 Literal 字面量由登记路径（写入工具白名单）保证
    return PendingWriteRead(
        id=row.id,
        conversation_id=row.conversation_id,
        kind=row.kind,
        payload=payload,
        baseline=baseline,
        status=row.status,
        summary=_pending_summary(row.kind, payload),
        created_at=row.created_at,
    )


async def _apply_pending_write(
    db_session: AsyncSession, row: PendingWrite, project_id: str
) -> ApproveResultItem:
    """按类别把单条登记落库（服务端二次校验；白名单重建输入 DTO）。

    作用:
        approve 的单项执行器——payload 虽来自登记行（模型产物），落库前
        仍按类别显式键重建 entities/relations/agent service 输入 DTO
        （不信任任何持久化载荷），project_id 一律以会话归属覆盖。
        write_doc_section 经 update_section 的 CAS 复核（baseline 版本）。
    参数: db_session — 数据库会话；row — 登记行；project_id — 会话归属项目。
    返回值: ApproveResultItem（目标 id 与名称）。
    异常: 落库异常由调用方折叠进 failed（本函数不吞异常）。
    依赖: entities/relations/agent service、agent.repository。
    """
    payload = json.loads(row.payload_json)
    if row.kind == "create_entity":
        entity = await entities_service.create(
            db_session,
            entities_service.EntityCreate(
                # 必填键以 .get 取值：缺失时交由 EntityCreate 校验捕获
                # （三要素可读），而非 KeyError 透传
                type=payload.get("type", ""),
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                aliases=list(payload.get("aliases", [])),
                audience_known=bool(payload.get("audience_known", False)),
                properties=dict(payload.get("properties", {})),
                project_id=project_id,
            ),
        )
        return ApproveResultItem(id=row.id, kind=row.kind, target_id=entity.id, name=entity.name)
    if row.kind == "update_entity":
        entity_id = str(payload.get("entity_id", ""))
        if not entity_id:
            raise ValidationError(
                problem="登记载荷缺少 entity_id",
                cause="写入工具登记时的必填键在载荷中缺失（载荷损坏或被篡改）",
                fix="放弃该项登记，由 agent 重新发起",
                detail={"payload": str(payload)[:120]},
            )
        entity = await entities_service.get(db_session, entity_id)
        if entity.project_id != project_id:
            raise ValidationError(
                problem="待更新实体不在会话所属项目",
                cause=f"实体 {entity_id} 归属 {entity.project_id}，会话归属 {project_id}",
                fix="放弃该项登记，在正确的项目会话中重新发起",
                detail={"entity_id": entity_id},
            )
        patch: dict[str, Any] = {}
        for key in ("name", "description", "aliases", "audience_known"):
            if key in payload:
                patch[key] = payload[key]
        if "properties_patch" in payload:
            patch["properties"] = payload["properties_patch"]
        updated = await entities_service.update(
            db_session, entity_id, entities_service.EntityUpdate(**patch)
        )
        return ApproveResultItem(id=row.id, kind=row.kind, target_id=updated.id, name=updated.name)
    if row.kind == "create_relation":
        relation = await relations_service.create(
            db_session,
            relations_service.RelationCreate(
                source=payload.get("source", ""),
                target=payload.get("target", ""),
                type=payload.get("type", ""),
                known_by=list(payload.get("known_by", [])),
                project_id=project_id,
                **{
                    key: payload[key]
                    for key in ("trust", "intimacy", "dependency", "resentment")
                    if key in payload
                },
            ),
        )
        return ApproveResultItem(
            id=row.id,
            kind=row.kind,
            target_id=relation.id,
            name=f"{relation.type}({relation.source}->{relation.target})",
        )
    if row.kind == "create_memory_doc":
        doc_read = await create_doc(
            db_session,
            project_id=project_id,
            kind=str(payload.get("kind", "")),
            title=payload.get("title"),
        )
        return ApproveResultItem(
            id=row.id, kind=row.kind, target_id=doc_read.id, name=doc_read.title
        )
    # write_doc_section：CAS 基线复核（用户手改优先，登记自动失效）
    baseline = json.loads(row.baseline_json or "{}")
    doc_id = str(payload.get("doc_id", ""))
    doc_row = await repository.get_doc(db_session, doc_id)
    if doc_row is None or doc_row.project_id != project_id:
        raise NotFoundError(
            problem=f"记忆文档 {doc_id} 不存在或不在会话项目",
            cause="文档已删除，或登记后项目归属变化",
            fix="放弃该项登记，重新确认文档状态后由 agent 再次发起",
            detail={"doc_id": doc_id},
        )
    section = await repository.get_section(db_session, baseline.get("section_id", ""))
    if section is None or section.doc_id != doc_row.id:
        raise NotFoundError(
            problem=f"记忆文档《{doc_row.title}》的登记段已不存在",
            cause="段在登记后被删除（文档结构变更）",
            fix="放弃该项登记，由 agent 按新文档目录重新发起",
            detail={"doc_id": doc_row.id, "section_id": baseline.get("section_id")},
        )
    updated_section = await update_section(
        db_session,
        doc_row.id,
        section.id,
        SectionUpdate(
            content=payload.get("content", ""),
            expected_version=int(baseline.get("expected_version", 0)),
            title=payload.get("title"),
        ),
        updated_by="agent",
    )
    return ApproveResultItem(
        id=row.id,
        kind=row.kind,
        target_id=updated_section.id,
        name=f"《{doc_row.title}》第 {updated_section.seq} 段",
    )


@checkpoint
async def approve_pending_writes(
    db_session: AsyncSession, schema: PendingWriteActionRequest
) -> ApproveResponse:
    """批准待写入登记并批量落库（服务端逐项二次校验，OQ-8 确认段）。

    作用:
        成功项经既有 service 严格校验后落库并置 approved；失败项保持
        pending（确认卡可重试或放弃），原因折叠进 failed（三要素可读）；
        单项失败不阻断其他项。归属复核：登记行 conversation_id 必须与请求
        一致；落库 project_id 一律以会话归属覆盖。
    参数: db_session — 数据库会话；schema — 请求（会话 + 登记行 id 列表）。
    返回值: ApproveResponse（created/failed 列表）。
    异常: NotFoundError — 会话不存在。
    依赖: agent.repository、_apply_pending_write。
    """
    conversation = await _load_conversation(db_session, schema.conversation_id)
    created: list[ApproveResultItem] = []
    failed: list[ApproveFailedItem] = []
    for pending_id in schema.ids:
        row = await repository.get_pending(db_session, pending_id)
        if row is None or row.conversation_id != conversation.id:
            failed.append(
                ApproveFailedItem(
                    id=pending_id,
                    reason="登记行不存在或不属于该会话（已被清理或归属不符）",
                )
            )
            continue
        if row.status != "pending":
            failed.append(
                ApproveFailedItem(
                    id=pending_id, reason=f"登记行状态为 {row.status}，仅 pending 可确认"
                )
            )
            continue
        try:
            result = await _apply_pending_write(db_session, row, conversation.project_id)
            row.status = "approved"
            await repository.save_pending(db_session, row)
            await db_session.commit()
            created.append(result)
        except Exception as exc:  # noqa: BLE001 — 单项失败折叠，其余项继续
            await db_session.rollback()
            failed.append(ApproveFailedItem(id=pending_id, reason=_format_failure(exc)))
    return ApproveResponse(created=created, failed=failed)


@checkpoint
async def reject_pending_writes(
    db_session: AsyncSession, schema: PendingWriteActionRequest
) -> RejectResponse:
    """放弃待写入登记（置 rejected；非 pending 项跳过）。

    参数: db_session — 数据库会话；schema — 请求（会话 + 登记行 id 列表）。
    返回值: RejectResponse（置 rejected 的 id 列表）。
    异常: NotFoundError — 会话或任一登记行不存在（显式 404，语义幂等可测）。
    依赖: agent.repository。
    """
    conversation = await _load_conversation(db_session, schema.conversation_id)
    rejected: list[str] = []
    for pending_id in schema.ids:
        row = await repository.get_pending(db_session, pending_id)
        if row is None or row.conversation_id != conversation.id:
            raise _pending_not_found(pending_id)
        if row.status == "pending":
            row.status = "rejected"
            await repository.save_pending(db_session, row)
            rejected.append(pending_id)
    await db_session.commit()
    return RejectResponse(rejected=rejected)


@checkpoint
async def list_pending_writes(
    db_session: AsyncSession, conversation_id: str
) -> list[PendingWriteRead]:
    """列出会话全部待写入登记（created_at 升序；含全部状态，前端回读）。

    参数: db_session — 数据库会话；conversation_id — 会话 id。
    返回值: list[PendingWriteRead]。异常: NotFoundError — 会话不存在。
    依赖: agent.repository。
    """
    await _load_conversation(db_session, conversation_id)
    rows = await repository.list_pending_by_conversation(db_session, conversation_id)
    return [_pending_read(r) for r in rows]


def _pending_not_found(pending_id: str) -> NotFoundError:
    """构造登记行不存在的三要素异常。"""
    return NotFoundError(
        problem="待写入登记不存在",
        cause=f"登记行 '{pending_id}' 未在库中，或不属于该会话",
        fix="以 done 事件清单 / GET /api/agent/pending-writes 中的 id 重试",
        detail={"pending_id": pending_id},
    )


# ---- 项目级联 ----


@checkpoint
async def delete_project_data(db_session: AsyncSession, project_id: str) -> list[str]:
    """清理项目的会话与记忆文档（项目删除级联的组合层入口）。

    参数: db_session — 数据库会话；project_id — 项目 id。
    返回值: list[str] — 被清理的会话 id 列表。异常: 无。
    依赖: app.agent.repository。
    """
    return await repository.delete_by_project(db_session, project_id)


async def dispose_resources() -> None:
    """释放模块级资源（LLM 客户端连接；应用停机时由 lifespan 调用）。

    作用: main 组合根只经本门面触达模块内部资源（import-linter 契约：
        main 禁止 import app.agent.llm 等内部层）。
    参数: 无。返回值: 无。异常: 无。依赖: app.agent.llm.dispose_client。
    """
    await llm.dispose_client()
