# Production documents

The production chain is Screenplay → Production Breakdown → Performance Script → Shot Plan →
Storyboard → Timeline. Artifact Core remains the canonical store for stable block identity, immutable
revisions, semantic snapshots, diffs, approval, and revert. Lineage owns dependencies and freshness. `app.production` owns only document
purpose, episode/scene binding, type-specific semantic validation, and immediate-upstream sequencing.

Readable `content` and optional structured `semantic_json` coexist in each immutable block snapshot.
Screenplay accepts only scene heading, action, dialogue, parenthetical, and transition blocks; it does
not absorb camera or provider settings. Breakdown describes resources and continuity. Performance beats
describe acting, movement, and pacing. Shot plans describe camera intent. Storyboards bind panels to
shots and references. Timeline clips organize playable tracks and do not become world-model truth.

Every downstream document selects at least one current block from the same-project, same-episode,
immediately preceding document. Lineage dependencies retain that source revision. Editing a selected
source block marks only matching dependents stale and never deletes or regenerates them automatically.
R6 skills may propose these documents but must use the same validation and candidate-acceptance boundary.

Reverse change proposals validate the bound production semantic contract through `production.service`
before committing through Artifact Core. The proposal service never writes production tables directly.
