"""Public Workflow Core contracts."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class RequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    content: dict[str, object]


class RequirementRead(BaseModel):
    id: str
    project_id: str
    version: int
    content: dict[str, object]
    created_at: datetime


class SeriesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    title: str = Field(min_length=1, max_length=200)


class SeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    title: str
    created_at: datetime


class EpisodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    series_id: str
    position: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    outline: str = Field(default="", max_length=100_000)


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    series_id: str
    position: int
    title: str
    outline: str
    status: str
    created_at: datetime


class ScenePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    episode_id: str
    position: int = Field(ge=0)
    location_ref: str | None = None
    time_context: str = Field(min_length=1, max_length=200)
    characters: list[str] = Field(default_factory=list)
    scene_goal: str = Field(min_length=1)
    character_goal: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    turn: str = Field(min_length=1)
    reveal: str = ""
    exit_change: str = Field(min_length=1)
    target_duration: int = Field(gt=0)
    required_setup: list[str] = Field(default_factory=list)
    required_payoff: list[str] = Field(default_factory=list)


class ScenePlanRead(BaseModel):
    id: str
    project_id: str
    episode_id: str
    position: int
    location_ref: str | None
    time_context: str
    characters: list[str]
    scene_goal: str
    character_goal: str
    conflict: str
    turn: str
    reveal: str
    exit_change: str
    target_duration: int
    required_setup: list[str]
    required_payoff: list[str]
    created_at: datetime


class GateRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    expected: object = True


class GateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    scope_type: Literal["project", "series", "episode", "scene"]
    scope_id: str
    stage: str = Field(min_length=1, max_length=100)
    requirements: list[GateRequirement] = Field(min_length=1)


class GateEvaluate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: dict[str, object]


class GateEvaluationRead(BaseModel):
    gate_id: str
    passed: bool
    unmet: list[GateRequirement]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    scope_type: Literal["project", "series", "episode", "scene", "artifact", "block"]
    scope_id: str
    skill_id: str = Field(min_length=1, max_length=200)
    input: dict[str, object] = Field(default_factory=dict)


class StepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=100)
    detail: dict[str, object] = Field(default_factory=dict)


class MockExecute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output: dict[str, object] = Field(default_factory=dict)
    steps: list[StepCreate] = Field(default_factory=list)


class StepRead(BaseModel):
    id: str
    position: int
    kind: str
    detail: dict[str, object]
    created_at: datetime


class RunRead(BaseModel):
    id: str
    project_id: str
    scope_type: str
    scope_id: str
    skill_id: str
    status: str
    input: dict[str, object]
    output: dict[str, object] | None
    steps: list[StepRead]
    created_at: datetime
    completed_at: datetime | None
