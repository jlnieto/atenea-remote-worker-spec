Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and migration proof

- [ ] 0.1 Re-audit project/session/branch constraints, Git topology and AX42
  ownership; build synthetic legacy and multi-branch fixtures; prove WS19
  exact exclusion and seal the expand/contract plan

## 1. Domain and persistence

- [ ] 1.1 Add red domain/persistence tests for multiple changes, one active
  session per change, branch collision, source revision and downstream stale
  invalidation
- [ ] 1.2 Add expand-only `DevelopmentChange` persistence and nullable
  WorkSession binding while retaining the project-level legacy guard
- [ ] 1.3 Implement disabled create/list/detail/pause/abandon and session-bind
  APIs with server-derived branches, ownership and next actions

## 2. Workspace and drift lifecycle

- [ ] 2.1 Implement durable provision/inspect/reconcile operations using fixed
  worker contracts; test restart, lost response, ownership mismatch and
  foreign-resource refusal
- [ ] 2.2 Prove two synthetic Atenea changes have isolated branches,
  worktrees, sessions, Codex thread identities and resources without running a
  real prompt
- [ ] 2.3 Specify and test disabled `LEGACY_BIND` plan/confirmation with an
  explicit WS19 exclusion and no automatic backfill

## 3. Contract migration and rollout

- [ ] 3.1 Seal the constraint-contract migration and Atenea-only rollout;
  strict-validate and stop for H1/H2/H3 as applicable
- [ ] 3.2 After exact authorization, apply only the sealed rollout and prove
  synthetic multi-change operation while legacy clients and WS19 remain exact
- [ ] 3.3 Observe, seal no-impact and archive; leave legacy binding disabled
