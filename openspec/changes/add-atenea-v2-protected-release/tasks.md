Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and production threat model

- [ ] 0.1 Audit current deployment/rollback, target registries, credentials
  boundaries, images and health checks in read-only mode; define exact Atenea
  target policy and non-production fixtures

## 1. Candidate and plan

- [ ] 1.1 Add red tests and expand-only schema for ReleaseCandidate,
  DeploymentPlan, DeploymentOperation, steps, receipts and predecessor
- [ ] 1.2 Implement disabled candidate eligibility and read-only exact plan
  generation with source/integration/artifact/provenance checks
- [ ] 1.3 Bind plan confirmation to M1 one-use step-up and prove expired,
  replayed, cross-target and changed-current-version denials

## 2. Restricted executor

- [ ] 2.1 Implement a typed least-privilege executor and fixed Atenea runbook;
  prove no client/Codex shell, host, service, credential or database authority
- [ ] 2.2 Implement durable deploy/inspect/reconcile and exact-predecessor
  rollback with finite health checks
- [ ] 2.3 Pass non-production success, response loss, restart, health failure,
  rollback failure, foreign-resource and audit/privacy suites

## 3. Production rollout

- [ ] 3.1 Seal schema/backend/executor predecessor-successor rollback and stop
  for H1/H2/H3; keep promotion disabled
- [ ] 3.2 After authorization, install disabled executor and run read-only Atenea
  planning/rehearsal without deployment
- [ ] 3.3 Seal an exact candidate/DeploymentPlan and stop for H9
- [ ] 3.4 After exact H9, deploy only that candidate, verify receipt/health and
  rollback behavior; observe and archive without enabling another project
