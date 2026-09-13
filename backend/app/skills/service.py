"""Atomic Skill validation, audit, impact, and confirmed commit pipeline."""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import service as artifacts_service
from app.core.exceptions import ConflictError, ValidationError
from app.production import service as production_service
from app.projects import service as projects_service
from app.skills import repository
from app.skills.models import SkillCandidate, _utcnow
from app.skills.registry import SkillContract, registry
from app.skills.schemas import CandidateRead, SkillExecute, SkillRead, generate_id
from app.workflow import service as workflow_service


def _invalid(problem: str, cause: str, fix: str) -> ValidationError:
    return ValidationError(problem=problem, cause=cause, fix=fix)


def _validate_schema(value: dict[str, object], schema: dict[str, object], label: str) -> None:
    raw_required = schema.get("required", [])
    if not isinstance(raw_required, list):
        raise _invalid(f"{label} schema 无效", "required 不是 array", "修正 skill schema")
    required = {str(item) for item in raw_required}
    missing = sorted(required - value.keys())
    if missing:
        raise _invalid(
            f"{label} schema 校验失败", f"缺少字段 {missing}", "按 skill schema 补齐字段"
        )
    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        python_types: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "object": dict,
            "array": list,
            "number": (int, float),
            "boolean": bool,
        }
        for key, spec in properties.items():
            if key not in value or not isinstance(spec, dict) or "type" not in spec:
                continue
            expected = python_types.get(str(spec["type"]))
            if expected is not None and not isinstance(value[key], expected):
                raise _invalid(
                    f"{label} schema 校验失败", f"字段 '{key}' 类型不符", "按 skill schema 修正类型"
                )


def _validate_contract(contract: SkillContract, payload: SkillExecute) -> None:
    if payload.scope_type != contract.scope:
        raise _invalid(
            "skill scope 不匹配",
            f"{contract.id} requires {contract.scope}",
            "使用 manifest 声明的 scope_type",
        )
    missing = sorted(set(contract.required_context) - payload.context.keys())
    if missing:
        raise _invalid(
            "skill context 不完整",
            f"缺少 required context {missing}",
            "仅补齐 manifest 声明的 required context",
        )
    denied = sorted(set(contract.denied_context) & payload.context.keys())
    if denied:
        raise _invalid(
            "context permission 拒绝",
            f"包含禁止来源 {denied}",
            "移除当前 perspective 不可见的 context",
        )
    _validate_schema(payload.input, contract.input_schema, "input")
    _validate_schema(payload.candidate, contract.output_schema, "output")
    if "facts_preserved" in contract.validators:
        before = payload.input.get("facts")
        after = payload.candidate.get("facts")
        if before is not None and before != after:
            raise _invalid(
                "screenplay facts 被改变",
                "candidate facts 与 input facts 不一致",
                "保留事实或使用显式 story revision",
            )
    if "protected_spans_unchanged" in contract.validators:
        before = payload.input.get("protected_spans")
        after = payload.candidate.get("protected_spans")
        if before is not None and before != after:
            raise _invalid(
                "protected spans 被改变", "candidate 修改了锁定片段", "恢复所有 protected spans"
            )


def _read(row: SkillCandidate) -> CandidateRead:
    return CandidateRead(
        id=row.id,
        project_id=row.project_id,
        run_id=row.run_id,
        skill_id=row.skill_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        candidate=row.candidate_json,
        impact=row.impact_json,
        status=row.status,
        committed_ref=row.committed_ref,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def list_skills() -> list[SkillRead]:
    return [
        SkillRead(
            id=item.id,
            scope=item.scope,
            required_context=list(item.required_context),
            optional_context=list(item.optional_context),
            writes=list(item.writes),
            forbidden=list(item.forbidden),
            validators=list(item.validators),
        )
        for item in registry.list()
    ]


async def execute(session: AsyncSession, skill_id: str, payload: SkillExecute) -> CandidateRead:
    await projects_service.ensure_exists(session, payload.project_id)
    contract = registry.get(skill_id)
    _validate_contract(contract, payload)
    if payload.gate_id is not None:
        evaluation = await workflow_service.evaluate_gate_for_project(
            session, payload.project_id, payload.gate_id, payload.gate_facts
        )
        if not evaluation.passed:
            raise _invalid(
                "workflow gate blocked",
                f"unmet={evaluation.model_dump()['unmet']}",
                "满足全部 prerequisite 后重试",
            )
    if contract.commit_action == "edit_block":
        artifact = await artifacts_service.get(session, str(payload.candidate["artifact_id"]))
        if artifact.project_id != payload.project_id:
            raise _invalid(
                "candidate target 跨项目", "artifact ownership 不一致", "选择同项目 block"
            )
    run = await workflow_service.start_run(
        session,
        project_id=payload.project_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        skill_id=skill_id,
        input_data=payload.input,
    )
    impact = {
        "writes": list(contract.writes),
        "forbidden": list(contract.forbidden),
        "scope": {"type": payload.scope_type, "id": payload.scope_id},
        "requires_confirmation": contract.commit_action != "none",
    }
    await workflow_service.complete_run(
        session,
        run.id,
        output={"candidate": payload.candidate, "impact": impact},
        steps=[
            {"kind": "context", "detail": {"loaded": sorted(payload.context)}},
            {
                "kind": "validation",
                "detail": {"validators": list(contract.validators), "passed": True},
            },
            {"kind": "candidate", "detail": {"commit_action": contract.commit_action}},
        ],
    )
    row = SkillCandidate(
        id=generate_id(),
        project_id=payload.project_id,
        run_id=run.id,
        skill_id=skill_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        candidate_json=payload.candidate,
        impact_json=impact,
        commit_action=contract.commit_action,
        status="pending",
        committed_ref=None,
        created_at=_utcnow(),
        decided_at=None,
    )
    await repository.add(session, row)
    await session.commit()
    return _read(row)


async def decide(
    session: AsyncSession, candidate_id: str, project_id: str, *, accept: bool
) -> CandidateRead:
    row = await repository.get(session, candidate_id)
    if row is None or row.project_id != project_id:
        raise _invalid(
            "candidate 不存在或不属于项目",
            "id/ownership 不匹配",
            "使用 execute 返回的同项目 candidate id",
        )
    if row.status != "pending":
        raise ConflictError(
            problem="candidate 已决定",
            cause=f"status={row.status}",
            fix="不要重复 accept/reject；创建新 execution",
        )
    committed_ref: str | None = None
    if accept and row.commit_action == "edit_block":
        value = row.candidate_json
        artifact = await artifacts_service.edit_structured_block(
            session,
            project_id=project_id,
            artifact_id=str(value["artifact_id"]),
            block_id=str(value["block_id"]),
            content=str(value["content"]),
            semantic=(
                cast(dict[str, object], value.get("semantic"))
                if isinstance(value.get("semantic"), dict)
                else None
            ),
        )
        committed_ref = artifact.current_revision.id
    elif accept and row.commit_action == "create_production_document":
        raw_document = row.candidate_json.get("production_document")
        if not isinstance(raw_document, dict):
            raise _invalid(
                "production candidate 无效",
                "production_document 不是 object",
                "按 output schema 提供 production_document",
            )
        document = await production_service.create_from_payload(
            session, project_id, cast(dict[str, object], raw_document)
        )
        committed_ref = document.id
    row.status = "accepted" if accept else "rejected"
    row.committed_ref = committed_ref
    row.decided_at = _utcnow()
    await session.commit()
    return _read(row)


async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    await repository.delete_project(session, project_id)
