## ADDED Requirements

### Requirement: Durable development change aggregate

Atenea SHALL represent each independent development objective as a
`DevelopmentChange` with exact project, base ref/commit, workspace branch,
workspace identity, source fingerprint and policy revision.

#### Scenario: Two changes are opened for Atenea

- **WHEN** two authorized changes are created for the same project
- **THEN** they receive distinct branches, workspaces and ownership while both
  remain independently operable

### Requirement: WorkSession isolation by change

Every new V2 WorkSession SHALL belong to exactly one DevelopmentChange, and a
change SHALL have at most one `OPEN` or `CLOSING` WorkSession while a project
may have multiple active changes.

#### Scenario: Client targets a session from another change

- **WHEN** a turn or operation identifies a session/change pair that does not
  match persisted ownership
- **THEN** Atenea returns an ownership conflict and creates no turn, run or
  remote effect

### Requirement: Server-owned branch and workspace selection

Branch refs, filesystem paths, worker, remote session and allocation SHALL be
resolved and validated by Atenea from registered policy. A client SHALL NOT
choose those internal identities.

#### Scenario: Client supplies a branch path or worker selector

- **WHEN** an otherwise valid create request includes an internal selector
- **THEN** Atenea rejects it before provisioning

### Requirement: Exact source projection and staleness

A change SHALL persist a revisioned source fingerprint. Any relevant source or
definition change SHALL make dependent validation, review and release
projections stale without deleting their records.

#### Scenario: Source changes after accepted validation

- **WHEN** the workspace fingerprint advances after validation/review
- **THEN** Atenea retains the old evidence, marks it stale and blocks
  integration until new required evidence is produced

### Requirement: Durable source reconciliation

Canonical-source advance or uncertain workspace state SHALL use a durable,
idempotent reconciliation operation and SHALL never overwrite a retained draft
or foreign resource automatically.

#### Scenario: Canonical base advances while draft is dirty

- **WHEN** Atenea detects both a retained draft and a newer canonical base
- **THEN** it reports `STALE` with a plan/next action and performs no implicit
  reset, rebase or replacement

### Requirement: Explicit legacy coexistence and binding

Legacy WorkSessions SHALL remain valid without a DevelopmentChange. Binding a
legacy session SHALL require an exact preflighted, step-up-confirmed,
idempotent operation and SHALL not change its source or ownership.

#### Scenario: Expand migration encounters WorkSession 19

- **WHEN** V2 schema/code is deployed
- **THEN** WorkSession 19 remains unbound and all its Git, turns, runs,
  attachments and remote resources remain unchanged
