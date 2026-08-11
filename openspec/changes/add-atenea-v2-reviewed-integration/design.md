## Context

WorkSessionGitHubService already proves publish/sync/close rules, and remote
close persists exact RELEASED receipts. V2 wraps those primitives in a
DevelopmentChange-level integration operation with validation/review guards.

Dependencies: M1 security, M2 changes, M3 artifacts, M4 validation and M5
review.

## Goals / Non-Goals

**Goals:**

- Publish only the exact accepted source.
- Keep one PR identity per change and reconcile unknown outcomes.
- Enforce required checks and explicit merge confirmation.
- Close/release WorkSessions only after Git/delivery and worker receipts.
- Keep other changes and retained evidence intact.

**Non-Goals:**

- Deploy or publish release artifacts.
- Rebase/overwrite conflicts automatically.
- Let client choose repo URL, ref, merge target or credentials.
- Retry a failed AgentRun or copy conversation content.

## Decisions

### 1. Immutable IntegrationPlan

The plan freezes change/source, base, branch, validation projection, review
decision, expected GitHub repository and required checks. Displayed plan SHA
is the confirmation target.

### 2. Separate publish and merge operations

Publish creates/reconciles commit, push and PR. Merge is a distinct H7 action
after required checks. This lets the operator inspect GitHub state and prevents
one confirmation from covering both effects.

### 3. GitHub reconciliation first

After network/response uncertainty, Atenea queries the exact repo/branch/PR/
commit and compares identities. It never creates another PR or merge until the
previous effect is classified.

### 4. Close after integrated source

Once merge is durable, Atenea synchronizes canonical Git and invokes the
existing monotonic close/release lifecycle. DevelopmentChange integration is
not `INTEGRATED` until Git and the exact worker RELEASED receipt are persisted.

## Risks / Trade-offs

- [PR already exists] -> adopt only if full branch/base/head/change marker
  matches; otherwise ownership conflict.
- [Checks change after plan] -> readiness becomes stale and merge blocks.
- [Merge succeeds but response is lost] -> inspect exact PR merge commit and
  persist the original result.
- [Closing one session affects another branch] -> change/workspace ownership
  preflight and non-impact checks.

## Migration Plan

1. Add disabled integration plan/operation/event schema and read APIs.
2. Implement GitHub adapter against synthetic/local fixtures and a bounded test
  repository.
3. Enable read-only planning for Atenea, then one synthetic publish canary.
4. Require separate H7 for real publish and merge; close only the named
   WorkSession.

Rollback disables new integration, reconciles already accepted operations,
restores the backend predecessor and preserves branches, PRs, worktrees and
receipts. It never force-pushes or deletes ambiguous refs.

## Open Questions

Merge strategy is project policy and must be explicitly selected for Atenea at
implementation entry; clients cannot override it per request.
