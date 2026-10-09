#!/usr/bin/env python3
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("source_sync", Path(__file__).with_name("atenea-project-source-sync-v1.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SourceSyncTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="atenea-source-sync-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mirror = self.root / "mirror.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.mirror)], check=True)
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test",
               "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        def git(*args, data=None):
            return subprocess.check_output(["git", f"--git-dir={self.mirror}", *args], input=data, env=env).decode().strip()
        tree = git("mktree", data=b"")
        self.old = git("commit-tree", tree, data=b"old\n")
        self.new = git("commit-tree", tree, "-p", self.old, data=b"new\n")
        git("update-ref", sync.REF, self.old)
        self.before = json.dumps({"commit": self.old, "retained": "unchanged"}).encode()
        self.after = self.before.replace(self.old.encode(), self.new.encode())
        self.config = self.root / "config.json"
        self.config.write_bytes(self.before)
        self.config.chmod(0o644)
        self.journal = self.root / "journal"
        self.journal.mkdir(mode=0o700)
        self.state = {"current": "0.157.0", "previous": "0.145.0", "ws21": "clean"}
        self.service_calls = []
        original_command = sync.command
        def command(args, env=None):
            if args[0] == "/usr/bin/systemctl":
                self.service_calls.append(args)
                return ""
            return original_command(args, env)
        for name, value in {"MIRROR": self.mirror, "CONFIG": self.config, "JOURNAL": self.journal,
                            "RECORD": self.journal / "operation-v1.json", "BACKUP": self.journal / "config-before.json",
                            "OLD": self.old, "NEW": self.new, "OLD_HASH": sync.digest(self.before),
                            "NEW_HASH": sync.digest(self.after)}.items():
            item = patch.object(sync, name, value)
            item.start()
            self.addCleanup(item.stop)
        for name, value in (("trusted", lambda path, mode=None: path), ("fetch", Mock()),
                            ("check", self.check), ("preserved", lambda: dict(self.state)),
                            ("command", command)):
            item = patch.object(sync, name, value)
            item.start()
            self.addCleanup(item.stop)

    def check(self):
        ref = sync.git("rev-parse", "--verify", sync.REF)
        if self.config.read_bytes() != (self.before if ref == self.old else self.after if ref == self.new else b""):
            raise sync.Rejected("CONFIG_REF_MISMATCH")

    def test_exact_promotion_preserves_only_commit(self):
        result = sync.apply_locked()
        self.assertEqual("SUCCEEDED", result["state"])
        self.assertEqual(self.new, sync.git("rev-parse", sync.REF))
        self.assertEqual(self.after, self.config.read_bytes())
        self.assertEqual(self.before, sync.BACKUP.read_bytes())
        self.assertEqual(self.state, result["preserved"])
        self.assertEqual(0o600, sync.RECORD.stat().st_mode & 0o777)
        self.assertEqual(["stop", "start"], [args[1] for args in self.service_calls])
        self.assertTrue(all(args[2] == sync.SERVICE for args in self.service_calls))

    def test_idempotence_keeps_operation_and_no_second_fetch(self):
        first = sync.apply_locked()
        receipt = sync.RECORD.read_bytes()
        second = sync.apply_locked()
        self.assertEqual(first, second)
        self.assertEqual(receipt, sync.RECORD.read_bytes())
        sync.fetch.assert_called_once()
        self.assertEqual(2, len(self.service_calls))

    def test_foreign_config_and_moved_ref_are_rejected_before_effects(self):
        self.config.write_bytes(self.before + b"\n")
        with self.assertRaises(sync.Rejected): sync.apply_locked()
        sync.fetch.assert_not_called()
        self.assertFalse(sync.RECORD.exists())
        self.config.write_bytes(self.before)
        sync.git("update-ref", sync.REF, self.new, self.old)
        with self.assertRaises(sync.Rejected): sync.apply_locked()
        self.assertEqual(self.before, self.config.read_bytes())

    def test_active_operation_or_ws19_drift_fails_closed(self):
        with patch.object(sync, "check", side_effect=sync.Rejected("ACTIVE_OR_FOREIGN_WORKSPACE")):
            with self.assertRaises(sync.Rejected): sync.apply_locked()
        sync.fetch.assert_not_called()
        self.assertEqual(self.old, sync.git("rev-parse", sync.REF))
        self.assertEqual([], self.service_calls)

    def test_source_fetch_must_match_fixed_reviewed_main(self):
        with patch.object(sync, "fetch", side_effect=sync.Rejected("AUTHORITATIVE_MAIN_MOVED")):
            with self.assertRaises(sync.Rejected): sync.apply_locked()
        self.assertEqual(self.before, self.config.read_bytes())
        self.assertEqual(self.old, sync.git("rev-parse", sync.REF))

    def test_late_config_drift_rejected(self):
        sync.fetch.side_effect = lambda: self.config.write_bytes(self.before + b"\n")
        with self.assertRaises(sync.Rejected): sync.apply_locked()
        self.assertFalse(sync.RECORD.exists())
        self.assertEqual(self.old, sync.git("rev-parse", sync.REF))

    def test_postcondition_failure_restores_ref_and_config(self):
        checks = iter([None, None, sync.Rejected("HEALTH_FAILED"), None])
        def check():
            value = next(checks)
            if value: raise value
        with patch.object(sync, "check", side_effect=check):
            with self.assertRaisesRegex(sync.Rejected, "POSTCONDITION_FAILED_RESTORED"):
                sync.apply_locked()
        self.assertEqual(self.before, self.config.read_bytes())
        self.assertEqual(self.old, sync.git("rev-parse", sync.REF))
        self.assertEqual("ROLLED_BACK", json.loads(sync.RECORD.read_bytes())["state"])
        with self.assertRaisesRegex(sync.Rejected, "TERMINAL_OPERATION_REQUIRES_REVIEW"):
            sync.apply_locked()

    def test_interrupted_half_commit_restored_without_repeating(self):
        original = sync.save
        def interrupted(path, data, mode=0o600):
            if path == self.config: raise KeyboardInterrupt()
            return original(path, data, mode)
        with patch.object(sync, "save", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt): sync.apply_locked()
        self.assertEqual(self.new, sync.git("rev-parse", sync.REF))
        self.assertEqual("APPLYING", sync.load()["state"])
        with self.assertRaisesRegex(sync.Rejected, "INTERRUPTED_OPERATION_RESTORED"):
            sync.apply_locked()
        self.assertEqual(self.old, sync.git("rev-parse", sync.REF))
        self.assertEqual(self.before, self.config.read_bytes())
        sync.fetch.assert_called_once()

    def test_completed_evidence_drift_is_rejected(self):
        sync.apply_locked()
        self.state["ws21"] = "changed"
        with self.assertRaisesRegex(sync.Rejected, "COMPLETED_STATE_CHANGED"):
            sync.apply_locked()

    def test_foreign_durable_identity_rejected(self):
        sync.apply_locked()
        record = sync.load()
        record["newCommit"] = "a" * 40
        sync.persist(record)
        with self.assertRaisesRegex(sync.Rejected, "DURABLE_IDENTITY_INVALID"):
            sync.apply_locked()

    def test_cli_rejects_arbitrary_target_and_arguments(self):
        with patch.object(sync.os, "geteuid", return_value=0):
            for args in (["--apply", self.new], ["--apply", "/tmp/foreign"], ["--execute"], []):
                with patch.object(sys, "argv", ["source-sync", *args]):
                    with self.assertRaisesRegex(sync.Rejected, "ROOT_FIXED_OPERATION_REQUIRED"):
                        sync.main()

    def test_exclusive_guard_excludes_admission_and_other_publishers(self):
        lock = self.root / "admission.lock"
        lock.touch()
        lock.chmod(0o640)
        with patch.object(sync, "LOCK", lock):
            with lock.open("rb") as reader:
                fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    with sync.guard(): self.fail("active admission was bypassed")
            with sync.guard():
                with lock.open("rb") as reader:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)


class FetchContractTest(unittest.TestCase):
    def test_foreign_and_symlink_authority_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "token"
            path.write_text("not-a-real-token")
            path.chmod(0o666)
            with self.assertRaises(sync.Rejected): sync.trusted(path, 0o600)
            link = Path(root) / "link"
            link.symlink_to(path)
            with self.assertRaises(sync.Rejected): sync.trusted(link, 0o600)

    def test_fixed_read_token_and_fetch_does_not_update_a_ref(self):
        token = Mock()
        token.read_text.return_value = "read-token"
        calls = []
        def git(*args, env=None):
            calls.append((args, env))
            return sync.NEW if args[0] == "rev-parse" else ""
        with patch.object(sync, "trusted", return_value=token), patch.object(sync, "git", side_effect=git):
            sync.fetch()
        self.assertEqual(("fetch", "--no-tags", "--refmap=", sync.REPOSITORY, "refs/heads/main"), calls[0][0])
        self.assertEqual("0", calls[0][1]["GIT_TERMINAL_PROMPT"])
        self.assertNotIn("read-token", str(calls[0][0]))
        self.assertEqual("merge-base", calls[-1][0][0])

    def test_wrong_fetch_head_rejected_without_updating_a_ref(self):
        token = Mock()
        token.read_text.return_value = "read-token"
        with patch.object(sync, "trusted", return_value=token), patch.object(sync, "git", return_value="a" * 40):
            with self.assertRaisesRegex(sync.Rejected, "AUTHORITATIVE_MAIN_MOVED"):
                sync.fetch()


if __name__ == "__main__":
    unittest.main()
