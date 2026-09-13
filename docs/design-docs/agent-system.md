# Agent system

This document owns the durable design of project-scoped Agent conversations, context compilation,
memory documents, and confirmed writes.

For a code-level assessment of the current guarantees and their limitations, see
[the 2026-09-12 engineering assessment](agent-engineering-assessment-2026-09-12.md). Its improvement
plan is active; slice A supplies internal contracts and reproducible fault baselines, without runtime
integration yet. In particular, summary coverage, cross-perspective history isolation,
database-atomic version checks, and atomic approval/effect persistence are not yet complete guarantees.

## Context boundary

Each conversation is bound to a project. Context is assembled from stable instructions, project memory
directories/sections, a compact visible graph directory, the conversation summary, and recent messages.
Graph directories, detail lookup, neighborhood lookup, and name resolution all pass through the
perspectives service before entering a prompt.

Project and tool data is wrapped as untrusted data and tool output is bounded before prompt insertion.
Budgets, history windows, tool-call limits, model names, and provider configuration come from runtime
configuration. No vector store is used at the current project scale; directory-first lookup followed
by targeted detail retrieval is the deliberate simpler design.

## Conversation lifecycle

User messages commit before an LLM turn so provider failure does not lose authored input. Streaming is
owned by the conversation store rather than a dock component, allowing presentation to close without
aborting the response. Project switching and explicit stop are cancellation boundaries. Only one turn
streams globally at a time to prevent concurrent UI ownership of the same interaction channel.

Rolling summaries are maintenance data. A failed or empty summary leaves the prior summary and cursor
unchanged. Provider failures are translated at the Agent boundary rather than leaking SDK exceptions.

## Memory documents

Memory is split into documents and ordered sections so an Agent or creator can read and update a bounded
piece rather than rewriting a long document. Both document and section versions support optimistic
concurrency. A patch based on an older version fails; user edits are never silently overwritten.

World-model facts remain in entities and relationships. Memory documents hold creative guidance and
working material, not a second copy of graph facts. Dynamic document content is escaped before HTML
rendering.

## Confirmed writes

Write-tool execution only records a pending operation in the conversation transaction. Approval is a
second, explicit request. The server reconstructs typed input, overrides untrusted project identity,
resolves entity names through the visible-context boundary, and calls the owning domain service.

Approval is item-scoped: valid selected operations may succeed while invalid ones remain pending with
an explanation. Section operations recheck their captured version. Rejection changes pending state but
never invokes a domain write. This two-stage boundary preserves creator authority without pausing an SSE
stream for every tool call.

The older propose/confirm draft path remains a compatibility surface; new write capabilities use the
pending-operation path.

## Reliability contracts (slice A; not yet wired into runtime)

`agent/contracts.py` defines strict, immutable metadata models. Unknown fields are rejected. These are
internal contracts rather than new API promises, persistence tables, or optional policy hooks. Passing
their validation does not prove that a source exists, that its content is visible, or that a summary
is semantically accurate. The participating services must supply and verify those facts at runtime.

- `ContextScope` identifies one exact project/perspective/character partition. Character scope requires
  a character ID; other scopes forbid it. Future history, summary, memory, and retrieval paths use the
  same boundary. Existing unlabelled content must default to author-only access during migration.
- `SourceRef` identifies an original message or a versioned section/entity/artifact revision. Read
  boundaries, not model-generated metadata, supply versions. Derivation must preserve these references
  through summaries, tool results, and proposed writes; references never grant access themselves.
- `ContextManifest` records included/omitted/denied sources and selection reasons, the estimator name,
  total request input, output reserve, and capacity. It rejects required omissions, cross-partition
  included fragments, and declared overflow. Runtime accounting must also include system rules,
  tool schemas, protocol overhead, and every subsequent completion/repair/summary request.
- `ToolResult` separates successful content from error codes and retryability. Truncation requires an
  explicit continuation. A continuation must later be resolved under the same scope and source version;
  a string token by itself is not authorization. Unknown write outcomes must be queried, not retried.
- `SummaryCoverage` checks an exact ordered source range and its last-source cursor. A failed check
  cannot authorize cursor advancement. Source existence, old-cursor continuity, exact-value retention,
  and human evaluation of semantic quality remain separate runtime checks for slice E.

### Run and confirmation state are separate

The proposed chat run transitions are `queued → running → completed | failed | cancelled`;
queued runs may also fail or be cancelled before starting. A completed run means the answer and pending
operations have committed. It does not mean the pending business writes have been accepted. Confirmation
keeps its own pending/approved/rejected state, avoiding a run that appears unfinished indefinitely while
the author considers a proposal. Workflow creative-stage runs remain separate objects.

`RunEvent` requires a stable run ID and contiguous positive sequence numbers. Running events may repeat;
terminal outcomes cannot be rewritten. A replay carries original IDs/sequence numbers: consumers
deduplicate already seen events and query persisted status when a gap or EOF occurs. Cancellation after
completion reports completion rather than claiming rollback. Persistence, idempotent turn creation,
restart reconciliation, cancellation, and event replay are work for slice D; the current SSE loop does
not yet implement them.

### Baseline evidence and intended failure semantics

See [the executable fault matrix](../tests/agent-reliability-baseline.md). Slice A reproduces six faults
with a scripted provider and disposable database, including a second-session user edit and an exception
between the domain write and approval-state persistence. It does not claim to reproduce an OS process
crash or simultaneous SQL compare-and-swap race. UI refresh and old-stream cleanup risks currently have
static evidence only and require store integration tests in slice D.

The future boundaries should explicitly distinguish permission denial, context-budget exhaustion,
tool quota exhaustion, stale-read conflict, interrupted run, and summary coverage gaps. Provider-visible
errors must omit hidden data; client-visible errors must provide a recovery action. The names are design
categories, not newly implemented HTTP/SSE error codes. An unresolved write result must never be shown
as a confirmed failure or cancellation until persisted business state has been checked.
