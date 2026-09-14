"""Internal reliability contracts; persistence and runtime wiring belong to later slices.

These types validate metadata, never infer visibility or semantic truth from model text.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.schemas import Perspective


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ContextScope(Contract):
    project_id: str = Field(min_length=1)
    perspective: Perspective
    character_id: str | None = None

    @model_validator(mode="after")
    def validate_character(self) -> Self:
        if self.perspective == "character":
            if not self.character_id:
                raise ValueError("character scope requires character_id")
        elif self.character_id is not None:
            raise ValueError("only character scope may carry character_id")
        return self


class SourceRef(Contract):
    scope: ContextScope
    kind: Literal[
        "message",
        "section",
        "entity",
        "artifact_revision",
        "graph_projection",
        "project_metadata",
        "summary",
    ]
    source_id: str = Field(min_length=1)
    version: int | None = Field(default=None, ge=1)
    revision_id: str | None = None

    @model_validator(mode="after")
    def require_read_baseline(self) -> Self:
        if self.kind in {"section", "entity"} and self.version is None:
            raise ValueError("mutable sources require the version actually read")
        if self.kind == "artifact_revision" and not self.revision_id:
            raise ValueError("artifact sources require revision_id")
        return self


class ContextFragment(Contract):
    source: SourceRef
    reason: str = Field(min_length=1)
    estimated_tokens: int = Field(ge=0)
    disposition: Literal["included", "omitted", "denied"]
    required: bool = False


class ContextManifest(Contract):
    scope: ContextScope
    fragments: tuple[ContextFragment, ...]
    estimator: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_reserve: int = Field(ge=0)
    budget: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.input_tokens + self.output_reserve > self.budget:
            raise ValueError("request exceeds budget")
        for fragment in self.fragments:
            if fragment.disposition == "included" and fragment.source.scope != self.scope:
                raise ValueError("included source must belong to the exact context partition")
            if fragment.required and fragment.disposition != "included":
                raise ValueError("required context cannot be silently omitted")
        return self


class ToolResult(Contract):
    ok: bool
    content: str = ""
    error_code: str | None = None
    retryable: bool = False
    truncated: bool = False
    continuation: str | None = None
    sources: tuple[SourceRef, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.ok == (self.error_code is not None):
            raise ValueError("failed result requires error_code; success forbids it")
        if self.ok and self.retryable:
            raise ValueError("successful results must not request retries")
        if self.truncated and not self.continuation:
            raise ValueError("truncation requires an explicit continuation")
        return self


class SummaryCoverage(Contract):
    scope: ContextScope
    source_ids: tuple[str, ...] = Field(min_length=1)
    previous_cursor: str | None = None
    next_cursor: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: Literal["verified", "failed"]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if any(not source_id for source_id in self.source_ids):
            raise ValueError("source IDs must be nonempty")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("duplicate summary sources")
        if self.next_cursor != self.source_ids[-1]:
            raise ValueError("cursor must end at the last covered source")
        return self

    def covers(self, expected_source_ids: tuple[str, ...]) -> bool:
        """Check ordered range coverage, not the semantic accuracy of a summary."""
        return self.status == "verified" and self.source_ids == expected_source_ids


RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    "queued": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class RunEvent(Contract):
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    status: RunStatus

    def follows(self, previous: "RunEvent") -> bool:
        """Allow ordered running events, prohibit restart or rewriting terminal outcomes."""
        return (
            self.run_id == previous.run_id
            and self.sequence == previous.sequence + 1
            and (
                self.status in _TRANSITIONS[previous.status]
                or previous.status == self.status == "running"
            )
        )
