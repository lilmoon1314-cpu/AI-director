# Artifact Core product behavior

This specification owns observable structured-artifact, revision, diff, dependency, and stale
behavior. Supported artifact kinds are defined by the current Artifact API schema.

## Screenplay and revisions

- A screenplay has a stable artifact identity and ordered blocks with stable generated identities.
  Block identity does not depend on current text or array position.
- Creating a screenplay creates revision 1 containing the initial block state.
- Editing one block keeps the artifact and block identities, creates the next immutable revision, and
  leaves earlier revision content readable and unchanged.
- Submitting content identical to the current block is rejected rather than creating a false revision.
- A revision diff classifies each stable block as unchanged, modified, added, or removed and reports
  the exact changed block IDs. R2's write surface edits existing blocks; added/removed classifications
  make comparisons well-defined without introducing insertion/deletion workflows.

## Dependencies and stale state

- A dependency is directed from a source artifact block at a source revision baseline to a
  dependent artifact in the same project.
- Editing a block marks only fresh dependencies sourced from that changed block as stale and marks
  their dependent artifacts stale. Sibling-block dependencies and their dependent artifacts remain
  unaffected.
- Stale means the dependent was based on older source content. R2 does not delete or regenerate it and
  does not schedule follow-up work.

## Ownership and lifecycle

- Every artifact belongs to an existing project. Both ends of a dependency must belong to that same
  project, and the source block/revision must belong to the declared source artifact.
- Deleting a project removes its artifacts, blocks, revisions, revision snapshots, and dependencies as
  part of the existing primary-database deletion transaction.
- Agent memory documents remain a separate domain and are not converted to artifacts.


## Approval, source review, and revert

- Approval is draft → review → approved → archived. Review can return to draft. Content edits and
  revert create a draft; rebase preserves approval because content is unchanged. An archived item is
  restored through a new revision. Approval changes require the current revision and an audit reason.
- Freshness is independent: an approved artifact can become STALE. Consumers of an unresolved source
  are BLOCKED. New approval is refused while sources remain unresolved. Legacy `status` is a response
  compatibility projection (`draft` or `stale`), not the approval authority.
- Revert copies a selected historical snapshot into a new revision, retaining intermediate history.
  Reverted downstream content keeps current source baselines and requires their review; it does not
  silently inherit source approval that may belong to a different content version.
- Policy-based impact previews, explicit reverse proposals, validated rebase, and review audit are
  specified in `production-workspace.md` and designed in `../design-docs/lineage-and-change-management.md`.
