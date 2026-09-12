"""Public request and response schemas for Narrative State Core."""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

StateOperation = Literal["set", "add", "remove", "transition"]
CauseType = Literal["screenplay", "event", "user_edit", "system", "migration"]
KnowerType = Literal["character", "audience"]
KnowledgeStatus = Literal["unknown", "suspects", "believes", "knows", "misled"]


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class TimepointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    series_id: str | None = None
    episode_id: str | None = None
    scene_id: str | None = None
    beat_id: str | None = None
    sequence_no: int = Field(ge=0)
    world_time: str | None = None


class TimepointRead(TimepointCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class StateEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    subject_type: Literal["entity", "relationship"]
    subject_id: str = Field(min_length=1)
    attribute_key: str = Field(min_length=1, max_length=100)
    operation: StateOperation
    value: Any
    expected_before: Any | None = None
    timepoint_id: str = Field(min_length=1)
    cause_type: CauseType
    cause_ref: str = Field(min_length=1)
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    compensates_event_id: str | None = None

    @model_validator(mode="after")
    def validate_provenance_pair(self) -> "StateEventCreate":
        paired = self.source_artifact_id is not None and self.source_revision_id is not None
        if (self.source_artifact_id is None) != (self.source_revision_id is None):
            raise ValueError("source_artifact_id and source_revision_id must be supplied together")
        if self.cause_type == "screenplay" and not paired:
            raise ValueError("screenplay cause requires artifact and revision provenance")
        return self


class StateEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    subject_type: str
    subject_id: str
    attribute_key: str
    operation: str
    before_json: Any | None
    after_json: Any | None
    timepoint_id: str
    cause_type: str
    cause_ref: str
    source_artifact_id: str | None
    source_revision_id: str | None
    compensates_event_id: str | None
    created_at: datetime


class StateCurrentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: str
    subject_type: str
    subject_id: str
    attribute_key: str
    value_json: Any | None
    last_event_id: str
    timepoint_id: str
    version: int


class EventApplicationRead(BaseModel):
    event: StateEventRead
    current: StateCurrentRead


class SnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    scope_type: Literal["scene_entry", "scene_exit", "episode_entry", "episode_exit"]
    scope_id: str = Field(min_length=1)
    timepoint_id: str = Field(min_length=1)


class SnapshotRead(SnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    snapshot_json: list[dict[str, Any]]
    source_event_cursor: str | None
    created_at: datetime


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    predicate: str = Field(min_length=1, max_length=200)
    object_json: Any
    truth_status: Literal["true", "false", "uncertain"]
    author_note: str | None = None


class ClaimRead(ClaimCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class KnowledgeStateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    knower_type: KnowerType
    knower_id: str | None = None
    claim_id: str = Field(min_length=1)
    status: KnowledgeStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    acquired_timepoint_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_knower_shape(self) -> "KnowledgeStateCreate":
        if self.knower_type == "audience" and self.knower_id is not None:
            raise ValueError("audience knowledge must not supply knower_id")
        if self.knower_type == "character" and self.knower_id is None:
            raise ValueError("character knowledge requires knower_id")
        return self


class KnowledgeStateRead(KnowledgeStateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    superseded_by: str | None
    created_at: datetime
