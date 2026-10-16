# Managed editable files and private control records

The installed source mediator and Codex sandbox have different, fixed Unix
identities. `atenea-worker` owns the Change root, worktree root, ownership and
publication records, preparation journals and refs. The sandbox executes as
`jose:atenea`; newly created/replaced Git files and nested directories therefore
legitimately belong to `jose`, not necessarily `atenea-worker`.
The sandbox fixes `UMask=0007`: future ordinary files/directories retain shared
group access (0660/0770), without adding world access. Existing safe 0664 Git
files remain usable; no installed file is chmodded as a recovery shortcut.

Source preparation/continuation recognizes only those two installed actors for
editable paths, resolving their IDs from the OS account authority. The mediator
must itself be `atenea-worker`, with its expected `atenea` group; the sandbox
writer must be a distinct non-root `jose` account belonging to `atenea`. No
request, environment override, repository file or package can select actors.
The installer pins both programs; a contract test checks the actual sandbox
command against the mediator's actor constants.

Every retained file still must occur in the exact original/prepared Git tree,
with matching bytes and executable bit, shared group, one hardlink, bounded size
and safe permissions. Symlinks, unrelated users/groups, extra files, deliberate
later edits, special bits and world-writable paths fail closed. Reads use
`O_NOFOLLOW` and compare inode/metadata before and after reading. Nested editable
directories may belong to either fixed actor, but their group/modes remain
checked. The worktree and Change roots, private records, config and credentials
do **not** adopt the two-actor rule.

No ownership is repaired or normalized; there is no `chown`, new sudoers rule,
arbitrary actor allowlist, root runner, or identity supplied by a client. A
retained `PREPARED` operation resumes through its normal authenticated recovery
with the same immutable target, IDs and receipts. `INSPECT` stays read-only.

Validation:

```bash
python3 -B ops/worker/test-development-change-editable-actors-v1.py ActorContractTest
sudo python3 -B ops/worker/test-development-change-editable-actors-v1.py DistinctActorRecoveryTest
```

The root-only fixture uses existing nonprivileged accounts and real kernel UID
switches, not mocked `lstat` results, exclusively inside its synthetic `mkdtemp`
Git/workspace. It reproduces the former worker-only rejection, recovers the same
`PREPARED` operation, lets the other actor resolve conflicts, and finalizes the
same branch without changing any owner manually. Foreign-user/group/path,
symlink/hardlink, later edit and private-root/journal rejection are covered.
CI runs the distinct-UID suite explicitly, without skipping it. No real worker,
GitHub, Codex execution or production workspace is used by these tests.
