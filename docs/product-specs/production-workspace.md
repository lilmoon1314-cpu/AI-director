# Production workspace: source changes and review

The production shell provides project/episode navigation as described in
`../design-docs/frontend-production-workspace.md`. The R2 API behavior adds the following review
capabilities; the integrated review interface is a later stage.

- Approval and source freshness are separate. An approved document may need source review without
  losing its approval history or content. Consumers of unresolved sources are blocked.
- Impact preview identifies the selected changed blocks' dependencies and transitive blockers.
  Editing another block does not invalidate an unrelated branch.
- Dependencies declare whether a change requires review, compatibility/timing validation, a notice,
  or no action. Review explains the reason and records the reviewed versions and actor.
- A downstream artifact may propose a change to an upstream block it depends on. Creating a proposal
  never changes the upstream. Accept/reject/supersede decisions are explicit and auditable.
- Acceptance creates an upstream revision through its owner. If the origin already matches the new
  source under a server validator, the origin receives a content-identical rebased revision. Otherwise
  it remains available for review. Other affected consumers are not automatically cleared.
- Changed origin/target bases require renewed review; failed acceptance leaves no partial source
  revision or decision. Retrying an already completed identical decision does not duplicate writes.
- Revert creates a new revision with old content; intermediate history stays readable. Source
  assumptions for reverted downstream content must be reviewed again.
- Cross-project references and unsupported owner types are rejected. Explicit project deletion cleans
  up its dependency/proposal/audit records along with its artifacts.
- No source change triggers paid generation, overwrites downstream content, or deletes past work.
