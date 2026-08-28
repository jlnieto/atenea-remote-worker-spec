#!/usr/bin/env python3

import io
import hashlib
import json
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid
import os
import subprocess
import urllib.error
import urllib.request
from http import HTTPStatus
from pathlib import Path

from importlib.machinery import SourceFileLoader

MODULE = SourceFileLoader(
    "agent_run_worker_v1",
    str(Path(__file__).with_name("agent-run-worker-v1.py")),
).load_module()
TEST_COMMIT = "1" * 40


class WorkerErrorEnvelopeTest(unittest.TestCase):
    def test_closed_envelope_has_only_safe_bounded_fields(self):
        payload = MODULE.worker_error_envelope(
            "NORMAL_CAPACITY_EXHAUSTED",
            "CAPACITY",
            True,
            "WAIT",
            "11111111-1111-4111-8111-111111111111",
        )

        self.assertEqual(
            {
                "schemaVersion", "code", "category", "retryable",
                "nextAction", "blockerSessionId",
            },
            set(payload),
        )
        self.assertEqual(MODULE.WORKER_ERROR_SCHEMA, payload["schemaVersion"])
        self.assertLessEqual(
            len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()),
            MODULE.WORKER_ERROR_MAX_BYTES,
        )
        self.assertEqual(payload, MODULE.validate_worker_error_envelope(payload))
        with self.assertRaises(ValueError):
            MODULE.validate_worker_error_envelope({**payload, "detail": "unsafe"})

    def test_reviewed_mediator_codes_map_to_fixed_safe_decisions(self):
        expected = {
            "NORMAL_CAPACITY_EXHAUSTED": ("CAPACITY", True, "WAIT"),
            "HEAVY_CAPACITY_EXHAUSTED": ("CAPACITY", True, "WAIT"),
            "RUNTIME_OWNERSHIP_CONFLICT": (
                "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
            ),
            "RECONCILIATION_REQUIRED": (
                "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
            ),
            "OPERATION_FAILED": (
                "POLICY", False, "CONTACT_PLATFORM_ADMINISTRATOR",
            ),
            "ATENEA_WORKSPACE_ACTIVATION_REJECTED": (
                "VALIDATION", False, "CONTACT_PLATFORM_ADMINISTRATOR",
            ),
        }

        for code, values in expected.items():
            with self.subTest(code=code):
                payload = MODULE.reviewed_mediator_error_envelope(json.dumps({"code": code}))
                self.assertEqual(code, payload["code"])
                self.assertEqual(values, (
                    payload["category"], payload["retryable"], payload["nextAction"],
                ))

    def test_mediator_envelope_rejects_unknown_unsafe_or_ambiguous_input(self):
        rejected = (
            {"code": "UNKNOWN_MEDIATOR_CODE"},
            {"code": "NORMAL_CAPACITY_EXHAUSTED", "detail": "/srv/foreign"},
            {"code": "NORMAL_CAPACITY_EXHAUSTED", "command": "id"},
            {"code": "NORMAL_CAPACITY_EXHAUSTED", "blockerSessionId": "not-a-uuid"},
            {
                "code": "RUNTIME_OWNERSHIP_CONFLICT",
                "blockerSessionId": "11111111-1111-4111-8111-111111111111",
            },
        )
        for payload in rejected:
            with self.subTest(payload=set(payload)), self.assertRaises(ValueError):
                MODULE.reviewed_mediator_error_envelope(json.dumps(payload))

        oversized = " " * (MODULE.MEDIATOR_ERROR_MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "size"):
            MODULE.reviewed_mediator_error_envelope(oversized)

    def test_reviewed_stderr_maps_code_without_copying_detail(self):
        marker = "unsafe-command-and-path-detail"
        payload = MODULE.reviewed_mediator_stderr_envelope(
            f"NORMAL_CAPACITY_EXHAUSTED: {marker}\nNext action: ignored"
        )

        self.assertEqual("NORMAL_CAPACITY_EXHAUSTED", payload["code"])
        self.assertNotIn(marker, json.dumps(payload))
        with self.assertRaises(ValueError):
            MODULE.reviewed_mediator_stderr_envelope(f"UNKNOWN_FAILURE: {marker}")


class WorkspaceReleaseContractTest(unittest.TestCase):
    def setUp(self):
        self.session_id = "11111111-1111-4111-8111-111111111111"
        self.request = {
            "operationId": "22222222-2222-4222-8222-222222222222",
            "idempotencyKey": "33333333-3333-4333-8333-333333333333",
            "sessionId": self.session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + self.session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + self.session_id,
        }

    def receipt(self):
        receipt = {
            "schemaVersion": MODULE.WORKSPACE_RELEASE_SCHEMA,
            "state": "RELEASED",
            **self.request,
            "workerId": "ax42-01",
            "requestFingerprintSha256": MODULE.canonical_hash(self.request),
            "revision": 6,
            "removed": {
                "runtimeContainers": 0,
                "runtimeNetworks": 0,
                "sessionImages": 0,
                "previewResources": 0,
                "brokerResources": 0,
                "browserProcesses": 0,
            },
            "released": {
                "registration": True,
                "normalAdmission": True,
                "heavyAdmission": True,
                "allocation": True,
            },
            "retained": {
                "workspaceRecord": True,
                "worktree": True,
                "git": True,
                "turns": True,
                "agentRuns": True,
                "attachments": True,
                "logs": True,
                "artifacts": True,
                "backups": True,
                "policyVolumes": True,
            },
            "ownershipFingerprintSha256": "4" * 64,
            "valuesExposed": False,
        }
        receipt["receiptSha256"] = MODULE.canonical_hash(receipt)
        return receipt

    def test_exact_request_and_receipt_are_closed_and_ownership_matching(self):
        self.assertEqual(MODULE.WORKSPACE_RELEASE_PATH, "/v1/project-workspaces/release")
        self.assertEqual(self.request, MODULE.validate_workspace_release_request(self.request))
        receipt = self.receipt()
        self.assertEqual(
            receipt,
            MODULE.validate_workspace_release_receipt(self.request, "ax42-01", receipt),
        )

    def test_request_fingerprint_is_immutable_and_changed_input_conflicts(self):
        first = MODULE.workspace_release_request_fingerprint(self.request)
        second = MODULE.workspace_release_request_fingerprint(dict(self.request))
        changed_identity = {
            **self.request,
            "operationId": "55555555-5555-4555-8555-555555555555",
            "idempotencyKey": "66666666-6666-4666-8666-666666666666",
        }
        changed_input = {**self.request, "commit": "7" * 40}

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            MODULE.validate_workspace_release_repetition(self.request, dict(self.request)),
        )
        self.assertNotEqual(
            first, MODULE.workspace_release_request_fingerprint(changed_identity)
        )
        with self.assertRaisesRegex(MODULE.ProtocolError, "immutable"):
            MODULE.validate_workspace_release_repetition(self.request, changed_input)

    def test_request_rejects_every_caller_authority_field(self):
        for key, value in {
            "command": "id",
            "path": "/srv/foreign",
            "slot": "slot2",
            "port": 8080,
            "service": "foreign.service",
            "endpoint": "http://foreign",
            "resourceName": "foreign",
            "label": "foreign=true",
            "credential": "not-accepted",
            "deletionTarget": "foreign",
        }.items():
            with self.subTest(key=key), self.assertRaises(MODULE.ProtocolError):
                MODULE.validate_workspace_release_request({**self.request, key: value})

    def test_receipt_rejects_mismatched_ownership_or_open_projection(self):
        for changed in (
            {"workerId": "foreign-worker"},
            {"workspaceIdentity": "remote:foreign:work-session:" + self.session_id},
            {"revision": 0},
            {"revision": 5},
            {"valuesExposed": True},
            {"removed": {**self.receipt()["removed"], "runtimeContainers": "1"}},
            {"released": {**self.receipt()["released"], "allocation": False}},
            {"retained": {**self.receipt()["retained"], "git": False}},
        ):
            receipt = {**self.receipt(), **changed}
            receipt["receiptSha256"] = MODULE.canonical_hash(
                {key: value for key, value in receipt.items() if key != "receiptSha256"}
            )
            with self.subTest(changed=set(changed)), self.assertRaises(MODULE.ProtocolError):
                MODULE.validate_workspace_release_receipt(self.request, "ax42-01", receipt)

    def test_non_terminal_exact_execution_blocks_before_release(self):
        executions = {
            "dispatch": {
                "sessionId": self.session_id,
                "status": "RECONCILING",
            },
            "terminal": {
                "sessionId": self.session_id,
                "status": "FAILED",
            },
        }
        with self.assertRaisesRegex(MODULE.ProtocolError, "terminal"):
            MODULE.assert_no_non_terminal_session_execution(executions, self.session_id)
        executions["dispatch"]["status"] = "CANCELLED"
        MODULE.assert_no_non_terminal_session_execution(executions, self.session_id)


class WorkspaceReleaseWorkerExecutionTest(WorkspaceReleaseContractTest):
    def setUp(self):
        super().setUp()
        self.temporary = tempfile.TemporaryDirectory()
        self.releaser = Path(self.temporary.name) / "fixed-releaser"
        self.releaser.write_text("reviewed fixed mediator\n", encoding="utf-8")
        self.state = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            privilege_command=(),
            project_workspace_releaser=self.releaser,
            unactivated_release_enabled=True,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_release_invokes_only_fixed_mediator_with_canonical_stdin(self):
        receipt = self.receipt()
        completed = subprocess.CompletedProcess(
            [str(self.releaser)], 0, json.dumps(receipt), ""
        )
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            first = self.state.release_workspace(self.request)
            second = self.state.release_workspace(dict(self.request))

        self.assertEqual(receipt, first)
        self.assertEqual(first, second)
        self.assertEqual(2, run.call_count)
        for invocation in run.call_args_list:
            self.assertEqual([str(self.releaser)], invocation.args[0])
            self.assertEqual(
                json.dumps(self.request, sort_keys=True, separators=(",", ":")),
                invocation.kwargs["input"],
            )
            self.assertEqual(300, invocation.kwargs["timeout"])

    def test_non_terminal_execution_blocks_before_mediator(self):
        self.state.executions["dispatch"] = {
            "sessionId": self.session_id,
            "status": "RECONCILING",
        }
        with mock.patch.object(MODULE.subprocess, "run") as run:
            with self.assertRaisesRegex(MODULE.ProtocolError, "terminal"):
                self.state.release_workspace(self.request)
        run.assert_not_called()

    def test_timeout_and_malformed_receipt_are_distinct_transport_failures(self):
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=MODULE.subprocess.TimeoutExpired([str(self.releaser)], 300),
        ):
            with self.assertRaises(MODULE.ProtocolError) as timeout:
                self.state.release_workspace(self.request)
        self.assertEqual(HTTPStatus.GATEWAY_TIMEOUT, timeout.exception.status)
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([str(self.releaser)], 0, "{}", ""),
        ):
            with self.assertRaises(MODULE.ProtocolError) as malformed:
                self.state.release_workspace(self.request)
        self.assertEqual(HTTPStatus.BAD_GATEWAY, malformed.exception.status)

    def test_unactivated_release_is_default_off_durable_and_idempotent(self):
        disabled = MODULE.WorkerState(
            Path(self.temporary.name) / "disabled",
            "ax42-01",
            privilege_command=(),
            project_workspace_releaser=self.releaser,
        )
        with mock.patch.object(MODULE.subprocess, "run") as run:
            with self.assertRaises(MODULE.ProtocolError) as rejected:
                disabled.release_unactivated_workspace(self.request)
        self.assertEqual(HTTPStatus.FORBIDDEN, rejected.exception.status)
        run.assert_not_called()

        diagnosis = {
            "schemaVersion": MODULE.WORKSPACE_UNACTIVATED_DIAGNOSIS_SCHEMA,
            "state": "UNACTIVATED_ABSENCE_CONFIRMED",
            "sessionId": self.request["sessionId"],
            "workspaceIdentity": self.request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "ax42-01",
            "requestFingerprintSha256": MODULE.canonical_hash(self.request),
            "absenceFingerprintSha256": "9" * 64,
            "valuesExposed": False,
        }
        completed = subprocess.CompletedProcess(
            [str(self.releaser), "--diagnose-unactivated"],
            0,
            json.dumps(diagnosis),
            "",
        )
        with mock.patch.object(
            MODULE.subprocess, "run", return_value=completed
        ) as run:
            first = self.state.release_unactivated_workspace(self.request)
            second = self.state.release_unactivated_workspace(dict(self.request))

        self.assertEqual(first, second)
        self.assertEqual("RELEASED", first["state"])
        self.assertEqual(6, first["revision"])
        self.assertEqual(
            {key: 0 for key in MODULE.WORKSPACE_RELEASE_REMOVED_KEYS},
            first["removed"],
        )
        self.assertEqual(1, run.call_count)
        self.assertEqual(
            [str(self.releaser), "--diagnose-unactivated"],
            run.call_args.args[0],
        )
        self.assertEqual(60, run.call_args.kwargs["timeout"])

        restarted = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            privilege_command=(),
            project_workspace_releaser=self.releaser,
            unactivated_release_enabled=True,
        )
        with mock.patch.object(MODULE.subprocess, "run") as repeated:
            self.assertEqual(
                first,
                restarted.release_unactivated_workspace(dict(self.request)),
            )
        repeated.assert_not_called()

    def test_unactivated_release_rejects_any_prior_execution_before_mediator(self):
        self.state.executions["terminal"] = {
            "sessionId": self.session_id,
            "status": "FAILED",
        }
        with mock.patch.object(MODULE.subprocess, "run") as run:
            with self.assertRaisesRegex(MODULE.ProtocolError, "no worker execution"):
                self.state.release_unactivated_workspace(self.request)
        run.assert_not_called()

    def test_capacity_owner_diagnosis_invokes_only_fixed_read_only_mode(self):
        request = {
            key: value for key, value in self.request.items()
            if key not in {"operationId", "idempotencyKey"}
        }
        response = {
            "schemaVersion": MODULE.WORKSPACE_CAPACITY_OWNER_SCHEMA,
            "state": "OWNED",
            "sessionId": request["sessionId"],
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "ax42-01",
            "requestFingerprintSha256": MODULE.canonical_hash(request),
            "ownershipFingerprintSha256": "7" * 64,
            "valuesExposed": False,
        }
        completed = subprocess.CompletedProcess(
            [str(self.releaser), "--diagnose-capacity-owner"],
            0,
            json.dumps(response),
            "",
        )
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            observed = self.state.diagnose_workspace_capacity_owner(request)

        self.assertEqual(response, observed)
        self.assertEqual(
            [str(self.releaser), "--diagnose-capacity-owner"],
            run.call_args.args[0],
        )
        self.assertEqual(60, run.call_args.kwargs["timeout"])
        for forbidden in (
            "command", "path", "slot", "port", "service", "endpoint",
            "resourceName", "label", "credential", "deletionTarget",
        ):
            with self.subTest(field=forbidden), self.assertRaises(MODULE.ProtocolError):
                MODULE.validate_workspace_capacity_owner_request(
                    {**request, forbidden: "caller-value"}
                )
    def test_release_preflight_invokes_only_fixed_non_mutating_mode(self):
        response = {
            "schemaVersion": MODULE.WORKSPACE_RELEASE_PREFLIGHT_SCHEMA,
            "state": "PREFLIGHT_ACCEPTED",
            "operationId": self.request["operationId"],
            "sessionId": self.request["sessionId"],
            "workspaceIdentity": self.request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "ax42-01",
            "requestFingerprintSha256": MODULE.canonical_hash(self.request),
            "ownershipFingerprintSha256": "7" * 64,
            "allocationFingerprintSha256": "8" * 64,
            "valuesExposed": False,
        }
        completed = subprocess.CompletedProcess(
            [str(self.releaser), "--diagnose-release-preflight"],
            0,
            json.dumps(response),
            "",
        )
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            observed = self.state.diagnose_workspace_release_preflight(
                self.request
            )

        self.assertEqual(response, observed)
        self.assertEqual(
            [str(self.releaser), "--diagnose-release-preflight"],
            run.call_args.args[0],
        )
        self.assertEqual(60, run.call_args.kwargs["timeout"])
        self.assertEqual(
            json.dumps(self.request, sort_keys=True, separators=(",", ":")),
            run.call_args.kwargs["input"],
        )
        for forbidden in (
            "command", "path", "slot", "port", "service", "endpoint",
            "resourceName", "label", "credential", "deletionTarget",
        ):
            with self.subTest(field=forbidden), self.assertRaises(MODULE.ProtocolError):
                MODULE.validate_workspace_release_request(
                    {**self.request, forbidden: "caller-value"}
                )


class WorkspaceReadinessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.session_id = "11111111-1111-4111-8111-111111111111"
        self.request = {
            "sessionId": self.session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + self.session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + self.session_id,
        }
        self.state = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            project_readiness_enabled=True,
        )
        self.refreshes = []
        self.state._refresh_project_mirror = lambda route: self.refreshes.append(
            route["identity"]["projectId"]
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_off_rejects_before_refresh(self):
        disabled = MODULE.WorkerState(
            Path(self.temporary.name) / "disabled",
            "ax42-01",
        )
        with mock.patch.object(disabled, "_refresh_project_mirror") as refresh:
            with self.assertRaises(MODULE.ProtocolError) as rejected:
                disabled.diagnose_workspace_readiness(self.request)
        self.assertEqual(HTTPStatus.FORBIDDEN, rejected.exception.status)
        refresh.assert_not_called()

    def test_equal_commit_is_retryable_without_activation(self):
        self.state._observe_project_commit = lambda _route: TEST_COMMIT
        with mock.patch.object(self.state, "_is_project_commit_ancestor") as ancestor:
            response = self.state.diagnose_workspace_readiness(self.request)

        self.assertEqual("READY_FOR_RETRY", response["state"])
        self.assertTrue(response["retryAllowed"])
        self.assertEqual("RETRY_AGENT_RUN", response["nextAction"])
        self.assertEqual(["atenea"], self.refreshes)
        ancestor.assert_not_called()

    def test_exact_ancestor_requires_fresh_session_without_activation(self):
        current = "2" * 40
        self.state._observe_project_commit = lambda _route: current
        self.state._is_project_commit_ancestor = lambda _route, old, new: (
            old == TEST_COMMIT and new == current
        )

        response = self.state.diagnose_workspace_readiness(self.request)

        self.assertEqual("SOURCE_ADVANCED", response["state"])
        self.assertFalse(response["retryAllowed"])
        self.assertEqual("START_FRESH_SESSION", response["nextAction"])
        self.assertEqual(TEST_COMMIT, response["requestedCommit"])
        self.assertEqual(current, response["canonicalCommit"])
        self.assertFalse(response["valuesExposed"])

    def test_unrelated_or_foreign_source_fails_deterministically(self):
        self.state._observe_project_commit = lambda _route: "2" * 40
        self.state._is_project_commit_ancestor = lambda *_args: False
        with self.assertRaises(MODULE.ProtocolError) as rejected:
            self.state.diagnose_workspace_readiness(self.request)
        self.assertEqual(HTTPStatus.CONFLICT, rejected.exception.status)
        self.assertEqual("OWNERSHIP", rejected.exception.safe_error["category"])
        for forbidden in (
            "command", "path", "slot", "port", "service", "endpoint",
            "resourceName", "label", "credential", "deletionTarget",
        ):
            with self.subTest(field=forbidden), self.assertRaises(MODULE.ProtocolError):
                MODULE.validate_workspace_readiness_request(
                    {**self.request, forbidden: "caller-value"}
                )


class WorkerStateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = MODULE.WorkerState(Path(self.temporary.name), "test-worker", 4, 2)
        self.state.start()

    def tearDown(self):
        self.state.stop()
        self.temporary.cleanup()

    def request(self, *, workload_class="NORMAL", duration=250, message="hello"):
        return {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:test:" + str(uuid.uuid4()),
            "workloadClass": workload_class,
            "leaseGeneration": 1,
            "workload": {
                "kind": "synthetic-routing-v1",
                "message": message,
                "durationMs": duration,
                "steps": 5,
            },
        }

    def wait_terminal(self, dispatch_id, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            execution = self.state.get(dispatch_id)
            if execution["status"] in MODULE.TERMINAL:
                return execution
            time.sleep(0.02)
        self.fail("execution did not become terminal")

    def exact_operation(self, execution):
        return {
            "executionId": execution["executionId"],
            "sessionId": execution["sessionId"],
            "workspaceIdentity": execution["workspaceIdentity"],
            "leaseGeneration": execution["leaseGeneration"],
        }

    def test_duplicate_dispatch_returns_same_execution_and_conflict_is_closed(self):
        request = self.request()
        first, created = self.state.create(request)
        second, created_again = self.state.create(json.loads(json.dumps(request)))
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["executionId"], second["executionId"])
        request["workload"]["message"] = "different"
        with self.assertRaisesRegex(MODULE.ProtocolError, "different immutable request"):
            self.state.create(request)
        self.assertEqual(first["executionId"], self.state.get(first["dispatchId"])["executionId"])

    def test_progress_coalesces_before_sequence_and_retains_newest_200(self):
        request = self.request(duration=1000)
        with self.state.lock:
            execution, _ = self.state.create(request)
            stored = self.state.executions[request["dispatchId"]]
            next_sequence = stored["nextProgressSequence"]

            self.assertFalse(self.state._append_progress(
                stored, "QUEUED", "Execution is queued for admission."
            ))
            self.assertEqual(next_sequence, stored["nextProgressSequence"])

            for index in range(205):
                category = "CHECKING" if index % 2 == 0 else "WAITING"
                message = "Checking the accepted project." if index % 2 == 0 else "Waiting for a bounded operation."
                self.assertTrue(self.state._append_progress(stored, category, message))

            events = stored["progressEvents"]
            self.assertEqual(MODULE.PROGRESS_LIMIT, len(events))
            self.assertGreater(events[0]["sequence"], 1)
            self.assertEqual(sorted(event["sequence"] for event in events), [event["sequence"] for event in events])
            self.assertEqual(execution["executionId"], events[-1]["executionId"])

    def test_four_normal_slots_queue_fifth(self):
        requests = [self.request(duration=800) for _ in range(5)]
        for request in requests:
            self.state.create(request)
        time.sleep(0.15)
        statuses = [self.state.get(item["dispatchId"])["status"] for item in requests]
        self.assertEqual(4, sum(status in {"STARTING", "RUNNING"} for status in statuses))
        self.assertEqual(1, statuses.count("QUEUED"))

    def test_two_heavy_permits_queue_third(self):
        requests = [self.request(workload_class="HEAVY", duration=700) for _ in range(3)]
        for request in requests:
            self.state.create(request)
        time.sleep(0.15)
        statuses = [self.state.get(item["dispatchId"])["status"] for item in requests]
        self.assertEqual(2, sum(status in {"STARTING", "RUNNING"} for status in statuses))
        self.assertEqual(1, statuses.count("QUEUED"))

    def test_cancel_exact_execution_preserves_other(self):
        first = self.request(duration=700)
        second = self.request(duration=250)
        first_execution, _ = self.state.create(first)
        second_execution, _ = self.state.create(second)
        self.state.cancel(first["dispatchId"], {"executionId": first_execution["executionId"]})
        cancelled = self.wait_terminal(first["dispatchId"])
        completed = self.wait_terminal(second["dispatchId"])
        self.assertEqual("CANCELLED", cancelled["status"])
        self.assertEqual("SUCCEEDED", completed["status"])

    def test_closed_exact_cancel_rejects_foreign_ambiguous_and_added_authority(self):
        first = self.request(duration=700)
        second = self.request(duration=250)
        first_execution, _ = self.state.create(first)
        self.state.create(second)
        exact = self.exact_operation(first_execution)

        for field, value in (
            ("executionId", str(uuid.uuid4())),
            ("sessionId", str(uuid.uuid4())),
            ("workspaceIdentity", "remote:foreign"),
            ("leaseGeneration", 2),
        ):
            rejected = {**exact, field: value}
            with self.assertRaises(MODULE.ProtocolError):
                self.state.cancel_exact(first["dispatchId"], rejected)
        with self.assertRaisesRegex(MODULE.ProtocolError, "fields are invalid"):
            self.state.cancel_exact(first["dispatchId"], {**exact, "command": "id"})

        self.state.cancel_exact(first["dispatchId"], exact)
        self.assertEqual("CANCELLED", self.wait_terminal(first["dispatchId"])["status"])
        self.assertEqual("SUCCEEDED", self.wait_terminal(second["dispatchId"])["status"])

    def test_reconcile_inspection_is_read_only_and_doctor_is_sanitized(self):
        marker = "SECRET_PROMPT_AND_RESULT_MARKER"
        request = self.request(duration=100, message=marker)
        execution, _ = self.state.create(request)
        terminal = self.wait_terminal(request["dispatchId"])
        exact = self.exact_operation(terminal)
        state_before = self.state.state_file.read_bytes()

        first = self.state.inspect_reconciliation(request["dispatchId"], exact)
        second = self.state.inspect_reconciliation(request["dispatchId"], exact)
        diagnostic = self.state.doctor(request["dispatchId"], exact)

        self.assertEqual(first, second)
        self.assertEqual(state_before, self.state.state_file.read_bytes())
        self.assertEqual("agent-run-doctor-v1", diagnostic["schemaVersion"])
        self.assertEqual("TERMINAL", diagnostic["observation"])
        self.assertFalse(diagnostic["valuesExposed"])
        self.assertNotIn(marker, json.dumps(diagnostic))
        for forbidden in (
            "workload", "result", "message", "command", "output", "path",
            "host", "slot", "environment", "credential",
        ):
            self.assertNotIn(forbidden, diagnostic)

        for operation in (self.state.inspect_reconciliation, self.state.doctor):
            with self.assertRaises(MODULE.ProtocolError):
                operation(request["dispatchId"], {**exact, "host": "foreign.invalid"})
            with self.assertRaises(MODULE.ProtocolError):
                operation(request["dispatchId"], {**exact, "sessionId": str(uuid.uuid4())})
        self.assertEqual(state_before, self.state.state_file.read_bytes())

    def test_restart_recovers_same_execution_identity(self):
        request = self.request(duration=700)
        created, _ = self.state.create(request)
        time.sleep(0.15)
        self.state.stop()
        recovered = MODULE.WorkerState(Path(self.temporary.name), "test-worker", 4, 2)
        recovered.start()
        self.state = recovered
        terminal = self.wait_terminal(request["dispatchId"])
        self.assertEqual(created["executionId"], terminal["executionId"])
        self.assertEqual("SUCCEEDED", terminal["status"])

    def test_terminal_progress_and_result_are_byte_stable_across_worker_restart(self):
        request = self.request(duration=100)
        created, _ = self.state.create(request)
        terminal = self.wait_terminal(request["dispatchId"])
        before = json.dumps(terminal, sort_keys=True, separators=(",", ":"))

        self.state.stop()
        recovered = MODULE.WorkerState(Path(self.temporary.name), "test-worker", 4, 2)
        duplicate, was_created = recovered.create(json.loads(json.dumps(request)))
        self.state = recovered

        self.assertFalse(was_created)
        self.assertEqual(created["executionId"], duplicate["executionId"])
        self.assertEqual(before, json.dumps(duplicate, sort_keys=True, separators=(",", ":")))
        self.assertEqual(
            list(range(1, len(duplicate["progressEvents"]) + 1)),
            [event["sequence"] for event in duplicate["progressEvents"]],
        )

    def test_unknown_or_arbitrary_fields_are_rejected(self):
        request = self.request()
        request["command"] = "id"
        with self.assertRaisesRegex(MODULE.ProtocolError, "dispatch fields"):
            self.state.create(request)

    def test_catalog_revision_is_stable_and_advertises_exact_profile(self):
        first = self.state.codex_catalog()
        second = self.state.codex_catalog()

        self.assertIn(MODULE.CODEX_CATALOG_CAPABILITY, self.state.health()["capabilities"])
        self.assertEqual("codex-model-catalog-v1", first["schemaVersion"])
        self.assertEqual("0.145.0", first["codexVersion"])
        self.assertEqual(
            "125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187",
            first["catalogRevision"],
        )
        self.assertEqual(first["catalogRevision"], second["catalogRevision"])
        self.assertEqual(
            ["none", "low", "medium", "high", "xhigh", "max"],
            first["models"][0]["supportedEfforts"],
        )


class WorkspaceActivationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.calls = root / "calls"
        self.activator = root / "activator"
        self.activator.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import sys
calls = pathlib.Path(sys.argv[0]).with_name("calls")
calls.write_text(calls.read_text() + "1\\n" if calls.exists() else "1\\n")
session_id = sys.argv[2]
branch = sys.argv[3]
print(json.dumps({
    "state": "ready",
    "sessionId": session_id,
    "workspaceIdentity": "remote:ax42-01:work-session:" + session_id,
    "projectId": "beautips",
    "workspaceBranch": branch,
    "slot": "slot4",
    "canonicalCommit": "e9e0b3c319c518363d4135f5378ebbddced96dfb",
    "selectionEnabled": True,
    "executionEnabled": True,
    "valuesExposed": False,
}))
""",
            encoding="utf-8",
        )
        self.activator.chmod(0o755)
        self.atenea_activator = root / "atenea-activator"
        self.atenea_activator.write_text(
            self.activator.read_text()
            .replace('"projectId": "beautips"', '"projectId": "atenea"')
            .replace('"slot": "slot4"', '"slot": "slot2"')
            .replace(
                '"e9e0b3c319c518363d4135f5378ebbddced96dfb"',
                '"' + TEST_COMMIT + '"',
            ),
            encoding="utf-8",
        )
        self.atenea_activator.chmod(0o755)
        self.state = MODULE.WorkerState(
            root / "state",
            "ax42-01",
            privilege_command=(),
            project_workspace_activator=self.atenea_activator,
            beautips_workspace_activator=self.activator,
        )
        self.state._observe_project_commit = lambda route: (
            TEST_COMMIT
            if route["identity"]["projectId"] == MODULE.PROJECT_ID
            else MODULE.BEAUTIPS_PROJECT_COMMIT
        )
        self.refreshes = []
        self.state._refresh_project_mirror = lambda route: self.refreshes.append(
            route["identity"]["projectId"]
        )
        self.session_id = str(uuid.uuid4())

    def tearDown(self):
        self.temporary.cleanup()

    def request(self):
        return {
            "sessionId": self.session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + self.session_id,
            "projectId": MODULE.BEAUTIPS_PROJECT_ID,
            "repository": MODULE.BEAUTIPS_PROJECT_REPOSITORY,
            "branch": MODULE.BEAUTIPS_PROJECT_BRANCH,
            "commit": MODULE.BEAUTIPS_PROJECT_COMMIT,
            "manifestSha256": MODULE.BEAUTIPS_PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + self.session_id,
        }

    def test_exact_workspace_can_be_ensured_repeatedly(self):
        first = self.state.ensure_workspace(self.request())
        second = self.state.ensure_workspace(self.request())
        self.assertEqual(first, second)
        self.assertEqual("ready", first["state"])
        self.assertEqual(2, len(self.calls.read_text().splitlines()))

    def test_exact_atenea_workspace_uses_its_separate_activator(self):
        request = self.request()
        request.update({
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        })
        result = self.state.ensure_workspace(request)
        self.assertEqual("ready", result["state"])
        self.assertEqual("atenea", result["projectId"])
        self.assertEqual("slot2", result["slot"])
        self.assertEqual(["atenea"], self.refreshes)

    def test_atenea_refresh_failure_blocks_activation(self):
        request = self.request()
        request.update({
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        })

        def reject_refresh(_route):
            raise MODULE.ProtocolError(
                MODULE.HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror canonical refresh failed closed",
            )

        self.state._refresh_project_mirror = reject_refresh
        with self.assertRaisesRegex(MODULE.ProtocolError, "refresh failed closed"):
            self.state.ensure_workspace(request)
        self.assertFalse(self.calls.exists())

    def test_foreign_identity_and_arbitrary_field_fail_before_activation(self):
        foreign = self.request()
        foreign["repository"] = "https://github.com/foreign/beautips.git"
        with self.assertRaisesRegex(MODULE.ProtocolError, "not exact"):
            self.state.ensure_workspace(foreign)
        self.assertEqual([], self.refreshes)
        arbitrary = self.request()
        arbitrary["command"] = "id"
        with self.assertRaisesRegex(MODULE.ProtocolError, "fields"):
            self.state.ensure_workspace(arbitrary)
        self.assertFalse(self.calls.exists())

    def test_noncanonical_branch_fails_before_activation(self):
        request = self.request()
        request["workspaceBranch"] = "main"
        with self.assertRaisesRegex(MODULE.ProtocolError, "persisted WorkSession"):
            self.state.ensure_workspace(request)
        self.assertFalse(self.calls.exists())

    def test_branch_owned_by_another_session_fails_before_activation(self):
        request = self.request()
        request["workspaceBranch"] = "atenea/session-22222222-2222-4222-8222-222222222222"
        with self.assertRaisesRegex(MODULE.ProtocolError, "persisted WorkSession"):
            self.state.ensure_workspace(request)
        self.assertFalse(self.calls.exists())

    def test_activation_failure_maps_reviewed_code_and_discards_stderr_detail(self):
        marker = "unsafe-mediator-command-and-path"
        self.activator.write_text(
            "#!/bin/sh\n"
            f"printf 'NORMAL_CAPACITY_EXHAUSTED: {marker}\\n' >&2\n"
            "exit 65\n",
            encoding="utf-8",
        )

        with self.assertRaises(MODULE.ProtocolError) as rejected:
            self.state.ensure_workspace(self.request())

        self.assertEqual(409, rejected.exception.status)
        self.assertEqual("NORMAL_CAPACITY_EXHAUSTED", rejected.exception.safe_error["code"])
        self.assertEqual("CAPACITY", rejected.exception.safe_error["category"])
        self.assertTrue(rejected.exception.safe_error["retryable"])
        self.assertEqual("WAIT", rejected.exception.safe_error["nextAction"])
        self.assertNotIn(marker, json.dumps(rejected.exception.safe_error))

    def test_lifecycle_lock_serializes_ensure_and_release_participant(self):
        request = self.request()
        request.update({
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        })
        ensure_entered = threading.Event()
        allow_ensure = threading.Event()
        events = []

        def blocked_refresh(_route):
            events.append("ensure-owns-lifecycle")
            ensure_entered.set()
            self.assertTrue(allow_ensure.wait(2))

        self.state._refresh_project_mirror = blocked_refresh
        ensure_thread = threading.Thread(target=lambda: self.state.ensure_workspace(request))

        def release_participant():
            with self.state.workspace_lifecycle_lock():
                events.append("release-owns-lifecycle")

        release_thread = threading.Thread(target=release_participant)
        ensure_thread.start()
        self.assertTrue(ensure_entered.wait(1))
        release_thread.start()
        time.sleep(0.05)
        self.assertEqual(["ensure-owns-lifecycle"], events)
        allow_ensure.set()
        ensure_thread.join(2)
        release_thread.join(2)

        self.assertFalse(ensure_thread.is_alive())
        self.assertFalse(release_thread.is_alive())
        self.assertEqual(
            ["ensure-owns-lifecycle", "release-owns-lifecycle"], events
        )
        lock_stat = self.state.workspace_lifecycle_lock_file.stat()
        self.assertEqual(0o600, lock_stat.st_mode & 0o777)

    def test_lifecycle_lock_timeout_runs_no_activation(self):
        self.state.workspace_lifecycle_timeout = 0.03
        rejected = []

        def competing_ensure():
            try:
                self.state.ensure_workspace(self.request())
            except MODULE.ProtocolError as exception:
                rejected.append(exception)

        with self.state.workspace_lifecycle_lock():
            contender = threading.Thread(target=competing_ensure)
            contender.start()
            contender.join(1)

        self.assertFalse(contender.is_alive())
        self.assertEqual(1, len(rejected))
        self.assertEqual(MODULE.HTTPStatus.LOCKED, rejected[0].status)
        self.assertEqual("WORKSPACE_LIFECYCLE_BUSY", rejected[0].safe_error["code"])
        self.assertEqual("WAIT", rejected[0].safe_error["nextAction"])
        self.assertFalse(self.calls.exists())


class ProjectMirrorRefreshTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.origin = root / "origin.git"
        self.mirror = root / "mirror.git"
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True)
        subprocess.run(["git", "init", "-q", "--bare", self.mirror], check=True)
        subprocess.run(
            ["git", "--git-dir", self.mirror, "remote", "add", "origin", self.origin],
            check=True,
        )
        subprocess.run(
            [
                "git", "--git-dir", self.mirror, "config", "remote.origin.fetch",
                "+refs/heads/*:refs/remotes/origin/*",
            ],
            check=True,
        )
        self.state = MODULE.WorkerState(root / "state", "ax42-01")
        self.route = {
            "mirror": self.mirror,
            "identity": {"repository": str(self.origin)},
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_exact_canonical_mirror_refreshes(self):
        self.state._refresh_project_mirror(self.route)

    def test_foreign_push_url_fails_closed(self):
        subprocess.run(
            [
                "git", "--git-dir", self.mirror, "config", "remote.origin.pushurl",
                "https://example.invalid/foreign.git",
            ],
            check=True,
        )
        with self.assertRaisesRegex(MODULE.ProtocolError, "failed closed"):
            self.state._refresh_project_mirror(self.route)


class RetainedDraftFingerprintTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.worktree = root / "worktree"
        self.worktree.mkdir()
        subprocess.run(["git", "init", "-q", "-b", MODULE.PROJECT_BRANCH], cwd=self.worktree, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.worktree, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.worktree, check=True)
        (self.worktree / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.worktree, check=True)
        subprocess.run(["git", "commit", "-qm", "stale base"], cwd=self.worktree, check=True)
        self.retained_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.worktree,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        (self.worktree / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
        (self.worktree / "staged.txt").write_text("staged\n", encoding="utf-8")
        subprocess.run(["git", "add", "staged.txt"], cwd=self.worktree, check=True)
        (self.worktree / "untracked.txt").write_text("untracked secret-shaped value\n", encoding="utf-8")

        self.accepted_commit = "2" * 40
        self.session_id = str(uuid.uuid4())
        self.workspace_identity = "remote:ax42-01:work-session:" + self.session_id
        self.runner = root / "runner"
        self.runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.runner.chmod(0o755)
        self.validation_calls = root / "validation-calls"
        self.validation_mediator = root / "validation-mediator"
        self.validation_mediator.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import pathlib
import sys
action, operation, session_id, source_sha, validation_id = sys.argv[1:]
calls = pathlib.Path(__file__).with_name("validation-calls")
if action == "start":
    calls.write_text(calls.read_text() + "call\\n" if calls.exists() else "call\\n")
definitions = {
    "BACKEND_TEST": "atenea-backend-test-v1",
    "WEB_BUILD": "atenea-web-build-v1",
    "ANDROID_BUILD": "atenea-android-build-v1",
    "PLAYWRIGHT_ACCEPTANCE": "atenea-playwright-acceptance-v1",
}
print(json.dumps({
    "schemaVersion": 1,
    "protocolVersion": "closed-validation-broker/v1",
    "operationId": validation_id,
    "sessionId": session_id,
    "operation": operation,
    "definitionRevision": definitions[operation],
    "sourceTreeFingerprintSha256": source_sha,
    "state": "CANCELLED" if action == "cancel" else "SUCCEEDED",
    "terminalCause": "CANCELLED" if action == "cancel" else "NONE",
    "exitCode": None if action == "cancel" else 0,
    "durationMillis": 7,
    "artifactManifestSha256": None if action == "cancel" else hashlib.sha256(validation_id.encode()).hexdigest(),
    "summary": "Closed validation was cancelled" if action == "cancel" else "Closed validation passed",
    "valuesExposed": False,
}))
""",
            encoding="utf-8",
        )
        self.validation_mediator.chmod(0o755)
        self.role_calls = root / "role-calls"
        self.role_mediator = root / "role-mediator"
        self.role_mediator.write_text(
            """#!/usr/bin/env python3
import hashlib, json, pathlib, sys
_, session, change, code = sys.argv[1:]
calls = pathlib.Path(__file__).with_name("role-calls")
calls.write_text(calls.read_text() + "call\\n" if calls.exists() else "call\\n")
repository = "https://github.com/jlnieto/atenea.git"
program = "3" * 40
roles = []
for role, branch, commit, profile in (
    ("ATENEA_CODE", "main", code, "atenea-code-v1"),
    ("PROGRAMME_OPENSPEC", "program/remote-codex-worker-platform", program, "openspec-strict-v1"),
    ("WORKER_SOURCE", "program/remote-codex-worker-platform", program, "worker-contract-v1"),
):
    roles.append({"role": role, "authority": "READ_WRITE", "repository": repository,
        "branch": branch, "commit": commit,
        "mirrorIdentitySha256": hashlib.sha256(b"mirror").hexdigest(),
        "worktreeIdentitySha256": hashlib.sha256(role.encode()).hexdigest(),
        "validationProfile": profile, "readiness": "DRAFT"})
print(json.dumps({"sessionId": session,
    "workspaceIdentity": "remote:ax42-01:work-session:" + session,
    "changeIdentity": change, "roles": roles, "valuesExposed": False}))
""",
            encoding="utf-8",
        )
        self.role_mediator.chmod(0o755)
        self.config = root / "project.json"
        self.config.write_text(json.dumps({
            "schemaVersion": MODULE.PROJECT_CAPABILITY,
            "selectionEnabled": True,
            "executionEnabled": False,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": self.retained_head,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "runner": str(self.runner),
            "attachmentRoot": MODULE.PROJECT_ATTACHMENT_ROOT,
            "workspaces": {
                self.workspace_identity: {
                    "sessionId": self.session_id,
                    "worktree": str(self.worktree),
                    "allocationSha256": "a" * 64,
                    "canonicalCommit": self.retained_head,
                }
            },
        }), encoding="utf-8")
        self.config.chmod(0o644)
        self.state = MODULE.WorkerState(
            root / "state",
            "ax42-01",
            project_config=self.config,
            project_runner=self.runner,
            project_config_uid=os.getuid(),
            privilege_command=(),
            project_validation_mediator=self.validation_mediator,
            repository_role_mediator=self.role_mediator,
        )
        self.state._observe_project_commit = lambda _route: self.accepted_commit

    def tearDown(self):
        if self.state.scheduler is not None:
            self.state.stop()
        self.temporary.cleanup()

    def request(self):
        return {
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "acceptedCommit": self.accepted_commit,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        }

    def test_dirty_stale_draft_fingerprint_is_sanitized_repeatable_and_read_only(self):
        before = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=self.worktree,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        first = self.state.fingerprint_retained_draft(self.request())
        second = self.state.fingerprint_retained_draft(self.request())
        after = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=self.worktree,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout

        self.assertEqual(first, second)
        self.assertEqual(before, after)
        self.assertEqual("draft_blocked_ready", first["state"])
        self.assertEqual(self.retained_head, first["retainedHead"])
        self.assertEqual(1, first["stagedChangeCount"])
        self.assertEqual(1, first["unstagedChangeCount"])
        self.assertEqual(1, first["untrackedChangeCount"])
        self.assertFalse(first["valuesExposed"])
        serialized = json.dumps(first)
        self.assertNotIn("tracked.txt", serialized)
        self.assertNotIn("secret-shaped", serialized)

    def test_foreign_ambiguous_or_active_ownership_fails_closed(self):
        foreign = self.request()
        foreign["workspaceIdentity"] = "remote:ax42-01:work-session:" + str(uuid.uuid4())
        with self.assertRaisesRegex(MODULE.ProtocolError, "not exact"):
            self.state.fingerprint_retained_draft(foreign)

        ambiguous = self.request()
        ambiguous["extra"] = "arbitrary"
        with self.assertRaisesRegex(MODULE.ProtocolError, "fields"):
            self.state.fingerprint_retained_draft(ambiguous)

        self.state.executions["active"] = {
            "sessionId": self.session_id,
            "status": "RUNNING",
        }
        with self.assertRaisesRegex(MODULE.ProtocolError, "non-terminal"):
            self.state.fingerprint_retained_draft(self.request())

    def test_current_source_tree_fingerprint_is_sanitized_and_changes_with_content(self):
        self.state._observe_project_commit = lambda _route: self.retained_head
        request = {
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": self.retained_head,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        }

        before = self.state.fingerprint_source_tree(request)
        (self.worktree / "untracked.txt").write_text("changed value\n", encoding="utf-8")
        after = self.state.fingerprint_source_tree(request)

        self.assertNotEqual(before["fingerprintSha256"], after["fingerprintSha256"])
        self.assertEqual(self.retained_head, after["headCommit"])
        self.assertFalse(after["valuesExposed"])
        serialized = json.dumps(after)
        self.assertNotIn("untracked.txt", serialized)
        self.assertNotIn("changed value", serialized)

        foreign = dict(request)
        foreign["repository"] = "https://github.com/foreign/atenea.git"
        with self.assertRaisesRegex(MODULE.ProtocolError, "not exact"):
            self.state.fingerprint_source_tree(foreign)

    def validation_request(self, validation_id=None):
        self.state._observe_project_commit = lambda _route: self.retained_head
        source_request = {
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": self.retained_head,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
        }
        source = self.state.fingerprint_source_tree(source_request)
        return {
            **source_request,
            "validationId": validation_id or str(uuid.uuid4()),
            "operation": "BACKEND_TEST",
            "definitionRevision": "atenea-backend-test-v1",
            "sourceTreeFingerprintSha256": source["fingerprintSha256"],
        }

    def durable_validation_request(self, validation_id=None, operation="BACKEND_TEST"):
        legacy = self.validation_request(validation_id)
        revision = MODULE.VALIDATION_DEFINITIONS[operation][0]
        return {
            "schemaVersion": 1,
            "protocolVersion": MODULE.CLOSED_VALIDATION_CAPABILITY,
            "operationId": legacy.pop("validationId"),
            **legacy,
            "operation": operation,
            "definitionRevision": revision,
        }

    @staticmethod
    def exact_validation(request):
        return {key: request[key] for key in MODULE.VALIDATION_EXACT_KEYS}

    @staticmethod
    def mediator_observation(request, state, cause="NONE", exit_code=None):
        artifact = None
        if state in {"SUCCEEDED", "CANDIDATE_FAILED"}:
            artifact = hashlib.sha256(request["operationId"].encode()).hexdigest()
        return {
            "schemaVersion": 1,
            "protocolVersion": MODULE.CLOSED_VALIDATION_CAPABILITY,
            "operationId": request["operationId"],
            "sessionId": request["sessionId"],
            "operation": request["operation"],
            "definitionRevision": request["definitionRevision"],
            "sourceTreeFingerprintSha256": request["sourceTreeFingerprintSha256"],
            "state": state,
            "terminalCause": cause,
            "exitCode": exit_code,
            "durationMillis": 7,
            "artifactManifestSha256": artifact,
            "summary": "safe",
            "valuesExposed": False,
        }

    def wait_validation(self, request, timeout=3):
        deadline = time.monotonic() + timeout
        exact = self.exact_validation(request)
        while time.monotonic() < deadline:
            observed = self.state.inspect_validation(exact)
            if observed["state"] in MODULE.VALIDATION_TERMINAL:
                return observed
            time.sleep(0.02)
        self.fail("validation did not become terminal")

    def test_durable_validation_start_running_terminal(self):
        request = self.durable_validation_request()
        release = threading.Event()

        def observe(action, _validation):
            if action == "start" or not release.is_set():
                return self.mediator_observation(request, "RUNNING")
            return self.mediator_observation(request, "SUCCEEDED", exit_code=0)

        with mock.patch.object(
            self.state, "_validation_mediator_observation", side_effect=observe
        ):
            self.state.start()
            queued, created = self.state.start_validation(request)
            self.assertTrue(created)
            self.assertEqual("QUEUED", queued["state"])
            deadline = time.monotonic() + 3
            running = queued
            while running["state"] == "QUEUED":
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
                running = self.state.inspect_validation(self.exact_validation(request))
            self.assertEqual("RUNNING", running["state"])
            release.set()
            terminal = self.wait_validation(request)
        self.assertEqual("SUCCEEDED", terminal["state"])
        self.assertEqual("NONE", terminal["terminalCause"])

    def test_durable_validation_exact_replay_and_conflict(self):
        request = self.durable_validation_request()
        first, created = self.state.start_validation(request)
        (self.worktree / "untracked.txt").write_text("changed after admission\n")
        replay, created_again = self.state.start_validation(dict(request))
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, replay)

        conflicting = dict(request)
        conflicting["operation"] = "WEB_BUILD"
        conflicting["definitionRevision"] = "atenea-web-build-v1"
        with self.assertRaisesRegex(MODULE.ProtocolError, "different immutable request"):
            self.state.start_validation(conflicting)

    def test_durable_validation_cancel_before_start_is_repeatable_and_owned(self):
        request = self.durable_validation_request()
        self.state.start_validation(request)
        exact = self.exact_validation(request)
        first = self.state.cancel_validation(exact)
        second = self.state.cancel_validation(dict(exact))
        self.assertEqual(first, second)
        self.assertEqual("CANCELLED", first["state"])
        self.assertEqual("CANCELLED", first["terminalCause"])

        foreign = dict(exact)
        foreign["sessionId"] = str(uuid.uuid4())
        with self.assertRaisesRegex(MODULE.ProtocolError, "ownership is not exact"):
            self.state.cancel_validation(foreign)

    def test_durable_validation_cancel_while_running_does_not_touch_other(self):
        first = self.durable_validation_request()
        second = self.durable_validation_request()

        def observe(action, validation):
            request = first if validation["operationId"] == first["operationId"] else second
            if action == "cancel":
                return self.mediator_observation(request, "CANCELLED", "CANCELLED")
            return self.mediator_observation(request, "RUNNING")

        with mock.patch.object(
            self.state, "_validation_mediator_observation", side_effect=observe
        ):
            self.state.start()
            self.state.start_validation(first)
            self.state.start_validation(second)
            deadline = time.monotonic() + 3
            while self.state.inspect_validation(self.exact_validation(first))["state"] == "QUEUED":
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
            self.state.cancel_validation(self.exact_validation(first))
            cancelled = self.wait_validation(first)
            other = self.state.inspect_validation(self.exact_validation(second))
        self.assertEqual("CANCELLED", cancelled["state"])
        self.assertEqual("RUNNING", other["state"])

    def test_durable_validation_restart_inspect_adopts_terminal_result(self):
        request = self.durable_validation_request()
        self.state.start_validation(request)
        with self.state.lock:
            stored = self.state.validations[request["operationId"]]
            stored["state"] = "RUNNING"
            stored["startedAt"] = MODULE.utc_now()
            self.state._persist()
        recovered = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            project_config=self.config,
            project_runner=self.runner,
            project_config_uid=os.getuid(),
            privilege_command=(),
            project_validation_mediator=self.validation_mediator,
        )
        recovered._observe_project_commit = lambda _route: self.retained_head
        self.state = recovered
        with mock.patch.object(
            recovered,
            "_validation_mediator_observation",
            return_value=self.mediator_observation(request, "SUCCEEDED", exit_code=0),
        ):
            result = recovered.inspect_validation(self.exact_validation(request))
        self.assertEqual("SUCCEEDED", result["state"])
        self.assertEqual("CONFIRMED", result["transportState"])

    def test_validation_capacity_is_server_owned_and_shared(self):
        self.state.normal_capacity = 2
        requests = [self.durable_validation_request() for _ in range(3)]

        def observe(_action, validation):
            request = next(
                item for item in requests
                if item["operationId"] == validation["operationId"]
            )
            return self.mediator_observation(request, "RUNNING")

        with mock.patch.object(
            self.state, "_validation_mediator_observation", side_effect=observe
        ):
            self.state.start()
            for request in requests:
                self.state.start_validation(request)
            deadline = time.monotonic() + 3
            states = []
            while time.monotonic() < deadline:
                states = [
                    self.state.inspect_validation(self.exact_validation(request))["state"]
                    for request in requests
                ]
                if states.count("RUNNING") == 2 and states.count("QUEUED") == 1:
                    break
                time.sleep(0.02)
        self.assertEqual(2, states.count("RUNNING"))
        self.assertEqual(1, states.count("QUEUED"))

    def test_restart_reserves_capacity_for_adopted_validation(self):
        request = self.durable_validation_request()
        self.state.start_validation(request)
        with self.state.lock:
            self.state.validations[request["operationId"]]["state"] = "RUNNING"
            self.state._persist()
        recovered = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            normal_capacity=1,
            heavy_capacity=1,
            project_config=self.config,
            project_runner=self.runner,
            project_config_uid=os.getuid(),
            privilege_command=(),
            project_validation_mediator=self.validation_mediator,
        )
        recovered._observe_project_commit = lambda _route: self.retained_head
        dispatch = {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:test:" + str(uuid.uuid4()),
            "workloadClass": "NORMAL",
            "leaseGeneration": 1,
            "workload": {
                "kind": "synthetic-routing-v1",
                "message": "queued behind durable validation",
                "durationMs": 100,
                "steps": 2,
            },
        }
        recovered.create(dispatch)
        self.state = recovered
        with mock.patch.object(
            recovered,
            "_validation_mediator_observation",
            return_value=self.mediator_observation(request, "RUNNING"),
        ):
            recovered.start()
            deadline = time.monotonic() + 3
            while request["operationId"] not in recovered.validation_threads:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
            self.assertEqual("QUEUED", recovered.get(dispatch["dispatchId"])["status"])

    def test_terminal_causes_and_four_symbolic_definitions_are_preserved(self):
        expected = {
            "BACKEND_TEST": "atenea-backend-test-v1",
            "WEB_BUILD": "atenea-web-build-v1",
            "ANDROID_BUILD": "atenea-android-build-v1",
            "PLAYWRIGHT_ACCEPTANCE": "atenea-playwright-acceptance-v1",
        }
        for operation, revision in expected.items():
            request = self.durable_validation_request(operation=operation)
            queued, _ = self.state.start_validation(request)
            self.assertEqual(operation, queued["validationDefinition"])
            self.assertEqual(revision, queued["definitionRevision"])

        candidate = self.durable_validation_request()
        infrastructure = self.durable_validation_request()
        self.state.start_validation(candidate)
        self.state.start_validation(infrastructure)
        with self.state.lock:
            self.state._apply_validation_observation(
                self.state.validations[candidate["operationId"]],
                self.mediator_observation(
                    candidate, "CANDIDATE_FAILED", "CANDIDATE", 1
                ),
            )
            self.state._apply_validation_observation(
                self.state.validations[infrastructure["operationId"]],
                self.mediator_observation(
                    infrastructure, "INFRASTRUCTURE_FAILED", "INFRASTRUCTURE"
                ),
            )
        self.assertEqual(
            "CANDIDATE",
            self.state.inspect_validation(self.exact_validation(candidate))["terminalCause"],
        )
        self.assertEqual(
            "INFRASTRUCTURE",
            self.state.inspect_validation(self.exact_validation(infrastructure))[
                "terminalCause"
            ],
        )

    def test_closed_validation_is_sanitized_idempotent_and_durable(self):
        request = self.validation_request()
        first = self.state.run_validation(request)
        second = self.state.run_validation(request)
        recovered = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            project_config=self.config,
            project_runner=self.runner,
            project_config_uid=os.getuid(),
            privilege_command=(),
            project_validation_mediator=self.validation_mediator,
        )
        recovered._observe_project_commit = lambda _route: self.retained_head
        third = recovered.run_validation(request)

        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual("SUCCEEDED", first["status"])
        self.assertFalse(first["valuesExposed"])
        self.assertEqual(1, self.validation_calls.read_text().count("call"))
        serialized = json.dumps(first)
        self.assertNotIn("command", serialized)
        self.assertNotIn("environment", serialized)
        self.assertNotIn("secret-shaped", serialized)

    def test_predecessor_terminal_validation_record_remains_replayable(self):
        request = self.validation_request()
        with self.state.lock:
            self.state.validations[request["validationId"]] = {
                "validationId": request["validationId"],
                "sessionId": request["sessionId"],
                "workspaceIdentity": request["workspaceIdentity"],
                "operation": request["operation"],
                "definitionRevision": request["definitionRevision"],
                "sourceTreeFingerprintSha256": request[
                    "sourceTreeFingerprintSha256"
                ],
                "requestFingerprint": MODULE.canonical_hash(request),
                "status": "SUCCEEDED",
                "exitCode": 0,
                "durationMillis": 7,
                "artifactManifestSha256": hashlib.sha256(
                    request["validationId"].encode()
                ).hexdigest(),
                "summary": "Closed validation passed",
                "valuesExposed": False,
                "createdAt": MODULE.utc_now(),
                "finishedAt": MODULE.utc_now(),
            }
            self.state._persist()
        recovered = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "ax42-01",
            project_config=self.config,
            project_runner=self.runner,
            project_config_uid=os.getuid(),
            privilege_command=(),
            project_validation_mediator=self.validation_mediator,
        )
        recovered._observe_project_commit = lambda _route: self.retained_head
        result = recovered.run_validation(request)
        self.assertEqual("SUCCEEDED", result["status"])
        self.assertEqual(request["validationId"], result["validationId"])
        self.assertFalse(self.validation_calls.exists())

    def test_closed_validation_rejects_altered_authority_before_process(self):
        for key, value in (
            ("operation", "ARBITRARY_COMMAND"),
            ("definitionRevision", "caller-v1"),
            ("command", "docker run --privileged"),
        ):
            request = self.validation_request()
            request[key] = value
            with self.assertRaises(MODULE.ProtocolError):
                self.state.run_validation(request)
        foreign = self.validation_request()
        foreign["workspaceIdentity"] = "remote:ax42-01:work-session:" + str(uuid.uuid4())
        with self.assertRaises(MODULE.ProtocolError):
            self.state.run_validation(foreign)
        self.assertFalse(self.validation_calls.exists())

    def test_closed_validation_lost_start_response_reconciles_without_replay(self):
        request = self.durable_validation_request()
        original_run = subprocess.run
        lost = False

        def bounded_timeout(command, *args, **kwargs):
            nonlocal lost
            if str(self.validation_mediator) in command and not lost:
                lost = True
                raise subprocess.TimeoutExpired(command, timeout=30)
            return original_run(command, *args, **kwargs)

        self.state.start()
        with mock.patch.object(
                MODULE.subprocess,
                "run",
                side_effect=bounded_timeout,
        ):
            started, created = self.state.start_validation(request)
            self.assertTrue(created)
            deadline = time.monotonic() + 3
            result = started
            while result["state"] not in MODULE.VALIDATION_TERMINAL:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
                result = self.state.inspect_validation(self.exact_validation(request))

        self.assertEqual("SUCCEEDED", result["state"])
        self.assertEqual("CONFIRMED", result["transportState"])
        self.assertRegex(result["artifactManifestSha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(result["valuesExposed"])
        replay, created_again = self.state.start_validation(request)
        self.assertFalse(created_again)
        self.assertEqual(result, replay)

    def test_multi_repository_roles_are_fixed_separate_and_sanitized(self):
        request = {
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "changeIdentity": str(uuid.uuid4()),
            "codeCommit": self.retained_head,
        }
        result = self.state.ensure_repository_roles(request)

        self.assertEqual(3, len(result["roles"]))
        self.assertEqual(
            {"ATENEA_CODE", "PROGRAMME_OPENSPEC", "WORKER_SOURCE"},
            {role["role"] for role in result["roles"]},
        )
        self.assertFalse(result["valuesExposed"])
        self.assertEqual(1, self.role_calls.read_text().count("call"))
        self.assertNotIn("path", json.dumps(result))

    def test_multi_repository_roles_reject_extra_and_foreign_authority(self):
        base = {
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "changeIdentity": str(uuid.uuid4()),
            "codeCommit": self.retained_head,
        }
        for mutation in (
            {"repository": "https://github.com/foreign/repo.git"},
            {"workspaceIdentity": "remote:ax42-01:work-session:" + str(uuid.uuid4())},
            {"codeCommit": "f" * 40},
        ):
            request = {**base, **mutation}
            with self.assertRaises(MODULE.ProtocolError):
                self.state.ensure_repository_roles(request)
        self.assertFalse(self.role_calls.exists())


class ProjectWorkerStateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.runner = root / "fake-project-runner"
        self.runner.write_text(
            """#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path
request = json.load(sys.stdin)
calls = Path(sys.argv[0]).with_name("project-runner-calls")
calls.write_text(calls.read_text() + "call\\n" if calls.exists() else "call\\n")
message = request["workload"]["message"]
if message.startswith("sleep:"):
    time.sleep(float(message.split(":", 1)[1]))
print(json.dumps({
    "threadId": request["workload"]["threadId"] or "f9d68d92-71c6-4fa5-b77b-63863f8f2dc7",
    "turnId": request["executionId"],
    "finalAnswer": "bounded fake result",
    "outputSummary": request["workload"]["kind"] + " completed",
    **({key: request["workload"][key] for key in (
        "modelId", "reasoningEffort", "catalogRevision", "codexVersion"
    )} | {"progressEvents": [
        {"category": "INSPECTING_PROJECT", "occurredAt": "unsafe-ignored",
         "message": "Inspecting the accepted project."},
        {"category": "CHECKING", "occurredAt": "unsafe-ignored",
         "message": "Checking the accepted project."}
    ]} if request["workload"]["kind"] in {
        "project-codex-v2", "project-codex-v3", "project-codex-v4"
    } else {}),
    **({"sourceIdentity": {
        "changeKey": request["changeOwnership"]["changeKey"],
        "databaseWorkSessionId": request["changeOwnership"]["databaseWorkSessionId"],
        "remoteSessionId": request["changeOwnership"]["remoteSessionId"],
        "workspaceIdentity": request["changeOwnership"]["workspaceIdentity"],
        "executionId": request["executionId"],
        "sourceCommit": request["workload"]["commit"],
        "sourceFingerprintSha256": request["changeOwnership"]["sourceFingerprintSha256"],
        "workspaceDirty": True,
    }} if request["workload"]["kind"] == "project-codex-v4" else {})
}))
""",
            encoding="utf-8",
        )
        self.runner.chmod(0o755)
        self.change_mediator_calls = root / "change-mediator-calls"
        self.change_mediator = root / "change-mediator"
        self.change_mediator.write_text(
            """#!/usr/bin/env python3
import json
import pathlib
import sys
r = json.load(sys.stdin)
calls = pathlib.Path(sys.argv[0]).with_name("change-mediator-calls")
calls.write_text(calls.read_text() + r["operation"] + "\\n" if calls.exists() else r["operation"] + "\\n")
owned = r["sourceFingerprintSha256"] == "c" * 64
print(json.dumps({
    "schemaVersion": r["schemaVersion"],
    "protocolVersion": r["protocolVersion"],
    "state": "OWNED" if owned else "FOREIGN",
    "effect": r["effect"],
    "operationId": r["operationId"],
    "idempotencyKey": r["idempotencyKey"],
    "operation": r["operation"],
    "predecessorOperationId": r["predecessorOperationId"],
    "changeKey": r["changeKey"],
    "databaseProjectId": r["databaseProjectId"],
    "projectId": r["projectId"],
    "repository": r["repository"],
    "repositoryBranch": r["repositoryBranch"],
    "baseCommit": r["baseCommit"],
    "workspaceBranch": r["workspaceBranch"],
    "workspaceIdentity": r["workspaceIdentity"],
    "workerId": r["workerId"],
    "sourceRevision": r["sourceRevision"],
    "sourceCommit": r["sourceCommit"] if owned else None,
    "sourceFingerprintSha256": r["sourceFingerprintSha256"] if owned else None,
    "workspaceDirty": True if owned else None,
    "retainedDraft": True if owned else None,
    "requestFingerprintSha256": r["requestFingerprintSha256"],
    "valuesExposed": False,
}, sort_keys=True, separators=(",", ":")))
""",
            encoding="utf-8",
        )
        self.change_mediator.chmod(0o755)
        self.session_id = str(uuid.uuid4())
        self.workspace_identity = "remote:ax42-01:work-session:" + self.session_id
        self.config = root / "project.json"
        self.config.write_text(
            json.dumps({
                "schemaVersion": "project-codex-v1",
                "selectionEnabled": True,
                "executionEnabled": True,
                "projectId": "atenea",
                "repository": MODULE.PROJECT_REPOSITORY,
                "branch": MODULE.PROJECT_BRANCH,
                "commit": TEST_COMMIT,
                "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
                "runner": str(self.runner),
                "attachmentRoot": MODULE.PROJECT_ATTACHMENT_ROOT,
                "workspaces": {
                    self.workspace_identity: {
                        "sessionId": self.session_id,
                        "worktree": "/srv/atenea/workspaces/sessions/" + self.session_id + "/atenea",
                        "allocationSha256": "a" * 64,
                        "canonicalCommit": TEST_COMMIT,
                    }
                },
            }),
            encoding="utf-8",
        )
        self.config.chmod(0o644)
        self.state = MODULE.WorkerState(
            root / "state",
            "test-worker",
            project_config=self.config,
            project_runner=self.runner,
            project_timeout=30,
            project_config_uid=os.getuid(),
            privilege_command=(),
            development_change_workspace_mediator=self.change_mediator,
        )
        self.state._observe_project_commit = lambda _route: TEST_COMMIT
        self.state.start()

    def tearDown(self):
        self.state.stop()
        self.temporary.cleanup()

    def request(self, message="hello", thread_id=None):
        return {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": self.session_id,
            "workspaceIdentity": self.workspace_identity,
            "workloadClass": "NORMAL",
            "leaseGeneration": 1,
            "workload": {
                "kind": "project-codex-v1",
                "projectId": "atenea",
                "repository": MODULE.PROJECT_REPOSITORY,
                "branch": MODULE.PROJECT_BRANCH,
                "commit": TEST_COMMIT,
                "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
                "instructionBundleRevision": MODULE.INSTRUCTION_BUNDLE_REVISION,
                "instructionBundleSha256": MODULE.ATENEA_INSTRUCTION_BUNDLE_SHA256,
                "platformInstructionSha256": MODULE.PLATFORM_INSTRUCTION_SHA256,
                "projectInstructionPath": MODULE.PROJECT_INSTRUCTION_PATH,
                "projectInstructionSha256": MODULE.ATENEA_PROJECT_INSTRUCTION_SHA256,
                "message": message,
                "threadId": thread_id,
            },
        }

    def profiled_request(self, effort="high"):
        request = self.request()
        request["workload"].update({
            "kind": MODULE.PROJECT_V2_CAPABILITY,
            "modelId": "gpt-5.6-sol",
            "reasoningEffort": effort,
            "catalogRevision": MODULE.codex_catalog_revision(),
            "codexVersion": MODULE.CODEX_VERSION,
        })
        return request

    def image_request(self):
        request = self.profiled_request()
        request["workload"].update({
            "kind": MODULE.PROJECT_V3_CAPABILITY,
            "attachments": [
                {
                    "attachmentId": "11111111-1111-4111-8111-111111111111",
                    "contentType": "image/png",
                    "sizeBytes": 1024,
                    "sha256": "1" * 64,
                },
                {
                    "attachmentId": "22222222-2222-4222-8222-222222222222",
                    "contentType": "image/webp",
                    "sizeBytes": 2048,
                    "sha256": "2" * 64,
                },
            ],
        })
        return request

    def change_request(self, message="hello"):
        request = self.profiled_request()
        change_key = "88888888-8888-4888-8888-888888888888"
        workspace_identity = "remote:test-worker:change:" + change_key
        request.update({
            "workspaceIdentity": workspace_identity,
            "changeOwnership": {
                "changeKey": change_key,
                "databaseWorkSessionId": 19,
                "remoteSessionId": self.session_id,
                "workspaceIdentity": workspace_identity,
                "databaseProjectId": 7,
                "baseCommit": TEST_COMMIT,
                "sourceRevision": 3,
                "sourceFingerprintSha256": "c" * 64,
            },
        })
        request["workload"].update({
            "kind": MODULE.PROJECT_V4_CAPABILITY,
            "message": message,
            "attachments": [],
        })
        for key in (
            "manifestSha256", "instructionBundleRevision",
            "instructionBundleSha256", "platformInstructionSha256",
            "projectInstructionPath", "projectInstructionSha256",
        ):
            request["workload"].pop(key)
        return request

    def wait_terminal(self, dispatch_id, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            execution = self.state.get(dispatch_id)
            if execution["status"] in MODULE.TERMINAL:
                return execution
            time.sleep(0.02)
        self.fail("execution did not become terminal")

    def test_exact_project_dispatch_is_idempotent_and_preserves_thread(self):
        thread_id = str(uuid.uuid4())
        request = self.request(thread_id=thread_id)
        created, was_created = self.state.create(request)
        duplicate, was_created_again = self.state.create(json.loads(json.dumps(request)))
        self.assertTrue(was_created)
        self.assertFalse(was_created_again)
        self.assertEqual(created["executionId"], duplicate["executionId"])
        terminal = self.wait_terminal(request["dispatchId"])
        self.assertEqual("SUCCEEDED", terminal["status"])
        self.assertEqual(thread_id, terminal["result"]["threadId"])

    def test_change_owned_dispatch_reuses_exact_workspace_and_replay_is_stable(self):
        request = self.change_request()
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["selectionEnabled"] = False
        config["commit"] = "2" * 40
        config["manifestSha256"] = "3" * 64
        config.pop("workspaces")
        self.config.write_text(json.dumps(config), encoding="utf-8")
        health = self.state.health()["capabilities"]
        self.assertIn(MODULE.PROJECT_V4_CAPABILITY, health)
        self.assertNotIn(MODULE.PROJECT_CAPABILITY, health)
        self.assertNotIn(MODULE.PROJECT_V2_CAPABILITY, health)
        created, was_created = self.state.create(request)
        terminal = self.wait_terminal(request["dispatchId"])
        calls_before_replay = self.change_mediator_calls.read_text().splitlines()
        duplicate, created_again = self.state.create(json.loads(json.dumps(request)))

        self.assertTrue(was_created)
        self.assertFalse(created_again)
        self.assertEqual(created["executionId"], duplicate["executionId"])
        self.assertEqual("SUCCEEDED", terminal["status"])
        self.assertEqual("project-codex-v4 completed", terminal["result"]["outputSummary"])
        source_identity = terminal["result"]["sourceIdentity"]
        self.assertEqual(
            request["changeOwnership"]["changeKey"], source_identity["changeKey"]
        )
        self.assertEqual(
            terminal["executionId"], source_identity["executionId"]
        )
        self.assertEqual(
            request["workspaceIdentity"], source_identity["workspaceIdentity"]
        )
        self.assertEqual(["INSPECT", "INSPECT"], calls_before_replay)
        self.assertEqual(
            calls_before_replay, self.change_mediator_calls.read_text().splitlines()
        )
        durable = self.state.executions[request["dispatchId"]]
        self.assertEqual(request["changeOwnership"], durable["changeOwnership"])
        self.assertNotIn("path", json.dumps(self.state.get(request["dispatchId"])).lower())

    def test_change_source_identity_rejects_foreign_execution_and_ambiguous_fingerprint(self):
        request = self.change_request()
        request["executionId"] = str(uuid.uuid4())
        ownership = request["changeOwnership"]
        identity = {
            "changeKey": ownership["changeKey"],
            "databaseWorkSessionId": ownership["databaseWorkSessionId"],
            "remoteSessionId": ownership["remoteSessionId"],
            "workspaceIdentity": ownership["workspaceIdentity"],
            "executionId": request["executionId"],
            "sourceCommit": TEST_COMMIT,
            "sourceFingerprintSha256": "d" * 64,
            "workspaceDirty": True,
        }
        self.assertTrue(self.state._valid_change_source_identity(request, identity))

        foreign = json.loads(json.dumps(identity))
        foreign["executionId"] = str(uuid.uuid4())
        self.assertFalse(self.state._valid_change_source_identity(request, foreign))

        ambiguous = json.loads(json.dumps(identity))
        ambiguous["sourceFingerprintSha256"] = None
        self.assertFalse(self.state._valid_change_source_identity(request, ambiguous))

    def test_change_owned_dispatch_rejects_crossed_or_incompatible_ownership(self):
        cases = []
        crossed_change = self.change_request()
        crossed_change["changeOwnership"]["changeKey"] = str(uuid.uuid4())
        cases.append(crossed_change)
        crossed_session = self.change_request()
        crossed_session["changeOwnership"]["remoteSessionId"] = str(uuid.uuid4())
        cases.append(crossed_session)
        crossed_workspace = self.change_request()
        crossed_workspace["changeOwnership"]["workspaceIdentity"] = (
            "remote:test-worker:change:" + str(uuid.uuid4())
        )
        cases.append(crossed_workspace)
        incompatible_source = self.change_request()
        incompatible_source["changeOwnership"]["sourceFingerprintSha256"] = "d" * 64
        cases.append(incompatible_source)

        for request in cases:
            with self.subTest(change=request["changeOwnership"]), self.assertRaises(
                MODULE.ProtocolError
            ):
                self.state.create(request)
            self.assertNotIn(request["dispatchId"], self.state.executions)

    def test_change_owned_dispatch_serializes_same_workspace_across_sessions(self):
        first = self.change_request(message="sleep:0.3")
        self.state.create(first)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.state.get(first["dispatchId"])["status"] in {"STARTING", "RUNNING"}:
                break
            time.sleep(0.01)

        competing = self.change_request()
        competing_session = str(uuid.uuid4())
        competing["sessionId"] = competing_session
        competing["changeOwnership"]["remoteSessionId"] = competing_session
        competing["changeOwnership"]["databaseWorkSessionId"] = 20
        with self.assertRaisesRegex(MODULE.ProtocolError, "non-terminal execution"):
            self.state.create(competing)
        self.assertNotIn(competing["dispatchId"], self.state.executions)
        self.assertEqual("SUCCEEDED", self.wait_terminal(first["dispatchId"])["status"])

    def test_change_owned_dispatch_rejects_durable_worksession_cross_ownership(self):
        first = self.change_request()
        self.state.create(first)
        self.assertEqual("SUCCEEDED", self.wait_terminal(first["dispatchId"])["status"])

        crossed = self.change_request()
        crossed_session = str(uuid.uuid4())
        crossed_change = str(uuid.uuid4())
        crossed_workspace = "remote:test-worker:change:" + crossed_change
        crossed["sessionId"] = crossed_session
        crossed["workspaceIdentity"] = crossed_workspace
        crossed["changeOwnership"].update({
            "changeKey": crossed_change,
            "remoteSessionId": crossed_session,
            "workspaceIdentity": crossed_workspace,
        })
        with self.assertRaisesRegex(MODULE.ProtocolError, "different development change"):
            self.state.create(crossed)
        self.assertNotIn(crossed["dispatchId"], self.state.executions)

    def test_change_owned_replay_conflict_does_not_reinspect_or_execute(self):
        request = self.change_request()
        self.state.create(request)
        self.wait_terminal(request["dispatchId"])
        calls_before = self.change_mediator_calls.read_text()
        runner_calls_before = (
            Path(self.temporary.name) / "project-runner-calls"
        ).read_text()
        conflicting = json.loads(json.dumps(request))
        conflicting["changeOwnership"]["sourceRevision"] += 1

        with self.assertRaisesRegex(MODULE.ProtocolError, "different immutable request"):
            self.state.create(conflicting)
        self.assertEqual(calls_before, self.change_mediator_calls.read_text())
        self.assertEqual(
            runner_calls_before,
            (Path(self.temporary.name) / "project-runner-calls").read_text(),
        )

    def test_legacy_configuration_preserves_text_routing_and_rejects_images(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config.pop("attachmentRoot")
        self.config.write_text(json.dumps(config), encoding="utf-8")

        text_request = self.request()
        created, was_created = self.state.create(text_request)
        self.assertTrue(was_created)
        self.assertEqual(
            "SUCCEEDED", self.wait_terminal(text_request["dispatchId"])["status"]
        )
        self.assertEqual(
            created["executionId"],
            self.state.executions[text_request["dispatchId"]]["executionId"],
        )

        image_request = self.image_request()
        with self.assertRaisesRegex(
            MODULE.ProtocolError, "image-bearing project configuration is not activated"
        ):
            self.state.create(image_request)
        self.assertNotIn(image_request["dispatchId"], self.state.executions)

    def test_profiled_fingerprint_binds_model_effort_and_exact_workspace(self):
        high = self.profiled_request(effort="high")
        medium = json.loads(json.dumps(high))
        medium["workload"]["reasoningEffort"] = "medium"

        self.assertNotEqual(
            self.state.profiled_project_fingerprint(high),
            self.state.profiled_project_fingerprint(medium),
        )
        created, was_created = self.state.create(high)
        self.assertTrue(was_created)
        terminal = self.wait_terminal(high["dispatchId"])
        self.assertEqual("SUCCEEDED", terminal["status"])
        self.assertEqual("gpt-5.6-sol", terminal["result"]["modelId"])
        self.assertEqual("high", terminal["result"]["reasoningEffort"])
        self.assertEqual(MODULE.CODEX_VERSION, terminal["result"]["codexVersion"])
        self.assertEqual(created["executionId"], terminal["result"]["turnId"])

        for field, value in (
            ("modelId", "arbitrary-model"),
            ("reasoningEffort", "ultra"),
            ("catalogRevision", "f" * 64),
            ("codexVersion", "9.9.9"),
        ):
            rejected = self.profiled_request()
            rejected["workload"][field] = value
            with self.assertRaisesRegex(MODULE.ProtocolError, "accepted worker catalog"):
                self.state.profiled_project_fingerprint(rejected)
            self.assertNotIn(rejected["dispatchId"], self.state.executions)

        foreign = self.profiled_request()
        foreign["workspaceIdentity"] = "remote:ax42-01:work-session:" + str(uuid.uuid4())
        with self.assertRaisesRegex(MODULE.ProtocolError, "persistently registered"):
            self.state.profiled_project_fingerprint(foreign)
        self.assertNotIn(foreign["dispatchId"], self.state.executions)

    def test_profiled_fingerprint_rejects_added_operational_authority(self):
        request = self.profiled_request()
        request["workload"]["provider"] = "arbitrary"

        with self.assertRaisesRegex(MODULE.ProtocolError, "fields are invalid"):
            self.state.profiled_project_fingerprint(request)
        self.assertNotIn(request["dispatchId"], self.state.executions)

    def test_image_dispatch_fingerprint_is_ordered_idempotent_and_durable(self):
        request = self.image_request()
        expected_fingerprint = MODULE.canonical_hash(request)

        created, was_created = self.state.create(request)
        self.assertTrue(was_created)
        terminal = self.wait_terminal(request["dispatchId"])
        self.assertEqual("SUCCEEDED", terminal["status"])
        self.assertEqual(
            expected_fingerprint,
            self.state.executions[request["dispatchId"]]["requestFingerprint"],
        )
        self.assertEqual(request["workload"]["attachments"], self.state.executions[
            request["dispatchId"]
        ]["workload"]["attachments"])

        self.state.stop()
        reloaded = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "test-worker",
            project_config=self.config,
            project_runner=self.runner,
            project_timeout=30,
            project_config_uid=os.getuid(),
            privilege_command=(),
        )
        reloaded._observe_project_commit = lambda _route: TEST_COMMIT
        self.state = reloaded
        duplicate, was_created_again = self.state.create(json.loads(json.dumps(request)))
        self.assertFalse(was_created_again)
        self.assertEqual(created["executionId"], duplicate["executionId"])

        reordered = json.loads(json.dumps(request))
        reordered["workload"]["attachments"].reverse()
        self.assertNotEqual(
            expected_fingerprint,
            self.state.profiled_project_fingerprint(reordered),
        )
        state_before = self.state.state_file.read_bytes()
        with self.assertRaisesRegex(MODULE.ProtocolError, "different immutable request"):
            self.state.create(reordered)
        self.assertEqual(state_before, self.state.state_file.read_bytes())
        self.assertEqual(1, (Path(self.temporary.name) / "project-runner-calls").read_text().count(
            "call"
        ))

    def test_image_dispatch_preserves_exact_resumed_thread_with_one_execution(self):
        thread_id = "77777777-7777-4777-8777-777777777777"
        request = self.image_request()
        request["workload"]["threadId"] = thread_id

        created, was_created = self.state.create(request)
        duplicate, was_created_again = self.state.create(json.loads(json.dumps(request)))
        terminal = self.wait_terminal(request["dispatchId"])

        self.assertTrue(was_created)
        self.assertFalse(was_created_again)
        self.assertEqual(created["executionId"], duplicate["executionId"])
        self.assertEqual("SUCCEEDED", terminal["status"])
        self.assertEqual(thread_id, terminal["result"]["threadId"])
        self.assertEqual(1, (Path(self.temporary.name) / "project-runner-calls").read_text().count(
            "call"
        ))

    def test_image_dispatch_rejects_non_exact_or_over_bound_arrays_without_state(self):
        def duplicate_identity(request):
            request["workload"]["attachments"][1]["attachmentId"] = (
                request["workload"]["attachments"][0]["attachmentId"]
            )

        def over_total(request):
            request["workload"]["attachments"] = [
                {
                    "attachmentId": f"{index:08d}-0000-4000-8000-000000000000",
                    "contentType": "image/jpeg",
                    "sizeBytes": MODULE.PROJECT_V3_MAX_ATTACHMENT_BYTES,
                    "sha256": f"{index}" * 64,
                }
                for index in (1, 2)
            ]
            request["workload"]["attachments"].append({
                "attachmentId": "00000003-0000-4000-8000-000000000000",
                "contentType": "image/jpeg",
                "sizeBytes": 1,
                "sha256": "3" * 64,
            })

        cases = (
            ("empty", lambda request: request["workload"].__setitem__("attachments", [])),
            ("over_count", lambda request: request["workload"].__setitem__(
                "attachments", request["workload"]["attachments"] * 3)),
            ("duplicate", duplicate_identity),
            ("non_image", lambda request: request["workload"]["attachments"][0].__setitem__(
                "contentType", "text/plain")),
            ("over_file", lambda request: request["workload"]["attachments"][0].__setitem__(
                "sizeBytes", MODULE.PROJECT_V3_MAX_ATTACHMENT_BYTES + 1)),
            ("boolean_size", lambda request: request["workload"]["attachments"][0].__setitem__(
                "sizeBytes", True)),
            ("over_total", over_total),
            ("bad_digest", lambda request: request["workload"]["attachments"][0].__setitem__(
                "sha256", "A" * 64)),
            ("partial", lambda request: request["workload"]["attachments"][0].pop("sha256")),
            ("path_authority", lambda request: request["workload"]["attachments"][0].__setitem__(
                "path", "/srv/foreign")),
            ("top_level_storage", lambda request: request["workload"].__setitem__(
                "attachmentRoot", "/srv/atenea/attachments-v1")),
            ("foreign_project", lambda request: request["workload"].__setitem__(
                "projectId", MODULE.BEAUTIPS_PROJECT_ID)),
            ("v2_cannot_carry_images", lambda request: request["workload"].__setitem__(
                "kind", MODULE.PROJECT_V2_CAPABILITY)),
            ("v3_requires_images", lambda request: request["workload"].pop("attachments")),
        )
        baseline = MODULE.canonical_hash(self.state.executions)
        for name, mutate in cases:
            request = self.image_request()
            mutate(request)
            with self.subTest(case=name), self.assertRaises(MODULE.ProtocolError):
                self.state.create(request)
            self.assertEqual(baseline, MODULE.canonical_hash(self.state.executions))
            self.assertEqual({}, self.state.processes)

    def test_profiled_runner_cannot_report_a_different_effective_profile(self):
        self.runner.write_text(
            """#!/usr/bin/env python3
import json
import sys
request = json.load(sys.stdin)
print(json.dumps({
    "threadId": "f9d68d92-71c6-4fa5-b77b-63863f8f2dc7",
    "turnId": request["executionId"],
    "finalAnswer": "bounded fake result",
    "outputSummary": "project-codex-v2 completed",
    "modelId": "different-model",
    "reasoningEffort": request["workload"]["reasoningEffort"],
    "catalogRevision": request["workload"]["catalogRevision"],
    "codexVersion": request["workload"]["codexVersion"],
    "progressEvents": []
}))
""",
            encoding="utf-8",
        )
        self.runner.chmod(0o755)
        request = self.profiled_request()

        self.state.create(request)
        terminal = self.wait_terminal(request["dispatchId"])

        self.assertEqual("FAILED", terminal["status"])
        self.assertEqual("Project runner returned invalid output", terminal["statusReason"])
        self.assertIsNone(terminal["result"])

    def test_profiled_progress_is_sequenced_sanitized_and_payload_free(self):
        request = self.profiled_request()
        self.state.create(request)
        terminal = self.wait_terminal(request["dispatchId"])

        events = terminal["progressEvents"]
        self.assertEqual(list(range(1, len(events) + 1)), [event["sequence"] for event in events])
        self.assertEqual("ACCEPTED", events[0]["category"])
        self.assertEqual("COMPLETED", events[-1]["category"])
        self.assertIn("INSPECTING_PROJECT", [event["category"] for event in events])
        self.assertIn("CHECKING", [event["category"] for event in events])
        serialized = json.dumps(events)
        self.assertNotIn("unsafe-ignored", serialized)
        self.assertNotIn("progressEvents", terminal["result"])

        execution = self.state.executions[request["dispatchId"]]
        before = len(execution["progressEvents"])
        self.state._append_runner_progress(execution, [
            {"category": "RUNNING_COMMAND", "occurredAt": "secret",
             "message": "raw command token-value"},
            {"category": "UNKNOWN", "occurredAt": "secret",
             "message": "token-value"},
        ])
        self.assertEqual(before, len(execution["progressEvents"]))
        self.assertNotIn("token-value", json.dumps(execution))

    def test_disabled_foreign_ambiguous_and_arbitrary_requests_fail_closed(self):
        baseline = self.config.read_bytes()
        for mutate in (
            lambda request: request["workload"].__setitem__("projectId", "beautips"),
            lambda request: request["workload"].__setitem__("command", "id"),
            lambda request: request["workload"].__setitem__(
                "instructionBundleSha256", "f" * 64
            ),
            lambda request: request.__setitem__("workspaceIdentity", "remote:foreign"),
        ):
            request = self.request()
            mutate(request)
            with self.assertRaises(MODULE.ProtocolError):
                self.state.create(request)
            self.assertEqual(baseline, self.config.read_bytes())
        parsed = json.loads(baseline)
        parsed["executionEnabled"] = False
        self.config.write_text(json.dumps(parsed), encoding="utf-8")
        self.assertIn("project-codex-v1", self.state.health()["capabilities"])
        with self.assertRaisesRegex(MODULE.ProtocolError, "disabled"):
            self.state.create(self.request())

    def test_complete_caller_authority_matrix_is_denied_without_state_or_process(self):
        baseline_config = self.config.read_bytes()
        baseline_executions = MODULE.canonical_hash(self.state.executions)
        cases = (
            ("command", lambda request: request["workload"].__setitem__(
                "command", ["sh", "-lc", "id"])),
            ("image", lambda request: request["workload"].__setitem__(
                "image", "foreign.invalid/runtime:latest")),
            ("compose", lambda request: request["workload"].__setitem__(
                "composeFile", "docker-compose.foreign.yml")),
            ("environment", lambda request: request["workload"].__setitem__(
                "environment", {"FORBIDDEN_REFERENCE": "synthetic"})),
            ("path", lambda request: request["workload"].__setitem__(
                "path", "/srv/foreign")),
            ("host", lambda request: request["workload"].__setitem__(
                "host", "foreign.invalid")),
            ("slot", lambda request: request["workload"].__setitem__(
                "slot", "slot4")),
            ("endpoint", lambda request: request["workload"].__setitem__(
                "endpoint", "http://127.0.0.1:1")),
            ("credential", lambda request: request["workload"].__setitem__(
                "credential", "synthetic-reference")),
            ("repository", lambda request: request["workload"].__setitem__(
                "repository", "https://github.com/foreign/repository.git")),
            ("rule_source", lambda request: request["workload"].__setitem__(
                "ruleSource", "/tmp/foreign.rules")),
            ("foreign_owner", lambda request: request.__setitem__(
                "workspaceIdentity",
                "remote:ax42-01:work-session:" + str(uuid.uuid4()))),
        )
        for name, mutate in cases:
            request = self.request()
            mutate(request)
            with self.subTest(authority=name), self.assertRaises(MODULE.ProtocolError):
                self.state.create(request)
            self.assertEqual(baseline_config, self.config.read_bytes())
            self.assertEqual(
                baseline_executions,
                MODULE.canonical_hash(self.state.executions),
            )

    def test_moved_worker_mirror_is_rejected_before_dispatch(self):
        self.state._observe_project_commit = lambda _route: "2" * 40

        with self.assertRaisesRegex(MODULE.ProtocolError, "moved before admission"):
            self.state.create(self.request())

    def test_beautips_route_is_independent_and_accepts_only_its_exact_workspace(self):
        self.state.stop()
        root = Path(self.temporary.name)
        atenea_config = json.loads(self.config.read_text(encoding="utf-8"))
        atenea_config["selectionEnabled"] = False
        atenea_config["executionEnabled"] = False
        self.config.write_text(json.dumps(atenea_config), encoding="utf-8")

        beautips_session = str(uuid.uuid4())
        beautips_workspace = "remote:ax42-01:work-session:" + beautips_session
        beautips_config = root / "beautips-project.json"
        beautips_config.write_text(
            json.dumps({
                "schemaVersion": "project-codex-v1",
                "selectionEnabled": True,
                "executionEnabled": True,
                "projectId": MODULE.BEAUTIPS_PROJECT_ID,
                "repository": MODULE.BEAUTIPS_PROJECT_REPOSITORY,
                "branch": MODULE.BEAUTIPS_PROJECT_BRANCH,
                "commit": MODULE.BEAUTIPS_PROJECT_COMMIT,
                "manifestSha256": MODULE.BEAUTIPS_PROJECT_MANIFEST_SHA256,
                "runner": str(self.runner),
                "workspaces": {
                    beautips_workspace: {
                        "sessionId": beautips_session,
                        "worktree": (
                            "/srv/atenea/workspaces/sessions/"
                            + beautips_session
                            + "/beautips"
                        ),
                        "allocationSha256": "b" * 64,
                    }
                },
            }),
            encoding="utf-8",
        )
        beautips_config.chmod(0o644)
        self.state = MODULE.WorkerState(
            root / "state-beautips",
            "test-worker",
            project_config=self.config,
            project_runner=self.runner,
            project_timeout=30,
            project_config_uid=os.getuid(),
            privilege_command=(),
            beautips_project_config=beautips_config,
            beautips_project_runner=self.runner,
        )
        self.state.start()
        self.assertIn("project-codex-v1", self.state.health()["capabilities"])

        exact = self.request()
        exact["sessionId"] = beautips_session
        exact["workspaceIdentity"] = beautips_workspace
        exact["workload"].update({
            "projectId": MODULE.BEAUTIPS_PROJECT_ID,
            "repository": MODULE.BEAUTIPS_PROJECT_REPOSITORY,
            "branch": MODULE.BEAUTIPS_PROJECT_BRANCH,
            "commit": MODULE.BEAUTIPS_PROJECT_COMMIT,
            "manifestSha256": MODULE.BEAUTIPS_PROJECT_MANIFEST_SHA256,
            "instructionBundleSha256": MODULE.BEAUTIPS_INSTRUCTION_BUNDLE_SHA256,
            "projectInstructionSha256": MODULE.BEAUTIPS_PROJECT_INSTRUCTION_SHA256,
        })
        accepted, created = self.state.create(exact)
        self.assertTrue(created)
        self.assertEqual("SUCCEEDED", self.wait_terminal(accepted["dispatchId"])["status"])

        state_before = self.state.state_file.read_bytes()
        foreign_workspace = self.request()
        foreign_workspace["sessionId"] = str(uuid.uuid4())
        foreign_workspace["workspaceIdentity"] = (
            "remote:ax42-01:work-session:" + foreign_workspace["sessionId"]
        )
        foreign_workspace["workload"].update(exact["workload"])
        with self.assertRaisesRegex(MODULE.ProtocolError, "workspace identity"):
            self.state.create(foreign_workspace)
        self.assertEqual(state_before, self.state.state_file.read_bytes())

        with self.assertRaisesRegex(MODULE.ProtocolError, "disabled"):
            self.state.create(self.request())

    def test_cancel_terminates_only_exact_project_process(self):
        request = self.request(message="sleep:3")
        other = self.request(message="hello")
        execution, _ = self.state.create(request)
        self.state.create(other)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.state.get(request["dispatchId"])["status"] == "RUNNING":
                break
            time.sleep(0.02)
        self.state.cancel(request["dispatchId"], {"executionId": execution["executionId"]})
        terminal = self.wait_terminal(request["dispatchId"])
        other_terminal = self.wait_terminal(other["dispatchId"])
        self.assertEqual("CANCELLED", terminal["status"])
        self.assertEqual("SUCCEEDED", other_terminal["status"])

    def test_restart_reconciliation_does_not_duplicate_uncertain_turn(self):
        request = self.request(message="sleep:3")
        created, _ = self.state.create(request)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.state.get(request["dispatchId"])["status"] == "RUNNING":
                break
            time.sleep(0.02)
        self.state.stop()
        state_file = Path(self.temporary.name) / "state" / "executions.json"
        persisted = json.loads(state_file.read_text(encoding="utf-8"))
        persisted["executions"][request["dispatchId"]]["status"] = "RUNNING"
        persisted["executions"][request["dispatchId"]]["statusReason"] = "simulated uncertain process"
        state_file.write_text(json.dumps(persisted), encoding="utf-8")
        recovered = MODULE.WorkerState(
            Path(self.temporary.name) / "state",
            "test-worker",
            project_config=self.config,
            project_runner=self.runner,
            project_timeout=30,
            project_config_uid=os.getuid(),
            privilege_command=(),
        )
        recovered.start()
        self.state = recovered
        terminal = self.wait_terminal(request["dispatchId"])
        self.assertEqual(created["executionId"], terminal["executionId"])
        self.assertEqual("FAILED", terminal["status"])
        self.assertIn("refused to duplicate", terminal["statusReason"])


class CodexUpdateStageWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.calls = root / "calls"
        self.registry = root / "registry.json"
        self.registry.write_text("{}", encoding="utf-8")
        self.release_root = root / "releases"
        self.mediator = root / "mediator.py"
        self.mediator.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import pathlib
import sys
request = json.load(sys.stdin)
calls = pathlib.Path(sys.argv[0]).with_name("calls")
calls.write_text(calls.read_text() + "1\\n" if calls.exists() else "1\\n")
digest = hashlib.sha256(b"synthetic").hexdigest()
print(json.dumps({
    "schemaVersion": "codex-update-stage-v1",
    "operation": request["operation"],
    "workerId": "ax42-01",
    "planId": request["planId"],
    "candidateId": request["candidateId"],
    "idempotencyKey": request["idempotencyKey"],
    "state": "STAGED",
    "codexVersion": "0.146.0",
    "releaseDigestSha256": digest,
    "catalogRevision": digest,
    "releaseManifestSha256": digest,
    "schemaManifestSha256": digest,
    "releaseVerification": "PASS",
    "schemaGeneration": "PASS",
    "retention": "PASS",
    "currentLinkFingerprint": digest,
    "previousLinkFingerprint": digest,
    "linksChanged": False,
    "valuesExposed": False,
}))
""",
            encoding="utf-8",
        )
        self.mediator.chmod(0o755)
        self.state = MODULE.WorkerState(
            root / "state", "ax42-01", privilege_command=(),
            codex_update_mediator=self.mediator,
            codex_update_registry=self.registry,
            codex_release_root=self.release_root,
        )
        self.request = {
            "operation": "STAGE_CODEX_UPDATE",
            "planId": str(uuid.uuid4()),
            "candidateId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_closed_stage_invokes_only_fixed_mediator_and_validates_result(self):
        self.assertIn(MODULE.CODEX_UPDATE_STAGE_CAPABILITY,
                      self.state.health()["capabilities"])
        result = self.state.stage_codex_update(self.request)
        self.assertEqual("STAGED", result["state"])
        self.assertFalse(result["linksChanged"])
        self.assertFalse(result["valuesExposed"])
        self.assertEqual(["1"], self.calls.read_text().splitlines())

        with self.assertRaisesRegex(MODULE.ProtocolError, "exact"):
            self.state.stage_codex_update({**self.request, "releaseUrl": "https://foreign.invalid"})
        self.assertEqual(["1"], self.calls.read_text().splitlines())

    def test_conflicting_mediator_result_fails_closed(self):
        source = self.mediator.read_text(encoding="utf-8")
        self.mediator.write_text(source.replace('"workerId": "ax42-01"',
                                                '"workerId": "foreign"'),
                                 encoding="utf-8")
        self.mediator.chmod(0o755)
        with self.assertRaisesRegex(MODULE.ProtocolError, "conflicting"):
            self.state.stage_codex_update(self.request)


class CodexUpdateActivationWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.calls = root / "activation-calls"
        self.registry = root / "registry.json"
        self.registry.write_text("{}", encoding="utf-8")
        self.release_root = root / "releases"
        self.mediator = root / "activate.py"
        self.mediator.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import pathlib
import sys
request = json.load(sys.stdin)
calls = pathlib.Path(sys.argv[0]).with_name("activation-calls")
calls.write_text(calls.read_text() + "1\\n" if calls.exists() else "1\\n")
digest = hashlib.sha256(b"synthetic-activation").hexdigest()
if request["operation"] == "ROLLBACK_CODEX_UPDATE":
    print(json.dumps({
        "schemaVersion": "codex-update-rollback-v1",
        "operation": request["operation"],
        "workerId": "ax42-01",
        "planId": request["planId"],
        "candidateId": request["candidateId"],
        "activationId": request["activationId"],
        "authorizationId": request["authorizationId"],
        "idempotencyKey": request["idempotencyKey"],
        "state": "ROLLED_BACK",
        "linkRestore": "PASS",
        "workerServiceRestart": "PASS",
        "affectedServices": ["atenea-agent-run-worker-v1.service"],
        "appServerServicesRestarted": 0,
        "currentBeforeFingerprint": digest,
        "previousBeforeFingerprint": digest,
        "currentAfterFingerprint": digest,
        "previousAfterFingerprint": digest,
        "valuesExposed": False,
    }))
    raise SystemExit(0)
print(json.dumps({
    "schemaVersion": "codex-update-activate-v1",
    "operation": request["operation"],
    "workerId": "ax42-01",
    "planId": request["planId"],
    "candidateId": request["candidateId"],
    "authorizationId": request["authorizationId"],
    "idempotencyKey": request["idempotencyKey"],
    "state": "ACTIVATED",
    "codexVersion": "0.146.0",
    "releaseDigestSha256": digest,
    "catalogRevision": digest,
    "schemaComparison": "PASS",
    "focusedContracts": "PASS",
    "workerHealth": "PASS",
    "canary": "PASS",
    "currentBeforeFingerprint": digest,
    "previousBeforeFingerprint": digest,
    "currentAfterFingerprint": digest,
    "previousAfterFingerprint": digest,
    "automaticRestore": "NOT_REQUIRED",
    "valuesExposed": False,
}))
""",
            encoding="utf-8",
        )
        self.mediator.chmod(0o755)
        self.state = MODULE.WorkerState(
            root / "state", "ax42-01", privilege_command=(),
            codex_update_mediator=self.mediator,
            codex_activate_mediator=self.mediator,
            codex_rollback_mediator=self.mediator,
            codex_restart_scheduler=self.mediator,
            codex_update_registry=self.registry,
            codex_release_root=self.release_root,
        )
        self.request = {
            "operation": "ACTIVATE_CODEX_UPDATE",
            "planId": str(uuid.uuid4()),
            "candidateId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        self.rollback_request = {
            "operation": "ROLLBACK_CODEX_UPDATE",
            "planId": self.request["planId"],
            "candidateId": self.request["candidateId"],
            "activationId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_closed_activation_requires_zero_runs_and_validates_all_gates(self):
        self.assertIn(MODULE.CODEX_UPDATE_ACTIVATE_CAPABILITY,
                      self.state.health()["capabilities"])
        result = self.state.activate_codex_update(self.request)
        self.assertEqual("ACTIVATED", result["state"])
        self.assertEqual("PASS", result["canary"])
        self.assertEqual(["1"], self.calls.read_text().splitlines())

        with self.assertRaisesRegex(MODULE.ProtocolError, "exact"):
            self.state.activate_codex_update({**self.request, "service": "foreign.service"})
        self.state.executions["active"] = {"status": "RUNNING"}
        with self.assertRaisesRegex(MODULE.ProtocolError, "zero"):
            self.state.activate_codex_update({**self.request, "idempotencyKey": str(uuid.uuid4())})
        self.assertEqual(["1"], self.calls.read_text().splitlines())

    def test_conflicting_activation_result_fails_closed(self):
        source = self.mediator.read_text(encoding="utf-8")
        self.mediator.write_text(source.replace('"canary": "PASS"', '"canary": "FAIL"'),
                                 encoding="utf-8")
        self.mediator.chmod(0o755)
        with self.assertRaisesRegex(MODULE.ProtocolError, "conflicting"):
            self.state.activate_codex_update(self.request)

    def test_closed_rollback_restarts_only_exact_worker_boundary(self):
        self.assertIn(MODULE.CODEX_UPDATE_ROLLBACK_CAPABILITY,
                      self.state.health()["capabilities"])
        result = self.state.rollback_codex_update(self.rollback_request)
        self.assertEqual("ROLLED_BACK", result["state"])
        self.assertEqual(["atenea-agent-run-worker-v1.service"],
                         result["affectedServices"])
        self.assertEqual(0, result["appServerServicesRestarted"])
        with self.assertRaisesRegex(MODULE.ProtocolError, "exact"):
            self.state.rollback_codex_update(
                {**self.rollback_request, "service": "foreign.service"})
        self.state.executions["active"] = {"status": "RUNNING"}
        with self.assertRaisesRegex(MODULE.ProtocolError, "zero"):
            self.state.rollback_codex_update(
                {**self.rollback_request, "idempotencyKey": str(uuid.uuid4())})


class MaterializationStartupReconciliationTest(unittest.TestCase):
    def test_start_resolves_uncertain_project_then_runs_closed_reconciler(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captured = root / "captured.json"
            runner = root / "runner"
            runner.write_text(
                """#!/usr/bin/env python3
import json
import pathlib
import sys
payload = json.load(sys.stdin)
pathlib.Path(sys.argv[0]).with_name("captured.json").write_text(
    json.dumps({"arguments": sys.argv[1:], "payload": payload}, sort_keys=True)
)
print(json.dumps({
    "schemaVersion": "codex-image-reconciliation-v1",
    "state": "PASS",
    "removed": 1,
    "retained": 0,
    "ambiguous": 0,
    "valuesExposed": False,
}))
""",
                encoding="utf-8",
            )
            runner.chmod(0o755)
            config = root / "project.json"
            state = MODULE.WorkerState(
                root / "state",
                "test-worker",
                project_config=config,
                project_runner=runner,
                privilege_command=(),
                reconcile_materializations_on_start=True,
            )
            dispatch_id = "11111111-1111-4111-8111-111111111111"
            execution_id = "22222222-2222-4222-8222-222222222222"
            attachment = {
                "attachmentId": "33333333-3333-4333-8333-333333333333",
                "contentType": "image/png",
                "sizeBytes": 8,
                "sha256": "a" * 64,
            }
            state.executions[dispatch_id] = {
                "dispatchId": dispatch_id,
                "executionId": execution_id,
                "status": "RECONCILING",
                "statusReason": "restart",
                "workload": {"kind": MODULE.PROJECT_V3_CAPABILITY, "attachments": [attachment]},
                "revision": 1,
                "updatedAt": MODULE.utc_now(),
                "finishedAt": None,
                "progressEvents": [],
                "nextProgressSequence": 1,
            }
            state.start()
            state.stop()

            self.assertEqual("FAILED", state.executions[dispatch_id]["status"])
            observed = json.loads(captured.read_text(encoding="utf-8"))
            self.assertEqual(
                ["--config", str(config), "--reconcile-materializations"],
                observed["arguments"],
            )
            self.assertEqual("FAILED", observed["payload"]["executions"][0]["status"])
            self.assertEqual([attachment], observed["payload"]["executions"][0]["attachments"])
            self.assertNotIn("message", json.dumps(observed))

    def test_ambiguous_reconciler_result_blocks_worker_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = root / "runner"
            runner.write_text(
                """#!/usr/bin/env python3
import json
print(json.dumps({
    "schemaVersion": "codex-image-reconciliation-v1",
    "state": "PASS",
    "removed": 0,
    "retained": 0,
    "ambiguous": 1,
    "valuesExposed": False,
}))
""",
                encoding="utf-8",
            )
            runner.chmod(0o755)
            state = MODULE.WorkerState(
                root / "state",
                "test-worker",
                project_config=root / "project.json",
                project_runner=runner,
                privilege_command=(),
                reconcile_materializations_on_start=True,
            )
            with self.assertRaisesRegex(RuntimeError, "failed closed"):
                state.start()
            self.assertIsNone(state.scheduler)


class WorkerHttpTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = MODULE.WorkerState(Path(self.temporary.name), "http-worker", 4, 2)
        self.server = MODULE.AgentRunServer(("127.0.0.1", 0), self.state, "t" * 64)
        self.state.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.state.stop()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, path, token=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        return urllib.request.urlopen(
            urllib.request.Request(self.url + path, headers=headers),
            timeout=2,
        )

    def test_http_log_exposes_no_request_path_or_identity(self):
        handler = object.__new__(MODULE.AgentRunHandler)
        output = io.StringIO()
        execution_id = str(uuid.uuid4())
        sensitive_path = f"/v1/executions/{execution_id}"

        with mock.patch("sys.stdout", output):
            handler.log_message('"%s" %s %s', f"GET {sensitive_path} HTTP/1.1", "200", "-")

        payload = json.loads(output.getvalue())
        self.assertEqual({"at", "event"}, set(payload))
        self.assertEqual("http_request", payload["event"])
        self.assertNotIn(sensitive_path, output.getvalue())
        self.assertNotIn(execution_id, output.getvalue())

    def post(self, path, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        return urllib.request.urlopen(
            urllib.request.Request(
                self.url + path,
                data=json.dumps(body).encode(),
                headers=headers,
                method="POST",
            ),
            timeout=2,
        )

    def test_durable_validation_routes_dispatch_versioned_operations(self):
        request = {"operation": "opaque-test-request"}
        response = {"state": "QUEUED", "valuesExposed": False}
        observed = []

        def start(body):
            observed.append(("start", body))
            return response, True

        def inspect(body):
            observed.append(("inspect", body))
            return response

        def cancel(body):
            observed.append(("cancel", body))
            return {**response, "state": "CANCELLED"}

        self.state.start_validation = start
        self.state.inspect_validation = inspect
        self.state.cancel_validation = cancel
        states = []
        statuses = []
        for action in ("start", "inspect", "cancel"):
            with self.post(
                MODULE.CLOSED_VALIDATION_PATH_PREFIX + action,
                request,
                "t" * 64,
            ) as http_response:
                statuses.append(http_response.status)
                states.append(json.load(http_response)["state"])

        self.assertEqual([202, 200, 200], statuses)
        self.assertEqual(["QUEUED", "QUEUED", "CANCELLED"], states)
        self.assertEqual(
            [("start", request), ("inspect", request), ("cancel", request)],
            observed,
        )

    def test_workspace_release_route_dispatches_exact_authenticated_request(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        request = {
            "operationId": "22222222-2222-4222-8222-222222222222",
            "idempotencyKey": "33333333-3333-4333-8333-333333333333",
            "sessionId": session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + session_id,
        }
        expected = WorkspaceReleaseContractTest()
        expected.setUp()
        receipt = expected.receipt()
        observed = []

        def release_workspace(body):
            observed.append(body)
            return receipt

        self.state.release_workspace = release_workspace
        with self.post(MODULE.WORKSPACE_RELEASE_PATH, request, "t" * 64) as response:
            payload = json.load(response)

        self.assertEqual([request], observed)
        self.assertEqual(receipt, payload)

    def test_readiness_and_unactivated_release_routes_are_exact_and_authenticated(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        readiness_request = {
            "sessionId": session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + session_id,
        }
        release_request = {
            "operationId": "22222222-2222-4222-8222-222222222222",
            "idempotencyKey": "33333333-3333-4333-8333-333333333333",
            **readiness_request,
        }
        readiness = {
            "schemaVersion": MODULE.WORKSPACE_READINESS_SCHEMA,
            "state": "SOURCE_ADVANCED",
            "sessionId": session_id,
            "workspaceIdentity": readiness_request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "http-worker",
            "requestedCommit": TEST_COMMIT,
            "canonicalCommit": "2" * 40,
            "retryAllowed": False,
            "nextAction": "START_FRESH_SESSION",
            "requestFingerprintSha256": MODULE.canonical_hash(readiness_request),
            "relationshipFingerprintSha256": "4" * 64,
            "valuesExposed": False,
        }
        receipt_fixture = WorkspaceReleaseContractTest()
        receipt_fixture.setUp()
        receipt = receipt_fixture.receipt()
        observed = []
        self.state.diagnose_workspace_readiness = lambda body: (
            observed.append(("readiness", body)) or readiness
        )
        self.state.release_unactivated_workspace = lambda body: (
            observed.append(("release", body)) or receipt
        )

        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.post(MODULE.WORKSPACE_READINESS_PATH, readiness_request)
        self.assertEqual(401, denied.exception.code)
        with self.post(
            MODULE.WORKSPACE_READINESS_PATH, readiness_request, "t" * 64
        ) as response:
            self.assertEqual(readiness, json.load(response))
        with self.post(
            MODULE.WORKSPACE_UNACTIVATED_RELEASE_PATH,
            release_request,
            "t" * 64,
        ) as response:
            self.assertEqual(receipt, json.load(response))

        self.assertEqual([
            ("readiness", readiness_request),
            ("release", release_request),
        ], observed)

    def test_capacity_owner_route_dispatches_exact_authenticated_request(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        request = {
            "sessionId": session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + session_id,
        }
        result = {
            "schemaVersion": MODULE.WORKSPACE_CAPACITY_OWNER_SCHEMA,
            "state": "OWNED",
            "sessionId": session_id,
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "test-worker",
            "requestFingerprintSha256": MODULE.canonical_hash(request),
            "ownershipFingerprintSha256": "8" * 64,
            "valuesExposed": False,
        }
        observed = []

        def diagnose(body):
            observed.append(body)
            return result

        self.state.diagnose_workspace_capacity_owner = diagnose
        with self.post(MODULE.WORKSPACE_CAPACITY_OWNER_PATH, request, "t" * 64) as response:
            payload = json.load(response)

        self.assertEqual([request], observed)
        self.assertEqual(result, payload)

    def test_release_preflight_route_dispatches_exact_authenticated_request(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        request = {
            "operationId": "22222222-2222-4222-8222-222222222222",
            "idempotencyKey": "22222222-2222-4222-8222-222222222222",
            "sessionId": session_id,
            "workspaceIdentity": "remote:ax42-01:work-session:" + session_id,
            "projectId": MODULE.PROJECT_ID,
            "repository": MODULE.PROJECT_REPOSITORY,
            "branch": MODULE.PROJECT_BRANCH,
            "commit": TEST_COMMIT,
            "manifestSha256": MODULE.PROJECT_MANIFEST_SHA256,
            "workspaceBranch": "atenea/session-" + session_id,
        }
        result = {
            "schemaVersion": MODULE.WORKSPACE_RELEASE_PREFLIGHT_SCHEMA,
            "state": "PREFLIGHT_ACCEPTED",
            "operationId": request["operationId"],
            "sessionId": session_id,
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": MODULE.PROJECT_ID,
            "workerId": "test-worker",
            "requestFingerprintSha256": MODULE.canonical_hash(request),
            "ownershipFingerprintSha256": "8" * 64,
            "allocationFingerprintSha256": "9" * 64,
            "valuesExposed": False,
        }
        observed = []

        def diagnose(body):
            observed.append(body)
            return result

        self.state.diagnose_workspace_release_preflight = diagnose
        with self.post(
            MODULE.WORKSPACE_RELEASE_PREFLIGHT_PATH, request, "t" * 64
        ) as response:
            payload = json.load(response)

        self.assertEqual([request], observed)
        self.assertEqual(result, payload)

    def test_health_requires_authentication_and_exposes_capacity(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.request("/v1/health")
        self.assertEqual(401, denied.exception.code)
        error = json.load(denied.exception)
        self.assertEqual(
            {"schemaVersion", "code", "category", "retryable", "nextAction"},
            set(error),
        )
        self.assertEqual("UNAUTHORIZED", error["code"])
        self.assertEqual("POLICY", error["category"])
        self.assertFalse(error["retryable"])
        self.assertNotIn("credential", json.dumps(error))
        with self.request("/v1/health", "t" * 64) as accepted:
            health = json.load(accepted)
        self.assertEqual("agent-run-worker/v1", health["protocolVersion"])
        self.assertEqual(4, health["normalCapacity"])
        self.assertEqual(2, health["heavyCapacity"])

    def test_catalog_requires_authentication_and_exposes_closed_inventory(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.request("/v1/codex/catalog")
        self.assertEqual(401, denied.exception.code)

        with self.request("/v1/codex/catalog", "t" * 64) as accepted:
            catalog = json.load(accepted)
        self.assertEqual(
            {
                "schemaVersion",
                "catalogRevision",
                "workerId",
                "codexVersion",
                "generatedAt",
                "models",
            },
            set(catalog),
        )
        self.assertEqual("http-worker", catalog["workerId"])
        self.assertEqual("gpt-5.6-sol", catalog["models"][0]["modelId"])

    def test_exact_reconcile_and_doctor_routes_require_closed_ownership(self):
        request = {
            "dispatchId": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "workspaceIdentity": "remote:test:" + str(uuid.uuid4()),
            "workloadClass": "NORMAL",
            "leaseGeneration": 1,
            "workload": {
                "kind": "synthetic-routing-v1",
                "message": "synthetic marker",
                "durationMs": 500,
                "steps": 5,
            },
        }
        execution, _ = self.state.create(request)
        exact = {
            "executionId": execution["executionId"],
            "sessionId": execution["sessionId"],
            "workspaceIdentity": execution["workspaceIdentity"],
            "leaseGeneration": execution["leaseGeneration"],
        }
        base = "/v1/executions/" + request["dispatchId"]

        with self.post(base + "/reconcile", exact, "t" * 64) as response:
            inspected = json.load(response)
        with self.post(base + "/doctor", exact, "t" * 64) as response:
            diagnostic = json.load(response)

        self.assertEqual(execution["executionId"], inspected["executionId"])
        self.assertEqual("agent-run-doctor-v1", diagnostic["schemaVersion"])
        self.assertFalse(diagnostic["valuesExposed"])
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post(base + "/doctor", {**exact, "host": "foreign.invalid"}, "t" * 64)
        self.assertEqual(400, rejected.exception.code)

    def test_stage_route_is_authenticated_closed_and_unavailable_without_mediator(self):
        exact = {
            "operation": "STAGE_CODEX_UPDATE",
            "planId": str(uuid.uuid4()),
            "candidateId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        with self.assertRaises(urllib.error.HTTPError) as unauthenticated:
            self.post("/v1/codex/update/stage", exact)
        self.assertEqual(401, unauthenticated.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as unavailable:
            self.post("/v1/codex/update/stage", exact, "t" * 64)
        self.assertEqual(503, unavailable.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post("/v1/codex/update/stage", {**exact, "path": "/tmp/release"}, "t" * 64)
        self.assertEqual(400, rejected.exception.code)

    def test_activation_route_is_authenticated_closed_and_unavailable_without_mediator(self):
        exact = {
            "operation": "ACTIVATE_CODEX_UPDATE",
            "planId": str(uuid.uuid4()),
            "candidateId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        with self.assertRaises(urllib.error.HTTPError) as unauthenticated:
            self.post("/v1/codex/update/activate", exact)
        self.assertEqual(401, unauthenticated.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as unavailable:
            self.post("/v1/codex/update/activate", exact, "t" * 64)
        self.assertEqual(503, unavailable.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post("/v1/codex/update/activate", {**exact, "host": "foreign"}, "t" * 64)
        self.assertEqual(400, rejected.exception.code)

    def test_rollback_route_is_authenticated_closed_and_unavailable_without_mediator(self):
        exact = {
            "operation": "ROLLBACK_CODEX_UPDATE",
            "planId": str(uuid.uuid4()),
            "candidateId": str(uuid.uuid4()),
            "activationId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        with self.assertRaises(urllib.error.HTTPError) as unauthenticated:
            self.post("/v1/codex/update/rollback", exact)
        self.assertEqual(401, unauthenticated.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as unavailable:
            self.post("/v1/codex/update/rollback", exact, "t" * 64)
        self.assertEqual(503, unavailable.exception.code)
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.post("/v1/codex/update/rollback", {**exact, "service": "foreign"}, "t" * 64)
        self.assertEqual(400, rejected.exception.code)


if __name__ == "__main__":
    unittest.main()
