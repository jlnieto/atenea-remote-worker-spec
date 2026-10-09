# Managed Codex execution access

The release owner is `atenea-worker:atenea`; the project runner executes as
`jose:atenea` inside the existing read-only Bubblewrap mount of managed
`current`. Packages must be traversable/readable/executable by that group,
without group-write permission. Canonical installed modes are directories
and executables `0750`, data files `0640`. The staged package remains owned
by the staging identity; credentials and operation journals remain private.

`codex-release-stage-v1.py` normalizes its fully verified private extracted
tree before publishing a stage. Its archive digest and file bytes remain
unchanged. This does not modify old stage receipts or activate a release.

For the already activated, exact 0.157.0 candidate, the installer owns the
closed `codex-release-runtime-access-v1.py` recovery. It accepts only
`plan`, `apply`, or `verify`, never paths, versions or commands. It requires
the retained current/previous targets, registry candidate/plan, archive
digest, sealed file manifest, successful stage/activation, expected owners
and modes, and no active AgentRuns/validations. Foreign files, hashes,
symlinks, hardlinks, unsafe modes and unknown states fail closed.

The normal Platform installer apply executes this recovery after stopping
the worker, under the existing release publisher admission guard. It stores
a root-owned durable receipt outside the protected Codex inventory tree at
`/srv/atenea/release-v1/codex-runtime-access-v1.json`, preserving all historical
Codex JSON evidence and links. A repeated apply adopts the same operation.
If the identity/version check fails, it restores the original exact modes
and records `ROLLED_BACK`; it does not activate, change ownership or retry.

The check executes only `current/bin/codex --version` as `jose:atenea` in
the read-only namespace. It mounts no auth directory, project, prompt,
other release or inventory and does not make a Codex turn or canary.
The existing installer verify repeats it. Successful process/version
verification is still not functional AgentRun or mobile acceptance.

Focused tests include an actual separate-UID Bubblewrap check: the private
package is inaccessible before normalization and executable afterward,
while writes remain denied. Existing activation records/protocol fields
are not rewritten or renamed by this correction.
