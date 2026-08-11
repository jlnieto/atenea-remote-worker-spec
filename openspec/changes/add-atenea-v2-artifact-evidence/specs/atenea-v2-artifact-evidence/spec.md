## ADDED Requirements

### Requirement: Content-addressed immutable artifacts

Every V2 artifact SHALL be finalized under a server-owned storage identity and
identified by server-computed SHA-256, size and validated media type. Finalized
bytes and identity SHALL be immutable.

#### Scenario: Producer repeats finalization

- **WHEN** the same operation finalizes the same staged bytes again
- **THEN** Atenea returns the original artifact/receipt without creating a
  duplicate or rewriting bytes

### Requirement: Exact artifact provenance

An artifact SHALL identify its authorized producer, project/change, source
fingerprint, definition/toolchain revision, class, timestamps and retention
policy.

#### Scenario: Producer ownership does not match the change

- **WHEN** a producer attempts to register output for another change/session
- **THEN** the operation fails as ownership with no blob or metadata adoption

### Requirement: Canonical artifact manifests

Atenea SHALL represent a producer output as an ordered canonical manifest with
its own immutable SHA-256. Consumers SHALL reference the exact manifest rather
than discover files by time or path.

#### Scenario: Same files are reordered or metadata changes

- **WHEN** a manifest input differs in order or any canonical provenance field
- **THEN** it receives a different identity and cannot satisfy the previous
  review/release reference

### Requirement: Mediated artifact access

Clients SHALL access artifacts through authorized artifact IDs and SHALL NOT
provide or receive worker filesystem paths, credentials or arbitrary storage
URLs.

#### Scenario: Client requests an arbitrary path

- **WHEN** a download/register request contains a filesystem path or storage
  selector outside the typed contract
- **THEN** Atenea rejects it before contacting storage

### Requirement: Retention-safe teardown and garbage collection

Runtime/preview teardown SHALL preserve retained artifacts. Garbage collection
SHALL remove only expired, unreferenced and exactly owned blobs selected by a
durable dry-run plan.

#### Scenario: Blob ownership is partial or ambiguous

- **WHEN** cleanup cannot prove every required ownership and reference field
- **THEN** it skips the blob, records an ownership blocker and removes nothing

### Requirement: Artifact backup and restore

Artifact metadata, manifests and retained blobs SHALL be included in encrypted
backup/check/restore with digest verification.

#### Scenario: Isolated restore is exercised

- **WHEN** a backup is restored to an empty supported isolated target
- **THEN** every selected artifact and manifest verifies its original SHA-256
  without accessing production resources

### Requirement: Signing creates a distinct artifact

Signing or publishing an APK/package SHALL create a derived artifact with
certificate/channel provenance and SHALL NOT mutate or promote an unsigned
validation artifact implicitly.

#### Scenario: Unsigned validation APK is selected for publication

- **WHEN** no protected signing derivation and authorization exist
- **THEN** publication is blocked even if the underlying validation passed
