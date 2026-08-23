Every task MUST be completed, tested, documented, strict-validated, committed
and published before the next task begins. Only one task may be in progress.

## 0. Entry

- [x] 0.1 Re-read applicable contracts; verify exact local/remote Git and
  sanitized Atenea/AX42 state; select the accepted application base and next
  migration number; document the compatibility and threat model without
  changing runtime

## 1. Shared control contract

- [ ] 1.1 Add focused red tests for deny-by-default global/project policy,
  normalized failure classification, idempotency collision and monotonic
  operation projection
- [ ] 1.2 Add the expand-only persistence model, audit/outbox boundary and
  additive V2 API value objects with all gates disabled
- [ ] 1.3 Implement server-derived `phase`, `blocking` and `primaryAction`
  projection plus deterministic policy/ownership responses; pass focused and
  full backend suites

## 2. Compatibility and rollout preparation

- [ ] 2.1 Prove legacy APIs and retained records remain byte/behavior
  compatible across migration, backend restart and backup/restore
- [ ] 2.2 Seal an exact production migration/image predecessor-successor-
  rollback manifest, verify non-impact and stop for H1 authorization
- [ ] 2.3 After separate authorization, apply only the sealed migration/image
  with V2 disabled; prove production, preview, Beautips, WS19, worker,
  ownership, slots, backups and RAID remain intact
- [ ] 2.4 Strict-validate, seal final evidence and archive without enabling a
  V2 project
