# ExecPlan protocol

Use an ExecPlan only for work that is complex, multi-step, or likely to cross sessions. A
small fix should go directly from the target code to its nearest tests.

An active plan owns only the state of its task:

- purpose and scope;
- progress as a short checklist;
- discoveries needed to resume safely;
- task-local decisions and rejected alternatives;
- validation and acceptance;
- recovery or handoff notes.

Active plans live in `docs/exec-plans/active/`. Keep at most the plans for work that is
actually in progress. When the work finishes, move the plan to `docs/exec-plans/completed/`
only if its summary remains useful for future recovery; otherwise let Git retain the history.

Durable results do not stay in a completed plan. Move architecture reasoning to the relevant
design doc, observable behavior to the relevant product spec, and acceptance state to
`feature_list.json` before completion.

Do not create a global roadmap, progress log, decision log, or context manifest.
