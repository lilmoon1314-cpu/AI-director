# R2 Artifact Core

## Purpose and scope

Build the smallest complete Artifact domain that supports one real type, `screenplay`, and proves:

```text
segment-level edit -> immutable revision -> block-local diff -> localized stale
```

R0 Harness Refactor and R1 Agent Service Split are baselines. This plan does not reopen either stage,
does not integrate Agent tools, and does not enter R3 Narrative State or workflow/regeneration work.

## Invariants

- **Artifact identity:** an artifact has one stable ID for its lifetime. Editing content creates a new
  revision and never replaces the artifact with another row.
- **Block identity:** every screenplay block has a generated stable ID independent of text and order.
  The same block keeps that ID across revisions.
- **Revision immutability:** a revision and its block snapshots are append-only historical state.
  Creating a later revision never updates earlier revision content.
- **Diff locality:** comparing two revisions classifies blocks by stable ID and reports at least
  `unchanged` and `modified`; the edit path identifies changed block IDs rather than treating the
  screenplay as one string.
- **Dependency direction:** each dependency points from one source screenplay block/revision baseline
  to one dependent artifact: source change -> dependent may become stale.
- **Localized stale:** an edit invalidates only dependencies whose source block is in the real diff;
  dependencies on unchanged sibling blocks and their dependent artifacts remain fresh.
- **Ownership and lifecycle:** artifacts and both ends of a dependency belong to one existing project;
  project deletion removes Artifact-domain data through the existing projects-router composition
  boundary.

## Progress

- [x] Preflight: clean worktree, R1 archived, R2 diff is isolatable.
- [x] Minimal discovery: current specs/design, feature registry, ORM/migrations, domain layers, tests,
  project ownership/deletion, and similarly named concepts.
- [x] Slice A: Artifact + Block foundation and project lifecycle.
- [x] Slice B: immutable revision history and block edit.
- [x] Slice C: revision diff with block-local results.
- [x] Slice D: directed dependencies.
- [x] Slice E: edit -> diff -> localized stale integration proof.
- [x] Durable architecture/product documentation and import boundary.
- [x] R2-targeted validation and feature acceptance verification.
- [x] Archive this plan and stop before R3.

## Discoveries

- No current `app.artifacts` owner or Artifact API/schema exists.
- `feature_list.json` has no Artifact Core feature. F15 is Agent long-term memory and F16 is multi-series;
  neither is an acceptable proxy. R2 needs its own acceptance entry once behavior is implemented.
- Agent `memory_docs` have section-level CAS, but they own editable assistant memory and are not
  structured creative artifacts. R2 will not migrate or reuse them.
- Existing relationship `dependency` is a 0-1 character-relationship attribute, not a directed build
  dependency. Existing asset `stale` is lazy render-cache freshness, and Agent `stale` is a CAS
  conflict. None carry Artifact invalidation semantics.
- The master plan's bounded Artifact sections specify structured artifacts/blocks/revisions and
  directed stale propagation, but list many future artifact types. R2 deliberately admits only
  `screenplay`.
- Project deletion is composed in `projects.router`; domain business layers do not import sibling
  internals. Artifact cleanup must join that composition point through `artifacts.service`.
- Alembic metadata registration is explicit in `migrations/env.py`; a new models module must be added.
- Alembic's environment did not register the existing Agent models, so the first R2 autogenerate
  attempted to drop all five R1-baseline Agent tables. That unsafe generated file was removed before
  use; metadata registration now includes Agent and Artifact models so regeneration stays additive.
- Alembic also lacked a renderer for the runtime `UTCDateTime` decorator, producing a migration with
  an unresolved Python reference. The environment now renders it as portable `sa.DateTime` DDL; the
  invalid generated file was removed and not executed.
- `uv run alembic heads` initially hit a host uv-cache path collision. Validation will use a
  workspace-local `UV_CACHE_DIR`, without altering runtime configuration.
- Narrative timepoints, character knowledge/state, workflow gates, regeneration, and downstream
  scheduling belong to R3+ and remain intentionally absent.
- Repository-wide mypy still reports six pre-existing type errors in `app/agent/tools.py`; targeted
  Artifact mypy is clean. The R1 baseline errors were recorded and left untouched.

## Decisions

- Store an artifact-level revision plus immutable per-block snapshots for that revision. Snapshot
  duplication is acceptable at R2 scale and keeps reads/diffs explicit without event sourcing.
- Keep block identity in a durable `artifact_blocks` row; content and order live in immutable revision
  snapshots. A block ID is never derived from array position or content.
- R2 exposes creation/read, revision read, one-block edit, revision diff, and dependency creation/read.
  It does not implement block insertion/removal, branching, merging, undo, or collaboration history.
- A dependency records the source artifact, source block, source revision baseline, and dependent
  artifact. Invalidation marks both the matching dependency and dependent artifact stale so impact is
  queryable and product-visible; it does not regenerate anything.
- Dependencies are project-local and validated through the Artifact service boundary. Generalized
  cross-domain reference polymorphism is rejected as premature.
- Add one import-linter privacy contract for the new domain internals and one focused ORM/migration
  architecture assertion; avoid per-file contracts.

## Validation and acceptance

- Slice A: focused Artifact service/repository tests plus API create/read and project deletion.
- Slice B/C: focused immutable revision and diff tests.
- Slice D/E: focused dependency tests and an integration scenario with independent A and B branches,
  proving edit(A) makes dependent A stale, leaves dependent B fresh, and the diff names only A.
- Boundary: import-linter plus focused architecture test.
- Final R2 suite: Artifact unit/integration/E2E tests and the new feature's recorded verification via
  `python scripts/task.py verify <id>`. The registry is updated only after the behavior passes.

Completed evidence:

- `python scripts/task.py verify F17`: 5 Artifact behavior/E2E tests and 11 architecture tests pass;
  acceptance is `passing`.
- Combined Artifact + project lifecycle + architecture selection: 38 tests pass.
- `ruff check` and `ruff format --check` pass for all touched Python source/test/configuration files.
- `mypy app/artifacts`: success with 0 errors; all 9 import-linter contracts are kept.
- Fresh-database Alembic upgrade reaches `4da706c0d824 (head)` from the initial migration.
- Inhabited upgrade-path acceptance also passes: a temporary database is upgraded to the pre-R2 head
  `a8f3c1d6e2b4`, populated with representative Project data plus rows in all five Agent tables, then
  upgraded to `4da706c0d824`. Every pre-R2 table and inserted row remains, and all five Artifact tables
  exist (`tests/integration/test_artifact_migration_upgrade.py`).
- Generated frontend OpenAPI types include all Artifact routes/schemas; `tsc -b` passes from
  `frontend/`.
- `git diff --check` passes. Only ordinary CRLF conversion notices remain on this Windows checkout.

## Outcome

R2 is complete: a single `screenplay` type now has stable blocks, immutable aggregate revisions,
block-local diffs, directed dependencies, localized stale propagation, and project lifecycle support.
No Agent integration, Narrative State, workflow/gate, or regeneration engine was introduced.

## Recovery / handoff

Resume from the first unchecked item. Inspect `git status --short`, this plan, and only the nearest
Artifact tests. Do not rerun R1 acceptance or load completed R0/R1 plans unless a concrete interface
conflict appears.
