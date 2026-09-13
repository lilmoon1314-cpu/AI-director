# Workflow Core

Workflow Core owns the deterministic planning hierarchy and execution audit between a project brief and
creative artifacts. A project requirement specification is append-only version history; the highest
version is current. The minimal hierarchy is project → workflow series → ordered episode → ordered scene
plan. The series record is only a workflow container in R4 and does not claim the broader F16 filtering
behavior.

A scene plan is a pre-screenplay narrative card. It records location/time, participating character refs,
scene and character goals, conflict, turn, reveal, exit change, target duration, setup, and payoff. It is
not a screenplay or production breakdown and contains no camera/provider instructions.

Workflow gates are deterministic definitions evaluated against explicit facts supplied by the owning
application flow. Evaluation returns every unmet key/expected-value pair. A prompt or skill cannot bypass
a gate, and gate evaluation does not automatically change a workflow stage.

Execution runs record requested scope, skill identifier, input, status, output candidate, and ordered
steps. R4's mock executor can only finish a pending run and persist its candidate/trace; it cannot write
canonical entities, state, artifacts, or workflow progression. R6 replaces this mock boundary with
validated Atomic Skills while retaining the audit contract.

`app.workflow` is the only owner of these records. Cross-domain callers use its service boundary, and
project deletion composes cleanup in the projects router.
