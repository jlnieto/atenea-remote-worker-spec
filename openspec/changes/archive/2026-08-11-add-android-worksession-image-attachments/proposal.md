## Why

Atenea's authenticated backend and web conversation already support governed,
idempotent WorkSession image attachments for the canonical `atenea` project,
but the installed native Android conversation can submit only text. The missing
native client contract makes the same eligible WorkSession appear attachment-
capable on web and attachment-incapable in the app.

## What Changes

- Add typed Android API models for WorkSession attachment capability, metadata,
  multipart upload, authenticated content download and image-bearing turn
  submission.
- Add a state-first image picker to the existing WorkSession composer, using
  Android's document provider without broad storage permission.
- Validate MIME type and server-advertised count/byte limits before upload,
  show compact selected-image state and allow removal before sending.
- Preserve one stable turn request UUID and the selected uploaded attachment
  identities after transport or uncertain submission failure; clear them only
  after the accepted conversation echoes the exact ordered identities.
- Render historical attachment metadata on its exact turn and allow an
  authenticated, temporary-cache open action.
- Keep Send as the sole primary action and keep all authority server-derived,
  default-off and limited by the existing canonical Atenea-only capability.
- Build and validate an immutable APK candidate, but require a separate exact
  authorization before publishing or installing it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `worksession-attachments`: Add state-first native Android selection, upload,
  durable submission and historical retrieval parity for eligible sessions.

## Impact

- Atenea repository: Android `:api` DTO/request support and `:core-console`
  WorkSession conversation state/UI/tests; no backend, database, web, worker or
  routing change.
- Android permissions: no media-library or filesystem permission is added;
  selection uses the system document provider and viewing uses the existing
  non-exported `FileProvider` cache boundary.
- Production activation: unchanged existing global gate and exact canonical
  `atenea` allowlist remain the only authority. Beautips and all other projects
  stay blocked.
- Rollout: implementation and candidate APK may be prepared now; publication
  and installation remain a separately authorized operation.
