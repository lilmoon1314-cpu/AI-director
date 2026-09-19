"""Public request/response contracts for the Artifact domain."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ArtifactType = Literal[
    "screenplay",
    "production_breakdown",
    "performance_script",
    "shot_plan",
    "storyboard",
    "timeline",
]
DiffKind = Literal["unchanged", "modified", "added", "removed"]


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class ScreenplayBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_type: str = Field(min_length=1, max_length=64)
    content: str = Field(max_length=100_000)
    semantic: dict[str, object] | None = None


class ArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    type: ArtifactType
    title: str = Field(min_length=1, max_length=200)
    blocks: list[ScreenplayBlockCreate] = Field(min_length=1)


class ArtifactBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    block_type: str
    position: int
    content: str
    semantic: dict[str, object] | None


class ArtifactRevisionRead(BaseModel):
    id: str
    artifact_id: str
    revision_no: int
    blocks: list[ArtifactBlockRead]
    created_at: datetime


class ArtifactRead(BaseModel):
    id: str
    project_id: str
    type: ArtifactType
    title: str
    status: str
    approval_status: Literal["draft", "review", "approved", "archived"] = "draft"
    freshness: Literal["VALID", "STALE", "BLOCKED"] = "VALID"
    current_revision: ArtifactRevisionRead
    created_at: datetime
    updated_at: datetime


class BlockEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=100_000)
    semantic: dict[str, object] | None = None
    expected_revision_id: str | None = Field(default=None, min_length=1)


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_status: Literal["draft", "review", "approved", "archived"]
    expected_revision_id: str
    actor: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=10000)


class RevertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: str
    expected_revision_id: str
    actor: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=10000)


class RevisionDiffEntry(BaseModel):
    block_id: str
    kind: DiffKind
    old_position: int | None
    new_position: int | None
    old_content: str | None
    new_content: str | None


class RevisionDiffRead(BaseModel):
    artifact_id: str
    from_revision_id: str
    to_revision_id: str
    changed_block_ids: list[str]
    blocks: list[RevisionDiffEntry]


class DependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_artifact_id: str
    source_block_id: str
    source_revision_id: str | None = None
    dependent_artifact_id: str
    dependency_type: str = Field(default="derived_from", min_length=1, max_length=64)


class DependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    source_artifact_id: str
    source_block_id: str
    source_revision_id: str
    dependent_artifact_id: str
    dependency_type: str
    is_stale: bool
    created_at: datetime
    updated_at: datetime
