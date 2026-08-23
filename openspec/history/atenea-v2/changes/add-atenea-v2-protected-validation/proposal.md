## Why

Real Atenea work exposed the key gap: Codex can edit Android UI but cannot run
the repository build because Docker is intentionally unavailable inside the
AgentRun sandbox. Granting Docker to Codex is the wrong fix. The older backend
verifier also accepts repository-declared command strings across a privileged
boundary. V2 needs a separate protected validation plane.

## What Changes

- Add immutable ValidationPlans and durable ValidationRuns for closed symbolic
  checks.
- Execute builds, tests and Playwright through a fixed AX42 rootless broker,
  never through AgentRun or client-selected shell.
- Pin toolchains/images/mediators, resources, network and timeouts by server
  policy.
- Persist result classification, progress, manifests and receipts; invalidate
  results when any source/definition input changes.
- Support backend, web, Android and browser acceptance as separate checks.

## Capabilities

### New Capabilities

- `atenea-v2-protected-validation`: Safe, reproducible validation plane bound
  to exact source and artifact evidence.

### Modified Capabilities

None.

## Impact

- Future backend schema/API, AX42 validation broker/toolchains and later UI.
- Replaces the V2 path of the broad legacy project verifier but does not remove
  it in this change.
- Depends on M0–M3 and requires separate migration/worker/activation gates.
