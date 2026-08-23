# AGENTS

This is `jlnieto/atenea-remote-worker-spec`. It owns the Atenea worker,
runtime operations, operator tools, and machine-readable runtime contracts.
Product application code belongs in `../app`.

Keep app/platform integration protocol-based. Do not copy Spring, web,
Android, or Flyway sources into this repository.

Worker operations must remain server-owned, allowlisted, ownership-checked,
rootless where defined, and fail closed for ambiguous or foreign resources.
Never expose secrets or arbitrary shell, paths, hosts, slots, services, or
credentials through public contracts.

Validate changed JSON schemas as Draft 2020-12 and use the focused tests beside
the affected worker component.

Local edits, tests, builds, inspection, commits, push, and PR creation do not
require an Atenea-specific gate. AX42 installation/configuration/restarts,
mutations affecting active workloads, infrastructure or secret changes,
restore, destructive cleanup, deployment, and rollback require explicit
authorization.
