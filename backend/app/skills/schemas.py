"""Public Atomic Skill API contracts."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def generate_id() -> str:
    return f"cand-{uuid4().hex[:12]}"


class SkillRead(BaseModel):
    id: str
    scope: str
    required_context: list[str]
    optional_context: list[str]
    writes: list[str]
    forbidden: list[str]
    validators: list[str]


class SkillExecute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    scope_type: str
    scope_id: str
    context: dict[str, object] = Field(default_factory=dict)
    input: dict[str, object] = Field(default_factory=dict)
    candidate: dict[str, object]
    gate_id: str | None = None
    gate_facts: dict[str, object] = Field(default_factory=dict)


class CandidateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str


class CandidateRead(BaseModel):
    id: str
    project_id: str
    run_id: str
    skill_id: str
    scope_type: str
    scope_id: str
    candidate: dict[str, object]
    impact: dict[str, object]
    status: str
    committed_ref: str | None
    base_revision_id: str | None
    created_at: datetime
    decided_at: datetime | None
