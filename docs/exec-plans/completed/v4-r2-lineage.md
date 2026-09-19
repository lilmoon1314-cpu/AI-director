# V4-R2 Lifecycle, Lineage, and Change Proposal

## Purpose and scope

Implement V4.1 R2 only: separate approval from freshness; move dependency ownership into Lineage;
provide policy-based impact, explicit reverse proposals, validated rebase, immutable artifact revert,
and review audit. Baseline is c87c5e5 (R0/R1 committed and pushed). Master owner:
`CODEX_REFACTOR_MASTER_PLAN_V4.1.md` sections 9–13, 65, 68.2–3, 69 R2, 74.1–2.
Existing Artifact/Production clients remain compatible. No media providers, R3 domains, new planning
versioning, or Agent G/H implementation. R2 is backend/API work; the integrated review UI belongs to R9.

## Progress

- [x] 2026-09-19 17:09–17:28 (+08:00) Runtime slices (implemented together): additive storage,
  legacy cutover, approval/freshness, policy impact, proposal decisions, validated rebase, revert,
  audit, ownership, concurrency serialization, and rollback acceptance.
- [x] 2026-09-19 17:28–17:32 (+08:00) Acceptance/documentation: regression checks, generated types,
  real DB backup/upgrade, durable docs, and completed plan. Delivery commit/push follows.

## Surprises / Discoveries

- Prior work was uncommitted R0/R1, now preserved in c87c5e5 and pushed to origin/main.
- Starting migration head was f4b7c8d9e0a1; it is now a5557d421f40. Existing dependencies only describe artifact blocks and store
  stale flags. Preserve the old table as migration history, with no runtime writes after cutover.
- Active Agent plan A–F complete, G/H not implemented; it remains independent.
- Global screenshot preference saved to C:/Users/18539/.codex/AGENTS.md; repository rule and
  test/pic_test directory added. No frontend layout change is planned for R2.

## Decision Log

- Use typed references with explicit owner resolution, rejecting unsupported owner types. Artifact
  and artifact-block are the initial live adapters; future domains register their own owner adapters.
- Keep legacy status only as a compatibility projection; approval and lineage are authoritative.
- Use an outer transaction for proposals, target revisions, invalidation, rebase, and audit.

## Validation and acceptance

Run focused Artifact/Production/Lineage API tests, inhabited migration tests, relevant architecture
checks/import contracts, lint/types, and regenerate OpenAPI types. Prove changed-block isolation,
approval retained on stale, all policies, ownership rejection, proposal rejection/accept/replay/conflict,
compatibility pass/fail, immutable revert, audit, and project cleanup. Avoid historical full suites.

## Outcomes / Retrospective

R2 runtime and acceptance are complete. Approval/freshness, policy impact, explicit proposals,
validated rebase, immutable revert, legacy cutover, and audit are implemented through backend APIs.
Initial live owners are Artifact and Artifact Block; richer future owners/validators and integrated
review UI stay at their respective stage boundaries. No media provider or Agent G/H work was added.
Frontend layout was unchanged, so screenshot acceptance was not required for this task.

## Recovery / restart point

Implementation complete; delivery commit/push is authorized and is the only remaining operation.
The real database is upgraded with a local backup at
`backend/data/backups/pre-v4-r2-20260919-173152.db` (ignored, never committed). All 35 pre-existing tables'
original columns/rows match the backup; foreign keys and Alembic metadata checks pass. `.env` and
asset files are unchanged. Stop at R2; no automatic R3 or Agent G/H continuation.

### Final validation evidence (2026-09-19 17:32 +08:00)

- New Lineage API + inhabited migration: 18 passed (including concurrent idempotent acceptance and
  injected failure after target write and after rebase).
- Existing Artifact/E2E/Production/Skills/navigation + architecture: 27 passed.
- Import contracts: 18 kept. Targeted mypy, Ruff lint, formatting, and Git diff checks passed.
- Generated OpenAPI types and frontend `tsc -b` pass via installed Node CLIs. `pnpm` tried to reinstall
  the existing node_modules due to its local runtime/store mismatch; bypassed that wrapper without
  changing dependencies or lockfiles.
- Actual database upgraded f4b7c8d9e0a1 → a5557d421f40 after backup. Existing data preserved.
  `alembic check` reports no new upgrade operations. Test suites show only the existing Starlette
  httpx deprecation warning.
- No V4-R2 feature ID exists; F17 remains passing with unchanged recorded acceptance. No manual edit
  of feature_list acceptance state is needed.

### Decisions refined during acceptance

- Revert retains incoming baselines but marks them for review, because historical pre-Lineage source
  snapshots may be incomplete. It must not silently approve old content against current sources.
- SQLite write serialization plus revision compare-and-set prevents duplicate confirmations. Fault
  injection after target revision and after rebase proves nested failures leave no partial audit/data.
