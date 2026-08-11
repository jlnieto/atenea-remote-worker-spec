## ADDED Requirements

### Requirement: Immutable eligible release candidate

A ReleaseCandidate SHALL bind an exact integrated commit, current accepted
review/validation, eligible ArtifactManifest and required provenance. Mutable,
stale or unsigned-when-required artifacts SHALL be ineligible.

#### Scenario: Candidate artifact differs from reviewed manifest

- **WHEN** any artifact/provenance digest differs
- **THEN** candidate creation or deployment is blocked before target contact

### Requirement: Read-only exact deployment plan

Atenea SHALL generate a canonical read-only DeploymentPlan containing fixed
target/service, current version, candidate, preflight, health checks,
predecessor and rollback policy.

#### Scenario: Target state changes after planning

- **WHEN** current deployed version or target fingerprint differs at confirm
- **THEN** the plan becomes stale and a new plan/authorization is required

### Requirement: Action-bound production authorization

Production deploy and manual rollback SHALL require a recent one-use privileged
authorization bound to the exact DeploymentPlan hash, action and target.

#### Scenario: Ordinary administrator access token is supplied alone

- **WHEN** no matching unconsumed step-up authorization exists
- **THEN** Atenea denies the operation without contacting the executor

### Requirement: Least-privilege production executor

The production executor SHALL accept only registered plan/operation identities,
resolve fixed runbooks and credentials internally, and reject client/Codex
commands, paths, hosts, services, endpoints, labels and credentials.

#### Scenario: Plan references an unregistered action

- **WHEN** the resolved target registry lacks the exact versioned action
- **THEN** execution blocks as policy before any connection or mutation

### Requirement: Durable deploy and exact success

Deployment SHALL be idempotent/reconciliable and SHALL become `DEPLOYED` only
after the exact target receipt and all required health results are persisted.

#### Scenario: Response is lost after service restart

- **WHEN** the target applied the candidate but Atenea timed out
- **THEN** Atenea inspects the same deployment identity and persists its
  original receipt without applying it again

### Requirement: Version-addressed rollback

Automatic or manual rollback SHALL select the exact known predecessor artifact
from the authorized plan, SHALL not rebuild mutable source and SHALL preserve
all evidence.

#### Scenario: Post-deploy health fails

- **WHEN** policy-authorized automatic rollback is part of the exact plan
- **THEN** the executor restores only that predecessor, verifies health and
  persists a rollback receipt

### Requirement: Project-by-project production enablement

Release gates SHALL remain disabled by default and initial production
enablement SHALL allow exactly project `atenea`. Legacy flags/resources SHALL
not authorize Beautips or another project.

#### Scenario: Beautips candidate is requested during Atenea canary

- **WHEN** Beautips has no separately accepted V2 release policy
- **THEN** Atenea denies planning/execution before reading its runtime or target
