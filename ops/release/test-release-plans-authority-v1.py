#!/usr/bin/env python3
"""Fixed journal authority recovery; no services, real journals or installation."""
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_plans_authority", Path(__file__).with_name("release-control-v1.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class PlansAuthorityTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="release-plans-authority-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.plans = self.root / "plans"
        self.owner = self.group = 0
        original_lstat, original_fstat = Path.lstat, os.fstat

        def metadata(value):
            fields = list(value)
            fields[stat.ST_UID], fields[stat.ST_GID] = self.owner, self.group
            return os.stat_result(fields)

        # Synthetic fixture ownership only. Modes, no-follow, bytes, inodes,
        # fchmod and repeated observations use the real temporary filesystem.
        for context in (
            patch.object(m, "ROOT", self.root),
            patch.object(Path, "lstat", lambda path: metadata(original_lstat(path))),
            patch.object(os, "fstat", lambda fd: metadata(original_fstat(fd))),
            patch.object(m, "trusted_directory"),
        ):
            context.start()
            self.addCleanup(context.stop)

    def records(self):
        entry = self.plans / "00000000-0000-4000-8000-000000000001"
        entry.mkdir(mode=0o700)
        for name in ("operation.json", "receipt.json", "baseline.json"):
            (entry / name).write_text(json.dumps({"evidence": name}))
            (entry / name).chmod(0o600)
        return {path: (path.stat().st_ino, path.read_bytes(), path.stat().st_mode)
                for path in entry.iterdir()}

    def test_new_install_materializes_private_plans(self):
        self.assertEqual(self.plans, m.plans_authority(legacy=True, absent=True))
        self.assertFalse(self.plans.exists())
        m.prepare_plans()
        self.assertEqual(0o700, stat.S_IMODE(self.plans.stat().st_mode))
        self.assertEqual(self.plans, m.plans_authority())

    def test_exact_legacy_directory_is_tightened_without_rewriting_evidence(self):
        self.plans.mkdir(mode=0o755)
        self.plans.chmod(0o755)
        records = self.records()
        m.prepare_plans()
        self.assertEqual(0o700, stat.S_IMODE(self.plans.stat().st_mode))
        self.assertEqual(records, {p: (p.stat().st_ino, p.read_bytes(), p.stat().st_mode)
                                   for p in records})

    def test_preflight_is_read_only_and_verify_requires_final_mode(self):
        self.plans.mkdir(mode=0o755)
        self.plans.chmod(0o755)
        self.assertEqual(self.plans, m.plans_authority(legacy=True, absent=True))
        self.assertEqual(0o755, stat.S_IMODE(self.plans.stat().st_mode))
        with self.assertRaises(m.Rejected):
            m.plans_authority()

    def test_idempotence_preserves_private_directory_and_records(self):
        m.prepare_plans()
        records = self.records()
        inode = self.plans.stat().st_ino
        m.prepare_plans()
        self.assertEqual(inode, self.plans.stat().st_ino)
        self.assertEqual(records, {p: (p.stat().st_ino, p.read_bytes(), p.stat().st_mode)
                                   for p in records})

    def test_unexpected_permissions_owner_group_and_symlink_rejected(self):
        self.plans.mkdir(mode=0o700)
        for mode in (0o750, 0o770, 0o777, 0o500):
            with self.subTest(mode=oct(mode)):
                self.plans.chmod(mode)
                with self.assertRaises(m.Rejected):
                    m.prepare_plans()
                self.assertEqual(mode, stat.S_IMODE(self.plans.stat().st_mode))
        self.plans.chmod(0o755)
        for owner, group in ((1000, 0), (0, 1000)):
            self.owner, self.group = owner, group
            with self.subTest(owner=owner, group=group), self.assertRaises(m.Rejected):
                m.prepare_plans()
            self.assertEqual(0o755, stat.S_IMODE(self.plans.stat().st_mode))
        self.owner = self.group = 0
        self.plans.rmdir()
        target = self.root / "foreign"
        target.mkdir(mode=0o755)
        target.chmod(0o755)
        self.plans.symlink_to(target, target_is_directory=True)
        with self.assertRaises(m.Rejected):
            m.prepare_plans()
        self.assertTrue(self.plans.is_symlink())
        self.assertEqual(0o755, stat.S_IMODE(target.stat().st_mode))

    def test_foreign_replacement_between_inspection_and_open_is_rejected(self):
        self.plans.mkdir(mode=0o755)
        self.plans.chmod(0o755)
        original_open = os.open

        def open_foreign(path, flags):
            self.owner = 1000
            return original_open(path, flags)

        with patch.object(os, "open", side_effect=open_foreign), self.assertRaises(m.Rejected):
            m.prepare_plans()
        self.assertEqual(0o755, stat.S_IMODE(self.plans.stat().st_mode))

    def test_nonprivate_parent_rejected_before_creating_plans(self):
        with patch.object(m, "trusted_directory", side_effect=m.Rejected("INSTALLED_AUTHORITY_INVALID")):
            with self.assertRaises(m.Rejected):
                m.prepare_plans()
        self.assertFalse(self.plans.exists())

    def test_regular_file_is_not_a_journal_directory(self):
        self.plans.write_bytes(b"foreign")
        self.plans.chmod(0o700)
        with self.assertRaises(m.Rejected):
            m.prepare_plans()
        self.assertEqual(b"foreign", self.plans.read_bytes())


if __name__ == "__main__":
    unittest.main()
