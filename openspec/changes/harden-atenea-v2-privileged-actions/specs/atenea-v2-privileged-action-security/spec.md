## ADDED Requirements

### Requirement: Phishing-resistant strong factor

Atenea SHALL support WebAuthn/passkey credentials with server-generated
challenges, exact RP/origin verification, user verification and replay-safe
challenge consumption. Private credential material SHALL remain on the
authenticator.

#### Scenario: Challenge is replayed or origin differs

- **WHEN** a used/expired challenge or an assertion for another RP/origin is
  submitted
- **THEN** Atenea denies authentication deterministically and records only
  sanitized security metadata

### Requirement: Rotating refresh session families

Every login SHALL create an identifiable refresh-token family. Refresh SHALL
atomically consume and rotate the token, and reuse of a consumed token SHALL
revoke the complete family.

#### Scenario: Stolen refresh token is reused

- **WHEN** any previously consumed token in a family is presented again
- **THEN** every active token in that family is revoked and future access from
  the family is denied

### Requirement: Operator session control

The operator SHALL be able to list sanitized active session metadata and
revoke one session or all other sessions without exposing token values.

#### Scenario: Operator revokes another device

- **WHEN** an authenticated operator revokes a selected session family
- **THEN** its refresh tokens and version-bound access tokens stop authorizing
  requests while unrelated selected sessions remain active

### Requirement: Exact privileged step-up

A high-impact V2 action SHALL require `PLATFORM_ADMINISTRATOR` plus a recent,
one-use `PrivilegedActionAuthorization` bound to action kind, target and plan
fingerprints.

#### Scenario: Authorization is reused for another plan

- **WHEN** a valid unexpired authorization for one plan is supplied for a
  different target/fingerprint or after consumption
- **THEN** Atenea denies the action before creating or contacting its executor

### Requirement: Controlled recovery

Atenea SHALL offer an explicitly enrolled fallback factor and hashed one-use
recovery codes. Completing account recovery SHALL advance credential version
and revoke other sessions.

#### Scenario: Recovery code is used twice

- **WHEN** a previously consumed recovery code is submitted
- **THEN** recovery is denied and no session or factor is created

### Requirement: Authentication abuse controls

Login, refresh, factor enrollment, step-up and recovery SHALL have bounded
attempts, timing-safe secret comparison, actionable but non-enumerating errors
and sanitized audit/alert events.

#### Scenario: Repeated invalid step-up attempts occur

- **WHEN** attempts exceed the configured server-owned threshold
- **THEN** Atenea rate-limits the exact security scope without revealing which
  credential property was incorrect
