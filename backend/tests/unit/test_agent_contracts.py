"""Reliability metadata invariants, independent of provider and persistence."""

import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    ContextFragment,
    ContextManifest,
    ContextScope,
    RunEvent,
    SourceRef,
    SummaryCoverage,
    ToolResult,
)

pytestmark = pytest.mark.unit
AUTHOR = ContextScope(project_id="project-a", perspective="author")


@pytest.mark.parametrize(
    "values",
    [
        {"project_id": "", "perspective": "author"},
        {"project_id": "p", "perspective": "character"},
        {"project_id": "p", "perspective": "audience", "character_id": "c"},
        {"project_id": "p", "perspective": "author", "bypass": True},
    ],
)
def test_invalid_scope_rejected(values):
    with pytest.raises(ValidationError):
        ContextScope(**values)


@pytest.mark.parametrize("kind", ["section", "entity", "artifact_revision"])
def test_mutable_or_revision_source_requires_read_baseline(kind):
    with pytest.raises(ValidationError):
        SourceRef(scope=AUTHOR, kind=kind, source_id="source")


@pytest.mark.parametrize(
    "scope,disposition,required,input_tokens",
    [
        (ContextScope(project_id="other", perspective="author"), "included", False, 10),
        (ContextScope(project_id="project-a", perspective="audience"), "included", False, 10),
        (AUTHOR, "omitted", True, 10),
        (AUTHOR, "included", False, 91),
    ],
)
def test_manifest_rejects_wrong_scope_lost_constraints_and_overflow(
    scope, disposition, required, input_tokens
):
    with pytest.raises(ValidationError):
        ContextManifest(
            scope=AUTHOR,
            fragments=(
                ContextFragment(
                    source=SourceRef(scope=scope, kind="message", source_id="m1"),
                    reason="current requirement",
                    estimated_tokens=10,
                    disposition=disposition,
                    required=required,
                ),
            ),
            estimator="test",
            input_tokens=input_tokens,
            output_reserve=10,
            budget=100,
        )


def test_manifest_allows_explicit_denial_and_exact_budget():
    manifest = ContextManifest(
        scope=AUTHOR,
        fragments=(
            ContextFragment(
                source=SourceRef(
                    scope=ContextScope(project_id="other", perspective="author"),
                    kind="message",
                    source_id="m2",
                ),
                reason="different project",
                estimated_tokens=10,
                disposition="denied",
            ),
        ),
        estimator="test",
        input_tokens=90,
        output_reserve=10,
        budget=100,
    )
    assert manifest.fragments[0].disposition == "denied"


@pytest.mark.parametrize(
    "values",
    [
        {"ok": False},
        {"ok": True, "error_code": "TIMEOUT"},
        {"ok": True, "retryable": True},
        {"ok": True, "truncated": True},
    ],
)
def test_tool_result_cannot_hide_failure_or_truncation(values):
    with pytest.raises(ValidationError):
        ToolResult(**values)


def test_coverage_requires_exact_order_and_success():
    coverage = SummaryCoverage(
        scope=AUTHOR,
        source_ids=("m1", "m2"),
        next_cursor="m2",
        strategy_version="v1",
        model="fake",
        status="verified",
    )
    assert coverage.covers(("m1", "m2"))
    assert not coverage.covers(("m2", "m1"))
    assert not coverage.covers(("m0", "m1", "m2"))
    assert not coverage.model_copy(update={"status": "failed"}).covers(("m1", "m2"))


@pytest.mark.parametrize("ids,cursor", [(("m1", "m1"), "m1"), (("m1", "m2"), "m1")])
def test_coverage_rejects_duplicate_sources_and_false_cursor(ids, cursor):
    with pytest.raises(ValidationError):
        SummaryCoverage(
            scope=AUTHOR,
            source_ids=ids,
            next_cursor=cursor,
            strategy_version="v1",
            model="fake",
            status="verified",
        )


def test_run_events_are_ordered_and_terminal_states_are_final():
    queued = RunEvent(run_id="r1", sequence=1, status="queued")
    running = RunEvent(run_id="r1", sequence=2, status="running")
    completed = RunEvent(run_id="r1", sequence=3, status="completed")
    assert running.follows(queued)
    assert completed.follows(running)
    assert not completed.follows(queued)
    assert not RunEvent(run_id="r2", sequence=3, status="completed").follows(running)
    for status in ("running", "completed", "failed", "cancelled"):
        assert not RunEvent(run_id="r1", sequence=4, status=status).follows(completed)
