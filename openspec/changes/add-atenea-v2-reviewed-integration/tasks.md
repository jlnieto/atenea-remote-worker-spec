Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and Git contract

- [ ] 0.1 Audit GitHub permissions, current publish/close code, branch rules
  and retained refs in read-only mode; define exact Atenea integration policy
  and synthetic repository fixtures

## 1. Durable integration

- [ ] 1.1 Add red tests and expand-only schema for IntegrationPlan,
  IntegrationOperation, steps, receipts and one-PR-per-change identity
- [ ] 1.2 Implement disabled plan/publish/inspect/reconcile with exact
  source/validation/review guards and no client-selected Git authority
- [ ] 1.3 Implement required-check readiness and separately confirmed merge
  with step-up policy and lost-response idempotence

## 2. Close and multi-change safety

- [ ] 2.1 Integrate existing Git reconciliation and remote RELEASED receipt;
  prove no `INTEGRATED/CLOSED` projection can precede both persisted results
- [ ] 2.2 Prove publish/merge/close for one synthetic change leaves another
  same-project branch/workspace/session and all foreign refs untouched

## 3. Rollout

- [ ] 3.1 Seal migration/backend/GitHub rollout and stop for H1/H3; keep real
  publish/merge disabled
- [ ] 3.2 After authorization, enable/read-test Atenea integration planning and
  one synthetic bounded canary
- [ ] 3.3 After separate H7 authorizations, publish then merge only the exact
  accepted canary and prove reconciled close/idempotence
- [ ] 3.4 Observe, strict-validate, seal and archive without creating a release
