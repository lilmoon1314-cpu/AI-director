# Atomic Skills

An Atomic Skill is a bounded creative action described by one filesystem package: manifest, prompt,
input/output schemas, validator declaration, and example. The registry validates packages at startup and
exposes only registered IDs. Contracts declare scope, required/optional/denied context, writes, forbidden
effects, validators, and one commit action. A skill cannot invoke another skill or advance workflow.

Provider output enters the executor as a candidate. Deterministic code verifies project/scope, minimum
context, perspective permission, optional Workflow gate, input/output shape, fact preservation, and
protected spans. Only then does it create a Workflow execution run/trace and a persistent pending
candidate with an impact preview. Raw provider reasoning is not used as execution truth.

Candidate decisions survive sessions and are one-way. Reject performs no write. Accept may perform only
the contract's declared adapter: no canonical write, one Artifact block revision, or one validated
Production document. Those adapters call the owning domain service and retain their existing revision,
sequencing, dependency, stale, and project-isolation rules. No output is auto-accepted.

The initial registry covers requirement refinement, story development, scene planning, screenplay scene
writing, dialogue humanization, production breakdown, performance direction, shot planning, continuity
checking, and audience auditing. Audience audit explicitly denies future plans, hidden truth, unrevealed
character goals, writer notes, and agent scratch context.
