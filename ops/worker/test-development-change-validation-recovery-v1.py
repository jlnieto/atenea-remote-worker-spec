#!/usr/bin/env python3
"""Closed recovery: synthetic worktrees only; never calls an installed worker."""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest import mock
from jsonschema import Draft202012Validator, FormatChecker

SOURCE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("workspace_recovery_fixtures", SOURCE / "test-development-change-workspace-v1.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
m = fixtures.mediator_module


class ValidationRecoveryTest(unittest.TestCase):
    setUp = fixtures.DevelopmentChangeWorkspaceMediatorTest.setUp
    tearDown = fixtures.DevelopmentChangeWorkspaceMediatorTest.tearDown
    _git = fixtures.DevelopmentChangeWorkspaceMediatorTest._git
    request = fixtures.DevelopmentChangeWorkspaceMediatorTest.request

    def prepare(self):
        self.mediator.execute(self.request(), "PROVISION")
        self.worktree = self.workspaces / self.change_key / "atenea"
        self.target = self.worktree / m.VALIDATION_RECOVERY_FILE
        self.target.parent.mkdir(parents=True)
        self.before = b"// synthetic reviewed build\n" + m.VALIDATION_RECOVERY_BEFORE
        self.after = b"// synthetic reviewed build\n" + m.VALIDATION_RECOVERY_AFTER
        policy = self.root / "approved-inputs.json"
        normalized = re.sub(rb'(?m)^        versionCode = [0-9]+$', b'        versionCode = 1', self.after)
        normalized = re.sub(rb'(?m)^        versionName = "[0-9.]+"$', b'        versionName = "0.0.0"', normalized)
        policy.write_text(json.dumps({"common": {m.VALIDATION_RECOVERY_FILE: hashlib.sha256(normalized).hexdigest()},
                                      "bundles": [{"files": {}}]}))
        patcher = mock.patch.object(m, "VALIDATION_RECOVERY_POLICY", policy);patcher.start();self.addCleanup(patcher.stop)
        patcher = mock.patch.object(m, "VALIDATION_RECOVERY_POLICY_SHA256", hashlib.sha256(policy.read_bytes()).hexdigest())
        patcher.start();self.addCleanup(patcher.stop)
        self.target.write_bytes(self.before)
        # A tracked source file is required, and the unrelated draft is retained.
        self._git("-C", str(self.worktree), "add", "android")
        self._git("-C", str(self.worktree), "-c", "user.name=Synthetic", "-c", "user.email=s@invalid",
                  "commit", "-m", "reviewed build")
        self.head = self._git("-C", str(self.worktree), "rev-parse", "HEAD", capture=True).strip()
        (self.worktree / "ticket.txt").write_text("keep this real draft\n")
        self.owner = (self.worktree.parent / "workspace-v1.json").read_bytes()
        observed = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        self.validation_id = str(uuid.uuid4())
        self.worker_state = self.state / "executions.json"
        self.worker_state.write_text(json.dumps({"protocol": "agent-run-worker/v1", "workerId": "ax42-01",
            "executions": {}, "validations": {self.validation_id: {"state": "POLICY_FAILED",
            "validationDefinition": "ANDROID_BUILD", "workspaceIdentity": observed["workspaceIdentity"],
            "sourceTreeFingerprintSha256": observed["sourceFingerprintSha256"],
            "summary": "ANDROID_BUILD/TOOLCHAIN: UNSUPPORTED_DEPENDENCY_MANIFEST"}}}))
        self.worker_state.chmod(0o600)
        for key, data in (("VALIDATION_RECOVERY_BEFORE_SHA256", self.before), ("VALIDATION_RECOVERY_AFTER_SHA256", self.after)):
            patcher = mock.patch.object(m, key, hashlib.sha256(data).hexdigest())
            patcher.start(); self.addCleanup(patcher.stop)
        request = {k: v for k, v in self.request("INSPECT").items() if k not in {"predecessorOperationId"}}
        request.update(protocolVersion=m.VALIDATION_RECOVERY_PROTOCOL, operation="PREPARE", effect="PREPARE_EXACT_REPAIR",
                       operationId=str(uuid.uuid4()), idempotencyKey=str(uuid.uuid4()), sourceCommit=self.head,
                       sourceFingerprintSha256=observed["sourceFingerprintSha256"], validationOperationId=self.validation_id)
        self.command = self.exact(request)
        return self.command

    @staticmethod
    def exact(request, **updates):
        value = {**request, **updates}
        value["requestFingerprintSha256"] = m.canonical_sha256({k: v for k, v in value.items() if k != "requestFingerprintSha256"})
        return value

    def act(self, request, operation):
        return self.exact(request, operation=operation, effect={"APPLY": "APPLY_EXACT_REPAIR",
                "PREPARE": "PREPARE_EXACT_REPAIR", "DIAGNOSE": "OBSERVE_ONLY", "INSPECT": "OBSERVE_ONLY"}[operation])

    def test_prepare_is_not_apply_and_apply_changes_only_reviewed_file(self):
        command = self.prepare()
        first = self.mediator.recover_validation(command, "PREPARE")
        self.assertEqual("READY", first["state"])
        self.assertEqual(self.before, self.target.read_bytes())
        result = self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")
        for kind, value in (("request", command), ("response", result)):
            schema = json.loads((SOURCE.parent.parent / "runtime-contract" /
                ("development-change-validation-recovery-v1." + kind + ".schema.json")).read_bytes())
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
        self.assertEqual("APPLIED", result["state"])
        self.assertNotEqual(command["sourceFingerprintSha256"], result["resultFingerprintSha256"])
        self.assertEqual(self.after, self.target.read_bytes())
        self.assertEqual("keep this real draft\n", (self.worktree / "ticket.txt").read_text())
        self.assertEqual(self.owner, (self.worktree.parent / "workspace-v1.json").read_bytes())
        self.assertEqual(self.head, self._git("-C", str(self.worktree), "rev-parse", "HEAD", capture=True).strip())

    def test_diagnose_and_absent_inspection_do_not_create_a_plan_or_edit_source(self):
        command = self.prepare()
        for operation, expected in (("DIAGNOSE", "AVAILABLE"), ("INSPECT", "ABSENT")):
            result = self.mediator.recover_validation(self.act(command, operation), operation)
            self.assertEqual(expected, result["state"])
        self.assertEqual([], list(self.worktree.parent.glob("validation-recovery-*.json")))
        self.assertEqual(self.before, self.target.read_bytes())

    def test_group_only_managed_file_mode_is_repairable_and_preserved(self):
        command = self.prepare()
        # Real managed drafts use group access without world-read permission.
        self.target.chmod(0o660)
        before = self.target.stat()
        result = self.mediator.recover_validation(self.act(command, "DIAGNOSE"), "DIAGNOSE")
        self.assertEqual("AVAILABLE", result["state"])
        self.assertEqual(self.before, self.target.read_bytes())
        self.assertEqual([], list(self.worktree.parent.glob("validation-recovery-*.json")))
        self.assertEqual("READY", self.mediator.recover_validation(command, "PREPARE")["state"])
        self.assertEqual("APPLIED", self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")["state"])
        after = self.target.stat()
        self.assertEqual((before.st_uid, before.st_gid, 0o660),
                         (after.st_uid, after.st_gid, after.st_mode & 0o7777))
        self.assertEqual(self.after, self.target.read_bytes())
        self.assertEqual("keep this real draft\n", (self.worktree / "ticket.txt").read_text())

    def test_world_writable_or_executable_file_modes_remain_rejected(self):
        command = self.prepare()
        for mode in (0o666, 0o606, 0o770, 0o1660):
            with self.subTest(mode=oct(mode)):
                self.target.chmod(mode)
                with self.assertRaisesRegex(m.ContractError, "source file is unsafe"):
                    self.mediator.recover_validation(self.act(command, "DIAGNOSE"), "DIAGNOSE")
                self.assertEqual(self.before, self.target.read_bytes())
                self.assertEqual([], list(self.worktree.parent.glob("validation-recovery-*.json")))

    def test_double_prepare_apply_and_inspect_are_idempotent(self):
        command = self.prepare()
        first = self.mediator.recover_validation(command, "PREPARE")
        self.assertEqual(first, self.mediator.recover_validation(command, "PREPARE"))
        applied = self.act(command, "APPLY")
        first = self.mediator.recover_validation(applied, "APPLY")
        self.assertEqual(first, self.mediator.recover_validation(applied, "APPLY"))
        observed = self.mediator.recover_validation(self.act(command, "INSPECT"), "INSPECT")
        self.assertEqual(first["receiptSha256"], observed["receiptSha256"])
        self.assertEqual(1, len(list(self.worktree.parent.glob("validation-recovery-*.json"))))

    def test_lost_response_after_file_replacement_resumes_same_intent(self):
        command = self.prepare()
        self.mediator.recover_validation(command, "PREPARE")
        save = self.mediator._save_source_update
        def interrupt(path, record):
            if record["state"] == "APPLIED": raise m.ContractError("synthetic interruption")
            return save(path, record)
        with mock.patch.object(self.mediator, "_save_source_update", side_effect=interrupt):
            with self.assertRaisesRegex(m.ContractError, "synthetic interruption"):
                self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")
        self.assertEqual(self.after, self.target.read_bytes())
        self.assertEqual("APPLYING", self.mediator.recover_validation(self.act(command, "INSPECT"), "INSPECT")["state"])
        self.assertEqual("APPLIED", self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")["state"])

    def test_apply_without_preparation_and_arbitrary_fields_are_rejected(self):
        command = self.prepare()
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")
        for key in ("path", "command", "version", "targetMainCommit", "replacement", "shell"):
            with self.subTest(key=key), self.assertRaises(m.ContractError):
                self.mediator.recover_validation(self.exact(command, **{key: "foreign"}), "PREPARE")

    def test_other_build_logic_and_symlinks_are_rejected(self):
        command = self.prepare()
        self.target.write_bytes(self.before + b"dependencies { implementation(\"foreign:package:1\") }\n")
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(command, "PREPARE")

    def test_unreviewed_build_authority_is_not_a_repairable_version_mismatch(self):
        command = self.prepare()
        (self.worktree / "android/buildSrc").mkdir()
        result = self.mediator.recover_validation(self.act(command, "DIAGNOSE"), "DIAGNOSE")
        self.assertEqual("UNSUPPORTED", result["state"])
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(command, "PREPARE")
        self.target.unlink(); self.target.symlink_to(self.worktree / "ticket.txt")
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(command, "PREPARE")

    def test_later_edit_and_index_mutation_are_not_overwritten(self):
        command = self.prepare(); self.mediator.recover_validation(command, "PREPARE")
        (self.worktree / "ticket.txt").write_text("a later deliberate edit\n")
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(self.act(command, "APPLY"), "APPLY")
        self.assertEqual(self.before, self.target.read_bytes())

    def test_unrelated_failure_active_run_and_foreign_owner_are_rejected(self):
        command = self.prepare()
        value = json.loads(self.worker_state.read_text()); value["executions"] = {"x": {"status": "RUNNING"}}
        self.worker_state.write_text(json.dumps(value))
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(command, "PREPARE")
        value["executions"] = {}; value["validations"][self.validation_id]["sourceTreeFingerprintSha256"] = "f" * 64
        self.worker_state.write_text(json.dumps(value))
        with self.assertRaises(m.ContractError): self.mediator.recover_validation(command, "PREPARE")
        with self.assertRaises(m.ContractError):
            self.mediator.recover_validation(self.exact(command, workspaceIdentity="remote:ax42-01:change:" + str(uuid.uuid4())), "PREPARE")

    def worker(self):
        worker = fixtures.worker_module
        state = worker.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=SOURCE / "development-change-workspace-v1.py")
        for patcher in (mock.patch.object(worker, "RELEASE_INSTALLED_MARKER", self.root / "absent"),
                        mock.patch.object(worker, "load_source_authority", return_value=vars(m))):
            patcher.start();self.addCleanup(patcher.stop)
        return worker, state

    def test_worker_invokes_only_fixed_mediator_and_rejects_active_work(self):
        request=self.prepare();worker,state=self.worker()
        response=self.mediator.recover_validation(request,"PREPARE")
        with mock.patch.object(worker.subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(response),"")) as run:
            self.assertEqual(response,state.recover_validation_build(request,"PREPARE"))
            self.assertEqual([str(SOURCE / "development-change-workspace-v1.py"),"prepare-validation"],run.call_args.args[0])
            self.assertEqual(request,json.loads(run.call_args.kwargs["input"]))
            state.executions["active"]={"status":"RUNNING"}
            with self.assertRaises(worker.ProtocolError):state.recover_validation_build(request,"PREPARE")
            self.assertEqual(1,run.call_count)

    def test_worker_rejects_foreign_echo_unexpected_fields_and_wrong_action_state(self):
        request=self.prepare();worker,state=self.worker()
        response=self.mediator.recover_validation(request,"PREPARE")
        for changed in ({"sourceCommit":"f"*40},{"path":"/foreign"},{"state":"ABSENT"},{"recipeId":None},{"valuesExposed":True}):
            with self.subTest(changed=changed), mock.patch.object(worker.subprocess,"run",return_value=
                    subprocess.CompletedProcess([],0,json.dumps({**response,**changed}),"")):
                with self.assertRaises(worker.ProtocolError):state.recover_validation_build(request,"PREPARE")

    def test_http_authentication_and_read_only_route_do_not_prepare(self):
        request=self.prepare();worker,state=self.worker()
        server=worker.AgentRunServer(("127.0.0.1",0),state,"synthetic-token")
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(action,body,token="synthetic-token"):
            req=urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}"+worker.VALIDATION_RECOVERY_PATH_PREFIX+action,
                data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+token})
            try:
                with urllib.request.urlopen(req,timeout=3) as result:return result.status,json.load(result)
            except urllib.error.HTTPError as error:return error.code,json.load(error)
        try:
            inspect=self.act(request,"INSPECT")
            absent=self.mediator.recover_validation(inspect,"INSPECT")
            with mock.patch.object(worker.subprocess,"run") as run:
                self.assertEqual(401,call("prepare",request,"foreign")[0])
                self.assertEqual(404,call("execute",request)[0]);run.assert_not_called()
                run.return_value=subprocess.CompletedProcess([],0,json.dumps(absent),"")
                status,result=call("inspect",inspect)
                self.assertEqual(200,status);self.assertEqual("ABSENT",result["state"])
                self.assertEqual([],list(self.worktree.parent.glob("validation-recovery-*.json")))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)


if __name__ == "__main__": unittest.main()
