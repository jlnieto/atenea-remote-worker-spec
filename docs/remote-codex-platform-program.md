# Remote Codex Platform Programme

## Authority and status

This document is the durable programme ledger for moving Atenea development execution to a dedicated remote worker.

- Programme: `remote-codex-platform`
- Foundation change: `establish-remote-codex-platform-program`
- Current phase: `complete-remote-worksession-close-lifecycle` completed,
  live-accepted and archived; AgentRun 96 remains retained and explicitly will
  not be retried, while current-code work continues from empty WorkSession 19
- Runtime routing: exact canonical Atenea and Beautips project routes are
  enabled; generic project routing and every unrelated project remain disabled
- Production/control plane: current Atenea VPS
- Development/execution plane: Hetzner AX42; Atenea WorkSessions 16 and 17 are
  closed with exact durable `RELEASED` receipts, WorkSession 19 is open and
  empty on current canonical code, and Beautips retains its accepted slot-4
  WorkSession while the administrative slot-1 stack remains foreign
- Canonical source: GitHub
- Last evidence refresh: 2026-08-11

The normative requirements live in OpenSpec. This ledger records phase state, decisions, evidence locations and the exact resume point. Code, tests and migrations remain authoritative for existing Atenea runtime behaviour.

## Objective

Move all repository development and Codex execution initiated through Atenea to
the AX42 without coupling work to the operator laptop. The platform must support
up to four bounded concurrent project sessions, preserve the trusted Codex
workflow, and make manual and automated browser verification available from
laptop and mobile without publishing development services. The Atenea server
remains the production and control plane, not a general development executor.

## Programme invariants

1. Atenea remains authoritative for `Project`, `WorkSession`, `SessionTurn`, `AgentRun`, delivery and operator access.
2. An open WorkSession is pinned to one execution target and one session-owned workspace.
3. No more than one AgentRun executes per WorkSession.
4. The first worker admits at most four normal sessions and at most two heavy operations by default.
5. Each session owns an isolated Git worktree and runtime namespace.
6. Codex does not receive the host Docker socket, host root filesystem or unrelated workspaces.
7. Worker API, Codex App Server and previews are private by default.
8. Client disconnection does not cancel a durably accepted run.
9. Restart recovery reconciles worker state before declaring a remote run failed.
10. Active sessions are never moved implicitly during rollout or rollback.
11. Authentication and project secrets are not copied as ordinary repository files.
12. RAID availability is complemented by external backup and restore evidence.
13. GitHub remains the canonical source for repository code; worker mirrors and worktrees are execution state, not a replacement remote.
14. Atenea production, its PostgreSQL, secrets, backups, monitoring and deploy/rollback authority remain on the Atenea server.
15. Builds, Codex, project runtimes, development databases, Playwright, previews, repositories and worktrees belong on the AX42 after their migration gates pass.
16. “Latest screenshot” and related image references resolve only inside the current WorkSession attachment set.
17. Database replacement requires explicit confirmation and is permitted only for development databases.
18. Production deployment is a separate governed workflow using a reviewed versioned artifact, restricted credentials, confirmation, health checks and rollback; normal Codex execution cannot deploy directly.

## Scope

Included:

- secure AX42 worker baseline;
- private network between Atenea, worker, laptop and mobile;
- durable worker dispatch and reconciliation;
- session worktrees and runtime manifests;
- compatible `dev` CLI;
- four-slot scheduling and resource policy;
- private previews, SSH tunnels and Playwright artifacts;
- WorkSession-scoped attachments and deterministic screenshot resolution;
- Codex instruction, skill and toolchain parity;
- development relocation and onboarding for Atenea itself;
- onboarding Yvateve, Beautips, ISC, Recambios, Fomasys and Checkpol;
- isolated development databases and confirmed development-only refresh;
- controlled production deployment from versioned artifacts;
- monitoring, backups, cleanup, capacity and rollback.

Excluded:

- moving Atenea PostgreSQL, web or mobile APIs to the worker;
- giving ordinary Codex runs production deployment or production database credentials;
- local model inference;
- Kubernetes or a general CI product;
- multiple simultaneous open WorkSessions for one project;
- automatic reconciliation of uncommitted laptop work;
- public development hosting by default.

## Current and target topology

### Current

```text
Laptop
  ├─ trusted Codex configuration
  ├─ dev + local runtimes + browser
  └─ must remain online for local work

Atenea VPS (4 vCPU / 8 GB)
  ├─ public web + Android APIs
  ├─ PostgreSQL prod/preview
  ├─ repositories
  ├─ Codex App Server prod/preview/rescue
  └─ execution coupled to control-plane lifetime

AX42
  ├─ four prepared rootless runtime slots
  ├─ administrative Codex/tmux bridge
  └─ manual Beautips runtime + tailnet-only pilot preview
```

This is the observed state on 2026-07-25, not the target boundary. In
particular, the Atenea server still hosts repositories and Codex App Server
containers, and no Atenea AgentRun is routed to the AX42. AX42 Codex is
available in a login shell as `0.145.0`; GitHub is independently authenticated;
the four slot proxies and `codex-beautips` tmux session are active. The Beautips
runtime remains healthy on worker loopback, but the previously accepted
Tailscale Serve route was absent at the 2026-07-25 refresh and is not currently
an available preview. Playwright has pilot evidence through project tooling but
is not currently exposed as a global login-shell command.

### Target

```text
Laptop / Android
        │ authenticated operator traffic
        ▼
Atenea control plane
  ├─ public web + mobile APIs
  ├─ production PostgreSQL and durable workflow state
  ├─ production secrets, backups and monitoring
  ├─ scheduling, leases and notifications
  ├─ governed deploy/health/rollback control
  └─ authenticated private worker protocol
        │ encrypted private network
        ▼
AX42 worker
  ├─ GitHub-backed mirrors + session worktrees
  ├─ bounded Codex, build and test execution
  ├─ project runtimes, development databases and caches
  ├─ private previews + Playwright
  └─ WorkSession attachments + operational telemetry
```

Atenea is also an internal development project. Its source worktree, builds,
tests, development runtime and development database move to the AX42 through a
dedicated phase. Its public service, production database, production secrets,
backup/monitoring and deploy/rollback control remain on the Atenea server.

## Ownership boundaries

| Concern | Authority | Notes |
|---|---|---|
| Projects and WorkSessions | Atenea | Logical project identity replaces assumptions that one host path is universal. |
| Conversation and AgentRun state | Atenea/PostgreSQL | Worker events are idempotently incorporated. |
| Dispatch lease and live processes | Worker, observed by Atenea | Atenea decides admission and terminal product state. |
| Git workspace | Worker per WorkSession | Canonical remotes and branches remain Git-backed. |
| Runtime manifest | Project repository | Consumed by worker and `dev`. |
| Preview route | Worker, published in Atenea | Private by default and session-scoped. |
| Attachments/browser artifacts | Worker storage, indexed by Atenea/PostgreSQL | WorkSession-scoped ordering and retention survive preview teardown. |
| Development databases | Worker per declared project/session policy | Replace/restore is confirmed and cannot target production. |
| Codex context | Versioned Atenea/project sources | The run records the effective context version. |
| Secrets | Dedicated secret boundary | Never OpenSpec, Git, ordinary logs or copied home directories. |
| Public/mobile authentication | Atenea | Existing operator contract remains. |
| Backups | External target | RAID is not the backup target. |
| Production deployment | Atenea governed operations boundary | Consumes versioned artifacts with restricted credentials, confirmation, health check and rollback. |

## Phase order

1. `bootstrap-secure-codex-worker`
2. `establish-project-runtime-contract`
3. `relocate-atenea-development-to-ax42`
4. `route-agent-runs-to-remote-worker`
5. `add-worksession-attachments`
6. `add-private-session-previews`
7. `establish-development-database-lifecycle`
8. individual project onboarding changes for Atenea, Beautips, Checkpol, Yvateve, Fomasys, ISC and Recambios
9. `add-controlled-production-deployments`
10. `harden-worker-operations`
11. `retire-legacy-atenea-executor`

Entry, evidence, rollback and archive gates are defined in `remote-codex-platform-phases.md`. No phase becomes authoritative merely because its code builds.

`relocate-atenea-development-to-ax42` is archived.
`route-agent-runs-to-remote-worker` is archived as
`2026-07-28-route-agent-runs-to-remote-worker` with all `35/35` tasks complete.
Production routing was unchanged and disabled at that archive.
`add-worksession-attachments` is
archived as `2026-07-29-add-worksession-attachments` with all `31/31` tasks
complete. `add-private-session-previews` is archived as
`2026-07-29-add-private-session-previews` with all `37/37` tasks complete. Its
accepted synthetic boundary used an authenticated coordinator on `8789`,
tailnet-only ingress ports `19000–19031`, a renewable five-minute lease, an
eight-hour hard lifetime and 30-day preview audit metadata. Rollback leaves
the capability disabled with zero route/runtime projection resources. Public
sharing remains disabled. The former real-project backup gate was later
lifted by the accepted independent external backup.
`establish-development-database-lifecycle` is archived as
`2026-07-29-establish-development-database-lifecycle` with all `37/37` tasks
complete. Its synthetic PostgreSQL and MariaDB fixtures were restored,
rollback-tested and exact-cleaned; database automation remains disabled and
real-project activation remains blocked on individual onboarding plus an
independent restore-tested backup. `onboard-atenea-on-ax42` is archived as
`2026-07-29-onboard-atenea-on-ax42` with all `45/45` tasks complete. Its exact
protocol remains installed but project selection/execution is disabled with
zero registered workspaces. Beautips onboarding and its subsequent exact
production activation are recorded later in this ledger.
`complete-remote-worksession-close-lifecycle` is archived as
`2026-08-11-complete-remote-worksession-close-lifecycle` with all `60/60` tasks
complete. Its final report-only choice retained AgentRun 96 without retry and
cannot release ownership, replay a prompt or start runtime.

## Decision log

| ID | Decision | Rationale | Status | Owner | Safe review point |
|---|---|---|---|---|---|
| D-001 | Keep Atenea as control plane and AX42 as worker. | Preserves working web/mobile/durable state and isolates resource-heavy execution. | accepted | platform owner | before any control-plane relocation proposal |
| D-002 | Introduce an authenticated worker protocol instead of pointing Atenea directly at one remote App Server. | Scheduling, leases, cancellation, workspace and preview ownership need a worker contract. | accepted | platform owner | remote routing design phase |
| D-003 | Use Tailscale initially. | Provides WireGuard data plane, device identity, NAT traversal, mobile support and policy with lower operational load. | accepted and enrolled in `codynwave.com` | platform owner | before adding another user or network path |
| D-011 | Use `info@codynwave.com` as the sole tailnet Owner initially. | Keeps Standard billing to one seat; Microsoft MFA/recovery plus tested public key-only SSH break-glass cover the initial recovery model. | accepted; second independent admin deferred | platform owner | before removing public SSH break-glass or expanding the operator team |
| D-004 | Retain `dev` as a compatibility CLI over manifests. | Preserves operator muscle memory while removing laptop-only internals. | accepted | platform owner | runtime contract phase |
| D-005 | One worktree and runtime namespace per WorkSession. | Protects branches and permits safe cross-project concurrency. | accepted | platform owner | runtime contract phase |
| D-006 | Do not expose the host Docker socket to Codex. | A mounted socket is effective host-root and defeats session isolation. | accepted | security owner | isolation spike |
| D-007 | Reconcile remote runs through leases after restart. | Backend process lifetime is not execution lifetime. | accepted | backend owner | remote routing phase |
| D-008 | Use one stable foundation plus short-lived implementation changes. | Avoids one unreviewable long-running migration change. | accepted | programme owner | after every phase archive |
| D-009 | Prefer Beautips as pilot after repository synchronization. | Checkpol is simpler at runtime but currently has 14 local uncommitted changes; Beautips is locally clean. | provisional | programme owner | onboarding gate comparison |
| D-010 | Keep localhost SSH tunnels as compatibility fallback. | Some cookies, callbacks and legacy assumptions may not accept a tailnet hostname. | accepted | runtime owner | each project onboarding |
| D-012 | Keep Atenea production/control responsibilities on the Atenea server and move Atenea development to AX42. | Separates durable public control state from builds, Codex and mutable development runtimes. | accepted | platform owner | relocation design phase |
| D-013 | Keep GitHub canonical for all source, including Atenea. | Mirrors and worktrees must be reproducible and cannot become an unreviewed source of truth. | accepted | programme owner | every onboarding gate |
| D-014 | Scope attachments and screenshot language to WorkSession. | Global folders can mix projects and make “latest” nondeterministic. | accepted | product owner | attachment phase |
| D-015 | Permit database replacement only for development databases and only after confirmation. | Prevents an execution-plane operation from reaching production data. | accepted | data owner | development database phase |
| D-016 | Separate production deployment from ordinary Codex execution. | Production requires reviewed artifacts, restricted authority, explicit confirmation, health checks and rollback. | accepted | operations owner | controlled deployment phase |
| D-017 | Keep executable reboot harnesses beneath `/tmp`, but persist synthetic WorkSession state and retained evidence in the canonical `/srv/atenea` roots. | AX42 clears `/tmp` during reboot; reconciliation must be based on real surviving state rather than static or lost files. | accepted and proven in 5.3 | runtime owner | cleanup and retention design |
| D-018 | Give the administrative Beautips PostgreSQL and Redis containers the same `unless-stopped` restart policy as the application. | The first reboot proved that dependencies with restart policy `no` leave the application unhealthy after host recovery. | accepted and proven in 5.3 | operations owner | Beautips onboarding |
| D-019 | Pin execution target and immutable workspace identity when each WorkSession is opened. | A feature change or transient failure must never move an active Codex thread implicitly. | accepted | backend owner | remote routing implementation |
| D-020 | Use a UUID dispatch identity plus monotonic worker lifecycle revision as the idempotency boundary. | Retries and duplicate terminal delivery must return existing work rather than create another run or response. | accepted | backend owner | remote routing acceptance |
| D-021 | Use an additive V46 expand/contract migration and disable routing for rollback instead of down-migrating live history. | Retained remote ownership is required for reconciliation and audit; destructive rollback is unnecessary. | accepted | data owner | after remote records have aged out |
| D-022 | Restrict Phase 4 execution to the fixed `synthetic-routing-v1` workload over a private authenticated protocol. | Routing continuity can be proved without granting arbitrary shell, repository, container or real-project authority. | accepted | security owner | first real-project onboarding |
| D-023 | Retain non-terminal lease and lifecycle records; do not reuse expired leases or delete routing history in Phase 4. | Reconciliation requires durable ownership while final retention can be informed by measured synthetic runs. | accepted | backend owner | before production remote-routing defaults |
| D-024 | Keep attachment metadata authoritative in Atenea/PostgreSQL and content bytes on AX42 behind opaque storage identities. | Ordered ownership belongs in the control plane while large content should remain on the worker without exposing filesystem paths. | accepted for synthetic Phase 5 | platform owner | before real-project activation |
| D-025 | Default attachment limits to 16 MiB per file and 256 MiB retained per WorkSession with a narrow validated media-type allowlist. | Safe bounded defaults prevent an upload surface from becoming arbitrary worker storage. | accepted | security owner | after representative preview measurements |
| D-026 | Record `TRANSIENT` 24-hour, `SESSION` 30-day and `EVIDENCE` 180-day retention classes but perform no general deletion in Phase 5. | The contract needs deterministic retention metadata while production cleanup requires measured evidence and external backup. | accepted for preproduction | data owner | before production defaults |
| D-027 | Keep Phase 5 default-off and exact-synthetic-only until independent external backup is configured and restore-tested. | RAID is availability, not backup, and synthetic fixtures are recreatable. | accepted | operations owner | before authoritative real-project artifacts |
| D-028 | Use one bounded tailnet ingress port per active preview instead of a shared path-rewriting proxy. | Legacy applications commonly emit root-relative redirects, cookies and assets; a private ingress port preserves application semantics without publishing the allocation-derived runtime port. | accepted for synthetic Phase 6 | platform owner | after representative project onboarding |
| D-029 | Give preview routes a five-minute renewable lease, eight-hour hard lifetime, 60-second revocation target and 30-day audit metadata. | Durable intent must survive restart, while abandoned development routes must not remain reachable indefinitely. Attachments keep their independent retention. | accepted for synthetic Phase 6 | operations owner | before production preview defaults |
| D-030 | Keep Phase 6 public sharing disabled and generate localhost forwarding only for an explicit manifest declaration. | Tailnet-only access satisfies laptop/Android operation without introducing Internet ingress; per-project origin constraints must be proven rather than guessed. | accepted | security owner | each project onboarding |
| D-031 | Limit Phase 7 to deterministic PostgreSQL and MariaDB fixtures containing no production-derived rows. | Database ownership, replacement and restore can be proven without granting AX42 production connectivity or adopting retained real-project volumes. | accepted for synthetic Phase 7 | data owner | each project onboarding |
| D-032 | Keep at most three synthetic snapshots for seven days and require a one-use five-minute revision-bound replacement challenge plus verified pre-snapshot. | Bounded local evidence and explicit destructive intent are sufficient for recreatable fixtures; authoritative retention remains blocked on external backup. | accepted for synthetic Phase 7 | data/operations owners | before authoritative database activation |
| D-033 | Archive a closed synthetic WorkSession's byte-exact allocation record only after its admission is released and its exact runtime resources are absent. | A released slot must become reusable without discarding immutable allocation evidence, worktree, mirror, Git, logs or artifacts. | accepted for completed synthetic fixtures | runtime owner | before general allocation retirement support |
| D-034 | Onboard Atenea first and Beautips second; keep every other project independently disabled. | Phase 8 requires one archived change per project and Atenea already has the strongest canonical manifest/relocation evidence. | accepted | programme owner | after Atenea archive |
| D-035 | Run the first managed real Codex workload through bounded `codex exec` as the already authenticated AX42 administrative identity without copying or reading its authentication cache. | The service identity is deliberately unauthenticated; the documented ephemeral probe proves usable ChatGPT authentication while preserving the forbidden-auth boundary. | accepted for Atenea pilot | security/runtime owners | before expanding beyond the pilot |
| D-036 | Keep Atenea onboarding artifacts non-authoritative and its database empty-migrated plus synthetic until an external backup has passed restore. | RAID and retained acceptance evidence do not satisfy authoritative project backup. | accepted | data/operations owners | before any real retained data |
| D-037 | Admit `project-codex-v1` only from a root-owned exact Atenea workspace registry and execute it in a per-run Bubblewrap namespace with no caller-supplied command, path, remote, endpoint or environment. | The authenticated identity can be reused without turning the worker into a general shell or mounting other workspaces, daemon sockets or production paths. Uncertain turns fail closed after restart instead of being replayed. | accepted for Atenea pilot | security/runtime owners | after Atenea archive and before a second project |
| D-038 | Close Atenea onboarding after a 15-minute disabled/clean observation with exact samples at minute 0, 5, 10 and 15. | Four bounded samples are sufficient to detect automatic resurrection or health drift after exact rollback while keeping this disposable, non-production gate finite. Any drift blocks archive. | accepted for Atenea pilot | programme owner | before onboarding archive |
| D-039 | Pin Beautips to GitHub `jlnieto/beautips` `main`; retain entry commit `5044a3b07b3db82895e9c8ff47bc4bc9b0e97130` and manifest commit `e4256d7fe1610e191099bd12ce993591a5cd4b7a` as reviewed ancestors, with task 2.3 descendant `e9e0b3c319c518363d4135f5378ebbddced96dfb` as current mediated source. | GitHub and AX42 agreed at entry, both older copies were strict ancestors, and accepted descendants remove fixed manual runtime authority plus unmanaged smoke fallbacks before allocation. | accepted for Beautips pilot | programme owner | before any managed Beautips allocation |
| D-040 | Treat the existing manual slot 1 Beautips workspace, runtime, listener, secret boundary and persistent data/files as foreign retained state. | The administrative pilot is healthy but has no WorkSession ownership or independent restore-tested external backup. | accepted | runtime/data owners | throughout Beautips onboarding |
| D-041 | Use only empty migrated PostgreSQL, disposable Redis, invented fixtures/files and disabled WhatsApp for managed acceptance. | Platform ownership can be proven without copying administrative, legacy or production-derived data and without external messaging authority. | accepted | data/security owners | before managed runtime start |
| D-042 | Declare no localhost requirement for the disabled-WhatsApp acceptance; block on any absolute-origin failure rather than generating a tunnel implicitly. | Relative application paths can be verified through the private preview while excluded OAuth/messaging flows cannot justify broader compatibility. | accepted for Beautips pilot | runtime/product owners | private preview acceptance |
| D-043 | Close Beautips after a 15-minute disabled/clean window with samples at minute 0, 5, 10 and 15. | The same bounded post-rollback control detects resurrection and protects the administrative pilot and production. | accepted for Beautips pilot | programme owner | before onboarding archive |
| D-044 | Use a private Backblaze B2 bucket in an operator-owned account as AX42's independent encrypted backup target, keeping 14 daily, 8 weekly and 12 monthly exact-host restic snapshots. | A separate provider and recovery boundary protects against complete AX42/Hetzner loss; bucket-scoped credentials, bounded retention and restore evidence are required before authoritative retained state. | accepted, provisioned and restore-tested | operations owner | before lifting the external-backup gate |
| D-045 | Enable production remote selection only for the exact Beautips project after its workspace is durably provisioned; keep the generic route and every unrelated project disabled. | A project-specific gate permits normal laptop operation without widening remote authority or moving existing sessions. | accepted and active | platform owner | before a second real project |
| D-046 | Give AX42 a dedicated read-only Beautips GitHub deploy key and pin GitHub's Ed25519 host identity while preserving the canonical HTTPS remote URL. | Automated workspace creation needs private repository read access without reusing an operator credential or storing a transport-specific canonical remote. | accepted and active | security/runtime owners | deploy-key rotation |
| D-047 | Derive preview worker project identity as a bounded lowercase project name while retaining the exact Atenea project name for allowlisting and UI. | Atenea persists `Beautips`, while the runtime allocation contract owns `beautips`; explicit canonicalization prevents a case-only ownership conflict. | accepted and regression-tested | backend owner | before project names requiring a non-trivial slug |
| D-048 | Retire the closed onboarding session's stale active allocation marker only after its released admission, absent runtime resources and archived byte-identical allocation are proved. | The retained active marker contradicted reusable slot ownership even though the closed fixture had completed the D-033 release gate. | accepted for the exact onboarding record | runtime owner | general allocation-retirement support |
| D-049 | Activate private previews in production Atenea with a dedicated host-to-host credential, the exact `Beautips` allowlist and tailnet-only AX42 control/ingress. | Real browser acceptance must use the same control plane as normal operation without public sharing, runtime-port disclosure or credential exposure. | accepted and active | platform/security owners | preview credential rotation or public-sharing proposal |
| D-050 | Retain the four fail-closed activation AgentRuns as immutable audit history and accept only subsequent terminal successes. | Rewriting failed attempts would destroy evidence of prerequisite enforcement; successful runs on the same workspace and thread prove the corrected path. | accepted | backend/programme owners | terminal audit-retention policy |
| D-051 | Retire a `DRAFT_BLOCKED` WorkSession's stale active allocation marker only after exact recovery, released admission, sealed semantic equality, absent owned runtime resources and byte-preserving rename are proved. | A retained source draft must remain reviewable without permanently preventing its clean replacement from owning the fixed project slot. | accepted for the exact Atenea recovery | runtime/programme owners | general retained-draft allocation retirement support |
| D-052 | Resolve model and effort independently through next-turn, WorkSession, project, platform and worker-default precedence; persist both field sources with the exact catalog revision and Codex version. | A one-turn effort change must not erase a longer-lived model choice, and later setting changes must never rewrite execution history. | accepted | backend/worker owners | before changing execution-profile precedence or source fields |
| D-053 | Version the worker catalog with canonical worker/Codex/model fields and accept only each model's advertised subset of `none`, `low`, `medium`, `high`, `xhigh` and `max`; aliases, Pro and Ultra remain outside persisted profile authority. | Current Codex families do not share one implicit capability set, so exact per-model advertisement and fail-closed intersection avoid silent substitution. | accepted | platform/worker owners | each catalog schema revision or Codex family expansion |
| D-054 | Use the thirteen fixed sanitized progress categories, coalesce identical consecutive events before sequencing and retain the newest 200 events plus independent current/latest/terminal/next-action projections. | The operator gets bounded useful progress and deterministic replay without retaining reasoning, raw commands, output or secrets. | accepted | backend/worker owners | before changing progress taxonomy or retention bound |
| D-055 | Enable completion, failure and action-required push categories by default per active Android device, keep intermediate progress in-app only, and reserve update plan/stage/activation/rollback for platform administrators with separate exact activation and operator-rollback authorizations. | Defaults must notify unattended work without push noise, while binary lifecycle changes remain distinct from routine and mediated recovery authority. | accepted | product/platform/security owners | notification-default or Codex-update authority change |
| D-056 | Add V57–V61 in dependency order for profiles/catalog, progress, recovery, generic notifications and managed updates; keep five independent gates default-off and accept production migration only after a protected V56 restore plus exact rollback-image compatibility proof. | Expanded history is required for audit/reconciliation, while a nominal old image may reject future Flyway history and therefore cannot be assumed to be a viable rollback. | accepted | data/backend/platform owners | before production V57 or any later schema contraction |
| D-057 | Introduce additive `project-codex-v2`, catalog, progress and closed API schemas while keeping installed v1 compatible; require semantic catalog and exact session/workspace validation after structural schema validation. | JSON syntax alone cannot reject a well-formed foreign UUID or model absent from the current worker catalog, and accepting caller operational fields would recreate arbitrary command authority. | accepted | security/backend/worker owners | protocol v2 implementation or schema revision |
| D-058 | Persist project and WorkSession model/effort defaults independently, but require the immutable AgentRun effective profile to be either entirely absent for legacy history or complete with both values, both sources, catalog revision and Codex version. | Model and effort have independent precedence, while partial execution history would be ambiguous and unauditable. | accepted | backend/data owners | before changing V57 profile constraints or snapshot semantics |
| D-059 | Persist only the thirteen exact category-derived operator messages in V58, serialize sequence allocation with the owning AgentRun row and evict detail below a moving 200-event floor without removing the independent projection. | Free-form progress text can retain commands, output or credentials; row ownership plus a non-reused sequence and projection-first replay gives deterministic concurrent append and reconnect behavior. | accepted | backend/data/security owners | before adding or localizing a progress template or changing replay retention |
| D-060 | Bind each V59 recovery request to one active operator's persisted role snapshot, exact WorkSession/AgentRun composite ownership, idempotency key and canonical request fingerprint; persist routine attempts at privileged actions as closed `ROLE_REQUIRED` outcomes, and permit `RETRY_CREATED` only with immutable same-session `retryOfRunId` lineage. | Authentication alone does not grant host authority, repeated keys must not change meaning after timeout, and a replacement run without exact lineage could duplicate a still-live execution. | accepted | backend/data/security owners | before expanding recovery actions, role authority or retry lineage |
| D-061 | Make V60 notification defaults implicit-enabled through absent preference rows, constrain event copy to the three exact `agent-run-safe-v1` templates, bind deduplication to category/run/source revision and own one FCM delivery per exact event/device without copying the device token. | Upgrade and re-registration must not reset user choices, event rows must never retain conversation content, and partial dispatch needs independently retryable delivery ownership without duplicate presentation. | accepted | backend/mobile/data/security owners | before adding a notification category, template version, channel or changing preference defaults |
| D-062 | Keep the established three-field authenticated principal and resolve operational role from the current active account for each privileged API; require exact JSON field sets, catalog membership and persisted ownership, and expose V57–V60 APIs only behind five independent default-false gates. | Token-carried authority can become stale, permissive JSON binding silently accepts forbidden fields, and additive persistence must remain inert until each rollout dimension is separately accepted. | accepted | backend/security/platform owners | before changing API authority, closed request fields or feature-gate defaults |
| D-063 | Give every shared web/mobile session event a stable persisted-identity key, seed and poll the bounded 200-event SSE window by that identity, and replace the legacy run-terminal timeline item only when a committed terminal progress event is published behind the enabled progress gate. | Timestamp cursors can drop same-instant events or resend them after reconnect; publishing both lifecycle and progress terminals creates duplicate operator output, while disable-first rollback must retain the established terminal feed. | accepted | backend/web/mobile owners | before changing shared-stream identity, progress publication or terminal fallback |
| D-064 | Run shared control-plane integration suites with global synthetic authentication bootstrap disabled and require authentication-specific tests to opt in with their exact operator fixture. | An eager default operator makes database-backed authorization tests order-dependent and can conceal which persisted role or identity actually authorized an operation. | accepted | backend/security/test owners | before changing integration-test authentication bootstrap |
| D-065 | Advertise the first exact Codex catalog through a separately authenticated `codex-model-catalog-v1` endpoint/capability while retaining the strict v1 health shape and withholding `agent-run-project-codex-v2` execution until its fingerprint and runner are complete. | Adding fields to the fail-closed v1 health DTO would break the current control plane, while advertising executable v2 authority before validation and runner support would create a false capability. | accepted | worker/backend/security owners | before changing catalog transport or advertising v2 execution |
| D-066 | Validate and fingerprint the complete `project-codex-v2` envelope, profile and existing v1 ownership before persistence, but reject even a valid v2 create as `profile_execution_unavailable` until the fixed runner consumes the validated profile. | Persisting or scheduling a profiled request before model/effort flags are actually enforced could execute under a silently different profile; staged validation must remain fail-closed. | accepted | worker/security owners | task 3.3 runner enablement or profile-fingerprint change |
| D-067 | Permit profiled execution only through the fixed runner's exact `--model` plus `model_reasoning_effort` arguments, require a pre-execution exact fixed-binary version probe, and reject any runner result whose echoed profile/version differs from the request. | A validated request can still execute incorrectly if the binary link moved, ambient configuration wins or the runner reports a substituted profile; all three boundaries must agree before success. | accepted | worker/security owners | before changing runner flags, binary path or effective-profile result fields |
| D-068 | Normalize only recognized Codex JSONL structure into fixed progress messages, discard every source payload value and let the worker replace timestamps while assigning identity, monotonic sequence, coalescence and bounded retention. | Trusting model-provided text, command/output fields or source timestamps would let secret-bearing content cross the worker boundary even when the category itself is allowed. | accepted | worker/security owners | before changing structured-event mappings or progress message templates |
| D-069 | Persist the highest imported worker progress sequence on the AgentRun and lock that row before atomically applying progress, terminal state and result turn; retain byte-stable terminal worker records across restart. | Lifecycle revision alone cannot deduplicate replayed detail events, and two coordinators must not both create a response turn after observing the same terminal worker revision. | accepted | backend/worker/data owners | before changing worker replay identity, coordinator locking or terminal transaction boundaries |
| D-070 | Require dispatch-path, execution, session, workspace and lease ownership for new routine recovery routes; make reconciliation read-only and constrain doctor to a closed no-values schema while retaining the v1 cancel route. | Execution ID alone is insufficient for new recovery authority, and a free-form diagnostic could expose prompts, results, commands, paths or secrets or accidentally mutate execution state. | accepted | worker/backend/security owners | before changing recovery ownership fields, doctor output or v1 cancel compatibility |
| D-071 | Treat the base runner digest and every derived Beautips adapter, mediator, allowlist and installer digest as one reviewed trust chain, and require the complete Phase 3 worker plus Beautips aggregate to pass twice. | A fail-closed downstream pin correctly rejected the task 3.6 runner until every dependent identity was refreshed; isolated runner tests alone do not prove the installed project chain remains internally consistent. | accepted | worker/project/security owners | whenever the base runner or any derived reviewed source changes |
| D-072 | Present the future WorkSession execution profile as one compact state-first control beside the conversation composer; resolve model and effort independently and require pending changes to be applied before send. | The operator must know the next run's exact profile in under three seconds without adding a competing dashboard or permitting submission against an unseen/stale selection. | accepted | web/operator-experience owners | before changing profile placement, source disclosure or pending-selection behavior |
| D-073 | Put one current-run card before secondary conversation content, render only the six newest normalized events, and locally bound the timeline on mobile. | State, elapsed time, latest progress and next action must be visible immediately while the 200-event durable replay remains an audit boundary rather than a visually unbounded conversation dashboard. | accepted | web/operator-experience owners | before changing current-run placement, visible event bound or mobile timeline overflow |
| D-074 | Derive exactly one routine recovery action from persisted run state/next-action, keep the backend as permission authority, and disable new-turn submission while an execution is active. | Cancel, retry and reconciliation are mutually contextual; exposing them together or allowing a competing send would make the operator guess and could create conflicting work. | accepted | web/backend/operator-experience owners | before changing recovery action visibility, permission authority or active-run submission behavior |
| D-075 | Give each Android run an in-memory monotonic replay cursor, merge only sequence-keyed durable gaps after foreground resume, reset on run identity change and keep immersive conversation content within system-bar insets. | Replaying from zero can duplicate a mobile timeline after backgrounding, while an edge-to-edge surface without safe insets can hide the very state and action the operator needs to see immediately. | accepted and emulator-verified | Android/operator-experience owners | before changing Android replay cursor lifetime, gap merge or immersive insets |
| D-076 | Snapshot the independently resolved WorkSession/project/worker model and effort on every future remote AgentRun before durable dispatch, and project that immutable profile onto both its originating and result turns. | A mutable settings view alone cannot prove which profile produced old conversation content; one run-owned snapshot keeps legacy turns compatible while making later setting changes auditable on web and Android. | accepted and web/Android verified | backend/web/Android owners | before changing AgentRun profile snapshot or historical-turn projection semantics |
| D-077 | Close the operator-experience phase only after one synthetic state matrix proves exact data-to-DOM-to-visible mappings for failed, reconciling and terminal runs with deliberately long canonical identities on web and real Compose. | Unit/build success does not prove that the operator can identify state and act within the first viewport or that long persisted identities remain usable on narrow screens. | accepted and visually verified | web/Android/operator-experience owners | before changing current-run hierarchy, responsive wrapping or visual acceptance viewports |
| D-078 | Cut over the overlapping legacy run-completed push only when the generic outbox gate is enabled; persist and claim each exact delivery before provider I/O, while leaving non-AgentRun legacy categories untouched. | Dual sending would duplicate user notifications, provider I/O inside the terminal transaction would weaken durability, and forcing PR/billing/close events into the three-category AgentRun schema would invent unsupported ownership. | accepted and persistence-tested | backend/notification owners | before enabling the generic notification gate or extending event ownership beyond AgentRun categories |
| D-079 | Emit completion, failure and first action-required events from the same local or remote transaction that persists their owning AgentRun state; suppress repeated action-required production while retaining outbox uniqueness as the durable duplicate barrier. | A post-commit producer can lose the notification on process failure, while every reconciliation poll must not create a new user event for one unchanged actionable state. | accepted and transition-tested | backend/notification owners | before changing terminal transaction boundaries or actionable-state revision semantics |
| D-080 | Retry only closed transient FCM/transport/authentication failures at 30, 60, 120 and 240 seconds, stop after five attempts or expiry, and deactivate only an exactly owned device on a closed invalid-token response. | Unbounded or content-derived retry can amplify provider failures; fixed diagnostics and per-device isolation preserve operability without retaining tokens or provider payloads. | accepted and persistence-tested | backend/notification owners | before changing delivery attempt limits, retry schedule or invalid-token classification |
| D-081 | Encode generic AgentRun pushes as `atenea-notification-data-v1` with fixed `AGENT_RUN_STATE` semantics, an exact `atenea://work-sessions/{id}/conversation` deep link and only closed immutable/numeric identity fields. | Android needs one stable route to the exact conversation, while copying domain text or accepting an unrecognized template would leak content and make notification handling ambiguous. | accepted and payload-tested | backend/Android/notification owners | before changing notification payload schema, safe-copy catalog or WorkSession deep-link route |
| D-082 | Parse notification routes fail-closed in Android, use the immutable event ID as local presentation identity, retain only the ten safe payload fields in the PendingIntent and consume a valid event in-app while MainActivity is foregrounded. | Exact route validation prevents arbitrary intent navigation, stable event ownership avoids repeated local cards, and returning before presentation prevents a second notification beside the refreshed conversation. | accepted, unit-tested and emulator-verified | Android/notification owners | before changing foreground delivery, PendingIntent fields or notification route parsing |
| D-083 | Use the immutable notification-event UUID as the Android FCM replacement tag while preserving the existing legacy payload when no generic event identity exists. | Database uniqueness prevents a second delivery owner but cannot prevent Android from rendering two cards after a provider-timeout retry; the stable platform tag makes repeated generic presentation replace the same user notification without inventing identity for legacy events. | accepted and repetition-tested | backend/Android/notification owners | before changing FCM Android notification fields, event identity or legacy push compatibility |
| D-084 | Permit authenticated routine operators to inspect a closed persisted Codex release inventory, but require a current platform administrator and the independent default-false managed-updates gate to create or read an idempotent update plan whose candidate is server-derived and whose four compatibility gates and no-side-effect impact are fixed. | Planning must expose enough current/previous/candidate state to make a safe later decision without accepting caller versions, URLs, hosts, services, commands or paths, and must never install, relink or restart anything by itself. | accepted and integration-tested | backend/platform/security owners | before changing update inventory fields, planning authority, candidate selection or plan side effects |
| D-085 | Stage a planned Codex candidate only from exact persisted plan/candidate/idempotency identities, deriving archive, version, digest, catalog and filesystem authority from a root-owned registry; accept the release only after bounded archive verification, version-matched schema generation, immutable manifests and unchanged current/previous link fingerprints. | A caller-controlled URL, path, command or version would turn administration into remote execution authority, while relinking during staging would collapse the separately authorized activation boundary. Keeping the capability absent until mediator and registry both exist makes partial installation fail closed. | accepted, repetition-tested and not deployed | backend/worker/platform/security owners | before changing release registry ownership, staging request fields, archive/schema verification or retained-link semantics |
| D-086 | Activate a staged Codex release only with a separate ten-minute single-use platform-administrator authorization bound to the exact administrator, worker, plan, current release, candidate release and digest; serialize activation against new remote AgentRuns, require zero non-terminal runs, fixed schema/contract/health/canary gates and automatic exact two-link restoration on health or canary failure. | A pre-check without a shared transaction barrier permits a queued run to race activation, while a caller-selected gate or partial link restore could change execution semantics or lose the verified rollback identity. Re-reading authorization after the barrier and blocking worker dispatch during the bounded operation makes the accepted transition deterministic and fail closed. | accepted, synthetic repetition/restore-tested and not deployed | backend/worker/platform/security owners | before changing activation lifetime, binding, run barrier, gate set, link transition or automatic restoration |
| D-087 | Roll back an accepted Codex activation only with a new ten-minute single-use platform-administrator authorization bound to the exact administrator, worker, plan, activation and current/previous inventory; swap only those two verified links and schedule a restart only for `atenea-agent-run-worker-v1.service`, with zero project App Server restarts. | An activation authorization cannot safely authorize a later operator rollback, and caller-selected services or reconstructed release ownership could affect project runtimes. A durable intermediate link-restored state makes interruption retry only the fixed restart schedule instead of swapping links twice. | accepted, synthetic interruption/repetition-tested and not deployed | backend/worker/platform/security owners | before changing rollback lifetime, binding, persisted transition, link identity or affected service boundary |
| D-088 | Expose managed Codex versions as a state-first platform-administrator web workflow with distinct plan, stage, authorize-activation, activate, authorize-rollback and rollback actions; derive every request from returned persisted identities and hide the navigation from known non-administrator roles while retaining backend authority on direct access. | Combining authorization and execution or accepting free-form operational input would weaken the security boundary, while a generic dashboard would obscure whether the system is ready, blocked or awaiting a separately authorized action. | accepted, role/API/browser-tested and not deployed | web/backend/platform/security owners | before changing operator role projection, managed-update navigation, action sequencing or displayed service impact |
| D-089 | Close the first managed-Codex lifecycle through its fully accepted synthetic update/rollback branch and retain AX42 at Codex CLI 0.145.0 until a future instruction separately and explicitly authorizes one named real managed update. | General implementation or rollout authority does not satisfy the change's deliberately separate real-release boundary; the task explicitly permits synthetic closure, which proves the machinery without silently changing the production execution engine. | accepted and read-only baseline-verified | platform/security owners | before any real managed Codex stage, activation, rollback or worker restart |
| D-090 | Refresh only the fixed, non-symlink Atenea canonical mirror immediately before first-workspace commit admission, after validating static WorkSession/project ownership and only when the origin URL, remote-only fetch mapping and absence of a push URL are exact. | A newly published canonical commit can otherwise leave AX42 safely but permanently rejecting a current WorkSession against a stale mirror; refreshing before static ownership checks or through caller authority would weaken the fail-closed boundary. | accepted, worker-tested and live-verified | worker/platform/security owners | before changing first-workspace canonical refresh, mirror provenance or admission ordering |
| D-091 | Persist a failed-run retry's immutable lineage and inherited Codex profile in the same first AgentRun insert, and retire a pre-dispatch orphan only after exact session/run/status/null-remote/null-lineage predicates plus zero worker execution are proven. | Attaching an immutable lineage after insertion can leave an unowned queued row when completion validation fails; atomic insertion prevents that race while the exact remediation rule preserves the failed audit record without adopting or dispatching it. | accepted, full-suite-tested and live-verified | backend/recovery/platform owners | before changing retry creation, lineage mutability or pre-dispatch orphan remediation |
| D-092 | Gate real attachments with one global create/bind switch, one closed canonical-project registry and an immutable policy revision recorded only on newly eligible WorkSessions; activate only canonical `atenea` in the first change. | Mutable display names and retroactive enablement cannot prove project/session authority, while a new-session snapshot gives rollback and audit one exact eligibility boundary. | accepted, full-suite-tested and live-verified | backend/platform/security owners | before changing attachment admission or enabling another real project |
| D-093 | Bind an ordered image manifest immutably to one idempotent operator turn and AgentRun, and dispatch it only through additive `project-codex-v3` references containing UUID, media type, size and SHA-256. | Upload alone does not tell Codex which screenshot belongs to a prompt; exact binding plus a stable client request identity prevents implicit latest-file selection, duplicate turns and caller path authority. | accepted, idempotency/retry-tested and live-verified | backend/worker owners | before changing image-bearing turn, retry or manifest semantics |
| D-094 | Extend attachment v1 compatibly for real ownership, then have the fixed runner verify and materialize only the selected images into an execution-owned temporary boundary exposed read-only to Codex. | Rollback must keep retained downloads readable, and neither Codex nor a caller may gain visibility of the attachment store or choose filesystem paths. | accepted, worker-tested and live-verified | worker/security owners | before changing real storage, materialization or runner support |
| D-095 | Treat `retainUntil` as the minimum keep and new-binding boundary, with no general automatic deletion in the first real activation. | First use needs reversible retention and verified external backup; adding destructive cleanup simultaneously would introduce an unproven ownership/tombstone policy. | accepted, retention/no-deletion verified | data/operations owners | before any attachment expiry/deletion implementation |
| D-096 | Deploy V62, backend and worker support disabled, then require separate production-rollout authorization and one operator-assisted non-secret Atenea web canary followed by backup/check/isolated restore before accepting the project gate. | A synthetic pass does not prove real browser-to-Codex delivery or non-empty external recovery, while disabled-first deployment and exact canary evidence bound the production risk. | accepted, rollback/re-enable/canary/restore verified | platform/operations/product owners | before another real-project rollout or changing the acceptance gates |
| D-097 | Promote Atenea's two accepted descendant histories to GitHub `main` in order using merge-commit semantics, then reconcile every canonical base declaration to the resulting immutable commit. Squash, force update and source-branch deletion are forbidden. | The attachment candidate already descends from the accumulated feature history; preserving that ancestry makes the second review contain only its additional commits and prevents split source authority for future WorkSessions. | accepted and live-verified | platform/Git/operations owners | before opening the next real Atenea development WorkSession |
| D-098 | Preserve WorkSession 6 as an immutable `DRAFT_BLOCKED` retained draft during main promotion; do not call ordinary close, rewrite its worktree or change its row after its accepted replacement and allocation-retirement contract has completed. | V51 intentionally requires retained drafts to remain non-closed and fingerprinted; the state is reviewable history rather than an active project lock, and closing it would destroy the distinction the recovery contract created. | accepted and live-verified | WorkSession/programme owners | before any retained-draft lifecycle expansion or deletion policy |
| D-099 | Retire only WorkSession 15's exact active-name allocation after proving it closed, released, unregistered and resource-free; preserve bytes, inode, ownership, mode, size and mtime under the canonical retired name before repeating WorkSession 16 activation. | The active filename continued to assert fixed slot-2 ownership after the mediated registration/admission release, so the corrected activator properly rejected the replacement; an exact same-filesystem rename retains audit evidence while making released capacity reusable. | accepted and live-verified for the exact closed canary | runtime/programme owners | before general closed-allocation retirement support |
| D-100 | Make one exact worker `RELEASED` receipt a precondition for a remote WorkSession to become `CLOSED`; mark pre-V63 remote closures `UNVERIFIED_LEGACY` without inferring or changing worker state. | Git reconciliation alone cannot prove that registration, admission, allocation or ephemeral runtime ownership was released, and automatically trusting historical rows would adopt unknown state. | accepted, migration/full-suite/live-verified | backend/data/worker owners | before changing remote-close terminality, receipt identity or legacy classification |
| D-101 | Preserve a strict bounded worker error envelope and classify authenticated deterministic rejections separately from transport unavailability. | Discarding the HTTP 409 body caused 81 repetitions of an impossible activation and reported a healthy worker as unavailable, hiding the action that could actually resolve the blocker. | accepted, protocol/full-suite/live-verified | backend/worker/security owners | before changing worker error schemas, retry windows or unavailable classification |
| D-102 | Serialize ensure/release under one lifecycle lock and finalize exact ownership through a monotonic crash-resumable journal while retaining source, conversation, attachments, logs, artifacts, backups and policy-retained volumes. | A multi-resource close can stop between mutations; a reviewed prefix journal permits only the same operation to continue without recreating released ownership or deleting ambiguous state. | accepted, adversarial/crash-resume/live-verified | runtime/worker/security owners | before changing lifecycle locking, journal ordering, release ownership or retention |
| D-103 | Permit historical closed-session release only through a separately confirmed platform-administrator action in Atenea, and never retry the preserved prompt automatically after capacity is released. | Legacy repair is materially different from ordinary retry; binding confirmation to an exact ownership fingerprint makes it self-service without granting arbitrary cleanup or duplicating user work. | accepted, role/browser/live-verified for WorkSession 16 | product/platform/security owners | before expanding reconciliation authority or retrying any retained failed run |
| D-104 | Require a blocked legacy operation's complete immutable release request to pass a non-mutating worker preflight before Atenea persists another human-confirmation plan. | Capacity-owner diagnosis alone proved the retained owner but did not exercise the real release request, lifecycle lock, fixed mediator and journal boundary; consuming more operator plans without that proof repeated the same deterministic failure without diagnostic value. | accepted, full-suite/live-intervention-verified | backend/worker/platform/security owners | before changing reconciliation preflight, plan fingerprint or confirmation consumption |
| D-105 | Handle the newly reported `dompurify` and `nanoid` npm advisories in a separately scoped security-maintenance change, without altering the sealed close-lifecycle implementation or its evidence. The follow-up must identify direct/transitive ownership, select the minimum compatible upgrades, regenerate the lockfile deterministically, obtain a zero-unresolved-applicable-advisory audit or explicitly accepted residual-risk record, and repeat the production web build plus the complete desktop/mobile Playwright qualification before any deployment. | The advisory database changed after the accepted task 6.2 audit. Mixing dependency upgrades into final archival would invalidate reviewed artifacts and expand the close-lifecycle scope, while deferring them without an owned gate would leave a high-severity advisory untracked. | deferred, evidence-backed security follow-up; no dependency or deployment mutation authorized | web/security/platform owners | before the next ordinary production web deployment; immediately if separate exploitability triage finds current exposure |

## Deferred decisions and gates

| Decision | Deferral | Must be resolved before |
|---|---|---|
| Second independent tailnet administrator | The operator chose one paid seat initially. `info@codynwave.com` is Owner; Microsoft recovery and public SSH break-glass remain mandatory. | removing public SSH break-glass or expanding beyond one operator |
| Per-project localhost requirement | Discover through cookies, callbacks and browser tests. | declaring that project's private preview ready |
| Initial runtime sandbox implementation | Prototype mediated rootless/container alternatives against the no-host-socket requirement. | accepting the runtime contract phase |
| Terminal AgentRun, artifact and preview retention durations | Non-terminal Phase 4 lease/lifecycle retention is fixed; measure representative runs before choosing terminal cleanup. | production defaults in remote routing/preview phases |
| Atenea development data fixture and sanitization policy | Production data must not be copied implicitly to AX42. | relocating the Atenea development database |
| Versioned artifact format and promotion authority | Deployment must not build mutable source on the production host. | controlled deployment phase |

## Runtime non-impact statement

This foundation does not:

- deploy services;
- change Atenea endpoints or database schema;
- point any WorkSession at the AX42;
- relocate the current Atenea worktree, preview stack or database;
- modify current production containers;
- open or close firewall ports;
- copy repositories or credentials;
- change startup reconciliation.

Every implementation phase requires a dedicated OpenSpec change, test evidence, deployment evidence, an observation window and an executable rollback.

## Resume protocol

The secure AX42 bootstrap was accepted after more than 24 hours of clean
observation and archived as
`openspec/changes/archive/2026-07-24-bootstrap-secure-codex-worker`.

After any interruption:

1. Open this ledger and identify `Current phase`.
2. Run `openspec list` and `openspec status --change <current-change>` in the canonical Atenea worktree.
3. Confirm the production Atenea worktree and the programme worktree are not being confused.
4. Read the stable capability specs and the active phase proposal/design/tasks.
5. Recheck the dependency gate in `remote-codex-platform-phases.md`.
6. Inspect actual worker/control-plane state before continuing; never infer it from documentation alone.
7. Continue the first unchecked task or record a new decision if evidence invalidates the plan.
8. Validate strictly, collect release/rollback evidence and archive the phase before advancing.

`establish-project-runtime-contract` completed all 21 tasks and is archived at
`openspec/changes/archive/2026-07-26-establish-project-runtime-contract`.
OpenSpec synchronized eight modified requirements with no additions, removals
or renames; strict validation passes for the archived change.

The runtime-engine mode mismatch observed during the 5.4 rollback was corrected
without weakening the invariant. An owned engine state root created below the
canonical setgid runtime directory is normalized to exact mode `0700`. The
regression starts from a setgid parent, fails against the previous engine and
passes against the corrected implementation.

Local and AX42 contract, allocation, dev, manager, engine and admission suites
passed. AX42 returned to the accepted empty-state baseline, retained evidence
from 5.3 and 5.4 remained intact, Beautips remained healthy at the published
commit, and Atenea production remained unchanged and unrouted.

The entry-gate review for `relocate-atenea-development-to-ax42` found a dirty
Atenea development worktree. The operator authorized reconciliation: the
reviewed React-console migration and documentation were validated, committed
and published normally on `feature/actualizar-conversacion-en-web` at
`a9fe14989544308acc587e3eb71cb985fa637b2d`. The branch is now clean and matches
its remote; production remains healthy, unchanged and unrouted.

The active change is apply-ready with proposal, design, two capability deltas
and 27 implementation tasks. Tasks 1.1 through 1.3 recorded the canonical
source and sentinels, committed the schema-valid heavy Atenea manifest, and
defined the empty PostgreSQL 16 migration plus synthetic-fixture contract.
Task 2.1 then added the deliberately adapter-dependent Atenea worker Compose
definition and proved its fail-closed resolution without activating it. Task
2.2 extended only the manager/engine allowlist for that exact manifest and
Compose hash, one persisted heavy allocation, the three declared services,
session-owned paths, three loopback ports, full-runtime resource names and
five exact ownership labels. Task 2.3 then added the dedicated negative policy
corpus at both the manager-inspection and engine closed-plan boundaries. It
proves that daemon sockets, privileged or host namespaces, devices, undeclared
mounts, fixed global identities and unlabelled, partially labelled, foreign
or ambiguous resources fail before engine execution or daemon access. Task
2.4 then passed the complete synthetic contract, allocation, lifecycle,
manager, engine, admission, health/browser/retention and cleanup regression
gate from `/tmp`, plus both focused Atenea adapter suites. The integrated
contract suite's protected manager/engine hashes were advanced only to the
exact task 2.2 implementations.
Detailed results are in `docs/atenea-development-relocation-evidence.md`;
OpenSpec progress is `12/27`.

Atenea is clean and synchronized locally and remotely at
`7cc003dba3b931e5d4769c507d65983d377a3222`. With explicit operator
authorization for task 3.2, the three previously local reviewed commits were
published in order above the accepted entry commit. The first adds
`ops/atenea-runtime.json`; the second adds only
`ops/atenea-development-data-v1.json` and its 45-file migration checksum
inventory; the third adds only `ops/worker/docker-compose.ax42.yml`.
PostgreSQL 16.11 applied all 45
Flyway migrations from an empty temporary volume and reached V45 with zero
domain rows before fixtures; the temporary container and volume were removed.
The declared fixture contains one synthetic operator, one synthetic project,
one closed synthetic WorkSession and two synthetic turns, with all other
domain counts zero and explicit production/external-integration denials.

The current Compose SHA-256 is
`2133646b9fe6227ca417d6d62c92a74306caaa46a2957cdee810d5d7b0e5bb9f`.
It declares exactly `db`, `codex-app-server` and `atenea-dev`, requires all
session identities, images, internal ports, owned paths, network, volume and
secret-file references from the future allowlisted adapter, and has no host
port publication or fallback to `docker-compose.dev.yml`. Resolution from
`/tmp` passed with the AX42 Compose `5.3.1`; all 18 required inputs fail closed
when individually absent.

The allowlisted Atenea plan remains deliberately non-activable: after exact
plan validation the engine rejects lifecycle execution before resolving or
calling a daemon. Manager validation never executes manifest `argv`, and the
plan contains named secret references rather than values. The synthetic
fixture loader remains deferred to 4.3.

Task 3.1 created the sole GitHub-backed Atenea bare mirror at
`/srv/atenea/repositories/atenea.git` as `atenea-worker:atenea`, mode `2770`,
using the contract's credential-free HTTPS identity and
`+refs/heads/*:refs/remotes/origin/*` fetch mapping. A fresh fetch selected
`a9fe14989544308acc587e3eb71cb985fa637b2d`, exactly equal to the accepted
entry commit. The mirror contains none of Atenea's three unpublished local
commits and has no local alternates, credential-bearing URL or persisted
credential material.

Task 3.2 admitted administrative development WorkSession
`41c0ff95-e555-4773-b7b4-60903a3af1ad` in `slot2` with `heavy1`. Its clean
session branch and worktree are pinned at the synchronized GitHub commit
`7cc003dba3b931e5d4769c507d65983d377a3222`. Workspace, admission, allocation,
runtime-path, log, artifact, reconstructible-cache and empty named-secret
reference ownership records are persisted beneath the canonical
`/srv/atenea` roots as `atenea-worker:atenea`, with session roots mode `2770`
and records mode `0640`.

No lifecycle command, manager, engine, client, container, image, network,
volume, listener, service unit or route was started. Slot container/image
counts remain `3/3`, `0/4`, `0/0`, `0/0`; admission capacity is `1/4` normal
and `1/2` heavy.

Task 3.3 first stopped at its default-deny source-isolation gate because the
worker Compose mounted the owned upload path at `/workspace/data/uploads`
without setting `ATENEA_MOBILE_UPLOAD_ROOT`. With explicit commit/push
authorization, Atenea commit
`b6dc854d94ba5b1976926656c9a6aba330f671e2` added only the missing environment
binding and was published on the selected branch. The exact Compose hash and
the manager/engine allowlist hashes were advanced, and both isolated adapter
suites passed against a fresh GitHub checkout.

The AX42 mirror fetched the published correction and the existing
administrative session branch was fast-forwarded locally without publication.
`workspace-v1.json` now records `b6dc854...`; allocation and admission records
remained byte-identical in `slot2/heavy1`. The accepted read-only proof
reproduced Git common-directory, GitHub publication, mirror self-containment,
the three administrative records, the four exact inputs, all 45 migration
hashes and the effective owned upload root. It found no alternate, symlink,
bind mount, control-plane runtime input or real WorkSession/AgentRun authority.
Complete mirror, worktree, record, artifact and cache content/metadata
fingerprints were identical before and after the proof.

Task 4.1 verified the exact committed manifest at
`b6dc854d94ba5b1976926656c9a6aba330f671e2` without executing or changing a
toolchain. The worktree and Git blob both reproduce manifest SHA-256
`3b26e1899a06993bee69ac596e7cb69b6200a37d063d98203ad308058c91bfa3`;
the manifest passes the staged versioned schema on AX42. Existing package
records prove the pinned Git, Docker and Compose versions, while immutable OCI
index/platform/config metadata and stored layer identity prove the selected
Node, Java, Maven, Playwright and Chromium versions. No package, image,
wrapper, browser or container was downloaded, installed, updated, built or
executed.

Task 4.2 ran `npm ci`, the zero-vulnerability audit and the canonical
`scripts/web-build.sh` with the pinned Node image in `slot2`. The audit
reported zero vulnerabilities and the generated `index.html`, CSS and
JavaScript are byte-identical to the selected commit. The index references
exactly the two files emitted by Vite, with no stale asset identity. Evidence
is retained beneath the administrative WorkSession artifact root at
`runs/task-4.2-web-build`.

The rootless slot daemon cannot traverse the `atenea-worker:atenea` mode
`2770` worktree ancestors for a direct bind. Task 4.2 therefore used a
byte-exact `git archive` scratch owned by `atenea-slot2`, without changing
ACLs, ownership or the worktree; the scratch was removed. This does not block
the accepted build, but direct worktree mounting remains an explicit gate
before the private runtime task 5.1.

Tasks 4.2 and 4.3 are complete and programme progress is `13/27`. Task 4.3
initialized a new runtime-derived, exactly labelled PostgreSQL volume from
the approved PostgreSQL 16 digest. A one-shot `network=none` helper used the
already documented least-authority pattern of `cap_drop=ALL` plus only
`CAP_CHOWN` to assign the empty volume root to `999:999`, then exited and was
removed. Persistent PostgreSQL ran as `999:999` with all capabilities dropped,
an internal WorkSession network, no published ports and zero host listeners.

Flyway validated and applied exactly the committed V1–V45 inventory from an
empty schema, with 45 successful history rows, zero failures and final version
45. Before fixtures all 28 declared domain counts were zero. The deterministic
fixture created exactly one operator, one project, one closed WorkSession, two
SessionTurns and zero AgentRuns; every other declared count is zero. Exact
reapplication was a no-op and a conflicting pre-existing project failed
closed with a transaction rollback.

All temporary containers, networks, scratch and processes were removed.
Slot2 retains the exact approved image and exactly one session-owned volume
for task 4.4; session-owned containers and networks, allocated-port listeners
and AgentRun routing are zero. Production, preview and Beautips remain `UP`.
Passing evidence is retained beneath `runs/task-4.3-database`; the first
fail-closed attempt remains separately beneath
`runs/task-4.3-database-attempt-1-blocked`.

Task 4.4 is complete and programme progress is `14/27`. The committed
`scripts/test.sh` remained the canonical entry point, with an ephemeral
exact-invocation adapter replacing only its unsafe local Compose operations.
The adapter used the commit-exact source archive, a new task-only PostgreSQL
volume, an internal network and the pinned Maven/JDK 21 and PostgreSQL 16
digests. It did not run `docker compose up`, Codex App Server or the private
application runtime.

After dependency prefetch, the complete backend suite ran once offline:
327 tests passed with zero failures, errors or skipped tests across 48
Surefire XML reports. The container exited zero after 26 seconds; thirteen
samples recorded peak CPU `203.50%`, peak memory `654 MiB / 3 GiB` and peak
PID count `71`. All external integrations were disabled or test-local.

All task 4.4 containers, networks, test volumes, caches and scratch were
removed. Slot2 retains only the accepted task 4.3 database volume for the
private runtime step; there are zero session-owned containers and networks,
zero allocated-port listeners and zero AgentRun routing keys. Evidence is
retained beneath `runs/task-4.4-backend-tests`.

The first task 5.1 preflight stopped before daemon access. Its unchanged
blocked evidence was moved to
`runs/task-5.1-private-runtime-attempt-1-blocked`; the SHA-256 of its
`SHA256SUMS` remains
`4098564cff3eccda9002fa85fd6d9c1e593997ea0f5ea7fd694b7b3962f240b4`.

Task 5.1 is now complete and programme progress is `15/27`. The versioned
runtime contract installs a root-owned client, manager, engine and dedicated
Atenea adapter, creates a commit-exact WorkSession delivery without changing
the protected worktree ancestors, and starts exactly `db`,
`codex-app-server` and `atenea-dev` through the admitted
`slot2/heavy1` lifecycle.

The three containers are running with the exact runtime-derived names and
ownership labels, read-only root filesystems, all capabilities dropped,
`no-new-privileges`, no host namespaces, devices, privilege or daemon socket.
They share one labelled internal network. Because that network has no Docker
gateway publisher, the adapter retains exactly three RootlessKit `tcp4`
mappings on `127.0.0.1`: `28541→5432`, `22667→8092` and `22359→8081`.

Codex `0.145.0` is fixed at OCI digest `sha256:c081aaa9...`; its
authentication-disabled App Server listens only on container loopback and a
reviewed same-container TCP proxy exposes the declared internal port. Atenea
returns `UP` at its private health endpoint. PostgreSQL reuses the exact task
4.3 volume, data root, database and role: Flyway history remains byte-identical
at 45 successful V1–V45 rows, and all 28 counts remain exact, including one
synthetic operator, one project, one closed WorkSession, two SessionTurns and
zero AgentRuns. No fixture or migration was rerun.

OpenAI, DeepSeek, FCM, GitHub operations and other external integrations are
disabled or fail-safe local. Rootful Docker and containerd remain inactive
and masked; production, preview and Beautips remain `UP`; routing and secret
value matches remain zero. Passing evidence is retained beneath
`runs/task-5.1-private-runtime`; the SHA-256 of its `SHA256SUMS` is
`23010f74668e1f962a056b67505bb8c9816e47a953409fd2a53c0056f87ea856`.
Detailed evidence is in
`docs/atenea-development-relocation-evidence.md`.

Task 5.2 is complete and programme progress is `16/27`. A reviewed,
package-lock-enforced Playwright `1.60.0` module bundle was installed for
slot2 and verified against content-tree SHA-256
`1ca49077563d996a21591e41f5a71296747d81ed9f1936e4887924fcb574b2ee`.
The official pinned image continues to provide Chromium `148.0.7778.96`;
the module bundle is mounted read-only and no dependency download occurs
during browser acceptance.

Playwright authenticated the synthetic operator at `1440x900` and `390x844`
through the exact WorkSession internal network. Both viewports proved login
absence after authentication, the expected operator identity, non-empty
complete DOM, `Atenea Core`, the synthetic project, the closed fixture's
declared `Sin sesión` operator projection and the expected enabled/disabled
critical actions. Login and project-overview reads returned HTTP 200. Browser
external requests, failed local requests, AgentRuns, routing, secret matches,
screenshots and traces were all zero.

The committed manifest preview path `/admin/login` returned 404 in the
selected Atenea commit. Acceptance therefore used `/`, backed by the
commit-exact `src/main/resources/static/index.html` Git object
`ac4ea34f6dabcb4e200188afad801928bcb79d0d`; the discrepancy is retained in
the evidence rather than hidden or repaired through a runtime redeploy.

The accepted runtime, three containers, internal network, retained volume,
three loopback listeners, 45 Flyway migrations and exact synthetic counts
remain unchanged. Production, preview and Beautips remain `UP`; browser
processes and refresh tokens were cleaned to zero. Passing evidence is beneath
`runs/task-5.2-playwright-dom`; the SHA-256 of its `SHA256SUMS` is
`351dca13a8e356bf0eac6e8018f672250de5a4006887ff711d4505af445b7418`.
Toolchain remediation evidence is beneath
`runs/task-5.2-toolchain-remediation`.

Task 5.3 is complete and programme progress is `17/27`. Playwright ran only
on AX42 in the same admitted `slot2/heavy1` WorkSession network and captured
the authenticated Projects screen at `1440x900` and `390x844`. Pre-capture
semantic locators proved the expected synthetic operator, project,
`Sin sesión` projection and critical action states, with no login, permanent
loading, inline error, external browser request or failed local request.

Finite DOM measurements recorded equal `scrollWidth` and `clientWidth` at
both viewports, full viewport intersection for the critical state and actions,
and zero stable visible overlaps. Direct inspection of both original-resolution
PNGs passed hierarchy, readability, primary-action visibility, clipping,
overlap, overflow, control containment, wrapping, empty-state distinction and
desktop/mobile consistency.

The accepted commit, runtime, three containers, internal network, retained
volume, three listeners, 45 Flyway migrations and exact synthetic counts
remain unchanged. Refresh tokens, AgentRuns, routing and browser processes are
zero. Production, preview and Beautips remain `UP`. Final sanitization found no
secret value or forbidden unsanitized browser artifact. Passing evidence is
beneath `runs/task-5.3-playwright-visual`; the SHA-256 of its `SHA256SUMS` is
`8d6cc8093107126b2d07b517d0ef5177462c609fea996d285cc8d7743cedf37f`.

Task 5.4 is complete and programme progress is `18/27`. The accepted probe
ran only on AX42 against the existing admitted `slot2/heavy1` WorkSession and
its loopback endpoints. Runtime configuration kept OpenAI, DeepSeek costs,
briefing, FCM and LLM intent routing disabled; all declared provider base URLs
remained the non-routable loopback sentinel `127.0.0.1:9`, the session network
remained internal and no external credential environment variable existed.

Authenticated costs returned OpenAI and DeepSeek as `configured=false` and
`disabled`. Speech synthesis, realtime voice and transcription each returned
the exact sanitized HTTP 503 disabled outcome before provider transport.
Source-guard hashes and runtime boundaries prove that disabled FCM returns
before token/message HTTP, disabled DeepSeek briefing returns before provider
HTTP and an absent GitHub token fails before GitHub HTTP; no operational
GitHub, push, briefing, host-management or external-provider action was
invoked. Runtime log signatures and the internal network boundary recorded
zero provider attempts.

Logout revoked the one temporary refresh token and bounded cleanup restored
the table to zero. Flyway remained at 45 successful migrations; the exact
synthetic counts, Git identities, WorkSession records, allocation, admission,
three containers, one network, one retained volume and three listeners were
unchanged. AgentRuns, API usage, push records, managed hosts, core commands,
routing and residual task processes remained zero. Production, preview and
Beautips remained `UP`; rootful Docker, its socket and containerd remained
inactive and masked. Final scanning found no secret value, retained auth
material or unsanitized provider response.

Passing evidence is beneath
`runs/task-5.4-external-integrations-fail-safe`; the SHA-256 of its
`SHA256SUMS` is
`bc750f5c958867f69b6f8b23d562ed7a13c96e990fb5f64b2d463ca0e10d0a70`.

Task 6.1 is complete and programme progress is `19/27`. A key-authenticated
private SSH connection over Tailscale established the named tmux session
`codex-atenea-41c0ff95` as administrator `jose`, with one
`administrative` window rooted at the exact admitted WorkSession worktree.
Codex `0.145.0`, the sanitized `remote-codex-admin-v1` context and ChatGPT
login guard passed. The conversation contains the non-secret continuity marker
`CONTEXT-READY ATENEA-41C0FF95-20260728`.

Tmux options label the session `administrative` and bind it to the existing
WorkSession/runtime while explicitly recording `AgentRun=none`, worker
lease `none` and routing `none`. The Codex process has no `DOCKER_HOST`
environment. The worktree commit/tree/index, workspace/allocation/admission
hashes, private runtime resources, 45 migrations and synthetic counts remained
unchanged. AgentRuns, refresh tokens and routing records remain zero.
Production, preview and Beautips remain `UP`; rootful Docker, its socket and
containerd remain inactive and masked.

The installed `codex-work` helper differs from the programme template only by
`export COLORTERM=truecolor`; the retained comparison proves no workspace,
daemon or authority change. Task 6.1 used an explicit detached tmux command,
not that drifted helper. Final scanning retained no Codex auth/history/session
file, environment dump or secret value.

Passing evidence is beneath
`runs/task-6.1-administrative-tmux-session`; the SHA-256 of its
`SHA256SUMS` is
`c914c4d4234701dd5d2d01ecabcd841f6c7fd72fca09bc982f4bef5045498ecf`.

Task 6.2 is complete and programme progress is `20/27`. Two independent,
finite private SSH clients attached in sequence to the existing
`codex-atenea-41c0ff95` tmux session. Before the first disconnect, during the
detached interval, after the second resume and after final detach, the session
retained `session_created=1785262669`, window `administrative`, pane `%0`, pane
PID `1170290`, the exact worktree and the same live Codex process. Attached
client counts followed `0→1→0→1→0`.

The resumed pane still contained
`CONTEXT-READY ATENEA-41C0FF95-20260728`. Without tools or file changes, the
existing conversation returned the exact response
`CONTINUITY-RESUMED ATENEA-41C0FF95-20260728`. The final client detached
cleanly; tmux and Codex remain alive with zero attached clients.

The worktree commit/tree/index, workspace/allocation/admission hashes,
`slot2/heavy1` identity, runtime `ready/healthy`, three containers, internal
network, retained volume and three loopback listeners remained unchanged.
Flyway remains at 45 successful migrations and the synthetic counts remain one
operator, one project, one closed WorkSession and two SessionTurns. AgentRuns,
refresh tokens and routing remain zero. The session labels still classify this
as administrative with no dispatch or lease. Production, preview and Beautips
remain `UP`.

Passing evidence is beneath
`runs/task-6.2-administrative-continuity`; the SHA-256 of its `SHA256SUMS` is
`1216ed3162348b6d3f4f2e465bffd071ed8ec468b792bf1b5ff517b176bb54ed`.
Sanitization retained no raw terminal, Codex auth/history/internal-session
file, token, cookie, environment dump or credential-pattern match.

Task 7.1 is complete and programme progress is `21/27`. The installed mediated
manager stopped the exact admitted Atenea runtime and returned
`stopped/stopped` in 1,631 ms. Its fixed adapter retained logs and removed the
three owned RootlessKit listeners. A task-scoped rollback wrapper then required
the exact five ownership labels and immutable IDs before removing only the
three stopped session containers and their now-empty internal network.

The session PostgreSQL volume and complete image inventory were retained.
`heavy1` was released before `slot2` through the exact versioned admission
tool; the admission record now records `released/released`. Workspace and
allocation records, mirror refs, worktree commit/tree/index, post-stop logs and
all prior retained artifacts are unchanged. The administrative tmux/Codex
session remains alive with zero attached clients.

The first wrapper continuation stopped after the successful mediated stop
because its network assertion still expected the pre-stop three endpoints;
Compose had correctly disconnected stopped containers and the actual count was
zero. No resource had yet been removed and admission remained held. The
assertion was corrected, the stop was not repeated and the runtime was not
recreated.

Pre-stop Flyway and synthetic data checks remained exact at 45 migrations, one
operator, one project, one closed WorkSession, two SessionTurns and zero
AgentRuns/refresh tokens. Routing remains zero. Production, preview and
Beautips remain `UP`; rootful Docker, its socket and containerd remain
inactive.

Passing evidence is beneath
`runs/task-7.1-atenea-runtime-rollback`; the SHA-256 of its `SHA256SUMS` is
`25c6a03f43c727652020161116011a82d3a881e2b8b74ba94dd59b6b3bd2bf70`.
Sanitization retained no Codex auth/history/internal-session file, token,
cookie, environment dump, private key or credential-pattern match.

Task 7.2 is complete and programme progress is `22/27`. The bounded second
rollback pass began from the exact 7.1 terminal boundary: zero session
containers, networks and listeners, one retained PostgreSQL volume and
persisted `slot2/heavy1` admission already `released/released`. It removed zero
containers, networks, images and listeners and did not recreate the runtime.
The mediated manager rejected a post-release stop with the expected
`RUNTIME_OWNERSHIP_CONFLICT`; repeating both versioned admission releases was
an idempotent zero-exit no-op.

Four synthetic network identities then exercised literal no-label, partial
label, complete foreign-owner and complete-but-ambiguous ownership. Every
candidate was recorded by immutable ID, name, creation time, driver and labels
before use. The exact rollback ownership gate rejected every case with exit 65
and `RUNTIME_OWNERSHIP_CONFLICT`; inspect SHA-256 remained byte-identical and
each rejected resource remained present during denial. Cleanup revalidated the
complete recorded identity and removed only that exact immutable ID.

All four rootless-slot container, network, volume and image inventories match
their pre-fixture fingerprints. The Atenea session has zero residual
containers, networks, owned images, allocated listeners, brokers and
Playwright/Chromium processes, while its labelled PostgreSQL volume, mirror,
worktree, clean Git/index, allocation, delivery, engine state, logs and all
prior artifacts remain byte-identical. AgentRuns, worker lease and routing
remain zero/none. The administrative tmux/Codex session remains alive with the
same identity and zero attached clients. Production, preview and Beautips
remain `UP`; rootful Docker, its socket and containerd remain inactive.

Four bounded preliminary attempts are retained transparently. They exposed an
inaccessible inherited cwd, an unbounded denial exit, an absent-resource
status propagated after exact deletion, and a nominally unlabelled fixture
carrying a non-ownership task label. No attempt recreated runtime, removed a
rollback target, changed admission or modified a foreign resource. The two
anonymous volumes created by the early container fixtures were identified by
their exact creation identities and removed by immutable ID; the pre-existing
anonymous volume and the retained session volume were preserved. The accepted
corpus uses network-only fixtures and a literally unlabelled candidate.

Passing evidence is beneath
`runs/task-7.2-rollback-idempotence`; the SHA-256 of its `SHA256SUMS` is
`f65acffc596e333ac3a3428c784756eeee8b73729d6046c5e810e051b84745c0`.
Sanitization retained no Codex auth/history/internal-session file, token,
cookie, environment dump, private key or credential-pattern match.

Task 7.3 is complete and programme progress is `23/27`. After the separately
authorized single AX42 restart, the boot ID changed from
`0886b4d0-485c-4035-b8bb-1b0ab910e85c` to
`5cc2a4e3-020d-4d19-8a55-6ecae77f22ce`. Finite SSH probes first observed the
host unavailable and reconnected on attempt 10. No second reboot was
requested.

All three RAID arrays returned `[UU]`; storage, key-only SSH, firewall,
Tailscale, the health timer and the strict worker health suite pass. The four
rootless user daemons and daemon sockets returned automatically. Read-only
`docker info` through each stable proxy socket proved all four proxy paths.
Rootful Docker, its socket and containerd remain inactive and masked.

Reconciliation selected only the exact persisted workspace, allocation,
released admission, engine owner marker and rootless immutable metadata for
WorkSession `41c0ff95-e555-4773-b7b4-60903a3af1ad`. The allocation still names
`slot2/heavy1`, admission remains `released/released` and no ephemeral runtime
resource exists. The accepted outcome is therefore `stopped/stopped` with
action `report-only`: no runtime was recreated or started, no resource was
removed, no volume was reattached, no slot was reassigned and no ownership was
invented.

The retained PostgreSQL volume, mirror refs, worktree commit/tree/index,
workspace/allocation/admission records, engine state, logs and every prior
artifact survived byte-identically. The rebuildable delivery under `/tmp` was
cleared by reboot as expected. Rootless Docker regenerated only each daemon's
default `bridge` ID; network name/driver shape is identical and the `host`,
`none` and persistent Beautips network IDs are exact. No session container,
network, owned image, listener, AgentRun, lease or routing record appeared.

The administrative tmux/Codex session ended with the host reboot, as expected
for the non-persisted administrative bridge. It was not recreated or replaced.
Production and preview remain `UP` with the same nine immutable containers.
Beautips remains `UP` with the same three immutable containers.

Two read-only preflight attempts are retained: an outer capture returned 1
before reboot, then a doubled escape in the healthy `[UU]` assertion was
localized and corrected. Two postflight assertion continuations distinguished
regenerated default bridges from persistent network ownership and sorted the
normalized network shape. None changed a resource or issued another reboot.

Passing evidence is beneath
`runs/task-7.3-restart-reconciliation`; the SHA-256 of its `SHA256SUMS` is
`57c702382e7d9551224d19121a310adb337b6aba554fe5434bc57e553f0819ba`.
Sanitization retained no Codex auth/history/internal-session file, token,
cookie, environment dump, private key or credential-pattern match.

Task 8.1 is complete and programme progress is `24/27`. The final
control-plane capture remains clean and synchronized: the programme was at
`bb14726b06ad07c8cb804fd76b3747beb37fa474` before handoff documentation and
the Atenea source remains on
`feature/actualizar-conversacion-en-web` at
`b6dc854d94ba5b1976926656c9a6aba330f671e2`. Production and preview are `UP`.
The nine immutable production/preview container IDs match task 7.3 exactly,
including the production PostgreSQL container. This proves the unchanged
runtime configuration and environment boundary without reading an environment
value or database row. Source and persisted routing-record scans are zero.

The final AX42 session inventory has zero containers, networks, owned images
and allocated listeners, one retained labelled PostgreSQL volume, zero
AgentRuns by the unchanged retained database evidence, no lease and no routing.
Beautips remains `UP`. Passing evidence is beneath
`runs/task-8.1-final-non-impact`; the SHA-256 of its `SHA256SUMS` is
`21ef3351db436d2cec0223a692c92ca6c303e08683553eeafe37744f942692d7`.
A read-only first assertion attempt is retained separately and records no
resource change.

Task 8.2 is complete and programme progress is `25/27`. The strict installed
worker verifier passes. All three RAID arrays are `[UU]` with no recovery
action; root and Atenea filesystems are each at 4% use. UFW is active, SSH is
key-only, Tailscale is online with no Serve configuration, and all four
rootless slots, daemon sockets and stable proxies are healthy. Every slot
retains the accepted CPU `4s`, `MemoryHigh=10737418240`,
`MemoryMax=12884901888` and `TasksMax=4096` boundary.

Rootful Docker, its socket and containerd remain inactive and masked, with no
Docker group members. All slot container, image, volume, normalized-network
and persistent-network inventories equal task 7.3. Beautips remains clean,
synchronized at `5044a3b07b3db82895e9c8ff47bc4bc9b0e97130` and `UP` with
the same immutable containers. Passing evidence is beneath
`runs/task-8.2-final-worker-audit`; the SHA-256 of its `SHA256SUMS` is
`00de504f1a1381c5945701d08dc3ebcdba88703c98d1655200994b731a538a00`.

Task 8.3 is complete and programme progress is `26/27`. The operator workflow,
rollback boundary and explicit administrative resume procedure now distinguish
this accepted manual pilot from managed AgentRun routing. The handoff points
only to non-secret artifact roots and verified manifests. Passing evidence is
beneath `runs/task-8.3-operator-handoff`; the SHA-256 of its `SHA256SUMS` is
`0068a4f8428e6d8a2d2c1bb8896bb8c68b8f90e544b21cbd0f9e6676743338f7`.

Task 8.4 is complete and programme progress is `27/27`. All task checkboxes
were complete before strict change validation passed. One
`openspec archive relocate-atenea-development-to-ax42 -y --json` invocation
archived the change as
`openspec/changes/archive/2026-07-28-relocate-atenea-development-to-ax42` and
synchronized seven added requirements plus one modified requirement into the
normative specs. Strict all-spec validation passed.

The worktree and cached diff checks identified one blank line at EOF introduced
by the archive formatter in each of the two synchronized specs. Removing only
those two blank lines made the diff clean and strict all-spec validation passed
again. The archive command was not repeated and the index remained empty. No
runtime, route, production resource, unrelated slot or Beautips resource
changed.

Passing evidence is beneath `runs/task-8.4-openspec-archive`; the SHA-256 of
its `SHA256SUMS` is
`7f03e7ba6916d8394daed6fac2795fdec0a30c8e8e3a7f2d83d75cb49558c6cc`.

## Phase 4 entry and active resume point

The `route-agent-runs-to-remote-worker` entry gate was accepted on 2026-07-28.
Canonical programme Git was clean at
`8b964f2c3db54481315b59a9ed7ac1a399f53353`; Atenea source was clean at
`b6dc854d94ba5b1976926656c9a6aba330f671e2`. Production, preview and Beautips
were `UP`, production routing records were zero, AX42 strict health passed,
three RAID arrays were `[UU]`, all four bounded rootless slots were healthy and
the accepted capacity remained four normal slots plus two heavy permits.

The exact installed runtime client, manager, engine and Atenea adapter hashes
match their versioned sources. The retained production-schema backup is
`/srv/atenea/backups/prod/atenea_prod_before_remote_routing_v46_20260728T222500Z.dump`
with SHA-256
`a48a7d25b5d9b3289e926bef4201c074c5f523bb32a793b0f3ccc8e1f1760160`.
It restored successfully into a network-disabled disposable PostgreSQL 16
fixture with the full successful Flyway V45 history and expected public tables.
The fixture was removed by exact immutable identity.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/route-agent-runs-to-remote-worker/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`783780d6170441392e7cc2124ecf54c571df859005d1847b710dc728a946b245`.
The first blocked lexical-version check and its exact cleanup remain retained
separately for audit; it changed no production or foreign resource.

Tasks 1.1–1.4 are complete. The proposal,
design and deltas close execution affinity, authenticated protocol, lease,
capacity, synthetic scope and non-destructive migration rollback decisions.
Attachments/previews, real-project selection, per-project localhost,
artifact-promotion authority, external backup retention and a second tailnet
administrator remain at their later declared gates and do not block synthetic
Phase 4 routing.

Tasks 2.1–2.4 and 3.1–3.4 are complete and programme progress is `12/35`.
The additive V46 model, immutable session affinity, durable dispatch identity,
lease/lifecycle state, optimistic terminal acceptance and non-terminal
per-session uniqueness are committed in Atenea source at
`23a9549e2ef2f3930325004068aea7bc0aad7454`. Routing remains default-disabled
and existing rows remain local.

The accepted V45 restore plus current V46 migration proof is beneath
`runs/task-2.4-v46-restore-migration`; the SHA-256 of its `SHA256SUMS` is
`70a752d212a6ae4e2ee77a083200859968b4c85b46cf70a221d31e605b7ec18f`.
It used a network-disabled disposable PostgreSQL fixture, verified the
expand/contract boundary and removed the fixture by exact identity without
changing production.

The versioned worker source now implements authenticated
`agent-run-worker/v1`, atomic durable state, idempotent dispatch, fail-closed
conflict handling, exact cancellation and bounded four-normal/two-heavy FIFO
scheduling. Its seven protocol/scheduler tests pass, including service-state
restart recovery with the same execution identity. The complete Atenea backend
suite passed with `330` tests and no failures after recreating only its
disposable test database; focused routing/API/reconciliation tests passed
`19/19`.

Tasks 3.5 and 4.1–4.7 are complete and programme progress is `20/35`. The
private worker is installed as `atenea-worker`, listens only on
`100.81.98.93:8787`, and UFW permits that port only from Atenea at
`100.88.252.28`. Unauthenticated health is rejected, an unrelated tailnet
source cannot connect, and authenticated health reports the exact v1 protocol,
`ax42-01` identity and `4/2` capacity. Root-owned configuration, bounded
readiness and systemd hardening pass the installed verifier.

Accepted installation evidence is beneath
`runs/task-3.5-private-worker-install`; the SHA-256 of its `SHA256SUMS` is
`62d1ffaecc727b876996529c7b9e6d78be4224e944666db9871e9b378d057d55`.
Two fail-closed verifier attempts and their separately committed fixes remain
documented there; neither accepted an execution.

Atenea now has default-disabled exact-allowlist selection, authenticated finite
clients, durable-before-dispatch coordination, monotonic optimistic terminal
acceptance, exact cancellation and persisted-target reconciliation. The local
startup path explicitly excludes remote runs and its original stale-run policy
continues for local runs.

Tasks 5.1–5.5 are complete and programme progress is `25/35`. The final Atenea
backend suite passed `335/335`; the web build and canonical packaged backend
build also passed on AX42. Installed-protocol acceptance returned one execution
for an identical retry, rejected conflicting identity reuse with HTTP `409`,
held the fifth normal run queued behind four permits, and held the third heavy
run queued behind two permits. All admitted and queued fixtures subsequently
completed and capacity returned.

The exact Compose fixture was removed with volumes and local build images.
Slot 2 returned to zero containers and custom networks, seven baseline images
and only the pre-existing retained Phase 3 PostgreSQL volume. Production
configuration, routing and AgentRun count remained unchanged.

Accepted validation evidence is beneath `runs/task-5-automated-validation`;
the SHA-256 of its `SHA256SUMS` is
`dc4f59d3c58c0b760eaed04d95fc58e8b9faf84948cc10b1748e74f63a12d754`.

Tasks 6.1–6.5 are complete and programme progress is `30/35`. An empty
disposable V46 control plane completed six remote AgentRuns: five succeeded and
one exact cancellation became `CANCELLED`; no non-terminal row remained.

One live execution survived an Atenea backend restart with the same dispatch
and execution identities and exactly one visible response. A proxy-scoped
partition exposed `RECONCILING` with an explicit no-replacement reason, then
healed to the same successful execution. Exact cancellation left a concurrent
unrelated execution running to success. Three turns in one WorkSession retained
`ax42-01`, one workspace identity and one synthetic thread, while using three
distinct dispatch/execution identities and producing exactly six visible
operator/worker turns.

Production AgentRun count and routing remained unchanged; production and
preview containers remained `UP`. Beautips health remained `UP`, all four
rootless slots retained their accepted inventories, RAID remained healthy and
the private worker returned to zero capacity in use.

Accepted continuity evidence is beneath `runs/task-6-synthetic-continuity`; the
manifest includes the rollback instance identity recorded before removal. The
final SHA-256 of its `SHA256SUMS` is
`c3ef39356cd83d92e82a8a0c64ad7b5bb1c6b1cbc5a34948384c1385672f8292`.

Tasks 7.1–7.4 are complete and programme progress is `34/35`. Remote selection
was disabled with all six synthetic AgentRuns terminal. The four existing
WorkSessions retained their persisted remote affinity. The first exact rollback
removed the registered disposable resources and private firewall/listener; the
second exited zero with every target already absent and removed nothing.

Worker state retains fifteen terminal protocol records (`14 SUCCEEDED`,
`1 CANCELLED`) and zero non-terminal records. The worker is inactive/disabled
with no port 8787 listener or UFW rule. Production remains on its unchanged
schema with AgentRun count `58`; production, preview and Beautips remain `UP`.
AX42 strict verification passes, RAID is `[UU]`, slot inventories match
baseline, source Git is clean/synchronized and no Phase 4 temporary resource
remains.

Accepted rollback and observation evidence is beneath
`runs/task-7-rollback-observation`; the SHA-256 of its `SHA256SUMS` is
`5db761a247ee2c5981ca67fb62046e7e0b250c7a07c044056e8d484775ceeb89`.

Task 7.5 is complete and programme progress is `35/35`. Strict change
validation passed with all tasks checked before one archive invocation moved
the change to
`openspec/changes/archive/2026-07-28-route-agent-runs-to-remote-worker`.
Twelve modified requirements were synchronized into the two normative specs.
The archive formatter added one blank line at EOF to each synchronized spec;
removing only those lines made the diff clean. Strict validation then passed
for all seven normative specs.

Accepted archive evidence is beneath `runs/task-7.5-openspec-archive`; the
SHA-256 of its `SHA256SUMS` is
`fbc4713c8a884144d1d1b73728a72d455e49507a6c79fe658c025ecfbe2a77c6`.

The exact resume point is the Phase 5 entry gate for
`add-worksession-attachments`.

## Phase 5 progress: add-worksession-attachments

Tasks 1.1–1.4 are complete and change progress is `4/31`. The accepted entry
gate proves clean synchronized source and programme Git, unchanged production
and preview container identities and health, no V47 source, no AX42 attachment
root, an inactive/disabled Phase 4 worker, four healthy rootless slots, healthy
RAID and unchanged Beautips state. The first capture attempt is retained
separately because obsolete verifier/database assumptions exited non-zero; it
was not accepted and caused no mutation.

The storage, metadata, access-control, ordering, limits, retention and rollback
contract is approved for exact synthetic preproduction use. Authoritative
real-project activation is explicitly blocked until an independent external
backup target is configured and restore-tested. Accepted entry evidence is
beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`1d63a3ce1c6b76d2baa03b7422260796ee365e6a6f9e9200cb025b71ced7913d`.

The exact resume point is task 2.1 of `add-worksession-attachments`.

Tasks 2.1–2.4 are complete and change progress is `8/31`. Atenea source commit
`631ee048e9f3f541a940e3bedcaecb8d909ca251` adds the expand-only V47 attachment
table, immutable UUID/integrity/storage identities, ownership-derived project
metadata, exact optional AgentRun validation, pessimistic WorkSession quota
serialization, idempotent conflict detection and deterministic
`createdAt DESC, id DESC` screenshot queries.

The focused metadata suite passes `7/7`. A clean disposable PostgreSQL schema
validated and applied all 47 migrations, Hibernate schema validation passed
and the existing WorkSession integration suite passed `26/26`. The first V47
integration attempt exposed a `CHAR`/`VARCHAR` mapping mismatch; the disposable
test schema was recreated exactly, V47 was corrected before publication and
the accepted rerun passed.

The exact resume point is task 3.1 of `add-worksession-attachments`.

Tasks 3.1–3.4 are complete and change progress is `12/31`. The versioned
`worksession-attachment/v1` service accepts only authenticated exact UUID
routes; streams bounded content through an owned temporary file; verifies the
declared SHA-256 and file signature/text encoding; atomically publishes content
plus metadata; returns opaque identities; and exposes no filesystem list,
path, command or execution field. It independently enforces 16 MiB file and
256 MiB WorkSession limits.

Identical retries return the original object and conflicting identity reuse
changes nothing. General deletion is absent; the exact delete route requires
both persisted and request-side synthetic-fixture identity. The `11/11`
protocol tests cover authentication, atomic/idempotent create, conflict,
integrity, MIME, file/quota bounds, cross-session/traversal rejection,
restart persistence, download and exact synthetic cleanup.

The exact resume point is task 3.5 of `add-worksession-attachments`.

Task 3.5 is complete and change progress is `13/31`. AX42 runs the
enabled/active service only on `100.81.98.93:8788`; UFW admits that port only
from Atenea tailnet identity `100.88.252.28`. The retained root is
`0700 atenea-worker:atenea`, initially contains only its owned `.incoming` and
`work-sessions` directories and starts no project runtime. Installed programme
and unit SHA-256 identities match commit
`0cc8b7b09d00f45dde160400560890de15cbef52`. The follow-up aligns the worker
route with Atenea's canonical positive-decimal WorkSession database identity;
the attachment identity remains a UUID.

AX42 strict verification and RAID pass after installation. All four slot
inventories remain untouched and Beautips reports actuator health `UP`.
Accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/runs/task-3-worker-storage`;
the SHA-256 of its `SHA256SUMS` is
`f81c159f533b399331c130187f94b7c17d2fe1f73410512aa59862ad4a55dc44`.

The exact resume point is task 4.1 of `add-worksession-attachments`.

Tasks 4.1–4.4 are complete and change progress is `17/31`. Atenea source commit
`7a77923da458a4488aabb897860d13afb7c4ad58` adds default-off configuration,
finite-timeout private worker authentication, WorkSession-scoped web/mobile
upload and read APIs, exact integrity-checked download and bounded screenshot
resolution. API responses omit worker paths and storage identities; existing
Spring Security authentication covers every new `/api/**` route.

Creation is limited to an exact synthetic project allowlist plus persisted
remote worker affinity. Project identity is derived from the WorkSession and an
optional AgentRun must belong to that same session. The legacy global mobile
upload remains compatible while the capability is disabled and fails with an
actionable WorkSession instruction when scoped attachment creation is enabled.
The focused client, service, controller, metadata and compatibility suites pass
`20/20`. The worker protocol also accepts a content-identical idempotent retry
with a later request timestamp while retaining the original immutable
`createdAt`; all other classification or content changes remain conflicts.

The exact resume point is task 5.1 of `add-worksession-attachments`.

Tasks 5.1–5.4 are complete and change progress is `21/31`. Atenea source commit
`e98138dd2e82e928399502a040f6c01557d2a1ad` adds one compact attachment surface
to the existing WorkSession conversation: current retained count, accepted
types and 16 MiB bound are visible immediately, one primary upload action is
available, retained items download through the authenticated client and
backend failures remain actionable.

The production web bundle builds successfully. Focused backend tests pass
`21/21`. A controlled Playwright validation exercised a successful list/upload
refresh at `1440x900` and an unsupported-format state at `390x844`; DOM
assertions passed, screenshots were visually inspected, no horizontal overflow
was present and the browser closed cleanly. Accepted sanitized evidence is
beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/runs/task-5-operator-experience`;
the SHA-256 of its `SHA256SUMS` is
`3dc344dd8f446a2990e9ea8952432c040bf7bccbe31a90144b113177dbe38ff7`.

The exact resume point is task 6.1 of `add-worksession-attachments`.

Tasks 6.1–6.5 are complete and change progress is `26/31`. The accepted
disposable control plane applied all 47 migrations and the complete Atenea
regression passed `356/356`. Exact synthetic HTTP acceptance proved private
authentication, one-row/one-object idempotency, stable integrity, prompt/image
ownership under WorkSession `51001` and AgentRun `51001`, bounded ordering by
session/source and exclusion of a newer cross-project sentinel.

Unauthorized, foreign-session, foreign-run, conflicting, unsupported,
content-mismatched, oversized, quota, empty and traversal inputs failed closed
with their expected actionable status. Rejected identities left no database
rows, retained objects or incoming temporary files. Four accepted fixtures
remained byte-identical after client disconnect, disposable control-plane
restart and the real attachment-service restart; no preview runtime was
required or coupled to retained content.

The first real idempotency retry exposed nanosecond/microsecond timestamp drift
at PostgreSQL persistence. Atenea source commit
`3beee9de0f6a75434cc92175627ecd276e06fbb4` normalizes attachment creation time
before worker retention. Focused tests and the complete regression passed
before the clean accepted rerun.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/runs/task-6-automated-continuity`;
the SHA-256 of its `SHA256SUMS` is
`7e32a0efcfb1a2c9d0da5b87d3bacfedbc83c631554cd072934125bf2557caf4`.

The exact resume point is task 7.1 of `add-worksession-attachments`.

Tasks 7.1–7.5 are complete and change progress is `31/31`. Creation was
disabled twice without rebuilding the worker service. Both executions retained
the same four indexed synthetic attachments and exact downloadable content;
the repeated rollback produced empty worker-hash and authoritative-metadata
diffs, proving idempotence. A new upload failed closed with `409` and left zero
metadata or worker residue.

Cleanup first validated every recorded attachment identity, WorkSession,
SHA-256 and synthetic-fixture marker. The worker deleted exactly four objects,
the disposable database deleted exactly four matching rows and all rejected
and accepted synthetic residue is zero. Temporary control-plane and local
containers, volumes, networks, scripts and installer harnesses were removed
only after their immutable identities or exact Compose labels matched the
recorded harness.

Final fingerprints preserve the AX42 boot identity, healthy RAID `[UU]`, all
four rootless slot inventories, Beautips and the nine production/preview
containers. Production and preview remain `UP` and unchanged. The sole
intentional AX42 delta is the empty tailnet-only attachment service and retained
root introduced by Phase 5; it contains no fixture, incoming, browser or proxy
residue. Atenea source commit
`1f3598691df09f5a54dfb940519a2c36cbb60884` also retains the actionable
limit, unsupported-type and worker-unavailable controller regression coverage.

Accepted sanitized rollback/final evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/runs/task-7-rollback-final`;
the SHA-256 of its `SHA256SUMS` is
`2edf4d395c0f893a723cdead42072ec70ec465a41fdff295bf53e88c66972c74`.
The operator-render evidence remains in the accepted task 5 bundle and the
complete `356/356` regression plus real continuity evidence remains in the
accepted task 6 bundle.

Strict validation passed with all tasks checked. The attachment delta adds the
new `worksession-attachments` capability and synchronizes the scoped artifact
requirements in `private-development-preview` and `remote-work-continuity`.
The completed change is archived at
`openspec/changes/archive/2026-07-29-add-worksession-attachments`.
Accepted archive evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-worksession-attachments/runs/task-7.5-openspec-archive`;
the SHA-256 of its `SHA256SUMS` is
`db2a837afa470543f8917cadac1d4cd7ea6f7f0f2c388d91ea3f375b4ff1ffc5`.

The exact resume point is the Phase 6 entry gate for
`add-private-session-previews`.

## Phase 6 progress: add-private-session-previews

Tasks 1.1–1.4 are complete and change progress is `4/37`. The accepted entry
gate proves clean synchronized Atenea source and programme Git, unchanged nine
production/preview container identities, production and preview health `UP`,
no deployed V46/V47/V48 schema and no Phase 6 service, state, listener,
container, browser or proxy.

AX42 strict verification passes with RAID `[UU]`, rootful Docker
inactive/masked, unchanged four-slot inventory and Beautips `UP`. The Phase 5
attachment service is active and both retained/incoming stores are empty.
Atenea control, the operator laptop and Pixel 7 are online in the approved
tailnet.

The synthetic contract fixes coordinator control port `8789`, tailnet-only
ingress `19000–19031`, a renewable five-minute lease, eight-hour hard lifetime,
60-second route revocation and 30-day preview audit metadata. Localhost
forwarding requires a manifest declaration and public shares fail closed. The
proposal, design, four delta specs and task plan pass strict validation.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`a1a42baa8bacd14524219f9c0a25c0255d8f0f1063770ba34c3f105153d59ec9`.

The exact resume point is task 2.1 of `add-private-session-previews`.

Tasks 2.1–2.4 are complete and change progress is `8/37`. Atenea source commit
`bc32118e4e3f85d20a69af953deafc90d37cece8` adds the expand-only V48 preview
registry, immutable WorkSession/project/worker/allocation ownership, optional
same-session AgentRun validation, one-active-preview constraint, monotonic
optimistic revision and deterministic reconciliation/audit queries.

The metadata state machine enforces `STARTING`, `READY`, `RECONCILING`,
`BLOCKED`, `STOPPED` and `EXPIRED`; stale or invalid transitions mutate
nothing. Ready and renewed routes remain inside the approved tailnet/range,
five-minute lease and eight-hour hard limit. Blocked text is bounded and
sanitized, and 30-day audit identity survives stop/expiry.

The focused metadata suite passes `10/10`. A fresh disposable PostgreSQL
database validated and applied all 48 migrations, Hibernate schema validation
passed and the existing WorkSession integration suite passed `26/26`.

The exact resume point is task 3.1 of `add-private-session-previews`.

Tasks 3.1–3.6 are complete and change progress is `14/37`. Programme commit
`41e2d509286964f4dd91d2f05659f334b405fe4b` adds the authenticated
`session-preview/v1` coordinator, exact persisted projection records, bounded
tailnet ingress forwarding and manifest-derived localhost tunnel data without
credentials or runtime-port disclosure.

The coordinator is active/enabled on AX42 at tailnet-only
`100.81.98.93:8789`. UFW accepts that control endpoint only from Atenea
`100.88.252.28` and accepts ingress `19000–19031` only on `tailscale0` from
`100.64.0.0/10`. Its state store is empty and installation started no project
runtime or ingress listener. Twelve synthetic protocol tests pass, including
authentication, idempotence, stale revision, partial/foreign/ambiguous
ownership, persisted restart, lease expiry and exact cleanup.

Rootful Docker remains inactive/masked, all four rootless daemons are active,
slots 2–4 remain empty and slot 1 retains only the same three Beautips
containers. RAID remains `[UU]`; production, preview and Beautips remain `UP`.
Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-3-private-coordinator`;
the SHA-256 of its `SHA256SUMS` is
`7084d061238835f5ee234fa38a50189fe9c0cd2b364c24acd423663dc8fcbe9e`.

The exact resume point is task 4.1 of `add-private-session-previews`.

Tasks 4.1–4.5 are complete and change progress is `19/37`. Atenea source
commit `0b6a8178d52e325e9c86cddfb16d03920bba496c` adds a default-off,
finite-timeout authenticated preview client plus WorkSession-scoped activate,
status, retained history, renew, stop and declared-localhost APIs.

Atenea derives project, worker and allocation identity from the persisted
WorkSession plus the submitted runtime UUID; AX42 remains the authority that
validates the supplied allocation fingerprint against its exact persisted
record. Web and mobile share one read model that exposes the private URL only
for `READY`, bounded expiry and one primary next action, without worker or
allocation internals.

Startup and 30-second periodic reconciliation select only persisted
reconcilable records, cap each batch, renew only exact ready ownership and
never create or reassign a runtime. Twenty-three focused client, service,
persistence, reconciliation and controller tests pass, including default-off,
foreign ownership, stale identity and sanitized worker rejection paths.

No deployment occurred; production and preview remain default-off and `UP`.
Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-4-atenea-api-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`78e614b3b5a5657fabb83d1de1d493b8aef755bc5dbc0c8690d8d76a63361cfa`.

The exact resume point is task 5.1 of `add-private-session-previews`.

Tasks 5.1–5.5 are complete and change progress is `24/37`. Atenea source
commit `24ad3dcfaea8974d4f18fbd83f3df68ac4ee7182` adds one compact preview
surface immediately beneath the WorkSession header on web and Android.
`READY` alone exposes the primary `Abrir preview` action; starting and
reconciling visibly wait, while blocked, expired and stopped remain concise,
actionable and omit stale URLs. Android opens the same tailnet URL directly
and links secondarily to the existing retained-evidence surface.

The production web build, isolated secret-free Android debug build and focused
UI API regression pass. Playwright asserted all six lifecycle states and
verified the ready surface at `1440x900` and `390x844`: state and action remain
inside the first viewport, with no horizontal overflow, clipping or overlap.
The final desktop, mobile and blocked-state screenshots were visually
inspected. No deployment occurred and production/preview remain `UP`.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-5-operator-experience`;
the SHA-256 of its `SHA256SUMS` is
`915d0f6ff2828c5a1b006d0e37f5ef1eea1f34fb8e6b17812d80cf0bb259b94a`.

The exact resume point is task 6.1 of `add-private-session-previews`.

Task 6.1 is complete and change progress is `25/37`. Exact synthetic
WorkSession runtime `80b54495-88cf-4354-b1e4-aada1921644a` is
`ready/healthy` in its persisted free `slot3` allocation, with runtime
upstream bound only to `127.0.0.1:22243`. Preview
`f106453b-601a-47f3-9272-adafaa58ec7b` is `READY` at the single tailnet
projection `100.81.98.93:19000`; an exact duplicate activation returned the
same byte-identical identity and created no second listener.

The initial `slot2` allocation stopped before runtime creation because the
retained Phase 2 allocation still owns that slot. No historical record was
changed. Runtime-engine commit
`4bc325c3e7d9cc1a2ad87d78a7ef60f3f63040ed` removed the synthetic fixture's
obsolete `slot2` constant, accepts only the allocation's validated
`slot1`–`slot4` identity and adds `slot3` regression coverage. The new
session's admission was released from `slot2`, reacquired exactly in free
`slot3`, and the root-owned engine was installed with SHA-256
`48bc54324bf39086401fc7430a1b9b8048bcb6bd37e028bf8cad80e92bc4360e`.

Atenea reached the fixture over Tailscale with HTTP 200. Independent probes
from Atenea and the operator host to AX42's public address on ingress,
coordinator and runtime ports all timed out with HTTP 000. `ss` proves the
preview listener binds only the AX42 tailnet address, the runtime remains
loopback-only, unauthenticated control returned 401 and an injected public
sharing request returned 400 without changing the private route. Rootful
Docker remains inactive/masked; RAID is `[UU]`; production, preview and
Beautips retain their accepted inventories.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.1-synthetic-private-preview`;
the SHA-256 of its `SHA256SUMS` is
`ed59877411b6eafb5e3d1668a826a5ed8d48c3c946debe936339e028522d3147`.

The exact resume point is task 6.2 of `add-private-session-previews`.

Task 6.2 is complete and change progress is `26/37`. The operator laptop and
an independent Atenea private client both resolved preview
`f106453b-601a-47f3-9272-adafaa58ec7b` as `READY` for WorkSession `96061`
and reached the same tailnet URL. Their live response bodies are byte-identical
with SHA-256
`54c244c22440ed1f09203f79bb0d45387b8ddc543146fb87a736bf7f6572e4d6`.

The Pixel 7 Android private peer is online on the approved tailnet and answered
a finite peer probe in 126 ms. It exposes no ADB transport, so no automated
physical-device browser claim is made; the accepted `Android/private-client`
case uses the independent private client while the previously accepted Android
build/read model remains unchanged.

An authenticated inspect using foreign WorkSession `96062` returned
`ownership_conflict`. The coordinator record was byte-identical before and
after that denial at SHA-256
`27823e1a510cd5fdf7202d466adae0c99ea48940c56184bf3c8ef5f29526ebb1`,
and the coordinator still contains exactly one preview record. No foreign
WorkSession was resolved or changed.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.2-private-clients`;
the SHA-256 of its `SHA256SUMS` is
`9d87f73687a8054b02c3cec8cf6ccf30012a0e516efb5c51b3291e1bed27a8aa`.

The exact resume point is task 6.3 of `add-private-session-previews`.

Task 6.3 is complete and change progress is `27/37`. The manifest-declared
localhost case returned only credential-free SSH destination
`codex-worker`, tailnet ingress `100.81.98.93:19000` and path `/`; it
explicitly reports `runtimePortExposed=false` and never discloses upstream
port `22243`.

One bounded key-authenticated SSH forward bound
`127.0.0.1:39061` to the exact preview ingress. The localhost response and
the direct tailnet response are byte-identical at SHA-256
`54c244c22440ed1f09203f79bb0d45387b8ddc543146fb87a736bf7f6572e4d6`.
The listener never bound `0.0.0.0` or the operator's tailnet address, and a
non-loopback probe failed without content. The recorded SSH PID was terminated
and awaited; the localhost listener is absent after cleanup while the private
preview remains ready.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.3-localhost-tunnel`;
the SHA-256 of its `SHA256SUMS` is
`71afeff381ff56b83c20d24ef4c7b75226420fa4dc62ebbec06ed457e19c2f8a`.

The exact resume point is task 6.4 of `add-private-session-previews`.

Task 6.4 is complete and change progress is `28/37`. A single exact-labelled
Playwright 1.60.0 container ran on the synthetic runtime network with no
published port, all capabilities dropped, read-only root and finite timeouts.
It asserted HTTP success, visible body text and the expected fixture identity
at `1440x900` and `390x844`. Both records report `textLength=66`, no clipping
and no horizontal overflow. The inspected desktop and mobile screenshots show
all content visibly within their viewports; the narrow rendering wraps without
overflow.

The first browser attempt stopped before navigation because the read-only
container lacked a writable Playwright `/tmp`. Its exact diagnostic container
was removed. The accepted run uses a bounded noexec/nosuid tmpfs, completed in
1968 ms, closed pages, contexts and Chromium in `finally`, and left zero
browser containers or browser processes.

Desktop attachment `905681df-c014-47f0-9e0c-01f59c3d1eae` and mobile
attachment `5639d847-445b-441d-8a33-70037709bc53` were accepted through the
authenticated AX42 attachment boundary as `BROWSER_SCREENSHOT/IMAGE` evidence.
Their downloaded SHA-256 values exactly match the Playwright registry:
`9c52eccafaf54635063809ac3a4deabf788e821b5fecf33e7f785ae308282f26`
and
`e5f912bcdf5e695733df61f91cf24513d85856ae83ba398e3ee568073c27c6f5`.

The isolated non-production `atenea_test` database has all 48 Flyway rows and
indexes both attachments under exact WorkSession `96061`, project `9606`,
AgentRun `9606101`, worker `ax42-01` and preview
`f106453b-601a-47f3-9272-adafaa58ec7b`. The transactional index took 76 ms.
The physical Android device exposes no ADB transport; no device-browser claim
is included in this browser acceptance.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.4-playwright-attachments`;
the SHA-256 of its `SHA256SUMS` is
`af7b6b18ff1f325bb2d66ecd2d160fa9fe832d240a43d6283c5ebfaac351f9b3`.

The exact resume point is task 6.5 of `add-private-session-previews`.

Task 6.5 is complete and change progress is `29/37`. The exact preview lease
expired at `2026-07-29T02:20:01.698489Z`; the coordinator persisted
`EXPIRED` and removed its listener at
`2026-07-29T02:20:02.591403Z`, 0.893 seconds later. The tailnet route now
returns HTTP 000 while the separately owned runtime remains healthy and
loopback-only on `127.0.0.1:22243`.

Both attachment metadata records and both contents remain retrievable through
the authenticated boundary after route teardown. Their SHA-256 values remain
exactly
`9c52eccafaf54635063809ac3a4deabf788e821b5fecf33e7f785ae308282f26`
and
`e5f912bcdf5e695733df61f91cf24513d85856ae83ba398e3ee568073c27c6f5`;
the isolated Atenea index still binds both to WorkSession `96061` and AgentRun
`9606101`.

After those retained copies were reverified, only the exact temporary browser
scratch was deleted. There are zero preview-labelled browser containers, zero
Chromium/Playwright processes and no local-forward listener. The runtime,
allocation, worktree, Git, production, preview, Beautips and RAID state remain
unchanged.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.5-preview-teardown-retention`;
the SHA-256 of its `SHA256SUMS` is
`57a1de69afa5beb591e4145efc4f004f4154f129452af2b22c0167a415aabd66`.

The exact resume point is task 6.6 of `add-private-session-previews`.

Task 6.6 is complete and change progress is `30/37`. Preview
`05aa7e6e-f4a7-4621-aeda-248e491eeee6` was activated for the same exact
WorkSession, project, worker and allocation while the prior preview remained
terminal. Restarting only the AX42 preview coordinator changed its PID and
restored the same persisted unexpired route in 790 ms. Preview identity,
revision, ingress, upstream, lease and hard lifetime remained exact; the
runtime container and retained attachment hashes were byte-identical. The
prior expired record was byte-identical and was not restored.

An independent disposable Atenea acceptance database applied all 48 Flyway
migrations and retained the exact synthetic WorkSession, AgentRun, two
attachments, one expired preview and one unexpired ready preview. Two separate
Atenea startups reconciled only the ready row through authenticated finite
requests; the AX42 journal contains four successful exact-ownership inspections
and no request for the expired preview. Database state was unchanged across
both startups, no runtime was created or reassigned, and each application
process stopped cleanly without a remaining listener.

The worker credential was streamed only into an anonymous in-memory file
descriptor and was neither printed nor written to a filesystem. The final
credential helper inventory is empty. Production, preview, Beautips, rootful
Docker, RAID, runtime allocation and canonical Git state remain unchanged.
The preview subsequently reached its recorded lease expiry normally; that
post-window terminal state is retained separately and is not used to claim
that the accepted reconciliation remained ready indefinitely.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.6-restart-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`07836ce14b406d6fdb27d5b90653de02213b62b0ea91c94db6b0e234d1f21ea9`.

The exact resume point is task 6.7 of `add-private-session-previews`.

Task 6.7 is complete and change progress is `31/37`. Preview
`05aa7e6e-f4a7-4621-aeda-248e491eeee6` stopped receiving renewals and
reached its persisted lease at `2026-07-29T02:37:20.908708Z`. The coordinator
persisted `EXPIRED` and removed its route 0.881 seconds later, well inside the
60-second bound.

A separate exact synthetic preview,
`62f6ac6d-3248-48b0-9e16-710775a28a7d`, became `READY` revision 2 at the
same private ingress and returned HTTP 200 to Atenea. Its exact authenticated
stop completed in 49 ms as `STOPPED` revision 3 with no private URL. The
ingress listener was absent immediately after the response, and an independent
Atenea route probe failed closed with exit 7 and HTTP 000 in 107 ms.

Before and after fingerprints for the persisted allocation, runtime container,
worktree HEAD/tree/status and both attachment metadata/content pairs are
byte-identical. The runtime remains healthy and loopback-only at
`127.0.0.1:22243`; both preview services remain active and no browser process
exists. Production, preview, Beautips, rootful Docker, RAID and firewall state
remain unchanged.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.7-expiry-hard-stop`;
the SHA-256 of its `SHA256SUMS` is
`8112ff5559db5221ba4fefc06097f9c4b9395cf7addf941968bce710eed644ef`.

The exact resume point is task 6.8 of `add-private-session-previews`.

Task 6.8 is complete and change progress is `32/37`. The first canonical
Atenea run executed 379 tests with zero failures and 27 setup errors, all from
the same foreign-key guard: the exact Phase 6 attachment index created for
task 6.4 still referenced synthetic AgentRun `9606101` in the shared test
database. Immutable ownership checks resolved only the two attachment rows,
one preview row, AgentRun, internal turn, WorkSession and project created by
this acceptance. Their exact transactional removal left all seven fixture
counts at zero; physical AX42 attachments and the independent continuity
database were not changed.

The repeated canonical regression passed all 379 tests with zero failures,
errors or skips in 31.683 seconds. The programme-source worker regressions also
passed: preview protocol 12/12, attachment protocol 11/11, runtime engine, and
the complete project-runtime contract 8/8. The preview and attachment protocol
suites were independently repeated on AX42 and passed 12/12 and 11/11.

The installed coordinator verification passed service, listener, permission,
firewall and systemd-hardening checks using the persisted Atenea control-plane
identity. A preceding verification deliberately made no change and rejected
the operator-host address because it did not match that exact firewall rule.
All temporary suite directories are absent. Canonical Git trees are clean,
the preview ingress remains absent, the runtime remains loopback-only, and
production, preview, Beautips, RAID, firewall and rootful Docker remain
unchanged.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-6.8-regression-suites`;
the SHA-256 of its `SHA256SUMS` is
`f839c16318ef16e1a846f33f7d124bb95b6df0e3fd6c5435847e902cc9e4f0ef`.

The exact resume point is task 7.1 of `add-private-session-previews`.

Task 7.1 is complete and change progress is `33/37`. The canonical AX42
preview coordinator is disabled and inactive; its control and ingress
listeners are absent, while the separately owned synthetic runtime remains
healthy and loopback-only on `127.0.0.1:22243`. The three terminal preview
records, both preview firewall rules and installed worker program remained
byte-identical for the exact rollback acceptance in task 7.2.

Both retained attachment metadata documents and both PNG contents remained
readable through the authenticated attachment boundary. Their content hashes,
the two preview audit rows and the two independent attachment indexes were
unchanged. The disabled control endpoint fails closed from Atenea, while
production, preview, Beautips, RAID, rootful Docker, allocation, worktree and
Git fingerprints remain unchanged.

A retained `READY` read-model regression was found and closed before
acceptance: with the capability disabled, Atenea now retains the state and
audit copy but suppresses the private URL and returns primary action `NONE`.
Web and Android also require server-derived `OPEN` before exposing an open
action. Source commit `b605c8d5b063e7321edd60fec2265ec7ddb84ea9` is pushed.
Eight focused backend tests, the web build, Android core-console compile and
the complete final Atenea regression (`380/380`) pass.

Playwright used a disposable loopback-only Atenea instance and the real
preview read boundary. At `1440x900` and `390x844`, it proved the retained
state and disabled copy visible, zero open actions and zero horizontal
overflow. Both screenshots were inspected, the browser/application processes
were closed and all exact temporary authentication rows were removed.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.1-disable-affordances`;
the SHA-256 of its `SHA256SUMS` is
`f47c42242bcca2d482f0df879a455ddfbf9471483fc4b79cf1a0e52e52509e90`.

The exact resume point is task 7.2 of `add-private-session-previews`.

Task 7.2 is complete and change progress is `34/37`. The first exact AX42
rollback exited 0 in 547 ms and changed only the two Phase 6 UFW entries: the
control rule on `8789/tcp` from Atenea and the bounded tailnet ingress rule on
`19000–19031/tcp`. The coordinator remained disabled/inactive and no
coordinator or ingress process was started.

The identical rollback was repeated with the same immutable control-plane
identity and finite timeout. It exited 0 in 264 ms; complete worker
fingerprints after the first and second executions are byte-identical.
All three terminal preview record hashes, the runtime allocation/admission,
runtime container, worktree Git, attachment service, rootless inventories,
Beautips, RAID and every non-preview firewall rule remained unchanged.
Production and preview retained the same nine container identities and both
health probes returned HTTP 302.

The coordinator regression now includes an explicit unlabelled preview-like
candidate and proves its directory and payload hash remain unchanged after
rejection. Together with the existing partial-record, foreign non-synthetic
record and ambiguous allocation cases, it proves fail-closed preservation for
all four required classes. The accepted suite passes `13/13` locally and
`13/13` on AX42 from isolated temporary directories. No installed coordinator,
listener or projection was created, all suite directories are absent and only
the exact three-file staging directory was removed.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.2-idempotent-rollback-rejection`;
the SHA-256 of its `SHA256SUMS` is
`8a7d51fbcf435a8cbd67b5e72978b65fc8160ffc9495810f1413c67c98e50f20`.

The exact resume point is task 7.3 of `add-private-session-previews`.

Task 7.3 is complete and change progress is `35/37`. Before mutation, all
three remaining terminal worker projections were resolved by immutable preview
UUID, WorkSession `96061`, project, worker, runtime UUID, allocation
identity/fingerprint, ingress port, lifecycle revision, terminal state,
synthetic marker and exact record SHA-256.

With the systemd coordinator still disabled/inactive, the installed
coordinator's exact synthetic-delete contract removed only those three
validated records in 52 ms. The worker preview state root now has zero records
and zero child entries, with no control/ingress listener or coordinator
process. Complete before/after worker diff contains no other change.

The first projection-cleanup pass preserved the runtime because the design
treats runtime, worktree and Git as separate resources. Before archive, the
common Phase 6 rollback contract was rechecked and its explicit requirement to
stop the synthetic preview runtime was correctly treated as the separate
teardown authorization required by that design.

The installed mediated runtime client then stopped the exact slot3 runtime as
`stopped/stopped` in 616 ms. Only after validating immutable container,
network and image IDs, their complete engine/session/runtime labels, the
allocation hash, stopped state, engine owner marker and held admission record,
the correction removed container `f08f9993b621…`, network `9fd22daf1cb5…`,
image `sha256:b73b260ae26b…`, the owner-marked engine temporary root and its
regular lock. Cleanup exited 0 in 670 ms and released only this WorkSession's
slot3 admission.

There are now zero session-owned containers, networks, images, volumes,
runtime/preview listeners, browser processes and preview processes. The
allocation record, released admission record, worktree HEAD/status, bare
mirror HEAD/fsck, Git, logs, artifacts and both attachments remain. Beautips,
RAID `[UU]`, base services, rootful Docker `inactive/masked`, every non-preview
firewall rule and Atenea production/preview remain unchanged.

The independent continuity database remains byte-identical with two preview
audit rows, two attachment indexes and one synthetic AgentRun, proving worker
projection cleanup did not down-migrate retained history. Atenea production
and preview retain the same nine container identities and healthy probes.
Only the two exact task staging files were removed after verification.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.3-exact-projection-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`cf6edafe395f173e561520652278c8b65150294e3c5403f73257d6aff2153c24`.

Accepted supplemental teardown evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.3b-runtime-teardown-correction`;
the SHA-256 of its `SHA256SUMS` is
`ccfcd5612968eb43aa50549a5f1197447ff5513beb7bc750f49a52f2f65f4903`.

The exact resume point is task 7.4 of `add-private-session-previews`.

Task 7.4 is complete and change progress is `36/37`. The Phase 6 chain of
custody now indexes and independently verifies 15 artifact sets across their
owning hosts: entry gate and tasks 3–5 on Atenea, then tasks 6.1–7.3 on AX42.
Every internal `sha256sum -c SHA256SUMS` passes and every outer hash matches
the immutable value in this ledger.

Fifteen accepted PNGs remain indexed by exact SHA-256 across the operator UI,
private Playwright attachment and disabled-affordance evidence, including
desktop and mobile viewports. Command ledgers retain exit codes, finite
timeouts and durations. Bounded filename-only sanitization audits on both
artifact roots found zero credential-bearing patterns and zero forbidden auth,
cookie or credential filenames.

After task 7.3 sealed its retained database counts, the independent local
continuity database was resolved as disposable acceptance infrastructure by
its pre-recorded container and anonymous-volume identities. Only container
`2a18dabc20cd1716106e2ec82c08829ecdc879d239f4b11f28cfe88f8b055c1c`
and volume
`bf9b660be492ab5eda170dc449a8ec887e79b7894faa4de51cdbcf16352923b8`
were stopped and removed, exiting 0 in 475 ms; both are absent. This does not
down-migrate authoritative history, and the sealed task 7.3 evidence retains
the observed audit, attachment-index and AgentRun counts.

The supplemental task 7.3 teardown supersedes the rollup's interim live-runtime
line. Final state retains zero AX42 preview records, session-owned containers,
networks, images, volumes, runtime/preview listeners, browser/preview processes
and preview firewall rules; three unchanged Beautips containers, RAID `[UU]`,
rootful Docker `inactive/masked`, nine unchanged Atenea production/preview
containers and successful health probes remain.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.4-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`1c1b57d6a4f828e569e388b52c2439af02bde20ed91f7984bb2b1f4192563e28`.

The exact resume point is task 7.5 of `add-private-session-previews`.

Task 7.5 is complete and Phase 6 progress is `37/37`. Pre-archive strict
validation accepted the complete change. OpenSpec applied three added and
eight modified requirements across `isolated-project-runtime`,
`private-development-preview`, `worker-operational-safety` and
`worksession-attachments`, then archived the change as
`2026-07-29-add-private-session-previews`.

Post-archive strict validation passes all eight authoritative specifications
with zero failures and OpenSpec reports no active changes. Atenea source is
clean and synchronized at
`b605c8d5b063e7321edd60fec2265ec7ddb84ea9`; the programme branch is clean
and synchronized after the archive commit.

Phase 6 closes with the capability disabled, zero preview records/routes,
zero session-owned containers, networks, images or volumes, zero runtime or
preview listeners, released slot3 admission, preserved allocation, worktree,
mirror, Git, logs, artifacts and attachments, unchanged production and
Beautips, RAID `[UU]` and rootful Docker `inactive/masked`.

The exact resume point is the Phase 7 entry gate for
`establish-development-database-lifecycle`. No Phase 7 implementation or
authoritative development database operation has been executed yet.

Accepted final archive evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-private-session-previews/runs/task-7.5-archive`;
the SHA-256 of its `SHA256SUMS` is
`a86cc97f7847efe832b2d72aece0231341eccb73c708a06eebe2753f6b132bcb`.

## Phase 7 progress: establish-development-database-lifecycle

Tasks 1.1–1.5 are complete and change progress is `5/37`. The entry gate
proves clean synchronized programme and Atenea source Git, archived Phase 6,
strictly valid authoritative specs, unchanged nine-container Atenea
production/preview inventory and healthy public probes.

AX42 has RAID `[UU]`, 419826200576 bytes available, rootful Docker
inactive/masked, all four rootless engines and proxies healthy, unchanged
three-container Beautips in slot1, the foreign retained Phase 3 volumes in
slot2 and empty slots 3–4. Phase 6 left zero preview state, listener or
session-owned runtime resource.

Atenea production/preview PostgreSQL, Beautips and the retained Phase 3 Atenea
volumes are classified out of scope and were not read, mounted, started,
labelled, adopted or changed. Phase 7 accepts only two new deterministic
synthetic fixtures: pinned PostgreSQL and MariaDB with versioned migration/seed
rows and no production-derived data.

The approved contract uses named ephemeral secret files, private
integrity-addressed snapshots capped at three copies/seven days, sanitized
reports without raw dumps, a one-use five-minute revision-bound replacement
challenge and a verified pre-replacement snapshot. Authoritative activation
remains blocked until independent external backup passes restore.

The proposal, design, new `development-database-lifecycle` capability, three
modified capability deltas and 37-task plan pass strict OpenSpec validation.
Accepted sanitized entry evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`2acf24c1ac3a39b1dec979eea43ddcc50b87dffd8cd8b5a2a27baf65587b033a`.

The exact resume point is task 2.1 of
`establish-development-database-lifecycle`.

Tasks 2.1–2.5 are complete and change progress is `10/37`. The runtime
manifest now has one optional closed database contract accepting only pinned
PostgreSQL or MariaDB images, exact synthetic-development classification,
relative deterministic migration/seed inputs, one declared database port,
one required named database secret and fixed health, snapshot, retention and
explicit-replacement policies.

The two accepted fixtures contain only versioned generated schema and one seed
row each. A dependency-free state layer persists canonical database/
WorkSession/project/worker/allocation/slot/manifest ownership, derives
container/network/volume identities and writes strictly validated atomic
mode-0600 records. Lifecycle revisions are monotonic and idempotent.
Replacement challenges store only a SHA-256, bind to one revision, expire
after five minutes and are consumable once.

Private snapshot metadata binds exact ownership, lifecycle revision, byte
count and SHA-256. Retention selects but does not delete only exact synthetic
snapshots older than seven days or beyond three copies; foreign metadata fails
closed unchanged.

The focused state/schema suite passes `13/13` locally and `13/13` on AX42.
The complete project-runtime contract passes `8/8`. All isolated staging and
state-test directories are absent; no worker component was installed and no
runtime, volume, service, firewall, Beautips or production resource changed.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-2-manifest-state-contract`;
the SHA-256 of its `SHA256SUMS` is
`883533db49f7e1ffb98c088f053f838e935186dfe413b158fdf725b6088b2a47`.

The exact resume point is task 3.1 of
`establish-development-database-lifecycle`.

Tasks 3.1–3.6 are complete and change progress is `16/37`. AX42 now has a
root-owned fixed-operation database mediator, immutable state module, narrow
`atenea-worker` client and one exact sudoers delegation. The installation is
deliberately disabled: the enable marker is absent, reconciliation reports
zero records and performs no implicit create or start, and there is no
service, host listener, published database port or firewall rule.

The mediator accepts only `register`, `create`, `migrate`, `seed`, `health`,
`status`, `snapshot`, `prepare-replace`, `replace`, `restore`, `stop`,
`cleanup`, `retain`, `reconcile` and `verify`. It derives the rootless slot,
container, internal-only network, volume, image, endpoint and private snapshot
path from the exact allocation, manifest and persisted database ownership.
Caller endpoints, literal credentials, arbitrary Docker arguments,
production-like manifests and partial/foreign/ambiguous resources have no
accepted command surface and fail before resource mutation.

PostgreSQL uses custom-format `pg_dump`/transactional `pg_restore`; MariaDB
uses a single-transaction engine dump and fixed client restore. Replacement
first consumes a one-use five-minute revision-bound confirmation, then creates
and verifies an engine-native pre-replacement snapshot before deleting the
complete exact projection. Secret values exist only in a mode-0600 ephemeral
file owned by the admitted rootless slot user; outputs and evidence contain no
value.

The focused state suite passes `13/13`, the mediated worker suite passes
`9/9`, and the expanded project-runtime integration suite passes `10/10`
locally and on AX42. Repeated installation is idempotent and remains disabled.
The four rootless inventories still match entry: Beautips remains the only
slot1 workload, the two retained Phase 3 volumes remain in slot2, and slots
3–4 have no project resources. There are zero database lifecycle containers,
networks or volumes in every slot. Atenea is clean and synchronized at
`b605c8d5b063e7321edd60fec2265ec7ddb84ea9` with all nine production/preview
containers running; RAID remains `[UU]` and rootful Docker remains
inactive/masked.

The first AX42 integration invocation inherited an inaccessible administrative
working directory and stopped before mutation; repeating from `/tmp` passed.
The first install also exposed inherited setgid mode `2700` on the new state
root and stopped while disabled; the installer now normalizes both private
roots to `0700`, and its exact idempotent repetition passes. These corrections
did not create a database record or Docker resource.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-3d-final-accepted`;
the SHA-256 of its `SHA256SUMS` is
`71692f364c6844745b698607e9441fe9cf4bad8626baaa5d26712b4a07613e25`.
Earlier task-3, task-3b and task-3c runs are retained as superseded audit
history; the accepted task-3d run proves the final warning-free binary at
SHA-256 `785780ba9a29310f884300aecb4ec274bc9c72cdb196f7f7506550b42dc8d216`.

The exact resume point is task 4.1 of
`establish-development-database-lifecycle`.

Task 4.1 is complete and change progress is `17/37`. PostgreSQL owns
WorkSession `1e452a4a-8b06-40a6-837e-952bcaa74c7e`, database
`925bce0d-7662-4e15-97d1-13f7e1f97a5a` and slot3. Its canonical mirror,
session worktree, immutable allocation and admission record are persisted.
The worktree is clean at programme commit
`102057745733de264b335a1ae77a0b6c3268c54d`.

Slot3 admission was free, but the archived Phase 6 allocation record still
claimed the slot. Before reuse, its sealed SHA-256
`58b77d11384d79fd50a88fc5d3052048337859e9fd97eac1b027ba7ed5203672`,
released admission and zero exact resources were re-proven. The byte-exact
record was moved into task 4.1 evidence; its worktree, mirror, Git, logs and
artifacts remain in place. No foreign allocation or resource changed.

The first database create exposed that the rootless daemon cannot bind a
secret from host-global `/run`, even though the slot user can read it. The
attempt created no container and its exact new network/volume were removed by
the mediator. The corrected boundary uses the slot's own XDG runtime tmpfs,
`/run/user/1103`, with a mode-0600 file owned only by `atenea-slot3`. No
secret value appears in output, process arguments or evidence.

The final idempotent create persists state `CREATED`, revision `2`, one
completely labelled container, one internal-only network and one named volume.
There are no published host ports, database listeners or firewall rules.
Beautips remains three running containers, Atenea remains clean/synchronized
with nine running production/preview containers, RAID has three `[UU]` arrays
and rootful Docker remains inactive.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-4.1-postgresql-create`;
the SHA-256 of its `SHA256SUMS` is
`4d5e9f55072401ba973c23bd4b99ccf3c8e33ca44dd49eac1d6ebe1cfdf62158`.
It also supersedes the task-3d installed-worker hash with the XDG-runtime
correction, SHA-256
`07e250df652120bd3a3d6a07e0b28f2d8dff12e1aafcd5cf1fe79f9690366c01`.

The exact resume point is task 4.2 of
`establish-development-database-lifecycle`.

Task 4.2 is complete and change progress is `18/37`. The fixed PostgreSQL
migration advanced revision `2 -> 3`, the fixed seed advanced `3 -> 4`, and
the fixed `select-one` health acceptance advanced `4 -> 5`. The resulting
synthetic identity is one row and four declared columns; evidence retains only
their counts and SHA-256-like MD5 comparison digests, never raw row content.

Late retries of migrate, seed and health now return the existing `HEALTHY`
revision `5` without re-executing SQL or changing state. The initial mediator
had used the stable rootless proxy for `docker exec`; real acceptance showed
that proxy carries normal Docker calls and stdin but drops hijacked stdout.
The corrected mediator validates the persisted slot user's real Unix socket
type and owner, then executes as that user against
`/run/user/<slot-uid>/docker.sock`. It still cannot select rootful Docker or a
caller-provided/foreign slot.

The accepted resource has an internal-only network, no published port and no
listener on allocated loopback port `24752`; a finite connection attempt is
denied. Slot4 cannot inspect or enumerate any container, network or volume for
the PostgreSQL WorkSession. Atenea production/preview remains nine running
containers, Beautips remains three, RAID remains `[UU]` and rootful Docker
remains inactive.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-4.2-postgresql-migrate-seed-health`;
the SHA-256 of its `SHA256SUMS` is
`d6672c69e49cdf11cae44974c4d6fbb4c585f0a8485ec13aab95d24b1948755f`.
The accepted mediator SHA-256 is now
`7ad5e07c7b0507a4032629c1db86102f2f8e6bebf62a0bd982ae0f761f4250e5`.

The exact resume point is task 4.3 of
`establish-development-database-lifecycle`.

Task 4.3 is complete and change progress is `19/37`. An explicit
custom-format PostgreSQL snapshot was stored privately at revision `5`, then
one replacement challenge advanced the bound revision to `6`. Its value lived
only in memory, expired after five minutes by contract and is absent from
evidence; persisted audit retains only its SHA-256, operation UUID
`276ea038-61ad-4058-9cad-dcd1f039b45e`, bound revision and consumed state.

Confirmed replacement created and verified a second engine-native snapshot
before removing any exact database resource. It then replaced only the
session-labelled container/network/volume projection, reapplied the fixed
migration and seed, and returned `HEALTHY` at revision `13`. The container
immutable ID changed while the persisted resource names, allocation, slot,
project, WorkSession and database identities remained constant. The
deterministic row count/digest still matches.

Both raw snapshots remain mode-0600 beneath the private snapshot root. Their
byte counts and SHA-256 values match immutable metadata; neither dump nor a raw
row is attached. The accepted initial interactive run retained fixed
timeouts/exit codes but not per-command duration, so task 4.5 will repeat the
whole lifecycle with a duration-bearing harness.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-4.3-postgresql-confirmed-replacement`;
the SHA-256 of its `SHA256SUMS` is
`6f42070eba6b6490d0d6eb1c3cd8f9a2dc7c48426458e1d4e7aef4e47cb2ddd2`.

The exact resume point is task 4.4 of
`establish-development-database-lifecycle`.

Task 4.4 is complete and change progress is `20/37`. The automatic
pre-replacement snapshot `c0417c78-8b0b-4669-bccd-d83cd6a7057a` was
re-verified by size, SHA-256, database, WorkSession, engine, allocation and
synthetic ownership before restore.

Fixed `pg_restore --clean --if-exists --single-transaction` advanced
`HEALTHY 13 -> RESTORING 14 -> HEALTHY 15`. The restored row-count/content
digest exactly matches the pre-replacement digest. Restore changed neither the
container immutable ID nor the worktree: HEAD remains
`102057745733de264b335a1ae77a0b6c3268c54d`, tree remains
`6cb26b9cce81496ca5e02e8ea0a7d1ce5e04b1b4`, status is clean and `git fsck`
passes. No raw dump or row entered evidence.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-4.4-postgresql-restore`;
the SHA-256 of its `SHA256SUMS` is
`c6b624c7cb138ae29a6f60b68309a0b93d15fc18c1c728ece84f9af824780ff2`.

The exact resume point is task 4.5 of
`establish-development-database-lifecycle`.

Task 4.5 is complete, the PostgreSQL section is `5/5`, and total change
progress is `21/37`. A duration-bearing harness repeated the complete
lifecycle from revision `15`: exact stop/cleanup, create plus duplicate
create, migration, seed, health, explicit snapshot, prepare/confirmed replace,
restore and late migration/seed retries.

Exact cleanup removed only the PostgreSQL session's container, internal
network and volume. Recreate regenerated the same persisted names with a new
container identity. The duplicate create retained revision `17`; late
migrate/seed retries retained final revision `30`. Confirmed replacement
created and verified another pre-snapshot, returned healthy revision `28`,
and restore of the explicit snapshot returned healthy revision `30`.

All thirteen measured operations exited `0` within their finite timeouts.
Observed durations ranged from 52 ms to 3982 ms. Final data fingerprint equals
the original/restored fingerprint, Git is byte-identical and clean, snapshots
remain private, and no confirmation/secret/raw row/raw dump entered evidence.
Atenea production/preview remains nine running containers, Beautips remains
three, RAID remains `[UU]` and rootful Docker remains inactive.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-4.5-postgresql-repeat`;
the SHA-256 of its `SHA256SUMS` is
`3497a6da2a888283633c99172ffa07dba702cf273a347a43b37c695788617cd2`.

The exact resume point is task 5.1 of
`establish-development-database-lifecycle`.

Task 5.1 is complete and change progress is `22/37`. MariaDB owns separate
WorkSession `0fd2c888-07f0-4a47-a762-0eae444a166a`, database
`7b15eb56-86a7-465b-bc28-f00e47b57068` and slot4. Its independent mirror,
clean worktree, allocation and held admission are persisted at programme
commit `1e0ac9e42051cac6b768f09de8ad65507fd09791`.

The idempotent create persisted `CREATED` revision `2`, one exact labelled
container, one internal-only network and one named volume. Its secret is a
mode-0600 file owned by `atenea-slot4` beneath that slot's XDG runtime tmpfs.
There is no host publication, loopback listener or firewall rule. The
PostgreSQL WorkSession remains independently `HEALTHY` in slot3, Beautips
remains three running containers and RAID remains `[UU]`.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-5.1-mariadb-create`;
the SHA-256 of its `SHA256SUMS` is
`83e182e3c4c011fc55d089e4e9587f04eee82277171f8e46fb379961a450afff`.

The exact resume point is task 5.2 of
`establish-development-database-lifecycle`.

Task 5.2 is complete and change progress is `23/37`. The first MariaDB
migration stopped safely in `CREATED` after its 90-second bounded health wait.
Read-only diagnosis proved the server and named-file authentication healthy;
the fixed client argv had supplied the database once as `$1` and again inside
`$@`. No SQL or lifecycle revision changed during that failed attempt.

Both engine clients now bind `database="$1"` and `shift` before passing the
remaining fixed arguments. The mediated worker suite passes `10/10`, and the
installed worker SHA-256 is
`e45142209c1d0a24640f6d13ee2c7b9d56891efa36f0aa1365d24085a1272473`.
MariaDB migration, seed and health then advanced revisions `2 -> 5`; late
retries retain `HEALTHY` revision `5` without executing SQL again.

Evidence retains only one-row content digest and four-column schema digest.
The network is internal, no listener exists on allocation port `26853`, a
finite loopback connection fails, and isolated slot3 cannot inspect or list
any slot4 MariaDB resource. No raw row or credential was retained.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-5.2-mariadb-migrate-seed-health`;
the SHA-256 of its `SHA256SUMS` is
`d457d257195f94e162ba12f03fe1ec48b3c3f17a7e302ee3ab287a2817340ea1`.

The exact resume point is task 5.3 of
`establish-development-database-lifecycle`.

Task 5.3 is complete and change progress is `24/37`. One explicit MariaDB
single-transaction snapshot and one automatic verified pre-replacement
snapshot match their private byte counts, SHA-256 values and exact immutable
ownership metadata.

Operation `ed436137-65ac-43f7-a9ea-cf0622815a6c` consumed its five-minute
revision-6 challenge without retaining the confirmation. Replacement changed
the container immutable ID, preserved all persisted resource/WorkSession/
project/allocation/slot names, reapplied migration/seed/health and returned
`HEALTHY` revision `13`. The deterministic data digest still matches, and no
raw dump or row is attached.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-5.3-mariadb-confirmed-replacement`;
the SHA-256 of its `SHA256SUMS` is
`56501214400d19a216959252e89344bc9ae000345a7b69ef12a237bd0d56bef6`.

The exact resume point is task 5.4 of
`establish-development-database-lifecycle`.

Task 5.4 is complete and change progress is `25/37`. The verified automatic
snapshot was imported first into a derived staging database. Only after the
import succeeded, one MariaDB `RENAME TABLE` statement atomically exchanged
`phase7_items`; the staging and backup databases were then removed.

Restore advanced `HEALTHY 13 -> RESTORING 14 -> HEALTHY 15`. Zero derived
restore/backup databases remain, the data digest matches pre-replacement, the
container immutable ID is unchanged, and MariaDB worktree HEAD
`1e0ac9e42051cac6b768f09de8ad65507fd09791`, tree and clean status are
unchanged with passing `git fsck`. No raw dump or row entered evidence.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-5.4-mariadb-restore`;
the SHA-256 of its `SHA256SUMS` is
`f432db394e1410dc00390537f3c24eb3b81a812a3437fac5e4ea9b3e2d6cbf55`.

The exact resume point is task 5.5 of
`establish-development-database-lifecycle`.

Task 5.5 is complete, the MariaDB section is `5/5`, and total change progress
is `26/37`. The duration-bearing second cycle repeated exact stop/cleanup,
create plus duplicate create, migration, seed, health, explicit snapshot,
prepare/confirmed replace, atomic restore and late migration/seed retries.

All thirteen operations exited `0` within finite timeouts; durations ranged
from 50 ms to 9268 ms. Cleanup removed only the MariaDB session's exact
container, internal network and volume. Final state is `HEALTHY` revision
`30`, duplicate/late retries changed no revision, data digest and Git match,
and the confirmed replacement/restore retained no confirmation, raw dump,
raw row or secret.

PostgreSQL remains independently `HEALTHY` in slot3. Atenea production/preview
remains nine running containers, Beautips remains three, RAID remains `[UU]`
and rootful Docker remains inactive.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-5.5-mariadb-repeat`;
the SHA-256 of its `SHA256SUMS` is
`fb976c12b179c520d9e4d238d8c7b2eb131d3991adc476619fde117cc9f8e77b`.

The exact resume point is task 6.1 of
`establish-development-database-lifecycle`.

Task 6.1 is complete and change progress is `27/37`. Cross-slot Docker inspect,
DNS resolution and labelled resource enumeration all fail in both directions.
Neither database container contains the mediator client, sudo, any Docker
socket, worker state root or private snapshot root, so a WorkSession runtime
has no authority to request snapshot, replace, restore or cleanup.

A complete fingerprint of both records, all snapshot metadata/content and both
live resource identities/labels is byte-identical before and after the denial
attempts. The trusted global `atenea-worker` mediator remains the only caller
and still requires exact persisted database ownership before an operation.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.1-cross-session-isolation`;
the SHA-256 of its `SHA256SUMS` is
`2c68ff9dfadc270ca2184f93b5a974b4574f8099e4a93fba6e6f9f71eec3c70a`.

The exact resume point is task 6.2 of
`establish-development-database-lifecycle`.

Task 6.2 is complete and change progress is `28/37`. Against PostgreSQL
revision `30`, missing confirmation arguments, stale revision `29` and an
incorrect confirmation were rejected with unchanged complete fingerprints.
After an actual 305-second wait without changing system time, the exact
revision-31 challenge returned `REPLACEMENT_CONFIRMATION_EXPIRED` and the
record, snapshots and resources remained byte-identical.

One new explicitly confirmed replacement was then executed only to establish
a consumed revision-32 operation; it returned `HEALTHY` revision `39`.
Replaying the exact same operation returned `STALE_REVISION`, and its complete
post-success fingerprint remained byte-identical. Confirmation values existed
only in shell memory and are absent from artifacts.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.2-confirmation-denials`;
the SHA-256 of its `SHA256SUMS` is
`446d0dc6b9786bc18ffe1f93f7373ad819633e7578fd08eeb638ef0127309d87`.

The exact resume point is task 6.3 of
`establish-development-database-lifecycle`.

Task 6.3 is complete and change progress is `29/37`. MariaDB was stopped and
exact-cleaned while preserving its record/snapshots. Four temporary collisions
were then created with pre-recorded immutable Docker IDs: unlabelled,
partially labelled, fully labelled foreign, and an ambiguous exact-container/
foreign-network projection.

Every mediated create returned ownership denial before mutation, and each
fixture's complete inspect SHA-256 was identical before/after rejection. Only
then was each fixture removed by its recorded exact container/network ID.
MariaDB was reconstructed from persisted ownership and returned `HEALTHY`
revision `35`.

The PostgreSQL record remained byte-identical. Beautips, slot2 retained Phase
3 resources, RAID and firewall share one unchanged before/after fingerprint.
Atenea's clean Git plus exact nine-container production/preview fingerprint is
also identical. The `13/13` state suite reconfirmed production-like manifest
denial, while the CLI still exposes no caller endpoint, literal credential or
arbitrary resource argument.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.3-target-and-resource-denials`;
the SHA-256 of its `SHA256SUMS` is
`e1baca72a4fbacd2a94507a5bfdbfbec5a94d1f301a59ac8af4cd9a3036f5e4b`.

The exact resume point is task 6.4 of
`establish-development-database-lifecycle`.

Task 6.4 is complete and change progress is `30/37`. The slot 3 and slot 4
rootless Docker daemons were restarted with finite timeouts, then a fresh
process-per-invocation mediator reconciled exactly the two persisted database
records with `implicitCreation=false`. Both exact database containers remained
exited under restart policy `no`; no container create/start event occurred and
rootful Docker remained inactive.

Container, WorkSession-network and volume identities were byte-identical
before and after. Docker expectedly regenerated only each daemon's built-in
unlabelled `bridge` network, so that daemon-private identity is explicitly
normalized while every WorkSession resource ID remains strict. Records,
snapshot metadata/content, workspaces, Git files, host boot ID and RAID have
one unchanged static fingerprint.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.4-rootless-restart-reconcile`;
the SHA-256 of its `SHA256SUMS` is
`715a6cca3dee81475a6d6fc7add73b15dc32415525c41295439cf4bc73c01bc4`.

The exact resume point is task 6.5 of
`establish-development-database-lifecycle`.

Task 6.5 is complete and change progress is `31/37`. Two immutable fixture IDs
were recorded before creating one expired, exact-owned synthetic snapshot per
database. The first retention pass removed exactly the registry-computed
expired/excess IDs; PostgreSQL and MariaDB each retain the three newest
verified copies within seven days. A second pass removed nothing.

Every retained content file was checked against its recorded SHA-256 and size,
but no dump bytes or rows enter evidence. Database records, workspaces, host
boot, RAID, rootful Docker and all four slots' complete container, network and
volume inventories share one unchanged before/after fingerprint. Atenea's
clean Git and nine-container production/preview inventory also remain
byte-identical.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.5-bounded-snapshot-retention`;
the SHA-256 of its `SHA256SUMS` is
`888f28b9a182b0690fc14222880de06e5c6f05d07aaa8d72a4d0566b64b168bf`.

The exact resume point is task 6.6 of
`establish-development-database-lifecycle`.

Task 6.6 is complete and change progress is `32/37`. Two independent accepted
passes each completed `13/13` database state/manifest tests, `10/10`
mediator/engine tests and `10/10` project-runtime integration tests. Each pass
also read both persisted engine records/resources and reconciled exactly two
`HEALTHY/RUNNING` records with `implicitCreation=false`.

The integration harness ran as `atenea-worker` from a temporary exact source
copy owned by that executor. Two earlier fail-closed attempts are retained:
the harness first rejected root-owned test workspaces, then rejected an
inaccessible inherited working directory. Neither attempt mutated database
lifecycle state. All accepted invocations have finite timeouts, exit zero and
recorded durations.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-6.6-double-regression`;
the SHA-256 of its `SHA256SUMS` is
`4fe5bce53459130a91028da6a985f71fba33bb3b3e49463b81e0dd8cdccabcf7`.

The exact resume point is task 7.1 of
`establish-development-database-lifecycle`.

Task 7.1 is complete and change progress is `33/37`. New database operations
are disabled and both exact synthetic records are `STOPPED/STOPPED`.
Containers remain present and exited; their networks, volumes, six retained
snapshots, records, worktrees and allocations are preserved. Reconciliation
reports only the two persisted stopped records and creates nothing.

The first rollback attempt exposed a contract gap before any container
mutation: the disabled mediator also rejected `stop`. The boundary was
minimally corrected so only exact-ownership `stop` and `cleanup` remain
available as rollback actions while registration, creation, snapshots,
replacement and other new work stay disabled. The corrected implementation
passed `13/13` state tests, `10/10` worker tests and `10/10` integration tests;
its installed SHA-256 is
`d4bf3ea20bbd1ea5d083a4a46de61aa3c52a45c64a4a74bd97e3084c91764ab8`.

Snapshots, exact resource IDs and the protected platform fingerprint are
byte-identical across the accepted run. Atenea's clean Git and nine-container
production/preview inventory are unchanged.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-7.1-disable-stop-preserve`;
the SHA-256 of its `SHA256SUMS` is
`f07c7b394466c6c5d36e38d30757798206baba1484c424903bbee899afbb1685`.

The exact resume point is task 7.2 of
`establish-development-database-lifecycle`.

Task 7.2 is complete and change progress is `34/37`. Disabling the lifecycle
and stopping both exact persisted database IDs was repeated with finite
timeouts. Both records were already stopped, all calls were idempotent and a
complete fingerprint of records, snapshots, workspaces, allocations,
admission, every rootless container/network/volume/image, boot, RAID, rootful
Docker and firewall remained byte-identical. No additional resource was
deleted.

The sealed task 6.3 evidence was reverified file-by-file and its accepted
`SHA256SUMS` hash remains
`e1baca72a4fbacd2a94507a5bfdbfbec5a94d1f301a59ac8af4cd9a3036f5e4b`.
That real acceptance proves unlabelled, partial, fully foreign and ambiguous
fixtures retained identical inspect hashes throughout rejection and were
removed afterward only by pre-recorded exact IDs. A fresh `10/10` mediator
suite reconfirmed the denial paths. No fixture needed recreation during the
no-mutation rollback repeat. Atenea production/preview also has one unchanged
fingerprint.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-7.2-repeat-rollback-denials`;
the SHA-256 of its `SHA256SUMS` is
`34a137f6ab06b676800dd7198b6f2934587f3cc7a9fcc5d4e31a82c621599f99`.

The exact resume point is task 7.3 of
`establish-development-database-lifecycle`.

Task 7.3 is complete and change progress is `35/37`. Cleanup now validates the
complete container/network/volume projection and every retained snapshot
before its first deletion. Its `11/11` worker tests include a fail-closed case
where a foreign network prevents all deletion; the `13/13` state and `10/10`
integration suites also pass. The installed worker SHA-256 is
`4dd6dc93ca36726e2c523dc0d99eb5baab75af357bf9170f111aacee96ea5196`.

Exact final cleanup removed two stopped containers, two session networks, two
labelled data volumes, six private snapshot metadata/content pairs, two
ephemeral secret roots and two terminal database records. Reconciliation is
empty with `enabled=false` and `implicitCreation=false`; no allocated database
listener or Playwright/Chromium process remains.

The slot3 and slot4 admissions are released. Their allocation records were
archived byte-for-byte into accepted evidence only after exact resources were
absent and capacity was released. Both clean worktrees, mirrors and Git heads
remain. Four pre-existing anonymous slot4 volumes have incomplete ownership
labels, so fail-closed cleanup deliberately preserved them unchanged; images
also remain unchanged as shared immutable cache.

Beautips remains three running containers, retained slot2 resources are
unchanged, all three RAID arrays are `[UU]`, rootful Docker remains inactive,
and the firewall, AgentRuns and foreign-resource fingerprint is identical.
Atenea's clean Git and nine running production/preview containers also retain
one unchanged fingerprint.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-7.3-exact-final-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`667096b7bcb995753e7bae903b9a5c15bd8ffa669a182cec3fa0c749e5227be9`.

The exact resume point is task 7.4 of
`establish-development-database-lifecycle`.

Task 7.4 is complete and change progress is `36/37`. The final rollup
reverified all `25` prior evidence packages file-by-file and records each
relative package, file count, byte count, `SHA256SUMS` digest, result and audit
duration. It inventories `23` sanitized command ledgers and `11`
timeout/exit-code/duration ledgers.

The complete Phase 7 artifact tree has no symlink, special file,
world-accessible file, raw snapshot, dump, environment file, credential file
or unmistakable private-key/token pattern. Versioned SQL migration and seed
files are deterministic synthetic programme inputs rather than captured
database output. No dump bytes, result rows, credential values or environment
captures enter the rollup.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-7.4-sanitized-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`cfdc552c9078f9f907ba5f147925f7281d66562b7c72c906adfcc769774f4dac`.

The exact resume point is task 7.5 of
`establish-development-database-lifecycle`.

Task 7.5 is complete and Phase 7 progress is `37/37`. Pre-archive strict
validation accepted the complete change. OpenSpec applied the new
`development-database-lifecycle` capability plus the isolated-runtime,
operational-safety and attachment deltas, then archived the change as
`2026-07-29-establish-development-database-lifecycle`.

Post-archive strict validation passes every authoritative specification and
OpenSpec reports no active Phase 7 change. The programme branch and Atenea
source are clean and synchronized after the archive commit.

Phase 7 closes default-disabled with zero database records, exact containers,
session networks, labelled volumes, private snapshot files, database
listeners or browser processes. Slot3 and slot4 admission is released; their
allocation records are archived while worktrees, mirrors, Git and sanitized
evidence remain. Beautips and retained slot2 resources are unchanged, RAID is
`[UU]`, rootful Docker remains inactive and Atenea production/preview remains
nine running containers.

Accepted final archive evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-development-database-lifecycle/runs/task-7.5-archive`;
the SHA-256 of its `SHA256SUMS` is
`60b29553abef2b1b0a7bbe79b5f6c1d9a85e53e581fd0bf511175c78dc44b3c1`.

The exact resume point is the Phase 8 individual-project onboarding entry
gate. No real project has been activated by Phase 7.

## Phase 8 progress: onboard-atenea-on-ax42

Tasks 1.1–7.5 are complete and change progress is `41/45`. The entry gate pins
GitHub `jlnieto/atenea`, branch
`feature/actualizar-conversacion-en-web`, commit
`b605c8d5b063e7321edd60fec2265ec7ddb84ea9` and manifest SHA-256
`3b26e1899a06993bee69ac596e7cb69b6200a37d063d98203ad308058c91bfa3`.
Atenea source and its control-plane checkout are clean and synchronized; the
Dropbox `atenea` folder is four documentation files, not a Git source.

The first two projects are explicitly ordered Atenea then Beautips. All other
projects remain disabled. Atenea uses empty migrated PostgreSQL plus declared
synthetic fixtures, requires no localhost preview compatibility, publishes
only an exact WorkSession draft delivery and keeps all non-Git artifacts
non-authoritative until an external backup passes restore.

Following the current Codex non-interactive contract, an isolated probe used
`codex exec --ephemeral`, ignored user config/rules, selected a read-only
sandbox and completed in `4873 ms`. Only exit code, timeout, duration and
expected-output SHA-256 were retained. `codex login status` identified the
authentication method, but no `auth.json`, internal session, token, cookie,
credential or environment was read or copied by orchestration. The real pilot
uses a bounded per-run process, a Bubblewrap workspace-write filesystem
namespace and a collected transient cgroup. The Codex CLI's nested sandbox is
disabled only inside that reviewed namespace because AX42 rejects nested
unprivileged user namespaces. Only the exact derived
worktree, canonical Git common directory, private result directory and
Codex-owned authentication/session boundary are mounted. The child denies
loopback, RFC1918, Tailscale and link-local destinations while retaining
public Codex egress. The prompt remains on stdin and only the thread, turn,
final answer and fixed summary enter the result.

`project-codex-v1` has versioned request/result schemas and an exact root-owned
Atenea registry. Unknown fields, caller commands, paths, remotes, endpoints,
environments, foreign project/workspace identities and an empty allowlist fail
closed. Duplicate dispatches retain one execution, exact cancellation does not
affect another process, and restart reconciliation never silently duplicates
an uncertain turn. The existing authenticated tailnet port is reused; no public
or additional listener is introduced.

AX42 retains four active rootless daemons, free container slots 2–4, three
running Beautips containers, three RAID arrays `[UU]`, active Tailscale/UFW,
inactive rootful Docker and disabled real worker/preview/database capabilities.
Atenea retains nine running production/preview containers. No runtime, route,
database or real AgentRun was created by the gate.

The worker was installed, enabled, verified, disabled and rolled back twice.
Its final state is `disabled/inactive`, port `8787` has no listener or UFW
rule, the exact project registry is disabled with zero workspaces, and the
installed runner/config are root-owned. Focused tests pass locally and on
AX42. AX42 lacks the optional `jsonschema` Python module, so schema validation
runs in the repository environment while portable runner tests exercise argv
isolation and thread continuity on AX42. A first remote test invocation
recorded exit `2` because its test file had not yet been copied; corrected
bounded invocations are retained rather than hiding that setup failure. The
first network baseline selected a tailnet SSH destination that does not admit
AX42 and timed out; the corrected control uses AX42's reachable tailnet
attachment listener, proves it reachable without the child policy, then proves
the same tailnet and loopback destinations denied while public egress remains
available. An initial broad `pgrep -f` matched its own capture shell; the
authoritative corrected final state uses exact listener, firewall and transient
unit counts.

The repository-wide test entrypoint was also attempted, but Compose stopped
before tests because two pre-existing local test containers already owned its
fixed names. The attempt-created empty network and unused volume were removed
by their exact recorded identities; the older containers were left unchanged.
The protocol suites above are green. The corrected source mount was then used
for the two complete regressions recorded at task 3.6.

Atenea commit `467e2abed1e86e9b8eac5fac2fcec2df59825be7` completes
the control-plane integration. Each newly selected remote WorkSession now
persists a UUID external session identity and one immutable workload kind;
each project AgentRun additionally persists the exact Atenea project,
repository, branch, base commit and manifest hash before dispatch. The
separate `ATENEA_REMOTE_WORKER_PROJECT_CODEX_ENABLED` gate defaults false,
synthetic routing remains compatible, and a worker lacking the exact
capability leaves a new session local.

The client sends no caller command, path, endpoint or environment and carries
the prior external thread UUID only for continuation. Terminal application
maps the returned thread, turn, final answer and summary once. Focused tests
cover exact selection/denial, payload, persistence, cancellation, bounded
partition, startup reconciliation without redispatch and duplicate terminal
delivery. Migration V49 passed against PostgreSQL test state. Two final full
regressions each passed `391/391` in `32.337 s` and `32.537 s`; production
configuration and its nine running containers did not change.

Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`fdaf300e4057ce174785a55dee832ff1cac78db8aee4bb0ca8604a1a3a1ba049`.

Protocol evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-2-project-codex-worker`;
the SHA-256 of its `SHA256SUMS` is
`2bad7bca1e4771746df14b01b8441c0c2594a663d6909f88081b963447b14abf`.

Control-plane integration evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-3-control-plane-integration`;
the SHA-256 of its `SHA256SUMS` is
`a204af05e56a8719623b80b688c75f172a81a26ba4f6a6093e059333462ae4c9`.

The canonical acceptance owns WorkSession
`c20f3cde-9a64-4c7b-a674-7b63f94ca475`, branch
`atenea/session-c20f3cde-9a64-4c7b-a674-7b63f94ca475`, external Codex thread
`019facd4-89cc-7cf3-a289-f0190b9a1767`, slot 3 and heavy admission 1. Its
worktree remains pinned to
`b605c8d5b063e7321edd60fec2265ec7ddb84ea9`; the two accepted turns created
only `docs/ax42-onboarding-acceptance.md`, with SHA-256
`5eb0ecbbe266063473e78d44b884c2d7fbab42594e1a946762d347278c3203b8`.
The second turn reused the same thread, exact replay reused its execution and
left both worker state and project content unchanged, and a new observer
connection recovered the same session, workspace, branch, thread and terminal
state.

The disposable control plane records all ten failed hardening attempts and
three successful protocol executions; only the final two successful turns are
the accepted project mutation. Every failed attempt left the project
unchanged. A complete foreign workspace was denied with
`workspace_ownership_conflict` while its registry and worker-state
fingerprints remained unchanged. No session runtime container, network,
listener or temporary result directory remains, and production retains its
nine unchanged containers.

Canonical acceptance evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-4-canonical-worksession-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`1f0659e909dcf05af91d1bcaf6c6af05a4b108bcfa7ed5a4b57c99f32d265394`.

Task 5.1 builds the archived exact WorkSession commit rather than the dirty
operator worktree. The final mediated invocation completed the Vite production
build with 1,583 modules and Maven `clean package` with `380/380` tests, zero
failures, zero errors and zero skips. It produced executable JAR SHA-256
`aaed96b9639bf8501c7692b39fcfdfb9ef66f597811b178fe8b08998523ab9e8`
in 53,211 ms.

Four preceding fail-closed invocations remain in the evidence ledger. They
exposed, in order, the missing isolated test PostgreSQL, dependency resolution
on an internal-only build network, the absent writable integration-test
scratch and its missing exact workspace-root setting. The accepted adapter now
uses an ephemeral exact-owned PostgreSQL container and test network plus a
tmpfs `/workspace/repos`; every temporary build resource is removed after the
invocation. No runtime, PostgreSQL volume or allocated listener was started.
The WorkSession still has only its task-4 documentation change, and Atenea
production retains its nine unchanged containers.

Task 5.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.1-build-tests`;
the SHA-256 of its `SHA256SUMS` is
`be08c49c59b805356a9a50a6a3e82b94cc290c9bdf3d16391a29c1fa19ba564d`.

Task 5.2 starts the exact slot-3 runtime with three session-labelled
containers, one internal network, one retained PostgreSQL volume and only the
three allocated loopback projections. The web actuator is `UP`. PostgreSQL
initialized from the empty volume, applied `48/48` successful migrations and
retains zero rows across the declared domain tables; the declared fixture set
is empty.

The first fail-closed start found that the allocation had persisted
zero-length development secret placeholders. The mediator now generates only
those exact placeholders atomically after validating ownership, mode and
length, and never emits or retains their values. A second start reached a
healthy migrated runtime but rejected historical administrative expectations
of 45 migrations and non-empty fixtures. The corrected status check accepted
the already-running resources in 718 ms without recreating any identity.
Production retains its nine unchanged containers.

Task 5.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.2-rootless-runtime`;
the SHA-256 of its `SHA256SUMS` is
`4a09f4067af42718cb8c88690724543ff67d24fff247a6ea98f935e5ea295390`.

Task 5.3 proves the running application cannot reach public Internet, Atenea
production/preview, Atenea SSH or PostgreSQL. Its root filesystem is
read-only, all capabilities are dropped, no devices or privileged mode exist,
and Docker sockets, runtime proxies, host root and foreign workspace paths are
absent.

An exact mediated restart passed in 14,879 ms. The three container IDs and
retained volume fingerprint remained unchanged, the migration summary stayed
`48|1|48|48|0|48`, declared domain rows stayed zero and the actuator returned
`UP`. Only the three exact RootlessKit projection-record IDs rotated; their
loopback addresses and allocated ports did not. WorkSession Git and the nine
production containers remain unchanged.

Task 5.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.3-isolation-persistence`;
the SHA-256 of its `SHA256SUMS` is
`118400fe8660e0012ab77f4a64bc61f3b761ce4b7876484b3a32f194e8dc120c`.

Task 5.4 creates exact synthetic preview
`a6b4a872-8cfe-495f-a457-25af7593f256` on tailnet-only ingress
`100.81.98.93:19000`. Operator and Atenea probes retrieved the SPA root with
HTTP 200 and the same 449-byte body SHA-256
`3555271f84b38f49b72634d5134693d82b96607332f3f92a738ba5abb7480404`.
Both public probes to `167.235.186.151:19000` timed out after 15 seconds with
HTTP 000 and zero response bytes. UFW limits ingress to `tailscale0` from the
tailnet range and limits control to the exact Atenea tailnet identity.

Atenea declares no localhost compatibility requirement, so the coordinator
returned `localhostCompatible=false` and `tunnel=null`; no localhost forward
or temporary listener was created. The known committed manifest path
`/admin/login` still returns HTTP 404 while the relocation-accepted SPA route
`/` returns HTTP 200. The discrepancy remains explicit and no WorkSession pin,
source or runtime was changed to conceal it.

The exploratory preview expired under its bounded lease and was deleted only
through its exact persisted synthetic identity. The accepted preview was
created and renewed once to revision 3. Production, preview, Beautips, the
slot-3 runtime and Git fingerprints remain unchanged.

Task 5.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.4-tailnet-preview`;
the SHA-256 of its `SHA256SUMS` is
`03079faab79ccee57e477bcb816d16b07e28b2d366f24ecfbfec3f2ad79ddd7a`.

Task 5.5 runs Playwright 1.60.0 and Chromium 148 against the real tailnet
preview. Both `1440x900` and `390x844` loaded the SPA root with HTTP 200 and
proved visible `Acceso de operador`, `Backend disponible`, both credential
fields and the disabled empty-input `Entrar` action. Each viewport has exact
document/body width, no horizontal overflow, no failed or external request and
positive in-viewport boxes for every critical element.

The first real browser attempt exposed a preview-forwarder defect:
non-blocking `sendall()` truncated the 313,903-byte JavaScript bundle after
43,772 bytes. The accepted bounded bidirectional pump delivers the complete
bundle and a new 2.75 MiB regression passes with all `15/15` preview tests.
The installed and source program SHA-256 is
`678b3f66e18f792e29f06ae83bfc8cc08bbbeea0cc04d07bae4d06cf61ab070f`.

Both original-resolution screenshots were inspected. The desktop and mobile
login states have a clear operational-status hierarchy, readable copy and
fields, consistent spacing, no clipping, overlap or misleading empty state.
Their SHA-256 values are respectively
`a00a037ecea12f4dbb805b977285144a7655d0fac6861681a866e663f9f3b03c`
and
`761494d34127842802f59f027a3f2794c5280795c1ba885f3dbae6b1e248839b`.
Page, context and browser closed in `finally`; the guarded browser boundary is
idle with no task-owned process. Runtime, production, preview, Beautips and
WorkSession Git remain unchanged.

Task 5.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.5-playwright-visual`;
the SHA-256 of its `SHA256SUMS` is
`ac6da0210f252e08e84e12d5b71d62614e7f1005dd74d85678d3574f2c4ae0d4`.

Task 5.6 registers the desktop PNG, mobile PNG and DOM report as three exact
`EVIDENCE`-retained synthetic attachments for WorkSession
`c20f3cde-9a64-4c7b-a674-7b63f94ca475`. The first PUTs returned HTTP 201;
repeating the same immutable attachment identities returned HTTP 200 with the
original metadata and introduced no duplicate bytes.

The attachment boundary now accepts the existing positive-decimal WorkSession
identity or a canonical UUID while malformed/non-canonical values still fail
closed. All `12/12` attachment tests pass, and the installed/source program
SHA-256 is
`139401e9b336264af29d6f3a20493ed3185e630496e9d261628b62364121be12`.

After registration, the expired preview was deleted only through exact
preview ID `a6b4a872-8cfe-495f-a457-25af7593f256`, revision 5 and complete
synthetic ownership. Its record and ingress listener are absent. Two complete
post-teardown retrieval passes returned HTTP 200 for all three metadata and
content identities; every byte count and SHA-256 matches the original
registered artifact. The records remain explicitly non-authoritative
synthetic evidence. Runtime, production, preview, Beautips and WorkSession Git
remain unchanged.

Task 5.6 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-5.6-artifact-retention`;
the SHA-256 of its `SHA256SUMS` is
`8e68d17226bff549222d9166fe1fd175fa51879ef8b52169f0846c3dd307ed55`.

Task 6.1 commits the canonical documentation change as
`0230c6b973692205ed9a17f8015cd151269d8080`, tree
`d2feee00f9ab2efdb858f77b47536dcb638e1639`, on exact branch
`atenea/session-c20f3cde-9a64-4c7b-a674-7b63f94ca475`. The AX42 worktree and
both disposable control-plane checkouts are clean.

The normal authenticated Atenea publish endpoint created draft pull request
`jlnieto/atenea#4`. GitHub reports exact base
`feature/actualizar-conversacion-en-web` at
`649edba356e104695ce7ca0713f9b86e54b02d36`, exact WorkSession head at the
commit above, one documentation commit, state `OPEN`, `isDraft=true` and
`MERGEABLE`. Atenea persisted the same branch, URL and final commit.

Delivery now creates draft pull requests and reuses a pre-existing remote
WorkSession branch only when its head equals the local head. Missing branches
use a normal non-force push; different or ambiguous heads fail closed before
GitHub mutation. The disposable control plane additionally consumes GitHub
authentication through a named token file. Its first tokenless real publish
failed closed with HTTP 502; the accepted attempt consumed an ephemeral
credential without putting it in configuration, arguments, output or
evidence. The exact secret file, external acceptance configuration, Git bundle
and transfer ref were removed immediately after use.

Focused delivery tests pass `7/7`, the named-token-file test passes `1/1` and
the final complete regression passes `397/397`. The runtime remains `UP` with
the same three containers, internal network and retained PostgreSQL volume;
the nine production/preview containers and three Beautips containers remain
unchanged.

Task 6.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-6.1-draft-delivery`;
the SHA-256 of its `SHA256SUMS` is
`01631b47930c76270433c15c876a0686b6af476516edddaa152e2f0eed8fae78`.

Task 6.2 merges pull request `#4` through the normal GitHub merge operation.
Merge commit `b94aacd4dae52f7567156e15710faae66062e814` has exact latest base
`849ceee3293dcc7ce461ee04a564ea12958f5dd3` and immutable WorkSession head
`0230c6b973692205ed9a17f8015cd151269d8080` as its two parents. Both are
ancestors of the merge commit. The WorkSession remote branch still points to
its original head, so no force update or branch deletion occurred.

Atenea synchronization now requires the GitHub pull request number, canonical
URL, base repository/ref, head repository/ref and head SHA to match the exact
persisted WorkSession identity. Cross-session metadata fails closed before
persistence or notification. Repeating a successful `MERGED` sync does not
emit a second merge notification. The complete regression passes `399/399`.

The real sync endpoint ran twice and returned identical material delivery
state: WorkSession `OPEN`, pull request `MERGED`, the same workspace identity,
branch, final commit and original publication timestamp. A disposable
cross-session fixture retained MD5
`d6c507484f57e9e7270c5c9bbe38bf25` across both calls, then exact ID,
ownership, SHA and MD5 preconditions removed only its project and WorkSession
records. Both fixture IDs are absent.

The ephemeral GitHub token file was deleted after the first sync; the second
used only the running control process's in-memory credential. Zero
non-terminal AgentRuns and zero push-notification log rows remain. Runtime,
production/preview, Beautips, the AX42 worktree and both control-plane
checkouts remain healthy and clean.

Task 6.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-6.2-merge-sync`;
the SHA-256 of its `SHA256SUMS` is
`89f10cbfd82d576cf54b94860d4586e209a4d18f4eb794603fc52879b0455b3b`.

Task 6.3 closes the canonical WorkSession through Atenea's normal reconciled
endpoint at `2026-07-29T10:01:03.245941289Z`. Final state is
`CLOSED/CLOSED`, delivery remains `MERGED`, the exact workspace identity,
pull-request URL and final commit remain persisted, and there is no close
block or retryable close state.

The shared exact PR validator now also protects close. A repository, number,
base, head or SHA mismatch blocks before checkout or branch deletion; the
complete regression passes `400/400`. Accepted close fetched origin, checked
out base branch `feature/actualizar-conversacion-en-web`, fast-forwarded to
`b18f8a38d41006728c2cdf9518e3f9af20cccc87` and removed only the merged
WorkSession branch locally and remotely.

The merged base history, pull request and AX42 worktree retain exact
WorkSession commit `0230c6b973692205ed9a17f8015cd151269d8080`. The AX42
worktree remains clean on its local WorkSession branch. The exact runtime
remains `UP` with its original three containers, internal network and retained
volume. Ten session artifacts, ten runtime logs and six retained attachment
files survive, and the accepted 5.6, 6.1 and 6.2 checksum files remain
unchanged.

An exact repository-local credential helper consumed the named ephemeral
token only for the normal remote branch deletion. Its config entry, helper,
token and external configuration were removed immediately after close.
Production/preview and Beautips fingerprints remain unchanged.

Task 6.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-6.3-canonical-close`;
the SHA-256 of its `SHA256SUMS` is
`49fe27c0d084a46295a2cb9803526a83ddb597b2e959433ffd0924f97078c0dd`.

Task 6.4 restarted only `atenea-agent-run-worker-v1.service`. Its PID changed
from `446520` to `538943`; the service returned healthy with the same
`project-codex-v1` capability after a finite readiness wait. The complete
durable state remained byte-identical: 28 executions, including the 13
terminal records owned by the canonical WorkSession and its three successful
turns, retained the same dispatch, execution, workspace, lease, thread,
revision and terminal identities with `reconcileRequired=false`.

No new dispatch, prompt turn, transient project unit or project process was
created. The allowlist and installed mediator/runner hashes, AX42 WorkSession
Git HEAD/tree/clean status and runtime health are unchanged. Canonical
rootless Docker inspection confirms the same three slot 3 runtime containers,
network and retained volume and the same three slot 1 Beautips containers.
The nine accepted production/preview container identities and the clean
control repository also match the sealed task 6.3 boundary.

Task 6.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-6.4-worker-restart-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`bc0b1ebdb7d1f6d91c4cc1833f7426808a0ea0c1b40bbf939a7a5201150abf7d`.

Task 6.5 proves the accepted Atenea boundary remains available without opening
a session or rerunning a prompt. The healthy mediator advertises
`project-codex-v1`; its exact selection/execution allowlist retains only
Atenea and the canonical workspace. Authenticated retrieval returned the three
accepted terminal turns with their original dispatch, execution, workspace,
thread and turn identities.

Immutable denial probes for Beautips, Yvateve, ISC, Recambios, Fomasys and
Checkpol each returned HTTP 403 `project_ownership_conflict`. An exact Atenea
identity with an unknown workspace progressed to the narrower fail-closed
`workspace_ownership_conflict`, proving that availability does not bypass
persisted ownership. All seven dispatch IDs remain absent and the complete
durable execution file is byte-identical at 28 records with zero non-terminal
executions. Runtime, WorkSession Git, production, preview and Beautips remain
`UP` with their accepted identities.

Task 6.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-6.5-atenea-availability-denial`;
the SHA-256 of its `SHA256SUMS` is
`0c8011a01b0667da1a5f1bbd03b777b7b287ced9fb0fa02887e10ab21a5ee198`.

Task 7.1 first disabled only new Atenea real-project selection. The mediator
remains healthy with synthetic compatibility but no longer advertises
`project-codex-v1`; execution is disabled and the exact persisted workspace is
retained for reconciliation.

The first mediated stop blocked before resource mutation because the adapter
required the live worktree HEAD to remain at admitted base `b605c8d`, although
normal accepted delivery had cleanly advanced it to `0230c6b`. The adapter now
validates the exact admitted base tree and requires it to be an ancestor of
the clean current HEAD while retaining exact manifest and Compose hashes.
Divergent history remains fail-closed. Focused adapter validation and the
complete project-runtime contract pass `10/10`; real status then returned
`ready/healthy`.

The accepted mediated stop returned `stopped/stopped`. A task-scoped cleanup
validated five exact ownership labels and immutable IDs before removing only
the three stopped slot 3 containers and their empty internal network. It
removed zero images and volumes. The labelled PostgreSQL volume, allocation,
`slot3/heavy1` held admission, disabled workspace registration, mirror,
worktree HEAD/tree/clean index, delivery, logs and sanitized evidence remain.
The preview projection was already absent; session listeners and transient
project/browser processes are zero. Production, preview and Beautips remain
`UP` with unchanged container identities.

Task 7.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-7.1-atenea-project-rollback`;
the SHA-256 of its `SHA256SUMS` is
`b5e9fbb0c7657c82ce95459bf9e0a3f6551ded59abbed32501e23fdcd77d7cb3`.

Task 7.2 repeated project disable, mediated stop and exact cleanup without
recreating the runtime. Stop remained `stopped/stopped`; cleanup removed zero
networks and every disabled allowlist, workspace, allocation, held admission,
durable execution and installed adapter hash remained byte-identical.

Four sequential task-owned network fixtures reused the absent runtime network
name with literal no labels, partial labels, complete foreign ownership and
complete Atenea labels on an ambiguous immutable ID. Each immutable ID,
creation time, driver, labels and full inspect SHA-256 was recorded first.
The cleanup gate rejected all four with exit 65
`RUNTIME_OWNERSHIP_CONFLICT`; every inspect fingerprint remained byte-identical
and the resource remained present during rejection. Each fixture was then
revalidated and removed only by its recorded immutable ID.

Final inventories for all four rootless slots exactly equal their pre-fixture
inventories. There are zero fixture/session containers, networks, owned
images, listeners or temporary project/browser processes, while the retained
PostgreSQL volume remains. Production, preview and Beautips are `UP` with
unchanged identities.

Task 7.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-7.2-rollback-idempotence`;
the SHA-256 of its `SHA256SUMS` is
`2db41894002dd536c2719a7d04f889218bfee595a35605095242efe095c5920b`.

Task 7.3 released `heavy1` before `slot3` through the versioned admission
boundary. The retained admission record is now `released/released`, capacity
reports zero normal and heavy use, and idempotent release verification returns
the same state.

After exact cleanup and capacity release, the allocation record was copied
byte-for-byte into accepted evidence at SHA-256
`bd45cac9d22f03ccdf2ef0d2759d850e6200c094953e8d37f419160c5e961e29`.
The original persisted allocation remains unchanged. The disabled worker
registry then unregistered only the exact canonical session/workspace identity
and now contains zero workspaces.

The mirror refs, WorkSession HEAD/tree/clean index, control source, merged
GitHub pull request `#4`, persisted workspace record, durable terminal
executions, retained PostgreSQL volume and all sealed task evidence remain
unchanged. Runtime/preview/listener/project/browser process counts remain zero;
production, preview and Beautips are `UP` with unchanged identities.

The accepted release operations emitted harmless inaccessible inherited-cwd
warnings after their successful fixed record scans, and one post-copy shell
substitution probe was malformed after the archive had already been copied.
Both are retained transparently. Clean idempotent release and direct
persisted/archive SHA comparison supersede those non-mutating warnings.

Task 7.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-7.3-release-allocation-archive`;
the SHA-256 of its `SHA256SUMS` is
`da48445d6f83f99119e587e6a10a5325baa0aa4fc959c61f73b49b383aa2d0aa`.

Task 7.4 proves slot 1/Beautips and the complete slot 2 and slot 4
container/network/volume inventories are byte-identical to the sealed entry
gate. Slot 3 has no session container, network, owned image or listener and
retains only the expected labelled PostgreSQL volume beyond its unchanged
default networks.

All three RAID1 arrays report `[UU]` with filesystem headroom. SSH, Tailscale,
UFW, the three private mediators, worker-health timer, four rootless daemons
and four stable socket proxies are active. Rootful Docker, its socket and
containerd remain inactive/masked, `/var/run/docker.sock` is absent and the
database lifecycle gate remains disabled.

UFW has the eight original IPv4/IPv6 base rules plus exactly four reviewed
IPv4 tailnet-only mediator rules: attachment `8788`, AgentRun `8787`, preview
control `8789` from the control-plane address and preview ingress
`19000:19031` from the tailnet CIDR. The expected nftables hash therefore
differs from the pre-install entry hash only after these reviewed additions.

Production and preview retain the same nine full container identities and both
actuator probes are `UP`. Beautips retains its three full identities and is
`UP`. Programme, Atenea source and WorkSession Git are clean and synchronized
at their expected heads.

Task 7.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-7.4-final-nonimpact`;
the SHA-256 of its `SHA256SUMS` is
`70a039182d7400e8f80f9d0640e35ebf2389c4fc40e2dc8827ae9a5044116b75`.

Task 7.5 passes two independent regression cycles. Each worker/manifest cycle
passes the AgentRun worker `11` tests, project runner `6` tests, positive
Atenea adapter, negative policy corpus and complete project-runtime contract
`10/10`. Each focused Atenea cycle passes all `15` remote-worker tests.

Both complete canonical containerized Atenea regressions pass `400/400` with
zero failures, errors or skips. The first durations were 187 seconds for
worker/manifest, 8 seconds focused and 33 seconds complete; the second were
188, 7 and 35 seconds.

One ignored two-file Python `__pycache__` generated by a nested focused suite
was removed by its exact directory after both accepted passes. Final programme
and Atenea Git, installed/source adapter hash, disabled zero-workspace worker
registry, released admission, durable executions, empty slot 3 projection,
retained volume and production/preview/Beautips health match the pre-test
fingerprint exactly.

Task 7.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-7.5-double-regressions`;
the SHA-256 of its `SHA256SUMS` is
`c39f1e78f4a57660c6975c0fc07bc09a22da21ed316b6d3884d0e31abee21091`.

Task 8.1 revalidates all `20/20` preceding accepted evidence packages
file-by-file. The rollup covers `381` files and `743150` bytes; all `85/85`
modern command metadata records contain the sanitized command description,
start/end timestamps, duration, exit code and finite timeout. It indexes the
two retained Playwright screenshots and `97` command/meta ledger files.

The prohibited-material audit finds zero forbidden filenames and zero risky
content files. The final boundary remains disabled with zero registered
workspaces, released normal/heavy admission, clean synchronized programme and
Atenea Git, intact task 7.5 evidence and all three production, preview and
Beautips health probes `UP`.

Task 8.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-8.1-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`1fede0bb37fdac444d10a7cd50c031aaca1abe244e25d18f99c063609a644512`.

Task 8.2 applies D-038's finite 15-minute close window. Normalized samples at
minute `0`, `5`, `10` and `15` are byte-identical. Across all four, project
selection/execution stays disabled with zero registered workspaces, normal and
heavy admission stay released, all `28` durable executions remain terminal
and the exact session runtime, preview, listener, transient unit and browser
process projection remains zero.

The canonical PostgreSQL volume, allocation, admission, workspace, worktree,
mirror and all accepted artifact files remain intact. All four rootless slot
inventories, three RAID arrays `[UU]`, the reviewed firewall, base/mediator
services and inactive/masked rootful Docker boundary remain unchanged.
Atenea production, preview and Beautips retain their exact container
identities and all three health probes remain `UP`.

The first pre-window harness invocation exited `1` before an accepted sample
because it used a nonexistent mirror path and lowercase terminal-state names.
That read-only diagnostic is retained transparently. The corrected harness
uses the canonical mirror and uppercase protocol states, restarted at minute
zero and completed all four accepted samples without drift.

Task 8.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-8.2-disabled-clean-observation`;
the SHA-256 of its `SHA256SUMS` is
`151165a3f9d8a045e53382dedc7b9619d0c62093e6d2b25436f8f176050ac40c`.

Task 8.3 passes pre-archive strict validation at `45/45`. OpenSpec creates the
`atenea-project-onboarding` capability, applies five reviewed requirement
updates and archives the completed change as
`2026-07-29-onboard-atenea-on-ax42`. Post-archive strict validation passes all
`10/10` authoritative specifications and reports zero active changes.

The first pre-archive count assertion exited `2` after successful validation
because an empty pending-task match was not normalized to integer zero. A
subsequent archive attempt exited `1` without changing files because the
active safety delta referenced a requirement title superseded by an earlier
archive. The delta was reconciled with the authoritative
`Least-privilege execution` and `Safe garbage collection` requirements while
preserving their existing scenarios. OpenSpec then archived successfully. Its
generated trailing blank lines caused one post-archive `git diff --check` exit
`2`; those three formatting-only lines were removed and the complete strict
and boundary validation passed. All diagnostics are retained transparently.

Atenea source remains clean and synchronized at
`b18f8a38d41006728c2cdf9518e3f9af20cccc87`; its explicit push was already
up-to-date. The worker remains disabled/released, task 8.2 evidence revalidates
and production, preview and Beautips remain `UP`.

Task 8.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-atenea-on-ax42/runs/task-8.3-openspec-archive`;
the SHA-256 of its `SHA256SUMS` is
`79475771be27cc2297f38fc4cec0b15b3f77a46bf834b188f1bc72aab300eb13`.

The exact resume point at the Atenea archive boundary was the entry gate for a
separate `onboard-beautips-on-ax42` change. At that boundary it had not yet
been created and Beautips managed routing had not been enabled or modified;
the separate entry gate below begins from that preserved state.

## Phase 8 progress: onboard-beautips-on-ax42

Tasks 1.1–3.5 are complete and change progress is `20/45`. GitHub
`jlnieto/beautips`, branch `main`, managed-manifest commit
`e9e0b3c319c518363d4135f5378ebbddced96dfb`, tree
`533d32f97ae362997ad003170a826da674c31c1d`, runtime manifest SHA-256
`365f1c66c51c9018c2c6f48deddbaa619b4588cae2dd463dcd916cde884e2e82`
and managed Compose SHA-256
`840e64166e8e1ddaefb74d11763fe150e6539074bb02c3173e2175a446555941`
are pinned. The entry commit and legacy manifest remain recorded as reviewed
ancestors, not as enabled runtime authority.

The clean laptop commit `a6d2f28` and clean Atenea commit `bd15a16` were strict
ancestors of GitHub; AX42 already matched. Only ancestry-proven
`pull --ff-only` was used. All three copies are now clean and synchronized at
the pinned head without merge, reset, force update, deployment or container
restart.

The healthy administrative Beautips pilot remains three rootless slot 1
containers with its existing network, loopback listener, root-owned manual
secret boundary and four persistent PostgreSQL/Redis/assets/imports volumes.
These are foreign retained controls and cannot be registered, mounted,
relabeled, snapshotted, stopped or cleaned by the managed WorkSession.

The managed acceptance will use another admitted slot with empty migrated
PostgreSQL, disposable Redis, invented versioned tenants/users/loyalty/files
and distinct session volumes. Current manual data, backups, legacy dumps,
production rows and credential values are excluded. WhatsApp embedded signup,
webhooks, scheduler, outbox and external Graph API access remain disabled.

The two local backup folders are on the laptop root filesystem, and AX42 has
no restic, borg or rclone target. They are not an independent restore-tested
backup, so all non-Git acceptance state remains synthetic, non-authoritative
and cleanup-bound. The pilot declares no required localhost compatibility;
any origin/cookie/redirect failure blocks and requires an explicit manifest
revision.

Managed project selection/execution remains disabled with zero registered
workspaces. Atenea production/preview, the administrative Beautips pilot, all
four rootless daemons, RAID `[UU]`, firewall and inactive/masked rootful Docker
remain healthy and unchanged.

Task 2.1 removes the legacy fixed port, project, Docker network, tracked
env-file and cleanup-disabled command contract. The accepted runtime-contract
v1 manifest points only to a separate managed Compose definition. That
definition receives the WorkSession identity, runtime identity, loopback web,
PostgreSQL and Redis ports, network and four volume names from persisted
allocation values and applies complete ownership labels. It declares an
internal network, disables restart and WhatsApp scheduling/credentials, and
requires stop cleanup of volumes, orphans and locally built images. The manual
`docker-compose.yml` remains byte-identical.

Draft 2020-12 schema validation, Compose non-interpolating validation and
static denial of the legacy literals pass. Two identical synthetic allocation
calls produced byte-identical session paths, Compose/network/volume names and
three unique loopback ports; the fixture was then moved to trash. The mandatory
local `dev redeploy beautips` completed and local health is `UP`.

The AX42 registry remains
`selectionEnabled=false`, `executionEnabled=false`, with zero workspaces. The
three exact slot 1 administrative container identities remain running and
Beautips health is `UP`. Atenea's exact nine production/preview identities
remain running and both health probes are `UP`. Two unrelated
`atenea-onboard-task4-*` containers observed on the control-plane host were
retained unchanged and excluded from this task.

Task 2.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.1-session-safe-manifest`;
the SHA-256 of its `SHA256SUMS` is
`43ca64baf25a2a4f76a51f5ca0362cc4640ca02dedc9b0d19683beb070e8d621`.

Task 2.2 adds one closed source allowlist containing exactly Beautips. It pins
GitHub repository, branch, commit, tree, runtime manifest, managed Compose,
worker `ax42-01`, normal workload and allowed slots 2–4. Both selection and
execution are false, slot 1 is excluded and the workspace map is empty.

The allowlist SHA-256 is
`e3ad1824c7a134280f907b2831b75391c3791373060806fb1827dc05cb6756fc`;
its exact Draft 2020-12 schema SHA-256 is
`1fc4d61a46e10ea9a6b7201573daef5b50267f13d252e20c6dab062e6fee10e2`.
Valid-format foreign repository, branch, commit, tree, manifest, Compose,
worker, slot, workspace, project and unknown-field mutations all fail schema
validation.

The registry remains source-only and was not installed on AX42. The installed
Atenea registry retains SHA-256
`26a7d75cc4c3d919b82ee6efeb8e7d4214e53d4854ad34dc1985d36aceb7a94a`,
is disabled with zero workspaces and the existing worker remains active.
Focused worker and project-runner regressions pass `11/11` and `6/6`.
Administrative Beautips and Atenea production/preview retain their exact
running identities and all health probes are `UP`.

Task 2.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.2-disabled-exact-allowlist`;
the SHA-256 of its `SHA256SUMS` is
`a4c60545032856054db1b9980a83cfb1413fddde59c632aacc09998d5555b9d2`.

Task 2.3 adds a closed, source-only mediator for exactly ten reviewed
operations: Node build, Maven test, Compose build, runtime
start/health/logs/stop/cleanup and functional/customer smoke. It accepts only
the canonical WorkSession UUID plus a symbolic operation and derives every
other identity from persisted allocation and the exact source allowlist.

All plans have a finite timeout, named synthetic secret references and
`executionEnabled=false`. Caller commands, paths, endpoints and environments
are not request fields. The plan schema rejects unknown fields; the mediator
rejects unknown operations, `slot1`, noncanonical sessions, duplicate or
foreign ports, project/path/Git drift and altered manifest or Compose before
operation execution.

The two Beautips smoke scripts now have a managed mode that does not load
repository `.env` and requires explicit named inputs. Manual mode remains
unchanged. Mandatory local redeploy completed and health is `UP`. Four focused
mediator tests, worker `11/11` and runner `6/6` regressions pass. The mediator
and updated allowlist remain absent from installed AX42 paths; the existing
Atenea registry is still disabled with zero workspaces. Administrative
Beautips and Atenea production/preview retain exact running identities and all
health probes are `UP`.

Task 2.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.3-reviewed-operation-mediator`;
the SHA-256 of its `SHA256SUMS` is
`940e412d45833ce2a25223e4a279966258faedf57c77e4f2f7ae377f9f3c1e1f`.

Task 2.4 adds an exact Beautips identity adapter around the already accepted
Codex runner. The adapter pins the base runner SHA-256
`de84b0c96908677e334184b9290691a2116b963dd37483022f97a0fd57ed44d1`
and changes only project, repository, branch, commit, manifest and canonical
Git common-directory identity. Its own SHA-256 is
`55e8f585e19f6a19d3c51aaf7532b1cf0f74f6b087ae0d1ef67faaea3029b73b`.

The inherited execution boundary retains the transient systemd cgroup,
Bubblewrap workspace-write namespace, exact WorkSession worktree and Beautips
mirror mounts, finite timeout, cancellation and thread continuity. It denies
loopback, RFC1918, Tailscale and link-local destinations and does not mount the
manual Beautips workspace, Docker socket or `auth.json`.

Four focused adapter tests pass exact config/workload, real
Git/manifest/allocation fingerprints, foreign identity denials and sandbox
mount/network assertions. The accepted base runner remains `6/6`. The adapter
is not installed, no Codex process ran and the installed Atenea registry stays
disabled with zero workspaces. Administrative Beautips and Atenea
production/preview remain `UP`.

Task 2.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.4-exact-codex-sandbox`;
the SHA-256 of its `SHA256SUMS` is
`d4853f1712db7130fdb3442957684e4799977774de567448f304835dec9de37b`.

Task 2.5 adds a WorkSession-derived synthetic secret boundary with exactly
four separate names: PostgreSQL password, smoke administrator email/password
and smoke seal code. The exact directory is mode `0700`; files and value-free
metadata are mode `0600` under the worker service identity. Preparation is
byte-idempotent and outputs only names plus `valuesExposed=false`.

The tool accepts no caller value, env file or path. Ambient manual/WhatsApp
variables are ignored. `.env`, WhatsApp, token, cookie, unknown, symlink,
partial and unsafe-mode entries all reject the boundary. Three focused tests
and the four dependent mediator tests pass; generated values lived only under
automatically removed `/tmp` roots and none entered evidence.

The secret tool remains uninstalled, no real WorkSession secret was generated,
the installed Atenea registry remains disabled with zero workspaces and
administrative Beautips health is `UP`.

Task 2.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.5-synthetic-secret-boundary`;
the SHA-256 of its `SHA256SUMS` is
`0ab26949f1ba66c1f44a2fbe5375dc49aabd88c0914cdef9ca8fe4649150cb3c`.

Task 2.6 installs a durable, default-disabled Beautips lifecycle boundary on
AX42. It installs the exact mediator, project runner, secret boundary,
operation registry and immutable source allowlist under
`/usr/local/libexec/atenea`, plus a separate runtime config with
`selectionEnabled=false`, `executionEnabled=false` and zero workspaces. The
sudoers boundary names only the exact Beautips runner and config.

Plan, apply, verify, selection-enable, enable, disable and rollback are
implemented. Repeated apply is byte-idempotent. Enable without exactly one
persisted workspace fails with exit `65`; modified installed artifacts fail
closed and remain untouched; rollback removes only exact disabled Beautips
artifacts and preserves the shared base runner. The installed lifecycle tool
also verified and rolled itself back after the deployment staging bundle was
removed, then was installed again in the final disabled state.

AX42 listener and UFW digests are identical before and after. The installed
Atenea registry and shared runner hashes are unchanged, the worker service
remains active, and the administrative Beautips, Atenea production and Atenea
preview health probes are `UP` with their retained exact identities. No
runtime, workspace, listener, firewall rule, service restart or routing was
created.

Task 2.6 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.6-install-lifecycle`;
the SHA-256 of its `SHA256SUMS` is
`eb1d01c689a09e2936eea19f7a792c289e88102e7b5e2d60acf6744c4d3e2e28`.

Task 2.7 adds an aggregate Beautips worker-contract regression. Three focused
cases validate the Draft 2020-12 manifest, exact cleanup argv, private
no-localhost preview, three service identities, loopback ports, internal
network, four session-labelled volumes and absence of fixed containers,
manual paths or env files. Two mediation calls produce an identical cleanup
plan bound to the exact slot socket, Compose project, WorkSession and runtime.

The aggregate also passes mediator ownership `4/4`, Codex identity/sandbox
`4/4`, secret boundary `3/3`, the complete install lifecycle and inherited
project idempotence/cancellation/restart `3/3`. The final source passes locally
in `71.38 s` and twice on AX42 in `20.75 s` and `17.86 s`.

The administrative checkout remains intentionally at its retained entry
commit and was not used as the managed source. AX42 tests used an exact
temporary checkout of the pinned managed commit and removed it afterwards.
Ubuntu `python3-jsonschema` and `python3-pyrsistent` were installed as the
missing worker test prerequisite; apt reported no service or container
restart. All temporary roots and test processes are absent.

Final Beautips selection/execution remains false/false with zero workspaces.
AX42 listener/UFW fingerprints, the active worker, exact administrative
Beautips identities and Atenea production/preview identities and health are
unchanged.

Task 2.7 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-2.7-worker-contract-tests`;
the SHA-256 of its `SHA256SUMS` is
`5978278bc7db11f36258040bd3969d2c85fc6196c9afac5d7c65feef2bb97983`.

Task 3.1 adds a separate default-false Beautips control-plane gate. Exact
project name `Beautips`, canonical repository path, project branch `main` and
WorkSession base branch `main` select `project-codex-v1` only when the global
worker gate and the Beautips gate are enabled and AX42 advertises that
capability. The existing real-project gate cannot select Beautips. Partial or
foreign name, path or either branch remain local without contacting the
worker; missing capability also fails closed.

Atenea source is committed and synchronized at
`2f92c7ba8d869d79ed3a12f5758661d01174f7c7`, tree
`88e348b688f63a6f0ae6e827d817fe60aa93fe86`. Its laptop and server checkouts
were reconciled by exact ancestry guards and `ff-only`. The Beautips
control-plane checkout was likewise ancestry-reconciled to the already
accepted GitHub commit and tree. Focused selector tests pass `11/11`; the
selector, client and AgentRun set passes `26/26` both locally and from the
committed Atenea server source.

No production deployment, selector environment, WorkSession, AgentRun, lease,
routing record or database mutation was created. Production and preview
actuator checks are `UP` over their loopback-published ports. AX42 retains
three exact administrative Beautips containers in slot 1, empty slots 2–4,
four active rootless daemons, RAID `[UU]`, inactive/masked rootful Docker and
administrative Beautips health `UP`. Canonical identity persistence before
dispatch remains exclusively task 3.2.

Task 3.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-3.1-exact-beautips-selection`;
the SHA-256 of its `SHA256SUMS` is
`1558e608f35e6b9412bfdc4e1dbfb3eea0af0b62a89ffd44848f14cf8c3142f9`.

Task 3.2 reuses the additive remote-routing persistence model and adds no
database migration. An exact Beautips queued run now persists target
repository path, selected worker, remote session UUID, derived workspace,
workload, project identity, repository URL, branch, accepted commit and
manifest SHA-256 before dispatch registration. The remote execution identity
remains null until the worker accepts that persisted dispatch UUID.

Acceptance requires worker `ax42-01`, workload `project-codex-v1` and workspace
`remote:ax42-01:work-session:<remote UUID>` in addition to the exact project
and branch identity from 3.1. A foreign workspace fails before
`AgentRunRepository.save`. Atenea project persistence and synthetic
compatibility remain passing.

Atenea source is clean and synchronized at
`dab379b3d11cfacd2e1714d4f56dc1210948d5c5`, tree
`9068166413e9ab85ba4829e4929b1a0e43303c4c`. The focused persistence,
selection and client suites pass `28/28` locally and `28/28` from the
committed server checkout. No deployment, database write, real WorkSession,
AgentRun or remote dispatch occurred.

Production and preview actuator checks remain `UP`; no Beautips selector key
is deployed. AX42 retains boot identity, RAID `[UU]`, slot 1's three exact
administrative Beautips containers, empty slots 2–4 and administrative health
`UP`.

Task 3.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-3.2-persisted-beautips-identity`;
the SHA-256 of its `SHA256SUMS` is
`add7b084323e1af19cc3c85c23289aa15eff0cadf91060aca93a191f6b2c5d3f`.

Task 3.3 extends the existing exact project-payload acceptance to Beautips
without a new protocol or endpoint. Repository, branch, commit and manifest
are read only from the persisted AgentRun; its dispatch UUID remains the
idempotency boundary and the WorkSession external thread ID is forwarded for
continuation. Caller command, path, endpoint and environment are absent.

The existing project-neutral coordinator maps a Beautips terminal success to
the saved WorkSession thread, AgentRun external turn and exactly one CODEX
result turn. A second observation after terminal returns without redispatch
or duplicate turn. Existing Atenea project mapping and four-field synthetic
payload compatibility remain passing.

Atenea source is clean and synchronized at
`dc6d5ef2f037e6b88d7fa63107622d5859aceb5b`, tree
`92d8123f34b9a17d9afc96813eccfb197dfd8415`. The focused payload,
coordinator, persistence and selection set passes `34/34` locally and `34/34`
from the committed server checkout. No real dispatch, production database
write, deployment or routing activation occurred.

Production and preview remain `UP` with zero backend restarts and no deployed
Beautips selector key. AX42 retains three `[UU]` arrays, slot 1's three
administrative containers, empty slots 2–4 and Beautips health `UP`.

Task 3.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-3.3-idempotent-turn-mapping`;
the SHA-256 of its `SHA256SUMS` is
`e0d4a5e7a8de473027845dd181d126adc6c96b210001273475635203cb4c41c8`.

Task 3.4 keeps the coordinator state machine unchanged and adds exact
Beautips continuity cases. Cancellation uses only the persisted execution
identity and does not redispatch. Startup reconciliation polls the persisted
execution without replacement. A bounded partition fails the same run with
explicit operator review and no reassignment. Re-observing a terminal
Beautips run creates no duplicate dispatch or result turn.

Equivalent Atenea cases remain in the suite. The focused coordinator set
passes `8/8`; coordinator, client, persistence and selection pass `37/37`
locally and `37/37` from the committed Atenea server checkout at
`9e264e3820d6803225d57139150e1df990d9e09e`, tree
`6046d03ac3067aad54ba9127faccd4d099e51454`.

No real restart, dispatch, cancellation, production database write,
deployment or routing activation occurred. Production and preview remain
`UP` with zero backend restarts. AX42 retains three `[UU]` arrays, slot 1's
administrative Beautips runtime, empty slots 2–4 and Beautips health `UP`.

Task 3.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-3.4-continuity-semantics`;
the SHA-256 of its `SHA256SUMS` is
`946bf1d692bb7156beb014f991197928c41e0299780164377af691df090d4a9a`.

Task 3.5 closes control-plane allowlisting at Atenea commit
`9e264e3820d6803225d57139150e1df990d9e09e`, tree
`6046d03ac3067aad54ba9127faccd4d099e51454`. Exact selection, payload,
persistence, delivery, denial, Atenea project and synthetic compatibility
pass in two final focused runs of `37/37`, lasting `7.32 s` and `7.50 s`.

Two fresh full Atenea runs pass `411/411`, lasting `56.21 s` and `47.88 s`.
Each used an internal labelled network, PostgreSQL 16 container and isolated
workspace volume, applied all 49 migrations, and removed every fixture after
exact name, ID and label verification. Final task container, network, volume
and diagnostic workspace counts are zero.

The first full harness omitted `ATENEA_WORKSPACE_ROOT`; the application
correctly rejected integration repositories outside its configured `/repos`
root, producing 25 expected-boundary failures. A one-case diagnostic proved
the harness mismatch. Instrumentation was removed byte-for-byte, the accepted
harness mounted `/workspace/repos` independently with the canonical root, and
both complete passes then succeeded. No diagnostic response body or generated
credential was retained.

Atenea production and preview remain `UP` with zero backend restarts. The two
unrelated task4 containers retain exact identities. AX42 retains RAID `[UU]`,
slot 1's administrative Beautips runtime, empty slots 2–4 and Beautips health
`UP`. No production deployment, real WorkSession, dispatch, database write or
routing activation occurred.

Task 3.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-3.5-double-regression`;
the SHA-256 of its `SHA256SUMS` is
`fe03bba5fc28349dc87486a98e602130731d0fd3bb81b28e09f816c03b8c0550`.

Accepted sanitized entry evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/entry-gate`;
the SHA-256 of its `SHA256SUMS` is
`87fe021a4e9ba914d7ca2cb8e12910b2eb184cde3f4d5783ed05af2067a183e6`.

Task 4.1 creates the canonical managed Beautips identity without starting a
runtime. A fresh isolated Atenea control plane persists one remote WorkSession,
`6375c738-99da-4ef3-91f5-21e30d3b27d3`, for exact project `Beautips`,
worker `ax42-01`, workload `project-codex-v1`, repository
`https://github.com/jlnieto/beautips.git`, branch `main` and workspace branch
`atenea/session-6375c738-99da-4ef3-91f5-21e30d3b27d3`. Its fresh PostgreSQL
contains one project, one open WorkSession and zero AgentRuns or SessionTurns.

The AX42 service identity fetched the private canonical repository through an
ephemeral mode-0700 Git credential-cache boundary fed by the already
configured operator credential. No credential value was emitted or persisted;
the daemon, socket and directory are absent after provisioning. The canonical
bare mirror has exact HTTPS origin and remote-only fetch mapping. Mirror,
worktree and manifest resolve to commit
`e9e0b3c319c518363d4135f5378ebbddced96dfb`, tree
`533d32f97ae362997ad003170a826da674c31c1d` and manifest SHA-256
`365f1c66c51c9018c2c6f48deddbaa619b4588cae2dd463dcd916cde884e2e82`.
The worktree is clean.

Historical persisted allocations retain slots 2 and 3, so the new normal
admission correctly holds the only unclaimed managed slot, slot 4. Allocation
reserves three collision-free loopback ports but starts no runtime: session
container, network and listener counts are all zero. Project execution remains
disabled with zero registered workspaces. The administrative slot 1 Beautips
pilot, production, preview, prior Atenea acceptance resources, rootful Docker
state and canonical Atenea checkout are unchanged and healthy.

Task 4.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-4.1-canonical-mirror-allocation`;
the SHA-256 of its `SHA256SUMS` is
`261a48fea26345289f454c323e0a86cb20ee03bf27a599cfd244e3373b246f98`.

Task 4.2 closes the real worker composition exposed by the first canonical
session. `project-codex-v1` now resolves through independent root-owned Atenea
and Beautips routes. The existing Atenea route remains
`selectionEnabled=false`, `executionEnabled=false` with zero workspaces.
Beautips alone is enabled with the single immutable key
`remote:ax42-01:work-session:6375c738-99da-4ef3-91f5-21e30d3b27d3`.
Its registry record binds that UUID, the exact worker-owned worktree and
allocation SHA-256
`0e46cc38968509fbdd6585e3741f8c8e1eecb32f0161139400ec923780f49dbc`.

The lifecycle now registers only after validating file ownership/modes,
canonical Git common directory and HTTPS origin, branch, commit, manifest,
normal slot 2–4 allocation and exact session/workspace identity. Unregister
requires disabled execution plus the same one-key identity. The installed
worker, systemd unit and final lifecycle SHA-256 values are respectively
`fd5784155fcfe477599c72751fc0cc7064322cea25728de7573ac3c47ef46de4`,
`aa17d70b2c482aaa329778c0629f00f4ab6db8a58233de9d7e41b2d17ed92536`
and
`7f5bc41255bdfb2feaf1823a50ce4a9a7aca6951fa7ed49ce7d88d7e17481d98`.
The existing Tailscale-only worker listener, token boundary, capacity and 28
durable terminal records were retained.

The final complete AX42 aggregate passes all manifest, mediator, sandbox,
secret, lifecycle and four selected worker-route cases in `18.230 s`.
Lifecycle ownership hardening separately passes in `1.796 s`. Six
authenticated negative requests reject the administrative pilot, a complete
foreign Beautips workspace, an ambiguous session/workspace pair, disabled
Atenea, a foreign project and an arbitrary command field with exact HTTP
400/403 closed errors in `59 ms`. Worker state remains byte-identical before
and after all denials. No accepted execution or prompt was submitted.

The canonical worktree remains clean at its accepted commit and has zero
runtime containers and networks. The administrative Beautips pilot,
production, preview, isolated control plane, prior Atenea acceptance
resources and canonical Atenea source remain unchanged and healthy.

Task 4.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-4.2-exact-session-enable-denials`;
the SHA-256 of its `SHA256SUMS` is
`f46712a552456436595f7ac348395547e978df6c3474d1a42474a60baa1a572a`.

Task 4.3 submits the first and only accepted Beautips operator turn at this
gate. The deterministic prompt required exactly one new file,
`docs/ax42-onboarding-acceptance.md`, containing the single line
`AX42 Beautips onboarding acceptance.`, no other change, commit or push.
AgentRun 1 reached `SUCCEEDED` in `36.743 s` with dispatch
`7f08985d-2dd9-4c8a-addb-b12176d5e743`, execution/turn
`a8f7ffaf-2a44-4cbb-a344-a8b4a183a968`, thread
`019faf5f-0a96-7592-a936-583cb044dae8` and exact answer
`BEAUTIPS_TURN_1_OK`.

The target is 37 bytes, one line and has SHA-256
`83368013af053c2ede88faf4728abf9a30ddf352fbc47a09ad91707f63166fd3`.
The full pre-turn content manifest is byte-identical after the turn when that
single target is excluded. Worktree HEAD, tree and index are unchanged, and
Git status contains only the expected untracked file. Workspace, allocation,
admission and registry fingerprints remain exact. Atenea persists one
AgentRun, one operator turn and one Codex result turn with the complete
canonical Beautips identity.

No session runtime container or network was created. The isolated control
project/source and canonical Atenea checkouts remain clean. Administrative
Beautips, production, preview and prior foreign acceptance controls remain
unchanged and healthy. No second turn, duplicate replay, commit or push
occurred.

Task 4.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-4.3-deterministic-first-turn`;
the SHA-256 of its `SHA256SUMS` is
`d163c82caf3daac1668d672b731e800bdd625998c165ef2e3b0bd3e38d4142bf`.

Task 4.4 continues the same Beautips WorkSession with a deterministic second
turn. AgentRun 2 appended only
`Turn 2: same Codex thread continued idempotently.` and reached `SUCCEEDED` in
`28.528 s`. Dispatch `7bcc0c89-d94d-4fdf-bc5c-e5d3a71b5c12` maps to
execution/turn `f27cc38e-0aa0-4b30-9dce-3b540fee139b`; both its thread input
and result equal the first turn thread
`019faf5f-0a96-7592-a936-583cb044dae8`. Its exact answer is
`BEAUTIPS_TURN_2_OK`.

The target now contains exactly the two accepted lines, 87 bytes, with
SHA-256
`28fc81714c03aa8d640c01cb1cdc6f47a1a129aff143f0a3cc9aa691a3438eaf`.
HEAD, tree and index remain unchanged and Git status still contains only this
untracked file.

Replaying the complete immutable second request with the same dispatch ID
returned HTTP 200 in `11 ms`, the same execution ID, terminal status and
revision 5. Worker state remained byte-identical at 30 records and the target
SHA-256 did not change. Atenea retained exactly two AgentRuns and four turns
before and after replay, with one result turn per run; no duplicate terminal
delivery was created.

Workspace, allocation and admission fingerprints remain unchanged and no
session runtime resource exists. Administrative Beautips, production,
preview, canonical Atenea and the isolated control-plane checkout remain
unchanged and healthy.

Task 4.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-4.4-thread-continuity-idempotence`;
the SHA-256 of its `SHA256SUMS` is
`f02bde3306fea98eacf0109bc67fb64f275ee8923fbee09e688fbbf1fdc39d8b`.

The exact resume point is task 4.5 of `onboard-beautips-on-ax42`.

Task 4.5 is complete and change progress is `25/45`. Two independent, finite
SSH observer processes read the same isolated non-production Atenea state in
sequence. Observer A exited completely before observer B started; the detached
interval contained zero matching observer processes and zero established
connections to the isolated control plane. The processes had distinct process
IDs while their normalized WorkSession, AgentRun, turn, Codex thread and
workspace observation SHA-256 values were identical at
`5088c79bc22085fde50582ef0d8c887f8d0f52c095554deb7886659230d0a58e`.

The WorkSession remained `OPEN` with the same remote execution target,
`ax42-01` worker, external thread and exact workspace identity. The isolated
control plane retained exactly one WorkSession, two successful AgentRuns and
four turns. No prompt or worker execution was submitted during observer
reconnection.

AX42 worker state and its 30 retained execution records remained
byte-identical. Worktree HEAD, tree, index, expected two-line untracked target,
workspace registry, allocation and admission fingerprints remained unchanged.
No session runtime resource was created. Administrative Beautips, production,
preview and the isolated control plane remained healthy. Synthetic
authentication values were transient and are absent from evidence.

Task 4.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-4.5-observer-reconnect`;
the SHA-256 of its `SHA256SUMS` is
`17dd85832424cc065eb537ae66f3d4f3355bf8579887dd88361d8d5610a89b22`.

The exact resume point is task 5.1 of `onboard-beautips-on-ax42`.

Task 5.1 is complete and change progress is `26/45`. The canonical Beautips
commit `e9e0b3c319c518363d4135f5378ebbddced96dfb` passed the fixed Node 22
CSS build and the complete Maven 3.9.9/Java 21 suite on assigned rootless
`slot4`. Surefire retained 30 tests with zero failures, errors or skips. Both
acceptance commands used the exact reviewed digest-pinned plans with
`--network none` after public dependencies were populated only in this
WorkSession's isolated cache.

The assigned slot receives traverse-only ACLs on shared ancestors and access
only to the exact WorkSession worktree and cache. Ownership, group, allocation,
workspace record and Git remain unchanged. Pre/post fingerprints prove the
same HEAD, tree, index, expected two-line untracked target, allocation,
workspace, worker state and 30 durable worker executions. Slot4 retained zero
task containers and only its three default networks.

Preflight exposed three closed plan defects before acceptance. Git now receives
an invocation-local `safe.directory` for only the already validated worktree;
npm explicitly uses `/workspace/.npm`; and Maven uses the canonical
`-Dfrontend.build.skip=true` because Node has already built CSS. Focused
mediator and installer tests pass. Installed mediator and lifecycle SHA-256
values are respectively
`6cbb65d4b667c08220e40b4b03df5d0143c28bf444fed1bf1305c22ba61917da`
and
`c85d05a2220b9d42a8696884669d83996159e7dae15876bd66e531b7b93d26be`.

The failed attempts stopped at their documented boundary; all partial ACL
projections were reverted before retry. One diagnostic container was removed
by its recorded immutable ID. No failed or passing attempt changed production,
preview, administrative Beautips, other slots, foreign WorkSessions, routing
or canonical Git. Production, preview, administrative Beautips and the
isolated control plane remained healthy.

Task 5.1 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.1-canonical-build-tests`;
the SHA-256 of its `SHA256SUMS` is
`e3b5c63bd6b7de888504a0807d806201d16aa25de01cb5aaa1c37728b9791ae8`.
Five sealed blocked-attempt directories remain beside it with their own
integrity manifests and are indexed by the accepted attempt ledger.

The exact resume point is task 5.2 of `onboard-beautips-on-ax42`.

Task 5.2 is complete and change progress is `27/45`. The exact Beautips
WorkSession now owns three running rootless slot4 containers, one internal
network, four labelled PostgreSQL/Redis/assets/imports volumes and one local
Compose application image. PostgreSQL and Redis are healthy and the app
actuator is `UP`.

PostgreSQL applied 41 source migrations. All tenant, user, customer, loyalty,
import, credential, channel, outbox and event tables remain empty. Thirteen
rows exist only in three migration-defined static catalog tables; these are
versioned schema bootstrap records, not fixtures or production-derived data.
Redis `DBSIZE` is zero.

Docker retained the requested `PortBindings` but RootlessKit created no host
listeners for the `internal=true` network. A finite 300-second wait closed.
RootlessKit records 1, 2 and 3 now forward only allocation-derived
`127.0.0.1` ports 21379, 25592 and 23826 to the exact app, PostgreSQL and Redis
container IP/ports. The runtime network remains internal with no egress; the
three complete records are retained for reconciliation and exact cleanup.

The first secret preparation stopped before values or Docker resources because
setgid inheritance produced directory mode `2700`. The exact empty directory
was removed. Creation now normalizes mode `0700` after ownership and the
regression test covers a setgid parent. Four synthetic named values plus
value-free metadata are retained as `0600`; no value appears in evidence.

Current installed secret boundary, source allowlist, mediator and lifecycle
SHA-256 values are respectively
`acbbb58f5ead82f47288fa499009c46797655bd277071d57e21b5c6ccfd504f6`,
`696a00eae3d35f9e54d3eebc55441252705c982dc19adb0aa9aa7aecd59a61b0`,
`a4ca6dc559ccf92868fe85d6419a674cc069d5da186365f4d269870748fe331c`
and
`ef05e83d9f38ce6858417d3b088ad47f0b8c4e08802654c2ee0a49ebf3fcba05`.

Canonical Git, allocation and worker state remain unchanged. Four pre-existing
foreign anonymous slot4 volumes and all default networks are byte-identical.
Administrative Beautips, production, preview and the isolated control plane
remain healthy; rootful Docker remains inactive.

Task 5.2 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.2-rootless-empty-runtime`;
the SHA-256 of its `SHA256SUMS` is
`9ff3a320071c79043a5e5761db23428f51c5cf7210507c1f06609534f10886b8`.
The sealed pre-resource blocked attempt remains beside it with manifest
SHA-256
`3355d7533d84fb8caf3c2abec414dca6244d459fd74b429a02f78f88ee451920`.

The exact resume point is task 5.3 of `onboard-beautips-on-ax42`.

Task 5.3 is complete and change progress is `28/45`. Versioned fixture bundle
`beautips-acceptance-v1` is pinned to programme commit
`a30117789d1bddfde804dbaa00a71f2975178d60`; its manifest and SQL SHA-256
values are respectively
`3be6c7609a33272aec519058061dfbf98df66e773f1824792c9df609bae5e2fe`
and
`aa49558debab93c5f044663fcd01f76e8a5028cb635d4e9572c7eea2b71cb3db`.
It contains only invented `.invalid` identities, one SVG and one CSV; no
backup, legacy import, production row or manual asset participates.

The canonical APIs created one invented tenant and owner from the exact named
synthetic boundary. Idempotent SQL created exactly one customer, consent,
LOYALTY module, stamp-card program, account, transaction, program event,
service catalog and completed import job. The exact SVG and CSV exist only in
the session-owned asset/import volumes. Two full repeated loads produced
byte-identical sanitized database, file and Redis snapshots. Every declared
synthetic table reports one row; tenant WhatsApp credentials, outbox rows and
Redis keys report zero.

Acceptance exposed an eight-versus-four digit synthetic seal mismatch before
tenant persistence. Programme commit
`858e946c4e5c0ac704e2776179e2667dd73d6f66` corrects the generator and focused
boundary/lifecycle tests pass. The installed boundary and lifecycle hashes
are now respectively
`6f79b5f4cfae1924a479d541e4189c3db9cc8abcb0357a38603bdc7d7d4d21b1`
and
`c39b0a578a87161c79025de2c5b72930e7a2c834bdecbed074c0ecdbe8ad782b`.
Only this WorkSession's synthetic seal was shortened; the other named secrets
and exact enabled workspace config remained unchanged. Remediation evidence
is sealed with `SHA256SUMS` SHA-256
`ed5cb97c057a190ead56405609f9d829d980b12d4533f0b9c92afb0e4eaf3cb4`.

The running rootless containers ceased executing `docker exec` during
preflight. Fully session-labelled client containers therefore used only the
exact `internal=true` network, recorded immutable IDs and removed themselves.
The introduced PostgreSQL client image tag, private slot4 I/O directory and
all helper containers are absent after acceptance. Thirteen sealed blocked
attempt directories retain the output-transport, contract, schema and
evidence-query boundaries without secret values.

The three managed containers remain running, app/PostgreSQL/Redis are healthy,
and Redis is empty. Canonical Git, worktree change, allocation and routing
remain unchanged. Administrative Beautips, production, preview and the
isolated control plane remain healthy with their exact foreign identities.

Task 5.3 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.3-versioned-synthetic-fixtures`;
the SHA-256 of its `SHA256SUMS` is
`2d14e489e7315645a815b89297504c1dcbc883d8e3437c86aae5a7518b03005f`.

The exact resume point is task 5.4 of `onboard-beautips-on-ax42`.

Task 5.4 is complete and change progress is `29/45`. Exact container and
volume inspection proves the managed app, PostgreSQL and Redis mount only the
four complete-ownership WorkSession volumes. The separate administrative
slot1 workspace, its four volumes, three containers, network, listener and
manual boundary are absent from every managed mount and remain unchanged.
Neither a rootless/rootful Docker socket nor another host runtime path is
mounted.

The exact runtime network is still `internal=true` with only its three managed
endpoints. A finite fully labelled probe observed no default route, no
`host.docker.internal` resolution, no daemon socket paths and denied loopback
ports 18083, 2375 and 2376. Its immutable container ID was recorded and the
helper removed itself. It used the existing PostgreSQL 16 image, so image
inventory remained byte-identical.

A separate fully labelled database probe reports zero legacy import batches,
legacy mappings, non-synthetic import jobs, tenant WhatsApp channels,
credentials, outbox/messages, onboarding sessions and webhook events. The
pinned managed Compose SHA remains exact, its WhatsApp inputs are empty, the
birthday scheduler is false and no manual path, `.env` or daemon socket is
declared.

All four rootless slot container/network/volume/image inventories and AX42
boot, rootful Docker, Git, allocation, worktree, listeners and administrative
health are byte-identical before and after. Atenea production, preview,
isolated control plane, Git, listeners and complete rootful container
inventory are also byte-identical. Every checked health is `UP`.

Task 5.4 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.4-isolation-connectivity`;
the SHA-256 of its `SHA256SUMS` is
`9faeee64028161c7999ed6c1deaf9f10b913c7d7ebc71fc323ef009725a13a9c`.
Two sealed fail-closed attempts remain beside it with their own integrity
manifests; neither changed persistent or foreign resources.

The exact resume point is task 5.5 of `onboard-beautips-on-ax42`.

Task 5.5 is complete and change progress is `30/45`. The installed active
`session-preview/v1` coordinator created exactly one persisted synthetic
preview for control-plane WorkSession database ID 2 and runtime session
`6375c738-99da-4ef3-91f5-21e30d3b27d3`. Allocation fingerprint remains
`0e46cc38968509fbdd6585e3741f8c8e1eecb32f0161139400ec923780f49dbc`.

The READY preview has one listener on AX42 Tailscale IPv4 `100.81.98.93`
inside ingress range `19000–19031` and forwards only to allocation-owned
loopback port 21379. The private `/admin/login` route returns HTTP 200 both
from AX42 and the operator laptop over the tailnet. There is no wildcard or
localhost ingress listener.

The canonical manifest, persisted record and response all retain
`localhostCompatible=false`. The response has no tunnel metadata and does not
expose the runtime port. A localhost connection to the ingress port fails, and
the response page plus headers contain no `localhost` or `127.0.0.1`
reference. No public share, firewall change, production route or unrelated
preview was created.

Canonical Git and the intended untracked two-line WorkSession file remain
unchanged. Production, preview, isolated control plane, managed runtime and
administrative Beautips remain `UP`; Atenea boot, Git and complete container
inventory are byte-identical before and after.

Task 5.5 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.5-tailnet-preview`;
the SHA-256 of its `SHA256SUMS` is
`00949ceff54bc1fcf2efe5472e6973325332dbc9b0ce4f19c64d945840e39f66`.

The exact resume point is task 5.6 of `onboard-beautips-on-ax42`.

Task 5.6 is complete and change progress is `31/45`. The reviewed
`functional-smoke` and `customer-smoke` mediator plans remain execution
disabled by default and were invoked with their exact bounded argv and
600-second timeouts. The functional smoke passed its health, setup, admin,
salon, catalog, public customer, registration, QR accumulation/redemption and
business-query checks. Its one invented tenant was recorded by immutable
database id plus slug and exact-deleted after the customer smoke; all
tenant-scoped residual counts are zero and only `aurora-acceptance` remains.

Finite preview leases expired during authorised pauses. Each terminal
synthetic record was matched to the exact persisted ownership and deleted by
UUID before one replacement was activated. At most one preview was READY at
any time; runtime state, production routing and foreign preview resources did
not change.

The customer smoke found a real versioned fixture defect before acceptance:
raw value `SYNTHETIC_ACCEPTANCE` is not a valid
`TenantModuleActivationSource` and caused the public synthetic salon to return
HTTP 500. Programme commit
`a30117789d1bddfde804dbaa00a71f2975178d60` uses valid source `ADMIN`, updates
the SQL/manifest hashes, and changes no application or production data. The
exact runtime projection was replaced only after matching both previous
hashes. Two repeated idempotent reloads are byte-identical, the public page
returns HTTP 200 and the complete customer smoke then passes both invented
salons.

Playwright 1.60.0 ran from the operator laptop through the private tailnet
listener. Named synthetic login values travelled only through stdin and were
not retained. DOM assertions passed for the login, filtered single salon,
primary management action and exact customer `1`, active-program `1 / 1` and
active-access `1` KPIs. The credential identifier was sanitized before
capture. Inspected desktop `1440x900` and mobile `390x844` screenshots show
clear state/action hierarchy with no clipping, overlap or horizontal
overflow.

All helper containers were fully labelled and recorded by immutable ID. The
functional tenant, helper containers, newly pulled helper image, task-private
I/O directories and Playwright browser processes are absent. The pre-existing
operator Chrome is foreign and untouched. The three managed containers, four
volumes, internal network, canonical worktree and finite READY preview remain;
administrative Beautips and Atenea production, preview and isolated control
all remain `UP`.

Task 5.6 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.6-functional-playwright`;
the SHA-256 of its `SHA256SUMS` is
`4e6c5ded2a688a8d8d12d5846e354500b0c8dfd2fce8f459620fa31b8e95aefa`.

The exact resume point is task 5.7 of `onboard-beautips-on-ax42`.

Task 5.7 is complete and change progress is `32/45`. The sanitized desktop
PNG, mobile PNG and Playwright DOM JSON report are registered through the
authenticated `worksession-attachment/v1` boundary under exact WorkSession
UUID `6375c738-99da-4ef3-91f5-21e30d3b27d3`. Their deterministic immutable
attachment UUIDs are respectively
`8fdb5346-57c7-5aff-baa9-5c1b676ad4ad`,
`c420ebd1-b76b-5dcd-9a3e-58accf4be087` and
`a501aac8-2c2d-54e3-8b6e-f455eb5d785f`.

All three records declare synthetic identity and `EVIDENCE` retention with
opaque storage identities. Initial registrations returned HTTP 201. Repeating
the same identities, metadata and bytes returned HTTP 200 with the original
metadata and no duplicate retained files.

The finite preview was already `EXPIRED`. Its complete persisted ownership,
revision 4, exact UUID and absent listener were checked before exact terminal
synthetic deletion. Its record and the entire preview ingress range are now
absent while the three-container managed runtime remains running.

Two complete retrieval passes after teardown returned HTTP 200 for all three
metadata and all three content identities. Every byte count and SHA-256
matches the sanitized source and both passes are identical. No temporary
retrieval copy, token value, credential, cookie, authorization header,
environment dump or production data remains in evidence.

The first continuation observed the historical internal name `sessions/`
after registration and stopped before preview mutation. Canonical continuation
used `work-sessions/`, retained the failed non-mutating check and reused the
already idempotently accepted records.

Administrative Beautips, the managed runtime and Atenea production, preview
and isolated control remain `UP`. Canonical WorkSession Git remains unchanged.

Task 5.7 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-5.7-artifact-retention`;
the SHA-256 of its `SHA256SUMS` is
`aa7e4667e09ca367c3826563c7d8e8a254a1862ff6ea72b4096dc335fd1754fb`.

The exact resume point is task 6.1 of `onboard-beautips-on-ax42`.

Task 6.1 is complete and change progress is `33/45`. The exact WorkSession
branch `atenea/session-6375c738-99da-4ef3-91f5-21e30d3b27d3` contains one new
commit, `03f77b0389f5303153c47bc3f890b1e0e9e92eb8`, with tree
`ea2050c15dc7949515a432cce70f1b6f4362d7e0`. It adds only the two-line
`docs/ax42-onboarding-acceptance.md`; the AX42 and isolated-control worktrees
are clean.

The remote branch was absent at entry. Complete history moved through an
exact SHA-256-matched bundle, the isolated checkout advanced only by
`merge --ff-only`, and a normal push created the branch without force.
Atenea's authenticated `POST /api/sessions/2/publish` then created
`jlnieto/beautips#1`. GitHub reports one `OPEN` draft based on exact `main`
`e9e0b3c319c518363d4135f5378ebbddced96dfb`, headed by the exact WorkSession
commit, mergeable, with one commit, one file and two insertions. Atenea
persisted the same URL, branch and final commit.

The first endpoint attempt failed closed with HTTP 409 before GitHub mutation
because its disposable control lacked Git authentication for the remote-head
read. The accepted retry returned HTTP 200 through a temporary isolated
control and finite-lived credential pipes. The helper, FIFOs, control
container, temporary image, bundle and transfer ref were all removed by exact
identity. No credential value, authorization header, cookie, environment dump
or token is retained.

The WorkSession remains `OPEN` with zero running AgentRuns. Its exact managed
runtime, Git state and registered evidence remain present. Atenea production
and preview and the foreign administrative Beautips runtime remain `UP`.

Task 6.1 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-6.1-draft-delivery`;
the SHA-256 of its `SHA256SUMS` is
`9538eeed1f53788fc35b7da7bcad10fa2db948f0bc363a4742bd56b36ad7f82f`.

The exact resume point is task 6.2 of `onboard-beautips-on-ax42`.

Task 6.2 is complete and change progress is `34/45`. GitHub CI `Test and
build` passed for exact draft `jlnieto/beautips#1`. The one-file diff, base,
head and commit were reviewed before marking it ready and performing a normal
merge without branch deletion. Merge commit
`f836940d71ed761a4d12e560c3790eeba9778f85` has exactly pre-merge `main`
`e9e0b3c319c518363d4135f5378ebbddced96dfb` and immutable WorkSession head
`03f77b0389f5303153c47bc3f890b1e0e9e92eb8` as parents. Remote `main` points
to the merge and the WorkSession branch remains at its original head.

The real Atenea pull-request synchronization endpoint ran twice with finite
timeouts. Both calls returned HTTP 200 and retained byte-identical material
delivery fields: WorkSession `OPEN`, pull-request status `MERGED`, exact URL,
branch, final commit and original publication timestamp. Non-terminal
AgentRuns and push-notification rows remain zero.

Exact isolated-database project and WorkSession IDs `6102` acted as a
cross-session sentinel. Its selected-row MD5
`58e081bb652ef8549e821b086d94eb3b` remained unchanged across both real sync
calls. Cleanup required that MD5 plus the exact IDs, project, workspace
identity and final SHA, then removed only those two rows. Both fixture IDs are
absent.

Focused `WorkSessionGitHubServiceTest` passed `9/9`. The sync credential was
consumed only through a finite-lived FIFO and cached only by the ephemeral
process for the repeat call. The exact FIFO, temporary control and image are
absent. No force update, duplicate delivery response, cross-session mutation,
credential value, authorization header, cookie or environment dump is
retained.

Task 6.2 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-6.2-merge-sync`;
the SHA-256 of its `SHA256SUMS` is
`5d988f75682a2e8c830b1d7b1f31b5f5805bb1e9170d864382a6e34bf27e644d`.

The exact resume point is task 6.3 of `onboard-beautips-on-ax42`.

Task 6.3 is complete and change progress is `35/45`. Atenea's authenticated
close endpoint reconciled database WorkSession `2` and external WorkSession
`6375c738-99da-4ef3-91f5-21e30d3b27d3` to `CLOSED/CLOSED` at
`2026-07-29T22:38:08.356739Z`. Pull-request status remains `MERGED`; exact
workspace identity, URL, publication timestamp and final commit are unchanged.
There is no close block and retryable state is false.

The canonical close revalidated the GitHub repository, pull-request number,
base, head and head SHA. It fetched origin, checked out `main`, fast-forwarded
only to exact merge `f836940d71ed761a4d12e560c3790eeba9778f85`, then deleted
only the merged session branch from the disposable control clone and GitHub.
Both are absent. AX42 retains its clean local WorkSession branch at
`03f77b0389f5303153c47bc3f890b1e0e9e92eb8`; merged history and the pull
request retain the same commit.

The first close attempt stopped at retryable `CLOSING/fetch_failed` before
branch mutation because the ephemeral helper executable was placed on a
`noexec` tmpfs. Moving only that executable to temporary container `/tmp`
preserved the in-memory token and allowed the same canonical close to return
HTTP 200. The repository helper, temporary control and image are absent, and
no credential value or environment dump is retained.

Focused close reconciliation tests passed `38/38`. The three-container managed
runtime, network, four volumes and three log files remain present. The exact
six registered attachment files remain `158452` bytes. Tasks 5.6, 5.7, 6.1
and 6.2 checksum hashes are unchanged. Atenea production, preview and the
foreign administrative Beautips runtime remain `UP`.

Task 6.3 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-6.3-canonical-close`;
the SHA-256 of its `SHA256SUMS` is
`0179ea4a72eb629225289db4e93211caf4213256cd3e9b450f1367532f32fda2`.

The exact resume point is task 6.4 of `onboard-beautips-on-ax42`.

Task 6.4 is complete and change progress is `36/45`. Only
`atenea-agent-run-worker-v1.service` restarted. Its PID changed from `726675`
to `916853` and the service returned `active/running` on the same tailnet-only
listener at `2026-07-29T22:44:53Z`. No host or project runtime restarted.

The durable execution file remained byte-identical at SHA-256
`f65e488816560e022ac8e7d4a68adf55483cf772e387e6f20b990bf31c53734a`.
Its sanitized protocol, worker, global status histogram and exact Beautips
ownership projection also remained byte-identical at
`a4628fb6f07b76fcebb129e1cc3ff6f46366ce1a09485b6ce576718f317828ac`.

The restarted mediator returns the same two `SUCCEEDED`, revision-5 Beautips
executions under exact WorkSession ownership. Immutable dispatch, execution
and turn IDs and shared thread `019faf5f-0a96-7592-a936-583cb044dae8` are
unchanged. Its journal has zero new execution POSTs and the WorkSession has
zero runner/Codex processes. Atenea still has two terminal AgentRuns, four
turns and zero non-terminal runs, proving no prompt or dispatch reran.

The first readiness request used noncanonical `/health` and returned 404
without mutation. Authenticated `/v1/health` then reported worker `ax42-01`
healthy with zero normal/heavy capacity in use and zero queued work. Git, the
three-container runtime, network, four volumes and six attachments remain
unchanged. Production, preview, isolated control and administrative Beautips
remain `UP`.

Task 6.4 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-6.4-worker-restart-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`18574badb39b2faf4045aa1a2cc36f0f43d01b5a2bd56c5ed29ece85a4fe9a19`.

The exact resume point is task 6.5 of `onboard-beautips-on-ax42`.

Task 6.5 is complete and change progress is `37/45`; phase 6 delivery, close
and continuity is complete. The installed Beautips contract verifies with
selection and execution enabled and one exact persisted workspace. Its
configuration SHA-256 is
`f3fb28e3f4b81ae6b584e8f21bfa3a1742e77772d1a2701fdf56b14b1e12592a`.
The allocation-owned managed web health returns `UP` with the same three
containers.

The worker loads only the exact Beautips config/runner and the generic Atenea
config/runner. Atenea remains `false/false` with no workspace; the root-owned
static allowlist has only key `beautips`. The isolated control has only its
exact Beautips project gate enabled and the generic project gate disabled.
Unknown projects have no installed config or runner authority.

Focused Atenea routing tests pass `11/11`, covering exact selection, disabled
selection, partial/foreign identity, missing capability and unknown-project
denials. The worker's exact Beautips route test passes `1/1` and accepts only
the exact registered workspace. No real session, run, dispatch or prompt is
created: durable worker SHA-256 is unchanged, Atenea remains at two terminal
AgentRuns, four turns and zero non-terminal runs.

A first HTTP probe targeted allocated Redis port `23826` and received an empty
reply. The persisted allocation identified correct managed web port `21379`,
where `/actuator/health` returns `UP`; the failed probe mutated nothing.
Production, preview, isolated control and administrative Beautips remain
healthy.

Task 6.5 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-6.5-availability-denials`;
the SHA-256 of its `SHA256SUMS` is
`912123af504fb6f672cb191bdcdfdc02c67279d9ee1dfbb9423499f4543e6a26`.

The exact resume point is task 7.1 of `onboard-beautips-on-ax42`.

Task 7.1 is complete and change progress is `38/45`. New Beautips selection
and execution are disabled in the AX42 installed config while its exact
persisted workspace remains registered for reconciliation. The disposable
Atenea control was replaced from its own committed image with only the
Beautips project gate overridden to false; its database, port and health
remain unchanged.

Accepted RootlessKit records `1`, `2` and `3` first matched their complete
parent/child tuples and were then deleted by immutable ID. The exact mediated
`runtime-cleanup` removed only containers `5e59b7d8e112`, `adaa784a6bc2`,
`4096ca2c7a3c`, network `f5b9c323b395`, four session volumes and local image
`aaefc03e7b80`. The exact runtime root contained only
`fixtures`, `secrets` and `tomcat`; realpath, non-symlink and top-level-name
checks passed before removing that file projection.

Final exact-session counts are zero containers, networks, volumes, images,
RootlessKit records, allocated listeners and runtime root. Preview records
remain zero. Mirror, allocation, clean worktree at
`03f77b0389f5303153c47bc3f890b1e0e9e92eb8`, six attachments and programme
evidence remain retained. WorkSession state is `CLOSED/MERGED` with zero
non-terminal AgentRuns.

Administrative Beautips retains its original three containers and remains
`UP`. Atenea production, preview and disabled isolated control remain `UP`;
no production, foreign WorkSession, unrelated slot or routing resource
changed.

Task 7.1 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-7.1-disable-exact-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`27225617d206dc430f9ccc7eb349f15333afb2ae3475980f4b39aab96ce8199d`.

The exact resume point is task 7.2 of `onboard-beautips-on-ax42`.

Task 7.2 is complete and change progress is `39/45`. Repeating the exact
worker disable and allocation-derived mediated cleanup from the 7.1 empty
boundary returned exit 0 and deleted nothing: managed container, network,
volume and image counts remained zero.

Four stopped slot 4 internal-network fixtures represented unlabelled, partial,
foreign full ownership and ambiguous exact labels with a non-allocation name.
Their normalized immutable ID, name, labels and internal-state projection had
SHA-256
`42c7ecbb4bd3253556242ca3b733cbc2fe8cfbdc060702ef721183b0406b9e34`
both before and after cleanup. Every rejected resource therefore remained
intact. Only after equality passed were the four fixtures deleted by their
recorded immutable IDs; fixture count is now zero.

Selection/execution remains `false/false` with one persisted workspace.
Worktree, mirror, allocation, six attachments and evidence remain retained.
Administrative Beautips, production, preview and isolated control remain
`UP`.

Task 7.2 passing evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-7.2-idempotent-rejection`;
the SHA-256 of its `SHA256SUMS` is
`2e6f5a561ff71c75db9c4b8cd3f4a53dd4303276cb461e8932d84b1024aea467`.

The exact resume point is task 7.3 of `onboard-beautips-on-ax42`.

Task 7.3 is complete and change progress is `40/45`. Versioned admission
released exact `slot4`; normal usage is `0/4`, heavy usage `0/2` and this
session has no heavy permit. The original allocation remains retained and its
archived evidence copy is byte-exact at SHA-256
`0e46cc38968509fbdd6585e3741f8c8e1eecb32f0161139400ec923780f49dbc`.
After release/archive verification, the exact disabled workspace registration
was removed; selection/execution remains false and workspace count is zero.
Mirror, worktree, Git, merged delivery, attachments and evidence remain.

Task 7.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-7.3-release-allocation-archive`;
its `SHA256SUMS` hash is
`6d351ceea4a05eaad092fec129e1f31694fe5deb860ff1022be186171cffb3db`.

The exact resume point is task 7.4 of `onboard-beautips-on-ax42`.

Task 7.4 is complete and change progress is `41/45`. Read-only comparison
retained the three exact administrative slot 1 container IDs and proved all
nine accepted Atenea production/preview rootful Docker identities byte-exact.
Slots 2–4 contain no containers; all four rootless Docker daemons and
restricted proxies are active. AX42 RAID remains `[UU]`, storage is healthy,
SSH, Tailscale and platform services are active, and administrative Beautips,
production, preview and isolated control are `UP`. No lifecycle or foreign
resource mutation was performed.

Task 7.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-7.4-nonimpact-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`4c1f3d71c2030e5f5d58c911fdfd6e4d2ca9427aa10073c81ab78165fb003e22`.

The exact resume point is task 7.5 of `onboard-beautips-on-ax42`.

Task 7.5 is complete and change progress is `42/45`. Two independent
regression cycles each pass the Beautips worker aggregate, manifest ownership
and exact-cleanup `3/3`, Beautips focused `29/29`, Beautips full `30/30`,
Atenea focused `37/37` and Atenea full `411/411`. Each full Atenea cycle
applied all 49 migrations from a new empty PostgreSQL 16 schema on a separate
internal network and isolated workspace.

The initial harness warmup proved `-DskipTests` did not prefetch the Surefire
JUnit provider; the internal network rejected its unplanned lookup before
product tests. Exact cleanup returned its resources to zero. The corrected
bounded warmup ran one unit test before both accepted internal-network cycles.
Final test containers, networks and volumes are zero. Generated Python cache
files were removed by exact path. Programme, Beautips and Atenea Git are clean;
administrative Beautips, production, preview and isolated control remain
`UP`, and RAID remains `[UU]`.

Task 7.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-7.5-double-regressions`;
the SHA-256 of its `SHA256SUMS` is
`320dc72e85cc38a889423e18ed6186dc96afbf37f9bafa3f0eeed1294e4c9b7a`.

The exact resume point is task 8.1 of `onboard-beautips-on-ax42`.

Task 8.1 is complete and change progress is `43/45`. All 60 pre-existing
sealed evidence packages validate file by file, covering 579 files and
1,417,430 bytes. The rollup indexes the two accepted Playwright screenshots
and 36 command metadata files. Filename and value-shape audits found zero
retained auth files, environment dumps, cookies, credentials, tokens,
authorization values, GitHub-token shapes or JWT shapes.

Task 8.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-8.1-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`39b6a069bd459c2a7820edd4d7c47bce5385d672abd015ec11e28eb19526951f`.

The exact resume point is task 8.2 of `onboard-beautips-on-ax42`.

Task 8.2 is complete and change progress is `44/45`. The accepted close
window lasted 909 seconds. Normalized samples at minute `0`, `5`, `10` and
`15` are byte-identical at SHA-256
`26dd67580ef414aa28c66c39074d0572a79b6a467bf0565e1b55cb9ddddf1685`.
Selection/execution and workspace count remain false/false/zero; admission is
released; exact owned resources, listeners, non-terminal AgentRuns, active
leases, active remote routing, preview records and browser processes remain
zero.

Allocation, mirror, clean worktree, six attachments and evidence remain.
Administrative Beautips retains its exact three identities; RAID is `[UU]`;
production, preview, administrative Beautips and isolated control remain
`UP`. The isolated acceptance control retains 17 active refresh-token rows
for its one synthetic operator, all created before task 7.1 and stable across
the four samples. They are not WorkSession or production ownership; no hash
or value was read, retained or modified.

Three pre-window read-only diagnostics rejected a nonexistent mirror ref,
untrusted Git ownership and attachment traversal before an accepted sample.
The corrected harness restarted at minute zero and completed without drift or
mutation.

Task 8.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-8.2-disabled-clean-observation`;
the SHA-256 of its `SHA256SUMS` is
`76999878fcce8fc53ea5310f02e391d304daf74005a3fb70384410da88ee30c1`.

The exact resume point is task 8.3 of `onboard-beautips-on-ax42`.

Task 8.3 completes `onboard-beautips-on-ax42` at `45/45`. Pre-archive strict
validation passes, and the programme stops after canonical archive, final
all-spec validation and synchronized push. No subsequent project onboarding,
routing activation, runtime, deployment or production mutation is started.

Canonical OpenSpec archive creates
`openspec/changes/archive/2026-07-30-onboard-beautips-on-ax42` and promotes
the seven accepted requirements into authoritative capability
`openspec/specs/beautips-project-onboarding/spec.md`. Post-archive strict
validation passes all 11 authoritative specs. Final non-impact checks retain
disabled zero-workspace selection/execution, released slot 4 admission, clean
WorkSession Git, RAID `[UU]`, exact administrative Beautips identities and
`UP` health for administrative Beautips, production, preview and isolated
control.

Task 8.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/onboard-beautips-on-ax42/runs/task-8.3-strict-archive`;
the SHA-256 of its `SHA256SUMS` is
`6e5912431f7f5201119a1e7b0f3e00684a2c8f9ba88907586b728d4ac8c890a4`.

The programme is paused after Beautips onboarding. No next project has been
selected or started.

## Independent external backup progress

The `establish-independent-worker-backup` acceptance is complete through task
6.3. Backblaze B2 is provisioned in the independent operator account as a
private bucket with provider-side encryption, Object Lock disabled and
bucket-scoped read/write credentials restricted to the owned AX42 restic
prefix. Credential values and the restic password were installed out of band
as root-owned mode-0600 inputs and never entered Git, chat, command arguments,
logs or evidence.

The exact source policy accepts 3,234 files totalling 10,914,251 bytes. Its
normalized aggregate manifest SHA-256 is
`6d22bd9d8dc81594c3a6148471c07190bf1674355ce4f73adf42020de8b22f16`.
Snapshot `b0738177a5983e4f597f0be1ee8344a4b91876b6a641995d99b2e622ea9bbb28`
passed repository check. A second accepted backup was restored into a new
empty isolated projection: all 3,234 files, byte count and manifest matched
exactly, after which only that exact projection was removed.

A mediated scheduled boundary produced checked snapshot
`9e9c8c2768089e0e2cbf663cc61905bbd5d434f16e7c2fdd86ad51668f1fa25b`.
Retention removed only the superseded intermediate snapshot and leaves the
first and scheduled accepted recovery points. The daily backup and weekly
integrity timers are enabled and persisted. A concurrent integrity attempt
failed closed after its 30-second lock timeout, and the isolated retry passed.

Disable and full rollback were each repeated twice. They removed only the
installed programme components and did not alter credentials, local persisted
state, routing fingerprints, evidence or either retained remote snapshot. The
accepted version was then reinstalled and only its two backup timers were
re-enabled. A deliberately missing-input invocation returned fixed exit `65`
without changing state or routing.

Final non-impact checks retain boot ID
`5cc2a4e3-020d-4d19-8a55-6ecae77f22ce`, all three RAID1 arrays at `[UU]`,
active SSH, Tailscale and worker services, four rootless daemons, slot
container counts `3/0/0/0`, admission usage `0/4` normal plus `0/2` heavy,
13 running and zero unhealthy Atenea containers, and healthy production,
preview and administrative Beautips. Atenea and Beautips selection/execution
remain disabled with zero registered workspaces.

Sanitized acceptance evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/establish-independent-worker-backup/runs/task-6.1-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`90c2acc6882d8f498bd70742d9dcb3b7699edbe3628e6d1fba829938ecc18b4c`.

The external-backup prerequisite is lifted and all 32 tasks are complete.
`establish-independent-worker-backup` is archived at
`openspec/changes/archive/2026-07-30-establish-independent-worker-backup`;
post-archive strict validation passes all 11 authoritative specs. No active
OpenSpec change remained at that acceptance point. Beautips routing and
authoritative retained state were then disabled pending the separate
activation recorded below.

## Beautips production remote routing activation

`activate-beautips-remote-routing` promotes only Beautips from accepted
onboarding to normal remote operation. All `32/32` tasks are complete and the
change is archived as
`openspec/changes/archive/2026-07-30-activate-beautips-remote-routing`.
Atenea source
`4efd3f9b96924e9d2668a19ba1110eca18b49791` is deployed and synchronized.
The production backend has the global and exact Beautips gates enabled, the
generic project gate disabled, the private AX42 endpoint configured and
previews allowlisted only for `Beautips`.

WorkSession `4` is open and pinned to worker `ax42-01`, remote UUID
`2ac2a5fd-2981-49cf-8fac-8132e46a2d64`, workspace identity
`remote:ax42-01:work-session:2ac2a5fd-2981-49cf-8fac-8132e46a2d64` and branch
`atenea/session-2ac2a5fd-2981-49cf-8fac-8132e46a2d64`. AX42 retains the clean
accepted Beautips commit `e9e0b3c319c518363d4135f5378ebbddced96dfb` in
slot 4 with one normal admission, one allocation, three healthy runtime
containers, one network, four volumes and the exact three loopback listeners.

Runs `63`, `64` and `65` succeeded on Codex thread
`019fb299-8752-7f31-bfe5-6bc91f7d0551`. The final dispatch
`fdc7c547-fd07-42e2-abfe-863cfb30eb58` has one terminal worker execution and
two byte-identical terminal reads. The four earlier fail-closed attempts remain
auditable and were not rewritten.

The invented acceptance dataset contains one tenant, operator, customer,
consent, module, loyalty chain, catalogue and import; WhatsApp credentials,
outbox and Redis remain empty. Preview
`eeaa6195-322f-43ff-b84b-06fe9d55c430` is `READY` only on
`100.81.98.93:19000`; loopback ingress is rejected. Playwright verified the
real Beautips login at `1440x900` and `390x844`, with all critical controls
visible and zero horizontal overflow.

Disable was repeated without moving the open WorkSession or deleting retained
ownership. Both disabled configurations had SHA-256
`20957d326aadf1a00ca516972ad4010669b5335aa0c1f4378ed4df2d3be7aad7`;
workspace, allocation, admission, Git, runtime resources, preview, backup and
the foreign slot 1 stack remained unchanged. Two isolated reconciliation and
rejection cycles passed, including `16/16` worker tests per cycle. Exact
reconciliation restored the original enabled configuration SHA-256
`87ba464a62af351912407f7fe9fd225d7b9826b1d5c5c6fbe791326f1b5fd0ad`.

Two final Atenea regressions pass `413/413`. RAID remains `[UU]` on all three
arrays, rootful Docker remains inactive, external-backup timers are
enabled/active, production and preview are `UP`, all 13 Atenea containers are
running with zero unhealthy, and no unrelated remote WorkSession exists.

Sanitized acceptance evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-beautips-remote-routing/runs/task-7-closure`;
the SHA-256 of its `SHA256SUMS` is
`bd9a02bd00281e3ee400ae24365f2d12a9f1c32b6b3f58f94bd5c02b87906006`.

The programme resume point is the next separately approved real project
activation. No unrelated project has been enabled or started.

## Atenea production remote routing activation

`activate-atenea-remote-routing` is complete through task 3.3 at `12/19`.
The global and exact Atenea gates are enabled for one open WorkSession pinned
to worker `ax42-01`, remote UUID
`c750641d-3226-44c3-81dc-d9149aac0de1`, workspace identity
`remote:ax42-01:work-session:c750641d-3226-44c3-81dc-d9149aac0de1` and branch
`atenea/session-c750641d-3226-44c3-81dc-d9149aac0de1`.

The archived development session's released slot-2 allocation marker was
retired only after its exact SHA-256 matched sealed task-7.3 evidence and its
containers, networks, images and listeners were proven absent. The record was
preserved byte-for-byte under its retired filename; no runtime or foreign
resource was removed.

The first two operator turns remain as auditable pre-dispatch failures: neither
received a remote execution identity. They exposed that activation commands
restarted the worker from inside its own workspace-ensure request. Programme
commit `8631dcb5cb26dfd7b76698c5d5158caac505ad4a` replaces that sequence with
one atomic project activation write. The worker reads the configuration on
every request, so no self-restart is required. An idempotent activation repeat
kept the exact worker PID and zero restart count.

Run `74` then completed automatically with dispatch
`bf03e0d2-289c-44d9-911c-934614968240`, execution
`fd8042b4-4422-46dd-9a1f-43c11882efd0` and one persisted Codex response.
The bounded read-only answer reported the session branch, accepted commit
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b` and a clean worktree without
modifying a file. The control plane contains one row for the successful
dispatch and the worker retains one terminal revision-5 execution.

Sanitized task-3.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-3.3-first-terminal-turn`;
the SHA-256 of its `SHA256SUMS` is
`1c617cf8c5f538725448268cc272a97b7d0ed630f62223d74ce90f3b43e2f2d1`.

Task 3.4 is complete and change progress is `13/19`. Run `75` completed with
dispatch `e94aa212-da6b-4a26-a193-2c460eb8b4fd` and execution
`a1cafad8-0909-44b0-bd2a-7781f09118ca`. Runs `74` and `75` both use exact
persisted Codex thread `019fb47f-1934-75f1-889a-506ec94c71d8`, have distinct
turn identities, reached terminal revision 5 and retained one response each.
Each dispatch occurs once in the control plane; there is no duplicate
delivery.

Sanitized task-3.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-3.4-thread-continuation`;
the SHA-256 of its `SHA256SUMS` is
`b04248a347f18adae29b74f7411909f2e1707fc29673d2cc1f7003b8c2424168`.

Task 3.5 is complete and change progress is `14/19`. Production and preview
are `UP`; all 13 Atenea containers are running with zero unhealthy. All three
RAID arrays remain `[UU]` and the worker service is active with zero
non-terminal AgentRuns and zero active leases.

Slot container counts remain `3/0/0/3`. The Atenea session has zero owned
containers, networks, allocated listeners and residual execution processes,
while its worktree remains clean. Administrative Beautips in slot 1 retains
its three containers. Routed Beautips in slot 4 retains its three containers,
one session network and all three allocated listeners. The only remote
WorkSessions are the accepted Beautips and Atenea identities; the unrelated
remote-session count is zero.

Sanitized task-3.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-3.5-nonimpact`;
the SHA-256 of its `SHA256SUMS` is
`c1a031d8450a1d6b88eba91ce0bdca60e4bc4ec2bee2b912f2a689fea6df8698`.

Task 4.1 is complete and change progress is `15/19`. Only Atenea selection
and execution were disabled. WorkSession `6` remains `OPEN` with exact worker,
remote UUID, workspace identity and persisted Codex thread unchanged.
Workspace and allocation records are byte-identical. The Beautips
configuration remains byte-identical at SHA-256
`87ba464a62af351912407f7fe9fd225d7b9826b1d5c5c6fbe791326f1b5fd0ad`;
there are zero non-terminal Atenea AgentRuns.

Sanitized task-4.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-4.1-disable-retain`;
the SHA-256 of its `SHA256SUMS` is
`7d425a082e4c1bd77788abbfc849dbb950bc46889334c06add85360a0d5cb5d1`.

Task 4.2 is complete and change progress is `16/19`. Exact retained Atenea
selection/execution was re-enabled without replacing its workspace. Run `76`
completed with dispatch `5370587e-b583-4fb5-82d1-667eb436ed26`, execution
`14eccdcd-22b8-4270-98da-98c3bb859b26` and the same persisted Codex thread
`019fb47f-1934-75f1-889a-506ec94c71d8`. The dispatch occurs once, one response
is persisted and the read-only turn reports accepted commit
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b` without changing a file.

Sanitized task-4.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-4.2-reenable-final-turn`;
the SHA-256 of its `SHA256SUMS` is
`c5563f8d4f4e665a845ab994a95ed62ed29f3b138952de4f7827728d489265e4`.

Task 4.3 is complete and change progress is `17/19`. The rollup verifies six
task `SHA256SUMS` manifests, nine root evidence sidecars and 52 pre-rollup
files totalling 76,528 bytes. Filename and value-shape audits found zero
retained auth files, environment dumps, cookies, credentials, tokens,
authorization values, private keys or JWT-shaped values.

Sanitized task-4.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-4.3-evidence-rollup`;
the SHA-256 of its `SHA256SUMS` is
`a931b973b04dca14fce3ab1cf59e9941f76e339ce98149ca70b2ef091519b353`.

Task 4.4 is complete and change progress is `18/19`. Pre-archive strict
validation passed. Canonical archive moved the change to
`openspec/changes/archive/2026-07-30-activate-atenea-remote-routing` and
synchronized the accepted Atenea activation behavior into authoritative
`atenea-project-onboarding` and `remote-worker-control`. Post-archive strict
validation passes all 11 authoritative specifications; there are no active
changes.

Sanitized task-4.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-4.4-openspec-archive`;
the SHA-256 of its `SHA256SUMS` is
`70ba3ebb5f3be3c8ad689302c81a7190f128777fe7143619c5da1f28ebdd9e22`.

Task 4.5 completes `activate-atenea-remote-routing` at `19/19`. Atenea source
is clean and synchronized at
`1bef4b01a0ddd71f71279721bad908867cc21c3c`; the programme archive parent is
clean and synchronized at
`a3b8add8afeaf6a01691f9abe79789d2a7030dfd`. All 11 authoritative OpenSpec
specifications pass strict validation and no active change remains.

Atenea and Beautips selection/execution are enabled only for their exact
retained workspace identities. Production and preview are `UP`; the worker is
active; all three RAID arrays are `[UU]`; slot container counts remain
`3/0/0/3`; and non-terminal AgentRuns plus unexpected remote WorkSessions are
zero.

Sanitized task-4.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-remote-routing/runs/task-4.5-final-state`;
the SHA-256 of its `SHA256SUMS` is
`5ceeff47febe959e5b9b3dd3dc64a9eb87947e4d1fe7e685aae2c37ea5bd3473`.

The Atenea activation change is complete and archived. Atenea and Beautips are
ready for normal remote work from the laptop and mobile application.

## Codex session operations

The active OpenSpec change is `add-codex-session-operations`. It defines the
next programme phase for professional day-to-day Codex operation through
Atenea: effective model and reasoning-effort selection, sanitized intermediate
progress, self-service run recovery, reusable Android notifications and a
separately authorized managed Codex version lifecycle.

The change contains 57 ordered tasks across safe execution foundations,
contracts, the Atenea control plane, AX42, web and Android experience,
notifications, version administration and final acceptance. Progress is
`0/57`; the exact resume point is task 0.1. Implementation must proceed task by
task and retain the disable-first rollback boundary. A real AX42 Codex version
activation remains subject to separate explicit authorization at task 6.7.

The accepted control boundary does not expose arbitrary Codex flags, commands,
providers, endpoints, paths, environment values or host services. Model and
effort changes apply only to future AgentRuns; each run retains its immutable
effective profile and Codex version. Intermediate progress is bounded and
sanitized and must never retain hidden reasoning, raw command output, prompts,
answers, credentials or tokens.

The first broad Atenea implementation attempt is retained only as a stale
unvalidated draft. It started from
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b`, four commits behind canonical
`1bef4b01a0ddd71f71279721bad908867cc21c3c`, overlaps newer canonical web and
Android prompt-delivery fixes, contains no new tests and has a compile-time
duplicate parameter in `RemoteAgentRunCoordinator`. AgentRun `78` records
successful Codex process completion, not accepted work. No draft file may be
committed, rebased, ported, deployed or discarded before task 0.1 fingerprints
it and the foundation gates permit reviewed recovery.

Task 0.1 is complete and change progress is `1/57`; the exact resume point is
task 0.2. The retained draft remains byte-identical before and after capture
at HEAD `d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b`, with an unchanged clean index,
28 tracked modified files and 16 untracked files. Its tracked binary diff
fingerprint is
`fe004b66dc9d76da024c6c514ccd7992b6846b2556fab8694bbfd3feb6257fa8`;
its untracked manifest fingerprint is
`b7b2d520213300600bdbb3bd005ede283fd505f24be31d4e018e90a144fc4fa8`.

Canonical Atenea remains clean and synchronized at
`1bef4b01a0ddd71f71279721bad908867cc21c3c`, four commits ahead. The exact
overlap is limited to `WorkSessionConversationScreen.kt`, `web/src/App.tsx`
and `web/src/api.ts`. Allocation remains `slot2/heavy1`; the slot and rootless
Docker service are active while owned containers, networks, listeners,
session processes, Codex executions, project runners and Playwright/Chromium
processes are all zero.

Sanitized task-0.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.1-stale-draft-fingerprint`;
the SHA-256 of its `SHA256SUMS` is
`7cdfa7a4b8861bd4a27cd59e1742bd79db156ca508eaa6b84044e3275da38ee9`.

Task 0.2 is complete and change progress is `2/57`; the exact resume point is
task 0.3. Its initial static-pin experiment was deliberately discarded before
commit after proving that a repository cannot embed its own current branch
HEAD as a stable constant: the commit containing that constant immediately
creates a different HEAD.

Atenea now observes its fixed remote branch at runtime before the first
write, requires the canonical checkout to be on that branch, clean and exactly
equal to the remote commit, then persists the ref, commit, observation
fingerprint and time. The immutable value is copied into AgentRun. AX42
independently resolves the root-owned mirror ref before workspace admission
and dispatch; configuration, workload, mirror, registered workspace and clean
WorkSession HEAD must all match. The independently observed worker commit is
returned and persisted before dispatch.

The Atenea implementation is published cleanly at
`5dfa8d4174b67019216a9c97746d502431e1959c`. Two complete backend passes each
ran 420 tests with zero failures, errors or skips. Two worker passes each ran
8 project-runner, 18 AgentRun-worker and 4 Beautips-compatibility tests plus
shell syntax validation. External timeouts were 600 seconds for backend
passes and 120 seconds for worker passes. Negative acceptance covers stale
ancestor, divergence, tracked/untracked dirt, missing or ambiguous ref, moved
control-plane ref, moved worker mirror and conflicting workload commit.

The stale WorkSession remains byte-preserved at
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b` with clean index, 28 tracked
changes, 16 untracked files and zero session processes. No worker install or
production deployment occurred. The installed mirror remains deliberately at
`1bef4b01a0ddd71f71279721bad908867cc21c3c`; the new contract rejects that
difference from canonical instead of fetching, resetting, reassigning or
inventing ownership during admission.

Sanitized task-0.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.2-canonical-source-admission`;
the SHA-256 of its `SHA256SUMS` is
`da95d1047002253d983e1b877eac1d955d598065d9a60d33f820d8cd30ca8fb9`.

Task 0.3 is complete and change progress is `3/57`; the exact resume point is
task 0.4.

Atenea now has a durable `DRAFT_BLOCKED` state separate from active and closed
sessions. The mediated recovery locks the exact stale remote Atenea
WorkSession, refuses non-terminal AgentRuns, observes the accepted canonical
source and requests a sanitized AX42 fingerprint. The worker accepts only its
fixed root-owned Atenea route, current mirror commit, exact registered
WorkSession and inactive execution ownership. The result contains hashes,
counts and immutable identities only; fixed Git operations have finite
timeouts plus bounded entry and byte limits.

The old WorkSession is flushed as `DRAFT_BLOCKED` before the replacement
`OPEN` row is inserted, preserving the one-active-session database invariant
inside one transaction. The replacement receives a new remote identity,
workspace branch and accepted canonical observation. External thread, final
commit and draft metadata are not transferred. A completed recovery is
idempotent and returns its persisted replacement without another worker call
or session creation. No rebase, merge, reset, commit, checkout, clean, copy or
draft deletion occurs.

The Atenea implementation is published cleanly at
`a94c119e561fe9a70b158fae54cd333a8507c541`. Two accepted backend passes each
ran 425 tests with zero failures, errors or skips and validated all 51 Flyway
migrations. Two worker passes each ran 20 tests with zero failures; shell
syntax validation also passed. External timeouts were 600 seconds for backend
passes and 120 seconds for worker passes.

The real retained draft remains unchanged at
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b`, with tree
`7e4531a5c5538d4f30fdb63d588db1afc9e34ddc`, clean index, 28 tracked
changes, 16 untracked files and zero session processes. Its tracked and
untracked fingerprints still match task 0.1. No backend, migration or worker
deployment and no real recovery occurred; task 0.10 retains ownership of
creating the current clean Atenea WorkSession after all remaining foundation
gates pass. The installed worker mirror therefore remains deliberately at
`1bef4b01a0ddd71f71279721bad908867cc21c3c`.

Sanitized task-0.3 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.3-retained-draft-recovery`;
the SHA-256 of its `SHA256SUMS` is
`246f3f7aa197a4907faf88851c32ce5b09b3022540243cf1753ba4ab469869d1`.

Task 0.4 is complete and change progress is `4/57`; the exact resume point is
task 0.5.

AgentRun now persists a separate terminal process outcome constrained to agree
with lifecycle status. A successful Codex process therefore means only
`processOutcome=SUCCEEDED`; it does not imply build, test, review, publication
or task acceptance.

WorkSession independently persists `DRAFT`, `VALIDATING`, `BLOCKED`,
`VALIDATED` and `INTEGRATION_READY` acceptance states. The projection binds an
exact source-tree SHA-256, observation time, validation-projection SHA-256 and
validator-definition revision. Blocked state names one bounded missing or
failed check and the next permitted action. Integration readiness is accepted
only from `VALIDATED` with the identical tree, projection and definition
revision and performs no implicit commit, publication or deployment.

Starting another AgentRun conservatively removes earlier validation and
readiness. Observing any different tracked or untracked source-tree
fingerprint clears the complete validation projection and both validated and
integration-ready times atomically. Re-observing the identical tree preserves
the accepted projection.

AX42 source now includes a closed source-tree fingerprint operation. It accepts
only the fixed current Atenea route, current mirror commit and exact registered
WorkSession, runs fixed bounded Git operations and returns only the HEAD,
fingerprint and counts. File names, contents, caller commands, paths and
environment values are not returned or accepted.

Task 0.5 is complete and change progress is `5/57`; the exact resume point is
task 0.6.

Atenea now exposes only the symbolic `BACKEND_TEST`, `WEB_BUILD` and
`ANDROID_BUILD` validation operations. Each operation derives its immutable
identity from the exact remote WorkSession, current sanitized source-tree
fingerprint and versioned validator definition. Repeating that identity returns
the durable operation instead of starting a duplicate. The persisted result
contains only lifecycle state, exit code, bounded duration, sanitized summary
and artifact-manifest SHA-256. The acceptance projection remains separate and
becomes `VALIDATED` only after all three exact operations succeed; no commit,
publication, routing or deployment is implied.

The AX42 worker accepts an exact fixed-field request and independently
re-observes the registered Atenea workspace before admission. Unknown or extra
fields, foreign ownership, altered operation or definition, and changed source
fail closed before the mediator starts. The root-owned mediator accepts exactly
four validated positional identities, resolves the worktree only from the
root-owned registry, uses fixed commands in an isolated copy, applies
900/600/1200-second timeouts and deletes raw command output after hashing it.
The Android definition uses an empty environment and explicitly unavailable
secret files, so validation has no APK or Firebase credential authority.
Interrupted durable `RUNNING` validations reconcile to a sanitized `BLOCKED`
terminal state after worker restart.

Two accepted backend passes each ran 435 tests with zero failures, errors or
skips and validated all 53 Flyway migrations. Two worker passes each ran 24
tests with zero failures. Python compilation, shell syntax checks and strict
OpenSpec validation passed. The isolated database container and network were
removed after the suites; the named test database volume remains retained.
No worker installation, service restart, real validation, production change or
WorkSession mutation occurred in task 0.5.

Sanitized task-0.5 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.5-closed-validation-operations`;
the SHA-256 of its `SHA256SUMS` is
`2d81fdae178520a167e8d698faea2de184d354924d44108d38317f1ce5791877`.

Task 0.6 is complete and change progress is `6/57`; the exact resume point is
task 0.7.

`PLAYWRIGHT_ACCEPTANCE` extends the same immutable validation identity and
acceptance projection with definition
`atenea-playwright-acceptance-v1` and a fixed 600-second outer timeout. Its
root-owned runner derives the exact slot only from the WorkSession allocation,
requires the locked Playwright 1.60.0 module and image, builds the web source in
the isolated validation copy and starts one exact-labelled rootless container.
The caller supplies no URL, route, viewport, assertion, browser, image, network,
mount, path, slot or environment.

The browser container has no network, drops all capabilities, has a read-only
root, bounded memory/PIDs and a finite writable `/tmp`. A fixed in-container
loopback server presents the built SPA. Playwright separately proves HTTP/data,
non-empty visible DOM and no horizontal overflow at `1440x900` and `390x844`,
then retains only the two PNGs and a sanitized report containing dimensions,
counts, booleans and SHA-256 values. Pages, contexts, browser and server close
in `finally`. `--rm` removes the exact container; timeout cleanup removes it
only when all three immutable ownership labels match, and retains any foreign
same-name object fail-closed.

Two synthetic Playwright passes completed with HTTP 200, visible critical
content, no horizontal overflow and deterministic two-viewport reports.
Desktop and mobile screenshots were inspected at original resolution: content,
state and long identifiers are readable with no clipping, overlap or
off-screen rendering. Two worker passes each ran 24 tests without failure. Two
backend passes each ran 435 tests with zero failures, errors or skips and
validated all 54 Flyway migrations. Shell syntax, JavaScript syntax and strict
OpenSpec validation passed. Temporary browser processes, backend containers and
networks were removed; no real WorkSession, worker installation, production,
routing, preview or Beautips resource changed.

Sanitized task-0.6 evidence, including the inspected original-resolution PNGs,
is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.6-closed-playwright-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`db4611b2c718a19ea78737e78268da4ef9f24c1d5659b223680f8394267515be`.

The Atenea implementation is published cleanly at
`e4947afc0cc6011df14d5d8a6396ec31a977fe8d`. Two backend passes each ran 431
tests with zero failures, errors or skips and validated all 52 Flyway
migrations. Two worker passes each ran 21 tests with zero failures; Python and
shell syntax validation also passed. No backend, database migration or worker
deployment occurred, and no real production acceptance projection was
written. The retained stale draft and installed worker mirror remain
unchanged.

Sanitized task-0.4 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.4-truthful-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`88a9e53f34bc1026003d187b6709a8c0f86dd04176373c513208d09e3c0b1006`.

Task 0.7 is complete and change progress is `7/57`; the exact resume point is
task 0.8.

Atenea now persists one closed three-role repository set per remote
WorkSession. `ATENEA_CODE`, `PROGRAMME_OPENSPEC` and `WORKER_SOURCE` share one
immutable change identity while retaining their own exact repository, branch,
commit, mirror/worktree SHA-256 identity, validation profile and readiness.
The database requires both source and validation-projection fingerprints
before a role can become `VALIDATED` or `INTEGRATION_READY`. Linked readiness
cannot advance while any component remains `DRAFT`.

The AX42 worker contract accepts no caller repository, path, branch, mirror,
authority, validation profile or command. Its fixed root-owned mediator derives
the registered Atenea workspace, creates distinct programme and worker-source
worktrees from the reviewed programme commit and assigns them to separate
non-login operating-system identities with no group/other permissions. The
installed root-owned worker remains outside both writable roles. Repeating the
same identity is idempotent; alternate change identities, foreign commits,
extra fields, missing ownership and ambiguous pre-existing paths fail closed.

Two backend passes each ran 440 tests with zero failures, errors or skips and
migrated an empty PostgreSQL database through all 55 Flyway migrations. Two
worker passes each ran 26 tests with zero failures and each also passed the
synthetic multi-worktree ownership scenario. Focused API/service, Python
compile, shell syntax, diff and strict OpenSpec validation passed. Test
containers and networks were removed while the named test database volume was
retained.

No worker installation, deployment, real repository-role creation,
production, routing, preview or Beautips change occurred. The installed worker
and its deliberately stale mirror refs remain unchanged pending later
foundation rollout tasks.

Sanitized task-0.7 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.7-multi-repository-roles`;
the SHA-256 of its `SHA256SUMS` is
`de64f78e63956ff9c466ed185700a8454b300c61e7d58b60fd7fd81d3f469022`.

Task 0.8 is complete and change progress is `8/57`; the exact resume point is
task 0.9.

Every new exact remote project AgentRun now persists the reviewed instruction
bundle revision, combined SHA-256, platform-source SHA-256, fixed
`AGENTS.md` path and repository-source SHA-256 before dispatch. Atenea and
Beautips have separate project and combined fingerprints while sharing one
root-owned platform policy. Historical runs remain truthful rather than being
backfilled with an instruction identity they did not execute.

The worker accepts only the project-specific closed fingerprints. The runner
independently verifies the root-owned, non-writable platform file and compares
the worktree bytes of `AGENTS.md` with both the expected SHA-256 and
`HEAD:AGENTS.md` from the exact accepted commit. A changed file,
`AGENTS.override.md`, repository `.codex` content, missing source, unsafe
ownership or any conflicting fingerprint blocks before Codex starts.

Inside the reviewed Bubblewrap namespace, global `AGENTS.md` and
`AGENTS.override.md` plus automatic repository instruction discovery are
masked. The verified platform and repository contents are instead injected as
one explicit developer-instruction bundle. `--ignore-user-config` continues to
exclude personal configuration and `--ignore-rules` excludes ambient
exec-policy rules. The request has no instruction content, rule-source path,
configuration fragment or override authority.

Two backend passes each ran 441 tests with zero failures, errors or skips and
migrated empty PostgreSQL databases through all 56 Flyway migrations. Each of
two worker rounds passed 26 AgentRun-worker tests, 9 instruction-runner tests,
4 Beautips adapter tests, 5 Beautips mediator tests and the synthetic install
lifecycle. Python compilation, shell syntax, JSON parsing, immutable source
hashes, diff checks and strict OpenSpec validation passed.

No worker installation, real AgentRun, deployment, production, routing,
preview or Beautips resource changed. The installed worker and deliberately
stale mirror remain unchanged for the later foundation rollout gate.

Sanitized task-0.8 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.8-reviewed-instruction-bundle`;
the SHA-256 of its `SHA256SUMS` is
`de0d49bf0d2f9d7880401273d8e269c8bdd5b5948677aca6f0d28e812b497631`.

Task 0.9 is complete and change progress is `9/57`; the exact resume point is
task 0.10.

The project dispatch schema and worker now carry a permanent negative
authority matrix. Caller-supplied commands, images, Compose files,
environments, paths, hosts, slots, endpoints, credential references and rule
sources are rejected as unknown fields. Foreign repositories fail the fixed
project identity, while foreign WorkSession ownership fails the exact
registered workspace identity. The schema additionally binds the workspace to
`remote:ax42-01:work-session:<canonical UUID>` before the worker verifies its
persisted session relationship.

Every matrix case is asserted to stop before execution state is created or a
runner process can start. The durable worker execution map remains identical
and the root-owned project configuration remains byte-equivalent after each
denial. Atenea's client test independently proves that the control plane emits
only the thirteen reviewed workload fields and none of the prohibited
authorities.

Two backend passes each ran 441 tests with zero failures, errors or skips from
empty PostgreSQL databases through all 56 Flyway migrations. Two worker rounds
each passed 27 AgentRun-worker tests, 9 runner/schema tests and 4 shared
Beautips adapter tests. JSON parsing, diff checks and strict OpenSpec
validation passed.

No installation, real WorkSession or AgentRun, deployment, production,
routing, preview or Beautips resource changed. All rejected inputs were
synthetic non-secret references and no rejected credential value was read.

Sanitized task-0.9 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.9-closed-authority-denial`;
the SHA-256 of its `SHA256SUMS` is
`05e616c10027e88191efe897004142bfb4ef5c93b9afc7d0651fe517e22cea9c`.

Task 0.10 is complete and change progress is `10/57`; the exact resume point
is task 1.1.

The final Atenea source is clean and synchronized at
`ec867f75bd4bb58f582607cf0025a003400f02c8`. Two clean-container backend
passes against separate empty PostgreSQL databases each ran 445 tests with
zero failures, errors or skips and applied all 56 Flyway migrations. Two final
worker passes each accepted the AgentRun worker, Atenea runner, Beautips
adapter, Beautips operation mediator, multi-repository, Playwright, retained
installer and shared installer suites; shell syntax also passed. The accepted
backend passes took 40 and 43 seconds, and the worker passes took 58 and 57
seconds, under external timeouts of 600 and 180 seconds respectively.

Production runs backend image
`sha256:7b62d5459831ede557e6277e6252a891e79230e2b52ce57d4ac9277c0928e36d`
with zero restarts and schema V56. A root-only, profile-gated command invoked
the same transactional recovery service without reading an operator token or
modifying the database directly. Its exact authority bound database row 6,
remote UUID `c750641d-3226-44c3-81dc-d9149aac0de1`, retained HEAD
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b` and accepted commit
`ec867f75bd4bb58f582607cf0025a003400f02c8`. The sanitized result exposed no
values, marked row 6 `DRAFT_BLOCKED` and created row 7 `OPEN` with remote UUID
`83356a20-421c-4d5f-8de6-05c98cce1c32`.

The stale draft remains byte-equivalent to task 0.1: clean index, 28 tracked
changes, 16 untracked files, tracked diff SHA-256
`fe004b66dc9d76da024c6c514ccd7992b6846b2556fab8694bbfd3feb6257fa8`
and untracked manifest SHA-256
`b7b2d520213300600bdbb3bd005ede283fd505f24be31d4e018e90a144fc4fa8`.
Its released allocation conflicted with safe reuse of fixed slot 2. Following
D-048 and new decision D-051, the marker was renamed to
`runtime-allocation-v1.retired.json` only after semantic equality with sealed
task-0.1 evidence and zero owned containers, networks, images, listeners and
runtime unit were proved. SHA-256 remained
`f143453718f4c8758665a02986ce44c607feff3f44cc0971100fb63ab4ac1cac`
before and after the rename.

The replacement worktree is clean on branch
`atenea/session-83356a20-421c-4d5f-8de6-05c98cce1c32` at the exact accepted
commit. It owns slot 2 and heavy 1, one allocation and the only enabled Atenea
worker registration, but no runtime container, network, listener or process
was started. The installed registration path disables optional Git locks so a
root-owned read cannot replace the worker-owned index; an idempotent activation
repeat preserved index ownership `atenea-worker:atenea:0644`.

Non-terminal AgentRuns and previews for the retained/replacement sessions are
zero. Slot inventories remain `3/0/0/3`; production, preview, administrative
Beautips and WorkSession Beautips are `UP`; rootful Docker remains
inactive/masked; SSH, Tailscale, UFW and the worker are active; all RAID arrays
remain `[UU]`. Temporary installer fixtures were removed by exact identity.

Sanitized task-0.10 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-0.10-foundation-current-worksession`;
the SHA-256 of its `SHA256SUMS` is
`76cbdf25b6f49ed78c3ba16a536edc20e52e43053adb7ed2a60153679ee4cc0b`.

Task 1.1 is complete and change progress is `11/57`; the exact resume point is
task 1.2.

The entry baseline records clean synchronized Atenea source at
`ec867f75bd4bb58f582607cf0025a003400f02c8`, clean synchronized programme
source at `54f489d2d2b8b5359c11812f59c474b210a64741`, and AX42 mirror refs at those
same commits. Production and preview are `UP`; the backend and both App Server
containers are running with zero restarts; schema remains V56. The two open
remote sessions are only Beautips row 4 and current Atenea row 7, with zero
non-terminal AgentRuns.

The installed worker is active with protocol `agent-run-worker/v1`, capacities
4 normal and 2 heavy, plus synthetic and exact-project capabilities. Atenea and
Beautips each have one exact enabled registration. Installed programme and
runner fingerprints pass verification, slot inventories remain `3/0/0/3`,
SSH, Tailscale and UFW are active, and all RAID arrays remain `[UU]`.

The effective AX42 project runner currently invokes standalone Codex CLI
`0.145.0` with SHA-256
`a2a05dafaa1acb002a45eaec0a462de5b13694fcfcd7bc43305f14781ce7be14`.
Production and rescue App Servers contain Codex CLI `0.130.0`. The runner has
no explicit model or reasoning-effort option, ignores user configuration and
ambient rules, and persists no AgentRun effective model, effort or Codex
version. This observed difference is retained truthfully for the precedence
and catalog decisions in task 1.2 rather than being normalized during capture.

The FCM/device projection contains two active Android devices, one reporting
app `0.5.94` and one `0.5.95`, plus three sent `RUN_SUCCEEDED` notification
records and zero notification records for current Atenea session 7. No push
token, device identifier, notification body, credential, environment dump,
auth file, prompt, answer or execution result was read or retained.

Sanitized task-1.1 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-1.1-entry-baseline`;
the SHA-256 of its `SHA256SUMS` is
`b5d6a97596b072282ddc28adc629b341b711fd480ad765c08c50d7c922b0f6fb`.

Task 1.2 is complete and change progress is `12/57`; the exact resume point is
task 1.3.

Model and effort now resolve independently through exact `NEXT_TURN`,
`WORK_SESSION`, `PROJECT`, `PLATFORM` and `WORKER_DEFAULT` precedence. Every
future AgentRun must persist both field sources, the canonical values, catalog
revision and exact Codex version before dispatch. Settings never rewrite an
earlier run.

The worker catalog fields, digest boundary and per-model effort advertisement
are fixed. The only recognized effort vocabulary is `none`, `low`, `medium`,
`high`, `xhigh` and `max`, intersected fail-closed with worker and
platform/project policy. Friendly aliases, Pro mode and Ultra operation do not
become persisted execution-profile values. These decisions were checked
against the current official GPT-5.6 migration and prompting guidance rather
than inferred from the older installed CLI baseline.

The exact progress taxonomy contains thirteen sanitized categories. Identical
consecutive category/message pairs coalesce before sequence allocation; each
run retains its newest 200 normalized events without sequence reuse, while
current/latest/terminal/elapsed/next-action projections remain independent.
Raw reasoning, commands, output, environment and secret-bearing payloads remain
forbidden.

The routine, privileged and platform-administrator role matrix is now closed.
Binary update planning and staging require platform administration; activation
uses a finite single-use exact authorization, and an operator-requested
rollback requires a separate authorization. The activation authority covers
only automatic restoration of its exact previous version after a failed gate.

`RUN_COMPLETED`, `RUN_FAILED` and `ACTION_REQUIRED` default enabled for active
Android devices without an explicit preference. Explicit device preferences
survive re-registration/application upgrade, while intermediate progress stays
in-app/SSE and produces no push notification.

Final read-only checks confirmed clean Atenea source, production and preview
`UP` with zero backend/App Server restarts, active AX42 worker/SSH/Tailscale/UFW,
all RAID arrays `[UU]` and rootful Docker inactive. No runtime, routing,
database, WorkSession, AgentRun, slot, device or notification delivery changed.

Sanitized task-1.2 evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-1.2-contract-freeze`;
the SHA-256 of its `SHA256SUMS` is
`07bcd219a0316538df281f0069b5d00c73c209e42b760519721cd64c0871ba24`.

Task 1.3 is complete and change progress is `13/57`; the exact resume point is
task 1.4.

The production baseline remains Flyway V56. The accepted design reserves V57
through V61, in order, for execution profile/catalog inventory, bounded
progress, idempotent recovery, generic notification events/preferences/
deliveries and managed Codex update inventory/operations. Every migration is
expand-only: legacy AgentRuns and push logs are neither backfilled with
invented values nor deleted, and migration itself enables no behavior.

Five independent profile, progress, recovery, notification-outbox and
managed-update gates are fixed default-false. Rollout applies the schema, then
deploys reader-compatible backend, dual-compatible worker and clients before
synthetic capability-by-capability activation. Notification cutover stops the
old category producer before its generic dispatcher starts, preventing a
dual-send window.

Before any production V57 application, the production backup authority must
create a PostgreSQL 16 custom-format V56 backup and restore it in a disposable
network-isolated fixture. That fixture must reproduce the sanitized baseline,
accept V57–V61 twice with the second pass a no-op, pass candidate tests and run
the exact intended rollback image. If that image rejects future Flyway history
or expanded reads, production migration remains blocked until a compatibility
image containing V57–V61 with every new gate disabled passes.

Rollback is explicitly disable-first: reject new update/recovery/profile work,
stop generic push/progress publication, block new affected dispatch and
reconcile persisted ownership before restoring only a fixture-proven
compatible application. Expanded rows, devices, deliveries, WorkSessions,
routing and affinity remain. Flyway repair, destructive down migration,
notification replay and automatic schema contraction are forbidden.

Task 1.3 was documentation-only. No backup was created, no migration was
applied and no runtime, production, routing, database or worker state changed.
Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-1.3-migration-rollback-design`;
the SHA-256 of its `SHA256SUMS` is
`0ac9a8a867df7078bede37d6164072728dce34192291aa2538c23b375499b98e`.

Task 1.4 is complete and change progress is `14/57`; the exact resume point is
task 1.5.

The programme now contains additive executable schemas for the canonical
worker model catalog, `project-codex-v2` dispatch/result, sanitized progress
and the closed authenticated settings/recovery/update API request union. The
currently installed `project-codex-v1` remains unchanged; v2 is a contract for
the later worker implementation tasks, not an implicit activation.

The v2 workload adds only canonical model, effort, catalog revision and Codex
version. API callers may name persisted WorkSession, AgentRun, plan, candidate
and authorization identities, but cannot submit a workspace, command,
provider, endpoint, path, service, host, slot, environment, credential or
release URL. Those authorities remain fixed and server-derived.

Schema validation is followed by exact semantic validation. The catalog digest
is canonical, its model identities are unique, each default effort belongs to
the advertised model set, and dispatch must match the accepted catalog/Codex
version plus the exact registered `(sessionId, workspaceIdentity)` pair. Thus a
well-formed arbitrary model or foreign UUID still fails before execution state
or process creation.

The synthetic corpus covers twelve negative model, effort, catalog, command,
provider, endpoint, path, service, update and foreign/ambiguous ownership cases.
Progress separately rejects reasoning, raw command/output and environment
fields. The new contract tests and existing v1 project runner/worker suites ran
40 tests with zero failures, errors or skips in under four seconds. Every JSON
document parses, `git diff --check` and strict OpenSpec validation pass.

No contract was installed and no runtime, production, routing, database,
WorkSession, AgentRun, worker service or Codex process changed. Sanitized
evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-1.4-closed-schemas-negative-fixtures`;
the SHA-256 of its `SHA256SUMS` is
`f7ff10be7fd6c70f168432d7bbc35a949bf77d89220941cdf95a8041f2e81030`.

Task 1.5 and Phase 1 are complete. Change progress is `15/57`; the exact
implementation resume point is task 2.1. Tasks 2.2 and later remain pending.

Strict OpenSpec validation passes from the programme environment, every JSON
contract parses and the same new contract suite passes in the canonical
repository. The Atenea host itself does not have the `openspec` executable, so
its attempted command returned 127 without changing state; this is an explicit
tooling fact, not a validation failure or an authority to install host-global
software.

Atenea code remains clean and synchronized at
`ec867f75bd4bb58f582607cf0025a003400f02c8`; programme code was clean and
synchronized at the task-1.4 commit before this closure. Production and preview
are `UP`, backend/App Server restarts are zero, AX42 worker/SSH/Tailscale/UFW
are active, every RAID array is `[UU]`, rootful Docker is inactive and no v2
schema is installed on the worker.

Task 2.1 must begin by implementing only V57 and its persistence model in the
Atenea code repository: nullable WorkSession/project defaults, immutable
AgentRun model/effort plus independent sources, catalog revision, Codex version
and normalized worker catalog inventory. Existing V56 rows remain explicitly
profile-absent, all five feature gates stay false and no production migration,
v2 installation or managed Codex update is implied.

Sanitized phase-closure evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-1.5-phase-1-closure`;
the SHA-256 of its `SHA256SUMS` is
`d8ccbe68b5d0dc10616254de146c8fab684cdc65036f37fae373445effe22a3e`.

Task 2.1 is complete and change progress is `16/57`; the exact implementation
resume point is task 2.2. Tasks 2.2 and later remain pending.

Atenea commit `77c813104d02290ecd7c4c263055ace7e56ad71c` adds only V57
and its persistence model. Project and WorkSession model/effort defaults are
independently nullable. An AgentRun execution profile is immutable and must be
either absent for legacy V56 history or complete with effective model, effort,
both independent sources, catalog revision and Codex version. Normalized worker
catalog, model and effort inventory is present, and only the canonical efforts
`none`, `low`, `medium`, `high`, `xhigh` and `max` are accepted.

Five focused persistence tests and two complete 450-test passes against
separate fresh PostgreSQL 16 databases passed with zero failures, errors or
skips. The exact V56-to-V57 fixture retained legacy null history, accepted an
independent WorkSession effort default and a complete AgentRun snapshot, and
rejected `ultra` plus partial snapshots fail-closed. Test containers and
networks were removed. Raw authentication integration logs were not retained.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain `UP` with zero backend restarts;
production remains on Flyway V56. No production migration, routing, runtime,
WorkSession, AgentRun, worker, notification or device state changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.1-execution-profile-persistence`;
the SHA-256 of its `SHA256SUMS` is
`7d0e0ac7e09c9fe52f710bf0eadef84e64ea3aaddfeb6de48f7ca403ee45e6fc`.

Task 2.2 is complete and change progress is `17/57`; the exact implementation
resume point is task 2.3. Tasks 2.3 and later remain pending.

Atenea commit `63bd7c1eac15cbd1865f6718f8c17aec28c230af` adds V58,
the durable event entity/repository and transactional append/replay service.
An exact AgentRun row lock serializes allocation. Identical consecutive
category/template pairs coalesce before allocation, sequences are never reused
and insertion beyond 200 events advances the retained floor and removes only
older detail rows. Current/latest state, terminal outcome, elapsed time and
required next action remain separate AgentRun projections.

The thirteen category messages are closed templates enforced in both Java and
PostgreSQL; free-form or credential-shaped message insertion is rejected. A
terminal category must match the persisted AgentRun outcome. A client below
the retained floor receives the projection and retained gap, while a legacy
run with no progress remains explicitly projection-absent.

Eleven focused persistence tests passed. Two complete 456-test passes against
separate fresh PostgreSQL 16 databases migrated through V58 passed with zero
failures, errors or skips in 43 and 44 seconds. Source and Maven dependencies
were read-only, database ports were not published, and the exact fixed test
workspace was separately writable. No test container, network, volume or raw
authentication log remains.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain `UP` with zero backend restarts;
production remains on Flyway V56. No production migration or operational
state changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.2-bounded-progress`;
the SHA-256 of its `SHA256SUMS` is
`c2db676350664d73e2d7552cf80cf3c16ea3f5dab55c1a8e198740790ee77a30`.

Task 2.3 is complete and change progress is `18/57`; the exact implementation
resume point is task 2.4. Tasks 2.4 and later remain pending.

Atenea commit `cf3dfacaa6b6b4b732b38a536fafa58ee5e13296` adds V59
and closed recovery persistence. Operator accounts default to
`ROUTINE_OPERATOR`; every operation snapshots that persisted role and binds an
exact operator, WorkSession, AgentRun, action, idempotency key and canonical
request fingerprint. Composite ownership rejects a foreign run/session pair.
Exact repetition returns the existing operation, while conflicting key reuse
fails closed.

Routine cancel, retry, reconciliation and diagnostic requests are permitted.
A routine restart attempt is retained as an actionable `ROLE_REQUIRED`
rejection without invoking any service. Privileged roles may persist only the
two fixed mediated restart actions. State/outcome, exact sanitized summary and
next-action combinations are constrained in PostgreSQL. `RETRY_CREATED`
requires one same-session result AgentRun with immutable `retryOfRunId`
lineage to the failed source; the original attempt remains unchanged.

Seventeen focused persistence tests passed. The final two complete 462-test
passes against separate fresh PostgreSQL 16 databases migrated through V59
passed with zero failures, errors or skips in 45 seconds each. Read-only source
and dependencies, isolated workspaces and databases without published ports
were used. No task container, network, volume or raw authentication log
remains.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain `UP` with zero backend restarts;
production remains on Flyway V56. No real recovery operation, production
migration or operational state change occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.3-idempotent-recovery`;
the SHA-256 of its `SHA256SUMS` is
`85086b48f96e6de5e69a3ef8bad6a42b8b21012135ec9f6b395df8ebe505e025`.

Task 2.4 is complete and change progress is `19/57`; the exact implementation
resume point is task 2.5. Tasks 2.5 and later remain pending.

Atenea commit `a15719e8c2c54502c4b66a586481e62b061c2f20` adds V60
and the generic notification outbox persistence service. Events are limited to
`RUN_COMPLETED`, `RUN_FAILED` and `ACTION_REQUIRED`; their title/body and link
kind are exact `agent-run-safe-v1` database-enforced templates. Event identity
binds category, AgentRun and source revision to a SHA-256 deduplication key and
composite WorkSession/AgentRun ownership. Prompt, answer, internal worker detail
and device token are absent from event and delivery rows.

An absent per-device/category preference means enabled, while an explicit row
wins and survives re-registration. Each active enabled device receives at most
one `(event, device, FCM)` delivery with bounded attempt/expiry state ready for
the later dispatcher task. This task persisted no real event and did not
activate or invoke FCM.

Twenty-three focused persistence tests passed. Two complete 468-test passes
against separate fresh PostgreSQL 16 databases migrated through V60 passed
with zero failures, errors or skips in 47 and 44 seconds. Read-only source and
dependencies, isolated workspaces and unexposed databases were used. No task
container, network, volume or raw authentication log remains.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain `UP` with zero backend restarts;
production remains on Flyway V56. No device, notification, production database
or operational state changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.4-generic-notification-outbox`;
the SHA-256 of its `SHA256SUMS` is
`413a2e015ecce66a12bbdb90c47c0b27c5001bf4883dfaa9718e63c96ba80bbc`.

Task 2.5 is complete and change progress is `20/57`; the exact implementation
resume point is task 2.6. Tasks 2.6 and later remain pending.

Atenea commit `b95ea1682bccdc65db45a102a2f580e5eda6d919` exposes
authenticated catalog, project/WorkSession future settings, immutable run
detail, durable progress replay, recovery request, owned device preference and
platform-administrator inventory endpoints. Profile writes require exact
current catalog/model/effort membership and never rewrite a historical
AgentRun. Recovery reuses V59 ownership and idempotence.

All write endpoints compare the exact JSON field set before conversion, so an
additional provider, endpoint, host, path, service, command or other authority
is rejected. Foreign devices are hidden. Administrator authority is resolved
from the current active database account instead of a token claim. Catalog and
inventory responses omit endpoint, credentials and device-token values.

The five independent profile, progress, recovery, notification-outbox and
managed-update gates now exist and default false. Seven focused HTTP tests and
the existing mobile controller regression set passed. Two final complete
475-test passes against separate fresh PostgreSQL 16 databases at V60 passed
with zero failures, errors or skips in 46 seconds each. The first pre-acceptance
full run exposed and led to removal of an incompatible principal constructor;
both final runs prove the corrected design.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain `UP` with zero backend restarts;
production remains V56 and no new endpoint or gate was deployed or enabled.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.5-authenticated-operations-apis`;
the SHA-256 of its `SHA256SUMS` is
`45dc30a1433681cfed5087039fb2b394953a3dcc0cf418662498fd65ece31b96`.

Task 2.6 is complete and change progress is `21/57`; the exact implementation
resume point is task 2.7. Tasks 2.7 and later remain pending.

Atenea commit `5938c5d87db64d0f5b4f947bc0d81ce332109661` publishes
committed V58 progress through the existing shared web/mobile event feed while
the independently default-disabled progress gate is enabled. Each safe closed
category carries its persisted sequence and stable
`progress:{runId}:{sequence}` identity. Existing session, turn, run and
deliverable items also have stable identities, and the SSE connection seeds
and polls the bounded 200-item window by identity instead of timestamp.

When a run has committed terminal progress, the enabled feed publishes one
progress terminal and suppresses the parallel legacy lifecycle terminal. Its
single persisted `TURN_CODEX` remains the only conversation response. With the
gate disabled, no progress is published and the legacy terminal feed remains
available without rewriting history. Web and Android accept the same additive
identity and sequence fields.

Eleven focused backend/API/SSE tests passed. Two complete 478-test passes
against separate fresh PostgreSQL 16 databases at V60 passed with zero
failures, errors or skips in 43.274 and 48.058 seconds. Web production builds
and Android API Kotlin compilation each passed twice. The final suites used a
globally disabled synthetic bootstrap so only authentication tests created
their own operator. No task container, network, database volume or raw test
log remains.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain running with zero backend restarts;
production remains V56 and no new code, migration or gate was deployed or
enabled.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.6-shared-progress-stream`;
the SHA-256 of its `SHA256SUMS` is
`88d2054778bc56c9c682dc36f35d9774fd95e4f0fc8a537acb6481f5016050e1`.

Task 2.7 and Phase 2 are complete. Change progress is `22/57`; the exact
implementation resume point is task 3.1. Tasks 3.1 and later remain pending.

Atenea commit `652eaa08934dd1e6a6261407596a95c5a6630aeb` adds the final
focused migration integration check and no production functionality. It
proves Flyway V57–V60 ordering, the expected additive tables, columns and
ownership constraints, and all five capability gates default false. Together
with the focused suites added throughout tasks 2.1–2.6, Phase 2 now has direct
migration, repository, service, authorization, API, SSE, idempotency and
sanitization coverage.

The combined focused set passed 34 tests. Two complete 479-test passes against
separate fresh PostgreSQL 16 databases at V60 passed with zero failures,
errors or skips in 43.592 and 43.434 seconds. Global synthetic authentication
bootstrap was disabled; authentication-specific tests opt in with their exact
fixture. No task container, network, database volume or raw test log remains.

The canonical Atenea branch and remote are clean and synchronized at that
commit. Production and preview remain running with zero backend restarts;
production remains V56. Phase 2 was not deployed or enabled, and AX42 worker
protocol/capability work begins only at task 3.1.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-2.7-focused-control-plane-tests`;
the SHA-256 of its `SHA256SUMS` is
`c4402aca10b2075045bc97b3c41d2a43204abba4ef1f215e309d7085eef2088b`.

Task 3.1 is complete and change progress is `23/57`; the exact implementation
resume point is task 3.2. Tasks 3.2 and later remain pending.

Programme/worker commit `48c201034bdfdbc4fcc10fcceb8a653c3194f769`
adds authenticated `GET /v1/codex/catalog` and the independent
`codex-model-catalog-v1` capability. The closed catalog contains exact worker
identity, Codex `0.145.0`, canonical revision, generation time and sorted model
entries. Its digest excludes generation time and matches accepted revision
`125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187`.

The initial inventory exposes only canonical `gpt-5.6-sol`, availability
`AVAILABLE`, default effort `medium` and its exact `none`, `low`, `medium`,
`high`, `xhigh`, `max` set. It exposes no alias, Pro/Ultra mode, provider,
endpoint, path, flag, configuration or credential. The strict v1 health shape
is unchanged, and executable `agent-run-project-codex-v2` remains withheld
until tasks 3.2 and 3.3 complete.

Two final 33-test worker/catalog passes succeeded with zero failures, errors
or skips under 120-second command bounds. AX42 independently reported the
fixed runner binary as `codex-cli 0.145.0`; its installed worker remained
active/running with zero restarts, the same program SHA-256 and the same
tailnet-only listener. This task was not installed or enabled. Production and
preview remained running with zero backend restarts and production stayed V56.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.1-worker-codex-catalog`;
the SHA-256 of its `SHA256SUMS` is
`a1109ee47e17724280e996148670790e1448bd7c3e7265ae9f16b01da5bf13dc`.

Task 3.2 is complete and change progress is `24/57`; the exact implementation
resume point is task 3.3. Tasks 3.3 and later remain pending.

Programme/worker commit `b42534bac10840c701b206032e344b78a490b291`
adds staged `project-codex-v2` validation and its canonical immutable request
fingerprint. Exact model, effort, catalog revision and Codex version extend the
existing complete project, source, manifest, instruction and persisted
session/workspace ownership identity rather than replacing it.

Unsupported model/effort, stale revision/version, foreign workspace and added
provider or other caller authority all fail before an execution row or process
exists. A valid v2 create also remains fail-closed as
`profile_execution_unavailable`; task 3.3 must make the fixed runner enforce
the profile before v2 execution can be persisted or scheduled.

Two final 35-test worker/protocol passes succeeded with zero failures, errors
or skips under 120-second bounds. They prove an effort change changes the
fingerprint and every rejection retains empty execution state. AX42's installed
worker remained active with zero restarts, identical program SHA-256 and the
same private listener; nothing was installed, enabled or dispatched.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.2-profiled-workload-fingerprint`;
the SHA-256 of its `SHA256SUMS` is
`0f84ee5c2281a93cda6e9e5ab3475e8a519bbcff462dccd1e30a9af0a597f36d`.

Task 3.3 is complete and change progress is `25/57`; the exact implementation
resume point is task 3.4. Tasks 3.4 and later remain pending.

Programme/worker commit `7c3a66ca83e76e9cbb4ac85733a0e57e26d5d4df`
connects validated `project-codex-v2` requests to the existing fixed project
runner. Only exact `--model` and canonical `model_reasoning_effort` arguments
are added to the reviewed command. Prompt remains stdin-only, while provider,
profile, endpoint, path, environment, credential and arbitrary flags remain
outside caller authority.

The runner probes only the fixed Codex binary and requires exact
`codex-cli 0.145.0` before execution. It echoes model, effort, catalog revision
and Codex version; the worker rejects a mismatching effective result as a
sanitized failure. Existing v1 execution remains compatible, and v2 capability
appears only under the existing exact project-selection gate.

Two final 47-test worker/runner/contract passes succeeded with zero failures,
errors or skips under 120-second bounds. AX42's real CLI help and version were
observed read-only. Its installed worker and runner hashes, private listener,
active service and zero restart count remained unchanged; nothing was
installed, enabled or dispatched.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.3-fixed-profiled-runner`;
the SHA-256 of its `SHA256SUMS` is
`4bec258f08e5d24d9c2ecd94ac1cdc6208df9346f9d9ba652ed4ef2fd39a94e2`.

Task 3.4 is complete and change progress is `26/57`; the exact implementation
resume point is task 3.5. Tasks 3.5 and later remain pending.

Programme/worker commit `54e0df2e310e0e65c80578389921f87e73bdead4`
adds a closed Codex JSONL normalization boundary. Recognized lifecycle and
tool shapes become only fixed messages from the thirteen-category taxonomy.
Reasoning, agent messages, command arguments, command output, searches,
environment values, unsupported events and every other source payload field
are discarded rather than copied or sanitized heuristically.

The worker accepts only exact category/message pairs from that boundary,
replaces the source timestamp, binds dispatch and execution identity, assigns
monotonic sequences, coalesces identical consecutive events before sequence
allocation and retains the newest 200 without sequence reuse. Progress remains
separate from final answer and effective profile. Restart/delivery
idempotence remains task 3.5.

Two final 50-test worker/runner/contract passes succeeded with zero failures,
errors or skips in 3.67 and 3.86 seconds under 120-second bounds. The Beautips
session/worker compatibility suite also passed. AX42's installed worker,
runner, Codex version, private listener, active service and zero restart count
remained unchanged; nothing was installed, enabled, dispatched or restarted.
Production and preview remained running with zero backend restarts.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.4-safe-progress-normalization`;
the SHA-256 of its `SHA256SUMS` is
`9bc042d2a5980f96f527b155b598caa0f91788e6c37757a9e55faaefada3c6b2`.

Task 3.5 is complete and change progress is `27/57`; the exact implementation
resume point is task 3.6. Tasks 3.6 and later remain pending.

Atenea commit `4765c93a0fb871a4e2b8e1ab1902eb3701c9dfc6`
adds a V58 worker-source cursor and imports only strictly owned, ordered,
fixed-message progress. The coordinator takes the owning AgentRun's
pessimistic row lock before processing a response. Imported sequences,
terminal status, external thread/turn identities and the single result turn
therefore share one transaction; repeated polling, concurrent coordinators and
startup reconciliation cannot create a second persisted event or response.

Programme/worker commit `7bf5c1d7011b49c02e549b2af070e0b99d3329e4`
adds byte-stability coverage for a terminal execution reloaded from durable
worker state. Repeating its immutable create request returns the same execution
identity, lifecycle revision, result and normalized sequence list.

Two final 30-test Atenea passes against separate empty PostgreSQL 16 databases
migrated to V60 succeeded with zero failures, errors or skips in 24.08 and
22.96 seconds. Two final 51-test worker/runner/contract passes also succeeded
in 3.85 and 3.78 seconds. Every exact synthetic database container was removed
by recorded ID. AX42's installed service, hashes, version, private listener and
zero restart count remained unchanged; production and preview remained
running with zero backend restarts. Nothing was installed or enabled.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.5-idempotent-progress-terminal-replay`;
the SHA-256 of its `SHA256SUMS` is
`25f00ab8cf37018644bb7d8a33e5649747904036572a9251ef071a001bbfcb08`.

Task 3.6 is complete and change progress is `28/57`; the exact implementation
resume point is task 3.7. Task 3.7 and all later tasks remain pending.

Programme/worker commit `3c9af70133f7a865646b24974ceddd99ebc2079d`
adds authenticated exact-cancel, read-only reconciliation inspection and
sanitized doctor routes. The new operations require complete dispatch-path,
execution, session, workspace and lease ownership. Added command, host,
service, path, slot, endpoint, environment or credential fields and all
foreign, stale or partial identities fail before mutation. The established v1
cancel surface remains compatible.

Doctor is constrained by `agent-run-doctor-v1` to fixed ownership/status fields,
one closed process observation, recovery booleans and bounded progress counts.
It excludes workload, prompt, result, command, output and operational host
detail. Reconciliation returns the existing execution and never creates,
resumes or replaces a turn. Atenea commit
`b5a5c814448324860dec587ada12873902c936d8` derives all three request envelopes
from the persisted AgentRun; coordinator cancellation now uses exact ownership.

Two final 22-test Atenea client/coordinator passes succeeded with zero failures,
errors or skips in 10.37 and 10.26 seconds. Two final 54-test
worker/runner/contract passes succeeded in 4.84 and 4.75 seconds. AX42's
installed service, hashes, Codex version, private listener, zero project
runners and zero restart count remained unchanged; production and preview
remained running with zero backend restarts. Nothing was installed or enabled.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.6-exact-recovery-operations`;
the SHA-256 of its `SHA256SUMS` is
`bece4b14c5f6def0aced6f1aa666682296b510c1c00b410b17155ab564359ae6`.

Task 3.7 is complete and change progress is `29/57`; Phase 3 is closed. The
exact implementation resume point is task 4.1. Task 4.1 and all later tasks
remain pending.

The first complete closure attempt correctly failed closed because task 3.6
changed the base project runner while the derived Beautips adapter still
pinned its predecessor. Programme/worker commit
`0879919dfce835fe65f6f2ce0aeb5711633835a3` refreshes only the reviewed
base-runner, adapter, mediator, allowlist and installer digest chain. No
runtime behavior, project ownership or enablement flag changed.

Two final complete passes then ran the 38-test worker protocol suite, 12-test
project runner suite, 4-test session-operations schema suite, worker installer
lifecycle and full Beautips aggregate. Every component passed with zero
failures, errors, skips or timeouts: 100 seconds for pass 1 and 103 seconds for
pass 2 under independent 180/240-second bounds. Exact synthetic fixtures and
test processes were removed.

AX42's installed worker and runner hashes, active service, private listener,
zero restart count and zero project-runner processes remained unchanged.
Production, preview and the existing Beautips control/database containers
remained `Up`; nothing was installed, enabled, dispatched or restarted.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-3.7-phase-3-worker-closure`;
the SHA-256 of its `SHA256SUMS` is
`fb82da0274bca64e55fb1bc9799a0bbae18fe076743c956cb21317f3c28e76de`.

Task 4.1 is complete and change progress is `30/57`; the exact implementation
resume point is task 4.2. Task 4.2 and all later tasks remain pending.

Atenea commit `83d9e47dabc9cf36a03ed570f1bc3db8a839cfbd` adds one
compact `Próxima ejecución` control to the web conversation composer. It
shows the allowlisted effective model, reasoning effort, installed Codex
version and independent model/effort sources before submission. Selection is
limited to available catalog entries and the selected model's advertised
efforts; pending changes are explicit and block send until the existing
closed WorkSession settings API accepts them. A disabled-capability 404 leaves
the established composer behavior available for disable-first rollout.

The production TypeScript/Vite build passed. Synthetic authenticated
Playwright checks proved data resolution, visible DOM, ready/pending behavior,
the exact settings transition and zero horizontal overflow. Final screenshots
at `1440x900` and `390x844` were inspected for hierarchy, clarity,
consistency, responsiveness, clipping and overlap. Chromium and the temporary
preview were closed. Nothing was deployed or restarted.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.1-web-execution-profile`;
the SHA-256 of its `SHA256SUMS` is
`b926a4d3736458556539d5013f149eadc7aa53341a0dcd61abc8e2205f19fcd5`.

Task 4.2 is complete and change progress is `31/57`; the exact implementation
resume point is task 4.3. Task 4.3 and all later tasks remain pending.

Atenea commit `19d730d5f0262d1aa6e4b0dc7fa30d9f390087ef` adds one
current-run card before secondary conversation content. It reads the closed
run-detail and progress replay APIs and shows current state, elapsed time,
immutable effective profile/version, latest fixed progress message and fixed
next-action guidance. Active reads refresh every three seconds without
creating or mutating an execution. The visual timeline retains only the six
newest normalized events and is locally bounded on mobile.

The production TypeScript/Vite build passed. Synthetic authenticated
Playwright checks proved `CHECKING`, `1 min 24 s`, effective profile, latest
event, `WAIT` guidance and the supplied five-event timeline in the visible
DOM. Final `1440x900` and `390x844` screenshots were inspected; critical state
remains visible without page scrolling and there is no horizontal overflow,
overlap or unreadable wrapping. All temporary browser/preview processes were
closed; nothing was deployed or restarted.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.2-web-progress-card`;
the SHA-256 of its `SHA256SUMS` is
`2cf3faa8e40d4e4344f94058b3a608e005b36bfc9d44c9f03733c564aa2a387f`.

Task 4.3 is complete and change progress is `32/57`; the exact implementation
resume point is task 4.4. Task 4.4 and all later tasks remain pending.

Atenea commit `91a3b09aa2fa7e54c0a330dfa601b25332117da0` adds exactly
one applicable routine recovery action to the owning run card: cancel while
active, retry after a retryable failure, or request reconciliation for an
uncertain state. Requests contain only the run path identity, WorkSession ID,
closed action enum and fresh idempotency key; backend authorization remains
authoritative. Active execution disables conversation submission. Accepted,
role-denied, missing-run, changed-state and generic failures all provide an
actionable next step in the same card.

The production build passed. Synthetic Playwright interaction proved all
three mappings, exact request shape, active-send denial, accepted feedback and
the authorized-operator message for a 403. Desktop cancel/permission states
and mobile reconciliation were inspected with no overflow or overlap. No real
recovery operation was requested and nothing was deployed or restarted.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.3-web-recovery-actions`;
the SHA-256 of its `SHA256SUMS` is
`c5f48b42ce75ed9ce979747f7480a78b31aa8ebf6f05db4854a8ae7300148acc`.

Task 4.4 is complete and change progress is `33/57`; the exact implementation
resume point is task 4.5. Task 4.5 and all later tasks remain pending.

Atenea commits `41bd2e8e746642e73ba51c458a2e1013b48a6f5b` and
`7420762b7f1eca4eac2502ebd6a5661b5a321b3c` give Android the same closed
catalog, independent effective settings, run detail, progress replay and
contextual recovery behavior as web. Active runs poll every three seconds.
Each run retains its last observed sequence while the conversation remains
alive; foreground resume reloads the conversation/profile projections and
requests only the durable gap. Sequence-keyed merge rejects duplicates,
honours the retained floor, keeps at most 200 events and resets on a new run.

Six focused tests passed with zero failures, errors or skips, and the normal
debug APK assembled successfully. A temporary API 35 emulator rendered the
real Compose controls at `390x844`: current state, elapsed time, immutable
profile/version, latest event, next action and future-run profile were visible
in the first viewport, the composer was disabled and the sole reconciliation
action produced visible feedback. The first inspection exposed inherited
system-bar overlap; safe insets were added and the repeated DOM/visual check
proved no overlap, clipping or horizontal overflow.

The visual-only activity, AVD and downloaded system image were removed, and
the final normal APK excludes that activity. The complete Android unit/lint
commands still expose one voice-intent failure and two lint errors outside the
task paths; all reproduce unchanged at parent commit
`91a3b09aa2fa7e54c0a330dfa601b25332117da0`, so they remain explicit baseline
debt rather than being suppressed or mixed into 4.4. No deployment, real
recovery request, worker mutation or restart occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.4-android-session-operations`;
the SHA-256 of its `SHA256SUMS` is
`bb3e1acd203ffcb1bf3b000c3d16a71bac3398dea0fd21956f4b9376599f72f5`.

Task 4.5 is complete and change progress is `34/57`; the exact implementation
resume point is task 4.6. Task 4.6 and all later tasks remain pending.

Atenea commit `eb90cb6ad361ff9a8a70bca208ee921192cc9ac6` resolves the
effective model and effort immediately before each new remote AgentRun is
saved for dispatch, using the selected worker's current catalog and independent
WorkSession/project/worker-default precedence. The complete immutable model,
effort, sources, catalog revision and Codex version remain on the AgentRun;
later settings changes do not update earlier rows. Conversation history now
projects that snapshot onto both the visible originating turn and result turn,
while legacy turns without a profile retain the existing null-compatible API.

Web and Android render the run-owned `model · effort · Codex version` alongside
historical content. A transactional PostgreSQL test changed a synthetic
WorkSession from `medium` to `high`, proved the earlier run remained `medium`
with `PROJECT` provenance, and proved only the later run became `high` with
`WORK_SESSION` provenance. Fourteen focused backend tests and six focused
Android operations tests passed; the TypeScript/Vite production build and the
normal debug APK also assembled successfully.

Synthetic Playwright checks asserted both immutable labels and zero horizontal
overflow at `1440x900` and `390x844`. A temporary API 35 emulator rendered the
real Compose conversation and its UI hierarchy exposed both labels without
clipping or system-bar overlap. The visual activity, AVD, emulator, Vite,
Playwright and local test containers were removed. The known unrelated Android
voice-intent baseline failure remains documented from task 4.4 and was not
suppressed or mixed into this change.

Read-only post-checks found Atenea health `UP`, production/preview/Beautips
containers `Up`, the canonical AX42 worker unit active with `NRestarts=0`, all
four slot proxies active, zero project runners and zero rootful containers. No
deployment, real WorkSession mutation, routing change, recovery action, worker
restart or production data access occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.5-future-profile-history`;
the SHA-256 of its `SHA256SUMS` is
`97aceea799d9dbc9ade285225c074907fdaa5834ab2ca992aceccaeb80de325b`.

Task 4.6 is complete, Phase 4 is closed and change progress is `35/57`; the
exact implementation resume point is task 5.1. Task 5.1 and all later tasks
remain pending.

One secret-free synthetic matrix drove the existing Atenea commit
`eb90cb6ad361ff9a8a70bca208ee921192cc9ac6` through `FAILED` with `RETRY`,
`RECONCILING` with `REQUEST_RECONCILIATION`, and terminal `COMPLETED` with no
next action. It used deliberately long immutable WorkSession and canonical
model identifiers, fixed safe progress messages and the exact effective
profile/version projection.

Six isolated Playwright contexts proved the data-to-DOM mapping and inspected
screen at both required web viewports. Every state, sole next action, latest
event and long profile identity was visible, and both document and body widths
remained within their viewport. The current state and action remained above
the fixed composer at `390x844`; no horizontal overflow, overlap or unreadable
identifier was observed.

Three API 35 emulator launches then rendered the same matrix through the real
Compose `CodexRunProgressCard`, conversation and future-profile strip. The
UIAutomator hierarchy contained each exact state/profile/action mapping and
the inspected screenshots kept the operational decision in the first viewport
without clipping or system-bar intrusion. Failure exposed only retry,
reconciliation exposed only request-reconciliation with submission disabled,
and terminal success exposed continuation without a competing recovery action.

The temporary route mocks, Vite, Playwright, visual activity, emulator, AVD,
system image and Android home were removed. A final normal APK build passed and
the Atenea tree remained clean at the same commit, so no task 4.6 code commit
was necessary. Read-only post-checks kept Atenea `UP`, production, preview and
Beautips `Up`, the canonical worker active with `NRestarts=0`, four active slot
proxies and zero project runners. Nothing was deployed, restarted or routed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-4.6-visual-state-matrix`;
the SHA-256 of its `SHA256SUMS` is
`9061e47417e1d20341382d2af7f7e5c9f343ae86b611a830e9bbb4162fcd79cc`.

Task 5.1 is complete and change progress is `36/57`; the exact implementation
resume point is task 5.2. Task 5.2 and all later tasks remain pending.

Atenea commit `cec314dcee8a4b54f6e73fbb3daa6353b80a1d79` introduces the
generic delivery boundary behind the existing FCM sender. With the outbox gate
off, the established run-completed path and historical push log are unchanged.
With the gate on, the same local completion producer instead records one V60
`RUN_COMPLETED` event and its preference-aware deliveries in the owning
transaction; it performs no legacy send and creates no legacy log row.

A scheduled dispatcher remains inert unless both the independent outbox gate
and FCM configuration are ready. It selects bounded pending IDs, locks and
claims each exact delivery in a short transaction, then performs provider I/O
outside that transaction and persists `DELIVERED` or a closed failure state.
Payload construction derives only category, immutable event/template/deep-link
kind and numeric WorkSession/AgentRun identity from the persisted event. No
prompt, answer, worker detail or token enters event data or logs.

The initial generic schema normatively owns only AgentRun completion, failure
and action-required categories. Existing PR-merged, billing-ready and
close-blocked sends therefore remain on their established compatibility path
instead of receiving invented AgentRun ownership. Task 5.2 will connect every
local and remote terminal/action-required transition to the generic producer.

Twenty-eight focused unit and PostgreSQL persistence tests passed with zero
failures, errors or skips after all 60 migrations were validated. They proved
gate-off rollback compatibility, gate-on no-double-send cutover, idempotent
event/device ownership, exact delivery claim/terminal transitions and absence
of synthetic conversation content. FCM was mocked; no real device or provider
request was used. The local test container was removed and nothing was
deployed, enabled, routed or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.1-generic-notification-outbox`;
the SHA-256 of its `SHA256SUMS` is
`2e821ec0f51c79d5fec0b3b369556438bf1b214d3791fab965a78aa251b7cea6`.

Task 5.2 is complete and change progress is `37/57`; the exact implementation
resume point is task 5.3. Task 5.3 and all later tasks remain pending.

Atenea commit `9aa85cb39578d1a71abee336fa32434db5777cff` connects the
three generic AgentRun categories to their owning state transitions. Local
success and failure, conditional failure and local startup/stale
reconciliation now write their event within the service transaction. Remote
success, failure, malformed-success failure and bounded reconciliation-timeout
failure write the matching event within the coordinator's `REQUIRES_NEW`
terminal transaction.

The first persisted remote unavailable state also records
`REQUEST_RECONCILIATION` and `ACTION_REQUIRED` together. Repeated polling of
that unchanged actionable state does not call the producer again. Existing
terminal guards and immutable outbox category/run/revision ownership retain
one terminal outcome, result turn and applicable event on replay. Cancellation
and intermediate progress remain outside the initial push categories.

Seventy-six focused unit and PostgreSQL persistence tests passed with zero
failures, errors or skips after all 60 migrations were validated. They cover
local and remote success/failure, local reconciliation, first actionable
remote reconciliation, terminal replay, outbox persistence and dispatcher
regressions. FCM remained mocked and the gate remains default-off. The
temporary database and App Server containers were removed; the reusable test
volume was retained. Nothing was deployed, enabled, routed or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.2-terminal-notification-transitions`;
the SHA-256 of its `SHA256SUMS` is
`3e184038abb66229278092c45ffde357d64a8b49483ccc6264b8328e4e888509`.

Task 5.3 is complete and change progress is `38/57`; the exact implementation
resume point is task 5.4. Task 5.4 and all later tasks remain pending.

Atenea commit `1d30e8d239156aa3bb1664b3e8f50b42c604b463` completes the
V60 delivery lifecycle. Pending and due retry rows are selected in bounded
batches, claimed under their exact row lock and retried after fixed exponential
delays of 30, 60, 120 and 240 seconds. A fifth transient failure closes as
`FAILED`; a row whose next attempt reaches its 24-hour lifetime closes as
`EXPIRED` without provider I/O.

FCM response handling now maps only closed provider/authentication/transport
classes into fixed diagnostic codes. Provider bodies are discarded. An exact
invalid-token result closes only that delivery as `INVALID_TOKEN` and
deactivates only its owning device, leaving other devices and their deliveries
unchanged. Transient provider and authentication failures remain retryable;
credential or other closed client rejections fail permanently.

The authenticated per-device/category preference API retains all-three-on
defaults and foreign-device rejection. Persistence validation additionally
proved that an explicit override remains attached to the same device identity
through re-registration and application-version update.

Thirty-two focused unit, API and PostgreSQL persistence tests passed with zero
failures, errors or skips after all 60 migrations were validated. No provider
response content or token entered a diagnostic or log, FCM remained synthetic,
and the notification gate remains default-off. The temporary database
container was removed and its reusable volume retained. Nothing was deployed,
enabled, routed or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.3-delivery-policy`;
the SHA-256 of its `SHA256SUMS` is
`38b0b2203a90fd7a5d3eaad5f784231693ecfb92c48a90bbc49003bd935df33a`.

Task 5.4 is complete and change progress is `39/57`; the exact implementation
resume point is task 5.5. Task 5.5 and all later tasks remain pending.

Atenea commit `a21d4f92644a2b12c8847f43b7a9e602c1e7376d` introduces an
explicit safe-copy catalog for `agent-run-safe-v1` and a closed payload factory
for `atenea-notification-data-v1`. Every generic AgentRun notification now
contains the fixed event type `AGENT_RUN_STATE`, category/template/event
identity, numeric WorkSession/AgentRun ownership and the exact deep link
`atenea://work-sessions/{sessionId}/conversation`.

The payload key set is fixed to ten safe fields, retaining `type` only as the
existing category compatibility alias. Unknown template versions, altered
safe copy, altered deep-link kind and inconsistent run/session ownership fail
closed before provider I/O. Prompt, answer, secret and worker-internal content
are neither accepted nor derived.

Twenty-seven focused unit and PostgreSQL persistence tests passed with zero
failures, errors or skips after all 60 migrations were validated. FCM remained
synthetic, the gate remains default-off and the temporary database container
was removed while retaining its reusable volume. Nothing was deployed,
enabled, routed or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.4-safe-deep-link-payloads`;
the SHA-256 of its `SHA256SUMS` is
`f14ae0a9308ef750c204d4aaaf0e7ffbb7b6fd6515bd55637fa4f1ec3de93af3`.

Task 5.5 is complete and change progress is `40/57`; the exact implementation
resume point is task 5.6. Task 5.6 and all later tasks remain pending.

Atenea commit `8a8229348677783287de04bb979b92079fe3ce13` gives Android a
closed notification route parser for the versioned ten-field payload and the
exact `atenea://work-sessions/{id}/conversation` URI. Schema, category,
template, run, session and UUID event ownership must all agree. Unknown,
mismatched, queried, fragmented or non-positive routes fail closed.

The production notification presenter now uses the immutable event UUID as
its stable Android notification/PendingIntent identity and copies only the ten
allow-listed safe fields. MainActivity accepts both platform notification
extras and direct browsable deep links, retains the route through login, and
opens the exact conversation without requiring an invented project identity.
A fresh event recreates that conversation projection so its committed state is
reloaded. While MainActivity is foregrounded, the FCM service delivers the
route in-app and returns before local notification presentation.

Four focused JVM tests passed with zero failures, errors or skips. The final
normal debug APK assembled successfully. A temporary API 35 emulator displayed
the real production notification presenter in the background; its inspected
notification was concise and actionable. Tapping its real PendingIntent opened
only synthetic WorkSession `12`, confirmed by the UIAutomator hierarchy and an
inspected Compose screenshot with no clipping, overlap or horizontal overflow.

The visual-only activity, cleartext test manifest, mock API/authentication,
emulator, AVD and downloaded system image were removed before the final normal
build. No FCM token value was read or retained. Read-only post-checks kept
Atenea `UP`, production/preview/Beautips containers `Up`, the AX42 AgentRun
worker active with `NRestarts=0`, four active slot proxies, zero project runners
and rootful Docker inactive. Nothing was deployed, enabled, routed or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.5-android-notification-routing`;
the SHA-256 of its `SHA256SUMS` is
`1e5c8e87a63955b917df90ee570ab213ba6b879a951cdde86f94fd828865dd3d`.

Task 5.6 is complete and change progress is `41/57`; the exact implementation
resume point is task 5.7. Task 5.7 and all later tasks remain pending.

Atenea commit `4c32f4ab38bbd9337c5304c88d57e4914b2c6a15` closes the
provider-presentation half of durable ownership. Generic FCM Android payloads
now use the immutable notification-event UUID as their platform replacement
tag. A repeated provider delivery therefore targets the same visible Android
notification. Legacy events without a generic event identity retain their
existing untagged payload instead of receiving invented ownership.

One PostgreSQL test creates two device/channel owners for one event, makes one
provider attempt retryable while the other succeeds, reconstructs both outbox
and claim services, repeats event production, and then completes only the due
failed row. The event UUID and both delivery IDs remain unchanged, the already
delivered row cannot be reclaimed, the final event still owns exactly two rows
and no row remains dispatchable. A dispatcher test independently proves that
one device failure does not block the second device in the same batch.

The focused FCM sender, dispatcher and persistence set ran twice in disposable
test processes: each run passed 21 tests with zero failures, errors or skips
after validating all 60 migrations. FCM and device values remained synthetic;
no provider request or real token was used. Exact test containers were removed
and the reusable database/Maven volumes retained.

Read-only post-checks kept Atenea `UP`, production/preview/Beautips containers
`Up`, the AX42 AgentRun worker active with `NRestarts=0`, four active slot
proxies and zero project runners. Nothing was deployed, enabled, routed,
restarted in production or sent.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.6-durable-notification-ownership`;
the SHA-256 of its `SHA256SUMS` is
`d295390a8e6dacc716b35fd96ac9f89c47ff0e71b9e7eb6472275b35c708a6ef`.

Task 5.7 is complete, Phase 5 is closed and change progress is `42/57`; the
exact implementation resume point is task 6.1. Task 6.1 and all later tasks
remain pending.

One active real Android device running Atenea `0.5.96` (`versionCode 129`) was
validated separately with the exact WorkSession 7 conversation foregrounded,
with Atenea backgrounded, and with Atenea removed from recents without Android
force-stop. Three versioned `agent-run-safe-v1` presentation messages used
fresh immutable event UUIDs and the exact
`atenea://work-sessions/7/conversation` route.

FCM accepted each message once with HTTP 200. In foreground the valid event
was consumed inside the visible conversation and no Android system
notification appeared. In background and closed states Android displayed one
concise notification; tapping it respectively resumed or launched Atenea in
the exact current conversation. The operator confirmed each observed result
before the next state was exercised.

The sole matching token was selected inside a bounded remote shell and piped
directly to a short-lived sender through standard input. It was never printed,
written to evidence or retained. OAuth, provider and signing operations had
finite timeouts, provider bodies were discarded, and the sender exposed only
safe event/session/run receipt metadata. Temporary host and container copies
were removed after the exercise.

The presentation-only run numbers were not persisted. Production remains at
Flyway V56 and therefore has no V60 generic notification tables; no AgentRun,
WorkSession, device preference, routing or notification gate changed. Atenea
health remained `UP`, production, preview and Beautips containers remained
`Up`, the AX42 AgentRun worker remained active with `NRestarts=0`, all four
slot proxies remained active and project runners remained zero. No backend was
deployed or restarted.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-5.7-real-android-device`;
the SHA-256 of its `SHA256SUMS` is
`a3ba8662e4b93d5b9891cf2b9199c897d5a576d044a063ed4c7171fb716a1b29`.

Task 6.1 is complete and change progress is `43/57`; the exact implementation
resume point is task 6.2. Task 6.2 and all later tasks remain pending.

Atenea commit `c17af98eef607df80909206226480df37ea6e011` adds the
additive V61 managed Codex inventory and update-plan persistence plus three
closed APIs. An authenticated routine operator can inspect installed, current
and previous releases and their compatibility state. Only a current platform
administrator, behind the independent default-false `managed-updates` gate,
can create or read an update plan.

The plan request accepts only the fixed operation, exact worker identity and
idempotency key. Candidate selection is derived from persisted inventory. The
immutable projection records exact release identities and digests, the fixed
`WORKER_HEALTH`, `CURRENT_LINK`, `CATALOG_ALIGNMENT` and
`CANDIDATE_COMPATIBILITY` gates, and a fixed no-side-effect impact statement.
Repetition returns the same plan; a missing candidate fails closed and an
incompatible candidate remains visible while blocking the plan. No caller
version, URL, host, endpoint, service, command or path authority is accepted.

The focused migration, API, authorization, idempotency, compatibility and
historical-profile set passed 13 tests with zero failures, errors or skips
after all 61 migrations were validated. V61 was also applied from an empty
test schema, repeated against the migrated schema, and the backend package
build completed successfully. Disposable test containers and their network
were removed while reusable volumes were retained.

Nothing was deployed, enabled, installed, relinked, routed or restarted.
Atenea remained `UP`; production, preview and Beautips containers remained
`Up`; the AX42 AgentRun worker remained active with `NRestarts=0`, all four
rootless daemons and socket proxies remained active, project runners remained
zero, rootful Docker remained inactive, SSH and Tailscale remained active and
all three RAID arrays remained `[UU]`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.1-managed-update-inventory`;
the SHA-256 of its `SHA256SUMS` is
`0dfbd1ee14759a29b8c89985745cec33ec6be21b57cf89b2e5bd857706e3cb1b`.

Task 6.2 is complete and change progress is `44/57`; the exact implementation
resume point is task 6.3. Task 6.3 and all later tasks remain pending.

Atenea commit `8e05276bb0b3c183fdb350e085fbaadae85fc451` adds the
administrator-only persisted stage operation and its closed worker call.
Stage creation remains behind the independent default-false managed-updates
gate, requires the exact READY plan and compatible persisted candidate, and
accepts only operation, plan, candidate and idempotency identities. A repeated
request returns the same immutable result; blocked plans fail before worker
I/O and a conflicting worker result rolls back persistence.

Worker/contract commit `a61f190a5d6685d0d001ed03753b7e47dacaf16c`
adds the closed staging mediator, versioned result schema and conditional
worker capability. Archive location, Codex version, digest, catalog revision
and release roots come only from fixed service arguments and a root-owned
registry. The mediator verifies ownership, mode, SHA-256 and bounded safe tar
members, invokes only the candidate's fixed schema generator, requires exact
version-matched App Server and CLI schemas, writes immutable manifests and
proves the current and previous link fingerprints did not change.

The backend focused suite passed 30 tests with zero failures, errors or skips
after validating all 61 migrations, and its clean web/Java package build
succeeded. The combined worker and contract suite passed twice at 49 tests per
run, and the retained-draft installer suite passed twice. Negative fixtures
proved rejection of extra caller authority, invalid digest, traversal,
schema-version mismatch, unavailable mediator/registry and conflicting
persisted identities.

Nothing was deployed, installed, enabled, staged on AX42, relinked, restarted
or routed. Atenea production, preview and Beautips remained `UP`; the AX42
worker remained active with `NRestarts=0`; SSH, Tailscale, four rootless Docker
daemons and all three `[UU]` RAID arrays remained healthy; rootful Docker
remained inactive. Existing Beautips and foreign WorkSession containers were
observed before and after and were not modified.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.2-closed-codex-staging`;
the SHA-256 of its `SHA256SUMS` is
`82c009c426233e76808edb146d59fb73f463d96cbacac74925f182fe550847ea`.

Task 6.3 is complete and change progress is `45/57`; the exact implementation
resume point is task 6.4. Task 6.4 and all later tasks remain pending.

Atenea commit `60a47757959d1d794c48ebcaf8c1c9e5d1ba3c89` adds the
separate ten-minute single-use activation authorization, immutable activation
record, closed administrator APIs and fixed worker call. Authorization is
bound to the requesting administrator, worker, plan, current and candidate
inventory/version identities and release digest. A worker-scoped database row
lock serializes activation with creation of new remote AgentRuns; authorization
is re-read after acquiring it and every non-terminal run state blocks worker
I/O.

Worker/contract commit `1eea10192c523ca8307e3a3a3d9ed724893c7776`
adds the conditional activation capability, closed result schema and root
mediator. The worker independently requires zero non-terminal executions and
blocks new dispatch for the bounded operation. The mediator accepts no caller
host, service, command, path, version or release authority; it requires exactly
one accepted stage record, validates both version-matched schemas, runs only
the fixed focused-contract, health and single-canary executables, atomically
advances the exact links and restores both original targets when health or the
canary fails.

Two backend passes from independently empty PostgreSQL databases each passed
45 tests with zero failures, errors or skips after validating all 61
migrations. A final seven-test activation recheck passed after the serialization
review, and the clean web/Java package build succeeded. The combined
worker/contract activation suite passed twice at 52 tests per run plus the
installer assertion. Repetition returned one immutable result without rerunning
gates; active runs, extra authority, ambiguous stage records, conflicting
results and failed health/canary fixtures failed closed, with exact link
restoration proved for post-switch failures.

Nothing was deployed, installed, enabled or activated on AX42, relinked,
restarted or routed. Atenea production, preview and Beautips remained `UP`; the
AX42 worker remained active with `NRestarts=0`; SSH, Tailscale, four rootless
slot proxies and all three `[UU]` RAID arrays remained healthy; rootful Docker
remained inactive. Existing Beautips and foreign WorkSession containers were
observed and not modified.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.3-gated-codex-activation`;
the SHA-256 of its `SHA256SUMS` is
`9b7d13aebf5c392e1b2de88c3b2a885add4140db8f09af45607e2c1e20a06b6a`.

Task 6.4 is complete and change progress is `46/57`; the exact implementation
resume point is task 6.5. Task 6.5 and all later tasks remain pending.

Atenea commit `6b67fdb8d70d7b8550b566021f8a018d863f1ae6` adds a
separate ten-minute single-use rollback authorization, immutable rollback
operation, closed administrator APIs and exact worker call. Authorization is
bound to the requesting administrator, worker, plan, accepted activation and
the persisted current/previous inventory identities. The same worker-scoped
database barrier used by activation serializes rollback with new remote
AgentRuns, authorization is re-read under that lock and every non-terminal run
blocks worker I/O.

Worker/contract commit `40e4cd99d282cf006c7cd3ccb5532df5db94a4cb`
adds the conditional rollback capability, closed result schema, exact link
restoration and a fixed restart scheduler. The worker independently requires
zero non-terminal executions and blocks dispatch for the bounded operation.
The mediator accepts no caller host, service, command, path or release
authority, requires exactly one accepted activation and exact matching link
fingerprints, swaps only `current` and `previous`, and records a durable
`LINKS_RESTORED/PENDING` transition before scheduling the restart. An
interrupted retry therefore resumes only that schedule; an accepted repetition
returns the immutable result without swapping or scheduling again.

AX42 has one global affected Codex boundary,
`atenea-agent-run-worker-v1.service`; project App Servers belong to individual
WorkSessions and are not restarted. Both database constraints and the worker
result require that exact service and record zero App Server services
restarted.

Two backend acceptance passes from independently empty PostgreSQL databases
each passed 46 tests with zero failures, errors or skips after validating all
61 migrations, and the clean web/Java package build succeeded. The combined
worker rollback, dispatch, contract and installer set passed twice at 58 tests
per run plus the installer assertion. Negative cases proved routine-role,
extra-field, active-run, link-drift, ambiguous activation, foreign-service,
malformed-identity and scheduler-interruption rejection.

Nothing was deployed, installed, enabled, activated or rolled back on AX42;
no real link changed and no real service restarted. Atenea production, preview
and Beautips remained `UP`; the AX42 worker remained active with
`NRestarts=0`; SSH and Tailscale remained active, rootful Docker remained
inactive and all three RAID arrays remained `[UU]`. No routing, project runtime
or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.4-exact-codex-rollback`;
the SHA-256 of its `SHA256SUMS` is
`58721aeac9eb50783ad48050612b61464a03411a9a5abc9867560d4a218d8d3b`.

Task 6.5 is complete and change progress is `47/57`; the exact implementation
resume point is task 6.6. Task 6.6 and all later tasks remain pending.

Atenea commit `a8b7f9256d2036cb5c7414657585b852e52d783f` adds a
state-first “Versiones Codex” web surface. The first viewport shows the exact
current and previous versions, whether managed updates are enabled, the
current workflow state and one next action. Plan, stage, activation
authorization, activation, rollback authorization and rollback remain
separate explicit actions; request bodies are built only from immutable
identities returned by the preceding operation.

The authenticated operator profile now projects its closed Codex-operations
role. Known routine and privileged operators do not receive the platform
administration navigation. Backend authorization remains authoritative:
direct routine access fails with HTTP 403 and the screen presents an
actionable restricted-access message rather than exposing data or controls.
Legacy stored web sessions without the new role field retain navigation until
their next refresh/login, but the backend still denies them unless the current
database role is `PLATFORM_ADMINISTRATOR`.

The surface presents fixed impact guarantees beside the workflow: zero active
executions are required, only the Codex worker boundary is affected, both
sensitive transitions use separate ten-minute single-use authorizations and
no URL, command, path or credential authority is displayed. A completed
rollback explicitly reports zero restarted App Servers.

The web bundle built repeatedly at 1,583 modules and the clean Java package
build succeeded. Two focused runs from independently empty PostgreSQL 16
schemas each passed 18 authentication, role, update-API and rollback tests
with zero failures, errors or skips after all 61 migrations. A synthetic
Playwright flow exercised every action through rollback at `1440x900` and
`390x844`, asserted critical DOM states, verified routine-role denial and
proved no horizontal overflow. Inspected screenshots showed clear hierarchy,
wrapped guarantee copy and no clipping or overlap.

Nothing was deployed, enabled, installed, activated, rolled back, restarted
or routed. Atenea production, preview and Beautips remained `UP`; the AX42
worker remained active with `NRestarts=0`, and all three RAID arrays remained
`[UU]`.

Sanitized evidence, including the four inspected screenshots, is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.5-administrator-codex-surface`;
the SHA-256 of its `SHA256SUMS` is
`3d993e2dc1fca04974bc507f2cb5d4c6343c0b756d13df3816bec4f4b4760152`.

Task 6.6 is complete and change progress is `48/57`; the exact implementation
resume point is task 6.7. Task 6.7 and all later tasks remain pending.

No source change was necessary. The closed contracts accepted in tasks
6.1–6.5 were exercised as one negative matrix against backend commit
`a8b7f9256d2036cb5c7414657585b852e52d783f` and worker source commit
`453e01db2f71077282dcab2e382ebde88957daf5`.

An incompatible persisted candidate remained visible but produced a blocked
plan without worker I/O. A candidate that generated schemas for a foreign
Codex version was rejected and its temporary release removed. Non-terminal
AgentRuns blocked both activation and rollback before worker I/O. Failed fixed
health and canary gates restored both exact links and created no accepted
activation. Caller-supplied service fields and direct foreign-service restart
requests were rejected without a restart.

Exact repetition returned the same immutable stage, activation or rollback
result without rerunning gates, swapping links or scheduling another restart.
Reusing the same idempotency identity with a different authorization or
request fingerprint failed closed with no additional action. Ambiguous stage
records and rollback link drift were also rejected without changing the
observed state.

Two backend passes from independently empty PostgreSQL 16 schemas each passed
the seven-test managed-update integration class after all 61 migrations. The
combined worker staging, activation/rollback and boundary set passed twice at
58 tests per pass. All releases, registries and active-run fixtures were
synthetic; temporary stacks were stopped afterward.

No real AX42 link, service, release or operation changed. Atenea production,
preview and Beautips remained `UP`; the AX42 worker remained active with
`NRestarts=0`, all three RAID arrays remained `[UU]`, and both canonical
worktrees remained clean.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.6-managed-update-rejections`;
the SHA-256 of its `SHA256SUMS` is
`c857ecb9dc26e45d102f53ca497b2df3151b736c07bef12edcbabefec5412316`.

Task 6.7 is complete, Phase 6 is closed and change progress is `49/57`; the
exact implementation resume point is task 7.1. Task 7.1 and all later tasks
remain pending.

Task 6.7 used its explicitly permitted fully accepted synthetic branch. No
instruction separately and specifically authorized a named real AX42 Codex
release update for this task; general implementation authority and the prior
application rollout authorization were not treated as that distinct release
authority.

The accepted proof chain comprises the closed staged installer from 6.2, the
separately authorized activation and exact automatic restoration from 6.3,
the separately authorized operator rollback from 6.4, the administrator web
surface from 6.5 and the complete negative matrix from 6.6. Together they
prove successful, repeated, interrupted and rejected update/rollback paths
without needing to modify the real worker.

A final read-only AX42 baseline found Codex CLI `0.145.0`, the worker active
with `NRestarts=0`, zero non-terminal Codex processes and zero managed-update
transient units. As expected before deployment, the root-owned release
registry, managed release root, stage/activation mediators and restart
scheduler are absent. This absence is retained rather than reconstructed.

No release was staged, activated or rolled back, no worker restarted and no
production route changed. Atenea production, preview and Beautips remained
`UP`; all three RAID arrays remained `[UU]`; both canonical worktrees remained
clean.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-6.7-synthetic-update-closure`;
the SHA-256 of its `SHA256SUMS` is
`306cdfb0371389dac52aa491026970bb2be9324eaa58af9587142540a8536104`.

Task 7.1 is complete and change progress is `50/57`; the exact implementation
resume point is task 7.2. Task 7.2 and all later tasks remain pending.

The first full discovery pass exposed two validation regressions before the
accepted runs. The mobile-auth integration test assumed its annotation's
display name even though the canonical Compose environment deliberately
overrides that value. The Android voice interpreter also evaluated the
generic latest-response command before the more specific Codex status intent.
A minimal Atenea fix now asserts a non-empty persisted display name and orders
the specific status question first. Focused tests passed before the complete
runs; canonical Atenea commit
`e60aa025d260e2a6bc1fbbfccde11009a7131c00` is clean and synchronized.

Two backend passes from independently copied clean trees and independently
empty PostgreSQL 16 volumes each applied all 61 migrations and passed 513
tests with zero failures, errors or skips. The web bundle built twice at 1,583
modules. Two clean Android copies each passed 74 tests and executed 228 Gradle
tasks; both produced byte-identical debug APKs with SHA-256
`e8455b2c893b22394f4b1ffdab79686d12a9e3347f3d9dad29c20a2707aaa8e9`.
All 31 worker test entry points passed twice, including the bounded synthetic
Playwright, ownership, runtime, admission, cleanup, backup, update and worker
protocol contracts.

All task-owned Compose containers, networks, volumes and image tags were
removed after exact label inspection. The temporary browser wrapper was
deleted and no task Playwright/Chromium process remained. No deployment,
routing change, runtime start or service restart occurred.

Final postchecks found production, preview and Beautips `UP`; the canonical
AX42 worker remained active with `NRestarts=0`, the same executable SHA and
boot ID; all four rootless Docker daemons were active and all three RAID
arrays remained `[UU]`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.1-complete-suites`;
the SHA-256 of its `SHA256SUMS` is
`03c82bf67c242ba55c3706c98cfc116350dd8a06d8a4006a129e95a59e7bbcab`.

Task 7.2 is complete and change progress is `51/57`; the exact implementation
resume point is task 7.3. Task 7.3 and all later tasks remain pending.

Immediately before the first production migration, the production authority
created PostgreSQL 16 custom-format backup
`atenea_prod_before_codex_operations_v56_20260731T235659Z.dump`. It is mode
`0600`, 1,636,785 bytes and has SHA-256
`0ba0549abcc91ba562a13468a84387e22976a0b8c7a6f7d865d98f4a9e82b48e`.
An internal-only disposable PostgreSQL 16 restore reproduced V56, all 34
tables and the source table-count digest. The candidate applied V57–V61 once,
then reported a no-op second pass with 61 Flyway rows.

The exact former production image
`sha256:7b62d5459831ede557e6277e6252a891e79230e2b52ce57d4ac9277c0928e36d`
started `UP` against the migrated fixture and left V61 unchanged. It remains
retained as `atenea-rollback-codex-operations-v56:7b62d545`. The production
backend then deployed successfully from commit
`e60aa025d260e2a6bc1fbbfccde11009a7131c00`; health is `UP`, restart count is
zero and production is at V61. All five new gates remain absent/default-false
and every new profile, progress, recovery, notification and managed-update
table remains empty.

The dual-compatible worker was installed from accepted worker source
`453e01db2f71077282dcab2e382ebde88957daf5`. Its existing project
configuration SHA-256
`02338c48c6414ded537059bd590ee1319f9e6338d7ad5616223a6b06c86d265a`
and token identity were retained exactly. The single intentional worker
restart returned active with `NRestarts=0`; no release registry or release
file was created. The retained WorkSession, registration, clean worktree HEAD
and execution ownership did not change.

Because code 129 was already published, Android received the new immutable
identity `0.5.97 (130)` in packaging commit
`51051495a023fb9ab8b755077f11e04a6409a7cc`. Two clean secret-free builds
each passed 74 tests and 228 Gradle tasks with identical APKs. The configured
production build published SHA-256
`d9f2a3958d9d9ec137b08e78d4ba4139313edd903b51e1fdeb01fb62314e9ae9`
and retained code 129 as the previous release.

Production, preview and Beautips remained `UP`. All four rootless Docker
daemons remained active with accepted container counts `3/0/0/3`; rootful
Docker remained inactive/masked. External-backup timers remained
active/enabled with successful last results, SSH/Tailscale/firewall remained
healthy and all three RAID arrays remained `[UU]`. Exact labelled fixtures
and temporary worker source were removed; the protected backup, rollback
image and versioned APKs are intentionally retained.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.2-disabled-deployment`;
the SHA-256 of its `SHA256SUMS` is
`8b92d30315869ae8b4653d9aa35e72143d66c4ef397fc5c3fe3230e9b67cfed0`.

Task 7.3 is complete and change progress is `52/57`; the exact implementation
resume point is task 7.4. Task 7.4 and all later tasks remain pending.

One real Atenea WorkSession, remote UUID
`f8b7bd8d-5708-4c76-b206-e76d61fd8a89`, remained `OPEN` on AX42 with the
persisted default profile `gpt-5.6-sol` / `high`. Both accepted runs used
Codex `0.145.0`, catalog revision
`125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187`
and exact canonical, mirror and clean worktree commit
`3615d29b8ddf20830289051bb7539c223296fbf7`.

The initial accepted turn completed in 25.785 seconds with seven monotonic
safe events from `ACCEPTED` through `COMPLETED`. The user-submitted
continuation completed in 7.711 seconds with six safe events and the same
terminal projection. The control plane retained two dispatched runs with two
distinct execution identities and zero non-terminal runs. A worker-side
aggregate proved both results carried a thread identity, both used one
distinct thread and two distinct turns; no thread, turn, prompt, answer or
remote execution identifier was retained in programme evidence.

Two preceding attempts remain immutable fail-closed history and have no
remote execution identity. Investigation found that a previously closed
Atenea WorkSession still owned its released admission registration and active
allocation marker while owning zero containers. Its exact registration and
admission were released, and its byte-preserved allocation marker was retired
under D-048 after the sealed SHA-256
`c4425a8ca00247e97c33ca1718606c5c0d7310ee82cb57ee56b0c6ddac3da3f1`
and zero-resource state were verified. No foreign WorkSession or unrelated
slot was changed. D-050 permits retaining these pre-dispatch failures beside
the later successful terminal runs.

The exercise also exposed missing durable progress on closed reconciliation
paths. Atenea commits `4f81c0855d0966293faaa8e5e5660831b58dde8f` and
`3615d29b8ddf20830289051bb7539c223296fbf7` now append the applicable
`RECONCILING`, `FAILED` or `CANCELLED` events for command, timeout,
cancellation and startup reconciliation. Focused tests and the complete
backend suite passed, with 518 tests and zero failures, errors or skips, before
the final production deployment. The intentionally disabled recovery gate
continued to reject retry API calls; the accepted validation used a new turn
and did not enable task-7.4 recovery behavior early.

Final checks found production, preview and Beautips `UP`; canonical Atenea,
its upstream, the AX42 mirror and the WorkSession worktree are synchronized
and clean. The worker is active/running with `NRestarts=0`, all four rootless
slot proxies are active with container counts `3/0/0/3`, all RAID arrays are
`[UU]`, and SSH, Tailscale and the firewall are active. The accepted
WorkSession retains exact `slot2` and `heavy1` admission, while session-owned
processes, Playwright/Chromium processes and active worker executions are
zero. Production routing and unrelated resources did not change.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.3-atenea-profile-progress-continuation`;
the SHA-256 of its `SHA256SUMS` is
`270597dfaf55571e7cdc2bf766c3a0f99499b7172dfd5b17cbbe38375b7aef79`.

Task 7.4 is complete and change progress is `53/57`; the exact implementation
resume point is task 7.5. Task 7.5 and all later tasks remain pending.

The accepted exercise used only Atenea WorkSession
`2d98d762-7d9b-4cc1-948f-5e6353dc8b76`, profile `gpt-5.6-sol` / `high` and
canonical commit `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Canonical Atenea,
its upstream, the AX42 mirror and the clean WorkSession worktree were equal;
the control-plane tree was
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`.

One exact remote execution accepted one cancellation request and reached
`CANCELLED` after 191.710 seconds. The recovery operation reached `SUCCEEDED`
with closed outcome `CANCELLED`; AX42 retained one cancelled execution and
zero session processes. A second turn was persisted and the Android client
was then closed while the worker service was deliberately unavailable. The
run remained `RECONCILING` for the bounded policy and reached `FAILED` after
120.426 seconds with no remote execution identity and no replacement
dispatch.

The worker then returned active with its project configuration and allocation
hashes plus mirror and worktree commits unchanged. An exact recovery retry of
the pre-dispatch failure persisted one immutable `retryOfRunId` link, inherited
the same profile, completed its recovery operation as `RETRY_CREATED`, and
created one dispatch plus one remote execution. The backend was restarted
while that execution remained live; Spring returned in 14.140 seconds and
startup reconciliation retained the same execution. The retry reached
`SUCCEEDED` after 192.387 seconds without a second linked run, dispatch or
remote execution.

The aggregate is three control-plane runs, three distinct dispatches, two
remote executions and zero non-terminal runs: one cancelled, one deliberately
absent pre-dispatch failure and one successful linked retry. Worker state
contains exactly the cancelled and successful executions. No session,
Playwright or Chromium process remains. No remote execution, Codex thread,
turn, prompt, answer, token or credential identity was retained in programme
evidence.

The live exercise exposed two implementation defects before acceptance. The
first validation WorkSession observed the current control-plane commit while
AX42 still held the preceding mirror tip, so exact admission returned HTTP 403
before creating any workspace or remote execution. Worker commit `b30b14f`
implements D-090 and passed 49 tests. The second defect inserted a retry before
attaching its immutable lineage, causing Hibernate to reject the later update.
The exact queued orphan had no remote execution, was absent from worker state
and was terminalized only through D-091's complete predicates. Atenea commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` now inserts lineage and inherited
profile atomically. Focused tests and the complete clean-database backend
suite passed with 526 tests and zero failures, errors or skips.

The initial backend-restart harness reported its own timeout because it
searched for JSON quotes with literal backslashes. No second restart or
rebuild followed. Read-only container/log/worker inspection showed the
application had started normally; a corrected finite curl returned HTTP 200
and `UP`. The backend image remained unchanged across the restart and Docker
restart count remained zero.

Final checks found production `UP`, preview and Beautips containers `UP`, the
worker active with `NRestarts=0`, exact slot2/heavy1 admission retained and
zero session/browser processes. Production routing, Beautips routing,
unrelated WorkSessions and unrelated worker resources were unchanged.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.4-recovery-disconnect-restart`;
the SHA-256 of its `SHA256SUMS` is
`378021b3bb1bca888937502ef8b9b2573e00982ad07a87eb12efdf80eba69c4a`.

Task 7.5 is complete and change progress is `54/57`; the exact implementation
resume point is task 7.6. Task 7.6 and all later tasks remain pending.

The generic notification outbox was enabled from an empty V60 baseline by
changing only its production gate and recreating only the production backend.
The backend returned `UP` in 16.162 seconds. No historical event or delivery
was replayed, both active Android registrations remained on Atenea `0.5.97`
and their absent preference rows continued to mean that all three initial
categories were enabled.

AgentRun 89 completed in 5.960 seconds and transactionally persisted one
`RUN_COMPLETED` event. Each active Android device owned one delivery, accepted
once. The configured device displayed exactly one safe completion
notification; tapping it opened only WorkSession
`2d98d762-7d9b-4cc1-948f-5e6353dc8b76` and its exact conversation. A separate
backend restart returned `UP` in 16.001 seconds and left the event/delivery
fingerprint, counts and single-attempt ownership unchanged. No second visible
notification appeared.

With zero non-terminal runs, only the canonical AX42 AgentRun worker was then
stopped. AgentRun 90 entered `RECONCILING` without a remote execution and
persisted one `ACTION_REQUIRED` event. After the bounded window it reached
`FAILED` in 120.412 seconds and persisted one `RUN_FAILED` event. Each
category again owned exactly one delivered row per active device with one
attempt. The configured device displayed exactly one action-required and one
failure notification. Tapping the failure notification opened the same exact
conversation and exposed the failed execution.

The worker was restored active with `NRestarts=0`, and its program, project
configuration, admission record, mirror, clean worktree and Git commit were
retained. A second backend restart returned `UP` in 13.891 seconds and left
the combined action-required/failure fingerprint byte-stable, with zero
dispatchable rows and no duplicate visible notification. Neither new run
created a legacy push log.

Final checks found three immutable events, six delivered device rows, one
attempt per row, zero non-terminal AgentRuns and zero session, Playwright or
Chromium processes. Production, preview and Beautips remained available; all
four rootless Docker services remained active with container counts
`3/0/0/3`; SSH and Tailscale remained active and all RAID arrays remained
`[UU]`. Production routing, unrelated WorkSessions, slots and worker resources
did not change. No device identity, push token, provider body, credential,
prompt, answer, Codex thread/turn identity or remote execution identity was
retained.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.5-notification-dedup-deep-link`;
the SHA-256 of its `SHA256SUMS` is
`ee2f1f8b5b0409ba3184a897f9fc129520b2506c1c1c03e6eb1c0cca47a770aa`.

Task 7.6 is complete and change progress is `55/57`; the exact implementation
resume point is task 7.7. Tasks 7.7 and 7.8 remain pending.

The disable-first entry gate found production at V61 with zero non-terminal
AgentRuns. Exact fingerprints were fixed for the open WorkSession, five
profile-bearing AgentRuns, 24 safe progress events, two recovery operations,
two active Android devices, three generic notification events, six delivered
rows, legacy logs, Git and routing. The accepted current backend image was
`sha256:bb983725de00ca3cba29f45ffce34c071943d3a6dc25923cdcc4730b300a3a7f`;
the fixture-proven rollback image remained
`sha256:7b62d5459831ede557e6277e6252a891e79230e2b52ce57d4ac9277c0928e36d`.

Profiles, progress, recovery, generic notification dispatch and managed
updates were all disabled before changing an application image. The current
backend returned `UP` in 16.205 seconds with all five gates false. Every
persisted fingerprint remained unchanged and no delivery became dispatchable.

The exact rollback image then returned `UP` against production V61 in 13.998
seconds without a Flyway or schema error. An exact repeated rollback completed
as a 125 ms no-op: both container identity and start time remained unchanged.
The WorkSession, affinity, profile history, progress, recovery, devices,
preferences, notification ownership and Git fingerprints remained identical.
No schema repair, down migration, notification replay, profile rewrite,
device deletion or WorkSession movement occurred.

The byte-exact entry Compose and current backend image were restored. The
backend returned `UP` in 16.131 seconds with profiles, progress, recovery and
notifications enabled and managed updates disabled. A repeated re-enable was
a 96 ms container no-op. After multiple dispatcher intervals the three events
and six single-attempt delivered rows remained byte-stable, zero row was
dispatchable, legacy logs did not increase and no managed update operation
appeared.

The AX42 worker was neither restarted nor replaced and remained active with
`NRestarts=0`. Its program, project configuration, exact admission record,
mirror, clean WorkSession worktree and commit remained stable. Production,
preview and Beautips remained available; Caddy routing was byte/container
stable; all four rootless daemons retained container counts `3/0/0/3`;
external backup timers, firewall, SSH and Tailscale remained active; rootful
Docker remained inactive/masked; all RAID arrays remained `[UU]`; and no
session Codex, Playwright or Chromium process remained. Task-owned temporary
files were removed by exact path.

No device identifier, push token, credential, prompt, answer, provider body,
Codex thread/turn identity or remote execution identity was retained.
Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.6-disable-rollback-reenable`;
the SHA-256 of its `SHA256SUMS` is
`60d2808c00a021312640d1a0359041556de6bf96da484cbcae66222c6a85eba3`.

Task 7.7 was initially blocked by an unexpected authenticated recovery. Task
7.8 has not started.

At 2026-08-01 18:09:39 UTC, after the accepted task-7.6 fingerprints, one
persisted recovery operation requested `RETRY` for failed AgentRun 90. It
completed once as `RETRY_CREATED`, owns exactly one linked AgentRun 91 and
retained the accepted WorkSession, model and effort. The linked run received
one remote execution, reached `SUCCEEDED` after 5.398 seconds, persisted six
monotonic safe progress events and produced one `RUN_COMPLETED` notification
event with one single-attempt delivered row per active Android device.

The operator explicitly confirmed that they did not request or press this
retry. There is no duplicate recovery, linked run, notification event,
non-terminal AgentRun or dispatchable delivery, but the initiating client or
mechanism is unexplained. The immutable recovery, execution, progress and
delivery records were retained. No cancellation, deletion, profile rewrite,
WorkSession replacement, notification replay, cleanup or ownership
reconstruction was performed.

The partially assembled final ledger was retained without acceptance beneath
`task-7.7-draft-evidence-ledger-blocked-20260801`. Sanitized blocker evidence
is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.7-blocked-unexpected-retry`;
the SHA-256 of its `SHA256SUMS` is
`49fd72f2158a1f11f05adb673027095bd7bf0930a038e55fbdd4c630fac17e38`.

Read-only source inspection found no automatic recovery caller: web and
Android invoke the endpoint only from an explicit button handler. Web has no
POST retry queue; Android bounds connection/read to 15/60 seconds and permits
only one immediate authentication-refresh replay. Backend creation has one
POST entry point. The 37-minute delayed-command hypothesis is therefore
outside the clients' finite lifetimes.

Exact historical client attribution is unavailable. V59 retains operator,
role, WorkSession, AgentRun, action, idempotency and request fingerprint, but
not authentication-session identity, client surface, request identity, remote
address or user agent; backend and Caddy retained no access record for the
request. This limitation is disclosed rather than replaced by an inference.

Containment resolved the operation's exact operator and revoked only its five
still-open refresh-session metadata rows, IDs 283, 292, 318, 320 and 321, in
one transaction. No token hash or value was selected or retained. All issued
access tokens had already exceeded the production 15-minute lifetime.
Repeated post-containment observations retained five global recovery
operations, three for this WorkSession, zero non-terminal AgentRuns and zero
renewable sessions. Atenea requires a fresh login; no project, conversation,
AgentRun, notification, device, routing or worker record was deleted,
rewritten, replayed or reconstructed.

The final ledger verifies `55/55` completed-task evidence directories across
Atenea and AX42, inventories 32 sealed screenshots, re-inspects seven
representative desktop/mobile/Android states, and consolidates 57 normalized
duration/timeout records plus the real-device notification receipts. The
superseded draft and original blocker evidence remain retained transparently.
The accepted ledger is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.7-final-evidence-ledger`;
the SHA-256 of its `SHA256SUMS` is
`35bcdf85b3610668f85fa991107071e4ca04f0ecb6d86343248ceda7ea4aab57`.

Task 7.7 is complete and change progress is `56/57`. The exact resume point is
task 7.8. No prompt, answer, remote execution identity, device identity, push
token, credential, provider body, token hash or token value was read or
retained.

Task 7.8 is complete and `add-codex-session-operations` is closed at `57/57`.
OpenSpec synchronized the canonical specifications, created
`codex-session-operations`, updated `remote-work-continuity` and
`remote-worker-control`, and archived the full proposal, design, deltas and
tasks as `2026-08-01-add-codex-session-operations`. The archive tool's two
non-semantic trailing blank lines were removed; `git diff --check` passes and
strict validation reports `12/12` canonical specifications valid.

The Atenea implementation repository remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Direct read-only health probes
report production Atenea, preview and Beautips `UP`. The AX42 worker remains
active with `NRestarts=0`, both independent backup timers active, zero
non-terminal AgentRuns and no recovery newer than
`2026-08-01T18:09:39.936109Z`. The five prior renewable operator sessions
remain revoked, so the next interactive Atenea use requires a fresh login.

No application image, schema/data record, route, WorkSession, project runtime,
worker service, device, notification or unrelated resource changed during
archive closure. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/add-codex-session-operations/runs/task-7.8-strict-sync-archive-closure`;
the SHA-256 of its `SHA256SUMS` is
`f57a1c5bb9a9943a345b7cc05a3765893edd79397e37742f9c862b339f114305`.

There is no remaining task or resume point in this archived change. Normal
Atenea and Beautips operation is confirmed; subsequent programme work requires
a separately selected OpenSpec change.

## Selected next change: real Atenea WorkSession attachments

`activate-atenea-real-worksession-attachments` is the selected apply-ready
change. Its proposal, design, five capability deltas and 83 ordered tasks are
complete; strict OpenSpec validation passes. Progress is `0/83` and the exact
implementation resume point is task 0.1. High MUST finish, verify, mark,
commit and push each task before starting the next one, and MUST stop on an
ownership, Git, backup, runtime, production or foreign-resource divergence
rather than repair or adopt it automatically.

The 2026-08-01 read-only audit found production at V61 with zero
`work_session_attachment` rows. Real creation is disabled by the default-false
global gate, the production backend has neither an attachment endpoint/token
override nor a token mount, and AX42's private
`atenea-worksession-attachment-v1.service` is active against an empty retained
root. The accepted independent B2/restic source policy includes that root and
its backup, check and isolated-restore boundary is healthy, so the prior
external-backup prerequisite is satisfied but has not yet been proven with
non-empty real attachment content.

The audit also confirmed that the current implementation is synthetic rather
than production-ready: admission depends on mutable project display names;
the backend hard-codes `X-Atenea-Synthetic-Fixture: true`; routine upload lets
the caller request privileged source/kind/retention classifications; turn
creation accepts only text; AgentRun v1/v2 and the fixed runner carry no
attachment references; and the web presents an enabled-looking standalone
upload affordance even when the gate will reject creation. Codex CLI 0.145.0
does support fixed `--image` inputs, but no current Atenea path invokes them.
Android has no scoped attachment composer and remains explicitly outside this
change.

The accepted implementation boundary is global default-off plus exact
canonical `atenea` enablement for newly created eligible WorkSessions only;
server-derived operator classification; additive V62 immutable ordered turn
bindings and request idempotency; closed `project-codex-v3` image references;
compatible v1 retained-content reads; exact worker-side verification and
per-execution materialization; and a state-first web composer with picker,
clipboard paste, selection, retry and historical attachment metadata. One turn
is bounded to four PNG/JPEG/WebP images and 32 MiB combined, inside the
existing 16 MiB per-file and 256 MiB per-WorkSession limits. General deletion,
Beautips activation, native Android selection and non-image Codex inputs remain
out of scope.

Tasks 0.1 through 5.9 cover audit, policy/migration, backend contracts, AX42
storage/runner, web UX and complete synthetic acceptance without production
activation. Task 6.4 is an explicit stop gate: production schema/image/service,
credential or feature configuration MUST NOT change without separate rollout
authorization. Task 7.4 is the operator-assisted web canary gate. Closure then
proves non-empty external backup/restore and disable-first rollback twice,
re-enables only canonical Atenea, seals sanitized evidence and stops before
Beautips, Android attachments or retention deletion.

No implementation, migration, service, credential, route, WorkSession,
production data or project gate was changed while preparing this specification.

### Real attachment implementation entry progress

Task 0.1 is complete and change progress is `1/83`; the exact resume point is
task 0.2. The applicable agent instructions, complete programme, active
proposal/design/five deltas/tasks, canonical attachment/worker/continuity/
onboarding specifications and archived attachment plus external-backup
contracts were read before implementation mutation.

The complete accepted attachment rollback bundle verifies against SHA-256
`2edf4d395c0f893a723cdead42072ec70ec465a41fdff295bf53e88c66972c74`.
The complete accepted external-backup rollup verifies against SHA-256
`90c2acc6882d8f498bd70742d9dcb3b7699edbe3628e6d1fba829938ecc18b4c`.
No credential value, prompt, answer, attachment content or Codex internal state
was read or retained.

Task 0.2 is complete and change progress is `2/83`; the exact resume point is
task 0.3. The active programme worktree is clean on
`codex/task-7.4-worker-canonical-refresh-20260801`; its local and internal
remote ref are equal at `d42617f0a0dbca6781f73c9ca50ee69984c7427c` after
the task-0.1 documentation commit. The canonical Atenea source worktree is
clean on `feature/actualizar-conversacion-en-web` and equals its upstream at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. No implementation worktree,
branch, migration or source commit was created.

Task 0.3 is blocked and remains the first pending task. The read-only
fingerprint confirmed production V61, zero attachment rows/bytes, zero
non-terminal AgentRuns, zero active remote leases/previews, production and
preview `UP`, default-off attachment creation, no backend attachment override
or token mount, healthy RAID `[UU]`, active SSH/Tailscale/firewall, four active
rootless daemons, inactive rootful Docker, active attachment/AgentRun services,
zero attachment files/bytes, active backup/check timers and slot container
counts `3/0/0/3`.

The installed canonical AgentRun worker verifier then exited `1`. Its installed
SHA-256 `49bc6e32ba920e1bf8cbc3247b8dcb2bcc57b45bb3a899f5dac05e21b79da4a3`
equals the reviewed source, which requires exact `0750` for the Codex release
root plus root-owned activation and rollback children. AX42 reports all three
as `2750`. No accepted decision or prior evidence authorizes that mode, so the
change's ownership rule blocks implementation rather than allowing automatic
chmod, adoption or verifier relaxation.

No source, schema, mode, directory, service, runtime, route, database row,
credential, WorkSession, slot or foreign resource was changed. Sanitized
blocker evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.3-blocked-codex-release-mode`;
the SHA-256 of its `SHA256SUMS` is
`917263d315f6829dc52a47af4c875e8badadb9a869fa21b4415ce7c8d25bd26e`.

The release-root mode blocker is now resolved. Programme commit
`a1c487b33efca6e03b7ca392f779ab64dc27d5ba` adds an installer regression for
setgid inheritance beneath a `2770` parent and explicitly clears inherited
special bits so the existing exact `0750` contract is enforced. All 13 focused
installer, staging and activation tests pass. The exact installer was deployed
to AX42 and only the six platform-owned release, inbox, operation, activation
and rollback directory modes were normalized. The AgentRun service was not
restarted; release links, project configuration and entry count did not
change; the complete canonical verifier now passes.

The first sealed task-0.3 bundle's zero attachment-file/byte result is invalid.
Its unprivileged traversal returned `Permission denied`, and the pipeline lacked
`pipefail`, allowing the following count to mask that failure. The original
bundle remains unchanged for audit transparency, but those two fields are
superseded by a corrected mediated read-only fingerprint.

That fingerprint found 16 regular files totalling 261,276 bytes in the retained
attachment boundary while production remains at V61 with zero attachment rows
and zero indexed attachment bytes. None is incoming, a symlink or a special
file; all are mode `0600` and owned by `atenea-worker:atenea`. No filename,
attachment or WorkSession identity, sidecar value, digest, content, prompt or
answer was read or retained, and no file was modified, moved, adopted,
downloaded or deleted. Without authoritative control-plane ownership, this is
ambiguous retained state and task 0.3 remains blocked under the change's
fail-closed contract.

Production, preview and Beautips remain `UP`; RAID remains healthy; the
AgentRun worker, attachment service and both backup timers remain active; and
zero Codex or browser process remains. Corrective sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.3-blocked-unindexed-attachment-content`;
the SHA-256 of its `SHA256SUMS` is
`ff33b6e9e081e55f714a830383e7844393424b58d5162cdcab5151b1ab85c1ed`.
Change progress remains `2/83`, task 0.3 is the first pending task and no task
0.4 or later has started.

The separately authorized ownership investigation resolved the apparent
attachment ambiguity without cleanup or adoption. A mediated read-only
comparison matched all eight retained attachment identities and their exact
session/path/sidecar ownership against three accepted historical evidence
bundles: private-preview acceptance, Atenea onboarding and Beautips onboarding.
All three source bundles verify against their published `SHA256SUMS`; zero
unexpected retained identities exist and zero accepted identities are missing.

The retained set is six PNG and two JSON synthetic `EVIDENCE` records in three
sessions: eight content files totalling 256,755 bytes and eight sidecars
totalling 4,521 bytes. All path, protocol, worker, storage-identity, file-type,
mode, classification and size comparisons pass. No attachment content was
opened, downloaded or hashed; no UUID, filename, storage identity, sidecar
value, digest, prompt or answer is retained in the new evidence. No retained
resource changed.

The earlier premise that the retained root was empty is therefore corrected,
not enforced destructively. Production's zero V61 attachment rows/bytes remain
accurate because the retained records belong to accepted non-production
synthetic evidence boundaries. The active design and task wording now require
preservation of that exact baseline.

Task 0.3 is complete and change progress is `3/83`; the exact resume point is
task 0.4. Accepted sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.3-entry-fingerprint-accepted`;
the SHA-256 of its `SHA256SUMS` is
`388181570cbe2eff43f117a6a6ded0e822afb72915341c7f8597652b3bcd4ec2`.

Task 0.4 is complete and change progress is `4/83`; the exact resume point is
task 0.5. Production exposes zero attachment environment override names, zero
attachment-related mount destinations and no attachment token file. Its
default-disabled backend therefore has no usable real attachment endpoint or
credential boundary.

AX42's attachment program and systemd unit are byte-exact with reviewed source.
The service is active on the worker's private Tailscale address only, owns one
exact listener, has one exact Atenea-to-AX42 UFW admission rule and returns HTTP
401 without authentication. The installed external-backup program is also
byte-exact with reviewed source and its closed source policy includes the
attachment boundary. Both backup timers are active, both latest service results
are `success/0`, and the accepted backup/check/retention/isolated-restore rollup
still verifies at SHA-256
`90c2acc6882d8f498bd70742d9dcb3b7699edbe3628e6d1fba829938ecc18b4c`.

No backup, restore, upload, download, service restart or configuration mutation
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.4-prerequisite-boundary`;
the SHA-256 of its `SHA256SUMS` is
`32a6bc99470b6f36a5b37d35fff29b5166a32be8d923f128dd3952673e89f9c0`.

Task 0.5 is complete and change progress is `5/83`; the exact resume point is
task 0.6. Source at canonical Atenea commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and the reviewed programme worker
confirms all six planned gaps: mutable display-name synthetic admission,
hard-coded synthetic upload, caller-selected source/kind/retention, message-only
turn creation, absent `project-codex-v3`/`--image` delivery, and a standalone
enabled-looking primary upload panel that does not bind files to a turn.

The audit was read-only and records exact Git blob identities for the inspected
source boundary. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.5-gap-audit`;
the SHA-256 of its `SHA256SUMS` is
`be760d23025b1cb586171fee8df2471a5e014befe3229571f03daca789f4262b`.

Task 0.6 is complete and the entry gate is closed at change progress `6/83`;
the exact resume point is task 1.1. All five supporting entry bundles and every
file they declare pass checksum verification. The rollup preserves command
summaries, exit codes, finite timeouts and relevant durations without retaining
credentials, environment values, attachment identities/content, prompts,
answers or Codex internal state.

Strict validation passes for the active change and for all 13 authoritative
OpenSpec items. No production schema, data, credential, deployment, routing,
WorkSession, runtime or retained attachment changed during entry-gate closure.
Sanitized rollup evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-0.6-entry-gate-rollup`;
the SHA-256 of its `SHA256SUMS` is
`cb7ce62b054030b5ae4a0e619d2eaa11864b1c5d6ea8514e9b4b18fd94ad6563`.

Task 1.1 is complete and change progress is `7/83`; the exact resume point is
task 1.2. Atenea commit
`e50862e46a067f38d7d3a1fa689fa623e8c3d5b5` on published branch
`codex/activate-atenea-real-worksession-attachments` adds a closed real-
attachment registry whose only canonical identity is `atenea`, fixed to worker
`ax42-01` and policy revision `atenea-real-attachments-v1`. The runtime
allowlist defaults empty.

Six focused tests prove exact Atenea acceptance plus startup rejection of
Beautips, the mutable `Atenea` display name, arbitrary unknown values and mixed
known/unknown configuration; the enabled set is immutable. The canonical test
script could not allocate two fixed names already owned by an unrelated local
environment and stopped before tests. The equivalent canonical Maven command
passed in a uniquely labelled isolated Compose project, after which its exact
container, network, volumes and image were removed with zero residue. No
foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.1-canonical-registry`;
the SHA-256 of its `SHA256SUMS` is
`7743a093cc741fe68b2ca58a3a763f66c2ce78c62a44581ba3d4953f09d1a7f8`.

Task 1.2 is complete and change progress is `8/83`; the exact resume point is
task 1.3. Atenea commit
`3255953b20c9c7fa2648f5560ae0ea3267851b58` centralizes the default-false
global create/bind kill switch while retaining independent synthetic and
canonical real-project allowlists. Exact real `atenea` configuration cannot
enable the legacy synthetic `Atenea` display-name path; foreign real identities
fail closed.

Fifteen focused registry, admission-policy and attachment-service tests pass.
They also prove that disabling creation leaves retained list and authenticated
download unchanged. The isolated Compose test resources were removed with zero
residue; production and remote services were not changed. Sanitized evidence
is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.2-admission-separation`;
the SHA-256 of its `SHA256SUMS` is
`3b82523a3da52b9d18393b2c4734b8427dd9fabc9e35246d250a18629fa82178`.

Task 1.3 is complete and change progress is `9/83`; the exact resume point is
task 1.4. Atenea commit
`ba116da3996a249ef2e6ac1bcca3ece11f9af2ad` snapshots
`atenea-real-attachments-v1` only after a newly created WorkSession has been
routed with the exact canonical Atenea identity, AX42 worker, remote session
UUID, project workload and deterministic workspace identity. Global or project
disable, local placement and foreign, partial or ambiguous ownership retain a
null revision. Resolving an existing open WorkSession returns before routing or
snapshot evaluation, and an existing revision is never rewritten.

The V61-compatible domain property remains transient in this task; additive
V62 persistence and constraints are explicitly owned by task 1.4. Fifty-six
focused registry, admission, snapshot and WorkSession tests pass, followed by
two Spring/JPA tests against isolated PostgreSQL after a clean V1-to-V61
migration. All exact test containers, networks, volumes and images were removed
with zero residue and no fixed-name foreign local resource was changed.

The canonical Atenea checkout remains clean and equal to its upstream at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips report `UP`; the versioned AX42 AgentRun and attachment services plus
both backup timers are active; RAID is `3/3`; slot container counts remain
`3/0/0/3`. No production deployment, schema, database row, WorkSession,
attachment, route, service or credential changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.3-policy-snapshot`;
the SHA-256 of its `SHA256SUMS` is
`c40a4cfdf1e6aef7d35457dd9ac25b7ffc59fd548f05bea8fd99fef914f774ad`.

Task 1.4 is complete and change progress is `10/83`; the exact resume point is
task 1.5. Atenea commit
`83cf2356d87c1903b755497b1727701e312abedd` adds the single additive V62
migration and matching JPA fields for the WorkSession policy revision, paired
turn request identity/fingerprint, ordered same-session attachment binding,
AgentRun attachment count/bytes/manifest and nullable real storage ownership.

Database constraints accept only complete remote AX42 policy ownership, pair
and validate idempotency fields, enforce unique request identity per session,
bind turns and attachments through composite same-session foreign keys, reject
project/worker/remote-session/workspace disagreement, bound distinct positions
to zero through three and constrain AgentRuns to either the compatible
zero/zero/null shape or one to four attachments totalling at most 32 MiB with a
lowercase SHA-256 under `project-codex-v3`. Existing attachment ownership fields
remain null and existing AgentRuns expand to zero/zero/null without row rewrite.

Review of the first disposable fixture caught PostgreSQL `CHECK` null semantics;
explicit non-null predicates were added before commit, that exact fixture was
destroyed and corrected V1 through V62 were applied to a fresh database. Two
Spring/JPA tests pass after the fresh migration and 56 focused policy/snapshot/
WorkSession tests pass. Catalog inspection confirms V62, the four binding
columns and all 15 named ownership constraints. Exact fixture resources were
removed with zero residue.

Production and preview remain `UP`; Beautips remains `UP`; the canonical Atenea
checkout remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; AX42's versioned AgentRun and
attachment services plus both backup timers remain active and RAID remains
`3/3`. No production migration, deployment, schema, data, route, service or
credential changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.4-v62-schema`;
the SHA-256 of its `SHA256SUMS` is
`1412f5f59985f96df6aa3415de78a1dd040465ac53b189499cf27df99d7af386`.

Task 1.5 is complete and change progress is `11/83`; the exact resume point is
task 1.6. Atenea commit
`0a9b0ef90d9d1358e5e01d32ddc765fb9523e972` adds permanent isolated-
PostgreSQL migration regressions for an empty V1-through-V62 database, a
representative V61 database and the V62 ownership constraints. Every test uses
a unique schema and drops only that exact schema in `finally`.

Three tests pass. They prove a repeated Flyway migration applies zero changes;
legacy policy, request identity and storage ownership remain null; legacy
AgentRuns retain the compatible zero/zero/null attachment shape; and partial,
foreign or ambiguous policy, request, storage, binding and manifest writes fail
with integrity SQLSTATEs while accepted synthetic rows remain unchanged. A
final-run attempt stopped before compilation when Maven Central was temporarily
unreachable; the process had exited, connectivity returned HTTP 200 and one
bounded retry passed all three tests without a source change.

All temporary schemas and exact Compose resources were removed with zero
residue. Production, preview and Beautips remain `UP`; AX42's versioned AgentRun
and attachment services plus both backup timers remain active; RAID remains
`3/3`. No production migration, schema, data, WorkSession, attachment, routing,
service, credential or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.5-v62-migration-tests`;
the SHA-256 of its `SHA256SUMS` is
`331a5385553d71ec63bcd91ae3757b0dc53f88d4759a7dfffe8b48d53c9e3979`.

Task 1.6 is complete and change progress is `12/83`; the exact resume point is
task 1.7. Atenea commit
`cd332b75b518e9cc117313f0f9dd012686808284` adds the composite turn/
attachment persistence identity, an immutable Hibernate read entity and a
closed Spring Data repository. The repository exposes exactly one native
insert, one exact-turn ordered read and one deterministic multi-turn ordered
read; it does not inherit or declare save, update or delete operations.

Two PostgreSQL V62 integration tests pass. They prove that persisted positions
control one-turn order independently of insertion order, multi-turn reads are
ordered by turn then position and the repository method surface contains no
generic mutation path. Transaction rollback leaves zero synthetic projects,
workers or bindings. An initial host invocation stopped before compilation on
a previously root-owned generated `target/`; the containerized first run then
identified an incomplete test worker fixture, which was completed without
weakening a database constraint, and the bounded final run passed.

All exact task containers were removed with zero labelled container, network
or volume residue. The canonical Atenea checkout remains clean and synchronized
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned AgentRun and attachment services plus
both backup timers remain active; RAID remains `3/3`. No production schema,
data, WorkSession, attachment, route, service, credential or foreign resource
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.6-immutable-bindings`;
the SHA-256 of its `SHA256SUMS` is
`5483f665aef7e457932e80be03060112773500b540b67c242a577c6ab468a7f7`.

Task 1.7 is complete and change progress is `13/83`; the exact resume point is
task 1.8. Atenea commit
`064e4b278757d179a3159c1c4039e7485413226f` defines separate versioned
SHA-256 domains for the ordered attachment manifest and its image-turn request.
Message normalization converts CRLF/CR to LF, applies Unicode NFC and strips
outer whitespace while preserving internal content.

The canonical binary format length-prefixes UTF-8 text and writes the ordered
count, UUID bits, byte size and raw content digest in big-endian form. The
request then frames the normalized message and raw manifest digest. It does not
depend on JSON ordering, locale or text delimiters and fails closed on blank
messages, empty, duplicate or over-bound lists, non-canonical image media type,
non-positive size and non-lowercase SHA-256.

Four focused tests pass with locked golden manifest/request vectors. They prove
normalization stability, attachment-order sensitivity, influence of every
immutable field and rejection of malformed or ambiguous inputs. An independent
Perl/Digest::SHA implementation with explicit UTF-8 reproduces both golden
hashes exactly. Two earlier runs failed only on deliberate placeholder golden
assertions used to capture those vectors; the published source contains no
placeholder.

All exact task containers were removed with zero labelled container, network
or volume residue. The canonical Atenea checkout remains clean and synchronized
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; the versioned AX42 services and both backup timers remain
active; RAID remains `3/3`. No production or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.7-canonical-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`1a87034915d9f0e10566f8c4ce3e35edeada74e880d75b10a02d5654b8638553`.

Task 1.8 is complete and change progress is `14/83`; Phase 1 is complete and
the exact resume point is task 2.1. Atenea closure commit
`f6a233714afaf2d8c5d199e14c66a58aa405d39b` publishes the already-tested
tree `7644e41313f44791bb5ae9259a0e18e1fd8b33d2` for the complete policy,
migration and immutable-ownership slice.

The combined PostgreSQL suite passes all 69 registry, admission, retained-
synthetic compatibility, new-session snapshot, WorkSession, V62 migration,
invalid ownership, immutable ordered repository and canonical hashing tests.
The first combined runner passed 66 tests while the three isolated migration
tests stopped before their bodies because their datasource was supplied as
Spring properties but not the required test environment names. The corrected
runner used both forms against the same isolated database and passed `69/69`.

Static V62 inspection finds no `DROP TABLE`, `DROP COLUMN`, row `UPDATE`, row
`DELETE` or `TRUNCATE`. The only drops replace the two existing AgentRun check
constraints in the same migration with v1/v3-compatible constraints. V62's
SHA-256 is
`cc55e65b536384365a9b0efd824aab032c6f3892095bf7230329fde26a3ef1db`;
the migration regressions prove null/zero legacy compatibility and zero change
on repetition.

All isolated schemas, transaction fixtures and exact task containers were
removed with zero labelled container, network or volume residue. The canonical
Atenea checkout remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned services and both backup timers remain
active; RAID remains `3/3`. No production or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-1.8-policy-migration-slice`;
the SHA-256 of its `SHA256SUMS` is
`b57194a5ada8c33226cbd19e8fae568ecbbd576ed484907471e70e011c6ca956`.

Task 2.1 is complete and change progress is `15/83`; the exact resume point is
task 2.2. Atenea commit
`f04ea4f2a62992a81ee8483acc81d9cba7c5b08e` makes the routine authenticated
upload route derive `OPERATOR_UPLOAD`, `SESSION` and `IMAGE`/`FILE`
classification server-side. PNG, JPEG and WebP derive `IMAGE`; other media
types derive `FILE` and remain subject to the existing closed worker allowlist
and content validation.

Legacy source, kind and retention form fields remain optional for compatible
rollout, but now act only as equality assertions. Browser screenshot, browser
trace and report sources; trace, report or media-mismatched kinds; and
`EVIDENCE` or `TRANSIENT` retention claims all fail before worker health,
storage or metadata indexing. Mediated preview/evidence authority is unchanged.

Eleven focused controller/service tests pass in 16.81 seconds under a
180-second timeout, with no network and an ephemeral build target. They prove
omitted and matching compatibility fields, image/file derivation, eight closed
rejection variants and zero worker or index calls after rejection. Three
earlier invocations stopped before tests solely on isolated Maven cache/target
runner configuration; the corrected offline runner passed without a following
source change.

The implementation branch is clean and published with tree
`db950a130b087e565089d97c800ad3ef535be299`. The canonical Atenea checkout
remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned services and both backup timers remain
active; RAID remains `3/3`; slot container counts remain `3/0/0/3`. No
deployment, schema/data record, route, service, retained content, credential or
foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.1-server-derived-classification`;
the SHA-256 of its `SHA256SUMS` is
`0571e817b6742845ffbfd67ccbecb3042b489868a545975111da2202249c3d36`.

Task 2.2 is complete and change progress is `16/83`; the exact resume point is
task 2.3. Atenea commit
`23199875e32e2716f10eafa4a5b669a294f6c849` replaces upload whole-file
buffering with a bounded private spool: the same-owner real directory is mode
`0700`, unpredictable regular files are mode `0600`, input is copied in 64 KiB
blocks and the 16 MiB limit is enforced against bytes actually read.

The streaming pass calculates SHA-256 and retains only a 16-byte signature
window. PNG, JPEG, WebP, PDF and ZIP use the closed AX42 signatures; text must
be strict UTF-8 without NUL; JSON is parsed as exactly one root value without
building an in-memory tree. The worker client sends the file publisher with a
known content length rather than a second byte array, and Atenea verifies the
returned size, digest, type and classification.

The spool closes before metadata indexing. Success, non-derived authority,
actual-stream overflow, read failure, type mismatch, worker failure,
worker-response identity mismatch and indexing failure tests all leave zero
temporary files. Newly created synthetic worker content is removed through its
exact existing identity when a post-PUT validation or index step fails.

The final focused suite passes `21/21` tests in 11.90 seconds under a 240-second
timeout, with no network and an ephemeral build target. Two earlier passing
20-test runs preceded review improvements for single-root JSON and invalid
worker-response cleanup. Static inspection finds zero `MultipartFile.getBytes`
calls in the upload path and the default spool path is absent after testing.

The implementation branch is clean and published with tree
`1e4192ec45a7c28bb4e27fe1835f4908fa0f6c5a`. The canonical Atenea checkout
remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned services and both backup timers remain
active; RAID remains `3/3`; slot container counts remain `3/0/0/3`. No
deployment, schema/data record, route, service, retained content, credential or
foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.2-private-upload-spool`;
the SHA-256 of its `SHA256SUMS` is
`d2198e7f66250d9828b8b5e94815fded7317e758a280bd461eb1ec46a346d634`.

Task 2.3 is complete and change progress is `17/83`; the exact resume point is
task 2.4. Atenea commit
`223a20ee07da3ba4b5b885e90b83e24b2dbbd4de` separates legacy synthetic and
real attachment storage ownership without changing the public base-v1 response.

Synthetic uploads retain their positive decimal control-plane WorkSession
identity, explicit `syntheticFixture=true`, null V62 real-scope fields and exact
synthetic-only cleanup. Real upload requires the immutable accepted policy
revision plus exact canonical Atenea project, AX42 worker, remote workload,
remote WorkSession UUID and deterministic workspace identity.

Before any real PUT, Atenea requires the separate authenticated
`real-project-attachment/v1` capability. An absent or incompatible endpoint
fails before worker content. The accepted PUT uses the remote UUID in the base
v1 route and sends only server-derived `atenea`, workspace, `REAL_SESSION` and
explicit non-synthetic ownership headers. Returned public metadata must match
the UUID, worker, attachment, size, SHA-256, classification and non-synthetic
identity before indexing.

V62 indexing persists and compares complete real scope against the locked
canonical WorkSession while continuing to accept only all-null legacy scope.
Base-v1 metadata/content retrieval routes null legacy scope by decimal identity
and complete real scope by remote UUID; partial or mixed scope fails before
network. Real content is never sent to the synthetic delete route, including
after an index failure.

The final focused suite passes `38/38` tests in 11.53 seconds under a 300-second
timeout, with no network and an ephemeral build target. One broadened
intermediate command also passed those 38 tests but selected three V62 migration
tests without their required isolated-PostgreSQL environment; only those three
stopped before their bodies and no resource was created.

The implementation branch is clean and published with tree
`372a204838c4a6738e0a4790dc2b34d5d21996d3`. The canonical Atenea checkout
remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned services and both backup timers remain
active; RAID remains `3/3`; slot container counts remain `3/0/0/3`. No
deployment, schema/data record, route, service, retained content, credential or
foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.3-real-storage-scope`;
the SHA-256 of its `SHA256SUMS` is
`bc2494d04de1af4590aac406149945a7228a00f4e5a166228e4137100a884bfc`.

Task 2.4 is complete and change progress is `18/83`; the exact resume point is
task 2.5. Atenea commit
`409a2f3222a5fd61b693a4154d3de7820ff850e9` adds an authenticated
state-first capability read model to the existing web/mobile WorkSession
attachment API without enabling either UI.

The response reports exactly one `READY` or `BLOCKED` state and one closed,
actionable reason for global disable, project disable, legacy-session
ineligibility, invalid ownership, exhausted quota, unavailable storage or an
unsupported worker contract. It also reports the immutable session policy
revision, explicit worker compatibility state, PNG/JPEG/WebP selection types,
current/maximum/remaining session bytes, the 16 MiB file bound and the four-
image/32 MiB per-turn limits. It exposes no endpoint, token, worker identity,
storage scope or path.

Policy and quota rejection stop before AX42 access. A ready response requires
the exact new Atenea session ownership, compatible base v1 limits/types and the
separate exact `real-project-attachment/v1` capability. Both web and existing
mobile aliases remain beneath the stateless authenticated `/api/**` boundary.

The final isolated PostgreSQL V62 suite passes `17/17` tests in 26.01 seconds:
eight capability-service tests, six controller tests and three authentication
integration tests. Its exact ephemeral container and network are absent after
the cleanup trap. An earlier 14.63-second invocation stopped on one Mockito
restubbing defect and the intentionally absent integration datasource; the
mock was corrected without weakening the contract. The database-free rerun
then passed `14/14` before the complete isolated run.

The implementation branch is clean and published with tree
`8ceb0a40f152866aee5b64e0e73b9d2da2a9efb5`. The canonical Atenea checkout
remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview and
Beautips remain `UP`; AX42's versioned services and both backup timers remain
active; RAID remains `3/3`; the corrected rootless slot inventory remains
`3/0/0/3`. Two invalid read-only slot probes were discarded before the exact
user/socket/binary probe; no resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.4-authenticated-capability`;
the SHA-256 of its `SHA256SUMS` is
`6448d1ebd8c01d6246eb8ebb42e8d79d26a455df6815f02749cc3cde9721c276`.

Task 2.5 is complete and change progress is `19/83`; the exact resume point is
task 2.6. Atenea commit
`cfb9409663cbc27fe2f3e3f42494b3bad3e8215b` extends the authenticated turn
request additively with an optional `clientRequestId` UUID and immutable
ordered `attachmentIds` UUID list.

Missing or null attachment lists normalize to empty. A non-empty list without
the stable client request identity fails Jakarta request validation before
`SessionTurnService`; exact attachment order reaches the service unchanged.
The existing one-argument Java constructor and legacy JSON containing only
`message` retain null identity plus an empty list, so web/mobile text turns,
voice and Core call sites remain compatible.

This task deliberately adds no count, duplicate, size, type, expiry, integrity
or ownership validation and creates no binding, turn snapshot or dispatch;
those remain tasks 2.6 onward. The offline source-read-only compatibility suite
passes `58/58` tests in 14.93 seconds under a 300-second timeout, covering the
web request boundary plus existing mobile, service, voice and Core callers.

The implementation branch is clean and published with tree
`457fd0e81926a04abc9a0ed60185c34d4ab7c32e`. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips remain `UP`; exact AX42 services and backup timers remain active;
RAID is `3/3 [UU]`; rootless slot inventory remains `3/0/0/3`. No deployment,
schema/data, WorkSession, turn, attachment, routing or credential changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.5-additive-turn-identities`;
the SHA-256 of its `SHA256SUMS` is
`e2d3482171ae555b4b94855b25b53542ceacb8f2bede1e48b806182857996b77`.

Task 2.6 is complete and change progress is `20/83`; the exact resume point is
task 2.7. Atenea commit
`d273daa3e1ed6b977ee214c32310270432877a5d` adds a read-only validator for
one to four ordered, distinct, same-session real PNG/JPEG/WebP selections with
a 32 MiB combined limit.

Each indexed image must retain exact canonical Atenea project, WorkSession,
AX42 worker, remote UUID, deterministic workspace, `REAL_SESSION` scope,
operator/session classification, positive per-file bounded size, lowercase
SHA-256 and future `retainUntil`. Empty, over-count, duplicate, missing,
foreign, partial, non-image, unsupported, oversized and expired selections
fail before any AX42 request.

After local validation, selection requires compatible base-v1 and exact
`real-project-attachment/v1` capabilities. Atenea compares complete remote
metadata against the immutable index, then performs one authenticated bounded
content read per image and independently checks type, size and SHA-256. Reads
are sequential, bytes do not escape the validator and no delete path is ever
used. The accepted result exposes only ordered UUID/type/size/SHA references,
total bytes and the canonical manifest digest needed by task 2.7.

The final offline source-read-only suite passes `20/20` tests in 11.69 seconds
under a 300-second timeout. It includes a content-modified/metadata-unchanged
rejection. An initial `19/19` pass preceded that deliberate integrity
strengthening and had no failure or external mutation.

The implementation branch is clean and published with tree
`3a011aaa1e011a85f16724db2b05ae37ba8120d9`. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips remain `UP`; exact AX42 services and backup timers remain active;
RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`. No deployment, schema,
record, retained content, route, service or credential changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.6-real-image-validation`;
the SHA-256 of its `SHA256SUMS` is
`705010ed62c0d2b82ee18cbe9f8988b17c6fefefc7145ab61f8c57cd2a3246e9`.

Task 2.7 is complete and change progress is `21/83`; the exact resume point is
task 2.8. Atenea commit
`651473e78a390afc25e7b960624a52b148908439` atomically persists an accepted
image-bearing operator turn, its stable client request identity and request
fingerprint, an immutable `project-codex-v3` AgentRun attachment snapshot and
the ordered positional bindings before dispatch registration.

The complete selection still validates before the first write. Dispatch is
registered only after every binding exists and remains an after-commit action.
An invalid selection therefore creates no turn, AgentRun, binding or dispatch;
a deliberately induced second-binding foreign-key rejection rolled back the
turn, first binding, AgentRun and WorkSession activity timestamp while leaving
the already retained attachment intact.

The final focused suite used an isolated PostgreSQL 16 database migrated from
empty through Flyway V62, a read-only source checkout and an ephemeral build
target. It passed `46/46` tests in 26 seconds under a 300-second timeout. The
evidence also records the preceding compile, datasource, matcher and build
environment failures transparently; none contacted or changed production.

The implementation branch is clean and published with tree
`2ad90e0ed85e19be3d540a4cccfc5ebefd46f31b`. Canonical Atenea remains clean
and synchronized at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`;
production, preview and Beautips remain `UP`; the AgentRun worker, attachment
service and backup timers are active; RAID remains `3/3 [UU]`; rootless slots
remain `3/0/0/3`. No deployment, migration, production record, retained
content, route, credential or service changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.7-atomic-image-turn`;
the SHA-256 of its `SHA256SUMS` is
`24a185d01c8f10f63bd9e9c7dbfdb42067f74ecb5d7defc11cc54b66ca6dc3d3`.

Task 2.8 is complete and change progress is `22/83`; the exact resume point is
task 2.9. Atenea commit
`74b50c3e3fb6e6ba9e2135ccf042d329685f31ff` makes accepted image-turn
submission idempotent under the existing V62 request identity.

Any request carrying a client UUID locks its exact WorkSession before reading
the unique `(session_id, client_request_id)` row. A replay succeeds only when
the normalized request fingerprint, exact ordered and contiguous bindings,
indexed immutable manifest and original `project-codex-v3` AgentRun snapshot
all agree. It then returns the original turn/run without attachment
revalidation, reconciliation, worker access, binding insertion or dispatch.

Different message or image order, malformed binding positions, changed
manifest or incomplete persisted ownership uses the existing attachment
conflict mapping to return `409` and preserves the first acceptance unchanged.
The session lock serializes concurrent UUID reuse before the V62 unique
constraint can be raced.

The final focused suite passed `48/48` tests in 24 seconds under a 300-second
timeout against an isolated PostgreSQL 16 database migrated from empty through
V62. It proved identical replay returns the original identities, conflict keeps
one turn/binding/run/dispatch and retained content remains intact. All exact
synthetic rows and the named database container were removed.

The implementation branch is clean and published with tree
`4d0b9fdfe19f9b4cf567f03775a5a26c28d5e198`. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips remain `UP`; required AX42 services and backup timers are active;
RAID remains `3/3 [UU]`; rootless slots remain `3/0/0/3`. No deployment,
migration, production record, retained content, route, credential or service
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.8-idempotent-image-turn`;
the SHA-256 of its `SHA256SUMS` is
`2b53a1fb2624bc1a38c349569545f98718dab9fae084f0b785f4679e1be5e3ea`.

Task 2.9 is complete and change progress is `23/83`; the exact resume point is
task 2.10. Atenea commit
`35a02e6723d64acd06e4f002a5f13aae3609e618` projects exact bound-image
metadata onto immediate and historical turn responses.

The new additive per-turn list contains only attachment UUID, immutable
position, normalized filename, media type, byte size, SHA-256 and an
authenticated same-session API download path. It contains no content bytes,
worker ID, storage identity, workspace identity, remote-session identity or
filesystem path. Legacy response constructors remain source-compatible and
text-only turns expose an immutable empty list.

Historical windows use one bounded binding query and one indexed metadata
query rather than per-turn reads. Missing metadata, non-contiguous positions,
more than four bindings, unsupported/non-image types, invalid size/SHA or more
than 32 MiB per turn fails closed. Exact-turn grouping proves that a later
text/Codex turn never inherits an earlier image.

The final isolated PostgreSQL V62 slice passed `49/49` tests in 17 seconds
under a 300-second timeout. The HTTP boundary passed `12/12`, asserting all
permitted JSON fields and the absence of forbidden ownership/content fields;
the controller/mobile/Core/voice compatibility slice passed `85/85`. Exact
fixtures and named containers were removed.

The implementation branch is clean and published with tree
`e18f77b34876020789d3d3ed6c3dd6011d0ef780`. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips remain `UP`; required AX42 services and backup timers are active;
RAID remains `3/3 [UU]`; rootless slots remain `3/0/0/3`. No deployment,
migration, production record, retained content, route, credential or service
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.9-historical-image-projection`;
the SHA-256 of its `SHA256SUMS` is
`203f4aa8972ead9d1f626f4ff6176574403c0af5fd18b58f39c7226807b018ba`.

Task 2.10 is complete and change progress is `24/83`; the exact resume point
is task 2.11. Atenea commit
`1aed75fe7f679dd53eda1c692f8a846c88c7db8c` preserves the exact image
manifest and effective Codex profile on safe failed-run retry.

Recovery locks the source run, returns an already linked retry idempotently,
and otherwise reconstructs the ordered attachment selection only from the
failed run's immutable origin-turn bindings. Binding positions must be
contiguous and their count, combined bytes and canonical manifest SHA-256 must
equal the persisted `project-codex-v3` snapshot before a new linked AgentRun
can be saved.

The retry path deliberately bypasses only new create/bind admission and expiry
eligibility. Canonical WorkSession/project/worker/workspace/storage ownership,
worker capabilities, retained metadata and content SHA-256 still have to match
exactly. This permits an already bound failed run to retry after `retainUntil`
while the bytes remain intact, but missing, reordered or changed content fails
closed rather than executing text-only. The retry copies all six effective
Codex profile fields and creates no turn, attachment or binding.

The final focused V62 suite passed `53/53` tests in 18 seconds under a
300-second timeout: validator `11/11`, turn service `8/8`, HTTP controller
`12/12`, AgentRun service `17/17`, binding persistence `2/2` and atomic retry
integration `3/3`. The integration proof observed one additional linked
AgentRun with invariant turn/binding/attachment counts and storage/workspace
identity after retention expiry. Exact fixture rows and the uniquely named
PostgreSQL container were removed.

The implementation branch is clean and published with tree
`5f796e22058e133ae563a8d9f01c06cf52749e99`. Canonical Atenea remains clean
and synchronized at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`;
production, preview and Beautips return HTTP 200; required AX42 services and
backup timers are active; RAID remains `3/3 [UU]`; rootless slots remain
`3/0/0/3`. No deployment, migration, production record, attachment ownership,
retained content, route, credential or service changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.10-safe-image-retry`;
the SHA-256 of its `SHA256SUMS` is
`c751319208a23d131026bfc0f160b036129389875ab78af9f90c52d0c86dc999`.

Task 2.11 is complete and change progress is `25/83`; the exact resume point
is task 2.12. Atenea commit
`f6e628abcae200f9ab04a9ce98140d5d3f1e0ac0` adds the closed
`project-codex-v3` control-plane serialization.

An image-bearing profiled AgentRun uses the same persisted project, canonical
source, reviewed instruction bundle and workspace authority as v1/v2. Its sole
additional workload field is an ordered `attachments` array. Every entry
contains exactly `attachmentId`, `contentType`, `sizeBytes` and `sha256`;
filenames, content bytes, paths, URLs, storage identities, remote/workspace
identities, worker identity and arbitrary options are absent.

The array is reconstructed from the immutable origin-turn binding order and
indexed V62 metadata rather than caller input. Before serialization, Atenea
requires exact policy, project, session, worker, remote-session, workspace and
real-storage ownership, contiguous unique positions, supported image metadata
and complete indexed identity. It recomputes the ordered canonical manifest
and compares attachment count, combined bytes and SHA-256 with the AgentRun
snapshot. Partial, foreign, reordered or changed state returns conflict before
network dispatch. Array order participates in the serialized workload and a
test proves reordering changes its SHA-256 fingerprint.

The final combined slice passed `58/58` tests in 17 seconds under a 300-second
timeout against PostgreSQL 16 migrated from empty through V62. It covered
manifest projection, v1/v2/v3 client compatibility, coordinator workspace
admission, retained recovery, AgentRun behavior and atomic V62 persistence.
The exact serialization repetition passed `23/23`; exact fixture rows and the
uniquely named PostgreSQL container were removed.

The implementation branch is clean and published with tree
`545c1d599c39771bc0ac3ec6c1dbe221db0b6a47`. Canonical Atenea remains clean
and synchronized at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`;
production, preview and Beautips return HTTP 200; required AX42 services and
backup timers are active; RAID remains `3/3 [UU]`; rootless slots remain
`3/0/0/3`. No deployment, migration, production record, attachment ownership,
retained content, route, credential or service changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.11-closed-v3-serialization`;
the SHA-256 of its `SHA256SUMS` is
`10a21bfcd0ec852fe0ddc47abf24a3aedc7fb97ffa47bda84c15e84799002852`.

Task 2.12 is complete and change progress is `26/83`; the exact resume point
is task 2.13. Atenea commit
`e16287d037298d9b909eeac9e77f8187b5dc3955` closes the backend denial and
authorization coverage matrix for the real Atenea attachment contract.

The HTTP boundary now proves unauthenticated web and mobile attachment list,
content, multipart upload and image-bearing turn submission all return `401`.
Attachment ownership/conflict failures map to `409` and individual/combined
size failures map to `413` without disclosing worker identity, storage identity
or filesystem paths. The service matrix covers same-session ordered success,
empty and duplicate selection, expired content, individual and aggregate size,
unsupported image type, partial/foreign/inconsistent ownership, conflicting
idempotency and absent immutable retry bindings. Every rejection occurs before
dispatch or additional persistence.

The final isolated PostgreSQL V62 matrix passed `107/107` tests in 21 seconds
under a 300-second timeout across twelve exact controller, authorization,
admission, persistence, idempotency, retry, manifest and serialization classes.
Its deliberate foreign composite binding was rejected by the V62 database
constraint and rolled back atomically. The uniquely named PostgreSQL fixture
was removed after the run.

The implementation branch is clean and published with tree
`f1ee9dafdf33934236e2da593f62ea39f58b86d3`. Canonical Atenea remains clean
and synchronized at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production,
preview and Beautips return HTTP 200; required AX42 services and backup/health
timers are active; RAID remains `3/3 [UU]`; rootless slots remain `3/0/0/3`.
No deployment, migration, production record, retained content, route,
credential or service changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.12-backend-coverage-matrix`;
the SHA-256 of its `SHA256SUMS` is
`970c1fd09bcac49045c3e07b567e157ba2d966975053507850cc00f50cbbe5ac`.

Task 2.13 is complete and change progress is `27/83`; the exact resume point
is task 3.1. Atenea closure commit
`fe9ac3fa2095069d99bf29db1c4c78e5ab850fa8` publishes the completed backend
contract slice without changing its accepted tree.

The final focused backend run passed `158/158` tests across twenty exact V62,
upload, admission, authorization, turn, atomic persistence, idempotency, retry,
manifest and v1/v2/v3 serialization classes in 29 seconds. The complete Maven
backend suite then passed `612/612` tests across 96 classes in 70 seconds from
a clean target and a new empty PostgreSQL 16 database migrated through V62.

Two earlier complete-suite attempts were retained transparently as sanitized
harness diagnostics. The first reused the focused database and lacked the
legacy integration workspace. The second used a fresh database and proved the
remaining `400` responses were the correct fail-closed result of starting the
application with `/repos` while the legacy test fixture creates repositories
beneath `/workspace/repos`. A third new database, clean target and the fixture's
exact application workspace root passed without any source relaxation or
contract change.

All uniquely named PostgreSQL containers and the exact task-created workspace
were removed. The implementation branch is clean, published and synchronized
at the closure commit with tree
`f1ee9dafdf33934236e2da593f62ea39f58b86d3`. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers remain active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.
No production deployment, schema, row, content, credential, route, service or
unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-2.13-complete-backend-suite`;
the SHA-256 of its `SHA256SUMS` is
`c32aa634eebb9454dacf17fad43b3f0ed9716ea06470781e4e069a4680c89f64`.

Task 3.1 is complete and change progress is `28/83`; the exact resume point is
task 3.2. Programme/worker commit
`851c70abb20541cc7c145b568ae10c0fe7f6d06c` adds the separate authenticated
`GET /v1/capabilities/real-project-attachment` endpoint in source.

The closed response contains exactly protocol version, worker identity, healthy
state, project identities, storage scopes and server time. It advertises only
`real-project-attachment/v1`, canonical project `atenea` and storage scope
`REAL_SESSION`; an unauthenticated request receives `401`. The existing base
health response remains exactly seven keys and the existing stored-attachment
public response remains exactly fourteen keys. No path or write authority is
introduced by the capability response.

Python compilation and the final attachment worker suite passed `13/13` in
three seconds under 120-second timeouts. The generated bytecode cache was
removed and the source branch is clean, published and synchronized with tree
`52842f6a2cbfb1b9cf9892008c679e9674e9fdaa` before this ledger update.

The candidate was not installed and the AX42 attachment service was not
restarted. Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers remain active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.1-real-attachment-capability`;
the SHA-256 of its `SHA256SUMS` is
`c6ec64d9f4f0a43be91da2c6a5139b0166197e501353b9a48bb703d8894e6038`.

Task 3.2 is complete and change progress is `29/83`; the exact resume point is
task 3.3. Programme/worker commit
`96dab152c1873bd19564c0eaa5fad794e7cdcb57` implements exact real attachment
write ownership.

A real PUT now requires a canonical remote WorkSession UUID, explicit
`syntheticFixture=false`, project identity `atenea`, workspace identity derived
exactly from the configured worker plus remote session, and storage scope
`REAL_SESSION`. Legacy decimal session identities, missing ownership, Beautips
or another project, inconsistent worker/workspace, foreign scope and synthetic
requests carrying real ownership are rejected before any content is retained.

The three real ownership fields are written only to the private sidecar. The
common v1 response omits them and reveals no filesystem root. Legacy synthetic
store callers remain source-compatible by normalizing absent private fields to
null, while any supplied partial or ambiguous ownership still fails closed.
The synthetic deletion proof now creates a fully owned real attachment and
confirms it remains intact.

After two transparent test corrections for legacy fixtures that lacked the new
normalized fields or attempted an intentionally obsolete unowned real write,
the final worker suite passed `15/15` in three seconds under a 120-second
timeout. Rejected ownership cases left zero retained content. The source branch
is clean and published with tree
`fb9d1b854d30b73576d6ffbe0f55adb99c4f8496` before this ledger update.

The candidate was not installed and no service was restarted. Canonical Atenea
remains clean at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production,
preview and Beautips return HTTP 200; AX42 attachment/AgentRun services and
health/backup timers remain active; RAID is `3/3 [UU]`; rootless slots remain
`3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.2-exact-real-put-ownership`;
the SHA-256 of its `SHA256SUMS` is
`fc21f2d9921b2fbc48cae8a4390b2b87dff8d98f0c9579312fc11a0a3a57ab59`.

Task 3.3 is complete and change progress is `30/83`; the exact resume point is
task 3.4. Programme/worker commit
`482897ef9633cbb5d53bf8c391050e79f47425d7` adds the explicit rollback-reader
and real-content deletion-preservation proofs.

An extended real sidecar is reopened through a restarted store and the unchanged
base v1 metadata/content methods. Both return the original common public
metadata and exact content while omitting all three private ownership fields;
the sidecar bytes remain identical before and after both reads. This proves the
additive private fields do not require rewrite or change the v1 read response.

The authenticated base v1 DELETE route is then called with exact synthetic
confirmation against a real attachment. It returns `403`, and both the content
and sidecar remain byte-identical. Existing deletion behavior still succeeds
only for exact synthetic ownership. The focused worker suite passed `17/17` in
four seconds under 120-second timeouts; generated bytecode was removed. The
source branch is clean and published with tree
`35c688c8c89e7dfed1bce60cc4c7ff779643bf7d` before this ledger update.

The candidate remains uninstalled. Canonical Atenea is clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers are active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.3-base-reader-delete-preservation`;
the SHA-256 of its `SHA256SUMS` is
`a5ae1859a9cf87f7035b3c0fe1df62582f0e7757871b3e67f828e1b19f08cf9d`.

Task 3.4 is complete and change progress is `31/83`; the exact resume point is
task 3.5. Programme/worker commit
`a0f58ad0320716d7da9b58ddf339045e9b6a71ab` adds the closed
`project-codex-v3` request schema, exact semantic bounds and durable ordered
attachment fingerprint behavior.

V3 is accepted only for canonical Atenea ownership and extends the existing v2
profile by exactly one ordered `attachments` array. It admits one to four
distinct canonical UUIDs, PNG/JPEG/WebP only, 16 MiB per image and 32 MiB
combined, with each entry restricted to UUID, media type, byte count and
lowercase SHA-256. Empty, partial, duplicate, non-image, over-bound, foreign or
authority-bearing input is rejected before execution state or a process exists.

The durable proof persists a two-image request, reloads `WorkerState` and shows
that identical replay returns the same execution. Reordering those references
changes the canonical request fingerprint and reuse of the dispatch identity is
rejected while the existing durable state remains byte-identical. The existing
v1/v2 request and project runner behavior remains compatible. The focused
AgentRun, session-operation contract and runner suites passed `68/68` in 5.928
seconds under a 120-second timeout.

The source-only candidate remains uninstalled and does not advertise v3 before
the bounded runner path is complete. Programme/worker tree
`d39139e2447539a61596e0ddf1e3b5305fb072ca` is clean and published; the Atenea
implementation branch remains clean at
`fe9ac3fa2095069d99bf29db1c4c78e5ab850fa8`. Canonical Atenea is clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; AX42 attachment/AgentRun services and health/backup timers are
active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.4-project-codex-v3-contract`;
the SHA-256 of its `SHA256SUMS` is
`cdcc2f9a61f572c3a64bddd055261a10268182fcce2d9c3e570b68ae677b8c55`.

Task 3.5 is complete and change progress is `32/83`; the exact resume point is
task 3.6. Programme/worker commit
`c1d6eafcd2bfddcbdfc4ee27bfa2eb2133750807` binds the canonical Atenea runner
configuration to the non-caller root `/srv/atenea/attachments-v1` and verifies
each retained image before process creation.

For v3 only, the runner derives every path from canonical session and attachment
UUIDs. Root, session and attachment directories must be non-symlink owned mode
`0700`; private sidecar and content must be single-link regular owned mode
`0600` and are opened no-follow. The exact sidecar binds the attachment service
protocol and worker plus canonical project, session, workspace, storage scope,
UUID, type, byte count and SHA-256. The content size, digest and PNG/JPEG/WebP
signature are reverified from the same opened file. No caller filename, path,
root, URL or storage identity is accepted.

One exact synthetic retained image validates without changing bytes or modes.
Project, session, workspace, type, size, sidecar digest, content digest,
permission and partial-metadata conflicts all fail before `Popen`, and both
retained files remain byte-identical. The source-only runner deliberately keeps
image delivery unavailable until task 3.6 provides the bounded materialization.
The Beautips adapter retains its old configuration and explicitly rejects v3.
The focused runner, AgentRun, Beautips and session-operation suites passed
`75/75` in 13.444 seconds under a 120-second timeout.

Programme/worker tree `0f60053b72755611f9e29729803e5ca5971a171b` is clean and
published. The installed runner remains byte-identical to its previous
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`
version, so no candidate was installed. Canonical Atenea is clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; AX42 attachment/AgentRun services and health/backup timers are
active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.5-retained-image-verification`;
the SHA-256 of its `SHA256SUMS` is
`5af7647eb23deea0e8dea5fd7be0b712d97c320ee6e5b7bc25c852f62e41488e`.

Task 3.6 is complete and change progress is `33/83`; the exact resume point is
task 3.7. Programme/worker commit
`114cdef2d81dabb3c4131d247f477b9a8b94c7a5` adds ordered runtime image
materialization, individual read-only Bubblewrap exposure and the closed v3
result contract.

After retained verification, each image is recopied and reverified into the
canonical execution UUID directory beneath `/run/atenea/codex-images`. That
directory is owned by the unprivileged execution identity at mode `0700`; every
derived position/UUID/type copy is mode `0600`. Source filenames never
participate. The namespace creates only the empty runtime directory chain and
read-only binds each exact copy; neither the retained attachment root nor a
retained content path appears in the command.

New turns receive one ordered fixed `--image` argument before stdin. Resumed
turns receive the same ordered flags after the `resume` subcommand and before
the exact thread UUID and stdin. The installed Codex 0.145.0 parser accepts both
forms. A two-image synthetic proof checks copy order, ownership modes, mount
sources, argument order, absence of retained paths, unchanged source bytes and
an empty execution boundary after the successful context. The worker also
requires a result summary matching the exact workload kind, and the new closed
v3 result schema validates. Exhaustive terminal cleanup and stale reconciliation
remain task 3.7. The focused suites passed `76/76` in 13.509 seconds under a
120-second timeout.

Programme/worker tree `b50a1c402d16b20da8415264d8c70acd14a99c09` is clean and
published. The installed runner remains byte-identical to its previous
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`
version, so no candidate was installed. Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; AX42 attachment/AgentRun services and health/backup timers are
active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.6-ordered-image-materialization`;
the SHA-256 of its `SHA256SUMS` is
`85ab9b36da1fb396cc2c10aa65b6bcf2816d26f0a22e24942658a990b7083f52`.

Task 3.7 is complete and change progress is `34/83`; the exact resume point is
task 3.8. Programme/worker commit
`4bba01e558129bc34184d8dae3ede653905ce3a4` adds identity-checked terminal
cleanup and startup reconciliation for the image materialization boundary.

The managed materialization context records the exact created device/inode,
derived path, media type, size and digest. Its `finally` path removes only the
complete matching file set from the exact `0700` execution directory. Success,
forced failure, timeout, cancellation/interruption and explicit runner exit all
leave the synthetic runtime boundary empty and the retained sources unchanged.
A replaced inode or changed content fails closed, remains untouched and produces
only the sanitized materialization rejection.

Worker startup first resolves a persisted uncertain project execution to
terminal failure without duplicating its turn, then sends the root runner a
closed projection containing only execution ID, state and v3 attachment
references. The runner uses a two-pass scan: exact absent and terminal paths are
removed; non-terminal paths are retained; unlabelled, foreign or ambiguous
candidates cause rejection before any otherwise removable candidate changes.
The mediator result is closed and any nonzero ambiguous count prevents the
worker scheduler from starting. The focused suites passed `82/82` in 13.528
seconds under a 120-second timeout.

Programme/worker tree `f1326a7c7ef3b6b42e7d27be1d4074b7c6a747af` is clean and
published. The installed runner remains byte-identical to its previous
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`
version and the installed materialization root remains absent, as expected
before task 3.10. Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; AX42 attachment/AgentRun services and health/backup timers are
active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.7-exact-materialization-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`479ede60f1479c73393603ee49ead1149f1008502597ef917b0dd48a64049027`.

Task 3.8 is complete and change progress is `35/83`; the exact resume point is
task 3.9. Programme/worker test commit
`bcdb8c6333484aa994779af5338acedebc047cad` adds the complete retained-image
fail-closed denial matrix without changing the accepted implementation.

Fifteen isolated generated cases cover missing sidecar, missing content,
modified content, symlinked content, symlinked sidecar, partial sidecar,
unlabelled sidecar, foreign sidecar, ambiguous extra authority, invalid content
mode, invalid sidecar mode, invalid directory mode, over-bound sidecar,
over-bound file declaration and over-bound attachment count. Each case captures
a complete lstat-based tree fingerprint after arranging the invalid fixture,
executes the exact validation with a mocked process boundary, observes a
sanitized rejection, proves zero `Popen` calls and obtains the identical tree
fingerprint afterward. The runner therefore neither repairs, adopts, rewrites
nor deletes rejected retained state. The full focused slice passed `83/83` in
13.374 seconds under a 120-second timeout.

Programme/worker tree `8a073d00db71c5173e10757c4e50d35856fedfba` is clean and
published. The installed runner remains byte-identical to its previous
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`
version, so the candidate remains uninstalled. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; AX42 attachment/AgentRun services and health/backup timers are
active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.8-retained-image-denial-matrix`;
the SHA-256 of its `SHA256SUMS` is
`2a82d7499204229f455a74b93f9ad7ea724664ad1e8f29971da8e8ff16fc7be4`.

Task 3.9 is complete and change progress is `36/83`; the exact resume point is
task 3.10. Programme/worker commit
`a89989686011fb25a3c0576b87e25ae96e80deb5` proves the complete image
execution lifecycle without changing the accepted runtime implementation.

New-thread and exact resumed-thread cases each invoke the project runner once
and return the expected terminal thread projection. An identical request after
durable state reload returns the same execution with zero additional runner
calls, while a reordered manifest under the same dispatch identity is rejected
without execution. Timeout requests terminate the process group once and
remove their exact materialization. Existing cancellation, interruption,
service-start reconciliation and stale-path cases prove that terminal state is
not duplicated and that absent/terminal paths are cleaned, active paths remain
and ambiguous paths block all mutation.

The final focused AgentRun, project runner, Beautips adapter and session
operations slice passed `85/85` tests in 13.497 seconds under a 120-second
timeout. Every accepted terminal case left the synthetic materialization root
empty and retained source bytes unchanged. The source tree
`02177bd0b89e7312c542dba08580045202162ffa` is clean, published and
synchronized before this ledger update.

The candidate remains uninstalled. The installed runner retains SHA-256
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`
and `/run/atenea/codex-images` remains absent. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers are active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`. No
deployment, migration, production record, retained content, route, credential,
service or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.9-image-execution-lifecycle`;
the SHA-256 of its `SHA256SUMS` is
`ee5388ee9c2244c261c8176c647994db1486c1302975728ba405b1544b87788f`.

Task 3.10 is complete and change progress is `37/83`; the exact resume point
is task 3.11. Programme/worker commit
`80bd5e9008dc4c8475f13577cde28f4b4377379f` updates the versioned AgentRun
installation, verification, rollback and systemd sandbox contracts in source.

The generated canonical Atenea configuration now contains the sole fixed
attachment root `/srv/atenea/attachments-v1` under an exact top-level schema.
Foreign or additional root authority is rejected. The installer pins the
reviewed worker and project-runner SHA-256 values, installs only the normal and
fixed reconciliation sudo commands, and verifies the exact configuration,
binaries, units, modes and owners.

The AgentRun service receives the retained root read-only and adds only
`/run/atenea/codex-images` to its existing write paths. A separate root oneshot
creates the controlled parent and root only when absent, then verifies exact
`root:atenea` ownership and `0750`/`0710` modes. Existing, foreign-owned,
symlinked or otherwise ambiguous paths fail closed and are never repaired or
adopted. The oneshot remains active for the worker lifetime and is recreated
through the fixed dependency after reboot. Rollback verifies every boundary,
stops only the two exact services and preserves all boundary content.

The task-specific installer/sandbox/rollback test passed in 0.73 seconds. The
focused AgentRun, runner, Beautips and session-operations suite passed `85/85`
in 13.599 seconds under a 120-second timeout. Both systemd templates passed an
isolated parser check after replacing only locally unavailable AX42 executable
paths with `/bin/true`; static tests separately pinned the real commands and
unit hashes. The accepted source tree
`c0a08cec93c2540d828fe475158a86e03da66d4a` is clean, published and
synchronized before this ledger update.

The candidate remains uninstalled: its helper and materialization root remain
absent. The installed runner retains SHA-256
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`.
Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers are active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`. No
deployment, migration, production record, retained content, route, credential,
service or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.10-versioned-install-sandbox`;
the SHA-256 of its `SHA256SUMS` is
`8b8abdbbacdb741fdb697c79c5c93c77001d60e6bf62e22be40a5631bf62bc0d`.

Task 3.11 is complete, phase 3 is closed and change progress is `38/83`; the
exact resume point is task 4.1. Completed programme/worker source commit
`8c96ec76240d2ba14ef1a4ded7fccde42829139a` has tree
`bd765445276ed387e1a0da2fe916bd609e8a2ac8`.

Two independent clean worker clones at that commit and two independent clean
Atenea input clones at `fe9ac3fa2095069d99bf29db1c4c78e5ab850fa8`
each ran the same sorted 31 top-level worker test entrypoints with a 900-second
timeout per entrypoint. Both passes completed `31/31` with zero nonzero exit
codes in 529 and 540 seconds. Their normalized index/name/exit SHA-256 is
identically
`0ab4a2870682148a634587c670de8f1b1ec2625c864f78ec493c13da1f38d8d3`.
The 19 unittest reports inside each pass totalled 190 tests per pass, excluding
the separate shell assertions.

The closure exposed one stale fail-closed trust pin before the accepted runs.
The Beautips installer still selected the adapter and shared base-runner
digests from before tasks 3.5-3.7. Commit
`8c96ec76240d2ba14ef1a4ded7fccde42829139a` changes only those two expected
digests to the already reviewed source. Focused installer/session tests passed,
the fix was published, and both complete passes restarted from new clean clones.
An earlier harness attempt that omitted the runtime adapter's required explicit
synthetic Atenea root was also discarded transparently; neither attempt reached
an install or external resource.

Attachment and AgentRun protocols, Atenea and Beautips runners, install and
rollback, project/runtime, ownership and browser cleanup, backup, session and
database lifecycle all passed twice. The source clones were clean before and
after removing only generated bytecode. All task-created clones, logs, visual
fixtures and wrapper were removed. Known test directories are zero; the two
pre-existing browser processes kept the same identity fingerprint; local
Docker retained its six pre-existing containers with stable container,
network and image identities across the accepted passes.

The candidate remains uninstalled: its helper and materialization root are
absent, and the installed runner retains SHA-256
`d15c78b09fcf048f7968168861ed976dd054b038168548b7216781568d1126f0`.
Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment/AgentRun services and health/backup
timers are active; RAID is `3/3 [UU]`; rootless slots remain `3/0/0/3`. No
deployment, migration, production record, retained content, route, credential,
service or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-3.11-complete-worker-slice`;
the SHA-256 of its `SHA256SUMS` is
`c205216f47c9d7385539729f8a763aa64ca438e574a1a2998e763be0be286c55`.

Task 4.1 is complete and change progress is `39/83`; the exact resume point is
task 4.2. Atenea commit
`59f55e27f703e6858c501aaabb07125bb88183f4` has tree
`a65bf945dfcc854a75430a409bd07bd3f8ed2d44` and is clean and published on
`codex/activate-atenea-real-worksession-attachments`.

The web client now types the complete capability projection, caller-owned
upload idempotency identity, caller-owned stable turn request identity, exact
ordered attachment IDs and immutable historical turn attachment metadata. The
HTTP layer copies caller order without sorting or deduplicating it and does not
regenerate either identity during dispatch. The existing text-only path uses
an empty explicit attachment selection; persistence across an uncertain UI
submission remains deliberately assigned to task 4.5.

The production TypeScript/Vite web build passed in 4 seconds under a
600-second timeout, transforming 1,583 modules. The task has no rendered or
styling change, so real desktop/mobile Playwright validation begins with the
visible composer changes and is consolidated by tasks 4.9 and 4.10. Strict
OpenSpec validation passed.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment, preview and AgentRun services plus
health/backup timers are active; RAID is `3/3 [UU]`; rootless slots remain
`3/0/0/3`; the candidate helper and materialization root remain absent. No
deployment, migration, route, service, production record, retained content,
credential or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.1-typed-web-clients`;
the SHA-256 of its `SHA256SUMS` is
`a0d29366ce3f59e38585ac741aa8cb59e81e51c65b75e3d57f7c7d1cee8ab147`.

Task 4.2 is complete and change progress is `40/83`; the exact resume point is
task 4.3. Atenea commit
`5ba98287547bce4b51d53057304f6167889d206b` has tree
`334b0095b981f65ed7e77603dd0690e5ea5e15e6` and is clean and published.

The misleading standalone enabled-looking attachment panel and its primary
upload action are removed. A compact capability-aware status now belongs to
the fixed conversation composer, distinguishes checking, ready and fail-closed
text-only states, displays the server-owned message and next action, and keeps
`Enviar` as the sole primary action. The same-screen review also corrected the
inherited dark empty-state title that had been unreadable on the dark
conversation surface.

The production web build passed in 4 seconds under a 600-second timeout. A
fresh isolated Chromium acceptance used only synthetic empty-conversation,
profile and capability data and passed in 3 seconds. At `1440x900` and
`390x844`, data and DOM assertions proved the ready state, zero standalone
panel, one primary action and visible Send button. Geometry and manual PNG
inspection proved zero horizontal overflow, no clipped composer, readable
hierarchy, consistent spacing and responsive stacking. Browser, contexts,
pages and temporary Vite were closed.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; AX42 attachment, preview and AgentRun services plus
health/backup timers are active; RAID is `3/3 [UU]`; rootless slots remain
`3/0/0/3`. No rollout or unrelated mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.2-composer-capability`;
the SHA-256 of its `SHA256SUMS` is
`e5baec734b019c30d2525dd5bba27af044df40058cb19816e3d2594e20c54ee2`.

Task 4.3 is complete and change progress is `41/83`; the exact resume point is
task 4.4. Atenea commit
`81f819fa86d2a205e8e84de67c6192501d3d79aa` has tree
`449b154385064b6ee98b8dc394e559f844a07c0d` and is clean and published.

The composer now offers one secondary `Añadir imagen` file picker and accepts
PNG, JPEG or WebP clipboard images on the message textarea. Both paths use the
same bounded validation and multipart upload, supply one explicit UUID v4
idempotency identity per upload, retain picker/paste order and automatically
append each successful immutable result to the pending selection. Unsupported,
over-file, over-turn and over-quota inputs stop before dispatch. A paste during
an in-flight upload receives an actionable wait-and-retry message instead of
being silently lost.

The production web build passed in 4 seconds. Isolated Chromium acceptance
used only synthetic empty-conversation data and performed one picker upload
followed by one clipboard upload in each viewport. All four requests were
multipart, carried four distinct UUID identities and produced the expected
`1 imagen lista` then `2 imágenes listas` DOM states. At `1440x900` and
`390x844`, the clip stayed secondary, Send remained the sole primary action,
there was no horizontal overflow or clipping, and manual PNG inspection found
clear hierarchy and responsive stacking. Browser and temporary Vite processes
were closed.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; RAID is
`3/3 [UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.3-picker-paste`;
the SHA-256 of its `SHA256SUMS` is
`3f0dfd5616fc34c55d8f5fc43f627d3f1091e691321da556b555df16de8cbd50`.

Task 4.4 is complete and change progress is `42/83`; the exact resume point is
task 4.5. Atenea commit
`9fac3d785a4023e96a782e53e97d9e01fb25c4e8` has tree
`b786e201d7467d498ee9e631bae36b221d3434c6` and is clean and published.

The composer now renders at most four pending-image chips with a local
thumbnail, bounded filename and byte size, explicit uploading/ready/error state
and an exact remove action. Object URLs are revoked on removal, session change
and unmount. No storage path, worker identity or implementation detail is
projected.

The production web build passed in 4 seconds. Isolated Playwright acceptance
proved uploading, one ready and one rejected chip, exact rejection removal,
then four ready thumbnails and four remove actions. Desktop `1440x900` and
mobile `390x844` had no horizontal overflow or clipped composer; manual PNG
inspection confirmed readable state colors, bounded metadata and responsive
four-column/two-column layouts. Send remained the sole primary action. Browser
and temporary Vite processes were closed.

Production, preview and Beautips returned HTTP 200; required AX42 services
were active and RAID remained `3/3 [UU]`. No rollout or unrelated mutation
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.4-image-chips`;
the SHA-256 of its `SHA256SUMS` is
`2180cc9942af77b3ce69e1bb433b4ca78528ebffc2e9e8cf877c9834efb261b5`.

Task 4.5 is complete and change progress is `43/83`; the exact resume point is
task 4.6. Atenea commit
`81eeee5d6be406c1380983ca3fcbbb4b951a2e8d` has tree
`3ee9c96675757d7fd6bbbbd2e194614f01c9b4b2` and is clean and published.

Turn submission now sends the caller-owned stable request UUID and exact ready
attachment IDs in displayed order. A failed or uncertain outcome retains text,
selection, previews and UUID for an identical safe retry. Synchronous duplicate
submits are blocked. Editing text, adding or removing an image starts a new
logical request identity. Draft state is cleared only when the returned
conversation contains an operator turn with the exact normalized message and
ordered attachment projection.

The production build passed in 5 seconds. Synthetic Playwright acceptance at
`1440x900` and `390x844` proved 504 preservation, visible retry, identical UUID
and order, one request for two synchronous submit events, exact accepted-turn
confirmation and accepted clearing. Screenshots mask textarea content. There
was no overflow or clipping and all browser/Vite processes closed.

Entry operational checks retained production, preview and Beautips at HTTP
200, required AX42 services active, RAID `3/3 [UU]` and slots `3/0/0/3`. No
rollout occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.5-safe-turn-retry`;
the SHA-256 of its `SHA256SUMS` is
`eee0e718caf7c16c18433fe8c5cd46139534addb45e42b71eb778a508a838f1d`.

Task 4.6 is complete and change progress is `44/83`; the exact resume point is
task 4.7. Atenea commit
`256a69c19bc47bf3214fbfd9941e482249220740` has tree
`0a946bf91c25257b21faecf176d5410968e69e55` and is clean and published.

Each historical turn now renders only its immutable bound-image projection:
bounded filename, size, ordinal and authenticated download. Download uses the
session-scoped authenticated API and never exposes retained bytes or worker
paths in conversation JSON. Turns with an empty projection render no attachment
surface, so later text-only turns cannot inherit an earlier image.

The production build passed in 4 seconds. Synthetic empty-text Playwright
acceptance at `1440x900` and `390x844` proved two bindings on the exact owner
turn, zero lists on the following Codex and text-only operator turns, bearer-
authenticated download with the bounded filename and no horizontal overflow.
Visual inspection passed and browser/Vite processes closed.

Entry operational checks retained production, preview and Beautips HTTP 200,
required AX42 services active, RAID `3/3 [UU]` and slots `3/0/0/3`. No rollout
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.6-historical-bindings`;
the SHA-256 of its `SHA256SUMS` is
`369f3d66033f9d8b88a3a65325eefb768d025e78dd36981aa9fac8057675ba30`.

Task 4.7 is complete and change progress is `45/83`; the exact resume point is
task 4.8. Atenea commit
`bffe7613ac45013ff0b7f73be011afe6d5e488ac` has tree
`53a5ed2eed3f0a081f9078518e38a58f42491589` and is clean and published.

The composer now names legacy-session, ownership-invalid, exhausted-quota,
worker-unavailable and worker-incompatible blocks directly while preserving
the server-owned reason and next action. Global-disabled and project-disabled
remain concise text-only states. Client validation errors no longer inherit the
green ready indicator: over-file and over-turn states use an explicit error
state and direct the operator to choose, remove or continue with text as
appropriate. The singular one-image limit is grammatical.

The production build passed in 4 seconds. Isolated empty-conversation
Playwright acceptance covered all eight task states at `1440x900` and
`390x844`: six fail-closed capability blocks, over-file and over-turn. Every
title and action was visible in the first relevant viewport; blocked states had
zero picker, the over-turn case retained its first valid selection, Send stayed
the only primary action, and inspected PNGs had no clipping, overlap or
horizontal overflow. Browser and temporary Vite processes closed.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; all RAID
arrays remain `[UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated
mutation occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.7-actionable-blocked-states`;
the SHA-256 of its `SHA256SUMS` is
`a11e6cd7c4754fdd43a635690ba57d90f05501d16e6440e94b2e673320602abd`.

Task 4.8 is complete and change progress is `46/83`; the exact resume point is
task 4.9. Atenea commit
`fca3175161e3bb184aa6f88c725a508fca22cca1` has tree
`d60f906d91f0e6193432b39ac86e0b6b26f69d1c` and is clean and published.

The web repository now owns a typed Playwright component/API suite with one
worker and finite test, action, navigation, web-server and outer process
timeouts. Its 17 tests cover picker and clipboard upload through the same
multipart API, caller-owned upload UUIDs, automatic selection, exact order,
exact removal, stable retry identity, clearing only after exact acceptance,
historical reload, all seven blocked capability reasons and every local type,
file, count, turn-byte and remaining-quota rejection used by the composer.

After correcting two ambiguous test locators that legitimately matched both
the state summary and chip error, the complete suite passed `17/17` twice; the
final run included the dedicated TypeScript test compile and completed in 16
seconds. The canonical production web build passed in 4 seconds and transformed
1,583 modules. The suite generates no trace, video or screenshot and its
temporary runner metadata is outside the repository.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; RAID is
`3/3 [UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.8-web-component-api-tests`;
the SHA-256 of its `SHA256SUMS` is
`3ab0944779d1494fd64cdc227a4ff2c60dd225d84a0961fb64eb295187537e0d`.

Task 4.9 is complete and change progress is `47/83`; the exact resume point is
task 4.10. The production web bundle was rebuilt from clean published Atenea
commit `fca3175161e3bb184aa6f88c725a508fca22cca1`, tree
`d60f906d91f0e6193432b39ac86e0b6b26f69d1c`.

Playwright loaded that production bundle and passed 16 data/DOM/visual
scenarios: ready, global-disabled, project-disabled, worker-unavailable,
uploading, selected, over-limit and accepted-turn at both `1440x900` and
`390x844`. It proved one exact accepted historical binding, zero pending
selection after acceptance, blocked picker omission, ready picker presence,
one primary action and exact document/viewport widths. State and textarea
geometry remained ordered and entirely inside the viewport.

All 16 screenshots were inspected. Hierarchy, state colors, next-action copy,
secondary attachment action, bounded chips and responsive stacking are clear;
there is no overlap, clipping or horizontal overflow. Accepted-turn text is
masked in retained PNGs. Browser/context/page cleanup ran in `finally`, the
preview server was stopped explicitly and Playwright-safe returned idle with
zero related process.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; RAID is
`3/3 [UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.9-production-visual-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`a012b21c539a918381e43677d8d01d458dd8e163c4361c8889ede99cdfdd6875`.

Task 4.10 is complete, phase 4 is closed and change progress is `48/83`; the
exact resume point is task 5.1. The complete web slice consists of eight clean,
published Atenea commits from `59f55e2` through
`fca3175161e3bb184aa6f88c725a508fca22cca1`; local and remote candidate refs
match exactly at tree `d60f906d91f0e6193432b39ac86e0b6b26f69d1c`.

The final permanent component/API suite passed `17/17` in 18 seconds including
its TypeScript compile, and the canonical production build passed in 4 seconds
with 1,583 modules. Repository and local temporary-root audits found zero PNG,
JPEG, WebP, trace, video, ZIP, Playwright report, test-result or `.last-run`
residue outside the accepted AX42 evidence roots. No browser or Vite process
remained.

The task 4.7, 4.8 and 4.9 evidence sets each passed full checksum verification;
their `SHA256SUMS` hashes remain respectively
`a11e6cd7c4754fdd43a635690ba57d90f05501d16e6440e94b2e673320602abd`,
`3ab0944779d1494fd64cdc227a4ff2c60dd225d84a0961fb64eb295187537e0d`
and `a012b21c539a918381e43677d8d01d458dd8e163c4361c8889ede99cdfdd6875`.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; RAID is
`3/3 [UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred. Sanitized closure evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-4.10-completed-web-slice`;
the SHA-256 of its `SHA256SUMS` is
`7e2bfba087fe84db8ef4e0ed4b4483b067229d52b655d39a4207a807a1ac819e`.

Task 5.1 is complete and change progress is `49/83`; the exact resume point is
task 5.2. All focused cross-repository suites passed `273/273` from clean,
published source: V62/backend `163/163` across twenty exact classes, web
component/API `17/17`, WorkSession attachment protocol `17/17`, AgentRun worker
`54/54` and Atenea project runner `22/22`.

The backend ran against a new uniquely named PostgreSQL 16 container and empty
workspace/upload roots. Its V62 tests migrated a new schema through all 62
migrations and also exercised V61-to-V62. The worker suites ran with Python
bytecode disabled. Expected database integrity and worker rejection logs came
only from passing fail-closed negative cases; no contract mismatch or source
change was required.

The synthetic container's exact immutable ID and task label were revalidated
before stop/removal. The empty roots, Maven target, Playwright result and all
browser/Vite/bytecode residue were removed; the pre-existing shared test
database was not touched.

Candidate Atenea remains clean and published at
`fca3175161e3bb184aa6f88c725a508fca22cca1`; canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services/timers are active; RAID is
`3/3 [UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.1-focused-integration`;
the SHA-256 of its `SHA256SUMS` is
`6190a7306b273a4b3c4de2f2965ab14db68908b0f8f29fee2d4cfd4b1e3fc52d`.

Task 5.2 is complete and change progress is `50/83`; the exact resume point is
task 5.3. Two independent clean Atenea source/workspace pairs at
`fca3175161e3bb184aa6f88c725a508fca22cca1`, tree
`d60f906d91f0e6193432b39ac86e0b6b26f69d1c`, ran the canonical backend,
production web-build and package Playwright entrypoints. Backend passes were
`612/612` in 74 and 73 seconds, builds transformed 1,583 modules in 7 and 6
seconds, and web passes were `17/17` in 17 and 18 seconds. Outer timeouts were
1,800 seconds for backend and 900 seconds for each web step.

Two independent clean worker clones at
`385334a9671dd10732d575e644d5ca19c1d43f81`, tree
`d0aa4d2af442232f0821edbaefa09785879a034d`, and independent Atenea inputs ran
the same sorted 31 top-level entrypoints with a 900-second bound per entry.
Both passed `31/31` in 471 and 479 seconds. Each contained 19 unittest reports
totalling 190 tests, excluding separate shell assertions. Their normalized
index/name/exit SHA-256 is identically
`0ab4a2870682148a634587c670de8f1b1ec2625c864f78ec493c13da1f38d8d3`.

Pre-acceptance diagnostics exposed only two browser-wrapper invocation
preconditions and a Docker Compose client reap issue under a pseudo-terminal;
accepted passes restarted from clean clones after bounded preflight. No product
change was required. Task-owned containers, networks, volumes, clones, visual
roots and browser processes were removed. The pre-existing local test database
and app-server containers retained their exact immutable IDs and original
running/exited states.

Canonical Atenea remains clean and synchronized at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200. Required AX42 services and backup/health timers are active,
all three RAID arrays remain `[UU]`, and rootless slots remain `3/0/0/3`. No
rollout, migration, route, production record, credential, retained attachment,
service or unrelated resource changed. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.2-complete-suites`;
the SHA-256 of its `SHA256SUMS` is
`00f5baccd357c2f3f09ee2ab6643025b6bfa576376b73442bc44c24292d9b2c5`.

Task 5.3 is complete and change progress is `51/83`; the exact resume point is
task 5.4. Atenea test commit
`cade6a8c3576c9e060b7197398dd87bb70e5e919`, tree
`eea5c97fa1d1ff3a8d473e5d4b5c0d11b9f58c9e`, adds permanent persistent and
closed-request acceptance for one synthetic image turn, one same-thread image
continuation with a different explicit image, and one later text-only
continuation.

The database scenario proves exactly three operator turns, three AgentRuns,
two immutable bindings and two retained source attachments. The first two runs
each retain one distinct exact manifest. All three preserve the same remote
WorkSession and workspace; the second and third preserve the same persisted
Codex thread. The third run has attachment count and bytes zero, a null manifest
and an empty historical attachment projection.

Captured worker requests are respectively `project-codex-v3`,
`project-codex-v3` and `project-codex-v2`. The second request includes only its
new explicit attachment, while the third contains no attachments array or
singular attachment, image or path authority. The final backend/serialization
slice passed `26/26` in 25 seconds against a new empty PostgreSQL 16 fixture
migrated through V62; project-runner and AgentRun-worker suites passed `76/76`
in 9 seconds; the permanent web suite passed `17/17` in 18 seconds.

The exact synthetic database ID and label were revalidated before removal.
Maven output, browser processes, Playwright results and bytecode residue are
zero. Candidate Atenea and programme/worker Git are clean and published.
Canonical Atenea remains clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and Beautips
return HTTP 200; required AX42 services and timers are active; all RAID arrays
remain `[UU]`; rootless slots remain `3/0/0/3`. No rollout or unrelated
mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.3-explicit-continuations`;
the SHA-256 of its `SHA256SUMS` is
`baa57f6422a9fb0c4984eecd20a24e3b0adf4700d687f54805bd6cb5cdeff714`.

Task 5.4 is complete and change progress is `52/83`; the exact resume point is
task 5.5. Atenea commit
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`, tree
`2bd29fa979372175a603d7a3b3ead1ae0745f76d`, adds a permanent two-context
backend restart acceptance.

The first complete Spring context persisted one image-bearing operator turn,
immutable binding, terminal AgentRun, ordered manifest, Codex thread and result
turn. It then closed its JPA pool and application context. A newly started
context over the same V62 database replayed the request as after response loss
and returned the exact original turn, run and result IDs. Turn, run, binding and
attachment counts, manifest, storage identity and thread were unchanged;
selection/upload validation and remote dispatch were not invoked again.

The safe retry contract also retained its origin turn, exact manifest, binding,
attachment, storage/workspace identities and execution profile while adding
only the required linked retry run. Worker reconstruction retained one
execution identity and byte-stable terminal progress/result, and duplicate
dispatch returned that execution. Attachment-store reconstruction returned
identical metadata/content; a base-v1 reader reopened the extended real sidecar
without rewriting it. Runner new/resumed/recovery paths retained one process
and zero temporary materialization residue.

The final backend slice passed `28/28` in 27 seconds against a new empty
PostgreSQL 16 fixture migrated through V62. Attachment service, AgentRun worker
and project runner passed `17/17`, `54/54` and `22/22` respectively (`93/93`)
in 12 seconds. The exact database ID/label was revalidated before removal;
Maven output, browser processes and bytecode residue are zero.

Candidate/programme Git are clean and published. Canonical Atenea remains clean
at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; production, preview and
Beautips return HTTP 200; required AX42 services and timers are active; RAID
remains `[UU]`; slots remain `3/0/0/3`. No real service was restarted and no
rollout or unrelated mutation occurred. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.4-restart-retry-continuity`;
the SHA-256 of its `SHA256SUMS` is
`c8a1f76bf5dea5b2cf8f848f33286da0ea893e13df0aa17a32b9bc0b09bd8a70`.

Task 5.5 is complete and change progress is `53/83`; the exact resume point is
task 5.6. The permanent fail-closed matrix covered all 11 required classes:
unlabelled, partial, foreign-project, foreign-session, foreign-workspace,
modified-content, symlink, unsupported, duplicate, expired and ambiguous.

Runner fixtures were fingerprinted before rejection using relative identity,
mode, owner, group, size and file SHA-256 or symlink target. Every complete
before/after snapshot remained identical and no Codex process started. Backend
validation stopped duplicates before repository/worker access, retained
foreign/partial/expired rows, rejected unsupported kind/type before worker
access and never invoked deletion for metadata or content mismatch. AgentRun
protocol denial created no execution state; attachment-service denial retained
no partial content and never adopted or removed foreign/ambiguous content.

Backend validation passed `12/12` in 12 seconds. Project runner, AgentRun worker
and WorkSession attachment service passed `22/22`, `54/54` and `17/17`
respectively (`93/93`) in 11 seconds. Maven output, task fixture containers,
known temporary roots, bytecode and browser processes are zero. No product
change was required.

Candidate Atenea remains clean and published at
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`; programme/worker Git is clean
and published at `0ad4ec45b3d4cca2f5f27b8ed61daa8cdeaef35d`; canonical Atenea
remains clean at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production, preview
and Beautips return HTTP 200; required AX42 services/timers are active; RAID
remains `[UU]`; slots remain `3/0/0/3`. No rollout or unrelated mutation
occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.5-fail-closed-fixture-matrix`;
the SHA-256 of its `SHA256SUMS` is
`c7d3fe5fe374d3a574d5f5e754fdad4e338687bf24f71fbd3ed10c680d2cb134`.

Task 5.6 is complete and change progress is `54/83`; the exact resume point is
task 5.7. The runner exercised forced failure, timeout,
cancellation/interruption and closed process exit after exact image
materialization. Every path emptied its execution-owned materialization in
`finally`, while retained source and sidecar bytes remained identical.
New-thread, resumed-thread and timeout execution created one bounded process,
terminated the timeout process group and retained zero temporary image.

The AgentRun worker cancelled only the exact execution while an unrelated one
completed, and restart reconciliation refused to duplicate an uncertain
process. Attachment storage rejected integrity/type failure with zero indexed
content and zero `.incoming` residue. Project runner, AgentRun worker and
WorkSession attachment service passed `22/22`, `54/54` and `17/17`
respectively (`93/93`) in 11 seconds. Actual Codex-execution and browser-process
counts were `0 -> 0`; known test/materialization roots and bytecode are zero.

Candidate Atenea remains clean and published at
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`; programme/worker and canonical
Atenea remain clean. Production, preview and Beautips return HTTP 200; required
AX42 services/timers are active; RAID remains `[UU]`; slots remain `3/0/0/3`.
No real process or service was cancelled/restarted and no rollout or unrelated
mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.6-terminal-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`a994288aa1f3124596c9f05992379921dca2919dfe284fb1b27ed10ca41c868a`.

Task 5.7 is complete and change progress is `55/83`; the exact resume point is
task 5.8. The V62-aware rollback backend is fixed at commit
`409a2f3222a5fd61b693a4154d3de7820ff850e9`, tree
`8ceb0a40f152866aee5b64e0e73b9d2da2a9efb5`. It understands the expanded V62
schema and exact remote-session read identity while predating image-bearing
turn dispatch. Global, synthetic and real create/bind admission default false.

With creation disabled, the rollback service rejected upload before worker
creation while retained metadata list and integrity-checked download remained
available. Exact real ownership read through the remote WorkSession UUID;
ambiguous ownership failed before worker access. There is no new image-binding
submission surface in the rollback source. Admission, service and controller
tests passed `25/25` in 11 seconds, and V62 migration tests passed `3/3` in 6
seconds against one labelled disposable PostgreSQL 16 fixture.

The exact legacy base-v1 attachment service at
`6baa87488ca32967f16790e0e607b74908320856` reopened content written by the
extended real-compatible store. Listed metadata and downloaded bytes matched,
private ownership fields were not exposed, and the full sidecar hash was
identical before and after the legacy read. The exact database fixture and
temporary worktrees were removed after identity validation; Maven output,
Python bytecode and browser processes are zero.

Candidate Atenea remains clean and published at
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`; programme/worker and canonical
Atenea remain clean. Production, preview and Beautips return HTTP 200; required
AX42 services/timers are active; RAID remains `[UU]`; rootless slots remain
`3/0/0/3`. No service was restarted and no rollout, production migration,
WorkSession, route, credential, retained real content or unrelated resource
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.7-rollback-read-compatibility`;
the SHA-256 of its `SHA256SUMS` is
`8b32c062818f137a43f8134ab73c1a90bc14f39b31712c1615cb51cd849a26c8`.

Task 5.8 is complete and change progress is `56/83`; the exact resume point is
task 5.9. The privacy audit covered candidate/programme source, the bounded
attachment, AgentRun and preview journals, and every retained file beneath the
active change evidence root without emitting journal values.

The source audit found two inherited HTTP request loggers that could expose
attachment/session or execution identities through the request line. Published
worker commit `ae03da7baa7049f9ed7d8b338ea88a5d8bf6faf8`, tree
`eabf14cc605fbbe7942b5fc87222325af75a90cd`, replaces both with a fixed
timestamp plus `http_request` event, adds exact non-exposure tests and updates
the canonical installation fingerprint. Attachment and AgentRun suites passed
`18/18` and `55/55`; all 14 Python worker programmes passed `173/173` with one
declared skip in 103 seconds; install/rollback validation passed.

The evidence audit removed the exact 30 generated visual PNG files after
recording only basename, viewport dimensions, byte count and SHA-256 in seven
text manifests. It redacted six attachment-path values in four known text
files. All 11 affected evidence directories were verified against their old
immutable seals before mutation, then resealed; the programme's individual
ledger hashes above now reference the sanitized seals. The old-to-new map is
retained in task 5.8 evidence.

The final audit covers 324 files and returns zero prompt values, answer values,
screenshot bytes, thumbnail data, credentials, tokens, attachment-storage
paths, Codex identity values, risky filenames or environment dumps. Every
change-level `SHA256SUMS` verifies. Focused backend response tests passed
`22/22`; the complete attachment web suite passed `17/17`; no Playwright,
browser or bytecode process/residue remains.

Candidate Atenea remains clean and published at
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`; programme/worker and canonical
Atenea remain clean and published. Production, preview and Beautips return
HTTP 200; required AX42 services/timers are active; RAID remains `[UU]`;
rootless slots remain `3/0/0/3`. No candidate service was installed/restarted
and no rollout, production migration, WorkSession, route, credential, retained
real attachment or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.8-privacy-audit`;
the SHA-256 of its `SHA256SUMS` is
`4bc0a61a9d74cf8ae2940c48e7f62c0f88338c20a2da088deb0d82c7657e751f`.

Task 5.9 and the complete integrated synthetic phase are complete. Change
progress is `57/83`; the exact resume point is task 6.1.

Exactly 56 accepted evidence directories through task 5.8 each passed their
individual `SHA256SUMS`. Their checksum-manifest identity, sealed file count
and sealed byte count are fixed in one non-circular aggregate ledger, itself
covered by the task 5.9 seal. The complete retained evidence set remains at
zero privacy findings after the task 5.8 sanitation.

Candidate Atenea remains clean and published at
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59`; programme/worker is clean and
published at `c9b5b822ef0880132a209f2ede1b4548ed9e9ef7`; canonical Atenea remains
clean at `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. The installed attachment
and AgentRun worker hashes remain the pre-rollout versions and differ from the
candidate hashes.

Production, preview and Beautips return HTTP 200; required AX42 services and
backup/health timers are active; all RAID arrays remain `[UU]`; rootless slots
remain `3/0/0/3`. No production backup restore, V62 migration, candidate
image/service installation, restart, rollout, route, WorkSession, credential,
retained real attachment or unrelated mutation occurred.

Sanitized phase-closure evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-5.9-synthetic-phase-seal`;
the SHA-256 of its `SHA256SUMS` is
`45296c4e788e6d7509cb9a1f1c45960310999362a7b87ffc3433b14e970ac25e`.

Task 6.1 is complete. Change progress is `58/83`; task 6.2 is the exact
resume point.

A PostgreSQL 16 custom-format production backup was created atomically under
mode `0600`, retained in the protected backup boundary and identified by
SHA-256 without recording its production endpoint or any row value. Its
catalog is readable and it restored successfully into an exact task-labelled
PostgreSQL 16 container whose data directory is tmpfs. The disposable fixture
uses an internal-only Docker network, publishes no port and has no persistent
mount. Its immutable container and network identities were recorded before
use and remain intact for the V62 compatibility proof in task 6.2.

The restored snapshot reports V61, all 61 successful Flyway rows and 50 public
tables. Production remained live and accumulated three additional rows after
the snapshot; only aggregate counts and digests were retained, and the normal
post-snapshot drift was not mistaken for restore failure. The dump restore and
catalog checks returned exit 0 within finite bounds.

Programme, candidate and canonical Git remain clean and synchronized at their
accepted commits. Production and preview return HTTP 200; the AX42 attachment,
preview and AgentRun services plus backup/check/health timers are active; RAID
remains `3/3 [UU]`; rootless slots remain `3/0/0/3`, including unchanged
Beautips. No migration, deploy, restart, gate, route, WorkSession, credential,
attachment content or unrelated resource changed.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.1-protected-backup-isolated-restore`;
the SHA-256 of its `SHA256SUMS` is
`ed5199a718b98f22ad9db55b6fe06d14f8682f6d7cb8737dd10fb7dda709923d`.

Task 6.2 is complete. Change progress is `59/83`; task 6.3 is the exact
resume point.

The candidate backend image was built from exact commit
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59` and the V62-aware rollback image
from exact commit `409a2f3222a5fd61b693a4154d3de7820ff850e9`.
Each image carries its full source identity. Both builds returned exit 0 within
finite bounds.

Against the isolated restored snapshot, the first candidate start advanced
Flyway exactly from V61/61 to V62/62. A second candidate start remained
V62/62, proving the migration no-op, and the exact rollback image then started
healthy and read V62/62 unchanged. All starts used the global attachment gate
false plus empty synthetic and real-project allowlists. Aggregate checks found
zero policy revisions, turn attachments and attachment-bearing AgentRuns.
Every short-lived backend fixture was removed by exact immutable ID after its
check; the two labelled images and the exact task 6.1 database/network remain
for task 6.3 fingerprinting and cleanup.

Production remains V61 and production plus preview return HTTP 200. Candidate,
programme and canonical Git remain synchronized; no production migration,
deploy, service restart, gate, route, WorkSession, credential, attachment
content or unrelated resource changed.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.2-v62-image-compatibility`;
the SHA-256 of its `SHA256SUMS` is
`158b3dacad3e6b713b06160722b47ca3e94799a56fc43d092c5c55a610e76b33`.

Task 6.3 is complete. Change progress is `60/83`; task 6.4 is the mandatory
rollout-authorization stop gate and exact resume point.

The candidate backend/web release remains content-addressed by image
`sha256:208af4c93512a07f4bcd8f8a4fa9bc1c47421b1e4213dc9ab228a56c654c5277`,
with embedded application JAR SHA-256
`6d2e1b3ce6b8d1f705e68acd95c6ff2f8e800ddd651253572043211c6da6bf53`
and committed static-tree digest
`e24754b3b6a2a2fd5a4ec17ccfe05a70ab7bac77c9c3cfb7d828f1f1e1a87bf2`.
The exact compatible backend rollback remains image
`sha256:00afca3569c7367f1df27c4ddd380c4c643fb4045e649964c55d870cb9e46c84`.
Both have version-addressed release tags and exact source commit/tree labels.

A deterministic protected candidate worker/storage bundle contains exactly
the reviewed AgentRun worker, attachment service, runner, installers, unit
templates, mediators and v3 schemas from programme commit
`d9fc09398282da9d160d3357304896c73887e256`; its SHA-256 is
`74c98790489b57a12c0806df30253c4dd7c7ad706c36b1cdf605cd5601d40a37`.
A separate protected pre-rollout rollback bundle contains only the six exact
installed code/unit artifacts and explicit absence metadata; its SHA-256 is
`ca8532832f9e24dc2544d22cd17c4dba8944b51b2be7f4628bd1eae144953411`.
Both are root-owned, mode `0640`, and carry verified internal checksum
manifests. No configuration, state, credential or retained content is bundled.

The task 6.1 tmpfs database container and internal network were removed only
after their IDs, labels and sole membership matched the registered ownership.
No task 6.1–6.3 container, network or volume remains. The protected production
backup and the candidate/rollback release artifacts are intentionally
retained.

Production remains V61; production and preview return HTTP 200; required AX42
services/timers are active; RAID remains `3/3 [UU]`; rootless slots remain
`3/0/0/3`, including unchanged Beautips. Git remains clean and synchronized.
No production migration, deployment, restart, feature configuration,
credential, route, WorkSession, attachment content or unrelated resource
changed.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.3-immutable-artifacts-fixture-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`e81b0260da63e4ec772ae812ac96af97857066a4dd165ae0c00d2e776a094ff5`.

Task 6.4 is complete. Change progress is `61/83`; task 6.5 is the exact
resume point.

At `2026-08-02T12:50:11Z` the operator supplied a new separate explicit
authorization scoped to the V62 production migration, backend/web artifact,
exact AX42 attachment and AgentRun services, out-of-band private credential
and initially disabled attachment configuration. The operator message itself
is not copied into evidence. This authorization does not enable any project or
widen scope to Beautips, Android attachments, retention deletion or unrelated
resources.

The authorization preflight reconfirmed clean synchronized programme,
candidate and canonical Git; production V61; zero production attachment rows;
zero non-terminal AgentRuns; absent/default-false attachment gate environment
entries; exact candidate/rollback artifacts and protected backup; HTTP 200 for
production and preview; active AX42 services/timers; RAID `3/3 [UU]`; and
rootless slots `3/0/0/3`. A first read-only query used generic terminal names
and counted the 76 successful historical runs; comparison with the source enum
corrected the query to the accepted zero non-terminal result. No mutation
occurred during the gate.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.4-rollout-authorization`;
the SHA-256 of its `SHA256SUMS` is
`8a83888c1be35f29c4e6c131fc48a12a8bae2ea28c5a48469647648f51b1e1cd`.

Task 6.5 is complete. Change progress is `62/83`; task 6.6 is the exact
resume point.

The AX42 attachment identity was rotated atomically from fresh 256-bit random
material and transferred directly over bounded SSH into the control host's
protected secret boundary. Its value and digest were never emitted or retained
in evidence. Opaque equality passed; worker ownership/mode is
`0640 root:atenea` and control-host ownership/mode is `0640 jose:atenea`.

The byte-exact former production Compose was retained under mode `0600`. The
new Compose validates against the protected environment and declares the
attachment gate false, both synthetic and real-project allowlists empty, the
tailnet service location and exactly one read-only secret mount on only the
production backend. Its SHA-256 is
`610c60251e42eb1e42e9dfba2c3de68710e4a17fd1e7b5500fc70b0f0e84df29`.

The current production backend was recreated alone with `--no-deps --no-build`
to make the mount real before candidate rollout. It retained exact former image
`sha256:bb983725de00ca3cba29f45ffce34c071943d3a6dc25923cdcc4730b300a3a7f`,
returned HTTP 200 in 15 seconds and has restart count zero. The application
identity can read and validate the mounted file without outputting it; all
running rootful containers expose exactly one such mount. Production and
preview remain healthy, unrelated rootful and rootless inventories are
unchanged, production remains V61 and no AX42 service was yet restarted.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.5-private-channel-and-mount`;
the SHA-256 of its `SHA256SUMS` is
`c30ac1d39da94c2bd7dcea80b67647f4209c05f901468560f5778638431d361b`.

Task 6.6 is blocked and remains the first pending task. Change progress remains
`62/83`.

The final pre-install ownership check found the authoritative AX42
`project-codex-v1` configuration has selection and execution enabled with
exactly one structurally valid persisted canonical Atenea workspace. Its
sanitized configuration SHA-256 is
`d9878267d7b979197521a48d90789c593dd775ac3973f96dcf84e135f9f25b87`.
The reviewed candidate installer at SHA-256
`0bb94c9e8246abb1a8845697da410573f5d036684e025194a4fc701088f29846`
instead invokes `write_project_config false false '{}'` in its `apply` path
before restarting the AgentRun service. Executing it would silently replace
the existing one-workspace routing registry with an empty disabled registry.
That conflicts with the exact persisted ownership and the no-routing-change
contract.

In accordance with the fail-closed divergence rule, neither candidate
installer ran. V62 was not applied, the candidate backend was not deployed and
no AX42 service was restarted. No automatic merge, adoption, repair or manual
installation bypass was attempted. Production remains V61 on exact former
image `sha256:bb983725de00ca3cba29f45ffce34c071943d3a6dc25923cdcc4730b300a3a7f`;
production and preview return HTTP 200; required AX42 services are active;
rootless slots remain `3/0/0/3`; RAID remains `3/3 [UU]`.

Task 6.6 can resume only after a reviewed candidate change preserves the exact
existing project configuration during installation, with focused regression,
complete worker-suite, install/rollback and immutable-artifact verification
repeated before deployment.

Sanitized blocking evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.6-blocked-persisted-routing-preservation`;
the SHA-256 of its `SHA256SUMS` is
`f932806f0bee48aa9c542e32183d24306008ec18f30069dc5b8de382fcf2dcc1`.

Task 6.6 is complete. Change progress is `63/83`; task 6.7 is the exact
resume point.

The blocking installer was corrected and published through programme commits
`843367e8e7bbb4334c1ccd2aeed4ad37cb7eddf6`,
`c93c19073af031b441fdbae9d69dc01d8aa4253d` and final deployable commit
`4ea60175e77c2fca8a5f888fe50a54b7b6010c19`. The final installer accepts only
the exact legacy or attachment-aware Atenea configuration schemas, validates
complete persisted ownership before mutation and preserves an existing file
byte for byte. Existing text routing remains available under the legacy form;
image-bearing work remains fail-closed until explicit attachment activation.
The shared runner change also updates only the exact known Beautips adapter
predecessor while AgentRun is stopped, preserving Beautips compatibility
without enabling its attachment capability.

Focused AgentRun, runner and installer tests passed. Two independent clean
clones at the final programme commit ran all 31 sorted worker entrypoints with
900-second per-entry limits and passed `31/31` in 385 and 416 seconds. The
candidate and rollback archives were rebuilt deterministically, passed every
internal checksum and are retained under a new immutable root-owned release.
Their SHA-256 values are respectively
`2e847db4283bad3c1f9d7e65bcecdef611fe946dfca813e4b1697bcb761e6445`
and `d3bdaf5f4c89bda187642d8f52d7ec088a01e2e2a4fe3c01af1b8f1c7c3474ac`.

The exact former production Compose is retained mode `0600`. The candidate
definition SHA-256 is
`87f5c1251dd093cb5a7ef8ba3ee466937c458906d12f98a8bec3d4aebdab7336`.
Only the production backend was recreated, reaching HTTP 200 in 15 seconds on
candidate image
`sha256:208af4c93512a07f4bcd8f8a4fa9bc1c47421b1e4213dc9ab228a56c654c5277`
with restart count zero. Production migrated to V62 while the global gate
remained false and both allowlists remained empty.

Only the exact AX42 attachment and AgentRun services were installed/restarted;
no project runtime restarted. The persisted routing configuration retained
SHA-256 `d9878267d7b979197521a48d90789c593dd775ac3973f96dcf84e135f9f25b87`,
one workspace and its enabled text-routing state. Both services are enabled
and active with zero restart count, exactly two tailnet listeners and no
wildcard listener. Storage, materializations and AgentRun state contain zero
files. Policy revisions, real attachment rows, turn bindings and
attachment-bearing AgentRuns are all zero.

Production, preview and Beautips return HTTP 200. Required AX42 services and
timers are active, rootless slots remain `3/0/0/3`, RAID remains `3/3 [UU]`,
and canonical/candidate Git remain clean and synchronized. No project was
activated, no credential value was emitted and no foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.6-routing-preserving-deployment`;
the SHA-256 of its `SHA256SUMS` is
`59b1a5ce3571d08eead911f2558ff48ec15c0740b285fbf38287e76a41f0bf93`.

Task 6.7 is complete. Change progress is `64/83`; task 6.8 is the exact
resume point.

Two aggregate production fingerprints separated by a bounded 20-second
observation window matched exactly. Both contain zero attachment rows and
logical bytes, turn bindings, attachment-bearing AgentRuns and attachment
policy revisions. AX42 retains zero attachment-storage entries, AgentRun state
files and materializations. All ten pre-existing WorkSessions retain null
attachment policy revision and are therefore ineligible.

Without exposing the selected existing session identity, the deployed
capability, list and download paths each returned the expected authentication
boundary rather than a missing route or server error. The exact candidate
commit's retained list/download and public-shape compatibility remains proven
by sealed task 5.7 evidence with manifest SHA-256
`8b32c062818f137a43f8134ab73c1a90bc14f39b31712c1615cb51cd849a26c8`.
Production contains no attachment row whose content could be read during this
disabled gate.

The backend remains on the exact V62 candidate image with restart count zero.
The routing configuration retains SHA-256
`d9878267d7b979197521a48d90789c593dd775ac3973f96dcf84e135f9f25b87`;
both AX42 services remain enabled/active; rootless slots remain `3/0/0/3` and
RAID remains `3/3 [UU]`. Production, preview and Beautips return HTTP 200. No
project runtime, gate, route, WorkSession or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.7-disabled-mode-production`;
the SHA-256 of its `SHA256SUMS` is
`563a640ffdb121bf896216eaeee78c5f00db8e3999dadef94b87de8fb80b49c3`.

Task 6.8 is complete, phase 6 is closed and change progress is `65/83`; task
7.1 is the exact resume point.

A bounded GET-only request from the control host authenticated successfully to
the private AX42 capability. The normalized response is exactly protocol
`real-project-attachment/v1`, worker `ax42-01`, healthy true, sole project
identity `atenea` and sole storage scope `REAL_SESSION`. A fixed invalid
credential returned 401. No upload, metadata read or content read was
attempted, and no credential value or digest entered evidence.

The task also corrects one earlier storage-accounting statement. Task 6.6 and
6.7 used an unprivileged `find` with denied-path errors discarded and described
the worker attachment store as empty. That statement is superseded; no file
was created or removed by the mistaken observation. V62 production does have
zero real attachment rows and logical bytes, bindings, image AgentRuns and
policy revisions, and there are zero materializations. Separately, AX42
correctly retains eight pre-rollout legacy attachments across two UUID session
directories and one base-v1 numeric session directory. All eight attachment
identities, file/directory owners and modes are exact, no unknown or incoming
entry exists and every file predates the rollout.

The complete retained-storage metadata fingerprint before and after a repeated
authenticated capability GET is identically
`9170ec9ace7e935599ab02fb6841df92ee9bc333c403592f58bf06829f8407b6`.
The historical bytes were not read, adopted, deleted or rewritten. This
preservation is required by the compatibility/no-deletion contract and does
not make any old WorkSession eligible for new attachment creation.

All attachment gates and allowlists remain disabled/empty. Routing retains
SHA-256 `d9878267d7b979197521a48d90789c593dd775ac3973f96dcf84e135f9f25b87`;
incoming storage, materializations and AgentRun state are empty; rootless slots
remain `3/0/0/3`; RAID remains `3/3 [UU]`; production, preview and Beautips
return HTTP 200. No project, WorkSession, route or foreign resource changed.

Sanitized evidence, including the superseding storage-accounting correction,
is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-6.8-authenticated-capability-seal`;
the SHA-256 of its `SHA256SUMS` is
`da6daf6c17e1ee487b5a431320ce6cac79add23cdf2503c3aaf87c45b435e987`.

Task 7.1 remains the first pending task and change progress remains `65/83`.
The complete read-only technical preflight passes, but activation is blocked
before any gate change pending separate explicit operator authorization.

Programme, candidate and canonical Git are clean and synchronized at
`caeb2c78b02aad2b40659a232b4e12c36a5971dd`,
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59` and
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production is V62 with all
attachment gates disabled and both allowlists empty. The 76 succeeded, 14
failed and one cancelled historical AgentRuns are terminal; non-terminal
AgentRuns are zero. Worker AgentRun state, incoming storage and materialization
state are empty.

The exact runner, attachment worker and Beautips adapter fingerprints match
the deployed bundle. Retained-storage metadata retains SHA-256
`9170ec9ace7e935599ab02fb6841df92ee9bc333c403592f58bf06829f8407b6`.
The canonical `atenea-worker-health.timer`, `atenea-external-backup-v1.timer`
and `atenea-external-backup-check-v1.timer` are enabled/active and all three
paired services last completed with result success and exit 0. The backup
sandbox includes the fixed attachment root read-only. SSH, Tailscale and UFW
are active, RAID is `3/3 [UU]`, and production, preview and Beautips return
HTTP 200.

The authorization accepted for task 6.4 expressly scoped the production
rollout to initially disabled configuration. It does not separately authorize
enabling the global/project gates or performing the real operator canary. The
change contract requires that activation authorization to be explicit. No
gate, route, WorkSession, service, runtime, retained content or foreign
resource was changed during this preflight.

Sanitized blocking evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.1-blocked-activation-authorization`;
the SHA-256 of its `SHA256SUMS` is
`b420b4e35d57d3456d0f8ef3e517a910c828f2de00d78bdee3420d444db5d920`.

Task 7.1 is complete. Change progress is `66/83`; task 7.2 is the exact
resume point.

The operator separately and explicitly authorized enabling the global real
attachment gate, then enabling only canonical `atenea`, and creating one new
eligible WorkSession. Beautips and every other project remain outside that
authorization. The authorization was accepted only after repeating the full
read-only technical preflight.

Programme, candidate and canonical Git are clean and synchronized at
`524ffb4ade1a3aa3f23385655b638ed79cf653ef`,
`99bda7d1a93f9aa5e9f6e3e8f9f0365cef36ce59` and
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. Production remains on V62 with
the global gate false and both allowlists empty. All 91 historical AgentRuns
are terminal and no attachment row, logical byte, turn binding or policy
revision exists in production.

The exact AgentRun runner, attachment worker and Beautips adapter hashes match
the deployed candidate. Both worker services are enabled, active and running
with zero restarts. The corrected live state path contains one expected
durable registry with 50 terminal executions, zero validations and zero
non-terminal state; incoming and materialization state is empty. The
previously accepted authenticated capability seal remains the
storage compatibility authority and the retained metadata fingerprint remains
`9170ec9ace7e935599ab02fb6841df92ee9bc333c403592f58bf06829f8407b6`.

Health and both external-backup timers are enabled/active with successful
paired service results. SSH, Tailscale and UFW are active, rootful Docker is
inactive, all three RAID arrays are `[UU]`, rootless slot counts remain
`3/0/0/3`, and production, preview and Beautips return HTTP 200. No gate,
WorkSession, runtime, route, retained content or foreign resource changed in
task 7.1.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.1-activation-authorization-accepted`;
the SHA-256 of its `SHA256SUMS` is
`41784d01a3c0ec88766a3beb15336ec79ec0b500210f3a6bc31342ba58934c73`.

Task 7.2 is complete. Change progress is `67/83`; task 7.3 is the exact
resume point.

The exact production Compose was retained mode `0600` with SHA-256
`87f5c1251dd093cb5a7ef8ba3ee466937c458906d12f98a8bec3d4aebdab7336`.
The atomically installed definition has SHA-256
`ed90865e76afca8c3ef8d917648d893e630025bc23d7f13404dcc4280483985f`
and changes only the global attachment gate from false to true. Both the
synthetic and real-project allowlists remain empty.

Only `atenea-backend-prod` was recreated, retaining immutable image
`sha256:208af4c93512a07f4bcd8f8a4fa9bc1c47421b1e4213dc9ab228a56c654c5277`,
reaching readiness in 13 seconds with restart count zero. Live configuration
confirms the global gate true and both allowlists empty. All nine observed
projects, including Atenea and Beautips, retain zero attachment policy
revisions and are therefore fail-closed.

Before/after aggregate production counts remain zero attachment rows, logical
bytes, turn bindings, attachment policy revisions and non-terminal AgentRuns.
The retained worker storage metadata fingerprint is identically
`95d7b4c6a9e5c3b3b47ebc2acdb06f391a12119dbf932c36acad64440e6985b1`;
the expected durable AgentRun registry contains zero non-terminal entries.
No retained content was read or changed.

The worker project configuration remains byte-identical. Both worker services
remain active with zero restarts, rootless slot counts remain `3/0/0/3`, all
three RAID arrays remain `[UU]`, and production, preview and Beautips return
HTTP 200. No WorkSession, route, project runtime or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.2-global-empty-allowlists`;
the SHA-256 of its `SHA256SUMS` is
`236b396402b62235f52d665b17ecd57d63b3e7f769a8db7f5687af273f9e4932`.

Task 7.3 is complete. Change progress is `68/83`; task 7.4 is the exact
resume point and requires the operator's real web interaction.

The exact global-only Compose was retained mode `0600` with SHA-256
`ed90865e76afca8c3ef8d917648d893e630025bc23d7f13404dcc4280483985f`.
The atomically installed definition has SHA-256
`ad292a88149ca1eeea5eb3c720c5fcb9153c2dd5facb289cd2b72891e719e29d`
and adds only canonical `atenea` to the real-project allowlist. The global gate
remains true and the synthetic allowlist remains empty. Only the production
backend was recreated on the same immutable image; it reached readiness in 14
seconds with restart count zero.

Before project activation, all seven prior Atenea WorkSessions retained null
policy. The reviewed worker mediator added the sole fixed attachment root while
preserving the registered workspace and clean Git. The normal authenticated
production API then closed the sole clean old open Atenea session and created
WorkSession `13`, remote session
`707c58a1-5105-45be-b7b7-bebd9bf8ab8e`. Authentication material and tokens
remained memory-only inside the backend, no value was emitted or written, and
logout returned 204.

The new WorkSession is `OPEN`, pinned to `ax42-01` with workload
`project-codex-v1`, and is the sole row carrying immutable policy revision
`atenea-real-attachments-v1`. It has zero turns and zero AgentRuns. The former
open session is `CLOSED`, retains null policy and reports capability
`BLOCKED/SESSION_NOT_ELIGIBLE`; the new session reports
`READY/NONE/COMPATIBLE`; Beautips reports
`BLOCKED/PROJECT_DISABLED` with null policy.

Before provisioning the new workspace, AX42's sole registration was resolved
as exact retained ownership of older WorkSession `11`, already `CLOSED`, not a
foreign resource. Database identity, worker config, clean Git, admission and
allocation matched. Its assigned containers, network, volumes, listeners and
runtime unit were all absent. Heavy then normal admission were released, its
allocation was retained under the canonical retired name with unchanged
SHA-256
`4ca527500e94573324a082cad6803b565bfec82a1fb5b52885853503af4b255b`,
and only that exact registration was removed.

An administrative direct activation attempt was rejected before mutation as
a foreign caller; absence of the new session root, admission and registration
was confirmed. The accepted retry used the exact `atenea-worker` privilege
chain and completed in 1.613 seconds. The new worktree is clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`; it owns slot 2 and heavy 1, one
allocation and the sole worker registration, but no runtime was started.

The final worker project configuration SHA-256 is
`413170ed2dff0067fe74fabeaa98e83bc04dd10083b522d5009c05bdcfb2e868`.
Attachment rows, logical bytes and bindings remain zero; the retained storage
metadata fingerprint remains
`95d7b4c6a9e5c3b3b47ebc2acdb06f391a12119dbf932c36acad64440e6985b1`.
Both worker services and all required timers remain active; rootless slot
counts remain `3/0/0/3`; all RAID arrays remain `[UU]`; SSH, Tailscale and UFW
remain active; rootful Docker remains inactive. Production, preview and
Beautips return HTTP 200. No unrelated project, route, runtime or foreign
resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.3-canonical-atenea-activation`;
the SHA-256 of its `SHA256SUMS` is
`dec649358ed24efe7c627c89c913595579a88e7515e0b6ab1ad23a114782832c`.

Task 7.4 is complete. Change progress is `69/83`; task 7.5 is the exact
resume point and was not started.

The operator signed in to the production web application, selected one
generated non-secret PNG through the real composer for WorkSession `13` and
confirmed its visible selected state. The evidence retains neither attachment
bytes nor the user-facing filename. No prompt was submitted.

Production records exactly one `OPERATOR_UPLOAD`/`IMAGE`/`image/png` attachment
of 42,499 bytes in `SESSION` retention and `REAL_SESSION` scope. Its SHA-256
matches the generated fixture and its canonical project, worker, remote-session
and workspace ownership match the eligible Atenea WorkSession. The session
still has zero turns, zero bindings and zero AgentRuns, so no dispatch or Codex
execution occurred.

The retained worker metadata fingerprint changed from
`95d7b4c6a9e5c3b3b47ebc2acdb06f391a12119dbf932c36acad64440e6985b1` to
`1abb194230581881b03f1f7fcbd182f5fcf6e2cb449eaf557a07b41478cc108c`,
accounted for by the expected private content/sidecar pair. Content, names and
private storage identities were not read or recorded. Temporary
materializations, runner processes and browser processes remain zero.

Both AX42 worker services remain enabled, active and running with zero
restarts; required health/backup timers remain enabled and active; rootless
slots remain `3/0/0/3`; RAID remains `3/3 [UU]`; rootful Docker remains
inactive. Production, preview and Beautips return HTTP 200. Canonical and
worktree Git remain clean at
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`. The global gate remains true,
the real allowlist remains exactly `atenea`, and the synthetic allowlist
remains empty. No unrelated project, route, runtime or foreign resource
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.4-real-web-selected-state`.
The SHA-256 of its `SHA256SUMS` is
`c6705a4892d5d0f15c9a1c12f510110a18d1dea5cc39b87f857e32bf885dd024`.

Task 7.5 is blocked and remains unmarked. Change progress remains `69/83`, with
task 7.5 still the exact resume point.

On the first operator Send attempt, the production conversation screen became
fully blank. The backend remained healthy and persisted exactly two new
immutable turns plus one terminal successful AgentRun, but the attachment
binding count remained zero. AgentRun `92` is `project-codex-v1` with attachment
count/bytes `0/0` and no manifest, rather than the required
`project-codex-v3` run with one exact binding. The retained real attachment
remains intact, unbound and without an AgentRun association. Prompt, response,
attachment and screenshot content were not read or retained.

The immutable production JavaScript asset has SHA-256
`84aa38dd2481933589c9770b0aa7b7c7788171c5478e884a084524871edcd12f` and
contains the reviewed `attachmentIds` submission and accepted-turn
confirmation paths. The evidence therefore locates the divergence at the
client submission/rendering boundary. A stale in-memory client or browser-side
exception is consistent with the blank screen, but neither is asserted as the
exact cause without a browser console/network trace.

Production, preview and Beautips continue to return HTTP 200. The backend and
both AX42 worker services remain active/running with zero restarts; temporary
materializations and runner processes remain zero. No retry, deletion,
adoption, session replacement, service restart or automatic repair was
performed. The existing canary state is preserved for review.

Sanitized blocking evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.5-blocked-unbound-submit`.
The SHA-256 of its `SHA256SUMS` is
`f38e8856269708bd942bc2a4c5399e2670caac65307f570394a29f872e8115cc`.

The operator explicitly authorized the reviewed clean-session recovery. Task
7.5 remains unmarked and progress remains `69/83`.

WorkSession `13` was closed through the normal authenticated API after its sole
AgentRun was terminal and both canonical and remote worktrees were clean. Its
real attachment, immutable turns/run, worktree and artifacts remain retained.
Only its exact `slot2/heavy1` admission was released; allocation SHA-256
`d5006a1c0707eb61af29999cb0291c3fae2078042cd3f6115e56b98d919d9df2`
was preserved under the canonical retired name, and only its exact worker
registration was removed. No runtime object or listener existed.

The same authenticated API created WorkSession `14`, remote session
`8497e4e4-951e-477a-b457-cf91d341eed8`, with attachment policy
`atenea-real-attachments-v1`. Authentication values and tokens remained
memory-only and both logout operations returned 204. The reviewed worker
mediator activated its exact branch and workspace in 1.64 seconds through the
`atenea-worker` privilege chain.

WorkSession `14` is the sole open Atenea session and sole active Atenea worker
registration. It reports `READY/NONE/COMPATIBLE`, owns `slot2/heavy1`, and has
zero attachments, turns, bindings, AgentRuns, runtime objects and temporary
materializations. Its worktree is clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`. Production, preview and Beautips
remain HTTP 200. The next action is manual web selection of the generated
non-secret PNG in session `14`; no prompt may be submitted before that receipt.

Sanitized recovery evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.5-recovery-clean-session`.
The SHA-256 of its `SHA256SUMS` is
`c9d7cc33b3bcd5e8044a8b3647ed6994a16c760f34fabcab8e2d3ecd76e8eece`.

The next manual Send reached the server with one exact selected attachment.
WorkSession `14` now has one attachment, two turns, one immutable binding and
one terminal successful AgentRun. Run `93` is `project-codex-v3` with attachment
count/bytes `1/42499` and manifest SHA-256
`d8f4977b555230f2812964650d4c878c3153d61dc68f4536033daa5bcb63d72f`.
Its retained attachment SHA-256 matches the generated fixture. AX42 has zero
materializations and runner processes after completion. Because the operator
text was accidental, semantic image understanding is not claimed and task 7.5
remains unmarked.

The client reported that `recentTurns` was undefined. Source comparison proved
the backend returns `CreateSessionTurnConversationViewResponse` as an outer
record whose `view` member contains the conversation envelope, while the web
client decoded the outer record as the envelope itself. Candidate commit
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d` fixes only that boundary and makes
the synthetic test server use the exact production response shape. The 17
attachment Playwright tests pass, the production web build passes, and rendered
desktop `1440x900` plus mobile `390x844` submission checks retain the accepted
turn/image, clear the composer and show no horizontal overflow.

Immutable candidate image
`sha256:ca076c3a615c7745c8a86fe7abd729123041bf9c38e529716892dd72c6dbc0c3`
was built from the exact published commit and is used by zero containers. Its
production rollout stopped before mutation because the live Compose mode is
`0664`, whereas accepted tasks 7.2/7.3 require `0600`. Compose content remains
the accepted SHA-256
`ad292a88149ca1eeea5eb3c720c5fcb9153c2dd5facb289cd2b72891e719e29d`
and owner `jose:jose`; the active backend remains on the prior immutable image,
running with zero restarts. Production, preview and Beautips remain HTTP 200.
No chmod, backup, Compose replacement or container recreation was attempted.

Task 7.5 is blocked and remains the first pending task at `69/83`. Resumption
requires explicit authorization to restore only the exact production Compose
mode to `0600`, deploy the exact candidate image and complete a controlled
semantic canary without retrying run `93`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.5-blocked-wrapper-compose-mode`.
The SHA-256 of its `SHA256SUMS` is
`4893feeb7e069e02d734bcffc5cbd9df519c95d8fcb383480365cf9c14fe6102`.

The operator explicitly authorized restoring only the production Compose mode
from `0664` to `0600`, deploying the exact response-wrapper fix and preparing a
new clean WorkSession. Task 7.5 remains unmarked at `69/83`.

After exact owner/content assertions, the Compose mode was changed to `0600`
without changing SHA-256
`ad292a88149ca1eeea5eb3c720c5fcb9153c2dd5facb289cd2b72891e719e29d`.
The candidate Compose then changed only the backend image reference, was
strict-validated against the protected environment and atomically installed
mode `0600`; its SHA-256 is
`d7f94b1e611fad6329cb66346cbe99eba91d79bdba30e19fda73e48b51abb4ba`.
The exact prior Compose remains as a mode-0600 rollback copy with its original
hash.

Only `atenea-backend-prod` was recreated. It reached readiness in 13 seconds on
immutable image
`sha256:ca076c3a615c7745c8a86fe7abd729123041bf9c38e529716892dd72c6dbc0c3`,
source commit `57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d`, with restart count zero.
The served JavaScript SHA-256 is
`8f7e89bc6ed0adf4a65a71cadb7585685cc87af2546a890ccdb78f147a3cb6b4`,
matching the candidate. The global gate remains true, the real allowlist
remains exactly `atenea` and the synthetic allowlist remains empty.

WorkSession `14` was closed through the normal authenticated API with its
attachment, binding, terminal v3 run, worktree and artifacts intact. Only its
exact `slot2/heavy1` admission was released; allocation SHA-256
`ebc691bec22ab966e887915e59817a014a2a6e7703eeaa27d8fa3a92b489fa86`
was retained under the canonical retired name, and only its exact registration
was removed.

The API then created WorkSession `15`, remote session
`c80c1e72-e34f-46b9-ba34-5a9a0c0ad2d7`; authentication values remained
memory-only and logout returned 204. The reviewed mediator activated its exact
workspace in 1.63 seconds. It is the sole open/registered Atenea session,
reports `READY/NONE/COMPATIBLE`, owns `slot2/heavy1`, and has zero attachments,
turns, bindings, AgentRuns, runtime objects and materializations. Its worktree
is clean at commit `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`.

Worker services and required timers remain active; rootless slots remain
`3/0/0/3`; RAID remains `3/3 [UU]`; rootful Docker remains inactive; SSH,
Tailscale and UFW remain active. Production, preview and Beautips remain HTTP
200. The next action is the operator's manual selected-state receipt in session
`15`; no prompt has been submitted there.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.5-authorized-wrapper-rollout-clean-session`.
The SHA-256 of its `SHA256SUMS` is
`e0d517a3f678292bb03c364569d6d3e7592fbf001fbf69e24ba74b9c0f682773`.

Task 7.5 is complete. Change progress is `70/83`; task 7.6 is the exact
resume point and was not started.

The operator submitted one bounded image-bearing instruction through the real
production web composer in WorkSession `15`. Production retains exactly one
42,499-byte `OPERATOR_UPLOAD`/`IMAGE`/`image/png` attachment, two turns, one
position-zero immutable binding and one AgentRun. Run `94` completed
`SUCCEEDED/SUCCEEDED` in 8.046 seconds as `project-codex-v3` with attachment
count/bytes `1/42499` and manifest SHA-256
`5fb7c7c421012c6b1194d9dbac9ade928e1e37b6a37978a769c2a6b72d3bd89e`.
There are zero non-terminal AgentRuns.

The AX42 durable execution registry independently contains exactly one
matching successful v3 execution, with one attachment and one terminal result.
Temporary materializations, browser processes and Codex processes are zero.
The operator's first post-submit view still held the older in-memory web bundle
and could not render the already persisted response. No retry was performed;
a hard refresh loaded the corrected production asset and the operator then
confirmed the expected title and non-secret marker understanding. Evidence
retains only those two semantic booleans, not the prompt, response, image,
filename, private storage identity or internal Codex identity.

The session worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`; its allocation SHA-256 remains
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`.
Both worker services remain active/running with zero restarts, backup/check and
worker-health timers remain enabled/active, rootless slot container counts
remain `3/0/0/3`, all three RAID arrays remain `[UU]`, and rootful Docker
remains inactive. Production, preview and Beautips return HTTP 200. The global
gate remains true, the real allowlist remains exactly `atenea`, the synthetic
allowlist remains empty, and no unrelated project, route or resource changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.5-final-real-image-canary`;
the SHA-256 of its `SHA256SUMS` is
`3028d878710350ccb9261525a64429e4899e7f3b8f792d389d422710d1fdaa99`.

Task 7.6 is complete. Change progress is `71/83`; task 7.7 is the exact
resume point and was not started.

The operator submitted one later text-only continuation through the same
production conversation in WorkSession `15`. The session now has four turns,
two terminal successful AgentRuns, but still exactly one retained attachment,
one immutable binding and one bound turn. Run `95` completed
`SUCCEEDED/SUCCEEDED` in 5.607 seconds with attachment count/bytes `0/0` and a
null attachment-manifest identity. No prompt or response content was selected
or retained.

The control plane correctly retains the base text workload identity while its
complete Codex profile is serialized to the worker's closed
`project-codex-v2` contract. AX42 durable state proves the continuation uses
the same remote WorkSession and workspace as the image run, its input thread
equals the prior result thread, its result preserves that thread, and its
workload has no `attachments` key. The two durable executions are exactly one
successful v3 image run followed by one successful v2 text run, with attachment
counts `1,0`; both have terminal results and there is no third execution.

The focused `RemoteWorkerClientTest` contract suite passes `22/22` with zero
failures or errors. Temporary materializations, browser processes and Codex
processes remain zero. The session worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`; allocation SHA-256 remains
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`.
Worker services and backup/health timers remain active, rootless slot container
counts remain `3/0/0/3`, all three RAID arrays remain `[UU]`, and rootful
Docker remains inactive. Production, preview and Beautips return HTTP 200; the
backend remains running with zero restarts and the protected Compose remains
mode `0600` with unchanged SHA-256. No unrelated project, route or resource
changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.6-text-only-continuation`;
the SHA-256 of its `SHA256SUMS` is
`bc09cf74364356a5e6ed2d8f7c87838f711ee66bf2a1d26cf457ad996e652cc8`.

Task 7.7 is complete. Change progress is `72/83`; task 7.8 is the exact
resume point and was not started.

With zero non-terminal AgentRuns, the production backend, AX42 attachment
service and AX42 AgentRun worker were restarted separately and in that order.
Only `atenea-backend-prod` was restarted; it returned HTTP 200 on bounded
readiness attempt 14 in 14 seconds, with zero restart-loop count, while preview
and Beautips remained HTTP 200. Production records immediately remained one
attachment, four turns, one historical binding, two AgentRuns and two distinct
result turns.

The attachment service then received an isolated bounded systemd restart. Its
PID changed, the AgentRun-worker PID remained unchanged, and the exact tailnet
listener returned on bounded attempt 2. An authenticated in-memory download
returned HTTP 200, exactly 42,499 bytes and SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`,
matching both the response digest and persisted identity. The credential never
entered output or evidence, and downloaded bytes were not retained.

The AgentRun worker was restarted only after reconfirming zero non-terminal
runs. Its PID changed, the attachment-service PID remained unchanged, and its
listener returned on bounded attempt 2. The durable execution-state SHA-256
remained byte-identical at
`7964895ca393c919fc265d78f64102c651344baa2c7286e7926fce1f1b4b42ff`.
Post-restart state remains exactly two successful worker executions—one v3
image run and one v2 text continuation—with attachment counts `1,0`, two
results, preserved thread continuity and no attachment key on the continuation.

A second final authenticated download after all three restarts reproduced the
same HTTP status, size, digest and SHA-256. Database identity remains exactly
four distinct turns, one position-zero binding, two distinct origins, results,
dispatches and remote executions, with no non-terminal run. Temporary
materializations, browser processes and Codex processes remain zero.

The session worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`; allocation SHA-256 remains
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`.
Worker services and backup/health timers are active, rootless slot container
counts remain `3/0/0/3`, RAID remains `3/3 [UU]`, rootful Docker remains
inactive, and production, preview and Beautips return HTTP 200. No project
runtime, route, unrelated slot or foreign resource changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.7-separate-service-restarts`;
the SHA-256 of its `SHA256SUMS` is
`3e9bfa4c24bbd78f77eeb9a9403f89f668dd317bb54d18e6fc1028c151c9fcb7`.

Task 7.8 is complete. Change progress is `73/83`; task 7.9 is the exact
resume point and was not started.

An authenticated bounded production rejection matrix exercised only exact
known identities. The pre-activation Atenea session reported
`SESSION_NOT_ELIGIBLE` and rejected upload with HTTP 409. The Beautips session
reported `PROJECT_DISABLED` and rejected upload with HTTP 409. A retained
attachment from a different Atenea WorkSession was rejected for a new turn
with HTTP 409, and a changed request reusing the accepted canary's idempotency
identity was also rejected with HTTP 409. The rejected attachment and every
real or foreign record remained intact; no rejected operation created a turn,
binding, AgentRun, dispatch or worker execution.

The complete pre/post structural fingerprints are byte-identical: WorkSessions
`a1990cfcf492ba4911fef8bbe330f24c`, attachments
`624668d9cec0a702d55673a1bb9fc732`, turns
`c66b3e23ea933cec217b79a4ae0dfaf1`, bindings
`ba0b31561cfd2a9cba03957f1df79acd`, AgentRuns
`074d53bf5e24353a7124d819448dd907`, attachment metadata
`79b061fe76c69a8d3701a10c20b1aac02f8d2e1a6cfba51666562e9252d6feb9`
and durable execution state
`7964895ca393c919fc265d78f64102c651344baa2c7286e7926fce1f1b4b42ff`.
The corresponding counts remain 3 attachments, 30 turns, 2 bindings, 17
AgentRuns, 22 retained attachment files and zero non-terminal AgentRuns.

Four bounded authentication diagnostics used during the matrix were all
explicitly logged out. They added only four normal revoked refresh-token audit
receipts; the active-token count remained exactly 5 and no credential or token
value entered output or evidence. The generated one-pixel request fixture was
held only in memory and discarded. A focused isolated suite passed 38/38 tests
with zero failures, errors or skips. Its exact temporary network, PostgreSQL
container and two volumes were removed after the run, while pre-existing local
test resources were neither adopted nor modified.

Temporary materializations, browser processes and Codex processes remain zero.
The session worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`; allocation SHA-256 remains
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`.
Attachment and AgentRun services remain active with zero restarts, rootless
slot container counts remain `3/0/0/3`, all three RAID arrays remain `[UU]`,
and rootful Docker remains inactive. Production, preview and Beautips return
HTTP 200. No project gate, runtime, route, unrelated slot or foreign resource
changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.8-production-rejection-matrix`;
the SHA-256 of its `SHA256SUMS` is
`c9257432a19faa49ce281d331890f716b1c2dcd6e8501dbf9e2fb74b6cafe90e`.

Task 7.9 is complete. Change progress is `74/83`; task 7.10 is the exact
resume point and was not started.

The canonical external-backup service created snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`,
newer than accepted predecessor
`01cdda7f985e88bf60b78185011704b3afa31182c256258f42d5329b4c8645b2`.
Its exact source policy selected 3,870 regular files totalling 12,257,180
bytes with normalized manifest SHA-256
`51cf5989796d05093548e65cacfe2e9d02f8ec68ed9f087a54b38e76e233fb25`.
Backup completed in 5,498 ms, the repository check completed against the same
snapshot in 4,563 ms, and bounded retention ran only after both succeeded.

The exact snapshot was restored in 4,250 ms to the newly allocated empty
isolated projection
`task-7.9-15261384-62e7-46cd-9069-72cd3580ff52`. The restored aggregate is
exactly 3,870 files, 12,257,180 bytes and the same normalized manifest, with
zero symbolic links. The projection is retained solely for task 7.10 and is
bound to device/inode `2306:10780335`, mode `2755` and numeric owner
`0:988`; it was not removed or otherwise changed after verification.

The exact canonical WorkSession sidecar selected one unambiguous real Atenea
canary from three equal-content historical copies. Source and restore both have
42,499 content bytes with SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`
and 730 sidecar bytes with SHA-256
`6491b3ef325a9bc4bb11b090a1953ac02102c1611eeb6460e4ed318bee6172cf`;
all four files retain mode `0600` and exact real-project ownership metadata.
No attachment bytes, user-facing filename, prompt, answer, credential, token
or private provider value entered evidence.

Production WorkSession 15 remains exactly one attachment, four turns, one
binding and two AgentRuns. Its Git worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`. Attachment, AgentRun,
backup, check and worker-health units remain active with zero service restarts;
temporary materializations remain zero, RAID remains `3/3 [UU]`, and rootful
Docker remains inactive. Production, preview and Beautips containers remain
up. No gate, route, runtime, WorkSession or unrelated resource changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.9-new-backup-isolated-restore`;
the SHA-256 of its `SHA256SUMS` is
`b98b18089ccc2888516c39a5db61044b7eb9db64cc38687d09aaf9e6bc002ef6`.

Task 7.10 is complete. Change progress is `75/83`; task 8.1 is the exact
resume point and was not started.

Immediately before cleanup, the isolated restore projection still matched its
accepted device/inode `2306:10780335`, mode `2755`, numeric owner `0:988`,
3,870-file count, 12,257,180-byte total and normalized manifest SHA-256
`51cf5989796d05093548e65cacfe2e9d02f8ec68ed9f087a54b38e76e233fb25`.
Every manifest entry was a regular non-symlink file with exact path, size, mode
and digest, and the restored tree contained no extra file.

Only projection `task-7.9-15261384-62e7-46cd-9069-72cd3580ff52` was removed.
The restore parent contained zero other projections before and after; its
normalized foreign-projection fingerprint remained
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The exact target is absent. The removed disposable projection remains
recoverable from the preserved accepted external snapshot and no source or
remote backup content was removed.

A fresh post-cleanup repository check completed successfully in 3,437 ms and
still selected accepted snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`.
Both external-backup timers remain enabled and active. Attachment, AgentRun and
worker-health units remain active with zero service restarts; materializations
remain zero, RAID remains `3/3 [UU]`, and rootful Docker remains inactive.

Production WorkSession 15 remains exactly one attachment, four turns, one
binding and two AgentRuns. Its worktree remains clean at commit
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`. Production, preview and Beautips
containers remain up. No gate, route, runtime, WorkSession, source attachment,
snapshot or unrelated resource changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-7.10-exact-restore-cleanup`;
the SHA-256 of its `SHA256SUMS` is
`a164dd08a401ffc15a54eb1daa064b058f74bf86642d99848e552c9c1fe67329`.

Task 8.1 is complete. Change progress is `76/83`; task 8.2 is the exact
resume point and no image or worker service has yet changed.

The protected production Compose was backed up and changed in two atomic,
separately deployed steps. First the exact real-project allowlist changed from
`atenea` to empty while the global gate remained true; only the production
backend was recreated on unchanged image
`sha256:ca076c3a615c7745c8a86fe7abd729123041bf9c38e529716892dd72c6dbc0c3`
and reached HTTP 200 on bounded attempt 14. The canonical session then reported
`BLOCKED/PROJECT_DISABLED`, while its one-item list, four-turn history, one
historical projection and authenticated download remained available.

Only after that proof, the global gate changed from true to false with both
allowlists empty. The same backend image was recreated and again reached HTTP
200 on attempt 14. The canonical session now reports
`BLOCKED/GLOBAL_DISABLED`; list and history still return the exact same counts,
and the retained download remains 42,499 bytes with SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`.
The final protected Compose remains `jose:jose 0600` with SHA-256
`dd43f6e8ed0d13431956ab0763731cc0d212f277375f643faa047a368b9286c4`.

All successful authentication probes explicitly logged out and active refresh
tokens remain exactly 5; no credential or token value entered output or
evidence. Production WorkSession 15 remains exactly one attachment, four
turns, one binding and two AgentRuns. Materializations remain zero, attachment
and AgentRun services remain active with zero restarts, rootless slot counts
remain `3/0/0/3`, RAID remains `3/3 [UU]`, and rootful Docker remains inactive.
Production, preview and Beautips containers remain up. No route, runtime,
WorkSession, source attachment, snapshot or unrelated resource changed.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.1-disable-first`;
the SHA-256 of its `SHA256SUMS` is
`66f20372c77c7885018639e1b2264298dd07bb70cfc8936963fa16dc01fe9b62`.

Task 8.2 is complete. Change progress is `77/83`; task 8.3 is the exact
resume point and the rollback has not yet been repeated.

The rollback precondition found zero non-terminal `project-codex-v3` AgentRuns
and production schema V62. With both create/bind gates already false, only the
backend image changed to the accepted V62-aware rollback
`sha256:00afca3569c7367f1df27c4ddd380c4c643fb4045e649964c55d870cb9e46c84`.
It reached HTTP 200 on bounded attempt 13 with zero restarts; Compose remains
`jose:jose 0600`, globally disabled with empty allowlists, and has SHA-256
`8e034951181c5ed40747da133a5a249e338cf0c8bc4ccec0d3266e98fcd08de0`.
Flyway remains exactly V62 and no down migration ran.

The accepted worker rollback archive SHA-256
`ca8532832f9e24dc2544d22cd17c4dba8944b51b2be7f4628bd1eae144953411`
passed safe-member and internal-checksum verification. Only the six declared
pre-rollout code/unit artifacts were installed. The single new
`attachmentRoot` configuration key was removed while the exact registered
workspace and true selection/execution state were preserved; the compatible
configuration SHA-256 is
`6db2823c96b5776c7bbe5a0ebbe43b3ee83c339094874ecaf2ccd01f6a8dc634`.
The candidate-only materialization unit was stopped and removed according to
the rollback absence manifest; its data boundary remains empty.

Both base services are enabled, active and restart-count zero. Authenticated
health returns HTTP 200, the old attachment service has no real-project create
capability (`404`), and the AgentRun worker advertises only v1/v2 plus its
pre-existing fixed capabilities, not v3. The disabled rollback backend still
lists the retained canary and downloads exactly 42,499 bytes with SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`.
The canary sidecar remains 730 bytes with SHA-256
`6491b3ef325a9bc4bb11b090a1953ac02102c1611eeb6460e4ed318bee6172cf`.

The immutable binding remains in V62 even though the older conversation view
does not project it; production counts remain one attachment, four turns, one
binding and two AgentRuns. Atenea Git, allocation and workspace are unchanged;
Beautips remains `OPEN` with `0/22/0/13` attachment/turn/binding/run counts and
slot counts remain `3/0/0/3`. RAID remains `3/3 [UU]`, rootful Docker remains
inactive, backup timers remain active, and production, preview and Beautips
containers remain up. No route, WorkSession, snapshot, attachment, Git or
foreign resource was deleted or moved.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.2-compatible-rollback`;
the SHA-256 of its `SHA256SUMS` is
`cdb93f9b02327f52c8e68ec65a4045841592c72928868c98943c1046a6ca8c15`.

Task 8.3 is complete. Change progress is `78/83`; task 8.4 is the exact
resume point and current artifacts have not yet been restored.

The complete desired rollback was repeated without forced recreation,
reinstallation, deletion or service restart. `docker compose up` reported the
rollback backend already running; its container/image/restart identity, the
protected Compose SHA-256
`8e034951181c5ed40747da133a5a249e338cf0c8bc4ccec0d3266e98fcd08de0`,
preview and Beautips container identities, V62, Atenea counts `1/4/1/2`,
Beautips counts `0/22/0/13` and canonical Git tree were identical before and
after the four-second repetition.

On AX42, the six-file rollback aggregate, compatible project configuration,
both service PIDs/restart counts, exact canary content/sidecar fingerprint,
workspace tree, allocation and all rootless container identities remained
byte-identical around a no-op start of the already active services. The
materialization unit remained absent and materializations remained zero. No
archive was extracted and no cleanup or retention operation ran.

The scheduled backup timer had independently created newer snapshot
`1f19641cfcbb19f85e3dd4fece2cc21616a044a9314d40200b1ab82d00b10dd2`
before this rollback repetition. Repository inventory contains seven snapshots
and still includes the accepted canary snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`.
Backup and check timers remain enabled and active, RAID remains `3/3 [UU]`,
and production health remains HTTP 200. The repeated rollback removed or
changed nothing additional.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.3-idempotent-rollback`;
the SHA-256 of its `SHA256SUMS` is
`f34eee61d9173c5e5361793f3a64dd3c2bc2b639fa802f7b7e46d4d13c6eeae6`.

Task 8.4 is complete. Change progress is `79/83`; task 8.5 is the exact
resume point and no validation upload or Codex turn has been created.

The accepted current backend image
`sha256:ca076c3a615c7745c8a86fe7abd729123041bf9c38e529716892dd72c6dbc0c3`
was restored while the global gate and both allowlists remained empty. It
reached HTTP 200 with V62 unchanged and zero non-terminal AgentRuns. The exact
published worker archive SHA-256
`2e847db4283bad3c1f9d7e65bcecdef611fe946dfca813e4b1697bcb761e6445`
passed member-safety and internal-checksum validation; its current code,
service units and protected project configuration were restored exactly.
Materialization preparation is active/exited with an empty boundary, and both
runtime services are active with zero restarts.

Before re-enabling, the retained canary still downloaded as 42,499 bytes with
SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`,
and external inventory still contained accepted snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`
exactly once among seven snapshots. The global gate was then enabled with both
allowlists empty and returned `BLOCKED/PROJECT_DISABLED`. Only after that
proof, the real-project allowlist was restored to quoted canonical `atenea`;
the final protected Compose is byte-identical to the accepted pre-disable file,
mode `0600`, SHA-256
`d7f94b1e611fad6329cb66346cbe99eba91d79bdba30e19fda73e48b51abb4ba`.

Canonical WorkSession 15 now reports `READY/NONE/COMPATIBLE`, while its
counts remain exactly one attachment, four turns, one binding and two
AgentRuns. No upload, binding, turn or execution was created. Production,
preview and Beautips remain up; no route, WorkSession, snapshot, Git or foreign
resource changed. All successful authentication probes logged out and no
credential or token value entered evidence.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.4-current-restore-reenable`;
the SHA-256 of its `SHA256SUMS` is
`e071771aa8d8ae2ba1c37ffbe0e8c7594f1eb858d84436ec4f47deebc65a8574`.

Task 8.5 is complete. Change progress is `80/83`; task 8.6 is the exact
resume point. The check was deliberately read-only: no upload route, file
selection or turn route was invoked.

Canonical WorkSession 15 reports `READY/NONE/COMPATIBLE`, policy revision
`atenea-real-attachments-v1`, exactly PNG/JPEG/WebP acceptance and a maximum
of four selected images per turn. Every pre-activation Atenea WorkSession
without an accepted policy revision, IDs 6 through 12, reports
`BLOCKED/SESSION_NOT_ELIGIBLE`. All sessions belonging to the only two
non-Atenea projects that currently have WorkSessions, Fomasys and Beautips,
report `BLOCKED/PROJECT_DISABLED`. There are eight registered non-Atenea
projects in total; all remain structurally blocked because the closed
real-project allowlist contains exactly canonical `atenea`.

Database counts before and after remained three attachments, 172 turns, two
bindings, 95 AgentRuns and five active refresh tokens. Their content-free
ownership fingerprint remained
`79adbbbcecd953735432fa056e3491c15ae2d3f490366c650e7903cc96713d66`.
Metadata-only worker storage remained 22 files, 20 directories and 390,963
bytes with fingerprint
`d9c0086da648d7e0f0ef0ac17b86cddc52540bc542b6e4a1ec6c51a4df3927cd`.
Materializations and temporary attachment/browser processes remained zero.
All authentication probes logged out; no credential, token, filename,
attachment content, prompt or response entered evidence.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.5-read-only-reenable-check`;
the SHA-256 of its `SHA256SUMS` is
`f471f0b2f4a46dec63c24b6c809eaa7ee6b121560fbb934aa77dcd6d9ece888f`.

A read-only project-inventory audit during task 8.6 found that the original
8.5 result field `non_atenea_project_count=2` was mislabeled: two is the number
of non-Atenea projects with WorkSessions, while eight non-Atenea projects are
registered. The original immutable package remains unchanged. A sanitized
corrective addendum proving the `9/8/2` registered/non-Atenea/non-Atenea-with-
sessions inventory and the exact one-entry `atenea` allowlist is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.5-project-inventory-correction`;
the SHA-256 of its `SHA256SUMS` is
`9012903d9838f99c082f769c33ebc72ef937c97702d575d7368470d4c662048b`.
No operational state changed.

Task 8.6 is complete. Change progress is `81/83`; task 8.7 is the exact
resume point. The final inventory is read-only and contains no private content.

Programme head/upstream are exact at
`5781abe334b5399e7fbe49b4a91ebaf13df0b961`, candidate head/upstream remain
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d`, and canonical Atenea
head/upstream remain `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`; every index is clean.
The canonical mirror and single registered workspace match canonical head and
tree `f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`, with object checks passing.

Production remains V62 with 13 WorkSessions, three attachment rows totalling
127,497 logical bytes, 172 turns, two bindings, 95 terminal AgentRuns, zero
non-terminal runs and zero active leases. The final sanitized policy,
attachment, binding, run and routing fingerprints are respectively
`3c86c0bb10086303fc476b5fa7c99b4d9fb13b5bbd80c2ad5b71ae40e0622715`,
`475e8d5acf79fe797a2b321ec34a9a0862a59fc24921fcfc691ed29b464b9f6b`,
`1e79669caacb08b1619dd26a5a2d2d60d6a7d766c8be2ec2c01f89a6a4659915`,
`e0d5a0821d548003537e915c8c537fa5992efdb73fc315992419f8629040768a`
and `6b66c9a0b241ec8bb4719b0490f39d62d5a1911bb1e35ee6f6e347e6f214d074`.

The final protected Compose remains mode `0600`, global true, synthetic empty
and real allowlist exactly `atenea`, with accepted SHA-256
`d7f94b1e611fad6329cb66346cbe99eba91d79bdba30e19fda73e48b51abb4ba`.
Production, preview and Beautips remain running with zero restarts and HTTP
200. The canary is still `READY/COMPATIBLE` and downloads as 42,499 bytes with
SHA-256
`3547d21c912406eb42b757109568d07af9770d1cd94f498ee90ccd95be3a63f5`;
the old session and Beautips remain blocked.

Worker storage remains 22 files, 20 directories and 390,963 bytes with
metadata-only fingerprint
`d9c0086da648d7e0f0ef0ac17b86cddc52540bc542b6e4a1ec6c51a4df3927cd`.
Materializations, backend spools, execution runners, Codex children, Bubblewrap
and browser/Playwright processes are all zero. The worker services and four
slot proxies are active with zero restarts; rootless running counts remain
`3/0/0/3`, rootful Docker remains inactive, and allocation SHA-256 remains
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`.

Both backup timers remain enabled/active with successful last runs. Seven
external snapshots include accepted snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`.
All three RAID1 arrays are clean `2/2 [UU]`; UFW, SSH sockets and Tailscale are
active on both hosts. No production route, foreign resource, credential or
prohibited content changed or entered evidence.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.6-final-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`fc369111526ae042ef3f95c88f1dc05581db9bd069aa2a09cbe7eab9a69d7e13`.

Task 8.7 is complete. Change progress is `82/83`; task 8.8 is the exact
resume point and no archive command has yet run.

Sixteen authoritative evidence packages containing 84 files revalidated
against their original `SHA256SUMS`. Every package has a sanitized command
record with finite timeout and exit result. The normalized credential/content
scan found zero JWT-like values, provider keys, unredacted Bearer values,
credential-like email values, private attachment child paths or internal Codex
identity fields.

The production DOM/visual matrix remains sealed for `1440x900` and `390x844`
across all eight composer states, including DOM presence/omission, exact
viewport geometry, one primary action, no overlap, no clipping and no
horizontal overflow. The real operator selected-state receipt and the later
current-wrapper Playwright/build receipt are chained without copying pixels.
The deployed image is exactly candidate commit
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d`, digest
`sha256:ca076c3a615c7745c8a86fe7abd729123041bf9c38e529716892dd72c6dbc0c3`.

The final semantic canary, external snapshot/restore, exact cleanup,
rollback/idempotence/re-enable and final infrastructure receipts are all
linked by immutable hashes. Accepted snapshot
`50980a4b74d68ed40525b73ebba2945f92885839fef4af5412d58d96e3d77de4`
remains present. The closure package itself is text-only and retains no
attachment/screenshot content, prompt, response, filename, credential, token,
private storage identity or internal Codex identity.

Sanitized accepted evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.7-closure-seal`;
the SHA-256 of its `SHA256SUMS` is
`d67116247925d202746500e1c8aea33e269071f0f12af3a6aea4d6c5a9d9aa27`.

Task 8.8 is complete. Change progress is `83/83` with zero pending tasks.
Decisions D-092 through D-096 are accepted with their tested/live status.
Pre-archive strict validation passed, and OpenSpec archived the change as
`2026-08-03-activate-atenea-real-worksession-attachments`, adding six and
modifying five installed requirements without removal or rename.

Post-archive strict validation passes all `12/12` installed specs. OpenSpec
reports zero active changes, and the archived task ledger remains exactly
`83/83` with zero pending. The candidate repository remains clean and
published at `57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d`; its final push was a
no-op because upstream already matched.

The post-archive operational smoke changed nothing: production remains V62,
the protected Compose SHA-256 remains
`d7f94b1e611fad6329cb66346cbe99eba91d79bdba30e19fda73e48b51abb4ba`,
the global gate is true, the synthetic allowlist is empty and the only real
project is `atenea`. Production, preview and Beautips return HTTP 200; all
three worker services and both external-backup timers are active,
materializations remain zero and RAID remains `3/3 [UU]`.

This change stops here. It does not enable Beautips real attachments, add
Android-native attachments or implement automatic retention deletion. Each
requires a separate future OpenSpec change and its own authorization/acceptance
boundary.

Sanitized accepted archive evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/activate-atenea-real-worksession-attachments/runs/task-8.8-openspec-archive`;
the SHA-256 of its `SHA256SUMS` is
`2f0f83c0e68d9f1648cb4d543d99e16e40fc3ff67557b58e92629329b6c4311c`.

## Atenea canonical main promotion

Tasks 0.1 through 0.3 of `promote-atenea-canonical-base-to-main` are
complete. The change contract fixes two ordered GitHub pull requests and
forbids squash, rebase rewriting, force updates and source-branch deletion.
Operational reconciliation begins only after both accepted tips are ancestors
of GitHub `main`.

Entry Git is clean for the candidate and canonical Atenea sources. GitHub
default is `main` at `7e8afa6c7039a70aea3b330234ddeabdcf2a6587`; published
feature tip `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` is exactly 86
commits ahead with `main` as ancestor. Attachment candidate tip
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d` is exactly 32 further
commits with the feature tip as ancestor. GitHub permits merge commits and has
no open pull request.

The canonical project default, checkout and worker registry still name the
feature branch and commit. The AX42 mirror has the matching feature and old
main refs; the candidate is not yet published there. The only non-closed
Atenea session is historical WorkSession 6 in `DRAFT_BLOCKED`; its worktree is
retained with 37 porcelain entries and will be inspected against its accepted
retained-draft contract before any disposition.
Every AgentRun is terminal.

Production and preview return HTTP 200. AX42 AgentRun, attachment, preview and
Tailscale services are active; both external-backup timers are enabled and
active; all three RAID1 arrays are `[UU]`. Rootless slot inventory is
`3/0/0/3`: administrative Beautips remains in slot 1 and its separate exact
WorkSession runtime remains in slot 4. These and every unrelated project are
outside this promotion and must remain unchanged.

Sanitized entry evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-0-entry`;
the SHA-256 of its `SHA256SUMS` is
`eca6d664cce819fbe6273afda3531673a85529570181d31f99b7684523aab8ec`.
The accepted entry contract passed strict validation and was published at
programme commit `e8d532c732b065a462049c2934553bef02a57421`. Task group 0 is
complete at `4/22`; task 1.1 is the exact resume point. No GitHub Atenea ref,
project setting, worker registry, mirror, WorkSession or service has changed.

Task group 1 is complete and change progress is `7/22`; task 2.1 is the exact
resume point. Live inspection proves WorkSession 6 is already the accepted V51
retained-draft quarantine, not an active stale session. It persists exact
remote UUID `c750641d-3226-44c3-81dc-d9149aac0de1`, retained HEAD
`d5ea39e7b575b63c6fff3a66a0400c5af5e9ff2b`, accepted commit
`ec867f75bd4bb58f582607cf0025a003400f02c8`, fingerprint
`19450e0fc0edb52625f93fe19688b2fc7de94c5c422d3fde12b25d70ee325f37`
and its linked replacement WorkSession 7, which is closed.

The retained worktree still has tree
`7e4531a5c5538d4f30fdb63d588db1afc9e34ddc`, clean index, 28 tracked
modified files, 16 untracked files and the accepted tracked binary-diff
SHA-256
`fe004b66dc9d76da024c6c514ccd7992b6846b2556fab8694bbfd3feb6257fa8`.
Its retired allocation remains byte-identical with SHA-256
`f143453718f4c8758665a02986ce44c607feff3f44cc0971100fb63ab4ac1cac`.
It owns zero containers, networks, units, listeners and worktree processes in
all four slots. Every AgentRun is terminal.

The ordinary close service accepts only `OPEN` or `CLOSING`, while the V51
constraint deliberately keeps a fingerprinted retained draft non-closed.
Accordingly, no close endpoint, recovery mutation or database update ran.
One focused local test attempt stopped before Maven because the fixed
`atenea-db-test` name belongs to a separate retained Compose project; that
foreign test container was left intact. Existing accepted tests, source
hashes and live invariants establish the disposition, and GitHub checks remain
mandatory before merge.

Production/preview remain HTTP 200; rootless slot counts remain `3/0/0/3`,
worker services and backup timers remain active and RAID remains `[UU]`.
Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-1-retained-draft-disposition`;
the SHA-256 of its `SHA256SUMS` is
`95c4c04218e22c160f22903409ad9bc4aebf3e95e392dfd9c6caca4e3a2eaa90`.

Task 2.1 is complete and change progress is `8/22`; task 2.2 is the exact
resume point. Exact detached feature tip
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`, tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`, passed all 526 backend
tests with zero failures, errors or skips and validated/applied all 61 Flyway
migrations to an empty disposable PostgreSQL database. The TypeScript/Vite
production web build passed with 1,583 transformed modules and zero reported
npm vulnerabilities.

The isolated validation used three unique disposable Compose container names
because two six-week-old exited canonical development containers retain the
fixed defaults. Those foreign containers stayed byte-identical and stopped.
The accepted harness changed only those three temporary names; application,
test, migration, web and built static sources matched the exact commit.

Exact cleanup removed the test containers, network, volumes, images and
detached worktree. A first removal returned 1 after the tests left 2,502
root-owned synthetic repository entries under the recorded temporary root; a
single exact bind-mounted cleanup container removed only those entries and
then removed itself. The root and every project-labelled resource are absent.
Production/canonical Git remained clean and synchronized and production plus
preview remain HTTP 200.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-2.1-feature-validation`;
the SHA-256 of its `SHA256SUMS` is
`064b734699b02c1ca15c444941a8cfa6ba744e46136373c54d42bae0d9a387bb`.

Task 2.2 is complete and change progress is `9/22`; task 2.3 is the exact
resume point. GitHub PR
`https://github.com/jlnieto/atenea/pull/5` integrated exact feature tip
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` into `main` using merge-commit
semantics. The resulting immutable main commit is
`f3c4e7e6433b9d943a840be9e65932c0d7bfff73`, with old main
`7e8afa6c7039a70aea3b330234ddeabdcf2a6587` and the validated feature tip as
its two ordered parents, and tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`.

Before merge, the PR was non-draft, `MERGEABLE`/`CLEAN`, had the exact base
and head refs and reported no GitHub status checks. The merge command was
head-locked to the validated SHA. No squash, rebase, force update, branch
deletion, deployment, routing change or runtime mutation occurred. The source
branch remains published at its unchanged exact tip. The GitHub connector's
write integration returned a bounded HTTP 403 without creating state, so the
documented authenticated `gh` fallback performed the authorized operation.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-2.2-feature-pr-merge`;
the SHA-256 of its `SHA256SUMS` is
`f355fd3f23c523bdae5f441400e2b2dd6752779c08017725cb74dd25a50a47c4`.

Task 2.3 is complete and change progress is `10/22`; task 3.1 is the exact
resume point. GitHub's comparison from retained feature tip
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` to merged main
`f3c4e7e6433b9d943a840be9e65932c0d7bfff73` reports ahead by exactly the
single merge commit, behind by zero, with the feature tip as the exact merge
base. Both GitHub refs remain present and unchanged.

The canonical checkout, project default and reviewed worker pin deliberately
remain on the feature tip until the bounded reconciliation in section 4.
Their Git and ownership state is unchanged. Rootful container identities,
rootless slot counts `3/0/0/3`, non-closed WorkSessions and terminal AgentRun
counts match entry fingerprints. Production and preview remain HTTP 200; the
Beautips administrative and WorkSession resources retain their exact six
container IDs. The four canonical worker services are active, both backup
timers are active/enabled and all three RAID arrays remain `[UU]`.

Initial read-only discovery used three plausible but non-canonical service
unit names and received `inactive`; inventory identified the actual names and
the exact check proved all four active. Protected selected-field registry and
named-database queries likewise passed after two bounded read-only invocation
errors. No repair, restart or mutation was performed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-2.3-feature-nonimpact`;
the SHA-256 of its `SHA256SUMS` is
`c5f015712287043d2f705fbf959942fc75331aae55823ec8aac434d5eef3d30d`.

Task 3.1 is complete and change progress is `11/22`; task 3.2 is the exact
resume point. Clean candidate branch
`codex/activate-atenea-real-worksession-attachments` remains synchronized to
internal upstream at exact commit
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d` and has been published as a new
GitHub ref at that same SHA using an ordinary, non-force push.

The GitHub comparison against merged main reports exactly 32 candidate
commits, 71 changed files, 9,011 additions and 394 deletions. The apparent
one-commit behind count is solely main's accepted merge commit: the exact
merge base is feature tip `8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`,
and main plus feature have the identical tree
`f7b3c8c56abfcefd40b5aa2cbcca133278a29ae9`. Thus the second review contains
only the 32 descendant attachment commits and no repeated historical diff.

A read-only SSH GitHub probe failed because this account's configured protocol
is HTTPS; it created no state. The authenticated HTTPS publication and all
exact remote/tree checks passed. No runtime, service, deployment, routing,
project, WorkSession or foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-3.1-candidate-publication`;
the SHA-256 of its `SHA256SUMS` is
`67f446a909a4ab8240eb47b84b2e44480171b6ffbaa40e54b6998799acc29ee1`.

Task 3.2 is complete and change progress is `12/22`; task 3.3 is the exact
resume point. The first green validation attempt was rejected because its
default Compose bind mounted the canonical feature checkout. The corrected
isolated repository layout then executed original candidate
`57b4123abaa4d66ba335fcb0cf4b64cd9fdd589d`, validated 62 migrations and
exposed one failure plus seven errors among 616 tests.

The cause was bounded to two new image-turn integration tests: each created
synthetic worker `ax42-01` and its durable activation barrier but cleaned only
session/project rows. Historical Codex administration tests therefore saw a
duplicate or foreign fixture. Test-only commit
`d0036e427bae2d6753d81a4725971f2fb91c5add` tracks whether each fixture
created the worker and deletes its exact barrier/worker only under that
ownership. It preserves any pre-existing node and changes no application or
runtime source.

The corrected sequence passed 6/6 new tests, proved both synthetic rows absent
and then passed 14/14 historical Codex operations tests on the same database.
A fresh empty database passed all 616 tests with zero failures, errors or
skips and all 62 migrations. The web production build passed with 1,583
modules and zero npm vulnerabilities.

Every uniquely labelled Compose resource, image and temporary worktree was
removed. Exact cleanup removed 4,998 root-owned entries beneath the recorded
temporary root. The rejected default bind's 28 work repositories plus 28 bare
remotes were registered by immutable name/inode and normalized manifest
SHA-256 `d88fb9847dc0e5b0a68544690cb453e1f134ae690499f6cfdab18581e1867909`,
then only those 56 exact creation-window fixtures were deleted; older fixtures
and the two historical exited development containers remain intact.

GitHub PR `https://github.com/jlnieto/atenea/pull/6` was non-draft,
`MERGEABLE`/`CLEAN`, had exact head
`d0036e427bae2d6753d81a4725971f2fb91c5add` and no status checks. A head-locked
merge commit produced new main `51e6ea40286ae8c44e6235b32be9f644af57b11c`,
whose ordered parents are prior main
`f3c4e7e6433b9d943a840be9e65932c0d7bfff73` and the exact validated
successor. Both source branches remain published. No deployment, routing,
configuration, service or runtime mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-3.2-candidate-validation-merge`;
the SHA-256 of its `SHA256SUMS` is
`d99c3e2f377b496d5b97873b6b86b07222fa3da8cbcc38892d19c998d62fe81a`.

Task 3.3 is complete and change progress is `13/22`; task 4.1 is the exact
resume point. GitHub main
`51e6ea40286ae8c44e6235b32be9f644af57b11c` retains feature tip
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d` and validated attachment tip
`d0036e427bae2d6753d81a4725971f2fb91c5add` as ancestors. The comparisons
report behind by zero and exact merge bases at the corresponding accepted
tips. Both source branches remain published at their exact immutable SHAs;
PRs 5 and 6 remain merged through their expected merge commits.

The canonical checkout, project default, worker registry and mirror remain
deliberately unreconciled until section 4. The checkout is clean at the
feature tip. Non-closed WorkSessions and terminal AgentRun totals match entry
fingerprints, with zero non-terminal runs. Rootful container identities and
rootless slot counts `3/0/0/3` are unchanged. Production, preview and Beautips
return HTTP 200; the four worker services and both active/enabled backup
timers retain state, and all three RAID arrays remain `[UU]`. No deployment,
restart, routing change, runtime start or resource mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-3.3-post-merge-nonimpact`;
the SHA-256 of its `SHA256SUMS` is
`6cd7ce7149f700ba7111482f270c7f9e9f1b3ebfeedbeb822f4690c8581443fb`.

Task 4.1 is complete and change progress is `14/22`; task 4.2 is the exact
resume point. After rechecking the clean feature checkout, ordinary GitHub
origin and both accepted ancestors, a bounded fetch advanced only
`origin/main` from `7e8afa6c7039a70aea3b330234ddeabdcf2a6587` to exact merged main
`51e6ea40286ae8c44e6235b32be9f644af57b11c`. The local `main` branch was
then fast-forwarded to that same commit and `origin/HEAD` now points to
`refs/remotes/origin/main`.

The canonical checkout is clean on `main`, its upstream is exact, its tree is
`40e8e9fab894ecad8f4ee6af340b32b918cb0148`, object integrity passes and the
feature branch remains unchanged at its accepted tip. The inverse operation
is recorded without rewriting GitHub or local-main history. No deployment,
service restart, project row, mirror, worker registry, WorkSession, runtime or
routing state changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.1-canonical-checkout`;
the SHA-256 of its `SHA256SUMS` is
`f88d9ea45bac89dc1dd79ddc77940e8a51bbfcff58a4cd92348b2d56aed0f6f8`.

Task 4.2 is blocked and remains the first pending task. Change progress remains
`14/22`.

The final-main application tree and deployed backend still require exact
branch `feature/actualizar-conversacion-en-web` through
`ProjectCodexIdentity.BRANCH`; the accepted runtime manifest names the same
branch and has pinned SHA-256
`3b26e1899a06993bee69ac596e7cb69b6200a37d063d98203ad308058c91bfa3`.
AX42's AgentRun worker, project runner, activation/validation/multi-repository
mediators, installer and three request schemas independently require that
same feature branch. Changing only the worker JSON and project default to
`main` would therefore leave new sessions local or fail closed against
inconsistent authorities. Correct reconciliation requires an application
successor, coordinated worker/schema update, new manifest identity, complete
validation and production rollout, all explicitly excluded by this change's
current non-goals.

The ownership audit also found the sole registered AX42 Atenea workspace
belongs to closed WorkSession 15, remote session
`c80c1e72-e34f-46b9-ba34-5a9a0c0ad2d7`. Its clean feature worktree and
allocation are retained, while admission still reports `slot2=held` and
`heavy1=held` and slot 2 has zero containers. The exact worker contract
permits only one registered Atenea workspace, so preserving this record would
reject a new main canary; unregistering/releasing it would exceed task 4.2's
declared pin-only mutation and cannot be inferred under the fail-closed
ownership rule.

No mirror fetch, worker/config write, service restart, admission release,
project-row mutation, runtime start or routing change was attempted.
Production, preview and Beautips remain HTTP 200, rootless slot counts remain
`3/0/0/3`, the worker is active with zero restarts, non-terminal AgentRuns are
zero and all RAID arrays remain `[UU]`.

Sanitized blocking evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.2-blocked-source-contract`;
the SHA-256 of its `SHA256SUMS` is
`e80ee6e9d8f20078612084f9eca7b054b27d1142f2fcdf2b40e77918ca346e5d`.

The operator separately authorized the complete corrective path on
2026-08-03. Task 4.2 is now complete and the amended change progress is
`15/25`; task 4.3 is the exact resume point.

The reviewed contract now treats Atenea's compiled backend identity, runtime
manifest, complete AX42 worker/mediator/schema identity, immutable manifest
hash and persisted project declarations as one transition to `main`. It also
permits releasing only the exact stale registration and held admission of
already closed WorkSession 15 after complete ownership and zero-resource
proof, while retaining its allocation sidecar, worktree, Git, logs,
attachments and artifacts.

The authorized rollout is bounded to the identity-only Atenea successor, the
AgentRun worker and the production backend. It does not authorize a schema,
UI, attachment-policy, routing-policy, preview, Beautips, unrelated-session or
runtime change. Rollback restores exact recorded worker artifacts/config and
the prior backend image without rewriting the append-only GitHub history or
reintroducing retired closed-session ownership.

Task 4.3 is complete and amended change progress is `16/25`; task 4.4 is the
exact resume point. Atenea branch
`codex/promote-atenea-main-identity-20260803` contains one identity-only commit
`3d02c3ec8fbbe21c4a6d20bf6ddddb2e8b3f0c1c` over merged main. It changes
only the application branch constant, runtime-manifest default, derived
manifest SHA-256
`327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b`
and a literal regression test. The clean branch is published to the internal
canonical remote.

The programme worker sources now move the complete Atenea authority set to
`main`: AgentRun worker, project runner, activation/validation/
multi-repository mediators, installer, runtime manager/engine/adapter and all
three request schemas. No former branch or manifest identity remains in the
operational source set. Beautips' adapter and installers changed only their
derived shared-runner fingerprints; all Beautips repository, commit,
manifest, routing and runtime identities remain unchanged.

Focused validation passed 58 backend tests, 56 AgentRun-worker tests, 22
project-runner tests, four Beautips-runner tests, five Codex contract tests,
three Beautips session-contract tests, both install/rollback lifecycles, both
runtime adapter corpora and all 10 project-runtime groups. Two rejected
backend harness attempts exposed historical container-name ownership and an
incorrect default bind; neither foreign container changed. The accepted
isolated run removed all exact temporary Compose resources and restored its
temporary Compose edits before commit.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.3-main-identity-sources`;
the SHA-256 of its `SHA256SUMS` is
`96a017cf4c51976134e8045e409c56373b14b7522d1d44b7eb2d8b186503554d`.

Task 4.4 is complete and amended change progress is `17/25`; task 4.5 is the
exact resume point. The clean Atenea successor passed all 617 backend tests
with zero failures or errors and validated all 62 migrations. Its production
web build compiled 1,583 modules with zero npm vulnerabilities. The complete
sorted worker suite passed all 31 entrypoints from detached clean sources.
The browser-cleanup entrypoint first rejected its absent mandatory synthetic
wrapper before product execution; after supplying the same bounded
`playwright-safe` wrapper required by the accepted historical suite, it and
the remaining entrypoints passed.

GitHub PR `https://github.com/jlnieto/atenea/pull/7` was non-draft,
`MERGEABLE`/`CLEAN`, had exact head
`3d02c3ec8fbbe21c4a6d20bf6ddddb2e8b3f0c1c`, one commit and only the three
reviewed identity files. A head-locked merge commit produced main
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, whose ordered parents are former
main `51e6ea40286ae8c44e6235b32be9f644af57b11c` and the validated successor;
its tree exactly equals candidate tree
`3b8a5517bdc0845e3a2f52718173e6ef5307245a`. The feature, attachment and
identity source refs remain published.

All exact temporary Compose resources were removed and both accepted source
trees are clean. Production, preview and Beautips remain HTTP 200; worker
services, registry fingerprint, rootless slot counts `3/0/0/3` and all three
RAID arrays retain their prior state. No deployment, service restart, mirror
refresh, project default mutation, runtime start or routing change occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.4-main-identity-validation-merge`;
the SHA-256 of its `SHA256SUMS` is
`7446d11fb78ae820a953d84768d627af20f78f917128adfd07d3e7c72adac936`.

Task 4.5 is complete and amended change progress is `18/25`; task 4.6 is the
exact resume point. Production WorkSession 15 is still `CLOSED` with exact
remote identity `c80c1e72-e34f-46b9-ba34-5a9a0c0ad2d7`, two terminal
`SUCCEEDED` AgentRuns and zero non-terminal runs globally. Its registry,
allocation, workspace record, clean feature worktree and admission record
matched all reviewed pre-change hashes. It owned no container, network,
volume, image, listener, runtime unit or process.

Installed mediator SHA-256
`da60b0a1d871b0815f81d864735d88518f224323d831036b51fb1eb440931db6`
matches reviewed programme commit
`4ea60175e77c2fca8a5f888fe50a54b7b6010c19`. Its exact
`project-unregister` operation removed only this workspace registration,
disabled the former Atenea selection/execution gates and restarted only the
AgentRun worker. The installed verification passed. The unchanged reviewed
admission helper then released `heavy1` before `slot2`; both released states
remain persisted.

The allocation and workspace-record hashes, retained filesystem inodes,
worktree HEAD/tree/cleanliness, database row, two runs, one attachment row and
four turn rows are unchanged. Every foreign admission fingerprint and all
four rootless slot container-identity manifests match their before values.
The worker is active with `NRestarts=0`; production, preview and Beautips
remain HTTP 200 and RAID remains `[UU]`. No mirror, worktree, Git, allocation,
log, attachment, artifact, runtime, routing or unrelated resource was removed
or modified.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.5-closed-session-ownership-release`;
the SHA-256 of its `SHA256SUMS` is
`808eaedb24130e655056598d3a8c43e46f0008d8e6f73a8f4035dae9f926fbae`.

Task 4.6 is complete and amended change progress is `19/25`; task 4.7 is the
exact resume point. The AX42 bare mirror passed owner, mode, remote, single
fetch-refspec, absent-pushurl and integrity checks. Its bounded fetch advanced
only from the published repository and moved `origin/main` from
`7e8afa6c7039a70aea3b330234ddeabdcf2a6587` to exact accepted main
`615e539d1f2622a4ac2568ba7697b876d49ae33e`; the historical feature ref remains
`8d5acdf9d593a2b0bafbf00fbef1ab2cc11cad9d`.

Deployment preflight exposed that preserving the exact empty, disabled feature
registry after main advanced correctly failed closed. Programme commit
`cd004e846b7ebf2acd089988613ffa1e97c78655` added an atomic installer
transition which accepts only that exact predecessor while the worker is
stopped, requires the reviewed target commit, and validates current repository,
branch, manifest and runner authorities literally. A timestamp-substring
flakiness in the attachment log test was also bounded to its two-character
fixture; the replacement UUID passed 20 consecutive runs.

The first candidate then rejected the installed Beautips compatibility runner
before stopping or writing anything. Its SHA-256
`60d54f1e6e6eaf1edea43e9bf3b0800226a413b4feee5a59ce8152954d97b983`
matched reviewed commits `c93c19073af031b441fdbae9d69dc01d8aa4253d` and
`4ea60175e77c2fca8a5f888fe50a54b7b6010c19`; it was the omitted immediate
predecessor, not a foreign file. Commit
`c0872d286527b98e1f44cecd442ee5b5428e22e0` advances only that exact
predecessor identity. The final source passed all 31 sorted worker entrypoints
in 487 seconds.

The immutable release source SHA-256 is
`0ef7866357c4834bedf6b631a27edf651bc4eb17890f20fd7abf8fa3d31adb29`.
Its 16-file whitelist-only rollback excludes tokens, credentials and
environment dumps and has manifest SHA-256
`373084bc1746d66b63fd5fd08c7214d07b504f0709b3e57b08a92d9e1270076f`.
The release `SHA256SUMS` hash is
`139f3636dacf87afe08586ad20feedc95b89bc95d0e59b564a70251c608cf7f5`.

Final apply completed in 1,085 ms, installed the reviewed files, transitioned
the empty registry to disabled `main@615e539d1f2622a4ac2568ba7697b876d49ae33e`
with manifest SHA-256
`327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b`,
and restarted only the AgentRun worker. Full installed verification passed.
No workspace was registered or runtime started. The closed allocation and
released admission remain exact, all four slot identity manifests match,
non-terminal AgentRuns remain zero, and the Atenea project default remains on
the feature branch for task 4.7. Production, preview and Beautips remain HTTP
200; backups, firewall and RAID remain healthy.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.6-main-mirror-worker-install`;
the SHA-256 of its `SHA256SUMS` is
`435a94e644ffde45f341812adeec109308a87a8e9e17905a58f5c7d3229aff49`.

Task 4.7 is complete and amended change progress is `20/25`; task 4.8 is the
exact resume point. A fresh canonical encrypted external backup, repository
check and bounded retention sequence completed successfully before production
changed. The clean canonical checkout advanced by ordinary fast-forward to
accepted `main` commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, tree
`3b8a5517bdc0845e3a2f52718173e6ef5307245a`, with its upstream and
`origin/HEAD` exact.

The identity-successor backend image was built from that exact source in 16
seconds. It has immutable image ID
`sha256:fe5bb7a6b39dbcc2f9847dd05b68b9aabe72bf4d2775ad55f5624fcd99b1d96f`
and application JAR SHA-256
`4d3f4222e559c7f6787e73ad9dc5af151cd10fe9262de390bf01e09c6dea9978`.
The protected production Compose changed only its backend image reference,
remains `jose:jose` mode `0600`, and has SHA-256
`6951a486535b19f348d305bd48a443fe93698f3aade2880f1bd1565babec5d40`.
Its exact prior definition remains mode `0600` with original SHA-256
`d7f94b1e611fad6329cb66346cbe99eba91d79bdba30e19fda73e48b51abb4ba`
as the bounded rollback.

Only `atenea-backend-prod` was recreated. It reached HTTP 200 on bounded
readiness attempt 14 in 14,418 ms with zero restarts. Container, network and
volume fingerprints excluding that one backend remained byte-identical; preview
and Beautips remained HTTP 200.

The persisted configuration contract then locked and changed exactly project
ID 1 whose immutable name, in-container repo path, old branch and prior
timestamp all matched. Its default is now `main`; the target row SHA-256 moved
from `717297825b03378bd172ffd34bc04ff6d0cc0089a9aa27a312ad5890593e3d29`
to `0572a20dc12d8ee3a804c38431a3127546314b2e9741e95ce08813e0e2917dac`.
Every non-target project remains byte-identical at SHA-256
`1e8e55413658bc080054b558838220a5f5ffa6340896cd84f15f4698019cf80e`.
The inverse exact-row transaction is recorded against the new timestamp.

Flyway remains `62/62`; all 95 AgentRuns are terminal, active leases are zero,
and WorkSession, attachment, binding, policy-snapshot and preview counts remain
`13/3/2/3/1`. The unauthenticated project API correctly returned 401 and no
credential was read. AX42's reviewed registry SHA-256 remains
`7369170a308ea81746ca5fd2cc4ae01fa11e36194ff08204122ee5cfa871c4db`;
its services have zero restarts, slot counts remain `3/0/0/3`, backup timers
remain active/enabled and RAID remains `3/3 [UU]`.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.7-main-backend-project-default`;
the SHA-256 of its `SHA256SUMS` is
`2e23e53082006d5e8d53c95673b0400acf7296a9d9fc3bf2d65a26aecee329cd`.

Task 4.8 is complete and amended change progress is `21/25`; task 5.1 is the
exact resume point. Repeated application reconciliation was a no-op: Compose
reported the exact backend already `Running` in 102 ms, retained container ID
`ab4d4e95fc3e0486ab51efeabc969243236baf6953a8aae149e60bf62ba13005`,
and the locked project transaction verified the sole canonical `main` row in
129 ms without issuing an update. Container, network and volume inventories
remained byte-identical.

Sanitized database projections remained identical before and after. There are
still 9 projects, 13 WorkSessions, 95 terminal AgentRuns, 3 attachments, 2
bindings and 1 preview; non-terminal runs and active leases remain zero. The
historical `DRAFT_BLOCKED` WorkSession 6 and closed feature-based WorkSession 15
remain immutable. Flyway remains `62/62`; production, preview and Beautips
remain HTTP 200.

The installed AX42 worker verifier passed in 165 ms without restarting a
service. Registry SHA-256
`7369170a308ea81746ca5fd2cc4ae01fa11e36194ff08204122ee5cfa871c4db`
remains disabled, empty and exact at
`main@615e539d1f2622a4ac2568ba7697b876d49ae33e`. Mirror ref-set SHA-256
`f18d94266a4e74f5183131aa365e2b371c6e3438617926d43629d5e48e9c24f0`
remained unchanged and full object integrity passed. The closed allocation,
workspace-record and released-admission SHA-256 values remain exact, with zero
session runtime references.

Worker service, listener and four-slot inventory projections remained
byte-identical. Rootful Docker and containerd remain inactive/masked, both
backup timers remain active/enabled and RAID remains `3/3 [UU]`. No runtime,
route, AgentRun, lease, listener, container, network, volume, attachment,
preview, Beautips or unrelated resource was created, adopted, restarted or
modified.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.8-main-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`77670483bb1632e11edf2bbd5942bc390f2c0a2da31991b9c5422a2200fdb318`.

Task 5.1 remains the exact resume point and amended change progress remains
`21/25`. The operator created the one new canonical Atenea WorkSession through
the real web flow. Persisted WorkSession 16 has remote session ID
`7151dce0-69ab-4614-86e4-f93f1af825e4`, exact `baseBranch=main`, remote AX42
affinity, the compatible `project-codex-v1` and
`atenea-real-attachments-v1` policies, and zero turns, AgentRuns, attachments
or previews. It remains deliberately `OPEN/DRAFT`: canonical source fields are
null and no workspace, allocation, admission record or slot resource exists.

The required activation then failed closed before invocation. AX42's installed
`/usr/local/libexec/atenea/atenea-workspace-activation-v1.sh` has SHA-256
`61fc03da468f2f9fa1fb101dc42129a773f02acaacbc40fd46e18d7a06724df2`
and still pins `feature/actualizar-conversacion-en-web` plus the preceding
manifest. The reviewed immutable release contains the correct `main` mediator
at SHA-256
`5ef544c478c17a0ae6ae88586915185572721ca89dc48dbbf15b65ad417aa889`,
but the installed installer at SHA-256
`9c841e1a6e76d7477f056792f9749609682532d56d309d2c17c069b348d9f48f`
contains zero references to the Atenea activation mediator. Its previous
successful verification therefore could neither detect nor replace this stale
installed program. The task 4.6 installation-completeness assumption and the
corresponding task 4.8 verifier claim are superseded by this exact finding
until a reviewed corrective closure is completed; their other sealed
fingerprints remain valid.

Executing the installed mediator would create a workspace from the rejected
feature identity, so it was not run. No repair, adoption, deletion, prompt,
runtime or AgentRun was attempted. The registry remains disabled and empty at
exact `main@615e539d1f2622a4ac2568ba7697b876d49ae33e`, the mirror passed full
object integrity, global non-terminal AgentRuns and active leases remain zero,
all three worker services remain active, and production, preview and Beautips
remain HTTP 200.

Resume requires a separately reviewed corrective change that adds this
mediator to the versioned installer and verifier, proves exact rollback and
the complete worker regression, installs only that correction, and repeats
reconciliation. Task 5.1 may then continue against retained WorkSession 16
without sending a prompt or starting a runtime. Sanitized blocker evidence is
beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.1-blocked-stale-activation-mediator`;
the SHA-256 of its `SHA256SUMS` is
`fa3ac7672d1e439cd922bb2c27d463f54d65d8b78e9960a8b36b0e36bf89c69b`.

Task 4.9 of the authorized activation corrective is complete. Amended change
progress is `22/27`; task 4.10 is the exact resume point. The dedicated Atenea
routing installer now accepts only a completely absent bundle, the exact
current bundle, or the exact reviewed feature-program predecessor with current
sudoers and dependency identities. Partial, symlinked, foreign and ambiguous
state is rejected unchanged, and the whole-bundle preflight is repeated before
the first write.

The AgentRun installer now verifies the exact main activator, sudo boundary and
three workspace dependencies before it stops the service and again in its
ordinary installed verification. The deployment runbook explicitly applies
the dedicated activation installer first. Corrective routing-installer and
AgentRun-installer SHA-256 values are respectively
`bd4c406399011f87d21643dd94de8e2254098c7c7d883107d6e863ffced3cd07`
and
`d7c103ea181a5bf542fe839e002aaf53336bf78fb1cbd00f5934696c8aa4a819`.

Both focused suites passed twice. The complete 32-entry worker suite, including
the bounded synthetic Playwright browser/cleanup entry, passed `32/32` in 522
seconds. Strict OpenSpec validation passed. No AX42 install, service restart,
registry change, workspace activation, prompt, runtime or AgentRun occurred in
this source-only task. WorkSession 16 remains the retained no-run canary.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.9-activation-corrective-source`;
the SHA-256 of its `SHA256SUMS` is
`4e21609b8dbd77fa61d9f99d696130f8c679cf8632b8c7d26c5369c7fb17995e`.

Task 4.10 is complete and amended change progress is `23/27`; task 5.1 is again
the exact resume point. Immutable corrective release
`4252719b8ab092e4431bfbae5033a75d4c3abdfd` has source-tar SHA-256
`102dc45b2d649438a83a6bc8d3c496a7f289b0f25c6e3dc2e14a0c1ea08584b2`.
Its top `SHA256SUMS` hash is
`76764dddd7619f35d0213ab1ee5a4f42d67bf6f55943e2d9ef971aee5756004f`;
the six-file exact installed-predecessor rollback `SHA256SUMS` hash is
`bccce0096d4c7c63c35c205ba0f8c64472e0ca078dbf79e6d3adfbff66781002`.

The dedicated apply advanced only the exact reviewed activation mediator from
SHA-256
`61fc03da468f2f9fa1fb101dc42129a773f02acaacbc40fd46e18d7a06724df2`
to main SHA-256
`5ef544c478c17a0ae6ae88586915185572721ca89dc48dbbf15b65ad417aa889`,
retained the byte-identical sudoers boundary and dependencies, and installed
the complete AgentRun verifier at SHA-256
`d7c103ea181a5bf542fe839e002aaf53336bf78fb1cbd00f5934696c8aa4a819`.
Apply took 127 ms. Both installed verification paths passed twice in 220/221
ms.

No service restarted: the AgentRun worker retained PID `1420261`, zero
restarts and active state. Registry, service, listener and four-slot
projections remained byte-identical. WorkSession 16 remains `OPEN/DRAFT/main`
with zero turns, AgentRuns, attachments and previews; its workspace,
allocation, admission and runtime remain absent. Global non-terminal AgentRuns
and active leases remain zero. Backup timers remain active, rootful daemons
remain inactive/masked, RAID remains `3/3 [UU]`, temporary worker browser
processes remain zero, and production, preview and Beautips remain HTTP 200.
Automatic exact rollback was armed but not needed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.10-activation-corrective-rollout`;
the SHA-256 of its `SHA256SUMS` is
`a29a80a7c6ecb6b5f026a2840123eac0032d7c5b7e1dab5e84a9a50442bd7261`.

Task 5.1 remains incomplete and progress remains `23/27`. The corrected main
mediator began the authorized no-run activation for retained WorkSession 16.
It created the exact clean worktree and workspace record at accepted main
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, then acquired its exact free
admission as `slot2=held/heavy1=held`. Runtime allocation failed closed with
`RUNTIME_OWNERSHIP_CONFLICT` before registry activation because closed
WorkSession 15 still retains an active-name `runtime-allocation-v1.json` that
declares `slot2`.

The target partial state is exact and retained: workspace-record SHA-256
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`,
admission SHA-256
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`,
no target allocation, no registry entry and zero runtime resources. The
conflicting WorkSession 15 allocation has unchanged SHA-256
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`;
its control-plane session is `CLOSED`, admission is
`slot2=released/heavy1=released`, registry ownership is absent and runtime
resources are zero. It was not renamed, repaired or modified.

The conflict is between task 4.5's retained active-name allocation and the
fixed-slot no-run canary contract. No retry or cleanup was attempted. Global
non-terminal AgentRuns and active leases remain zero, the worker remains active
with zero restarts, RAID remains `3/3 [UU]`, and production, preview and
Beautips remain HTTP 200.

Resume requires separate authorization to prove and atomically retire only
WorkSession 15's exact allocation from `runtime-allocation-v1.json` to the
canonical `runtime-allocation-v1.retired.json`, preserving bytes and metadata,
then repeat the same idempotent WorkSession 16 activation. Its exact worktree
and admission must remain retained for that retry. Sanitized blocker evidence
is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.1-blocked-retained-allocation-slot-conflict`;
the SHA-256 of its `SHA256SUMS` is
`8ed5c18625f59215e6a9f3e505fcd8bcc7570465c802c6d1824061e17bba73d9`.

Task 4.11 is complete and amended change progress is `24/28`; task 5.1 is the
exact resume point. Following the operator's separate bounded authorization
and D-099, WorkSession 15 was re-proved `CLOSED`, with both admission permits
released, no registry entry, zero non-terminal AgentRuns and zero owned
containers, networks, images, volumes, listeners or runtime unit. Its exact
active allocation SHA-256 was
`89fe98bfb3afb0d4d2c0007c22c5636669f0d3b77bfc588732992bbdb95a2a35`
and the canonical retired destination was absent.

One same-filesystem rename moved only that inode from
`runtime-allocation-v1.json` to `runtime-allocation-v1.retired.json` in 9 ms
under a 10-second timeout. SHA-256, device/inode `2306:10780300`, numeric
owner/group `999:988`, mode `0640`, size `1854` and mtime `1785699877` are
identical before and after. Required hash reads and namespace changes advanced
filesystem-managed atime/ctime; neither was rewritten. The first collector
attempt stopped before mutation, and three diagnostic renames were restored
automatically and exactly while isolating an invalid atime-equality assertion;
none changed bytes or stable metadata or touched another resource.

WorkSession 16 remains `OPEN/DRAFT/main` with its clean exact workspace and
`slot2=held/heavy1=held` admission, but no allocation, registry entry,
AgentRun, turn or runtime. Every other allocation, admission, four-slot
inventory, listener, registry and service projection remained byte-identical.
The AgentRun worker retained zero restarts, backup timers stayed active, RAID
remained `3/3 [UU]`, temporary browser processes remained zero, and
production, preview and Beautips remained HTTP 200.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-4.11-retire-closed-allocation`;
the SHA-256 of its `SHA256SUMS` is
`fe6560e0f1229b33b4503c6cbf31fec56d50a6e5cfa60be4112df33a574b6a82`.

Task 5.1 is complete and amended change progress is `25/28`; task 5.2 is the
exact resume point. The installed reviewed mediator completed the retained
WorkSession 16 activation in 1350 ms and an immediate idempotent repeat in
1213 ms, both under 300-second timeouts and with identical closed results.
No prompt was sent, no AgentRun was created and no runtime was started.

The WorkSession remains `OPEN/DRAFT`, persists `baseBranch=main`, remote
workload `project-codex-v1`, attachment policy
`atenea-real-attachments-v1`, worker `ax42-01` and exact workspace identity
`remote:ax42-01:work-session:7151dce0-69ab-4614-86e4-f93f1af825e4`.
Its clean worktree is at accepted main commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e` and tree
`3b8a5517bdc0845e3a2f52718173e6ef5307245a`.

Workspace-record SHA-256 remains
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`;
new allocation SHA-256 is
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`;
held admission SHA-256 remains
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`;
and the exact one-workspace enabled registry SHA-256 is
`6dbb541e51d672236af660e01f83d9f89b0e3c0a5652757340170f2a70ca87e7`.
The allocation owns `slot2/heavy1`, but containers, networks, volumes,
listeners and runtime units remain zero.

WorkSession turns, AgentRuns, attachments and previews remain zero, as do
global non-terminal AgentRuns and active leases. WorkSession 15's retired
allocation remains byte-identical. Worker services and backup timers remain
active, worker restarts remain zero, rootful daemons remain inactive/masked,
RAID remains `3/3 [UU]`, temporary browser processes remain zero, and
production, preview and Beautips remain HTTP 200.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.1-main-no-run-canary`;
the SHA-256 of its `SHA256SUMS` is
`10993b55fe0f70025519c4ab38735fc84d64f9447f656fd0c0e8d8c222afcd3e`.

Task 5.2 is complete and amended change progress is `26/28`; task 5.3 is the
exact resume point. The operator opened WorkSession 16 through the real
authenticated production web application and confirmed visible state `IDLE`,
`Base main`, `Sin runs` / `Codex en reposo` and a conversation ready to
operate. No prompt was sent and no session action was invoked.

That authenticated observation was cross-checked against the exact
control-plane projection and the production-served web bundle
`/assets/index-Aqg6-x4j.js`, SHA-256
`8f7e89bc6ed0adf4a65a71cadb7585685cc87af2546a890ccdb78f147a3cb6b4`.
The bundle contains the required base, no-run, resting and ready-state copy;
unauthenticated session, summary and conversation API requests remained
fail-closed at HTTP 401.

Workspace, allocation, admission and registry remain exact and the worktree
remains clean. No automated browser was launched, no operator browser profile
was inspected or closed, and AX42 temporary browser processes remained zero.
Production, preview and Beautips remained HTTP 200.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.2-web-api-ready-state`;
the SHA-256 of its `SHA256SUMS` is
`ce545a5e9aef04d9fc26578b8ecaa071d68568989366354e20f8124245dc7556`.

Task 5.3 is complete and amended change progress is `27/28`; task 5.4 is the
exact resume point. Final programme Git was clean and upstream-exact at
`c38e1763d1a258c8b59dc905a8e73e5fb4e90da3`. Canonical Atenea Git and the
AX42 mirror/worktree were clean and exact at main commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e`; both accepted historical tips
remain ancestors and the mirror passed full fsck.

WorkSession 16 remains open, draft, remote, main-based and prompt-free. Its
turns, AgentRuns, attachments, previews, runtime resources, listeners and
runtime unit are zero, as are global non-terminal AgentRuns and active leases.
Workspace, allocation, admission and registry fingerprints remain exact;
WorkSession 15's retired allocation remains byte-identical.

The complete rootless slot container inventory remains `3/0/0/3`, with
slot/inventory SHA-256
`54f050afa4baab9600b3e26cbd1d433cd4d6f60aab21d25effb0124da83db5f3`.
Worker services remain active with zero AgentRun-worker restarts. Both
external-backup timers remain active/enabled and their last services completed
successfully. Rootful Docker/containerd remain inactive/masked, RAID remains
`3/3 [UU]`, SSH/Tailscale/UFW remain active, temporary browser processes
remain zero, and production, preview and Beautips remain HTTP 200.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.3-final-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`2342c1fde6644c7f8f09aa13edbb96b11cd80be96a98e3ae6eb6e70de82e831a`.

Task 5.4 and `promote-atenea-canonical-base-to-main` are complete at amended
progress `28/28`. Twenty-four prior task/blocker evidence packages were
checksum-verified across the control plane and AX42 before archive. The active
change passed strict validation, added one requirement each to canonical
`atenea-project-onboarding` and `remote-work-continuity`, and was archived as
`2026-08-03-promote-atenea-canonical-base-to-main` with all 28 tasks marked.

Strict global validation passed all 12 canonical specifications with zero
failures. The aggregate SHA-256 of the two updated canonical specs is
`723d68c90e3898e36a603f7bf05be10cf22c95e01cd8314b453a4ab6cfb699d3`.
Post-archive checks retained zero WorkSession-16 turns, AgentRuns,
attachments, previews, non-terminal AgentRuns, active leases and runtime
resources; exact worker fingerprints; zero worker restarts; RAID `3/3 [UU]`;
zero temporary browser processes; and production, preview and Beautips HTTP
200. No prompt was sent and no runtime was started.

Sanitized closure evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/promote-atenea-canonical-base-to-main/runs/task-5.4-archive-closure`;
the SHA-256 of its `SHA256SUMS` is
`127ff3882176eda80342cc985c90177f6c7a712d7dc8957b3adf46f1e01477b9`.

## Active change: complete remote WorkSession close lifecycle

`complete-remote-worksession-close-lifecycle` is the active planned change at
`0/60`; task 0.1 is the exact implementation resume point. Its proposal,
design, five capability deltas and ordered task plan define the product and
worker correction required before consecutive canonical Atenea WorkSessions
can be considered operationally complete.

Read-only inspection found that production WorkSession 16 was closed after its
Git reconciliation but still owns the AX42 Atenea registration,
`slot2/heavy1` admission and active allocation SHA-256
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`.
It owns zero runtime containers, networks, volumes, listeners or runtime unit.
WorkSession 17 is open and clean on exact accepted `main`; its workspace record
SHA-256 is
`97b41b63e425eb483175b96bce875ac3190300cedb089b176aa2fdaedd515cbb`,
while its admission, allocation and runtime are absent.

Its first real AgentRun 96 failed before worker dispatch. The worker was active
and healthy but rejected workspace activation 81 times because fixed slot 2
was still owned. The authenticated HTTP 409 body was discarded by the current
client, so the coordinator used the network-unavailability window and finally
persisted the misleading generic error. The run has no remote execution
identity; its operator turn and one attachment remain durable. Their text and
content were not inspected.

The planned correction adds an additive V63 close lifecycle, typed bounded
worker failures, one exact idempotent workspace-release protocol, a
crash-resumable ownership finalizer, durable normal close, confirmed legacy
close reconciliation and state-first web/Android actions. All new gates remain
disabled by default. Task 6.8 requires a separate explicit production
authorization before V63, deployment, AX42 installation or activation. Task
7.7 then requires a real in-product single-use operator confirmation before
WorkSession 16 may be released. AgentRun 96 is never retried automatically.

At planning time no database row, worker configuration, admission, allocation,
runtime, route, prompt, attachment, service or production component was
modified. Canonical Atenea remains clean at
`615e539d1f2622a4ac2568ba7697b876d49ae33e`; the worker services, SSH,
Tailscale and firewall are active; production, preview and Beautips containers
remain up. Strict validation passes for the active change.

Task 0.1 is complete. Change progress is `1/60`; task 0.2 is the exact resume
point and has not started.

All three applicable `AGENTS.md` instruction sets, the complete 10,679-line
programme ledger, the phase dependency contract, proposal, design, all five
deltas, task plan, repository OpenSpec apply workflow, current canonical
continuity/worker-control/worker-safety/attachment/runtime/database/preview/
parity/onboarding/Codex-operation specifications and both runtime-contract
documents were read before implementation. OpenSpec reported the
`spec-driven` schema, complete planning artifacts and state `ready`.

A read-only guardrail pass found no Git, ownership, RAID, backup, runtime,
production, preview, Beautips or foreign-resource divergence before this
documentary task was recorded. It does not mark task 0.2; that task will retain
its own complete operational fingerprints after this commit is published. No
prompt, response, attachment content, screenshot, credential, token, cookie,
`auth.json`, Codex history or environment dump was read or retained, and no
production or worker operational state changed.

Strict validation passes. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-0.1-document-contract`;
the SHA-256 of its `SHA256SUMS` is
`3106f6b283bc1bb4e6983f7fffcc53d1f72d28db0af6540ecb64af2c8ea86f8f`.

Task 0.2 is complete. Change progress is `2/60`; task 0.3 is the exact resume
point and has not started.

Programme Git is clean and upstream-exact at
`a3692b6a9da5367cc88daa292edf94cee08a4159`. Canonical Atenea, the AX42 bare
mirror and both incident worktrees are clean and exact at main commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, tree
`3b8a5517bdc0845e3a2f52718173e6ef5307245a`; mirror fsck passes.

Production remains at V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal AgentRuns. Content-free WorkSession, AgentRun and project
projection SHA-256 values are respectively
`d2d9c94858d3cabb5e3f34547e5cac53ddb87a067840578871f36bfd469d319a`,
`52d570ef0b9f432aade2ab6c408d2112ebe9f45efe711fee26c1b27cd65dfa5a`
and `65b9a8aac96e221eb4db7301f478aa4be9583665ce7a8602cbb05a6a41985776`.
No turn text, result, attachment content or private identity was selected.

Production, preview and Beautips return HTTP 200. SSH, Tailscale, UFW and
control-plane Docker are active. AX42 SSH, Tailscale and UFW are active;
rootful Docker/containerd remain inactive/masked; all three RAID1 arrays are
`[UU]`. The AgentRun, attachment and preview services are active with zero
restarts. Backup, backup-check and worker-health timers are enabled/active and
their last services succeeded with exit 0.

Rootless running counts remain `3/0/0/3`. The exact registry, WorkSession 16
allocation/admission and WorkSession 17 workspace hashes remain
`6dbb541e51d672236af660e01f83d9f89b0e3c0a5652757340170f2a70ca87e7`,
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`,
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`
and `97b41b63e425eb483175b96bce875ac3190300cedb089b176aa2fdaedd515cbb`.
Both incident runtime namespaces have zero containers and no systemd unit.
Existing retained/administrative resources were fingerprinted only by counts
and hashes and were not adopted, repaired, stopped, removed or rebuilt.

Strict validation passes. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-0.2-live-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`7bf216bd615502ac38dbc8b1e5d63f6296a136c04f4f676043af7b88d4561731`.

Task 0.3 is complete. Change progress is `3/60`; task 0.4 is the exact resume
point and has not started.

The content-free incident projection confirms WorkSession 16 is `CLOSED` with
zero turns, AgentRuns, attachments, bindings, previews or owned ephemeral
resources, yet remains the sole registered Atenea workspace and exact owner of
the active allocation plus `slot2/heavy1`. WorkSession 17 is `OPEN` and clean
at accepted main with one immutable turn, one attachment, one binding and one
AgentRun, but no registration, admission, allocation, preview or runtime.

AgentRun 96 remains terminal `FAILED`, pre-dispatch and unretried. It has one
immutable dispatch ID, no remote execution, no live lease, no result turn and
no retry or replacement run. Its exact source is accepted Atenea main and its
complete retained profile is `gpt-5.6-sol`/`medium` from worker defaults,
catalog revision
`125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187`
and Codex `0.145.0`. The attachment manifest remains one item and 27,364 bytes.

The run entered reconciliation at `2026-08-03T19:34:30.923915Z` and failed at
`2026-08-03T19:36:31.517089Z`, a 121-second bounded window. V62 has no stable
failure-code column; reviewed worker source names its discarded 409 code
`workspace_activation_failed`, while the exact ownership projects to future
`CLOSED_SESSION_OWNS_CAPACITY`/`RECONCILE_REMOTE_CLOSE`. The accepted planning
artifacts retain the exact 81 activation attempts. The privacy-preserving
worker journal has 85 total fixed request events in the encompassing interval
but intentionally retains no route/status, so it was not used to invent
per-request attribution.

No turn message, response, original filename, private storage identity,
attachment byte, screenshot, credential, token, cookie, environment or Codex
history was selected or retained. No retry, dispatch, release, cleanup,
adoption or operational mutation occurred.

Strict validation passes. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-0.3-incident-projection`;
the SHA-256 of its `SHA256SUMS` is
`ab9718203f5993415c5e6ff9e34a9c6a1ca21c8eda6f24b0043d729eba590aa6`.

Task 0.4 and the complete entry section are complete. Change progress is
`4/60`; task 1.1 is the exact resume point and no V63 test or implementation
has started.

The repeated entry gate found no divergence. WorkSession 16 remains the sole
registered Atenea workspace and exact owner of its accepted workspace,
allocation and `slot2/heavy1` admission while its owned container, network,
volume, listener, preview and runtime-unit counts remain zero. WorkSession 17
remains open and clean at exact accepted main, with its registry, admission,
allocation, preview and runtime absent. AgentRun 96 remains terminal,
pre-dispatch and unretried with its retained turn, profile, attachment and
binding projection unchanged.

The AgentRun worker is active with zero restarts. Its tailnet listener returns
the expected unauthenticated 401 boundary from the control host and the
control-plane health row remains enabled/healthy at capacity `4/2`, usage
`0/0`. The initial loopback connection failure is expected because the service
is tailnet-only and caused no mutation.

Programme/canonical/mirror/worktree Git, production lifecycle and container
hashes, routing configuration, registry/admission/allocation aggregates,
service/listener projection and all rootless container/network/volume/image
hashes match task 0.2. Production, preview and Beautips remain HTTP 200;
backups and worker-health last succeeded; rootful daemons remain
inactive/masked and RAID remains `3/3 [UU]`. Every task 0.1–0.3 evidence seal
revalidates.

Strict validation passes. Sanitized closure evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-0.4-entry-closure`;
the SHA-256 of its `SHA256SUMS` is
`1da190af79c3e240255041604e72faf456347f661f8b69e5dd3d49a707033cc0`.

Task 1.1 is complete. Change progress is `5/60`; task 1.2 is the exact resume
point and no V63 implementation has started.

The dedicated canonical Atenea candidate branch
`codex/complete-remote-worksession-close-lifecycle-atenea-20260803` now fixes
the RED persistence contract at commit
`9a20854325b215ae1b9208d02999f8e573291e6c`, published exactly in both the
canonical repository and GitHub. Canonical Atenea `main` remains clean and
unchanged at `615e539d1f2622a4ac2568ba7697b876d49ae33e`.

Three domain tests now require the closed seven-state remote-close vocabulary,
durable WorkSession identity/revision/receipt/error/timestamp accessors and
safe WorkSession/AgentRun next-action read projections. Their expected RED
result is three errors caused only by absent V63 types and accessors. Three
isolated PostgreSQL migration tests require migration 63, exact additive
columns/indexes, local `NOT_REQUIRED`, open-remote `NOT_STARTED` and historical
closed-remote `UNVERIFIED_LEGACY` backfill, immutable operation identity,
monotonic revision and receipt/error plus failure/action consistency. Their
expected RED result is three errors caused only by absent migration 63. The
current V62 migration baseline remains green at 3/3. Both PostgreSQL 16 test
containers used Docker-selected loopback ports and were removed after their
finite runs.

The post-task read-only guard confirms production remains at V62 with 15
WorkSessions, 96 terminal AgentRuns and zero non-terminal AgentRuns.
WorkSession 16 remains `CLOSED/REMOTE` with its exact workspace, allocation and
admission hashes unchanged; WorkSession 17 remains `OPEN/REMOTE` with its
workspace hash unchanged; AgentRun 96 remains terminal `FAILED`, pre-dispatch
and unretried. Production, preview and Beautips remain HTTP 200 on their prior
images. Worker services remain active with zero restarts, rootless running
counts remain `3/0/0/3`, rootful daemons remain inactive/masked and RAID
remains `3/3` healthy. No routing, capability, database, service, runtime,
allocation, admission, registry or foreign resource was changed.

No prompt, response, attachment content, screenshot, credential, token,
cookie, `auth.json`, Codex history or environment dump was read or retained.
Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-1.1-v63-red-tests`;
the SHA-256 of its `SHA256SUMS` is
`7bc14b407f864b3ecb6ed6ab56e1bf391d89792fc0744d8718b11c1fe03f9395`.

Task 1.2 is complete. Change progress is `6/60`; task 1.3 is the exact resume
point.

Canonical Atenea candidate commit
`06c0c0704da30aec2a0144fd51e14e52f1cece0f` adds source-only migration V63
and is published exactly in the canonical repository and GitHub. The migration
adds the seven-state remote-close projection, one unique immutable operation
UUID, monotonic revision, safe error and receipt fields, durable timestamps,
closed consistency constraints, partial reconciliation indexes and a trigger
that rejects backwards lifecycle transitions or changes to persisted
operation/request/receipt/release facts. AgentRun receives a paired safe
failure-code/recovery-action projection, including the exact
`CLOSED_SESSION_OWNS_CAPACITY` to `RECONCILE_REMOTE_CLOSE` invariant; the
existing recovery next-action constraint is expanded additively.

The V63 backfill records local sessions as `NOT_REQUIRED`, non-closed remote
sessions as `NOT_STARTED` and historical closed remote sessions as
`UNVERIFIED_LEGACY`. It leaves operation, receipt, error and lifecycle
timestamps null at revision zero and never infers historical release. No
existing status, run, turn, delivery or attachment column is updated.

In isolated PostgreSQL 16, the V63 contract passes 3/3, the V62 migration
regression passes 3/3 and Codex operations migration integration passes 1/1.
The task-1.1 domain/read-model contract intentionally remains RED 3/3 until
task 1.3. All exact fixture containers were removed after finite runs.

Canonical Atenea `main` remains clean at
`615e539d1f2622a4ac2568ba7697b876d49ae33e`; production remains at V62 with
15 WorkSessions, 96 terminal AgentRuns and no non-terminal run. WorkSession 16,
WorkSession 17 and AgentRun 96 remain respectively `CLOSED`, `OPEN` and
terminal unretried `FAILED`. Production, preview and Beautips remain HTTP 200.
Worker services/restarts, rootless `3/0/0/3`, rootful masking, RAID and the
exact incident workspace/allocation/admission hashes remain unchanged. No
production migration, deploy, routing/gate change, runtime action or foreign
resource mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-1.2-v63-additive-schema`;
the SHA-256 of its `SHA256SUMS` is
`ec6f321623fbe77b5fbe6741c9eff554fed38823e01560dfdc8065e89a39d024`.

Task 1.3 is complete. Change progress is `7/60`; task 1.4 is the exact resume
point.

Canonical Atenea candidate commit
`27f9a7eb5e986f8cacffd0b169af931e03934d96` is published exactly in the
canonical repository and GitHub. It maps every V63 WorkSession remote-close
field and the paired AgentRun safe failure/action fields into JPA. The
seven-state lifecycle, durable operation identity, monotonic revision,
receipt, bounded error and timestamps are available to persistence without
changing any legacy row.

WorkSession and AgentRun API projections now expose only state, safe error
code and enum next action while retaining every existing local/legacy
constructor. Local sessions remain `NOT_REQUIRED`, newly routed remote
sessions begin at `NOT_STARTED`, and the legacy constructor conservatively
maps a historical closed remote session to `UNVERIFIED_LEGACY` without
claiming a receipt. Action mapping distinguishes reconciliation from
privileged platform review while retaining the prior summary fields.

The release and reconciliation gates remain disabled by default with an empty
server allowlist. Runtime evaluation requires the corresponding global flag,
exact allowlist membership and the hard-coded canonical identity `atenea`;
Beautips remains rejected even if accidentally added to that allowlist. No
production or worker configuration was changed.

The focused domain, default-gate, routing and read-model suite passes 76/76,
including the former task-1.1 RED domain contract at 3/3 green, and the
application package succeeds. In isolated PostgreSQL 16, the V63 migration
contract remains green 3/3 and Spring/Hibernate migration integration passes
1/1. The uniquely named fixture was removed after the finite run.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSession 16, WorkSession 17 and AgentRun 96 remain
`CLOSED`, `OPEN` and terminal unretried `FAILED`; WorkSession 17 still has one
turn, run, attachment and binding plus its execution profile. Production,
preview and Beautips remain HTTP 200. Worker services are active with zero
restarts, rootless counts remain `3/0/0/3`, rootful daemons remain
inactive/masked, RAID is `3/3`, backup timers and last results are healthy,
both incident worktrees are clean at accepted main and all exact incident
ownership hashes are unchanged. Neither incident owns an ephemeral runtime
resource.

No prompt, response, attachment content, screenshot, credential, token,
cookie, `auth.json`, Codex history or environment dump was read or retained.
No migration, deploy, routing, runtime, admission, allocation, registry,
service or foreign resource was mutated. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-1.3-remote-close-mapping`;
the SHA-256 of its `SHA256SUMS` is
`e05b5583e09cb6893cbbfce3c11a272e245b8ddbf0bc7b1cdf066814ce9d24ad`.

Task 1.4 is complete. Change progress is `8/60`; task 1.5 is the exact resume
point.

The latest accepted custom-format production backup,
`atenea_prod_before_real_attachments_v61_20260802T115453Z.dump`, remained mode
`0600`, 1,830,268 bytes and SHA-256
`02797fd448689316a7521c2976fc0e51a6d1eaa1e92442c7fb3ab7a29cc7a8f2`.
Its 496-entry catalog was read by PostgreSQL 16.13 and the dump was restored
into an empty task-owned database on tmpfs. Its Docker network was internal
only, published no port and contained no persistent write mount.

The rollback source is exact Atenea candidate commit
`27f9a7eb5e986f8cacffd0b169af931e03934d96`, tree
`179a019bdb5d0f57594320f01c169395efb5db4a`. This is the last published point
that understands V63 persistence/read models but has no remote-close writer.
The built image identity was
`sha256:1f29ae0e903d76c1b9fd2e838a1c5617b415115d37eb97b55c294c46af1a50e6`.

The restored snapshot began at V61/61 with 50 public tables, 10 WorkSessions
and 91 AgentRuns. Its first normal application start applied V62 and V63 once,
reached `UP`, exposed all eight WorkSession remote-close columns plus both
AgentRun failure/action columns and retained the 10/91 row counts. Conservative
backfill produced two `NOT_REQUIRED`, three `NOT_STARTED` and five
`UNVERIFIED_LEGACY` sessions.

A second normal start and an explicitly named rollback start both reached
`UP`, reported Flyway up to date and initialized JPA. The complete successful
Flyway-history SHA-256 remained
`3b300188c4f3f2b544a56abf8061d57f11ba8e336f23dad5c443236dd18659e3`,
with exactly one V63 row. Every new capability was explicitly false and both
remote-close allowlists were empty. No down migration or Flyway repair was
attempted.

All labelled containers, the internal network, image tag and exact source
export were removed by immutable task identity. Production remains V62 with
the same 15 WorkSessions, 96 terminal AgentRuns and zero non-terminal runs;
WorkSessions 16/17 and AgentRun 96 remain `CLOSED`/`OPEN`/unretried `FAILED`
with their retained 1/1/1/1 turn, run, attachment and binding projection.
Production, preview and Beautips remain HTTP 200. Worker ownership hashes,
services/restarts, rootless `3/0/0/3`, rootful masking, RAID `3/3` and
backup/health results remain unchanged.

No prompt, response, attachment content, screenshot, credential, token,
cookie, `auth.json`, environment dump or Codex history was read or retained.
No production migration, deployment, route, gate, service, runtime, ownership
or foreign resource was changed. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-1.4-v63-rollback-restore`;
the SHA-256 of its `SHA256SUMS` is
`9ae93d8d44613c5e288a655dd3f51cc6974e0f70401bf5035cd13763e7e11b6f`.

Task 1.5 and additive lifecycle persistence section 1 are complete. Change
progress is `9/60`; task 2.1 is the exact resume point and no section 2 work
has started.

Canonical Atenea candidate commit
`49e6cd9a6c11c1680837b92526fd422e4fceed7c` is published exactly in the
canonical repository and GitHub. The complete suite exposed four synthetic
REMOTE integration fixtures that still used the entity default
`NOT_REQUIRED`; the commit changes only those fixtures to declare V63
`NOT_STARTED`. The affected groups pass 14/14.

The final focused migration, persistence, routing and read-model suite passes
83/83. The complete Maven suite passes 627/627 with zero errors, failures or
skips from the exact candidate source in a finite isolated runner with Git, a
writable `/workspace/repos` test boundary and PostgreSQL 16.13 on tmpfs. The
database had no published port and its Docker network was internal only.

Rejected harness attempts were classified and excluded: four initial fixture
violations led to the source correction; the local host could not write the
suite's fixed `/workspace` boundary; and the minimal runner initially lacked
Maven provider artifacts, Git and the documented test workspace-root setting.
One discarded diagnostic over-selected generated integration authentication
responses. It did not involve production credentials; no value was copied to
evidence, and every report-bearing container/image was destroyed immediately.
All test containers, images, the tmpfs database, network and harness-only
Dockerfile are absent.

Production remains at V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSession 16 remains `CLOSED`, WorkSession 17 remains
`OPEN`, and AgentRun 96 remains terminal unretried `FAILED`. Exact registry,
WorkSession 16 workspace/allocation/admission and WorkSession 17 workspace
hashes match entry; WorkSession 17 still has no allocation or admission.
Production, preview and Beautips each return HTTP 200 from their exact internal
health surface. Worker services remain active with zero restarts, rootless
counts remain `3/0/0/3`, rootful daemons remain inactive/masked, RAID remains
`3/3 [UU]`, and backup/check/health results remain successful. No production
migration, deployment, configuration, routing, runtime, ownership or foreign
resource changed.

The retained package contains no report body, generated credential value,
prompt, response, attachment content, screenshot, cookie, `auth.json`,
environment dump or Codex history. Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-1.5-additive-persistence-closure`;
the SHA-256 of its `SHA256SUMS` is
`ca4a433793b66f8c82cec754fe6eeff394217710c02369869e3991a9c50b1973`.

Task 2.1 is complete. Change progress is `10/60`; task 2.2 is the exact resume
point and no client/coordinator handling has started.

The source-only worker now returns the closed `worker-error-v1` envelope for
HTTP rejection: schema version, uppercase safe code, closed category, boolean
retryability, closed next action and an optional canonical blocker WorkSession
UUID. Blocker identity is accepted only for capacity, encoded output is bounded
to 1,024 bytes and no free-form message is serialized.

Reviewed mediator input is bounded to 4,096 bytes and six allowlisted codes.
Structured input accepts only code plus optional blocker UUID; unknown fields,
unsafe detail/command/path authority, invalid or misplaced blocker UUID,
unknown code, invalid JSON and oversized output fail closed. Legacy reviewed
stderr contributes only its allowlisted leading code, and all remaining detail
is discarded. Unknown mediator failure becomes fixed
`WORKSPACE_ACTIVATION_FAILED` with platform review rather than copied stderr.

Eighteen focused envelope, activation and HTTP tests pass. The complete
AgentRun worker file passes 61/61, and the worker installer, sandbox and
rollback contract passes against program SHA-256
`189654227b5550a5ac23823c7164608ef47c3f36dc51afc6fa1f2a73631da2f7`.
No worker installation, service restart, configuration change or capability
activation occurred.

Production remains V62 with 15 WorkSessions and 96 terminal AgentRuns;
WorkSessions 16/17 and AgentRun 96 remain `CLOSED`/`OPEN`/unretried `FAILED`.
Production, preview and Beautips return HTTP 200. Worker services have zero
restarts, rootless slots remain `3/0/0/3`, rootful daemons remain inactive,
RAID remains `3/3 [UU]`, backup/check/health last results remain successful and
every exact incident ownership hash matches entry. No foreign resource was
adopted, repaired or mutated.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.1-typed-worker-errors`;
the SHA-256 of its `SHA256SUMS` is
`85d0e0385ad7b5969f129e1b5e3ea9b7105d6c3ae661aa2298b2f489511ea5ee`.

Task 2.2 is complete. Change progress is `11/60`; task 2.3 is the exact resume
point and coordinator admission decisions remain unchanged.

Canonical Atenea candidate commit
`17b53559718f7eb612a5e430057345acc6742c17` is published exactly in the
canonical repository and GitHub. `RemoteWorkerException` now retains HTTP
status, safe code, closed category, retryability, next action and optional
blocker UUID while preserving both existing constructors.

`RemoteWorkerClient` obtains response bodies as streams. Successful responses
continue through the unchanged record decoder. For a non-success response it
accepts only exact `application/json`, reads at most 1,025 bytes, rejects more
than the 1,024-byte worker limit, parses only `worker-error-v1`, validates all
fields and values, and zeroes its temporary byte buffer.

Unknown fields, malformed JSON, missing values, unknown schema/category/action,
worker-selected `RECONCILE_REMOTE_CLOSE`, invalid or misplaced blocker UUID,
wrong content type and oversized bodies become only
`REMOTE_WORKER_PROTOCOL_FAILURE` with platform review. Raw body bytes and
parser exceptions are never attached to the application exception, log or
persistence projection. A valid capacity envelope preserves only its safe
projection and canonical blocker UUID.

All 24 client tests pass, including unchanged success decoding and the complete
malformed/unsafe/oversized matrix. The related client, coordinator, routing and
attachment-manifest regression set passes 48/48. Maven report artifacts were
cleaned after aggregation. No source was deployed.

Production remains V62 with 15 WorkSessions and 96 terminal AgentRuns;
WorkSessions 16/17 and AgentRun 96 remain `CLOSED`/`OPEN`/unretried `FAILED`.
Production, preview and Beautips return HTTP 200. Worker services have zero
restarts, rootless slots remain `3/0/0/3`, rootful daemons remain inactive,
RAID remains `3/3 [UU]`, backup/check/health results remain successful and all
exact incident ownership hashes match entry. No foreign resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.2-strict-worker-client-errors`;
the SHA-256 of its `SHA256SUMS` is
`f747c63023c762e6d3c555e775a7431e5db03d20b8adda0190a53e7f2163141a`.

Task 2.3 is complete. Change progress is `12/60`; task 2.4 is the exact
resume point and no malformed-response repetition or retry-gating task has
started.

Canonical Atenea candidate commit
`317e93129ec7fd8992c9a12919920ec5ef8ae1ad` is published exactly in the
canonical repository and GitHub. The coordinator admits only status-zero I/O
failures or compatible typed, retryable transport 5xx responses to the finite
same-dispatch reconciliation window. Its persisted unavailable reason is now
fixed and never incorporates exception or response text. Every other rejection
leaves that window immediately with one safe failure projection.

Capacity handling accepts only a typed retryable 4xx `CAPACITY/WAIT` envelope,
then resolves its optional canonical blocker UUID through Atenea's unique
WorkSession identity. The reported owner must be a different remote session
with the same persisted project ID and worker plus its internally derived
canonical workspace identity. An exact `OPEN` or `CLOSING` owner leaves the
new run `QUEUED`, with a fixed reason and no dispatch. An exact `CLOSED` owner
with zero non-terminal runs becomes only
`CLOSED_SESSION_OWNS_CAPACITY/RECONCILE_REMOTE_CLOSE`; unknown, same-session,
foreign, partial, ambiguous or live-run ownership becomes
`CAPACITY_OWNER_UNVERIFIED/CONTACT_PLATFORM_ADMINISTRATOR`. The reserved local
closed-owner code cannot be selected by a worker rejection.

All 16 coordinator tests pass, covering status-zero I/O and compatible 503
reconciliation, immediate deterministic 409 failure, exact open-owner waiting,
exact closed-owner action and foreign-owner rejection without dispatch. The
related strict client, routing and attachment-manifest regression set passes
37/37, for 53/53 aggregate with zero failures, errors or skips. No source was
deployed and all new release/reconciliation gates remain false by default.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains
terminal unretried `FAILED`. Production, preview and Beautips are `UP`, routing
remains `ax42-01` enabled/healthy at `4/2` with `0/0` usage, worker services
remain active with zero restarts, rootless slots remain `3/0/0/3`, rootful
daemons remain inactive, all three RAID arrays remain `[UU]`, and
backup/check/health results remain `success/0`. Registry, WorkSession 16
workspace/allocation/admission and WorkSession 17 workspace SHA-256 values
match task entry; WorkSession 17 allocation/admission remain absent. No
production, preview, Beautips, routing, runtime, ownership or foreign resource
was changed.

The retained package contains summaries and hashes only: no prompt, response,
attachment content, screenshot, credential, token, cookie, `auth.json`, raw
HTTP body, mediator stderr, environment dump or Codex history. Sanitized
evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.3-coordinator-admission-decisions`;
the SHA-256 of its `SHA256SUMS` is
`c5043eb66f92531383c0ba2e12ec223a73379c059e24916c5211283b6da87317`.

Task 2.4 is complete. Change progress is `13/60`; task 2.5 is the exact
resume point and safe-retry blocker clearance has not started.

Canonical Atenea candidate commit
`16b96b7656e80795de3fccb7906dc406366b1017` is published exactly in the
canonical repository and GitHub. It adds proof only. The coordinator test set
now verifies that the safe projection produced for malformed worker-error
responses, an unknown capacity blocker, a foreign owner and an ownership-
mismatched success response is terminal platform-administrator review rather
than worker unavailability.

The deterministic activation rejection is observed for more than 81 possible
one-millisecond poll intervals. `ensureWorkspace` is still called exactly
once, dispatch is never called, and the terminal run retains no remote
execution identity, lease or `retryOfRun` replacement link. This directly
regresses the incident's former 81 impossible activation attempts without
reading or retrying its real prompt.

All 19 coordinator tests and all 24 strict worker-client malformed-response
tests pass: 43/43 total with zero failures, errors or skips. No application or
worker source was deployed and no capability gate was enabled.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 and AgentRun 96 remain
`CLOSED`/`OPEN`/unretried `FAILED`. Production, preview and Beautips remain
`UP`; routing remains enabled/healthy `4/2` at `0/0`; exact incident ownership
hashes, active zero-restart worker services, rootless `3/0/0/3`, inactive
rootful daemons, three `[UU]` RAID arrays and backup/check/health `success/0`
all match task entry. No foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.4-fail-closed-admission-proof`;
the SHA-256 of its `SHA256SUMS` is
`12001b29b68a41c25352478fe4be52b9563659226209cf461fab01a8e09d462c`.

Task 2.5 is complete. Change progress is `14/60`; task 2.6 is the exact
resume point and the section-wide regression/closure run has not started.

Canonical Atenea candidate commit
`2ac6267249ba0bd040f6d7c347c04341f5108fc8` is published exactly in the
canonical repository and GitHub. Retry now has two fail-closed checks. The
recovery coordinator rejects a deterministic blocker before canonical-source
admission or worker proof; `AgentRunService` repeats the same pure policy after
locking the source run and before looking up or creating a retry. V63 failures
are eligible only when their persisted next action is already `RETRY`; legacy
failures with no V63 projection retain existing compatibility. `WAIT`,
reconciliation and administrator actions cannot create or dispatch a retry.

The blocked proof performs zero admission calls, worker terminal/absence
proofs, retry creates or dispatches. It does not save a run, turn or binding,
does not validate attachment bytes and does not resnapshot the profile. The
eligible proof creates one linked run while the original failed run, origin
turn, model/effort/catalog/version snapshot and exact attachment count, bytes
and manifest SHA-256 remain unchanged; no binding or turn is recreated.

All 20 AgentRun service tests and all three recovery-coordinator tests pass:
23/23 total with zero failures, errors or skips. No real recovery request,
prompt, worker execution or source deployment occurred. AgentRun 96 was not
retried or read for content.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs; WorkSessions 16/17 and AgentRun 96 remain
`CLOSED`/`OPEN`/unretried `FAILED`. Production, preview and Beautips remain
`UP`, routing remains `ax42-01` enabled/healthy `4/2` at `0/0`, all five exact
ownership hashes match, worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful daemons remain inactive, all three
RAID arrays remain `[UU]`, and backup/check/health remain `success/0`. No
foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.5-deterministic-retry-gate`;
the SHA-256 of its `SHA256SUMS` is
`09830dac18ca52c8b5007d65236579870ca823ca7923ddc653c4be25d5ec0c74`.

Task 2.6 and typed worker failure/admission-decision section 2 are complete.
Change progress is `15/60`; task 3.1 is the exact resume point and no worker
workspace-release protocol work has started.

Canonical Atenea candidate remains
`2ac6267249ba0bd040f6d7c347c04341f5108fc8`, already published exactly in
the canonical repository and GitHub; this closure task required no source
correction. The exact candidate ran in a finite Maven 3.9.11 / JDK 21 container
against PostgreSQL 16.13 on `tmpfs`, on an internal-only Docker network with no
published database port. Flyway validated and applied all 63 migrations to the
empty fixture.

The strict client, coordinator, AgentRun service, recovery coordinator,
AgentRun API, session-operations API, recovery persistence, backend restart and
atomic image-turn suites pass 88/88 with zero failures, errors or skips. This
includes compatible partition reconciliation, deterministic one-attempt
rejection, exact cancellation, restart/resume continuity, blocked and linked
retry, strict malformed response handling, and immutable turn/profile/
attachment lineage. An expected negative atomic-persistence fixture logged its
synthetic foreign-key rejection and passed 4/4.

The first harness attempt stopped before compilation because its offline Maven
cache mount named the parent rather than repository root and its `tmpfs` was
non-executable for optional Jansi loading. It ran zero tests and changed no
database state. That exact runner was removed before the corrected run. After
success, the exact Maven runner, PostgreSQL `tmpfs` container and internal
network were removed; task-labelled container/network/image counts are
`0/0/0`.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 and AgentRun 96 remain
`CLOSED`/`OPEN`/unretried `FAILED`. Production, preview and Beautips remain
`UP`; routing remains `ax42-01` enabled/healthy `4/2` at `0/0`; exact incident
ownership hashes, active zero-restart worker services, rootless `3/0/0/3`,
inactive rootful daemons, three `[UU]` RAID arrays and backup/check/health
`success/0` all match entry. No source was deployed, no new gate was enabled
and no foreign or unrelated resource changed.

The retained evidence contains summaries and hashes only and no prompt,
response, attachment content, screenshot, credential, token, cookie,
`auth.json`, raw worker payload, environment dump or Codex history. Sanitized
evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-2.6-typed-failure-section-closure`;
the SHA-256 of its `SHA256SUMS` is
`986c6514e6b3f0d14281ce387ff9dfec4b839ee12f093b637f75a7c9d4be9abe`.

Task 3.1 is complete. Change progress is `16/60`; task 3.2 is the exact
resume point and no lifecycle lock, release preflight, journal or finalizer has
started.

The worker source now defines the closed request and
`project-workspace-release-v1` receipt contract for fixed route
`/v1/project-workspaces/release`. This task deliberately does not register that
HTTP route or expose a callable release operation, so release remains
unavailable by default. Beautips and every non-Atenea project remain
ineligible.

The request accepts exactly immutable operation, idempotency and WorkSession
UUIDs plus persisted workspace, canonical Atenea project, repository, branch,
40-hex commit, manifest and workspace-branch identity. Unknown fields reject
commands, paths, slots, ports, services, endpoints, resource names, labels,
credentials and deletion targets. Sharing either operation UUID or idempotency
key requires the identical canonical request fingerprint; changed input fails
with an immutable-identity conflict.

The response validator accepts only exact operation/request/worker ownership,
`RELEASED`, a positive monotonic revision, closed non-negative removal counts,
closed release booleans, all required retention booleans true, safe 64-hex
ownership fingerprint, `valuesExposed=false` and a matching receipt SHA-256.
The terminality guard rejects any exact-session `QUEUED`, `STARTING`,
`RUNNING`, `CANCELLING` or `RECONCILING` execution before a future release.

All five new contract tests pass, covering exact fixtures, immutable
repetition, caller-authority rejection, mismatched/open receipt rejection and
non-terminal execution. The complete AgentRun worker file passes 66/66. The
generated Python bytecode cache was removed before sealing. No worker source
was installed and no service or configuration changed.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 and AgentRun 96 remain
`CLOSED`/`OPEN`/unretried `FAILED`. Production, preview and Beautips remain
`UP`; routing stays enabled/healthy `4/2` at `0/0`; exact ownership hashes,
active zero-restart worker services, rootless `3/0/0/3`, inactive rootful
daemons, three `[UU]` RAID arrays and backup/check/health `success/0` all match
entry. No runtime, ownership, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.1-closed-release-contract`;
the SHA-256 of its `SHA256SUMS` is
`c65cd6ee77da894310e8cb91c8a8f294e137f0728ebff805cf29a164e1a95eed`.

Task 3.2 is complete. Change progress is `17/60`; task 3.3 is the exact
resume point and no release preflight or mutation has started.

One global persistent `workspace-lifecycle-v1.lock` now serializes the entire
Atenea `ensure` operation and is the sole shared participant for future
release. It is opened without following symlinks, must remain a regular file
owned by the worker effective UID at mode `0600`, and uses an exclusive
non-blocking `flock` with a finite monotonic deadline. Every path unlocks and
closes its descriptor.

A competing operation that exceeds the deadline returns only the closed safe
projection `WORKSPACE_LIFECYCLE_BUSY/CAPACITY/retryable/WAIT`; it invokes no
workspace activator. The concurrency proof holds ensure inside its registration
and admission boundary while a release participant waits, then proves release
enters only after ensure exits. Thus no two sessions can interleave those fixed
ownership transitions. The HTTP release route remains absent and capability
remains unavailable by default.

All nine workspace activation/lifecycle-lock tests pass, including persistence
mode, serialization and timeout. The complete AgentRun worker file passes
68/68. The generated Python cache was removed before sealing; no worker source
was installed.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 and AgentRun 96 remain
`CLOSED`/`OPEN`/unretried `FAILED`. Production, preview and Beautips remain
`UP`; routing remains `4/2` at `0/0`; exact ownership hashes, active
zero-restart services, rootless `3/0/0/3`, inactive rootful daemons, three
`[UU]` arrays and backup/check/health `success/0` all match entry. No ownership,
runtime, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.2-workspace-lifecycle-lock`;
the SHA-256 of its `SHA256SUMS` is
`a880a8f1bf2f7b75402b0ed30b96b0fcb3943e2b4849efc43f824fcd346c67ad`.

Task 3.3 is complete. Change progress is `18/60`; task 3.4 is the exact
resume point and no release journal or mutation has started.

The new internal Atenea finalizer contract performs one pure, complete,
fail-closed preflight before a future journal may be created. It first requires
the exact fixed workspace record, canonical worktree, project registry entry,
held normal/heavy admission and active allocation, all bound to the immutable
release request, deterministic session runtime and allocation SHA-256.

It then validates every internally observed runtime container, network,
session image, preview, listener, rootless/Codex proxy broker, attachment
materialization and temporary Codex/Playwright browser candidate against the
same session UUID, runtime ID, Atenea project, `ax42-01` worker, allocation
fingerprint and complete existing runtime labels. Resource identities must be
derived from the fixed contract; duplicate, partial, foreign, symlinked,
ambiguous, Beautips, production-like, unallocated-port or cross-preview
candidates reject the entire projection with one fixed safe code. Active
previews require exactly one matching tailnet listener, and runtime listeners
must correspond exactly to their rootless broker mappings.

The validator performs no filesystem, registry, process, socket or runtime
write. It exposes no CLI or HTTP route and has no journal or mutation method.
Its accepted result contains only closed candidate counts and request,
allocation and ownership SHA-256 fingerprints with `valuesExposed=false`.
Release therefore remains unavailable by default.

All ten complete preflight tests pass, including a byte-for-byte unchanged
input proof, empty and populated ephemeral projections, every authoritative
root, all eight ephemeral families, duplicate identities, foreign/session/
project/production ambiguity, allocation-derived listeners and canonical
materialization/browser operations. The preflight plus complete AgentRun
worker regression passes 78/78 with zero failures, errors or skips. Generated
Python bytecode was removed before sealing; no worker source was installed.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains
terminal unretried `FAILED`, and its origin turn, execution profile, one linked
attachment, exact count/bytes and attachment-manifest SHA-256 remain intact.
Production, preview and Beautips remain up with zero backend/control restarts;
routing remains `ax42-01` enabled/healthy `4/2` at `0/0`. Exact registry,
WorkSession 16 workspace/allocation/admission and WorkSession 17 workspace
hashes match entry, WorkSession 17 allocation/admission remain absent, and both
incident runtime candidate counts remain zero. Worker services remain active
with zero restarts, rootless slots remain `3/0/0/3`, rootful daemons remain
inactive, all three RAID arrays remain `[UU]`, and backup/check/health remain
`success/0`. No ownership, runtime, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.3-complete-no-write-preflight`;
the SHA-256 of its `SHA256SUMS` is
`26a11cef3d203b427f792da5136a49451f06dffb8b9848627c12a2b56d05c39a`.

Task 3.4 is complete. Change progress is `19/60`; task 3.5 is the exact
resume point and no ephemeral or ownership release mutation has started.

The finalizer now has one private session journal beneath the fixed worker
release root. `prepare` first repeats the complete task 3.3 preflight, then
persists immutable operation, idempotency, session, workspace, project,
worker, request, ownership and allocation identity at `PREPARED` revision 1.
Each later stage appends one evidence SHA-256 and may advance only to its direct
successor: `EPHEMERAL_RELEASED` revision 2, `UNREGISTERED` 3,
`ADMISSION_RELEASED` 4, `ALLOCATION_RETIRED` 5 and `RELEASED` 6. Skips,
retrogression and a wrong expected state reject unchanged.

Every record is a regular single-link private `0600` JSON file in a private
`0700` session directory. It carries a SHA-256 self-seal and an exact
cumulative evidence prefix. Writes use a same-directory temporary file,
complete write, file fsync, atomic replace and directory fsync. Before replace,
the writer reopens without following symlinks and compares the current seal to
the exact revision read at entry. A competing, forged, partial, wrong-mode,
symlinked or identity-changed journal is therefore never overwritten.

All 19 preflight/journal tests pass. They prove all six revisions, stable
repeated `PREPARED`, changed request/preflight rejection, skip/backward/wrong-
expected rejection, schema/revision/evidence/seal corruption, private mode and
single link, no symlink following, bounded evidence, atomic replace failure and
a valid competing-revision TOCTOU event. The journal plus complete AgentRun
worker regression passes 87/87 with zero failures, errors or skips. Only
private temporary fixtures were written; no installed journal root exists and
the release route remains unavailable.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains
terminal unretried `FAILED`, with its origin turn, execution profile, linked
attachment and exact attachment projection intact. Production, preview and
Beautips remain up with zero restarts; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`. All five incident ownership hashes match
entry, WorkSession 17 allocation/admission remain absent and both incident
runtime candidate counts remain zero. Worker services remain active with zero
restarts, rootless slots remain `3/0/0/3`, rootful daemons remain inactive,
RAID remains `3/3 [UU]` and backup/check/health remain `success/0`. No runtime,
ownership, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.4-immutable-release-journal`;
the SHA-256 of its `SHA256SUMS` is
`2b41bd0d36662e4136df2c1667c83a89e13a306a31f4ef125ea4ce5cb6eadb73`.

Task 3.5 is complete. Change progress is `20/60`; task 3.6 is the exact
resume point and interruption/restart idempotence proof has not started.

The finalizer now binds each journal stage to one closed mutation result. It
removes exact projected browser processes, attachment materializations,
previews, listeners, rootless/Codex brokers, runtime containers, networks and
session images in fixed order. The narrow reviewed boundary passes only the
already preflighted category, exact resource ID and sealed candidate to its
internal operator, requires one exact ownership-matching removal response and
never exposes a caller-selected command, path, slot, port, endpoint, label or
target. Policy-retained volumes are outside the removal interface.

Only after exact ephemeral release does it unregister the selected session and
workspace identity, require zero remaining registration with project selection
and execution disabled, release heavy admission before normal admission, and
retire the active allocation. A final exact proof must show zero ephemeral
resources, absent registration, released heavy/normal admission, absent active
allocation, present retired allocation and every declared retained class true
before the journal can reach `RELEASED` revision 6.

The allocation successor derives its source and canonical retired name solely
from the session UUID under the fixed workspace root. It rejects symlinks,
wrong fingerprints and any existing retired target, performs a same-directory
rename plus directory fsync, then proves identical bytes, device, inode, UID,
GID, mode, size and mtime. It observes atime/ctime without setting either.
Workspace record, worktree, Git, turns, AgentRuns, attachments, logs, artifacts,
backups and policy-retained volumes are never passed to a deletion primitive.

All 30 release tests pass. They prove exact candidate IDs and order, unchanged
input projection and retained volume, heavy-before-normal, closed stage result
validation, blocked progression on wrong removal/unregistration/admission/
allocation/retention evidence, default-unavailable production boundary, and a
real temporary allocation rename with retained sentinel plus wrong-hash,
existing-target and no-follow symlink negatives. The release plus complete
AgentRun worker regression passes 98/98 with zero failures, errors or skips.
No installed finalizer, route, service, configuration or runtime was invoked.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains
terminal unretried `FAILED`, with origin turn, profile, linked attachment and
exact attachment projection intact. Production, preview and Beautips remain up
with zero restarts; routing remains `ax42-01` enabled/healthy `4/2` at `0/0`.
All incident hashes remain exact, WorkSession 17 allocation/admission remain
absent and both incident runtime candidate counts remain zero. Worker services
remain active with zero restarts, rootless slots remain `3/0/0/3`, rootful
daemons remain inactive, RAID remains `3/3 [UU]` and backup/check/health remain
`success/0`. No ownership, runtime, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.5-exact-ordered-release`;
the SHA-256 of its `SHA256SUMS` is
`414707a9b19a9fdcdf529772923f50b3dd9c9c4961a59217deac0e5fc33b7883`.

Task 3.6 is complete. Change progress is `21/60`; task 3.7 is the exact
resume point and foreign/partial fixture creation has not started.

The private journal now retains the exact immutable request, complete accepted
preflight projection and candidate counts beneath its existing self-seal. On
restart, the finalizer opens that plan only by the same operation,
idempotency, session and request fingerprint. It never recomputes already
released ownership from an incomplete current host projection and never adopts
a replacement operation.

Each stage is reentrant for its sealed planned targets. Exact already-absent
ephemeral resources, already-absent registration, already-released admission
and the exact already-retired allocation return a closed unchanged result;
they do not recreate or mutate ownership. The finalizer evaluates the current
journal state before each boundary, so a persisted stage is skipped entirely.
An allocation retry accepts only absent active plus matching regular retired
record and returns its preserved identity with `changed=false`.

All 33 focused tests pass. Six interruption cases stop immediately after each
mutation boundary—ephemeral, unregister, heavy, normal, allocation and final
retention proof—then instantiate a new journal store/finalizer and finish the
same operation with every real state change counted once. Five lost-response
cases stop after persisting each post-`PREPARED` revision and prove the resumed
process does not call that completed stage again. A completed repetition calls
no boundary and returns the identical strict
`project-workspace-release-v1` receipt, revision 6, request/ownership
fingerprints and receipt SHA-256; the existing worker receipt validator accepts
it exactly. The focused plus complete AgentRun worker regression passes
101/101 with zero failures, errors or skips.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains
terminal unretried `FAILED`, with its origin turn, profile and linked
attachment projection intact. Production, preview and Beautips remain up with
zero restarts; routing remains `ax42-01` enabled/healthy `4/2` at `0/0`. All
incident hashes remain exact, WorkSession 17 allocation/admission remain absent
and both incident runtime candidate counts remain zero. Worker services remain
active with zero restarts, rootless slots remain `3/0/0/3`, rootful daemons
remain inactive, RAID remains `3/3 [UU]` and backup/check/health remain
`success/0`. No installed release boundary exists and no ownership, runtime,
foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.6-crash-resume-stable-receipt`;
the SHA-256 of its `SHA256SUMS` is
`54f9a5ad4b89871222133ba7ed098bf23b7b698ee7c4d093991b9b6d068cf090`.

Task 3.7 is complete. Change progress is `22/60`; task 3.8 is the exact
resume point and installer/sudoers/rollback work has not started.

One private synthetic fixture set covers unlabelled, partially labelled,
foreign-owned, wrong-session, wrong-project, symlinked and ambiguous
ownership. Before denial, the harness records each fixture's device, inode,
mode, size and content SHA-256. Every deterministic preflight rejection leaves
the complete recorded set and an unrelated sentinel byte-identical. The
symlink case is inspected with `lstat` and never followed.

After all rejections, cleanup unlinks only a fixture whose live complete
`lstat` identity still equals its recorded identity. All eight exact fixture
paths, including the symlink and its synthetic target, are absent afterward;
the unrelated sentinel remains exact. The isolated adversarial test passes
1/1, all focused release tests pass 34/34 and the focused plus complete
AgentRun worker regression passes 102/102 with zero failures or errors. The
fixtures existed only beneath bounded temporary test state; no real worker
resource was created, adopted or removed.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview health remain
`UP`; production, preview and Beautips containers remain running with zero
restarts; routing remains `ax42-01` enabled/healthy `4/2` at `0/0`. All five
incident ownership hashes remain exact, WorkSession 17 allocation/admission
remain absent and both incident container candidate counts remain zero.
Worker services remain active with zero restarts, rootless slots remain
`3/0/0/3`, rootful daemons remain inactive, RAID remains `3/3 [UU]` and
backup/check/health remain `success/0`. No source was installed and no route,
deployment, configuration, ownership, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.7-adversarial-ownership-fixtures`;
the SHA-256 of its `SHA256SUMS` is
`9fc86f79eb50cd64f1ddf34099a88c13229ba9d84121fc02ed4d9a9fe7986e18`.

Task 3.8 is complete. Change progress is `23/60`; task 3.9 is the exact
resume point and the section-wide sorted worker closure run has not started.

The dedicated Atenea workspace lifecycle installer now recognizes only an
all-absent bundle, the exact activation-only predecessor, the exact successor
or the one disable-first rollback intermediate. Fixed SHA-256 values cover the
activation mediator, release mediator, session-workspace, admission,
allocation and current AgentRun worker sources. Apply repeats whole-bundle
preflight before writing, creates the private `0700 root:root` journal root,
installs both exact mediators and then verifies owner, group, mode, hash and
sudo syntax.

The successor sudoers has exactly two rules: the retained fixed Atenea ensure
form and the workspace-release program with no arguments. It contains no
release wildcard, client path, slot, port, service, endpoint, label or resource
authority. Both the dedicated installed verifier and the worker installer
require this exact rule set, exact program hash and exact journal root. Their
safe result explicitly reports `releaseEnabledByDefault=false`; no worker
route, service or production gate was enabled.

Rollback first atomically restores the activation-only sudoers predecessor,
then removes only the still-exact successor release program. It retains the
activation mediator, all three reviewed dependencies, journal root and every
record beneath it. Repetition is unchanged/idempotent; the exact intermediate
resumes. A foreign release program, broadened sudoers, partial bundle, symlink
or changed dependency rejects without removal. Sandbox apply/reapply proves a
retained operation remains byte-identical, and rollback proves both its journal
and an unrelated operation remain exact.

All four shell files pass syntax validation; both installer/rollback suites
pass. The release finalizer and complete AgentRun worker regressions pass
34/34 and 68/68 respectively, 102/102 aggregate, with zero failures or errors.
The current AX42 installation remains the exact activation-only predecessor:
the release binary, journal root and release sudo rule are absent, while the
one existing ensure rule remains.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview remain `UP`;
production, preview and Beautips remain running with zero restarts; routing is
still `ax42-01` enabled/healthy `4/2` at `0/0`. All five incident ownership
hashes remain exact, WorkSession 17 allocation/admission remain absent and both
incident container candidate counts remain zero. Worker services remain
active with zero restarts, rootless slots remain `3/0/0/3`, rootful daemons
remain inactive, RAID remains `3/3 [UU]` and backup/check/health remain
`success/0`. No deployment, installation, activation, ownership or foreign
resource mutation occurred.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.8-exact-release-installer-rollback`;
the SHA-256 of its `SHA256SUMS` is
`d29a1cd08c008f26db2e5648e5246c76c1d67719dfc43124bf45569298693b5e`.

Task 3.9 and worker exact-release section 3 are complete. Change progress is
`24/60`; task 4.1 is the exact resume point and no control-plane client or
close-orchestration work has started.

One detached clean programme worktree at
`92bef8ab8bba4b99ac708887604e913ceabcdb5d` and a separate clean canonical
Atenea input copy at `615e539d1f2622a4ac2568ba7697b876d49ae33e`
ran all 33 top-level worker test entrypoints in bytewise lexical order. Every
entrypoint had a 900-second outer timeout. All 33/33 passed in 492 aggregate
entrypoint seconds with zero nonzero exits. The exact result table SHA-256 is
`4abc7d16d3c946b53984f3543b4fadef90568a8ab3ae86011a574aa5340f664a`;
its normalized index/name/exit SHA-256 is
`79067a973bcc7055bf71ac516372de8defa5f9c3b10c5f98cb0068890f2772e6`.

The pass contains 20 unittest reports totalling 239 tests, with zero failures
or errors. One test is deliberately skipped: real encrypted Restic integration
requires separate `RESTIC_REAL_INTEGRATION=1`; all six bounded backup contract
tests pass and live backup/check/health remain `success/0`. The accepted suite
includes the 34 release tests, both workspace lifecycle installer/rollback
entrypoints, the AgentRun installer/rollback entrypoint, real synthetic
Playwright validation, browser cleanup, ownership denial, runtime, admission,
allocation, workspace, attachment, preview, database and backup contracts.

After success, the registered programme worktree, Atenea input copy, logs,
visual registry and explicit Playwright wrapper were removed only by their
validated temporary identities. Known test roots, bytecode roots, screenshots,
fixture containers, networks, images, listeners, brokers and
Playwright/Chromium processes are all zero locally and on AX42. Rootless slot
inventory remains `3/0/0/3`; no task-labelled resource or candidate unit
exists.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview health remain
`UP`; production, preview and Beautips containers remain running with zero
restarts; routing stays `ax42-01` enabled/healthy `4/2` at `0/0`. All five
incident ownership hashes remain exact and WorkSession 17 allocation/admission
remain absent. Worker services remain active with zero restarts, rootful
daemons remain inactive, RAID remains `3/3 [UU]`, and no release binary,
journal root or release sudo rule is installed. No deployment, installation,
activation, ownership, production, preview, Beautips, foreign or unrelated
resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-3.9-worker-release-section-closure`;
the SHA-256 of its `SHA256SUMS` is
`5a6e92ff3b2a17db98119926081fe19f69f21285a3da1c0f1236ed931e5107e1`.

Task 4.1 is complete. Change progress is `25/60`; task 4.2 is the exact resume
point and normal close orchestration has not been changed.

Atenea commit `4f735cc8646e7b90e91b06f110acd7582f1e052d` adds one
`releaseWorkspace(WorkSessionEntity)` client boundary. Its ten-field request
is derived only from the persisted immutable remote-close UUID, remote session,
workspace and canonical source observation plus the fixed Atenea worker,
project, repository, branch and manifest identities. The one persisted close
UUID is also the idempotency boundary. No caller command, path, slot, port,
service, endpoint, resource name, label, credential or deletion target can be
supplied.

The client rejects before network I/O unless the WorkSession is the exact
remote Atenea owner, pinned to `ax42-01`, the canonical workspace identity and
branch, a complete canonical source observation and a durable requested,
reconciling or blocked close operation. A success must be the exact closed
`project-workspace-release-v1` object. It validates request and worker
ownership, `RELEASED`, positive revision, non-negative closed removal counts,
closed release booleans, every retained class `true`, `valuesExposed=false`,
both SHA-256 fields, the cross-language canonical request fingerprint and the
receipt seal. Unknown, foreign, unsafe or unsealed success responses become a
non-retryable protocol failure rather than worker unavailability.

The focused `RemoteWorkerClient`, project-identity and default-gate matrix
passes 30/30 with zero failures, errors or skips; the backend package also
passes. The canonical Java request fingerprint equals Python's sorted compact
JSON SHA-256,
`205ff648ddd1d736a40c92e695d395c565f006ec245ee0de291629bcb2b903b7`.
No feature gate was enabled, no release route was invoked and Beautips remains
ineligible for this operation.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with its one origin turn, complete profile,
one attachment binding and one retained attachment intact. Production and
preview remain `UP`; Beautips returns HTTP 200; all six observed containers
remain running with zero restarts. Routing remains `ax42-01` enabled/healthy
`4/2` at `0/0`.

The five exact incident ownership hashes remain unchanged, WorkSession 17
allocation/admission remain absent, worker services remain active with zero
restarts, rootless slots remain `3/0/0/3`, rootful daemons remain inactive,
all three RAID arrays remain `[UU]` and backup/check/health remain `success/0`.
The release binary and journal root remain absent. No deployment, schema,
configuration, ownership, production, preview, Beautips, foreign or unrelated
resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.1-strict-release-client`;
the SHA-256 of its `SHA256SUMS` is
`47ed2670eb57224483204b65b919afd4178ed10e1e4f00d8872c7bddb2b722c4`.

Task 4.2 is complete. Change progress is `26/60`; task 4.3 is the exact resume
point and startup reconciliation has not been implemented.

Atenea commit `7a9f4035726e87ae335d395df458a1115862da6f` refactors
normal WorkSession close into three independent `REQUIRES_NEW` commits. The
first reconciles terminal AgentRuns, pull-request delivery and Git. For a
remote session, the second creates or reuses one immutable close UUID and
persists `CLOSING/REQUESTED` before any worker I/O. Only after the strict
client returns an exact receipt does the third atomically persist the receipt
SHA-256, monotonic revision, release time and `CLOSED/RELEASED`.

Local WorkSessions retain the prior Git/delivery path and close in the first
transaction with `NOT_REQUIRED` and no worker call. A remote close with its
default-off gate disabled remains `CLOSING/NOT_STARTED`, creates no operation
and performs no worker I/O. Transport failure retains the committed operation
as `CLOSING/RECONCILING`; deterministic ownership rejection retains it as
`CLOSING/BLOCKED`. Neither path records a receipt or `closedAt`. Re-entry from
`BLOCKED` advances through `RECONCILING` with the same UUID rather than
creating replacement ownership.

The accepted service, client and default-gate matrix passes 74/74. A separate
PostgreSQL 16 fixture migrated empty and V62 schemas through V63 and passed the
3/3 monotonic persistence tests, for 77/77 accepted tests with zero failures,
errors or skips. The backend package also passes. The application HTTP test
context started and migrated through V63, but its historical Git fixtures are
hard-coded below `/workspace/repos`; this user cannot create `/workspace`, so
25 cases stopped uniformly with `AccessDenied /workspace` before assertions.
Permissions and that global path were not changed. The exact task PostgreSQL
container was removed.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview remain `UP`,
Beautips returns HTTP 200 and routing remains `ax42-01` enabled/healthy `4/2`
at `0/0`.

All five incident ownership hashes remain exact; WorkSession 17 allocation and
admission remain absent. Worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful Docker/containerd remain inactive,
all three RAID arrays remain `[UU]` and backup/check/health remain `success/0`.
The release program and journal root remain absent. No production migration,
deployment, gate, route, release, ownership, foreign or unrelated resource was
changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.2-durable-normal-close`;
the SHA-256 of its `SHA256SUMS` is
`d02bd416ddb2bfa64def5a180a21a96ce50ebbc91fdc0d86f588fa0e3cbd9e9d`.

Task 4.3 is complete. Change progress is `27/60`; task 4.4 is the exact resume
point and no legacy planning or administrator confirmation operation exists.

Atenea commit `4aebd7e630adaf3c107b4191a66ce240427deafc` adds
explicit reconciliation of a normal `CLOSING` remote WorkSession only when it
already owns an immutable close operation. The operator path and startup path
both reuse the task-4.2 transaction/receipt boundary. They cannot create a new
operation from `NOT_STARTED`, repeat Git/delivery mutation, choose another
worker or workspace, or retry an AgentRun or prompt.

Startup is independently default-off. When enabled for canonical Atenea, it
reads only `CLOSING` rows and attempts exact `REQUESTED` or `RECONCILING`
owners. Local, foreign, incomplete and deterministically `BLOCKED` rows are
ignored. One failed attempt leaves its durable projection authoritative and
does not prevent a later eligible row from being attempted.

The 78/78 focused tests pass with zero failures, errors or skips and the
backend package passes. They simulate process loss after the request commit,
loss of the worker response after release, and failure immediately before the
final database commit. Every recovery repeats the same operation UUID, calls
no Git reconciliation again, accepts the same strict receipt and reaches
`CLOSED/RELEASED` once. Default-off startup performs no query or worker I/O.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview remain `UP`,
Beautips returns HTTP 200 and routing remains `ax42-01` enabled/healthy `4/2`
at `0/0`. The five incident ownership hashes remain exact, rootless slots
remain `3/0/0/3`, rootful daemons remain inactive, RAID remains `3/3 [UU]` and
backup/check/health remain `success/0`. The release boundary remains absent;
no startup reconciliation ran against production and no deployment,
configuration, ownership, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.3-close-reconciliation`;
the SHA-256 of its `SHA256SUMS` is
`f1b9e2f61aca5c5d0237fceef6258abba2baf8186493d2f5a04c8cbd24a5b42e`.

Task 4.4 is complete. Change progress is `28/60`; task 4.5 is the exact resume
point. No worker diagnosis or legacy release has been implemented.

Atenea commit `fea34411b9c0c749fd6471744136c8ac7be354ba` adds a
read-only plan for one explicitly selected `CLOSED/REMOTE` canonical Atenea
legacy WorkSession and a fixed `RECONCILE_REMOTE_CLOSE` confirmation. Both
operations are hidden while the existing reconciliation gate is off, accept
only server-bounded fields and require an active `PLATFORM_ADMINISTRATOR`.
The plan persists an exact server-derived ownership/Git/delivery SHA-256 and
expires after ten minutes. Confirmation is single-use and idempotent, rejects
stale ownership and persists only one `REQUESTED` operation. It performs no
worker call, legacy scan, WorkSession transition or resource release.

The focused migration, service, HTTP, normal-close, startup, strict-client and
default-gate matrix passes 86/86 with zero failures, errors or skips; the
backend package also passes. A complete-suite attempt observed 655 tests and
27 environment or historical-fixture errors: 25 fixed `/workspace` Git
fixtures stopped before assertions because that root is not writable by this
user, and two mobile event contexts reached the isolated PostgreSQL fixture's
default client limit after accumulated Hikari pools. No global permission,
fixture path or database limit was changed; task 4.7 remains the explicit
complete-suite gate.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete execution profile. Production
and preview remain `UP`, Beautips returns HTTP 200, all observed containers
remain running with zero restarts and routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

The five incident ownership hashes remain exact; WorkSession 17 allocation
and admission remain absent. Worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful daemons remain inactive, RAID remains
`3/3 [UU]` and backup/check/health remain `success/0`. The release boundary
remains absent. No deployment, schema, configuration, ownership, production,
preview, Beautips, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.4-legacy-close-planning`;
the SHA-256 of its `SHA256SUMS` is
`25363a9716108dda1172118ee2d34afdf305c24ff1c986d1e5c82efcf71dd985`.

Task 4.5 is complete. Change progress is `29/60`; task 4.6 is the exact resume
point. Safe legacy-operation error audit and AgentRun retry projection remain
pending.

Atenea commit `66c9990e3a71cd2136732d205b410459e45163c8` turns the
confirmed exact legacy request into a durable release lifecycle. One
`REQUIRES_NEW` transaction locks and revalidates the selected historical owner,
proves its plan and unchanged ownership/Git/delivery fingerprint, requires zero
non-terminal AgentRuns, persists one immutable operation UUID and advances only
the remote-close projection to `REQUESTED`. The strict worker endpoint then
performs its exact preflight before release. A second independent transaction
accepts only the matching `RELEASED` receipt and advances the projection to
`RELEASED`; historical `CLOSED`, `closedAt`, turns, runs, delivery and retained
resources remain unchanged.

Open, foreign, partially identified, stale, expired, wrong-role and
non-terminal owners fail before worker I/O. A synthetic lost response leaves
the single operation durable, and repeating the exact confirmation reuses that
UUID, accepts the worker's idempotent receipt and closes the remote ownership
projection once. No replacement operation, prompt retry or caller-selected
resource is possible.

The focused migration, legacy service/API, normal close, startup, strict client
and default-gate matrix passes 89/89 with zero failures, errors or skips; the
backend package passes. Task 4.7 remains the explicit complete-suite gate.

Production remains V62 at 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains terminal unretried `FAILED`. Production and preview remain `UP`,
Beautips returns HTTP 200 and routing remains `ax42-01` enabled/healthy `4/2`
at `0/0`. The five ownership hashes remain exact, rootless slots remain
`3/0/0/3`, rootful daemons remain inactive, RAID remains `3/3 [UU]` and
backup/check/health remain `success/0`. No release was invoked outside the
synthetic mocked test boundary and no production, preview, Beautips, ownership,
foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.5-confirmed-legacy-release`;
the SHA-256 of its `SHA256SUMS` is
`9b76b6d73b36cacd8663b172c8ee7781c671a0d4719d170507a8308650ed6b85`.

Task 4.6 is complete. Change progress is `30/60`; task 4.7 is the exact resume
point. The complete backend regression and section-4 closure remain pending.

Atenea commit `1c2ac3d2015522813773928b7eb3318dca1a761d` adds an
append-only revision audit to each exact legacy close operation. The current
projection and every audit event retain only bounded state, safe error code,
typed category, next action, retryability, timestamps and the sealed release
receipt; no raw worker body or exception message is persisted or returned.
Transport loss remains `RECONCILING` with the immutable operation available
for exact replay. A deterministic 4xx becomes monotonic `BLOCKED`; repeating
the same confirmation returns the same projection without another worker
call and never enters the worker-unavailable window.

A deterministic AgentRun capacity failure now records the exact closed
WorkSession that blocked it. Generic retry remains unavailable until that same
canonical Atenea owner has a persisted `RELEASED` WorkSession projection and a
matching released legacy-operation receipt. The recovery coordinator still
requires the prior remote execution to be terminal or absent before creating
any retry. AgentRun 96 was neither retried nor modified.

The final migration, legacy close, normal close, startup, strict client,
default-gate, AgentRun retry/recovery and persistence matrix passes 144/144
with zero failures, errors or skips; the backend package passes. An earlier
expanded run exposed synthetic fixture teardown ordering against the intended
`RESTRICT` audit FK. Symmetric teardown fixed the fixture, the task-owned
database was recreated, and the complete focused matrix passed afterward.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete profile. Production and preview
remain `UP`, Beautips returns HTTP 200 and all observed related containers are
running with zero restarts. Routing remains `ax42-01` enabled/healthy `4/2` at
`0/0`.

The four directly rechecked incident ownership files retain their exact
accepted SHA-256 values; WorkSession 17 allocation and admission remain
absent. Worker services remain active with zero restarts, rootless slots remain
`3/0/0/3`, rootful daemons remain inactive, RAID remains `3/3 [UU]` and
backup/check/health remain `success/0`. No production migration, deployment,
configuration, release, prompt, ownership, preview, Beautips, foreign or
unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.6-safe-lifecycle-audit`;
the SHA-256 of its `SHA256SUMS` is
`be804b444c484ac52003d0af6d8629616cc0104f59b48a7c8ba91f11a786b9ce`.

Task 4.7 and section 4 are complete. Change progress is `31/60`; task 5.1 is
the exact resume point and no state-first UI work has started.

Atenea commit `bdd6ea8a82167a6da18a83309e12bed03a9a3fcc` records the
verified durable close lifecycle in the WorkSession architecture document.
The complete backend unit, integration, concurrency and restart suite passes
662/662 across 104 classes with zero failures, errors or skips. A separate
39-class close, attachment, notification, recovery, restart, GitHub and pull
request matrix passes 277/277, and the backend package passes.

The first complete-suite runner omitted the synthetic workspace-root setting
corresponding to its historical mounted repository path, so 25 Git fixtures
failed deterministic path validation before assertions. No code or shared
fixture changed. The task-owned database and result volume were recreated, the
runner setting was corrected and the complete suite passed. Only aggregate XML
results were retained; raw test logs and fixture messages were not read into
the evidence.

Production remains at V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote and AgentRun
96 remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete execution profile. Production
and preview remain `UP`, Beautips returns HTTP 200, all observed related
containers remain running, and routing remains `ax42-01` enabled/healthy `4/2`
at `0/0`.

The four incident ownership files retain their exact accepted SHA-256 values;
WorkSession 17 allocation and admission remain absent. Worker services remain
active with zero restarts, rootless slots remain `3/0/0/3`, rootful daemons
remain inactive, RAID remains `3/3 [UU]` and backup/check/health remain
`success/0`. No production migration, deployment, configuration, release,
prompt, ownership, preview, Beautips, foreign or unrelated resource changed.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-4.7-backend-section-closure`;
the SHA-256 of its `SHA256SUMS` is
`80ddd00d89bea246f1a013f4bdd7933c08b8f4726a797879f66f58bad2a76486`.

Task 5.1 is blocked and remains the first pending task. Change progress remains
`31/60`; no task 5 implementation has been committed or published.

The current conversation, close and recovery UI was analyzed and a minimal
shared operator-state read model was started locally. Before those changes
could be tested, the repository-mandated `scripts/test.sh` stopped at Docker
resource creation: fixed name `atenea-codex-app-server-dev` is already owned by
foreign Compose project `atenea-activation-code` rooted at
`/home/jose/atenea-activation-code`. Its matching `atenea-db-test` is also
foreign-owned. The former remains exited and the latter remains running.

Only content-free container identity and Compose ownership metadata were read.
No environment, log, database content, volume, credential or application
payload was inspected. Neither foreign container was adopted, restarted,
renamed, removed or rebuilt, and no alternate test surface was substituted.
The candidate read-model changes remain uncommitted and unpublished so they
cannot be mistaken for a completed task.

Production, preview, Beautips and AX42 were not mutated during this attempt.
Resumption requires the owner of the foreign local stack to resolve the exact
name conflict or separately authorize the exact disposition; task 5.1 must
then resume with focused tests before any further implementation.

Sanitized blocked evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.1-blocked-foreign-local-test-container`;
the SHA-256 of its `SHA256SUMS` is
`e46c9eca461db05f19f20eba4ce7e7cc28169cf9a20ec65f8b27f2a1f08e3e2e`.

Task 5.1 is complete. Change progress is `32/60`; task 5.2 is the exact resume
point. Atenea commit `fa69cee2b45ff2884e637387333261116108d9dc`
adds one shared, bounded operator-state read model to the existing mobile
WorkSession summary and types it for both web and Android. It presents current
state, a safe blocker and at most one primary action with availability, role
and domain target. It exposes no worker endpoint, workspace path, operation
identifier, slot, port, label, command or raw payload.

The model keeps its surface and actions disabled by default and permits the
remote-close reconciliation surface only for canonical Atenea. It separates
closing, blocked ownership, legacy confirmation, released capacity and
ambiguous ownership. Generic AgentRun retry becomes visible only for a
terminal run whose exact blocking closed owner has both the persisted
`RELEASED` projection and matching released receipt. Ambiguous ownership
requires administrator review and never enters worker-unavailable handling.

The previous local-resource block was resolved only after the operator's
separate exact authorization. Revalidation proved the obsolete
`atenea-activation-code` code already integrated into canonical main and no
process or service depending on its path. Only its two exact containers were
stopped/removed. Its clean upstream-exact repository, network, three
development/test/cache volumes and images remain preserved. No database or
volume content, environment or application payload was read.

The focused shared-read-model/API/retry/conversation matrix passes 64/64 across
six classes with zero failures, errors or skips. The production web build,
Android API tests with explicit absent/synthetic external-secret inputs and
backend package pass. The mandated runner's historical mounted-source path was
supplied through a task-owned temporary copy after the default local path
failed before tests; no application code or shared fixture changed. Task 5.1
changes response and typed-client models only, so no visible web/Android output
changed and Playwright is not applicable until tasks 5.2-5.3.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete profile. Production and preview
remain `UP`, Beautips returns HTTP 200 and routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

All four incident ownership hashes remain exact; WorkSession 17 allocation and
admission remain absent. Worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful daemons remain inactive, RAID remains
`3/3 [UU]` and backup/check/health remain `success/0`. No production migration,
deployment, configuration, release, prompt, runtime, ownership, preview,
Beautips, foreign or unrelated resource changed during implementation.

Sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.1-shared-operator-read-model`;
the SHA-256 of its `SHA256SUMS` is
`7450ee749174dad0a04f627528829de5d4d82d0c293cbdaee450b1fd067f47b0`.

Task 5.2 is complete. Change progress is `33/60`; task 5.3 is the exact resume
point. Atenea commit `d521d95a969b63ffc6f8fb47adcecbd77eaa0945`
adds the state-first web flow to both WorkSession and immersive conversation.
When the shared surface is enabled, current close/capacity state and its safe
blocker lead the first viewport with at most one primary action. Default and
unrelated session states render no new surface.

Normal close reconciliation repeats the existing close request and therefore
the same persisted operation. A legacy closed owner requires an administrator
plan followed by a separate finite explicit confirmation bound to the returned
plan and ownership fingerprint. Both client idempotency keys remain stable
across uncertain responses. No client-selected command, path, worker, slot,
port, endpoint, label, credential or resource target is accepted or displayed.

Generic retry is hidden while the remote-close surface owns the next action.
The secondary run panel says to reconcile before retry rather than describing
retry as safe. Only a persisted released-capacity projection presents
`Reintentar tarea`, and the retry still requires a separate explicit click. A
routine operator sees the administrator role requirement and cannot create a
legacy plan; reconciling or unverifiable ownership exposes neither retry nor
cleanup.

The production web build and application/test TypeScript compilation pass.
Four focused Playwright component flows pass for closing, exact legacy
confirmation, authorization, reconciling, blocked ownership and released
capacity. All 17 existing attachment/composer Playwright regressions also
pass. Synthetic request recording proves zero confirmation or retry before
release and the exact domain targets afterward.

Real rendered smoke inspection passes at `1440x900` and `390x844`. Data/API
state, DOM visibility and final pixels were checked separately. One initial
visual ambiguity in the secondary retry copy was corrected before the final
screenshots; the final state, blocker, permission and primary action are clear
without visible clipping, overlap or horizontal overflow. Task 5.3 retains the
full long-message, confirmation, refresh and responsive acceptance gate.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete profile. Production and preview
remain `UP`, Beautips returns HTTP 200 and routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

All four incident ownership hashes remain exact; WorkSession 17 allocation and
admission remain absent. Worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful daemons remain inactive, RAID remains
`3/3 [UU]` and backup/check/health remain `success/0`. Task-owned Docker
resources are absent. No production migration, deployment, configuration,
release, prompt, AgentRun retry, runtime, ownership, preview, Beautips, foreign
or unrelated resource changed.

Sanitized evidence, including synthetic desktop/mobile screenshots, is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.2-state-first-web`;
the SHA-256 of its `SHA256SUMS` is
`85ebde050fcd665fef9f6d5427a2d54032fcd959a8aa9e89f8f6fca37bba6405`.

Task 5.3 is complete. Change progress is `34/60`; task 5.4 is the exact resume
point. Atenea commit `8ea112abde9e81fe55637c1d9e54f6787629ff04`
completes the real rendered web acceptance and corrects the one responsive
defect it found. The complete project Playwright suite passes 25/25: eight
remote-close state/action cases and all 17 existing attachment/composer
regressions. The production web build and application/test TypeScript
compilation pass.

Data, DOM and pixels were checked separately. Synthetic request recording
proves no legacy release at plan creation, exact confirmation binding and zero
AgentRun retry until the released-capacity projection. DOM checks cover closing,
reconciling, blocked and unverifiable ownership, long safe messages, role
authority, separate confirmation, manual refresh, released capacity and the
explicit retry action.

Real Chromium rendered checks use exactly `1440x900` and `390x844`.
Programmatic geometry proves initial state and primary action are inside the
first viewport, document and state panel have no horizontal overflow, the
state title remains below the sticky header and both confirmation actions
remain above the fixed mobile composer. Six final synthetic screenshots were
inspected and retained.

The first long-message mobile render exposed the confirmation action partially
behind the fixed composer. A bounded confirmation scroll target fixed that
overlap; its initial responsive margin moved too far and hid part of the state
title, so it was reduced. The final render and geometry now keep the complete
title, confirmation, primary/secondary authority and composer clear. No
framework, screen, backend contract or unrelated component was added.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains `FAILED`, unretried and without a child. WorkSession 17 retains one
turn, one run, one attachment and one complete profile. Production and preview
remain `UP`, Beautips returns HTTP 200 and routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

All four incident ownership hashes remain exact; WorkSession 17 allocation and
admission remain absent. Worker services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful daemons remain inactive, RAID remains
`3/3 [UU]` and backup/check/health remain `success/0`. Task-owned Docker
resources are absent. No production migration, deployment, configuration,
release, prompt, AgentRun retry, runtime, ownership, preview, Beautips, foreign
or unrelated resource changed.

Sanitized final web acceptance evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.3-complete-web-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`1adfa7fa8b3fb4066c8785938c6a5ea9345cd8e2313e0d36578c35b213eb4fc0`.

Task 5.4 is complete. Change progress is `35/60`; task 5.5 is the exact
resume point. Atenea candidate commit
`7cec0490c7aa1663e9c7f012dfdc7ced245bf851` is published exactly in both the
canonical repository and GitHub. Android now consumes the same bounded
operator-state model as web in the WorkSession and conversation surfaces. It
presents current state, safe blocker, required authority and one primary
action without exposing infrastructure identity.

The Android auth session now retains the server-provided Codex operations
role. A routine operator cannot generate or confirm an administrator plan. A
legacy closed owner first creates a read-only plan, then requires a separate
explicit confirmation bound to that plan and ownership fingerprint. Plan and
confirmation idempotency keys remain stable across transport or response loss.
Normal close reconciliation repeats the persisted close operation.

Generic AgentRun retry is suppressed while remote-close state owns the next
action. Only exact `CAPACITY_RELEASED` with a target terminal run exposes the
retry, and it still requires an explicit tap. No prompt or AgentRun was sent
automatically. Deterministic policy, missing/stale state and validation errors
have separate safe messages and never appear as worker unavailability.

The complete core-console unit suite passes 34/34, including five new
coordinator tests for authority, state/action pairing, response-loss
idempotency, explicit retry and sanitized errors. Three Compose UI tests pass
on a real isolated API 35 emulator. Final synthetic `390x844` screenshots were
inspected separately from persistence and semantics: state, long safe blocker,
primary action, retained-state confirmation and both confirmation controls are
visible without clipping, overlap or horizontal overflow. The task emulator
and AVD were removed afterward.

One 59,896,815-byte canary APK was built from the exact candidate source using
the opaque established debug-channel keystore. Its SHA-256 is
`cfa88898bd0b3109b615741cf3b6dbb685178e80c2d4a34e2321acb56d262d8a`,
and its certificate SHA-256 matches the retained channel certificate at
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
Download and Firebase secret paths were explicitly absent and the manifest URL
was synthetic. The canary was neither published nor installed; its temporary
source and staging copy were removed after the evidence copy revalidated.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no child and one retained attachment.
WorkSession 17 retains one turn, one run, one attachment and one complete
profile. Production, preview and Beautips return HTTP 200 and routing remains
`ax42-01` enabled/healthy `4/2` at `0/0`.

WorkSession 16 workspace/allocation/admission and WorkSession 17 workspace
hashes remain exact; WorkSession 17 allocation/admission remain absent. Worker
services remain active with zero restarts, rootless slots remain `3/0/0/3`,
rootful Docker/containerd remain inactive, all three RAID arrays remain
`[UU]`, and backup/check/health remain `success/0`. No migration, deployment,
configuration, production, preview, Beautips, prompt, retry, runtime,
ownership, foreign or unrelated resource changed.

Sanitized Android evidence, two synthetic screenshots and the unpublished
signed canary are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.4-android-state-first-operation`;
the SHA-256 of its `SHA256SUMS` is
`b8eb6794be19771cae408f2df14a0d1fc81525dbcde3380d22e3e63bf597496f`.

Task 5.5 is complete. Change progress is `36/60`; task 6.1 is the exact
resume point. Atenea candidate commit
`03534c4998eaf150aa0eda9d0096b00f403b1baa` is published exactly in the
canonical repository and GitHub. Section 5 is complete; no task in section 6
has started.

Web and Android now enforce the same routine/privileged/administrator role
hierarchy and the same closed state/action pairs. Missing or unknown authority,
inconsistent actions and unavailable actions fail closed. No client-selected
worker, endpoint, workspace, command, slot, port, label, credential or
infrastructure resource is accepted or shown.

An HTTP 409 from plan creation or confirmation now discards the stale local
plan and both idempotency keys, blocks another plan until a fresh server
projection is loaded and presents an actionable refresh message. Transport or
response loss continues to reuse the stable key. Explicit refresh restores
the current server-derived action; unchanged automatic polling does not
discard a still-valid confirmation. Synthetic request recording proves zero
release retry or prompt action in the stale path.

Android's versioned notification parser now also requires the payload
`deepLink` field to equal the exact validated URI. The shell consumes only its
validated WorkSession ID and immutable request key, clears unrelated project
navigation and opens that exact conversation. Mismatched identity, scheme,
host, path, query or payload is rejected.

The production web build and application/test TypeScript compilation pass.
The complete Playwright suite passes 27/27: ten remote-close state/action/
refresh cases and all 17 attachment/composer regressions. Real Chromium at
`1440x900` and `390x844` shows the stale state, disabled action and required
refresh without clipping, overlap or horizontal overflow. A deliberate
same-state poll proves a valid replacement plan remains visible.

Android core-console and app unit suites pass 37/37 and 4/4. Four Compose UI
tests pass on a real isolated API 35 emulator, including the stale
confirmation. Its final synthetic `390x844` render keeps state, blocker,
disabled action and actionable error completely visible in the first
viewport. The emulator, AVD, test package and downloaded system image were
removed afterward. No APK was published or installed.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no child, one retained attachment
and a complete profile. WorkSession 17 retains one turn, one run and one
attachment. Production, preview and Beautips return HTTP 200 and routing
remains `ax42-01` enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact. WorkSession 17 allocation/admission remain
absent. Worker services remain active with zero restarts, rootless slots remain
`3/0/0/3`, rootful Docker/containerd remain inactive, all three RAID arrays
remain `[UU]`, and backup/check/health remain `success/0`. No migration,
deployment, configuration, prompt, retry, runtime, ownership, production,
preview, Beautips, foreign or unrelated resource changed.

Sanitized parity, diagnostics and final synthetic screenshots are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-5.5-state-first-section-closure`;
the SHA-256 of its `SHA256SUMS` is
`9e9b5978cc57b2548c7f27791a12dd1b0008620214647dd27b1756ed8268eaa7`.

Task 6.1 is complete. Change progress is `37/60`; task 6.2 is the exact
resume point. The unchanged Atenea candidate
`03534c4998eaf150aa0eda9d0096b00f403b1baa` ran from an exact detached clean
checkout against a new isolated PostgreSQL 16 database. The complete backend
suite passes 668/668 across 105 reports with zero failures, errors or skips.
The empty public schema contains exactly 63 successful versioned Flyway rows,
contiguous from V1 through V63, with no gap or failed history row.

The first diagnostic run reached PostgreSQL's default 100-client capacity
while loading the final Spring context and reported two capacity errors. It
made no production call or mutation. Its complete fixture was destroyed and
recreated empty, isolated database capacity was set to 300, and the unchanged
canonical suite passed. All task checkout, report, database and Compose
resources were removed after sanitized aggregation; final task-labelled
container/network/volume/image counts are `0/0/0/0` and isolated context and
Codex-home file counts are zero.

The first external check used the Beautips public root and exposed HTTP 403,
although its canonical deployment health endpoint remained HTTP 200. The
operator separately confirmed that rejecting the root was unintended and
explicitly authorized an isolated Beautips correction outside this OpenSpec
task. Beautips commit
`9e122bf024d29b9cda56b27f8a32c218e1f0d433` permits only safe reads of `/`
and redirects them to its documented administrator login; `POST /` remains
403. Its complete suite passes 31/31, the mandatory local redeploy passes, and
real Playwright at `1440x900` and `390x844` proves the redirect, visible DOM,
first-viewport primary action and absence of clipping or horizontal overflow.
GitHub Actions run `30912012906` deployed that exact commit successfully.
Beautips root now follows to HTTP 200 and its health endpoint remains 200.

The separately authorized Beautips correction did not touch Atenea or AX42.
Atenea production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and
zero non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote;
AgentRun 96 remains terminal unretried `FAILED` with no child. Production,
preview and Beautips return HTTP 200; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact; WorkSession 17 allocation/admission remain
absent. Worker services remain active with zero restarts, rootless slots remain
`3/0/0/3`, rootful Docker/containerd remain inactive, all three RAID arrays
remain `[UU]`, and backup/check/health remain `success/0`. No Atenea migration,
deployment, configuration, release, prompt, retry, runtime or ownership changed.

Sanitized backend, migration and final external-health evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.1-complete-backend-v63`;
the SHA-256 of its `SHA256SUMS` is
`e84c8ba62af00f411c1b0769c07b32ca251682dc413e5bd52f177fd10b38b30a`.

Task 6.2 is complete. Change progress is `38/60`; task 6.3 is the exact
resume point. The unchanged Atenea candidate
`03534c4998eaf150aa0eda9d0096b00f403b1baa`, tree
`d1a1e6ba2c1e1207f882c481428342a8f83a76ab`, ran from a detached task-owned
checkout with exact package-lock SHA-256
`62ea4d444da58e7e27bd83cb53ebcf49bcc9bf27dd5641e3d12ed8dd86ff21bc`.

`npm ci` and the separate live dependency audit pass. The audit covers 128
dependency records and reports zero informational, low, moderate, high or
critical vulnerabilities with exit 0. npm emitted only its advisory that the
existing esbuild postinstall is not yet covered by an `allowScripts`
declaration; no dependency approval, lockfile or configuration was changed.
The production TypeScript/Vite build passes and transforms 1,583 modules.
Generated index and bundle output remained confined to the disposable checkout.

The complete real Chromium suite passes 27/27 with one worker, zero retries
and finite timeouts: all 17 attachment/composer regressions and all ten remote
close state/action/refresh cases. Synthetic request recording proves
confirmation authority, explicit refresh and zero automatic release or
AgentRun retry in blocked and stale paths. DOM assertions cover closing,
blocked ownership, required administrator role, legacy confirmation, stale
confirmation, released capacity and explicit retry.

Eight final screenshots at exact `1440x900` and `390x844` were inspected.
State and one primary action remain visually dominant, long safe messages wrap,
permissions and stale errors remain legible, confirmation controls stay above
the fixed composer and no clipping, overlap or horizontal overflow is present.
The Playwright server exited, port 4175 is free and related Node/browser process
count is zero. The exact checkout, dependencies, build output and result file
were removed after evidence staging.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. AgentRun 96 remains unretried with no child. Production,
preview and Beautips return HTTP 200; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`. All five incident ownership hashes remain
exact; worker services remain active with zero restarts, rootless slots remain
`3/0/0/3`, rootful daemons remain inactive, RAID remains `3/3 [UU]` and
backup/check/health remain `success/0`. No production, preview, Beautips,
worker, ownership, prompt, retry, runtime or foreign resource changed.

Sanitized build, audit, DOM and final screenshot evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.2-final-web-acceptance`;
the SHA-256 of its `SHA256SUMS` is
`7a3ef0d0e4da6eb7e9d2f165b43672880c9a5f68857aeb3e2a7ee1a9b8df4305`.

Task 6.3 is complete. Change progress is `39/60`; task 6.4 is the exact
resume point. The unchanged Atenea candidate
`03534c4998eaf150aa0eda9d0096b00f403b1baa`, tree
`d1a1e6ba2c1e1207f882c481428342a8f83a76ab`, ran from exact disposable
source copies with finite test, emulator and build timeouts.

The complete `core-console` and `app` unit suites pass 37/37 and 4/4 with zero
failures, errors or skips. A single self-targeting instrumentation APK then ran
all four remote-close Compose cases on a real isolated API 35 emulator. It
covers visible retained-state confirmation, exact authorized primary action,
stale confirmation requiring refresh and missing-authority disablement. The
test package, emulator, AVD and task-downloaded system image were removed.

The changed `core-console` module passes Android lint with zero errors. Full
`--continue lintDebug` reports three findings in unchanged notification,
theme and voice-diagnostics files. The exact canonical base
`615e539d1f2622a4ac2568ba7697b876d49ae33e` reports the same three normalized
findings, so the candidate adds zero static-analysis errors. No lint baseline,
suppression or unrelated source correction was introduced.

One 59,896,815-byte canary APK was built from the exact candidate tree using
the opaque established debug-channel Android home. Its SHA-256 is
`88a24b98ac064218919292052d26628056efae7b2df4562b45dbc30148e819cf`.
APK Signature Scheme v2 verification passes and its certificate SHA-256
matches the retained channel at
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
APK-download and Firebase secret inputs were absent and the manifest URL was
synthetic. Both established published APKs remain the prior 59,863,832-byte
artifact with SHA-256
`d9f2a3958d9d9ec137b08e78d4ba4139313edd903b51e1fdeb01fb62314e9ae9`
and 2026-08-01 timestamps. The canary was neither published nor installed.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no child and a complete profile.
WorkSession 17 retains one turn, one run and one attachment. Production,
preview and Beautips return HTTP 200; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact; WorkSession 17 allocation/admission remain
absent. AgentRun, attachment and preview services remain active with zero
restarts, rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked, all three RAID arrays remain `[UU]`, and backup/check/health
remain `success/0`. All task-labelled containers, networks and volumes are
absent. No migration, deployment, configuration, publication, installation,
prompt, retry, runtime, ownership, production, preview, Beautips, foreign or
unrelated resource changed.

Sanitized unit, static-differential, instrumentation, signature and retained
canary evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.3-complete-android-canary`;
the SHA-256 of its `SHA256SUMS` is
`440ab21d144b7c50eb3e29f51b74d4e106b011c91a4d56ac3775c01edf37a5a4`.

Task 6.4 is complete. Change progress is `40/60`; task 6.5 is the exact
resume point. The complete 33-entry programme, worker, runtime, preview,
attachment, backup, installer, rollback and security suite ran in lexical
order from detached immutable source. Each entry had a finite 900-second
process timeout. All 33 entries pass in 514 seconds; 20 unittest reports cover
239 tests with zero failed reports. The exact suite-result SHA-256 is
`aa06848a90a3a4a2df5f83b54bbf7cd8d0dc4a55da669434eee3fdf7f7d7356e`.

The exact programme source was
`0315787445c536a4cfa6062ce18cb8e8a053f77e`, the unchanged Atenea candidate
was `03534c4998eaf150aa0eda9d0096b00f403b1baa`, and the Beautips contract used
its explicitly pinned historical source
`e9e0b3c319c518363d4135f5378ebbddced96dfb`. Beautips current source and
production were not changed. One pre-existing real Restic integration case
was deliberately skipped; its synthetic backup coverage passed and live
backup/check results remain `success/0`.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no child and a complete profile.
WorkSession 17 retains one turn, one run and one attachment. Production,
preview and Beautips return HTTP 200; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact; WorkSession 17 allocation/admission remain
absent. AgentRun, attachment and preview services remain active with zero
restarts, rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked, all three RAID arrays remain `[UU]`, and backup/check/health
remain `success/0`. Disposable worktrees, Python bytecode, browser artifacts,
raw logs and task-labelled containers, networks and volumes were removed.
Older unrelated temporary roots were preserved. No migration, deployment,
configuration, activation, prompt, retry, runtime, ownership, production,
preview, Beautips, foreign or unrelated resource changed.

Sanitized ordered-suite and retained-state evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.4-complete-sorted-source-suite`;
the SHA-256 of its `SHA256SUMS` is
`14411f1644af894d6f1cfcaafde08d2e0340b99d927d20d592f05d6e6f1ef952`.

Task 6.5 is complete. Change progress is `41/60`; task 6.6 is the exact
resume point. The independent adversarial review found and corrected five
in-scope blockers in the candidate and worker boundary. An HTTP 4xx can no
longer self-declare `TRANSPORT`, request reconciliation or become worker
unavailability: status, category, retryability, next action and blocker
identity must form one compatible projection, and every incompatible envelope
fails closed as a safe, non-retryable protocol error. Legacy close now applies
the same atomic fallback instead of retaining a contradictory reconciliation
action.

Normal remote close is now idempotent across a completed repeated request and
the transaction race between preparation and final persistence. A late
transport failure cannot downgrade or contradict an already durable exact
`CLOSED/RELEASED` result. The persisted final projection must include canonical
Atenea ownership, the same operation, a valid receipt SHA-256, revision at
least 6 and every required timestamp. Worker and client receipt validation now
require exact final revision 6 and every released and retained value true.

The reviewed Atenea candidate is
`989ec05b7ea325fd1921eb01eb06a4ca5d057ce6`, tree
`096639f41c5f349933ea2a290c64192be532ffbf`. Its complete backend suite ran in
the project development image against a new isolated PostgreSQL 16 database
and empty task-owned workspace root: 676/676 tests pass across 105 reports
with zero failures, errors or skips, and all 63 migrations applied only to the
disposable database. The complete affected worker suites pass: 68 agent worker
tests, 34 workspace finalizer tests, the installer/rollback contract and the
Beautips cross-contract against its pinned historical source. Current Beautips
source and production remained untouched. No web-visible source changed, so
the sealed task 6.2 Playwright result remains applicable.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no child and a complete profile.
WorkSession 17 retains one turn, one run and one attachment. Production,
preview and Beautips return HTTP 200; routing remains `ax42-01`
enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact; WorkSession 17 allocation/admission remain
absent. AgentRun, attachment and preview services remain active with zero
restarts, rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked, all three RAID arrays remain `[UU]`, and backup/check/health
remain `success/0`. Exact task containers, database volumes, generated reports,
workspaces, bytecode and historical worktree were removed. No production
migration, deployment, installation, configuration, activation, release,
prompt, retry, runtime, ownership, preview, Beautips, foreign or unrelated
resource changed.

Sanitized findings, diagnostics and test/state evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.5-independent-adversarial-review`;
the SHA-256 of its `SHA256SUMS` is
`550ad79a13e6fecdb92e46449ae2905e9ec7651f4224803bb2f9c81d0e1d5a8b`.

Task 6.6 is complete. Change progress is `42/60`; task 6.7 is the exact
resume point. The reviewed programme branch is published at
`8fea093692f16095cd73df4dfa8bf6be0694802d`, tree
`b88e8882c24c8c26b13901d6422a31127588d74e`. The reviewed Atenea branch is
published at `989ec05b7ea325fd1921eb01eb06a4ca5d057ce6`, tree
`096639f41c5f349933ea2a290c64192be532ffbf`. Local, internal where applicable
and GitHub refs are exact.

The checksum package retains exact source archives for the Atenea candidate
and V63-compatible rollback source `27f9a7eb5e986f8cacffd0b169af931e03934d96`,
tree `179a019bdb5d0f57594320f01c169395efb5db4a`; the programme AX42 install
bundle; and the five-file installed AX42 static predecessor. Dynamic worker
configuration, registry, admission, allocation, tokens and session state are
excluded so rollback cannot reconstruct ownership already released.

The retained, undeployed candidate backend image is
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
with exact candidate JAR SHA-256
`ecdad80bcd73736faffe5342a916788a35d3ca7e9062fcdcbe4139f9e4cc79ad`.
It uses the exact deployed production image
`sha256:fe5bb7a6b39dbcc2f9847dd05b68b9aabe72bf4d2775ad55f5624fcd99b1d96f`
as its first 11 layers and changes only the application JAR; runtime config is
byte-identical. No running container uses the candidate. The task 1.4 rollback
seal remains exact and task 7.2 still requires a fresh rollback build/proof.
The task 6.3 Android canary remains retained, unpublished and uninstalled.

Production remains V62 with 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote; AgentRun 96
remains terminal unretried `FAILED`, with no parent or child retry and a
complete profile. WorkSession 17 retains one turn, one run and one attachment.
Production and preview return HTTP 200 on their unchanged exact images;
Beautips remains clean/upstream-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433` and its public root returns HTTP
200. The prior unintended Beautips 403 is absent.

Routing remains `ax42-01` enabled/healthy `4/2` at `0/0`. The registry,
WorkSession 16 workspace/allocation/admission and WorkSession 17 workspace
hashes remain exact; WorkSession 17 allocation/admission and the release
successor remain absent. AgentRun, attachment and preview services remain
active/enabled with zero restarts, backup/check/health remain `success/0`,
rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked and all three RAID arrays remain `[UU]`. The unrelated local
`atenea-activation-code_default` network remains present and untouched.

No migration, deployment, installation, configuration, activation, release,
prompt, retry, runtime, ownership, production, preview, Beautips, foreign or
unrelated resource changed. Sanitized published-artifact evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.6-published-rollout-artifacts`;
the SHA-256 of its `SHA256SUMS` is
`034da1d2ba165556b52fe9ee3ed0d1b911424b7e69c7675dafa6f16e540d25fe`.

Task 6.7 is complete. Change progress is `43/60`; task 6.8 is the exact first
pending task and mandatory human rollout gate. OpenSpec strict validation
passes from published programme predecessor
`d73be2616a183b437734cf93a59ae5556185910e`, tree
`860bbbcd6ce429b8c9ae0d55c6402abd41e45e97`. The reviewed Atenea candidate
remains published and exact at
`989ec05b7ea325fd1921eb01eb06a4ca5d057ce6`, tree
`096639f41c5f349933ea2a290c64192be532ffbf`.

Every entry in the six task 6.1–6.6 checksum manifests was reverified: 48/48
files are exact. The closure also seals exact hashes for the proposal, design,
task plan and all five specification deltas. Complete backend/V63 migration,
web build/audit/desktop-mobile Playwright, Android unit/instrumentation/static/
canary, sorted programme/worker/runtime/security, adversarial review and
published rollout artifact evidence remain valid without rerunning or mutating
their retained artifacts.

Production remains V62 on exact image
`sha256:fe5bb7a6b39dbcc2f9847dd05b68b9aabe72bf4d2775ad55f5624fcd99b1d96f`;
preview remains on exact image
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`.
Both return HTTP 200 with zero restarts. Beautips remains clean,
upstream-exact and HTTP 200 at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`; its unintended 403 remains
absent and its activation remains disabled.

Production still has 15 WorkSessions, 96 terminal AgentRuns and zero
non-terminal runs. WorkSessions 16/17 remain `CLOSED/OPEN` remote. AgentRun 96
remains terminal `FAILED`, unretried, without child and with its complete
profile. WorkSession 17 retains exactly one turn, one run and one attachment.
Routing remains `ax42-01` enabled/healthy `4/2` at `0/0`.

The registry, WorkSession 16 workspace/allocation/admission and WorkSession 17
workspace hashes remain exact; WorkSession 17 allocation/admission and the
release successor remain absent. AX42 AgentRun, attachment and preview services
remain enabled/active at zero restarts, backup/check/health remain `success/0`,
rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked and RAID remains `3/3 [UU]`. The foreign local
`atenea-activation-code_default` network remains present and untouched.

No production migration, deployment, AX42 installation, configuration change,
capability activation, Android publication/installation, legacy release,
prompt, retry, ownership mutation or foreign-resource change occurred. Task
6.8 may proceed only after the operator separately and explicitly authorizes
the exact V63 rollout, reviewed AX42 successor, bounded rollback exercise and
Atenea-only activation.

Sanitized aggregate source-validation evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.7-source-validation-closure`;
the SHA-256 of its `SHA256SUMS` is
`a05e04004c29fa806db77a5ae994216cd5d233431d475521f6477d296dc65c1b`.

Task 6.8 is complete. Change progress is `44/60`; task 7.1 is the exact
resume point. After task 6.7 was complete and published, the operator
separately and explicitly selected the previously enumerated option 2.
Normalized authorization
`rollout-v63-atenea-only-20260804T161502Z` permits the exact tasks 7.1–7.6
scope: fresh external backup and isolated restore proof, bounded rollback
exercise, production V63 migration, exact reviewed backend/web deployment,
reviewed AX42 successor installation, established-channel Android canary
publication/installation, global prerequisite activation and then canonical
Atenea-only activation.

The authorization does not permit Beautips or another project, foreign
resource mutation, prompt submission, automatic AgentRun retry or legacy
WorkSession 16 release. Task 7.7 remains a separate mandatory in-product
single-use operator confirmation. AgentRun 96 remains explicitly unretried.
The original operator response is not retained; only this normalized bounded
decision is sealed.

No rollout action occurred while satisfying the gate. Production and preview
remain on their exact V62-era images at HTTP 200 with zero restarts. Beautips
remains clean, upstream-exact and HTTP 200 with activation disabled. AX42
services, ownership and retained resources remain exact. No migration,
deployment, installation, configuration, publication, activation, release,
prompt, retry or foreign-resource mutation occurred.

Sanitized authorization evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-6.8-rollout-authorization`;
the SHA-256 of its `SHA256SUMS` is
`ff9aa0a031ada1748a5ce9f53b4b9d54e476ffc876e36bb8b44aa6819cac5a1e`.

Task 7.1 is complete. Change progress is `45/60`; task 7.2 is the exact
resume point. Authorization
`rollout-v63-atenea-only-20260804T161502Z` and its seal were reverified before
the complete read-only recapture. Programme, Atenea candidate, canonical
Atenea, AX42 mirror/worktrees and Beautips Git are clean and exact at their
accepted commits. The AX42 mirror passes full fsck.

Production remains Flyway V62 with 15 WorkSessions, 96 terminal AgentRuns,
zero non-terminal runs and zero active leases. WorkSession 16 remains
`CLOSED/DRAFT/main/REMOTE` with zero turns, runs, attachments and previews.
WorkSession 17 remains `OPEN/DRAFT/main/REMOTE` with exact accepted source and
one turn, one run, one attachment, one binding and zero previews. AgentRun 96
remains terminal `FAILED`, unretried, without remote execution or child, with
its exact immutable profile and attachment metadata. No attachment content or
filename was selected.

The five incident ownership hashes and aggregate allocation/admission hashes
remain byte-exact. WorkSession 16 remains the sole Atenea registration and
owns no runtime container, network, volume, listener or unit. WorkSession 17
allocation/admission/registration remain absent. The release successor remains
uninstalled. Routing remains `ax42-01` enabled/healthy `4/2` at `0/0`.

Production and preview retain their exact compose and image identities, return
HTTP 200 and have zero restarts; the candidate image remains retained but
unused. Beautips remains clean/upstream-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`, returns HTTP 200 and remains
disabled for activation. The foreign local `atenea-activation-code_default`
network remains present with zero associated containers and was not touched.

AX42 AgentRun, attachment, preview and image services remain healthy without
restarts. Backup/check/health timers remain active/enabled with `success/0`;
their unit and executable projections are sealed. The worker listener
projection remains exact at
`e27a62a17adbb01121476e9c9927ae7634fcd32007c2dc85cdbeceaed8488b3b`.
SSH, Tailscale and UFW remain active on both hosts, rootful Docker/containerd
remain inactive/masked on AX42, rootless container counts remain `3/0/0/3`
and RAID remains `3/3 [UU]`. Slot container/network/volume/image projections
are sealed without classifying or opening foreign content.

No Git, ownership, RAID, backup, runtime, production, preview, Beautips or
foreign-resource divergence was found. No migration, deployment, installation,
configuration, activation, release, prompt or retry occurred. Sanitized
pre-rollout evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.1-pre-rollout-fingerprints`;
the SHA-256 of its `SHA256SUMS` is
`0b91050e06bbd6fabf072558f18f808e7d2651d1d6cf449caf9a516814edef60`.

Task 7.2 is complete. Change progress is `46/60`; task 7.3 is the exact resume
point. The established AX42 backup service created and checked fresh encrypted
snapshot
`809f2b58498c75456916421391ae147a546bcd21b92439232e817e1091f3380b`.
Its selected source manifest SHA-256 is
`18c34b5dbcb5df54ce268b710508844c2d81cae0876d45580aa770e458d76013`,
with 5,537 files and 155,817,597 bytes. Backup/check results remain
`success/0`; protected metadata remains mode `0600`, root-owned.

A fresh V62 production custom dump is retained at
`/srv/atenea/backups/prod/atenea_prod_before_remote_close_v62_20260804T163514Z.dump`,
SHA-256
`2e1d110e46d69188bce916b1205ce4a7c1fcb14ca0ab8356e2a38de0cf51a748`,
mode `0600`. Its catalog was checked, then it was restored into an empty
PostgreSQL 16 fixture on a labelled internal-only network with tmpfs storage
and no published ports. The restored V62 image contained 51 tables, 15
WorkSessions and 96 AgentRuns.

The exact reviewed candidate image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
started on the fixture, applied V63 once and repeated startup as a no-op. V63
backfilled `NOT_REQUIRED:2`, `NOT_STARTED:3` and
`UNVERIFIED_LEGACY:10`; it did not create any legacy plan, authorization or
operation. WorkSession 16 projected `UNVERIFIED_LEGACY`, WorkSession 17
projected `NOT_STARTED`, and AgentRun 96 gained no recovery failure, action or
blocker. The Flyway history SHA-256 remained
`4bd326d9abe3aeb8615d0ec9841dc5a09d1cefe28e1077a1979b4803b3a5871e`
across repeat startup.

The independently sealed rollback source
`27f9a7eb5e986f8cacffd0b169af931e03934d96` correctly failed closed when its
historical V63 checksum met the final candidate V63 history. No production
state was involved or changed. A minimal separate rollback branch copies only
the exact final V63 migration bytes: branch
`codex/complete-remote-worksession-close-lifecycle-rollback-20260804`, commit
`a0ac6326011f142006fdc24748cd9a69f8c93896`, tree
`fcf84ac45eb5c73781bf5b3cbde6665d3f730e48`. Internal and GitHub refs are
exact. Its retained rollback image is
`sha256:f2f6d8aaefb1e511ea5d3468e1505902f5ab0a686b964d13d2578e77a4af1859`;
it shares all 11 production base layers and normalized runtime configuration,
then reads the migrated fixture at V63 without new gate environment and
without another write. The incompatible diagnostic image was removed exactly.

The two labelled fixture containers and their internal network were removed;
zero task 7.2 container or network remains. Production is still V62 on exact
image
`sha256:fe5bb7a6b39dbcc2f9847dd05b68b9aabe72bf4d2775ad55f5624fcd99b1d96f`,
and preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`.
Production, preview and Beautips return HTTP 200 with zero relevant restarts.
The five accepted incident ownership hashes remain exact; WorkSession 17 has
no allocation, admission or registration. Rootless slots remain `3/0/0/3`,
rootful Docker/containerd remain inactive/masked and RAID remains `3/3 [UU]`.
The foreign local `atenea-activation-code_default` network remains present
with zero containers and untouched.

Production retains 15 WorkSessions, 96 terminal AgentRuns and zero V63 rows.
WorkSessions 16/17 remain `CLOSED/OPEN`; AgentRun 96 remains `FAILED`, without
retry parent or child. WorkSession 17 retains one turn, one run, one attachment
and one binding. No production migration, deployment, worker installation,
Android publication, capability activation, legacy release, prompt, retry,
Beautips change or foreign-resource mutation occurred.

Sanitized task evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.2-fresh-backup-v63-rollback-proof`;
the SHA-256 of its `SHA256SUMS` is
`eaa0ffc606d335c9ad6943428fef40f61c764c770b789ff42c6bae6d04baf853`.

Task 7.3 remains pending and change progress remains `46/60`. Its mandatory
pre-install runtime preflight found that the exact reviewed AX42 successor is
not operational for workspace release. The reviewed Atenea backend contains
one call to `POST /v1/project-workspaces/release`, while the exact reviewed
worker source defines the route constant but contains zero HTTP dispatches for
it and zero `WorkerState` release methods. The installed finalizer source also
contains zero executable entry points and explicitly documents that it exposes
no CLI or HTTP entry point.

An isolated in-memory worker server on a kernel-selected loopback port proved
the exact reviewed route returns HTTP 404. The server and temporary state were
closed and removed. No AX42 service, worker state, control-plane state or
foreign resource participated in the diagnostic.

Deploying the task 6.6 bundle would therefore install an HTTP worker that
cannot execute the backend's required release operation. The rollout stopped
before production mutation under the runtime-divergence rule. The exact five
installed AX42 predecessor files still verify against their sealed manifest;
the AgentRun worker remains active at zero restarts and the release successor
remains absent. Production remains V62 on
`sha256:fe5bb7a6b39dbcc2f9847dd05b68b9aabe72bf4d2775ad55f5624fcd99b1d96f`;
production, preview and Beautips remain HTTP 200. No compose edit, migration,
deployment, installation, configuration change, activation, release, prompt,
retry or ownership mutation occurred.

Task 7.3 can resume only after implementing the real closed worker dispatch,
fixed-authority finalizer entry point and live exact projection/boundary,
adding an actual HTTP acceptance test, repeating affected complete worker,
installer, security and adversarial review, publishing new exact artifacts,
and obtaining authorization for that corrected exact successor. The existing
rollout authorization was not consumed for deployment.

Sanitized blocked-preflight evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.3-rollout-preflight-blocked-runtime-route`;
the SHA-256 of its `SHA256SUMS` is
`ee2254f20817f9fa7c7cefd66cf7e7c4b4c829931c1c19919151976c64fd02a0`.

The task 7.3 remediation prerequisite is implemented, reviewed, tested and
published, but task 7.3 itself remains pending and change progress remains
`46/60`. Programme commit
`7c5d2e65b34d475e56ab53715661f37ff69472cb`, tree
`497b6cc370392cd45e027abcd72dd0c80b81d401`, adds the missing authenticated
`POST /v1/project-workspaces/release` dispatch, serializes it with workspace
activation, blocks any non-terminal exact-session execution, invokes only the
fixed no-argument privileged mediator with canonical JSON stdin and validates
the exact persisted `RELEASED` receipt. Transport timeout/unavailability,
malformed receipt, deterministic validation, policy and ownership failures
remain distinct and bounded; no deterministic HTTP 4xx enters worker-capacity
handling.

The fixed-root finalizer CLI accepts no arguments and derives no path, slot,
port, endpoint, label, service, command or credential from the caller. It
validates the exact live workspace, registry, admission, allocation, Git and
manifest projection, including the kernel hostname recorded by the existing
workspace activator. It journals the immutable request and each monotonic
stage before continuing, resumes the same operation after response or process
loss, unregisters only the exact identity, releases heavy before normal
admission, retires only the exact allocation by a same-directory rename and
requires retained-state proof before returning the same closed receipt.
Changed, partial, symlinked, foreign, ambiguous or production-like state is
rejected before mutation.

The first operational successor deliberately accepts only an empty ephemeral
projection. This matches the repeatedly observed WorkSession 16 inventory.
Any exact or ambiguous container, network, image, listener, preview,
materialization or browser candidate appearing before release blocks the
operation for a separately reviewed cleanup successor; it is never adopted or
deleted by this revision. The live read-only fixed-root projection for
WorkSession 16 passed through the same root boundary used by the exact
no-argument sudo rule. The temporary reviewed source used for that check was
removed and no release operation or journal was created.

Exact source SHA-256 values are worker
`e6f24a3265b1367ece444fcb1083d264e1024182884cbf5019560f81bd569193`,
finalizer
`dc8f4374f372127163df467c317a2f7fabff4af5e1667799a448173ac9546e15`,
worker installer
`aaea361d7a732d9fbc957b5c2d757fab44c0960a47a75c6fe64eb98159183613`,
routing installer
`50b09a0fa67b3d43149afa0f58ff25dd015fc8e79ced20993a958f9c52b508f6`
and service template
`90167677bcdacbc629f89f019b5a2c2ece56e46beaefcc91d84cf2646b1f4ff6`.
The routing installer accepts only the exact reviewed predecessor for upgrade
or rollback, but its installed verifier requires the exact new successor.

The finalizer and complete worker regressions pass `38/38` and `77/77`.
Both affected installer/apply/verify/rollback suites pass. A final clean-copy
run of all 33 top-level worker entrypoints passes `33/33`, including the real
Playwright acceptance, desktop `1440x900`, mobile `390x844`, browser cleanup,
runtime, ownership, slots, backup, attachments, Beautips isolation and
adversarial rejection contracts. Strict OpenSpec validation passes. Temporary
source copies, logs, browser wrappers, visual registry, screenshots and
bytecode roots were removed after the pass.

Reproducible Git archives are sealed as successor SHA-256
`1eddad93c8f9784a9b7ab0fc0a8db26f6d7ba7e95886cc1527e0989be6706bc1`
and predecessor SHA-256
`6fdcf76146f841ab5f38160c554348909674afc16d9e4b955f5aa2ff843289a1`.
Sanitized evidence and both archives are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.3-corrected-successor-preauthorization`;
the SHA-256 of its `SHA256SUMS` is
`8d5ee34a7d6c00130ac29751dc295ad406a48b476bfe09b82d9c5b6930a5d2bf`.

No production/preview deployment, V63 migration, AX42 installation, Android
publication or installation, configuration change, capability activation,
workspace release, prompt submission, AgentRun retry, Beautips change or
foreign-resource mutation occurred. The prior rollout authorization does not
name these corrected bytes. A new separate explicit authorization must name
the corrected successor commit/tree and evidence seal before task 7.3 may
resume. Task 7.7 remains a later independent in-product confirmation and must
not be simulated or executed through SSH.

Task 7.3 remains pending and change progress remains `46/60`. The operator's
separate response immediately after the exact corrected handoff was normalized
as authorization `rollout-corrected-v63-atenea-only-20260804`: tasks 7.3–7.6
only, programme HEAD
`96f7b5498f2df758724e226a6c8e2ad9c929710b`, worker successor
`7c5d2e65b34d475e56ab53715661f37ff69472cb`, tree
`497b6cc370392cd45e027abcd72dd0c80b81d401`, and artifact seal
`8d5ee34a7d6c00130ac29751dc295ad406a48b476bfe09b82d9c5b6930a5d2bf`.
It excluded Beautips activation, foreign resources, prompts, retries and the
later task 7.7 WorkSession 16 confirmation.

The authorized production half of task 7.3 completed. The exact V62 compose
predecessor was retained, one image line was changed atomically after Compose
validation, and only `atenea-backend-prod` was recreated. It reached HTTP 200
on bounded attempt 8 with zero restarts on exact image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`.
Flyway is now V63. The exact backfill remains `NOT_REQUIRED:2`,
`NOT_STARTED:3`, `UNVERIFIED_LEGACY:10`; WorkSession 16 is
`CLOSED/UNVERIFIED_LEGACY/revision 0`, WorkSession 17 is
`OPEN/NOT_STARTED/revision 0`, and AgentRun 96 remains terminal failed and
unretried. No legacy plan or operation exists. None of the three release gate
environment names is present, so application defaults keep release,
reconciliation and the project allowlist disabled. Preview remains on exact
image
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`,
HTTP 200 with zero restarts.

The AX42 routing and AgentRun installer plans then passed against the exact
predecessor. The first routing apply failed closed before the worker update:
the new journal leaf inherited the setgid bit from
`/srv/atenea/worker` and was mode `2700`, while the reviewed verifier correctly
required private mode `0700`. The only partial resources were the exact new
finalizer and an empty task-owned journal directory. After recording their
owner, mode, link count and exact hash, both were removed. The five-file
predecessor was restored from its sealed archive. The worker remains active at
zero restarts; registry, WorkSession 16 allocation/admission and all unrelated
ownership hashes remain exact. No release request, journal entry, registration
change, admission release, allocation retirement, prompt or retry occurred.

Programme commit
`666810a55bdf91d60e04f0cd896474f1bbe6a060`, tree
`650d4867d621e91635433e7ebcb7dcc9fb7876ad`, now explicitly clears inherited
setuid, setgid and sticky bits after creating the exact root-owned journal
leaf. Its regression creates a `2770` parent and proves apply normalizes the
leaf to `0700`; affected installer/rollback suites pass. A final clean-copy
run of all 33 top-level worker entrypoints passes `33/33`, including HTTP,
finalizer, Playwright, runtime, ownership, backup, attachment and Beautips
isolation contracts. Strict OpenSpec validation passes. The corrected routing
installer SHA-256 is
`7fb634aaf7327fef84924203d6433914728a196c4151d490c357abc538584cbc`;
the new reproducible source archive SHA-256 is
`d8d04186d1d22e988eceb3ea4e74607c133f07b72b614cbbb78ad8ba1ed181c6`.

Production-side sanitized evidence, both compose identities and the corrected
source archive are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.3-v63-worker-rollout`
on the control host; the SHA-256 of its `SHA256SUMS` is
`6915bca4b970ed391fda4b2a2205c8b42f45e6b6b0464e9e6e8e8c1bb4915fbe`.
The same path on AX42 retains the exact static predecessor, authorization,
failure/recovery summary and corrected archive; its `SHA256SUMS` SHA-256 is
`758a7395f10ffa8bc41a9f83a9348e158b1b360fe9d24bbf0e234a02b918b4d8`.

The previous authorization was consumed by the exact production deployment
and does not name the corrected installer bytes. Task 7.3 can resume only
after a new separate authorization names commit
`666810a55bdf91d60e04f0cd896474f1bbe6a060`, tree
`650d4867d621e91635433e7ebcb7dcc9fb7876ad`, archive SHA-256
`d8d04186d1d22e988eceb3ea4e74607c133f07b72b614cbbb78ad8ba1ed181c6`
and both evidence seals. Task 7.7 remains separately gated.

Task 7.3 is complete. Change progress is `47/60`; task 7.4 is the exact next
task but was not started. The operator separately authorized only the AX42
remainder against programme HEAD
`ab42ed298c6d1af2968d79cfb2ad954b0ebaa503`, correction commit
`666810a55bdf91d60e04f0cd896474f1bbe6a060`, tree
`650d4867d621e91635433e7ebcb7dcc9fb7876ad`, archive SHA-256
`d8d04186d1d22e988eceb3ea4e74607c133f07b72b614cbbb78ad8ba1ed181c6`
and the full control/AX42 predecessor evidence seals recorded above. The
authorization excluded task 7.4 and every later task, gate activation,
WorkSession 16 release, prompts, retries, Beautips activation and foreign
resources.

The corrected routing apply completed from that exact sealed archive. The
installed finalizer SHA-256 is
`dc8f4374f372127163df467c317a2f7fabff4af5e1667799a448173ac9546e15`;
the installed worker, worker installer and service template remain exact at
`e6f24a3265b1367ece444fcb1083d264e1024182884cbf5019560f81bd569193`,
`aaea361d7a732d9fbc957b5c2d757fab44c0960a47a75c6fe64eb98159183613`
and
`90167677bcdacbc629f89f019b5a2c2ece56e46beaefcc91d84cf2646b1f4ff6`.
Both installed verifiers pass. Routing reports
`releaseEnabledByDefault:false` and `arbitraryAuthority:false`; the fixed
release root is `0700 root:root`, has link count two and contains zero
operation journals. An unauthenticated fixed release request returns HTTP
401, proving that the installed dispatch is reachable without crossing its
authentication boundary. No authorized release request was sent.

The exact registry, WorkSession 16 workspace/allocation/admission hashes
remain
`6dbb541e51d672236af660e01f83d9f89b0e3c0a5652757340170f2a70ca87e7`,
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`,
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`
and
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`.
WorkSession 17 still has no allocation, admission or registration. AgentRun,
attachment, preview and image services are active with zero restarts;
backup/check/health timers are active with successful exit zero results;
rootless slots remain `3/0/0/3`; rootful Docker/containerd remain
inactive/masked; and all three RAID arrays remain `[UU]`. The exact
task-owned extraction and verifier directories were removed. No foreign or
ambiguous resource was adopted, repaired, removed or reconstructed.

Production remains V63 on exact image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
and preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`;
both return HTTP 200 with zero restarts. The deployed compose SHA-256 is
`69c97cf6c9595c613c17626703c4d090949bdbd44049a5e82c60e46f19e49df5`
and the sealed V62 predecessor remains
`6951a486535b19f348d305bd48a443fe93698f3aade2880f1bd1565babec5d40`.
All three release gate environment names remain absent. Production retains 15
WorkSessions, 96 terminal AgentRuns and zero non-terminal runs, with exact
remote-close counts `NOT_REQUIRED:2`, `NOT_STARTED:3` and
`UNVERIFIED_LEGACY:10`. WorkSession 16 remains
`CLOSED/UNVERIFIED_LEGACY/revision 0`; WorkSession 17 remains
`OPEN/NOT_STARTED/revision 0`; AgentRun 96 remains terminal failed with no
retry or recovery mutation; and zero legacy plan or operation exists.

Canonical Beautips remains clean and GitHub-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`, and its public root returns HTTP
200. Its separate AX42 administrative runtime remains clean and unchanged.
The local foreign `atenea-activation-code_default` network remains present
with zero containers and untouched. No Android publication, configuration or
capability activation, workspace release, prompt, retry, production/preview
route change, Beautips change or unrelated mutation occurred.

Final sanitized evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.3-v63-worker-rollout-final`
on both hosts. The control-host SHA-256 of `SHA256SUMS` is
`1ee5c02f066b414fd139eca3b55af3dd27f1e00d266c986b57750bd47f32be5a`;
the AX42 value is
`844f1af3617e093b221446693134a58a3e409aa9b29c38c8482518c28aa2d94c`.
The preceding sealed directories were not modified. A separate authorization
is required before task 7.4, and task 7.7 retains its independent mandatory
in-product operator gate.

Task 7.4 is in progress and change progress remains `47/60`. The operator's
separate `Adelante` response immediately after the exact task 7.3 handoff was
normalized as authorization for task 7.4 only, bound to programme commit
`19b4707c58f8ee1dfa92830c3695c6b9528943be` and tree
`ade0124919ba0a28b0b074d009a3fa8ed3cc8ecb`. It did not authorize task 7.5,
release-gate activation, WorkSession 16 release, prompts, retries, Beautips
activation or foreign resources.

The publication preflight found that the task 6.3 sealed canary and the
established published APK both identified themselves as `0.5.97 (130)` while
having distinct SHA-256 values. Both active Android registrations already
reported `0.5.97`, the update client treats any `versionCode` less than or
equal to the installed code as up to date, and the immutable release archive
already owns version 130. Replacing those bytes would therefore have made the
canary undiscoverable through the established updater and reused an immutable
identity. No publication occurred with that colliding identity.

The minimal packaging-only correction advances the unchanged validated
Android source to `0.5.98 (131)`. Atenea branch
`codex/complete-remote-worksession-close-lifecycle-atenea-20260803`, commit
`85e0dafc206c36637deea65ba356fe5a952b1c3f`, tree
`bb53a2379c76aac9c74673f41db17823fcff6c67`, changes only the two version
fields from parent
`989ec05b7ea325fd1921eb01eb06a4ca5d057ce6`. Internal copies and GitHub are
exact. The complete `core-console` plus `app` unit set passes `41/41` before
one production-configured build with the opaque established Android home.
No credential, token or environment value was printed or retained.

The resulting 59,896,815-byte APK has SHA-256
`5c32ef4a1f4c017a19f2d970ceb78de525f34026c374a1c9069c5c6b51afe3ee`,
verifies with APK Signature Scheme v2 and retains exact channel certificate
SHA-256
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
The established publication script installed identical bytes to the public,
protected-current and immutable `releases/131` paths. Bounded protected
manifest and APK requests return HTTP 200 without exposing their URL token.
The manifest names 131/current and retains exact predecessor 130 with SHA-256
`d9f2a3958d9d9ec137b08e78d4ba4139313edd903b51e1fdeb01fb62314e9ae9`.

Installation and the required operator confirmation remain pending. There is
no authorized ADB device, and both active registrations still report
`0.5.97`; task 7.4 therefore cannot be marked complete until the operator
installs `0.5.98 (131)` from Atenea's update screen and explicitly confirms
that web and Android behavior remain unchanged while release is disabled. No
claim of real-device or authenticated production-screen visual acceptance is
made before that intervention.

Post-publication checks keep all three release gate environment names absent.
Production and preview remain on their exact images at HTTP 200 with zero
restarts. WorkSession 16 remains `CLOSED/UNVERIFIED_LEGACY/revision 0`,
WorkSession 17 remains `OPEN/NOT_STARTED/revision 0`, AgentRun 96 remains
terminal failed and unretried, and zero legacy plan or operation exists. AX42
ownership hashes, empty release journal, active zero-restart services,
rootless slots `3/0/0/3`, successful backup/check, and all three `[UU]` RAID
arrays remain exact. Beautips remains clean and HTTP 200. The foreign local
`atenea-activation-code_default` network remains present with zero containers
and untouched. The exact build worktree and downloaded verification copies
were removed after retaining the immutable APK; no prompt, retry, release,
gate activation or unrelated mutation occurred.

Sanitized evidence and the exact APK are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.4-android-canary-publication-pending-confirmation`
on the control host. The SHA-256 of `SHA256SUMS` is
`30ab6aa4c22ce2fa0e144bf5d6e9ea0b45733b96591c3c1b29180cf263e1a609`.

Task 7.4 is complete. Change progress is `48/60`; task 7.5 is the exact next
task but was not started. The operator explicitly confirmed that canary
`0.5.98 (131)` was installed and that web plus Android behavior remained
unchanged while release was disabled. The original response is not retained;
only that bounded confirmation is sealed. Production independently records
both active Android registrations at `0.5.98`, replacing the two prior
`0.5.97` projections and proving that the installed client reopened and
registered the published version.

The final read-only recapture found all three release gate environment names
still absent. Production remains on exact V63 image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
and preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`;
both return HTTP 200 with zero restarts. WorkSession 16 remains
`CLOSED/UNVERIFIED_LEGACY/revision 0`, WorkSession 17 remains
`OPEN/NOT_STARTED/revision 0`, AgentRun 96 remains terminal failed without
retry or recovery action, and zero legacy plan or operation exists.

The exact registry and WorkSession 16 workspace/allocation/admission hashes
remain unchanged. The release journal is empty; all four declared AX42
services are active with zero restarts; rootless slots remain `3/0/0/3`;
backup/check/health timers remain active; and all three RAID arrays remain
`[UU]`. Canonical Beautips remains clean at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433` and HTTP 200. The foreign local
`atenea-activation-code_default` network remains present with zero containers
and untouched. No release, gate activation, prompt, retry or unrelated
mutation occurred during installation confirmation.

Final sanitized confirmation evidence is beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.4-android-canary-confirmed-final`
on the control host. The SHA-256 of its `SHA256SUMS` is
`6100de717234337272e18c599d8746506a2a857e16208ad874ea47d2271de5c5`.
The preceding publication evidence and APK remain sealed and unmodified under
their prior SHA-256. A separate authorization is required before task 7.5;
task 7.7 retains its independent mandatory in-product operator gate.

Task 7.5 is complete. Change progress is `49/60`; task 7.6 is the exact next
task but was not started. The operator separately authorized only task 7.5
from programme commit
`f5f5172e5f465944898d4b8c763ff6d266a336ac` and tree
`ceb9b62c218a257af18c70d7314f4402cfc3f3d9`. The normalized decision permits
the ordered global prerequisites and canonical Atenea allowlist; it excludes
task 7.6, legacy planning/release, prompts, retries, Beautips activation,
other projects and foreign resources.

Activation ran in two fail-closed phases against the unchanged exact V63
image. Phase one changed compose SHA-256 from the retained disabled
predecessor
`69c97cf6c9595c613c17626703c4d090949bdbd44049a5e82c60e46f19e49df5`
to global-only
`b326ddd7c61bddcbb794689f0c4d33df61723a9b44415cb40e674ac0825b216f`:
release and reconciliation were true while the project allowlist remained
empty. Only `atenea-backend-prod` was recreated; it returned HTTP 200 on
bounded attempt 8 with zero restarts, and no project was eligible. Zero
legacy plan, operation or worker journal appeared.

Phase two changed only the empty allowlist to exact `atenea`, producing final
compose SHA-256
`b96e5721e558460ae67b799da8e526dbf0c3668c8f267cef004d711d764323b8`.
Again only `atenea-backend-prod` was recreated and reached HTTP 200 on bounded
attempt 8 with zero restarts. Installed environment now projects release
`true`, reconciliation `true` and the singleton allowlist `atenea`. The
reviewed property boundary additionally requires the hard-coded canonical
project identity, so Beautips and every other identity remain ineligible.
No plan, operation, release request or journal was created.

The fingerprint of all 21 non-recreated containers remains exact at
`8c868730cab1c42b0833fe6ca5ac04ad79ade8690577d356e3f23ad00cd4b74a`.
All 10 networks remain exact at
`99bd956a55fea248080e8cde7af8e6c493ca841e90f7f5d5359b56b321b6fed7`
and all 26 volumes at
`026401b1597989cb49e1e6f690b7d25d12ca666175e589c8c5b27877e426ca45`.
Production and preview remain on their exact images at HTTP 200 with zero
restarts. Production retains 15 WorkSessions, 96 terminal AgentRuns and exact
remote-close counts `NOT_REQUIRED:2`, `NOT_STARTED:3` and
`UNVERIFIED_LEGACY:10`. WorkSession 16 remains
`CLOSED/UNVERIFIED_LEGACY/revision 0`; WorkSession 17 remains
`OPEN/NOT_STARTED/revision 0`; AgentRun 96 remains failed and unretried; and
both active Android devices remain on `0.5.98`.

Registry and WorkSession 16 workspace/allocation/admission hashes remain
exact. WorkSession 17 still has no allocation, admission or registration.
All four AX42 services remain active with zero restarts, the release journal
is empty, rootless slots remain `3/0/0/3`, rootful Docker/containerd remain
inactive/masked, backup/check/health remain successful and all three RAID
arrays remain `[UU]`. Canonical Beautips remains clean at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`, HTTP 200 and remote-close
ineligible. The foreign local `atenea-activation-code_default` network remains
present with zero containers and untouched.

Task 7.5 changes only server-side capability configuration; it introduces no
new web implementation. The previously validated state/action rendering is
unchanged, while authenticated real-plan visual acceptance remains
deliberately deferred to the mandatory in-product task 7.7 intervention. No
prompt, retry, release, legacy plan or unrelated mutation occurred. The exact
temporary Compose candidates were removed after their three identities were
retained.

Sanitized evidence and disabled/global-only/Atenea-only compose predecessors
are beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.5-atenea-only-activation`
on the control host. The SHA-256 of `SHA256SUMS` is
`d782f7029879b391b7b25bf22d1756ba3e35604cf94e399e2c161ba31546bae3`.
A separate authorization is required before task 7.6; task 7.7 retains its
independent single-use in-product operator gate.

Task 7.6 is complete. Change progress is `50/60`; task 7.7 is the exact next
task but was not started. The operator's separate authorization was normalized
only for isolated AX42 release acceptance from programme commit
`1f3dee6282bf8f34db98cff04bb3240b827b307a` and tree
`acd99e94b87ee1d97cac931f058c85d125d471ff`. It excludes the mandatory
in-product task 7.7 confirmation, real WorkSession 16 release, prompts,
AgentRun retries, runtime start, Beautips, other projects and foreign
resources.

The private AX42 sandbox imported the exact installed finalizer and worker
receipt validator at SHA-256
`dc8f4374f372127163df467c317a2f7fabff4af5e1667799a448173ac9546e15`
and
`e6f24a3265b1367ece444fcb1083d264e1024182884cbf5019560f81bd569193`.
The exact published test source SHA-256 was
`384d3c0b602d59fed1d7b02348270821ff945e51888efa4c5becb1e9a788c377`.
Under one finite 300-second bound, all 38 tests passed in 2.037 seconds with
zero failures, errors or skips.

The accepted real-filesystem synthetic release advanced exact fixed ownership
through `RELEASED` revision 6, retired only its derived allocation, released
heavy before normal admission, disabled only its synthetic registration and
retained its workspace and declared retained classes. Immediate repetition
returned the identical request/ownership fingerprints and receipt SHA-256 with
zero repeated mutation. Interruption after every mutation boundary and loss of
response after every persisted journal successor resumed the same operation
without reconstructing or repeating already released ownership.

The same installed-byte run rejected unlabelled, partially labelled,
foreign-owned, wrong-session, wrong-project, symlinked and ambiguous fixtures
unchanged. Additional duplicate, unknown, production-like, incomplete,
foreign-worker, foreign-project, foreign-session and noncanonical-operation
cases also failed closed before mutation. The harness compared every recorded
fixture identity, exact-cleaned only those still identical paths and preserved
the unrelated sentinel. No real HTTP release request was sent and the
installed release journal remained empty.

The first outer wrapper expected the historical suite count `34` after the
successful process had already reported `38/38`; that stale assertion made
only the wrapper exit before its own summary. The complete log proved `OK`, no
test process remained and the suite was deliberately not rerun. The four
staging files were individually re-hashed, explicitly removed by recorded
path, and their now-empty directory was removed. Zero synthetic fixture,
process, journal or real worker resource remains.

Before and after acceptance, the registry, WorkSession 16 workspace,
allocation and admission hashes remained exactly
`6dbb541e51d672236af660e01f83d9f89b0e3c0a5652757340170f2a70ca87e7`,
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`,
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`
and
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`.
All four AX42 services remain active with zero restarts; rootless slots remain
`3/0/0/3`; backup/check/health are active with successful exit zero results;
rootful Docker/containerd remain inactive/masked; and all three RAID arrays
remain `[UU]`.

All unrelated control-plane container, network and volume fingerprints are
identical before and after. Production remains on exact image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
and preview on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`;
both are running with zero restarts and return HTTP 200. Beautips remains
clean and upstream-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`, returns HTTP 200 and stays
remote-close ineligible. The foreign local `atenea-activation-code_default`
network remains present with zero containers and untouched.

Production still has 15 WorkSessions, 96 terminal AgentRuns and remote-close
counts `NOT_REQUIRED:2`, `NOT_STARTED:3`, `UNVERIFIED_LEGACY:10`.
WorkSession 16 remains `CLOSED/UNVERIFIED_LEGACY/revision 0`; WorkSession 17
remains `OPEN/NOT_STARTED/revision 0` with exactly one turn, run, attachment
and binding; AgentRun 96 remains failed without retry or recovery failure; and
legacy plan/operation counts remain zero. No prompt, response, attachment
content, screenshot, credential, token, cookie, `auth.json`, Codex history or
environment dump was read or retained.

Task 7.6 introduces no visible product change, so no new Playwright run is
required. Sanitized evidence is present beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.6-isolated-release-acceptance`
on both the control host and AX42. The SHA-256 of each `SHA256SUMS` is
`f8e0154658d5f08224277f47492fd6a7e27667424024c8d334c6560a04ee471f`.
Task 7.7 remains stopped for the operator's real in-product, single-use
confirmation and cannot be simulated or executed through SSH.

The task 7.7 preflight identified a historical compatibility gap without
starting task 7.7: AgentRun 96 correctly remains immutable with null pre-V63
typed capacity fields, so the existing shared operator projection could not
prove that WorkSession 16 still owns the blocked capacity. The correction is
default-disabled and canonical-Atenea-only. It considers only the immediate
older closed WorkSession, requires exact remote/pre-dispatch/project/worker
identity and obtains a read-only fixed-root AX42 ownership diagnosis. Missing,
partial, foreign, ambiguous, protocol and transport results fail closed in
their distinct categories; no alternative owner is discovered or adopted.

The published Atenea candidate correction is
`b4c6f88879fb396b39b3cb0364f6577c4c30362a`, tree
`62c026dc7a664009b5f37c39c6c40ac59b4000fa`. Its complete backend suite passes
682/682 with all 63 migrations on an empty isolated database. The unchanged
web implementation passes its production build and 10/10 focused Playwright
checks at `1440x900` and `390x844`, separating fixture/persistence, DOM and
visual acceptance. Android unit/build validation passes without Android source
changes, publication or installation. The programme worker suites pass 120
focused tests and 238 expanded tests with one deliberate skip; both installer
suites pass. Strict OpenSpec validation passes.

The reviewed worker successor SHA-256 values are
`101a3c784b5a371837c45d99110f5181939bc2908faf509a84ffdded1afd4945` for
the authenticated worker,
`df3515f92a99b568840e2cd77798171e8fc3207e7bb88ad61ec992ed07610c54` for
the fixed-root releaser/diagnoser,
`77e1c09de79c38195b16310567f829e73efcba32987b7ac37291d35aa7e61266` for
the worker installer and
`c80e1234aeca10a8762825904055f2a608154adee4e1c8aa96c867dd0a80f87a` for
the routing installer. No wildcard sudo authority or caller-selected
infrastructure value is introduced.

The final read-only recapture found production, preview and Beautips healthy
with zero relevant restarts. Canonical Beautips remains clean/upstream-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`; its separate AX42
administrative checkout remains clean and unchanged at documented historical
commit `5044a3b07b3db82895e9c8ff47bc4bc9b0e97130`. WorkSessions 16/17 remain
`CLOSED/UNVERIFIED_LEGACY/revision 0` and `OPEN/NOT_STARTED/revision 0`;
AgentRun 96 remains terminal failed, unretried and unmodified; WorkSession 17
retains one turn, run, attachment and binding; and legacy plan/operation counts
remain zero.

All exact ownership fingerprints remain unchanged; WorkSession 17 still has
no allocation or admission. AX42 services remain active with zero restarts,
rootless slots remain `3/0/0/3`, rootful Docker/containerd remain inactive,
backup/check/health remain successful and all three RAID arrays remain `[UU]`.
No deployment, installation, configuration, release, prompt, retry, ownership,
production, preview, Beautips, foreign or unrelated mutation occurred.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-prerequisite-correction`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-prerequisite-correction`.
Both copies verify 9/9 files; the SHA-256 of each `SHA256SUMS` is
`9aa5171e9b5b78bf96d4f975dfd02876e6b88d1f90b088105e6f836e08d4f76f`.

OpenSpec progress remains `50/60`; task 7.7 is still the first pending task.
The correction is not active in production. Before task 7.7 can present the
real plan, task 6.8 requires a new separate exact authorization for the new
backend image and reviewed AX42 successor. Task 7.7 then retains its own
mandatory in-product single-use operator confirmation; neither gate authorizes
a prompt, AgentRun retry, Beautips, another project or a foreign resource.

The exact correction rollout candidate is now prepared but remains unused.
The candidate JAR SHA-256 is
`efc39da85a5e1528245ab106aa3d6bc4847dd35e2dff5abda193f5b62381dda1`.
Retained image
`atenea-remote-close-v63-candidate:b4c6f88879fb396b39b3cb0364f6577c4c30362a`
has ID
`sha256:2e9b4075d180d07d645289f8dae57d79f4f11f7d52beab58e2dd172d940c4112`.
It retains the running predecessor's exact 12-layer prefix, adds only the
application JAR layer, has an exact matching non-secret runtime-configuration
projection and verifies the same JAR SHA-256 from inside an isolated
`--network none` ephemeral check. Zero container uses it and the check left
zero residual containers.

The exact programme worker archive for commit
`2a3936bdfde7581b88de7923d40e411557ae4f16`, tree
`8beb3e2e29a787f0fd17ace50036bb41a28c76d5`, has SHA-256
`76c6a190c9fe9960ef425b28f52eb89002dcb38661130ca68b72f95ff634f171`.
The currently installed AX42 predecessor remains byte-exact at worker
`e6f24a3265b1367ece444fcb1083d264e1024182884cbf5019560f81bd569193`,
release mediator
`dc8f4374f372127163df467c317a2f7fabff4af5e1667799a448173ac9546e15`
and installer
`aaea361d7a732d9fbc957b5c2d757fab44c0960a47a75c6fe64eb98159183613`.

The first build attempt used the local image ID directly in `FROM`; BuildKit
rejected it before creating any layer or image because it treated the ID as an
external repository. The corrected build used the exact local predecessor tag
with `--pull=false --network=none`. Production remained on predecessor image
`sha256:1c67ac36a6b45a4b0004e15ba79bcd6d50addfb4b09d8b7890b43c8ef092801a`
with zero restarts and unchanged Compose SHA-256
`b96e5721e558460ae67b799da8e526dbf0c3668c8f267cef004d711d764323b8`.

Final health checks return HTTP 200 for production, preview and Beautips with
zero relevant restarts. The candidate has zero consumers. All four AX42
services and all three backup/check/health timers remain active; their last
jobs report `success/0`; slots remain `3/0/0/3`; rootful Docker/containerd
remain inactive; and all three RAID arrays remain `[UU]`. The unrelated local
`atenea-activation-code_default` network remains present with zero containers
and untouched. The previously captured exact WorkSession/AgentRun/ownership
projection remains unchanged because no candidate code was executed against
production.

The exact rollout manifest and artifacts are beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-rollout-candidate`
and
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-rollout-candidate`.
Both copies verify 4/4 files; the SHA-256 of each `SHA256SUMS` is
`25bc7258e7e3e42727e419ca2649b2175173eb97a9adcc543584f5e0f7c8afc2`.
No production deployment, AX42 installation, configuration change, release,
prompt, retry, runtime, Android/APK, Beautips, ownership or foreign-resource
mutation is authorized or performed by preparing this retained candidate.

The operator separately authorized only the prerequisite rollout identified by
manifest seal
`25bc7258e7e3e42727e419ca2649b2175173eb97a9adcc543584f5e0f7c8afc2`,
backend image
`sha256:2e9b4075d180d07d645289f8dae57d79f4f11f7d52beab58e2dd172d940c4112`,
candidate commit `b4c6f88879fb396b39b3cb0364f6577c4c30362a` and AX42
bundle SHA-256
`76c6a190c9fe9960ef425b28f52eb89002dcb38661130ca68b72f95ff634f171`.
The authorization explicitly excluded task 7.7 confirmation, WorkSession 16
release, prompts, retries, APK/Android, Beautips, other projects and foreign or
ambiguous resources.

The complete preflight reverified local, internal and GitHub Git identities,
both evidence copies, running/retained images, Compose, all five ownership
hashes, WorkSessions 16/17, AgentRun 96, zero plans/operations/journals,
services, slots, backup/check/health and RAID. A first unprivileged journal
read was inconclusive and its properly privileged repetition first met an SSH
transport timeout; the finite retry proved zero journals before mutation.

An exact static AX42 predecessor was retained without token, dynamic
configuration, registry, ownership or session state. Its SHA-256 is
`ed79ee777cc092503429dba972784e2364feed9e55e237dd6c4a961db4d96a59`.
The first worker-installer apply failed closed because the release mediator was
still its accepted predecessor. Immediate inspection proved all five static
files, registry, service, ownership and journals remained exact. The same
authorized bundle's reviewed routing installer then performed its designed
prerequisite: exact release/diagnosis mediator plus exact no-wildcard sudo
authority, with default routing false and no service restart. The worker
installer then completed and verified.

Installed AX42 successor SHA-256 values are worker
`101a3c784b5a371837c45d99110f5181939bc2908faf509a84ffdded1afd4945`,
release/diagnosis mediator
`df3515f92a99b568840e2cd77798171e8fc3207e7bb88ad61ec992ed07610c54`
and worker installer
`77e1c09de79c38195b16310567f829e73efcba32987b7ac37291d35aa7e61266`.
The diagnosis route rejects an unauthenticated request with HTTP 401. No token
was read and no authenticated release or diagnosis was invoked through SSH.

The exact backend predecessor remains tagged as
`atenea-remote-close-v63-rollback:pre-b4c6f888-1c67ac36`. Only the existing
production image reference was pointed at the authorized successor; Compose
bytes and release-gate configuration did not change. Only
`atenea-backend-prod` was recreated. It reached HTTP 200 on bounded attempt 8
with zero restarts and now runs exact image
`sha256:2e9b4075d180d07d645289f8dae57d79f4f11f7d52beab58e2dd172d940c4112`.
Preview remains on exact image
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`.
Production, preview and Beautips return HTTP 200 with zero relevant restarts;
all unrelated container, network and volume fingerprints remain exact.

Flyway V63 remains successful. WorkSession 16 remains
`CLOSED/REMOTE/UNVERIFIED_LEGACY/revision 0`; WorkSession 17 remains
`OPEN/REMOTE/NOT_STARTED/revision 0`; and AgentRun 96 remains terminal failed,
pre-dispatch, unretried and complete in all six execution-profile fields.
WorkSession 17 retains exactly one turn, run, attachment and turn binding.
Retry-child, legacy-plan and legacy-operation counts remain zero. Routing
remains `ax42-01` enabled/healthy with capacity `4/2`, use `0/0`, zero
non-terminal runs and zero active leases.

All five ownership hashes remain exact and WorkSession 17 allocation/admission
remain absent. The release journal remains empty; all four AX42 services and
all three backup/check/health timers remain active; last jobs remain
`success/0`; slots remain `3/0/0/3`; rootful Docker/containerd remain inactive;
and all three RAID arrays remain `[UU]`. The unrelated local
`atenea-activation-code_default` network remains present with zero containers
and untouched.

No plan, release, prompt, response, retry, runtime start, Android/APK,
Beautips, foreign-resource or retention mutation occurred. Sanitized evidence
and the static predecessor are present locally, on the control host and on
AX42 beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-prerequisite-rollout-execution`
with the corresponding local copy beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-prerequisite-rollout-execution`.
All three copies verify 3/3 files; the SHA-256 of each `SHA256SUMS` is
`b862cbd7b9eaf178e3bed469a8ed6369edc4ddd74f8312e2dced329555221ccc`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
The rollout authorization is consumed. Task 7.7 still requires the operator to
perform the real in-product intervention; confirmation may not be simulated or
invoked through SSH, and no prompt or AgentRun retry is authorized.

The subsequent operator check proved that the prerequisite rollout still did
not render `Reconciliar cierre`. Read-only production inspection identified the
exact cause: WorkSession 16 predates canonical source-observation persistence
and all four of its observation fields are null, while the immediate successor
WorkSession 17 contains the exact persisted canonical observation. The first
compatibility correction deliberately required the historical owner itself to
carry that observation and therefore continued to fail closed. No task 7.7
plan or release was created and no retained state was changed.

The published Atenea successor correction is commit
`a0fcde629eac76db1a11559e94401a1db566d33b`, tree
`2a3d4020dd75759d99d76706ab264fa8620276f7`. It permits only the exact,
distinct, later, same-project, immediate-next WorkSession to serve as the
historical owner's canonical-source witness. That witness is bound through
projection, diagnosis, plan, locked confirmation, release, idempotent replay
and restart recovery. Missing, partial, foreign and non-immediate witnesses
fail closed before worker I/O. WorkSession 16 remains the owner, its historical
fields are not backfilled, and neither WorkSession 17 nor AgentRun 96 is
mutated or executed.

Main compilation passes. The focused backend suite passes 53/53 and the full
backend suite passes 688/688 on a fresh isolated Docker database. The exact
candidate JAR SHA-256 is
`dbe33e4f7c46ac506a064917b8cefc52933c7711b0609a9b1d6aeba6c940d1bc`.
The retained backend image
`atenea-remote-close-v63-candidate:a0fcde629eac76db1a11559e94401a1db566d33b`
has ID
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`.
It preserves the running image's exact 13-layer prefix, adds only the packaged
JAR layer and verifies the same JAR SHA-256 inside an isolated
`--network none` ephemeral container. Zero container uses the candidate.

Production remains on exact image
`sha256:2e9b4075d180d07d645289f8dae57d79f4f11f7d52beab58e2dd172d940c4112`
and preview on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`;
both are running with zero restarts and return HTTP 200. Beautips returns HTTP
200 and remains clean/upstream-exact at
`9e122bf024d29b9cda56b27f8a32c218e1f0d433`. AX42 bytes and configuration
remain unchanged: all four services are active with zero restarts, slots are
`3/0/0/3`, backup/check/health remain successful, rootful Docker/containerd
remain inactive and all three RAID arrays remain `[UU]`.

WorkSessions 16/17 remain respectively
`CLOSED/REMOTE/UNVERIFIED_LEGACY/revision 0` and
`OPEN/REMOTE/NOT_STARTED/revision 0`; AgentRun 96 remains terminal failed and
unretried; WorkSession 17 retains one turn, run, attachment and binding; and
plan, operation and release-journal counts remain zero. All five ownership
fingerprints remain exact and WorkSession 17 still has no registration,
allocation or admission. No prompt, response, attachment content, screenshot,
credential, token, cookie, `auth.json`, Codex history or environment dump was
read or retained.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-historical-witness-correction`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-historical-witness-correction`.
Both copies verify 7/7 files; the SHA-256 of each `SHA256SUMS` is
`3cdebb962850034c7c69fa13c70bdc78e007df75b411c7477d3dc697e941c2b2`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task and
has not started. The new image is not deployed. Task 6.8 requires a fresh,
separate, exact authorization before replacing only the canonical Atenea
production backend with image
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`.
No AX42 installation is required or requested. After rollout and real
Playwright validation at `1440x900` and `390x844`, task 7.7 retains its own
independent in-product single-use operator confirmation. Neither gate
authorizes WorkSession 16 release through SSH, prompts, AgentRun retry,
runtime, APK/Android, Beautips, another project or foreign resources.

The operator subsequently authorized only that exact pre-7.7 backend rollout
from manifest seal
`3cdebb962850034c7c69fa13c70bdc78e007df75b411c7477d3dc697e941c2b2`,
image
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`
and candidate commit `a0fcde629eac76db1a11559e94401a1db566d33b`. The
authorization explicitly excluded task 7.7 confirmation, WorkSession 16
release, prompts, retries, runtime, AX42 changes, APK, Beautips and other
projects.

The complete preflight reverified the manifest, local/internal/GitHub Git,
candidate JAR and image, production predecessor, preview, Compose, WorkSessions
16/17, AgentRun 96, zero plans/operations, all five ownership hashes, AX42
services and RAID. An initial ownership hash command used obsolete numeric
session-directory names and failed before hashing any target. The canonical
installed registry plus persisted remote session identities resolved the exact
server-owned UUID paths; the repeated check proved all five expected hashes
without accepting a caller path or invoking diagnosis/release.

The running predecessor was retained as
`atenea-remote-close-v63-rollback:pre-a0fcde62-2e9b4075` at exact image
`sha256:2e9b4075d180d07d645289f8dae57d79f4f11f7d52beab58e2dd172d940c4112`.
Only the existing production service tag was pointed at the authorized image
and only `atenea-backend-prod` was recreated. It reached HTTP 200 on bounded
attempt 8 and now runs the exact successor with zero restarts. Compose remains
byte-exact at SHA-256
`b96e5721e558460ae67b799da8e526dbf0c3668c8f267cef004d711d764323b8`.
Unrelated container, network and volume fingerprints are identical before and
after.

The live persistence postflight found WorkSession 16 unchanged at
`CLOSED/REMOTE/UNVERIFIED_LEGACY/revision 0`, WorkSession 17 unchanged at
`OPEN/REMOTE/NOT_STARTED/revision 0`, and AgentRun 96 terminal failed,
pre-dispatch, unretried and complete in its six execution-profile fields.
WorkSession 17 retains exactly one turn, run, attachment and binding. Retry
children, legacy plans, legacy operations and non-terminal runs remain zero;
worker `ax42-01` remains enabled/healthy at capacity `4/2`, use `0/0`.

All five ownership SHA-256 values remain exact and WorkSession 17 allocation
and admission remain absent. AX42 release journals remain zero; its four
services are active with zero restarts; slots remain `3/0/0/3`;
backup/check/health remain `success/0`; rootful Docker/containerd remain
inactive; and RAID remains `3/3 [UU]`. No AX42 byte or configuration changed.
The unrelated local `atenea-activation-code_default` network remains present
with zero containers.

The unchanged web implementation passes 10/10 focused Playwright checks at
`1440x900` and `390x844`. Sanitized synthetic-data screenshots and DOM
assertions prove state hierarchy, first-viewport primary action, role
permissions, long-message wrapping, confirmation controls, clipping and
overflow. No real plan or confirmation was created. The authenticated WS17
DOM/visual check remains an operator-only intervention because no credential,
token or cookie may be read or reused.

Production and preview actuator endpoints return HTTP 200, Atenea and preview
public roots return their expected authentication-boundary HTTP 401, and
Beautips returns HTTP 200. A separate postflight probe found that
`ateneaapp.yudri.es` returns HTTP 502: unchanged Caddy routes it to
`expo-prod:8084`, while the unchanged current container network has no such
alias. No pre-rollout response baseline exists for that root. Exact unchanged
Caddy/Compose bytes plus unrelated container/network fingerprints prove the
authorized backend rollout did not introduce this routing state. It was not
adopted, repaired or reconfigured because it is outside the authorization and
its ownership/status is ambiguous.

Sanitized rollout evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-historical-witness-rollout-execution`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-historical-witness-rollout-execution`.
Both copies verify 5/5 files; the SHA-256 of each `SHA256SUMS` is
`f23c1963e14855f4e99d3d425dd2e125a2b205a186be856f554b94f50e76d3f2`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task and
has not been confirmed. The rollout authorization is consumed. Progress stops
before the operator's real in-product check because of the mandatory 7.7 gate
and the separately observed ambiguous `ateneaapp.yudri.es` routing state. No
release, prompt, response, retry, runtime, AX42, APK/Android, Beautips,
other-project, ownership or retained-state mutation occurred.

The operator subsequently retired both obsolete Expo routes, accepted the
permanent absence of the empty `atenea-activation-code_default` network and
promoted the sole active account to `PLATFORM_ADMINISTRATOR` with its prior
sessions revoked. The accepted current source checkout is clean at `main`
commit `e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`; production still runs exact
backend image
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`
with zero restarts. These separately authorized changes did not authorize or
invoke WorkSession release, prompt retry, runtime, AX42 or Beautips mutation.

The operator then performed the mandatory real task 7.7 intervention from
Atenea. The finite plan matched WorkSession 16, canonical Atenea, worker
`ax42-01`, the active platform administrator and the accepted ownership
fingerprint. Its single-use confirmation created one immutable operation and
two events, then failed closed before the first worker mutation. The operation
is durably `BLOCKED` revision 2 with
`WORKSPACE_RELEASE_PREFLIGHT_REJECTED/OWNERSHIP`, next action
`CONTACT_PLATFORM_ADMINISTRATOR`, `retryable=false` and no receipt. WorkSession
16 is `CLOSED/BLOCKED/revision 2`; no release journal exists.

Registration, admission and allocation remain active and byte-exact. All five
accepted ownership hashes remain unchanged. WorkSession 17 remains
`OPEN/REMOTE/NOT_STARTED/revision 0` with one turn, run, attachment and binding;
AgentRun 96 remains terminal failed with zero retry children. All 96 AgentRuns
are terminal. AX42 has zero WorkSession 16/17-labelled containers, slots remain
`3/0/0/3`, all four services remain active with zero restarts, backup/check/
health remain `success/0`, rootful Docker/containerd remain inactive and all
three RAID arrays remain `[UU]`. Production, preview and isolated Beautips
return HTTP 200. No ownership was reconstructed or retried.

The published correction is Atenea commit
`5b3a08344bdc0821e75fe7c37ff1bbd3c22ff838`, tree
`0918252a78a9e63d825eedcbacf4e2fb19fcc25e`; functional commit
`37f46012fadfc8511bb1e77fd19d199fa331fcd9`. Additive V64 binds every consumed
single-use plan to an operation independently from the operation's immutable
original plan. Only the complete exact blocked predicate may obtain a fresh
read-only diagnosis and plan; confirmation moves the same operation to
`RECONCILING`. Lost response and restart reuse that identity. Startup resumes
only `REQUESTED/RECONCILING` and never a `BLOCKED` operation without explicit
confirmation. Every other blocked, foreign, partial or ambiguous state remains
unavailable.

Web and Android show `Volver a validar cierre` only when the backend proves
that exact predicate and the current role is `PLATFORM_ADMINISTRATOR`. A stale,
consumed or newly blocked plan is discarded until explicit refresh. The final
backend suite passes 694/694 on a fresh isolated PostgreSQL database with all
64 migrations. Focused backend/migration/state tests pass 31/31. Android unit
and build validation passes without configured secret files; the new canary is
0.5.99/code 132. Web build and 13/13 real Playwright checks pass at `1440x900`
and `390x844`, proving fixture/data, DOM and visible hierarchy, first-viewport
action, permissions, long messages, clipping and overflow.

The exact rollout image is
`sha256:ae98003faf568d461dd092d5299c6b18ebd9c825754d76a0800efdb98ebb941b`.
It preserves the running production predecessor's 14-layer prefix, adds one
networkless JAR layer and contains JAR SHA-256
`dbe33e4f7c46ac506a064917b8cefc52933c7711b0609a9b1d6aeba6c940d1bc`.
The optional Android debug canary SHA-256 is
`3557a154ac9d6bf61aa78a09d377d11a723c42ce9b74d89a6465d354905f22a0`.
Neither artifact is deployed, installed or published.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-blocked-recovery-candidate-20260806`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-blocked-recovery-candidate-20260806`.
Both copies verify 11/11 files; the SHA-256 of each `SHA256SUMS` is
`a3a5fc41fad0b25ebdaa3496b9fef570cdf27c3ea8ea4c7493eac9a1006d2a26`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
Progress stops before V64 production migration, backend deployment, Android
publication/installation and a second real confirmation. A separate explicit
rollout authorization must name the exact backend image and any exact Android
artifact. After rollout and real visual verification, the operator must
generate and confirm a new single-use plan from Atenea. No SSH release, prompt,
AgentRun 96 retry, runtime, AX42 change, Beautips or other project is authorized.

On 2026-08-07 the operator separately authorized the three blocked-candidate
remediations only: reconcile the apparent Git publication divergence,
investigate the Beautips TLS observation and generate a correctly signed
Android candidate. No deployment, publication, installation, second task 7.7
confirmation, release, prompt, retry, runtime or AX42 mutation was authorized.

The canonical local worktrees publish directly into the internal repositories
on `atenea`. Their branch refs are exact at programme
`e754980589f58e66b00b9a58e4966f8e6cb82b19` / tree
`a0eb079382751e5a6069eaac9851609a217f3b37` and Atenea
`5b3a08344bdc0821e75fe7c37ff1bbd3c22ff838` / tree
`0918252a78a9e63d825eedcbacf4e2fb19fcc25e`. The older values observed from
inside those repositories belong to their secondary GitHub origins, not the
internal publication channel. No GitHub ref was overwritten, adopted or
reconfigured; both internal repositories remain clean.

The reported TLS mismatch was also positively attributed without mutation.
`beautips.yudri.es` is neither present in Atenea's active Caddy configuration
nor the canonical Beautips endpoint; it resolves to an unrelated endpoint.
Canonical `beautips.app` serves a valid same-name certificate, returns HTTP 200
from its health endpoint and preserves the expected HTTP 302 root response.
The isolated Beautips control remains running with zero restarts. No DNS,
certificate, route, resource or Beautips byte changed.

One clean production-configured Android build from exact Atenea commit
`5b3a08344bdc0821e75fe7c37ff1bbd3c22ff838` ran the `core-console` and `app`
unit suites at 43/43 with zero skips, failures or errors, then assembled
`0.5.99` / versionCode `132`. The 59,896,815-byte candidate SHA-256 is
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`.
APK Signature Scheme v2 verifies and its certificate SHA-256 is exact to the
established installed channel:
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
No secret or environment value was printed or retained. The temporary build
worktree was removed after the exact APK was retained and independently
verified. The earlier APK
`3557a154ac9d6bf61aa78a09d377d11a723c42ce9b74d89a6465d354905f22a0`
has a different signer and must not be published or installed.

Post-remediation production and preview return HTTP 200 on their unchanged
exact images with zero restarts. AX42's four worker services remain active
with zero restarts, rootful Docker/containerd remain inactive, all three RAID
arrays remain `[UU]`, release journals remain zero and backup/check/health
timers remain active with last result `success/0`. The accepted absent target
`atenea-activation-code_default` network was not recreated.

The sealed exact rollout manifest and signed APK are retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-signed-apk-candidate-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-signed-apk-candidate-20260807`.
Both copies verify 5/5 files; the SHA-256 of each `SHA256SUMS` is
`20a72db1925fab2caafc38509a8396a53e9b48da33a9c59d8f2e0b9b87367939`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
The next gate requires a new exact authorization naming backend image
`sha256:ae98003faf568d461dd092d5299c6b18ebd9c825754d76a0800efdb98ebb941b`
and signed APK SHA-256
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`.
Only after deployment, publication/installation and real web/Android visual
verification may the operator generate and confirm a fresh single-use task
7.7 plan from Atenea.

The operator then gave the exact pre-7.7 rollout authorization bound to
manifest SHA-256
`9c8195d408c7af34b598bdd3531ab8f0657aeb39b6deffaeed3336fc133be331`,
backend image
`sha256:ae98003faf568d461dd092d5299c6b18ebd9c825754d76a0800efdb98ebb941b`
and signed APK SHA-256
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`.
The authorization excluded task 7.7 confirmation, WorkSession 16 release,
prompts, retries, runtime, AX42, Beautips and every other project.

The final preflight matched the manifest, evidence, clean/upstream-exact Git,
Flyway V63, production/preview images, WS16 `CLOSED/BLOCKED/revision 2` without
receipt, its immutable `BLOCKED/OWNERSHIP/CONTACT_PLATFORM_ADMINISTRATOR`
operation, WS17 `OPEN/NOT_STARTED/revision 0`, unretried failed AgentRun 96 and
legacy counts `3/1/2`. The exact candidate image was loaded on the control host
and the predecessor was retained under an exact rollback tag. Only
`atenea-backend-prod` was recreated. The candidate returned HTTP 200 with zero
restarts.

The mandatory migration gate rejected the rollout: production Flyway remained
at successful V63, V64 count was zero and the V64 plan-consumption columns were
absent. No startup release, retry or state mutation occurred. Read-only
artifact inspection identified the exact cause: sealed JAR
`dbe33e4f7c46ac506a064917b8cefc52933c7711b0609a9b1d6aeba6c940d1bc`
contains migrations only through V63 and omits
`V64__authorize_blocked_remote_close_recovery.sql`, although the exact source
tree contains that file with SHA-256
`8996f41539079c1d0b7fdd2325230cfebf7b802c358ef1a8657f1119325cb77d`.
The image therefore cannot satisfy its sealed V64 claim.

The exact predecessor
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`
was restored immediately by retagging the retained rollback and recreating
only the production backend. Final production returns HTTP 200 with zero
restarts, the Compose tag resolves to that predecessor and the rejected image
has zero running consumers. Flyway remains successful V63. WS16, its immutable
operation, WS17, AgentRun 96 and counts `3/1/2` remain exact.

Preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`
at HTTP 200 with zero restarts. Beautips remains running with zero restarts and
canonical health HTTP 200. AX42 was not mutated: all four services remain
active with zero restarts, backup/check/health remain `success/0`, rootful
Docker/containerd remain inactive, all three RAID arrays remain `[UU]` and
release journals remain zero. The signed APK was not published or installed;
the established published APK remains
`5c32ef4a1f4c017a19f2d970ceb78de525f34026c374a1c9069c5c6b51afe3ee`.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-v64-rollout-rejected-rollback-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-v64-rollout-rejected-rollback-20260807`.
Both copies verify 4/4 files; the SHA-256 of each `SHA256SUMS` is
`866335b435f9eb73ba9aa8e746ba122d5e0d4cfef254821387a0e3736384732c`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
The rollout authorization is consumed by the rejected attempt. Progress stops
before APK publication and before the second real in-product confirmation. A
corrected JAR and image must be built from the exact source tree, completely
retested, independently inspected for V64, sealed under new hashes and receive
a new separate exact rollout authorization.

The operator subsequently authorized only that corrected-candidate preparation
with `Adelante`; no deployment, APK publication/installation, task 7.7
confirmation, WorkSession release, prompt, retry, runtime, AX42, Beautips or
other-project mutation was authorized.

A clean detached worktree at exact Atenea commit
`5b3a08344bdc0821e75fe7c37ff1bbd3c22ff838`, tree
`0918252a78a9e63d825eedcbacf4e2fb19fcc25e`, ran offline Maven `clean verify`
inside a Docker-internal JDK/Git runner connected only to a fresh PostgreSQL 16
database. All 694 backend tests pass with zero failures, errors or skips. The
accepted run declared the fixture's `/workspace/repos` root and used finite
PostgreSQL capacity; three earlier environment-only attempts without the full
database/runner/root contract produced no selected artifact.

The fresh 56,456,650-byte JAR SHA-256 is
`f976353d79ae767cf3023b76b634d62f979c3ad4ec5fe5ce02b0ed9b51bc6392`.
Its highest and single V64 entry is
`V64__authorize_blocked_remote_close_recovery.sql`, and the embedded migration
hash is exact at
`8996f41539079c1d0b7fdd2325230cfebf7b802c358ef1a8657f1119325cb77d`.

Corrected image
`sha256:9e492fb567211e27cbc02ddcd4290cd55ed136b78e00a5625675023e193a8f95`
has exact parent
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`,
preserves all 14 predecessor layers and adds exactly one JAR layer. Independent
extraction from the finished image reproduces the exact JAR and V64 hashes.
An isolated real-image smoke returns HTTP 200 with zero restarts, applies
successful Flyway V64 exactly once and exposes all three V64 plan-consumption
columns. All test/smoke containers, networks, worktrees, contexts and runner
images were removed; the corrected rollout image remains retained locally.

The signed Android candidate remains exact at `0.5.99 (132)`, SHA-256
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`
and established channel signer
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
It remains unpublished and uninstalled.

Post-preparation production remains restored on predecessor
`sha256:d4ecec27bd1b7cd0ba5dca095a2524ee33ab342b99e6d0c774f0b2ddbbc568d2`
at HTTP 200 with zero restarts. Preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`
at HTTP 200 with zero restarts. Beautips remains running with zero restarts and
canonical health HTTP 200. The established published APK remains
`5c32ef4a1f4c017a19f2d970ceb78de525f34026c374a1c9069c5c6b51afe3ee`.
Canonical source, programme and internal worktrees remain clean. No live
database, WorkSession, AgentRun, ownership, service, slot, backup, RAID,
routing or unrelated resource changed.

Corrected evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-v64-corrected-rollout-candidate-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-v64-corrected-rollout-candidate-20260807`.
Both copies verify 6/6 files; the SHA-256 of each `SHA256SUMS` is
`dff1dadd07a3010dfe399a5cff4e3fabe1969a953afce74ff1939c462e4469ed`.

OpenSpec progress remains `50/60`; task 7.7 remains first pending. Progress
stops before the corrected rollout. A new separate exact authorization must
name corrected manifest SHA-256
`ab210244eeea6177dc9c38e0136f473ae84ab786321ba5d38075d8483af843d2`,
backend image
`sha256:9e492fb567211e27cbc02ddcd4290cd55ed136b78e00a5625675023e193a8f95`
and APK SHA-256
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`.

The operator then supplied that exact authorization and again explicitly
excluded task 7.7 confirmation, WorkSession 16 release, prompts, retries,
runtime, AX42, Beautips and other projects. Final preflight matched the sealed
manifest, both exact artifacts, clean/upstream-exact Git, production V63,
WS16/WS17/AgentRun 96, counts `3/1/2`, AX42 services, backup, RAID, preview and
Beautips.

Corrected image
`sha256:9e492fb567211e27cbc02ddcd4290cd55ed136b78e00a5625675023e193a8f95`
was transferred and matched independently on the control host. The exact V63
predecessor remained retained under a rollback tag. Only
`atenea-backend-prod` was recreated. Production returns HTTP 200 with zero
restarts, Flyway reports successful V64 exactly once and all three V64
plan-consumption columns exist.

WorkSession 16 remains `CLOSED/BLOCKED/revision 2` with exact
`WORKSPACE_RELEASE_PREFLIGHT_REJECTED`, no receipt and the same immutable
blocked operation. WorkSession 17 remains `OPEN/NOT_STARTED/revision 0`.
AgentRun 96 remains failed and unretried. Plan/operation/event counts remain
`3/1/2`; startup performed no release or retry.

The established publication script published exact signed APK `0.5.99 (132)`,
SHA-256
`8f37ceec4f68faaa6ae5fe7218628aea5e6ca6beeb30a9f79d65423738ffd546`,
to public, protected-current and immutable release 132 paths. All hashes,
Signature Scheme v2 and established signer
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`
verify. The manifest retains exact predecessor `0.5.98 (131)` at SHA-256
`5c32ef4a1f4c017a19f2d970ceb78de525f34026c374a1c9069c5c6b51afe3ee`;
bounded protected manifest/APK probes return HTTP 200 without exposing their
token.

No authorized ADB device exists on the workstation or control host. Both
active Android registrations still report `0.5.98`; physical installation and
authenticated production data/DOM/visual verification therefore remain an
operator intervention. No installation or real-device visual acceptance is
claimed yet.

Preview remains exact at HTTP 200 with zero restarts. Beautips remains running
with zero restarts and canonical health HTTP 200. AX42 remains unchanged: four
services active with zero restarts, backup/check/health `success/0`, inactive
rootful Docker/containerd, three `[UU]` arrays and zero release journals. The
accepted absent target `atenea-activation-code_default` network was not
recreated. No 7.7 confirmation, release, prompt, retry, runtime, AX42,
Beautips or other-project mutation occurred.

Sanitized partial-rollout evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-v64-corrected-rollout-pending-android-install-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-v64-corrected-rollout-pending-android-install-20260807`.
Both copies verify 3/3 files; the SHA-256 of each `SHA256SUMS` is
`9c40ae50519bafb2a2087f70ee5090f1e7ba6bfa27f581a3edb0203e315bded4`.

OpenSpec progress remains `50/60`; task 7.7 remains first pending. Progress
stops before physical Android installation and authenticated production visual
verification. A later, separate authorization remains mandatory before the
real single-use task 7.7 confirmation.

The operator subsequently installed `0.5.99 (132)`. Two real-device
screenshots proved that Atenea correctly opens only the active WorkSession 17;
the Android project resolver exposes no route to closed WorkSession 16. They
also proved a backend projection gap: the open session displayed
`OWNERSHIP_REVIEW_REQUIRED` and the disabled `Contactar con administración`
action even though WorkSession 16 now satisfies the exact persisted blocked
recovery predicate. Asking the operator to open a resulting WS16 screen was
therefore incorrect; the recovery must be projected into WS17 while retaining
WS16 as the immutable target.

Atenea commit `d8419cbf653f6062344d1d21fd7dead368610e18`, tree
`f13c9fc3a2a54ac4bd91085dadbea6b399f7609a`, applies that minimal backend-only
correction. Historical blocked predecessors now expose
`Volver a validar cierre` in the active session only when the exact preflight
error is present and `LegacyRemoteCloseService` independently accepts the
complete server-side eligibility predicate. A failed eligibility check keeps
the existing non-mutating ownership review. No client navigation, Android,
web, schema, release or retry contract changed; installed Android `0.5.99`
already supports the resulting server state.

The focused operator-state suite passes 15/15 and adds exact recoverable and
ineligible predecessor regressions. A clean detached source on an isolated
internal-only PostgreSQL 16 network passes all 696 backend tests and all 64
migrations. The production web build compiles 1,583 modules; all 13 remote
close Playwright checks pass, with fresh 1440x900 and 390x844 evidence proving
state hierarchy, first-viewport action, confirmation, permissions and absence
of clipping or horizontal overflow.

The backend-only candidate is
`sha256:d296f29cedb70bdb81bc375c5a33760e84e534bb6f3344ca0cbece709e5cf0a0`,
with exact parent
`sha256:9e492fb567211e27cbc02ddcd4290cd55ed136b78e00a5625675023e193a8f95`.
It preserves all 15 parent layers and adds one JAR layer. The independently
extracted JAR SHA-256 is
`a4c4d66b12f8745bf192f61fdfeb3ae483ca146da556671573dff9563b57e267`;
its embedded V64 exactly matches source SHA-256
`8996f41539079c1d0b7fdd2325230cfebf7b802c358ef1a8657f1119325cb77d`.
An isolated real-image smoke returns health `UP` with zero restarts and
successful V64. All temporary containers, networks and worktrees were removed.

Production remains on the exact parent image with HTTP 200 and zero restarts.
WorkSession 16 remains `CLOSED/BLOCKED/revision 2` with its exact preflight
error and no receipt; WorkSession 17 remains `OPEN/NOT_STARTED/revision 0`;
AgentRun 96 remains `FAILED` and unretried; plan/operation/event counts remain
`3/1/2`. Preview and Beautips remain healthy with zero restarts. AX42 worker
and proxy services remain active with zero restarts, backup/check/health remain
`success/0`, all three RAID arrays remain `[UU]` and rootful Docker/containerd
remain inactive.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-active-session-projection-candidate-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-active-session-projection-candidate-20260807`.
Both copies verify 7/7 files; the SHA-256 of each `SHA256SUMS` is
`1be9f5ef22e4e8b16caf7fddd44948e56fecd44d7508013e6bc3a69929fa74fa`.

OpenSpec progress remains `50/60`; task 7.7 remains first pending. No
production deployment or task 7.7 action occurred. A separate exact rollout
authorization must name manifest SHA-256
`830488ba8593afb7a3784e6c57010f2c7e03a60529860b17dc7c90c31fc7d92d`
and backend image
`sha256:d296f29cedb70bdb81bc375c5a33760e84e534bb6f3344ca0cbece709e5cf0a0`.
After that backend-only rollout, the operator should remain in WS17 and refresh
it for authenticated data/DOM/visual verification. Generating and confirming
the fresh single-use plan remains a later, independent human gate.

The operator subsequently reported that the application was refreshed and a
new plan was generated. Read-only persistence inspection after the third
failed confirmation found WorkSession 16 at
`CLOSED/BLOCKED/revision 6` with exact
`WORKSPACE_RELEASE_PREFLIGHT_REJECTED`, no release receipt and the immutable
operation at
`BLOCKED/revision 6/OWNERSHIP/CONTACT_PLATFORM_ADMINISTRATOR/non-retryable`.
WorkSession 17 remains `OPEN/NOT_STARTED/revision 0`; AgentRun 96 remains
`FAILED` with zero retry children. WorkSession 16 has five historical plans,
three consumed and zero currently unconsumed and unexpired. The regenerated
plan is therefore no longer actionable and was not reused.

The repeat demonstrated a diagnostic gap rather than an operator-navigation
problem: the blocked-recovery gate proved the retained capacity owner, but it
did not pass the exact complete release request through the same lifecycle
lock, fixed mediator, journal and ownership boundary as real release. Another
human plan could consequently be persisted and consumed before the same
deterministic release rejection surfaced.

Programme commit `9eacd058c51860d30fb526acd7340ec4e233b4bc`, tree
`e4b87e1a5fb72d10c5ad9fb1f970d86573850a9f`, adds the fixed authenticated
`/v1/project-workspaces/release-preflight` worker route and the mediator's
strict read-only diagnosis. It validates the exact full server-built request,
fixed roots, existing journal, lifecycle lock and resource projection without
creating a journal or releasing ownership. The exact sudo grant is limited to
that fixed diagnostic command. Atenea commit
`5ddfee555db442c66aae576a46db5e0798705fe7`, tree
`8764a1311f80cb8fdaf5799dc143f64074d21a2a`, requires this full preflight to
pass before persisting another blocked legacy plan and keeps transport,
protocol, validation/policy and ownership failures distinct.

Programme validation passes the installer contract, 81 worker tests, 43
release-mediator tests, Python compilation and shell syntax. Atenea passes 47
focused tests and all 698 isolated backend tests. Strict OpenSpec validation
passes. A real candidate-image smoke against fresh isolated PostgreSQL reaches
health `UP` with zero restarts and all remote worker, release,
reconciliation and authentication-bootstrap gates explicitly disabled.

The backend candidate is
`sha256:592577c4ca8919363390d88c7017f53a5c24d3e72403b996a68a421849d7d784`,
with exact parent
`sha256:d296f29cedb70bdb81bc375c5a33760e84e534bb6f3344ca0cbece709e5cf0a0`.
It retains the parent's 31 history entries and adds one JAR entry. The exact
JAR SHA-256 is
`fa5ad0ba76b478a5d35dd787b46e367461a34be9e6169ebcc5b5b89788c5ef5a`
and embedded V64 remains exact at
`8996f41539079c1d0b7fdd2325230cfebf7b802c358ef1a8657f1119325cb77d`.
The programme bundle SHA-256 is
`fe30acd565ea02f77e660afee8ecd2b5302c0d90c2b8526cacd26e51cbed82ea`;
its worker and release-mediator hashes are respectively
`4d102a4b02e7e0389d5bbae6e8fc0a45275101dda5b4e7577a7fa71555ef6749`
and
`baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0`.

Post-preparation production remains on the exact parent with zero restarts.
Preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`
and Beautips on
`sha256:ff9d2a0ab2620f0ea198daa029a6c92e9063a5b7369c9c0b3d49e3fab58385f3`,
both running with zero restarts. AX42's worker and attachment services remain
active with zero restarts; backup/check/health last results remain successful;
rootful Docker/containerd remain inactive; all three RAID arrays remain
`[UU]`; and release journals remain zero. The new worker bytes are not
installed. No release, prompt, retry, runtime, APK, AX42, production, preview,
Beautips, other-project or ownership mutation occurred.

Sanitized candidate evidence is retained beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-release-preflight-candidate-20260807`.
All 8 sealed files verify; the SHA-256 of `SHA256SUMS` is
`b3aae7ed4e6d807f32adfe7b4fa6a442a6cbcf24ee30fdd8bff1d5294c9eeffa`.
The exact rollout manifest SHA-256 is
`7f7797339fa011bf26972adde96aa2862dcf78d3827408e9d84745b2c54142ae`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
Progress stops before programme checkout fast-forward, AX42 installation,
production deployment and the later in-product confirmation. A new exact
pre-7.7 rollout authorization must name the final programme commit, programme
bundle SHA-256, Atenea commit, backend image and sealed manifest. That rollout
authorization must not be interpreted as the separate task 7.7 confirmation
or as permission for WorkSession release, prompts, retries, runtime, APK,
Beautips or other projects.

The operator then authorized the exact pre-7.7 rollout bound to programme
checkout `be52f6407974d0a0d9bf7058d67f2bc359cade4c`, programme bundle
`fe30acd565ea02f77e660afee8ecd2b5302c0d90c2b8526cacd26e51cbed82ea`,
Atenea image
`sha256:592577c4ca8919363390d88c7017f53a5c24d3e72403b996a68a421849d7d784`
and manifest
`7f7797339fa011bf26972adde96aa2862dcf78d3827408e9d84745b2c54142ae`.
Task 7.7 confirmation, WorkSession 16 release, prompts, retries, runtime, APK,
Beautips, preview and other projects remained explicitly excluded.

The programme checkout passed exact predecessor, branch, clean-index and
clean-worktree gates and advanced by fast-forward only from
`1b945cb545e0fdb8b3051e4f5d8970ef4580100a` to the authorized commit, tree
`4c34fe31a94cc7d13bb1883dfb13264fd2934512`. No other ref changed and the
transfer bundle was removed from both endpoints.

The canonical AX42 installation then rejected before its service-stop and
file-copy boundary with sanitized deterministic result
`Atenea workspace releaser differs from the reviewed source`. The installed
worker and mediator remained exact at predecessor hashes
`101a3c784b5a371837c45d99110f5181939bc2908faf509a84ffdded1afd4945`
and
`df3515f92a99b568840e2cd77798171e8fc3207e7bb88ad61ec992ed07610c54`;
the worker stayed active with zero restarts. No sudoers, journal, ownership or
runtime changed. The transferred bundle and extracted directory were removed.
The backend image was not transferred or deployed, so production, preview and
Beautips remained exact.

The rejection exposed a sealed installer-order defect. The worker installer
correctly required the new mediator, but the separate canonical routing
installer still sealed the live capacity-diagnosis mediator as its target and
had no representation of the fourth exact `--diagnose-release-preflight`
sudoers rule. The authorized bundle could therefore never upgrade the exact
known predecessor through its canonical entrypoint. Its authorization is
consumed and will not be reused.

Programme correction commit `5db81fdc31070a875e676a85fe362618b6fc1094`, tree
`3d2b8c2fc6f74852bbd9f515b573e39b36c00c15`, advances only that routing
installer. It accepts the exact installed mediator hash and exact three-rule
sudoers predecessor, rejects partial or foreign combinations, installs the
exact successor mediator and adds only the fixed fourth diagnostic rule. The
normal worker installer then verifies the successor. Rollback continues to
retain journals and remove release authority without reconstructing released
ownership.

Shell syntax, routing installer/rollback, worker installer/rollback and strict
OpenSpec validation pass. The worker and release-mediator Python suites pass
124 tests and 141 subtests. The new regression exercises the exact three-rule
predecessor-to-four-rule successor transition; all foreign, partial, symlink,
broad-authority, interruption and retained-journal cases continue to pass.

The corrected programme bundle SHA-256 is
`525b53b8b552c310090d16294546c6cb5c8222054d0eef3bde37be5131a52c72`.
The Atenea source commit, image and JAR remain unchanged at
`5ddfee555db442c66aae576a46db5e0798705fe7`,
`sha256:592577c4ca8919363390d88c7017f53a5c24d3e72403b996a68a421849d7d784`
and
`fa5ad0ba76b478a5d35dd787b46e367461a34be9e6169ebcc5b5b89788c5ef5a`.

Sanitized incident and corrected-candidate evidence is retained beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-release-preflight-installer-correction-20260807`.
All 6 sealed files verify. The corrected manifest SHA-256 is
`22de6c6f66d1452becaa6da5a02e920518f698e47381254a6da200a3b57f6827`
and the SHA-256 of `SHA256SUMS` is
`fec708f03377380d6e1e513775e57f8565d4dc2a7f4d9ff28a45769d3a429cc5`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
Progress stops before the new programme fast-forward, AX42 retry and backend
rollout. A new exact authorization must name the final programme commit, the
corrected bundle, the unchanged backend image and the corrected manifest. It
must remain separate from the later in-product task 7.7 confirmation.

The operator later completed the exact in-product target check and issued one
real confirmation for WorkSession 16 while WorkSession 17 remained the open
client context. The worker rejected fail-closed before the first persistent
mutation: WorkSession 16 retained
`WORKSPACE_RELEASE_PREFLIGHT_REJECTED`, the operation remained blocked without
a receipt, and the fixed AX42 release-journal root still contained zero session
directories. WorkSession 17, AgentRun 96 and every retained owner remained
unchanged.

Read-only comparison of the successful diagnostic path with the real release
found one deterministic service-sandbox defect. The installed worker unit has
`ProtectSystem=strict`, but its effective `ReadWritePaths` did not include
`/srv/atenea/worker/workspace-release-v1`. The host root was still exact
`0700 root:root`; only the worker service mount namespace made it read-only.
The diagnostic could therefore validate the complete request without writing,
while `ReleaseJournalStore.prepare()` could not create the mandatory first
session journal. This also explains the observed absence of any journal leaf
or ownership mutation and rules out Git, RAID, backup, capacity and foreign
resource divergence as the cause.

Programme correction commit
`82e26e118ff156b9398b08ab73b79aa4adb1e860`, tree
`81540f65e118bf4845869345fcd7daca5c3b699c`, adds only that fixed journal
parent to the hardened worker unit's write boundary, advances the sealed unit
hash and adds an installer regression. Attachments remain read-only. Worker
and release-mediator bytes remain unchanged at
`4d102a4b02e7e0389d5bbae6e8fc0a45275101dda5b4e7577a7fa71555ef6749`
and
`baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0`.

The installer/sandbox/rollback suite passes from source and from the extracted
candidate. The release mediator passes 43/43 from source and extracted bundle;
the AgentRun worker passes 81/81. Shell syntax, `git diff --check` and strict
OpenSpec validation pass. The exact bundle SHA-256 is
`82bd783b6d9bf692488bd11cc63a4e6b87dbd05f14be1e821b501e606dd2725a`.

Production remains on
`sha256:2037a4a52c6596b4b7fff201837e55bc87ca2646565cac690cbece709e5cf0a0`;
preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`;
and Beautips remains on
`sha256:ff9d2a0ab2620f0ea198daa029a6c92e9063a5b7369c9c0b3d49e3fab58385f3`.
All three return local health HTTP 200 with zero restarts. AX42's worker and
four proxy services remain active, backup/check/health retain successful
results, rootful Docker/containerd remain inactive, all three RAID arrays
remain `[UU]`, matching transient Codex/Playwright units remain zero and the
release journal remains empty. No new plan, confirmation, release, prompt,
retry, runtime, APK, AX42 installation, production, preview, Beautips or
other-project mutation occurred during correction preparation.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-release-journal-sandbox-correction-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-release-journal-sandbox-correction-20260807`.
Both copies verify 6/6 files. The SHA-256 of `SHA256SUMS` is
`63f833e931eb7168291baeec78db65fb8ce7a7479c701d474ce16d31e52a543a`;
the rollout-manifest SHA-256 is
`1dc6ab2ea756ee853b6e941607411d6405d4fab2dbc7f0c101180f3dd54128bf`.

OpenSpec progress remains `50/60`; task 7.7 remains the first pending task.
Progress stops before the mandatory separate authorization to install this
exact AX42 bundle and restart only the worker service. That rollout must remain
separate from generating another plan and from the later single-use operator
confirmation. It does not authorize WorkSession 16 release, prompts, AgentRun
96 retries, runtime, backend/web, APK, preview, Beautips or other projects.

The operator then authorized exclusively manifest
`1dc6ab2ea756ee853b6e941607411d6405d4fab2dbc7f0c101180f3dd54128bf`
and programme bundle
`82bd783b6d9bf692488bd11cc63a4e6b87dbd05f14be1e821b501e606dd2725a`
for the pre-7.7 AX42 worker rollout. A new plan, confirmation, WorkSession 16
release, prompts, retries, runtime, backend, APK, preview, Beautips and other
projects remained explicitly excluded.

The candidate and installed-predecessor archives passed exact local and remote
hash checks, fixed-prefix member validation and extracted-file validation. The
canonical installer completed its read-only plan and bounded apply, restarted
only the AgentRun worker and passed its established verification. Rollback was
staged but not required. All transferred archives, extracted trees and the
bounded orchestration script were removed.

The installed worker service is now exact at
`21064a91421914588bab464022c55599fe78a9ee4eba25e9c1b9164068eb5f18`;
its installer is
`46ad8b692d78ecd1565e87c22035f0fa93081d42a74742e42c0d7bc7f62b6418`.
Effective `ProtectSystem` remains `strict` and effective `ReadWritePaths`
contains exactly one
`/srv/atenea/worker/workspace-release-v1` entry. Worker and release-mediator
bytes remain unchanged at
`4d102a4b02e7e0389d5bbae6e8fc0a45275101dda5b4e7577a7fa71555ef6749`
and
`baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0`.
The worker is active with zero automatic restarts.

All five retained ownership fingerprints remain exact: registry
`6dbb541e51d672236af660e01f83d9f89b0e3c0a5652757340170f2a70ca87e7`,
WS16 workspace
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`,
WS16 allocation
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`,
WS16 admission
`099e565f0df471685c24925ce02d69431639b024499fd91e4d47c08c6d946e11`
and WS17 workspace
`97b41b63e425eb483175b96bce875ac3190300cedb089b176aa2fdaedd515cbb`.

WorkSession 16 remains `CLOSED/BLOCKED/revision 8` with exact preflight error
and no receipt; its immutable operation remains
`BLOCKED/revision 8/OWNERSHIP/CONTACT_PLATFORM_ADMINISTRATOR`, non-retryable
and without a receipt. WorkSession 17 remains
`OPEN/NOT_STARTED/revision 0`. AgentRun 96 remains `FAILED` with zero retry
children. WS16 plan/consumed/live counts remain `7/4/0` and its event count
remains 8. No plan, operation revision, event, journal or release was created
by the rollout.

The release journal remains empty, matching transient Codex/Playwright units
remain zero and rootless slots remain `3/0/0/3`. Worker, attachment, preview,
image-root and all four proxy services are active with zero automatic
restarts. Backup/check/health retain `success/0`, rootful Docker/containerd
remain inactive and all three RAID arrays remain `[UU]`.

Production, preview and Beautips retain their exact prior image and container
identities, return local health HTTP 200 and have zero restarts.
`atenea-activation-code_default` remains absent. No backend, APK, runtime,
preview, Beautips or other-project mutation occurred.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-release-journal-sandbox-rollout-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-release-journal-sandbox-rollout-20260807`.
Both copies verify 4/4 files; the SHA-256 of `SHA256SUMS` is
`9212d32fb9ccd9b89130df1e0a54c9558c6102e2ddc7bfad73526c842b95b307`.

OpenSpec progress remains `50/60`; task 7.7 remains first pending. Progress
stops before generating another read-only plan. That action and the later
single-use operator confirmation remain separate human gates; this completed
rollout authorizes neither.

The operator then separately authorized only generation of one new WS16 plan
from Atenea. The resulting real Android screen showed
`Objetivo: WorkSession 16`, `Sesión abierta: WorkSession 17` and one primary
`Confirmar WorkSession 16` action without clipping, overlap or an ambiguous
competing action. Read-only persistence confirmed exactly one unconsumed,
unexpired plan bound to canonical Atenea, `ax42-01` and remote session
`7151dce0-69ab-4614-86e4-f93f1af825e4`. WS16 remained blocked, WS17 remained
open and AgentRun 96 remained failed without retries.

After that exact target check, the operator gave a separate confirmation gate
and pressed the visible action once. The post-confirmation Android screen
showed `Capacidad liberada`, explicitly stated that no instruction was resent
and left `Reintentar tarea` as a future explicit decision. The action hierarchy
was visible in the first mobile viewport with no clipping, overlap or
horizontal overflow. The user-owned screenshots were inspected in place but
not copied into programme evidence, avoiding unnecessary retention of session
copy.

Atenea now persists WorkSession 16 as
`CLOSED/RELEASED/revision 10`, without an error and with exact receipt and
release timestamp. Its immutable operation is
`RELEASED/revision 10`, non-retryable, without error/category/next action and
with its receipt and release timestamp. The latest exact plan is consumed and
bound once. WorkSession 17 remains `OPEN/NOT_STARTED/revision 0` without a
receipt. AgentRun 96 remains `FAILED` with zero retry children; WS17 retains
one turn, one AgentRun, one attachment and one turn binding. Non-terminal
AgentRuns remain zero.

The first post-release ownership projection is exact: registration is disabled
with zero workspaces, admission is `released/released`, the active allocation
is absent and canonical `runtime-allocation-v1.retired.json` retains SHA-256
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`
with `0640 atenea-worker:atenea` identity and one link. WS16 and WS17 workspace
hashes remain
`6014606bb884c808a8f9603b9eb86aa7fc65c785fae59bd45a4caf468f0e065c`
and
`97b41b63e425eb483175b96bce875ac3190300cedb089b176aa2fdaedd515cbb`.
No direct SSH release, preflight repetition or private-journal authority was
used.

Matching transient Codex/Playwright units remain zero and rootless slots remain
`3/0/0/3`. All declared worker services are active with zero automatic
restarts; backup/check/health remain `success/0`; rootful Docker/containerd
remain inactive; and all three RAID arrays remain `[UU]`. Production, preview
and Beautips retain their exact image and container identities, return local
HTTP 200 and have zero restarts. `atenea-activation-code_default` remains
absent.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.7-real-confirmation-released-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.7-real-confirmation-released-20260807`.
Both copies verify 5/5 files; the SHA-256 of `SHA256SUMS` is
`549a5d5e55df91db1bd906b34b74925293925acf026b3b4daf1d6523a3f7c2d9`.

Task 7.7 is complete and OpenSpec progress advances to `51/60`; task 7.8 is
first pending. No idempotence repetition is claimed here. Task 7.8 must prove
the repeated exact receipt plus complete zero-residual and retained inventory
without reconstructing released ownership.

## Task 7.8 real RELEASED idempotence and retained-state proof

The operator authorized task 7.8 after its scope was limited to one controlled
repeat of WorkSession 16's already persisted exact release operation. The
complete request was reconstructed from persisted server state and reviewed
canonical constants, then sent exactly once from the production backend
container through its configured authenticated worker boundary with finite
timeouts. No client-selected path, endpoint, slot, port, service, label,
credential or resource was accepted. Authentication material was consumed
inside the request process and was neither printed nor retained.

The worker returned `RELEASED`, revision 6 and the exact existing receipt
`59987a1cad35992a0bf54b4b2fa3420f8daf83c4d0fb4cbeaef343457cdeed64`,
with zero removed resources, every release assertion true, every retention
assertion true and `valuesExposed=false`. An independent canonical
recalculation matched the worker and persisted receipt. WorkSession 16 and its
immutable operation remained `RELEASED/revision 10` with the same release
timestamp; persisted plan and lifecycle-event counts remained 8 and 10. The
repeat therefore added no mutation and did not reconstruct released ownership.

Registration remains disabled with zero workspaces, admission remains
`released/released`, the active allocation remains absent and the exact retired
allocation retains SHA-256
`af69156b9a6935cb11c96e0b7bdd73b950ec97959281a97b870bdad0c691a80f`.
WorkSession 16 and 17 workspace hashes, WorkSession 16 clean Git HEAD/tree, and
all 179 retained directories and 870 retained files were unchanged. WorkSession
17 remains `OPEN/NOT_STARTED/revision 0`; AgentRun 96 remains `FAILED` with zero
retry children, and its single turn, AgentRun, attachment and binding remain
present. No prompt, retry, Codex process or runtime was started.

Owned containers, networks, images, listeners and transient Codex/Playwright
units remain zero. Rootless slots remain `3/0/0/3`; the declared worker
services remain active without restarts; backup/check/health remain
`success/0`; all RAID arrays remain `[UU]`; and rootful Docker/containerd remain
inactive. Production, preview and Beautips retain their exact image/container
identities, zero restarts and local HTTP 200. The explicitly accepted absent
`atenea-activation-code_default` network was not recreated.

The worker/release suite passes 43/43. Focused backend verification passes
17/17 (2 unit and 15 integration tests) in a clean detached worktree against a
disposable PostgreSQL 16 instance. The standard development test compose stack
was not adopted because it named pre-existing containers; the isolated
equivalent avoided changing unrelated development resources. Its database,
worktree and logs were removed, the Atenea source branch remains clean, and no
test residue remains.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.8-real-release-idempotence-20260807`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.8-real-release-idempotence-20260807`.
The initial 5/5 payload seal was
`e865b89f4656b1810c299b4280c7f589f98e0d14ef8774b778755af9a5f407e1`.
The task 7.9 preflight found that its retention summary had transcribed the
unchanged Beautips image as `ff9d8e2c...` instead of the authoritative
`ff9d2a0a...`. Live state and all prior sealed rollout evidence retain the
second value; no production divergence or mutation occurred. Both evidence
copies preserve the original payload and add `CORRECTION.md`. The successor
6/6 payload seal is
`86ca45b8ce5f5c4ca3f8c50caf3cfaefd85633fdece2fafa59af7a324996041c`.

Task 7.8 is complete and OpenSpec progress advances to `52/60`; task 7.9 is
first pending. Task 7.9 must prepare only WorkSession 17 readiness and expose
the operator's explicit retry choice without sending a prompt, retrying
AgentRun 96, or starting Codex/runtime.

## Task 7.9 stopped — canonical source advanced after retained dispatch

The operator authorized task 7.9 only for a no-workload WorkSession 17
readiness ensure. Preflight proved WorkSession 17 clean and pinned to
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, with no registration, admission
or active allocation. AgentRun 96 remained terminal failed, pre-dispatch and
unretried with its exact turn, attachment and profile snapshot. The declared
Beautips WorkSession remained the only held admission in its unrelated
`slot4`; it was identified from the programme ledger and not touched.

Exactly one request was reconstructed from the eight persisted workspace
identity fields and sent through the configured authenticated worker boundary
with finite timeouts. Request SHA-256 is
`b9863be686ba0e90c2bbefda9d5fcd66712b6985d62b6301fc5826e4aba9d0ce`.
It contained no workload and accepted no client-selected command, endpoint,
path, slot, port, service, label, credential or resource.

The worker returned deterministic HTTP 403, which was not retried and did not
enter the worker-unavailable window. The single request refreshed the worker's
canonical mirror from retained `615e539d...` to current `main`
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`. The latter is one direct
descendant (`0/1` ahead/behind from the retained commit), tree
`46a36bf3b10c0f3556a024bb936a8c9103ccd64d`, with sanitized subject
`ops: retire obsolete Expo routes`. Because the worker compares the complete
request against refreshed canonical source before invoking its activation
mediator, the request failed closed on canonical ownership and created no
workspace readiness resources.

Post-checks prove WorkSession 16 remains exact `RELEASED/revision 10`;
WorkSession 17 remains `OPEN/NOT_STARTED/revision 0`; and AgentRun 96 remains
unchanged with zero retry children or recovery operations. Its retained counts
remain one turn, one run, one attachment and one binding. WorkSession 17
registration, admission and active allocation remain absent, its workspace
record hash and clean `615e539d...` worktree are unchanged, and temporary raw
request/response residue is zero.

Atenea and Beautips configuration hashes remain unchanged. Worker services are
active with zero restarts. Production, preview, Beautips and Caddy retain their
exact container/image identities, remain running with zero restarts, and
`atenea-activation-code_default` remains absent. No prompt, retry, Codex,
runtime, deployment, APK, preview action, routing change or Beautips mutation
occurred.

Sanitized evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.9-blocked-canonical-source-divergence-20260808`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.9-blocked-canonical-source-divergence-20260808`.
Both copies verify 5/5 payload files; the SHA-256 of `SHA256SUMS` is
`504c91c4c8371a99820a50131662d929f753033c121306f121ede6d2dc6426af`.

OpenSpec remains `52/60`; task 7.9 remains first pending. Do not repeat ensure,
rewrite AgentRun 96, move canonical `main`, or activate resources implicitly.
Continuation requires a separately reviewed and explicitly authorized design
decision that preserves the retained source snapshot, followed by a fresh
clean-state audit.

## Task 7.9 pre-rollout registry/source gate correction

The operator authorized the exact pre-task-7.9 rollout sealed by manifest
`b63db605b6f8dce1d24c1f11ed0d1e479a71c7ff3205ac2f5ed95aa6a158d73d`.
The mandatory entry audit found that AX42's exact disabled, empty canonical
Atenea registry still recorded `615e539d1f2622a4ac2568ba7697b876d49ae33e`,
while its fixed mirror had advanced one direct descendant to
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`. The authorized worker installer
would reject this state before stopping the service, while the routing
installer could advance independently. The rollout therefore stopped before
any fast-forward, transfer, installer, restart, configuration, image load,
deployment, APK publication or APK installation rather than creating a partial
successor.

The stopped preflight preserved WorkSession 16 at `CLOSED/RELEASED/revision
10`, WorkSession 17 at `OPEN/NOT_STARTED/revision 0`, AgentRun 96 at terminal
`FAILED` without retries, the exact empty disabled registry, absent WS16/WS17
active admission/allocation and rootless inventory `3/0/0/3`. Worker services,
backup/check/health, all three `[UU]` RAID arrays, production, preview,
Beautips and Caddy remained healthy and unchanged. The two fresh-session
production environment values and `atenea-activation-code_default` remained
absent.

Sanitized stopped-rollout evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.9-rollout-blocked-registry-source-divergence-20260808`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.9-rollout-blocked-registry-source-divergence-20260808`.
Both copies verify 4/4 payloads; the SHA-256 of `SHA256SUMS` is
`98bec4113a8f637c9aa487b9f4716472dfdf7ddb738509ca76ef681ea2864e40`.

The reviewed correction now recognizes only the complete modern root-owned
canonical Atenea registry with zero workspaces, selection/execution both false
and a retained commit that is an exact ancestor of the fixed mirror ref. Its
preflight binds the registry digest plus retained and canonical commits;
finalization rechecks all three and writes only the disabled empty successor.
Enabled, non-empty, legacy-incomplete, unrelated, foreign, ambiguous and
post-preflight-changed fixtures reject. Repetition retains byte identity and
does not rewrite the canonical disabled registry. The installer sandbox,
routing installer, authenticated worker 88/88 and release mediator 45/45 suites
pass, and OpenSpec strict validation remains valid.

OpenSpec remains `52/60`; task 7.9 remains first pending. The correction must
be committed, sealed into a new exact programme/AX42 candidate and pass a fresh
clean-state audit. Production, AX42 installation, configuration, APK and the
later `START_FRESH_SESSION` action remain separate authorization gates.

## Task 7.9 routing predecessor correction after stopped rollout

The operator next authorized the pre-task-7.9 rollout sealed by manifest
`c36be8cd6da28565be42803a30b2273d33975e4f7d312c7a6e1f8e239e466069`.
The programme checkout advanced by exact fast-forward to
`55cd3ca7104d86fda345077c8ff122fee8a65174`. The AX42 routing installer then
rejected before mutation because the exact live release mediator
`baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0`
was newer than the predecessor accepted by that candidate. Therefore no
worker installation, service restart, configuration activation, backend image
load/deploy, APK publication/installation or later WorkSession action ran.

Post-rejection verification preserved the live worker at
`4d102a4b02e7e0389d5bbae6e8fc0a45275101dda5b4e7577a7fa71555ef6749`,
release mediator at
`baccb3c7c7053e5d09eb05148f1c2e368faf90d5e2706a537ac3473429dfada0`,
worker service at
`21064a91421914588bab464022c55599fe78a9ee4eba25e9c1b9164068eb5f18`,
four-rule routing sudoers at
`45f07abab8b9b2af33bf98e6aa38ac937c6fe249fad6845d6a7ab66fad2791bf`,
disabled empty registry at
`839445b05b1006573646f0f6104ed01dab2cf15de84a226e67863a94d22c31c0` /
`615e539d1f2622a4ac2568ba7697b876d49ae33e`, and fixed mirror at
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5` with the retained commit as a
direct ancestor. Worker service remained active and enabled without restarts;
rootless slots remained `3/0/0/3`; rootful daemons remained inactive; all
three RAID arrays remained `[UU]`; backup and health units remained successful.
Production, preview, Beautips and Caddy were unchanged and healthy, both fresh-
session environment values remained absent, and
`atenea-activation-code_default` remained absent.

Sanitized stopped-rollout evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.9-registry-transition-rollout-20260808`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.9-registry-transition-rollout-20260808`.
Both copies verify and the SHA-256 of `SHA256SUMS` is
`7e1ea7d1a49d8e60277fac15de75c7fb0d1a660acc624e7702e48ab10c47435b`.

The correction accepts only that complete live four-rule generation. Apply
verifies and retains its exact root-owned mediator beneath a fixed private
predecessor root before installing the successor mediator and the fifth fixed
`--diagnose-unactivated` rule. Rollback verifies the retained file before
changing authority, then restores the four-rule sudoers generation and the
same mediator bytes. Repetition is idempotent. Missing, changed, symlinked,
partial or foreign retained state rejects before the installed bundle changes;
the operation never reconstructs registration, admission, allocation or other
released ownership.

The focused routing installer suite covers exact upgrade, byte-for-byte
retention, exact rollback, repeated rollback and foreign predecessor rejection.
Together with it, the worker installer sandbox passes, the authenticated worker
suite passes 88/88 and the release mediator suite passes 45/45. No UI contract
or rendered surface changed in this correction. OpenSpec remains `52/60` and
task 7.9 remains first pending until a separately authorized exact rollout and
its post-deployment readiness evidence complete.

## Task 7.9 completed — durable current-code successor for WorkSession 17

The complete readiness path retained AgentRun 96 as terminal `FAILED` without
retry and diagnosed its pinned commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e` as an exact ancestor of current
canonical `main` `e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`. The worker
installer now advances only the exact complete root-owned disabled empty
Atenea registry across that ancestor relationship and rejects enabled,
non-empty, incomplete, unrelated, ambiguous or post-preflight-changed state
before service stop. The routing installer accepts only the exact live
four-rule release-preflight generation, retains its static mediator and
restores both exact predecessor bytes and authority on rollback; foreign or
changed retained state rejects before mutation. The focused installer suites,
authenticated worker 88/88 suite and release mediator 45/45 suite pass.

The backend, web and Android implementation at Atenea commit
`918f3b2edbe87ca98dbbdefbb6947c2b2a4e0f80`, tree
`7c79c500d08321d5fd23178b98d0f658d7283ea4`, adds the disabled-by-default,
administrator-only `START_FRESH_SESSION` journal and exposes an incomplete
closed source from Projects without turning navigation into mutation. Focused
backend tests pass 12/12, the complete isolated PostgreSQL 16 suite passes
713/713 through V66, the complete remote-close Playwright suite passes 21/21,
focused web checks pass at `1440x900` and `390x844`, Android unit tests and
instrumentation compilation pass, and the signed `0.5.102` / versionCode 135
APK retains SHA-256
`6dc6dc1d49ee08063ecdcdb3d221acd6eb81d414a2a35557826c6e94966313d8`.

The first authorized backend candidate was correctly rejected by the real
deployed-assets gate because its embedded JAR was byte-identical to the
predecessor. Production was restored exactly before any operator action. The
clean corrected JAR `002bfc248d...` and non-privileged read-only image
`sha256:53d4a7f4aac19e64eac7528aa4310132ae2f872079916720af82a5f15cf9f0ad`
then passed isolated boot, V66 and static-asset checks before a separate exact
authorization deployed it. Production returned HTTP 200 with zero restarts;
preview, Beautips, Caddy, routing, AX42 and all excluded ownership remained
unchanged. Actual production assets passed the separated persistence, DOM and
visual gates, and the real Android screen clearly named WorkSession 17 and the
single recovery path without clipping or overflow.

The immutable operation
`595a2268-6447-48e8-92f6-9ae602979ceb` remained `SOURCE_RELEASED` with no
result through the original lost response and multiple backend replacements
and restarts. The operator resumed it only through Atenea. Project navigation
performed zero POST and left zero successors; the separately visible source
action then advanced the same operation monotonically to `COMPLETED` and
created exactly one result, WorkSession 19. WorkSession 17 remains
`CLOSED/RELEASED/revision 6` with its exact receipt. WorkSession 19 is `OPEN`
with zero turns, zero AgentRuns, zero attachments and zero bindings. AgentRun
96 remains `FAILED`, has no remote execution or retry child, and all source
retained counts remain `1/1/1/1` without reading retained content.

WorkSession 19 records only its deterministic future remote routing identity;
its close state is `NOT_STARTED`. Its exact workspace, artifact, cache,
admission, release and attachment paths are absent, the disabled empty worker
registry contains no owner, and all four rootless slots report zero matching
containers, networks and volumes. Global slot counts remain `3/0/0/3`,
admission remains `1/4` normal and `0/2` heavy, backups and health remain
`success/0`, all RAID arrays remain `[UU]`, and excluded allocation/admission
hashes remain `bd45cac9...` / `5ced8132...`.

Sanitized completion evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.9-start-fresh-session-completed-20260810`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.9-start-fresh-session-completed-20260810`.
Both copies verify; the SHA-256 of `SHA256SUMS` is
`72ee3fa3f8faff1f57e9ddbc7591669d6b89454c2482b46a71f2c0153ae266f6`.
The corrected rollout and real Android visual packages also verify at
`a94746918a1b04a193e4f7641b98c619cd8cb4aebe9a47913f3f7d1c28695ed2`
and `2b6e2002363698da2fcce5da7d1a4a1a4bfdea7de6fd200e615fc50b32a25493`.

OpenSpec progress is now `53/60`; task 7.10 is the exact first pending task.

## Task 7.10 completed — retained systems healthy after the real canary

The final section-7 audit was read-only. Production remains on exact image
`sha256:53d4a7f4aac19e64eac7528aa4310132ae2f872079916720af82a5f15cf9f0ad`,
preview remains on
`sha256:b097910ae585b5e3b9abe247cf38ca42da01cc742b09b2a2a714eb82cff33941`,
Beautips remains on
`sha256:ff9d2a0ab2620f0ea198daa029a6c92e9063a5b7369c9c0b3d49e3fab58385f3`
and Caddy remains on
`sha256:612f0ff47f33888e3b61a8db399ff2dc22c2cefb8cb652d86a619e52eabcd51f`.
All four containers are running with zero restarts. Production, preview and
Beautips return local HTTP 200; the unauthenticated public production API
remains HTTP 401. Production Compose remains exact at
`ec3e3e222d694016a16d422b328d47896ebc14bfb5285989cded9d0cb1e42ca2`,
Caddy validates at `f58e7b59...`, the retired Expo routes remain unserved and
`atenea-activation-code_default` remains absent.

Production retains only the established Atenea lifecycle policy: release,
reconciliation and current-code fresh-session gates are true, and both
project allowlists are exactly `atenea`. Preview and Beautips contain none of
those five values. No environment dump or secret was read. The control-host
network projection remains the exact sealed baseline `99bd956a...`; the
retained volume projection is `42d4a0c5...`, with zero volumes created on or
after the real operation date and no retained volume inspected for content or
changed.

Flyway remains successful through V66. The durable operation `595a2268...`
remains a single `COMPLETED` row with one idempotency key and WorkSession 19 as
its one result. WorkSession 17 remains `CLOSED/RELEASED/revision 6`,
WorkSession 19 remains `OPEN/NOT_STARTED` with exact content counts `0/0/0/0`,
and AgentRun 96 remains terminal `FAILED` without remote execution or retry.
Source retention remains `1/1/1/1` without reading content. Non-terminal
AgentRuns, active AgentRun leases, active preview leases, non-terminal legacy
close operations and non-terminal fresh-session operations are all zero.
Unrelated WorkSessions 3 and 4 remain open with their exact aggregate
projections; active application registrations remain one `0.5.102` and one
unrelated `0.5.98`, without selecting device identities or push tokens.

AX42's AgentRun worker, preview, attachment, image-root and four fixed proxy
services remain active with zero restarts. Backup, backup-check and worker
health remain `success/0`; their timers remain enabled and active. Failed
units are zero, rootful Docker/containerd remain inactive, Tailscale and UFW
remain active, and all three RAID arrays remain `[UU]` and pass explicit
`mdadm --detail --test`. Rootless slot container counts remain `3/0/0/3`,
admission remains ready at `1/4` normal and `0/2` heavy, and the sanitized TCP
listener projection is sealed at `cd5cdb9e...`.

The installed worker, release mediator, installer, service and five-rule
routing boundary retain exact reviewed hashes `1d4af8ea...`, `095e0db0...`,
`7ad4978d...`, `9d5e7b75...` and `a711394a...`; both sudoers boundaries
validate. The canonical registry remains disabled, empty and pinned to
`e4287dbc...`. The excluded allocation `c20f3cde...` and its admission record
remain byte-exact at `bd45cac9...` and `5ced8132...` and were not adopted,
repaired, retired or changed.

The exact task-7.9 completion, corrected rollout and Android visual evidence
packages verify both locally and remotely. Task-7.10 evidence is retained
locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-7.10-final-health-20260810`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-7.10-final-health-20260810`.
Both copies verify 6/6 payloads; the SHA-256 of `SHA256SUMS` is
`7318caa96e12b85153988714c2a9bc14ab94e42af897f0d9266eeb004781e017`.

No user-visible source changed during task 7.10, so the separated real
persistence, DOM and visual acceptance remains the sealed task-7.9 result.
No prompt, retry, Codex/runtime start, lifecycle action, deployment,
configuration, APK, preview, Beautips, other-project or foreign-resource
mutation occurred.

Section 7 is complete and OpenSpec progress advances to `54/60`; task 8.1 is
the exact first pending task. Task 8.1 would disable the Atenea and global
lifecycle gates and deploy retained application/worker predecessors. That is
a new production/AX42 rollback mutation and must not begin without a separate
exact sealed manifest and explicit operator authorization.

## Task 8.1 completed — disable-first V63-compatible rollback

The operator authorized only sealed manifest
`cb5b6d3deb9856f36561f9656f22dab749160c5f9c4a6bce96278ff6513c3843`.
Immediately before mutation, the programme and application repositories were
clean and aligned with their declared upstreams, production remained on the
exact V66 successor, Flyway reported `66:true`, lifecycle activity was
`0:0:0:0:0`, AX42 retained its reviewed successor generation, and the
excluded allocation/admission hashes remained exact.

The rollout first emptied only the canonical Atenea remote-close and
fresh-session allowlists, recreated only `atenea-backend-prod`, and re-proved
quietness and retained state. It then disabled the release, reconciliation and
fresh-session global prerequisites, recreated only the same service and
re-proved the same gates. Only after both layers were disabled did it deploy
the V66-aware V63-behaviour image
`sha256:877a401ff8c4e8cda3a941868c1daf18bf5c12a2db1e5f00c9faf080fa10c5ee`.
Final production Compose is
`6625e9b36b6917803ce21bc27186fbe8f6cfaad08c585dc25524743265c64498`;
all five lifecycle values are false or empty, production returns HTTP 200 and
has zero restarts. No down-migration ran and schema V66 remains intact.

On AX42, bundle
`308af80ec0c75d6605c8b6a87a6f22dd87dee891a976ab8d6951c6e35e739eb1`
verified as 33 fixed-prefix members with no symlink or traversal. The guarded
installer accepted only the complete reviewed successor and installed the
exact original predecessor: worker `b574fa2a...`, activation mediator
`5ef544c4...`, installer `d7c103ea...`, unit `0368f876...` and one-rule
sudoers `208730e9...`; the release mediator is absent. A second application
returned `already-complete`. Registry `ccf236bb...`, release journal
`128ec850...`, retained static tree `ffafb501...` and excluded ownership
`bd45cac9...` / `5ced8132...` remained exact. Only the fixed task-owned AX42
staging directory was deleted after verification.

WorkSessions 16, 17 and 19 remain respectively
`CLOSED/RELEASED/10`, `CLOSED/RELEASED/6` and `OPEN/NOT_STARTED/0`.
WorkSession 19 remains empty at `0/0/0`, AgentRun 96 remains
`FAILED/no-parent/0`, and the lifecycle projection remains `0:0:0:0:0`.
No prompt, retry, Codex or runtime started. The four worker services are active
with zero automatic restarts, rootless slots remain `3/0/0/3`, admission
remains `1/4` normal and `0/2` heavy, backup/check/health remain successful,
all RAID arrays remain `[UU]`, and rootful daemons remain inactive.

Preview stays on `sha256:b097910a...`, Beautips on `sha256:ff9d2a0a...` and
Caddy on `sha256:612f0ff4...`, all running with zero restarts; production,
preview and Beautips return local HTTP 200 and the public unauthenticated API
remains HTTP 401. The retired activation network remains absent. No
task-labelled container, network or volume, browser process, SSH tunnel or
AX42 staging remains. Three mode-0600 `.task81-plan-stage*` candidate-planning
files predated the rollout and were retained unchanged because the exact
authorization permits deletion only of the AX42 staging directory.

Persistence, rendered DOM and visual usability were checked separately. The
database proof is the retained projection above. Actual production assets,
loaded through a bounded local tunnel with wholly synthetic authentication and
API data, rendered Atenea WorkSession 19 as `OPEN` with `Abrir sesión` visible
in the first viewport at `1440x900` and `390x844`. Both viewports had zero POST,
visible error, horizontal overflow, clipping or overlap. The browser and
tunnel exited, and the retained screenshots contain no real conversation or
attachment data.

Sanitized rollout evidence is retained locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.1-rollback-rollout-20260810`,
on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.1-rollback-rollout-20260810`,
and the AX42 execution/archive remains under the same protected run path on
the worker. The evidence checksum is sealed in that package.

OpenSpec progress is now `55/60`; task 8.2 is the exact first pending task and
has not begun.

## Task 8.2 completed — expanded records remain readable and immutable

This task was a read-only post-rollback audit. Preflight reverified the clean,
published programme/app/rollback branches, exact task-8.1 evidence, disabled
production gates, V66 schema, V63-behaviour application and original AX42
static predecessor before any evidence directory was created. No deployment,
service restart, lifecycle action or runtime request occurred.

The live V64–V66 schema remains fully readable: all 20 selected expansion
columns/table fields, seven selected constraints, three selected indexes and
the V66 monotonic trigger function are present. WorkSession 16's eight legacy
plans are readable; five are consumed, all eight satisfy the nullable
consumption triple and every operation reference is valid. Its single durable
operation is still `RELEASED`. The single V65 fresh-session operation remains
`COMPLETED`, links exactly WorkSession 17, AgentRun 96 and result WorkSession
19, satisfies fingerprint, commit and timestamp invariants, and is bound once
to its result.

Independent before/after safe fingerprints are byte-identical for the plan
set `aeb511c5...`, fresh operation `88ed7809...`, WorkSessions 16/17/19
`22d33536...` / `8d8f470d...` / `e37a692d...` and AgentRun 96
`38483d2a...`. WorkSession 16 remains `CLOSED/RELEASED/revision 10`;
WorkSession 17 remains `CLOSED/RELEASED/revision 6`; WorkSession 19 remains
`OPEN/NOT_STARTED/revision 0`. AgentRun 96 remains terminal `FAILED`, has no
retry parent/children or remote execution, and retains its complete profile
and attachment metadata. WorkSession 17 retains exactly one turn, one run, one
attachment and one binding without reading their content.

WorkSession 16/17 workspace records remain exact at `6014606b...` and
`97b41b63...`; both worktrees remain clean at commit `615e539d...`, tree
`3b8a5517...`. WorkSession 16's active allocation remains absent while its
released admission and retired allocation remain exact at `eddd53a8...` and
`af69156b...`. WorkSession 17 has no active allocation or admission. The
excluded allocation/admission remain byte-exact at `bd45cac9...` /
`5ced8132...` and were not adopted or changed.

Production stays on `sha256:877a401f...`, preview on
`sha256:b097910a...`, Beautips on `sha256:ff9d2a0a...` and Caddy on
`sha256:612f0ff4...`; all are running with zero restarts. Production, preview
and Beautips return local HTTP 200, the unauthenticated public API remains HTTP
401, Compose remains `6625e9b3...`, and all five lifecycle values remain
false/empty. Unrelated WorkSessions 3 and 4 retain their exact aggregate
projections, lifecycle activity remains `0:0:0:0:0`, and the activation
network remains absent.

AX42 retains the original static predecessor and disabled empty registry
`ccf236bb...` pinned to `e4287dbc...`; release mediator remains absent, and
release journal/retained-static fingerprints are unchanged. All declared
worker, attachment, preview, image-root and proxy services remain active with
zero automatic restarts. Rootless container counts remain `3/0/0/3`, and all
container/network/volume inventory fingerprints are identical before/after.
Backup/check/health remain `success/0`, all three RAID arrays remain `[UU]`
and pass `mdadm --detail --test`, rootful Docker/containerd remain inactive,
Tailscale/UFW remain active and failed units remain zero.

The first audit SELECT used a nonexistent historical binding table name and
was rejected before its remaining reads. No data changed. The rejected read
was retained transparently, the catalogue identified
`session_turn_attachment`, and the complete corrected audit plus independent
post-audit fingerprints passed. No prompt, response, attachment content,
credential, cookie, screenshot, Codex internal history or environment dump was
read or retained.

No UI source or deployed asset changed, so the sealed task-8.1 Playwright
acceptance remains applicable and no duplicate visual run was required.
Task-labelled containers, networks, volumes and post-audit processes are zero;
the task-8.1 staging remains absent.

Sanitized evidence verifies locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.2-expanded-record-readability-20260810`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.2-expanded-record-readability-20260810`.
The SHA-256 of `SHA256SUMS` is
`6bd8243f5c90d11887fb433557b9ba7f0d5886325e57565ee672e3dbd89eb3d1`.

OpenSpec progress is now `56/60`; task 8.3 is the exact first pending task and
has not begun. Restoring the successor and re-enabling canonical Atenea are new
production/AX42 mutations and require a separately sealed rollout and explicit
operator authorization.

## Task 8.3 completed — reviewed successor restored and exact receipt repeated

The operator explicitly authorized sealed manifest `f7f63944...` for the
reviewed AX42/production successor, canonical Atenea-only gates and one exact
repeat of WorkSession 16's already `RELEASED` operation. Preflight first
reverified the published programme, Atenea and rollback branches; exact
task-8.2 rollback state; V66; lifecycle quiescence; retained WorkSessions/Git;
worker ownership; excluded allocation/admission; services; rootless slots;
backups; RAID; preview; Beautips and routing. No divergence was found.

The first orchestration attempt failed closed before service stop or installed
mutation because unprivileged archive extraction could not retain the guarded
bundle's required `root:root` payload ownership. Automatic rollback confirmed
the already-disabled production generation. Independent image/file timestamps,
hashes and service state proved that neither production nor AX42 had advanced,
and staging/process residue was zero. The additive correction changed only the
staging extraction authority to fixed `sudo -n tar`; manifest, bundle, image,
operations, target identities, gates, timeouts, rollback and exclusions stayed
unchanged. Its staging-only guarded preflight passed before the rollout was
resumed. The original candidate seal was `39ed6cf8...`; its additive corrected
seal is `fe99bf2ecffec3574b5181783ae234c53d881e497edfb900cf95f50013305378`.

The guarded AX42 installer then advanced the exact predecessor to the exact
successor and a repeated application returned `already-complete`. Installed
hashes are worker `1d4af8ea...`, activation mediator `5ef544c4...`, release
mediator `095e0db0...`, installer `7ad4978d...`, unit `9d5e7b75...` and
sudoers `a711394a...`. Registry remained disabled/disabled/empty at
`ccf236bb...`; release journal and retained static fingerprints were unchanged.
Only the AgentRun worker was stopped/started, and generated staging was removed.

Production advanced in the fail-closed order successor-with-gates-disabled
`e1f8dfb7...`, global-prerequisites-with-empty-allowlists `a7a52c56...`, then
canonical-Atenea-only `ec3e3e22...`. Final production image is exact
`sha256:53d4a7f4aac19e64eac7528aa4310132ae2f872079916720af82a5f15cf9f0ad`;
release, reconciliation and fresh-session globals are true, while both
allowlists contain exactly `atenea`. Only `atenea-backend-prod` was recreated
at each stage; it is healthy with zero automatic restarts.

Exactly one repeat of WorkSession 16 operation `5482cb8b...` ran from inside
the production backend through its configured authenticated fixed worker
boundary. It returned `RELEASED/revision 6`, request fingerprint `d8d92e5b...`,
the exact durable receipt
`59987a1cad35992a0bf54b4b2fa3420f8daf83c4d0fb4cbeaef343457cdeed64`,
zero removed resources, all four released assertions, all ten retained
assertions and `valuesExposed=false`. The complete safe durable projection was
byte-identical before/after at `437b3726...`: WorkSession/operation remain
revision 10 with the original timestamp, 8 plans, 5 consumed plans and 10
events. No ownership was reconstructed.

WorkSession 16/17 workspace records remain `6014606b...` / `97b41b63...` and
their worktrees remain clean at `615e539d...`, tree `3b8a5517...`.
WorkSession 16 active allocation remains absent, released admission and retired
allocation remain `eddd53a8...` / `af69156b...`; WorkSession 17 admission and
active allocation remain absent. The excluded allocation/admission remain
byte-exact at `bd45cac9...` / `5ced8132...` and were not adopted or changed.

WorkSessions 16, 17 and 19 remain respectively
`CLOSED/RELEASED/10`, `CLOSED/RELEASED/6` and `OPEN/NOT_STARTED/0`.
WorkSession 17 retains one turn/run/attachment/binding without content reads;
WorkSession 19 remains empty. AgentRun 96 remains `FAILED`, unparented,
unretried, without remote execution and with its complete profile. Lifecycle
activity remains `0:0:0:0:0`; unrelated WorkSessions 3/4 remain exact.

Production, preview and Beautips return local HTTP 200 and retain exact images
`53d4a7f4...`, `b097910a...` and `ff9d2a0a...`; Caddy remains `612f0ff4...`,
validates and keeps public root/API protected by HTTP 401. Worker services and
all four proxies/sockets are active, rootless slots remain `3/0/0/3`,
backup/check/health remain `success/0`, RAID is `3/3 [UU]`, rootful daemons
remain inactive, and the activation network remains absent. Task-labelled
containers/networks/volumes and AX42 staging are zero.

Persistence, DOM and visual usability were verified separately. Real restored
production assets were loaded through a bounded local tunnel with wholly
synthetic authentication/data and every POST fail-closed. At `1440x900` and
`390x844`, Atenea, `OPEN`, session `#19`, the complete long current-code message
and enabled `Abrir sesión` were visible in the first viewport with zero error,
POST, clipping, overlap or horizontal overflow. Sanitized captures were
inspected; browser and tunnel residue are zero. An initial public-origin probe
stopped at expected Basic Auth 401 before loading assets and read no credential.

Sanitized rollout evidence verifies locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.3-successor-rollout-20260811`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.3-successor-rollout-20260811`.
The SHA-256 of its `SHA256SUMS` is
`78a1231ae74cbeafe40899b9f49eb9a1fee67a106ee4c894afd2911b6099f478`.

OpenSpec progress is now `57/60`; task 8.4 is the exact first pending task and
has not begun.

## Task 8.4 completed — final application/worker smoke and fingerprints

Task 8.4 completed without changing application, worker or deployed source.
The accepted Atenea commit `918f3b2e...` passed all 713 backend tests against
an isolated PostgreSQL 16 fixture with all 66 migrations successful. Its web
build compiled 1,583 modules and the complete real Chromium suite passed
38/38 with one worker, zero retries and finite timeouts. The exact programme
commit `3a131147...` passed all 33 sorted top-level worker entrypoints,
including release, ownership, installer rollback, session operations,
runtime, slots, backup, attachments, preview, Beautips isolation and browser
cleanup.

Early backend harness diagnostics exposed only the fixture's historical
hard-coded `/workspace/repos` boundary and the separate application
workspace-root validator. The unchanged accepted run used a task-owned mounted
`/workspace`, a private labelled network and PostgreSQL fixture. All containers,
networks, detached worktrees, dependencies, results, logs, browser processes,
tunnels, wrappers and visual scratch state were removed. No production or
AX42 service was restarted.

Production, preview, Beautips and Caddy remain on exact images `53d4a7f4...`,
`b097910a...`, `ff9d2a0a...` and `612f0ff4...`, running with zero restarts.
The three application health checks return HTTP 200, public production remains
HTTP 401 without authentication and Caddy validation passes. Production
Compose remains `ec3e3e22...`; release, reconciliation and fresh-session
globals are true and both allowlists contain exactly `atenea`. Preview and
Beautips retain none of this enablement. The activation network remains absent
and task-labelled control resources are `0/0/0`.

WorkSessions 16, 17 and 19 remain `CLOSED/RELEASED/10`,
`CLOSED/RELEASED/6` and `OPEN/NOT_STARTED/0`. WorkSession 17 retains one
turn/run/attachment/binding without content reads, WorkSession 19 remains
empty and AgentRun 96 remains `FAILED`, unparented, without children or remote
execution. The lifecycle projection is `0:0:0:0:0`; WorkSession 16's exact
operation remains `RELEASED/revision 10` with receipt `59987a1c...`; unrelated
WorkSessions 3/4 remain exact.

AX42 retains the exact successor hashes, disabled empty registry pinned to
`e4287dbc...`, clean retained WorkSession 16/17 worktrees at `615e539d...`,
released/retired WorkSession 16 ownership and absent WorkSession 17 active
ownership. The excluded allocation/admission remain byte-exact at
`bd45cac9...` / `5ced8132...` and untouched. Worker, preview, attachment,
image and proxy boundaries are active with zero restarts; slots remain
`3/0/0/3`; backup/check/health remain `success/0`; RAID is `3/3 [UU]` with
all explicit tests passing; rootful daemons remain inactive.

Eighteen final wholly synthetic screenshots cover desktop `1440x900` and
mobile `390x844`. DOM assertions and inspected images prove clear state and
next action, first-viewport action visibility, long-message wrapping, role
handling and zero overflow/clipping. No UI source or deployed asset changed.

The live npm advisory service newly reports moderate `dompurify`
`GHSA-55q2-fjhq-7xh7` and high `nanoid` `GHSA-2v37-7h3g-55p8`, with fixes
available. This external-registry observation postdates the separately sealed
task 6.2 zero-vulnerability audit and is outside task 8.4's application/worker
smoke. No dependency, lockfile, image or deployment was changed; a separately
scoped security-maintenance change must refresh and requalify the full chain.

Sanitized evidence verifies locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.4-final-smoke-20260811`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.4-final-smoke-20260811`.
The SHA-256 of its `SHA256SUMS` is
`256b8a1d8c48e715b34eca006bbf14df059fa7516f6605d00a916838dbf23255`.

OpenSpec progress is now `58/60`; task 8.5 is the exact first pending task and
has not begun.

## Task 8.5 completed — evidence ledger and OpenSpec archive

Task 8.5 verified every pre-existing `SHA256SUMS` in place: 56 local, 58 on
the control host and 53 on AX42, for 167/167 verified host copies. The sealed
closure evidence adds one local and one control-host manifest; the final
verification is therefore 57/57 local, 59/59 control and 53/53 AX42, or
169/169 host copies. Stable sorted manifest-ledger aggregates are respectively
`c7a7560ca3d697997d92fb39e9bcf71b051b79afd16b2f13f1dad97fa3fc1e39`,
`8f27572b7bff689b3a3fbec96216be7396b02b90073f24472b4eadea02144573`
and `1b2acbfed5500a8f5746b87678cfb30efd73986b37be2bffa8a51822b69c8164`.

Decisions D-100 through D-104 are accepted with their migration, protocol,
full-suite, adversarial, crash-resume, browser and live WorkSession 16 evidence.
D-105 remains a separately scoped security-maintenance follow-up and does not
alter the sealed close-lifecycle implementation. No dependency, lockfile,
image or deployment changed during archive closure.

OpenSpec applied eleven additive requirements to the five declared canonical
specifications and archived the change as
`2026-08-11-complete-remote-worksession-close-lifecycle`. Global strict
validation passes all 12 canonical specifications with zero failures and
`openspec list` reports no active changes. The archived `tasks.md` marks only
task 8.5 newly complete and preserves task 8.6 unchecked.

Production, preview, Beautips and Caddy retain their exact accepted images,
zero restarts and healthy state. AX42 services and proxy sockets are active,
slots remain `3/0/0/3`, backup/check/health remain `success/0`, RAID remains
`3/3 [UU]`, rootful daemons remain inactive, task resources remain zero and
the accepted-absent activation network remains absent. WorkSession 16/17
active allocations remain absent; no retained or foreign resource was read,
adopted, repaired, removed or changed.

The declared Atenea implementation and rollback branches remain clean and
already published at `918f3b2e...` and `f44ec24...`; canonical Atenea and
Beautips remain clean at `e4287dbc...` and `9e122bf0...`. Only the programme
branch contains this archive closure and is published by its closing commit,
without force, history rewriting or changes to other refs.

Sanitized closure evidence verifies locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.5-archive-20260811`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.5-archive-20260811`.
The SHA-256 of its six-file `SHA256SUMS` is
`476800d833baae7a1ee4d03dba5a109364fbf4eede1b8c111d2c4281cd460c3d`.

OpenSpec progress is now `59/60`. The exact resume point is archived task 8.6:
report the preserved explicit operator choice without retrying AgentRun 96,
replaying a prompt, starting Codex/runtime or beginning unrelated work.

## Task 8.6 completed — preserved operator choice

The final read-only comparison confirms that AgentRun 96 is terminal `FAILED`
and pinned to repository commit
`615e539d1f2622a4ac2568ba7697b876d49ae33e`. That commit remains an ancestor
of, but is not equal to, current canonical Atenea `main`
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`. The contract permits retry only
while the pinned commit is still canonical, so retry is not an eligible choice.

The operator's preserved choice is therefore to abandon replay of that failed
work while retaining AgentRun 96 as immutable audit history, and to continue
future current-code work from the already-created empty WorkSession 19. This
does not delete AgentRun 96 or any turn, attachment, log, artifact, backup,
volume or source state. It does not copy any old prompt into WorkSession 19.

A production transaction declared `READ ONLY` and ended with `ROLLBACK`.
AgentRun 96 remains in WorkSession 17 with no remote execution, no retry parent
and zero retry children. WorkSession 17 remains `CLOSED/RELEASED` with retained
metadata counts `1/1/1/1`; no retained content was read. WorkSession 19 remains
`OPEN/NOT_STARTED` with counts `0/0/0/0`. No prompt was sent and no Codex,
runtime, worker ownership or unrelated operation began.

Sanitized report evidence verifies locally beneath
`/home/jose/codex-evidence/complete-remote-worksession-close-lifecycle/task-8.6-operator-choice-20260811`
and on the control host beneath
`/srv/atenea/artifacts/program/remote-codex-platform/complete-remote-worksession-close-lifecycle/runs/task-8.6-operator-choice-20260811`.
The SHA-256 of its three-file `SHA256SUMS` is
`a599645791689560539e56c1c85353edd611271e32f4f066c67886d16c567b25`.

The archived change is complete at `60/60`. There is no remaining task or
automatic action in this change; normal use of WorkSession 19 requires a new,
explicit operator prompt outside this close-lifecycle scope.

## Android WorkSession image attachments — candidate prepared

The separate OpenSpec change `add-android-worksession-image-attachments`
closes the native Android parity gap discovered after the lifecycle rollout.
The backend V62 contract was already complete and enabled only for canonical
`atenea`; Android had no capability query, image picker, multipart upload or
attachment-aware turn request.

Implementation commit `39d7d7379423b3da36ce89cc3329cbc6f87f00b3`
adds server-authoritative ready/blocked state, PNG/JPEG/WebP selection through
Android's system provider, bounded reads without storage permission,
sequential idempotent uploads, stable uncertain-turn replay, exact ordered
attachment binding and authenticated explicit-only historical viewing. The
composer keeps Send as its sole primary action and exposes concise selection,
upload, failure, retry and blocked next-action state.

From clean committed source, 56 API/core unit tests pass, affected-module lint
passes, both APKs assemble and 10 Android 35 instrumented tests pass. Five
synthetic 390x844 renders independently prove selected, blocked, uploading,
retryable long-name error and historical states without clipping or overflow.
The repository-wide lint command also ran; its only failures are unchanged
pre-existing notification/style/voice-runtime findings outside this OpenSpec.
The backend harness was not allowed to replace a labelled pre-existing local
Compose database container; it remained untouched, and no backend source was
changed.

The uninstalled and unpublished candidate is Atenea `0.5.103`, versionCode
`136`, SHA-256
`507ec30d5a99e017625ade793354578ef6626e2a9eee354b02ad358d6340d95b`,
at exact implementation tree
`bc3d9c42c43b311b1eb88681088091998ec8c247`. Production, preview, Beautips
and Caddy retain exact accepted images with zero restarts and HTTP 200; AX42
services, backups, timers, slots `3/0/0/3`, admission `1/4` and `0/2`, empty
disabled registry and RAID `[UU]` remain unchanged. No prompt, real attachment,
runtime, deployment, APK publication/installation or foreign-resource action
occurred.

Sanitized evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-4-candidate`;
the SHA-256 of its `SHA256SUMS` is
`ac8b1e7aaa854db39742013e69253dab635dc2f367fe0f0ab099b93a992bd892`.
OpenSpec progress is `24/28`; task 5.1 is the exact first pending task and
requires separate authorization for the exact commit and APK hash before any
publication or installation.

## Android attachment rollout gate — signing preflight blocked safely

The operator authorized the previously fingerprinted APK `507ec30d...`, but
the mandatory pre-publication signature comparison found that it was signed by
temporary local certificate `411021d4...`; the established Atenea channel and
installed application use certificate `a1642a05...`. Android would reject that
artifact as an update. The public/protected APKs, manifest and release archive
therefore remained untouched at `0.5.102` / versionCode 135 /
`6dc6dc1d...`, and release 136 remains absent.

A corrected `0.5.103` / versionCode 136 candidate was built from the same clean
implementation commit `39d7d7379423b3da36ce89cc3329cbc6f87f00b3`
through the established production Android builder without reading its key or
secret values. Its APK SHA-256 is
`bec7c6539df49bda3a877d47e4010468c4f6f09168348189ac1c6aa48462341e`
and its certificate SHA-256 is the exact channel certificate
`a1642a052853e9992da7ae8f8b6fe09e150533877776c009e7cca83e8b76559a`.
The task-owned signing worktree was removed; the corrected immutable artifact
is staged only as candidate evidence and has not been published or installed.

Sanitized evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-signing-preflight-blocked`;
the SHA-256 of its `SHA256SUMS` is
`27f5f07c85a83159ef8d32d3fe8a25b446d7a020e9a0e3af7fbebd54d84b63c0`.
OpenSpec remains `24/28`; task 5.1 is still pending and now requires separate
authorization for the corrected APK hash and matching channel certificate.

## Android attachment rollout — exact APK published, installation pending

The operator separately authorized exact commit `39d7d737...`, corrected APK
`bec7c653...` and channel certificate `a1642a05...`. Publication completed
through the existing protected Android channel with automatic predecessor
rollback armed and unused. Public, protected, release-136 and authenticated
download copies all match exact candidate SHA-256
`bec7c6539df49bda3a877d47e4010468c4f6f09168348189ac1c6aa48462341e`.
Both current and archived manifests expose `0.5.103` / versionCode 136 with
the exact previous release `0.5.102` / versionCode 135 / `6dc6dc1d...`.

The downloaded published APK independently verifies against exact channel
certificate `a1642a05...`. Publication staging is absent. No Android device was
available over ADB, so installation and the bounded synthetic-image canary
remain an explicit operator action. Production, preview, Beautips and Caddy
retain their accepted images, running state, zero restarts and HTTP 200. No
backend, AX42, runtime, prompt, turn, attachment, database, routing,
configuration or foreign resource was touched.

Sanitized evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-rollout-20260811`;
the SHA-256 of its `SHA256SUMS` is
`70868b20a5a1df93b3a461da414c68ed42082170c5b449ce57fccabd3611af14`.
The evidence includes a generated abstract PNG fixture with no text, person,
UI, brand or real data for the bounded on-device selection canary.
OpenSpec progress is `25/28`; task 5.2 is the exact first pending task. It will
remain incomplete until the operator installs 0.5.103 and the real Android
screen proves the eligible Atenea WorkSession attachment state without
sending a prompt.

## Android attachment rollout — real device ready state verified

Task 5.2 is complete. The operator installed the exact authorized Atenea APK
`0.5.103` / versionCode `136`; the application settings screen independently
shows that version as current and retains `0.5.102` as the predecessor. The
real Android conversation exposes the bounded image-selection affordance for
canonical Atenea WorkSession 19 without requiring a prompt.

A production transaction declared `READ ONLY` and ended with `ROLLBACK`
confirms that WorkSession 19 is the sole open canonical Atenea session, remains
`OPEN/NOT_STARTED`, and uses attachment policy version 1. Since the canary
began there are zero new turns, zero new AgentRuns and zero attachment
bindings. No prompt, response, credential or attachment content was read or
retained. The settings screenshot is retained; the conversation screenshot is
intentionally not copied because it also contains unrelated retained response
text.

Sanitized evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-rollout-20260811`;
the SHA-256 of its `SHA256SUMS` is
`fa172351d9872ca48d0fcab5e5f9224a90c59293bcd6da30582846b3af4348e0`.
OpenSpec progress is `26/28`; task 5.3 is the exact first pending task.

## Android attachment rollout — bounded synthetic selection verified

Task 5.3 is complete. With explicit operator intent, the real Android picker
selected the generated non-secret geometric JPEG and the composer visibly
reported `1/4` selected, a thumbnail, `75.4 KB`, and the secondary removal
action. The input remained empty and the operator stopped before Send. The
state is readable in the first mobile viewport with no clipping, overlap,
horizontal overflow or competition with the sole primary Send action.

Read-only production metadata confirms two distinct, byte-identical,
unbound operator uploads from the two picker selections. Both are retained
unchanged under the attachment policy: neither has an AgentRun or turn
binding, and no deletion, adoption or rebinding was attempted. Since the first
selection there remain zero new turns, zero new AgentRuns and zero attachment
bindings, proving that selecting and uploading the image did not submit a
prompt or start Codex/runtime.

The generated source fixture and sanitized metadata report remain in
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-rollout-20260811`;
the SHA-256 of its `SHA256SUMS` is
`fa172351d9872ca48d0fcab5e5f9224a90c59293bcd6da30582846b3af4348e0`.
OpenSpec progress is `27/28`; task 5.4 is the exact first pending task.

## Android attachment rollout — final archive blocked by AX42 divergence

Task 5.4 started with a read-only control/worker postflight and stopped before
archive or corrective action. Production, preview, Beautips and Caddy retain
their exact accepted images, running state and zero restarts; all three
application health checks return HTTP 200 and Caddy configuration is valid.
The accepted absent activation network remains absent.

AX42 no longer matches the task-4 baseline. Admission changed from normal
`1/4`, heavy `0/2` to normal `2/4`, heavy `1/2`; registry selection/execution
changed from disabled to enabled and its workspace count changed from zero to
one. The sole registration is WorkSession 19 remote UUID
`6547081d-895e-4be1-a8fd-d115b7743cdf`. Its admission, allocation and registry
were materialized together at `2026-08-11 15:48:38 +0200`. This was not part
of the authorized image-selection canary and prevents a truthful final
non-impact claim.

No resource was adopted, repaired, released, removed or modified. Worker,
preview and attachment services, backups, timers, slots `3/0/0/3`, RAID
`[UU]`, and the explicitly excluded allocation/admission remain intact. The
sanitized blocker evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-rollout-20260811`;
the SHA-256 of its `SHA256SUMS` is
`e4a84d8444c84991d39da5d967cf380ce01f9cd89ca183dff9061b3866f1b0b7`.

OpenSpec progress remains `27/28`; task 5.4 remains the exact first pending
task and the change is deliberately not archived. A separate operator
decision must first accept this WorkSession 19 ownership as expected or
authorize its exact lifecycle disposition.

## Android attachment rollout — completed and archived

The operator accepted WorkSession 19 registration, admission and allocation
as exact expected ownership created by successful AgentRun 97 before the
attachment canary. Read-only correlation removes the apparent time conflict:
AX42's `15:48 +0200` materialization is `13:48 UTC`, matching AgentRun 97;
the two generated-image uploads occurred later at `15:10` and `15:12 UTC`.
Source inspection confirms AgentRun admission ensures workspace ownership
before dispatch, while capability and attachment upload only check/use
existing ownership.

Final read-only persistence proves AgentRun 97 remains terminal `SUCCEEDED`
with zero attachments. Since the first generated upload there are zero new
turns, zero new AgentRuns and zero attachment bindings. Both byte-identical
uploads remain unbound and retained by policy. No prompt, response or
attachment content was read; every database query ended with `ROLLBACK`.

The accepted WorkSession 19 admission, allocation and registry remain
byte-exact at `7a89d9e4...`, `08db9255...` and `c867783c...`. Production,
preview, Beautips and Caddy retain exact accepted images, running state and
zero restarts; application health is HTTP 200 and Caddy configuration is
valid. AX42 services, successful backups, slots `3/0/0/3`, admission `2/4`
and `1/2`, RAID `[UU]`, and the separately excluded ownership remain intact.

Final sanitized evidence is retained at
`/home/jose/codex-evidence/add-android-worksession-image-attachments/task-5-rollout-20260811`;
the SHA-256 of its `SHA256SUMS` is
`a43ff299a0430aee5a0c5db172cefa48422061f649cff332b17add83ef859bd4`.
Task 5.4 is complete and OpenSpec progress is `28/28`. Strict validation
passed and the change is archived as
`2026-08-11-add-android-worksession-image-attachments`, with its three native
Android requirements applied to the canonical WorkSession attachment spec.
There is no remaining rollout or operator action in this change.

## Reviewed instruction sandbox cleanliness — root cause and specification

The separate corrective change
`fix-reviewed-instruction-sandbox-cleanliness` addresses the false dirty
source state exposed by WorkSession 19 AgentRun 97. The retained host worktree
is clean at canonical commit `e4287dbc...`; tracked `AGENTS.md` is 3,804 bytes,
matches index blob `75173298...` and accepted SHA-256 `a09adc58...`. No source
file was emptied or modified.

The exact installed and reviewed runner predecessor instead bind-mounts its
zero-byte ambient instruction mask over the tracked repository path inside
Bubblewrap. Git therefore reports a modified empty `AGENTS.md` only to the
Codex process. The runner had already validated and injected the real reviewed
bundle, but Codex correctly refused to work from the contradictory visible
source state. AgentRun process success records only the terminal response; it
does not imply a source change.

Official OpenAI documentation confirms automatic non-empty `AGENTS.md`
discovery and the runner-owned `project_doc_max_bytes` bound. A content-free
probe against exact installed Codex `0.145.0` proves bound `0` yields one
explicit bundle marker and zero automatic project markers, while the default
32 KiB bound yields one of each. The specified successor will project the
already-validated repository bytes read-only, set the automatic bound to zero
and retain one explicit combined bundle. Ambient home masks and all existing
authority/sandbox restrictions remain unchanged.

No installed runner, WorkSession, Git, ownership, service, runtime, prompt,
response, attachment, production, preview or Beautips resource changed.
Sanitized entry evidence is retained at
`/home/jose/codex-evidence/fix-reviewed-instruction-sandbox-cleanliness/task-0.1-entry-20260811`;
the SHA-256 of its `SHA256SUMS` is
`e3255eaf5c14843ec786399b895a07c2608f43f5b64f2256f086b44d469d10aa`.

Task 0.1 is complete and OpenSpec progress is `1/8`; task 1.1 is the exact
first pending task. AX42 installation and any real prompt remain separate
explicit gates.

## Reviewed instruction sandbox cleanliness — focused red regression

Task 1.1 adds one synthetic contract test for the successor boundary. It
requires two distinct temporary projections: an empty mask only for ambient
home instructions and the exact validated repository bytes for the tracked
worktree `AGENTS.md`. It also requires that the project bind is read-only, the
host repository remains clean, the explicit reviewed bundle appears once,
automatic project discovery is disabled and both projections disappear with
the temporary execution directory.

Against predecessor commit `d69dc63`, the focused finite test runs once and
fails only with the expected missing `prepare_instruction_projection`
implementation. No runner implementation, installed worker, live source,
WorkSession 19 ownership, service, prompt, response, attachment, production,
preview or Beautips resource changed.

Sanitized evidence is retained at
`/home/jose/codex-evidence/fix-reviewed-instruction-sandbox-cleanliness/task-1.1-red-regression-20260811`.
The SHA-256 of its `SHA256SUMS` is
`56dd315de82dba77a31a764f434d1104eeeaef3a14e640e8fa9017ed1c9ae125`.
Task 1.1 is complete and OpenSpec progress is `2/8`; task 1.2 is the exact
first pending task. Installation and a real prompt remain separate explicit
gates.

## Reviewed instruction sandbox cleanliness — implementation

Task 1.2 implements the successor boundary. Validation now preserves the exact
reviewed tracked repository bytes alongside the single explicit developer
bundle. Each execution materializes a distinct mode-0600 empty ambient mask
and exact project copy under its temporary result directory. Bubblewrap binds
only the ambient mask over the two home instruction paths and binds the exact
project copy read-only over the tracked worktree `AGENTS.md`. The fixed runner
argument `project_doc_max_bytes=0` prevents a second automatic injection.

Six focused contracts cover new, resumed and image-bearing invocations,
single injection, exact bytes, Git cleanliness and cleanup. All pass. The
complete runner contract suite also passes all 23 tests, and in-memory Python
syntax compilation and `git diff --check` pass.

Read-only non-impact reconfirmed the installed predecessor, clean WorkSession
19 source and exact ownership fingerprints. AX42 services, successful backup
and health jobs, active timers, slots `3/0/0/3`, ready admission `2/4` and
`1/2`, and all three RAID checks remain exact. Production, preview, Beautips
and Caddy retain their accepted images, zero restarts and HTTP 200; Caddy
validates and the accepted activation-network absence remains unchanged. No
live resource was changed.

Sanitized evidence is retained at
`/home/jose/codex-evidence/fix-reviewed-instruction-sandbox-cleanliness/task-1.2-implementation-20260811`.
The SHA-256 of its `SHA256SUMS` is
`26a08a0c7319c3cbc5ab8930c14669c761bdb60948ce8f19191269db0b503ea9`.
Task 1.2 is complete and OpenSpec progress is `3/8`; task 1.3 is the exact
first pending task. AX42 installation and a real prompt remain separate
explicit gates.
