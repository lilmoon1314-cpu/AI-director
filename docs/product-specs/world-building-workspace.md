# World-building workspace product behavior

This specification owns the observable behavior of the entity, relationship, graph, perspective,
and entity-reference features. Implementation details belong to code or design docs.

## World model

- A creator can create, inspect, update, delete, list, and search seven entity types: character,
  faction, location, item, skill, event, and concept.
- Entity IDs are stable after creation. Renaming an entity does not change references to it.
- Type-specific properties are validated on writes. Existing records remain readable when they
  contain properties unknown to a newer client.
- A creator can create, inspect, update, delete, and list typed relationships between entities.
- Relationship endpoints must exist in the same project. Self-links and silent duplicate
  source/target/type relationships are rejected.
- An entity that is still referenced by a relationship cannot be deleted until the reference is
  removed.

## Perspective views

- Author view shows the complete project graph.
- Character view requires a character and shows that character plus the entities and relationships
  they are allowed to know. Hidden entity names must not leak through edges or error payloads.
- Audience view shows only information marked as known to the audience, and only edges whose visible
  endpoints are also present.
- Changing perspective affects the graph display, not the creator's underlying ability to manage the
  complete world model.
- Perspective queries do not create or persist alternate copies of entities or relationships.

## Graph interaction and references

- The workspace renders entities and relationships as an interactive force-directed graph with
  zoom, drag, selection, neighborhood highlighting, type filtering, and a detail panel.
- Switching perspective refreshes the displayed graph and does not send a stale character selection
  with author or audience requests.
- Typing `@` in supported inputs searches entities and inserts a stable entity reference. Results
  indicate whether the entity is present in the current perspective view.
- Filtering or selecting graph elements changes presentation only; it does not modify stored data.

## Errors

API errors expose a stable `code`, `problem`, `cause`, `fix`, and optional `detail` structure. Raw
server tracebacks are never shown to the client.
