## Why

Atenea V2 is not production-ready merely because one happy path works. It must
prove restart, partition, capacity, disk, backup/restore, cleanup and
multi-project isolation, then onboard each project without inheriting Atenea's
permissions or creating one-off patches.

## What Changes

- Add end-to-end resilience/SLO/alerting and failure-injection acceptance.
- Extend encrypted backup/check/restore to every V2 resource.
- Prove capacity fairness and ownership-safe retention/garbage collection.
- Define a reusable project capability manifest and onboarding template.
- Require one OpenSpec and human gate per additional project.
- Define evidence required before retiring legacy execution paths.

## Capabilities

### New Capabilities

- `atenea-v2-resilience-onboarding`: Resilience, restore, capacity, project
  onboarding and legacy-retirement acceptance contract.

### Modified Capabilities

None.

## Impact

- Cross-cutting tests/runbooks/telemetry, backup policy and future project
  onboarding changes.
- Depends on M0–M8.
- Does not enable Beautips/other projects or retire any legacy component by
  itself.
