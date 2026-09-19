#!/usr/bin/env python3
"""One closed, resumable activation of the reconciled AX42 Codex bootstrap.

The worker calls ``prepare``; a transient systemd unit calls ``execute`` outside
the worker cgroup so that the worker itself can be restarted and observed.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import pwd
import grp
import re
import stat
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).with_name("codex-release-reconcile-v1.py")
spec = importlib.util.spec_from_file_location("codex_release_reconcile_v1", SCRIPT)
assert spec is not None and spec.loader is not None
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)

OPERATION = "ACTIVATE_RECONCILED_CODEX_RELEASES"
SCHEMA = "codex-release-recovery-activate-v1"
PLAN_ID = "15414500-0000-4000-8000-000000000001"
CURRENT_ID = "15414500-0000-4000-8000-000000000002"
CANDIDATE_ID = "15414500-0000-4000-8000-000000000003"
RECONCILE_KEY = "4fa545b2-dc97-4f68-8543-316c0a6e01f3"
CURRENT_DIGEST = "37de474b157b0313c73ddc05928855f61517676138827df51660fe8715dca14f"
CANDIDATE_DIGEST = "56da3312ccb2109a2f4e0d71b003f08d33244ec6f5863e8fc7f6f24b7a6489c2"
CATALOG_REVISION = "125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187"
ROOT = Path("/srv/atenea/worker/codex-releases-v1")
REGISTRY = Path("/etc/atenea-worker/codex-release-stage-v1.json")
ENV = Path("/etc/atenea-worker/agent-run-worker-v1.env")
TOKEN = Path("/etc/atenea-worker/agent-run-worker-v1.token")
SERVICE = "atenea-agent-run-worker-v1.service"
INSTALLED = Path("/usr/local/libexec/atenea/codex-release-recovery-activate-v1.py")
RUNNER = Path("/usr/local/libexec/atenea/project-codex-runner-v1.py")
REQUEST_FIELDS = {"operation", "idempotencyKey"}
PENDING_STATES = {"PENDING", "ACTIVATING", "RESTORING"}
TERMINAL_STATES = {"ACTIVATED", "RESTORED"}


class RecoveryError(RuntimeError):
    pass


def exact_request(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS or value.get("operation") != OPERATION:
        raise RecoveryError("exact recovery activation request is required")
    key = reconcile.require_uuid(value.get("idempotencyKey"), "idempotencyKey")
    return {"operation": OPERATION, "idempotencyKey": key}


def operation_path(key: str) -> Path:
    return ROOT / "recovery-activations" / (reconcile.require_uuid(key, "idempotencyKey") + ".json")


def read_json(path: Path, owner: int = 0) -> dict[str, Any]:
    reconcile.owned_regular(path, owner, path.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError(f"{path.name} is not an object")
    return value


def exact_bootstrap() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    reconcile.owned_regular(RUNNER, 0, "project Codex runner")
    runner_lines = RUNNER.read_text(encoding="utf-8").splitlines()
    assignments = [line for line in runner_lines if line.startswith("CODEX = ")]
    if assignments != ['CODEX = "/srv/atenea/worker/codex-releases-v1/current/bin/codex"']:
        raise RecoveryError("runner is not pinned to managed current")
    manifest = reconcile.read_manifest(0)
    if (manifest["planId"], manifest["currentInventoryId"], manifest["candidateInventoryId"]) != (
            PLAN_ID, CURRENT_ID, CANDIDATE_ID):
        raise RecoveryError("reconcile manifest is not the exact bootstrap")
    current = manifest["releases"]["current"]
    candidate = manifest["releases"]["candidate"]
    for role in ("current", "candidate"):
        reconcile.validate_release_definition(manifest["releases"][role], role)
    if ((current["version"], current["releaseDigestSha256"], current["catalogRevision"])
            != ("0.154.0", CURRENT_DIGEST, None)
            or (candidate["version"], candidate["releaseDigestSha256"], candidate["catalogRevision"])
            != ("0.145.0", CANDIDATE_DIGEST, CATALOG_REVISION)):
        raise RecoveryError("reconcile manifest release identities differ")
    reconcile.owned_directory(ROOT, 0, "managed release root")
    owner = pwd.getpwnam(manifest["destinationOwner"]).pw_uid
    releases_root = ROOT / "releases"
    reconcile.owned_directory(releases_root, owner, "managed releases")
    expected_releases = {
        "0.154.0-" + CURRENT_DIGEST[:16], "0.145.0-" + CANDIDATE_DIGEST[:16]}
    if {path.name for path in releases_root.iterdir()} != expected_releases:
        raise RecoveryError("managed release inventory is not the exact bootstrap")
    for release in (current, candidate):
        name = release["version"] + "-" + release["releaseDigestSha256"][:16]
        reconcile.verify_managed_release(ROOT / "releases" / name, release, owner)
        package = read_json(ROOT / "releases" / name / "codex-package.json", owner)
        if package != reconcile.package_json(release["version"]):
            raise RecoveryError("managed package metadata differs")
    inventory_path = ROOT / "inventory-v1.json"
    plan_path = ROOT / "recovery-plan-v1.json"
    inventory = read_json(inventory_path)
    plan = read_json(plan_path)
    registry = read_json(REGISTRY)
    reconciliations = ROOT / "reconciliations"
    if {path.name for path in reconciliations.iterdir()} != {RECONCILE_KEY + ".json"}:
        raise RecoveryError("reconciliation inventory is not the single bootstrap")
    record = read_json(reconciliations / (RECONCILE_KEY + ".json"))
    expected_request = {"operation": "RECONCILE_INSTALLED_CODEX_RELEASES",
                        "idempotencyKey": RECONCILE_KEY}
    result = record.get("result")
    if (record.get("requestFingerprint") != reconcile.digest_bytes(
            reconcile.canonical_bytes(expected_request))
            or not isinstance(result, dict)
            or result.get("schemaVersion") != "codex-release-reconcile-v1"
            or result.get("workerId") != "ax42-01"
            or result.get("operation") != "RECONCILE_INSTALLED_CODEX_RELEASES"
            or result.get("idempotencyKey") != RECONCILE_KEY
            or result.get("state") != "RECONCILED"
            or result.get("planId") != PLAN_ID
            or result.get("currentInventoryId") != CURRENT_ID
            or result.get("candidateInventoryId") != CANDIDATE_ID
            or result.get("currentReleaseDigestSha256") != CURRENT_DIGEST
            or result.get("candidateReleaseDigestSha256") != CANDIDATE_DIGEST
            or result.get("candidateCatalogRevision") != CATALOG_REVISION
            or result.get("previousState") != "ABSENT"
            or result.get("previousCompatibilityState") != "UNKNOWN"
            or result.get("valuesExposed") is not False
            or any(result.get(name) != "PASS" for name in (
                "structureVerification", "permissionVerification", "metadataVerification",
                "versionVerification", "hashVerification", "zeroNonTerminalRuns"))):
        raise RecoveryError("durable reconciliation is not the exact accepted bootstrap")
    for value, field in ((inventory, "inventorySha256"), (plan, "planSha256"),
                         (registry, "registrySha256")):
        if reconcile.digest_bytes(reconcile.canonical_bytes(value)) != result.get(field):
            raise RecoveryError(f"{field} differs from durable reconciliation")
    if (inventory.get("schemaVersion") != "codex-release-inventory-v1"
            or inventory.get("workerId") != "ax42-01"
            or inventory.get("previous") != {"state": "ABSENT", "compatibilityState": "UNKNOWN"}
            or inventory.get("current") != {
                "inventoryId": CURRENT_ID, "codexVersion": "0.154.0",
                "releaseDigestSha256": CURRENT_DIGEST, "installationState": "INSTALLED",
                "linkState": "CURRENT", "compatibilityState": "UNKNOWN", "catalogRevision": None}
            or inventory.get("candidate") != {
                "inventoryId": CANDIDATE_ID, "codexVersion": "0.145.0",
                "releaseDigestSha256": CANDIDATE_DIGEST, "installationState": "STAGED",
                "linkState": "NONE", "compatibilityState": "COMPATIBLE",
                "catalogRevision": CATALOG_REVISION}):
        raise RecoveryError("bootstrap inventory is not exact")
    if plan != {
            "schemaVersion": "codex-release-recovery-plan-v1", "workerId": "ax42-01",
            "planId": PLAN_ID, "state": "READY", "currentInventoryId": CURRENT_ID,
            "candidateInventoryId": CANDIDATE_ID, "previousState": "ABSENT_UNKNOWN",
            "activationTargetVersion": "0.145.0"}:
        raise RecoveryError("recovery plan is not exact")
    if registry != {
            "schemaVersion": "codex-release-stage-v1", "workerId": "ax42-01",
            "candidates": {CANDIDATE_ID: {
                "planId": PLAN_ID, "candidateId": CANDIDATE_ID,
                "codexVersion": "0.145.0", "releaseDigestSha256": CANDIDATE_DIGEST,
                "catalogRevision": CATALOG_REVISION}}}:
        raise RecoveryError("root-owned candidate registry is not exact")
    current_link = ROOT / "current"
    expected = "releases/0.154.0-" + CURRENT_DIGEST[:16]
    if not current_link.is_symlink() or os.readlink(current_link) != expected:
        raise RecoveryError("managed current is not the reconciled release")
    if (ROOT / "previous").exists() or (ROOT / "previous").is_symlink():
        raise RecoveryError("bootstrap previous must be absent")
    if reconcile.link_fingerprint(current_link, expected) != result.get("currentLinkFingerprint"):
        raise RecoveryError("current fingerprint differs from reconciliation")
    reconcile.validate_zero_non_terminal(owner)
    return manifest, inventory, plan, result


def exact_catalog() -> dict[str, Any]:
    reconcile.owned_regular(ENV, 0, "worker environment")
    reconcile.owned_regular(TOKEN, 0, "worker token")
    variables = dict(line.split("=", 1) for line in ENV.read_text(encoding="utf-8").splitlines()
                     if "=" in line and not line.startswith("#"))
    bind, port = variables.get("ATENEA_WORKER_BIND"), variables.get("ATENEA_WORKER_PORT")
    if not isinstance(bind, str) or not re.fullmatch(r"100\.(?:\d{1,3}\.){2}\d{1,3}", bind) or port != "8787":
        raise RecoveryError("worker endpoint is not the installed tailnet identity")
    token = TOKEN.read_text(encoding="utf-8").strip()
    if not token:
        raise RecoveryError("worker token is unavailable")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path: str) -> dict[str, Any]:
        request = urllib.request.Request(f"http://{bind}:8787{path}",
                                         headers={"Authorization": "Bearer " + token})
        with opener.open(request, timeout=5) as response:
            return json.load(response)
    health = get("/v1/health")
    catalog = get("/v1/codex/catalog")
    if (health.get("workerId") != "ax42-01" or health.get("healthy") is not True
            or "project-codex-v4" not in health.get("capabilities", [])
            or catalog.get("workerId") != "ax42-01"
            or catalog.get("codexVersion") != "0.145.0"
            or catalog.get("catalogRevision") != CATALOG_REVISION):
        raise RecoveryError("worker health or catalog postcondition failed")
    return health


def fixed_probe(version: str) -> None:
    release = ROOT / "releases" / (version + "-" +
                                   (CANDIDATE_DIGEST if version == "0.145.0" else CURRENT_DIGEST)[:16])
    binary = release / "bin/codex"
    for arguments in (("--version",), ("exec", "--help")):
        completed = subprocess.run([str(binary), *arguments], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, timeout=30, check=False,
                                   env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        if completed.returncode != 0 or not completed.stdout.strip():
            raise RecoveryError("fixed Codex probe failed")
        if arguments == ("--version",) and completed.stdout.strip() != "codex-cli " + version:
            raise RecoveryError("effective Codex version differs")


def replace_link(link: Path, target: str) -> None:
    temporary = link.parent / ("." + link.name + "." + uuid.uuid4().hex)
    try:
        temporary.symlink_to(target)
        os.replace(temporary, link)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def persist_operation(path: Path, value: dict[str, Any]) -> None:
    group = grp.getgrnam("atenea").gr_gid
    reconcile.persist_json(path, value, 0o640, 0, group)


def read_operation(key: str) -> dict[str, Any]:
    value = read_json(operation_path(key))
    if (value.get("schemaVersion") != SCHEMA or value.get("operation") != OPERATION
            or value.get("idempotencyKey") != key or value.get("planId") != PLAN_ID
            or value.get("currentInventoryId") != CURRENT_ID
            or value.get("candidateInventoryId") != CANDIDATE_ID
            or value.get("state") not in PENDING_STATES | TERMINAL_STATES):
        raise RecoveryError("durable recovery activation is invalid")
    return value


def schedule(key: str) -> None:
    unit = "atenea-codex-recovery-" + uuid.uuid4().hex
    completed = subprocess.run([
        "/usr/bin/systemd-run", "--quiet", "--collect", "--unit=" + unit,
        "--on-active=2s", str(INSTALLED), "--execute", key],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=15, check=False)
    if completed.returncode != 0:
        raise RecoveryError("recovery activation scheduling failed")


def prepare(request: dict[str, str]) -> dict[str, Any]:
    key = request["idempotencyKey"]
    directory = ROOT / "recovery-activations"
    if not directory.exists():
        directory.mkdir(mode=0o750)
        os.chown(directory, 0, grp.getgrnam("atenea").gr_gid)
    reconcile.owned_directory(directory, 0, "recovery activation directory")
    path = operation_path(key)
    if path.exists():
        existing = read_operation(key)
        if existing["state"] in PENDING_STATES:
            schedule(key)
        return existing
    if any(directory.glob("*.json")) or any((ROOT / "activations").glob("*.json")):
        raise RecoveryError("another activation already owns this bootstrap")
    exact_bootstrap()
    fixed_probe("0.154.0")
    fixed_probe("0.145.0")
    value = {"schemaVersion": SCHEMA, "operation": OPERATION,
             "idempotencyKey": key, "workerId": "ax42-01", "planId": PLAN_ID,
             "currentInventoryId": CURRENT_ID, "candidateInventoryId": CANDIDATE_ID,
             "state": "PENDING", "gates": {}, "automaticRestore": "NOT_REQUIRED",
             "valuesExposed": False}
    persist_operation(path, value)
    try:
        schedule(key)
    except RecoveryError:
        path.unlink()
        raise
    return value


def restart_and_wait(expected_version: str) -> None:
    completed = subprocess.run(["/usr/bin/systemctl", "restart", SERVICE],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=45, check=False)
    if completed.returncode != 0:
        raise RecoveryError("controlled worker restart failed")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if expected_version == "0.145.0":
                exact_catalog()
            else:
                # The catalog advertises the compatible 0.145.0 in both states.
                exact_catalog()
            return
        except (RecoveryError, OSError, ValueError, json.JSONDecodeError):
            time.sleep(1)
    raise RecoveryError("worker health/catalog did not recover after restart")


def execute(key: str) -> dict[str, Any]:
    path = operation_path(key)
    record = read_operation(key)
    if record["state"] in TERMINAL_STATES:
        return record
    if record["state"] == "RESTORING":
        return restore(key, record)
    try:
        if record["state"] == "PENDING":
            _manifest, inventory, plan, evidence = exact_bootstrap()
            fixed_probe("0.145.0")
            record["state"] = "ACTIVATING"
            record["currentBeforeFingerprint"] = evidence["currentLinkFingerprint"]
            persist_operation(path, record)
            replace_link(ROOT / "previous", "releases/0.154.0-" + CURRENT_DIGEST[:16])
            replace_link(ROOT / "current", "releases/0.145.0-" + CANDIDATE_DIGEST[:16])
        else:
            # A restarted transient unit may resume only the two exact links.
            if (os.readlink(ROOT / "current") != "releases/0.145.0-" + CANDIDATE_DIGEST[:16]
                    or os.readlink(ROOT / "previous") != "releases/0.154.0-" + CURRENT_DIGEST[:16]):
                raise RecoveryError("interrupted activation links are ambiguous")
            inventory = read_json(ROOT / "inventory-v1.json")
            plan = read_json(ROOT / "recovery-plan-v1.json")
            evidence = read_json(ROOT / "reconciliations" / (RECONCILE_KEY + ".json"))["result"]
            registry = read_json(REGISTRY)
            manifest = reconcile.read_manifest(0)
            if (reconcile.digest_bytes(reconcile.canonical_bytes(inventory)) != evidence["inventorySha256"]
                    or reconcile.digest_bytes(reconcile.canonical_bytes(plan)) != evidence["planSha256"]
                    or reconcile.digest_bytes(reconcile.canonical_bytes(registry)) != evidence["registrySha256"]
                    or manifest.get("planId") != PLAN_ID):
                raise RecoveryError("interrupted activation state is ambiguous")
            owner = pwd.getpwnam("atenea-worker").pw_uid
            for role, version, digest in (("current", "0.154.0", CURRENT_DIGEST),
                                          ("candidate", "0.145.0", CANDIDATE_DIGEST)):
                definition = manifest["releases"][role]
                reconcile.validate_release_definition(definition, role)
                if definition["version"] != version or definition["releaseDigestSha256"] != digest:
                    raise RecoveryError("resumed release identity differs")
                reconcile.verify_managed_release(
                    ROOT / "releases" / (version + "-" + digest[:16]), definition, owner)
            reconcile.validate_zero_non_terminal(owner)
        fixed_probe("0.145.0")
        restart_and_wait("0.145.0")
        if (os.readlink(ROOT / "current") != "releases/0.145.0-" + CANDIDATE_DIGEST[:16]
                or os.readlink(ROOT / "previous") != "releases/0.154.0-" + CURRENT_DIGEST[:16]):
            raise RecoveryError("activation links changed during postconditions")
        reconcile.validate_zero_non_terminal(pwd.getpwnam("atenea-worker").pw_uid)
        final_inventory = {
            "schemaVersion": "codex-release-inventory-v1", "workerId": "ax42-01",
            "current": {**inventory["candidate"], "installationState": "INSTALLED", "linkState": "CURRENT"},
            "previous": {**inventory["current"], "linkState": "PREVIOUS"}}
        final_plan = {**plan, "state": "ACTIVATED"}
        reconcile.persist_json(ROOT / "inventory-v1.json", final_inventory, 0o600, 0,
                               grp.getgrnam("atenea").gr_gid)
        reconcile.persist_json(ROOT / "recovery-plan-v1.json", final_plan, 0o600, 0,
                               grp.getgrnam("atenea").gr_gid)
        record.update(state="ACTIVATED", gates={
            "hashes": "PASS", "catalog": "PASS", "version": "PASS",
            "workerHealth": "PASS", "fixedCanary": "PASS", "zeroNonTerminalRuns": "PASS"},
            currentAfterFingerprint=reconcile.link_fingerprint(
                ROOT / "current", os.readlink(ROOT / "current")),
            previousAfterFingerprint=reconcile.link_fingerprint(
                ROOT / "previous", os.readlink(ROOT / "previous")),
            inventorySha256=reconcile.digest_bytes(reconcile.canonical_bytes(final_inventory)),
            planSha256=reconcile.digest_bytes(reconcile.canonical_bytes(final_plan)),
            completedAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        persist_operation(path, record)
        return record
    except (Exception,) as error:
        record["state"] = "RESTORING"
        record["failure"] = type(error).__name__
        persist_operation(path, record)
        return restore(key, record)


def restore(key: str, record: dict[str, Any]) -> dict[str, Any]:
    path = operation_path(key)
    evidence = read_json(ROOT / "reconciliations" / (RECONCILE_KEY + ".json"))["result"]
    manifest = reconcile.read_manifest(0)
    current_definition = manifest["releases"]["current"]
    reconcile.validate_release_definition(current_definition, "current")
    if (current_definition["version"] != "0.154.0"
            or current_definition["releaseDigestSha256"] != CURRENT_DIGEST):
        raise RecoveryError("automatic restoration source differs")
    reconcile.verify_managed_release(
        ROOT / "releases" / ("0.154.0-" + CURRENT_DIGEST[:16]),
        current_definition, pwd.getpwnam("atenea-worker").pw_uid)
    current = ROOT / "current"
    previous = ROOT / "previous"
    valid_current = {"releases/0.145.0-" + CANDIDATE_DIGEST[:16],
                     "releases/0.154.0-" + CURRENT_DIGEST[:16]}
    if not current.is_symlink() or os.readlink(current) not in valid_current:
        raise RecoveryError("automatic restoration stopped at ambiguous current link")
    if previous.exists() or previous.is_symlink():
        if not previous.is_symlink() or os.readlink(previous) != "releases/0.154.0-" + CURRENT_DIGEST[:16]:
            raise RecoveryError("automatic restoration stopped at ambiguous previous link")
    replace_link(current, "releases/0.154.0-" + CURRENT_DIGEST[:16])
    if previous.is_symlink():
        previous.unlink()
    # These exact initial bytes are reconstructed from the immutable reconciliation
    # manifest and compared to the recorded hashes before replacing any final state.
    current_release, candidate_release = manifest["releases"]["current"], manifest["releases"]["candidate"]
    inventory = {
        "schemaVersion": "codex-release-inventory-v1", "workerId": "ax42-01",
        "current": {"inventoryId": CURRENT_ID, "codexVersion": current_release["version"],
                    "releaseDigestSha256": CURRENT_DIGEST, "installationState": "INSTALLED",
                    "linkState": "CURRENT", "compatibilityState": "UNKNOWN", "catalogRevision": None},
        "candidate": {"inventoryId": CANDIDATE_ID, "codexVersion": candidate_release["version"],
                      "releaseDigestSha256": CANDIDATE_DIGEST, "installationState": "STAGED",
                      "linkState": "NONE", "compatibilityState": "COMPATIBLE",
                      "catalogRevision": CATALOG_REVISION},
        "previous": {"state": "ABSENT", "compatibilityState": "UNKNOWN"}}
    plan = {"schemaVersion": "codex-release-recovery-plan-v1", "workerId": "ax42-01",
            "planId": PLAN_ID, "state": "READY", "currentInventoryId": CURRENT_ID,
            "candidateInventoryId": CANDIDATE_ID, "previousState": "ABSENT_UNKNOWN",
            "activationTargetVersion": "0.145.0"}
    if (reconcile.digest_bytes(reconcile.canonical_bytes(inventory)) != evidence["inventorySha256"]
            or reconcile.digest_bytes(reconcile.canonical_bytes(plan)) != evidence["planSha256"]):
        raise RecoveryError("automatic restoration evidence differs")
    group = grp.getgrnam("atenea").gr_gid
    reconcile.persist_json(ROOT / "inventory-v1.json", inventory, 0o600, 0, group)
    reconcile.persist_json(ROOT / "recovery-plan-v1.json", plan, 0o600, 0, group)
    fixed_probe("0.154.0")
    restart_and_wait("0.154.0")
    if (reconcile.link_fingerprint(current, os.readlink(current)) != evidence["currentLinkFingerprint"]
            or previous.exists() or previous.is_symlink()):
        raise RecoveryError("automatic restoration postcondition failed")
    record.update(state="RESTORED", automaticRestore="PASS",
                  currentAfterFingerprint=evidence["currentLinkFingerprint"],
                  inventorySha256=evidence["inventorySha256"], planSha256=evidence["planSha256"],
                  completedAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    persist_operation(path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--execute", metavar="IDEMPOTENCY_KEY")
    group.add_argument("--inspect", metavar="IDEMPOTENCY_KEY")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print('{"error":"recovery_activation_rejected","message":"root required"}', file=sys.stderr)
        return 2
    try:
        if args.inspect:
            result = read_operation(reconcile.require_uuid(args.inspect, "idempotencyKey"))
        else:
            descriptor = os.open(ROOT / ".recovery-activate-v1.lock",
                                 os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0:
                    raise RecoveryError("recovery activation lock is unsafe")
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                if args.prepare:
                    result = prepare(exact_request(json.load(sys.stdin)))
                else:
                    result = execute(reconcile.require_uuid(args.execute, "idempotencyKey"))
            finally:
                os.close(descriptor)
    except (RecoveryError, reconcile.ReconcileError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": "recovery_activation_rejected", "message": str(error)}),
              file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
