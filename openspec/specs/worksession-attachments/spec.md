# worksession-attachments Specification

## Purpose

Define immutable WorkSession-scoped attachment ownership, private content
storage, deterministic screenshot resolution, bounded validation, retention
and rollback behavior.
## Requirements
### Requirement: Immutable WorkSession attachment ownership

Every attachment SHALL be indexed under exactly one WorkSession and project
with an immutable attachment identity and MAY reference only an AgentRun owned
by that WorkSession.

#### Scenario: Operator uploads an image

- **WHEN** an authenticated operator uploads an allowed image to a WorkSession
- **THEN** Atenea registers one immutable attachment for that session and no
  other session or project can list or retrieve it

#### Scenario: AgentRun belongs to another session

- **WHEN** attachment registration names an AgentRun outside the WorkSession
- **THEN** registration fails without creating metadata or retained content

### Requirement: Split metadata and content authority

Atenea/PostgreSQL SHALL own ordered attachment metadata while AX42 SHALL store
content under an ownership-derived opaque identity. Client APIs SHALL NOT
expose or accept worker filesystem paths.

#### Scenario: Client retrieves attachment metadata

- **WHEN** an authorized client reads an attachment
- **THEN** it receives the opaque attachment identity, source, kind, media type,
  size, retention, creation time and SHA-256 identity but no host path

### Requirement: Bounded validated atomic upload

The attachment boundary SHALL reject empty, oversized, unsupported, ambiguous
or content-type-mismatched input before it becomes retained or indexed. The
default per-file limit SHALL be 16 MiB and default retained WorkSession quota
SHALL be 256 MiB. A routine operator upload SHALL be classified by Atenea as
`OPERATOR_UPLOAD`, SHALL use `SESSION` retention and SHALL derive `IMAGE` or
`FILE` from validated content; caller attempts to claim browser, trace, report
or evidence authority MUST fail closed.

#### Scenario: Oversized upload is attempted

- **WHEN** input exceeds the configured per-file or session quota
- **THEN** Atenea returns an actionable limit state and neither metadata nor
  retained content is created

#### Scenario: Declared image contains another format

- **WHEN** the declared media type does not match the validated content
- **THEN** the worker rejects it fail closed and preserves existing attachments

#### Scenario: Routine operator claims evidence authority

- **WHEN** an operator upload supplies browser, trace, report, `EVIDENCE` or
  another classification that Atenea did not derive
- **THEN** Atenea rejects it before worker storage and creates no attachment

### Requirement: Integrity and idempotency

Content SHALL be streamed to a temporary owned file, SHA-256 verified and
atomically retained. Reusing an attachment identity with identical content
SHALL return the same record; conflicting reuse SHALL change nothing.

#### Scenario: Upload response is lost

- **WHEN** Atenea retries the same attachment identity and content
- **THEN** the worker returns the original storage identity and digest without
  storing a duplicate

### Requirement: Deterministic screenshot resolution

Latest, previous and last-N screenshot references SHALL resolve only within the
requested WorkSession and optional source, ordered by creation time descending
then attachment identity descending.

#### Scenario: Two projects capture screenshots

- **WHEN** an operator requests the latest screenshot for one WorkSession
- **THEN** only that WorkSession set participates even if another project has a
  newer global filesystem timestamp

### Requirement: Authenticated scoped retrieval

Upload, listing, metadata and content retrieval SHALL require the authenticated
operator boundary and exact WorkSession ownership. Foreign and missing
identities SHALL fail without disclosing foreign storage state.

#### Scenario: Foreign session requests exact content

- **WHEN** a request presents an attachment identity owned by another session
- **THEN** the request is denied and the foreign content remains unchanged

### Requirement: Explicit retention and rollback preservation

Each attachment SHALL record `TRANSIENT` (24 hours), `SESSION` (30 days) or
`EVIDENCE` (180 days) retention. `retainUntil` SHALL be a minimum keep boundary
and SHALL prevent new turn binding after expiry, but SHALL NOT by itself
authorize deletion. Disabling creation SHALL preserve indexed content,
immutable turn bindings and authenticated retrieval. General deletion SHALL
require a later separately specified ownership, tombstone and backup policy.

#### Scenario: Attachment creation is rolled back

- **WHEN** the global or project create/bind switch is disabled
- **THEN** new uploads and new bindings are rejected actionably while retained
  authorized attachments and historical bindings remain byte-identical and
  retrievable

#### Scenario: Unbound expired image is selected

- **WHEN** an operator attempts to bind an image after its `retainUntil`
- **THEN** the new turn is rejected without changing the image, conversation or
  AgentRun state

#### Scenario: Bound failed run is retried after retention eligibility

- **WHEN** a safely failed AgentRun is retried with its immutable image
  manifest after `retainUntil` while the retained bytes still verify
- **THEN** the retry reuses the exact existing binding and does not create a new
  attachment or silently remove the image

### Requirement: Preproduction activation boundary

The capability SHALL default off globally and SHALL keep synthetic fixture
admission separate from real-project admission. Real creation SHALL require an
exact canonical project identity registered by code, present in the runtime
allowlist, pinned to the expected remote worker and snapshotted as a policy
revision on a newly created WorkSession. An unknown project or a WorkSession
that predates activation MUST remain ineligible. `atenea` SHALL be the only
real project enabled by this change.

#### Scenario: New exact Atenea session is eligible

- **WHEN** global creation and canonical project `atenea` are enabled and a new
  remote WorkSession snapshots `atenea-real-attachments-v1` on AX42
- **THEN** Atenea may expose real upload/bind readiness for that session after
  worker compatibility and quota checks pass

#### Scenario: Existing session predates activation

- **WHEN** an open Atenea WorkSession has no accepted attachment-policy revision
- **THEN** enabling the project does not retroactively permit upload or binding

#### Scenario: Foreign or unknown project is configured

- **WHEN** configuration names Beautips, another disabled project, a display
  name or an unregistered identity
- **THEN** attachment creation remains disabled for it and unknown configured
  identities fail startup without changing any session

### Requirement: Preview browser evidence ownership

Every screenshot, trace or browser report accepted for a preview SHALL be
registered through the attachment boundary under the exact preview
WorkSession, project and optional same-session AgentRun with `PLAYWRIGHT` source
and recorded preview identity. Preview teardown or expiry SHALL NOT change its
attachment ordering, integrity or retention.

#### Scenario: Browser captures desktop and mobile evidence

- **WHEN** the mediated check accepts the ready preview at both required
  viewports
- **THEN** each retained artifact is indexed only under the originating
  WorkSession and optional AgentRun and remains byte-identical after route
  teardown

#### Scenario: Foreign AgentRun is supplied

- **WHEN** preview evidence names an AgentRun owned by another WorkSession
- **THEN** attachment registration and preview acceptance fail without
  retaining content or modifying the foreign run

### Requirement: Sanitized database lifecycle evidence

Database lifecycle acceptance SHALL register only sanitized command summaries,
ownership manifests, integrity hashes and restore assertions as WorkSession
evidence. Raw snapshots, dumps, row values, database credentials, connection
strings, environment captures and secret files MUST NOT be attachments.

#### Scenario: Snapshot acceptance is retained

- **WHEN** a synthetic database snapshot and restore passes
- **THEN** the WorkSession may retain its sanitized engine, revision, size,
  SHA-256 and result report without retaining raw database content

#### Scenario: Raw dump is offered as an attachment

- **WHEN** an upload is identified as a database dump, row export, credential
  file or connection configuration
- **THEN** attachment registration rejects it before retaining content or
  metadata

### Requirement: Immutable image-bearing turn submission

An image-bearing operator turn SHALL carry a client request UUID and an ordered
list of one to four distinct WorkSession attachment UUIDs totalling no more
than 32 MiB. Atenea SHALL validate same project, WorkSession, worker, remote
session, workspace, real storage scope, non-expired new-binding eligibility,
image kind, PNG/JPEG/WebP media type, size and SHA-256 before atomically
creating the visible turn, immutable bindings and AgentRun attachment manifest.

#### Scenario: Image-bearing turn is accepted

- **WHEN** an eligible operator submits a message with two valid ordered images
- **THEN** one visible turn and one AgentRun commit with the same two immutable
  bindings and one canonical attachment-manifest SHA-256 before dispatch

#### Scenario: Accepted submission response is lost

- **WHEN** the client repeats the same request UUID, normalized message and
  ordered image identities after a timeout
- **THEN** Atenea returns the original turn and AgentRun without another binding,
  dispatch or Codex turn

#### Scenario: Submission identity is reused with different content

- **WHEN** the same client request UUID carries a different message, image,
  order or attachment manifest
- **THEN** Atenea returns conflict and preserves the first submission unchanged

#### Scenario: One selected image is foreign or altered

- **WHEN** any selected identity belongs to another session/project/worker,
  exceeds a bound, is duplicated, expired for new binding, is not an image or
  no longer matches retained integrity
- **THEN** the entire turn fails before persistence or dispatch and every
  attachment remains unchanged

### Requirement: State-first web screenshot composition

The web conversation SHALL present attachment readiness and the next action in
the existing composer without adding a competing dashboard. When ready, file
selection and image clipboard paste SHALL use the same bounded upload path, a
successful image SHALL become selected for the next message, and compact
selected-image controls SHALL permit removal before submission. Send SHALL
remain the sole primary action.

#### Scenario: New Atenea session is ready

- **WHEN** capability, project, session, worker and quota checks pass
- **THEN** the operator sees one secondary attach action, accepted image limits,
  selected-image state and the primary Send action without scrolling past the
  current execution state

#### Scenario: Capability is blocked

- **WHEN** the global gate, project gate, session policy, worker or quota blocks
  creation
- **THEN** the composer disables or omits the upload affordance and displays one
  concise reason plus the applicable next action instead of allowing a doomed
  upload

#### Scenario: Submit outcome is uncertain

- **WHEN** upload succeeded but turn submission fails or times out without an
  accepted response
- **THEN** the selected images and stable client request UUID remain available
  for safe retry and are cleared only after Atenea confirms acceptance

#### Scenario: Accepted historical turn is rendered

- **WHEN** the conversation reloads after an image-bearing turn
- **THEN** it shows bounded attachment metadata and authenticated download for
  that exact turn without embedding bytes, worker paths or storage identities

### Requirement: State-first native Android image composition

The native Android WorkSession conversation SHALL read the authenticated
server attachment capability and present `READY` or the exact actionable
blocked state in the existing composer. When ready, it SHALL offer one
secondary system-picker action for PNG, JPEG and WebP images, SHALL enforce the
server-advertised file/session/turn limits before upload and SHALL keep Send as
the sole primary action. It MUST NOT request broad storage permission, accept a
client filesystem path or infer project/worker authority.

#### Scenario: Eligible Atenea session is ready

- **WHEN** the server capability for the current WorkSession is `READY`
- **THEN** the first relevant viewport shows the secondary attach action,
  limits, pending selection state and the primary Send action

#### Scenario: Capability is blocked

- **WHEN** the global/project/session/worker/quota capability is `BLOCKED`
- **THEN** the native composer disables the picker and shows the exact concise
  reason plus next action without attempting upload

#### Scenario: Selected image violates a bound

- **WHEN** a picked item is empty, unsupported, content-mismatched, too large
  or would exceed count/session/turn bytes
- **THEN** Android rejects it locally with an actionable validation state and
  uploads no bytes or metadata

#### Scenario: Non-Atenea project is opened

- **WHEN** Beautips, another project or a legacy-ineligible session returns a
  blocked capability
- **THEN** Android grants no attachment affordance or fallback authority and
  leaves the project and WorkSession unchanged

### Requirement: Durable native image-bearing turn submission

Android SHALL upload selected images with independent stable idempotency UUIDs
and SHALL submit their exact ordered server attachment UUIDs with one stable
turn `clientRequestId`. Upload SHALL be sequential and memory-bounded. The
pending message, ordered selection and request identity SHALL survive
transport failure or uncertain response and SHALL clear only after the server
returns an accepted operator turn containing the exact ordered identities.

#### Scenario: Image-bearing turn is accepted

- **WHEN** the operator sends text with one to four successfully uploaded
  images and Atenea returns the matching accepted turn
- **THEN** Android clears the draft selection and request identity exactly once
  and renders the bound images on that historical turn

#### Scenario: Turn response is lost

- **WHEN** the request may have been accepted but Android receives a timeout or
  transport failure
- **THEN** the exact message, attachment order and client request UUID remain
  available for a safe retry without re-upload

#### Scenario: Deterministic request is rejected

- **WHEN** Atenea returns a validation, policy, authorization, ownership or
  conflict 4xx
- **THEN** Android shows that category directly and does not route it through a
  worker-unavailable retry window

#### Scenario: Operator changes an uncertain request

- **WHEN** a prior image-bearing submission has an uncertain outcome
- **THEN** Android prevents mutation of its message/order under the same UUID
  and requires exact retry or explicit draft reset without deleting retained
  attachments

### Requirement: Authenticated native historical attachment viewing

Android SHALL render bounded attachment metadata only on the exact historical
turn returned by Atenea. An explicit open action SHALL download through the
authenticated API into app-private temporary cache and expose it only through
the existing non-exported `FileProvider` with a temporary read grant. Partial
or failed downloads SHALL leave no file, and diagnostics/evidence SHALL retain
no attachment bytes, URI, content, credential, user filename or worker path.

#### Scenario: Historical image is opened

- **WHEN** the operator taps an attachment on an accepted historical turn
- **THEN** Android authenticates the exact session/attachment download, writes
  one bounded private cache file and delegates viewing with temporary read
  permission

#### Scenario: Historical download fails

- **WHEN** transport, authentication, ownership or integrity retrieval fails
- **THEN** Android shows an actionable error, removes partial cache output and
  leaves retained server ownership unchanged

#### Scenario: Conversation reloads without opening content

- **WHEN** Android reloads an image-bearing conversation
- **THEN** only metadata is rendered and no attachment content is downloaded
  implicitly
