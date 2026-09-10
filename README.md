# AI-director

AI-director is a local workspace for developing film and series worlds. It combines structured entity
and relationship management, author/character/audience graph views, reusable and project-specific
assets, multi-project navigation, and a project-scoped creative assistant with user-confirmed writes.

The current application is a FastAPI + SQLite modular monolith with a React, TypeScript, Zustand, and
AntV G6 frontend. It stores the complete world model once and derives restricted views at read time.

## Requirements

- Python 3.12+
- Node.js 20+
- uv
- pnpm 9+
- make, or Python on Windows for the equivalent command panel

## Setup and development

```bash
make setup
make dev
```

The backend API documentation is available at `http://localhost:8000/docs`; the frontend runs at
`http://localhost:5173`.

Windows without make:

```powershell
python scripts/task.py setup
python scripts/task.py dev
```

Useful verification commands:

```bash
make test-unit
make test-integration
make test-e2e
make check
python scripts/task.py verify --list
```

Use checks proportional to the change. `make check` is the full repository suite, not a required
session-start or session-end action.

## Repository map

- `backend/app/` — FastAPI domain modules and core infrastructure.
- `backend/migrations/` — authoritative primary-database migrations.
- `frontend/src/` — application views, components, stores, and generated API client.
- `feature_list.json` — machine-readable product acceptance state.
- `ARCHITECTURE.md` — current high-level ownership and dependency map.
- `docs/product-specs/` — observable product behavior.
- `docs/design-docs/` — durable implementation reasoning.
- `docs/exec-plans/active/` — state for complex work currently in progress.
- `scripts/task.py` — cross-platform command implementation.

Agent operating guidance is in `AGENTS.md`. Historical implementation detail is available through Git
rather than an always-growing progress or decision log.
