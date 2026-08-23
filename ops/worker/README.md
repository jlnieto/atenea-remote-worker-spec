# Atenea Codex worker bootstrap

This directory contains the versioned, staged bootstrap for the Ubuntu 24.04
AX42 worker. It intentionally does not install Docker, Codex, project
repositories, application secrets, or Tailscale enrollment credentials.

## Safety model

- Run one stage at a time from an existing root recovery connection.
- Never close that connection until a fresh `jose` login has succeeded.
- The `ssh` stage keeps root public-key access as a break-glass path.
- The `firewall` stage exposes only rate-limited TCP/22 publicly.
- `tailscale-package` installs the signed package but does not enroll a tailnet.
- Every mutating stage writes rollback evidence beneath
  `/var/backups/atenea-worker-bootstrap/`.

## Usage

Copy this directory to the worker, then run:

```bash
sudo ./bootstrap.sh preflight
sudo ATENEA_WORKER_ADMIN_PUBKEY_FILE=/root/atenea-admin.pub ./bootstrap.sh prepare
ssh jose@WORKER_IP 'sudo -n true'
sudo ./bootstrap.sh ssh
ssh jose@WORKER_IP 'sudo -n sshd -T | head'
sudo ./bootstrap.sh firewall
ssh jose@WORKER_IP 'sudo -n ufw status verbose'
sudo ./bootstrap.sh tailscale-package
sudo ./bootstrap.sh monitoring
sudo ./verify.sh
sudo ./verify.sh --json
```

The approved administrator key is input, not repository content. The default
hostname is `codex-worker-01`; override it with
`ATENEA_WORKER_HOSTNAME` if the programme contract changes.

## Tailscale gate

Do not run `tailscale up` until the tailnet owner, a second recovery
administrator, device tags, and ACL policy have been agreed. Enrollment is a
separate operator action and no reusable personal auth key belongs on disk.

## Rollback

List snapshots first:

```bash
sudo ./rollback.sh list
sudo ./rollback.sh dry-run /var/backups/atenea-worker-bootstrap/TIMESTAMP-STAGE
```

Restore only from an open recovery shell. The rollback helper requires the
exact snapshot directory and validates sshd before reloading it. UFW is not
blindly disabled: its saved files are restored and reloaded.

## Evidence

```bash
sudo ./verify.sh
sudo ./verify.sh --json | jq .
sudo journalctl -u atenea-worker-health.service --since today
sudo systemctl status atenea-worker-health.timer --no-pager
sudo cat /proc/mdstat
sudo smartctl -H /dev/nvme0n1
sudo smartctl -H /dev/nvme1n1
```

## Administrative Codex bridge

After the secure baseline has passed and the runtime-contract change is active,
install the pinned, non-authoritative bridge:

```bash
sudo ./install-codex-bridge.sh
sudo -u jose -H codex login --device-auth
sudo -u jose -H codex doctor --summary
```

The script installs the Ubuntu 24.04 `bubblewrap` AppArmor profile recommended
for the Codex Linux sandbox, promotes only the versioned non-secret
configuration/instructions, and installs `codex-work`. It never copies a laptop
Codex home or authentication file.

The promoted administrative context is controlled by
`codex-context-allowlist-v1.txt`; `codex-context-lock-v1.txt` pins every source
hash and the reviewed Git revision. Review the deterministic effective
manifest without changing the worker:

```bash
./promote-codex-context.sh plan | jq .
```

Apply the reviewed context separately when its versioned sources change:

```bash
sudo ./promote-codex-context.sh apply
```

The apply action fails closed on unversioned or modified sources,
credential-like material, symlinks and unexpected custom skill files. It
installs only the allowlisted configuration, global instructions and OpenSpec
skills, writes `~/.codex/context-manifest.json` with per-file and aggregate
SHA-256 hashes, and does not read or copy authentication, histories, sessions,
logs, caches, state databases, SSH keys or project secrets.

Start or reattach a private persistent session:

```bash
ssh -t codex-worker \
  /home/jose/.local/bin/codex-work beautips \
  /srv/atenea/workspaces/manual/beautips
```

Detach with `Ctrl-b`, then `d`. This bridge runs as the named administrator and
MUST NOT be used as Atenea's managed AgentRun executor.

## Rootless runtime slots

Install one of the four pinned rootless Docker slots:

```bash
sudo ./install-rootless-runtime-slot.sh 1
```

The script masks the rootful Docker/containerd units, verifies Docker's signing
key, pins the Engine/CLI/Compose/Buildx/containerd packages, creates a
non-administrative slot user and applies a systemd CPU, memory and task limit.
It publishes a group-restricted proxy to that slot's rootless socket beneath
`/run/atenea-runtime/`; it never publishes `/var/run/docker.sock`.

The current `dev` template is an administrative Beautips pilot. The generic
manifest resolver and default-deny managed broker remain part of the active
runtime-contract change and are required before Atenea can schedule a project.

## Version-pinned toolchains

`toolchain-lock-v1.sh` pins the supported Ubuntu host packages, rootless Docker
packages and OCI manifest-list digests for Node 22, Maven/Java 21, Tomcat/Java
8 and Playwright/Chromium. Java, Node and browser tools run in the selected
rootless slot instead of mutating a host-global toolchain.

Review the lock without changing the worker:

```bash
./install-toolchain-prerequisites.sh plan
sudo ./install-toolchain-prerequisites.sh verify-host
```

Install and verify the immutable images in one prepared slot:

```bash
sudo ./install-toolchain-prerequisites.sh install-images 2
sudo ./install-toolchain-prerequisites.sh verify-slot 2
```

The Playwright image pins Chromium but intentionally does not serve as the
Node package source. `playwright-module-v1/package-lock.json` pins
`playwright` and `playwright-core`; `install-images` installs that bundle
through the selected rootless slot and verifies its complete content tree
before publishing it at
`/var/lib/atenea-slots/slotN/toolchain/playwright-module-v1`. Browser
containers from that slot mount the directory read-only and set `NODE_PATH`
to its `node_modules` directory. A standalone repair or initial installation
can use:

```bash
sudo ./install-toolchain-prerequisites.sh install-playwright-module 2
```

Package registry access is limited to this installation step. Runtime browser
checks use the retained, hash-verified bundle with `--network none` for
toolchain verification and do not download dependencies.

The image action is idempotent, uses only the selected slot's rootless socket,
runs version probes with networking disabled and never enables the rootful
Docker daemon. Repeat it explicitly for another slot when that slot needs the
toolchain cache.

## Session mirrors and worktrees

`session-workspace-v1.sh` implements task 3.1's Git boundary. Run it as the
`atenea-worker` service identity with the persisted WorkSession UUID, registered
project, credential-free canonical GitHub remote, base branch and session-owned
branch:

```bash
sudo -u atenea-worker ./session-workspace-v1.sh ensure \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  dummy-compose \
  https://github.com/example/dummy-compose.git \
  main \
  atenea/session-018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e
```

An individual onboarding may pin a reviewed ancestor of the canonical base
branch without publishing a temporary base branch:

```bash
sudo -u atenea-worker env \
  ATENEA_PINNED_BASE_COMMIT=0123456789abcdef0123456789abcdef01234567 \
  ./session-workspace-v1.sh ensure \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  dummy-compose \
  https://github.com/example/dummy-compose.git \
  main \
  atenea/session-018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e
```

The exact commit must already exist in the credential-free mirror and be an
ancestor of the fetched canonical branch. It becomes part of immutable
workspace ownership; a later conflicting pin fails closed.

The helper keeps fetched canonical branches under `refs/remotes/origin/*` so a
fetch cannot overwrite a session branch. It serializes changes per project,
persists a worker-owned `workspace-v1.json` beside the worktree and fails closed
when the session identity, remote, branch, ownership record or Git registration
does not match. It never resets, cleans or switches an existing worktree.

Run the synthetic lifecycle and conflict suite without GitHub or real project
state:

```bash
./test-session-workspace-v1.sh
```

The profiled runner consumes Codex JSONL only through a closed normalization
boundary. Recognized lifecycle and tool shapes become fixed operator messages
in the thirteen-category progress taxonomy. Reasoning, agent messages, command
arguments, command output, queries, environment values and unknown payloads are
discarded. The worker assigns run identity and monotonic sequence, coalesces an
identical consecutive category/message before allocation and retains only the
newest 200 events without reusing a sequence. The final answer remains in the
separate result contract; normalized progress never copies it.

The complete normalized event list is part of the durable execution record.
Repeated create/get calls return the same immutable execution identity,
lifecycle revision, result and event sequences. Reloading a terminal execution
after worker restart does not allocate another event or terminal result. The
control plane persists its highest imported worker sequence under the locked
AgentRun and imports the terminal event in the same transaction as the result
turn, so polling or startup reconciliation may safely replay the whole worker
projection.

Routine recovery uses three closed authenticated routes on that same durable
record. `cancel-exact`, `reconcile` and `doctor` accept only the persisted
execution, session, workspace and lease identities. Reconciliation is a
read-only inspection and never creates or resumes a turn. Doctor returns only
the fixed `agent-run-doctor-v1` observation, status/revision, boolean recovery
flags and bounded progress counters; it excludes workload, prompt, result,
command, output, path, host, service, slot, environment and credential data.
The legacy exact dispatch/execution cancel route remains available for v1
compatibility, while new control-plane recovery uses the complete ownership
envelope.

## Development-change workspaces

`development-change-workspace-v1.py` owns the fail-closed AX42 worktree
boundary consumed by the sibling `app` repository. The worker exposes
`POST /v1/development-changes/workspaces/{provision,inspect,reconcile}` and
advertises `development-change-workspace/v1` only while the exact executable
mediator is installed. Requests and responses are defined in
`runtime-contract/development-change-workspace-v1.*.schema.json`.

The general worker installer installs the mediator and prepares
`/srv/atenea/workspaces/changes`; it does not inspect an application checkout
or its migrations. Run the synthetic protocol, idempotency, ownership, schema,
and systemd-boundary suite with:

```bash
python3 ./test-development-change-workspace-v1.py
```

## Session runtime allocation

`session-runtime-allocation-v1.sh` implements task 3.2 without starting a
runtime or changing Git state. It requires the ready task 3.1 ownership record,
derives every runtime name from the complete WorkSession UUID, serializes
slot/port ownership, persists a byte-stable allocation and creates only the
declared runtime, log, artifact and rebuildable cache roots:

```bash
sudo -u atenea-worker ./session-runtime-allocation-v1.sh ensure \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  slot2 \
  /srv/atenea/workspaces/sessions/018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e/dummy-compose/runtime.json
```

Task 3.2 accepts normal-workload manifests only. Its caller must first acquire
the persisted normal slot returned by task 4.4's admission helper. Lifecycle
commands and JSON rendering are implemented by tasks 3.3 and 3.4. Run the
collision, ownership, preservation and concurrency suite with synthetic state
beneath `/tmp`:

```bash
./test-session-runtime-allocation-v1.sh
```

## WorkSession attachment storage

`worksession-attachment-worker-v1.py` is the private Phase 5 content boundary.
It accepts only authenticated, exact WorkSession and attachment UUID routes,
validates a narrow media-type allowlist, computes SHA-256 while streaming and
retains content atomically beneath `/srv/atenea/attachments-v1`. It exposes
opaque storage identities, not filesystem paths, and has no list, shell or
directory-browsing endpoint.

Run its synthetic protocol suite:

```bash
python3 ./test-worksession-attachment-worker-v1.py
```

Review and install it on AX42 with the exact Atenea tailnet address:

```bash
./install-worksession-attachment-v1.sh plan | jq .
sudo ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.x.y.z \
  ./install-worksession-attachment-v1.sh apply
```

The default limits are 16 MiB per file and 256 MiB per WorkSession. General
deletion is deliberately absent: the exact delete route works only when both
the retained record and the request identify a synthetic fixture. Disable new
traffic without deleting retained bytes with:

```bash
sudo ./install-worksession-attachment-v1.sh disable
```

## Private WorkSession previews

`session-preview-worker-v1.py` projects an exact persisted synthetic preview
identity onto one bounded tailnet listener. It derives the loopback upstream
only from `runtime-allocation-v1.json` and the worktree runtime manifest; API
callers cannot supply a host or port. The authenticated control protocol
supports activate, inspect, renew, stop and exact terminal-fixture deletion.
Retries are revision-aware and idempotent, while missing, partial, stale,
foreign and ambiguous ownership fails closed.

The public response exposes only the tailnet preview URL. When the project
manifest explicitly requires localhost compatibility, it also returns
credential-free tunnel inputs for the `codex-worker` SSH destination; it never
returns the runtime loopback port.

Install on the worker with an exact control-plane tailnet address:

```bash
sudo env ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.88.252.28 \
  ./install-session-preview-v1.sh plan
sudo env ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.88.252.28 \
  ./install-session-preview-v1.sh apply
sudo env ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.88.252.28 \
  ./install-session-preview-v1.sh verify
```

The installer binds control port `8789` to `tailscale0`, reserves private
ingress ports `19000-19031`, stores its bearer token outside the repository and
does not print it. `disable` stops new and existing projections while retaining
state. `rollback` additionally removes only the two exact firewall rules and
also retains persisted records for reconciliation or audit.

## Exact Atenea Codex workload

`agent-run-worker-v1.py` retains the synthetic protocol and adds the closed
`project-codex-v1` schema. The project capability is absent from health until
the root-owned configuration contains the one exact registered Atenea
WorkSession and is explicitly enabled. Requests contain no command, path,
remote, endpoint or environment. The runner derives the worktree and Git
common directory from persisted ownership, checks the pinned repository,
ancestor commit, manifest and allocation fingerprints, and feeds the prompt
only through stdin.

The authenticated `GET /v1/codex/catalog` route advertises the closed
`codex-model-catalog-v1` inventory independently of project execution. Its
revision digests the schema version, exact installed Codex `0.145.0` version
and canonical sorted model entries; the diagnostic generation time is excluded
from that digest. Health always advertises the catalog capability; profiled
`project-codex-v2` appears only with the existing exact project-selection gate
and remains subject to the later rollout gate.

The staged `project-codex-v2` validator extends the immutable canonical request
fingerprint with `modelId`, `reasoningEffort`, `catalogRevision` and
`codexVersion` only after reusing the complete v1 project, repository,
instruction and persisted session/workspace checks. Unsupported or stale
profiles and additional caller authority fail before an execution record is
created. The fixed runner passes only `--model` and the canonical
`model_reasoning_effort` override, verifies the installed Codex version before
execution and echoes the exact effective profile/version. A mismatching runner
result is rejected rather than accepted as terminal success.

The runner executes the existing authenticated `jose` Codex identity inside a
per-process Bubblewrap filesystem namespace and a collected transient systemd
cgroup. That reviewed outer namespace is the effective workspace-write
sandbox; the Codex CLI's nested sandbox is disabled only after entering it
because AX42 rejects nested unprivileged user namespaces. Only the exact
worktree, its canonical Git common directory, the Codex-owned
authentication/session boundary and a private result directory are mounted;
host daemon sockets, other workspaces and production paths are absent. The
child cgroup denies loopback, RFC1918, Tailscale and link-local destinations
while retaining public HTTPS/DNS egress for Codex. Orchestration never reads or
copies the Codex authentication cache.

`codex-release-stage-v1.py` implements the separately gated staging boundary.
The authenticated worker route accepts only `operation`, persisted plan UUID,
candidate UUID and idempotency UUID. The mediator derives the archive,
version, digest, catalog and filesystem roots from a root-owned registry;
caller URLs, versions, paths, commands and services are not accepted. It
verifies the complete archive digest and safe member set, invokes only the
verified release's fixed schema generator, validates App Server and CLI schema
version markers, writes an immutable release/schema manifest and returns no
path values. The canonical `current` and `previous` links are fingerprinted
before and after staging and must remain unchanged. The capability is absent
from worker health until the mediator and registry both exist; installing the
source alone therefore enables no update behavior.

Run its synthetic archive, traversal, digest, schema, retention and repetition
suite with:

```bash
python3 ./test-codex-release-stage-v1.py
```

`codex-release-activate-v1.py` is a distinct root-mediated boundary. It accepts
only the exact persisted plan, candidate, single-use authorization and
idempotency UUIDs. The worker rejects it while any execution is non-terminal
and blocks new dispatch for the bounded operation. The mediator requires one
accepted stage record, compares both generated schemas, runs only the fixed
candidate contract, health and canary executables, and atomically advances
`previous` and `current`. A health or canary failure restores both exact link
targets before returning failure. Repetition returns the immutable operation
without rerunning a canary, and no service, path, command or host comes from the
caller. The capability is absent until stage mediator, activation mediator and
root-owned registry all exist.

Run its focused link, gate, restore and repetition suite with:

```bash
python3 ./test-codex-release-activate-v1.py
```

The same closed mediator accepts the distinct `ROLLBACK_CODEX_UPDATE`
operation only with exact persisted plan, candidate, activation, rollback
authorization and idempotency UUIDs. It requires the live `current` and
`previous` fingerprints to match the accepted activation, swaps only those two
fixed links, persists the intermediate link-restored state and invokes the
root-owned restart scheduler. That scheduler rejects every service except
`atenea-agent-run-worker-v1.service` and creates an idempotent delayed systemd
unit so the authenticated HTTP response can finish before the worker restarts.
No project App Server, runtime, slot, host, command or service is selected by
the caller. Exact repetition returns the completed immutable result without a
second swap or restart schedule.

Installation updates the existing private tailnet worker endpoint and leaves
the real-project capability disabled:

```bash
sudo ./install-atenea-routing-activation-v1.sh apply
sudo env ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.88.252.28 \
  ./install-agent-run-worker-v1.sh apply
sudo ./install-agent-run-worker-v1.sh disable
```

The activation installer must run first. The AgentRun installer fails closed
before stopping or writing if the installed activation program, sudoers
boundary or three fixed workspace dependencies are absent, stale or foreign.
The routing installer also supports the single exact four-rule release-
preflight generation currently installed on AX42. Before replacing its exact
release mediator, it retains those root-owned bytes beneath the fixed private
routing predecessor root. The successor adds only the fixed
`--diagnose-unactivated` authority. Rollback restores the retained mediator and
the exact four-rule boundary; it never reconstructs released ownership. A
missing, changed, symlinked or foreign retained predecessor rejects before the
installed bundle is changed.
If canonical Atenea source advanced while its root-owned project registry was
completely empty and both selection and execution remained disabled, the
installer may advance only that registry commit after proving the retained
commit is an exact ancestor of the fixed canonical mirror. It rejects the
transition if a workspace exists, either gate is enabled, the modern fixed
authority fields are incomplete, or the commits are unrelated; the transition
never enables selection or execution.

Selection may be enabled with zero registered workspaces solely so Atenea can
open a new WorkSession and persist its worker-generated UUID. Dispatch remains
denied in this state:

```bash
sudo ./install-agent-run-worker-v1.sh project-selection-enable
```

When an earlier exactly owned Atenea WorkSession contains a stale dirty draft,
register that retained identity only for the sanitized recovery transaction.
The operation requires an ancestor HEAD, a non-empty draft, the exact
allocation and manifest, enables selection but keeps execution disabled:

```bash
sudo ./install-agent-run-worker-v1.sh project-retained-draft-register \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  remote:ax42-01:work-session:018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  0123456789abcdef0123456789abcdef01234567
```

After the canonical workspace/allocation exists, register and enable only its
exact immutable identity:

```bash
sudo ./install-agent-run-worker-v1.sh project-register \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  remote:ax42-01:work-session:018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e
sudo ./install-agent-run-worker-v1.sh project-enable
```

Rollback first disables the project and then unregisters only the matching
persisted identity. These operations do not remove a worktree, runtime,
database, preview, Git record or evidence:

```bash
sudo ./install-agent-run-worker-v1.sh project-disable
sudo ./install-agent-run-worker-v1.sh project-unregister \
  018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e \
  remote:ax42-01:work-session:018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e
```

An uncertain real turn found after service restart becomes terminal `FAILED`
with its original execution identity. It is never silently replayed; a later
operator action may resume only from a persisted Codex thread UUID.

## Active Beautips route

Beautips is the first production-control-plane project enabled on AX42. Normal
operation requires all of these identities to agree before dispatch:

- Atenea project name `Beautips` and worker project identity `beautips`;
- worker `ax42-01`;
- remote WorkSession UUID and workspace branch
  `atenea/session-<uuid>`;
- workspace identity `remote:ax42-01:work-session:<uuid>`;
- accepted commit `e9e0b3c319c518363d4135f5378ebbddced96dfb`;
- one normal slot in `slot2`–`slot4`;
- one exact registered workspace with selection and execution enabled.

The production compose configuration enables the global and exact Beautips
gates while keeping `ATENEA_REMOTE_WORKER_PROJECT_CODEX_ENABLED=false`.
Preview operation additionally requires `ATENEA_PREVIEWS_ENABLED=true`, the
exact `Beautips` allowlist, private coordinator `100.81.98.93:8789` and a
dedicated file-mounted credential. Never print or copy either credential into
logs or evidence.

Read-only normal checks:

```bash
sudo /usr/local/libexec/atenea/install-beautips-project-v1.sh verify
curl --fail --max-time 10 http://127.0.0.1:25378/actuator/health
git -C /srv/atenea/workspaces/sessions/<uuid>/beautips status --short
```

Rollback first changes only the exact production Beautips selector to `false`,
validates the compose model and recreates only `atenea-backend-prod`. After
zero non-terminal AgentRuns are confirmed, disable worker selection/execution:

```bash
sudo /usr/local/libexec/atenea/install-beautips-project-v1.sh disable
```

This retains the pinned open WorkSession, workspace registration, admission,
allocation, mirror, worktree, Git, runtime, database volume, logs, artifacts
and private preview. Repeat `disable` to prove byte-idempotence. Do not
unregister or clean resources as part of routing rollback.

Re-enable only after worker, RAID, external backup, production and foreign
slot checks pass. Invoke the closed mediator through its installed
`atenea-worker` sudo boundary; callers must not supply any path, repository,
slot, port or credential:

```bash
sudo -u atenea-worker sudo \
  /usr/local/libexec/atenea/beautips-workspace-activation-v1.sh ensure \
  <uuid> atenea/session-<uuid>
```

The operation must return the same workspace identity and restore exactly one
registered workspace. Only then restore the exact production Beautips gate,
validate compose and recreate only the backend. A final deterministic turn
must retain the existing Codex thread and produce one dispatch/execution.

## WorkSession-aware dev client

`dev-session-v1.sh` implements task 3.3's human command surface and task 3.4's
stable JSON renderer:

```bash
sudo -u atenea-worker ./dev-session-v1.sh list
sudo -u atenea-worker ./dev-session-v1.sh \
  --session 018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e status
sudo -u atenea-worker ./dev-session-v1.sh up dummy-compose \
  --session 018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e
sudo -u atenea-worker ./dev-session-v1.sh --json \
  --session 018f47a2-6b0c-7a31-9c2d-4f5a6b7c8d9e status
```

The client resolves a WorkSession from `--session`, the current owned worktree
or an unambiguous project selector. It validates both ownership records and the
exact repository-relative manifest persisted by task 3.2. `list`, `status`,
`url` and `doctor` render concise human state. `build`, `up`, `stop`, `restart`,
`redeploy` and `logs` delegate to `/usr/libexec/atenea-runtime-client-v1`; they
never execute manifest lifecycle commands or contact a container daemon
directly.

The mediated runtime client, manager and engine remain intentionally
uninstalled while their reviewed task 4.2 and 4.3 sources are staged. Mutating
commands therefore fail closed outside the synthetic suites. `--json` emits
one schema-valid envelope on stdout, keeps fixed diagnostics on stderr and
never copies raw runtime-client output into the envelope.

Run the complete resolver and delegation suite beneath `/tmp`:

```bash
./test-dev-session-v1.sh
```

## Mediated runtime manager

Task 4.2 adds `runtime-client-v1.sh` and `runtime-manager-v1.sh`. The client has
no runtime authority. Its production contract invokes only the fixed,
root-owned manager boundary as `atenea-worker`; the manager independently
validates caller identity, the WorkSession records, allocation ownership, the
complete reviewed manifest and the exact worktree boundary.

Before an operation can reach the fixed runtime-engine interface, the manager
requires a resolved policy report with:

- exactly the services declared by the manifest;
- no mounts, host namespaces, added capabilities, devices or daemon sockets;
- no unsupported runtime fields;
- only names derived from the selected WorkSession allocation.

The manager then creates a mode `0600` operation plan containing only validated
identities, allocations and default-deny restrictions. It never executes a
manifest lifecycle `argv`. The plan requires no-new-privileges, a read-only
root filesystem, all capabilities dropped, no host network/PID/IPC, no devices,
no daemon sockets and no mounts.

Run the manager, client, cross-session denial and synthetic-engine suite
beneath `/tmp`:

```bash
./test-runtime-manager-v1.sh
```

The suite does not contact Docker. Installing the root-owned client/manager and
engine remains a separate controlled worker action.

## Synthetic runtime engine fixtures

Task 4.3 adds `runtime-engine-v1.sh` and two fixed fixtures beneath
`runtime-contract/fixtures/valid`. Both declare internal HTTP port `8080`, no
secrets and no external service. One uses a generated restrictive Compose
definition and the pinned Node image. The other compiles a servlet with the
digest-pinned JDK 17 image and runs it with the pinned Java 8/Tomcat 8 image.

Engine v1 accepts only those two reviewed fixture identities. It consumes the
manager's mode `0600` plan, revalidates allocation ownership and exact fixture
file hashes, derives the rootless slot and every resource name from the
WorkSession, and generates its Dockerfile/Compose inputs in a private
session-owned runtime root. It never copies or executes manifest `argv`
values.

Runtime containers use loopback-only port publication, a read-only root
filesystem, no-new-privileges, all capabilities dropped, private namespaces,
no devices, no bind mounts and no daemon socket. Images, containers and
networks carry complete WorkSession/runtime ownership labels and are checked
before reuse or removal. `stop` retains WorkSession records, source, logs and
artifacts.

Run the dependency-free fake-Docker integration suite beneath `/tmp`:

```bash
./test-runtime-engine-v1.sh
```

The real rootless AX42 verification is deliberately temporary: it uses only an
explicitly assigned slot, synthetic state beneath `/tmp` and a short-lived
UID-checking broker. No global client, manager, engine, sudoers entry or
service is installed by task 4.3.

## Runtime capacity admission

Task 4.4 adds `runtime-admission-v1.sh` as a pre-runtime lease boundary. It
serializes every request through one worker-owned lock and recovers capacity
from mode-restricted records persisted by complete WorkSession UUID. The
admission limits are:

- four normal slots, `slot1` through `slot4`, with one owner each;
- two independent heavy permits, `heavy1` and `heavy2`;
- one heavy permit only after that WorkSession owns a normal slot.

Repeating an active acquisition returns the same byte-stable record. Releasing
a lease changes its state to `released` instead of deleting the record, so
ownership and recovery evidence remain available. Duplicate slot or permit
claims, mismatched record identities, unsafe modes and symbolic links fail
closed.

Before a new lease is granted, the helper retains host recovery headroom by
checking load, available memory and process count. A fifth normal session
returns `NORMAL_CAPACITY_EXHAUSTED`; a third heavy operation returns
`HEAVY_CAPACITY_EXHAUSTED`. Resource-pressure denial uses the corresponding
capacity code and starts no runtime process or container. Existing leases can
still be repeated or released while pressure is high.

The production control root is reserved at
`/srv/atenea/worker/runtime-admission-v1` for a later managed installation.
Task 4.4 stages the helper and tests only; it does not create that root, install
an executable, add sudoers or start a service. Run the complete synthetic suite
as `atenea-worker` from `/tmp`:

```bash
cd /tmp
/srv/atenea/worker/workspace-v1/ops/worker/test-runtime-admission-v1.sh
```

The suite covers concurrent allocation, capacity denial, idempotency,
persistent recovery, release/reuse, ownership conflicts, human/JSON state,
secret suppression, pressure denial and preservation of records, worktrees,
logs and artifacts.

## Project runtime contract integration

Task 5.1 adds `test-project-runtime-contract-v1.sh` as the minimum global
contract suite. It runs only with synthetic WorkSessions, manifests, fixtures,
adapters and bounded loopback ports beneath `/tmp`. It composes the workspace,
allocation, `dev`, manager, engine and admission regressions, then verifies
admission-to-allocation consistency across all four slots.

The integrated assertions cover:

- formal schema acceptance/rejection when Python `jsonschema` is available,
  plus a dependency-free corpus check on the worker;
- cross-session denial at workspace, allocation, admission, manager, engine
  and resource-ownership boundaries;
- the two fixed fixtures through idempotent human and JSON lifecycle paths;
- four unique allocations for internal port `8080`, including two bounded
  loopback adapters healthy at the same time;
- four normal slots, two heavy permits, fifth-session and third-heavy denial;
- byte-stable concurrent retries without duplicate records or allocations;
- retained workspace records, worktree content, logs and artifacts;
- suppression of environment markers and raw adapter diagnostics;
- unchanged task 4.2, 4.3 and 4.4 protected hashes.

Run it locally or from the AX42 staging root without installing any global
component:

```bash
cd /tmp
/srv/atenea/worker/workspace-v1/ops/worker/test-project-runtime-contract-v1.sh
```

On AX42 invoke it as `atenea-worker`. The staged schema and invalid corpus are
test inputs only. The suite does not create a real mirror, WorkSession,
project deployment, service, sudoers rule or rootful Docker authority.

## Synthetic development database lifecycle

`database-lifecycle-worker-v1.py` is the root-owned, fixed-operation boundary
for PostgreSQL and MariaDB development fixtures. It accepts no caller endpoint,
literal credential, arbitrary Docker argument or raw command. An exact
persisted allocation and manifest determine the rootless slot, internal-only
network, container, volume, engine image, migration/seed inputs and private
snapshot identity.

`install-database-lifecycle-v1.sh apply` installs the reviewed mediator, state
module, narrow client and sudoers rule but deliberately leaves new operations
disabled. `enable` creates one mode-0640 marker; `disable` removes it;
`reconcile` reads persisted records without creating or starting resources;
and `rollback` removes only the installed program boundary. No service,
listener or firewall rule is introduced.

The fixed CLI actions are `register`, `create`, `migrate`, `seed`, `health`,
`status`, `snapshot`, `prepare-replace`, `replace`, `restore`, `stop`,
`cleanup`, `retain`, `reconcile` and `verify`. Replacement consumes a one-use,
five-minute, revision-bound confirmation, takes and verifies an engine-native
pre-replacement snapshot before deleting an exact resource, and applies the
fixed migration and seed sequence. Restore verifies size and SHA-256 before
using the engine-native client. Cleanup first validates the complete persisted
label set and can remove only the exact stopped synthetic projection.

Run the focused non-Docker tests with:

```bash
python3 ./test-database-lifecycle-state-v1.py
python3 ./test-database-lifecycle-worker-v1.py
```

## Runtime health, browser evidence and cleanup

Task 5.2 adds:

- `project-runtime-browser-check-v1.js`, a finite-timeout Playwright check for
  declared loopback identity, expected DOM text, desktop/mobile usability and
  deterministic session/run artifact registration;
- `runtime-cleanup-v1.sh`, a synthetic cleanup boundary that validates the
  allocation and requires exact engine, WorkSession and runtime labels before
  removing a container, network or image;
- `test-project-runtime-health-browser-cleanup-v1.sh`, the local fake-Docker,
  loopback-health, browser, retention, denial and idempotency suite.

The cleanup helper accepts only explicit synthetic records beneath `/tmp` and
an assigned rootless slot or synthetic Docker socket. It validates every
existing target before deleting the first one. Missing, foreign or partial
labels block the complete cleanup request. Workspace/allocation records,
mirrors, worktrees, logs and registered artifacts are never cleanup targets.

The browser check records fixed filenames beneath:

```text
<artifact-root>/<session-uuid>/runs/<agent-run-id>/browser/
```

Repeating the same check replaces the same four artifact identities and
produces the same registry instead of appending duplicates. Chromium, pages
and contexts are closed in `finally`, and every navigation and screenshot has
a finite timeout.

Run the synthetic suite from `/tmp` with an explicit temporary Playwright
runner:

```bash
ATENEA_BROWSER_RUNNER=/tmp/atenea-playwright-runner \
ATENEA_VISUAL_ROOT=/tmp/codex-visual-checks/remote-codex-platform \
  ./test-project-runtime-health-browser-cleanup-v1.sh
```

The AX42 acceptance uses the pinned Playwright image and rootless slot selected
by synthetic admission. Browser transport may use the exact session network
and container name while the registered operator URL remains the allocation's
loopback URL. This avoids widening a loopback binding or using host networking.

## Independent encrypted backup

`external-backup-v1.py` mediates the AX42 authoritative backup policy. It
selects only regular non-symlink files from worker ownership state,
WorkSession attachments, sanitized artifacts and explicitly non-secret worker
configuration. Git mirrors/worktrees, deployed source, caches, runtime state,
Codex homes, manual Beautips state, tokens, environment files, keys, cookies
and dumps are never accepted sources.

The fixed operations are `init`, `manifest`, `backup`, `check`, `retain` and
`restore`. Every operation shares one finite lock. Backup snapshots are tagged
for worker `ax42-01` and policy `atenea-authoritative-v1`; retention requires
the exact latest backup and check identities before selecting 14 daily, 8
weekly and 12 monthly snapshots. Restore requires one immutable snapshot and a
previously absent target beneath
`/srv/atenea/backups-staging/restore-tests`; it never overlays live paths.

Install the reviewed automation in disabled state:

```bash
sudo ./install-external-backup-v1.sh apply
```

The operator must create `/etc/atenea-backup/repository.env` and
`/etc/atenea-backup/repository-password` out of band as `root:root` mode
`0600`. The environment file contains the restic repository and provider
variables; neither file is committed, printed, backed up or collected as
evidence. After creating the bucket-scoped Backblaze key, install both values
through an interactive terminal without command-line or shell-history
exposure:

```bash
sudo /usr/local/libexec/atenea/configure-external-backup-v1.sh
```

The helper also requests a new Restic repository password twice. The operator
must retain that password in an independent password manager because a
complete AX42 loss cannot be recovered without it. Enable timers only after
the independent repository and isolated restore have passed:

```bash
sudo ./install-external-backup-v1.sh enable
```

`disable` stops both timers while preserving all state. `rollback` additionally
removes only the installed units and mediator; it preserves repository
credentials, remote snapshots, local state and evidence.

Run the dependency-free contract suite twice. Set
`RESTIC_REAL_INTEGRATION=1` only inside a disposable test root to include an
encrypted local repository, repeated backup/check, ambiguous-retention denial
and isolated restore:

```bash
python3 ./test-external-backup-v1.py
RESTIC_REAL_INTEGRATION=1 python3 ./test-external-backup-v1.py
./test-configure-external-backup-v1.sh
```
