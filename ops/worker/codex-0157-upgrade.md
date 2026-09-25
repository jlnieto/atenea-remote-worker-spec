# AX42 managed Codex 0.157.0

This procedure is for the reviewed 0.145.0 → 0.157.0 update. It preserves the
completed 0.154.0 → 0.145.0 recovery record and the six saved GPT-5.6 Sol/high
session profiles. Run it only with `DEPLOY_MODE=AUTOMATED_ALLOWED` and explicit
authorization for this production update.

## Fixed candidate

- Inventory ID: `1d586e4a-0409-453a-9ea9-762e99d1438a`
- Version: `0.157.0`
- Archive SHA-256: `c30a04c5791c19534ba5d2586a63b3766272951e559ea0056cc5192b03d3abc9`
- Catalog revision: `1372647bd09888c3305147b9a7cf6889b5b4526e04d332971f7e3a43ccb7efc7`
- Official musl `bin/codex` SHA-256: `1a822376d4634ac32dddc030e5117c63359f7f8cd4b1b64382c68190287d0258`

Build the archive from the official 0.157.0 standalone package with
`python3 ops/worker/build-codex-0157-release.py PACKAGE_DIR ARCHIVE.tar.gz`.
The builder pins the official binary and omits only the official root `codex`
symlink, which the stage mediator does not allow. Compare the resulting archive
digest with the fixed value above before copying it to AX42.

## Order and checks

1. Merge the reviewed app and platform changes. Check that the live app
   inventory still has 0.145.0 CURRENT, 0.154.0 PREVIOUS, no other NONE
   candidate, and no nonterminal AX42 AgentRuns. Confirm the managed AX42
   `current` link and installed worker/runner still match those facts.
2. Fast-forward the clean app production checkout to `github/main` after the
   ancestry check in `docs/mobile-server-operations.md`. On the Atenea host,
   the current backend is an immutable `atenea-app:<commit>` image built from
   the root `Dockerfile`, with a commit-specific Compose override that keeps
   `ATENEA_CODEX_MANAGED_UPDATES_ENABLED=true`. The base Compose alone pins an
   older image and sets that flag to `false`, so `scripts/deploy-prod.sh` alone
   cannot deploy this update. Build `atenea-app:<new-main-commit>` from the
   exact fast-forwarded checkout, carrying the commit as
   `org.opencontainers.image.revision`. Create a new mode-0600 override for
   only `atenea-backend-prod`, setting that image and the managed-updates flag
   to `true`; preserve the previous override. Check the effective Compose
   image, flag and other services before recreating only `atenea-backend-prod`
   with `--no-deps --no-build`. Check backend health, image/revision and V83's
   single DISCOVERED/NONE candidate with the fixed inventory ID and archive
   digest. Do not continue if Flyway rejects the reviewed 0.145.0 state.
3. As a platform administrator, create the managed update plan in Atenea while
   its worker still advertises 0.145.0. Require state READY and capture its
   `planId`. Place the verified archive at
   `/srv/atenea/worker/codex-releases-v1/inbox/1d586e4a-0409-453a-9ea9-762e99d1438a.tar.gz`
   on AX42, owned by root with mode 0600. Add exactly this candidate and the
   captured `planId` to the root-owned
   `/etc/atenea-worker/codex-release-stage-v1.json`, preserving the existing
   recovery entry and mode 0600. The candidate fields are `planId`,
   `candidateId`, `codexVersion`, `releaseDigestSha256`, and `catalogRevision`.
4. Use Atenea's **Verificar** action to stage the planned candidate. Require
   STAGED and unchanged `current`/`previous` links. Check zero nonterminal
   AgentRuns again. Install the reviewed platform worker source using its
   `install-agent-run-worker-v1.sh apply` procedure and verify the service is
   active, publishes catalog 0.157.0 with GPT-6 Sol/high first, and still
   points the managed link at 0.145.0. Keep operator dispatch paused during
   this brief mismatch; the runner rejects a mismatched installed version
   before executing Codex.
5. In Atenea, create the separate activation authorization and immediately
   activate within its ten-minute lifetime. Require ACTIVATED, the candidate
   as CURRENT, old 0.145.0 as PREVIOUS, all focused/health/canary gates PASS,
   and no automatic restoration. Wait for catalog sync and verify the app's
   first available model is GPT-6 Sol/high while the six saved GPT-5.6 Sol/high
   sessions remain valid. Confirm one bounded AgentRun with the new default
   only after these checks pass.

Stop at any drift, failed gate, missing administrator session, active run, or
unhealthy service. Preserve the exact state for review; do not invoke recovery,
rollback, or manual database repair as an automatic continuation.
