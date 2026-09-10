# World model and perspectives

This document owns the durable design of the all-knowing world model and its perspective projections.

## Single source of truth

Entities and relationships are stored once in their complete author form. Author, character, and
audience graphs are read-time projections; no perspective-specific rows or databases are created.
This keeps corrections and later revelations attached to one stable fact.

Entity IDs, rather than names, are the reference boundary. Names and aliases are presentation and
search data and may change without rewriting references.

## Validation boundary

Writes validate strict current schemas and relationship invariants. Reads preserve unknown properties
so schema evolution does not destroy older data. Relationship endpoint and visibility-member checks
go through the entities service to preserve the module boundary.

Database foreign keys with restrictive deletion backstop service-level friendly validation. The
actual columns, indexes, and constraints are owned by ORM models and migrations.

## Perspective projection

The perspectives service owns visibility computation for both graph responses and Agent context.
Agent code must not reproduce visibility rules or retrieve hidden detail through a second path.

Character visibility includes the viewpoint character, explicitly known entities, and only relations
whose required endpoints remain visible. Audience edges likewise require visible endpoints. Returned
graph projections deliberately omit private full properties; Agent detail retrieval performs its own
request through the same perspectives boundary.

Management endpoints remain author tools. Perspective selection limits what is displayed or injected
into the Agent, not the creator's authority to repair the underlying model.
