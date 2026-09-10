"""Agent 会话与消息生命周期 owner。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import repository
from app.agent.models import Conversation, Message
from app.agent.schemas import (
    MessageRead,
    SessionCreate,
    SessionRead,
    generate_conversation_id,
)
from app.core.exceptions import NotFoundError
from app.core.observability import checkpoint
from app.projects import service as projects_service


def conversation_not_found(conversation_id: str) -> NotFoundError:
    return NotFoundError(
        problem="会话不存在",
        cause=f"conversation_id '{conversation_id}' 未在库中",
        fix="先调用 GET /api/agent/sessions 确认会话 id",
        detail={"conversation_id": conversation_id},
    )


async def load_conversation(db_session: AsyncSession, conversation_id: str) -> Conversation:
    conversation = await repository.get_conversation(db_session, conversation_id)
    if conversation is None:
        raise conversation_not_found(conversation_id)
    return conversation


def _session_read(conversation: Conversation) -> SessionRead:
    return SessionRead(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_read(message: Message) -> MessageRead:
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


@checkpoint
async def create_conversation(db_session: AsyncSession, schema: SessionCreate) -> SessionRead:
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
    return _session_read(await load_conversation(db_session, conversation_id))


@checkpoint
async def list_conversations(db_session: AsyncSession, project_id: str) -> list[SessionRead]:
    resolved = project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(db_session, resolved)
    rows = await repository.list_conversations(db_session, resolved)
    return [_session_read(conversation) for conversation in rows]


@checkpoint
async def get_messages(db_session: AsyncSession, conversation_id: str) -> list[MessageRead]:
    await load_conversation(db_session, conversation_id)
    rows = await repository.list_messages(db_session, conversation_id)
    return [_message_read(message) for message in rows]


@checkpoint
async def delete_conversation(db_session: AsyncSession, conversation_id: str) -> None:
    conversation = await load_conversation(db_session, conversation_id)
    await repository.delete_conversation(db_session, conversation)
    await db_session.commit()


@checkpoint
async def delete_project_data(db_session: AsyncSession, project_id: str) -> list[str]:
    """清理项目的全部 Agent-owned persistence。"""
    return await repository.delete_by_project(db_session, project_id)
