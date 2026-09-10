# Atenea platform UFD T1 pilot

Only `runtime-contract/fixtures/codex-session-operations-v1/negative-corpus.json`
is mapped to T1. Its sole automated operation is:

```bash
python3 ops/worker/test-codex-session-operations-contract-v1.py
```

All other paths remain T3. In particular, `.delivery`, `scripts/`, worker and
runtime code, schemas, installers, ownership, systemd, backup and recovery are
never part of this T1 area. `platform-strong-path` is declared for T3 but is
not automated by this pilot.

`scripts/validate-change` ignores only the pre-existing generated directory
`ops/worker/__pycache__/`; every other tracked, untracked, renamed or deleted
worktree entry prevents a UFD run.
