# Agent baseline follow-up and engineering assessment

## Purpose and scope

Resolve only the Agent lifecycle, format, and typing leftovers recorded in the completed R6 plan.
Then inspect the implemented Agent end to end and produce a detailed Chinese engineering assessment
and a separate proposed ExecPlan. The proposed capabilities must not be implemented in this task.
Preserve all pre-existing R4–R6 worktree changes and local data.

## Progress

- [x] 2026-09-12 17:37–17:42 (+08:00) A: repaired recorded baseline failures; lifecycle regression and static checks pass.
- [x] 2026-09-12 17:42–17:49 (+08:00) B: inspected memory, context, provider loop, tools, approval, frontend lifecycle, and Atomic Skill boundaries; documented evidence and limitations.
- [x] completed 2026-09-13 10:41 (+08:00) C: delivered a proposed, unexecuted improvement plan with priorities, acceptance, and restart instructions; resumed after the user requested continuation to reconcile final documentation and formatting.

## Surprises / Discoveries

- R6 is already archived at `docs/exec-plans/completed/r6-atomic-skills.md`; its exceptions are explicitly in scope now.
- The initial worktree contains extensive existing R4–R6 changes. None are to be discarded or committed.
- Reproduced six mypy errors from `_resolve_entity_by_name` returning strings despite a bool annotation,
  and format drift in chat and service tests. Corrected without changing tool behavior.
- The service characterization test can invoke unmocked summary maintenance, unlike its mocked stream.
  Added a default summary stub and a provider-client prohibition to the service fixture. Close now clears
  its singleton before awaiting disposal; two regression cases cover successful and failed close.
- The initial broad run did not reproduce the historical loop-closed error (430 passed); therefore the
  recorded symptom is ordering/environment sensitive, not claimed as a newly reproduced failure.
  Final post-edit backend run: 432 passed, with only the existing Starlette deprecation warning.
- Full backend mypy: 87 source files pass; Ruff check and format pass; 16 import contracts pass.

## Decision Log

- Separate implemented leftover repairs from proposed improvements. Audit findings do not authorize implementation of the new plan.

## Validation and acceptance

Reproduce targeted format/type checks and investigate the client lifetime. Add a deterministic lifecycle regression,
run Agent tests and a backend-suite check when necessary to establish that the recorded ordering failure is gone.
Assessment claims must reference current code; proposed behavior must be clearly distinguished from implemented behavior.

## Outcomes / Retrospective

The recorded R6 baseline leftovers are repaired. The detailed Chinese assessment is
`docs/design-docs/agent-engineering-assessment-2026-09-12.md`; the sole remaining active-directory plan is
`docs/exec-plans/active/agent-reliability-and-memory.md`, explicitly Proposed and not authorized for execution.
The report distinguishes current capabilities, code-derived risks, and recommendations. No audit-discovered
capability was implemented, no migration or real-data operation ran, and no feature status or Git commit was changed by this task.

## Recovery / restart point

This task is complete. No unsafe operation is underway. Implementation of the proposed plan requires a
subsequent user request; begin with its A slice only after that request. Prior test evidence is recorded
above; final cleanup only normalized line endings in the changed LLM docstring.
