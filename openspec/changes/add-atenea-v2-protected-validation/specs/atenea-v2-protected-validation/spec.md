## ADDED Requirements

### Requirement: Closed server-owned validation definitions

Atenea SHALL accept only symbolic validation capabilities resolved to a
versioned server-owned definition containing fixed mediator, toolchain digest,
resource/network limits, timeouts and artifact rules. Client or repository
input SHALL NOT provide executable commands or internal selectors.

#### Scenario: Repository manifest contains shell or image override

- **WHEN** a manifest attempts to supply a command, absolute path, image,
  socket, host, port, credential or target
- **THEN** planning fails as validation/policy before a worker is contacted

### Requirement: Immutable validation plan

Each ValidationPlan SHALL bind exact change, source fingerprint, policy
revision, ordered required checks and definition revisions in an immutable
SHA-256 identity.

#### Scenario: Source changes after plan creation

- **WHEN** current source no longer matches the plan fingerprint
- **THEN** Atenea marks the plan/results stale and refuses to start or reuse
  them for readiness

### Requirement: Isolated validation authority

Validation SHALL execute through an AX42 rootless broker. Ordinary AgentRuns,
clients and the production backend SHALL NOT receive Docker/runtime sockets,
sudo, validation credentials or production network authority.

#### Scenario: Codex attempts to invoke Docker

- **WHEN** an AgentRun checks its sandbox while a validation is available
- **THEN** Docker remains unavailable there and validation remains accessible
  only through the typed Atenea capability

### Requirement: Durable validation lifecycle

ValidationRuns SHALL persist operation, remote execution, lease, revision,
progress, terminal classification and receipt, and SHALL reconcile after
backend/worker/network interruption without duplicate execution.

#### Scenario: Backend loses the completion response

- **WHEN** the broker completed a build but Atenea did not receive its response
- **THEN** Atenea inspects the same remote operation, persists its exact receipt
  and returns the original result without starting another build

### Requirement: Truthful validation outcomes

`SUCCEEDED` SHALL mean the check passed; `FAILED` that it ran and found a
candidate defect; `BLOCKED` that a meaningful check could not run. Transport,
capacity, policy and ownership SHALL remain distinct and actionable.

#### Scenario: All heavy permits are occupied

- **WHEN** an authorized heavy build is requested at capacity
- **THEN** it is durably queued or reported as capacity, not failed validation
  or worker transport failure

### Requirement: Immutable validation evidence

Every terminal run SHALL produce a canonical result and, where applicable, an
exact ArtifactManifest bound to source, definition and toolchain identities.

#### Scenario: Android build succeeds

- **WHEN** the Atenea Android profile passes
- **THEN** reports and unsigned/test APK are registered as immutable artifacts
  but no signing, publication or deployment is authorized

### Requirement: Complete visible-change verification

A visible web change SHALL separately verify data/persistence, rendered DOM and
the actual visual result at 1440x900 and 390x844 with finite Playwright
timeouts and retained sanitized evidence.

#### Scenario: DOM text exists but is clipped

- **WHEN** a locator finds expected content but screenshot inspection shows it
  clipped, overlapped, off-screen or unreadable
- **THEN** visual acceptance fails even though the DOM assertion passed
