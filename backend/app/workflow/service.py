"""Workflow Core public application boundary."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.projects import service as projects_service
from app.workflow import repository
from app.workflow.models import (
    Episode,
    ExecutionRun,
    ExecutionStep,
    RequirementSpec,
    ScenePlan,
    WorkflowGate,
    WorkflowSeries,
    _utcnow,
)
from app.workflow.schemas import (
    EpisodeCreate,
    EpisodeRead,
    GateCreate,
    GateEvaluate,
    GateEvaluationRead,
    GateRequirement,
    MockExecute,
    RequirementCreate,
    RequirementRead,
    RunCreate,
    RunRead,
    ScenePlanCreate,
    ScenePlanRead,
    SeriesCreate,
    SeriesRead,
    StepRead,
    generate_id,
)


def _missing(kind: str, row_id: str) -> NotFoundError:
    return NotFoundError(
        problem=f"{kind} 不存在",
        cause=f"id '{row_id}' 未在工作流中找到",
        fix="先读取同项目的工作流资源并使用返回的 id",
        detail={"id": row_id, "kind": kind},
    )


def _wrong_project(kind: str, row_id: str) -> ValidationError:
    return ValidationError(
        problem=f"{kind} 不属于请求项目",
        cause=f"id '{row_id}' 的 project_id 与载荷不一致",
        fix="只引用同一项目内的工作流资源",
        detail={"id": row_id, "kind": kind},
    )


async def _owned(session: AsyncSession, model: type, row_id: str, project_id: str, kind: str):  # type: ignore[no-untyped-def]
    row = await repository.get(session, model, row_id)
    if row is None:
        raise _missing(kind, row_id)
    if row.project_id != project_id:
        raise _wrong_project(kind, row_id)
    return row


async def create_requirement(session: AsyncSession, schema: RequirementCreate) -> RequirementRead:
    await projects_service.ensure_exists(session, schema.project_id)
    row = RequirementSpec(
        id=generate_id("req"),
        project_id=schema.project_id,
        version=await repository.next_requirement_version(session, schema.project_id),
        content_json=schema.content,
        created_at=_utcnow(),
    )
    await repository.add(session, row)
    await session.commit()
    return RequirementRead(
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        content=row.content_json,
        created_at=row.created_at,
    )


async def get_current_requirement(session: AsyncSession, project_id: str) -> RequirementRead:
    await projects_service.ensure_exists(session, project_id)
    row = await repository.current_requirement(session, project_id)
    if row is None:
        raise _missing("requirement", project_id)
    return RequirementRead(
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        content=row.content_json,
        created_at=row.created_at,
    )


async def create_series(session: AsyncSession, schema: SeriesCreate) -> SeriesRead:
    await projects_service.ensure_exists(session, schema.project_id)
    row = WorkflowSeries(
        id=generate_id("ser"),
        project_id=schema.project_id,
        title=schema.title,
        created_at=_utcnow(),
    )
    await repository.add(session, row)
    await session.commit()
    return SeriesRead.model_validate(row)


async def create_episode(session: AsyncSession, schema: EpisodeCreate) -> EpisodeRead:
    await projects_service.ensure_exists(session, schema.project_id)
    await _owned(session, WorkflowSeries, schema.series_id, schema.project_id, "series")
    row = Episode(
        id=generate_id("ep"),
        project_id=schema.project_id,
        series_id=schema.series_id,
        position=schema.position,
        title=schema.title,
        outline=schema.outline,
        status="draft",
        created_at=_utcnow(),
    )
    try:
        await repository.add(session, row)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            problem="episode 顺序冲突",
            cause="同一 series 已存在该 position",
            fix="选择未使用的非负 position",
        ) from exc
    return EpisodeRead.model_validate(row)


def _scene_read(row: ScenePlan) -> ScenePlanRead:
    return ScenePlanRead(
        id=row.id,
        project_id=row.project_id,
        episode_id=row.episode_id,
        position=row.position,
        location_ref=row.location_ref,
        time_context=row.time_context,
        characters=row.characters_json,
        scene_goal=row.scene_goal,
        character_goal=row.character_goal,
        conflict=row.conflict,
        turn=row.turn,
        reveal=row.reveal,
        exit_change=row.exit_change,
        target_duration=row.target_duration,
        required_setup=row.required_setup_json,
        required_payoff=row.required_payoff_json,
        created_at=row.created_at,
    )


async def create_scene_plan(session: AsyncSession, schema: ScenePlanCreate) -> ScenePlanRead:
    await projects_service.ensure_exists(session, schema.project_id)
    await _owned(session, Episode, schema.episode_id, schema.project_id, "episode")
    row = ScenePlan(
        id=generate_id("scn"),
        project_id=schema.project_id,
        episode_id=schema.episode_id,
        position=schema.position,
        location_ref=schema.location_ref,
        time_context=schema.time_context,
        characters_json=schema.characters,
        scene_goal=schema.scene_goal,
        character_goal=schema.character_goal,
        conflict=schema.conflict,
        turn=schema.turn,
        reveal=schema.reveal,
        exit_change=schema.exit_change,
        target_duration=schema.target_duration,
        required_setup_json=schema.required_setup,
        required_payoff_json=schema.required_payoff,
        created_at=_utcnow(),
    )
    try:
        await repository.add(session, row)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            problem="scene plan 顺序冲突",
            cause="同一 episode 已存在该 position",
            fix="选择未使用的非负 position",
        ) from exc
    return _scene_read(row)


async def create_gate(session: AsyncSession, schema: GateCreate) -> str:
    await projects_service.ensure_exists(session, schema.project_id)
    await _validate_scope(session, schema.project_id, schema.scope_type, schema.scope_id)
    row = WorkflowGate(
        id=generate_id("gate"),
        project_id=schema.project_id,
        scope_type=schema.scope_type,
        scope_id=schema.scope_id,
        stage=schema.stage,
        requirements_json=[item.model_dump() for item in schema.requirements],
        created_at=_utcnow(),
    )
    await repository.add(session, row)
    await session.commit()
    return row.id


async def _validate_scope(
    session: AsyncSession, project_id: str, scope_type: str, scope_id: str
) -> None:
    models = {"series": WorkflowSeries, "episode": Episode, "scene": ScenePlan}
    if scope_type == "project":
        if scope_id != project_id:
            raise _wrong_project("project scope", scope_id)
        return
    model = models.get(scope_type)
    if model is not None:
        await _owned(session, model, scope_id, project_id, scope_type)


async def evaluate_gate(
    session: AsyncSession, gate_id: str, schema: GateEvaluate
) -> GateEvaluationRead:
    gate = await repository.get(session, WorkflowGate, gate_id)
    if gate is None:
        raise _missing("gate", gate_id)
    unmet = [
        GateRequirement.model_validate(item)
        for item in gate.requirements_json
        if schema.facts.get(str(item["key"])) != item.get("expected", True)
    ]
    return GateEvaluationRead(gate_id=gate.id, passed=not unmet, unmet=unmet)


def _run_read(row: ExecutionRun, steps: list[ExecutionStep]) -> RunRead:
    return RunRead(
        id=row.id,
        project_id=row.project_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        skill_id=row.skill_id,
        status=row.status,
        input=row.input_json,
        output=row.output_json,
        steps=[
            StepRead(
                id=s.id,
                position=s.position,
                kind=s.kind,
                detail=s.detail_json,
                created_at=s.created_at,
            )
            for s in steps
        ],
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def create_run(session: AsyncSession, schema: RunCreate) -> RunRead:
    await projects_service.ensure_exists(session, schema.project_id)
    await _validate_scope(session, schema.project_id, schema.scope_type, schema.scope_id)
    row = ExecutionRun(
        id=generate_id("run"),
        project_id=schema.project_id,
        scope_type=schema.scope_type,
        scope_id=schema.scope_id,
        skill_id=schema.skill_id,
        status="pending",
        input_json=schema.input,
        output_json=None,
        created_at=_utcnow(),
        completed_at=None,
    )
    await repository.add(session, row)
    await session.commit()
    return _run_read(row, [])


async def mock_execute(session: AsyncSession, run_id: str, schema: MockExecute) -> RunRead:
    row = await repository.get(session, ExecutionRun, run_id)
    if row is None:
        raise _missing("execution run", run_id)
    if row.status != "pending":
        raise ValidationError(
            problem="execution run 已结束",
            cause="mock execute 只能执行 pending run",
            fix="创建新的 execution run",
        )
    for position, item in enumerate(schema.steps):
        await repository.add(
            session,
            ExecutionStep(
                id=generate_id("step"),
                run_id=row.id,
                position=position,
                kind=item.kind,
                detail_json=item.detail,
                created_at=_utcnow(),
            ),
        )
    row.status = "completed"
    row.output_json = schema.output
    row.completed_at = _utcnow()
    await session.commit()
    return _run_read(row, await repository.steps_for_run(session, row.id))


async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    await repository.delete_project(session, project_id)


async def ensure_episode_owned(session: AsyncSession, project_id: str, episode_id: str) -> None:
    await _owned(session, Episode, episode_id, project_id, "episode")


async def ensure_scene_owned(
    session: AsyncSession, project_id: str, episode_id: str, scene_id: str
) -> None:
    scene = await _owned(session, ScenePlan, scene_id, project_id, "scene")
    if scene.episode_id != episode_id:
        raise ValidationError(
            problem="scene 不属于请求 episode",
            cause=f"scene '{scene_id}' 的 episode_id 与 '{episode_id}' 不一致",
            fix="使用同一 episode 内的 scene plan",
        )


async def start_run(
    session: AsyncSession,
    *,
    project_id: str,
    scope_type: str,
    scope_id: str,
    skill_id: str,
    input_data: dict[str, object],
) -> RunRead:
    """Cross-domain run creation without exposing Workflow internal schemas."""
    return await create_run(
        session,
        RunCreate.model_validate(
            {
                "project_id": project_id,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "skill_id": skill_id,
                "input": input_data,
            }
        ),
    )


async def complete_run(
    session: AsyncSession,
    run_id: str,
    *,
    output: dict[str, object],
    steps: list[dict[str, object]],
) -> RunRead:
    """Finish a validated external executor run and retain ordered audit steps."""
    return await mock_execute(
        session,
        run_id,
        MockExecute.model_validate({"output": output, "steps": steps}),
    )


async def evaluate_gate_for_project(
    session: AsyncSession,
    project_id: str,
    gate_id: str,
    facts: dict[str, object],
) -> GateEvaluationRead:
    gate = await repository.get(session, WorkflowGate, gate_id)
    if gate is None:
        raise _missing("gate", gate_id)
    if gate.project_id != project_id:
        raise _wrong_project("gate", gate_id)
    return await evaluate_gate(session, gate_id, GateEvaluate(facts=facts))
