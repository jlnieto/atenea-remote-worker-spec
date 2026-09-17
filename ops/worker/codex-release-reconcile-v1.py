#!/usr/bin/env python3
"""Bootstrap the exact installed standalone Codex releases into managed state."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import grp
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "codex-release-reconcile-v1"
MANIFEST_SCHEMA = "codex-release-reconcile-manifest-v1"
WORKER_ID = "ax42-01"
OPERATION = "RECONCILE_INSTALLED_CODEX_RELEASES"
SOURCE_ROOT = Path("/home/jose/.codex/packages/standalone/releases")
DESTINATION_ROOT = Path("/srv/atenea/worker/codex-releases-v1")
MANIFEST_PATH = Path("/etc/atenea-worker/codex-release-reconcile-v1.json")
EXECUTION_STATE_PATH = Path("/srv/atenea/worker/agent-runs-v1/executions.json")
REGISTRY_PATH = Path("/etc/atenea-worker/codex-release-stage-v1.json")
REQUEST_FIELDS = {"operation", "idempotencyKey"}
NON_TERMINAL = {"QUEUED", "STARTING", "RUNNING", "CANCELLING", "RECONCILING"}
DIGEST = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ALLOWED_DIRECTORIES = {
    "bin", "codex-path", "codex-resources", "codex-resources/zsh",
    "codex-resources/zsh/bin",
}


class ReconcileError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def require_uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ReconcileError(f"{field} must be a UUID")
    try:
        parsed = str(uuid.UUID(value))
    except ValueError as error:
        raise ReconcileError(f"{field} must be a UUID") from error
    if parsed != value:
        raise ReconcileError(f"{field} must be a canonical UUID")
    return value


def read_request() -> dict[str, str]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReconcileError("request must be valid JSON") from error
    return validate_request(value)


def validate_request(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise ReconcileError("exact reconcile request fields are required")
    if value.get("operation") != OPERATION:
        raise ReconcileError("reconcile operation is required")
    return {"operation": OPERATION,
            "idempotencyKey": require_uuid(value.get("idempotencyKey"), "idempotencyKey")}


def owned_regular(path: Path, owner_uid: int, description: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReconcileError(f"{description} is unavailable") from error
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner_uid
            or metadata.st_mode & 0o022):
        raise ReconcileError(f"{description} ownership or mode is unsafe")
    return metadata


def owned_directory(path: Path, owner_uid: int, description: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReconcileError(f"{description} is unavailable") from error
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != owner_uid
            or metadata.st_mode & 0o002):
        raise ReconcileError(f"{description} ownership or mode is unsafe")
    return metadata


def exact_json(path: Path, expected: dict[str, Any], owner_uid: int, description: str) -> None:
    owned_regular(path, owner_uid, description)
    try:
        observed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReconcileError(f"{description} is invalid") from error
    if observed != expected:
        raise ReconcileError(f"{description} conflicts with the recovered state")


def persist_json(path: Path, value: dict[str, Any], mode: int, uid: int, gid: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".reconcile-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, mode)
        os.chown(temporary_name, uid, gid)
        os.replace(temporary_name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def read_manifest(authority_uid: int) -> dict[str, Any]:
    owned_regular(MANIFEST_PATH, authority_uid, "reconcile manifest")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReconcileError("reconcile manifest is invalid") from error
    fields = {
        "schemaVersion", "workerId", "sourceRoot", "destinationRoot", "sourceOwner",
        "destinationOwner", "destinationGroup", "planId", "currentInventoryId",
        "candidateInventoryId", "releases",
    }
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ReconcileError("reconcile manifest fields are invalid")
    if (manifest["schemaVersion"] != MANIFEST_SCHEMA or manifest["workerId"] != WORKER_ID
            or manifest["sourceRoot"] != str(SOURCE_ROOT)
            or manifest["destinationRoot"] != str(DESTINATION_ROOT)):
        raise ReconcileError("reconcile manifest authority is invalid")
    for field in ("planId", "currentInventoryId", "candidateInventoryId"):
        require_uuid(manifest[field], field)
    if (not isinstance(manifest["releases"], dict)
            or set(manifest["releases"]) != {"current", "candidate"}):
        raise ReconcileError("exact current and candidate releases are required")
    return manifest


def release_digest(release: dict[str, Any]) -> str:
    identity = {
        "version": release["version"], "packageDirectory": release["packageDirectory"],
        "target": release["target"], "expectedVersionOutput": release["expectedVersionOutput"],
        "files": release["files"],
    }
    return digest_bytes(canonical_bytes(identity))


def validate_release_definition(release: Any, role: str) -> None:
    fields = {
        "version", "packageDirectory", "target", "expectedVersionOutput",
        "releaseDigestSha256", "catalogRevision", "files",
    }
    if not isinstance(release, dict) or set(release) != fields:
        raise ReconcileError(f"{role} release definition is invalid")
    if not isinstance(release["version"], str) or not VERSION.fullmatch(release["version"]):
        raise ReconcileError(f"{role} version is invalid")
    expected_directory = release["version"] + "-x86_64-unknown-linux-musl"
    if (release["packageDirectory"] != expected_directory
            or release["target"] != "x86_64-unknown-linux-musl"
            or release["expectedVersionOutput"] != "codex-cli " + release["version"]):
        raise ReconcileError(f"{role} package identity is invalid")
    if (not DIGEST.fullmatch(str(release["releaseDigestSha256"]))
            or release_digest(release) != release["releaseDigestSha256"]):
        raise ReconcileError(f"{role} release digest is invalid")
    if release["catalogRevision"] is not None and not DIGEST.fullmatch(str(release["catalogRevision"])):
        raise ReconcileError(f"{role} catalog revision is invalid")
    expected_files = {
        "bin/codex", "bin/codex-code-mode-host", "codex-package.json", "codex-path/rg",
        "codex-resources/bwrap", "codex-resources/zsh/bin/zsh",
    }
    if not isinstance(release["files"], dict) or set(release["files"]) != expected_files:
        raise ReconcileError(f"{role} file allowlist is invalid")
    for relative, identity in release["files"].items():
        if (not isinstance(identity, dict) or set(identity) != {"sha256", "mode"}
                or not DIGEST.fullmatch(str(identity["sha256"]))
                or identity["mode"] not in {"0644", "0755"}
                or Path(relative).is_absolute() or ".." in Path(relative).parts):
            raise ReconcileError(f"{role} file identity is invalid")


def package_json(version: str) -> dict[str, Any]:
    return {
        "layoutVersion": 1, "version": version, "target": "x86_64-unknown-linux-musl",
        "variant": "codex", "entrypoint": "bin/codex", "resourcesDir": "codex-resources",
        "pathDir": "codex-path",
    }


def validate_source_package(release: dict[str, Any], source_uid: int, role: str) -> Path:
    package = SOURCE_ROOT / release["packageDirectory"]
    metadata = owned_directory(package, source_uid, f"{role} source package")
    if stat.S_IMODE(metadata.st_mode) != 0o775:
        raise ReconcileError(f"{role} source package mode is unexpected")
    observed_directories: set[str] = set()
    observed_files: set[str] = set()
    observed_links: dict[str, str] = {}
    for path in package.rglob("*"):
        relative = path.relative_to(package).as_posix()
        item = path.lstat()
        if item.st_uid != source_uid or (not stat.S_ISLNK(item.st_mode) and item.st_mode & 0o002):
            raise ReconcileError(f"{role} source package contains unsafe ownership or mode")
        if stat.S_ISDIR(item.st_mode):
            if stat.S_IMODE(item.st_mode) != 0o755:
                raise ReconcileError(f"{role} source directory mode is unexpected")
            observed_directories.add(relative)
        elif stat.S_ISREG(item.st_mode):
            observed_files.add(relative)
        elif stat.S_ISLNK(item.st_mode):
            observed_links[relative] = os.readlink(path)
        else:
            raise ReconcileError(f"{role} source package contains an unsupported entry")
    if (observed_directories != ALLOWED_DIRECTORIES
            or observed_files != set(release["files"])
            or observed_links != {"codex": "bin/codex"}):
        raise ReconcileError(f"{role} source package structure is unexpected")
    for relative, identity in release["files"].items():
        path = package / relative
        item = owned_regular(path, source_uid, f"{role} {relative}")
        if (format(stat.S_IMODE(item.st_mode), "04o") != identity["mode"]
                or digest_file(path) != identity["sha256"]):
            raise ReconcileError(f"{role} {relative} does not match the manifest")
    try:
        metadata_value = json.loads((package / "codex-package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReconcileError(f"{role} codex-package.json is invalid") from error
    if metadata_value != package_json(release["version"]):
        raise ReconcileError(f"{role} codex-package.json is conflicting")
    try:
        completed = subprocess.run(
            [str(package / "bin/codex"), "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReconcileError(f"{role} fixed version probe failed") from error
    if completed.returncode != 0 or completed.stdout.strip() != release["expectedVersionOutput"]:
        raise ReconcileError(f"{role} fixed version probe is conflicting")
    return package


def validate_zero_non_terminal(execution_owner_uid: int) -> None:
    owned_regular(EXECUTION_STATE_PATH, execution_owner_uid, "worker execution state")
    try:
        state = json.loads(EXECUTION_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReconcileError("worker execution state is invalid") from error
    if (not isinstance(state, dict) or state.get("protocol") != "agent-run-worker/v1"
            or not isinstance(state.get("executions"), dict)):
        raise ReconcileError("worker execution state schema is invalid")
    if any(not isinstance(value, dict) or value.get("status") in NON_TERMINAL
           for value in state["executions"].values()):
        raise ReconcileError("reconciliation requires zero non-terminal AgentRuns")


def verify_managed_release(target: Path, release: dict[str, Any], owner_uid: int) -> None:
    owned_directory(target, owner_uid, "managed release")
    observed_files = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()}
    observed_directories = {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_dir()}
    if observed_files != set(release["files"]) or observed_directories != ALLOWED_DIRECTORIES:
        raise ReconcileError("managed release structure is conflicting")
    for relative, identity in release["files"].items():
        path = target / relative
        item = owned_regular(path, owner_uid, f"managed {relative}")
        if (format(stat.S_IMODE(item.st_mode), "04o") != identity["mode"]
                or digest_file(path) != identity["sha256"]):
            raise ReconcileError("managed release identity is conflicting")


def materialize_release(source: Path, release: dict[str, Any], owner_uid: int, group_gid: int) -> Path:
    releases = DESTINATION_ROOT / "releases"
    name = release["version"] + "-" + release["releaseDigestSha256"][:16]
    target = releases / name
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            raise ReconcileError("managed release target is ambiguous")
        verify_managed_release(target, release, owner_uid)
        return target
    temporary = Path(tempfile.mkdtemp(prefix=".reconcile-release-", dir=releases))
    try:
        os.chown(temporary, owner_uid, group_gid)
        os.chmod(temporary, 0o750)
        for directory in sorted(ALLOWED_DIRECTORIES, key=lambda value: (value.count("/"), value)):
            destination = temporary / directory
            destination.mkdir()
            os.chown(destination, owner_uid, group_gid)
            os.chmod(destination, 0o750)
        for relative, identity in release["files"].items():
            destination = temporary / relative
            with (source / relative).open("rb") as source_handle, destination.open("xb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
                target_handle.flush()
                os.fsync(target_handle.fileno())
            os.chown(destination, owner_uid, group_gid)
            os.chmod(destination, int(identity["mode"], 8))
        verify_managed_release(temporary, release, owner_uid)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target


def link_fingerprint(link: Path, target: str) -> str:
    return digest_bytes(canonical_bytes({"link": link.name, "target": target,
                                         "release": Path(target).name}))


def ensure_current(target: Path) -> tuple[str, bool]:
    current = DESTINATION_ROOT / "current"
    raw_target = "releases/" + target.name
    if current.is_symlink():
        if os.readlink(current) != raw_target or current.resolve(strict=True) != target.resolve(strict=True):
            raise ReconcileError("managed current link conflicts with observed release")
        return link_fingerprint(current, raw_target), False
    if current.exists():
        raise ReconcileError("managed current link is ambiguous")
    temporary = DESTINATION_ROOT / (".current-" + str(uuid.uuid4()))
    try:
        os.symlink(raw_target, temporary)
        os.replace(temporary, current)
    finally:
        if temporary.is_symlink():
            temporary.unlink()
    return link_fingerprint(current, raw_target), True


def reconcile(
        request: dict[str, str], authority_uid: int = 0, authority_gid: int = 0
) -> dict[str, Any]:
    request = validate_request(request)
    manifest = read_manifest(authority_uid)
    for role in ("current", "candidate"):
        validate_release_definition(manifest["releases"][role], role)
    source_uid = pwd.getpwnam(manifest["sourceOwner"]).pw_uid
    destination_uid = pwd.getpwnam(manifest["destinationOwner"]).pw_uid
    destination_gid = grp.getgrnam(manifest["destinationGroup"]).gr_gid
    execution_uid = destination_uid
    owned_directory(SOURCE_ROOT, source_uid, "standalone release root")
    owned_directory(DESTINATION_ROOT, authority_uid, "managed release root")
    releases_root = DESTINATION_ROOT / "releases"
    owned_directory(releases_root, destination_uid, "managed releases directory")
    validate_zero_non_terminal(execution_uid)
    sources = {role: validate_source_package(manifest["releases"][role], source_uid, role)
               for role in ("current", "candidate")}
    reconciliations = DESTINATION_ROOT / "reconciliations"
    inventory_path = DESTINATION_ROOT / "inventory-v1.json"
    plan_path = DESTINATION_ROOT / "recovery-plan-v1.json"
    lock_path = DESTINATION_ROOT / ".reconcile-v1.lock"
    for path, mode in ((reconciliations, 0o750),):
        if not path.exists():
            path.mkdir(mode=mode)
            os.chown(path, authority_uid, destination_gid)
        owned_directory(path, authority_uid, "reconcile operation directory")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != authority_uid:
            raise ReconcileError("reconcile lock ownership is unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        request_fingerprint = digest_bytes(canonical_bytes(request))
        operation_path = reconciliations / (request["idempotencyKey"] + ".json")
        if operation_path.exists():
            owned_regular(operation_path, authority_uid, "reconcile operation record")
            persisted = json.loads(operation_path.read_text(encoding="utf-8"))
            if (not isinstance(persisted, dict)
                    or persisted.get("requestFingerprint") != request_fingerprint
                    or not isinstance(persisted.get("result"), dict)):
                raise ReconcileError("persisted reconcile operation is invalid or conflicting")
            return persisted["result"]

        managed = {role: materialize_release(sources[role], manifest["releases"][role],
                                             destination_uid, destination_gid)
                   for role in ("current", "candidate")}
        previous = DESTINATION_ROOT / "previous"
        if previous.exists() or previous.is_symlink():
            raise ReconcileError("bootstrap previous must be absent")
        current_fingerprint, links_changed = ensure_current(managed["current"])
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        current_release = manifest["releases"]["current"]
        candidate_release = manifest["releases"]["candidate"]
        inventory = {
            "schemaVersion": "codex-release-inventory-v1", "workerId": WORKER_ID,
            "current": {
                "inventoryId": manifest["currentInventoryId"], "codexVersion": current_release["version"],
                "releaseDigestSha256": current_release["releaseDigestSha256"],
                "installationState": "INSTALLED", "linkState": "CURRENT",
                "compatibilityState": "UNKNOWN", "catalogRevision": None,
            },
            "candidate": {
                "inventoryId": manifest["candidateInventoryId"], "codexVersion": candidate_release["version"],
                "releaseDigestSha256": candidate_release["releaseDigestSha256"],
                "installationState": "STAGED", "linkState": "NONE",
                "compatibilityState": "COMPATIBLE", "catalogRevision": candidate_release["catalogRevision"],
            },
            "previous": {"state": "ABSENT", "compatibilityState": "UNKNOWN"},
        }
        plan = {
            "schemaVersion": "codex-release-recovery-plan-v1", "workerId": WORKER_ID,
            "planId": manifest["planId"], "state": "READY",
            "currentInventoryId": manifest["currentInventoryId"],
            "candidateInventoryId": manifest["candidateInventoryId"],
            "previousState": "ABSENT_UNKNOWN", "activationTargetVersion": candidate_release["version"],
        }
        registry = {
            "schemaVersion": "codex-release-stage-v1", "workerId": WORKER_ID,
            "candidates": {manifest["candidateInventoryId"]: {
                "planId": manifest["planId"], "candidateId": manifest["candidateInventoryId"],
                "codexVersion": candidate_release["version"],
                "releaseDigestSha256": candidate_release["releaseDigestSha256"],
                "catalogRevision": candidate_release["catalogRevision"],
            }},
        }
        for path, value, owner, group in (
            (inventory_path, inventory, authority_uid, destination_gid),
            (plan_path, plan, authority_uid, destination_gid),
            (REGISTRY_PATH, registry, authority_uid, authority_gid),
        ):
            if path.exists():
                exact_json(path, value, owner, path.name)
            else:
                persist_json(path, value, 0o600, owner, group)
        result = {
            "schemaVersion": SCHEMA_VERSION, "operation": OPERATION, "workerId": WORKER_ID,
            "idempotencyKey": request["idempotencyKey"], "state": "RECONCILED",
            "planId": manifest["planId"], "currentInventoryId": manifest["currentInventoryId"],
            "candidateInventoryId": manifest["candidateInventoryId"],
            "currentVersion": current_release["version"], "candidateVersion": candidate_release["version"],
            "currentReleaseDigestSha256": current_release["releaseDigestSha256"],
            "candidateReleaseDigestSha256": candidate_release["releaseDigestSha256"],
            "candidateCatalogRevision": candidate_release["catalogRevision"],
            "currentInstallationState": "INSTALLED", "currentLinkState": "CURRENT",
            "currentCompatibilityState": "UNKNOWN", "candidateInstallationState": "STAGED",
            "candidateLinkState": "NONE", "candidateCompatibilityState": "COMPATIBLE",
            "previousState": "ABSENT", "previousCompatibilityState": "UNKNOWN",
            "structureVerification": "PASS", "permissionVerification": "PASS",
            "metadataVerification": "PASS", "versionVerification": "PASS",
            "hashVerification": "PASS", "zeroNonTerminalRuns": "PASS",
            "currentLinkFingerprint": current_fingerprint, "linksChanged": links_changed,
            "inventorySha256": digest_bytes(canonical_bytes(inventory)),
            "planSha256": digest_bytes(canonical_bytes(plan)),
            "registrySha256": digest_bytes(canonical_bytes(registry)),
            "valuesExposed": False, "completedAt": now,
        }
        persist_json(operation_path, {"requestFingerprint": request_fingerprint, "result": result},
                     0o600, authority_uid, destination_gid)
        return result
    finally:
        os.close(descriptor)


def main() -> int:
    if os.geteuid() != 0:
        print('{"error":"reconcile_rejected","message":"root execution is required"}', file=sys.stderr)
        return 2
    try:
        result = reconcile(read_request())
    except (ReconcileError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"error": "reconcile_rejected", "message": str(error)},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
