#!/usr/bin/env python3
"""Real journal/filesystem tests in private fixtures; no live Docker/PROD effects."""
import copy
import hashlib
import importlib.util
import json
import os
import stat
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


r = module("retention_release", "release-control-v1.py")
ret = module("retention", "release-retention-v1.py")


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="retention-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "plans").mkdir(mode=0o700)
        self.apk = self.root / "android"
        self.apk.mkdir(mode=0o755)
        (self.apk / "releases").mkdir(mode=0o755)
        self.images, self.used, self.commands = {}, set(), []
        self.app = SimpleNamespace(observe_current=Mock())
        self.android = SimpleNamespace(APK_ROOT=self.apk, inspect=Mock())
        self.controller = r.Controller(self.root, None, {"APP_PROD": self.app, "ANDROID_STABLE": self.android})
        self.retention = ret.Retention(r, self.controller)
        self.controller.retention = self.retention
        self.free_bytes = 30 * ret.GIB
        self.retention.free = lambda: self.free_bytes

        def trusted(path, mode=None):
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                    or info.st_mode & 0o022 or mode is not None and stat.S_IMODE(info.st_mode) != mode):
                raise r.Rejected("INSTALLED_AUTHORITY_INVALID")
            return path

        def trusted_directory(path, mode):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
                raise r.Rejected("INSTALLED_AUTHORITY_INVALID")

        for name, value in (("trusted", trusted), ("trusted_directory", trusted_directory), ("command", self.command)):
            p = patch.object(r, name, side_effect=value)
            p.start()
            self.addCleanup(p.stop)
        self.apps = [self.plan("APP_PROD", n) for n in range(1, 6)]
        self.apks = [self.plan("ANDROID_STABLE", n) for n in range(101, 106)]
        self.app.observe_current.return_value = {"sourceCommit": self.apps[-1]["sourceCommit"],
            "imageId": self.image_id(5), "healthy": True}
        current = self.receipt(self.apks[-1])
        self.android.inspect.return_value = copy.deepcopy(current)
        r.save(self.apk / "manifest.json", current["manifest"], mode=0o644)
        self.metadata = self.protected()

    def image_id(self, n):
        return "sha256:" + format(n, "064x")

    def command(self, argv, **kwargs):
        self.commands.append(argv)
        if argv[1:3] == ["container", "ls"]:
            return ("\n".join(format(index+1, "064x") for index in range(len(self.used)))).encode()
        if argv[1:3] == ["container", "inspect"]:
            return json.dumps([{"Id": item, "Image": image} for item, image in zip(argv[3:], sorted(self.used))]).encode()
        if argv[1:3] == ["image", "ls"]:
            return "\n".join(self.images).encode()
        if argv[1:3] == ["image", "inspect"]:
            return json.dumps([self.images[argv[3]]]).encode()
        if argv[1:3] == ["image", "rm"]:
            self.assertEqual(4, len(argv))
            self.assertNotIn(argv[3], self.used)
            del self.images[argv[3]]
            return b"removed"
        self.fail("Unexpected external authority: " + repr(argv))

    def plan(self, target, n, state="SUCCEEDED"):
        directory = self.root / "plans" / str(uuid.uuid4())
        directory.mkdir(mode=0o700)
        payload = ret.PAYLOADS[target]
        for name in (payload, "artifact.zip"):
            (directory / name).write_bytes((name + str(n)).encode())
            (directory / name).chmod(0o600)
        source = format(n, "040x")
        finished = int(time.time()) - (200 - n) * 100
        artifact = {"payloadSha256": r.file_digest(directory / payload), "archiveSha256": r.file_digest(directory / "artifact.zip"),
                    "versionCode": n if target == "ANDROID_STABLE" else None}
        record = {"protocol": r.PROTOCOL, "planId": directory.name, "target": target,
            "sourceCommit": source, "artifact": artifact, "artifactSha256": artifact["payloadSha256"],
            "expiresAt": finished - 1000, "createdAt": finished - 2000, "finishedAt": finished,
            "operationId": str(uuid.uuid4()), "errorCode": None, "state": state,
            "predecessor": {"imageId": self.image_id(n-1), "sourceCommit": format(n-1, "040x"), "versionCode": n-1},
            "effectiveSourceCommit": source}
        record["planSha256"] = r.digest({key: record[key] for key in
            ("protocol", "planId", "target", "sourceCommit", "artifact", "predecessor", "expiresAt")})
        receipt = {"sourceCommit": source}
        if target == "APP_PROD":
            image_id = self.image_id(n)
            receipt["imageId"] = image_id
            self.images[image_id] = {"Id": image_id, "Config": {"Labels": {"org.opencontainers.image.revision": source}},
                "RepoTags": ["atenea-app:" + source], "RepoDigests": [], "Size": 1000}
            r.save(directory / "image.json", {"imageId": image_id})
        else:
            release = self.apk / "releases" / str(n)
            release.mkdir(mode=0o755)
            binary = release / "atenea-debug.apk"
            binary.write_bytes(("signed" + str(n)).encode())
            binary.chmod(0o644)
            receipt.update(versionCode=n, manifest={"sourceCommit": source, "versionCode": n,
                "sha256": r.file_digest(binary), "versionName": "0.5." + str(n),
                "apkUrl": "https://atenea.yudri.es/apk/" + "s"*24 + "/android/releases/" + str(n) + "/atenea-debug.apk"})
            r.save(release / "manifest.json", receipt["manifest"], mode=0o644)
            record["resultSha256"] = receipt["manifest"]["sha256"]
            (directory / "signed.apk").write_bytes(binary.read_bytes())
            (directory / "signed.apk").chmod(0o600)
            r.save(directory / "signed.json", {"sha256": receipt["manifest"]["sha256"]})
        r.save(directory / "operation.json", record)
        if state == "SUCCEEDED":
            r.save(directory / "receipt.json", receipt)
        return record

    def receipt(self, record):
        return json.loads((self.controller.path(record["planId"]) / "receipt.json").read_bytes())

    def protected(self):
        names = {"operation.json", "receipt.json", "manifest.json", "image.json", "signed.json"}
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*.json") if p.name in names}

    def test_inventory_is_read_only_and_retains_running_plus_two_previous(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        observed = self.retention.inventory()
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertEqual({self.image_id(n) for n in (3, 4, 5)}, set(observed["imagePins"]))
        self.assertEqual({103, 104, 105}, set(observed["apkPins"]))
        self.assertEqual(2, sum(item["kind"] == "IMAGE" for item in observed["actions"]))
        self.assertFalse(any(item["kind"] == "APK" for item in observed["actions"]))

    def test_collection_is_exact_and_preserves_history_and_unregistered_resources(self):
        foreign = self.image_id(999)
        self.images[foreign] = {"Id": foreign}
        protected = self.root / "backups"
        protected.mkdir()
        (protected / "production.dump").write_bytes(b"never collect")
        unknown = self.controller.path(self.apps[0]["planId"]) / "foreign.tar"
        unknown.write_bytes(b"not an allowlisted payload")
        first = self.controller.maintain("OPERATOR")
        self.assertEqual("SUCCEEDED", first["state"])
        self.assertEqual(self.metadata, self.protected())
        self.assertTrue(unknown.exists())
        self.assertEqual(b"never collect", (protected / "production.dump").read_bytes())
        self.assertIn(foreign, self.images)
        self.assertEqual({foreign, *(self.image_id(n) for n in (3, 4, 5))}, set(self.images))
        self.assertEqual("SUCCEEDED", self.controller.maintain("OPERATOR")["state"])
        self.assertEqual(2, sum(argv[1:3] == ["image", "rm"] for argv in self.commands))
        self.assertFalse(any("prune" in argv or "--force" in argv or "volume" in argv for argv in self.commands))

    def test_stopped_container_and_foreign_alias_pin_old_images(self):
        self.used.add(self.image_id(1))  # container snapshot includes --all, not only running.
        self.images[self.image_id(2)]["RepoTags"].append("another-project:protected")
        self.assertFalse(any(item["kind"] == "IMAGE" for item in self.retention.inventory()["actions"]))

    def test_current_health_receipt_and_image_identity_are_required(self):
        self.app.observe_current.return_value["healthy"] = False
        with self.assertRaises(r.Rejected):
            self.retention.inventory()
        self.app.observe_current.return_value["healthy"] = True
        self.images[self.image_id(1)]["Config"]["Labels"]["org.opencontainers.image.revision"] = "f"*40
        with self.assertRaises(r.Rejected):
            self.controller.maintain("OPERATOR")
        self.assertFalse(any(argv[1:3] == ["image", "rm"] for argv in self.commands))

    def test_active_or_unknown_rollback_blocks_collection(self):
        for state in ("PREPARING", "ACCEPTED", "APPLYING", "ROLLING_BACK", "ROLLBACK_FAILED"):
            record = self.apps[0]
            record["state"] = state
            r.save(self.controller.path(record["planId"]) / "operation.json", record)
            with self.subTest(state=state), self.assertRaises(r.Rejected) as error:
                self.retention.inventory()
            self.assertEqual("RETENTION_BUSY", error.exception.code)

    def test_pending_ready_plan_pins_candidate_and_rollback_images(self):
        record = self.apps[0]
        record.update(state="READY", operationId=None, expiresAt=int(time.time())+600)
        record["predecessor"]["imageId"] = self.image_id(2)
        record["planSha256"] = r.digest({key: record[key] for key in
            ("protocol", "planId", "target", "sourceCommit", "artifact", "predecessor", "expiresAt")})
        r.save(self.controller.path(record["planId"]) / "operation.json", record)
        observed = self.retention.inventory()
        self.assertIn(self.image_id(1), observed["imagePins"])
        self.assertIn(self.image_id(2), observed["imagePins"])

    def test_failure_grace_and_no_adoption_of_unknown_payload(self):
        record = self.apps[0]
        record.update(state="BLOCKED", finishedAt=int(time.time()), errorCode="IMAGE_IMPORT_FAILED")
        path = self.controller.path(record["planId"])
        r.save(path / "operation.json", record)
        self.controller.maintain("OPERATOR")
        self.assertTrue((path / "image.tar").exists())
        record["finishedAt"] -= 8*86400
        r.save(path / "operation.json", record)
        self.controller.maintain("OPERATOR")
        self.assertFalse((path / "image.tar").exists())
        self.assertTrue((path / "operation.json").exists())

    def test_apk_grace_starts_at_enrollment_and_resets_when_protected(self):
        self.controller.maintain("OPERATOR")
        for n in (101, 102):
            self.assertTrue((self.apk / "releases" / str(n) / "atenea-debug.apk").exists())
        with patch.object(ret.time, "time", return_value=time.time()+8*86400):
            result = self.controller.maintain("OPERATOR")
        self.assertEqual(2, sum(a["kind"] == "APK" and a["state"] == "DELETED" for a in result["actions"]))
        for n in (103, 104, 105):
            self.assertTrue((self.apk / "releases" / str(n) / "atenea-debug.apk").exists())
        self.assertEqual(self.metadata, self.protected())

    def test_hash_symlink_and_hardlink_drift_fail_before_deleting_anything(self):
        path = self.controller.path(self.apps[0]["planId"]) / "image.tar"
        original = path.read_bytes()
        path.write_bytes(b"modified")
        with self.assertRaises(r.Rejected):
            self.controller.maintain("OPERATOR")
        self.assertTrue(path.exists())
        path.write_bytes(original)
        linked = path.with_name("linked")
        os.link(path, linked)
        with self.assertRaises(r.Rejected):
            self.controller.maintain("OPERATOR")
        linked.unlink()
        path.unlink()
        path.symlink_to(self.apk / "manifest.json")
        with self.assertRaises(r.Rejected):
            self.controller.maintain("OPERATOR")
        self.assertEqual(self.metadata, self.protected())

    def test_crash_after_unlink_replays_durable_intent_not_another_resource(self):
        real_save = r.save
        crashed = False

        def interrupt(path, value, **kwargs):
            nonlocal crashed
            if path.parent.name == "runs" and any(a["state"] == "DELETED" for a in value.get("actions", [])) and not crashed:
                crashed = True
                raise KeyboardInterrupt("fixture crash after unlink, before acknowledgement")
            return real_save(path, value, **kwargs)

        with patch.object(r, "save", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            self.controller.maintain("OPERATOR")
        active = json.loads((self.retention.root / "active.json").read_bytes())["runId"]
        first = json.loads((self.retention.root / "runs" / (active+".json")).read_bytes())
        self.assertEqual("RUNNING", first["state"])
        final = self.controller.maintain("OPERATOR")
        self.assertEqual(active, final["runId"])
        self.assertEqual("SUCCEEDED", final["state"])
        self.assertEqual(self.metadata, self.protected())

    def test_capacity_failure_exposes_missing_bytes_without_any_publication(self):
        self.free_bytes = ret.GIB
        record = self.plan("APP_PROD", 6, state="PREPARING")
        record["operationId"] = None
        r.save(self.controller.path(record["planId"]) / "operation.json", record)
        with self.assertRaises(r.Rejected) as error:
            self.retention.capacity(record, ret.GIB)
        self.assertEqual("RELEASE_STORAGE_INSUFFICIENT", error.exception.code)
        value = self.controller.dispatch({"operation": "OBSERVE_STORAGE", "planId": record["planId"]})
        self.assertEqual("INSUFFICIENT_SPACE", value["phase"])
        self.assertEqual(value["requiredBytes"] - self.free_bytes, value["missingBytes"])
        self.assertNotIn("/", json.dumps(value).replace(ret.STORAGE_PROTOCOL, ""))
        self.assertTrue((self.controller.path(record["planId"]) / "image.tar").exists())

    def test_concurrent_lifecycle_and_foreign_observation_cannot_start_cleanup(self):
        acquired, release = threading.Event(), threading.Event()

        def active():
            with self.controller.lifecycle_lock:
                acquired.set()
                release.wait(2)

        thread = threading.Thread(target=active)
        thread.start()
        try:
            self.assertTrue(acquired.wait(1))
            with self.assertRaises(r.Rejected) as error:
                self.controller.maintain("NIGHTLY")
            self.assertEqual("RETENTION_BUSY", error.exception.code)
        finally:
            release.set()
            thread.join()
        with self.assertRaises(r.Rejected):
            self.controller.dispatch({"operation": "OBSERVE_STORAGE", "planId": self.apps[0]["planId"], "path": "/tmp"})
        self.assertFalse((self.retention.root / "active.json").exists())

    def test_expired_ready_closes_without_execution_and_keeps_failure_grace(self):
        record=self.apps[0]
        record.update(state="READY",operationId=None)
        path=self.controller.path(record["planId"])/"operation.json"
        r.save(path,record)
        self.controller.maintain("OPERATOR")
        closed=self.controller.read(record["planId"])
        self.assertEqual("BLOCKED",closed["state"]);self.assertEqual("PLAN_EXPIRED",closed["errorCode"])
        self.assertEqual(record["planSha256"],closed["planSha256"]);self.assertIsNone(closed["operationId"])
        self.assertTrue((path.parent/"image.tar").exists())

    def test_mismatched_storage_projection_is_never_exposed(self):
        record=self.apps[0]
        value=self.retention.storage(record,"CHECKING_SPACE")
        value["path"]="/must/not/leave/publisher"
        r.save(self.controller.path(record["planId"])/"storage.json",value)
        with self.assertRaises(r.Rejected):
            self.controller.dispatch({"operation":"OBSERVE_STORAGE","planId":record["planId"]})

    def test_ambiguous_image_deletion_is_observed_not_repeated_or_forced(self):
        original=self.command
        def command(argv,**kwargs):
            value=original(argv,**kwargs)
            if argv[1:3]==["image","rm"]:raise r.Rejected("RELEASE_COMMAND_FAILED")
            return value
        with patch.object(r,"command",side_effect=command):
            result=self.controller.maintain("OPERATOR")
        self.assertEqual("SUCCEEDED",result["state"])
        self.assertEqual(2,sum(argv[1:3]==["image","rm"] for argv in self.commands))

    def test_unresolved_deletion_failure_is_durable_attention_not_forced_next_time(self):
        original=self.command
        def command(argv,**kwargs):
            if argv[1:3]==["image","rm"]:raise r.Rejected("RELEASE_COMMAND_FAILED")
            return original(argv,**kwargs)
        with patch.object(r,"command",side_effect=command),self.assertRaises(r.Rejected):
            self.controller.maintain("OPERATOR")
        with self.assertRaises(r.Rejected) as error:self.controller.maintain("OPERATOR")
        self.assertEqual("RETENTION_REQUIRES_INSPECTION",error.exception.code)

    def test_read_only_storage_contract_is_draft_2020_12_and_closed(self):
        import jsonschema
        schema=json.loads((Path(__file__).parents[2]/"runtime-contract/release-control-v1.storage.schema.json").read_bytes())
        jsonschema.Draft202012Validator.check_schema(schema)
        value=self.retention.storage(self.apps[0],"CHECKING_SPACE")
        jsonschema.validate(value,schema)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate({**value,"command":"foreign"},schema)

    def test_missing_recovery_image_or_apk_cannot_erase_its_remaining_archive(self):
        del self.images[self.image_id(3)]
        with self.assertRaises(r.Rejected) as error:self.controller.maintain("OPERATOR")
        self.assertEqual("RETENTION_RECOVERY_CONTENT_MISSING",error.exception.code)
        self.assertTrue((self.controller.path(self.apps[2]["planId"])/"image.tar").exists())

    def test_missing_protected_apk_cannot_expire_its_signed_recovery_copy(self):
        (self.apk/"releases/103/atenea-debug.apk").unlink()
        with self.assertRaises(r.Rejected) as error:self.controller.maintain("OPERATOR")
        self.assertEqual("RETENTION_RECOVERY_CONTENT_MISSING",error.exception.code)
        self.assertTrue((self.controller.path(self.apks[2]["planId"])/"signed.apk").exists())


if __name__ == "__main__":
    unittest.main()
