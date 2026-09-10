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

## Context and memory

- Every conversation belongs to one project and uses the selected author, character, or audience
  perspective.
- World-model context and entity-name resolution expose only information visible in that perspective.
  Content retrieved from project data is treated as data, not as instructions to the Agent.
- Memory documents are project-scoped, split into editable sections, and rendered as escaped HTML.
- A stale section update is rejected instead of overwriting a newer user edit.
- Positioning and style are guide documents with at most one document of each kind per project.

## Proposed writes

- Read tools can inspect visible entities, neighborhoods, and memory sections without changing data.
- Write tools create pending operations; invoking a tool does not immediately alter the world model or
  memory documents.
- At the end of a response, pending operations appear together. The creator can select which items to
  apply or discard the proposal.
- Approval revalidates every selected item on the server, binds it to the conversation's project, and
  applies valid items through the owning domain service. One invalid item does not authorize or hide
  another item.
- Section writes retain optimistic-concurrency protection through approval. Applied world-model and
  document changes refresh their corresponding views.

## Planned acceptance

`feature_list.json` records future acceptance intent for long-term/global memory. This document does
not describe that behavior as implemented until its feature has been objectively verified.
