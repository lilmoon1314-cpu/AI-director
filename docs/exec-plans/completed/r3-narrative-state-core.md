# R3 Narrative State Core

## Purpose and scope

Build the smallest complete Narrative State domain on the completed R0-R2 baseline. R3 introduces
narrative timepoints, append-only state events with a materialized current projection, immutable state
snapshots, author claims, and temporal character/audience knowledge states. It proves that the system
can answer what is true now, when and why it changed, which artifact revision caused it, and what a
specific knower knows at a point in the narrative.

The first migration slice covers only the high-value relationship attributes `trust` and `resentment`.
Existing relationship columns and data remain available for compatibility; the R3 migration seeds a
project baseline timepoint plus traceable state event/current rows for populated values. R3 does not
migrate every entity property or relationship field, remove legacy visibility booleans, add workflow,
Episode/Scene/Gate models, regenerate artifacts, or enter R4.

## Invariants

- Every row is project-owned, and references accepted by the public service stay within one project.
- A narrative timepoint has a deterministic project-local sequence coordinate. R3 treats series,
  episode, scene, and beat IDs as optional opaque future references; it does not create R4 owners.
- State events are immutable and append-only. Corrections are new compensation events, never updates or
  deletes of historical events.
- The reducer atomically appends an event and advances exactly one materialized current row with an
  incrementing version and the event/timepoint that produced it.
- Artifact provenance, when supplied, names an existing same-project screenplay artifact and one of its
  revisions. A screenplay cause requires that complete provenance pair.
- A snapshot captures all current state in one declared scope at an event cursor and is never mutated.
- Claims hold author truth. Knowledge-state history holds character or audience belief separately;
  audience rows have no knower ID, character rows require one, and a newer row supersedes the prior
  current row for the same knower/claim.
- Project deletion removes all Narrative State-owned rows through the existing projects-router
  composition boundary.

## Progress

- [x] 2026-09-12 13:11–13:18 (+08:00) Preflight and baseline: confirmed R0-R2 completed, R3 not
  started, one active-plan slot available, current dirty work preserved, and R3/R4 boundary located.
- [x] 2026-09-12 13:18–13:24 (+08:00) Slice A: defined the Narrative State domain contract, ORM
  schema, additive migration, project lifecycle, and populated `trust`/`resentment` baseline upgrade.
- [x] 2026-09-12 13:18–13:27 (+08:00) Slice B: implemented ordered timepoints and append-only
  event/current reducer operations with validated artifact/revision provenance.
- [x] 2026-09-12 13:21–13:27 (+08:00) Slice C: implemented immutable scoped snapshots and latest
  event-cursor reads.
- [x] 2026-09-12 13:21–13:27 (+08:00) Slice D: implemented claims and temporal character/audience
  knowledge-state history.
- [x] 2026-09-12 13:23–13:29 (+08:00) Slice E: exposed the bounded REST contract and proved the
  cross-layer continuity scenario.
- [x] 2026-09-12 13:25–13:29 (+08:00) Updated durable architecture/product owners and registered the
  pending R3 acceptance feature F18.
- [x] 2026-09-12 13:29–13:38 (+08:00) Ran the declared R3 validation, closed compatibility projection
  divergence, archived this plan, marked only R3 completed in the master owner, and stopped before R4.

## Surprises / Discoveries

- The repository has no Narrative State owner or acceptance feature yet. `entities.properties` mixes
  canonical and changing values, while `relationships` stores several dynamic values as columns.
- R4 owns Series/Episode/Scene creation, so R3 timepoint hierarchy fields must remain optional opaque
  references rather than importing future workflow models.
- R2 established explicit Alembic model registration and safe populated-upgrade testing. R3 must extend
  both; autogeneration may not be trusted without reviewing destructive noise.
- The worktree already contains unrelated Harness consolidation changes, including the master stage
  table that establishes the completed R0-R2 baseline. R3 edits must be additive and preserve them.
- Frontend dependency verification initially attempted a non-interactive modules purge and then hit
  sandboxed registry access. Re-running the frozen-lockfile install with explicit approval reused the
  local store, restored `node_modules`, generated types, and passed TypeScript checking.
- Initial migration-only handling of trust/resentment would have allowed later relation-API writes to
  diverge from event-backed current state. R3 now keeps both legacy columns as synchronized projections:
  relation writes append events, while temporal events update the columns in the same transaction.

## Decision Log

- Create `app.narrative_state` as one bounded context with public service and REST boundaries; do not
  place temporal truth back into entities, relations, perspectives, or artifacts.
- Use JSON values for state and claim objects, with deterministic reducer semantics for `set`, `add`,
  `remove`, and `transition`. Attribute-specific schema registries remain future bounded work.
- Migrate only populated `relationships.trust` and `relationships.resentment` values. Preserve the
  legacy columns as synchronized compatibility projections instead of destructively removing them.
- Represent backfilled facts at one generated project-local baseline timepoint (`sequence_no = 0`) with
  `cause_type = migration` and `cause_ref = r3_relationship_state_baseline`.

## Validation and acceptance

- Focused service tests prove timepoint ordering/project isolation, all reducer operations, monotonic
  current versions, append-only event history, compensation, and invalid/cross-project provenance.
- Focused integration/E2E tests prove event -> current -> snapshot continuity and claim -> divergent
  character/audience knowledge without leaking author truth.
- Migration acceptance upgrades a populated R2 database, preserves every pre-R3 row, backfills only
  populated trust/resentment values, and reaches a single R3 head on both populated and fresh databases.
- Architecture checks prove six R3 tables, model registration, project cleanup, route registration, and
  module privacy; targeted Ruff, format, mypy, import-linter, generated OpenAPI/frontend typecheck, and
  `git diff --check` pass.
- Add one R3 feature entry and run `python scripts/task.py verify <id>` only after its recorded behavior
  passes. Do not run R0-R2 acceptance, mutation, or unrelated full-suite rituals.

## Outcomes / Retrospective

R3 is complete. Six project-owned Narrative State tables now provide ordered timepoints, immutable
state-event history, a versioned current projection, immutable continuity snapshots, author claims,
and superseding character/audience knowledge history. Screenplay-caused state changes retain validated
artifact/revision provenance. Populated R2 upgrades preserve all prior rows and seed only non-null
relationship trust/resentment values at an explicit migration baseline; legacy columns remain intact.

Acceptance evidence:

- `python scripts/task.py verify F18`: 8 API/migration/E2E tests and 12 architecture tests pass; F18 is
  `passing`.
- Fresh and populated Alembic upgrades reach the single `7c91e2ab4f30` head; `alembic check` reports no
  schema drift.
- R3-touched Ruff and format checks pass, `mypy app/narrative_state` reports no issues, and all 10
  import-linter contracts are kept.
- Generated frontend OpenAPI types include the Narrative State routes; `pnpm run typecheck` passes.
- Additional relation unit, project lifecycle, R2 Artifact API, and Harness regression selection: 41
  tests pass.
- `git diff --check` passes; only ordinary Windows CRLF conversion notices remain.

R3 retains the legacy trust/resentment columns as compatibility projections. Writes through either the
legacy relation API or Narrative State remain synchronized and event-backed; retiring those projections
later requires its own data-preserving migration.

## Recovery / restart point

No follow-up operation is required for R3. The next boundary is R4, which remains not started and
requires a separate explicit user request and stage-local ExecPlan.
