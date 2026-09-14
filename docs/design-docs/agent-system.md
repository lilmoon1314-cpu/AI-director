# Agent system

This document owns the durable design of project-scoped Agent conversations, context compilation,
memory documents, and confirmed writes.

For a code-level assessment of the current guarantees and their limitations, see
[the 2026-09-12 engineering assessment](agent-engineering-assessment-2026-09-12.md). Its improvement
plan is active; A supplied contracts and fault baselines, and B implements context partitioning,
request admission and execution limits. Semantic summary coverage, database-atomic version checks,
and atomic approval/effect persistence remain work for later slices.

## Context boundary

Each conversation is bound to a project. Context is assembled from stable instructions, project memory
directories/sections, a compact visible graph directory, the conversation summary, and recent messages.
Graph directories, detail lookup, neighborhood lookup, and name resolution all pass through the
perspectives service before entering a prompt.

Messages carry a server-selected `context_key`: author, audience, or character plus viewpoint ID.
Legacy messages default to author. Author summaries stay on Conversation for data-preserving
compatibility; narrow summaries use ConversationPartition keyed by conversation and context key.
Project scope is inherited from the conversation foreign key. Summary input and history both filter
the same key before compilation. Existing guide documents lack narrower permissions and therefore
remain author-only, including titles and tool errors. Creator management endpoints remain author tools.

Project and tool data is wrapped as untrusted data and tool output is bounded before prompt insertion.
Budgets, history windows, tool-call limits, model names, and provider configuration come from runtime
configuration. No vector store is used at the current project scale; directory-first lookup followed
by targeted detail retrieval is the deliberate simpler design.

The system message contains static rules only; names, titles, directories, summaries and other project
data are carried in quoted JSON data blocks with fixed delimiters in lower-trust messages. Data labels
cannot introduce structural newlines into a delimiter. These wrappers complement server-side reads;
they are not a guarantee that a language model will resist every instruction embedded in text.

`budget.check_request` accounts for serialized messages and tool schemas, per-message/protocol
allowances, and output reserve before SDK client creation, as well as at the orchestration boundary.
The UTF-8-byte fallback is intentionally conservative, not provider-exact tokenization. Each request
sets an output limit. SDK transport retries are disabled; JSON repair re-enters the same admission
boundary. A turn-local limiter shared through ContextVar counts main/summary/repair requests and bounds
elapsed time. Tool attempts are counted individually before dispatch, including failed attempts.

Compilation keeps authored guidance, summaries and all uncovered history. If necessary it omits only
recoverable directories with an explicit paging instruction; remaining overflow fails visibly rather
than silently deleting constraints. `ContextManifest` logs scope, references, dispositions and input
estimates without message bodies. Section references include versions; graph projections do not pretend
to have entity revisions that the domain does not yet expose. Full semantic coverage remains slice E.

`list_context_directory` supplies ordered visible pages. Truncated results use ToolResult metadata
inside a scope envelope and an opaque continuation stored in that turn's ToolContext. A different turn,
project or perspective cannot resolve the reference. This is a read-time snapshot cache, discarded with
the turn, not a durable memory or cross-session cache. Continuations consume normal tool quota.

## Conversation lifecycle

User messages commit before an LLM turn so provider failure does not lose authored input. Streaming is
owned by the conversation store rather than a dock component, allowing presentation to close without
aborting the response. Project switching and explicit stop are cancellation boundaries. Only one turn
streams globally at a time to prevent concurrent UI ownership of the same interaction channel.

Rolling summaries are maintenance data. A failed or empty summary leaves the prior summary and cursor
unchanged. Provider failures are translated at the Agent boundary rather than leaking SDK exceptions.
Provider streams are explicitly closed; total turn and tool timeouts abort current work without
automatically retrying pending writes. Missing final provider turns, invalid/duplicate tool-call IDs,
and tool calls after disabling tools become errors. Persistent run status and disconnect recovery are
still slice D work; a transport ending is not a durable completion guarantee.

## Memory documents

Memory is split into documents and ordered sections so an Agent or creator can read and update a bounded
piece rather than rewriting a long document. Both document and section versions support optimistic
concurrency. An explicitly stale expected version is rejected. Capturing the actual read version
and enforcing database-atomic compare-and-swap are active in slice C. Read tools store the returned
section/entity version in the current ToolContext; a write tool without that exact baseline fails and
asks for a reread. The database update includes the expected version in its `WHERE` clause, so checking
and changing the row are one operation rather than a vulnerable read-then-write pair.

World-model facts remain in entities and relationships. Memory documents hold creative guidance and
working material, not a second copy of graph facts. Dynamic document content is escaped before HTML
rendering.

## Confirmed writes

Write-tool execution only records a pending operation in the conversation transaction. Approval is a
second, explicit request. The server reconstructs typed input, overrides untrusted project identity,
resolves entity names through the visible-context boundary, and calls the owning domain service.

Approval is item-scoped: valid selected operations may succeed while invalid ones remain pending with
an explanation. A conditional pending-state update first wins the right to decide one item. Its domain
service then participates in the same caller-owned transaction without committing independently; the
business effect, stable result and approved state commit together. Failure rolls all three back. A
replayed approval returns the stored result, while an approve/reject race can commit only one outcome.
Rejection never invokes a domain write. This two-stage boundary preserves creator authority without
pausing an SSE stream for every tool call.

Entities use integer versions, memory sections use integer versions, and Artifacts use immutable
revision identities. Skill candidates save the Artifact/source revision used during generation. Skill
acceptance uses the same conditional decision and caller-owned transaction pattern across Artifact and
Production services. Stale candidates fail before replacing newer user work.

The older propose/confirm draft path remains a compatibility surface; new write capabilities use the
pending-operation path.

## Reliability contracts (introduced in A, integrated incrementally through C)

`agent/contracts.py` defines strict, immutable metadata models. Unknown fields are rejected. These are
internal contracts rather than optional policy hooks. ContextScope, ContextManifest, SourceRef metadata
and ToolResult are used by B; RunEvent and SummaryCoverage await D/E runtime integration. Passing
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

See [the executable fault matrix](../tests/agent-reliability-baseline.md). Slice A reproduced six faults
with a scripted provider and disposable database. B fixed four context/limit faults, and C converted the
remaining second-session stale write and approval-persistence fault into ordinary passing regressions.
The tests inject a transaction-boundary exception and controlled two-session interleaving; they do not
claim to simulate an operating-system process kill. UI refresh and old-stream cleanup risks remain slice
D work.

The future boundaries should explicitly distinguish permission denial, context-budget exhaustion,
tool quota exhaustion, stale-read conflict, interrupted run, and summary coverage gaps. Provider-visible
errors must omit hidden data; client-visible errors must provide a recovery action. The names are design
categories, not newly implemented HTTP/SSE error codes. An unresolved write result must never be shown
as a confirmed failure or cancellation until persisted business state has been checked.
