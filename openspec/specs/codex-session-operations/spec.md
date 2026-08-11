# codex-session-operations Specification

## Purpose
TBD - created by archiving change add-codex-session-operations. Update Purpose after archive.
## Requirements
### Requirement: Canonical source admission and draft quarantine

Every write-capable AgentRun SHALL bind an exact repository, branch, canonical
commit, mirror observation and clean WorkSession HEAD before execution. For a
new implementation the HEAD MUST equal the accepted canonical commit; merely
being its ancestor is insufficient. The canonical commit SHALL be observed and
persisted at runtime by fixed control-plane and worker mirror authorities and
MUST NOT be a self-referential compile-time constant in the observed
repository. A dirty stale WorkSession SHALL be retained as a blocked draft and
SHALL NOT be automatically rebased, merged, reset, committed, copied or
discarded.

#### Scenario: Clean WorkSession matches canonical source

- **WHEN** a write-capable run names a clean WorkSession whose exact HEAD equals the persisted canonical branch HEAD
- **THEN** the worker admits the run with that immutable source fingerprint

#### Scenario: WorkSession is behind canonical source

- **WHEN** the WorkSession HEAD is an ancestor of a newer accepted canonical HEAD
- **THEN** the write is blocked before Codex starts and Atenea offers creation of a new clean WorkSession

#### Scenario: Canonical observations differ or move

- **WHEN** the control plane and worker mirror observe different commits, the configured ref is missing, or the ref moves before admission
- **THEN** dispatch is blocked without substituting a compile-time pin or accepting an ancestor

#### Scenario: Stale WorkSession contains a draft

- **WHEN** a stale WorkSession has modified or untracked files
- **THEN** Atenea fingerprints and retains the draft unchanged and requires reviewed file-by-file porting into a new current WorkSession

### Requirement: Closed mediated validation

Atenea SHALL provide versioned symbolic operations for backend tests, web
build, Android build, Playwright acceptance, strict OpenSpec validation and
worker contract suites. Each operation SHALL bind exact WorkSession,
repository, source tree and validator ownership, use a finite timeout, retain
sanitized results and artifacts, and SHALL NOT expose a Docker socket,
arbitrary command, image, compose file, environment, path, host, slot,
endpoint or credential to the caller.

#### Scenario: Operator requests an accepted backend validation

- **WHEN** the exact WorkSession and source tree request the reviewed backend-test operation
- **THEN** the mediator runs its fixed definition with bounded authority and persists the exit status, duration and sanitized artifact manifest

#### Scenario: Caller changes validator authority

- **WHEN** a request supplies or alters a command, path, image, environment, service, slot, endpoint or foreign workspace identity
- **THEN** the mediator rejects it before starting a process or mounting a resource

#### Scenario: Validation request is repeated

- **WHEN** the same validation identity, source tree and validator revision are submitted again
- **THEN** Atenea returns or reconciles the same operation and does not start an ambiguous duplicate

### Requirement: Truthful work acceptance

Atenea SHALL represent Codex process outcome separately from validation and
integration readiness. A successful AgentRun SHALL mean only that Codex
returned a terminal result. Work SHALL remain draft, validating or blocked
until every required check for the immutable source tree passes, and SHALL
become integration-ready only after freshness and review gates also pass.

#### Scenario: Codex returns an uncompiled draft

- **WHEN** Codex exits successfully but a required build or test is missing or failed
- **THEN** the AgentRun may show process success while the WorkSession remains blocked and identifies the required next validation

#### Scenario: Source changes after validation

- **WHEN** any tracked or untracked source content changes after required checks passed
- **THEN** prior validation is invalidated and integration readiness is removed

#### Scenario: Every acceptance gate passes

- **WHEN** required builds, tests, visual checks, source freshness and review pass for one exact tree
- **THEN** Atenea marks that tree integration-ready without committing, publishing or deploying it implicitly

### Requirement: Reviewed instruction bundle

Every AgentRun SHALL persist the fingerprint and sources of a reviewed
platform/project instruction bundle. Ambient user configuration SHALL remain
excluded, but the runner MUST NOT silently ignore applicable repository
operating rules. Unknown, mutable, secret-bearing or caller-supplied rule
sources SHALL be rejected.

#### Scenario: Project has an accepted AGENTS contract

- **WHEN** Atenea resolves a platform bundle and repository-owned `AGENTS.md` for an exact source revision
- **THEN** the runner applies that immutable reviewed bundle and persists its fingerprint with the AgentRun

#### Scenario: Rule source is ambiguous

- **WHEN** rules resolve outside accepted repository/platform ownership or change after fingerprinting
- **THEN** dispatch is blocked without falling back to ignored or ambient instructions

### Requirement: Exact multi-repository authority

A cross-repository change SHALL declare each repository's exact identity,
branch, commit, mirror, WorkSession role and read/write authority. Code,
programme OpenSpec and worker source SHALL use separate owned worktrees and
validation profiles linked by one change identity. No repository or installed
root-owned file SHALL become writable merely because another repository is in
scope.

#### Scenario: Code change also requires worker and OpenSpec updates

- **WHEN** an accepted change declares all three exact repository roles
- **THEN** Atenea creates or selects separate owned worktrees and tracks validation/readiness for each component

#### Scenario: Code-only WorkSession attempts worker modification

- **WHEN** a code-only session targets the installed worker or an undeclared repository
- **THEN** the write is rejected and existing worker, repositories and services remain unchanged

### Requirement: Immutable effective Codex execution profile

Every AgentRun SHALL persist canonical `modelId`, `modelSource`,
`reasoningEffort`, `effortSource`, `catalogRevision` and `codexVersion` fields.
Model and effort SHALL resolve independently before durable dispatch using
`NEXT_TURN`, `WORK_SESSION`, `PROJECT`, `PLATFORM`, `WORKER_DEFAULT`
precedence. A settings change MUST affect only future AgentRuns and MUST NOT
rewrite execution history.

#### Scenario: Operator changes the WorkSession effort

- **WHEN** an authenticated operator changes a WorkSession from medium to high while no turn is being submitted
- **THEN** the next AgentRun persists high effort while every earlier AgentRun retains its original effective profile

#### Scenario: Next-turn override is supplied

- **WHEN** a valid next-turn model or effort override is submitted with a prompt
- **THEN** it is consumed by that AgentRun only and the WorkSession default remains unchanged

#### Scenario: Profile cannot be resolved exactly

- **WHEN** the requested model, effort, catalog revision or selected worker capability is missing, unsupported, stale or ambiguous
- **THEN** dispatch is blocked with the unsupported field and no silent model substitution occurs

### Requirement: Closed model and effort authority

Atenea SHALL expose only model identifiers and reasoning efforts advertised by
the selected compatible worker and permitted by platform/project policy. A
catalog SHALL contain canonical `schemaVersion`, `catalogRevision`, `workerId`,
`codexVersion`, `generatedAt` and `models` fields; every model entry SHALL
contain `modelId`, `displayName`, `supportedEfforts`, `defaultEffort` and
`availability`. Its revision SHALL digest the schema version, Codex version and
sorted model entries while excluding `generatedAt`. The only recognized effort
values SHALL be `none`, `low`, `medium`, `high`, `xhigh` and `max`, subject to
each model's advertised set. Friendly aliases, Pro mode and Ultra multi-agent
operation SHALL NOT become persisted model/effort values. The worker runner
SHALL derive reviewed Codex flags from validated canonical fields and SHALL NOT
accept an arbitrary provider, endpoint, configuration fragment, argument
array, path, environment value or credential.

#### Scenario: Supported profile is selected

- **WHEN** an operator selects a catalog-advertised model and one of its supported none, low, medium, high, xhigh or max efforts
- **THEN** Atenea displays the effective selection and the worker invokes Codex with exactly that validated profile

#### Scenario: Caller injects a Codex option

- **WHEN** a request includes an unrecognized effort, arbitrary model, provider, endpoint, flag or configuration value
- **THEN** Atenea and the worker reject it before starting Codex or changing persisted settings

### Requirement: Safe durable progress timeline

Atenea SHALL persist and publish monotonically sequenced, sanitized progress
events only as `ACCEPTED`, `QUEUED`, `PREPARING_WORKSPACE`, `CODEX_STARTED`,
`INSPECTING_PROJECT`, `RUNNING_COMMAND`, `CHECKING`, `WAITING`, `RECONCILING`,
`FINALIZING`, `COMPLETED`, `FAILED` or `CANCELLED`. Consecutive events with the
same category and sanitized message SHALL coalesce before sequence allocation.
Each AgentRun SHALL retain its 200 newest normalized events without sequence
reuse and SHALL always retain separate current-state, latest-event, terminal,
elapsed-time and required-next-action projections. A replay below the retained
floor SHALL return those projections and then the retained gap. Raw
chain-of-thought, model reasoning, command arguments, command output,
environment values and secret-bearing payloads MUST NOT be stored or published.

#### Scenario: Codex performs a multi-step task

- **WHEN** the worker receives accepted structured lifecycle and tool events
- **THEN** web and Android show concise stages such as preparing, inspecting, checking, waiting and finalizing in monotonic order

#### Scenario: Client reconnects after missing events

- **WHEN** a client resumes with its last persisted event sequence
- **THEN** Atenea replays the durable gap once and then continues live publication without duplicating events

#### Scenario: Event contains unsafe detail

- **WHEN** an event contains reasoning, raw command/output, credential-shaped content or an unsupported event type
- **THEN** the unsafe content is discarded and only an allowed generic state may be retained

### Requirement: Idempotent self-service recovery

An authenticated operator SHALL be able to cancel an exact non-terminal
AgentRun, request reconciliation of an exact unreachable/reconciling dispatch,
retry a safely terminal failed run and obtain a sanitized diagnostic summary.
Recovery commands SHALL be persisted, idempotent and scoped to the operator's
WorkSession.

#### Scenario: Unreachable run is reconciled

- **WHEN** an operator requests reconciliation for a persisted non-terminal dispatch
- **THEN** Atenea observes that same worker execution and does not create a replacement AgentRun

#### Scenario: Failed run is retried safely

- **WHEN** the worker proves the previous dispatch terminal or absent and the WorkSession has no non-terminal run
- **THEN** Atenea creates one new AgentRun linked to the failed run and keeps the original attempt unchanged

#### Scenario: Prior execution may still be live

- **WHEN** terminal or absent ownership cannot be proven
- **THEN** retry is rejected and Atenea presents reconciliation or privileged assistance as the next action

### Requirement: Privileged operational boundary

`ROUTINE_OPERATOR` SHALL be limited to reading the selected worker
catalog/version, changing permitted future-turn settings, and exact-owned
cancel, retry, reconciliation and sanitized diagnostics. `PRIVILEGED_OPERATOR`
SHALL additionally be able to request only policy-permitted mediated restarts
of an exact owned execution service or project App Server.
`PLATFORM_ADMINISTRATOR` SHALL additionally be able to plan, stage, separately
authorize activation and separately authorize operator-requested rollback of a
Codex release. Privileged actions SHALL use fixed mediated operations and exact
persisted ownership. No Atenea endpoint SHALL accept an arbitrary host,
service, command, slot or resource target.

#### Scenario: Routine operator requests host restart

- **WHEN** a routine WorkSession operator attempts to restart AX42, a worker service or Codex
- **THEN** the request is denied without changing platform state and the required administrator role is shown

#### Scenario: Privileged operator restarts an exact execution service

- **WHEN** policy permits a mediated restart and the complete worker/session/service identity matches
- **THEN** only the reviewed service is restarted and its persisted runs are reconciled before new dispatch

### Requirement: Managed Codex version lifecycle

Atenea SHALL expose the selected worker's installed, current and previous Codex
versions plus catalog/compatibility state. A real activation SHALL require a
separate, single-use, finite platform-administrator authorization bound to the
exact worker, current version, candidate version, release digest and plan,
zero active executions, verified release input, version-matched schema checks,
focused contracts, health and one canary. The previous verified version SHALL
remain available for exact rollback. Automatic restoration of that exact
previous version SHALL be part of the activation authority when a gate fails;
an operator-requested rollback SHALL require a new exact authorization.

#### Scenario: New Codex version is available

- **WHEN** an administrator requests a read-only update plan
- **THEN** Atenea reports current, candidate, compatibility gates and expected service impact without installing anything

#### Scenario: Active execution exists

- **WHEN** update activation is requested while any worker execution is non-terminal
- **THEN** activation is blocked and no binary, link or service changes

#### Scenario: Canary or compatibility fails

- **WHEN** schema, contract, health or canary acceptance fails after staging
- **THEN** the current version remains active or the previous verified link is restored without restarting project runtimes or unrelated slots

### Requirement: State-first cross-surface controls

Web and Android SHALL show current run state, effective model, reasoning effort,
Codex version, elapsed time, latest progress and primary next action without
scrolling. Both surfaces SHALL consume the same authorization and read model,
and errors SHALL state what happened and what the operator can do next.

#### Scenario: Run is active

- **WHEN** an AgentRun is queued, preparing, running, waiting or reconciling
- **THEN** its state and latest safe progress are immediately visible and cancel or reconciliation is the single applicable primary action

#### Scenario: Run fails safely

- **WHEN** an AgentRun reaches a retryable or administrator-required failure
- **THEN** the conversation distinguishes retry, reconcile and request-admin actions rather than showing a generic error

### Requirement: Additive persistence and disable-first rollback

Atenea SHALL introduce execution profiles, progress, recovery, generic
notifications and managed Codex updates through ordered additive migrations
after V56. Every capability SHALL remain independently disabled by default and
legacy AgentRuns and notification logs SHALL remain unchanged. Before the first
production migration, a current PostgreSQL 16 custom-format backup SHALL be
restored in a network-isolated disposable fixture, V57–V61 SHALL apply there
idempotently, and the exact application rollback image SHALL prove it can start
and read the expanded schema.

Rollback SHALL disable new update operations, dispatch/profile changes,
progress publication, recovery actions and generic notification dispatch
before changing application components. It SHALL retain expanded records and
existing affinity for audit/reconciliation and SHALL NOT down-migrate, repair
Flyway history, replay legacy notifications, rewrite profiles, delete devices
or move a WorkSession. Schema contraction SHALL require a later separately
authorized migration after zero readers/writers, retention expiry and a fresh
restore-tested backup.

#### Scenario: Current production image rejects future Flyway history

- **WHEN** the intended rollback image cannot start against the migrated isolated fixture
- **THEN** production migration is blocked until a schema-compatible image containing the additive migrations with every capability disabled passes the same fixture

#### Scenario: New capability must be rolled back

- **WHEN** an enabled profile, progress, recovery, notification or update path fails an acceptance gate
- **THEN** its gate is disabled first, affected runs are reconciled under their persisted ownership and expanded history remains intact

#### Scenario: Operator requests destructive down migration

- **WHEN** any new record may still be read, reconciled, delivered or audited
- **THEN** contraction is rejected and the disable-first expanded schema remains authoritative

### Requirement: Action-specific pre-admission recovery

A pre-dispatch remote AgentRun failure SHALL persist a stable safe failure code
and one applicable next action independently from its generic terminal progress
category. Retry SHALL be offered only when the prior execution is terminal or
absent and every deterministic admission blocker has been cleared.

#### Scenario: Closed session owns required capacity

- **WHEN** the worker identifies a blocker and Atenea proves it is an exact
  same-project, same-worker `CLOSED` WorkSession with zero non-terminal runs
- **THEN** the failed run shows `RECONCILE_REMOTE_CLOSE` and generic retry is
  unavailable until that close reconciliation succeeds

#### Scenario: Open session owns required capacity

- **WHEN** the exact blocking owner remains open or closing
- **THEN** the new run remains visibly queued or waiting with cancel available
  and no ownership is released automatically

#### Scenario: Blocking owner is foreign or ambiguous

- **WHEN** the reported owner cannot be matched exactly to the control-plane
  worker, project and WorkSession
- **THEN** the run requires platform-administrator review and neither retry nor
  cleanup is invoked

#### Scenario: Deterministic blocker was reconciled

- **WHEN** exact closed-session release succeeds and the prior dispatch is
  proven absent or terminal
- **THEN** Atenea may offer one explicit safe retry linked to the original
  failed AgentRun while preserving its turn, profile and attachments

### Requirement: Confirmed legacy remote-close reconciliation

A `PLATFORM_ADMINISTRATOR` SHALL be able to request only the fixed
`RECONCILE_REMOTE_CLOSE` operation for one selected historical remote
WorkSession. The operation SHALL require an explicit single-use finite
confirmation bound to the exact session, worker, project and read-only
ownership fingerprint. It SHALL never retry a prompt or accept an arbitrary
resource target.

#### Scenario: Exact legacy owner is confirmed

- **WHEN** the selected session is `CLOSED/UNVERIFIED_LEGACY`, every AgentRun is
  terminal and the confirmed worker ownership fingerprint still matches
- **THEN** Atenea invokes the exact workspace-release operation and records its
  receipt without changing historical session or delivery state

#### Scenario: Confirmation is stale or reused

- **WHEN** ownership changes, the confirmation expires or the same
  authorization is submitted again with different input
- **THEN** reconciliation fails before worker mutation and requires a fresh
  read-only plan

#### Scenario: Exact release preflight blocks the first confirmation

- **WHEN** the immutable operation is durably `BLOCKED` with exact
  `WORKSPACE_RELEASE_PREFLIGHT_REJECTED/OWNERSHIP`, administrative next action,
  `retryable=false`, no receipt and no worker mutation
- **THEN** only a fresh read-only plan and a new explicit single-use platform
  administrator confirmation MAY move that same operation to `RECONCILING`
- **AND** Atenea SHALL NOT create a replacement operation, automatically retry
  release, reconstruct ownership or accept a different fingerprint

#### Scenario: Reauthorized blocked operation completes

- **WHEN** the fresh confirmation still matches the exact owner and the worker
  returns the release receipt for the original operation identity
- **THEN** Atenea persists `RELEASED` and the receipt monotonically, while
  repeated confirmation returns the same result without another mutation

#### Scenario: Fresh blocked-recovery plan requires complete release preflight

- **WHEN** the immutable operation is already `BLOCKED` and the administrator
  requests another finite plan
- **THEN** Atenea first sends the complete server-derived release request for
  the original operation to the worker's non-mutating release-preflight
  endpoint and persists the plan only after the exact sanitized fingerprints
  match
- **AND** any deterministic, transport or protocol failure prevents plan
  creation with its own category and performs no release or automatic retry

#### Scenario: Routine operator requests legacy release

- **WHEN** an operator without platform-administrator authority invokes the
  action
- **THEN** Atenea rejects it and displays the required role without changing
  the session or worker

### Requirement: Remote-close state-first operator surface

Web and Android SHALL present the same persisted remote-close state, safe
reason and single primary next action in the first viewport. A deterministic
ownership or capacity failure MUST NOT appear as worker unavailability, and
raw infrastructure identities or error payloads MUST NOT be exposed.

#### Scenario: Remote close is reconciling

- **WHEN** a release request may have completed but its receipt is not yet
  reconciled
- **THEN** both surfaces show that closing is in progress and offer only wait
  or same-operation reconciliation

#### Scenario: Closed predecessor blocks a new run

- **WHEN** an exact legacy closed session retains required capacity
- **THEN** an authorized surface makes `Reconciliar cierre` the primary action
  and explains that retry will become available only afterwards

#### Scenario: Preserved run predates typed capacity recovery

- **WHEN** a remote terminal pre-dispatch AgentRun has no V63 failure or
  next-action fields and its immediate older same-project WorkSession is an
  exact canonical `CLOSED/UNVERIFIED_LEGACY` owner
- **THEN** Atenea SHALL preserve the AgentRun unchanged, obtain a read-only
  diagnosis for only that predecessor and project `Reconciliar cierre` only
  after exact worker ownership succeeds
- **AND** an unavailable, partial, foreign or ambiguous diagnosis SHALL disable
  retry and SHALL NOT discover, adopt or release another owner

#### Scenario: Capacity was released

- **WHEN** the exact release receipt is persisted and the failed dispatch is
  proven absent or terminal
- **THEN** both surfaces show `Capacidad liberada` and offer an explicit retry
  without executing it automatically

#### Scenario: Canonical source advanced before retry

- **WHEN** the failed pre-dispatch AgentRun is otherwise retry-eligible but its
  pinned commit is an exact ancestor of current canonical `main`
- **THEN** Atenea SHALL show `Código actualizado`, SHALL NOT offer or execute
  retry, and SHALL offer one `START_FRESH_SESSION` primary action only to a
  `PLATFORM_ADMINISTRATOR`
- **AND** the retained AgentRun, turn, profile and attachment binding SHALL
  remain unchanged

#### Scenario: Fresh start is repeated after response or backend loss

- **WHEN** the same operator repeats `START_FRESH_SESSION` with the same
  idempotency key
- **THEN** Atenea SHALL resume or return the same durable operation and the same
  successor WorkSession without closing or opening any additional session

#### Scenario: Exact blocked confirmation can be validated again

- **WHEN** the backend proves the complete exact blocked-operation recovery
  predicate and the operator has platform-administrator authority
- **THEN** both surfaces show `Volver a validar cierre` as the single primary
  action and require a fresh finite plan
- **AND** a stale, consumed or newly blocked confirmation disables the action
  until explicit refresh obtains another plan

#### Scenario: Confirmation target differs from the open session

- **WHEN** an operator opens a current WorkSession while a finite legacy plan
  targets a different exact closed WorkSession
- **THEN** web and Android identify both the open WorkSession and the exact
  target in the confirmation copy, identify the target again in the primary
  confirmation action and reject a plan whose target differs from the server
  state

### Requirement: Git-clean immutable reviewed instruction projection

For every real-project AgentRun, the runner SHALL validate the exact tracked
repository instruction bytes and combined reviewed bundle before execution.
Inside the execution sandbox the tracked repository instruction path MUST
contain those exact bytes, MUST be read-only to the workload and MUST NOT make
the accepted source tree appear modified. Automatic global/project instruction
discovery SHALL remain excluded through fixed runner-owned configuration, and
the exact reviewed combined bundle SHALL be injected once as developer
instructions. No caller may select a rule source, discovery setting, path,
override or instruction content.

#### Scenario: Exact new AgentRun inspects its source

- **WHEN** the runner starts Codex for a clean accepted real-project worktree
- **THEN** the sandbox sees `AGENTS.md` byte-identical to `HEAD:AGENTS.md`, Git
  remains clean and the explicit reviewed bundle is present exactly once

#### Scenario: Resumed or image-bearing AgentRun starts

- **WHEN** the runner resumes an accepted thread or supplies exact retained
  images
- **THEN** it preserves the same immutable instruction projection and does not
  enable automatic discovery, ambient rules or caller-selected configuration

#### Scenario: Workload attempts to change repository instructions

- **WHEN** the Codex process attempts to write the projected tracked
  instruction file
- **THEN** the sandbox denies the write and the host worktree blob, index,
  status and instruction SHA-256 remain unchanged

#### Scenario: Exact single-application control is unavailable

- **WHEN** the pinned Codex version cannot prove automatic discovery disabled
  while preserving the explicit reviewed bundle
- **THEN** validation blocks the candidate before installation or real dispatch
  and retains the existing worker unchanged

