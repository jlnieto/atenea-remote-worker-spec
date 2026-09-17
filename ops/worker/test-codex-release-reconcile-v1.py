#!/usr/bin/env python3

import getpass
import grp
import hashlib
import importlib.machinery
import json
import os
import pwd
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("codex-release-reconcile-v1.py")
MODULE = importlib.machinery.SourceFileLoader("codex_release_reconcile_v1", str(SCRIPT)).load_module()


class CodexReleaseReconcileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "standalone" / "releases"
        self.destination = self.root / "managed"
        self.releases = self.destination / "releases"
        self.operations = self.destination / "operations"
        self.source.mkdir(parents=True)
        self.destination.mkdir()
        self.releases.mkdir()
        self.operations.mkdir()
        self.uid = os.geteuid()
        self.gid = os.getegid()
        self.user = pwd.getpwuid(self.uid).pw_name
        self.group = grp.getgrgid(self.gid).gr_name
        for path in (self.source, self.destination, self.releases, self.operations):
            path.chmod(0o750)
        self.state = self.root / "executions.json"
        self.state.write_text(json.dumps({
            "protocol": "agent-run-worker/v1", "workerId": "ax42-01",
            "executions": {"terminal": {"status": "FAILED"}},
        }), encoding="utf-8")
        self.state.chmod(0o600)
        self.registry = self.root / "registry.json"
        self.manifest = self.root / "manifest.json"
        current = self._package("0.154.0", b"current-host", b"current-bwrap")
        candidate = self._package("0.145.0", b"candidate-host", b"candidate-bwrap")
        self.document = {
            "schemaVersion": "codex-release-reconcile-manifest-v1",
            "workerId": "ax42-01", "sourceRoot": str(self.source),
            "destinationRoot": str(self.destination), "sourceOwner": self.user,
            "destinationOwner": self.user, "destinationGroup": self.group,
            "planId": "15414500-0000-4000-8000-000000000001",
            "currentInventoryId": "15414500-0000-4000-8000-000000000002",
            "candidateInventoryId": "15414500-0000-4000-8000-000000000003",
            "releases": {"current": current, "candidate": candidate},
        }
        self._write_manifest()
        self.request = {"operation": "RECONCILE_INSTALLED_CODEX_RELEASES",
                        "idempotencyKey": str(uuid.uuid4())}

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _hash(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _package(self, version, host_content, bwrap_content):
        package = self.source / f"{version}-x86_64-unknown-linux-musl"
        for relative in MODULE.ALLOWED_DIRECTORIES:
            (package / relative).mkdir(parents=True, exist_ok=True)
        package.chmod(0o775)
        for path in package.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
        files = {
            "bin/codex": f"#!/bin/sh\nprintf 'codex-cli {version}\\n'\n".encode(),
            "bin/codex-code-mode-host": host_content,
            "codex-package.json": json.dumps(MODULE.package_json(version),
                                               separators=(",", ":")).encode(),
            "codex-path/rg": b"fixed-rg",
            "codex-resources/bwrap": bwrap_content,
            "codex-resources/zsh/bin/zsh": b"fixed-zsh",
        }
        identities = {}
        for relative, content in files.items():
            path = package / relative
            path.write_bytes(content)
            mode = 0o644 if relative == "codex-package.json" else 0o755
            path.chmod(mode)
            identities[relative] = {"sha256": self._hash(path), "mode": format(mode, "04o")}
        (package / "codex").symlink_to("bin/codex")
        release = {
            "version": version, "packageDirectory": package.name,
            "target": "x86_64-unknown-linux-musl",
            "expectedVersionOutput": f"codex-cli {version}",
            "releaseDigestSha256": "0" * 64,
            "catalogRevision": "1" * 64 if version == "0.145.0" else None,
            "files": identities,
        }
        release["releaseDigestSha256"] = MODULE.release_digest(release)
        return release

    def _write_manifest(self):
        self.manifest.write_text(json.dumps(self.document), encoding="utf-8")
        self.manifest.chmod(0o600)

    def _run(self, request=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(MODULE, "SOURCE_ROOT", self.source))
            stack.enter_context(patch.object(MODULE, "DESTINATION_ROOT", self.destination))
            stack.enter_context(patch.object(MODULE, "MANIFEST_PATH", self.manifest))
            stack.enter_context(patch.object(MODULE, "EXECUTION_STATE_PATH", self.state))
            stack.enter_context(patch.object(MODULE, "REGISTRY_PATH", self.registry))
            return MODULE.reconcile(
                request or self.request,
                authority_uid=self.uid,
                authority_gid=self.gid,
            )

    def test_bootstraps_exact_current_candidate_and_absent_previous_idempotently(self):
        first = self._run()
        second = self._run()

        self.assertEqual(first, second)
        self.assertEqual("RECONCILED", first["state"])
        self.assertEqual("0.154.0", first["currentVersion"])
        self.assertEqual("INSTALLED", first["currentInstallationState"])
        self.assertEqual("CURRENT", first["currentLinkState"])
        self.assertEqual("0.145.0", first["candidateVersion"])
        self.assertEqual("STAGED", first["candidateInstallationState"])
        self.assertEqual("NONE", first["candidateLinkState"])
        self.assertEqual("COMPATIBLE", first["candidateCompatibilityState"])
        self.assertEqual("ABSENT", first["previousState"])
        self.assertEqual("UNKNOWN", first["previousCompatibilityState"])
        self.assertTrue((self.destination / "current").is_symlink())
        self.assertFalse((self.destination / "previous").exists())
        self.assertEqual(2, len([item for item in self.releases.iterdir()
                                if item.is_dir() and not item.name.startswith(".")]))
        inventory = json.loads((self.destination / "inventory-v1.json").read_text())
        plan = json.loads((self.destination / "recovery-plan-v1.json").read_text())
        registry = json.loads(self.registry.read_text())
        self.assertEqual({"state": "ABSENT", "compatibilityState": "UNKNOWN"},
                         inventory["previous"])
        self.assertEqual("ABSENT_UNKNOWN", plan["previousState"])
        self.assertEqual([self.document["candidateInventoryId"]],
                         list(registry["candidates"]))
        self.assertEqual(1, len(list((self.destination / "reconciliations").glob("*.json"))))

    def test_rejects_unexpected_hash_package_and_non_terminal_run(self):
        candidate = self.source / self.document["releases"]["candidate"]["packageDirectory"]
        (candidate / "bin/codex-code-mode-host").write_bytes(b"tampered")
        with self.assertRaisesRegex(MODULE.ReconcileError, "does not match"):
            self._run()
        self.assertFalse((self.destination / "current").exists())

        (candidate / "bin/codex-code-mode-host").write_bytes(b"candidate-host")
        (candidate / "bin/codex-code-mode-host").chmod(0o755)
        (candidate / "unexpected").write_text("foreign", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.ReconcileError, "structure is unexpected"):
            self._run()
        (candidate / "unexpected").unlink()
        self.state.write_text(json.dumps({
            "protocol": "agent-run-worker/v1", "executions": {"active": {"status": "RUNNING"}},
        }), encoding="utf-8")
        with self.assertRaisesRegex(MODULE.ReconcileError, "zero non-terminal"):
            self._run()

    def test_rejects_request_authority_and_conflicting_current_link(self):
        with self.assertRaisesRegex(MODULE.ReconcileError, "reconcile operation"):
            self._run({**self.request, "operation": "IMPORT_ARBITRARY_RELEASE"})
        foreign = self.releases / "foreign"
        foreign.mkdir()
        (self.destination / "current").symlink_to("releases/foreign")
        with self.assertRaisesRegex(MODULE.ReconcileError, "current link conflicts"):
            self._run()


if __name__ == "__main__":
    unittest.main()
