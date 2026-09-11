# Artifacts constraints

- Only `screenplay` is a valid R2 artifact type.
- Artifact and block IDs remain stable across edits.
- Revision and block-revision rows are append-only after creation.
- Dependencies point source block/revision -> dependent artifact and cannot cross projects.
- Stale propagation is selected by changed block IDs and never regenerates or deletes downstream data.
- Router code does not access models/repository; cross-domain imports target service boundaries.

