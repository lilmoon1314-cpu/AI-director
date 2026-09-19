"""Reverse change requests; decisions run in one transaction with owning-domain revisions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.lineage import repository, service
from app.lineage.models import ChangeProposal, now
from app.lineage.schemas import (
    EdgeReview,
    ProposalCreate,
    ProposalDecision,
    ProposalRead,
)


async def get(session: AsyncSession, project_id: str, proposal_id: str) -> ChangeProposal:
    row = await repository.proposal(session, proposal_id)
    if row is None or row.project_id != project_id:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Change proposal not found", proposal_id, "Use a same-project proposal")
    return row


async def create(session: AsyncSession, project_id: str, schema: ProposalCreate) -> ProposalRead:
    await repository.lock_project(session, project_id)
    await service.resolve(session, project_id, schema.origin)
    await service.resolve(session, project_id, schema.target)
    if schema.origin.type != "artifact" or schema.target.type != "artifact_block":
        raise service.invalid("Initial proposals support artifact origin → artifact_block target")
    origin = await service.current(session, project_id, schema.origin.type, schema.origin.id)
    target = await service.current(session, project_id, schema.target.type, schema.target.id)
    if (
        origin["revision_id"] != schema.origin.revision_ref
        or target["revision_id"] != schema.target.revision_ref
    ):
        raise service.conflict("Proposal must use current origin and target revisions")
    edges = await repository.edges(session, project_id)
    if not any(
        edge.state != "superseded"
        and edge.downstream_id == schema.origin.id
        and edge.upstream_type == schema.target.type
        and edge.upstream_id == schema.target.id
        for edge in edges
    ):
        raise service.invalid("Origin must have a direct dependency on the proposed target block")
    row = ChangeProposal(
        id=service.new_id("proposal"),
        project_id=project_id,
        origin_type=schema.origin.type,
        origin_id=schema.origin.id,
        origin_revision_ref=schema.origin.revision_ref,
        target_type=schema.target.type,
        target_id=schema.target.id,
        target_base_revision_ref=schema.target.revision_ref,
        proposal_kind="edit_block",
        patch_json={"content": schema.content, "semantic": schema.semantic},
        rationale=schema.rationale,
        evidence_json=schema.evidence,
        status="proposed",
        created_by=schema.actor,
    )
    await repository.add(session, row)
    await service.audit(
        session,
        project_id,
        row.id,
        "change_proposal_created",
        schema.actor,
        schema.rationale,
        {"origin_id": row.origin_id, "target_id": row.target_id},
    )
    await session.commit()
    return ProposalRead.model_validate(row)


async def decide(
    session: AsyncSession, project_id: str, proposal_id: str, schema: ProposalDecision
) -> ProposalRead:
    from app.artifacts import service as artifacts
    from app.production import service as production

    async with session.begin_nested():
        await repository.lock_project(session, project_id)
        row = await get(session, project_id, proposal_id)
        target_status = {"accept": "accepted", "reject": "rejected", "supersede": "superseded"}[
            schema.decision
        ]
        if row.status != "proposed":
            if row.status == target_status:
                return ProposalRead.model_validate(row)
            raise service.conflict("Proposal has already been decided")
        if not await repository.claim_proposal(session, row.id, target_status):
            raise service.conflict("Proposal was decided concurrently")
        if schema.decision == "accept":
            origin = await service.current(session, project_id, row.origin_type, row.origin_id)
            target = await service.current(session, project_id, row.target_type, row.target_id)
            if (
                origin["revision_id"] != row.origin_revision_ref
                or target["revision_id"] != row.target_base_revision_ref
            ):
                raise service.conflict("Origin or target advanced since proposal creation")
            await production.validate_artifact_edit(
                session, str(target["artifact_id"]), row.target_id, row.patch_json
            )
            semantic = row.patch_json.get("semantic")
            if semantic is not None and not isinstance(semantic, dict):
                raise service.invalid("Stored semantic patch must be an object")
            result = await artifacts.edit_structured_block(
                session,
                project_id=project_id,
                artifact_id=str(target["artifact_id"]),
                block_id=row.target_id,
                content=str(row.patch_json["content"]),
                semantic=semantic,
                expected_revision_id=row.target_base_revision_ref,
                commit=False,
            )
            row.committed_ref = result.current_revision.id
            latest = await service.current(session, project_id, row.target_type, row.target_id)
            candidates = [
                edge
                for edge in await repository.edges(session, project_id)
                if edge.state != "superseded"
                and edge.downstream_id == row.origin_id
                and edge.upstream_type == row.target_type
                and edge.upstream_id == row.target_id
            ]
            for edge in candidates:
                can_rebase = service.compatible(edge.compatibility_validator, latest, origin)
                if (
                    can_rebase
                    and await service.freshness(session, project_id, str(target["artifact_id"]))
                    == "VALID"
                ):
                    await service.review_edge(
                        session,
                        project_id,
                        edge.id,
                        EdgeReview(
                            actor=schema.actor,
                            rationale=schema.rationale,
                            decision="rebase",
                            expected_upstream_revision_ref=result.current_revision.id,
                            expected_downstream_revision_ref=str(origin["revision_id"]),
                        ),
                        commit=False,
                    )
                else:
                    await service.audit(
                        session,
                        project_id,
                        edge.id,
                        "rebase_review_required",
                        schema.actor,
                        schema.rationale,
                        {"proposal_id": row.id, "compatibility_passed": can_rebase},
                    )
        row.status = target_status
        row.decided_at = now()
        await service.audit(
            session,
            project_id,
            row.id,
            f"change_proposal_{target_status}",
            schema.actor,
            schema.rationale,
            {"committed_ref": row.committed_ref},
        )
        await session.flush()
        result_read = ProposalRead.model_validate(row)
    await session.commit()
    return result_read
