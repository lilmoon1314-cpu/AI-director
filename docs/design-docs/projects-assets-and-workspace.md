# Projects, assets, and workspace

This document owns durable project isolation, cross-database asset lifecycle, and workspace state
boundaries.

## Project ownership

The route parameter is the frontend's project-context source. Leaf views compare their loaded project
with that context and reset project-scoped stores when it changes. General reference assets are the
intentional global exception and survive project switches.

The backend supports a compatibility default project. Domain writes without an explicit project bind
to that project; project-aware frontend calls supply project identity. Existing domain endpoints use a
`project_id` query dimension rather than pretending the planned path-prefixed API already exists.

The projects business layer depends only on core. Domain services validate project ownership through
the projects service and update project counters in the caller's primary-database transaction. The
projects router coordinates cross-domain deletion after proving the project is deletable, including
Artifact Core cleanup through `artifacts.service` in the primary-database transaction.

## Asset boundary

General assets are global records in the asset database. Entity asset pages are project-owned
indirectly through their source entities and are regenerated lazily from current entity data. Images
are files with database metadata, generated storage names, bounded types/sizes, and path-containment
checks.

Project deletion spans two databases and files. Primary world-model deletion is transactional; asset
cleanup is explicit, with orphan cleanup as recovery if the second store fails. Entity write paths do
not call back into assets, preserving a one-way assets-to-entities dependency.

## Frontend lifecycle

React Router owns durable navigation state. Nested views receive project identity synchronously through
Outlet context rather than waiting for a parent effect. Zustand stores own shared application state;
selectors on high-frequency graph paths avoid whole-tree rerenders.

The G6 instance is created and destroyed with its graph view. Rendering operations are serialized and
check that the instance remains alive. Perspective replacement may replace graph data; ordinary
filters and interactions use incremental visibility/state updates.
