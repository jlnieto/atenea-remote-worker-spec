#!/usr/bin/env python3
"""Focused kernel-permission regression; fixtures only, no worker/DB/run mutation."""
import importlib.util
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SPEC = importlib.util.spec_from_file_location("validation_slot_staging", Path(__file__).with_name("atenea-validation-v1.py"))
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class StagingContractTest(unittest.TestCase):
    def test_fixed_root_and_closed_docker_environment(self):
        self.assertEqual(Path("/srv/atenea/validation-runtime-v1"), RUNNER.RUNTIME_ROOT)
        client = RUNNER.RUNTIME_ROOT / str(uuid.uuid4()) / "docker-client"
        command = RUNNER.docker_slot_prefix("atenea-slot1", 1101, Path("/run/user/1101/docker.sock"), client)
        self.assertEqual([
            "/usr/sbin/runuser", "-u", "atenea-slot1", "--", "/usr/bin/env", "-i",
            "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "HOME=/var/lib/atenea-slots/slot1",
            "XDG_RUNTIME_DIR=/run/user/1101", "DOCKER_HOST=unix:///run/user/1101/docker.sock",
            f"DOCKER_CONFIG={client}", "/usr/bin/docker",
        ], command)

    def test_invalid_identity_and_slot_fail_before_touching_files(self):
        for operation, uid in (("../foreign", 1101), (str(uuid.uuid4()), 1100), (str(uuid.uuid4()), 1105)):
            with self.subTest(operation=operation, uid=uid), mock.patch.object(Path, "lstat") as inspect:
                with self.assertRaises(RUNNER.Rejected):
                    RUNNER.prepare_validation_runtime(operation, uid)
                inspect.assert_not_called()

    def test_foreign_runtime_authority_is_rejected_without_creating_scratch(self):
        for kind, owner, group, mode in (
            (stat.S_IFLNK, 0, 0, 0o711), (stat.S_IFREG, 0, 0, 0o711),
            (stat.S_IFDIR, 1101, 0, 0o711), (stat.S_IFDIR, 0, 1101, 0o711),
            (stat.S_IFDIR, 0, 0, 0o777), (stat.S_IFDIR, 0, 0, 0o750),
        ):
            observed = SimpleNamespace(st_mode=kind | mode, st_uid=owner, st_gid=group)
            with self.subTest(kind=kind, owner=owner, group=group, mode=mode), \
                    mock.patch.object(Path, "lstat", return_value=observed), \
                    mock.patch.object(Path, "resolve", return_value=RUNNER.RUNTIME_ROOT), \
                    mock.patch.object(Path, "mkdir") as create:
                with self.assertRaises(RUNNER.Rejected):
                    RUNNER.prepare_validation_runtime(str(uuid.uuid4()), 1101)
                create.assert_not_called()


@unittest.skipUnless(os.geteuid() == 0, "requires isolated root-owned filesystem fixtures")
class StagingPermissionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="atenea-slot-staging-test.")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.parent.chmod(0o755)
        self.runtime = self.parent / "runtime"
        self.runtime.mkdir(mode=0o711)
        self.runtime.chmod(0o711)
        self.patch = mock.patch.object(RUNNER, "RUNTIME_ROOT", self.runtime)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_modes_are_exact_even_under_restrictive_umask(self):
        old = os.umask(0o077)
        try:
            root = RUNNER.prepare_validation_runtime(str(uuid.uuid4()), 1101)
        finally:
            os.umask(old)
        for path, uid, gid, mode in ((self.runtime, 0, 0, 0o711), (root, 0, 1101, 0o710),
                                    (root / "docker-client", 1101, 1101, 0o700)):
            observed = path.stat()
            self.assertEqual((uid, gid, mode), (observed.st_uid, observed.st_gid, observed.st_mode & 0o7777))

    def test_existing_operation_is_not_adopted_or_overwritten(self):
        operation = str(uuid.uuid4())
        root = RUNNER.prepare_validation_runtime(operation, 1101)
        inode = root.stat().st_ino
        (root / "retained").write_text("keep")
        with self.assertRaises(RUNNER.Rejected):
            RUNNER.prepare_validation_runtime(operation, 1101)
        self.assertEqual(inode, root.stat().st_ino)
        self.assertEqual("keep", (root / "retained").read_text())

    def test_extended_and_default_acls_are_rejected_without_normalization(self):
        if not Path("/usr/bin/setfacl").is_file():
            self.skipTest("requires ACL utility for isolated fixtures")
        for acl in ("u:1102:--x", "d:u:1102:r-x"):
            subprocess.run(["/usr/bin/setfacl", "-m", acl, str(self.runtime)], check=True)
            with self.assertRaises(RUNNER.Rejected):
                RUNNER.prepare_validation_runtime(str(uuid.uuid4()), 1101)
            self.assertTrue({"system.posix_acl_access", "system.posix_acl_default"}.intersection(os.listxattr(self.runtime)))
            subprocess.run(["/usr/bin/setfacl", "-b", "-k", str(self.runtime)], check=True)
            self.runtime.chmod(0o711)

    def test_symlink_root_and_symlink_parent_are_rejected(self):
        alias = self.parent / "alias"
        alias.symlink_to(self.runtime, target_is_directory=True)
        for path in (alias, alias / "child"):
            if path.name == "child":
                (self.runtime / "child").mkdir(mode=0o711)
                (self.runtime / "child").chmod(0o711)
            with mock.patch.object(RUNNER, "RUNTIME_ROOT", path), self.assertRaises(RUNNER.Rejected):
                RUNNER.prepare_validation_runtime(str(uuid.uuid4()), 1101)

    def test_selected_slot_can_read_context_and_snapshot_but_not_modify_or_read_audit(self):
        try:
            pwd.getpwnam("atenea-slot1")
            pwd.getpwnam("atenea-slot2")
        except KeyError:
            self.skipTest("requires existing isolated slot accounts; never creates accounts")

        def allowed(user, flag, path):
            return subprocess.run(["/usr/sbin/runuser", "-u", user, "--", "/usr/bin/test", flag, str(path)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0

        # Reproduce the old topology using actual DAC, not mocked permission bits.
        audit = self.parent / "artifacts"
        audit.mkdir(mode=0o750)
        old_source = audit / "session" / "scratch" / "source"
        old_source.mkdir(parents=True)
        (old_source / "pom.xml").write_text("candidate")
        RUNNER.make_slot_readable(old_source, 1101)
        self.assertFalse(allowed("atenea-slot1", "-r", old_source / "pom.xml"))

        root = RUNNER.prepare_validation_runtime(str(uuid.uuid4()), 1101)
        for name in ("source", "backend-build", "android-build", "browser"):
            tree = root / name
            tree.mkdir(mode=0o700)
            probe = tree / "probe"
            probe.write_text("reviewed input")
            RUNNER.make_slot_readable(tree, 1101)
            self.assertTrue(allowed("atenea-slot1", "-r", probe), name)
            self.assertFalse(allowed("atenea-slot1", "-w", probe), name)
            self.assertFalse(allowed("atenea-slot1", "-w", tree), name)
            self.assertFalse(allowed("atenea-slot2", "-r", probe), name)
        self.assertTrue(allowed("atenea-slot1", "-w", root / "docker-client"))
        self.assertFalse(allowed("atenea-slot2", "-x", root))
        receipt = audit / "diagnostic.json"
        receipt.write_text("private durable evidence")
        receipt.chmod(0o600)
        self.assertFalse(allowed("atenea-slot1", "-r", receipt))
        self.assertEqual(0o750, audit.stat().st_mode & 0o7777)
        self.assertEqual(0o600, receipt.stat().st_mode & 0o7777)


if __name__ == "__main__":
    unittest.main()
