# Atomic Skill product behavior

- Creators can inspect a finite registry of bounded creative actions and each action's scope, context,
  writes, forbidden effects, and validators.
- Executing an action requires only its declared context. Missing inputs, schema errors, locked-span or
  fact changes, blocked workflow gates, and perspective-forbidden context fail before a candidate exists.
- A successful execution shows the loaded context categories, validation result, candidate, write impact,
  and ordered execution trace without exposing provider reasoning as authoritative workflow state.
- Every result remains pending until the creator accepts or rejects it. Rejection changes no canonical
  content. Acceptance invokes only the declared bounded write and returns the committed revision/document
  reference when one exists.
- Decisions are durable and one-way; repeated or cross-project decisions fail explicitly.
- Skills do not call one another, advance stages, overwrite approved downstream content, or select a
  generation provider.
