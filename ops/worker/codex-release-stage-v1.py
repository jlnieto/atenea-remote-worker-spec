#!/usr/bin/env python3
"""Closed, idempotent Codex release staging mediator.

The caller supplies only persisted plan/candidate/idempotency identities. All
release, filesystem and command authority is resolved from a root-owned
registry and fixed roots selected by the installed service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "codex-release-stage-v1"
RESULT_SCHEMA_VERSION = "codex-update-stage-v1"
WORKER_ID = "ax42-01"
REQUEST_FIELDS = {"operation", "planId", "candidateId", "idempotencyKey"}
RESULT_FIELDS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "idempotencyKey", "state", "codexVersion", "releaseDigestSha256",
    "catalogRevision", "releaseManifestSha256", "schemaManifestSha256",
    "releaseVerification", "schemaGeneration", "retention",
    "currentLinkFingerprint", "previousLinkFingerprint", "linksChanged",
    "valuesExposed",
}
DIGEST = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096


class StageError(RuntimeError):
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
        raise StageError(f"{field} must be a UUID")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise StageError(f"{field} must be a UUID") from error
    if str(parsed) != value.lower():
        raise StageError(f"{field} must be a canonical UUID")
    return value.lower()


def read_request() -> dict[str, str]:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise StageError("request must be valid JSON") from error
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise StageError("exact stage request fields are required")
    if request.get("operation") != "STAGE_CODEX_UPDATE":
        raise StageError("stage operation is required")
    return {
        "operation": "STAGE_CODEX_UPDATE",
        "planId": require_uuid(request.get("planId"), "planId"),
        "candidateId": require_uuid(request.get("candidateId"), "candidateId"),
        "idempotencyKey": require_uuid(request.get("idempotencyKey"), "idempotencyKey"),
    }


def safe_owned_regular(path: Path, owner_uid: int, description: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise StageError(f"{description} is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner_uid or metadata.st_mode & 0o022:
        raise StageError(f"{description} ownership is unsafe")


def safe_owned_directory(path: Path, owner_uid: int, description: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise StageError(f"{description} is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != owner_uid or metadata.st_mode & 0o022:
        raise StageError(f"{description} ownership is unsafe")


def read_registry(path: Path, owner_uid: int) -> dict[str, Any]:
    safe_owned_regular(path, owner_uid, "release registry")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StageError("release registry is invalid") from error
    if not isinstance(registry, dict) or set(registry) != {
        "schemaVersion", "workerId", "candidates"
    }:
        raise StageError("release registry fields are invalid")
    if registry["schemaVersion"] != SCHEMA_VERSION or registry["workerId"] != WORKER_ID:
        raise StageError("release registry identity is invalid")
    if not isinstance(registry["candidates"], dict):
        raise StageError("release registry candidates are invalid")
    return registry


def candidate_for(registry: dict[str, Any], request: dict[str, str]) -> dict[str, str]:
    candidate = registry["candidates"].get(request["candidateId"])
    fields = {
        "planId", "candidateId", "codexVersion", "releaseDigestSha256",
        "catalogRevision",
    }
    if not isinstance(candidate, dict) or set(candidate) != fields:
        raise StageError("candidate is not registered exactly")
    if candidate.get("planId") != request["planId"] or candidate.get("candidateId") != request["candidateId"]:
        raise StageError("candidate ownership does not match the plan")
    if not isinstance(candidate.get("codexVersion"), str) or not VERSION.fullmatch(candidate["codexVersion"]):
        raise StageError("candidate version is invalid")
    for field in ("releaseDigestSha256", "catalogRevision"):
        if not isinstance(candidate.get(field), str) or not DIGEST.fullmatch(candidate[field]):
            raise StageError(f"candidate {field} is invalid")
    return candidate


def fixed_child(root: Path, name: str) -> Path:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise StageError("derived release path is invalid")
    return root / name


def link_fingerprint(link: Path, releases_root: Path) -> str:
    if not link.is_symlink():
        raise StageError(f"required {link.name} link is unavailable")
    raw_target = os.readlink(link)
    resolved = link.resolve(strict=True)
    try:
        resolved.relative_to(releases_root.resolve(strict=True))
    except ValueError as error:
        raise StageError(f"{link.name} link escapes the release root") from error
    if not resolved.is_dir():
        raise StageError(f"{link.name} link target is invalid")
    return digest_bytes(canonical_bytes({"link": link.name, "target": raw_target,
                                         "release": resolved.name}))


def validate_archive_member(member: tarfile.TarInfo) -> None:
    member_path = Path(member.name)
    if member_path.is_absolute() or ".." in member_path.parts or not member_path.parts:
        raise StageError("release archive contains an unsafe path")
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise StageError("release archive contains an unsafe member type")
    if not (member.isdir() or member.isfile()):
        raise StageError("release archive contains an unsupported member")


def extract_verified(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            members = bundle.getmembers()
            if not members or len(members) > MAX_ARCHIVE_MEMBERS:
                raise StageError("release archive member count is outside policy")
            total = 0
            for member in members:
                validate_archive_member(member)
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise StageError("release archive expanded size is outside policy")
            bundle.extractall(destination, members=members, filter="data")
    except (OSError, tarfile.TarError) as error:
        raise StageError("release archive cannot be extracted") from error


def validate_generated_schemas(output: Path, version: str) -> str:
    if not output.is_dir() or output.is_symlink():
        raise StageError("generated schema directory is invalid")
    manifest: dict[str, str] = {}
    for name in ("app-server.schema.json", "cli.schema.json"):
        schema = output / name
        safe_owned_regular(schema, os.geteuid(), f"generated {name}")
        try:
            parsed = json.loads(schema.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StageError(f"generated {name} is invalid") from error
        if not isinstance(parsed, dict) or parsed.get("x-codex-version") != version:
            raise StageError(f"generated {name} does not match the candidate version")
        manifest[name] = digest_file(schema)
    return digest_bytes(canonical_bytes(manifest))


def generate_schemas(release: Path, output: Path, version: str) -> str:
    generator = release / "bin" / "generate-schemas"
    safe_owned_regular(generator, os.geteuid(), "version-matched schema generator")
    if not os.access(generator, os.X_OK):
        raise StageError("version-matched schema generator is not executable")
    if output.exists():
        return validate_generated_schemas(output, version)
    output.mkdir(mode=0o700)
    try:
        completed = subprocess.run(
            [str(generator), str(output)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StageError("version-matched schema generation failed closed") from error
    if completed.returncode != 0:
        raise StageError("version-matched schema generation failed closed")
    for name in ("app-server.schema.json", "cli.schema.json"):
        schema = output / name
        try:
            metadata = schema.lstat()
        except OSError as error:
            raise StageError(f"generated {name} is unavailable") from error
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise StageError(f"generated {name} ownership is unsafe")
        schema.chmod(0o600)
    return validate_generated_schemas(output, version)


def release_manifest(release: Path) -> str:
    entries: list[dict[str, Any]] = []
    for path in sorted(release.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(release).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise StageError("staged release contains a symbolic link")
        if stat.S_ISDIR(metadata.st_mode):
            entries.append({"path": relative, "type": "directory"})
        elif stat.S_ISREG(metadata.st_mode):
            entries.append({"path": relative, "type": "file", "sha256": digest_file(path),
                            "executable": bool(metadata.st_mode & 0o111)})
        else:
            raise StageError("staged release contains an unsupported file type")
    return digest_bytes(canonical_bytes(entries))


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise StageError("persisted stage result is invalid")
    return value


def stage(args: argparse.Namespace, request: dict[str, str]) -> dict[str, Any]:
    registry = read_registry(args.registry, args.registry_owner_uid)
    candidate = candidate_for(registry, request)
    safe_owned_directory(args.release_root, args.registry_owner_uid, "release root")
    releases = args.release_root / "releases"
    inbox = args.release_root / "inbox"
    operations = args.release_root / "operations"
    safe_owned_directory(inbox, args.registry_owner_uid, "release inbox")
    safe_owned_directory(releases, os.geteuid(), "release directory")
    safe_owned_directory(operations, os.geteuid(), "stage operation directory")

    request_fingerprint = digest_bytes(canonical_bytes(request))
    operation_path = fixed_child(operations, request["idempotencyKey"] + ".json")
    if operation_path.exists():
        safe_owned_regular(operation_path, os.geteuid(), "stage operation record")
        persisted = json.loads(operation_path.read_text(encoding="utf-8"))
        if not isinstance(persisted, dict) or set(persisted) != {"requestFingerprint", "result"}:
            raise StageError("persisted stage operation is invalid")
        if persisted["requestFingerprint"] != request_fingerprint:
            raise StageError("idempotency key belongs to a different stage request")
        return validate_result(persisted["result"])

    archive = fixed_child(inbox, request["candidateId"] + ".tar.gz")
    safe_owned_regular(archive, args.registry_owner_uid, "registered release archive")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise StageError("registered release archive is outside size policy")
    if digest_file(archive) != candidate["releaseDigestSha256"]:
        raise StageError("registered release digest does not match")

    current_before = link_fingerprint(args.release_root / "current", releases)
    previous_before = link_fingerprint(args.release_root / "previous", releases)
    release_name = candidate["codexVersion"] + "-" + candidate["releaseDigestSha256"][:16]
    target = fixed_child(releases, release_name)

    if target.exists():
        if not target.is_dir() or target.is_symlink():
            raise StageError("staged release target is ambiguous")
        generated = target / "generated-schemas"
        schema_manifest = generate_schemas(target, generated, candidate["codexVersion"])
        manifest = release_manifest(target)
    else:
        temporary = Path(tempfile.mkdtemp(prefix=".stage-", dir=releases))
        try:
            extract_verified(archive, temporary)
            schema_manifest = generate_schemas(
                temporary, temporary / "generated-schemas", candidate["codexVersion"]
            )
            manifest = release_manifest(temporary)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    current_after = link_fingerprint(args.release_root / "current", releases)
    previous_after = link_fingerprint(args.release_root / "previous", releases)
    if current_after != current_before or previous_after != previous_before:
        raise StageError("staging changed a canonical release link")

    result: dict[str, Any] = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "operation": "STAGE_CODEX_UPDATE",
        "workerId": WORKER_ID,
        "planId": request["planId"],
        "candidateId": request["candidateId"],
        "idempotencyKey": request["idempotencyKey"],
        "state": "STAGED",
        "codexVersion": candidate["codexVersion"],
        "releaseDigestSha256": candidate["releaseDigestSha256"],
        "catalogRevision": candidate["catalogRevision"],
        "releaseManifestSha256": manifest,
        "schemaManifestSha256": schema_manifest,
        "releaseVerification": "PASS",
        "schemaGeneration": "PASS",
        "retention": "PASS",
        "currentLinkFingerprint": current_after,
        "previousLinkFingerprint": previous_after,
        "linksChanged": False,
        "valuesExposed": False,
    }
    operation = {"requestFingerprint": request_fingerprint, "result": result}
    descriptor, temporary_name = tempfile.mkstemp(prefix=".operation-", dir=operations)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(operation))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, operation_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--registry-owner-uid", type=int, default=0)
    args = parser.parse_args()
    try:
        result = stage(args, read_request())
    except (StageError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": "stage_rejected", "message": str(error)},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
