#!/usr/bin/env python3
"""Recovery of immutable intents on synthetic local Git repositories only."""
import importlib.util
import json
import os
import stat
import subprocess
import unittest
from pathlib import Path
from unittest import mock
from jsonschema import Draft202012Validator, FormatChecker

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("main_recovery_fixtures",HERE / "test-development-change-source-continuation-v2.py")
fixtures=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module=fixtures.module


class MainRecoveryTest(fixtures.SourceContinuationTest):
    def recovery(self,request):
        return self.exact(request,operation="RECOVER",effect="RESUME_PINNED_SOURCE")

    def assert_evidence(self,request,kind):
        paths=list(self.path.parent.glob("source-main-recovery-*-v1.json"))
        self.assertEqual(1,len(paths))
        record=json.loads(paths[0].read_bytes())
        self.assertEqual(kind,record["kind"])
        self.assertEqual(request["targetMainCommit"],record["targetMainCommit"])
        self.assertEqual(self.target,record["observedMainCommit"])
        self.assertEqual(module.source_update_intent(request),record["intentSha256"])
        self.assertEqual(os.getuid(),paths[0].stat().st_uid)
        self.assertEqual(0o600,stat.S_IMODE(paths[0].stat().st_mode))
        self.assertEqual(record["recordSha256"],module.canonical_sha256({k:v for k,v in record.items() if k!="recordSha256"}))
        self.assertEqual(self.owner,(self.path.parent / "workspace-v1.json").read_bytes())
        self.assertEqual(self.publication,(self.path.parent / "branch-publication-v1.json").read_bytes())

    def test_absent_preparation_recovers_original_pinned_main_not_new_target(self):
        request=self.prepare_fixture()
        self.advance_main()
        with self.assertRaisesRegex(module.ContractError,"moved"):
            self.mediator.update_source(request,"PREPARE")
        self.assertFalse(self.path.exists())
        self.assertEqual("ABSENT",self.mediator.update_source(self.exact(request,operation="INSPECT",effect="OBSERVE_ONLY"),"INSPECT")["state"])
        recovered=self.mediator.update_source(self.recovery(request),"RECOVER")
        self.assertEqual("NEEDS_RESOLUTION",recovered["state"])
        self.assertEqual(request["targetMainCommit"],recovered["targetMainCommit"])
        self.assertFalse((self.worktree / "later-main.txt").exists())
        self.assertEqual(self.head,self._git("-C",str(self.worktree),"rev-parse","HEAD",capture=True).strip())
        before=self.path.read_bytes()
        self.assertEqual(recovered,self.mediator.update_source(self.recovery(request),"RECOVER"))
        self.assertEqual(before,self.path.read_bytes())
        self.assert_evidence(request,"PREPARATION")

    def test_prepared_interruption_recovers_without_repinning_or_losing_bytes(self):
        request=self.prepare_fixture()
        with mock.patch.object(self.mediator,"_resume_source_update",side_effect=module.ContractError("interrupt")):
            with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        old=json.loads(self.path.read_bytes())
        self.advance_main()
        with self.assertRaises(module.ContractError):
            self.mediator.update_source(self.exact(request,operation="RECONCILE",effect="OBSERVE_OR_RESUME_EXACT"),"RECONCILE")
        recovered=self.mediator.update_source(self.recovery(request),"RECOVER")
        self.assertEqual(old["preparedTreeSha"],recovered["preparedTreeSha"])
        self.assertEqual(old["intentSha256"],json.loads(self.path.read_bytes())["intentSha256"])
        self.assert_evidence(request,"PREPARATION")

    def test_finalization_recovers_after_cas_and_before_index_on_advanced_main(self):
        self.recover_interrupted_finalization("read-tree")

    def test_finalization_recovers_before_push_on_advanced_main(self):
        self.recover_interrupted_finalization("push")

    def recover_interrupted_finalization(self,point):
        request=self.interrupted(point)
        candidate=json.loads(self.final_path.read_bytes())["publishedHeadSha"]
        old_tree=json.loads(self.final_path.read_bytes())["expectedTreeSha"]
        self.advance_main()
        with self.assertRaises(module.ContractError): self.mediator.finalize_source(request,"FINALIZE")
        result=self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual("PUBLISHED",result["state"])
        self.assertEqual(candidate,result["publishedHeadSha"])
        self.assertEqual(old_tree,result["expectedTreeSha"])
        self.assertEqual(request["targetMainCommit"],self._git(f"--git-dir={self.mirror}","rev-parse",candidate+"^2",capture=True).strip())
        self.assertFalse((self.worktree / "later-main.txt").exists())
        self.assertEqual(result,self.mediator.finalize_source(self.recovery(request),"RECOVER"))
        self.assertEqual(self.preparation_bytes,self.path.read_bytes())
        self.assert_evidence(request,"FINALIZATION")
        # Only now can another pinned preparation incorporate the new main.
        continuation=self.continuation(request,published=result)
        prepared=self.mediator.update_source(continuation,"PREPARE")
        self.assertEqual("READY_TO_FINALIZE",prepared["state"])
        self.assertTrue((self.worktree / "later-main.txt").is_file())

    def test_lost_push_receipt_is_sealed_without_second_push(self):
        request=self.fixture()
        save=self.mediator._save_source_update
        def interrupt(path,record):
            if record.get("state")=="PUBLISHED": raise module.ContractError("lost receipt")
            return save(path,record)
        with mock.patch.object(self.mediator,"_save_source_update",side_effect=interrupt):
            with self.assertRaises(module.ContractError): self.mediator.finalize_source(request,"FINALIZE")
        self.advance_main()
        with mock.patch.object(self.mediator,"_safe_update_git",wraps=self.mediator._safe_update_git) as calls:
            result=self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual("PUBLISHED",result["state"])
        self.assertFalse(any(call.args[0]=="push" for call in calls.call_args_list))
        self.assert_evidence(request,"FINALIZATION")

    def test_newer_files_after_interruption_are_never_reset(self):
        request=self.interrupted("push");self.advance_main()
        (self.worktree / "README.md").write_text("keep newer edits\n")
        before=self.final_path.read_bytes()
        with self.assertRaisesRegex(module.ContractError,"later edit"):
            self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual(before,self.final_path.read_bytes())
        self.assertEqual("keep newer edits\n",(self.worktree / "README.md").read_text())

    def test_foreign_remote_branch_or_divergent_main_rejected_without_effect(self):
        request=self.interrupted("push");self.advance_main()
        before=self.final_path.read_bytes()
        self._git(f"--git-dir={self.remote}","update-ref",self._branch_ref(request),self.target)
        with self.assertRaises(module.ContractError): self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual(before,self.final_path.read_bytes())
        self.assertFalse(list(self.path.parent.glob("source-main-recovery-*-v1.json")))
        self._git(f"--git-dir={self.remote}","update-ref",self._branch_ref(request),self.head)
        self._git(f"--git-dir={self.remote}","update-ref","refs/heads/main",request["baseCommit"])
        self._git(f"--git-dir={self.mirror}","update-ref","refs/remotes/origin/main",request["baseCommit"])
        with self.assertRaises(module.ContractError): self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual(before,self.final_path.read_bytes())

    @staticmethod
    def _branch_ref(request): return "refs/heads/"+request["workspaceBranch"]

    def test_second_main_advance_during_recovery_fails_before_cas(self):
        request=self.fixture()
        with mock.patch.object(self.mediator,"_resume_source_finalization",side_effect=module.ContractError("interrupt")):
            with self.assertRaises(module.ContractError): self.mediator.finalize_source(request,"FINALIZE")
        self.advance_main()
        original=self.mediator._retain_main_recovery
        def move(*args):
            evidence=original(*args);self.advance_main();return evidence
        with mock.patch.object(self.mediator,"_retain_main_recovery",side_effect=move):
            with self.assertRaisesRegex(module.ContractError,"moved"):
                self.mediator.finalize_source(self.recovery(request),"RECOVER")
        self.assertEqual(self.head,self._git("-C",str(self.worktree),"rev-parse","HEAD",capture=True).strip())
        self.assertEqual("PUBLISHED",self.mediator.finalize_source(self.recovery(request),"RECOVER")["state"])
        self.assertEqual(2,len(list(self.path.parent.glob("source-main-recovery-*-v1.json"))))

    def test_mirror_and_github_disagreement_rejects_before_effect(self):
        request=self.prepare_fixture();old=request["targetMainCommit"];self.advance_main()
        self._git(f"--git-dir={self.mirror}","update-ref","refs/remotes/origin/main",old)
        before=(self.worktree / "README.md").read_bytes()
        with self.assertRaises(module.ContractError): self.mediator.update_source(self.recovery(request),"RECOVER")
        self.assertEqual(before,(self.worktree / "README.md").read_bytes())
        self.assertFalse(self.path.exists())
        self.assertFalse(list(self.path.parent.glob("source-main-recovery-*-v1.json")))

    def test_newer_preparation_files_after_interruption_are_preserved(self):
        request=self.prepare_fixture()
        with mock.patch.object(self.mediator,"_resume_source_update",side_effect=module.ContractError("interrupt")):
            with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        self.advance_main();(self.worktree / "README.md").write_text("retain later edit\n")
        before=self.path.read_bytes()
        with self.assertRaisesRegex(module.ContractError,"later edit"):
            self.mediator.update_source(self.recovery(request),"RECOVER")
        self.assertEqual(before,self.path.read_bytes())
        self.assertEqual("retain later edit\n",(self.worktree / "README.md").read_text())

    def test_v2_pending_preparation_can_resume_same_checkpoint_after_another_advance(self):
        final_request=self.fixture();self.advance_main();request=self.continuation(final_request)
        with mock.patch.object(self.mediator,"_resume_source_update",side_effect=module.ContractError("interrupt")):
            with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        path=self.path.parent / f"source-update-{request['operationId']}-v2.json"
        original=json.loads(path.read_bytes());self.advance_main()
        result=self.mediator.update_source(self.recovery(request),"RECOVER")
        self.assertEqual(original["preparedTreeSha"],result["preparedTreeSha"])
        self.assertEqual("ticket and main resolved\n",(self.worktree / "README.md").read_text())
        self.assertFalse((self.worktree / "later-main-2.txt").exists())
        self.assert_evidence(request,"PREPARATION")

    def test_worker_recovery_dispatch_is_closed_and_preserves_zero_active_admission(self):
        request=self.prepare_fixture();self.advance_main();request=self.recovery(request)
        response=self.mediator.update_source(request,"RECOVER")
        worker=fixtures.fixtures.fixtures.worker_module;state=self.worker()
        with mock.patch.object(worker,"RELEASE_INSTALLED_MARKER",self.root / "absent-marker"), \
                mock.patch.object(state,"_invoke_source_update_mediator",return_value=subprocess.CompletedProcess([],0,json.dumps(response),"")) as invoke:
            self.assertEqual(response,state.update_development_change_source(request,"RECOVER"))
            self.assertEqual("RECOVER",invoke.call_args.args[2])
            for change in ({"command":"id"},{"path":"/arbitrary"},{"operation":"PREPARE"}):
                with self.assertRaises(worker.ProtocolError): state.update_development_change_source({**request,**change},"RECOVER")
            state.executions["synthetic-active"]={"status":"RUNNING"}
            with self.assertRaises(worker.ProtocolError): state.update_development_change_source(request,"RECOVER")
            self.assertEqual(1,invoke.call_count)

    def test_recovery_request_is_closed_and_normal_action_cannot_opt_in(self):
        request=self.fixture();self.advance_main()
        recovered=self.recovery(request)
        for changes in ({"path":"/tmp/anything"},{"observedMainCommit":self.target},{"command":"git reset"}):
            with self.assertRaises(module.ContractError): self.mediator.finalize_source({**recovered,**changes},"RECOVER")
        with self.assertRaises(module.ContractError): self.mediator.finalize_source(recovered,"FINALIZE")
        # An authorized durable App intent can also have lost its first worker request.
        result=self.mediator.finalize_source(recovered,"RECOVER")
        self.assertEqual("PUBLISHED",result["state"])
        contracts=HERE.parent.parent / "runtime-contract"
        for suffix,value in (("request",recovered),("response",result)):
            schema=json.loads((contracts / f"development-change-source-finalization-v1.{suffix}.schema.json").read_bytes())
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema,format_checker=FormatChecker()).validate(value)
        self.assert_evidence(request,"FINALIZATION")


if __name__=="__main__":
    suite=unittest.TestSuite(MainRecoveryTest(name) for name in MainRecoveryTest.__dict__ if name.startswith("test_"))
    raise SystemExit(not unittest.TextTestRunner().run(suite).wasSuccessful())
