## Context

Current refresh tokens are hashed and consumed once, but there is no durable
session family/device inventory, replay-family revocation or action-bound
step-up. Role checks alone protect the most privileged recovery paths.

Dependency: `bootstrap-atenea-v2-control-contracts` (M0).

## Goals / Non-Goals

**Goals:**

- Make passkey/WebAuthn the preferred strong factor.
- Require recent proof for exact high-impact actions.
- Detect refresh replay and give the operator session visibility/revocation.
- Invalidate stale authorization after role, password or factor changes.
- Preserve a controlled offline recovery path.

**Non-Goals:**

- Add more human users or organizational RBAC.
- Use SMS or email links as a privileged factor.
- Store raw refresh tokens, passkey private material or recovery codes.
- Authorize any release, migration or production action.

## Decisions

### 1. Passkey first, password migration compatible

Existing password login remains temporarily available during rollout. A
registered passkey provides phishing-resistant login/step-up. Removal of
password-only login is a later contract phase after successful recovery tests.

### 2. Refresh-token families

Each login creates a family/session ID with device label, creation, last use,
expiry and revocation metadata. Each refresh rotates the token atomically.
Reuse of a consumed token revokes the entire family and emits an alert/audit
fact.

### 3. Version-bound access tokens

Access tokens carry session ID, role version and credential version. Every
authenticated request verifies the active account and versions. Factor, role,
password or global-revocation changes invalidate older tokens.

### 4. One-use action authorization

Step-up creates a short-lived `PrivilegedActionAuthorization` containing actor,
session, action kind, target fingerprint, plan fingerprint, expiry and
consumption. It cannot authorize a different action/target and is consumed in
the same transaction that durably accepts the operation.

### 5. Controlled recovery

TOTP may be enrolled as a fallback. Recovery codes are high entropy, shown
once, stored hashed and consumed once. Recovery changes credentials version
and revokes other sessions. No bypass is created by server configuration.

## Risks / Trade-offs

- [Operator locks themself out] -> require tested second factor and sealed
  recovery codes before enforcing passkey-only privileged actions.
- [Android/WebAuthn platform differences] -> shared backend challenge contract
  plus native/browser conformance tests.
- [Stolen refresh token races the real client] -> atomic rotation and family
  replay revocation.
- [Step-up token replay] -> one-use DB constraint, short TTL and exact target
  fingerprint.

## Migration Plan

1. Expand schema for credentials, session families, challenges and action
   authorizations with enforcement off.
2. Add session inventory/revocation and refresh rotation compatibility.
3. Enroll passkey and recovery factors only after H11 authorization.
4. Run shadow step-up checks, then require them only for V2 actions on Atenea.
5. Observe login/refresh/recovery on Android and web before tightening legacy
   privileged paths.

Rollback disables step-up enforcement but preserves factors, sessions and
audit; it must never export secrets or silently re-enable a revoked family.

## Open Questions

Whether password-only login is eventually removed is deferred until the
passkey/recovery observation window is accepted.
