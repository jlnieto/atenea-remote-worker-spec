# Atenea platform

Canonical technical platform for the AX42 remote worker and its reusable
runtime operations. The sibling `../app` repository owns the Spring Boot,
web, Android, Flyway, and product runtime sources.

Main surfaces:

- `ops/worker/`: worker protocol, workspaces, mirrors, slots, runtime manager,
  previews, attachments, database lifecycle, backups, installers, systemd
  units, release tooling, and focused tests;
- `runtime-contract/`: machine-readable worker/runtime contracts shared with
  `app` over HTTP and runtime manifests;
- `ops/operator/`: reusable operator entry points;
- `docs/` and `openspec/`: historical material retained from `727da19` for a
  later governance simplification; it is not an execution gate for this repo.

The current worker exposes `agent-run-worker/v1` and the exact
`development-change-workspace/v1` capability used by `app` V78 for workspace
provision, inspect, and reconciliation. Its additive `project-codex-v4`
AgentRun workload executes only an exact, previously provisioned
development-change workspace while v1-v3 remain compatible. Runtime manifests remain
project-owned inputs; platform code validates and executes them without a
compile-time dependency on `app`.

Focused validation:

```bash
python3 ops/worker/test-agent-run-worker-v1.py
python3 ops/worker/test-development-change-workspace-v1.py
bash ops/worker/test-install-agent-run-worker-v1.sh
bash ops/worker/test-runtime-engine-v1.sh
bash ops/worker/test-runtime-manager-v1.sh
bash ops/worker/test-project-runtime-contract-v1.sh
git diff --check
```

Tests needing a project source take an explicit source root, such as
`ATENEA_RELOCATION_SOURCE_ROOT` or `ATENEA_BEAUTIPS_SOURCE`; no local user home
or monorepo layout is required by the canonical repository structure.
