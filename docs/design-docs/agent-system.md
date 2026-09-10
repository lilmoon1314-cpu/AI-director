# Agent system

This document owns the durable design of project-scoped Agent conversations, context compilation,
memory documents, and confirmed writes.

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
