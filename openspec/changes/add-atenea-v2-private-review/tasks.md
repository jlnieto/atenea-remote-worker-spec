Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry

- [ ] 0.1 Audit current preview contracts, tailnet routing, visual evidence and
  retained resources; define exact V2 review policy and synthetic fixture

## 1. Domain and coordinator

- [ ] 1.1 Add red tests and expand-only schema for ReviewEnvironment,
  ReviewDecision, immutable inputs, leases, receipts and stale invalidation
- [ ] 1.2 Implement disabled plan/activate/inspect/renew/stop/reconcile APIs
  using server-owned routes and complete ownership validation
- [ ] 1.3 Extend the AX42 coordinator and pass isolation, Internet exposure,
  restart, expiry, idempotence and foreign-resource tests

## 2. Evidence and decision

- [ ] 2.1 Integrate persistence, DOM and 1440x900/390x844 visual evidence into
  ArtifactManifest with finite Playwright and sanitization
- [ ] 2.2 Implement accept/request-changes with exact source/evidence binding,
  step-up policy and automatic staleness

## 3. Clients and rollout

- [ ] 3.1 Implement web/Android review state and one primary action; validate
  data, DOM, visual and native behavior on synthetic state
- [ ] 3.2 Seal migration/backend/worker/client rollout and stop separately for
  H1/H2/H3 and any APK gate
- [ ] 3.3 After exact authorization, prove one synthetic Atenea private preview
  and teardown; stop before any real acceptance
- [ ] 3.4 After H6, record one exact authorized review decision, observe,
  strict-validate, seal and archive
