#!/usr/bin/env python3
"""Only synthetic local repositories; never contacts GitHub or a real worker."""
import importlib.util
import json
import os
import stat
import subprocess
import threading
import sys
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest import mock
from jsonschema import Draft202012Validator, FormatChecker

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_preparation_fixtures", HERE / "test-development-change-source-update-v1.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module = fixtures.mediator_module


class SourceFinalizationTest(unittest.TestCase):
    setUp = fixtures.SourceUpdateTest.setUp
    tearDown = fixtures.SourceUpdateTest.tearDown
    _git = fixtures.SourceUpdateTest._git
    request = fixtures.SourceUpdateTest.request
    publication_request = fixtures.SourceUpdateTest.publication_request
    prepare_fixture = fixtures.SourceUpdateTest.prepare_fixture
    exact = staticmethod(fixtures.SourceUpdateTest.exact)

    def fixture(self, conflict=True):
        preparation_request = self.prepare_fixture(conflict=conflict)
        prepared = self.mediator.update_source(preparation_request, "PREPARE")
        if conflict:
            (self.worktree / "README.md").write_text("ticket and main resolved\n")
        observed = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        self.final_path = self.path.parent / "source-finalization-v1.json"
        self.preparation_bytes = self.path.read_bytes()
        return self.exact({**preparation_request, "protocolVersion": module.SOURCE_FINALIZATION_PROTOCOL,
            "operation": "FINALIZE", "effect": "FINALIZE_VALIDATED_SOURCE",
            "operationId": str(uuid.uuid4()), "idempotencyKey": str(uuid.uuid4()),
            "sourceRevision": preparation_request["sourceRevision"] + 2,
            "sourceFingerprintSha256": observed["sourceFingerprintSha256"],
            "preparationOperationId": preparation_request["operationId"],
            "preparationReceiptSha256": prepared["receiptSha256"],
            "validationProjectionSha256": "f" * 64})

    def inspect(self, request):
        return self.exact(request, operation="INSPECT", effect="OBSERVE_ONLY")

    def assert_history(self):
        self.assertEqual(self.owner, (self.path.parent / "workspace-v1.json").read_bytes())
        self.assertEqual(self.publication, (self.path.parent / "branch-publication-v1.json").read_bytes())
        self.assertEqual(self.preparation_bytes, self.path.read_bytes())
        self.assertEqual(self.target, self._git(f"--git-dir={self.remote}", "rev-parse", "main", capture=True).strip())

    def test_finalizes_exact_resolved_tree_and_fast_forwards_same_branch(self):
        request = self.fixture()
        result = self.mediator.finalize_source(request, "FINALIZE")
        head = result["publishedHeadSha"]
        self.assertEqual("PUBLISHED", result["state"])
        self.assertEqual([head, self.head, self.target], self._git("-C", str(self.worktree), "rev-list",
                           "--parents", "-n", "1", "HEAD", capture=True).split())
        self.assertEqual(head, self._git(f"--git-dir={self.remote}", "rev-parse", request["workspaceBranch"], capture=True).strip())
        self.assertEqual("", self._git("-C", str(self.worktree), "status", "--porcelain", capture=True))
        self.assertEqual("ticket and main resolved\n", (self.worktree / "README.md").read_text())
        self.assertRegex(result["finalizationReceiptSha256"], "^[0-9a-f]{64}$")
        self.assertEqual(0o600, stat.S_IMODE(self.final_path.stat().st_mode))
        self.assert_history()

    def test_clean_merge_without_resolver_can_be_finalized(self):
        request = self.fixture(conflict=False)
        self.assertEqual("PUBLISHED", self.mediator.finalize_source(request, "FINALIZE")["state"])
        self.assert_history()

    def test_duplicate_and_lost_response_reuse_exact_commit_and_receipt(self):
        request = self.fixture()
        first = self.mediator.finalize_source(request, "FINALIZE")
        before = self.final_path.read_bytes()
        self.assertEqual(first, self.mediator.finalize_source(request, "FINALIZE"))
        self.assertEqual(before, self.final_path.read_bytes())
        inspected = self.mediator.finalize_source(self.inspect(request), "INSPECT")
        self.assertEqual(first["publishedHeadSha"], inspected["publishedHeadSha"])
        self.assertEqual(first["finalizationReceiptSha256"], inspected["finalizationReceiptSha256"])
        self.assert_history()

    def test_inspect_absent_never_creates_candidate_or_publishes(self):
        request = self.fixture()
        self.assertEqual("ABSENT", self.mediator.finalize_source(self.inspect(request), "INSPECT")["state"])
        self.assertFalse(self.final_path.exists())
        self.assertEqual(self.head, self._git("-C", str(self.worktree), "rev-parse", "HEAD", capture=True).strip())
        self.assert_history()

    def interrupted(self, point):
        request = self.fixture()
        original = self.mediator._safe_update_git
        def stop(*args, **kwargs):
            if args[0] == point:
                raise module.ContractError("synthetic interruption")
            return original(*args, **kwargs)
        with mock.patch.object(self.mediator, "_safe_update_git", side_effect=stop):
            with self.assertRaisesRegex(module.ContractError, "synthetic interruption"):
                self.mediator.finalize_source(request, "FINALIZE")
        return request

    def test_recovers_interruption_after_branch_cas_before_index(self):
        request = self.interrupted("read-tree")
        before = self.final_path.read_bytes()
        self.assertEqual("PREPARED", self.mediator.finalize_source(self.inspect(request), "INSPECT")["state"])
        self.assertEqual(before, self.final_path.read_bytes())
        self.assertEqual("PUBLISHED", self.mediator.finalize_source(request, "FINALIZE")["state"])
        self.assert_history()

    def test_recovers_interruption_before_push(self):
        request = self.interrupted("push")
        candidate = json.loads(self.final_path.read_text())["publishedHeadSha"]
        self.assertEqual(candidate, self.mediator.finalize_source(request, "FINALIZE")["publishedHeadSha"])
        self.assert_history()

    def test_later_edit_after_interruption_is_not_overwritten(self):
        request = self.interrupted("push")
        (self.worktree / "README.md").write_text("retain newer edit\n")
        before = self.final_path.read_bytes()
        with self.assertRaisesRegex(module.ContractError, "later edit"):
            self.mediator.finalize_source(request, "FINALIZE")
        self.assertEqual(before, self.final_path.read_bytes())
        self.assertEqual("retain newer edit\n", (self.worktree / "README.md").read_text())
        self.assert_history()

    def test_changed_source_fails_before_any_branch_effect(self):
        request = self.fixture()
        (self.worktree / "README.md").write_text("post validation edit\n")
        with self.assertRaisesRegex(module.ContractError, "source changed"):
            self.mediator.finalize_source(request, "FINALIZE")
        self.assertFalse(self.final_path.exists())
        self.assert_history()

    def test_markers_are_rejected_even_when_fingerprint_matches(self):
        request = self.fixture()
        (self.worktree / "README.md").write_text("<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> main\n")
        observed = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        request = self.exact(request, sourceFingerprintSha256=observed["sourceFingerprintSha256"])
        with self.assertRaisesRegex(module.ContractError, "unresolved markers"):
            self.mediator.finalize_source(request, "FINALIZE")
        self.assertFalse(self.final_path.exists())

    def test_foreign_identity_receipt_revision_and_caller_authority_rejected(self):
        request = self.fixture()
        variants = ({"preparationOperationId": str(uuid.uuid4())}, {"preparationReceiptSha256": "0" * 64},
            {"sourceRevision": 0}, {"sourceRevision": True}, {"validationProjectionSha256": ""},
            {"workspaceBranch": "main"}, {"baseCommit": "0" * 40}, {"command": "id"},
            {"path": "/tmp/foreign"}, {"protocolVersion": "other/v1"}, {"schemaVersion": True})
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises((module.ContractError, ValueError)):
                self.mediator.finalize_source(self.exact(request, **changes), "FINALIZE")
        self.assertFalse(self.final_path.exists())
        self.assert_history()

    def test_changed_main_or_remote_branch_is_not_selected_implicitly(self):
        request = self.fixture()
        self._git(f"--git-dir={self.remote}", "update-ref", "refs/heads/main", request["baseCommit"])
        with self.assertRaisesRegex(module.ContractError, "moved"):
            self.mediator.finalize_source(request, "FINALIZE")
        self.assertFalse(self.final_path.exists())

    def test_active_execution_or_validation_blocks(self):
        request = self.fixture()
        for field, state_field, status in (("executions", "status", "RUNNING"), ("validations", "state", "RUNNING")):
            state = {"protocol": "agent-run-worker/v1", "workerId": "ax42-01", "executions": {}, "validations": {}}
            state[field] = {"synthetic": {state_field: status}}
            self.state_file.write_text(json.dumps(state))
            with self.subTest(field=field), self.assertRaisesRegex(module.ContractError, "active"):
                self.mediator.finalize_source(request, "FINALIZE")
        self.assertFalse(self.final_path.exists())

    def test_replay_cannot_change_validated_intent(self):
        request = self.fixture()
        self.mediator.finalize_source(request, "FINALIZE")
        for changes in ({"idempotencyKey": str(uuid.uuid4())}, {"validationProjectionSha256": "e" * 64},
                        {"sourceRevision": request["sourceRevision"] + 1}):
            with self.subTest(changes=changes), self.assertRaisesRegex(module.ContractError, "durable identity"):
                self.mediator.finalize_source(self.exact(request, **changes), "FINALIZE")
        self.assert_history()

    def test_symlink_is_rejected_without_exposing_target(self):
        request = self.fixture()
        (self.worktree / "README.md").unlink()
        (self.worktree / "README.md").symlink_to(self.root / "outside")
        with self.assertRaises(module.ContractError):
            self.mediator.finalize_source(request, "FINALIZE")
        self.assertFalse(self.final_path.exists())

    def test_normal_push_and_private_candidate_are_exact_without_hooks(self):
        request = self.fixture()
        marker = self.root / "hook-must-not-run"
        hook = self.mirror / "hooks" / "pre-push"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
        with mock.patch.object(self.mediator, "_git_result", wraps=self.mediator._git_result) as calls:
            result = self.mediator.finalize_source(request, "FINALIZE")
        pushes = [call.args for call in calls.call_args_list if "push" in call.args]
        self.assertEqual(1, len(pushes))
        self.assertIn("--no-force", pushes[0])
        self.assertFalse(any(arg.startswith("--force") for args in (c.args for c in calls.call_args_list) for arg in args))
        self.assertIn(result["publishedHeadSha"] + ":refs/heads/" + request["workspaceBranch"], pushes[0])
        self.assertFalse(marker.exists())
        private = f"refs/atenea/source-finalizations/{self.change_key}/{request['operationId']}"
        self.assertEqual(result["publishedHeadSha"], self._git(f"--git-dir={self.mirror}", "rev-parse", private, capture=True).strip())
        self.assert_history()

    def test_candidate_survives_gc_and_recovers_unsealed_creation_exactly(self):
        request = self.fixture()
        original = self.mediator._save_source_update
        def fail_seal(path, record):
            if path == self.final_path:
                raise module.ContractError("synthetic seal interruption")
            return original(path, record)
        with mock.patch.object(self.mediator, "_save_source_update", side_effect=fail_seal):
            with self.assertRaisesRegex(module.ContractError, "seal interruption"):
                self.mediator.finalize_source(request, "FINALIZE")
        private = f"refs/atenea/source-finalizations/{self.change_key}/{request['operationId']}"
        candidate = self._git(f"--git-dir={self.mirror}", "rev-parse", private, capture=True).strip()
        self._git(f"--git-dir={self.mirror}", "gc", "--prune=now")
        self.assertFalse(self.final_path.exists())
        self.assertEqual(candidate, self.mediator.finalize_source(request, "FINALIZE")["publishedHeadSha"])
        self.assert_history()

    def test_remote_moved_after_durable_success_is_not_repaired_by_inspect_or_replay(self):
        request = self.fixture()
        self.mediator.finalize_source(request, "FINALIZE")
        self._git(f"--git-dir={self.remote}", "update-ref", "refs/heads/" + request["workspaceBranch"], self.head)
        before = self.final_path.read_bytes()
        for operation, command in (("INSPECT", self.inspect(request)), ("FINALIZE", request)):
            with self.subTest(operation=operation), self.assertRaisesRegex(module.ContractError, "published identity moved"):
                self.mediator.finalize_source(command, operation)
        self.assertEqual(before, self.final_path.read_bytes())
        self.assertEqual(self.head, self._git(f"--git-dir={self.remote}", "rev-parse", request["workspaceBranch"], capture=True).strip())

    def test_read_only_inspect_preserves_files_records_and_refs(self):
        request = self.interrupted("push")
        before = self.final_path.read_bytes()
        with mock.patch.object(self.mediator, "_git_result", wraps=self.mediator._git_result) as calls:
            result = self.mediator.finalize_source(self.inspect(request), "INSPECT")
        self.assertEqual("PREPARED", result["state"])
        self.assertEqual(before, self.final_path.read_bytes())
        self.assertFalse(any(any(arg in {"push", "update-ref", "read-tree", "commit-tree", "add", "reset"} for arg in call.args)
                             for call in calls.call_args_list))

    def test_contracts_are_closed_and_match_absent_prepared_and_published(self):
        request = self.fixture()
        validators = []
        for kind in ("request", "response"):
            schema = json.loads((HERE.parent.parent / "runtime-contract" /
                f"development-change-source-finalization-v1.{kind}.schema.json").read_text())
            Draft202012Validator.check_schema(schema)
            validators.append(Draft202012Validator(schema, format_checker=FormatChecker()))
        validators[0].validate(request)
        inspect = self.inspect(request)
        validators[0].validate(inspect)
        validators[1].validate(self.mediator.finalize_source(inspect, "INSPECT"))
        with mock.patch.object(self.mediator, "_resume_source_finalization", side_effect=module.ContractError("synthetic")):
            with self.assertRaises(module.ContractError):
                self.mediator.finalize_source(request, "FINALIZE")
        validators[1].validate(self.mediator.finalize_source(inspect, "INSPECT"))
        result = self.mediator.finalize_source(request, "FINALIZE")
        validators[1].validate(result)
        for invalid in ({**request, "command": "id"}, self.exact(request, sourceRevision=True),
                        self.exact(request, effect="OBSERVE_ONLY")):
            self.assertTrue(list(validators[0].iter_errors(invalid)))

    def worker(self):
        return fixtures.worker_module.WorkerState(self.state, "ax42-01",
            development_change_workspace_mediator=HERE / "development-change-workspace-v1.py")

    def test_worker_authentication_and_closed_read_only_route(self):
        request = self.fixture()
        worker = fixtures.worker_module
        state = self.worker()
        server = worker.AgentRunServer(("127.0.0.1", 0), state, "synthetic-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def invoke(suffix, command, token="synthetic-token"):
            route = f"http://127.0.0.1:{server.server_address[1]}" + worker.DEVELOPMENT_CHANGE_SOURCE_FINALIZATION_PATH_PREFIX + suffix
            call = urllib.request.Request(route, data=json.dumps(command).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
            try:
                with urllib.request.urlopen(call, timeout=3) as reply:
                    return reply.status, json.load(reply)
            except urllib.error.HTTPError as reply:
                return reply.code, json.load(reply)
        try:
            with mock.patch.object(worker, "RELEASE_INSTALLED_MARKER", self.root / "absent-marker"), \
                    mock.patch.object(state, "_invoke_source_update_mediator") as mediator:
                self.assertEqual(401, invoke("finalize", request, "wrong")[0])
                self.assertEqual(404, invoke("arbitrary", request)[0])
                mediator.assert_not_called()
                inspect = self.inspect(request)
                absent = self.mediator.finalize_source(inspect, "INSPECT")
                mediator.return_value = subprocess.CompletedProcess([], 0, json.dumps(absent), "")
                status, response = invoke("inspect", inspect)
                self.assertEqual(200, status)
                self.assertEqual("ABSENT", response["state"])
                self.assertEqual({"finalization": True}, mediator.call_args.kwargs)
                self.assertFalse(self.final_path.exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_worker_validates_exact_response_identity_and_does_not_expose_stderr(self):
        request = self.fixture()
        response = self.mediator.finalize_source(request, "FINALIZE")
        worker = fixtures.worker_module
        state = self.worker()
        with mock.patch.object(worker, "RELEASE_INSTALLED_MARKER", self.root / "absent-marker"):
            for changes in ({"baseCommit": "0" * 40}, {"valuesExposed": True}, {"path": "/secret"},
                            {"sourceRevision": True}, {"state": "PREPARED"}, {"finalizationReceiptSha256": None}):
                fake = {**response, **changes}
                with self.subTest(changes=changes), mock.patch.object(state, "_invoke_source_update_mediator",
                        return_value=subprocess.CompletedProcess([], 0, json.dumps(fake), "")):
                    with self.assertRaises(worker.ProtocolError) as rejected:
                        state.finalize_development_change_source(request, "FINALIZE")
                    self.assertEqual(worker.HTTPStatus.BAD_GATEWAY, rejected.exception.status)
            with mock.patch.object(state, "_invoke_source_update_mediator",
                    return_value=subprocess.CompletedProcess([], 65, "", "unsafe /srv/secret output")):
                with self.assertRaises(worker.ProtocolError) as rejected:
                    state.finalize_development_change_source(request, "FINALIZE")
                self.assertEqual(worker.HTTPStatus.BAD_GATEWAY, rejected.exception.status)

    def test_worker_invokes_only_fixed_finalization_command(self):
        request = self.fixture()
        state = self.worker()
        process = mock.Mock(pid=424242)
        process.communicate.return_value = ("{}", "")
        with mock.patch.object(fixtures.worker_module.subprocess, "Popen") as popen:
            popen.return_value.__enter__.return_value = process
            state._invoke_source_update_mediator(HERE / "development-change-workspace-v1.py", request, "FINALIZE", finalization=True)
        self.assertEqual([str(HERE / "development-change-workspace-v1.py"), "finalize-source"], popen.call_args.args[0])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_worker_fingerprints_only_head_authorized_by_sealed_preparation(self):
        request=self.fixture()
        state=self.worker()
        worker=fixtures.worker_module
        session=str(uuid.uuid4())
        source={"sessionId":session,"workspaceIdentity":request["workspaceIdentity"],"projectId":"atenea",
            "repository":worker.PROJECT_REPOSITORY,"branch":"main","manifestSha256":worker.PROJECT_MANIFEST_SHA256,
            "commit":self.head}
        with mock.patch.object(worker,"DEVELOPMENT_CHANGE_WORKSPACE_ROOT",self.workspaces), \
                mock.patch.object(worker,"load_source_authority",return_value={"approved_validation_commit":module.approved_validation_commit}):
            result=state._fingerprint_change_source_tree(source,session,{},self.change_key)
            self.assertEqual(self.head,result["headCommit"])
            self.assertEqual(request["sourceFingerprintSha256"],result["fingerprintSha256"])
            for commit in (request["baseCommit"],self.target,"f"*40):
                with self.subTest(commit=commit),self.assertRaises(worker.ProtocolError):
                    state._fingerprint_change_source_tree({**source,"commit":commit},session,{},self.change_key)
        self.assert_history()

    def test_privileged_validator_consumes_same_authority_without_changing_creation_base(self):
        request=self.fixture()
        specification=importlib.util.spec_from_file_location("source_finalization_validation_fixture",HERE / "atenea-validation-v1.py")
        validator=importlib.util.module_from_spec(specification)
        sys.modules[specification.name]=validator
        specification.loader.exec_module(validator)
        account=SimpleNamespace(pw_uid=os.geteuid(),pw_gid=os.getegid()+1)
        with mock.patch.object(validator,"CHANGE_WORKSPACE_ROOT",self.workspaces), \
                mock.patch.object(validator.pwd,"getpwnam",return_value=account), \
                mock.patch.object(validator.grp,"getgrnam",return_value=SimpleNamespace(gr_gid=os.getegid())) as shared_group, \
                mock.patch.object(validator,"load_source_authority",return_value={"approved_validation_commit":module.approved_validation_commit}):
            worktree,slot,head=validator.resolve_authority(str(uuid.uuid4()),request["workspaceIdentity"])
            self.assertEqual(self.worktree,worktree);self.assertIsNone(slot);self.assertEqual(self.head,head)
            shared_group.assert_called_once_with("atenea")
        self.assertEqual(request["baseCommit"],json.loads(self.owner)["baseCommit"])
        self.assert_history()

    def test_source_authority_rejects_tampered_preparation_and_predecessor(self):
        request=self.fixture()
        owner=json.loads(self.owner)
        root=self.path.parent
        self.assertEqual(self.head,module.approved_validation_commit(root,owner,os.geteuid(),os.getegid()))
        for file in (self.path,root / "branch-publication-v1.json"):
            before=file.read_bytes()
            value=json.loads(before);value["sourceCommit"]="0"*40;file.write_text(json.dumps(value))
            with self.subTest(file=file.name),self.assertRaises(module.ContractError):
                module.approved_validation_commit(root,owner,os.geteuid(),os.getegid())
            file.write_bytes(before)
        self.path.chmod(0o644)
        with self.assertRaises(module.ContractError):
            module.approved_validation_commit(root,owner,os.geteuid(),os.getegid())

    def test_source_authority_rejects_foreign_workspace_group(self):
        self.fixture()
        with self.assertRaises(module.ContractError):
            module.approved_validation_commit(self.path.parent,json.loads(self.owner),os.geteuid(),os.getegid()+1)

    def test_unprepared_workspace_keeps_original_validation_authority(self):
        request=self.prepare_fixture()
        owner=json.loads(self.owner)
        self.assertFalse(self.path.exists())
        self.assertEqual(request["baseCommit"],module.approved_validation_commit(self.path.parent,owner,os.geteuid(),os.getegid()))

    def test_worker_source_authority_loader_rejects_writable_or_symlink_module(self):
        candidate=self.root / "untrusted-authority.py"
        candidate.write_text("raise RuntimeError('must never execute')\n");candidate.chmod(0o777)
        worker=fixtures.worker_module
        with mock.patch.object(worker,"SOURCE_AUTHORITY_MEDIATOR",candidate):
            with self.assertRaisesRegex(ValueError,"root-managed"):
                worker.load_source_authority()
        link=self.root / "untrusted-link.py";link.symlink_to(candidate)
        with mock.patch.object(worker,"SOURCE_AUTHORITY_MEDIATOR",link):
            with self.assertRaisesRegex(ValueError,"root-managed"):
                worker.load_source_authority()


if __name__ == "__main__":
    unittest.main()
