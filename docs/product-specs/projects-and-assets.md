# Projects and assets product behavior

This specification owns observable project, navigation, and asset-library behavior.

## Projects and navigation

- The application opens on a project picker where creators can search, create, rename, enter, and
  delete projects.
- A default project preserves data created without an explicit project selection and cannot be
  deleted.
- Project routes identify the active project. Switching projects replaces project-scoped graph,
  selection, project-asset, conversation, and memory state while retaining global reference assets.
- Invalid or deleted project routes produce a recoverable error and a route back to the picker.
- Opening, creating, or switching to a project enters `overview`. The primary navigation is overview,
  creation, episodes, and reference assets. Existing graph, asset subroutes, and Agent session deep
  links remain available; the Agent dock remains accessible throughout the workspace.
- Overview shows the available planning context, a next navigation action, and explicit unavailable
  production capabilities. It never treats a saved document as approved or fabricates gate results.
- Deleting a project removes its project-scoped world-model, conversation, memory, Artifact Core, and
  entity-asset data. Shared reference assets remain available.

## Asset library

- General reference assets are shared across projects and support create, edit, delete, categorise,
  search, free-form attributes, and multiple uploaded images.
- Project assets are derived from project entities and are browsed first by entity type and then by
  entity card. Empty types provide a route to create an entity in the graph workspace.
- Asset sections have stable routes: `assets/general`, `assets/project`, and
  `assets/project/:entityType`. Invalid entity types return to the type library.
- General and project searches are independent. An empty library and a search with no matches use
  distinct, actionable states.
- General-asset editing occurs in a modal so the surrounding library remains visible.
- Asset cards display a lazy-loaded cover when available and a clear placeholder otherwise.
- Opening an asset renders a self-contained HTML page inside the application. User-controlled text
  is displayed as content, never executed as HTML or script.

## Upload and lifecycle behavior

- Only configured image formats and sizes are accepted. User filenames do not become storage paths.
- Removing an asset or image removes its owned physical file. Entity assets are regenerated when
  their source entity becomes newer than the rendered page.
