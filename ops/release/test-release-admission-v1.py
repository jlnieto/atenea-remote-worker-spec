#!/usr/bin/env python3
import contextlib
import fcntl
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location("release_worker",Path(__file__).parents[1]/"worker/agent-run-worker-v1.py")
worker=importlib.util.module_from_spec(spec); sys.modules[spec.name]=worker; spec.loader.exec_module(worker)

class AdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="release-admission-"); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.marker=self.root/"config.json"; self.lock=self.root/"admission.lock"
        self.marker.write_text('{"protocol":"atenea-release/v1"}'); self.marker.chmod(0o644)
        self.lock.touch(); self.lock.chmod(0o640)
        for name,value in (("RELEASE_INSTALLED_MARKER",self.marker),("RELEASE_ADMISSION_FILE",self.lock)):
            patcher=patch.object(worker,name,value); patcher.start(); self.addCleanup(patcher.stop)
        real=os.fstat
        def owner(fd):
            observed=real(fd)
            return SimpleNamespace(st_mode=observed.st_mode,st_uid=0)
        patcher=patch.object(worker.os,"fstat",side_effect=owner); patcher.start(); self.addCleanup(patcher.stop)

    def admission(self): return worker.WorkerState._release_admission(None)
    def test_legacy_uninstalled_release_control_preserves_admission(self):
        self.marker.unlink(); self.lock.unlink()
        with self.admission(): pass
    def test_shared_admission_allows_normal_work(self):
        with self.admission(), self.admission(): pass
    def test_deployment_exclusive_lock_rejects_admission(self):
        with self.lock.open("rb") as control:
            fcntl.flock(control,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(worker.ProtocolError) as rejected:
                with self.admission(): self.fail("Foreign work was admitted")
            self.assertEqual("release_in_progress",rejected.exception.code)
    def test_installed_marker_and_missing_lock_is_fail_closed(self):
        self.lock.unlink()
        with self.assertRaises(worker.ProtocolError):
            with self.admission(): pass
    def test_unreadable_or_foreign_marker_cannot_disable_admission_guard(self):
        self.marker.chmod(0o664)
        with self.assertRaises(worker.ProtocolError):
            with self.admission(): pass
        self.marker.unlink(); self.marker.symlink_to(self.root/"absent")
        with self.assertRaises(worker.ProtocolError):
            with self.admission(): pass
    def test_symlink_and_writable_lock_are_rejected(self):
        self.lock.chmod(0o660)
        with self.assertRaises(worker.ProtocolError):
            with self.admission(): pass
        self.lock.unlink(); self.lock.symlink_to(self.marker)
        with self.assertRaises(worker.ProtocolError):
            with self.admission(): pass
    def test_agent_run_and_validation_enter_guard_before_execution(self):
        for method,admitted in (("create","_create_admitted"),("start_validation","_start_validation_admitted")):
            target=SimpleNamespace(_release_admission=self.admission)
            setattr(target,admitted,Mock(return_value=({},False)))
            with self.lock.open("rb") as control:
                fcntl.flock(control,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(worker.ProtocolError): getattr(worker.WorkerState,method)(target,{})
            getattr(target,admitted).assert_not_called()
    def test_codex_and_workspace_mutations_use_same_guard(self):
        names=("stage_codex_update","activate_codex_update","rollback_codex_update",
               "reconcile_installed_codex_releases","activate_reconciled_codex_releases",
               "execute_development_change_workspace","publish_development_change_branch",
               "ensure_workspace","release_workspace","release_unactivated_workspace")
        for name in names:
            self.assertTrue(hasattr(getattr(worker.WorkerState,name),"__wrapped__"),name)

if __name__=="__main__": unittest.main()
