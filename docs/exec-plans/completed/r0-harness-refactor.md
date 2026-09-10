# R0 Harness refactor — completed

## Purpose and scope

R0 reduced cold-start recovery cost by giving each durable fact one owner. It changed only repository
Harness artifacts and their supporting validation script/tests; business behavior was not changed and
historical mutation/benchmark evidence was not rerun.

## Completed work

- [x] Step A: inventoried Harness sources, consumers, enforcement, duplication, and fan-out.
- [x] Step B: assigned one target owner to each information class.
- [x] Step C: established the minimal plan protocol and machine-readable feature state.
- [x] Step D: migrated Agent and adjacent current-system knowledge into bounded product/design owners.
- [x] Step E: retired global history, constraint, test-report, and session-check rituals.
- [x] Step F: verified progressive cold-start paths, feature queries, owner routes, and machine checks.

## Durable outcomes

- `AGENTS.md` is the only always-on Agent map and defines three progressive context paths.
- `ARCHITECTURE.md` owns the current high-level system/ownership map.
- `docs/product-specs/` owns observable current behavior; `docs/design-docs/` owns durable HOW/WHY.
- `feature_list.json` owns acceptance state. `scripts/verify_feature.py` reads/writes JSON atomically,
  supports filtered queries, and validates IDs, acceptance states, and commands. It does not represent
  or constrain current task execution; that state belongs to an active ExecPlan.
- `docs/PLANS.md` defines task-local state; completed work defaults to Git unless a compact recovery
  record such as this one remains useful.
- Former global manuals and feature reports are either removed or reduced to bounded compatibility
  routes so old code/test comments do not lead to missing files or duplicate facts.
- Mutation remains an optional diagnostic in `scripts/task.py`; it is no longer a universal feature
  gate. Full repository checks are no longer session rituals.

## Historical audit evidence retained from the retired global logs

These are historical observations explaining the R0 policy change, not current gates or always-on
instructions. They were preserved without rerunning mutation or benchmark workloads:

- F04 showed mutation's value on bounded domain logic and exposed a real test-harness gap: an L1-only
  killer initially killed 41/87 mutants (47%). Adding the HTTP-level L2 path and strengthening error
  response assertions raised the useful result to 95.4%, while four documentation-only mutations were
  treated as equivalent rather than pinning prose.
- F08 showed the opposite failure mode: a broad 549-mutant scope initially produced about 50% and
  encouraged tests to bind rendering templates, declarations, ORM metadata, and exact implementation
  details. Narrowing away template/declarative noise produced a meaningful 453-mutant scope and 85.9%,
  which is evidence for risk-based mutation rather than a universal gate.
- F10's Agent milestone historically generated 1015 mutants. Two runs stalled on the same infinite-loop
  mutation in `agent/service.py`; on Windows the workload accumulated about 2109 seconds of non-progress
  before bounded test doubles converted that case into a fast failure.
- F13 produced 1174 mutants, of which 687 were classified as suspicious and required manual reassessment.
  Review confirmed those suspicious mutants had in fact been killed by the tests, producing a final 100%
  kill rate. This is evidence that mutation testing on a large orchestration module can impose substantial
  execution and human-review cost even when behavior coverage is ultimately adequate.

## Final corrective audit

- [x] Removed `active` and `--activate` from feature acceptance state. Multiple features may retain
  independent acceptance results; current task state remains solely an ExecPlan concern.
- [x] Confirmed the repository contains only root `AGENTS.md` and added a check rejecting repository-local
  nested `AGENTS.md` or `AGENTS.override.md` files.
- [x] Restored the four bounded historical mutation observations above without restoring a global log or
  mandatory mutation policy.
- [x] Checked every retained compatibility page: explicit targets exist and none route through another
  compatibility page, which also rules out routing cycles.
- [x] Confirmed `.gitignore` ignores `backend/logs/*`, so the retired error journal cannot silently return
  as a tracked runtime log.
- [x] Sampled one product behavior, design decision, acceptance status, and task-local record; each has one
  detailed owner and only summary/navigation elsewhere.

## Validation evidence

- `ruff check` and `ruff format --check` passed for changed Python Harness files.
- `backend/tests/unit/test_verify_script.py` and `backend/tests/architecture/test_harness.py`: 12 passed.
- All architecture tests: 14 passed; import-linter: 8 contracts kept, 0 broken.
- `python scripts/task.py verify --list --status not_started` returned only F15/F16.
- `python scripts/task.py verify --list --category agent` returned only F10/F13/F14/F15.
- Repository searches found no active default instruction to read global progress/decisions, run full
  checks at session boundaries, or require per-feature mutation.
- `git diff --check` reported no whitespace errors.

The pre-existing full-check baseline still has six mypy errors in `backend/app/agent/tools.py`. R0 did
not modify that business module and did not treat an unrelated full-repository failure as a blocker to
the Harness-only acceptance declared above.

## Cold-start acceptance

- Small local fix: `AGENTS.md → target code → nearest test/config`.
- Single-domain complex change: add the relevant ARCHITECTURE section, one bounded design doc, the
  relevant product spec if behavior changes, and one active ExecPlan.
- Cross-layer product behavior: start at the product spec, load only participating design docs and
  feature entries, then target code and integration/E2E evidence.

Completed plans, unrelated specs/design docs, historical reports, and the R1+ master plan are excluded
from all three default paths.
