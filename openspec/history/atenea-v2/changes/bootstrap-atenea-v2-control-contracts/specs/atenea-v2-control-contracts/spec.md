## ADDED Requirements

### Requirement: Deny-by-default V2 capability policy

Every V2 capability SHALL require an enabled global gate and an enabled exact
project policy revision. Both SHALL default to disabled, SHALL be independent
of legacy flags and SHALL reject wildcard or client-supplied policy scope.

#### Scenario: Existing project has no V2 policy

- **WHEN** a client requests a V2 mutation for an existing project without an
  enabled exact V2 policy
- **THEN** Atenea returns a deterministic policy denial without contacting a
  worker or changing any record other than the sanitized denied audit fact

### Requirement: Durable idempotent operation identity

Every V2 mutation SHALL persist its operation identity, idempotency key,
canonical request fingerprint, target fingerprint, state and revision before
performing a remote effect. Revisions SHALL be monotonic and terminal receipts
SHALL be immutable.

#### Scenario: Response is lost after a remote effect

- **WHEN** the same authorized request is retried after the original response
  was lost
- **THEN** Atenea reconciles and returns the original operation and receipt
  without repeating the effect

#### Scenario: Idempotency key is reused for another target

- **WHEN** an existing key is supplied with a different request or target
  fingerprint
- **THEN** Atenea returns a deterministic conflict and performs no effect

### Requirement: Closed failure classification

V2 operations SHALL classify failures only as `TRANSPORT`, `CAPACITY`,
`VALIDATION`, `POLICY` or `OWNERSHIP` and SHALL expose a stable failure code and
server-derived next action.

#### Scenario: Worker returns a deterministic 4xx

- **WHEN** a worker or local preflight returns a deterministic validation,
  policy or ownership error
- **THEN** Atenea projects it immediately and does not traverse the
  worker-unavailable timeout or retry window

### Requirement: Server-owned operator action projection

Atenea SHALL derive phase, blocking reason, permissions and one primary next
action from authoritative state. Clients SHALL NOT infer or select internal
commands, paths, slots, ports, services, endpoints, images, labels,
credentials or resources.

#### Scenario: Client submits an internal execution selector

- **WHEN** a client attempts to include an internal selector not present in the
  public typed contract
- **THEN** Atenea rejects the request before persistence or remote contact

### Requirement: Sanitized append-only audit

Every accepted or denied V2 mutation SHALL produce a transactional append-only
audit fact containing identities, state, fingerprints and timings but no
prompt, response, attachment content, credential, token, cookie, Codex history
or environment dump.

#### Scenario: Operation is denied by policy

- **WHEN** a V2 operation is denied before execution
- **THEN** the denial is auditable by normalized metadata without persisting
  sensitive request content

### Requirement: Legacy coexistence

Expanded V2 schema and disabled code SHALL preserve all legacy WorkSessions,
AgentRuns, attachments, close receipts and clients without automatic backfill
or state transition.

#### Scenario: V2 schema is deployed with gates off

- **WHEN** production starts on the expanded schema with every V2 gate off
- **THEN** existing flows and WorkSession 19 remain unchanged and readable
