# R1 Agent Service Split

## Purpose and scope

Refactor `backend/app/agent/service.py` without changing observable behavior or the external Agent
service/API contract. Separate the owners that currently coexist there: conversation lifecycle,
context and rolling-summary compilation, memory documents, confirmed/pending writes, and the chat
orchestration shell. This plan is limited to R1 architecture work; product features and R2+ concerns
are out of scope.

`app.agent.service` remains the public cross-domain and router-facing façade. Extracted modules are
private implementation owners inside `app.agent` and may be reached externally only through that
façade.

## Contract and discovery baseline

- Public HTTP contract: the existing `/api/agent` routes, status codes, response DTOs, and SSE event
  protocol in `backend/app/agent/router.py`.
- Cross-domain contract: `projects.router` calls `service.delete_project_data`; application shutdown
  calls `service.dispose_resources`; other Agent callers use the public functions imported by the
  router.
- Conversation owner: create/ensure/list/delete sessions plus message readback and DTO conversion.
- Context owner: perspective-filtered graph directory, memory directory/sections, summary cursor,
  recent history window, prompt budget assembly, and rolling-summary maintenance.
- Document owner: guide-template creation/uniqueness, document reads/lists/deletion, section CAS, and
  escaped page rendering.
- Writes owner: legacy propose/confirm compatibility plus pending-write read/apply/approve/reject and
  per-item failure semantics.
- Chat shell owner: content review, durable user-message-first transaction, bounded tool loop,
  reasoning/token/usage SSE events, assistant persistence, pending-write completion payload, error
  translation, and summary trigger.
- Direct behavior evidence lives in `test_agent_service.py`, `test_agent_memory_docs.py`,
  `test_agent_api.py`, and `test_agent_flow.py`; architecture enforcement lives in
  `test_architecture.py` and the import-linter contracts in `backend/pyproject.toml`.

## Progress

- [x] Read the root routing instructions and ExecPlan protocol.
- [x] Locate current responsibilities, public callers, direct tests, and import contract.
- [x] Establish the pre-refactor targeted baseline and add only missing characterization coverage.
- [x] Slice 1: extract the context/summary owner; run targeted tests and architecture checks.
- [x] Slice 2: extract the memory-document owner; run targeted tests and architecture checks.
- [x] Slice 3: extract conversation lifecycle after dependency discovery; run targeted tests and
  architecture checks.
- [x] Slice 4: extract confirmed/pending writes; run targeted tests and architecture checks.
- [x] Slice 5: extract the chat orchestration shell and reduce `service.py` to the stable façade; run
  targeted tests and architecture checks.
- [x] Run final R1 acceptance validation, summarize results, and archive this plan per `docs/PLANS.md`.

## Characterization and validation plan

Before production-code movement:

1. Run the existing Agent unit suites and the Agent integration suite as the behavioral baseline.
2. Add focused characterization only where the owner boundary lacks observable coverage. Prefer
   returned DTOs, persisted state, transaction effects, SSE events, visibility filtering, CAS, and
   partial-success semantics; do not assert module paths, helper names, prompt literals, or templates.
3. For each slice, run the nearest unit tests plus the relevant integration cases. Run
   `backend/tests/architecture/test_architecture.py` and import-linter after each dependency-boundary
   change.
4. At R1 completion, run all Agent unit/integration/E2E tests and the architecture tests. A full
   repository check is unnecessary unless the change reveals a broader boundary impact.

## Task-local decisions

- Preserve `app.agent.service` as a compatibility façade so routers and cross-domain callers do not
  change.
- Move one coherent owner at a time; no whole-file rewrite.
- Keep transaction ownership and exception translation exactly where current behavior places them.
- Reuse current schemas, repository, prompts, tools, and domain service boundaries rather than create
  a second abstraction or registry.
- Do not update product specs, feature state, or durable design documents unless implementation
  discovers a genuinely new durable truth. The intended result implements the design already recorded
  in `docs/design-docs/agent-system.md`.

## Discoveries

- The repository baseline is intentionally dirty from R0; all unrelated changes are treated as user
  state and must remain untouched.
- Existing tests are extensive but several unit fixtures monkeypatch shared dependency modules through
  `app.agent.service`. Extractions must preserve those shared module objects or adjust fixtures toward
  public configuration seams without weakening behavioral assertions.
- Context characterization now explicitly locks summary-cursor exclusion, recent-tail retention, and
  exactly-once current-message injection at the provider boundary without asserting prompt templates.
- The document extraction's first targeted run caught a missing `SectionUpdate` import in the still
  colocated pending-write owner. Restoring that dependency returned both successful CAS and conflict
  behavior to baseline before proceeding.
- Writes needed the same conversation lookup and project-ownership rule as chat. Extracting
  `conversations.py` before `writes.py` avoided duplicated not-found semantics and a writes-to-façade
  dependency; this changed slice order but not scope.
- Whole-Agent mypy reports six pre-existing tuple annotation errors in unchanged `agent/tools.py`.
  They are outside the R1 diff and were not repaired. A narrow type check of all six R1 owner/façade
  files passes.
- No R2+ issue required implementation.
- R2+ findings, if any, will be recorded here briefly and not implemented.

## Validation record

- Pre-refactor: 77 Agent unit/integration tests passed; 10 architecture tests passed; import-linter
  kept all 8 contracts.
- Characterization addition: `test_stream_chat_context_uses_summary_cursor_and_recent_tail`; the Agent
  unit suite passed 44 tests before production movement.
- Context slice: 69 directly related unit/integration tests passed; 10 architecture tests passed; all
  8 import contracts kept.
- Documents slice: ruff passed; 78 directly related unit/integration tests passed; 10 architecture
  tests passed; all 8 import contracts kept.
- Conversation slice: 69 directly related unit/integration tests passed; all 8 import contracts kept.
- Final R1 behavior suite: 169 Agent unit/integration/E2E and architecture tests passed.
- Final static/boundary checks: ruff passed for `app/agent` and the changed characterization test;
  mypy passed for the six R1 owner/façade files with imported implementations skipped; import-linter
  analyzed 56 files/163 dependencies and kept all 8 contracts.
- The existing Agent private-layer contract now includes `context`, `conversations`, `documents`,
  `writes`, and `chat`, preserving `app.agent.service` as the only external service boundary.

## Result

- `service.py` is a small public façade that preserves router, project-deletion, shutdown, SSE, and
  legacy propose/confirm call surfaces.
- `context.py` owns visible context compilation and rolling summaries.
- `conversations.py` owns sessions, messages, and Agent project-data cleanup.
- `documents.py` owns memory-document templates, reads, CAS updates, deletion, and HTML rendering.
- `writes.py` owns legacy drafts plus pending-write approval/rejection and per-item failure behavior.
- `chat.py` owns content review, streaming/tool orchestration, persistence ordering, SSE payloads,
  usage reporting, and failure translation.
- No product capability, route, response schema, SSE behavior, feature state, or R2+ architecture was
  added or changed.

## Recovery / next slice

R1 is complete. Resume only for a regression in the recorded R1 contract; do not continue into R2
without a separate request and plan.
