#!/usr/bin/env python3
"""Focused, isolated tests for the exact reconciled release activation."""

import importlib.util
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("codex-release-recovery-activate-v1.py")
spec = importlib.util.spec_from_file_location("recovery_activate", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MANIFEST = json.loads(Path(__file__).with_name("codex-release-reconcile-v1.json").read_text())


class RecoveryActivationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "managed"
        self.root.mkdir()
        for directory in ("releases", "reconciliations", "activations", "recovery-activations"):
            (self.root / directory).mkdir()
        self.registry = Path(self.temporary.name) / "registry.json"
        self.runner = Path(self.temporary.name) / "runner.py"
        self.runner.write_text(
            'CODEX = "/srv/atenea/worker/codex-releases-v1/current/bin/codex"\n')
        self.key = str(uuid.uuid4())
        self.current_name = "0.154.0-" + module.CURRENT_DIGEST[:16]
        self.candidate_name = "0.145.0-" + module.CANDIDATE_DIGEST[:16]
        for name, version in ((self.current_name, "0.154.0"),
                              (self.candidate_name, "0.145.0")):
            release = self.root / "releases" / name
            release.mkdir()
            (release / "codex-package.json").write_text(
                json.dumps(module.reconcile.package_json(version)))
        (self.root / "current").symlink_to("releases/" + self.current_name)
        self.inventory = {
            "schemaVersion": "codex-release-inventory-v1", "workerId": "ax42-01",
            "current": {"inventoryId": module.CURRENT_ID, "codexVersion": "0.154.0",
                        "releaseDigestSha256": module.CURRENT_DIGEST,
                        "installationState": "INSTALLED", "linkState": "CURRENT",
                        "compatibilityState": "UNKNOWN", "catalogRevision": None},
            "candidate": {"inventoryId": module.CANDIDATE_ID, "codexVersion": "0.145.0",
                          "releaseDigestSha256": module.CANDIDATE_DIGEST,
                          "installationState": "STAGED", "linkState": "NONE",
                          "compatibilityState": "COMPATIBLE",
                          "catalogRevision": module.CATALOG_REVISION},
            "previous": {"state": "ABSENT", "compatibilityState": "UNKNOWN"}}
        self.plan = {
            "schemaVersion": "codex-release-recovery-plan-v1", "workerId": "ax42-01",
            "planId": module.PLAN_ID, "state": "READY",
            "currentInventoryId": module.CURRENT_ID,
            "candidateInventoryId": module.CANDIDATE_ID,
            "previousState": "ABSENT_UNKNOWN", "activationTargetVersion": "0.145.0"}
        self.registry_value = {
            "schemaVersion": "codex-release-stage-v1", "workerId": "ax42-01",
            "candidates": {module.CANDIDATE_ID: {
                "planId": module.PLAN_ID, "candidateId": module.CANDIDATE_ID,
                "codexVersion": "0.145.0",
                "releaseDigestSha256": module.CANDIDATE_DIGEST,
                "catalogRevision": module.CATALOG_REVISION}}}
        self._write(self.root / "inventory-v1.json", self.inventory)
        self._write(self.root / "recovery-plan-v1.json", self.plan)
        self._write(self.registry, self.registry_value)
        self.reconciliation = {
            "schemaVersion": "codex-release-reconcile-v1", "workerId": "ax42-01",
            "operation": "RECONCILE_INSTALLED_CODEX_RELEASES",
            "idempotencyKey": module.RECONCILE_KEY, "state": "RECONCILED",
            "planId": module.PLAN_ID, "currentInventoryId": module.CURRENT_ID,
            "candidateInventoryId": module.CANDIDATE_ID,
            "currentReleaseDigestSha256": module.CURRENT_DIGEST,
            "candidateReleaseDigestSha256": module.CANDIDATE_DIGEST,
            "candidateCatalogRevision": module.CATALOG_REVISION,
            "previousState": "ABSENT", "previousCompatibilityState": "UNKNOWN",
            "structureVerification": "PASS", "permissionVerification": "PASS",
            "metadataVerification": "PASS", "versionVerification": "PASS",
            "hashVerification": "PASS", "zeroNonTerminalRuns": "PASS",
            "valuesExposed": False,
            "currentLinkFingerprint": module.reconcile.link_fingerprint(
                self.root / "current", "releases/" + self.current_name),
            "inventorySha256": self._digest(self.inventory),
            "planSha256": self._digest(self.plan),
            "registrySha256": self._digest(self.registry_value)}
        self._write(self.root / "reconciliations" / (module.RECONCILE_KEY + ".json"),
                    {"requestFingerprint": self._digest({
                        "operation": "RECONCILE_INSTALLED_CODEX_RELEASES",
                        "idempotencyKey": module.RECONCILE_KEY}),
                     "result": self.reconciliation})
        self.patchers = [
            patch.object(module, "ROOT", self.root),
            patch.object(module, "REGISTRY", self.registry),
            patch.object(module, "RUNNER", self.runner),
            patch.object(module.reconcile, "read_manifest", return_value=MANIFEST),
            patch.object(module.reconcile, "owned_regular"),
            patch.object(module.reconcile, "owned_directory"),
            patch.object(module.reconcile, "verify_managed_release"),
            patch.object(module.reconcile, "validate_zero_non_terminal"),
            patch.object(module.reconcile, "persist_json", side_effect=self._persist),
            patch.object(module, "fixed_probe"),
            patch.object(module, "schedule"),
            patch.object(module, "restart_and_wait"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _digest(value):
        return module.reconcile.digest_bytes(module.reconcile.canonical_bytes(value))

    @staticmethod
    def _write(path, value):
        path.write_bytes(module.reconcile.canonical_bytes(value))

    def _persist(self, path, value, _mode, _uid, _gid):
        self._write(path, value)

    def _prepare(self):
        return module.prepare({"operation": module.OPERATION, "idempotencyKey": self.key})

    def test_exact_bootstrap_creates_previous_and_persists_final_inventory(self):
        self.assertEqual("PENDING", self._prepare()["state"])
        result = module.execute(self.key)
        self.assertEqual("ACTIVATED", result["state"])
        self.assertEqual("releases/" + self.candidate_name,
                         os.readlink(self.root / "current"))
        self.assertEqual("releases/" + self.current_name,
                         os.readlink(self.root / "previous"))
        final_inventory = module.read_json(self.root / "inventory-v1.json")
        self.assertEqual("CURRENT", final_inventory["current"]["linkState"])
        self.assertEqual("0.145.0", final_inventory["current"]["codexVersion"])
        self.assertEqual("PREVIOUS", final_inventory["previous"]["linkState"])
        self.assertEqual("0.154.0", final_inventory["previous"]["codexVersion"])
        self.assertEqual("ACTIVATED", module.read_json(self.root / "recovery-plan-v1.json")["state"])
        self.assertEqual(result, module.execute(self.key))
        self.assertEqual("ACTIVATED", module.read_operation(self.key)["state"])

    def _assert_restart_failure_restores(self, failure):
        self._prepare()
        with patch.object(module, "restart_and_wait", side_effect=[
                module.RecoveryError(failure), None]):
            result = module.execute(self.key)
        self.assertEqual("RESTORED", result["state"])
        self.assertEqual("PASS", result["automaticRestore"])
        self.assertEqual("releases/" + self.current_name,
                         os.readlink(self.root / "current"))
        self.assertFalse((self.root / "previous").exists())
        self.assertEqual(self.inventory, module.read_json(self.root / "inventory-v1.json"))
        self.assertEqual(self.plan, module.read_json(self.root / "recovery-plan-v1.json"))

    def test_health_failure_restores_exact_bootstrap(self):
        self._assert_restart_failure_restores("health failed")

    def test_catalog_failure_restores_exact_bootstrap(self):
        self._assert_restart_failure_restores("catalog failed")

    def test_link_postcondition_failure_restores_previous_absence(self):
        self._prepare()
        calls = 0
        def conflicting_restart(_version):
            nonlocal calls
            calls += 1
            if calls == 1:
                module.replace_link(self.root / "current", "releases/" + self.current_name)
        with patch.object(module, "restart_and_wait", side_effect=conflicting_restart):
            result = module.execute(self.key)
        self.assertEqual("RESTORED", result["state"])
        self.assertEqual("releases/" + self.current_name,
                         os.readlink(self.root / "current"))
        self.assertFalse((self.root / "previous").exists())
        self.assertEqual(self.inventory, module.read_json(self.root / "inventory-v1.json"))

    def test_unexpected_bootstrap_inventory_registry_or_link_is_rejected(self):
        for target, mutation in (
                ("inventory-v1.json", lambda value: value["candidate"].update(codexVersion="0.146.0")),
                ("recovery-plan-v1.json", lambda value: value.update(previousState="PRESENT")),
                ("registry", lambda value: value["candidates"][module.CANDIDATE_ID].update(
                    catalogRevision="0" * 64)),
        ):
            path = self.registry if target == "registry" else self.root / target
            original = path.read_bytes()
            value = json.loads(original)
            mutation(value)
            self._write(path, value)
            with self.assertRaises(module.RecoveryError):
                self._prepare()
            path.write_bytes(original)
        (self.root / "previous").symlink_to("releases/" + self.current_name)
        with self.assertRaises(module.RecoveryError):
            self._prepare()
        self.assertFalse(module.operation_path(self.key).exists())

    def test_runner_must_use_only_managed_current(self):
        self.runner.write_text('CODEX = "/home/jose/.codex/packages/standalone/current/bin/codex"\n')
        with self.assertRaisesRegex(module.RecoveryError, "runner"):
            self._prepare()
        self.assertFalse(module.operation_path(self.key).exists())

    def test_request_never_accepts_caller_versions_paths_or_commands(self):
        request = {"operation": module.OPERATION, "idempotencyKey": self.key}
        self.assertEqual(request, module.exact_request(request))
        for extra in ({"version": "0.145.0"}, {"path": "/tmp/foreign"},
                      {"command": "codex exec"}, {"symlink": "previous"}):
            with self.assertRaises(module.RecoveryError):
                module.exact_request({**request, **extra})

    def test_managed_package_hash_rejection_never_creates_operation(self):
        with patch.object(module.reconcile, "verify_managed_release",
                          side_effect=module.reconcile.ReconcileError("hash differs")):
            with self.assertRaisesRegex(module.reconcile.ReconcileError, "hash differs"):
                self._prepare()
        self.assertFalse(module.operation_path(self.key).exists())
        self.assertEqual("releases/" + self.current_name,
                         os.readlink(self.root / "current"))


if __name__ == "__main__":
    unittest.main()
