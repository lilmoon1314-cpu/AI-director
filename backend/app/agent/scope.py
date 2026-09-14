"""Authoritative internal context partition helpers; no model-selected scope."""

from app.agent.contracts import ContextScope
from app.agent.schemas import Perspective
from app.core.exceptions import AgentError


def context_key(perspective: Perspective, character_id: str = "") -> str:
    if perspective == "character":
        if not character_id:
            raise AgentError("角色视角缺少角色", "无法确定上下文分区", "先选择角色再发送")
        return f"character:{character_id}"
    return perspective


def make_scope(project_id: str, perspective: Perspective, character_id: str = "") -> ContextScope:
    context_key(perspective, character_id)
    return ContextScope(
        project_id=project_id,
        perspective=perspective,
        character_id=character_id if perspective == "character" else None,
    )
