# Artifact Core design

Artifact Core owns project-scoped structured artifact identities, stable blocks, immutable aggregate
and block revision snapshots, diffs, approval lifecycle, and content revert. Supported kinds are owned
by `artifacts.schemas`; Production owns type-specific semantics and episode bindings.

## Ownership and storage

`artifacts`, `artifact_blocks`, `artifact_revisions`, and `artifact_block_revisions` retain their existing
identity and snapshot meaning. Approval is stored as `approval_status` (draft/review/approved/archived).
The old `status` column and `artifact_dependencies` table are retained migration history, not runtime
write authorities. Lineage owns dependencies and freshness; see `lineage-and-change-management.md`.
The old dependency HTTP API is an adapter to Lineage, including preserved legacy dependency IDs.

## Revision transaction

A block edit compares stable IDs, content, order, and semantic data, appends the next immutable revision
with optimistic revision advancement, copies source baselines into new Lineage edges, and supersedes
the prior revision's edges. Only changed source blocks (or a changed whole-artifact source) invalidate
matching live edges. Source snapshots are compared against each edge's actual baseline, so an intervening
unrelated block edit does not lose dependency tracking. New content resets approval to draft.

Rebase appends a content-identical revision, preserves approval, and records new source baselines and
review audit. Revert copies an old full snapshot to a new revision, resets approval, and retains current
incoming baselines pending review. This conservative rule also supports revisions created before
Lineage existed, when full historical source snapshots were unavailable. Intermediate revisions remain
readable. No operation deletes a revision as an undo mechanism.

## Boundaries

Cross-domain callers use `artifacts.service`. `resolve_lineage_ref` validates artifact/block/revision
ownership without recursively loading freshness. Lineage's snapshot reader uses that boundary; Artifact
responses project freshness through `lineage.service`. Artifact internals never read Lineage tables.
Project deletion is composed by the project router: Lineage records first, then Artifact-owned rows.

Approval confirmation serializes with content writes in SQLite and requires the reviewed current
revision. Proposal acceptance, target revision, impact, origin rebase, and review audit are one outer
transaction; nested failures roll the whole operation back. Production proposals also validate the
production contract through its service before Artifact creates a revision.
