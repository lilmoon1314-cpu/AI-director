# Narrative state core

This document owns the durable design of temporal narrative state and knowledge perspectives.

## Temporal truth

Canonical identity remains in entities and relationships. Values that change during the story belong
to Narrative State. A project-local narrative timepoint supplies their ordering coordinate; its
series, episode, scene, and beat references are optional until the Workflow domain owns those objects.

Every change appends a state event. The event records the subject and attribute, before/after values,
narrative timepoint, cause, optional compensation target, and optional screenplay artifact/revision
provenance. Historical events are not edited. A materialized current row is a reducer-owned performance
projection, not a competing source of truth: it names the last event and timepoint and increments its
version on every accepted change. An event cannot move a current value backwards in narrative order.

The R3 attribute registry is deliberately small: entity `condition` and `current_location`, plus
relationship `trust` and `resentment`. The populated-data migration backfills only existing trust and
resentment values at a project baseline timepoint. Legacy relationship columns remain compatibility
projections in R3: relation-API writes append events at the attribute's current coordinate, and temporal
event writes update the projection in the same transaction. Expanding or retiring those columns
requires a later bounded migration.

## Snapshots

A state snapshot is an immutable copy of all materialized project state for one scene/episode entry or
exit scope. It records the narrative timepoint and latest event cursor present at capture. Later events
advance current state but do not rewrite an earlier snapshot. This provides a stable continuity input
without treating snapshots as the canonical event history.

## Claims and knowledge

A claim represents author truth: subject, predicate, object, truth status, and an optional private
author note. Knowledge states never copy that author note or redefine truth. Instead they record what
one character or the audience believes at a timepoint, including uncertainty, confidence, and source.

Character knowledge requires a same-project character entity. Audience knowledge has no knower ID.
Setting a newer state supersedes the previous current row while retaining both historical rows. Thus
author, character, and audience perspectives can disagree without multiple copies of the world model.

## Boundaries

`app.narrative_state` owns the six tables and reducer rules. It validates subjects through entity or
relationship services and artifact provenance through the Artifact service. Other domains may call its
public service only. Project deletion composes Narrative State cleanup in the projects router.

R3 does not create Series/Episode/Scene/Workflow records, gate execution, compile Agent context, or
regenerate stale artifacts. Those are later-stage consumers of this core.
