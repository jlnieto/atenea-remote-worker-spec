## Why

The reviewed Atenea project runner validates the exact tracked `AGENTS.md`
before every real AgentRun and injects the accepted platform/project bundle as
explicit developer instructions. Inside Bubblewrap, however, it overlays the
tracked repository file with an empty mask. Git and Codex therefore observe a
false dirty source tree with a modified empty instruction file, causing a
correctly cautious AgentRun to refuse otherwise authorized work.

The retained WorkSession 19 worktree is clean and its real `AGENTS.md` remains
byte-exact. The defect is confined to the ephemeral sandbox projection and
will recur on every Atenea AgentRun until the runner is corrected.

## What Changes

- Preserve the existing exact pre-dispatch validation of platform and tracked
  repository instruction bytes and their combined fingerprint.
- Project the already-validated repository `AGENTS.md` bytes read-only at the
  tracked path inside Bubblewrap so Git remains clean and manual inspection is
  truthful.
- Disable Codex automatic project-instruction discovery with the pinned,
  supported `project_doc_max_bytes=0` setting while continuing to inject the
  reviewed combined bundle exactly once as developer instructions.
- Keep ambient Codex-home `AGENTS.md`/override masks empty, reject repository
  overrides and `.codex` content, and retain the current no-caller-authority
  boundary.
- Add regression coverage for exact bytes, Git cleanliness, read-only
  projection, single explicit injection, new/resumed turns and cleanup.
- Prepare a checksum-pinned AX42 successor/rollback bundle, but require a
  separate exact authorization before installation or service restart.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `codex-session-operations`: Require the reviewed repository instruction
  projection to remain byte-exact, read-only and Git-clean while automatic
  discovery stays disabled and the explicit bundle is applied exactly once.

## Impact

- Programme repository: `ops/worker/project-codex-runner-v1.py`, focused
  worker tests, installer/checksum artifacts and operational documentation.
- Atenea backend, database, web and Android: no code, schema, configuration or
  deployment change. AX42 changes only the shared runner and its exact static
  adapter/installer trust pins; it does not change Beautips configuration,
  ownership, activation or execution.
- WorkSession 19: retained Git, registration, admission, allocation, turns,
  AgentRuns and attachments remain untouched while preparing the correction.
- Rollout: no AX42 installation, worker restart or real prompt may occur
  without a separate authorization naming the exact bundle and hashes.
