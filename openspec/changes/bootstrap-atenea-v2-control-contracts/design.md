## Context

Existing remote lifecycles prove idempotency and monotonic receipts in bounded
domains, while the older project verifier and Core capabilities use different
status/error shapes. V2 needs one closed vocabulary before any new authority is
introduced.

Dependencies: none. This is module M0.

## Goals / Non-Goals

**Goals:**

- Provide additive contracts reusable by all V2 modules.
- Make feature policy deny by default globally and per project.
- Distinguish transport, capacity, validation, policy and ownership.
- Make next action and permissions server-owned.
- Preserve durable idempotency and sanitized audit evidence.

**Non-Goals:**

- Create DevelopmentChanges, validations, artifacts, previews or releases.
- Activate any feature, project or worker path.
- Replace existing remote-close or AgentRun persistence.
- Backfill or modify WorkSession 19.

## Decisions

### 1. Additive `/api/v2` contract

V2 resources use a versioned additive API. Existing clients continue using
their current endpoints until module M8. Disabled V2 mutations return a
deterministic policy response without contacting AX42.

### 2. Two-key enablement

Every capability requires both a global gate and an exact project policy at a
known revision. Both default to false. Names, aliases or legacy feature flags
do not grant V2 policy.

### 3. Shared durable-operation fields, module-owned tables

Each module owns its operation table but implements the same fields and
invariants: operation/idempotency identity, request/target fingerprints,
revision, state, failure category/code, next action, receipt and timestamps.
This avoids one untyped mega-table while keeping behavior uniform.

### 4. Closed failure taxonomy

Only `TRANSPORT`, `CAPACITY`, `VALIDATION`, `POLICY` and `OWNERSHIP` are public
categories. Deterministic 4xx failures never enter a worker-unavailable retry
window. Unknown remote output is transport/reconciliation, not guessed.

### 5. Append-only audit and outbox

Mutations emit sanitized audit facts transactionally. Events carry IDs,
digests, states, counts and timings, never prompt/response/attachment content,
secrets or environment dumps.

## Risks / Trade-offs

- [A generic abstraction hides domain rules] -> share value objects and
  invariants, but keep module-specific tables and state machines.
- [Legacy flags accidentally enable V2] -> use a separate namespace and exact
  policy revision with negative tests.
- [Client action drift] -> return a full server-derived action projection and
  test Android/web contract fixtures.
- [Schema exists during rollback] -> readers tolerate it; disable gates rather
  than destructive down-migration.

## Migration Plan

1. Re-audit the accepted application base and assign the next free Flyway
   version.
2. Add expand-only policy/audit/outbox structures and nullable compatibility
   fields with gates absent or false.
3. Deploy code that reads legacy state unchanged and exposes disabled V2
   discovery only.
4. Prove restart, idempotency, 4xx classification and backup/restore.
5. Under a later exact gate, enable only synthetic shadow reads for `atenea`.

Rollback disables project policy first, then global gates, restores the exact
predecessor image and retains expanded schema/audit records.

## Open Questions

No product decision is open. Exact migration number, base commit and image
digest must be resolved at task 0.1 from then-current state.
