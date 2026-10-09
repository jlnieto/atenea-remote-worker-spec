#!/usr/bin/env python3
"""Pinned source update tests: only synthetic local repositories and state."""

import importlib.util
import json
import stat
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
spec = importlib.util.spec_from_file_location("workspace_fixtures", SOURCE / "test-development-change-workspace-v1.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
mediator_module = fixtures.mediator_module
worker_module = fixtures.worker_module


class SourceUpdateTest(unittest.TestCase):
    setUp = fixtures.DevelopmentChangeWorkspaceMediatorTest.setUp
    tearDown = fixtures.DevelopmentChangeWorkspaceMediatorTest.tearDown
    _git = fixtures.DevelopmentChangeWorkspaceMediatorTest._git
    request = fixtures.DevelopmentChangeWorkspaceMediatorTest.request
    publication_request = fixtures.DevelopmentChangeWorkspaceMediatorTest.publication_request

    def prepare_fixture(self, *, conflict=True):
        self.mediator.execute(self.request(), "PROVISION")
        self.worktree = self.workspaces / self.change_key / "atenea"
        (self.worktree / "ticket.txt").write_text("ticket change\n")
        if conflict:
            (self.worktree / "README.md").write_text("ticket README\n")
        observation = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        publication = self.publication_request(observation)
        published = self.mediator.publish(publication)
        (self.source / "README.md").write_text("main README\n")
        (self.source / "main.txt").write_text("new main file\n")
        self._git("-C", str(self.source), "add", ".")
        self._git("-C", str(self.source), "commit", "-m", "main advance")
        self.target = self._git("-C", str(self.source), "rev-parse", "HEAD", capture=True).strip()
        self._git("-C", str(self.source), "push", str(self.remote), "main:main")
        self._git(f"--git-dir={self.mirror}", "fetch", str(self.remote), "main:refs/remotes/origin/main")
        self.head = published["publishedHeadSha"]
        self.path = self.workspaces / self.change_key / "source-update-v1.json"
        self.owner = (self.workspaces / self.change_key / "workspace-v1.json").read_bytes()
        self.publication = (self.workspaces / self.change_key / "branch-publication-v1.json").read_bytes()
        self.state_file = self.state / "executions.json"
        self.state_file.write_text(json.dumps({"protocol": "agent-run-worker/v1", "workerId": "ax42-01",
                                               "executions": {}, "validations": {}}))
        self.state_file.chmod(0o600)
        request = {**publication, "protocolVersion": mediator_module.SOURCE_UPDATE_PROTOCOL,
                   "operationId": str(uuid.uuid4()), "idempotencyKey": str(uuid.uuid4()),
                   "effect": "PREPARE_PINNED_MAIN", "operation": "PREPARE", "sourceCommit": self.head,
                   "sourceFingerprintSha256": None, "targetMainCommit": self.target,
                   "publicationReceiptSha256": published["publicationReceiptSha256"]}
        return self.exact(request)

    @staticmethod
    def exact(request, **overrides):
        result = {**request, **overrides}
        result["requestFingerprintSha256"] = mediator_module.canonical_sha256({
            key: value for key, value in result.items() if key != "requestFingerprintSha256"})
        return result

    def observe(self, request, operation="INSPECT"):
        return self.exact(request, operation=operation,
                          effect="OBSERVE_ONLY" if operation == "INSPECT" else "OBSERVE_OR_RESUME_EXACT")

    def assert_retained(self):
        self.assertEqual(self.owner, (self.workspaces / self.change_key / "workspace-v1.json").read_bytes())
        self.assertEqual(self.publication, (self.workspaces / self.change_key / "branch-publication-v1.json").read_bytes())
        self.assertEqual(self.head, self._git("-C", str(self.worktree), "rev-parse", "HEAD", capture=True).strip())
        self.assertEqual(self.head, self._git(f"--git-dir={self.remote}", "rev-parse",
                                            self.request()["workspaceBranch"], capture=True).strip())
        self.assertEqual(self.target, self._git(f"--git-dir={self.remote}", "rev-parse", "main", capture=True).strip())
        self.assertEqual(self.request()["workspaceBranch"], self._git("-C", str(self.worktree),
                         "symbolic-ref", "--short", "HEAD", capture=True).strip())

    def test_conflicts_become_editable_files_without_changing_head_or_creation_base(self):
        request = self.prepare_fixture()
        result = self.mediator.update_source(request, "PREPARE")
        self.assertEqual("NEEDS_RESOLUTION", result["state"])
        self.assertEqual(["README.md"], result["conflictFiles"])
        self.assertIn("<<<<<<<", (self.worktree / "README.md").read_text())
        self.assertEqual("new main file\n", (self.worktree / "main.txt").read_text())
        self.assertEqual("ticket change\n", (self.worktree / "ticket.txt").read_text())
        self.assertEqual("", self._git("-C", str(self.worktree), "ls-files", "--unmerged", capture=True))
        git_dir = Path(self._git("-C", str(self.worktree), "rev-parse", "--absolute-git-dir", capture=True).strip())
        self.assertFalse((git_dir / "MERGE_HEAD").exists())
        self.assertRegex(result["preparedFingerprintSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(0o600, stat.S_IMODE(self.path.stat().st_mode))
        self.assert_retained()

    def test_clean_merge_is_prepared_not_published_or_validated(self):
        request = self.prepare_fixture(conflict=False)
        result = self.mediator.update_source(request, "PREPARE")
        self.assertEqual("READY_TO_FINALIZE", result["state"])
        self.assertEqual([], result["conflictFiles"])
        self.assertEqual("main README\n", (self.worktree / "README.md").read_text())
        self.assert_retained()

    def test_duplicate_prepare_and_reconcile_preserve_later_resolver_edits(self):
        request = self.prepare_fixture()
        first = self.mediator.update_source(request, "PREPARE")
        (self.worktree / "README.md").write_text("resolved deliberately\n")
        self.assertEqual(first, self.mediator.update_source(request, "PREPARE"))
        replay = self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual(first["receiptSha256"], replay["receiptSha256"])
        self.assertEqual("resolved deliberately\n", (self.worktree / "README.md").read_text())
        self.assert_retained()

    def test_lost_response_recovers_same_receipt_without_second_operation(self):
        request = self.prepare_fixture()
        with mock.patch.object(self.mediator, "_source_update_response", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                self.mediator.update_source(request, "PREPARE")
        before = self.path.read_bytes()
        result = self.mediator.update_source(request, "PREPARE")
        self.assertEqual("NEEDS_RESOLUTION", result["state"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.glob("source-update-*.json")))

    def interrupted(self):
        request = self.prepare_fixture()
        original = self.mediator._safe_update_git
        def interrupt(*args, **kwargs):
            if args[0] == "read-tree":
                raise mediator_module.ContractError("synthetic interruption")
            return original(*args, **kwargs)
        with mock.patch.object(self.mediator, "_safe_update_git", side_effect=interrupt):
            with self.assertRaisesRegex(mediator_module.ContractError, "synthetic interruption"):
                self.mediator.update_source(request, "PREPARE")
        self.assertEqual("PREPARED", json.loads(self.path.read_text())["state"])
        return request

    def test_inspect_is_read_only_and_reconcile_recovers_retained_preparation(self):
        request = self.interrupted()
        before = self.path.read_bytes()
        result = self.mediator.update_source(self.observe(request), "INSPECT")
        self.assertEqual("PREPARED", result["state"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("ticket README\n", (self.worktree / "README.md").read_text())
        self.assertEqual("NEEDS_RESOLUTION", self.mediator.update_source(
            self.observe(request, "RECONCILE"), "RECONCILE")["state"])
        self.assert_retained()

    def test_reconcile_recovers_only_exact_partial_file_materialization(self):
        request = self.interrupted()
        record = json.loads(self.path.read_text())
        blob = self.mediator._update_files(record["preparedTreeSha"])["main.txt"][1]
        (self.worktree / "main.txt").write_bytes(self.mediator._safe_update_git("cat-file", "blob", blob, git_dir=True))
        result = self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual("NEEDS_RESOLUTION", result["state"])
        self.assert_retained()

    def test_reconcile_does_not_overwrite_unattributed_later_edit(self):
        request = self.interrupted()
        (self.worktree / "README.md").write_text("do not overwrite\n")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(mediator_module.ContractError, "later edit"):
            self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("do not overwrite\n", (self.worktree / "README.md").read_text())

    def test_idempotency_and_retained_target_cannot_be_changed(self):
        request = self.prepare_fixture()
        self.mediator.update_source(request, "PREPARE")
        before = self.path.read_bytes()
        for changes in ({"idempotencyKey": str(uuid.uuid4())}, {"operationId": str(uuid.uuid4())},
                        {"targetMainCommit": self.base_commit}):
            with self.subTest(changes=changes), self.assertRaises(mediator_module.ContractError):
                self.mediator.update_source(self.exact(request, **changes), "PREPARE")
        self.assertEqual(before, self.path.read_bytes())
        self.assert_retained()

    def test_moved_mirror_main_is_rejected_before_worktree_effect(self):
        request = self.prepare_fixture()
        self._git(f"--git-dir={self.mirror}", "update-ref", "refs/remotes/origin/main", self.base_commit)
        with self.assertRaisesRegex(mediator_module.ContractError, "main or published head moved"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())
        self.assertEqual("ticket README\n", (self.worktree / "README.md").read_text())

    def test_moved_remote_main_is_rejected_before_worktree_effect(self):
        request = self.prepare_fixture()
        self._git(f"--git-dir={self.remote}", "update-ref", "refs/heads/main", self.base_commit)
        with self.assertRaisesRegex(mediator_module.ContractError, "main or published head moved"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())

    def test_moved_remote_change_branch_is_rejected(self):
        request = self.prepare_fixture()
        self._git(f"--git-dir={self.remote}", "update-ref", "refs/heads/" + request["workspaceBranch"], self.base_commit)
        with self.assertRaisesRegex(mediator_module.ContractError, "main or published head moved"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())

    def test_dirty_unpublished_workspace_is_rejected(self):
        request = self.prepare_fixture()
        (self.worktree / "README.md").write_text("unpublished edit\n")
        with self.assertRaisesRegex(mediator_module.ContractError, "not clean"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())

    def test_wrong_publication_receipt_owner_and_base_are_rejected(self):
        request = self.prepare_fixture()
        for changes in ({"publicationReceiptSha256": "a" * 64}, {"databaseProjectId": 99},
                        {"baseCommit": self.target}, {"sourceRevision": 99}, {"workerId": "other"}):
            with self.subTest(changes=changes), self.assertRaises(mediator_module.ContractError):
                self.mediator.update_source(self.exact(request, **changes), "PREPARE")
        self.assertFalse(self.path.exists())
        self.assert_retained()

    def test_worker_durable_active_or_unknown_states_reject_preparation(self):
        request = self.prepare_fixture()
        for section, value in (("executions", {"status": "RUNNING"}), ("executions", {"status": "UNKNOWN"}),
                               ("validations", {"state": "RECONCILING"})):
            state = {"protocol": "agent-run-worker/v1", "workerId": "ax42-01", "executions": {}, "validations": {}}
            state[section] = {"synthetic": value}
            self.state_file.write_text(json.dumps(state))
            with self.subTest(section=section, value=value), self.assertRaisesRegex(mediator_module.ContractError, "active"):
                self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())

    def test_tampered_durable_record_is_rejected_without_touching_resolver_edits(self):
        request = self.prepare_fixture()
        self.mediator.update_source(request, "PREPARE")
        record = json.loads(self.path.read_text())
        record["targetMainCommit"] = self.base_commit
        self.path.write_text(json.dumps(record))
        with self.assertRaisesRegex(mediator_module.ContractError, "seal"):
            self.mediator.update_source(request, "PREPARE")

    def test_no_commands_paths_repositories_or_bool_identities_are_accepted(self):
        request = self.prepare_fixture()
        for changes in ({"command": "touch forbidden"}, {"path": "/tmp/foreign"},
                        {"repository": "/tmp/foreign.git"}, {"schemaVersion": True}, {"schemaVersion": 1.0}, {"databaseProjectId": True},
                        {"baseCommit": int("1" * 40)}, {"sourceCommit": int("1" * 40)},
                        {"sourceRevision": True}, {"workspaceBranch": "main"}, {"sourceFingerprintSha256": "a" * 64}):
            with self.subTest(changes=changes), self.assertRaises(mediator_module.ContractError):
                self.mediator.update_source(self.exact(request, **changes), "PREPARE")
        self.assertFalse(self.path.exists())

    def test_external_merge_driver_is_rejected_and_never_executed(self):
        request = self.prepare_fixture()
        marker = self.root / "must-not-exist"
        self._git(f"--git-dir={self.mirror}", "config", "merge.hostile.driver", f"touch {marker}")
        with self.assertRaisesRegex(mediator_module.ContractError, "external Git"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(marker.exists())
        self.assertFalse(self.path.exists())

    def test_hooks_are_not_executed_and_no_force_push_occurs(self):
        request = self.prepare_fixture()
        marker = self.root / "hook-must-not-run"
        hook = self.mirror / "hooks" / "post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
        original = self.mediator._git_result
        with mock.patch.object(self.mediator, "_git_result", wraps=original) as calls:
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(marker.exists())
        self.assertFalse(any(any(arg in {"push", "commit", "rebase", "reset"} for arg in call.args)
                             for call in calls.call_args_list))
        private_ref = f"refs/atenea/source-updates/{self.change_key}/{request['operationId']}"
        updates = [call.args for call in calls.call_args_list if "update-ref" in call.args]
        self.assertEqual(1, len(updates))
        self.assertEqual(private_ref, updates[0][updates[0].index("update-ref") + 1])
        self.assert_retained()

    def test_symlink_in_retained_workspace_is_not_followed(self):
        request = self.interrupted()
        outside = self.root / "outside"
        outside.write_text("secret-like synthetic file")
        (self.worktree / "README.md").unlink()
        (self.worktree / "README.md").symlink_to(outside)
        with self.assertRaisesRegex(mediator_module.ContractError, "unexpected retained file"):
            self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual("secret-like synthetic file", outside.read_text())

    def test_versioned_contracts_match_all_operations_and_states(self):
        request = self.interrupted()
        request_validator = Draft202012Validator(json.loads((fixtures.CONTRACT_ROOT / "development-change-source-update-v1.request.schema.json").read_text()), format_checker=FormatChecker())
        response_validator = Draft202012Validator(json.loads((fixtures.CONTRACT_ROOT / "development-change-source-update-v1.response.schema.json").read_text()), format_checker=FormatChecker())
        for operation in ("INSPECT", "RECONCILE", "PREPARE"):
            exact = request if operation == "PREPARE" else self.observe(request, operation)
            request_validator.validate(exact)
            response_validator.validate(self.mediator.update_source(exact, operation))
        wrong = self.exact(request, effect="OBSERVE_ONLY")
        self.assertFalse(request_validator.is_valid(wrong))
        self.assertFalse(request_validator.is_valid({**request, "path": "/arbitrary"}))

    def test_worker_blocks_admission_before_mediator_and_checks_response_identity(self):
        request = self.prepare_fixture()
        state = worker_module.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=SOURCE / "development-change-workspace-v1.py")
        with mock.patch.object(worker_module, "RELEASE_INSTALLED_MARKER", self.root / "absent-release-marker"):
            with mock.patch.object(state, "_invoke_source_update_mediator") as run:
                with self.assertRaises(worker_module.ProtocolError) as rejected:
                    state.update_development_change_source(self.exact(request, workerId="other-worker"), "PREPARE")
                self.assertEqual(worker_module.HTTPStatus.UNPROCESSABLE_ENTITY, rejected.exception.status)
                run.assert_not_called()
            state.executions["active"] = {"status": "QUEUED"}
            with mock.patch.object(state, "_invoke_source_update_mediator") as run:
                with self.assertRaises(worker_module.ProtocolError) as rejected:
                    state.update_development_change_source(request, "PREPARE")
                self.assertEqual("SOURCE_UPDATE_EXECUTION_ACTIVE", rejected.exception.safe_error["code"])
                run.assert_not_called()
            state.executions.clear()
            response = self.mediator.update_source(request, "PREPARE")
            with mock.patch.object(state, "_invoke_source_update_mediator", return_value=subprocess.CompletedProcess([], 0, json.dumps(response), "")) as run:
                self.assertEqual(response, state.update_development_change_source(request, "PREPARE"))
                self.assertEqual("PREPARE", run.call_args.args[2])
            response["sourceCommit"] = self.base_commit
            with mock.patch.object(state, "_invoke_source_update_mediator", return_value=subprocess.CompletedProcess([], 0, json.dumps(response), "")):
                with self.assertRaises(worker_module.ProtocolError) as rejected:
                    state.update_development_change_source(request, "PREPARE")
                self.assertEqual(worker_module.HTTPStatus.BAD_GATEWAY, rejected.exception.status)

    def test_worker_timeout_kills_entire_private_mediator_process_group(self):
        request = self.prepare_fixture()
        state = worker_module.WorkerState(self.state, "ax42-01")
        process = mock.Mock(pid=424242)
        process.communicate.side_effect = [subprocess.TimeoutExpired("synthetic-mediator", 1), ("", "")]
        with mock.patch.object(worker_module.subprocess, "Popen") as popen, mock.patch.object(worker_module.os, "killpg") as kill:
            popen.return_value.__enter__.return_value = process
            with self.assertRaises(subprocess.TimeoutExpired):
                state._invoke_source_update_mediator(SOURCE / "development-change-workspace-v1.py", request, "PREPARE")
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertEqual([str(SOURCE / "development-change-workspace-v1.py"), "prepare-update"], popen.call_args.args[0])
            kill.assert_called_once_with(424242, worker_module.signal.SIGKILL)
            self.assertEqual(2, process.communicate.call_count)

    def test_http_route_is_authenticated_closed_and_inspection_does_not_prepare(self):
        request = self.prepare_fixture()
        state = worker_module.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=SOURCE / "development-change-workspace-v1.py")
        server = worker_module.AgentRunServer(("127.0.0.1", 0), state, "synthetic-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def invoke(route, body, token):
            url = f"http://127.0.0.1:{server.server_address[1]}{route}"
            call = urllib.request.Request(url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(call, timeout=3) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        try:
            with mock.patch.object(worker_module, "RELEASE_INSTALLED_MARKER", self.root / "absent-marker"), mock.patch.object(state, "_invoke_source_update_mediator") as mediator:
                route = worker_module.DEVELOPMENT_CHANGE_SOURCE_UPDATE_PATH_PREFIX
                self.assertEqual(401, invoke(route + "prepare", request, "wrong")[0])
                self.assertEqual(404, invoke(route + "arbitrary", request, "synthetic-token")[0])
                mediator.assert_not_called()
                inspect = self.observe(request)
                absent = self.mediator.update_source(inspect, "INSPECT")
                mediator.return_value = subprocess.CompletedProcess([], 0, json.dumps(absent), "")
                status, observation = invoke(route + "inspect", inspect, "synthetic-token")
                self.assertEqual(200, status)
                self.assertEqual("ABSENT", observation["state"])
                self.assertFalse(self.path.exists())
                self.assertEqual("INSPECT", mediator.call_args.args[2])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_worker_exposes_reviewed_specific_error_not_raw_git_or_paths(self):
        request = self.prepare_fixture()
        state = worker_module.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=SOURCE / "development-change-workspace-v1.py")
        with mock.patch.object(worker_module, "RELEASE_INSTALLED_MARKER", self.root / "absent-marker"):
            with mock.patch.object(state, "_invoke_source_update_mediator", return_value=subprocess.CompletedProcess([], 65, "", '{"code":"SOURCE_UPDATE_REF_MOVED"}')):
                with self.assertRaises(worker_module.ProtocolError) as rejected:
                    state.update_development_change_source(request, "PREPARE")
                self.assertEqual("SOURCE_UPDATE_REF_MOVED", rejected.exception.safe_error["code"])
                self.assertEqual("REQUEST_RECONCILIATION", rejected.exception.safe_error["nextAction"])
            with mock.patch.object(state, "_invoke_source_update_mediator", return_value=subprocess.CompletedProcess([], 65, "", 'unsafe /srv/secret command output')):
                with self.assertRaises(worker_module.ProtocolError) as rejected:
                    state.update_development_change_source(request, "PREPARE")
                self.assertEqual(worker_module.HTTPStatus.BAD_GATEWAY, rejected.exception.status)

    def test_failed_postcondition_retains_prepared_record_without_success_receipt(self):
        request = self.prepare_fixture()
        original = self.mediator._safe_update_git
        def wrong_index(*args, **kwargs):
            if args[0] == "write-tree":
                return ("a" * 40 + "\n").encode()
            return original(*args, **kwargs)
        with mock.patch.object(self.mediator, "_safe_update_git", side_effect=wrong_index):
            with self.assertRaisesRegex(mediator_module.ContractError, "index postcondition"):
                self.mediator.update_source(request, "PREPARE")
        self.assertEqual("PREPARED", json.loads(self.path.read_text())["state"])
        result = self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual("NEEDS_RESOLUTION", result["state"])
        self.assert_retained()

    def test_unexpected_ignored_file_is_retained_not_deleted_by_recovery(self):
        request = self.interrupted()
        (self.mirror / "info" / "exclude").write_text("private-cache.tmp\n")
        ignored = self.worktree / "private-cache.tmp"
        ignored.write_text("do not delete")
        self.assertEqual("private-cache.tmp", self._git("-C", str(self.worktree), "check-ignore",
                                                      "private-cache.tmp", capture=True).strip())
        with self.assertRaisesRegex(mediator_module.ContractError, "unexpected retained file"):
            self.mediator.update_source(self.observe(request, "RECONCILE"), "RECONCILE")
        self.assertEqual("do not delete", ignored.read_text())

    def test_target_tree_symlink_is_rejected_without_exposing_outside_path(self):
        request = self.prepare_fixture(conflict=False)
        (self.source / "bad-link").symlink_to("/etc/passwd")
        self._git("-C", str(self.source), "add", "bad-link")
        self._git("-C", str(self.source), "commit", "-m", "synthetic unsupported type")
        self.target = self._git("-C", str(self.source), "rev-parse", "HEAD", capture=True).strip()
        self._git("-C", str(self.source), "push", str(self.remote), "main:main")
        self._git(f"--git-dir={self.mirror}", "fetch", str(self.remote), "main:refs/remotes/origin/main")
        with self.assertRaisesRegex(mediator_module.ContractError, "file type or path"):
            self.mediator.update_source(self.exact(request, targetMainCommit=self.target), "PREPARE")
        self.assertFalse(self.path.exists())
        self.assertFalse((self.worktree / "bad-link").exists())
        self.assert_retained()

    def test_worker_health_advertises_update_only_with_existing_mediator(self):
        self.prepare_fixture()
        executable = self.root / "synthetic-mediator"
        executable.write_text("#!/bin/sh\nexit 1\n")
        executable.chmod(0o755)
        state = worker_module.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=executable)
        self.assertIn(mediator_module.SOURCE_UPDATE_PROTOCOL, state.health()["capabilities"])
        executable.unlink()
        self.assertNotIn(mediator_module.SOURCE_UPDATE_PROTOCOL, state.health()["capabilities"])

    def test_prepared_tree_is_retained_across_git_gc(self):
        request = self.prepare_fixture()
        result = self.mediator.update_source(request, "PREPARE")
        self._git(f"--git-dir={self.mirror}", "gc", "--prune=now")
        ref = f"refs/atenea/source-updates/{self.change_key}/{request['operationId']}"
        self.assertEqual(result["preparedTreeSha"], self._git(f"--git-dir={self.mirror}", "rev-parse", ref, capture=True).strip())
        self.assertEqual(result, self.mediator.update_source(request, "PREPARE"))
        self.assert_retained()

    def test_unsafe_change_root_mode_is_rejected_before_any_preparation(self):
        request = self.prepare_fixture()
        self.worktree.parent.chmod(0o777)
        with self.assertRaisesRegex(mediator_module.ContractError, "root mode"):
            self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())

    def test_main_moved_during_merge_preparation_is_rejected_before_materialization(self):
        request = self.prepare_fixture()
        original = self.mediator._git_result
        def move_target(*args, **kwargs):
            result = original(*args, **kwargs)
            if "merge-tree" in args:
                self._git(f"--git-dir={self.remote}", "update-ref", "refs/heads/main", self.base_commit)
            return result
        with mock.patch.object(self.mediator, "_git_result", side_effect=move_target):
            with self.assertRaisesRegex(mediator_module.ContractError, "main or published head moved"):
                self.mediator.update_source(request, "PREPARE")
        self.assertFalse(self.path.exists())
        self.assertEqual("ticket README\n", (self.worktree / "README.md").read_text())

    def test_execution_admission_cannot_race_between_preflight_and_effect(self):
        request = self.prepare_fixture()
        response = self.mediator.update_source(request, "PREPARE")
        state = worker_module.WorkerState(self.state, "ax42-01", development_change_workspace_mediator=SOURCE / "development-change-workspace-v1.py")
        entered, release, attempted, admitted = (threading.Event() for _ in range(4))
        errors = []
        execution_request = {"dispatchId": str(uuid.uuid4()), "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:test:" + str(uuid.uuid4()), "workloadClass": "NORMAL",
            "leaseGeneration": 1, "workload": {"kind": "synthetic-routing-v1", "message": "synthetic",
                                                  "durationMs": 250, "steps": 5}}
        def mediator(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("synthetic lock test")
            return subprocess.CompletedProcess([], 0, json.dumps(response), "")
        def prepare():
            try:
                state.update_development_change_source(request, "PREPARE")
            except Exception as error:
                errors.append(error)
        def create():
            try:
                attempted.set()
                state.create(execution_request)
                admitted.set()
            except Exception as error:
                errors.append(error)
        first, second = threading.Thread(target=prepare), threading.Thread(target=create)
        with mock.patch.object(worker_module, "RELEASE_INSTALLED_MARKER", self.root / "absent-marker"), mock.patch.object(state, "_invoke_source_update_mediator", side_effect=mediator):
            try:
                first.start()
                self.assertTrue(entered.wait(3))
                second.start()
                self.assertTrue(attempted.wait(3))
                self.assertFalse(admitted.wait(0.05))
            finally:
                release.set()
                first.join(timeout=3)
                if second.ident is not None:
                    second.join(timeout=3)
        self.assertEqual([], errors)
        self.assertTrue(admitted.is_set())
        self.assertFalse(first.is_alive() or second.is_alive())


if __name__ == "__main__":
    unittest.main()
