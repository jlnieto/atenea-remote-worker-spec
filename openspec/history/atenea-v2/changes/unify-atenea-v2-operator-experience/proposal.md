## Why

V2 is only useful remotely if Android and web present the same truthful state,
make the next action obvious and recover durable operations after disconnect.
The current session-first UI cannot represent several changes/branches plus
independent validation, review, integration and release axes without unsafe
client inference or visual overload.

## What Changes

- Add a shared Project → DevelopmentChanges → Change detail information
  architecture for Android and web.
- Consume server-derived phase, blocker, permissions and one primary action.
- Add focused surfaces for session/editing, validation, review, integration and
  release without a generic dashboard.
- Add operation recovery, stale/offline handling and step-up UX.
- Require data, DOM and visual validation in desktop/mobile viewports plus
  native Android verification.

## Capabilities

### New Capabilities

- `atenea-v2-operator-experience`: Consistent state-first remote operator
  experience across web and Android.

### Modified Capabilities

None.

## Impact

- Future web and Android UI/API models and focused backend read projections.
- Depends on M0–M7; rollout of web and APK are separate gates.
- Does not enable a backend capability merely by showing its disabled state.
