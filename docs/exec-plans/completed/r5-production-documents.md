# R5 Production Documents

## Purpose and scope

Build the production-document chain on the completed R0-R4 baseline in the master-plan order:
Screenplay → Production Breakdown → Performance Script → Shot Plan → Storyboard → Timeline. R5 extends
Artifact Core only where structured semantic blocks are required, then adds a production application
boundary that binds documents to an episode/optional scene, enforces immediate upstream prerequisites,
and records block-level artifact dependencies so localized edits use the existing stale mechanism.

R5 does not implement real Atomic Skill packages, prompt/provider execution, automatic regeneration,
frontend production workspaces, or any skill outside the R6 boundary. Documents are created explicitly;
downstream stale content is retained for review.

## Invariants

- Artifact Core remains the canonical revision/block/dependency store. Production owns document purpose,
  episode/scene binding, type-specific semantic validation, and derivation order without duplicating
  artifact content.
- The six document types follow the exact master-plan order. A downstream document names a same-project,
  same-episode immediate upstream document and at least one of its current source blocks.
- Each semantic production block carries the required fields for its document type; screenplay keeps its
  readable block vocabulary and is not polluted with camera/provider parameters.
- Editing a source block creates an immutable revision and stales only dependencies for that block;
  downstream artifacts and links are never automatically deleted or overwritten.
- Timeline is playable production structure, not world-model truth. Project deletion removes production
  links before Artifact Core deletes their artifacts. Migration preserves a populated R4 database.

## Progress

- [x] 2026-09-12 16:06–16:06 (+08:00) Preflight: archived accepted R4, confirmed F19 passing and a single
  R4 migration head, and opened the one active-plan slot at the R5 boundary.
- [x] 2026-09-12 16:06–16:10 (+08:00) Slice A: extended Artifact Core with semantic block snapshots and the
  six bounded artifact types while preserving existing screenplay API behavior.
- [x] 2026-09-12 16:08–16:12 (+08:00) Slice B: added Production document bindings, additive migration, registration, lifecycle, and
  populated-R4 upgrade evidence.
- [x] 2026-09-12 16:09–16:12 (+08:00) Slice C: enforced the six-step derivation order and type-specific screenplay/breakdown/performance/
  shot/storyboard/timeline semantic contracts through a project-isolated public API.
- [x] 2026-09-12 16:11–16:13 (+08:00) Slice D: proved block-local stale propagation across the production chain without deletion or
  automatic regeneration.
- [x] 2026-09-12 16:12–16:16 (+08:00) Slice E: updated durable owners and one R5 acceptance feature, ran declared validation, archived R5,
  and reconcile the R6 boundary.

## Surprises / Discoveries

- Artifact Core already provides stable blocks, immutable revisions, directed block dependencies, and
  localized stale evaluation, so R5 should extend that owner instead of creating a second revision store.

## Decision Log

- Add optional semantic JSON to immutable block revision snapshots. Existing screenplay `content` remains
  required and compatible; semantic JSON is canonical structured data for R5 blocks, not a replacement
  for readable/rendered content.
- Add `app.production` as the application boundary for document sequencing and episode binding; it calls
  Artifact and Workflow public services only.

## Validation and acceptance

- Focused Artifact regression tests prove R2 screenplay create/edit/diff/stale behavior remains intact and
  semantic JSON survives revisions.
- Production API/E2E tests create all six documents in order, reject missing/wrong/cross-project upstreams,
  validate representative required semantic fields, and prove localized stale with retained downstream.
- Fresh and populated R4 migrations reach one R5 head without prior-row loss or drift.
- Architecture/privacy, Ruff/format, mypy, import-linter, OpenAPI/frontend typecheck, and `git diff --check`
  pass. One R5 feature becomes passing only through Harness verification after behavior passes.

## Outcomes / Retrospective

R5 is complete. Artifact revisions now retain optional semantic JSON alongside readable content, and
Production binds the exact six ordered document types to an episode/scene and immediate upstream current
blocks. Invalid type order, ownership, source identity, and required semantic fields fail explicitly.
Selected source edits reuse Artifact Core localized stale and retain downstream content.

Acceptance evidence: 9 focused Artifact/Production API, E2E, and migration tests plus 14 architecture
tests pass; populated R4 content survives with a null semantic field and fresh/populated upgrades reach
single head `e52b7a91f4c8`; Alembic reports no drift. Ruff/format, mypy for Artifact/Production, all 14
import-linter contracts, regenerated OpenAPI, frontend TypeScript, and `git diff --check` pass. Harness
verification changed only F20 to `passing`.

## Recovery / restart point

R5 requires no follow-up. The user authorized continuation to the final bounded R6 Atomic Skills plan.
No unsafe or incomplete database operation is in progress.
