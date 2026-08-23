#!/usr/bin/env python3

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:
    Draft202012Validator = None
    FormatChecker = None

ROOT = Path(__file__).resolve().parents[2]
MODULE = SourceFileLoader(
    "project_codex_runner_v1",
    str(Path(__file__).with_name("project-codex-runner-v1.py")),
).load_module()
CHANGE_MEDIATOR = SourceFileLoader(
    "development_change_workspace_v1_for_runner",
    str(Path(__file__).with_name("development-change-workspace-v1.py")),
).load_module()
TEST_COMMIT = "1" * 40


class ProjectCodexContractTest(unittest.TestCase):
    def workload(self, thread_id=None):
        return {
            "kind": "project-codex-v1",
            "projectId": "atenea",
            "repository": MODULE.REPOSITORY,
            "branch": MODULE.BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.MANIFEST_SHA256,
            "instructionBundleRevision": MODULE.INSTRUCTION_BUNDLE_REVISION,
            "instructionBundleSha256": MODULE.INSTRUCTION_BUNDLE_SHA256,
            "platformInstructionSha256": MODULE.PLATFORM_INSTRUCTION_SHA256,
            "projectInstructionPath": MODULE.PROJECT_INSTRUCTION_PATH,
            "projectInstructionSha256": MODULE.PROJECT_INSTRUCTION_SHA256,
            "message": "Update only the accepted documentation fixture.",
            "threadId": thread_id,
        }

    def profiled_workload(self, thread_id=None, effort="high"):
        workload = self.workload(thread_id)
        workload.update({
            "kind": MODULE.PROFILED_CAPABILITY,
            "modelId": MODULE.CODEX_MODEL,
            "reasoningEffort": effort,
            "catalogRevision": MODULE.CODEX_CATALOG_REVISION,
            "codexVersion": MODULE.CODEX_VERSION,
        })
        return workload

    def change_request(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        change_key = "88888888-8888-4888-8888-888888888888"
        workspace_identity = "remote:ax42-01:change:" + change_key
        workload = self.profiled_workload()
        workload.update({"kind": MODULE.CHANGE_CAPABILITY, "attachments": []})
        return {
            "dispatchId": "33333333-3333-4333-8333-333333333333",
            "executionId": "44444444-4444-4444-8444-444444444444",
            "sessionId": session_id,
            "workspaceIdentity": workspace_identity,
            "changeOwnership": {
                "changeKey": change_key,
                "databaseWorkSessionId": 19,
                "remoteSessionId": session_id,
                "workspaceIdentity": workspace_identity,
                "databaseProjectId": 7,
                "baseCommit": TEST_COMMIT,
                "expectedCanonicalCommit": TEST_COMMIT,
                "sourceRevision": 0,
                "sourceFingerprintSha256": "a" * 64,
                "workspaceOwnershipFingerprintSha256": "b" * 64,
            },
            "workload": workload,
        }

    def image_fixture(self, root, content=b"\x89PNG\r\n\x1a\nsynthetic-image"):
        session_id = "11111111-1111-4111-8111-111111111111"
        attachment_id = "22222222-2222-4222-8222-222222222222"
        workspace_identity = "remote:ax42-01:work-session:" + session_id
        digest = hashlib.sha256(content).hexdigest()
        workload = self.profiled_workload()
        workload.update({
            "kind": MODULE.IMAGE_CAPABILITY,
            "attachments": [{
                "attachmentId": attachment_id,
                "contentType": "image/png",
                "sizeBytes": len(content),
                "sha256": digest,
            }],
        })
        request = {
            "dispatchId": "33333333-3333-4333-8333-333333333333",
            "executionId": "44444444-4444-4444-8444-444444444444",
            "sessionId": session_id,
            "workspaceIdentity": workspace_identity,
            "workload": workload,
        }
        attachment_root = root / "work-sessions" / session_id / attachment_id
        attachment_root.mkdir(parents=True)
        for directory in (root, root / "work-sessions", attachment_root.parent, attachment_root):
            directory.chmod(0o700)
        content_path = attachment_root / "content"
        metadata_path = attachment_root / "metadata.json"
        content_path.write_bytes(content)
        metadata_path.write_text(json.dumps({
            "protocolVersion": "worksession-attachment/v1",
            "workerId": MODULE.ATTACHMENT_WORKER_ID,
            "sessionId": session_id,
            "attachmentId": attachment_id,
            "storageIdentity": f"work-sessions/{session_id}/{attachment_id}/content",
            "source": "OPERATOR_UPLOAD",
            "kind": "IMAGE",
            "contentType": "image/png",
            "sizeBytes": len(content),
            "retentionClass": "SESSION",
            "sha256": digest,
            "syntheticFixture": False,
            "createdAt": "2026-08-01T00:00:00Z",
            "storedAt": "2026-08-01T00:00:01Z",
            "projectIdentity": "atenea",
            "workspaceIdentity": workspace_identity,
            "storageScope": "REAL_SESSION",
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        content_path.chmod(0o600)
        metadata_path.chmod(0o600)
        return request, content_path, metadata_path

    def atenea_config(self):
        return {
            "schemaVersion": MODULE.CAPABILITY,
            "selectionEnabled": True,
            "executionEnabled": True,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.REPOSITORY,
            "branch": MODULE.BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.MANIFEST_SHA256,
            "runner": str(Path(MODULE.__file__).resolve()),
            "attachmentRoot": str(MODULE.ATTACHMENT_ROOT),
            "workspaces": {},
        }

    def test_request_and_result_schemas_accept_exact_envelopes(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed on this worker")
        request_schema = json.loads(
            (ROOT / "runtime-contract/agent-run-project-codex-v1.request.schema.json").read_text()
        )
        result_schema = json.loads(
            (ROOT / "runtime-contract/agent-run-project-codex-v1.result.schema.json").read_text()
        )
        request = {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:ax42-01:work-session:" + str(uuid.uuid4()),
            "workloadClass": "NORMAL",
            "leaseGeneration": 1,
            "workload": self.workload(),
        }
        result = {
            "threadId": str(uuid.uuid4()),
            "turnId": str(uuid.uuid4()),
            "finalAnswer": "Done.",
            "outputSummary": "project-codex-v1 completed",
        }
        Draft202012Validator(request_schema, format_checker=FormatChecker()).validate(request)
        Draft202012Validator(result_schema, format_checker=FormatChecker()).validate(result)

    def test_change_request_and_result_schemas_are_closed_and_versioned(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed on this worker")
        request_schema = json.loads(
            (ROOT / "runtime-contract/agent-run-project-codex-v4.request.schema.json")
            .read_text(encoding="utf-8")
        )
        result_schema = json.loads(
            (ROOT / "runtime-contract/agent-run-project-codex-v4.result.schema.json")
            .read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(request_schema)
        Draft202012Validator.check_schema(result_schema)
        request = self.change_request()
        request.pop("executionId")
        request.update({"workloadClass": "NORMAL", "leaseGeneration": 1})
        result = {
            "threadId": str(uuid.uuid4()),
            "turnId": str(uuid.uuid4()),
            "finalAnswer": "Done.",
            "outputSummary": "project-codex-v4 completed",
            "modelId": MODULE.CODEX_MODEL,
            "reasoningEffort": "high",
            "catalogRevision": MODULE.CODEX_CATALOG_REVISION,
            "codexVersion": MODULE.CODEX_VERSION,
        }
        request_validator = Draft202012Validator(
            request_schema, format_checker=FormatChecker()
        )
        request_validator.validate(request)
        Draft202012Validator(
            result_schema, format_checker=FormatChecker()
        ).validate(result)
        for key, value in (
            ("path", "/srv/foreign"),
            ("host", "foreign"),
            ("slot", "slot9"),
            ("shell", "sh -lc id"),
        ):
            candidate = json.loads(json.dumps(request))
            candidate["changeOwnership"][key] = value
            self.assertTrue(list(request_validator.iter_errors(candidate)), key)

    def test_codex_failure_classification_is_closed_and_sanitized(self):
        cases = (
            ("database is locked at /secret/path", "Codex execution failed: thread persistence unavailable"),
            ("permission denied: token-value", "Codex execution failed: filesystem boundary"),
            ("bwrap: can't find source path token-value", "Codex execution failed: filesystem boundary"),
            ("totally novel token-value", "Codex execution failed: unclassified"),
        )
        for stderr, expected in cases:
            reason = MODULE.codex_failure_reason(stderr)
            self.assertEqual(expected, reason)
            self.assertNotIn("token-value", reason)
            self.assertNotIn("/secret/path", reason)

    def test_atenea_configuration_preserves_legacy_text_routing_until_attachment_activation(self):
        runner = Path(MODULE.__file__).resolve()
        config = self.atenea_config()
        MODULE.validate_config(config, runner)

        legacy = json.loads(json.dumps(config))
        legacy.pop("attachmentRoot")
        MODULE.validate_config(legacy, runner)

        for mutation in (
            lambda value: value.__setitem__("attachmentRoot", "/srv/foreign"),
            lambda value: value.__setitem__("attachmentRoots", [str(MODULE.ATTACHMENT_ROOT)]),
        ):
            candidate = json.loads(json.dumps(config))
            mutation(candidate)
            with self.assertRaises(SystemExit):
                MODULE.validate_config(candidate, runner)

    def test_exact_real_attachment_is_verified_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "attachments-v1"
            root.mkdir()
            request, content_path, metadata_path = self.image_fixture(root)
            config = {"attachmentRoot": str(root)}
            before = (
                content_path.read_bytes(), metadata_path.read_bytes(),
                content_path.stat().st_mode, metadata_path.stat().st_mode,
            )
            with patch.object(MODULE, "ATTACHMENT_ROOT", root), patch.object(
                MODULE, "attachment_owner_ids", return_value=(os.getuid(), os.getgid())
            ):
                verified = MODULE.validate_attachment_references(
                    request, request["workload"], config
                )
            self.assertEqual(1, len(verified))
            self.assertEqual(content_path, verified[0].content_path)
            self.assertEqual(request["workload"]["attachments"][0]["sha256"], verified[0].sha256)
            self.assertEqual(before, (
                content_path.read_bytes(), metadata_path.read_bytes(),
                content_path.stat().st_mode, metadata_path.stat().st_mode,
            ))

    def test_two_images_are_materialized_and_bound_read_only_in_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            retained_root = temporary_root / "attachments-v1"
            retained_root.mkdir()
            request, first_content_path, first_metadata_path = self.image_fixture(
                retained_root
            )
            session_id = request["sessionId"]
            second_id = "55555555-5555-4555-8555-555555555555"
            second_content = b"RIFF\x08\x00\x00\x00WEBPsynthetic"
            second_digest = hashlib.sha256(second_content).hexdigest()
            second_root = retained_root / "work-sessions" / session_id / second_id
            second_root.mkdir(mode=0o700)
            second_content_path = second_root / "content"
            second_metadata_path = second_root / "metadata.json"
            second_content_path.write_bytes(second_content)
            second_metadata = json.loads(first_metadata_path.read_text(encoding="utf-8"))
            second_metadata.update({
                "attachmentId": second_id,
                "storageIdentity": f"work-sessions/{session_id}/{second_id}/content",
                "contentType": "image/webp",
                "sizeBytes": len(second_content),
                "sha256": second_digest,
            })
            second_metadata_path.write_text(
                json.dumps(second_metadata, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            second_content_path.chmod(0o600)
            second_metadata_path.chmod(0o600)
            request["workload"]["attachments"].append({
                "attachmentId": second_id,
                "contentType": "image/webp",
                "sizeBytes": len(second_content),
                "sha256": second_digest,
            })
            materialization_root = temporary_root / "run" / "atenea" / "codex-images"
            materialization_root.mkdir(parents=True)
            materialization_root.chmod(0o710)
            owner = (os.getuid(), os.getgid())
            sources_before = (
                first_content_path.read_bytes(), first_metadata_path.read_bytes(),
                second_content_path.read_bytes(), second_metadata_path.read_bytes(),
            )
            with patch.object(MODULE, "ATTACHMENT_ROOT", retained_root), patch.object(
                MODULE, "MATERIALIZATION_ROOT", materialization_root
            ), patch.object(
                MODULE, "attachment_owner_ids", return_value=owner
            ), patch.object(
                MODULE,
                "materialization_owner_ids",
                return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
            ):
                verified = MODULE.validate_attachment_references(
                    request,
                    request["workload"],
                    {"attachmentRoot": str(retained_root)},
                )
                with MODULE.materialize_attachments(
                    verified, request["executionId"]
                ) as materialized:
                    self.assertEqual(
                        [item["attachmentId"] for item in request["workload"]["attachments"]],
                        [item.attachment_id for item in materialized],
                    )
                    self.assertTrue(all(item.path.stat().st_mode & 0o777 == 0o600 for item in materialized))
                    self.assertEqual(0o700, materialized[0].path.parent.stat().st_mode & 0o777)
                    command = MODULE.sandbox_command(
                        request["workload"],
                        Path("/srv/atenea/workspaces/sessions") / session_id / "atenea",
                        MODULE.GIT_COMMON_DIR,
                        temporary_root / "final.txt",
                        temporary_root / "resolv.conf",
                        temporary_root / "empty-instructions",
                        "reviewed instructions",
                        request["executionId"],
                        materialized,
                    )
                    image_paths = [
                        command[index + 1]
                        for index, value in enumerate(command)
                        if value == "--image"
                    ]
                    bind_sources = [
                        command[index + 1]
                        for index, value in enumerate(command)
                        if value == "--ro-bind"
                        and command[index + 1] in {str(item.path) for item in materialized}
                    ]
                    self.assertEqual([str(item.path) for item in materialized], image_paths)
                    self.assertEqual(image_paths, bind_sources)
                    self.assertNotIn(str(retained_root), command)
                    self.assertNotIn(str(first_content_path), command)
                    self.assertEqual(1, command.count("project_doc_max_bytes=0"))
                    self.assertEqual("-", command[-1])

                    resumed = json.loads(json.dumps(request["workload"]))
                    resumed["threadId"] = "66666666-6666-4666-8666-666666666666"
                    resumed_command = MODULE.sandbox_command(
                        resumed,
                        Path("/srv/atenea/workspaces/sessions") / session_id / "atenea",
                        MODULE.GIT_COMMON_DIR,
                        temporary_root / "final.txt",
                        temporary_root / "resolv.conf",
                        temporary_root / "empty-instructions",
                        "reviewed instructions",
                        request["executionId"],
                        materialized,
                    )
                    resumed_images = [
                        resumed_command[index + 1]
                        for index, value in enumerate(resumed_command)
                        if value == "--image"
                    ]
                    self.assertEqual(image_paths, resumed_images)
                    self.assertEqual(
                        1,
                        resumed_command.count("project_doc_max_bytes=0"),
                    )
                    resume_index = resumed_command.index("resume")
                    self.assertTrue(all(
                        resumed_command.index("--image", resume_index) > resume_index
                        for _item in materialized
                    ))
                    self.assertEqual([resumed["threadId"], "-"], resumed_command[-2:])
                self.assertFalse((materialization_root / request["executionId"]).exists())
                self.assertEqual([], list(materialization_root.iterdir()))
            self.assertEqual(sources_before, (
                first_content_path.read_bytes(), first_metadata_path.read_bytes(),
                second_content_path.read_bytes(), second_metadata_path.read_bytes(),
            ))

    def test_materialization_finally_cleans_bounded_terminal_outcomes(self):
        outcomes = (
            RuntimeError("forced runner failure"),
            subprocess.TimeoutExpired("codex", 1),
            InterruptedError("cancelled or interrupted"),
            SystemExit(2),
        )
        for outcome in outcomes:
            with self.subTest(outcome=type(outcome).__name__), tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                retained_root = temporary_root / "attachments-v1"
                retained_root.mkdir()
                request, content_path, metadata_path = self.image_fixture(retained_root)
                runtime_root = temporary_root / "run" / "atenea" / "codex-images"
                runtime_root.mkdir(parents=True)
                runtime_root.chmod(0o710)
                owner = (os.getuid(), os.getgid())
                retained_before = (content_path.read_bytes(), metadata_path.read_bytes())
                with patch.object(MODULE, "ATTACHMENT_ROOT", retained_root), patch.object(
                    MODULE, "MATERIALIZATION_ROOT", runtime_root
                ), patch.object(
                    MODULE, "attachment_owner_ids", return_value=owner
                ), patch.object(
                    MODULE,
                    "materialization_owner_ids",
                    return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
                ):
                    verified = MODULE.validate_attachment_references(
                        request, request["workload"], {"attachmentRoot": str(retained_root)}
                    )
                    with self.assertRaises(type(outcome)):
                        with MODULE.materialize_attachments(
                            verified, request["executionId"]
                        ):
                            raise outcome
                self.assertEqual([], list(runtime_root.iterdir()))
                self.assertEqual(
                    retained_before,
                    (content_path.read_bytes(), metadata_path.read_bytes()),
                )

    def test_new_resumed_and_timeout_execute_with_one_process_and_zero_residue(self):
        class SuccessProcess:
            commands = []

            def __init__(self, command, **_kwargs):
                self.command = command
                self.returncode = 0
                self.pid = 999999
                self.commands.append(command)

            def communicate(self, _message, timeout):
                self.assert_timeout = timeout
                final_path = Path(
                    self.command[self.command.index("--output-last-message") + 1]
                )
                final_path.write_text("bounded synthetic answer", encoding="utf-8")
                thread_id = (
                    self.command[-2]
                    if "resume" in self.command
                    else "77777777-7777-4777-8777-777777777777"
                )
                stream = json.dumps({
                    "type": "thread.started",
                    "thread_id": thread_id,
                })
                return stream, ""

        class TimeoutProcess(SuccessProcess):
            def communicate(self, _message, timeout):
                raise subprocess.TimeoutExpired("codex", timeout)

            def wait(self, timeout):
                self.returncode = -15
                return -15

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            retained_root = temporary_root / "attachments-v1"
            retained_root.mkdir()
            request, content_path, metadata_path = self.image_fixture(retained_root)
            runtime_root = temporary_root / "run" / "atenea" / "codex-images"
            runtime_root.mkdir(parents=True)
            runtime_root.chmod(0o710)
            worktree = temporary_root / "sessions" / request["sessionId"] / "atenea"
            worktree.mkdir(parents=True)
            owner = (os.getuid(), os.getgid())
            identity = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            with patch.object(MODULE, "ATTACHMENT_ROOT", retained_root), patch.object(
                MODULE, "MATERIALIZATION_ROOT", runtime_root
            ), patch.object(
                MODULE, "attachment_owner_ids", return_value=owner
            ), patch.object(
                MODULE,
                "materialization_owner_ids",
                return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
            ), patch.object(MODULE.pwd, "getpwnam", return_value=identity):
                verified = MODULE.validate_attachment_references(
                    request, request["workload"], {"attachmentRoot": str(retained_root)}
                )
                for thread_id in (None, "88888888-8888-4888-8888-888888888888"):
                    workload = json.loads(json.dumps(request["workload"]))
                    workload["threadId"] = thread_id
                    execution_id = str(uuid.uuid4())
                    with MODULE.materialize_attachments(
                        verified, execution_id
                    ) as materialized, patch.object(
                        MODULE.subprocess, "Popen", SuccessProcess
                    ):
                        result = MODULE.execute(
                            workload,
                            worktree,
                            MODULE.GIT_COMMON_DIR,
                            MODULE.ReviewedInstructionBundle(
                                "reviewed instructions",
                                b"repository instructions\n",
                            ),
                            execution_id,
                            30,
                            materialized,
                        )
                    self.assertEqual(
                        thread_id or "77777777-7777-4777-8777-777777777777",
                        result["threadId"],
                    )
                    self.assertEqual([], list(runtime_root.iterdir()))

                timeout_execution = str(uuid.uuid4())
                with self.assertRaises(SystemExit), patch.object(
                    MODULE.os, "killpg"
                ) as killpg, MODULE.materialize_attachments(
                    verified, timeout_execution
                ) as materialized, patch.object(
                    MODULE.subprocess, "Popen", TimeoutProcess
                ):
                    MODULE.execute(
                        request["workload"],
                        worktree,
                        MODULE.GIT_COMMON_DIR,
                        MODULE.ReviewedInstructionBundle(
                            "reviewed instructions",
                            b"repository instructions\n",
                        ),
                        timeout_execution,
                        30,
                        materialized,
                    )
                killpg.assert_called_once()
                self.assertEqual([], list(runtime_root.iterdir()))
            self.assertEqual(3, len(SuccessProcess.commands))
            self.assertTrue(content_path.is_file())
            self.assertTrue(metadata_path.is_file())

    def test_cleanup_refuses_replaced_materialization_and_preserves_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            retained_root = temporary_root / "attachments-v1"
            retained_root.mkdir()
            request, content_path, metadata_path = self.image_fixture(retained_root)
            runtime_root = temporary_root / "run" / "atenea" / "codex-images"
            runtime_root.mkdir(parents=True)
            runtime_root.chmod(0o710)
            owner = (os.getuid(), os.getgid())
            with patch.object(MODULE, "ATTACHMENT_ROOT", retained_root), patch.object(
                MODULE, "MATERIALIZATION_ROOT", runtime_root
            ), patch.object(
                MODULE, "attachment_owner_ids", return_value=owner
            ), patch.object(
                MODULE,
                "materialization_owner_ids",
                return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
            ):
                verified = MODULE.validate_attachment_references(
                    request, request["workload"], {"attachmentRoot": str(retained_root)}
                )
                with self.assertRaises(SystemExit):
                    with MODULE.materialize_attachments(
                        verified, request["executionId"]
                    ) as materialized:
                        replaced = materialized[0].path
                        replaced.unlink()
                        replaced.write_bytes(b"foreign-replacement")
                        replaced.chmod(0o600)
                self.assertEqual(b"foreign-replacement", replaced.read_bytes())
                self.assertTrue(replaced.parent.is_dir())
            self.assertTrue(content_path.is_file())
            self.assertTrue(metadata_path.is_file())

    def test_startup_reconciliation_removes_only_absent_or_terminal_exact_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "codex-images"
            root.mkdir()
            root.chmod(0o710)
            attachment_id = "11111111-1111-4111-8111-111111111111"
            materialized_content = b"\x89PNG\r\n\x1a\nsynthetic"
            reference = {
                "attachmentId": attachment_id,
                "contentType": "image/png",
                "sizeBytes": len(materialized_content),
                "sha256": hashlib.sha256(materialized_content).hexdigest(),
            }

            def candidate(execution_id):
                directory = root / execution_id
                directory.mkdir(mode=0o700)
                path = directory / f"01-{attachment_id}.png"
                path.write_bytes(materialized_content)
                path.chmod(0o600)
                return directory

            terminal_id = "22222222-2222-4222-8222-222222222222"
            absent_id = "33333333-3333-4333-8333-333333333333"
            running_id = "44444444-4444-4444-8444-444444444444"
            terminal = candidate(terminal_id)
            absent = candidate(absent_id)
            running = candidate(running_id)
            payload = {
                "schemaVersion": "codex-image-reconciliation-state-v1",
                "executions": [
                    {"executionId": terminal_id, "status": "FAILED", "attachments": [reference]},
                    {"executionId": running_id, "status": "RUNNING", "attachments": [reference]},
                ],
            }
            with patch.object(MODULE, "MATERIALIZATION_ROOT", root), patch.object(
                MODULE,
                "materialization_owner_ids",
                return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
            ):
                result = MODULE.reconcile_materializations(payload)
            self.assertEqual(2, result["removed"])
            self.assertEqual(1, result["retained"])
            self.assertFalse(terminal.exists())
            self.assertFalse(absent.exists())
            self.assertTrue(running.is_dir())

    def test_ambiguous_startup_candidate_blocks_without_removing_exact_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "codex-images"
            root.mkdir()
            root.chmod(0o710)
            execution_id = "22222222-2222-4222-8222-222222222222"
            attachment_id = "11111111-1111-4111-8111-111111111111"
            materialized_content = b"\x89PNG\r\n\x1a\nsynthetic"
            exact = root / execution_id
            exact.mkdir(mode=0o700)
            exact_file = exact / f"01-{attachment_id}.png"
            exact_file.write_bytes(materialized_content)
            exact_file.chmod(0o600)
            ambiguous = root / "foreign-unlabelled"
            ambiguous.write_bytes(b"untouched")
            payload = {
                "schemaVersion": "codex-image-reconciliation-state-v1",
                "executions": [{
                    "executionId": execution_id,
                    "status": "FAILED",
                    "attachments": [{
                        "attachmentId": attachment_id,
                        "contentType": "image/png",
                        "sizeBytes": len(materialized_content),
                        "sha256": hashlib.sha256(materialized_content).hexdigest(),
                    }],
                }],
            }
            with patch.object(MODULE, "MATERIALIZATION_ROOT", root), patch.object(
                MODULE,
                "materialization_owner_ids",
                return_value=(os.getuid(), os.getgid(), os.getuid(), os.getgid()),
            ), self.assertRaises(SystemExit):
                MODULE.reconcile_materializations(payload)
            self.assertEqual(materialized_content, exact_file.read_bytes())
            self.assertEqual(b"untouched", ambiguous.read_bytes())

    def test_sidecar_file_and_request_identity_must_match_before_delivery(self):
        cases = (
            ("project", lambda request, metadata, content: metadata.__setitem__(
                "projectIdentity", "beautips")),
            ("session", lambda request, metadata, content: metadata.__setitem__(
                "sessionId", "55555555-5555-4555-8555-555555555555")),
            ("workspace", lambda request, metadata, content: metadata.__setitem__(
                "workspaceIdentity", "remote:foreign")),
            ("type", lambda request, metadata, content: metadata.__setitem__(
                "contentType", "image/jpeg")),
            ("size", lambda request, metadata, content: metadata.__setitem__(
                "sizeBytes", metadata["sizeBytes"] + 1)),
            ("sidecar_sha", lambda request, metadata, content: metadata.__setitem__(
                "sha256", "f" * 64)),
            ("content_sha", lambda request, metadata, content: content.write_bytes(
                b"\x89PNG\r\n\x1a\nchanged")),
            ("content_mode", lambda request, metadata, content: content.chmod(0o640)),
            ("partial", lambda request, metadata, content: metadata.pop("storageScope")),
        )
        for name, mutate in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "attachments-v1"
                root.mkdir()
                request, content_path, metadata_path = self.image_fixture(root)
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                mutate(request, metadata, content_path)
                metadata_path.write_text(
                    json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                metadata_path.chmod(0o600)
                before_content = content_path.read_bytes()
                before_metadata = metadata_path.read_bytes()
                with patch.object(MODULE, "ATTACHMENT_ROOT", root), patch.object(
                    MODULE, "attachment_owner_ids", return_value=(os.getuid(), os.getgid())
                ), patch.object(MODULE.subprocess, "Popen") as process, self.assertRaisesRegex(
                    SystemExit, "2"
                ):
                    MODULE.validate_attachment_references(
                        request, request["workload"], {"attachmentRoot": str(root)}
                    )
                process.assert_not_called()
                self.assertEqual(before_content, content_path.read_bytes())
                self.assertEqual(before_metadata, metadata_path.read_bytes())

    def test_complete_retained_denial_matrix_starts_no_process_and_mutates_nothing(self):
        def snapshot(root):
            observed = []
            for path in sorted(root.rglob("*"), key=lambda item: str(item)):
                info = path.lstat()
                identity = (
                    str(path.relative_to(root)),
                    info.st_mode,
                    info.st_uid,
                    info.st_gid,
                    info.st_size,
                )
                if path.is_symlink():
                    value = ("symlink", os.readlink(path))
                elif path.is_file():
                    value = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
                else:
                    value = ("directory", None)
                observed.append((identity, value))
            return observed

        def rewrite_metadata(path, mutate):
            value = json.loads(path.read_text(encoding="utf-8"))
            mutate(value)
            path.write_text(
                json.dumps(value, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            path.chmod(0o600)

        def symlink_file(path):
            retained = path.read_bytes()
            foreign = path.parent.parent / "foreign-content"
            foreign.write_bytes(retained)
            path.unlink()
            path.symlink_to(foreign)

        def symlink_sidecar(path):
            retained = path.read_bytes()
            foreign = path.parent.parent / "foreign-sidecar"
            foreign.write_bytes(retained)
            path.unlink()
            path.symlink_to(foreign)

        def over_count(request, _content, _metadata):
            base = request["workload"]["attachments"][0]
            request["workload"]["attachments"] = [
                {**base, "attachmentId": f"0000000{index}-0000-4000-8000-000000000000"}
                for index in range(1, 6)
            ]

        cases = (
            ("missing_sidecar", lambda request, content, metadata: metadata.unlink()),
            ("missing_file", lambda request, content, metadata: content.unlink()),
            ("modified_file", lambda request, content, metadata: content.write_bytes(
                b"\x89PNG\r\n\x1a\nmodified")),
            ("symlinked_file", lambda request, content, metadata: symlink_file(content)),
            ("symlinked_sidecar", lambda request, content, metadata: symlink_sidecar(metadata)),
            ("partial_sidecar", lambda request, content, metadata: rewrite_metadata(
                metadata, lambda value: value.pop("storageScope"))),
            ("unlabelled_sidecar", lambda request, content, metadata: rewrite_metadata(
                metadata, lambda value: value.__setitem__("projectIdentity", None))),
            ("foreign_sidecar", lambda request, content, metadata: rewrite_metadata(
                metadata, lambda value: value.__setitem__("workspaceIdentity", "remote:foreign"))),
            ("ambiguous_sidecar", lambda request, content, metadata: rewrite_metadata(
                metadata, lambda value: value.__setitem__("path", "/srv/foreign"))),
            ("permission_invalid_file", lambda request, content, metadata: content.chmod(0o640)),
            ("permission_invalid_sidecar", lambda request, content, metadata: metadata.chmod(0o644)),
            ("permission_invalid_directory", lambda request, content, metadata: content.parent.chmod(0o750)),
            ("over_bound_sidecar", lambda request, content, metadata: (
                metadata.write_bytes(b"{" + b" " * (16 * 1024) + b"}"), metadata.chmod(0o600))),
            ("over_bound_file", lambda request, content, metadata: request["workload"][
                "attachments"
            ][0].__setitem__("sizeBytes", MODULE.MAX_ATTACHMENT_BYTES + 1)),
            ("over_bound_count", over_count),
        )
        for name, mutate in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                retained_root = Path(temporary) / "attachments-v1"
                retained_root.mkdir()
                request, content_path, metadata_path = self.image_fixture(retained_root)
                mutate(request, content_path, metadata_path)
                before = snapshot(retained_root)
                with patch.object(MODULE, "ATTACHMENT_ROOT", retained_root), patch.object(
                    MODULE, "attachment_owner_ids", return_value=(os.getuid(), os.getgid())
                ), patch.object(MODULE.subprocess, "Popen") as process, self.assertRaises(
                    SystemExit
                ):
                    MODULE.validate_attachment_references(
                        request,
                        request["workload"],
                        {"attachmentRoot": str(retained_root)},
                    )
                process.assert_not_called()
                self.assertEqual(before, snapshot(retained_root))

    def test_internal_failure_classification_retains_only_allowlisted_type(self):
        self.assertEqual(
            "Project runner internal exception: PermissionError",
            MODULE.internal_failure_reason(PermissionError("token-value")),
        )
        self.assertEqual(
            "Project runner internal exception: Other",
            MODULE.internal_failure_reason(RuntimeError("token-value")),
        )

    def test_structured_events_map_only_to_fixed_sanitized_progress(self):
        stream = "\n".join(json.dumps(event) for event in (
            {"type": "thread.started", "thread_id": str(uuid.uuid4())},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "type": "reasoning", "text": "SECRET_REASONING_TOKEN"}},
            {"type": "item.started", "item": {
                "type": "command_execution", "command": "curl SECRET_COMMAND_TOKEN"}},
            {"type": "item.completed", "item": {
                "type": "command_execution", "aggregated_output": "SECRET_OUTPUT_TOKEN"}},
            {"type": "item.started", "item": {
                "type": "web_search", "query": "SECRET_QUERY_TOKEN"}},
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": "SECRET_ANSWER_TOKEN"}},
            {"type": "unsupported", "payload": "SECRET_UNKNOWN_TOKEN"},
            {"type": "turn.completed", "usage": {"hidden": "SECRET_USAGE_TOKEN"}},
        ))

        events = MODULE.normalize_codex_events(stream)

        self.assertEqual(
            ["CODEX_STARTED", "RUNNING_COMMAND", "INSPECTING_PROJECT", "FINALIZING"],
            [event["category"] for event in events],
        )
        serialized = json.dumps(events)
        for marker in (
            "SECRET_REASONING_TOKEN", "SECRET_COMMAND_TOKEN", "SECRET_OUTPUT_TOKEN",
            "SECRET_QUERY_TOKEN", "SECRET_ANSWER_TOKEN", "SECRET_UNKNOWN_TOKEN",
            "SECRET_USAGE_TOKEN",
        ):
            self.assertNotIn(marker, serialized)
        self.assertTrue(all(set(event) == {"category", "occurredAt", "message"} for event in events))

    def test_sandbox_command_has_only_derived_mounts_and_prompt_stays_on_stdin(self):
        session_id = str(uuid.uuid4())
        worktree = Path("/srv/atenea/workspaces/sessions") / session_id / "atenea"
        common = MODULE.GIT_COMMON_DIR
        final = Path("/tmp/atenea-codex-result-test/final.txt")
        resolv = Path("/tmp/atenea-codex-result-test/resolv.conf")
        instruction_mask = Path("/tmp/atenea-codex-result-test/empty-instructions")
        execution_id = str(uuid.uuid4())
        workload = self.workload()
        workload["message"] = "SECRET_PROMPT_MUST_NOT_APPEAR_IN_ARGV"
        command = MODULE.sandbox_command(
            workload, worktree, common, final, resolv, instruction_mask,
            "reviewed instructions", execution_id
        )
        joined = "\n".join(command)
        self.assertNotIn(workload["message"], joined)
        self.assertIn(str(worktree), command)
        self.assertIn(str(common), command)
        self.assertIn("/srv/atenea/repositories", command)
        self.assertIn("/home/jose/.codex", command)
        self.assertIn("developer_instructions=\"reviewed instructions\"", command)
        self.assertEqual(2, command.count(str(instruction_mask)))
        self.assertEqual(
            1,
            command.count(str(instruction_mask.with_name("project-instructions"))),
        )
        self.assertEqual(1, command.count("project_doc_max_bytes=0"))
        self.assertIn(str(worktree / "AGENTS.md"), command)
        self.assertIn("Group=atenea", command)
        self.assertIn("danger-full-access", command)
        self.assertNotIn("workspace-write", command)
        self.assertIn("GIT_CONFIG_COUNT", command)
        self.assertIn("GIT_CONFIG_KEY_0", command)
        self.assertIn("safe.directory", command)
        git_value_index = command.index("GIT_CONFIG_VALUE_0")
        self.assertEqual(str(worktree), command[git_value_index + 1])
        self.assertNotIn("ProtectKernelTunables=yes", command)
        self.assertNotIn("ProtectKernelLogs=yes", command)
        self.assertIn("ProtectKernelModules=yes", command)
        self.assertIn("ProtectControlGroups=yes", command)
        self.assertNotIn("/var/run/docker.sock", joined)
        for denied in (
            "IPAddressDeny=127.0.0.0/8",
            "IPAddressDeny=10.0.0.0/8",
            "IPAddressDeny=100.64.0.0/10",
            "IPAddressDeny=172.16.0.0/12",
            "IPAddressDeny=192.168.0.0/16",
            "IPAddressDeny=fc00::/7",
        ):
            self.assertIn(denied, command)
        self.assertNotIn("/srv/atenea/workspaces/sessions/", "\n".join(
            value for value in command
            if value not in {
                str(worktree),
                str(worktree.parent),
                str(worktree / "AGENTS.md"),
            }
        ))
        self.assertEqual("-", command[-1])

    def test_change_sandbox_mounts_only_the_derived_change_parent(self):
        request = self.change_request()
        change_key = request["changeOwnership"]["changeKey"]
        worktree = MODULE.CHANGE_WORKSPACE_PARENT / change_key / MODULE.PROJECT_ID
        command = MODULE.sandbox_command(
            request["workload"],
            worktree,
            MODULE.GIT_COMMON_DIR,
            Path("/tmp/atenea-codex-result-test/final.txt"),
            Path("/tmp/atenea-codex-result-test/resolv.conf"),
            Path("/tmp/atenea-codex-result-test/empty-instructions"),
            "reviewed instructions",
            request["executionId"],
        )
        serialized = "\n".join(command)
        self.assertIn(str(MODULE.CHANGE_WORKSPACE_PARENT), command)
        self.assertIn(str(worktree), command)
        self.assertNotIn(request["workload"]["message"], serialized)
        self.assertNotIn("databaseWorkSessionId", serialized)
        self.assertNotIn(request["changeOwnership"]["sourceFingerprintSha256"], serialized)

    def test_reviewed_instruction_projection_is_exact_clean_single_and_temporary(self):
        project_bytes = b"synthetic reviewed repository contract\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worktree = root / "worktree"
            worktree.mkdir()
            agents = worktree / "AGENTS.md"
            agents.write_bytes(project_bytes)
            subprocess.run(["git", "init", "-q"], cwd=worktree, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Contract test"],
                cwd=worktree,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "contract@atenea.invalid"],
                cwd=worktree,
                check=True,
            )
            subprocess.run(["git", "add", "AGENTS.md"], cwd=worktree, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "instructions"],
                cwd=worktree,
                check=True,
            )
            projection_root = root / "projection"
            projection_root.mkdir(mode=0o700)
            projection = MODULE.prepare_instruction_projection(
                projection_root,
                project_bytes,
            )

            self.assertEqual(b"", projection.ambient_mask.read_bytes())
            self.assertEqual(project_bytes, projection.project_source.read_bytes())
            self.assertNotEqual(projection.ambient_mask, projection.project_source)
            self.assertEqual(
                subprocess.run(
                    ["git", "cat-file", "blob", "HEAD:AGENTS.md"],
                    cwd=worktree,
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout,
                projection.project_source.read_bytes(),
            )

            workload = self.workload()
            workload["message"] = "SYNTHETIC_PROMPT_STDIN_ONLY"
            command = MODULE.sandbox_command(
                workload,
                worktree,
                MODULE.GIT_COMMON_DIR,
                root / "final.txt",
                root / "resolv.conf",
                projection.ambient_mask,
                "synthetic explicit reviewed bundle",
                str(uuid.uuid4()),
            )
            project_target = str(worktree / "AGENTS.md")
            project_target_index = command.index(project_target)
            self.assertEqual("--ro-bind", command[project_target_index - 2])
            self.assertEqual(
                str(projection.project_source),
                command[project_target_index - 1],
            )
            self.assertEqual(2, command.count(str(projection.ambient_mask)))
            self.assertEqual(1, command.count(str(projection.project_source)))
            self.assertEqual(1, command.count("project_doc_max_bytes=0"))
            self.assertEqual(
                1,
                command.count(
                    'developer_instructions="synthetic explicit reviewed bundle"'
                ),
            )
            self.assertNotIn(workload["message"], "\n".join(command))
            if Path("/usr/bin/bwrap").is_file():
                subprocess.run(
                    [
                        "/usr/bin/bwrap",
                        "--die-with-parent",
                        "--unshare-all",
                        "--ro-bind",
                        "/",
                        "/",
                        "--bind",
                        str(worktree),
                        str(worktree),
                        "--ro-bind",
                        str(projection.project_source),
                        project_target,
                        "--chdir",
                        str(worktree),
                        "/bin/sh",
                        "-ceu",
                        (
                            'test -z "$(git status --porcelain=v1 '
                            '--untracked-files=all)"; '
                            'test "$(git hash-object AGENTS.md)" = '
                            '"$(git rev-parse HEAD:AGENTS.md)"; '
                            '! printf changed >AGENTS.md 2>/dev/null; '
                            'test "$(git hash-object AGENTS.md)" = '
                            '"$(git rev-parse HEAD:AGENTS.md)"'
                        ),
                    ],
                    check=True,
                    timeout=30,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            self.assertEqual(
                "",
                subprocess.run(
                    ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                    cwd=worktree,
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                ).stdout,
            )
            ambient_path = projection.ambient_mask
            project_path = projection.project_source

        self.assertFalse(ambient_path.exists())
        self.assertFalse(project_path.exists())

    def test_resume_uses_only_exact_uuid_and_stdin(self):
        thread_id = str(uuid.uuid4())
        command = MODULE.sandbox_command(
            self.workload(thread_id),
            Path("/srv/atenea/workspaces/sessions/11111111-1111-4111-8111-111111111111/atenea"),
            MODULE.GIT_COMMON_DIR,
            Path("/tmp/atenea-codex-result-test/final.txt"),
            Path("/tmp/atenea-codex-result-test/resolv.conf"),
            Path("/tmp/atenea-codex-result-test/empty-instructions"),
            "reviewed instructions",
            str(uuid.uuid4()),
        )
        self.assertEqual(1, command.count("project_doc_max_bytes=0"))
        self.assertEqual(["resume", thread_id, "-"], command[-3:])

    def test_profiled_command_uses_only_validated_model_and_effort_flags(self):
        workload = self.profiled_workload(effort="xhigh")
        command = MODULE.sandbox_command(
            workload,
            Path("/srv/atenea/workspaces/sessions/11111111-1111-4111-8111-111111111111/atenea"),
            MODULE.GIT_COMMON_DIR,
            Path("/tmp/atenea-codex-result-test/final.txt"),
            Path("/tmp/atenea-codex-result-test/resolv.conf"),
            Path("/tmp/atenea-codex-result-test/empty-instructions"),
            "reviewed instructions",
            str(uuid.uuid4()),
        )

        self.assertEqual(1, command.count("--model"))
        model_index = command.index("--model")
        self.assertEqual("gpt-5.6-sol", command[model_index + 1])
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertNotIn("--provider", command)
        self.assertNotIn("--profile", command)
        self.assertEqual(
            {
                "modelId": "gpt-5.6-sol",
                "reasoningEffort": "xhigh",
                "catalogRevision": MODULE.CODEX_CATALOG_REVISION,
                "codexVersion": "0.145.0",
            },
            MODULE.effective_profile(workload),
        )

    def test_profiled_runner_rejects_installed_codex_version_drift(self):
        workload = self.profiled_workload()
        accepted = subprocess.CompletedProcess([], 0, "codex-cli 0.145.0\n", "")
        with patch.object(MODULE.subprocess, "run", return_value=accepted) as run:
            MODULE.validate_codex_version(workload)
        self.assertEqual([MODULE.CODEX, "--version"], run.call_args.args[0])

        moved = subprocess.CompletedProcess([], 0, "codex-cli 9.9.9\n", "")
        with patch.object(MODULE.subprocess, "run", return_value=moved):
            with self.assertRaises(SystemExit):
                MODULE.validate_codex_version(workload)

    def test_schema_rejects_complete_caller_authority_matrix(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed on this worker")
        schema = json.loads(
            (ROOT / "runtime-contract/agent-run-project-codex-v1.request.schema.json").read_text()
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        request = {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:ax42-01:work-session:" + str(uuid.uuid4()),
            "workloadClass": "NORMAL",
            "leaseGeneration": 1,
            "workload": self.workload(),
        }
        for field, value in (
            ("command", ["sh", "-lc", "id"]),
            ("image", "foreign.invalid/runtime:latest"),
            ("composeFile", "docker-compose.foreign.yml"),
            ("path", "/tmp/foreign"),
            ("host", "foreign.invalid"),
            ("slot", "slot4"),
            ("endpoint", "http://127.0.0.1:1"),
            ("environment", {"FORBIDDEN_REFERENCE": "synthetic"}),
            ("credential", "synthetic-reference"),
            ("ruleSource", "/tmp/foreign.rules"),
        ):
            candidate = json.loads(json.dumps(request))
            candidate["workload"][field] = value
            self.assertTrue(list(validator.iter_errors(candidate)), field)
        foreign_repository = json.loads(json.dumps(request))
        foreign_repository["workload"]["repository"] = (
            "https://github.com/foreign/repository.git"
        )
        self.assertTrue(list(validator.iter_errors(foreign_repository)))
        foreign_workspace = json.loads(json.dumps(request))
        foreign_workspace["workspaceIdentity"] = (
            "remote:foreign:work-session:" + str(uuid.uuid4())
        )
        self.assertTrue(list(validator.iter_errors(foreign_workspace)))

    def test_dynamic_commit_must_match_root_owned_configuration(self):
        config = {"commit": TEST_COMMIT, "workspaces": {}}
        request = {
            "dispatchId": str(uuid.uuid4()),
            "executionId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:ax42-01:work-session:" + str(uuid.uuid4()),
            "workload": self.workload(),
        }
        request["workload"]["commit"] = "2" * 40

        with self.assertRaises(SystemExit):
            MODULE.validate_request(request, config)

    def test_reviewed_instruction_bundle_is_exact_and_ambient_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worktree = root / "worktree"
            platform = root / "platform.md"
            worktree.mkdir()
            platform.write_text("platform contract\n", encoding="utf-8")
            platform.chmod(0o644)
            agents = worktree / "AGENTS.md"
            agents.write_text("repository contract\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=worktree, check=True)
            subprocess.run(["git", "config", "user.name", "Contract test"], cwd=worktree, check=True)
            subprocess.run(
                ["git", "config", "user.email", "contract@atenea.invalid"],
                cwd=worktree,
                check=True,
            )
            subprocess.run(["git", "add", "AGENTS.md"], cwd=worktree, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "instructions"], cwd=worktree, check=True)
            old = (
                MODULE.PLATFORM_INSTRUCTION_PATH,
                MODULE.PLATFORM_INSTRUCTION_UID,
                MODULE.PLATFORM_INSTRUCTION_SHA256,
                MODULE.PROJECT_INSTRUCTION_SHA256,
                MODULE.INSTRUCTION_BUNDLE_SHA256,
            )
            platform_bytes = platform.read_bytes()
            project_bytes = agents.read_bytes()
            MODULE.PLATFORM_INSTRUCTION_PATH = platform
            MODULE.PLATFORM_INSTRUCTION_UID = platform.stat().st_uid
            MODULE.PLATFORM_INSTRUCTION_SHA256 = hashlib.sha256(platform_bytes).hexdigest()
            MODULE.PROJECT_INSTRUCTION_SHA256 = hashlib.sha256(project_bytes).hexdigest()
            MODULE.INSTRUCTION_BUNDLE_SHA256 = hashlib.sha256(
                MODULE.INSTRUCTION_BUNDLE_REVISION.encode("ascii")
                + b"\0" + platform_bytes + b"\0" + project_bytes
            ).hexdigest()
            try:
                bundle = MODULE.validate_instruction_bundle(worktree)
                self.assertIn("platform contract", bundle.developer_instructions)
                self.assertIn("repository contract", bundle.developer_instructions)
                self.assertEqual(project_bytes, bundle.project_bytes)

                (worktree / "AGENTS.override.md").write_text("ambient\n", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    MODULE.validate_instruction_bundle(worktree)
                (worktree / "AGENTS.override.md").unlink()

                (worktree / ".codex").mkdir()
                with self.assertRaises(SystemExit):
                    MODULE.validate_instruction_bundle(worktree)
                (worktree / ".codex").rmdir()

                agents.write_text("changed contract\n", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    MODULE.validate_instruction_bundle(worktree)
            finally:
                (
                    MODULE.PLATFORM_INSTRUCTION_PATH,
                    MODULE.PLATFORM_INSTRUCTION_UID,
                    MODULE.PLATFORM_INSTRUCTION_SHA256,
                    MODULE.PROJECT_INSTRUCTION_SHA256,
                    MODULE.INSTRUCTION_BUNDLE_SHA256,
                ) = old

    def test_exact_head_cleanliness_and_mirror_move_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worktree = root / "atenea"
            common = root / "atenea.git"
            worktree.mkdir()
            common.mkdir()
            manifest = worktree / "ops" / "atenea-runtime.json"
            manifest.parent.mkdir()
            manifest.write_bytes(b"manifest")
            allocation = worktree.parent / "runtime-allocation-v1.json"
            allocation.write_bytes(b"allocation")
            old_common = MODULE.GIT_COMMON_DIR
            old_manifest = MODULE.MANIFEST_SHA256
            MODULE.GIT_COMMON_DIR = common
            MODULE.MANIFEST_SHA256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
            record = {
                "sessionId": str(uuid.uuid4()),
                "worktree": str(worktree),
                "allocationSha256": hashlib.sha256(allocation.read_bytes()).hexdigest(),
                "canonicalCommit": TEST_COMMIT,
            }

            def observed(command, _cwd):
                joined = " ".join(command)
                if "--show-toplevel" in joined:
                    return str(worktree)
                if "remote get-url" in joined:
                    return MODULE.REPOSITORY
                if "--git-common-dir" in joined:
                    return str(common)
                if "refs/remotes/origin/" in joined:
                    return TEST_COMMIT
                if "HEAD^{commit}" in joined:
                    return TEST_COMMIT
                if "status --porcelain" in joined:
                    return ""
                raise AssertionError(joined)

            try:
                with patch.object(MODULE, "checked", side_effect=observed):
                    self.assertEqual(common, MODULE.validate_worktree(worktree, record))

                for changed_fragment, changed_value in (
                    ("status --porcelain", "?? draft.txt"),
                    ("HEAD^{commit}", "2" * 40),
                    ("refs/remotes/origin/", "2" * 40),
                ):
                    def changed(command, cwd, fragment=changed_fragment, value=changed_value):
                        joined = " ".join(command)
                        if fragment in joined:
                            return value
                        return observed(command, cwd)

                    with patch.object(MODULE, "checked", side_effect=changed):
                        with self.assertRaises(SystemExit):
                            MODULE.validate_worktree(worktree, record)
            finally:
                MODULE.GIT_COMMON_DIR = old_common
                MODULE.MANIFEST_SHA256 = old_manifest

    def test_change_worktree_reuses_sealed_workspace_and_rejects_stale_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            mirror = root / "atenea.git"
            changes = root / "changes"
            state = root / "state"
            changes.mkdir()
            state.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main", source], check=True)
            subprocess.run(
                ["git", "config", "user.name", "Contract test"], cwd=source, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "contract@atenea.invalid"],
                cwd=source,
                check=True,
            )
            (source / "ops").mkdir()
            manifest = source / "ops" / "atenea-runtime.json"
            manifest.write_text("{}\n", encoding="utf-8")
            (source / "AGENTS.md").write_text("reviewed\n", encoding="utf-8")
            (source / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=source, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "base"], cwd=source, check=True
            )
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            subprocess.run(["git", "clone", "-q", "--bare", source, mirror], check=True)
            subprocess.run(
                ["git", "--git-dir", mirror, "remote", "set-url", "origin", MODULE.REPOSITORY],
                check=True,
            )
            subprocess.run(
                [
                    "git", "--git-dir", mirror, "update-ref",
                    "refs/remotes/origin/main", commit,
                ],
                check=True,
            )
            mediator = CHANGE_MEDIATOR.WorkspaceMediator(
                mirror, changes, state / "workspace.lock", test_mode=True
            )
            runner_request = self.change_request()
            runner_request["workload"]["commit"] = commit
            runner_request["workload"]["manifestSha256"] = hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest()
            ownership = runner_request["changeOwnership"]
            ownership["baseCommit"] = commit
            ownership["expectedCanonicalCommit"] = commit

            def mediator_request(operation="PROVISION", revision=0, source_sha="a" * 64):
                operation_id = str(uuid.uuid4())
                body = {
                    "schemaVersion": 1,
                    "protocolVersion": "development-change-workspace/v1",
                    "effect": (
                        "CREATE_IF_ABSENT_EXACT" if operation == "PROVISION"
                        else "OBSERVE_ONLY"
                    ),
                    "operationId": operation_id,
                    "idempotencyKey": operation_id,
                    "operation": operation,
                    "predecessorOperationId": None,
                    "changeKey": ownership["changeKey"],
                    "databaseProjectId": ownership["databaseProjectId"],
                    "projectId": MODULE.PROJECT_ID,
                    "repository": MODULE.REPOSITORY,
                    "repositoryBranch": MODULE.BRANCH,
                    "baseCommit": commit,
                    "expectedCanonicalCommit": commit,
                    "workspaceBranch": f"atenea/change-{ownership['changeKey']}",
                    "workspaceIdentity": ownership["workspaceIdentity"],
                    "workerId": "ax42-01",
                    "sourceRevision": revision,
                    "sourceFingerprintSha256": source_sha,
                }
                body["requestFingerprintSha256"] = CHANGE_MEDIATOR.canonical_sha256(body)
                return body

            provisioned = mediator.execute(mediator_request(), "PROVISION")
            ownership["workspaceOwnershipFingerprintSha256"] = provisioned[
                "ownershipFingerprintSha256"
            ]
            config = self.atenea_config()
            config["commit"] = commit
            worktree = changes / ownership["changeKey"] / MODULE.PROJECT_ID
            os.chmod(worktree.parent, 0o700)
            os.chmod(worktree, 0o700)
            os.chmod(worktree / "tracked.txt", 0o600)
            old_values = (
                MODULE.CHANGE_WORKSPACE_PARENT,
                MODULE.GIT_COMMON_DIR,
                MODULE.MANIFEST_SHA256,
            )
            MODULE.CHANGE_WORKSPACE_PARENT = changes
            MODULE.GIT_COMMON_DIR = mirror
            MODULE.MANIFEST_SHA256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
            try:
                with patch.object(
                    MODULE,
                    "change_workspace_owner_ids",
                    return_value=(os.getuid(), {os.getuid()}, os.getgid()),
                ):
                    workload, observed_worktree = MODULE.validate_request(
                        runner_request, config
                    )
                    self.assertEqual(MODULE.CHANGE_CAPABILITY, workload["kind"])
                    self.assertEqual(worktree, observed_worktree)
                    self.assertEqual(
                        mirror, MODULE.validate_change_worktree(runner_request, worktree)
                    )
                    self.assertEqual(0o770, worktree.parent.stat().st_mode & 0o777)
                    self.assertEqual(0o770, worktree.stat().st_mode & 0o777)
                    self.assertEqual(0o660, (worktree / "tracked.txt").stat().st_mode & 0o777)
                    self.assertEqual(
                        0o600,
                        (worktree.parent / "workspace-v1.json").stat().st_mode & 0o777,
                    )

                    (worktree / "tracked.txt").write_text("changed\n", encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        MODULE.validate_change_worktree(runner_request, worktree)

                    observed = mediator.execute(
                        mediator_request("INSPECT", 1), "INSPECT"
                    )
                    ownership["sourceRevision"] = 1
                    ownership["sourceFingerprintSha256"] = observed[
                        "sourceFingerprintSha256"
                    ]
                    ownership["workspaceOwnershipFingerprintSha256"] = observed[
                        "ownershipFingerprintSha256"
                    ]
                    self.assertEqual(
                        mirror, MODULE.validate_change_worktree(runner_request, worktree)
                    )

                    crossed = json.loads(json.dumps(runner_request))
                    crossed["changeOwnership"]["remoteSessionId"] = str(uuid.uuid4())
                    with self.assertRaises(SystemExit):
                        MODULE.validate_request(crossed, config)
            finally:
                (
                    MODULE.CHANGE_WORKSPACE_PARENT,
                    MODULE.GIT_COMMON_DIR,
                    MODULE.MANIFEST_SHA256,
                ) = old_values


if __name__ == "__main__":
    unittest.main()
