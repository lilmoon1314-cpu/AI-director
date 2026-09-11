# Artifact Core design

This document owns the durable R2 boundary for structured creative artifacts. It deliberately excludes
Narrative State, Agent tooling, workflow gates, regeneration, branching, merging, and collaboration.

## Ownership and storage

`backend/app/artifacts/` owns artifact identity, stable blocks, immutable revisions, revision diffing,
directed dependencies, and stale propagation. Other domains may call only `artifacts.service`; the
FastAPI composition root mounts the Artifact router, and the projects router calls the service during
cross-domain project deletion.

The primary SQLite database stores five tables:

- `artifacts`: project-owned identity, the only admitted type (`screenplay`), current revision number,
  and coarse `draft`/`stale` state.
- `artifact_blocks`: stable block identity and block type. It intentionally stores no mutable content.
- `artifact_revisions`: immutable aggregate revision identity and monotonic number per artifact.
- `artifact_block_revisions`: immutable ordered content snapshots keyed by revision and stable block.
- `artifact_dependencies`: directed source artifact/block/revision baseline to dependent artifact,
  plus whether that edge has become stale.

Snapshotting every block in a revision is an intentional R2 tradeoff: it makes historical reads and
block-local comparisons deterministic without event sourcing or a generic version-control framework.
Content size and revision compaction are later concerns supported by evidence, not prebuilt here.

## Edit, diff, and invalidation transaction

A block edit loads the current immutable snapshot, rejects a no-op, appends the next revision and its
snapshots, and computes a stable-ID diff. Only changed block IDs select dependency edges. Those edges
and their dependent artifacts become stale in the same primary-database transaction; unrelated edges
are not updated. Project activity time is touched in that transaction.

Dependencies are artifact-local references rather than a universal polymorphic graph. Service
validation requires source block/revision ownership and same-project source/dependent artifacts. A
dependency baseline remains historical after invalidation so the stale cause is explainable.

## Lifecycle and migration

Artifact child tables use database cascade constraints below `artifacts`; project deletion is still
explicitly composed through `projects.router`, matching existing domain lifecycle rules. Alembic
registers both existing Agent models and Artifact models before autogeneration and renders the runtime
UTC type as portable `DateTime` DDL, preventing unrelated-table drops and unresolved generated types.

