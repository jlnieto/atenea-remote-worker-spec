## Context

The remote-worker program already proves RAID, encrypted external backup,
slots, heavy admission, restart reconciliation and ownership-safe teardown in
individual capabilities. V2 must prove their composition and provide an
onboarding process that never turns one project's acceptance into global
authority.

Dependencies: all M0–M8 modules.

## Goals / Non-Goals

**Goals:**

- Exercise realistic failures without corrupting retained state.
- Restore metadata/artifacts/ownership in an isolated supported environment.
- Define and measure availability/recovery/capacity objectives.
- Onboard projects through a closed reusable contract.
- Retire legacy paths only after accepted observation and fallback proof.

**Non-Goals:**

- Enable all known projects as a cohort.
- Use production data in development fixtures.
- Garbage-collect ambiguous/foreign resources.
- Retire Atenea production, PostgreSQL, secrets, backups or operations.

## Decisions

### 1. Resilience matrix is release-blocking

Backend restart, worker restart, network partition, response loss,
cancellation, capacity saturation, disk pressure and restore have explicit
expected state/receipt/next-action assertions. Unclassified outcomes block
general enablement.

### 2. Restore is the backup acceptance test

Successful backup jobs are insufficient. Periodic restore to an empty isolated
target must reconstruct selected DB metadata, artifacts, Git/workspace
manifests and receipts with SHA-256 verification, without production access.

### 3. SLOs describe control-plane truth

Track queue wait, operation age, reconciliation age, capacity, disk/RAID,
backup freshness, preview expiry and deployment health. Alerts contain IDs and
states, never content.

### 4. Project capability profile

Each project onboarding selects registered build/runtime/validation/review/
release definitions, fixtures and secret names from server policy. Repository
manifests reference symbolic IDs and cannot create new authority.

### 5. One project, one change, one gate

After Atenea acceptance, Beautips and every other project get a separate
OpenSpec, live audit, threat model, canary, observation and rollback. No
wildcard/copy of allowlists.

### 6. Legacy retirement last

Legacy executor/verifier/routes are inventoried and disabled for new work
before bounded removal. Active/retained state is never migrated or deleted
implicitly; production control dependencies remain.

## Risks / Trade-offs

- [Failure tests harm live work] -> synthetic isolated resources and exact
  gates; real host reboot only under explicit authorization.
- [Restore exposes production data] -> metadata/synthetic fixtures,
  encrypted target and no production connectivity.
- [Project manifests become code execution] -> symbolic registered
  capabilities only.
- [Legacy removal removes fallback] -> disable/observe first and retain exact
  predecessor until owner accepts retirement.

## Migration Plan

1. Add telemetry/restore metadata without new project enablement.
2. Execute synthetic failure/capacity/restore suites.
3. Run an Atenea-only observation window and close every acceptance criterion.
4. Create a separate onboarding change for each selected project.
5. After all required projects prove V2 and no active dependency remains,
   propose a separate legacy-retirement change.

Rollback disables automated GC/onboarding first, preserves metrics/evidence,
restores previous policies and never changes an active/ambiguous resource.

## Open Questions

Project onboarding order after Atenea remains an operator decision. Beautips is
not implicitly next and stays disabled until selected explicitly.
