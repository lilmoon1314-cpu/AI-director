# Lineage and change management

`app.lineage` is the sole owner of cross-domain dependency facts, freshness projection, impact,
reverse change proposals, and append-only review audit. Artifact owns content and approval;
Production owns semantic contracts. Cross-domain calls use the target service boundary.

## References and storage

`lineage_edges` stores project, typed upstream/downstream identities, exact revision references,
dependency category, invalidation policy, validator, state, cause, and superseded-edge identity.
The initial implemented source adapters are `artifact` and `artifact_block`; downstream is `artifact`.
Unknown kinds and forged/cross-project block or revision references fail closed. Future domains must
implement owner validation before adding admitted reference kinds; polymorphic IDs are never trusted
just because they are strings. Endpoints cannot self-depend or introduce cycles.

New downstream revisions carry incoming baselines into new edges, superseding old edges instead of
rewriting their revision references. The historical edge's baseline and cause remain readable. Each
new edge records `supersedes_id`; review audit identifies explicit rebase decisions. Existing legacy
dependency IDs are preserved by migration. New writes go only to Lineage; `artifact_dependencies`
is retained unchanged as historical migration evidence. Legacy dependency endpoints adapt to Lineage.

## Impact and freshness

Impact preview validates the current source revision and changed block IDs, returns direct edges
with their policies, and identifies transitive blocked artifacts without mutating anything. Whole
artifact sources respond to any block change; block sources respond only to that block. Invalidation
compares the actual edge baseline snapshot against current content/order/semantics, including when
unrelated revisions have intervened. A stale edge retains its first cause until explicit review.

| Policy | Direct effect | Resolution |
|---|---|---|
| hard_stale | STALE | Explicit still-valid review or validated rebase |
| review_required | STALE | Explicit still-valid review or validated rebase |
| compatibility_check | BLOCKED pending validation | Implemented compatibility validator must pass |
| timing_revalidate | BLOCKED pending timing validation | `timing_equal` must pass |
| notice_only | VALID, audit notice | No invalidation |
| none | VALID, no notice | No invalidation |

Active/rebased edges participate in freshness along with unresolved stale edges. A consumer of an
unresolved upstream artifact is BLOCKED even when its direct source content has not changed. Resolving
the upstream removes that derived block without fabricating a content change in the consumer. Approval
is independent and never overwritten by invalidation. No policy regenerates media or deletes work.

## Reviews, proposals, and rebase

Review requires an actor, reason, and expected current upstream/downstream revisions. `still_valid`
is an explicit human compatibility decision for ordinary stale/review policies. A `rebase` request,
timing policy, or compatibility policy requires a server validator. Validators read authoritative
snapshots: `content_equal` compares content plus semantics; `timing_equal` compares positive integer
`duration_ms` values. Missing/unknown validators fail closed; future domains supply richer validators.

A proposal records origin revision, target block/base revision, content/semantic patch, rationale,
evidence, creator, decision, and committed revision. Creating it changes no source content. Accept,
reject, and supersede are explicit decisions; retrying the same terminal decision is idempotent and
the opposite decision conflicts. Accept requires both bases still current, validates any bound
Production contract, and calls the Artifact owner to append the target revision. Compatible origins
get a content-identical new revision and rebased source edge; incompatible origins retain content and
their unresolved freshness. Other matching consumers remain stale. There is no silent upward edit.

SQLite write transactions serialize edge creation/review/decisions before reading bases. Artifact
revision advancement also uses compare-and-set. Nested savepoints allow a failed target write or
failed rebase/audit to roll back the proposal claim, revisions, edge changes, and audits together.
Review rows are append-only until explicit project deletion. Operational events contain IDs and
metadata; proposal content and evidence live in the database, not operational logs.

## Migration and boundaries

Migration `a5557d421f40` adds three tables and `artifacts.approval_status`, then copies legacy dependency
baselines/stale flags. It preserves original tables and revision pointers. Legacy stale records did
not store the causative new revision; their retained `stale_cause_ref` is the known old baseline,
not an invented edit event. Downgrade refuses to discard review history; recovery uses a pre-upgrade
SQLite backup. No old table drop is part of R2.

R2 provides backend APIs and generated frontend types. The integrated Impact Drawer/Review Center
belongs to the later workspace stage. Planning versioning, media providers, new Design/Timeline/Previz
owners, and Agent G/H work are not introduced here.
