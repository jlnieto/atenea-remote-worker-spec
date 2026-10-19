#!/usr/bin/env python3
"""Closed publisher-owned retention. No caller paths, versions or delete commands.

The release journal is the authority, not Docker tags, directory age or an ls.
Only binary content expires; original plans, receipts and manifests are immutable.
This module is loaded by the root publisher, under its lifecycle/execution locks.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid

PROTOCOL = "atenea-release-retention/v1"
STORAGE_PROTOCOL = "atenea-release-storage/v1"
GIB = 1024**3
POLICY = {"protocol": PROTOCOL, "revision": 1, "backendPrevious": 2,
          "androidPrevious": 2, "androidGraceSeconds": 7 * 86400,
          "failedGraceSeconds": 7 * 86400, "minimumFreeBytes": 20 * GIB,
          "reserveBytes": 2 * GIB, "maximumPayloadBytes": 6 * GIB,
          "maximumExpandedImageBytes": 6 * GIB}
PHASES = {"CHECKING_SPACE", "RECLAIMING", "SPACE_READY", "DOWNLOADING", "EXTRACTING",
          "STAGING", "READY", "INSUFFICIENT_SPACE", "ATTENTION"}
PAYLOADS = {"APP_PROD": "image.tar", "ANDROID_STABLE": "app-unsigned.apk"}
ACTIVE = {"PREPARING", "ACCEPTED", "APPLYING", "ROLLING_BACK", "ROLLBACK_FAILED"}


class Retention:
    def __init__(self, release, controller):
        self.r, self.controller = release, controller
        self.root = controller.root / "retention"

    def reject(self, code="RETENTION_EVIDENCE_MISMATCH"):
        raise self.r.Rejected(code)

    def read(self, path, mode=0o600, limit=262144):
        self.r.trusted(path, mode)
        if path.stat().st_size > limit:
            self.reject("RETENTION_BOUND_EXCEEDED")
        return json.loads(path.read_bytes())

    def plans(self):
        self.r.trusted_directory(self.controller.root / "plans", 0o700)
        entries = list((self.controller.root / "plans").iterdir())
        if len(entries) > 2000:
            self.reject("RETENTION_BOUND_EXCEEDED")
        result = []
        for directory in sorted(entries):
            self.r.identity(directory.name)
            self.r.trusted_directory(directory, 0o700)
            if not (directory / "operation.json").exists():
                # E.g. AX42's baseline: not an executable plan and never collected.
                continue
            record = self.read(directory / "operation.json")
            if (record.get("protocol") != self.r.PROTOCOL or record.get("planId") != directory.name
                    or record.get("target") not in self.r.TARGETS
                    or not self.r.HEX.fullmatch(record.get("sourceCommit", ""))
                    or record.get("state") not in self.r.TERMINAL | {"PREPARING", "READY", "ACCEPTED", "APPLYING", "ROLLING_BACK"}):
                self.reject()
            if record.get("planSha256") is not None:
                expected = self.r.digest({key: record[key] for key in
                    ("protocol", "planId", "target", "sourceCommit", "artifact", "predecessor", "expiresAt")})
                if record["planSha256"] != expected:
                    self.reject()
            result.append(record)
        return result

    def rescue_pins(self):
        directory = self.controller.root / "rescue"
        pins = set()
        if directory.exists():
            self.r.trusted_directory(directory, 0o700)
            paths = list(directory.iterdir())
            if len(paths) > 1000:
                self.reject("RETENTION_BOUND_EXCEEDED")
            for path in paths:
                self.r.identity(path.stem)
                if path.suffix != ".json":
                    self.reject()
                record = self.read(path)
                if record.get("state") in {"ACCEPTED", "APPLYING", "ATTENTION"}:
                    self.reject("RETENTION_BUSY")
                if record.get("state") == "READY" and record.get("expiresAt", 0) > int(time.time()):
                    pins.add(record["predecessor"]["imageId"])
        return pins

    def docker_snapshot(self):
        r = self.r
        raw = r.command(["/usr/bin/docker", "container", "ls", "--all", "--quiet", "--no-trunc"])
        ids = raw.decode().split()
        if len(ids) > 2000 or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in ids):
            self.reject("RETENTION_BOUND_EXCEEDED")
        used = set()
        for offset in range(0, len(ids), 100):
            values = json.loads(r.command(["/usr/bin/docker", "container", "inspect", *ids[offset:offset+100]]))
            if {item["Id"] for item in values} != set(ids[offset:offset+100]):
                self.reject()
            used.update(item["Image"] for item in values)
        images = r.command(["/usr/bin/docker", "image", "ls", "--all", "--quiet", "--no-trunc"]).decode().split()
        if len(images) > 10000 or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", item) for item in images):
            self.reject("RETENTION_BOUND_EXCEEDED")
        return used, set(images)

    def success(self, record):
        if record["state"] != "SUCCEEDED" or record["target"] not in PAYLOADS:
            return None
        receipt = self.read(self.controller.path(record["planId"]) / "receipt.json")
        if (record.get("errorCode") is not None or not record.get("planSha256")
                or receipt.get("sourceCommit") != record["sourceCommit"]
                or record.get("effectiveSourceCommit") != record["sourceCommit"]
                or not isinstance(record.get("finishedAt"), int) or isinstance(record["finishedAt"], bool)
                or not 0 < record["finishedAt"] <= int(time.time()) + 5):
            self.reject()
        self.r.identity(record.get("operationId"))
        if record["target"] == "APP_PROD":
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt.get("imageId", "")):
                self.reject()
        elif (receipt.get("versionCode") != record["artifact"].get("versionCode")
                or receipt.get("manifest", {}).get("sha256") != record.get("resultSha256")
                or not self.r.DIGEST.fullmatch(record.get("resultSha256", ""))):
            self.reject()
        return receipt

    def expire(self):
        # Expiry is a normal no-effect terminal rejection, not an invented execution.
        # A PREPARING/orphan or ROLLBACK_FAILED is NEVER declared safe by age.
        for record in self.plans():
            if record["state"] == "READY" and record.get("expiresAt", 0) <= int(time.time()) and record.get("operationId") is None:
                record.update(state="BLOCKED", errorCode="PLAN_EXPIRED", finishedAt=int(time.time()))
                self.r.save(self.controller.path(record["planId"]) / "operation.json", record)

    def inventory(self, *, preparing=None):
        """Read-only resolution of exact resources; never enroll by tag/age alone."""
        records = self.plans()
        expired = []
        for record in records:
            if record["state"] == "READY" and record.get("expiresAt", 0) <= int(time.time()) and record.get("operationId") is None:
                expired.append(record["planId"])
                # Project the normal expiry without rewriting any record. Thus a
                # pre-install inventory sees the same pins as the first collection.
                record.update(state="BLOCKED", finishedAt=int(time.time()), errorCode="PLAN_EXPIRED")
        if any(record["state"] in ACTIVE and record["planId"] != preparing for record in records):
            self.reject("RETENTION_BUSY")
        image_pins = self.rescue_pins()
        container_pins, available = self.docker_snapshot()
        image_pins |= container_pins
        app = self.controller.targets["APP_PROD"].observe_current()
        android = self.controller.targets["ANDROID_STABLE"].inspect()
        if app.get("healthy") is not True:
            self.reject("RETENTION_PRODUCTION_NOT_HEALTHY")
        image_pins.add(app["imageId"])
        apk_pins = {android["versionCode"]}
        previous = android["manifest"].get("previousRelease")
        if previous:
            apk_pins.add(previous["versionCode"])
        verified = [(record, self.success(record)) for record in records if record["state"] == "SUCCEEDED" and record["target"] in PAYLOADS]
        for target, current, field, pins, count in (
                ("APP_PROD", app["imageId"], "imageId", image_pins, POLICY["backendPrevious"]),
                ("ANDROID_STABLE", android["versionCode"], "versionCode", apk_pins, POLICY["androidPrevious"])):
            history = sorted([(rec, value) for rec, value in verified if rec["target"] == target],
                             key=lambda item: (item[0]["finishedAt"], item[0]["planId"]), reverse=True)
            anchor = next((rec["finishedAt"] for rec, value in history if value[field] == current), None)
            if anchor is None:
                self.reject("RETENTION_CURRENT_RECEIPT_REQUIRED")
            previous_values = []
            for rec, value in history:
                item = value[field]
                if rec["finishedAt"] <= anchor and item != current and item not in previous_values:
                    previous_values.append(item)
            pins.update(previous_values[:count])
        for record in records:
            if record["state"] not in self.r.TERMINAL:
                if record["target"] == "APP_PROD":
                    image_pins.add(record["predecessor"]["imageId"])
                    path = self.controller.path(record["planId"]) / "image.json"
                    if path.exists():
                        image_pins.add(self.read(path)["imageId"])
                elif record["target"] == "ANDROID_STABLE":
                    apk_pins.add(record["predecessor"]["versionCode"])
                    if record.get("versionCode"):
                        apk_pins.add(record["versionCode"])
        actions, apk_seen = {}, {}
        now = int(time.time())
        ledger_path = self.root / "inventory.json"
        ledger = self.read(ledger_path, limit=16*1024**2) if ledger_path.exists() else {"protocol": PROTOCOL, "apks": {}}
        if ledger.get("protocol") != PROTOCOL or not isinstance(ledger.get("apks"), dict):
            self.reject()
        for record in records:
            directory = self.controller.path(record["planId"])
            if record["target"] not in PAYLOADS or record["state"] not in self.r.TERMINAL or record["state"] == "ROLLBACK_FAILED":
                continue
            closed = record["state"] == "SUCCEEDED" or (record.get("finishedAt") is not None
                    and now - record["finishedAt"] >= POLICY["failedGraceSeconds"])
            if not closed:
                continue
            artifact = record.get("artifact", {})
            download = directory / "download.json"
            archive_hash = artifact.get("archiveSha256")
            if archive_hash is None and download.exists():
                attempted = self.read(download)
                if attempted.get("target") != record["target"] or attempted.get("sourceCommit") != record["sourceCommit"]:
                    self.reject()
                archive_hash = attempted["actualSha256"]
            for name, expected in (("artifact.zip", archive_hash),
                                   (PAYLOADS[record["target"]], artifact.get("payloadSha256"))):
                path = directory / name
                if not expected or not path.exists() and not path.is_symlink():
                    continue  # Unregistered/partial legacy content is left intact.
                self.add_file(actions, record, name, expected)
            if record["target"] == "ANDROID_STABLE" and (directory / "signed.json").exists():
                signed = self.read(directory / "signed.json")
                if (directory / "signed.apk").exists() or (directory / "signed.apk").is_symlink():
                    self.add_file(actions, record, "signed.apk", signed["sha256"])
        # Only an already verified publication receipt enrolls a Docker image or APK.
        # Foreign/unregistered images, build cache, volumes and platform trees are untouched.
        for record, receipt in verified:
            if record["target"] == "APP_PROD":
                image_id = receipt["imageId"]
                if image_id in image_pins or image_id not in available:
                    continue
                image = json.loads(self.r.command(["/usr/bin/docker", "image", "inspect", image_id]))[0]
                tags = image.get("RepoTags") or []
                if (image.get("Id") != image_id
                        or (image.get("Config", {}).get("Labels") or {}).get("org.opencontainers.image.revision") != record["sourceCommit"]):
                    self.reject()
                if image.get("RepoDigests") or any(tag != "atenea-app:" + record["sourceCommit"] for tag in tags):
                    continue  # Additional aliases can belong to another authority.
                actions["image:" + image_id] = {"kind": "IMAGE", "imageId": image_id,
                    "sourceCommit": record["sourceCommit"], "bytes": image["Size"]}
            else:
                version = receipt["versionCode"]
                key = str(version)
                retained = ledger["apks"].get(key)
                expected = receipt["manifest"]["sha256"]
                if retained and retained["sha256"] != expected:
                    self.reject()
                seen = {"sha256": expected, "firstSeenAt": retained["firstSeenAt"] if retained else now,
                        "lastProtectedAt": retained["lastProtectedAt"] if retained else now}
                if version in apk_pins:
                    seen["lastProtectedAt"] = now
                apk_seen[key] = seen
                if version in apk_pins or now - max(seen["firstSeenAt"], seen["lastProtectedAt"], record["finishedAt"]) < POLICY["androidGraceSeconds"]:
                    continue
                directory = self.controller.targets["ANDROID_STABLE"].APK_ROOT / "releases" / key
                if not directory.exists() and not directory.is_symlink():
                    continue  # Previously withdrawn generations are not invented/adopted.
                self.r.trusted_directory(directory, 0o755)
                manifest = self.read(directory / "manifest.json", 0o644)
                if manifest != receipt["manifest"]:
                    self.reject()
                path = directory / "atenea-debug.apk"
                if path.exists() or path.is_symlink():
                    self.check_file(path, expected, 0o644)
                    actions["apk:" + key] = {"kind": "APK", "versionCode": version,
                        "sha256": expected, "bytes": path.stat().st_size}
        return {"actions": list(actions.values()), "apks": {**ledger["apks"], **apk_seen},
                "productionSha256": self.r.digest({"app": app, "android": android}),
                "freeBytes": self.free(), "imagePins": sorted(image_pins), "apkPins": sorted(apk_pins),
                "expiredPlanIds": expired}

    def check_file(self, path, expected, mode=0o600):
        if not isinstance(expected, str) or not self.r.DIGEST.fullmatch(expected):
            self.reject()
        self.r.trusted(path, mode)
        if self.r.file_digest(path) != expected:
            self.reject()

    def add_file(self, actions, record, name, expected):
        path = self.controller.path(record["planId"]) / name
        self.check_file(path, expected)
        actions[record["planId"] + ":" + name] = {"kind": "PLAN_FILE", "planId": record["planId"],
            "name": name, "sha256": expected, "bytes": path.stat().st_size}

    def free(self):
        # Docker can use a different filesystem. The smaller capacity is binding.
        return min(shutil.disk_usage(self.controller.root).free, shutil.disk_usage("/var/lib/docker").free)

    def observe(self, record):
        value = self.read(self.controller.path(record["planId"]) / "storage.json")
        self.r.exact(value, {"protocol", "planId", "target", "sourceCommit", "phase", "observedAt",
                            "freeBytes", "requiredBytes", "missingBytes", "reclaimedBytes"})
        if (value["protocol"] != STORAGE_PROTOCOL or value["planId"] != record["planId"]
                or value["target"] != record["target"] or record["target"] not in PAYLOADS
                or value["sourceCommit"] != record["sourceCommit"] or value["phase"] not in PHASES
                or type(value["observedAt"]) is not int or not 0 < value["observedAt"] <= int(time.time()) + 5
                or any(type(value[key]) is not int or not 0 <= value[key] <= 1 << 50
                       for key in ("freeBytes", "requiredBytes", "missingBytes", "reclaimedBytes"))
                or value["missingBytes"] != max(0, value["requiredBytes"]-value["freeBytes"])):
            self.reject("RELEASE_STORAGE_EVIDENCE_MISMATCH")
        return value

    def storage(self, record, phase, *, required=None, reclaimed=None):
        if phase not in PHASES:
            self.reject()
        path = self.controller.path(record["planId"]) / "storage.json"
        previous = self.read(path) if path.exists() else {}
        required = previous.get("requiredBytes", 0) if required is None else required
        reclaimed = previous.get("reclaimedBytes", 0) if reclaimed is None else reclaimed
        free = self.free()
        value = {"protocol": STORAGE_PROTOCOL, "planId": record["planId"], "target": record["target"],
                 "sourceCommit": record["sourceCommit"], "phase": phase, "observedAt": int(time.time()),
                 "freeBytes": free, "requiredBytes": required, "missingBytes": max(0, required-free),
                 "reclaimedBytes": max(0, reclaimed)}
        self.r.save(path, value)
        return value

    def capacity(self, record, archive_bytes):
        # Before download: ZIP + maximum payload + two expanded-image copies + reserve.
        # Expanded image bytes are independently bounded before Docker imports it.
        required = max(POLICY["minimumFreeBytes"], archive_bytes + POLICY["maximumPayloadBytes"]
                       + 2 * POLICY["maximumExpandedImageBytes"] + POLICY["reserveBytes"])
        self.storage(record, "CHECKING_SPACE", required=required)
        self.storage(record, "RECLAIMING", required=required)
        before = self.free()
        self.controller.maintain("BEFORE_PREPARE", preparing=record["planId"])
        reclaimed = max(0, self.free()-before)
        if self.free() < required:
            self.storage(record, "INSUFFICIENT_SPACE", required=required, reclaimed=reclaimed)
            self.reject("RELEASE_STORAGE_INSUFFICIENT")
        self.storage(record, "SPACE_READY", required=required, reclaimed=reclaimed)

    def action_path(self, action):
        if action["kind"] == "PLAN_FILE":
            self.r.identity(action["planId"])
            if action["name"] not in {"artifact.zip", "image.tar", "app-unsigned.apk", "signed.apk"}:
                self.reject()
            return self.controller.path(action["planId"]) / action["name"], 0o600
        if action["kind"] == "APK" and type(action["versionCode"]) is int and action["versionCode"] > 0:
            return self.controller.targets["ANDROID_STABLE"].APK_ROOT / "releases" / str(action["versionCode"]) / "atenea-debug.apk", 0o644
        self.reject()

    @staticmethod
    def action_key(action):
        return json.dumps({key: value for key, value in action.items() if key not in {"state", "deletedAt"}}, sort_keys=True)

    def collect(self, reason, *, preparing=None):
        """Caller holds lifecycle + execution + controller locks; crash replay is exact."""
        if reason not in {"BEFORE_PREPARE", "AFTER_PUBLICATION", "NIGHTLY", "OPERATOR"}:
            self.reject("CLOSED_REQUEST_REQUIRED")
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.r.trusted_directory(self.root, 0o700)
        runs = self.root / "runs"
        runs.mkdir(mode=0o700, exist_ok=True)
        self.r.trusted_directory(runs, 0o700)
        pointer = self.root / "active.json"
        run = None
        if pointer.exists():
            active = self.read(pointer)
            self.r.exact(active, {"runId"})
            self.r.identity(active["runId"])
            run = self.read(runs / (active["runId"] + ".json"), limit=16*1024**2)
            if (run.get("protocol") != PROTOCOL or run.get("policySha256") != self.r.digest(POLICY)
                    or run.get("runId") != active["runId"] or run.get("state") not in {"RUNNING", "SUCCEEDED", "ATTENTION"}):
                self.reject()
            if run["state"] == "ATTENTION":
                self.reject("RETENTION_REQUIRES_INSPECTION")
        try:
            snapshot = self.inventory(preparing=preparing)
        except Exception as error:
            code = error.code if isinstance(error, self.r.Rejected) else "RETENTION_FAILED"
            stopped = run if run is not None else {"protocol": PROTOCOL, "runId": str(uuid.uuid4()), "reason": reason,
                       "policySha256": self.r.digest(POLICY), "state": "BLOCKED", "createdAt": int(time.time()),
                       "finishedAt": int(time.time()), "errorCode": code, "actions": []}
            if run is not None:
                stopped.update(state="ATTENTION", errorCode=code)
            self.r.save(runs / (stopped["runId"] + ".json"), stopped)
            self.r.save(self.root / "last-error.json", {key: stopped[key] for key in
                        ("protocol", "runId", "reason", "state", "finishedAt", "errorCode")})
            raise
        self.r.save(self.root / "inventory.json", {"protocol": PROTOCOL, "apks": snapshot["apks"]})
        if run is None:
            run = {"protocol": PROTOCOL, "runId": str(uuid.uuid4()), "reason": reason,
                   "policySha256": self.r.digest(POLICY), "state": "RUNNING", "createdAt": int(time.time()),
                   "freeBytesBefore": snapshot["freeBytes"], "actions": [dict(a, state="PENDING") for a in snapshot["actions"]]}
            self.r.save(runs / (run["runId"] + ".json"), run)
            self.r.save(pointer, {"runId": run["runId"]})
        if run.get("protocol") != PROTOCOL or run.get("policySha256") != self.r.digest(POLICY):
            self.reject()
        path = runs / (run["runId"] + ".json")
        eligible = {self.action_key(item) for item in snapshot["actions"]}
        try:
            for action in run["actions"]:
                if action["state"] in {"DELETED", "PINNED"}:
                    continue
                # Persist intent BEFORE deletion. On restart, a missing resource is
                # closed only if that exact durable deletion intent already existed.
                if action["kind"] == "IMAGE":
                    used, available = self.docker_snapshot()
                    exists = action["imageId"] in available
                else:
                    resource, mode = self.action_path(action)
                    exists = resource.exists() or resource.is_symlink()
                if not exists:
                    if action["state"] != "DELETING":
                        self.reject("RETENTION_RESOURCE_MOVED")
                elif self.action_key(action) not in eligible:
                    action["state"] = "PINNED"
                    self.r.save(path, run)
                    continue
                else:
                    action["state"] = "DELETING"
                    self.r.save(path, run)
                    if action["kind"] == "IMAGE":
                        if action["imageId"] in used:
                            self.reject("RETENTION_RESOURCE_MOVED")
                        try:
                            self.r.command(["/usr/bin/docker", "image", "rm", action["imageId"]], timeout=120)
                        except self.r.Rejected:
                            # Lost acknowledgement is settled by observing that exact
                            # image's absence, never by force or a broader second rm.
                            if action["imageId"] in self.docker_snapshot()[1]:
                                raise
                        if action["imageId"] in self.docker_snapshot()[1]:
                            self.reject("RETENTION_RESOURCE_MOVED")
                    else:
                        self.check_file(resource, action["sha256"], mode)
                        resource.unlink()  # Never recursive; no following symlinks.
                        descriptor = os.open(resource.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                        try:
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                action.update(state="DELETED", deletedAt=int(time.time()))
                self.r.save(path, run)
            observed = {"app": self.controller.targets["APP_PROD"].observe_current(),
                        "android": self.controller.targets["ANDROID_STABLE"].inspect()}
            if self.r.digest(observed) != snapshot["productionSha256"]:
                self.reject("RETENTION_PRODUCTION_MOVED")
            run.update(state="SUCCEEDED", finishedAt=int(time.time()), freeBytesAfter=self.free(), errorCode=None)
            run["productionSha256"] = snapshot["productionSha256"]
            self.r.save(path, run)
            self.r.save(self.root / "last.json", {key: run[key] for key in
                ("protocol", "runId", "state", "reason", "createdAt", "finishedAt", "freeBytesBefore", "freeBytesAfter", "errorCode")})
            pointer.unlink()
            return run
        except Exception as error:
            run.update(state="ATTENTION", errorCode=error.code if isinstance(error, self.r.Rejected) else "RETENTION_FAILED")
            self.r.save(path, run)
            raise


def attach(release, controller):
    return Retention(release, controller)
