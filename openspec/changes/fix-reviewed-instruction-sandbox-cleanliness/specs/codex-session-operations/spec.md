## ADDED Requirements

### Requirement: Git-clean immutable reviewed instruction projection

For every real-project AgentRun, the runner SHALL validate the exact tracked
repository instruction bytes and combined reviewed bundle before execution.
Inside the execution sandbox the tracked repository instruction path MUST
contain those exact bytes, MUST be read-only to the workload and MUST NOT make
the accepted source tree appear modified. Automatic global/project instruction
discovery SHALL remain excluded through fixed runner-owned configuration, and
the exact reviewed combined bundle SHALL be injected once as developer
instructions. No caller may select a rule source, discovery setting, path,
override or instruction content.

#### Scenario: Exact new AgentRun inspects its source

- **WHEN** the runner starts Codex for a clean accepted real-project worktree
- **THEN** the sandbox sees `AGENTS.md` byte-identical to `HEAD:AGENTS.md`, Git
  remains clean and the explicit reviewed bundle is present exactly once

#### Scenario: Resumed or image-bearing AgentRun starts

- **WHEN** the runner resumes an accepted thread or supplies exact retained
  images
- **THEN** it preserves the same immutable instruction projection and does not
  enable automatic discovery, ambient rules or caller-selected configuration

#### Scenario: Workload attempts to change repository instructions

- **WHEN** the Codex process attempts to write the projected tracked
  instruction file
- **THEN** the sandbox denies the write and the host worktree blob, index,
  status and instruction SHA-256 remain unchanged

#### Scenario: Exact single-application control is unavailable

- **WHEN** the pinned Codex version cannot prove automatic discovery disabled
  while preserving the explicit reviewed bundle
- **THEN** validation blocks the candidate before installation or real dispatch
  and retains the existing worker unchanged
