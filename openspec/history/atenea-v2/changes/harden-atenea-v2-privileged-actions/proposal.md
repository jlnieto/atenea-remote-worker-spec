## Why

Atenea has one active account with `PLATFORM_ADMINISTRATOR`, password login and
multiple valid refresh sessions. A sole operator still needs protection from
session theft: a long-lived administrator session must not be sufficient to
merge, deploy, roll back, change policy or recover privileged infrastructure.

## What Changes

- Add passkey/WebAuthn authentication and recent step-up proof.
- Add rotating refresh-token families, replay detection, session inventory and
  revocation.
- Bind one-use privileged authorizations to the exact action and target
  fingerprint.
- Add TOTP and hashed one-use recovery codes as controlled recovery paths.
- Add rate limits, credential/role version invalidation and sanitized security
  audit events.

## Capabilities

### New Capabilities

- `atenea-v2-privileged-action-security`: Strong authentication, session and
  action authorization contract for privileged V2 operations.

### Modified Capabilities

None.

## Impact

- Future authentication schema, backend endpoints, web/Android login and
  confirmation UI.
- Requires explicit credential-enrollment and production migration gates.
- Does not revoke current sessions, enroll a factor or change the account as
  part of specification work.
