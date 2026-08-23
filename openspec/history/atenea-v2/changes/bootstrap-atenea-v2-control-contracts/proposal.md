## Why

Atenea already has durable operations for remote AgentRuns, close recovery,
fresh sessions, attachments and previews, but their state envelopes, failure
categories, policy gates and operator next actions are not yet one V2 control
contract. Adding change, validation, review and release modules without that
foundation would duplicate retry logic and let clients infer unsafe actions.

## What Changes

- Add additive V2 control contracts for project policy, durable operation
  identity, monotonic revisions, normalized failure categories and
  server-derived next actions.
- Establish global and project gates that are disabled by default and cannot
  inherit legacy allowlists.
- Add sanitized append-only audit/evidence identities and an outbox boundary.
- Keep every legacy API and record readable while V2 is disabled.
- Define the exact precondition checks shared by all later V2 modules.

## Capabilities

### New Capabilities

- `atenea-v2-control-contracts`: Common safety and persistence contract for
  every Atenea V2 operation.

### Modified Capabilities

None.

## Impact

- Future Atenea backend schema, API and tests; no UI or worker behavior is
  enabled by this specification alone.
- Requires an expand-only migration and a separate production migration/
  deployment authorization.
- WorkSession 19 and all existing workers, projects and operations remain
  legacy and untouched.
