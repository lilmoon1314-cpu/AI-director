# Creative workflow product behavior

## Requirements and planning hierarchy

- A creator can save a project requirement specification repeatedly; every accepted version remains
  traceable and the newest version is returned as current.
- A creator can create a workflow series, ordered episodes within it, and ordered pre-screenplay scene
  plans within an episode.
- A scene plan captures the narrative planning fields needed to write one scene without mixing in
  production or provider instructions.
- Hierarchy references and positions are project-isolated; duplicate positions conflict explicitly.
- The product shell lists real series and ordered episodes in pages, and supports direct episode
  links with a project/series/episode breadcrumb. Invalid hierarchy combinations fail explicitly.
- Episode pages expose a production navigation rail and saved document records. Planning drafts are
  not production approvals. Editing, generation, review, and playable timeline workspaces remain
  explicitly unavailable in this shell stage; browser refresh/back restores the URL scope.

## Gates and execution trace

- A creator can define a stage gate for a project, series, episode, or scene from explicit prerequisite
  keys and expected values.
- Evaluation is deterministic and reports all unmet prerequisites. A blocked gate remains browsable and
  does not silently advance workflow state.
- A requested creative action creates an auditable execution run. R4 mock execution records ordered steps
  and a candidate output but does not change approved or canonical content.

## Lifecycle

- Deleting a project removes its requirement, hierarchy, gates, and execution audit records.
- R4 does not yet create production documents or execute real Atomic Skills.
