# Harness consolidation pass

## Purpose and scope

Consolidate durable repository working agreements so future V3 stages can start from the repository
Harness without repeating execution rules in the user prompt. This is an independent Harness-only
pass: R0, R1, and R2 remain completed baselines; business source, product behavior, feature acceptance
state, and R3 implementation are out of scope.

## Progress

- [x] Read the root Agent map and current ExecPlan protocol.
- [x] Inventory the existing Harness owners, V3 stage plan, completed child plans, feature state, and
  deterministic Harness checks.
- [x] 2026-09-12 12:19–12:20 (+08:00) Consolidate repository-wide working agreements in `AGENTS.md` without duplicating task, design,
  product, or acceptance truth.
- [x] Complete the lifecycle protocol in `docs/PLANS.md`, including truthful milestone timestamps and
  restartability. This milestone began before the protocol took effect, so no start time was backfilled.
- [x] 2026-09-12 12:20–12:20 (+08:00) Clarify the existing V3 master plan as the sole owner of the finite R0-R6 stage sequence and link
  completed child plans without adding another initiative taxonomy.
- [x] 2026-09-12 12:20–12:20 (+08:00) Adjust only high-value deterministic Harness checks needed to preserve the revised constitution.
- [x] 2026-09-12 12:20–12:23 (+08:00) Run the bounded Harness and architecture validation, record outcomes, archive this plan, and stop
  before R3.

## Discoveries

- `CODEX_REFACTOR_MASTER_PLAN_V3.md` already defines the finite R0-R6 sequence and is the only suitable
  initiative owner; no second roadmap or initiative artifact is needed.
- `AGENTS.md` already owns scope, user-data safety, proportional validation, complex-work routing, and
  progressive knowledge routes, but it lacks the durable context/turn discipline and explicit
  destructive/unrelated-change rules repeatedly supplied in stage prompts.
- `docs/PLANS.md` correctly limits itself to task-local state but does not yet specify coherent
  milestones, truthful progress, discovery/decision/validation/outcome sections, timestamp semantics,
  reliable restart points, or a clear archival lifecycle.
- The current architecture test enforces a 5000-byte limit. A small bounded guard remains valuable,
  but the present threshold may prevent concise high-value working agreements from being always-on.
- The first architecture runs exposed one R2-era ownership regression: the Artifact module retained
  current nested `ARCHITECTURE.md` and `CONSTRAINTS.md` pages that duplicated the root map and Artifact
  design/product owners. Both were reduced to direct compatibility routes like the other retired module
  pages.

## Decisions

- Extend the existing owners instead of creating `ROADMAP.md`, an initiatives directory, telemetry
  files, a second registry, or a semantic policy checker.
- Keep context/token principles in `AGENTS.md`; keep only ExecPlan-specific context recovery and
  timestamp rules in `docs/PLANS.md`.
- Preserve the existing V3 plan's detailed architecture material and add only bounded stage ownership,
  status, prerequisite/boundary, and child-plan routing where it is missing.
- Do not edit design docs, product specs, or `feature_list.json`: this pass changes no durable
  architecture truth, observable behavior, or acceptance state.
- Raise the deterministic `AGENTS.md` size guard from 5000 to 7000 bytes. The final constitution is 5944
  bytes and 99 lines; the old limit rejected the new high-value agreements, while the new bound still
  prevents task history, design detail, or product prose from accumulating silently.

## Validation and acceptance

- Run `backend/tests/architecture/test_harness.py` and all architecture tests.
- Run Ruff only for directly modified Python Harness tests, if any.
- Run `git diff --check`.
- Do not run mutation, benchmark, the full repository suite, R1/R2 acceptance, or unrelated frontend
  validation.

Acceptance requires one durable owner for each repeated rule class, no unnecessary Harness artifact,
no business-source change, passing targeted validation, and a future R3 launch prompt of three to five
intent-only lines.

Completed evidence:

- `uv run pytest tests/architecture -q` with a workspace-local uv cache: 15 passed. The first two runs
  found the R2 nested Artifact ownership regression; after converting both pages to direct routes, the
  complete selection passed. Remaining messages were a third-party Starlette deprecation and a pytest
  cache write warning, neither caused by this diff.
- `uv run ruff check tests/architecture/test_harness.py`: passed.
- `uv run ruff format --check tests/architecture/test_harness.py`: passed.
- `git diff --check`: passed; only ordinary LF-to-CRLF checkout notices were emitted.
- Scope audit: only Harness Markdown and one Harness architecture test changed; no business source,
  design/product owner, feature state, migration, dependency, or generated artifact changed.

## Outcomes / Retrospective

- `AGENTS.md` now owns stable repository-wide working agreements for scope/change safety, context and
  turn efficiency, progressive disclosure, migration safety, proportional validation, feature-state
  ownership, complex-work routing, and explicit V3 stage stopping.
- `docs/PLANS.md` now owns the complete ExecPlan protocol, including self-contained recovery, coherent
  milestones, truthful state, discoveries, decisions, validation, outcomes, archival, and timestamp
  semantics without becoming a global policy manual.
- `CODEX_REFACTOR_MASTER_PLAN_V3.md` remains the sole V3 initiative owner and now exposes stage status,
  prerequisites, bounded in/out scope, next-stage boundaries, and child-plan links in one table.
- No new taxonomy, DSL, registry, roadmap, telemetry file, design owner, or product owner was added. The
  only new Harness artifact was this required task ExecPlan, now archived as a compact completion record.
- The architecture suite revealed that R2 had reintroduced current nested architecture/constraint pages.
  Retiring them validated the value of the existing simple ownership invariant without adding a semantic
  checker.

## Recovery / handoff

This pass is complete and has no follow-up operation. R0-R2 remain baselines. R3 was not started; begin
it only from a new explicit user request, the V3 stage table, and a new R3 ExecPlan.
