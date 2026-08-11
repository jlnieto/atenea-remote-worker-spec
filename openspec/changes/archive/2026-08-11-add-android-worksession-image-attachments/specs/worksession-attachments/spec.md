## ADDED Requirements

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
