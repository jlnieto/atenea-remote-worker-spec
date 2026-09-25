#!/usr/bin/env python3

import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
import uuid
from pathlib import Path


SCRIPT = Path(__file__).with_name("codex-release-stage-v1.py")
VERSION = "0.146.0"
CATALOG = "b" * 64


class CodexReleaseStageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.release_root = self.root / "managed"
        self.releases = self.release_root / "releases"
        self.inbox = self.release_root / "inbox"
        self.releases.mkdir(parents=True)
        self.inbox.mkdir()
        (self.release_root / "operations").mkdir()
        for directory in (
            self.release_root, self.releases, self.inbox,
            self.release_root / "operations",
        ):
            directory.chmod(0o750)
        for name in ("0.145.0-current", "0.144.0-previous"):
            release = self.releases / name
            release.mkdir()
            (release / "retained.txt").write_text(name, encoding="utf-8")
        (self.release_root / "current").symlink_to("releases/0.145.0-current")
        (self.release_root / "previous").symlink_to("releases/0.144.0-previous")
        self.plan_id = str(uuid.uuid4())
        self.candidate_id = str(uuid.uuid4())
        self.idempotency_key = str(uuid.uuid4())
        self.archive = self.inbox / f"{self.candidate_id}.tar.gz"
        self._write_archive(VERSION)
        self.registry = self.root / "registry.json"
        self._write_registry(self._digest(self.archive))

    def tearDown(self):
        self.temporary.cleanup()

    def _digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_registry(self, digest, *, plan_id=None, candidate_id=None):
        candidate_id = candidate_id or self.candidate_id
        document = {
            "schemaVersion": "codex-release-stage-v1",
            "workerId": "ax42-01",
            "candidates": {
                candidate_id: {
                    "planId": plan_id or self.plan_id,
                    "candidateId": candidate_id,
                    "codexVersion": VERSION,
                    "releaseDigestSha256": digest,
                    "catalogRevision": CATALOG,
                }
            },
        }
        self.registry.write_text(json.dumps(document), encoding="utf-8")
        self.registry.chmod(0o600)

    def _write_archive(self, schema_version, unsafe_name=None):
        generator = f"""#!/usr/bin/env python3
import json
import pathlib
import sys
output = pathlib.Path(sys.argv[1])
for name in ("app-server.schema.json", "cli.schema.json"):
    (output / name).write_text(json.dumps({{"type":"object","x-codex-version":"{schema_version}"}}))
""".encode()
        with tarfile.open(self.archive, "w:gz") as bundle:
            info = tarfile.TarInfo("bin/generate-schemas")
            info.mode = 0o755
            info.size = len(generator)
            bundle.addfile(info, io.BytesIO(generator))
            marker = b"synthetic verified release"
            marker_info = tarfile.TarInfo(unsafe_name or "release.txt")
            marker_info.mode = 0o644
            marker_info.size = len(marker)
            bundle.addfile(marker_info, io.BytesIO(marker))
        self.archive.chmod(0o600)

    def request(self, **changes):
        request = {
            "operation": "STAGE_CODEX_UPDATE",
            "planId": self.plan_id,
            "candidateId": self.candidate_id,
            "idempotencyKey": self.idempotency_key,
        }
        request.update(changes)
        return request

    def run_stage(self, request=None):
        return subprocess.run(
            [str(SCRIPT), "--registry", str(self.registry),
             "--release-root", str(self.release_root),
             "--registry-owner-uid", str(os.geteuid())],
            input=json.dumps(request or self.request()),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )

    def test_stages_verified_release_generates_schemas_and_preserves_links(self):
        current = os.readlink(self.release_root / "current")
        previous = os.readlink(self.release_root / "previous")

        completed = self.run_stage()

        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("codex-update-stage-v1", result["schemaVersion"])
        self.assertEqual("STAGED", result["state"])
        self.assertEqual(VERSION, result["codexVersion"])
        self.assertEqual("PASS", result["releaseVerification"])
        self.assertEqual("PASS", result["schemaGeneration"])
        self.assertEqual("PASS", result["retention"])
        self.assertFalse(result["linksChanged"])
        self.assertFalse(result["valuesExposed"])
        self.assertEqual(current, os.readlink(self.release_root / "current"))
        self.assertEqual(previous, os.readlink(self.release_root / "previous"))
        staged = [path for path in self.releases.iterdir() if path.name.startswith(VERSION)]
        self.assertEqual(1, len(staged))
        self.assertTrue((staged[0] / "generated-schemas" / "app-server.schema.json").is_file())
        self.assertTrue((self.releases / "0.145.0-current" / "retained.txt").is_file())
        self.assertTrue((self.releases / "0.144.0-previous" / "retained.txt").is_file())

        repeated = self.run_stage()
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        self.assertEqual(completed.stdout, repeated.stdout)
        self.assertEqual(1, len(list((self.release_root / "operations").iterdir())))

        second_request = self.request(idempotencyKey=str(uuid.uuid4()))
        second = self.run_stage(second_request)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(result["releaseManifestSha256"],
                         json.loads(second.stdout)["releaseManifestSha256"])
        self.assertEqual(1, len(staged))

    def test_rejects_extra_authority_foreign_candidate_and_digest_mismatch(self):
        for request in (
            self.request(releaseUrl="https://foreign.invalid/release"),
            self.request(candidateId=str(uuid.uuid4())),
        ):
            completed = self.run_stage(request)
            self.assertEqual(2, completed.returncode)
        self._write_registry("f" * 64)
        completed = self.run_stage()
        self.assertEqual(2, completed.returncode)
        self.assertFalse(any(path.name.startswith(VERSION) for path in self.releases.iterdir()))
        self.assertEqual(2, len(list(self.releases.iterdir())))

    def test_rejects_unsafe_archive_member_without_escape_or_link_change(self):
        self._write_archive(VERSION, unsafe_name="../escaped.txt")
        self._write_registry(self._digest(self.archive))
        current = os.readlink(self.release_root / "current")
        previous = os.readlink(self.release_root / "previous")

        completed = self.run_stage()

        self.assertEqual(2, completed.returncode)
        self.assertFalse((self.release_root / "escaped.txt").exists())
        self.assertFalse((self.root / "escaped.txt").exists())
        self.assertEqual(current, os.readlink(self.release_root / "current"))
        self.assertEqual(previous, os.readlink(self.release_root / "previous"))

    def test_rejects_schema_for_different_version_and_removes_temporary_release(self):
        self._write_archive("9.9.9")
        self._write_registry(self._digest(self.archive))

        completed = self.run_stage()

        self.assertEqual(2, completed.returncode)
        self.assertFalse(any(path.name.startswith(VERSION) for path in self.releases.iterdir()))
        self.assertFalse(any(path.name.startswith(".stage-") for path in self.releases.iterdir()))


if __name__ == "__main__":
    unittest.main()
