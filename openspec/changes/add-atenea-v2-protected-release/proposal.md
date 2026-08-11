## Why

Atenea must eventually deploy reviewed changes from mobile/web, but ordinary
AgentRuns and development workers must never receive production authority.
Deployment needs immutable candidates, exact preflight, recent step-up,
restricted executors, health verification and version-addressed rollback.

## What Changes

- Add `ReleaseCandidate`, immutable `DeploymentPlan` and durable
  `DeploymentOperation`.
- Build candidates only from integrated commits and eligible artifact
  manifests.
- Resolve target/service/runbook/credentials from a fixed production registry.
- Require action-bound privileged authorization before promotion or manual
  rollback.
- Persist steps, health, receipt and automatic exact-predecessor rollback.

## Capabilities

### New Capabilities

- `atenea-v2-protected-release`: Reviewed artifact promotion and rollback
  through a least-privilege production boundary.

### Modified Capabilities

None.

## Impact

- Future release schema/API, restricted production executor and operator UI.
- Depends on M1 and M3–M6; first target is Atenea only.
- No deployment, credential/configuration change or production enablement is
  authorized by this specification.
