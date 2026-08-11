Every task requires complete tests, documentation, strict validation, commit
and publication before the next task.

## 0. Entry and storage threat model

- [ ] 0.1 Audit attachment/storage/backup contracts and live capacity in read-
  only mode; define artifact classes, limits, retention and exact AX42 storage
  boundary without reading retained content

## 1. Persistence and API

- [ ] 1.1 Add red tests and expand-only schema for artifact, manifest,
  provenance, links and staging/finalization operations
- [ ] 1.2 Implement disabled register/finalize/inspect/download APIs with
  exact ownership, digest, type, size and idempotency enforcement
- [ ] 1.3 Implement ordered canonical manifests and downstream stale/eligibility
  checks without changing WorkSessionAttachment behavior

## 2. Worker storage and continuity

- [ ] 2.1 Add a fixed AX42 artifact mediator with server-owned paths, finite
  limits, atomic finalization and no caller-selected filesystem authority
- [ ] 2.2 Prove response-loss/restart reconciliation, unauthorized access,
  digest mismatch, staging expiry and ownership-safe cleanup
- [ ] 2.3 Extend backup/check/restore for artifacts and prove byte-identical
  isolated restore with sanitized evidence

## 3. Rollout

- [ ] 3.1 Seal exact migration/backend/worker rollout and stop for H1/H2/H3
- [ ] 3.2 After authorization, enable only synthetic Atenea artifact traffic;
  verify no impact on retained attachments, WS19 or foreign resources
- [ ] 3.3 Observe, strict-validate, seal and archive while real producers remain
  gated until their modules
