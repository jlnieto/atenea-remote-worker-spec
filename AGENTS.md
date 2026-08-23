# AGENTS

## Scope

This repository owns the Atenea remote-worker and runtime platform. Product
code lives in the sibling `../app` repository and must not be copied here.

Canonical implementation roots are:

- `ops/worker/`
- `runtime-contract/`
- `ops/operator/`

Historical `docs/` and `openspec/` content is retained for later cleanup and
does not override code or tests.

## Working rules

- Preserve worker/runtime behavior from the reconciled `727da19` baseline.
- Keep app/platform integration protocol-based; do not add a Java build
  dependency or copy Spring, web, Android, or Flyway sources.
- Prefer focused `ops/worker/test-*` suites while iterating.
- Validate changed schemas with JSON Schema Draft 2020-12.
- Do not deploy to AX42, restart services, or use real credentials during
  repository validation without explicit authorization.
- Treat tests requiring a real host, service, Docker slot, browser runner, or
  backup repository as integration checks and report them as NOT RUN when the
  infrastructure is unavailable.
