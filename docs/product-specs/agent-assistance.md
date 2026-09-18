# Agent assistance product behavior

This specification owns the behavior visible to creators using project-scoped Agent conversations.

## Conversations

- A project has a persistent conversation list. The Agent home and dock use the same conversation
  pool, and the active session has a stable route.
- One response may stream at a time across the application. Closing the dock, navigating between
  project pages, or viewing another session does not silently cancel that response; explicit stop or
  project switching does.
- Responses stream reasoning and answer content separately when the provider supplies them. Token
  usage and context-capacity feedback appear when usage data is available.
- Conversation deletion requires an explicit user action and removes its messages and pending writes.
- Provider or validation failures remain visible as recoverable errors and do not erase a user message
  that was already submitted.
- Each submitted turn has a client request id and a durable server run id. Repeating the same request
  id with the same content reuses that run and does not duplicate the user or assistant message;
  reusing it for different content is a conflict.
- Stream frames carry the run id and a contiguous sequence. If a connection ends before a terminal
  frame, the client queries persisted status and resumes from its last sequence. Refreshing a session
  restores both unfinished runs and pending confirmation cards from the server.
- Stop is a server-side cancellation, not merely a closed browser connection. Completed work is
  reported as completed rather than retroactively cancelled; a cancelled or failed run keeps the
  already-saved user message. Runs interrupted by restart fail visibly and are never automatically
  replayed. Replay events are retained for the configured bounded period (seven days by default).

## Context and memory

- Every conversation belongs to one project and uses the selected author, character, or audience
  perspective.
- Model context is partitioned within that conversation by perspective and viewpoint character.
  Switching back resumes that partition's history and summary. Legacy unlabelled history and summaries
  remain available to author only. The creator's conversation-management view retains all messages;
  perspective selection is not a login or multi-user authorization system.
- World-model context and entity-name resolution expose only information visible in that perspective.
  Content retrieved from project data is treated as data, not as instructions to the Agent.
- Memory documents are project-scoped, split into editable sections, and rendered as escaped HTML.
- Their titles, directories, sections, and related Agent tools are author-only until narrower document
  permissions are explicitly supported. Graph tools still use the selected perspective.
- A stale section update is rejected instead of overwriting a newer user edit.
- Entity edits expose a version. The editor sends the version it displayed, and a stale save is
  rejected with a conflict instead of overwriting a later edit.
- Positioning and style are guide documents with at most one document of each kind per project.

## Request and tool limits

- Every model request is checked against the configured application budget, including tool contracts,
  serialized message fields, protocol allowance, and reserved output. The current estimator uses UTF-8
  bytes conservatively rather than claiming exact provider tokenization.
- Recoverable directories may be omitted with an explicit paging instruction. Guidance, summaries,
  and uncovered history are retained; if they do not fit, a visible error explains how to proceed.
- A tool batch cannot exceed the remaining execution quota. Every unexecuted call receives a quota
  result. Calls returned after tools are disabled cause a visible failure rather than extra execution.
- Long tool results have continuation references limited to the current turn and scope. Directory
  pages contain visible entries only. Reading a continuation also consumes a tool execution.
- Model-call count, total turn duration, per-tool duration, and repeated identical failures are bounded.
  SDK automatic retries are disabled; proposals are never silently retried as business writes.

## Proposed writes

- Read tools can inspect visible entities, neighborhoods, and memory sections without changing data.
- Write tools create pending operations; invoking a tool does not immediately alter the world model or
  memory documents.
- At the end of a response, pending operations appear together. The creator can select which items to
  apply or discard the proposal.
- Approval revalidates every selected item on the server, binds it to the conversation's project, and
  applies valid items through the owning domain service. One invalid item does not authorize or hide
  another item.
- The business effect and the pending operation's approved state commit in one database transaction.
  A failed decision leaves both unchanged. Repeating the same approval returns the first saved result
  and does not create the effect again; concurrent approve/reject requests allow only one decision.
- Entity and section writes carry the version actually returned by a read tool. A write request without
  that baseline is rejected and asks the Agent to reread. Artifact skill candidates retain their source
  revision and are rejected when that source is no longer current.
- Applied world-model and document changes refresh their corresponding views.
- A successful answer and its pending operations commit before rolling-summary maintenance begins.
  Every summary attempt records its version, source-message coverage, model/strategy and validation
  outcome. Summary failure is logged, leaves the previous verified version active, and leaves the
  completed answer and confirmations available.
- Summary compression never deletes or rewrites original messages. Critical constraints, decisions,
  unanswered tasks, exact references and tool failures retain links to their source messages. A damaged
  cursor is reported and recovered from a verified version or bounded original-message replay.
- Each response exposes an expandable context note: which source IDs were supplied, which recoverable
  sources were omitted, the active summary version, and whether bounded gap recovery was needed. The
  Agent can page original messages by source ID or time range only within the current conversation and
  perspective partition.
- Project long-term memory is separate from conversation summaries and memory documents. Critical user
  statements may create source-backed `proposed` candidates, but candidates do not enter another
  conversation until the creator accepts them. The UI distinguishes Agent suggestions from direct
  creator decisions and exposes source identifiers.
- Accepted memory is recalled only inside the same project and exact perspective/character partition.
  The Agent may recover a still-existing original message through the source-reading tool by an
  accepted memory ID. Character dialogue and temporary hypotheses are not promoted to global author
  preferences.
- A contradictory memory with the same subject is `disputed`; neither alternative silently wins or is
  injected as current guidance. The creator can select one alternative, which becomes accepted while
  the others become superseded. All decisions carry versions, and stale actions receive a conflict.
- Forgetting first shows the number and conversations of its sources. Confirmed forgetting redacts the
  derived memory and creates a non-content tombstone so maintenance cannot recreate it from the same
  source. Deleting a conversation removes its unaccepted single-source derivations, retains accepted
  project guidance, and preserves a multi-source derivation when another source remains. It does not
  delete separately accepted work or project documents.

## Long-term-memory acceptance

F15 is accepted only when cross-session recall, source recovery, proposed-versus-accepted separation,
project/partition isolation, explicit conflict resolution, deletion preview, and tombstone-backed
non-resurrection pass their recorded backend and frontend checks. Vector retrieval and cross-project
global preferences are not part of this behavior.
