## Context

Existing Android has project/session/Core screens and web has a WorkSession
surface. V2 introduces orthogonal states and multiple changes, so UI must use a
server-owned projection rather than duplicate business rules.

Dependencies: M0 through M7.

## Goals / Non-Goals

**Goals:**

- Communicate current state and next action in under three seconds.
- Let operator switch between independent changes safely.
- Keep one clear primary action and subordinate detail.
- Recover accepted operations after network/app restart.
- Make permissions, step-up, stale and blocked states actionable.
- Prove responsive and native visual quality.

**Non-Goals:**

- Create a generic metrics dashboard.
- Expose internal paths, slots, commands or raw worker logs.
- Reimplement state machines in clients.
- Enable Beautips or another project.

## Decisions

### 1. Change-first navigation

Project overview lists active/attention/recent DevelopmentChanges. Selecting a
change opens a summary with phase, branch/source, blocker and primary action,
then focused sections for conversation, validation, review and delivery.

### 2. One shared read model

Android/web DTOs mirror the V2 server projection. Unknown enum/action values
fail safely as unsupported and never expose a guessed mutation.

### 3. One primary action

The backend returns the primary action. Secondary reads or safe actions remain
visually subordinate. Sensitive actions open an exact plan/confirmation and,
when needed, step-up; they never execute from a generic chat phrase alone.

### 4. Durable recovery UX

Clients persist only public operation/change IDs and last revision. On
reconnect they fetch authoritative state and offer `Continue recovery` only
for the same durable operation. Repeated taps reuse idempotency.

### 5. Evidence-driven visual verification

Every visible change proves persistence, DOM and screenshot output. Web uses
Playwright 1440x900 and 390x844. Android uses the real rendered screen and
relevant device size; long labels/IDs, accessibility and offline states are
tested.

## Risks / Trade-offs

- [Many state axes overwhelm operator] -> derived phase and progressive detail,
  not equal-weight cards.
- [Clients lag new backend enum] -> explicit unsupported/stale state and no
  mutation.
- [Double tap duplicates operation] -> stable client idempotency key and
  server operation recovery.
- [Web and Android diverge] -> shared fixtures/contract tests and parity
  acceptance matrix.

## Migration Plan

1. Add read-only V2 navigation behind client/server flags.
2. Build synthetic fixtures for every phase/blocker/permission.
3. Add actions module by module while backend gates remain authoritative.
4. Roll out web first under H3, then publish/install exact APK under H8.
5. Observe Android/web parity before making V2 default for Atenea.

Rollback disables V2 navigation/actions and restores predecessor bundles while
retaining all backend state/operations. Legacy screens remain available until
separate retirement evidence.

## Open Questions

None for information architecture. Exact visual styling must reuse the current
design system and be reviewed from real screenshots during implementation.
