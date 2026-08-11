## ADDED Requirements

### Requirement: Exact private review environment

Every ReviewEnvironment SHALL bind an exact DevelopmentChange, source
fingerprint, validation projection, runtime definition, allocation and worker
ownership before activation.

#### Scenario: Source or allocation differs at activation

- **WHEN** any observed source or ownership identity differs from the sealed
  review request
- **THEN** activation blocks without creating a route, listener or runtime

### Requirement: Private server-owned access

Review URLs, routes, ports and tunnels SHALL be selected by the trusted
coordinator and SHALL be private by default. Clients SHALL NOT select or expose
them publicly.

#### Scenario: Client requests a public host or port

- **WHEN** a request contains routing or listener selectors
- **THEN** Atenea rejects it before coordinator contact

### Requirement: Leased recoverable preview lifecycle

Review environments SHALL use revisioned durable states, finite lease/hard
expiry and idempotent activate/renew/stop/reconcile behavior across backend or
worker restart.

#### Scenario: Stop response is lost

- **WHEN** the coordinator stopped the exact environment but Atenea lost the
  response
- **THEN** reconciliation persists the original stop receipt and does not stop
  any other environment

### Requirement: Three-layer visible evidence

A visible change SHALL have independent data/persistence, rendered DOM and
actual visual checks, including inspected 1440x900 and 390x844 screenshots,
before the review can be ready.

#### Scenario: Primary action is below the first viewport

- **WHEN** data and DOM assertions pass but the required primary action is not
  visibly usable in the first viewport
- **THEN** review evidence fails and reports an actionable visual blocker

### Requirement: Exact human review decision

A ReviewDecision SHALL bind actor, source, validation and evidence manifest and
record `ACCEPTED` or `CHANGES_REQUESTED`. Opening a preview or passing tests
SHALL NOT create acceptance.

#### Scenario: Operator accepts an exact candidate

- **WHEN** the authenticated authorized operator confirms the displayed exact
  source/evidence
- **THEN** Atenea persists one immutable decision and returns its receipt

### Requirement: Review staleness and retention

Changing source, validation definition or required evidence SHALL mark prior
review decisions stale while preserving them and their artifacts after preview
teardown.

#### Scenario: Accepted source is edited

- **WHEN** the DevelopmentChange source fingerprint advances
- **THEN** integration is blocked until new validation and review are complete,
  while old review evidence remains readable
