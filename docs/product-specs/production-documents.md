# Production document product behavior

- A creator can build an episode through Screenplay, Production Breakdown, Performance Script, Shot
  Plan, Storyboard, and Timeline in that order.
- Screenplay remains a readable story/performance document. Each later document exposes structured
  fields appropriate to preparation, acting beats, shots, panels, or playable tracks.
- A downstream document identifies its immediate upstream document and the current source blocks used.
  Skipping a stage, crossing a project/episode, or using an invalid source block is rejected explicitly.
- Every block revision retains readable content and structured semantic data where applicable.
- Editing one source block creates a revision and marks only matching dependents stale. Existing
  downstream content remains available for diff/review and is never automatically overwritten or deleted.
- Timeline represents playable production tracks; it does not replace canonical world or narrative state.
