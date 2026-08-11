## Context

`uk_work_session_open_project` and service checks currently allow only one
`OPEN/CLOSING` session per project. A WorkSession also carries branch,
workspace, worker and acceptance projections. V2 must introduce a higher
aggregate without rewriting retained histories.

Dependencies: M0 control contracts and M1 privileged security.

## Goals / Non-Goals

**Goals:**

- Work on multiple explicit branches of one project.
- Keep every workspace/session/run inside one change ownership boundary.
- Preserve exact canonical-source and draft fingerprints.
- Make source drift/conflict actionable and durable.
- Coexist with unbound legacy WorkSessions.

**Non-Goals:**

- Run validation, preview, merge or deployment.
- Copy prompts, turns or attachments between changes/sessions.
- Automatically bind, close or release a legacy session.
- Permit client-selected branch paths or worker resources.

## Decisions

### 1. Change identity owns branch identity

A change stores a server-generated `changeKey`, project, base ref/commit and a
validated server-derived workspace branch. `(project, workspaceBranch)` is
unique. Clients may propose a human title but not an arbitrary ref/path.

### 2. One active WorkSession per change

New WorkSessions carry nullable `development_change_id` during expansion. A
partial unique constraint prevents more than one `OPEN/CLOSING` session for a
bound change. Multiple bound changes of one project may each have one.

### 3. Deferred removal of project uniqueness

The existing project-level unique index remains until code can route both
legacy and V2 sessions safely and all affected states are audited. Contract
migration removes it only under H1 after a canary proves multi-change routing.

### 4. Source projection and invalidation

The workspace owner computes fingerprints without exposing content. Any
source change advances revision and invalidates downstream validation/review/
release projections. Canonical advance produces `STALE`, never automatic
rebase.

### 5. Explicit legacy binding

`LEGACY_BIND` creates a plan from exact DB/Git/worker ownership, requires H5
step-up confirmation and is idempotent. It cannot change source, session,
worker or resources. WorkSession 19 is hard-excluded until separately named.

## Risks / Trade-offs

- [Constraint removal permits accidental duplicate legacy sessions] -> keep a
  service guard for unbound sessions and contract only after data audit.
- [Two changes collide on branch/worktree] -> server-generated identities,
  unique constraints and worker ownership preflight.
- [Canonical branch advances] -> expose stale/reconcile plan; no implicit
  overwrite or rebase.
- [Legacy backfill changes WS19] -> no SQL backfill; explicit domain operation
  with project/session denylist during rollout.

## Migration Plan

1. Add change tables, nullable WorkSession FK and indexes; keep all old
   constraints.
2. Deploy dual-read APIs with creation disabled.
3. Enable synthetic Atenea change creation and prove two isolated workspaces.
4. Under H1/H3, contract project-level uniqueness only for V2-aware routing.
5. Enable new Atenea changes; leave all legacy rows unbound.

Rollback disables change creation/session binding, reconciles only durable V2
operations and retains schema/workspaces/evidence. It never deletes a change
workspace unless exact owned teardown was already part of its operation.

## Open Questions

Legacy binding for WorkSession 19 is intentionally unresolved and requires a
future H5 decision, not this implementation.
