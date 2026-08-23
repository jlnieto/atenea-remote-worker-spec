## Why

The current WorkSession flow can publish, synchronize and close after a merge,
but V2 needs integration to consume exact change validation and human review,
support several branches per project and recover safely from uncertain GitHub
responses. Integration must not be conflated with Codex completion or release.

## What Changes

- Add durable IntegrationPlans/Operations for commit, push, PR, checks, merge
  and reconciliation.
- Require current source, validation and review fingerprints.
- Bind every PR and merge to the registered DevelopmentChange branch/base.
- Reuse the proven remote close contract after integration without deleting
  retained state.
- Expose merge readiness and blockers as server-derived actions.

## Capabilities

### New Capabilities

- `atenea-v2-reviewed-integration`: Reviewed Git publication, PR, checks, merge
  and reconciled WorkSession close lifecycle.

### Modified Capabilities

None.

## Impact

- Future backend schema/GitHub integration/API and operator surfaces.
- Depends on M1–M5 and requires exact GitHub permissions and human H7 gates.
- Does not deploy production or authorize release.
