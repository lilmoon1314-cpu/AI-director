# ExecPlan protocol

Use an ExecPlan for work that is complex, multi-file, long-running, introduces a capability, performs
a significant refactor, or is likely to cross sessions. A small local fix should go directly from the
target code to its nearest tests. Keep only one active plan for one task unless the user explicitly
separates independent work.

## Plan ownership and structure

An active ExecPlan is the self-contained execution and recovery record for its task. A new contributor
must be able to resume from it and the linked authoritative sources without reconstructing the task
from chat history. It owns only task-local state and contains:

- **Purpose and scope:** the observable result, boundaries, relevant baselines, and explicit exclusions.
- **Progress:** coherent milestones that are independently verifiable, kept synchronized with actual
  work rather than intended or remembered work.
- **Surprises / Discoveries:** facts learned during execution that affect the remaining plan or safe
  recovery, with concise evidence.
- **Decision Log:** material task-local choices, alternatives rejected, and the reason; durable design
  conclusions must also move to their canonical owner.
- **Validation and acceptance:** the smallest sufficient checks and the evidence required to claim the
  task complete.
- **Outcomes / Retrospective:** final result, remaining limitations or blockers, and lessons that change
  how equivalent work should be planned.
- **Recovery / restart point:** the next concrete action, relevant paths or commands, worktree state, and
  any unsafe or incomplete operation that a new session must understand.

Milestones describe coherent architecture or behavior slices, not every command. Update Progress when a
milestone starts, changes materially, or completes. Update Discoveries and Decisions when the fact or
choice occurs; do not defer reconstruction until the end. If discoveries invalidate the plan, revise
the remaining milestones and record why.

## Timestamp protocol

For complex plans, every milestone or architecture slice with real execution significance records its
truthful start and completion time to minute precision with an explicit UTC offset. Use these forms:

```text
- [ ] started 2026-09-11 14:40 (+08:00) Slice A: ...
- [x] 2026-09-11 14:40–14:48 (+08:00) Slice A: ...
```

Do not guess or backfill times that were not observed, including historical stages completed before
this protocol. Obtain time alongside useful work when practical; do not create a separate model turn
only to read the clock. These timestamps let an external observer correlate cost by slice. Repository
plans do not own Codex session, rollout, or token telemetry.

## Execution, recovery, and completion

Active plans live in `docs/exec-plans/active/`. Follow the repository-wide context and validation
discipline in `AGENTS.md`; do not repeat it in each plan. Keep command output bounded, but preserve the
specific evidence needed to verify a milestone or resume a failed operation.

When context has grown substantially and much work remains, first update Progress, Discoveries,
Decisions, validation state, and the exact restart point. Then recommend continuing in a fresh session
from the active plan instead of relying on conversation history.

Before completion:

1. Reconcile every Progress item with reality and run the declared validation.
2. Move durable architecture reasoning to the relevant design doc, observable behavior to the relevant
   product spec, and machine-readable acceptance state to `feature_list.json` through its verification
   command when applicable.
3. Record Outcomes / Retrospective and a final recovery note or explicit no-follow-up state.
4. Move the plan to `docs/exec-plans/completed/` when its compact summary remains useful for future
   recovery or historical decisions; otherwise let Git retain the history.

Completed plans are cold history and are not default context. Do not create a global roadmap, progress
log, decision log, or context manifest from task-local plan material. A finite multi-stage initiative
may have one explicit master owner, but child ExecPlans still own each stage's detailed execution state.
