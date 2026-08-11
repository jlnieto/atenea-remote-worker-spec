## Context

Current production deploys use carefully sealed scripts/images and explicit
human manifests. V2 should productize that discipline without exposing SSH,
Docker, service names or secrets to Codex or clients.

Dependencies: M1 security, M3 artifacts, M4 validation, M5 review and M6
integration.

## Goals / Non-Goals

**Goals:**

- Promote immutable integrated artifacts to an exact registered target.
- Keep credentials and runbooks in a least-privilege executor.
- Require plan-bound step-up and durable idempotence.
- Verify post-deploy health and support exact rollback.
- Make mobile/web state truthful across disconnect/restart.

**Non-Goals:**

- Let Codex deploy or receive credentials.
- Deploy mutable branches or rebuild source during promotion.
- Accept arbitrary SSH, shell, host, service or database input.
- Enable Beautips/other projects or database production mutations.

## Decisions

### 1. Candidate from integrated identity

A candidate references exact merge commit, validation/review identities,
artifact manifest and provenance/SBOM policy. Candidate bytes never change; a
new artifact creates a new candidate.

### 2. Read-only plan before authorization

Planning inspects registered target, current version, candidate, capacity,
health checks and rollback predecessor without mutation. Its canonical hash is
shown to the operator and bound to step-up authorization.

### 3. Restricted production executor

The executor accepts only operation/plan IDs, retrieves a fixed target/action
from its registry and invokes allowlisted versioned runbooks. Secrets are
mounted there only and never returned. Database operations are excluded unless
a future separate capability specifies them.

### 4. Deployment/rollback durable state

Every step is revisioned and replay-safe. Success requires target receipt and
all required health checks. Policy may automatically roll back only to the
exact predecessor embedded in the authorized plan.

### 5. Disable-first rollback

Operational rollback first disables project/global release gates, reconciles
in-flight operations and restores the exact predecessor executor/image. Schema
and audit remain.

## Risks / Trade-offs

- [Stolen admin session deploys] -> M1 step-up, exact plan, one-use
  authorization and short TTL.
- [Target changed after plan] -> target/current-version fingerprint preflight
  rejects and requires a new plan.
- [Deploy applies but response is lost] -> inspect exact operation/release ID;
  no duplicate runbook.
- [Health false negative] -> bounded checks and exact automatic predecessor;
  retain failed version evidence.
- [Executor compromise] -> per-target identities, fixed scripts, no general
  shell and auditable minimal network.

## Migration Plan

1. Add disabled candidate/plan/operation schema and read-only planning.
2. Build a non-production executor fixture and prove deploy/rollback
   idempotence.
3. Install a production executor with every project disabled under H2/H1.
4. Rehearse Atenea target without promotion.
5. Under H9, promote one exact Atenea candidate with automatic rollback
   authorized only as declared.
6. Observe before normal enablement.

Rollback disables allowlist/global gates, reconciles accepted operations,
restores the sealed executor predecessor and keeps candidates/artifacts/audit.
It never deletes or rebuilds a release.

## Open Questions

The first exact Atenea deployment target/runbook and its SLO are selected and
sealed during implementation, not by this planning document.
