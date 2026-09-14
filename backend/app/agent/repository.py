"""agent 模块数据访问层：唯一允许 import 本模块 ORM 模型的层。

事务约定: 本层不 commit/rollback（事务边界在 service 层，backend/CONSTRAINTS.md）。
"""

from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import (
    AgentRun,
    AgentRunEvent,
    Conversation,
    ConversationPartition,
    MemoryDoc,
    MemoryDocSection,
    Message,
    PendingWrite,
)


async def summary_partition(
    session: AsyncSession,
    conversation: Conversation,
    key: str,
    *,
    create: bool = False,
) -> Conversation | ConversationPartition | None:
    if key == "author":
        return conversation
    row = await session.get(ConversationPartition, (conversation.id, key))
    if row is None and create:
        row = ConversationPartition(conversation_id=conversation.id, context_key=key, summary="")
        session.add(row)
        await session.flush()
    return row


# ---- 会话 ----


async def add_conversation(session: AsyncSession, conversation: Conversation) -> Conversation:
    """插入一条会话记录（不提交事务）。

    参数: session — 数据库会话；conversation — 已填充字段的 ORM 实例。
    返回值: Conversation。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(conversation)
    await session.flush()
    return conversation


async def get_conversation(session: AsyncSession, conversation_id: str) -> Conversation | None:
    """按 id 查询会话。

    参数: session — 数据库会话；conversation_id — 会话 id。
    返回值: Conversation 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(Conversation, conversation_id)


async def list_conversations(session: AsyncSession, project_id: str) -> list[Conversation]:
    """列出项目的全部会话（最近活跃在前）。

    作用: AgentHome 左栏会话列表数据源；id 作同刻次序键保证稳定。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: list[Conversation]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
    )
    return list(await session.scalars(stmt))


async def save_conversation(session: AsyncSession, conversation: Conversation) -> Conversation:
    """保存已修改的会话（标题/摘要/游标/updated_at 刷新）。

    参数: session — 数据库会话；conversation — 已在内存修改的 ORM 实例。
    返回值: Conversation。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return conversation


async def delete_conversation(session: AsyncSession, conversation: Conversation) -> None:
    """删除会话（消息经 FK CASCADE 随之清理；不提交事务）。

    参数: session — 数据库会话；conversation — 待删除的 ORM 实例。
    返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(conversation)
    await session.flush()


# ---- 消息 ----


async def add_message(session: AsyncSession, message: Message) -> Message:
    """插入一条消息（不提交事务）。

    参数: session — 数据库会话；message — 已填充字段的 ORM 实例。
    返回值: Message。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(message)
    await session.flush()
    return message


async def list_messages(session: AsyncSession, conversation_id: str) -> list[Message]:
    """按时间正序列出会话全部消息（含已摘要覆盖的旧消息，不删历史）。

    参数: session — 数据库会话；conversation_id — 会话 id。
    返回值: list[Message]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id)
    )
    return list(await session.scalars(stmt))


async def get_message(session: AsyncSession, message_id: str) -> Message | None:
    return await session.get(Message, message_id)


async def get_assistant_message_by_run(session: AsyncSession, run_id: str) -> Message | None:
    return await session.scalar(
        select(Message).where(Message.run_id == run_id, Message.role == "assistant").limit(1)
    )


# ---- 持久聊天运行与事件 ----


async def add_run(session: AsyncSession, run: AgentRun) -> AgentRun:
    session.add(run)
    await session.flush()
    return run


async def get_run(session: AsyncSession, run_id: str) -> AgentRun | None:
    return await session.get(AgentRun, run_id)


async def get_run_by_request(
    session: AsyncSession, conversation_id: str, request_id: str
) -> AgentRun | None:
    return await session.scalar(
        select(AgentRun).where(
            AgentRun.conversation_id == conversation_id, AgentRun.request_id == request_id
        )
    )


async def latest_run(session: AsyncSession, conversation_id: str) -> AgentRun | None:
    return await session.scalar(
        select(AgentRun)
        .where(AgentRun.conversation_id == conversation_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(1)
    )


async def claim_run(session: AsyncSession, run_id: str, started_at: datetime) -> bool:
    result = await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == "queued")
        .values(status="running", started_at=started_at)
        .execution_options(synchronize_session=False)
    )
    return bool(getattr(result, "rowcount", 0) == 1)


async def next_run_event_seq(session: AsyncSession, run_id: str) -> int:
    current = await session.scalar(
        select(func.max(AgentRunEvent.seq)).where(AgentRunEvent.run_id == run_id)
    )
    return int(current or 0) + 1


async def add_run_event(session: AsyncSession, event: AgentRunEvent) -> AgentRunEvent:
    session.add(event)
    await session.flush()
    return event


async def list_run_events(
    session: AsyncSession, run_id: str, after_seq: int = 0
) -> list[AgentRunEvent]:
    return list(
        await session.scalars(
            select(AgentRunEvent)
            .where(AgentRunEvent.run_id == run_id, AgentRunEvent.seq > after_seq)
            .order_by(AgentRunEvent.seq.asc())
        )
    )


async def request_run_cancel(session: AsyncSession, run_id: str) -> None:
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status.in_(("queued", "running")))
        .values(cancel_requested=True)
        .execution_options(synchronize_session=False)
    )


async def delete_expired_run_events(session: AsyncSession, cutoff: datetime) -> None:
    terminal_runs = select(AgentRun.id).where(
        AgentRun.completed_at.is_not(None), AgentRun.completed_at < cutoff
    )
    await session.execute(sa_delete(AgentRunEvent).where(AgentRunEvent.run_id.in_(terminal_runs)))


# ---- 记忆文档与段 ----


async def add_doc(session: AsyncSession, doc: MemoryDoc) -> MemoryDoc:
    """插入一条记忆文档（不提交事务）。

    参数: session — 数据库会话；doc — 已填充字段的 ORM 实例。
    返回值: MemoryDoc。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(doc)
    await session.flush()
    return doc


async def get_doc(session: AsyncSession, doc_id: str) -> MemoryDoc | None:
    """按 id 查询记忆文档。

    参数: session — 数据库会话；doc_id — 文档 id。
    返回值: MemoryDoc 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(MemoryDoc, doc_id)


async def list_docs(session: AsyncSession, project_id: str) -> list[MemoryDoc]:
    """列出项目的全部记忆文档（最近更新在前）。

    参数: session — 数据库会话；project_id — 项目 id。
    返回值: list[MemoryDoc]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(MemoryDoc)
        .where(MemoryDoc.project_id == project_id)
        .order_by(MemoryDoc.updated_at.desc(), MemoryDoc.id)
    )
    return list(await session.scalars(stmt))


async def find_doc_by_kind(session: AsyncSession, project_id: str, kind: str) -> MemoryDoc | None:
    """查询项目内指定 kind 的记忆文档（指导类唯一性查重用）。

    参数: session — 数据库会话；project_id — 项目 id；kind — 模板键。
    返回值: MemoryDoc 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = select(MemoryDoc).where(MemoryDoc.project_id == project_id, MemoryDoc.kind == kind)
    return (await session.scalars(stmt)).first()


async def delete_doc(session: AsyncSession, doc: MemoryDoc) -> None:
    """删除记忆文档（段经 FK CASCADE 随之清理；不提交事务）。

    参数: session — 数据库会话；doc — 待删除的 ORM 实例。
    返回值: 无。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.delete(doc)
    await session.flush()


async def add_section(session: AsyncSession, section: MemoryDocSection) -> MemoryDocSection:
    """插入一条文档段（不提交事务）。

    参数: session — 数据库会话；section — 已填充字段的 ORM 实例。
    返回值: MemoryDocSection。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(section)
    await session.flush()
    return section


async def list_sections(session: AsyncSession, doc_id: str) -> list[MemoryDocSection]:
    """按 seq 正序列出文档全部段。

    参数: session — 数据库会话；doc_id — 文档 id。
    返回值: list[MemoryDocSection]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(MemoryDocSection)
        .where(MemoryDocSection.doc_id == doc_id)
        .order_by(MemoryDocSection.seq.asc())
    )
    return list(await session.scalars(stmt))


async def get_section(session: AsyncSession, section_id: str) -> MemoryDocSection | None:
    """按 id 查询文档段。

    参数: session — 数据库会话；section_id — 段 id。
    返回值: MemoryDocSection 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(MemoryDocSection, section_id)


async def save_section(session: AsyncSession, section: MemoryDocSection) -> MemoryDocSection:
    """保存已修改的段（内容/版本/updated_by/updated_at）。

    参数: session — 数据库会话；section — 已在内存修改的 ORM 实例。
    返回值: MemoryDocSection。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return section


async def update_section_if_version(
    session: AsyncSession,
    *,
    doc_id: str,
    section_id: str,
    expected_version: int,
    content: str,
    title: str | None,
    updated_by: str,
    updated_at: object,
) -> bool:
    """原子更新段版本，并在同一事务内推进父文档版本。"""
    values: dict[str, object] = {
        "content": content,
        "version": expected_version + 1,
        "updated_by": updated_by,
        "updated_at": updated_at,
    }
    if title is not None:
        values["title"] = title
    result = await session.execute(
        update(MemoryDocSection)
        .where(
            MemoryDocSection.id == section_id,
            MemoryDocSection.doc_id == doc_id,
            MemoryDocSection.version == expected_version,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        return False
    await session.execute(
        update(MemoryDoc)
        .where(MemoryDoc.id == doc_id)
        .values(version=MemoryDoc.version + 1, updated_at=updated_at)
        .execution_options(synchronize_session=False)
    )
    return True


# ---- 待写入登记（F14 轮末统一确认）----


async def add_pending(session: AsyncSession, pending: PendingWrite) -> PendingWrite:
    """插入一条待写入登记（不提交事务；随对话轮事务提交/回滚）。

    参数: session — 数据库会话；pending — 已填充字段的 ORM 实例。
    返回值: PendingWrite。异常: 无。依赖: SQLAlchemy ORM。
    """
    session.add(pending)
    await session.flush()
    return pending


async def get_pending(session: AsyncSession, pending_id: str) -> PendingWrite | None:
    """按 id 查询待写入登记。

    参数: session — 数据库会话；pending_id — 登记行 id。
    返回值: PendingWrite 或 None。异常: 无。依赖: SQLAlchemy ORM。
    """
    return await session.get(PendingWrite, pending_id)


async def list_pending_by_conversation(
    session: AsyncSession, conversation_id: str
) -> list[PendingWrite]:
    """按会话列出全部待写入登记（created_at 升序；含全部状态）。

    参数: session — 数据库会话；conversation_id — 会话 id。
    返回值: list[PendingWrite]。异常: 无。依赖: SQLAlchemy ORM。
    """
    stmt = (
        select(PendingWrite)
        .where(PendingWrite.conversation_id == conversation_id)
        .order_by(PendingWrite.created_at.asc(), PendingWrite.id)
    )
    return list(await session.scalars(stmt))


async def save_pending(session: AsyncSession, pending: PendingWrite) -> PendingWrite:
    """保存已修改的登记行（status 状态流转；不提交事务）。

    参数: session — 数据库会话；pending — 已在内存修改的 ORM 实例。
    返回值: PendingWrite。异常: 无。依赖: SQLAlchemy ORM。
    """
    await session.flush()
    return pending


async def claim_pending(session: AsyncSession, pending_id: str) -> bool:
    """用数据库条件更新取得决定权；approving 只存在于当前未提交事务。"""
    result = await session.execute(
        update(PendingWrite)
        .where(PendingWrite.id == pending_id, PendingWrite.status == "pending")
        .values(status="approving")
        .execution_options(synchronize_session=False)
    )
    return bool(getattr(result, "rowcount", 0) == 1)


async def reject_pending_if_pending(session: AsyncSession, pending_id: str) -> bool:
    """只有 pending 可原子转为 rejected，供 approve/reject 并发竞争。"""
    result = await session.execute(
        update(PendingWrite)
        .where(PendingWrite.id == pending_id, PendingWrite.status == "pending")
        .values(status="rejected")
        .execution_options(synchronize_session=False)
    )
    return bool(getattr(result, "rowcount", 0) == 1)


# ---- 项目级联 ----


async def delete_by_project(session: AsyncSession, project_id: str) -> list[str]:
    """删除项目的全部会话与记忆文档（消息/段经 CASCADE 清理；不提交事务）。

    作用: 项目删除的级联清理入口（由 projects.router 组合层编排调用）。
    参数: session — 数据库会话；project_id — 项目 id。
    返回值: list[str] — 被清理的会话 id 列表（供级联结果汇总）。
    异常: 无。依赖: SQLAlchemy ORM。
    """
    conv_ids = list(
        await session.scalars(select(Conversation.id).where(Conversation.project_id == project_id))
    )
    await session.execute(sa_delete(Conversation).where(Conversation.project_id == project_id))
    await session.execute(sa_delete(MemoryDoc).where(MemoryDoc.project_id == project_id))
    return conv_ids
