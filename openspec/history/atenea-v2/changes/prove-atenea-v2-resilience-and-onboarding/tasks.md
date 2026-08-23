Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and acceptance matrix

- [ ] 0.1 Audit all V2/legacy services, backup/restore, capacity, retained and
  foreign resources; define SLOs, failure matrix and synthetic isolation plan

## 1. Observability and restore

- [ ] 1.1 Add sanitized metrics/alerts for queue, operation/reconciliation age,
  slots/heavy, disk/RAID, backup freshness, preview and deployment health
- [ ] 1.2 Extend encrypted backup/check manifests and perform byte-exact
  isolated restore of representative V2 metadata/artifacts/receipts

## 2. Failure and capacity proof

- [ ] 2.1 Prove backend restart, worker restart, response loss and network
  partition across change/validation/review/integration/release operations
- [ ] 2.2 Prove cancellation, four-normal/two-heavy capacity, fairness and no
  duplicate/foreign resource mutation
- [ ] 2.3 Prove disk-pressure/RAID/backup alert paths and ownership-safe GC
  dry-run/removal against synthetic expired resources only

## 3. Atenea observation and onboarding template

- [ ] 3.1 Run the accepted Atenea-only observation window and close every SLO,
  restore, security, UI and rollback criterion
- [ ] 3.2 Publish a project onboarding template with symbolic capability
  profile, fixtures, secrets, threats, tests, rollout, rollback and H12 gate
- [ ] 3.3 Demonstrate that an unapproved project, including Beautips, remains
  unschedulable for every V2 capability despite legacy flags/resources

## 4. Programme close

- [ ] 4.1 Seal final non-impact and full evidence chain, strict-validate and
  archive the resilience change
- [ ] 4.2 Stop for the operator to choose the first separate project onboarding
  OpenSpec; do not create it or retire legacy paths implicitly
