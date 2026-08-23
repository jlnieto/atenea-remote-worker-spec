## Why

Passing automated checks is not human acceptance. The operator needs to open
the exact candidate from mobile or web, inspect retained desktop/mobile
evidence and record a decision that becomes stale if the source changes.
Existing preview infrastructure provides a secure base but is WorkSession-
centric and not yet linked to a durable review decision.

## What Changes

- Add `ReviewEnvironment` bound to DevelopmentChange, source and validation
  evidence.
- Provision private, leased previews through server-owned routing.
- Add separate persistence, DOM and visual evidence requirements.
- Add immutable `ReviewDecision` for acceptance or requested changes.
- Preserve evidence after idempotent preview teardown/recovery.

## Capabilities

### New Capabilities

- `atenea-v2-private-review`: Private exact-source review environments and
  human review decisions.

### Modified Capabilities

None.

## Impact

- Future backend schema/API, AX42 preview coordinator and web/Android review
  surfaces.
- Depends on M1–M4 and remains Atenea-only/disabled until separate gates.
- Does not expose a public URL or alter existing Beautips preview state.
