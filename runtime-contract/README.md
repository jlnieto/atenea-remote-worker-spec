# Project runtime manifest contract

`project-runtime-v1.schema.json` is the machine-readable contract used before a
project can be activated on the AX42 worker. Version 1 manifests are JSON
documents. YAML may be added later only with a parser that preserves the same
JSON data model and validation result.

`development-change-workspace-v1.request.schema.json` and
`development-change-workspace-v1.response.schema.json` define the stable HTTP
payload boundary used by `app` to provision, inspect, and reconcile an exact
development-change worktree on AX42.

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
