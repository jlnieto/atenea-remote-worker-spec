## Context

The V62 attachment contract already exposes authenticated mobile aliases for
capability, multipart upload, listing, metadata and content download. A turn
request accepts a stable `clientRequestId` plus an ordered `attachmentIds`
array, and historical turns return bounded attachment metadata. The web client
implements that complete contract. Android's `AteneaApiClient` currently posts
only `{message}` and `ConversationSurface` exposes only text, microphone and
Send.

This change is client-only. It must not alter persisted attachment ownership,
worker paths, runtime, release lifecycle, project gates or retained data.

## Goals / Non-Goals

**Goals:**

- Give the native Android WorkSession conversation safe image parity with web.
- Communicate ready, blocked, uploading, selected and failed state immediately.
- Keep selection and request identity stable across uncertain submission.
- Support historical metadata plus authenticated local viewing.
- Prove API serialization, UI semantics and the real rendered Android screen.

**Non-Goals:**

- Add attachments to Rescue, Core, Home or the general Files inbox.
- Accept PDF, text, ZIP or arbitrary files in a Codex turn.
- Add camera capture, broad media/storage permissions or caller-selected paths.
- Change backend, database, AX42 services, gates, DNS, routing, preview,
  Beautips, Codex runtime or any WorkSession content.
- Publish or install an APK without a separate exact rollout authorization.

## Decisions

### 1. Reuse the existing server capability as the authority

Android reads `/api/mobile/sessions/{id}/attachments/capability` with the
existing authenticated session. The picker is enabled only for `READY`, and
the UI displays the server's concise reason and next action when blocked. The
client does not infer project eligibility, worker health or quotas and cannot
override them.

The existing server configuration remains deny-by-default and allowlists only
canonical `atenea`; shipping client code therefore grants no authority to
Beautips, legacy sessions or another project.

### 2. Use Android's system document provider without storage permission

`OpenMultipleDocuments` selects only `image/png`, `image/jpeg` and
`image/webp`. Atenea reads a content URI through `ContentResolver`, bounds the
stream before retaining it in memory and validates declared type, detected
header, non-empty size, per-file bytes, remaining session bytes and per-turn
combined bytes. It never accepts a caller filesystem path and does not request
`READ_MEDIA_IMAGES` or legacy storage permissions.

The client may retain only URI-backed preview state until upload finishes.
Uploaded server identities, not URIs or filenames, are the turn authority.

### 3. Upload sequentially with independent stable idempotency identities

Each selected image receives a UUID used as the `Idempotency-Key`. Uploads run
sequentially to bound memory and make the visible state deterministic. A
successful upload becomes a selected immutable attachment. A deterministic
validation/policy 4xx is shown directly and is never described as worker
unavailability; transport failure remains retryable with the same upload UUID.

No image bytes, local URI, filename, token or content is written to diagnostics.

### 4. Keep one stable request UUID until exact acceptance

When the pending selection first participates in Send, Android creates one
turn request UUID and posts the normalized text plus the exact ordered server
attachment IDs. The UUID and selection survive timeout, transport failure and
an uncertain response. They are cleared only when the returned conversation
contains an operator turn whose ordered attachment IDs exactly match the
submitted list. Reusing the UUID with edited text or selection is prevented in
the client and remains rejected by the server.

Text-only turns also use the additive request shape with an empty attachment
array while remaining compatible with the current server.

### 5. Integrate compact attachment state into the existing composer

One secondary paperclip action sits beside the input. Compact image rows show
thumbnail, bounded display name/size, upload/error/ready state and a remove or
retry action. Send remains the sole primary action. The state and applicable
next action are visible immediately above the composer; no new dashboard or
screen is added.

Historical turns render only metadata returned by Atenea. Tapping an item
downloads it through the authenticated API into an exact app-cache file and
opens it through the existing non-exported `FileProvider` with temporary read
permission. Failure deletes any partial file. No public URL or worker path is
introduced.

### 6. Validate data, semantics and the rendered Android surface separately

API unit tests cover JSON and multipart requests, refresh retry and bounded
binary response handling. Pure state tests cover capability, limits, stable
identities and exact accepted clearing. Compose instrumentation asserts visible
ready/blocked/upload/error/historical states and control semantics. A real
emulator/device render is captured with generated non-secret fixtures at a
390x844 viewport and inspected for hierarchy, first-viewport state, clipping,
overflow, long names/messages and the single primary Send action.

## Risks / Trade-offs

- [Large image exhausts mobile memory] -> query size first, bounded streaming
  read, hard stop at server max plus one byte, sequential upload and no bitmap
  decode at full resolution.
- [Response loss duplicates a turn] -> stable request UUID and exact server
  idempotency contract; preserve state until exact echo.
- [Selected bytes are uploaded but turn is not sent] -> retained upload remains
  governed by existing session quota/retention; the operator can retry or
  remove it from the pending turn without deleting retained ownership.
- [Client labels a policy error as network failure] -> map HTTP 4xx by status
  and server message; reserve transport wording for connection/timeouts.
- [Temporary historical download leaks] -> app-private cache, non-exported
  FileProvider, temporary grant and partial-file cleanup.
- [APK enables another project] -> client trusts only the existing server
  capability; default-off/global/project gates and canonical allowlist remain
  unchanged.

## Migration Plan

1. Establish clean synchronized programme/implementation branches and record
   live non-impact fingerprints without reading protected content.
2. Add and strict-validate this OpenSpec change.
3. Add Android API contracts and focused tests.
4. Add bounded picker/upload/submission state and focused tests.
5. Add compact composer/history UI and instrumentation fixtures.
6. Run Android unit, lint/build and real rendered visual acceptance, then run
   the relevant repository suites from clean source.
7. Build and fingerprint an APK candidate, seal sanitized evidence and publish
   only the Git branches.
8. Stop and request separate exact authorization before APK publication or
   installation; no backend/worker rollout is required.

## Open Questions

No implementation decision remains open. APK publication/installation and the
operator's first real image-bearing turn remain explicit execution gates.
