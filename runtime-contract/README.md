# Project runtime manifest contract

`project-runtime-v1.schema.json` is the machine-readable contract used before a
project can be activated on the AX42 worker. Version 1 manifests are JSON
documents. YAML may be added later only with a parser that preserves the same
JSON data model and validation result.

`development-change-workspace-v1.request.schema.json` and
`development-change-workspace-v1.response.schema.json` define the stable HTTP
payload boundary used by `app` to provision, inspect, and reconcile an exact
development-change worktree on AX42.

`development-change-branch-publication-v1.request.schema.json` and its response
schema bind one server-derived DevelopmentChange, source revision/fingerprint,
workspace ownership fingerprint, branch, and project remote to an exact pushed
head. The response exposes the head and a sanitized receipt, never a workspace
path, credential, remote URL, host, or Git command.

`agent-run-project-codex-v4.request.schema.json` and its result schema are the
additive AgentRun contract for a previously provisioned development-change
workspace. The request binds the immutable dispatch to the change key, database
WorkSession identity, remote session UUID, exact workspace identity, source
revision and both source/ownership fingerprints. It contains no workspace path,
host selector, slot, shell or command authority. Versions v1-v3 remain valid
legacy WorkSession-owned contracts. A successful v4 result binds the
worker-derived post-run source and workspace-ownership fingerprints to the
exact change, WorkSession, workspace, and execution, and reports only whether
the resulting worktree is dirty.

`closed-validation-start-v1.request.schema.json`,
`closed-validation-inspect-v1.request.schema.json`, and
`closed-validation-cancel-v1.request.schema.json` define the versioned durable
broker operations. `closed-validation-operation-v1.schema.json` is their common
sanitized state envelope. The immutable operation binds the project,
WorkSession workspace, source revision and fingerprint, and one of the four
reviewed symbolic validation definitions. The predecessor synchronous worker
route remains available as a compatibility adapter.

The schema deliberately:

- uses argument arrays instead of shell command strings;
- accepts only repository-relative paths;
- identifies secrets by name and never accepts secret values;
- exposes only declared internal ports;
- models Compose and legacy Tomcat runtimes without privileged, host namespace,
  device, daemon-socket or arbitrary mount fields;
- requires lifecycle, health, preview, browser, artifact and workload
  declarations.

`examples/` contains safe contract examples. `fixtures/invalid/` is a negative
corpus; every document in that directory must fail schema validation for the
reason encoded in its filename. These are contract fixtures, not runnable
projects and not onboarding approval for a real repository.

The session-level companion contract is documented in
`session-runtime-v1.md`. Its two schemas define allocation identity and the
stable `dev --json` state/error envelope without implementing the runtime
manager.
