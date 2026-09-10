"""Public Agent service façade.

Routers and cross-domain callers import this module. Conversation, context, document, write, and
chat owners live in focused internal modules; this façade preserves the established callable
contract.
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import chat, conversations, documents, llm, repository, tools, writes
from app.agent.prompts import wrap_data
from app.agent.schemas import (
    ConfirmRequest,
    ConfirmResponse,
    PendingWriteActionRequest,
    Perspective,
    ProposeRequest,
    ProposeResponse,
)
from app.config import get_settings
from app.core.observability import checkpoint

# Stable SSE names remain available from the service boundary.
EVENT_MESSAGE_START = chat.EVENT_MESSAGE_START
EVENT_TOKEN = chat.EVENT_TOKEN
EVENT_REASONING = chat.EVENT_REASONING
EVENT_USAGE = chat.EVENT_USAGE
EVENT_TOOL = chat.EVENT_TOOL
EVENT_DRAFT = chat.EVENT_DRAFT
EVENT_DOC_PATCH = chat.EVENT_DOC_PATCH
EVENT_ASK_USER = chat.EVENT_ASK_USER
EVENT_DONE = chat.EVENT_DONE
EVENT_ERROR = chat.EVENT_ERROR

# Stable conversation service contract.
create_conversation = conversations.create_conversation
ensure_conversation = conversations.ensure_conversation
list_conversations = conversations.list_conversations
get_messages = conversations.get_messages
delete_conversation = conversations.delete_conversation
delete_project_data = conversations.delete_project_data

# Stable memory-document service contract.
create_doc = documents.create_doc
list_docs = documents.list_docs
get_doc = documents.get_doc
delete_doc = documents.delete_doc
update_section = documents.update_section
render_page = documents.render_page

# Stable confirmed-write service contract.
confirm_write = writes.confirm_write
approve_pending_writes = writes.approve_pending_writes
reject_pending_writes = writes.reject_pending_writes
list_pending_writes = writes.list_pending_writes

# Compatibility seams for tests/callers that patch shared implementation modules.
entities_service = writes.entities_service
relations_service = writes.relations_service


async def stream_chat(
    conversation_id: str,
    message: str,
    *,
    perspective: Perspective,
    character_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """Delegate one SSE turn while resolving runtime settings at the public boundary."""
    async for event in chat.stream_chat(
        conversation_id,
        message,
        perspective=perspective,
        character_id=character_id,
        settings=get_settings(),
    ):
        yield event


@checkpoint
async def propose_drafts(db_session: AsyncSession, schema: ProposeRequest) -> ProposeResponse:
    """Delegate the legacy propose compatibility surface with current runtime settings."""
    return await writes.propose_drafts(db_session, schema, settings=get_settings())


async def dispose_resources() -> None:
    """Release Agent-owned provider resources during application shutdown."""
    await llm.dispose_client()


__all__ = [
    "ConfirmRequest",
    "ConfirmResponse",
    "PendingWriteActionRequest",
    "approve_pending_writes",
    "confirm_write",
    "create_conversation",
    "create_doc",
    "delete_conversation",
    "delete_doc",
    "delete_project_data",
    "dispose_resources",
    "ensure_conversation",
    "get_doc",
    "get_messages",
    "list_conversations",
    "list_docs",
    "list_pending_writes",
    "propose_drafts",
    "reject_pending_writes",
    "render_page",
    "repository",
    "stream_chat",
    "tools",
    "update_section",
    "wrap_data",
]
