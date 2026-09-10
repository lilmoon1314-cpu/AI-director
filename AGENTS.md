# AI-director agent map

AI-director is a local film-development workspace built around one complete world model and
author/character/audience projections. It is a FastAPI + SQLite modular monolith with a React/G6
frontend and a project-scoped creative assistant.

This is the only always-on Agent document. Load other knowledge progressively for the task at hand.

## Working rules

- Keep the requested scope. Do not fold unrelated refactors into a change.
- Preserve user changes and local data. Never commit `.env`, databases, uploaded assets, dependency
  directories, or credentials.
- Runtime configuration belongs in `backend/app/config.py`, frontend environment handling, and their
  example environment files—not scattered literals.
- Cross-domain backend calls use the target domain's service boundary. Exact import rules are enforced
  by `backend/pyproject.toml` and architecture tests.
- Use the smallest sufficient verification near the change. Add integration/E2E evidence when behavior
  crosses real component boundaries. A full repository check is for broad changes, release/CI, or an
  explicit request—not a session ritual.
- Mutation testing is optional and reserved for high-value pure domain logic when a task's validation
  plan justifies it. Never rerun historical mutation evidence by default.
- Complex or cross-session work uses one active ExecPlan following `docs/PLANS.md`. Small fixes do not.
- Product acceptance state is `feature_list.json`; update it only through
  `python scripts/task.py verify ...`.

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

Start with target code and its nearest tests. Read only the additional owner needed:

- System location, ownership, or dependency direction: `ARCHITECTURE.md`.
- Observable entity/relationship/graph behavior:
  `docs/product-specs/world-building-workspace.md`.
- Observable project/asset behavior: `docs/product-specs/projects-and-assets.md`.
- Observable assistant behavior: `docs/product-specs/agent-assistance.md`.
- Platform and storage reasoning: `docs/design-docs/platform-boundaries.md`.
- World-model and visibility design: `docs/design-docs/world-model-and-perspectives.md`.
- Project, asset, route, or workspace-state design:
  `docs/design-docs/projects-assets-and-workspace.md`.
- Agent context, memory, streaming, or confirmed-write design:
  `docs/design-docs/agent-system.md`.
- Current complex-task state: the relevant file in `docs/exec-plans/active/`.
- Feature status or acceptance references: query `feature_list.json` by ID/category/status; do not load
  the whole file when a narrow query is enough.
- Current API/schema/config: source code, ORM/migrations, `backend/openapi.json`, and config files.
- Third-party behavior: official upstream documentation or a task-specific file under
  `docs/references/` if one exists.

Completed plans, historical reports, the R1+ master plan, and unrelated design/product documents are
not default context.

## Cold-start paths

- Small local fix: `AGENTS.md → target code → nearest test/config`.
- Single-domain complex change: add the relevant ARCHITECTURE section, one bounded design doc, relevant
  product spec if behavior changes, and an active ExecPlan.
- Cross-layer behavior change: add the relevant product spec first, then only the participating design
  docs, active ExecPlan, relevant feature entries, and integration/E2E tests.
