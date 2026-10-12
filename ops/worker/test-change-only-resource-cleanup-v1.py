import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("cleanup", Path(__file__).with_name("change-only-resource-cleanup-v1.py"))
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
ACTUAL_WORKER_REPLACEMENT = c.replace_fixed_worker_state


def git(path, *arguments):
    return subprocess.check_output(["/usr/bin/git", "-c", "user.name=Synthetic cleanup test",
        "-c", "user.email=cleanup@atenea.test", *arguments], cwd=path, env=c.p.ENV,
        stderr=subprocess.DEVNULL, text=True).strip()


class FakeHost(c.Host):
    """Only ephemeral files/real Git, no service, Docker or remote requests."""
    def __init__(self, manifest):
        super().__init__(manifest)
        self.events = []; self.resources = copy.deepcopy(manifest["runtimeResources"])
        self.running = [r["id"] for r in self.resources if r["kind"] == "container"]
        self.maintenance = True; self.drift = False; self.fail_remove_ack = False

    def fenced(self):
        c.p.require(self.maintenance, "WORKER_MAINTENANCE_REQUIRED")

    def protected(self):
        real = c.p.WORKSPACES / "changes" / c.p.REAL_CHANGE
        return {"real": c.p.digest(c.canonical(c.inventory_tree(real))),
                "refs": {n: {r: h for r, h in refs.items() if r not in self.manifest["retireBranchRefs"][n]}
                         for n, refs in self.refs().items()}, "drift": self.drift,
                "codexCurrent": "releases/0.157.0", "codexPrevious": "releases/0.145.0"}

    def runtime_observation(self):
        return {"targets": copy.deepcopy(self.resources), "protected": [{"real-service": True}],
                "runningTargets": self.running.copy(),
                "allIdentifiers": [(r["slot"], r["kind"], r["id"]) for r in self.resources]}

    def docker(self, item, action):
        self.events.append((action, item["kind"], item["id"]))
        if action == "stop":
            if item["id"] in self.running: self.running.remove(item["id"])
        else:
            current = next((r for r in self.resources if r["id"] == item["id"]), None)
            if current:
                self.resources.remove(current)
                if item["kind"] == "volume": shutil.rmtree(item["mountpoint"])
                if self.fail_remove_ack:
                    self.fail_remove_ack = False
                    raise c.p.Refused("SYNTHETIC_LOST_REMOVE_ACK")


class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="change-only-physical-test-")
        self.root = Path(self.temporary.name)
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch.object(c.p, "WORKSPACES", self.root / "workspaces"))
        self.stack.enter_context(patch.object(c, "MIRRORS", self.root / "repositories"))
        self.stack.enter_context(patch.object(c.p, "MIRRORS", self.root / "repositories"))
        self.stack.enter_context(patch.object(c.p, "EXECUTIONS", self.root / "executions.json"))
        self.stack.enter_context(patch.object(c.p, "CONFIG", self.root / "project-config.json"))
        self.stack.enter_context(patch.object(c, "REGISTRY", self.root / "registry.json"))
        self.stack.enter_context(patch.object(c, "authority", self.synthetic_authority))
        self.stack.enter_context(patch.object(c, "replace_fixed_worker_state", self.synthetic_state_replacement))
        for path in (c.p.WORKSPACES / "sessions", c.p.WORKSPACES / "changes", c.MIRRORS): path.mkdir(parents=True)
        seed = self.root / "seed"; seed.mkdir()
        git(seed, "init", "--initial-branch=main")
        (seed / "tracked.txt").write_text("synthetic source\n")
        git(seed, "add", "tracked.txt"); git(seed, "commit", "-m", "Synthetic source")
        self.head = git(seed, "rev-parse", "HEAD")
        git(seed, "clone", "--bare", str(seed), str(c.MIRRORS / "atenea.git"))
        git(seed, "clone", "--bare", str(seed), str(c.MIRRORS / "beautips.git"))
        self.manifest = {"reviewedRoots": [], "mirrorConfigurationSha256": {},
            "retireBranchRefs": {"atenea.git": {}, "beautips.git": {}}, "supplementalTrialPaths": [],
            "trialRemoteSessionIds": {}, "trialSessionIds": [4, 19], "trialChangeKeys": ["synthetic-trial-change"]}
        c.p.CONFIG.write_bytes(c.canonical({"syntheticFixture": True, "projectId": "atenea"}))
        self.manifest["projectConfigurationSha256"] = c.file_hash(c.p.CONFIG)
        self.add_workspace("changes", c.p.REAL_CHANGE, "atenea", "refs/heads/atenea/change-" + c.p.REAL_CHANGE, False)
        self.add_workspace("sessions", "6547081d-895e-4be1-a8fd-d115b7743cdf", "atenea", "refs/heads/atenea/session-6547081d-895e-4be1-a8fd-d115b7743cdf", True)
        self.add_workspace("sessions", "2ac2a5fd-2981-49cf-8fac-8132e46a2d64", "beautips", "refs/heads/ax42-beautips-wip-preservation-2ac2a5fd", True)
        self.dirty_tree = c.p.WORKSPACES / "sessions/6547081d-895e-4be1-a8fd-d115b7743cdf/atenea"
        (self.dirty_tree / "uncommitted.txt").write_text("synthetic uncommitted work\n")
        self.manifest["reviewedRoots"][1]["dirty"] = True
        for name in self.manifest["retireBranchRefs"]:
            self.manifest["mirrorConfigurationSha256"][name] = c.file_hash(c.MIRRORS / name / "config")
        state = {"workerId": "ax42-01", "protocol": "agent-run-worker/v1", "unactivatedWorkspaceReleases": {},
            "validations": {"real-validation": {"workspaceIdentity": "remote:ax42-01:change:" + c.p.REAL_CHANGE, "state": "SUCCEEDED"}},
            "executions": {"real": {"status": "SUCCEEDED", "workspaceIdentity": "remote:ax42-01:change:" + c.p.REAL_CHANGE},
                           "trial": {"status": "FAILED", "workspaceIdentity": "remote:ax42-01:work-session:synthetic-trial"}}}
        c.p.EXECUTIONS.write_bytes(c.canonical(state)); c.p.EXECUTIONS.chmod(0o600)
        self.manifest["workerStateSha256"] = c.file_hash(c.p.EXECUTIONS)
        registry = {"projectId": "beautips", "selectionEnabled": True, "executionEnabled": True, "workspaces": {"synthetic-trial": {}}}
        c.REGISTRY.write_bytes(c.canonical(registry)); c.REGISTRY.chmod(0o600)
        final = {**registry, "selectionEnabled": False, "executionEnabled": False, "workspaces": {}}
        self.manifest["beautipsRegistryRetirement"] = {"before": c.file_hash(c.REGISTRY), "after": c.p.digest(c.canonical(final)), "final": final}
        volume = self.root / "volume-data"; volume.mkdir(); (volume / "database.bin").write_bytes(b"synthetic persistent data")
        self.manifest["runtimeResources"] = [{"slot": 4, "kind": "container", "id": "synthetic-owned-container"},
                                            {"slot": 4, "kind": "volume", "id": "synthetic-owned-volume", "mountpoint": str(volume)}]
        self.host = FakeHost(self.manifest)
        self.archive = self.root / "archive"; self.receipt = self.root / "receipt.json"
        self.task = c.Cleanup(self.host, self.archive, self.receipt)

    def synthetic_authority(self, path, directory=False):
        s = path.lstat()
        self.assertFalse(path.is_symlink()); self.assertEqual(os.getuid(), s.st_uid)
        self.assertFalse(s.st_mode & 0o022)

    def synthetic_state_replacement(self, value, expected):
        self.assertEqual(expected, c.file_hash(c.p.EXECUTIONS))
        c.p.EXECUTIONS.write_bytes(c.canonical(value))

    def add_workspace(self, kind, identity, project, branch, trial):
        root = c.p.WORKSPACES / kind / identity; root.mkdir()
        mirror = c.MIRRORS / (project + ".git")
        git(mirror, "worktree", "add", "-b", branch.removeprefix("refs/heads/"), str(root / project), "main")
        record = root / "workspace-v1.json"; record.write_text(json.dumps({"syntheticFixture": True, "sessionId": identity}))
        record.chmod(0o600)
        self.manifest["reviewedRoots"].append({"kind": kind, "id": identity, "projectId": project,
            "mirrorName": project + ".git", "disposition": "TRIAL" if trial else "PRESERVE", "retirementAuthorized": trial,
            "records": {record.name: {"sha256": c.file_hash(record), "uid": os.getuid(), "mode": "0o600"}},
            "head": self.head, "branch": branch, "dirty": False, "ancillaryPaths": []})
        if trial: self.manifest["retireBranchRefs"][project + ".git"][branch] = self.head

    def tearDown(self):
        self.stack.close(); self.temporary.cleanup()

    def test_exact_cleanup_archives_dirty_code_and_volumes_and_removes_authorized_beautips_branch(self):
        preserved = self.host.protected()
        result = self.task.apply()
        self.assertEqual("RELEASED", result["state"])
        self.assertEqual(preserved, self.host.protected())
        self.assertEqual([], self.host.resources)
        self.assertEqual({"real"}, set(json.loads(c.p.EXECUTIONS.read_bytes())["executions"]))
        self.assertFalse(json.loads(c.REGISTRY.read_bytes())["executionEnabled"])
        self.assertEqual(1, len(json.loads(c.p.EXECUTIONS.read_bytes())["validations"]))
        self.assertTrue(self.receipt.exists())
        before = self.task.journal["archives"][str(self.dirty_tree.parent)]
        self.assertTrue(any(n["path"].endswith("uncommitted.txt") for n in before["nodes"]))
        self.assertIn("stop", [a[0] for a in self.host.events])
        self.assertEqual(2, sum(a[0] == "remove" for a in self.host.events))
        self.assertNotIn("refs/heads/ax42-beautips-wip-preservation-2ac2a5fd", self.host.refs()["beautips.git"])
        self.assertEqual(self.head, self.host.refs()["beautips.git"]["refs/heads/main"])
        self.task.verify()

    def test_same_operation_is_idempotent_with_identical_receipt(self):
        first = self.task.apply(); events = len(self.host.events)
        replay = c.Cleanup(self.host, self.archive, self.receipt).apply()
        self.assertEqual(first, replay); self.assertEqual(events, len(self.host.events))

    def test_no_maintenance_no_side_effects_or_backups(self):
        self.host.maintenance = False
        with self.assertRaisesRegex(c.p.Refused, "WORKER_MAINTENANCE_REQUIRED"): self.task.apply()
        self.assertFalse(self.archive.exists()); self.assertFalse(self.receipt.exists()); self.assertFalse(self.host.events)

    def test_changed_branch_or_registry_is_rejected_before_any_retirement(self):
        row = self.manifest["reviewedRoots"][2]; row["head"] = "0" * 40
        with self.assertRaisesRegex(c.p.Refused, "WORKSPACE_IDENTITY_MOVED"): self.task.apply()
        self.assertFalse(self.host.events); self.assertFalse(self.receipt.exists())

    def test_non_terminal_run_blocks_without_creating_a_release(self):
        state = json.loads(c.p.EXECUTIONS.read_bytes()); state["executions"]["trial"]["status"] = "RUNNING"
        c.p.EXECUTIONS.write_bytes(c.canonical(state)); self.manifest["workerStateSha256"] = c.file_hash(c.p.EXECUTIONS)
        with self.assertRaisesRegex(c.p.Refused, "NON_TERMINAL_OPERATION"): self.task.apply()
        self.assertFalse(self.host.events); self.assertFalse(self.receipt.exists())

    def test_backup_failure_prevents_docker_removal_git_changes_and_receipt(self):
        with patch.object(c, "archive_tree", side_effect=c.p.Refused("SYNTHETIC_BACKUP_FAILED")):
            with self.assertRaisesRegex(c.p.Refused, "SYNTHETIC_BACKUP_FAILED"): self.task.apply()
        self.assertFalse(self.host.events); self.assertTrue(self.dirty_tree.exists()); self.assertFalse(self.receipt.exists())

    def test_lost_remove_ack_is_reconciled_by_same_operation(self):
        self.host.fail_remove_ack = True
        with self.assertRaisesRegex(c.p.Refused, "SYNTHETIC_LOST_REMOVE_ACK"): self.task.apply()
        self.assertFalse(self.receipt.exists())
        result = c.Cleanup(self.host, self.archive, self.receipt).apply()
        self.assertEqual("RELEASED", result["state"])
        self.assertFalse(self.host.resources)

    def test_lost_tar_ack_is_reconciled_against_unchanged_source(self):
        original = self.task.persist
        fired = False
        def lose_ack():
            nonlocal fired
            if self.task.journal["archives"] and not fired:
                fired = True
                raise c.p.Refused("SYNTHETIC_LOST_TAR_ACK")
            original()
        with patch.object(self.task, "persist", side_effect=lose_ack):
            with self.assertRaisesRegex(c.p.Refused, "SYNTHETIC_LOST_TAR_ACK"): self.task.apply()
        self.assertFalse(self.receipt.exists())
        result = c.Cleanup(self.host, self.archive, self.receipt).apply()
        self.assertEqual("RELEASED", result["state"])

    def test_new_uncommitted_code_after_backup_is_never_deleted(self):
        original = self.host.docker
        def change_after_quiesce(item, action):
            original(item, action)
            if action == "stop": (self.dirty_tree / "late-change.txt").write_text("must survive")
        with patch.object(self.host, "docker", side_effect=change_after_quiesce):
            with self.assertRaisesRegex(c.p.Refused, "WORKTREE_CONTENT_MOVED_AFTER_BACKUP"): self.task.apply()
        self.assertTrue((self.dirty_tree / "late-change.txt").exists())
        self.assertFalse(self.receipt.exists())

    def test_actual_worker_index_replacement_preserves_owner_mode_and_data(self):
        original = c.p.read_regular
        def worker_stat(path, *args, **kwargs):
            raw, observed = original(path, *args, **kwargs)
            # Emulate only the production worker uid in this private fixture;
            # the actual write/fsync/replace and SHA CAS are not mocked.
            values = list(observed); values[4] = 999
            return raw, os.stat_result(values)
        target = c.filtered_worker_state(c.p.EXECUTIONS.read_bytes())
        with patch.object(c.p, "read_regular", side_effect=worker_stat), patch.object(c.os, "fchown") as ownership:
            ACTUAL_WORKER_REPLACEMENT(target, c.file_hash(c.p.EXECUTIONS))
            ownership.assert_called_once_with(unittest.mock.ANY, 999, os.getgid())
        self.assertEqual(target, json.loads(c.p.EXECUTIONS.read_bytes()))
        self.assertEqual(0o600, c.p.EXECUTIONS.stat().st_mode & 0o777)

    def test_wrong_worker_index_owner_is_not_accepted(self):
        with self.assertRaisesRegex(c.p.Refused, "WORKER_STATE_AUTHORITY_MOVED"):
            ACTUAL_WORKER_REPLACEMENT({}, c.file_hash(c.p.EXECUTIONS))

    def test_failed_postcondition_never_emits_release_receipt(self):
        original = self.host.remove_ref
        def corrupt_after_removal(*args):
            original(*args); self.host.drift = True
        with patch.object(self.host, "remove_ref", side_effect=corrupt_after_removal):
            with self.assertRaisesRegex(c.p.Refused, "PROTECTED_RESOURCES_MOVED"): self.task.apply()
        self.assertFalse(self.receipt.exists())

    def test_changed_archive_is_rejected_on_replay_before_more_effects(self):
        self.task.apply()
        archive = next(self.archive.glob("*.tar")); archive.write_bytes(b"changed")
        events = len(self.host.events)
        with self.assertRaisesRegex(c.p.Refused, "ARCHIVE_CHECKSUM_MISMATCH"): c.Cleanup(self.host, self.archive, self.receipt).apply()
        self.assertEqual(events, len(self.host.events))

    def test_archive_preserves_links_without_reading_their_target_and_rejects_hardlinks(self):
        source = self.root / "archive-fixture"; source.mkdir()
        secret = self.root / "unrelated"; secret.write_bytes(b"must not be copied")
        (source / "link").symlink_to(secret)
        evidence = c.archive_tree(source, self.root / "links.tar")
        self.assertEqual(["dir", "link"], [n["kind"] for n in evidence["nodes"]])
        (source / "hardlink").hardlink_to(secret)
        with self.assertRaisesRegex(c.p.Refused, "UNEXPECTED_ARCHIVE_STRUCTURE"): c.inventory_tree(source)

    def test_no_client_targets_paths_versions_commands_hosts_or_operation_id(self):
        for mode in ("plan", "apply", "verify"): c.parse_arguments(["--" + mode])
        for args in (["--apply", "--path", "/tmp"], ["--apply", "--command", "id"], ["--apply", "--version", "1"],
                     ["--apply", "--host", "foreign"], ["--apply", "--operation-id", "another"], ["--ap"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): c.parse_arguments(args)

    def test_foreign_docker_identity_is_never_removed(self):
        item = self.manifest["runtimeResources"][0]
        observer = {"targets": [], "allIdentifiers": [(4, "container", item["id"])], "runningTargets": []}
        with patch.object(self.host, "runtime_observation", return_value=observer), patch.object(c.p, "command") as command:
            with self.assertRaisesRegex(c.p.Refused, "RUNTIME_OWNERSHIP_MOVED"): c.Host.docker(self.host, item, "remove")
            command.assert_not_called()

    def test_mount_order_is_not_ownership_drift_but_changed_mounts_are_rejected(self):
        first = {"kind": "container", "slot": 4, "id": "synthetic", "mounts": [
            {"Type": "volume", "Name": "first", "Destination": "/first", "RW": True},
            {"Type": "volume", "Name": "second", "Destination": "/second", "RW": True}]}
        second = copy.deepcopy(first); second["mounts"].reverse()
        self.assertEqual(c.normalized_resources([first]), c.normalized_resources([second]))
        second["mounts"][0]["Name"] = "foreign"
        self.assertNotEqual(c.normalized_resources([first]), c.normalized_resources([second]))


if __name__ == "__main__": unittest.main()
