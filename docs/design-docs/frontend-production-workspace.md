# Frontend production workspace

The project default is `overview`; picker create/open and the project switcher use that destination.
The shell keeps four primary groups: overview, creation, episodes, and reference assets. Graph and
Agent deep links remain supported, including asset drill-down and Agent session routes. Creation
exposes the future visual asset entry without claiming the V4.1 Prompting platform exists.

React Router owns project/series/episode identity. `ProductionWorkspace` remounts its page state on
pathname changes. Async resource effects discard results after unmount; pagination resets with scope.
Series and episode detail reads validate the hierarchy server-side, so a forged URL cannot combine
resources from different projects or series. Lists are bounded to 20 entries per UI page (API max 100),
with explicit previous/next controls. Failures are retryable and are distinct from empty lists.

Workflow owns series/episode reads through its service/repository. Production owns the episode document
index and checks episode ownership through Workflow's service. No new domain state or migration is
introduced. The shell reads saved records, not a new aggregate truth. A draft or document record does
not prove a production gate passed; stage approval, stale review, and next production decisions remain
unavailable until their owning services can supply authoritative state.

Workbench clears shared project interaction state before painting a different project, including the
asset viewer, selection, perspective, entity index, and Agent state. This must not depend on GraphView
mounting, because Overview is now the landing page. Global reference assets remain cached.

The collapsed episode rail provides navigable scope for script, production, shots, timing, storyboard, director,
timeline, generation, and review. These are shell pages exposing saved document metadata and clear
availability text, not editors or generation actions. The existing production timeline document is
explicitly distinguished from a future playable timeline.

Validation lives in workspace navigation API tests, production workspace route tests, and the isolated
`frontend/playwright.workspace.config.ts` journey. The isolated harness uses fresh temporary databases,
independent ports, and no process-wide server termination.
