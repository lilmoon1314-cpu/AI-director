# AI-director agent map

AI-director is a local film-development workspace built around one complete world model and
author/character/audience projections. It is a FastAPI + SQLite modular monolith with a React/G6
frontend and a project-scoped creative assistant.

This is the only always-on Agent document: a repository constitution and routing map, not an
encyclopedia, task history, design duplicate, or product specification.

## Working agreements

- Keep the requested scope. Preserve user changes and local data, and do not absorb unrelated changes
  into the task. Never destructively reset, discard, overwrite, or delete existing work without explicit
  authorization. Never commit `.env`, databases, uploaded assets, dependency directories, or credentials.
- Runtime configuration belongs in `backend/app/config.py`, frontend environment handling, and their
  example environment files—not scattered literals.
- Cross-domain backend calls use the target domain's service boundary. Exact import rules are enforced
  by `backend/pyproject.toml` and architecture tests.
- Database changes default to additive and data-preserving: inspect the current migration graph and model
  registration, review generated operations before execution, and prove the populated upgrade path when
  existing data may be affected. Destructive operations require explicit task scope and a recovery plan;
  never accept unrelated drops or rewrites as generated noise.
- Complex, multi-file, long-running, new-capability, or significant-refactor work uses one active
  ExecPlan following `docs/PLANS.md`; small local fixes do not. V3 stage purpose, order, prerequisites,
  status, and boundaries belong only to `CODEX_REFACTOR_MASTER_PLAN_V3.md`. Execute only the stage the
  user requested, use a stage-local ExecPlan, and stop at its next-stage boundary unless separately asked.
- Product acceptance state belongs to `feature_list.json`; query it narrowly and update it only through
  `python scripts/task.py verify ...` after the recorded behavior passes.

## Context discipline

Context and model turns are finite engineering resources. Start with targeted lookup, gather tightly
related files or symbols together, and expand only when the evidence requires it. Avoid unbounded
repository scans, repeated reads of unchanged large files, and fragmented `read → reason → read` loops
when one bounded retrieval can answer the question.

Keep command and test output bounded to evidence relevant to the current task. Do not read Codex session
or rollout logs to analyze token use; token telemetry is owned by an observer outside the repository.

## Validation defaults

- Use the smallest sufficient validation nearest the change. Add integration/E2E evidence when behavior
  crosses real component boundaries. A full repository check is for broad changes, release/CI, or an
  explicit request—not a session ritual.
- Do not rerun historical mutation, benchmark, full-suite, or acceptance evidence by default. Mutation
  testing is optional and reserved for high-value pure domain logic when a task's validation plan
  justifies it.
- Record unrelated pre-existing failures with enough evidence to distinguish them from the task; do not
  repair or absorb them unless the user expands scope.

## Commands

```bash
make setup                 # install dependencies, create .env, migrate
make dev                   # backend :8000/docs + frontend :5173
make test                  # all backend and frontend tests
make check                 # full repository verification when justified
make verify FXX            # run one feature's recorded acceptance checks
```

On Windows without make, use `python scripts/task.py <command>`. Run
`python scripts/task.py help` for the complete executable command list and
`python scripts/task.py verify --list` to query feature state.

## Progressive knowledge routes

Use `targeted lookup → nearest authoritative owner → nearest code/tests → expand only if needed`.
Read only the additional owner required by the task:

- System location, ownership, or dependency direction: `ARCHITECTURE.md`.
- Observable entity/relationship/graph behavior:
  `docs/product-specs/world-building-workspace.md`.
- Observable project/asset behavior: `docs/product-specs/projects-and-assets.md`.
- Observable assistant behavior: `docs/product-specs/agent-assistance.md`.
- Platform and storage reasoning: `docs/design-docs/platform-boundaries.md`.
- World-model and visibility design: `docs/design-docs/world-model-and-perspectives.md`.
- Temporal narrative state, continuity snapshots, claims, or knowledge perspectives:
  `docs/design-docs/narrative-state-core.md`.
- Project, asset, route, or workspace-state design:
  `docs/design-docs/projects-assets-and-workspace.md`.
- Agent context, memory, streaming, or confirmed-write design:
  `docs/design-docs/agent-system.md`.
- Current complex-task state: the relevant file in `docs/exec-plans/active/`.
- Finite V3 refactor stage purpose, order, prerequisites, status, and boundary:
  `CODEX_REFACTOR_MASTER_PLAN_V3.md` (only for a V3 stage task).
- Feature status or acceptance references: query `feature_list.json` by ID/category/status; do not load
  the whole file when a narrow query is enough.
- Current API/schema/config: source code, ORM/migrations, `backend/openapi.json`, and config files.
- Third-party behavior: official upstream documentation or a task-specific file under
  `docs/references/` if one exists.

Completed plans, historical reports, the V3 master plan outside a V3 stage task, and unrelated
design/product documents are not default context.

## Cold-start paths

- Small local fix: `AGENTS.md → target code → nearest test/config`.
- Single-domain complex change: add the relevant ARCHITECTURE section, one bounded design doc, relevant
  product spec if behavior changes, and an active ExecPlan.
- Cross-layer behavior change: add the relevant product spec first, then only the participating design
  docs, active ExecPlan, relevant feature entries, and integration/E2E tests.
