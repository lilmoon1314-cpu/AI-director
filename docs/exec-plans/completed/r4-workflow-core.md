# R4 Workflow Core

## Purpose and scope

Build the smallest complete Workflow Core on the completed R0-R3 baseline. R4 introduces project
requirement specifications, series-owned episodes, ordered scene plans, deterministic workflow gates,
and auditable execution runs/steps. It proves that a project can express its creative requirement,
organize an episode into pre-screenplay scene plans, evaluate explicit prerequisites outside prompts,
and record mock-skill execution without granting an Agent authority to advance the workflow.

R4 preserves the existing project, Artifact Core, and Narrative State contracts. It does not add the
production-document artifact sequence, real Atomic Skill packages/execution, provider generation,
frontend production workspace, or any R5/R6 behavior. The user has explicitly authorized the finite
R4-R6 initiative, so after R4 acceptance this plan will be archived and execution may continue through
the separately owned R5 and R6 child plans in master-plan order.

## Invariants

- Every workflow row is project-owned; series, episode, scene, gate, and run references accepted by the
  public service resolve within that same project.
- A project has at most one current requirement specification, while every accepted update retains an
  immutable version record rather than overwriting history.
- Episodes are ordered within a series and scene plans are ordered within an episode with deterministic,
  collision-free positions.
- Gate definitions and evaluation are deterministic code/data. A blocked gate reports every unmet
  prerequisite; prompts and mock skills cannot bypass or mutate gate truth.
- An execution run has an explicit requested scope, skill identifier, status transition, input/output,
  and ordered execution steps. R4 mock execution may produce output but may not write canonical domain
  or artifact state or automatically advance another stage.
- Project deletion removes all Workflow Core-owned rows through the existing projects-router composition
  boundary. Database migration is additive and preserves a populated R3 database.

## Progress

- [x] 2026-09-12 15:53–15:53 (+08:00) Preflight and baseline: confirmed R0-R3 completed, R4-R6 explicitly
  authorized, no active plan, clean worktree, and the R4/R5 boundary in the master owner.
- [x] 2026-09-12 15:53–15:58 (+08:00) Slice A: defined the Workflow Core durable contract, ORM schema,
  additive migration, model registration, project lifecycle, and populated-R3 upgrade proof.
- [x] 2026-09-12 15:55–16:00 (+08:00) Slice B: implemented requirement specification versioning plus ordered series/episode/scene-plan
  application operations and project-isolated REST contracts.
- [x] 2026-09-12 15:56–16:00 (+08:00) Slice C: implemented deterministic gate definitions/evaluation and explicit prerequisite reporting.
- [x] 2026-09-12 15:56–16:00 (+08:00) Slice D: implemented execution runs/steps and a bounded mock-skill executor that cannot write canonical
  state or advance workflow.
- [x] 2026-09-12 15:59–16:05 (+08:00) Slice E: added cross-layer acceptance, architecture enforcement, durable design/product owners, and
  one machine-readable R4 feature; run declared validation and reconcile the stage boundary.

## Surprises / Discoveries

- R3 deliberately stores series/episode/scene identifiers as optional opaque timepoint references; R4 is
  the first owner that may validate and create those hierarchy records without changing R3 history.
- `feature_list.json` has no Workflow Core entry after F18, so R4 will add one pending feature and change
  only that feature through the Harness verification command after its behavior passes.

## Decision Log

- Use a dedicated `app.workflow` bounded context and public service boundary. Requirement, hierarchy,
  gate, and run ownership remain together for this minimal stage; later evidence may justify narrower
  modules, but R4 will not pre-create empty target-state directories.
- Model the series container in Workflow Core because R4 owns Episode and existing F16 is not accepted;
  expose only the minimum series identity/order needed by episodes rather than absorbing the broader
  multi-series filtering feature.

## Validation and acceptance

- Focused service/API tests prove requirement version history, hierarchy ordering and isolation, complete
  scene-plan fields, deterministic gate pass/block results, run/step audit transitions, and mock-skill
  non-mutation.
- Migration acceptance upgrades a populated R3 database without changing prior rows and reaches one head
  on populated and fresh databases; Alembic schema drift is absent.
- Architecture checks prove model/route registration, project cleanup, and Workflow Core internal privacy.
- Targeted Ruff/format, mypy, import-linter, generated OpenAPI/frontend typecheck, and `git diff --check`
  pass for the participating boundaries.
- Add one R4 feature entry and run `python scripts/task.py verify <id>` only after the recorded commands pass.
  Do not rerun R0-R3 acceptance or mutation.

## Outcomes / Retrospective

R4 is complete. Workflow Core now owns versioned project requirements, the minimum workflow
series/episode/scene-plan hierarchy, deterministic explicit-fact gates, and auditable mock execution
runs/steps. Mock execution persists only a candidate and trace and cannot advance a stage or change
canonical state.

Acceptance evidence: 4 focused API/migration tests and 13 architecture tests pass; fresh and populated
R3 upgrades reach the single `d8410ca2e6b7` head and Alembic reports no drift; touched Ruff/format,
`mypy app/workflow`, all 12 import-linter contracts, regenerated OpenAPI types, frontend TypeScript, and
`git diff --check` pass. `python scripts/task.py verify F19` changed only F19 to `passing`.

## Recovery / restart point

R4 requires no follow-up. The user authorized continuation, so the next bounded owner is a new R5
Production Documents ExecPlan. No database operation or other unsafe action is in progress.
