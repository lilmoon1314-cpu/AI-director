# R6 Atomic Skills

## Purpose and scope

Complete the finite V3 initiative on the accepted R0-R5 baseline by adding a bounded Atomic Skill
registry, contract-driven executor, deterministic validators, context-permission enforcement, candidate
impact preview, and explicit accept/reject lifecycle. Register representative skills across requirement,
story, scene, screenplay, dialogue, production, performance, shot, continuity, and audience concerns.

R6 integrates provider-produced candidate payloads rather than adding or changing an LLM provider. The
executor validates the selected skill contract, required context, permissions, gate, input/output shape,
and protected/fact-preservation rules before recording a candidate and Workflow execution trace. Only an
explicit accept endpoint may invoke the declared bounded commit action. R6 does not invent a later stage,
auto-chain skills, auto-accept output, or redesign the frontend.

## Invariants

- Each registered skill owns one directory with manifest, prompt, input/output schemas, validators, and
  examples. Registry startup rejects duplicate IDs, invalid contracts, and unknown validators/actions.
- A skill declares scope, required/optional context, writes, forbidden effects, validators, and commit
  action. It cannot select another skill or advance workflow.
- Context is supplied explicitly and minimized by the contract. Audience/character permissions reject
  forbidden context categories before any candidate is recorded.
- Gate evaluation is deterministic and mandatory when a gate is supplied. Blocked execution records no
  candidate or canonical write.
- Successful execution records a Workflow run/steps plus a pending candidate and impact preview. Accept
  and reject are one-way, idempotence-safe decisions; only accept performs the declared bounded commit.
- Project isolation applies to run, candidate, target artifact/block, production scope, and gate.
  Migration is additive and preserves populated R5 data.

## Progress

- [x] 2026-09-12 16:16–16:16 (+08:00) Preflight: archived accepted R5, confirmed F20 passing and the R5
  single migration head, and opened the sole active-plan slot at the final R6 boundary.
- [x] 2026-09-12 16:16–16:51 (+08:00) Slice A: implemented manifest/schema registry and ten bounded skill
  packages with startup contract validation.
- [x] completed 2026-09-12 16:51 (+08:00) Slice B: implemented context permission, gate/input/output/validator pipeline and audited pending
  candidate execution.
- [x] completed 2026-09-12 16:51 (+08:00) Slice C: implemented impact preview and explicit accept/reject with bounded no-op, block-edit, and
  production-document commit adapters.
- [x] completed 2026-09-12 16:51 (+08:00) Slice D: added additive candidate persistence, project lifecycle, migration upgrade, architecture,
  cross-layer/E2E acceptance, and durable owners.
- [x] completed 2026-09-12 16:51 (+08:00) Slice E: ran declared validation, marked the R6 feature passing via Harness, archived the plan, marked R6
  completed in the master owner, and stop with no invented next stage.

## Surprises / Discoveries

- Workflow R4 already owns run/step audit and deterministic gates; R6 should extend its public service
  boundary instead of creating a second execution log.
- Production R5 owns sequencing and semantic validation, while Artifact Core owns block revision writes;
  skill accept adapters must call those public services rather than bypassing either domain.
- The full repository check exposed historical migration tests that used floating `head` while asserting
  an old stage revision. Pinning R2-R5 tests to their named revision restored their intended evidence;
  final-head coverage remains in R6 migration tests.
- The broad backend suite passes all 430 test bodies but has one unrelated Agent OpenAI-client teardown
  error (`RuntimeError: Event loop is closed`) after a prior test leaves the singleton client bound to a
  closed loop. The isolated smoke test passes, and the task has no diff in `app/agent/chat.py`,
  `app/agent/llm.py`, or `app/agent/tools.py`; fixing that lifecycle is outside R6.
- Repository-wide format/mypy also reveal untouched baseline drift in `app/agent/chat.py`,
  `tests/unit/test_agent_service.py`, and `app/agent/tools.py`. All R4-R6-owned files pass both checks.

## Decision Log

- Treat provider output as the `candidate` input to the deterministic executor. This cleanly bounds R6
  without coupling skill correctness to one model/provider and still exercises the real contract,
  validation, audit, impact, and confirmed-write pipeline.
- Persist candidate decisions because explicit acceptance/rejection and recovery must survive sessions.

## Validation and acceptance

- Registry tests load all ten packages and reject malformed/duplicate/unknown contracts.
- API/E2E tests prove missing context, forbidden audience context, blocked gates, invalid schemas,
  fact/protected-span violations, pending candidate audit, rejection, accepted block revision, accepted
  production document, one-way decisions, and project isolation.
- Fresh/populated R5 migration preserves existing data and reaches one R6 head without drift.
- Architecture/privacy, Ruff/format, mypy, import-linter, regenerated OpenAPI/frontend typecheck, and
  `git diff --check` pass. One R6 feature becomes passing only through Harness verification.

## Outcomes / Retrospective

R6 and the finite V3 R4-R6 initiative are complete. Ten filesystem skill packages load through a
validated registry. The executor enforces scope, minimal/denied context, deterministic gates, schema,
fact preservation, and protected spans before recording a Workflow trace and pending candidate. Impact
previews are explicit, decisions survive sessions and are one-way, and accept uses only the declared
no-op, Artifact block-revision, or Production-document adapter.

Acceptance evidence: 7 recorded registry/API/migration/E2E tests and 15 architecture tests pass; a
26-test cross-stage R4-R6 regression selection passes; fresh/populated migrations reach single head
`f63c8db205a9` with no drift. All R4-R6 files pass Ruff/format and targeted mypy; all 16 import-linter
contracts pass; regenerated OpenAPI, frontend typecheck/lint/build, and `git diff --check` pass. Harness
verification changed F21 to `passing`; F19/F20 remain passing. The only broad-suite exceptions are the
explicitly recorded untouched Agent baseline issues above.

## Recovery / restart point

Follow-up 2026-09-13: the Agent baseline exceptions recorded above were addressed in
[`agent-baseline-followup.md`](agent-baseline-followup.md). Post-fix backend verification passes
432 tests, Ruff/format, mypy and all 16 import contracts. The historical loop-closed symptom was not
reproduced in the follow-up environment; the unmocked summary path and stale singleton retention were
corrected with regression coverage. New audit findings belong to the separate proposed Agent plan.

No follow-up stage exists in the V3 master plan. R4, R5, and R6 are accepted and this plan can be
archived. No unsafe or incomplete operation is in progress.
