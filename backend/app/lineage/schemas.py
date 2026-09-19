"""Typed references: only owners with implemented validation are admitted."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Policy = Literal[
    "hard_stale",
    "review_required",
    "timing_revalidate",
    "compatibility_check",
    "notice_only",
    "none",
]
Validator = Literal["content_equal", "timing_equal"]


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["artifact", "artifact_block"]
    id: str = Field(min_length=1)
    revision_ref: str = Field(min_length=1)


class EdgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upstream: Reference
    downstream: Reference
    dependency_type: Literal[
        "structural",
        "semantic",
        "timing",
        "visual",
        "state",
        "spatial",
        "media",
        "generation_input",
        "reference",
    ] = "semantic"
    invalidation_policy: Policy = "hard_stale"
    compatibility_validator: Validator | None = None


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    upstream_type: str
    upstream_id: str
    upstream_revision_ref: str
    downstream_type: str
    downstream_id: str
    downstream_revision_ref: str
    dependency_type: str
    invalidation_policy: str
    compatibility_validator: str | None
    state: str
    stale_cause_ref: str | None
    supersedes_id: str | None
    created_at: datetime
    updated_at: datetime


class ImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Reference
    changed_block_ids: list[str] = Field(default_factory=list)


class ImpactRead(BaseModel):
    edges: list[EdgeRead]
    blocked_artifact_ids: list[str]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=10000)


class EdgeReview(ReviewRequest):
    expected_upstream_revision_ref: str
    expected_downstream_revision_ref: str
    decision: Literal["still_valid", "rebase"]


class ProposalCreate(ReviewRequest):
    origin: Reference
    target: Reference
    content: str = Field(max_length=100000)
    semantic: dict[str, object] | None = None
    evidence: dict[str, object] = Field(default_factory=dict)


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    origin_type: str
    origin_id: str
    origin_revision_ref: str
    target_type: str
    target_id: str
    target_base_revision_ref: str
    proposal_kind: str
    patch_json: dict[str, object]
    rationale: str
    evidence_json: dict[str, object]
    status: str
    committed_ref: str | None
    created_by: str
    created_at: datetime
    decided_at: datetime | None


class ProposalDecision(ReviewRequest):
    decision: Literal["accept", "reject", "supersede"]


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    subject_id: str
    action: str
    actor: str
    rationale: str
    details_json: dict[str, object]
    created_at: datetime
