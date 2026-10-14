# DevelopmentChange creation source admission

`PROVISION` now imports a missing, approved creation base through the existing
trusted workspace mediator. No new API, capability, caller path, command,
credential, version or mutable target is introduced.

After validating the exact request, roots, remote and absence of both workspace
and change-owned branch, a new workspace must have source revision zero,
`sourceCommit == baseCommit` and no dirty fingerprint. A base already in the
retained canonical ancestry needs no network. Otherwise the mediator observes
only `refs/heads/main` in the fixed Atenea GitHub repository, imports that exact
observed object ID using the existing worker-owned SSH credential/trust store,
and proves both retained canonical source and requested base are ancestors.
It rechecks the observed main and all mirror refs before creating anything.

The fetch imports objects only: no tags, refmap, recursive submodules,
`FETCH_HEAD`, automatic maintenance or mutable ref target. GitHub main movement,
unrelated/cached unmerged source, ambiguous observations, unsafe credentials,
local URL redirects/external Git commands or
foreign/partial resources fail closed. Objects retained by an interrupted import
do not count as approval; a base outside retained ancestry is rechecked even if
already cached. Existing workspaces never fetch, reset or rebase during replay.

The root-owned legacy project registry and `refs/remotes/origin/main` stay
unchanged. In the current v4/change-only model they are not a change's creation
base: that authority is the immutable App DevelopmentChange plus its own worker
ownership record. Advancing those legacy pins per App release is unnecessary and
would violate the independent code-deployment/configuration boundary.

For a source beyond retained ancestry, worker-owned `source-admission-v1.json`
records the App operation/idempotency IDs, request hash, immutable base, observed
GitHub main and retained mirror commit with a canonical SHA-256 seal. It is
written mode 0600 alongside the existing exact `workspace-v1.json`, never exposed
to the caller or Codex. Partial creation stays retained for normal diagnosis.
The App workspace operation and these files provide the durable evidence.

Only the fixed PROVISION mediator receives `CREDENTIALS_DIRECTORY`; INSPECT,
RECONCILE and ordinary subprocesses still do not. The existing ephemeral private
credential projection is cleaned after each network command. The bounded
PROVISION deadline covers the three bounded network calls; other operation
timeouts, sudoers, service mounts and runner behavior are unchanged.

Focused validation: `test-development-change-workspace-v1.py` covers automatic
import, captured-base preservation, cached-source revalidation, replay,
read-only observations, identity/partial rejection, main movement, evidence,
unchanged refs/FETCH_HEAD and credential isolation. The normal Platform CI now
includes this suite. Install only after review/CI through the existing worker
installer apply/verify or the managed AX42_PLATFORM publisher.

For a preexisting BLOCKED change, use the normal App workspace INSPECT action to
confirm absence and restore NOT_PROVISIONED, then PROVISION the same change.
Do not replace its immutable base, create another change/prompt or edit links,
refs, configuration or status rows manually.
