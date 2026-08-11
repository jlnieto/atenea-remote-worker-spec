## Context

The installed runner validates the root-owned platform instructions and exact
tracked `HEAD:AGENTS.md`, rejects overrides and project `.codex` content, and
builds one fingerprinted developer-instruction bundle. It then creates an
empty temporary mask and bind-mounts that same empty file over both ambient
Codex-home instruction names and the tracked repository `AGENTS.md`.

The first two masks are intentional. The repository mask is defective: inside
the execution namespace `git status` sees the tracked 3,804-byte file as an
empty modification even though the host worktree remains clean. AgentRun 97
surfaced the conflict and performed no source change.

Official OpenAI documentation states that Codex discovers non-empty
`AGENTS.md` files once per run and that `project_doc_max_bytes` bounds project
instruction discovery. A content-free `codex debug prompt-input` probe against
the exact installed Codex 0.145.0 proves that value `0` excludes repository
instructions while preserving one explicitly configured developer bundle;
the default bound includes the repository source once.

## Goals / Non-Goals

**Goals:**

- Make the sandbox's tracked `AGENTS.md` byte-identical to the validated HEAD
  blob and immutable to the Codex process.
- Keep Git clean at process start without weakening canonical-source checks.
- Apply the reviewed platform/project bundle exactly once.
- Preserve all ambient-rule, caller-authority, filesystem and privacy
  boundaries.
- Provide a reversible, checksum-pinned worker-only rollout.

**Non-Goals:**

- Change any instruction text, instruction fingerprint or WorkSession source.
- Permit repository `.codex`, overrides, fallbacks or user configuration.
- Change Codex version/model, backend dispatch, routing, runtime, attachments,
  Android, web UI or preview; enable, reconfigure or execute Beautips or
  another project. The shared-runner compatibility trust pin may move without
  changing the pre-existing project registry or ownership.
- Retry AgentRun 97 or submit any real prompt during preparation/installation.

## Decisions

### 1. Keep validation authoritative and separate projection from discovery

`validate_instruction_bundle` continues reading and validating the exact
platform bytes, tracked project bytes, ownership, size, Git blob and combined
fingerprint before Codex can start. It returns both the combined explicit
bundle and the exact validated project bytes.

The runner writes those project bytes to an execution-owned temporary file and
bind-mounts that file read-only over the repository `AGENTS.md`. This avoids a
validation-to-mount race, makes the namespace view equal to HEAD and prevents
the process from editing the instruction source.

### 2. Disable only automatic project instruction discovery

The Codex argv adds exactly one fixed
`--config project_doc_max_bytes=0`. Ambient home instruction names continue to
receive the empty read-only mask. The reviewed combined bundle continues to be
passed once as fixed `developer_instructions`; the prompt remains stdin-only.

The setting is runner-owned, not accepted from the client. Tests use the
pinned Codex debug projection to prove one explicit marker and zero automatic
project markers without retaining prompt or instruction content.

### 3. Preserve the worktree-write boundary without instruction mutability

The whole exact worktree remains the only project-write bind, but the later
file-level read-only bind narrows `AGENTS.md`. Git metadata, common-dir identity
and all existing Bubblewrap/network/systemd restrictions remain unchanged.
Unknown, changed, symlinked or empty instruction sources still reject before
the process starts.

### 4. Test the observable namespace contract

Focused tests shall assert:

- the project and ambient mask paths are distinct;
- the project projection contains the validated bytes and is mode-bounded;
- command construction binds it read-only at the tracked path;
- automatic discovery is disabled exactly once and explicit injection occurs
  exactly once;
- simulated sandbox inspection reports exact file bytes and clean Git;
- write attempts cannot mutate the projected or host instruction source;
- new, resumed and image-bearing command forms retain the same boundary;
- temporary projections are removed on success, failure, timeout and
  interruption.

### 5. Roll out only through an exact predecessor/successor transaction

The candidate bundle will require the installed runner, service, registry,
WorkSession 19 ownership and zero non-terminal executions to match the sealed
predecessor. It will stage the successor, retain an exact rollback copy,
replace only the reviewed runner/install checksum set, restart only
`atenea-agent-run-worker-v1.service`, and verify health, hashes, Git, slots,
admission, backup and RAID. Any mismatch triggers exact rollback; ambiguous or
foreign state stops before mutation.

Installation and the later real in-product canary are separate human gates.

## Risks / Trade-offs

- [Automatic and explicit instructions both apply] -> fixed discovery bound
  zero plus pinned debug-projection and argv-count regression tests.
- [Projected bytes race after validation] -> mount an execution-owned copy of
  the already-validated bytes, not the mutable worktree source.
- [Codex modifies the instruction contract] -> file-level read-only bind over
  the writable worktree; test failed write and unchanged host SHA-256.
- [Global or project override enters] -> retain empty ambient masks and reject
  repository override/`.codex` sources before execution.
- [Worker install disrupts live ownership] -> require terminal execution set,
  exact WorkSession 19 fingerprints, finite service restart and automatic
  predecessor rollback under separate authorization.

## Migration Plan

1. Record the sanitized reproduction, exact clean host worktree and pinned
   Codex discovery behavior; strict-validate and publish the specification.
2. Add the focused failing regression for the old empty repository mask.
3. Implement the exact immutable project projection and pass focused tests.
4. Run complete worker, installer, syntax, privacy and non-impact validation.
5. Build and seal the AX42 predecessor/successor/rollback bundle.
6. Stop for separate exact installation authorization.
7. After installation, stop again for an operator-created real WorkSession 19
   prompt; never synthesize or read that prompt/response.
8. Seal final non-impact evidence and archive only after the canary proves the
   false dirty state is gone.

## Open Questions

No implementation choice remains open. AX42 installation and a new real
AgentRun remain separate explicit operator gates.
