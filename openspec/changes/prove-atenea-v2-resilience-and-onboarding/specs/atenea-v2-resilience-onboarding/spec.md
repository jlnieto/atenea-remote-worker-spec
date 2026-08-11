## ADDED Requirements

### Requirement: Composed resilience acceptance

Atenea V2 SHALL define and pass bounded backend restart, worker restart,
network partition, response loss, cancellation, capacity and disk-pressure
scenarios for every durable operation family before general enablement.

#### Scenario: Failure outcome is not classifiable

- **WHEN** a scenario cannot prove one durable state, receipt and next action
- **THEN** the affected capability remains disabled and the programme does not
  claim resilience acceptance

### Requirement: Restore-proven backup

Backup acceptance SHALL require encrypted backup/check plus restore to an empty
supported isolated target with SHA-256 verification of selected metadata,
artifacts and receipts.

#### Scenario: Backup succeeds but restore digest differs

- **WHEN** any selected restored item fails its identity check
- **THEN** backup readiness fails and no project allowlist is expanded

### Requirement: Sanitized operational SLOs

Atenea SHALL measure and alert on queue wait, operation/reconciliation age,
capacity, disk/RAID, backup freshness, preview expiry and deployment health
using content-free metadata.

#### Scenario: Reconciliation exceeds its objective

- **WHEN** a durable operation remains reconciling beyond the configured
  server-owned threshold
- **THEN** Atenea emits an actionable alert with operation/target identity but
  no prompt, response, attachment content or secret

### Requirement: Ownership-safe retention and garbage collection

Garbage collection SHALL use a durable dry-run plan and remove only expired,
unreferenced, exactly owned resources. Active, retained, foreign or ambiguous
resources SHALL be preserved.

#### Scenario: Excluded allocation is encountered

- **WHEN** an allocation is not owned by the exact cleanup plan
- **THEN** it remains byte-identical and cleanup records an ownership skip

### Requirement: Symbolic project capability profile

Each onboarded project SHALL use a reviewed versioned profile of registered
source, validation, runtime, review and release capabilities. Repository or
client data SHALL NOT introduce executable authority.

#### Scenario: New project references an unknown capability

- **WHEN** its manifest requests an unregistered definition or secret/target
- **THEN** onboarding fails before workspace, runtime or credential access

### Requirement: Independent project enablement

Every project after Atenea SHALL require a separate OpenSpec, threat model,
fixtures, canary, observation, rollback and exact H12 allowlist authorization.

#### Scenario: Atenea V2 is fully accepted

- **WHEN** another project has no separately accepted onboarding
- **THEN** all its V2 gates remain disabled regardless of Atenea or legacy
  project flags

### Requirement: Evidence-gated legacy retirement

Legacy execution paths SHALL be disabled for new work and observed before any
bounded removal, and active/retained state SHALL never be migrated or deleted
implicitly.

#### Scenario: Legacy dependency or active state remains

- **WHEN** inventory cannot prove a component unused and recoverable
- **THEN** retirement blocks and the component/state remains intact
