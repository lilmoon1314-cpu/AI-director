# AI-director architecture map

This file answers where a concern lives, who owns it, and which direction dependencies flow. Detailed
behavior and reasoning live in the linked product specifications and design documents.

## System shape

```text
React + TypeScript + G6
  views/components → Zustand stores → generated API client
                         │ REST / SSE
FastAPI modular monolith
  projects  entities  relations  perspectives  assets  agent  artifacts  narrative_state  workflow  production  skills
                         ↓
  core: configuration, primary DB session, errors, observability
                         ↓
SQLite: app.db                 SQLite: assets.db + asset files
```

The exact current routes and schemas are owned by FastAPI/OpenAPI, ORM models, migrations, and frontend
generated types—not by hand-maintained tables in this document.

## Ownership map

| Concern | Code owner | Durable design |
|---|---|---|
| Runtime configuration, primary DB, errors, observability | `backend/app/core/` | `docs/design-docs/platform-boundaries.md` |
| Project identity, lifecycle, counters | `backend/app/projects/` | `docs/design-docs/projects-assets-and-workspace.md` |
| Entity facts and typed properties | `backend/app/entities/` | `docs/design-docs/world-model-and-perspectives.md` |
| Typed links between entities | `backend/app/relations/` | `docs/design-docs/world-model-and-perspectives.md` |
| Author/character/audience projections | `backend/app/perspectives/` | `docs/design-docs/world-model-and-perspectives.md` |
| General assets, entity pages, image storage | `backend/app/assets/` | `docs/design-docs/projects-assets-and-workspace.md` |
| Conversations, prompts, tools, memory, pending writes | `backend/app/agent/` | `docs/design-docs/agent-system.md` |
| Screenplay artifacts, blocks, revisions, dependencies, stale | `backend/app/artifacts/` | `docs/design-docs/artifact-core.md` |
| Timepoints, temporal state, snapshots, claims, knowledge | `backend/app/narrative_state/` | `docs/design-docs/narrative-state-core.md` |
| Requirements, series/episodes/scenes, gates, execution audit | `backend/app/workflow/` | `docs/design-docs/workflow-core.md` |
| Production document order, episode binding, semantic contracts | `backend/app/production/` | `docs/design-docs/production-documents.md` |
| Atomic Skill registry, validation, candidates, confirmed adapters | `backend/app/skills/`, `skills/` | `docs/design-docs/atomic-skills.md` |
| Navigation, graph, asset, and Agent UI | `frontend/src/` | `docs/design-docs/projects-assets-and-workspace.md`, `docs/design-docs/agent-system.md` |
| Product acceptance state | `feature_list.json` | product specs referenced by each feature |
| Development commands and feedback orchestration | `scripts/task.py` | `AGENTS.md` |

## Dependency direction

`core` has no domain knowledge. Domain modules may depend on core. Cross-domain calls go through the
target domain's service API; import-linter in `backend/pyproject.toml` owns the exact enforced matrix.

`projects` business layers depend only on core. The projects router is the composition point for
project deletion across domains. `perspectives` owns all visibility computation used by graph responses
and Agent context. `assets` may read entities through their service, while entity writes do not call
back into assets.

## Main flows

- World-model write: HTTP router → domain service validation/transaction → repository/ORM → app.db.
- Perspective read: graph request → perspectives service → entity/relation services → filtered
  projection; storage remains the complete author model.
- Asset read/write: asset service coordinates assets.db and contained asset files; entity pages derive
  from current entity data.
- Agent turn: persisted user message → visible project context → provider stream/tool loop → persisted
  response and pending operations → explicit user approval → owning domain service.
- Artifact edit: stable block edit → immutable revision snapshot → block-local diff → only matching
  directed dependencies and their dependent artifacts become stale.
- Narrative state: ordered timepoint → append-only event with optional artifact provenance → versioned
  current projection → immutable scope snapshot; claims remain separate from character/audience belief.
- Workflow: versioned requirement → series/episode/scene plan → deterministic gate evaluation → audited
  mock run/candidate; no prompt-driven stage advancement.
- Production: ordered document request → semantic validation → Artifact revision/dependency creation →
  localized stale on selected upstream block changes; retained downstream content.
- Atomic Skill: registered contract → explicit minimal context/gate validation → Workflow execution trace
  → pending candidate/impact → explicit accept/reject → bounded owning-service adapter.
- Project switch: route project ID → project-scoped store reset/reload; global reference assets remain.

## Knowledge routes

Observable behavior is owned by `docs/product-specs/`. Non-obvious implementation reasoning is owned by
`docs/design-docs/`. Complex work state is owned by `docs/exec-plans/active/`. Current schemas, API
contracts, dependencies, and executable checks are owned by code and machine configuration.
