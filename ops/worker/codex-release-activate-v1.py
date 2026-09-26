#!/usr/bin/env python3
"""Closed Codex release activation and exact previous-release rollback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA = "codex-release-stage-v1"
RESULT_SCHEMA = "codex-update-activate-v1"
ROLLBACK_RESULT_SCHEMA = "codex-update-rollback-v1"
WORKER_ID = "ax42-01"
REQUEST_FIELDS = {
    "operation", "planId", "candidateId", "authorizationId", "idempotencyKey",
}
RESULT_FIELDS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "authorizationId", "idempotencyKey", "state", "codexVersion",
    "releaseDigestSha256", "catalogRevision", "schemaComparison",
    "focusedContracts", "workerHealth", "canary", "currentBeforeFingerprint",
    "previousBeforeFingerprint", "currentAfterFingerprint",
    "previousAfterFingerprint", "automaticRestore", "valuesExposed",
}
ROLLBACK_REQUEST_FIELDS = {
    "operation", "planId", "candidateId", "activationId", "authorizationId",
    "idempotencyKey",
}
ROLLBACK_RESULT_FIELDS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "activationId", "authorizationId", "idempotencyKey", "state",
    "linkRestore", "workerServiceRestart", "affectedServices",
    "appServerServicesRestarted", "currentBeforeFingerprint",
    "previousBeforeFingerprint", "currentAfterFingerprint",
    "previousAfterFingerprint", "valuesExposed",
}
RESTART_SERVICE = "atenea-agent-run-worker-v1.service"
DIGEST = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ActivationError(RuntimeError):
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
        raise ActivationError(f"{field} must be a UUID")
    try:
        parsed = str(uuid.UUID(value))
    except ValueError as error:
        raise ActivationError(f"{field} must be a UUID") from error
    if parsed != value:
        raise ActivationError(f"{field} must be a canonical UUID")
    return value


def read_request() -> dict[str, str]:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ActivationError("request must be valid JSON") from error
    if not isinstance(request, dict):
        raise ActivationError("request must be a JSON object")
    if set(request) == REQUEST_FIELDS and request.get("operation") == "ACTIVATE_CODEX_UPDATE":
        identities = ("planId", "candidateId", "authorizationId", "idempotencyKey")
    elif (set(request) == ROLLBACK_REQUEST_FIELDS
          and request.get("operation") == "ROLLBACK_CODEX_UPDATE"):
        identities = (
            "planId", "candidateId", "activationId", "authorizationId", "idempotencyKey",
        )
    else:
        raise ActivationError("exact activation or rollback request fields are required")
    return {
        "operation": request["operation"],
        **{field: require_uuid(request.get(field), field) for field in identities},
    }


def owned_regular(path: Path, owner_uid: int, description: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ActivationError(f"{description} is unavailable") from error
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner_uid
            or metadata.st_mode & 0o022):
        raise ActivationError(f"{description} ownership is unsafe")
    return metadata


def owned_directory(path: Path, owner_uid: int, description: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ActivationError(f"{description} is unavailable") from error
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != owner_uid
            or metadata.st_mode & 0o022):
        raise ActivationError(f"{description} ownership is unsafe")


def read_registry(path: Path, owner_uid: int) -> dict[str, Any]:
    owned_regular(path, owner_uid, "release registry")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ActivationError("release registry is invalid") from error
    if not isinstance(registry, dict) or set(registry) != {
        "schemaVersion", "workerId", "candidates"
    }:
        raise ActivationError("release registry fields are invalid")
    if registry["schemaVersion"] != REGISTRY_SCHEMA or registry["workerId"] != WORKER_ID:
        raise ActivationError("release registry identity is invalid")
    return registry


def candidate_for(registry: dict[str, Any], request: dict[str, str]) -> dict[str, str]:
    candidate = registry.get("candidates", {}).get(request["candidateId"])
    fields = {
        "planId", "candidateId", "codexVersion", "releaseDigestSha256",
        "catalogRevision",
    }
    if not isinstance(candidate, dict) or set(candidate) != fields:
        raise ActivationError("candidate is not registered exactly")
    if (candidate["planId"] != request["planId"]
            or candidate["candidateId"] != request["candidateId"]):
        raise ActivationError("candidate ownership does not match the plan")
    if not isinstance(candidate["codexVersion"], str) or not VERSION.fullmatch(candidate["codexVersion"]):
        raise ActivationError("candidate version is invalid")
    if any(not isinstance(candidate[field], str) or not DIGEST.fullmatch(candidate[field])
           for field in ("releaseDigestSha256", "catalogRevision")):
        raise ActivationError("candidate digest identity is invalid")
    return candidate


def link_state(link: Path, releases: Path) -> tuple[str, str, str]:
    if not link.is_symlink():
        raise ActivationError(f"required {link.name} link is unavailable")
    raw = os.readlink(link)
    resolved = link.resolve(strict=True)
    try:
        resolved.relative_to(releases.resolve(strict=True))
    except ValueError as error:
        raise ActivationError(f"{link.name} link escapes the release root") from error
    if not resolved.is_dir() or resolved.is_symlink():
        raise ActivationError(f"{link.name} link target is invalid")
    fingerprint = digest_bytes(canonical_bytes({
        "link": link.name, "target": raw, "release": resolved.name,
    }))
    return raw, resolved.name, fingerprint


def replace_link(link: Path, raw_target: str) -> None:
    temporary = link.parent / ("." + link.name + "." + str(uuid.uuid4()))
    try:
        os.symlink(raw_target, temporary)
        os.replace(temporary, link)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def find_accepted_stage(operations: Path, request: dict[str, str], candidate: dict[str, str], owner_uid: int) -> None:
    accepted: dict[str, Any] | None = None
    for operation_path in operations.glob("*.json"):
        owned_regular(operation_path, owner_uid, "stage operation record")
        try:
            operation = json.loads(operation_path.read_text(encoding="utf-8"))
            result = operation["result"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ActivationError("stage operation record is invalid") from error
        if (not isinstance(result, dict) or result.get("state") != "STAGED"
                or result.get("planId") != request["planId"]
                or result.get("candidateId") != request["candidateId"]):
            continue
        if not (result.get("codexVersion") == candidate["codexVersion"]
                and result.get("releaseDigestSha256") == candidate["releaseDigestSha256"]
                and result.get("catalogRevision") == candidate["catalogRevision"]
                and result.get("releaseVerification") == "PASS"
                and result.get("schemaGeneration") == "PASS"
                and result.get("retention") == "PASS"
                and result.get("linksChanged") is False
                and result.get("valuesExposed") is False):
            raise ActivationError("stage operation conflicts with the candidate")
        normalized = {key: value for key, value in result.items()
                      if key != "idempotencyKey"}
        if accepted is not None and normalized != accepted:
            raise ActivationError("stage operation results conflict")
        accepted = normalized
    if accepted is None:
        raise ActivationError("an accepted stage operation is required")


def validate_schemas(release: Path, version: str, owner_uid: int) -> None:
    for name in ("app-server.schema.json", "cli.schema.json"):
        schema = release / "generated-schemas" / name
        owned_regular(schema, owner_uid, f"generated {name}")
        try:
            value = json.loads(schema.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ActivationError(f"generated {name} is invalid") from error
        if not isinstance(value, dict) or value.get("x-codex-version") != version:
            raise ActivationError(f"generated {name} does not match candidate")


def run_gate(release: Path, name: str, owner_uid: int, timeout: int) -> None:
    executable = release / "bin" / name
    metadata = owned_regular(executable, owner_uid, f"{name} gate")
    if not metadata.st_mode & stat.S_IXUSR:
        raise ActivationError(f"{name} gate is not executable")
    try:
        completed = subprocess.run(
            [str(executable)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ActivationError(f"{name} gate failed closed") from error
    if completed.returncode != 0:
        raise ActivationError(f"{name} gate failed closed")


def persist(path: Path, value: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".activation-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def accepted_activation(
        activations: Path, request: dict[str, str], owner_uid: int) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for operation_path in activations.glob("*.json"):
        owned_regular(operation_path, owner_uid, "activation operation record")
        try:
            operation = json.loads(operation_path.read_text(encoding="utf-8"))
            result = operation["result"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ActivationError("activation operation record is invalid") from error
        if (isinstance(result, dict) and set(result) == RESULT_FIELDS
                and result.get("state") == "ACTIVATED"
                and result.get("planId") == request["planId"]
                and result.get("candidateId") == request["candidateId"]
                and result.get("valuesExposed") is False):
            matches.append(result)
    if len(matches) != 1:
        raise ActivationError("exactly one accepted activation operation is required")
    return matches[0]


def schedule_restart(args: argparse.Namespace, request: dict[str, str]) -> None:
    owned_regular(args.restart_scheduler, args.registry_owner_uid, "restart scheduler")
    if not os.access(args.restart_scheduler, os.X_OK):
        raise ActivationError("restart scheduler is not executable")
    try:
        completed = subprocess.run(
            [str(args.restart_scheduler), request["idempotencyKey"], RESTART_SERVICE],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ActivationError("exact worker restart scheduling failed closed") from error
    if completed.returncode != 0:
        raise ActivationError("exact worker restart scheduling failed closed")


def rollback(args: argparse.Namespace, request: dict[str, str]) -> dict[str, Any]:
    owned_directory(args.release_root, args.registry_owner_uid, "release root")
    releases = args.release_root / "releases"
    activations = args.release_root / "activations"
    rollbacks = args.release_root / "rollbacks"
    owned_directory(releases, args.release_owner_uid, "release directory")
    owned_directory(activations, args.registry_owner_uid, "activation operation directory")
    owned_directory(rollbacks, args.registry_owner_uid, "rollback operation directory")
    activation = accepted_activation(activations, request, args.registry_owner_uid)
    request_fingerprint = digest_bytes(canonical_bytes(request))
    operation_path = rollbacks / (request["idempotencyKey"] + ".json")

    if operation_path.exists():
        owned_regular(operation_path, args.registry_owner_uid, "rollback operation record")
        persisted = json.loads(operation_path.read_text(encoding="utf-8"))
        if (not isinstance(persisted, dict)
                or set(persisted) != {"requestFingerprint", "result"}
                or persisted.get("requestFingerprint") != request_fingerprint
                or not isinstance(persisted.get("result"), dict)
                or set(persisted["result"]) != ROLLBACK_RESULT_FIELDS):
            raise ActivationError("persisted rollback operation is invalid or conflicting")
        result = persisted["result"]
        if result.get("state") == "ROLLED_BACK" and result.get("workerServiceRestart") == "PASS":
            return result
        if result.get("state") != "LINKS_RESTORED" or result.get("workerServiceRestart") != "PENDING":
            raise ActivationError("persisted rollback operation state is invalid")
    else:
        current = args.release_root / "current"
        previous = args.release_root / "previous"
        current_raw, _current_name, current_before = link_state(current, releases)
        previous_raw, _previous_name, previous_before = link_state(previous, releases)
        if (current_before != activation["currentAfterFingerprint"]
                or previous_before != activation["previousAfterFingerprint"]):
            raise ActivationError("current and previous links do not match the exact activation")
        try:
            replace_link(current, previous_raw)
            replace_link(previous, current_raw)
        except OSError as error:
            replace_link(current, current_raw)
            replace_link(previous, previous_raw)
            if (link_state(current, releases)[2] != current_before
                    or link_state(previous, releases)[2] != previous_before):
                raise ActivationError("failed rollback link restoration failed closed") from error
            raise ActivationError("exact rollback link swap failed closed") from error
        current_after_raw, _current_after_name, current_after = link_state(current, releases)
        previous_after_raw, _previous_after_name, previous_after = link_state(previous, releases)
        if current_after_raw != previous_raw or previous_after_raw != current_raw:
            raise ActivationError("exact rollback link swap is conflicting")
        result = {
            "schemaVersion": ROLLBACK_RESULT_SCHEMA,
            "operation": request["operation"],
            "workerId": WORKER_ID,
            "planId": request["planId"],
            "candidateId": request["candidateId"],
            "activationId": request["activationId"],
            "authorizationId": request["authorizationId"],
            "idempotencyKey": request["idempotencyKey"],
            "state": "LINKS_RESTORED",
            "linkRestore": "PASS",
            "workerServiceRestart": "PENDING",
            "affectedServices": [RESTART_SERVICE],
            "appServerServicesRestarted": 0,
            "currentBeforeFingerprint": current_before,
            "previousBeforeFingerprint": previous_before,
            "currentAfterFingerprint": current_after,
            "previousAfterFingerprint": previous_after,
            "valuesExposed": False,
        }
        persist(operation_path, {"requestFingerprint": request_fingerprint, "result": result})

    schedule_restart(args, request)
    result = {**result, "state": "ROLLED_BACK", "workerServiceRestart": "PASS"}
    persist(operation_path, {"requestFingerprint": request_fingerprint, "result": result})
    return result


def activate(args: argparse.Namespace, request: dict[str, str]) -> dict[str, Any]:
    registry = read_registry(args.registry, args.registry_owner_uid)
    candidate = candidate_for(registry, request)
    owned_directory(args.release_root, args.registry_owner_uid, "release root")
    releases = args.release_root / "releases"
    operations = args.release_root / "operations"
    activations = args.release_root / "activations"
    owned_directory(releases, args.release_owner_uid, "release directory")
    owned_directory(operations, args.release_owner_uid, "stage operation directory")
    owned_directory(activations, args.registry_owner_uid, "activation operation directory")

    request_fingerprint = digest_bytes(canonical_bytes(request))
    operation_path = activations / (request["idempotencyKey"] + ".json")
    if operation_path.exists():
        owned_regular(operation_path, args.registry_owner_uid, "activation operation record")
        persisted = json.loads(operation_path.read_text(encoding="utf-8"))
        if (not isinstance(persisted, dict)
                or set(persisted) != {"requestFingerprint", "result"}
                or persisted["requestFingerprint"] != request_fingerprint
                or not isinstance(persisted["result"], dict)
                or set(persisted["result"]) != RESULT_FIELDS):
            raise ActivationError("persisted activation operation is invalid or conflicting")
        return persisted["result"]

    find_accepted_stage(operations, request, candidate, args.release_owner_uid)
    release_name = candidate["codexVersion"] + "-" + candidate["releaseDigestSha256"][:16]
    release = releases / release_name
    owned_directory(release, args.release_owner_uid, "staged candidate release")
    validate_schemas(release, candidate["codexVersion"], args.release_owner_uid)
    current = args.release_root / "current"
    previous = args.release_root / "previous"
    current_raw, current_name, current_before = link_state(current, releases)
    previous_raw, _previous_name, previous_before = link_state(previous, releases)
    if current_name == release_name:
        raise ActivationError("candidate is already current without this activation identity")

    run_gate(release, "run-focused-contracts", args.release_owner_uid, 120)
    replace_link(previous, current_raw)
    replace_link(current, "releases/" + release_name)
    try:
        run_gate(release, "health-check", args.release_owner_uid, 30)
        run_gate(release, "run-canary", args.release_owner_uid, 120)
    except ActivationError:
        replace_link(current, current_raw)
        replace_link(previous, previous_raw)
        if (link_state(current, releases)[2] != current_before
                or link_state(previous, releases)[2] != previous_before):
            raise ActivationError("automatic restoration failed closed")
        raise

    current_after = link_state(current, releases)[2]
    previous_after = link_state(previous, releases)[2]
    result: dict[str, Any] = {
        "schemaVersion": RESULT_SCHEMA,
        "operation": request["operation"],
        "workerId": WORKER_ID,
        "planId": request["planId"],
        "candidateId": request["candidateId"],
        "authorizationId": request["authorizationId"],
        "idempotencyKey": request["idempotencyKey"],
        "state": "ACTIVATED",
        "codexVersion": candidate["codexVersion"],
        "releaseDigestSha256": candidate["releaseDigestSha256"],
        "catalogRevision": candidate["catalogRevision"],
        "schemaComparison": "PASS",
        "focusedContracts": "PASS",
        "workerHealth": "PASS",
        "canary": "PASS",
        "currentBeforeFingerprint": current_before,
        "previousBeforeFingerprint": previous_before,
        "currentAfterFingerprint": current_after,
        "previousAfterFingerprint": previous_after,
        "automaticRestore": "NOT_REQUIRED",
        "valuesExposed": False,
    }
    persist(operation_path, {"requestFingerprint": request_fingerprint, "result": result})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--registry-owner-uid", type=int, default=0)
    parser.add_argument("--release-owner-uid", type=int, required=True)
    parser.add_argument(
        "--restart-scheduler", type=Path,
        default=Path("/usr/local/libexec/atenea/codex-release-restart-v1.sh"),
    )
    args = parser.parse_args()
    try:
        request = read_request()
        result = (activate(args, request) if request["operation"] == "ACTIVATE_CODEX_UPDATE"
                  else rollback(args, request))
    except (ActivationError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": "activation_rejected", "message": str(error)},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
