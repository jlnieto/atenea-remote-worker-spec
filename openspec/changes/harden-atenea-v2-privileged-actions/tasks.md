Every task requires tests, documentation, strict validation, commit and
publication before the next task. Keep all enforcement disabled by default.

## 0. Entry and threat model

- [ ] 0.1 Audit authentication code, active-session metadata and clients
  without reading tokens; document threat model, browser/Android WebAuthn
  support, recovery policy and exact migration plan

## 1. Session hardening

- [ ] 1.1 Add red tests and expand-only schema for session families, atomic
  rotation, replay-family revocation, credential/role versions and session
  inventory
- [ ] 1.2 Implement compatible login/refresh/logout/list/revoke flows and pass
  security, concurrency and migration tests with enforcement off

## 2. Strong factors and action binding

- [ ] 2.1 Add WebAuthn challenge/credential registration and authentication
  with origin/RP/user-verification checks and no secret logging
- [ ] 2.2 Add optional TOTP, hashed one-use recovery codes and recovery-driven
  session revocation; prove enrollment and recovery on test identities only
- [ ] 2.3 Add short-lived one-use action authorization bound to actor, session,
  action and target/plan fingerprints; prove replay and cross-target denial

## 3. Operator clients and rollout

- [ ] 3.1 Add web and Android session/factor/step-up UX; verify persistence,
  DOM and visual states plus native behavior without changing production
- [ ] 3.2 Seal migration/client rollout and stop for H1/H11 and any APK
  authorization separately
- [ ] 3.3 After exact authorizations, roll out disabled/shadow support, enroll
  the operator-controlled factors and prove revocation/recovery without
  authorizing another V2 capability
- [ ] 3.4 Strict-validate, seal and archive after the observation window
