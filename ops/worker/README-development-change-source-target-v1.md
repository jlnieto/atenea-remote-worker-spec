# Pinned source retrieval for preparation and recovery

The closed source-update v1/v2 protocol is unchanged. The App owns the approved
target commit and durable operation; callers cannot supply transports, commands,
paths, refspecs or configuration. The worker's existing ownership, idle,
admission/lifecycle and workspace mutation locks still precede every effect.

A new preparation verifies the published branch against authenticated GitHub
and requires main to equal its approved target. It imports missing objects from
the fixed repository using the existing ephemeral SSH credential projection.
Fetch disables tags, refmap, FETCH_HEAD, submodules and automatic maintenance.
No configured refspec or caller-provided Git program is used. Both heads are
observed again after retrieval; creation base and retained canonical commit
must be ancestors of the observed main. Unexpected movement fails closed.

Only server-derived private refs are added, with an absent-to-exact CAS:

- `refs/atenea/source-targets/<change>/<preparation>` retains the approved target.
- `refs/atenea/source-observations/<change>/<preparation>/<commit>` retains ancestry proof.

`source-target-<preparation>-v1.json` is a sealed worker-owned 0600 record outside
the editable sandbox. Its schema is `development-change-source-target-v1.record`.
It binds the target to the exact App intent, idempotency identity, owner record
and predecessor publication. Another ref value, symlink or altered receipt is
rejected. Ref/receipt interruptions reuse only the same reviewed intent and exact
object. Private refs are GC roots; received objects alone never authorize work.

`RECOVER` may retrieve a newer observed main only as ancestry evidence: it must
contain the original approved target. The merge always consumes that original
target, not the newly observed main. A second advancement is rechecked before
each effect. Completed legacy preparations without a target record retain their
previous checks; read-only INSPECT never retrieves objects or creates a receipt.

The root-owned project registry, origin/main, all other existing refs, Codex
runtime, creation base and workspace ownership remain unchanged. Canonical source
is not advanced per App release. This extends the same boundary already used by
DevelopmentChange creation admission to conflict preparation and recovery.

`SOURCE_UPDATE_TARGET_UNAVAILABLE` reports bounded retrieval failure;
`SOURCE_UPDATE_TARGET_INVALID` reports unverifiable authority. Neither exposes
Git stderr or credentials. App preserves these reviewed error codes. An invalid
authority is not repaired by retrying an admin button.

Focused suites cover a missing target, private refs and unchanged canonical
source/config, interrupted fetch/pin/receipt/materialization, idempotency, main
movement, foreign branch/ref, modified/symlinked receipt, GC, continuation and
finalization of the same branch. No suite contacts a real worker or GitHub.
