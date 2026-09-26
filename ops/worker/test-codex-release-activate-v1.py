#!/usr/bin/env python3

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path


SCRIPT = Path(__file__).with_name("codex-release-activate-v1.py")
RESTART_SCRIPT = Path(__file__).with_name("codex-release-restart-v1.sh")


class CodexReleaseActivateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "codex-releases-v1"
        self.releases = self.root / "releases"
        self.operations = self.root / "operations"
        self.activations = self.root / "activations"
        self.rollbacks = self.root / "rollbacks"
        self.releases.mkdir(parents=True)
        self.operations.mkdir()
        self.activations.mkdir()
        self.rollbacks.mkdir()
        for directory in (
                self.root, self.releases, self.operations, self.activations, self.rollbacks):
            directory.chmod(0o750)
        self.current_release = self._release("0.144.0", "current")
        self.previous_release = self._release("0.143.0", "previous")
        self.digest = hashlib.sha256(b"candidate").hexdigest()
        self.catalog = hashlib.sha256(b"catalog").hexdigest()
        self.version = "0.146.0"
        self.candidate_name = self.version + "-" + self.digest[:16]
        self.candidate_release = self._release(self.version, "candidate", self.candidate_name)
        (self.root / "current").symlink_to("releases/" + self.current_release.name)
        (self.root / "previous").symlink_to("releases/" + self.previous_release.name)
        self.plan_id = str(uuid.uuid4())
        self.candidate_id = str(uuid.uuid4())
        self.authorization_id = str(uuid.uuid4())
        self.idempotency_key = str(uuid.uuid4())
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps({
            "schemaVersion": "codex-release-stage-v1",
            "workerId": "ax42-01",
            "candidates": {self.candidate_id: {
                "planId": self.plan_id,
                "candidateId": self.candidate_id,
                "codexVersion": self.version,
                "releaseDigestSha256": self.digest,
                "catalogRevision": self.catalog,
            }},
        }), encoding="utf-8")
        self.registry.chmod(0o600)
        self.restart_scheduler = self.root / "restart-scheduler"
        self.restart_scheduler.write_text(
            "#!/bin/sh\nprintf '%s %s\\n' \"$1\" \"$2\" >> '" +
            str(self.root / "restart-calls") + "'\nexit 0\n", encoding="utf-8")
        self.restart_scheduler.chmod(0o700)
        self._write_stage(str(uuid.uuid4()))
        self.request = {
            "operation": "ACTIVATE_CODEX_UPDATE",
            "planId": self.plan_id,
            "candidateId": self.candidate_id,
            "authorizationId": self.authorization_id,
            "idempotencyKey": self.idempotency_key,
        }

    def tearDown(self):
        self.temporary.cleanup()

    def _release(self, version, label, name=None):
        release = self.releases / (name or label)
        (release / "bin").mkdir(parents=True)
        schemas = release / "generated-schemas"
        schemas.mkdir()
        for directory in (release, release / "bin", schemas):
            directory.chmod(0o700)
        for schema in ("app-server.schema.json", "cli.schema.json"):
            schema_path = schemas / schema
            schema_path.write_text(
                json.dumps({"x-codex-version": version}), encoding="utf-8")
            schema_path.chmod(0o600)
        for gate in ("run-focused-contracts", "health-check", "run-canary"):
            executable = release / "bin" / gate
            executable.write_text(
                "#!/bin/sh\nprintf '%s\\n' '" + gate + "' >> '" +
                str(self.root / "gate-calls") + "'\nexit 0\n", encoding="utf-8")
            executable.chmod(0o700)
        return release

    def _write_stage(self, operation_id):
        result = {
            "state": "STAGED", "planId": self.plan_id,
            "candidateId": self.candidate_id, "codexVersion": self.version,
            "releaseDigestSha256": self.digest, "catalogRevision": self.catalog,
            "releaseVerification": "PASS", "schemaGeneration": "PASS",
            "retention": "PASS", "linksChanged": False, "valuesExposed": False,
        }
        operation = self.operations / (operation_id + ".json")
        operation.write_text(
            json.dumps({"requestFingerprint": "f" * 64, "result": result}),
            encoding="utf-8")
        operation.chmod(0o600)

    def _run(self, request=None):
        return subprocess.run(
            [str(SCRIPT), "--registry", str(self.registry),
             "--release-root", str(self.root),
             "--registry-owner-uid", str(os.geteuid()),
             "--release-owner-uid", str(os.geteuid()),
             "--restart-scheduler", str(self.restart_scheduler)],
            input=json.dumps(request or self.request), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        )

    def _links(self):
        return os.readlink(self.root / "current"), os.readlink(self.root / "previous")

    def test_activation_runs_each_gate_once_switches_exact_links_and_repeats(self):
        before = self._links()
        first = self._run()
        self.assertEqual(0, first.returncode, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual("ACTIVATED", result["state"])
        self.assertEqual("PASS", result["schemaComparison"])
        self.assertEqual("PASS", result["focusedContracts"])
        self.assertEqual("PASS", result["workerHealth"])
        self.assertEqual("PASS", result["canary"])
        self.assertEqual("releases/" + self.candidate_name,
                         os.readlink(self.root / "current"))
        self.assertEqual(before[0], os.readlink(self.root / "previous"))
        self.assertEqual(
            ["run-focused-contracts", "health-check", "run-canary"],
            (self.root / "gate-calls").read_text().splitlines())

        second = self._run()
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(result, json.loads(second.stdout))
        self.assertEqual(3, len((self.root / "gate-calls").read_text().splitlines()))

        conflict = self._run({**self.request, "authorizationId": str(uuid.uuid4())})
        self.assertNotEqual(0, conflict.returncode)
        self.assertEqual(3, len((self.root / "gate-calls").read_text().splitlines()))

    def test_extra_authority_and_conflicting_stage_fail_before_links(self):
        before = self._links()
        extra = self._run({**self.request, "service": "foreign.service"})
        self.assertNotEqual(0, extra.returncode)
        self.assertEqual(before, self._links())
        self._write_stage(str(uuid.uuid4()))
        repeated = self._run()
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        self.assertEqual("ACTIVATED", json.loads(repeated.stdout)["state"])

    def test_conflicting_repeated_stage_fails_before_links(self):
        before = self._links()
        second_id = str(uuid.uuid4())
        self._write_stage(second_id)
        second_path = self.operations / (second_id + ".json")
        second = json.loads(second_path.read_text(encoding="utf-8"))
        second["result"]["schemaManifestSha256"] = "a" * 64
        second_path.write_text(json.dumps(second), encoding="utf-8")
        ambiguous = self._run()
        self.assertNotEqual(0, ambiguous.returncode)
        self.assertEqual(before, self._links())

    def test_focused_contract_failure_never_changes_links(self):
        before = self._links()
        gate = self.candidate_release / "bin" / "run-focused-contracts"
        gate.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
        gate.chmod(0o700)
        result = self._run()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, self._links())

    def test_health_and_canary_failures_restore_both_links(self):
        for gate_name in ("health-check", "run-canary"):
            with self.subTest(gate=gate_name):
                before = self._links()
                gate = self.candidate_release / "bin" / gate_name
                original = gate.read_text(encoding="utf-8")
                gate.write_text("#!/bin/sh\nexit 8\n", encoding="utf-8")
                gate.chmod(0o700)
                result = self._run()
                self.assertNotEqual(0, result.returncode)
                self.assertEqual(before, self._links())
                self.assertEqual([], list(self.activations.iterdir()))
                gate.write_text(original, encoding="utf-8")
                gate.chmod(0o700)

    def test_rollback_swaps_exact_links_restarts_only_worker_and_repeats(self):
        original = self._links()
        activated = self._run()
        self.assertEqual(0, activated.returncode, activated.stderr)
        activation_links = self._links()
        rollback = {
            "operation": "ROLLBACK_CODEX_UPDATE",
            "planId": self.plan_id,
            "candidateId": self.candidate_id,
            "activationId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        first = self._run(rollback)
        self.assertEqual(0, first.returncode, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual("ROLLED_BACK", result["state"])
        self.assertEqual("PASS", result["linkRestore"])
        self.assertEqual("PASS", result["workerServiceRestart"])
        self.assertEqual(["atenea-agent-run-worker-v1.service"],
                         result["affectedServices"])
        self.assertEqual(0, result["appServerServicesRestarted"])
        self.assertEqual((activation_links[1], activation_links[0]), self._links())
        self.assertEqual(original[0], self._links()[0])
        calls = (self.root / "restart-calls").read_text().splitlines()
        self.assertEqual(
            [rollback["idempotencyKey"] + " atenea-agent-run-worker-v1.service"], calls)

        second = self._run(rollback)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(result, json.loads(second.stdout))
        self.assertEqual(calls, (self.root / "restart-calls").read_text().splitlines())

        conflict = self._run({**rollback, "authorizationId": str(uuid.uuid4())})
        self.assertNotEqual(0, conflict.returncode)
        self.assertEqual(calls, (self.root / "restart-calls").read_text().splitlines())

    def test_rollback_restart_failure_retains_resumable_exact_link_state(self):
        self.assertEqual(0, self._run().returncode)
        rollback = {
            "operation": "ROLLBACK_CODEX_UPDATE",
            "planId": self.plan_id,
            "candidateId": self.candidate_id,
            "activationId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        self.restart_scheduler.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
        self.restart_scheduler.chmod(0o700)
        failed = self._run(rollback)
        self.assertNotEqual(0, failed.returncode)
        links_after_swap = self._links()
        persisted = json.loads(
            (self.rollbacks / (rollback["idempotencyKey"] + ".json")).read_text())
        self.assertEqual("LINKS_RESTORED", persisted["result"]["state"])
        self.assertEqual("PENDING", persisted["result"]["workerServiceRestart"])

        self.restart_scheduler.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.restart_scheduler.chmod(0o700)
        retried = self._run(rollback)
        self.assertEqual(0, retried.returncode, retried.stderr)
        self.assertEqual("ROLLED_BACK", json.loads(retried.stdout)["state"])
        self.assertEqual(links_after_swap, self._links())

    def test_rollback_rejects_link_drift_without_further_change(self):
        self.assertEqual(0, self._run().returncode)
        previous = self.root / "previous"
        previous.unlink()
        previous.symlink_to("releases/" + self.previous_release.name)
        drifted = self._links()
        rollback = {
            "operation": "ROLLBACK_CODEX_UPDATE",
            "planId": self.plan_id,
            "candidateId": self.candidate_id,
            "activationId": str(uuid.uuid4()),
            "authorizationId": str(uuid.uuid4()),
            "idempotencyKey": str(uuid.uuid4()),
        }
        rejected = self._run(rollback)
        self.assertNotEqual(0, rejected.returncode)
        self.assertEqual(drifted, self._links())
        self.assertEqual([], list(self.rollbacks.iterdir()))

    def test_restart_scheduler_rejects_foreign_service_and_identity(self):
        foreign = subprocess.run(
            [str(RESTART_SCRIPT), str(uuid.uuid4()), "foreign.service"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        self.assertEqual(2, foreign.returncode)
        malformed = subprocess.run(
            [str(RESTART_SCRIPT), "not-a-uuid", "atenea-agent-run-worker-v1.service"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        self.assertEqual(2, malformed.returncode)


if __name__ == "__main__":
    unittest.main()
