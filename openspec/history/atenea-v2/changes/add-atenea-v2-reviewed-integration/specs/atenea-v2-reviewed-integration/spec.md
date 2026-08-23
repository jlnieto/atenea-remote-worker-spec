## ADDED Requirements

### Requirement: Exact integration eligibility

Atenea SHALL create an IntegrationPlan only for the current DevelopmentChange
source with required non-stale validation and accepted non-stale review.

#### Scenario: Validation or review is stale

- **WHEN** source or policy advanced after validation/review
- **THEN** integration planning or execution is blocked before any Git/GitHub
  mutation

### Requirement: Server-owned Git target

Atenea SHALL resolve repository, base ref, workspace branch, merge strategy,
checks and credentials from registered project/change policy. The client SHALL
NOT select them.

#### Scenario: Client supplies another base or repository

- **WHEN** an integration request contains a target outside the exact plan
- **THEN** Atenea rejects it without commit, push, PR or merge

### Requirement: Durable idempotent publication

Commit, push and PR publication SHALL be represented by a revisioned durable
operation with one exact PR identity per change and reconciliation after
unknown responses.

#### Scenario: PR creation response is lost

- **WHEN** GitHub created the exact PR but Atenea timed out
- **THEN** Atenea discovers and binds that exact PR without creating another

### Requirement: Separately authorized merge

Merge SHALL require required checks at their exact expected commits and a
separate H7 confirmation/step-up bound to the IntegrationPlan. Publication
confirmation SHALL NOT authorize merge.

#### Scenario: Check changes after confirmation plan

- **WHEN** a required check or head commit differs before merge
- **THEN** merge is blocked and a new plan/authorization is required

### Requirement: Monotonic reconciled integration close

A change/WorkSession SHALL NOT become `INTEGRATED/CLOSED` until canonical Git
delivery and the exact remote workspace `RELEASED` receipt are persisted.

#### Scenario: Worker released but Git reconciliation is incomplete

- **WHEN** the release receipt exists but Git is not proven at the merged base
- **THEN** the operation remains reconciling/blocked and does not project
  integrated close

### Requirement: Multi-change and foreign-resource non-impact

Integration of one change SHALL mutate only its registered refs, PR, session
and exact owned ephemeral resources. Other changes and foreign/ambiguous
resources SHALL remain untouched.

#### Scenario: Another open change uses the same project

- **WHEN** one change is merged and closed
- **THEN** the other change's branch, worktree, session, validation, review and
  ownership remain byte-identical
