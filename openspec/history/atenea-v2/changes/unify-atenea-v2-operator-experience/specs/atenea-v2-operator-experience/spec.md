## ADDED Requirements

### Requirement: State-first change navigation

Web and Android SHALL navigate Project → DevelopmentChanges → selected Change
and SHALL show its current phase, blocker and primary next action in the first
viewport within the initial usable state.

#### Scenario: Project has several active branches

- **WHEN** the operator opens the project
- **THEN** each change is distinguishable by human title, branch and state and
  selecting one cannot target another change's session/action

### Requirement: Server-derived actions and permissions

Clients SHALL render server-provided permissions and primary action and SHALL
NOT infer capability availability from local status combinations.

#### Scenario: Client receives an unknown action or stale revision

- **WHEN** the backend projection is unsupported or older than the operation
- **THEN** the client shows a safe refresh/unsupported state and offers no
  guessed mutation

### Requirement: One clear primary action

Each operational screen SHALL visually prioritize exactly one next action;
secondary actions and technical details SHALL not compete with it.

#### Scenario: Change is blocked by failed validation

- **WHEN** the detail screen renders that state
- **THEN** the failed check, actionable reason and valid next action are visible
  without scrolling and release/integration do not appear executable

### Requirement: Durable reconnect behavior

Clients SHALL recover accepted operations by public operation ID and latest
revision after disconnect/restart, using the original idempotency identity.

#### Scenario: App restarts after confirmation response loss

- **WHEN** the operation was durably accepted before the app stopped
- **THEN** the app shows and resumes that operation rather than creating a new
  one

### Requirement: Action-bound step-up experience

Sensitive actions SHALL display the exact plan/target, collect required step-up
and confirm only that plan. Authentication alone SHALL not silently execute it.

#### Scenario: Step-up succeeds after plan becomes stale

- **WHEN** the plan fingerprint changed before confirmation
- **THEN** the client shows that a new plan is required and no action runs

### Requirement: Responsive visual correctness

Every visible V2 change SHALL separately prove data/persistence, DOM and actual
visual output at 1440x900 and 390x844, plus relevant native Android rendering.

#### Scenario: Long identifier or error is rendered

- **WHEN** the longest supported branch, digest or actionable error appears
- **THEN** it remains readable without clipping, overlap or horizontal page
  overflow and the primary action remains usable

### Requirement: Truthful offline and disabled states

Cached/offline state SHALL be visibly stale and mutation-disabled. A backend
capability disabled by policy SHALL not appear available merely because client
code supports it.

#### Scenario: Device is offline with a previously green validation

- **WHEN** current server state cannot be confirmed
- **THEN** the UI labels the snapshot stale and does not offer merge/deploy
