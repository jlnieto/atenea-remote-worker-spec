## Why

The current database and service enforce one open WorkSession per project.
That prevents independent work on several branches and makes conversation,
workspace and delivery lifecycle the same concept. Atenea V2 needs a durable
change aggregate while preserving existing WorkSessions and remote ownership.

## What Changes

- Add `DevelopmentChange` with exact project, base, branch, source and
  workspace identities.
- Bind new WorkSessions to one change and allow multiple changes per project,
  with one open/closing WorkSession per change.
- Add orthogonal source/execution/validation/review/integration/release
  projections and server-derived phase/next action.
- Add safe source-drift and branch-conflict handling.
- Provide an explicit disabled legacy-binding operation; never backfill
  WorkSession 19 automatically.

## Capabilities

### New Capabilities

- `atenea-v2-development-change-control`: Multi-branch durable development
  change and workspace ownership lifecycle.

### Modified Capabilities

None.

## Impact

- Future backend schema/services/APIs and later web/Android reads.
- AX42 workspace provisioning is reused through stronger change ownership; no
  runtime is activated by this change alone.
- Requires M0 and M1, expand/contract migration and separate rollout gates.
