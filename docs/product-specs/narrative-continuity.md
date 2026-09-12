# Narrative continuity product behavior

This specification owns observable R3 temporal-state and knowledge behavior.

## State history and continuity

- A creator can establish ordered narrative timepoints within a project.
- A creator can append a state change for a registered entity or relationship attribute. The result
  reports both the immutable audit event and the new current value/version.
- Set and transition replace a value; add and remove update list-valued state. A transition can require
  an expected current value and conflicts rather than silently overwriting a newer value.
- A change records when it happened and why. A screenplay-caused change must identify a same-project
  screenplay artifact and one of its revisions.
- Corrections append a compensating event that references the earlier event. Earlier events remain
  readable and unchanged.
- A creator can capture a scene/episode entry or exit snapshot. Later changes do not alter the captured
  values or event cursor.
- Existing relationship trust and resentment fields remain readable for compatibility. Changing either
  through the relation API appends event history, and temporal changes keep those fields synchronized.

## Truth and perspective knowledge

- A creator can record an author claim with true, false, or uncertain truth status and a private note.
- A creator can independently record what a same-project character or the audience suspects, believes,
  knows, or is misled about at a narrative timepoint.
- Audience knowledge has no character identity. Character knowledge requires a character identity.
- A newer knowledge state becomes current without deleting the earlier state.
- Knowledge responses do not expose an author's private truth note.

## Isolation and lifecycle

- Subjects, timepoints, claims, knowers, and artifact provenance cannot cross project boundaries.
- Deleting a project removes its Narrative State data along with the project's other owned data.
- R3 supports only the registered initial attributes and does not expose workflow, generation, or
  automatic stage progression.
