"""Lineage policies, owner validation, immutable rebase, and auditable review boundary."""

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.observability import emit_event
from app.lineage import repository
from app.lineage.models import LineageEdge, ReviewAudit, now
from app.lineage.schemas import (
    EdgeCreate,
    EdgeRead,
    EdgeReview,
    ImpactRead,
    ImpactRequest,
    ProposalCreate,
    ProposalDecision,
    ProposalRead,
    Reference,
)
from app.projects import service as projects_service


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def invalid(cause: str) -> ValidationError:
    return ValidationError(
        "Invalid lineage operation", cause, "Reload same-project owner references"
    )


def conflict(cause: str) -> ConflictError:
    return ConflictError("Lineage base changed", cause, "Reload and review the current revisions")


async def resolve(session: AsyncSession, project_id: str, ref: Reference) -> dict[str, Any]:
    from app.artifacts import service as artifacts

    result = await artifacts.resolve_lineage_ref(session, ref.type, ref.id, ref.revision_ref)
    if result["project_id"] != project_id:
        raise invalid("Reference does not belong to the requested project")
    return result


async def current(
    session: AsyncSession, project_id: str, kind: str, resource_id: str
) -> dict[str, Any]:
    from app.artifacts import service as artifacts

    result = await artifacts.resolve_lineage_ref(session, kind, resource_id)
    if result["project_id"] != project_id:
        raise invalid("Reference does not belong to the requested project")
    return result


async def audit(
    session: AsyncSession,
    project_id: str,
    subject_id: str,
    action: str,
    actor: str,
    rationale: str,
    details: dict[str, object],
) -> None:
    await repository.add(
        session,
        ReviewAudit(
            id=new_id("review"),
            project_id=project_id,
            subject_id=subject_id,
            action=action,
            actor=actor,
            rationale=rationale,
            details_json=details,
        ),
    )
    emit_event(
        action, component="lineage", data={"project_id": project_id, "subject_id": subject_id}
    )


async def get_edge(session: AsyncSession, project_id: str, edge_id: str) -> LineageEdge:
    row = await repository.edge(session, edge_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Lineage edge not found", edge_id, "Use a same-project edge ID")
    return row


async def _owner_id(session: AsyncSession, edge: LineageEdge) -> str:
    source = await current(session, edge.project_id, edge.upstream_type, edge.upstream_id)
    return str(source["artifact_id"])


async def _graph(session: AsyncSession, project_id: str) -> list[tuple[LineageEdge, str]]:
    return [
        (edge, await _owner_id(session, edge))
        for edge in await repository.edges(session, project_id)
        if edge.state != "superseded"
    ]


def _freshness(
    artifact_id: str, graph: list[tuple[LineageEdge, str]], visited: frozenset[str] = frozenset()
) -> str:
    if artifact_id in visited:
        return "BLOCKED"
    result = "VALID"
    for edge, owner_id in graph:
        if edge.downstream_id != artifact_id or edge.invalidation_policy in ("none", "notice_only"):
            continue
        if _freshness(owner_id, graph, visited | {artifact_id}) != "VALID":
            return "BLOCKED"
        if edge.state == "stale":
            if edge.invalidation_policy in ("timing_revalidate", "compatibility_check"):
                return "BLOCKED"
            result = "STALE"
    return result


async def freshness(session: AsyncSession, project_id: str, artifact_id: str) -> str:
    return _freshness(artifact_id, await _graph(session, project_id))


async def create_edge(
    session: AsyncSession,
    project_id: str,
    schema: EdgeCreate,
    *,
    commit: bool = True,
    legacy_type: str | None = None,
) -> EdgeRead:
    await repository.lock_project(session, project_id)
    upstream = await resolve(session, project_id, schema.upstream)
    downstream = await resolve(session, project_id, schema.downstream)
    if schema.downstream.type != "artifact":
        raise invalid("Initial downstream owner is artifact; block-local sources are supported")
    latest = await current(session, project_id, "artifact", schema.downstream.id)
    if latest["revision_id"] != schema.downstream.revision_ref:
        raise conflict("Downstream revision is no longer current")
    if upstream["artifact_id"] == downstream["artifact_id"]:
        raise invalid("Self-dependency is not allowed")
    if schema.invalidation_policy == "compatibility_check" and not schema.compatibility_validator:
        raise invalid("compatibility_check requires an implemented validator")
    if (
        schema.invalidation_policy == "timing_revalidate"
        and schema.compatibility_validator != "timing_equal"
    ):
        raise invalid("timing_revalidate requires timing_equal")
    graph = await _graph(session, project_id)
    reachable = {str(downstream["artifact_id"])}
    while True:
        expanded = reachable | {edge.downstream_id for edge, owner in graph if owner in reachable}
        if expanded == reachable:
            break
        reachable = expanded
    if upstream["artifact_id"] in reachable:
        raise invalid("Dependency would introduce a cycle")
    for edge, _ in graph:
        if (edge.upstream_type, edge.upstream_id, edge.downstream_id) == (
            schema.upstream.type,
            schema.upstream.id,
            schema.downstream.id,
        ):
            raise conflict("A live dependency for these endpoints already exists")
    latest_source = await current(session, project_id, schema.upstream.type, schema.upstream.id)
    stale = upstream["blocks"] != latest_source["blocks"]
    if schema.invalidation_policy in ("none", "notice_only"):
        stale = False
    row = LineageEdge(
        id=new_id("edge"),
        project_id=project_id,
        upstream_type=schema.upstream.type,
        upstream_id=schema.upstream.id,
        upstream_revision_ref=schema.upstream.revision_ref,
        downstream_type=schema.downstream.type,
        downstream_id=schema.downstream.id,
        downstream_revision_ref=schema.downstream.revision_ref,
        dependency_type=legacy_type or schema.dependency_type,
        invalidation_policy=schema.invalidation_policy,
        compatibility_validator=schema.compatibility_validator,
        state="stale" if stale else "active",
        stale_cause_ref=str(latest_source["revision_id"]) if stale else None,
        created_at=now(),
        updated_at=now(),
    )
    await repository.add(session, row)
    if commit:
        await session.commit()
    return EdgeRead.model_validate(row)


async def advance_downstream(
    session: AsyncSession, project_id: str, artifact_id: str, revision_id: str
) -> None:
    """Freeze each old revision's dependency evidence and carry baselines into the next revision."""
    for old in await repository.edges(session, project_id):
        if old.state == "superseded" or old.downstream_id != artifact_id:
            continue
        values = EdgeRead.model_validate(old).model_dump(
            exclude={"id", "created_at", "updated_at", "supersedes_id"}
        )
        values["downstream_revision_ref"] = revision_id
        old.state = "superseded"
        await repository.add(
            session, LineageEdge(id=new_id("edge"), supersedes_id=old.id, **values)
        )


async def mark_revert_for_review(
    session: AsyncSession, project_id: str, artifact_id: str, revision_id: str
) -> None:
    """Reverted content cannot silently inherit approval of current source assumptions.

    Keep all current source baselines (including migrated ones) and require explicit review.
    Historical pre-Lineage revisions do not necessarily have complete dependency snapshots.
    """
    for edge in await repository.edges(session, project_id):
        if (
            edge.state != "superseded"
            and edge.downstream_id == artifact_id
            and edge.invalidation_policy not in ("none", "notice_only")
        ):
            edge.state = "stale"
            edge.stale_cause_ref = revision_id


async def invalidate_artifact(
    session: AsyncSession,
    project_id: str,
    artifact_id: str,
    revision_id: str,
    changed_ids: list[str],
) -> None:
    if not changed_ids:
        return
    for edge, owner in await _graph(session, project_id):
        if owner != artifact_id or edge.state == "stale":
            continue
        if edge.upstream_type == "artifact_block" and edge.upstream_id not in changed_ids:
            continue
        baseline = await resolve(
            session,
            project_id,
            Reference(
                type=edge.upstream_type,
                id=edge.upstream_id,
                revision_ref=edge.upstream_revision_ref,
            ),
        )
        latest = await current(session, project_id, edge.upstream_type, edge.upstream_id)
        if baseline["blocks"] == latest["blocks"]:
            continue
        if edge.invalidation_policy == "none":
            continue
        if edge.invalidation_policy != "notice_only":
            edge.state = "stale"
            edge.stale_cause_ref = revision_id
        await audit(
            session,
            project_id,
            edge.id,
            "lineage_notice"
            if edge.invalidation_policy == "notice_only"
            else "lineage_stale_marked",
            "system",
            "Upstream revision changed",
            {"revision_id": revision_id},
        )


async def impact(session: AsyncSession, project_id: str, schema: ImpactRequest) -> ImpactRead:
    source = await resolve(session, project_id, schema.source)
    latest = await current(session, project_id, schema.source.type, schema.source.id)
    if latest["revision_id"] != schema.source.revision_ref:
        raise conflict("Impact preview base is no longer current")
    block_ids = {str(block["id"]) for block in source["blocks"]}
    if not set(schema.changed_block_ids) <= block_ids:
        raise invalid("Changed blocks do not belong to source revision")
    selected = set(schema.changed_block_ids) or block_ids
    graph = await _graph(session, project_id)
    direct = [
        edge
        for edge, owner in graph
        if owner == source["artifact_id"]
        and (edge.upstream_type == "artifact" or edge.upstream_id in selected)
    ]
    affected = {
        edge.downstream_id
        for edge in direct
        if edge.invalidation_policy not in ("none", "notice_only")
    }
    initial = set(affected)
    while True:
        expanded = affected | {
            edge.downstream_id
            for edge, owner in graph
            if owner in affected and edge.invalidation_policy not in ("none", "notice_only")
        }
        if affected == expanded:
            break
        affected = expanded
    return ImpactRead(
        edges=[EdgeRead.model_validate(row) for row in direct],
        blocked_artifact_ids=sorted(affected - initial),
    )


def compatible(validator: str | None, upstream: dict[str, Any], downstream: dict[str, Any]) -> bool:
    """Fail closed; compatibility uses server-loaded snapshots, never client assertions."""
    if validator == "content_equal":
        return [(b["content"], b["semantic"]) for b in upstream["blocks"]] == [
            (b["content"], b["semantic"]) for b in downstream["blocks"]
        ]
    if validator == "timing_equal":

        def durations(ref: dict[str, Any]) -> list[object]:
            return [(b.get("semantic") or {}).get("duration_ms") for b in ref["blocks"]]

        left, right = durations(upstream), durations(downstream)
        return (
            bool(left)
            and all(type(value) is int and value > 0 for value in left + right)
            and left == right
        )
    return False


async def review_edge(
    session: AsyncSession, project_id: str, edge_id: str, schema: EdgeReview, *, commit: bool = True
) -> EdgeRead:
    from app.artifacts import service as artifacts

    async with session.begin_nested():
        await repository.lock_project(session, project_id)
        row = await get_edge(session, project_id, edge_id)
        if row.state == "superseded":
            raise conflict("This edge is historical")
        upstream = await current(session, project_id, row.upstream_type, row.upstream_id)
        downstream = await current(session, project_id, row.downstream_type, row.downstream_id)
        if (
            upstream["revision_id"] != schema.expected_upstream_revision_ref
            or downstream["revision_id"] != schema.expected_downstream_revision_ref
        ):
            raise conflict("Review bases are outdated")
        if await freshness(session, project_id, str(upstream["artifact_id"])) != "VALID":
            raise invalid("Resolve upstream freshness before reviewing this dependency")
        requires_validator = schema.decision == "rebase" or row.invalidation_policy in (
            "compatibility_check",
            "timing_revalidate",
        )
        if requires_validator and not compatible(row.compatibility_validator, upstream, downstream):
            raise invalid("Compatibility validator did not pass")
        old_id = row.id
        # Capture a new downstream revision before replacing its dependency baseline.
        result = await artifacts.append_snapshot(
            session, row.downstream_id, str(downstream["revision_id"]), preserve_approval=True
        )
        candidates = await repository.edges(session, project_id)
        rebased = next(edge for edge in candidates if edge.supersedes_id == old_id)
        rebased.upstream_revision_ref = str(upstream["revision_id"])
        rebased.state = "rebased"
        rebased.stale_cause_ref = None
        await audit(
            session,
            project_id,
            rebased.id,
            "dependency_rebased",
            schema.actor,
            schema.rationale,
            {
                "previous_edge_id": old_id,
                "decision": schema.decision,
                "revision_id": result.current_revision.id,
            },
        )
        await session.flush()
        read = EdgeRead.model_validate(rebased)
    if commit:
        await session.commit()
    return read


async def create_legacy_dependency(
    session: AsyncSession,
    *,
    project_id: str,
    source_artifact_id: str,
    block_id: str,
    revision_id: str,
    dependent_artifact_id: str,
    dependency_type: str,
    commit: bool,
) -> dict[str, object]:
    dependent = await current(session, project_id, "artifact", dependent_artifact_id)
    edge = await create_edge(
        session,
        project_id,
        EdgeCreate(
            upstream=Reference(type="artifact_block", id=block_id, revision_ref=revision_id),
            downstream=Reference(
                type="artifact",
                id=dependent_artifact_id,
                revision_ref=str(dependent["revision_id"]),
            ),
        ),
        legacy_type=dependency_type,
        commit=commit,
    )
    return await get_legacy_dependency(session, edge.id)


async def get_legacy_dependency(session: AsyncSession, edge_id: str) -> dict[str, object]:
    row = await repository.edge(session, edge_id)
    if row is None or row.upstream_type != "artifact_block":
        raise NotFoundError("Dependency not found", edge_id, "Read a valid artifact dependency")
    owner = await current(session, row.project_id, row.upstream_type, row.upstream_id)
    return dict(
        id=row.id,
        project_id=row.project_id,
        source_artifact_id=owner["artifact_id"],
        source_block_id=row.upstream_id,
        source_revision_id=row.upstream_revision_ref,
        dependent_artifact_id=row.downstream_id,
        dependency_type=row.dependency_type,
        is_stale=row.state == "stale" or row.stale_cause_ref is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    await repository.delete_project(session, project_id)


async def list_edges(session: AsyncSession, project_id: str) -> list[EdgeRead]:
    await projects_service.ensure_exists(session, project_id)
    return [EdgeRead.model_validate(row) for row in await repository.edges(session, project_id)]


async def list_audits(session: AsyncSession, project_id: str) -> list[dict[str, object]]:
    from app.lineage.schemas import AuditRead

    await projects_service.ensure_exists(session, project_id)
    return [
        AuditRead.model_validate(row).model_dump()
        for row in await repository.audits(session, project_id)
    ]


async def create_proposal(
    session: AsyncSession, project_id: str, schema: ProposalCreate
) -> ProposalRead:
    from app.lineage import proposals

    return await proposals.create(session, project_id, schema)


async def decide_proposal(
    session: AsyncSession, project_id: str, proposal_id: str, schema: ProposalDecision
) -> ProposalRead:
    from app.lineage import proposals

    return await proposals.decide(session, project_id, proposal_id, schema)


async def list_proposals(session: AsyncSession, project_id: str) -> list[ProposalRead]:
    await projects_service.ensure_exists(session, project_id)
    return [
        ProposalRead.model_validate(row) for row in await repository.proposals(session, project_id)
    ]
