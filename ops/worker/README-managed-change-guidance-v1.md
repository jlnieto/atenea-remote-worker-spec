# Managed change guidance v1

The existing project-codex-v4 runner appends a fixed trusted execution context
after verifying the DevelopmentChange worktree and reviewed repository bytes.
`ATENEA_MANAGED_CHANGE` is derived by the runner, never requested by a client.
The request/result schemas and existing ownership/catalog/source/sandbox checks
remain unchanged. Other workload kinds do not receive this context.

The manual workspace's github/main versus mirror origin/main rules are not a
requirement for this worker-owned bare mirror. The context does not grant fetch,
push, ref edits, Git configuration changes, host commands or deployment authority.
It preserves the reviewed AGENTS.md bytes and their non-topology restrictions.
An actual ownership or instruction integrity conflict still fails closed.

Codex should distinguish an unrequested validation from a failed validation and
explain the next mobile step. Completing a turn is not proof of PASS or deployment.
For operational questions, point to App's `Ayuda con este cambio`; do not create
another task, session or change. The helper is App-owned and does not use this
runner to answer questions or recover the worker.

Focused checks: reviewed bytes unchanged, fixed context after ownership checks,
no caller-selected mode/commands, existing instruction rejection and sandbox tests.
Installation is through the existing approved Platform installer, with separate
authorization. This source change itself installs/restarts/retries nothing.
