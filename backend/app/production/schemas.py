"""Public Production Document contracts."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ProductionDocumentType = Literal[
    "screenplay",
    "production_breakdown",
    "performance_script",
    "shot_plan",
    "storyboard",
    "timeline",
]


def generate_id() -> str:
    return f"pdoc-{uuid4().hex[:12]}"


class ProductionBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_type: str = Field(min_length=1, max_length=64)
    content: str = Field(max_length=100_000)
    semantic: dict[str, object] = Field(default_factory=dict)


class ProductionDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    episode_id: str
    scene_id: str | None = None
    document_type: ProductionDocumentType
    title: str = Field(min_length=1, max_length=200)
    blocks: list[ProductionBlockCreate] = Field(min_length=1)
    source_document_id: str | None = None
    source_block_ids: list[str] = Field(default_factory=list)


class ProductionDocumentRead(BaseModel):
    id: str
    project_id: str
    episode_id: str
    scene_id: str | None
    artifact_id: str
    document_type: ProductionDocumentType
    source_document_id: str | None
    source_artifact_id: str | None
    source_block_ids: list[str]
    created_at: datetime
