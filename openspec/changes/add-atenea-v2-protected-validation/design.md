## Context

The accepted AgentRun sandbox correctly has no Docker socket. AX42 already has
four rootless slots, two heavy permits, runtime manifests, Playwright and
ownership-safe infrastructure. V2 should broker those capabilities with a
closed protocol rather than weaken the sandbox.

Dependencies: M0 control, M1 security, M2 changes and M3 artifacts.

## Goals / Non-Goals

**Goals:**

- Build/test Android, backend, web and browser against exact source.
- Keep shell, Docker and production authority outside Codex/backend clients.
- Make runs durable, idempotent, cancellable and restart-recoverable.
- Separate capacity/transport from validation failure.
- Produce immutable artifact manifests and staleness projection.

**Non-Goals:**

- Publish APK, merge code or deploy production.
- Let repositories submit arbitrary command lines or images.
- Give AgentRun Docker, sudo, host paths or production network.
- Validate WorkSession 19 without a later exact authorization.

## Decisions

### 1. Symbolic validation catalog

The public API accepts only registered capability IDs. A server-owned
definition revision maps each capability/project profile to a fixed mediator,
toolchain digest, resource class, network policy, timeout and artifact rules.
Repository manifests may reference IDs but cannot define executable shell.

The existing closed `validation_operation` table is the predecessor for V2
ValidationRun and SHALL be evolved compatibly with plan/remote fields where
safe. The older `project_verification_run` path remains legacy/read-only and is
not used to execute a V2 plan; V2 does not create a third competing result
model.

### 2. Validation plan freezes all inputs

A plan contains change/source fingerprint, required checks, definition
revisions and policy revision. Its SHA-256 is immutable. A run can be reused
only if every canonical input matches and policy permits cached evidence.

### 3. Rootless broker boundary

AX42's validation service owns admission and exact slots. It receives a typed
request from Atenea, verifies ownership and invokes fixed mediators. The
backend does not mount a Docker socket for V2, and AgentRun cannot reach the
broker credentials/socket directly.

### 4. Durable run lifecycle

Runs use `QUEUED/STARTING/RUNNING/CANCELLING/RECONCILING` and terminal
`SUCCEEDED/FAILED/BLOCKED/CANCELLED`. Remote execution identity, lease,
revision and receipt are persisted. Unknown outcomes reconcile by inspection.

### 5. Closed first profile

The first Atenea-only profile includes backend tests, web tests/build, Android
tests/build and Playwright acceptance where applicable. The Android build is
the first functional canary. It produces an unsigned/test APK artifact and
reports; it never publishes them.

## Risks / Trade-offs

- [Repo needs a new command] -> review and version a new server-side definition
  instead of accepting shell dynamically.
- [Toolchain image supply-chain drift] -> pin digest, retain provenance/SBOM
  and require explicit update operation.
- [Build exhausts worker] -> normal/heavy admission, quotas and finite
  cancellation.
- [Response lost after completion] -> inspect remote operation ID and exact
  receipt; never rerun blindly.
- [Old verifier remains privileged] -> V2 never routes through it and later
  retirement requires independent evidence.

## Migration Plan

1. Add disabled validation plan/run/check persistence and APIs.
2. Install the broker and exact toolchains on AX42 under H2, with no project
   enabled.
3. Run synthetic contract/capacity/restart tests.
4. Enable shadow planning only for Atenea, then one synthetic validation.
5. Under H3, run the exact first Atenea validation canary without prompts.
6. Observe before exposing UI actions.

Rollback removes Atenea from validation policy, disables the global gate,
reconciles nonterminal runs, stops only owned validation resources and restores
the exact broker predecessor. Artifacts and records remain retained.

## Open Questions

Exact toolchain digests are deliberately selected at implementation entry, not
frozen in this planning document.
