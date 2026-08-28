#!/usr/bin/env python3
"""Root-owned exact Atenea Codex runner; accepts one closed JSON contract."""

from __future__ import annotations

import argparse
import contextlib
import grp
import hashlib
import json
import os
import pwd
import re
import signal
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

CAPABILITY = "project-codex-v1"
PROFILED_CAPABILITY = "project-codex-v2"
IMAGE_CAPABILITY = "project-codex-v3"
CHANGE_CAPABILITY = "project-codex-v4"
CODEX_VERSION = "0.145.0"
CODEX_MODEL = "gpt-5.6-sol"
CODEX_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
PROJECT_ID = "atenea"
REPOSITORY = "https://github.com/jlnieto/atenea.git"
BRANCH = "main"
BASE_COMMIT: str | None = None
MANIFEST_SHA256 = "327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b"
CODEX = "/home/jose/.codex/packages/standalone/current/bin/codex"
GIT_COMMON_DIR = Path("/srv/atenea/repositories/atenea.git")
CHANGE_WORKSPACE_PARENT = Path("/srv/atenea/workspaces/changes")
CHANGE_WORKSPACE_OWNER = "atenea-worker"
CHANGE_WORKSPACE_GROUP = "atenea"
INSTRUCTION_BUNDLE_REVISION = "atenea-reviewed-instruction-bundle-v1"
PLATFORM_INSTRUCTION_PATH = Path(
    "/usr/local/share/atenea/codex-platform-instructions-v1.md"
)
PLATFORM_INSTRUCTION_UID = 0
PLATFORM_INSTRUCTION_SHA256 = (
    "44c578a286eb50b35612be0b6c38d59a503e6fee1ecf6cd0339415af018cdf0d"
)
PROJECT_INSTRUCTION_PATH = "AGENTS.md"
PROJECT_INSTRUCTION_SHA256 = (
    "a09adc5855ff54490211a0f5c82f413cb84ee7197b2b350e0b0dc40eba7c98dc"
)
INSTRUCTION_BUNDLE_SHA256 = (
    "ab9f1877c83333945497797e6b8aefd20f67debf8e3bdc6d1b824fc5a3f86c04"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUEST_KEYS = {"dispatchId", "executionId", "sessionId", "workspaceIdentity", "workload"}
CHANGE_REQUEST_KEYS = REQUEST_KEYS | {"changeOwnership"}
WORKLOAD_KEYS = {
    "kind", "projectId", "repository", "branch", "commit",
    "manifestSha256", "message", "threadId", "instructionBundleRevision",
    "instructionBundleSha256", "platformInstructionSha256",
    "projectInstructionPath", "projectInstructionSha256",
}
PROFILED_WORKLOAD_KEYS = WORKLOAD_KEYS | {
    "modelId", "reasoningEffort", "catalogRevision", "codexVersion",
}
IMAGE_WORKLOAD_KEYS = PROFILED_WORKLOAD_KEYS | {"attachments"}
CHANGE_WORKLOAD_KEYS = {
    "kind", "projectId", "repository", "branch", "commit", "message", "threadId",
    "modelId", "reasoningEffort", "catalogRevision", "codexVersion", "attachments",
}
CHANGE_OWNERSHIP_KEYS = {
    "changeKey", "databaseWorkSessionId", "remoteSessionId",
    "workspaceIdentity", "databaseProjectId", "baseCommit",
    "expectedCanonicalCommit", "sourceRevision",
    "sourceFingerprintSha256", "workspaceOwnershipFingerprintSha256",
}
CHANGE_WORKSPACE_RECORD_KEYS = {
    "schemaVersion", "protocolVersion", "changeKey", "databaseProjectId",
    "projectId", "repository", "repositoryBranch", "baseCommit",
    "workspaceBranch", "workspaceIdentity", "workerId",
    "initialSourceFingerprintSha256", "recordSha256",
}
ATTACHMENT_REFERENCE_KEYS = {"attachmentId", "contentType", "sizeBytes", "sha256"}
ATTACHMENT_METADATA_KEYS = {
    "protocolVersion", "workerId", "sessionId", "attachmentId",
    "storageIdentity", "source", "kind", "contentType", "sizeBytes",
    "retentionClass", "sha256", "syntheticFixture", "createdAt", "storedAt",
    "projectIdentity", "workspaceIdentity", "storageScope",
}
ATTACHMENT_ROOT = Path("/srv/atenea/attachments-v1")
ATTACHMENT_WORKER_ID = "ax42-01"
ATTACHMENT_OWNER = "atenea-worker"
ATTACHMENT_GROUP = "atenea"
ATTACHMENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENT_TOTAL_BYTES = 32 * 1024 * 1024
MAX_CHANGE_FINGERPRINT_BYTES = 64 * 1024 * 1024
MATERIALIZATION_ROOT = Path("/run/atenea/codex-images")
TERMINAL_EXECUTION_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}
NON_TERMINAL_EXECUTION_STATES = {
    "QUEUED", "STARTING", "RUNNING", "CANCELLING", "RECONCILING",
}
MATERIALIZED_NAME = re.compile(
    r"^(?P<position>0[1-4])-(?P<attachment>[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})"
    r"(?P<extension>\.png|\.jpg|\.webp)$"
)
CODEX_CATALOG_REVISION = (
    "125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187"
)
SAFE_PROGRESS_MESSAGES = {
    "CODEX_STARTED": "Codex started the accepted turn.",
    "INSPECTING_PROJECT": "Inspecting the accepted project.",
    "RUNNING_COMMAND": "Running a reviewed project operation.",
    "CHECKING": "Checking the accepted project.",
    "WAITING": "Waiting for a bounded operation.",
    "FINALIZING": "Finalizing the Codex turn.",
}


class VerifiedAttachment(NamedTuple):
    attachment_id: str
    content_type: str
    size_bytes: int
    sha256: str
    content_path: Path


class MaterializedAttachment(NamedTuple):
    attachment_id: str
    content_type: str
    path: Path
    device: int
    inode: int
    size_bytes: int
    sha256: str


class ReviewedInstructionBundle(NamedTuple):
    developer_instructions: str
    project_bytes: bytes


class InstructionProjection(NamedTuple):
    ambient_mask: Path
    project_source: Path


class ChangeSourceObservation(NamedTuple):
    common_dir: Path
    source_fingerprint_sha256: str
    workspace_ownership_fingerprint_sha256: str
    workspace_dirty: bool


def reject(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def codex_failure_reason(stderr: str) -> str:
    lowered = stderr.lower()
    categories = (
        (("permission denied", "read-only file system", "operation not permitted",
          "can't find source path"),
         "Codex execution failed: filesystem boundary"),
        (("not logged in", "authentication", "unauthorized"),
         "Codex execution failed: authentication unavailable"),
        (("unknown argument", "unexpected argument", "invalid value"),
         "Codex execution failed: CLI contract"),
        (("failed to lookup address", "connection", "dns", "request failed"),
         "Codex execution failed: network unavailable"),
        (("thread", "session", "state database", "database is locked"),
         "Codex execution failed: thread persistence unavailable"),
    )
    for needles, reason in categories:
        if any(needle in lowered for needle in needles):
            return reason
    return "Codex execution failed: unclassified"


def validate_codex_version(workload: dict[str, Any]) -> None:
    if workload["kind"] not in {
        PROFILED_CAPABILITY, IMAGE_CAPABILITY, CHANGE_CAPABILITY,
    }:
        return
    try:
        observed = subprocess.run(
            [CODEX, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        reject("Codex execution failed: CLI contract")
    if observed != "codex-cli " + workload["codexVersion"]:
        reject("Codex execution failed: CLI contract")


def effective_profile(workload: dict[str, Any]) -> dict[str, str]:
    if workload["kind"] not in {
        PROFILED_CAPABILITY, IMAGE_CAPABILITY, CHANGE_CAPABILITY,
    }:
        return {}
    return {
        key: workload[key]
        for key in ("modelId", "reasoningEffort", "catalogRevision", "codexVersion")
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_codex_events(stream: str) -> list[dict[str, str]]:
    """Map only recognized structure to fixed text; discard every payload value."""
    normalized: list[dict[str, str]] = []

    def append(category: str) -> None:
        message = SAFE_PROGRESS_MESSAGES[category]
        if normalized and normalized[-1]["category"] == category and normalized[-1]["message"] == message:
            return
        normalized.append({
            "category": category,
            "occurredAt": utc_now(),
            "message": message,
        })
        if len(normalized) > 200:
            del normalized[:-200]

    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type in {"thread.started", "turn.started"}:
            append("CODEX_STARTED")
            continue
        if event_type == "turn.completed":
            append("FINALIZING")
            continue
        if event_type in {"turn.failed", "error"}:
            continue
        if event_type not in {"item.started", "item.completed"}:
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"reasoning", "agent_message"}:
            continue
        category = {
            "web_search": "INSPECTING_PROJECT",
            "command_execution": "RUNNING_COMMAND",
            "mcp_tool_call": "CHECKING",
            "file_change": "CHECKING",
            "todo_list": "CHECKING",
        }.get(item_type)
        if category is not None:
            append(category)
    return normalized


def internal_failure_reason(exception: Exception) -> str:
    allowed = {
        "AttributeError",
        "FileNotFoundError",
        "OSError",
        "PermissionError",
        "TypeError",
        "UnboundLocalError",
        "ValueError",
    }
    name = type(exception).__name__
    return "Project runner internal exception: " + (name if name in allowed else "Other")


def load_json(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reject("project configuration rejected")
    if stat.st_uid != 0 or stat.st_mode & 0o022 or not isinstance(value, dict):
        reject("project configuration rejected")
    return value


def validate_config(
    config: dict[str, Any], runner: Path, require_execution: bool = True,
    legacy_registry_required: bool = True,
) -> None:
    legacy_fields = {
        "schemaVersion", "selectionEnabled", "executionEnabled",
        "projectId", "repository", "branch",
        "commit", "manifestSha256", "runner", "workspaces",
    }
    shared_fields = {
        "schemaVersion", "executionEnabled", "projectId", "repository", "branch", "runner",
    }
    allowed_fields = legacy_fields | ({"attachmentRoot"} if PROJECT_ID == "atenea" else set())
    required_fields = legacy_fields if legacy_registry_required else shared_fields
    exact = {
        "schemaVersion": CAPABILITY,
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "runner": str(runner),
    }
    if legacy_registry_required:
        exact["manifestSha256"] = MANIFEST_SHA256
    if (
        not required_fields.issubset(config)
        or not set(config).issubset(allowed_fields)
        or any(config.get(key) != value for key, value in exact.items())
        or (
            "attachmentRoot" in config
            and config.get("attachmentRoot") != str(ATTACHMENT_ROOT)
        )
        or (
            legacy_registry_required
            and (
                not isinstance(config.get("commit"), str)
                or COMMIT_PATTERN.fullmatch(config["commit"]) is None
                or (BASE_COMMIT is not None and config["commit"] != BASE_COMMIT)
                or config.get("selectionEnabled") is not True
                or not isinstance(config.get("workspaces"), dict)
            )
        )
        or not isinstance(config.get("executionEnabled"), bool)
        or (
            require_execution
            and config["executionEnabled"] is not True
        )
    ):
        reject("project configuration rejected")


def validate_request(request: Any, config: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    workload = request.get("workload") if isinstance(request, dict) else None
    capability = workload.get("kind") if isinstance(workload, dict) else None
    request_keys = CHANGE_REQUEST_KEYS if capability == CHANGE_CAPABILITY else REQUEST_KEYS
    if not isinstance(request, dict) or set(request) != request_keys:
        reject("workspace ownership rejected")
    for key in ("dispatchId", "executionId", "sessionId"):
        try:
            uuid.UUID(request[key])
        except (ValueError, TypeError, AttributeError):
            reject("workspace ownership rejected")
    if not isinstance(request["workspaceIdentity"], str):
        reject("workspace ownership rejected")
    allowed_capabilities = {CAPABILITY, PROFILED_CAPABILITY}
    if PROJECT_ID == "atenea":
        allowed_capabilities.update({IMAGE_CAPABILITY, CHANGE_CAPABILITY})
    workload_keys = (
        CHANGE_WORKLOAD_KEYS
        if capability == CHANGE_CAPABILITY
        else IMAGE_WORKLOAD_KEYS
        if capability == IMAGE_CAPABILITY
        else PROFILED_WORKLOAD_KEYS
        if capability == PROFILED_CAPABILITY
        else WORKLOAD_KEYS
    )
    exact = {
        "kind": capability,
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
    }
    if capability != CHANGE_CAPABILITY:
        exact.update({
            "manifestSha256": MANIFEST_SHA256, "instructionBundleRevision": INSTRUCTION_BUNDLE_REVISION,
            "instructionBundleSha256": INSTRUCTION_BUNDLE_SHA256, "platformInstructionSha256": PLATFORM_INSTRUCTION_SHA256,
            "projectInstructionPath": PROJECT_INSTRUCTION_PATH, "projectInstructionSha256": PROJECT_INSTRUCTION_SHA256,
        })
    if (
        not isinstance(workload, dict)
        or capability not in allowed_capabilities
        or set(workload) != workload_keys
        or any(workload.get(key) != value for key, value in exact.items())
        or (
            capability != CHANGE_CAPABILITY
            and workload.get("commit") != config["commit"]
        )
        or not isinstance(workload.get("message"), str)
        or not (1 <= len(workload["message"]) <= 20_000)
    ):
        reject("workspace ownership rejected")
    if capability in {PROFILED_CAPABILITY, IMAGE_CAPABILITY, CHANGE_CAPABILITY} and (
        workload.get("modelId") != CODEX_MODEL
        or workload.get("reasoningEffort") not in CODEX_EFFORTS
        or workload.get("catalogRevision") != CODEX_CATALOG_REVISION
        or workload.get("codexVersion") != CODEX_VERSION
    ):
        reject("workspace ownership rejected")
    thread_id = workload["threadId"]
    if thread_id is not None:
        try:
            uuid.UUID(thread_id)
        except (ValueError, TypeError, AttributeError):
            reject("workspace ownership rejected")
    if capability == CHANGE_CAPABILITY:
        ownership = request.get("changeOwnership")
        if not isinstance(ownership, dict) or set(ownership) != CHANGE_OWNERSHIP_KEYS:
            reject("workspace ownership rejected")
        for key in ("changeKey", "remoteSessionId"):
            try:
                canonical = str(uuid.UUID(ownership.get(key)))
            except (ValueError, TypeError, AttributeError):
                canonical = None
            if canonical != ownership.get(key):
                reject("workspace ownership rejected")
        change_key = ownership["changeKey"]
        expected_identity = f"remote:{ATTACHMENT_WORKER_ID}:change:{change_key}"
        if (
            ownership.get("remoteSessionId") != request["sessionId"]
            or ownership.get("workspaceIdentity") != request["workspaceIdentity"]
            or request["workspaceIdentity"] != expected_identity
            or ownership.get("expectedCanonicalCommit") != workload["commit"]
            or not isinstance(ownership.get("databaseProjectId"), int)
            or isinstance(ownership.get("databaseProjectId"), bool)
            or ownership["databaseProjectId"] < 1
            or not isinstance(ownership.get("databaseWorkSessionId"), int)
            or isinstance(ownership.get("databaseWorkSessionId"), bool)
            or ownership["databaseWorkSessionId"] < 1
            or not isinstance(ownership.get("sourceRevision"), int)
            or isinstance(ownership.get("sourceRevision"), bool)
            or ownership["sourceRevision"] < 0
            or COMMIT_PATTERN.fullmatch(str(ownership.get("baseCommit", ""))) is None
            or COMMIT_PATTERN.fullmatch(
                str(ownership.get("expectedCanonicalCommit", ""))
            ) is None
            or any(
                SHA256_PATTERN.fullmatch(str(ownership.get(key, ""))) is None
                for key in (
                    "sourceFingerprintSha256",
                    "workspaceOwnershipFingerprintSha256",
                )
            )
        ):
            reject("workspace ownership rejected")
        references = workload.get("attachments")
        if not isinstance(references, list) or len(references) > 4:
            reject("workspace ownership rejected")
        worktree = CHANGE_WORKSPACE_PARENT / change_key / PROJECT_ID
        if not worktree.is_dir() or worktree.is_symlink():
            reject("workspace ownership rejected")
        return workload, worktree

    record = config["workspaces"].get(request["workspaceIdentity"])
    record_keys = {"sessionId", "worktree", "allocationSha256"}
    if BASE_COMMIT is None:
        record_keys.add("canonicalCommit")
    if (
        not isinstance(record, dict)
        or set(record) != record_keys
        or record["sessionId"] != request["sessionId"]
        or not isinstance(record["allocationSha256"], str)
        or len(record["allocationSha256"]) != 64
        or (BASE_COMMIT is None and record["canonicalCommit"] != config["commit"])
    ):
        reject("workspace ownership rejected")
    expected = Path("/srv/atenea/workspaces/sessions") / request["sessionId"] / PROJECT_ID
    worktree = Path(record["worktree"])
    if worktree != expected or not worktree.is_dir() or worktree.is_symlink():
        reject("workspace ownership rejected")
    return workload, worktree


def attachment_owner_ids() -> tuple[int, int]:
    try:
        return pwd.getpwnam(ATTACHMENT_OWNER).pw_uid, grp.getgrnam(ATTACHMENT_GROUP).gr_gid
    except KeyError:
        reject("attachment ownership rejected")


def validate_owned_path(
    path: Path,
    expected_mode: int,
    expected_uid: int,
    expected_gid: int,
    directory: bool,
) -> os.stat_result:
    try:
        observed = path.lstat()
    except OSError:
        reject("attachment ownership rejected")
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected_type(observed.st_mode)
        or stat.S_IMODE(observed.st_mode) != expected_mode
        or observed.st_uid != expected_uid
        or observed.st_gid != expected_gid
        or (not directory and observed.st_nlink != 1)
    ):
        reject("attachment ownership rejected")
    return observed


def read_owned_file(
    path: Path,
    expected: os.stat_result,
    maximum_bytes: int,
) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        reject("attachment ownership rejected")
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or opened.st_size <= 0
            or opened.st_size > maximum_bytes
        ):
            reject("attachment ownership rejected")
        chunks = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        value = b"".join(chunks)
        if len(value) != opened.st_size or len(value) > maximum_bytes:
            reject("attachment ownership rejected")
        return value
    finally:
        os.close(descriptor)


def content_matches_type(content_type: str, prefix: bytes) -> bool:
    if content_type == "image/png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return prefix.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"
    return False


def validate_attachment_references(
    request: dict[str, Any],
    workload: dict[str, Any],
    config: dict[str, Any],
) -> list[VerifiedAttachment]:
    if workload["kind"] not in {IMAGE_CAPABILITY, CHANGE_CAPABILITY}:
        return []
    references = workload.get("attachments")
    minimum = 0 if workload["kind"] == CHANGE_CAPABILITY else 1
    if not isinstance(references, list) or not (minimum <= len(references) <= 4):
        reject("attachment ownership rejected")
    if not references:
        return []
    session_id = request["sessionId"]
    try:
        canonical_session = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        canonical_session = None
    if canonical_session != session_id or config.get("attachmentRoot") != str(ATTACHMENT_ROOT):
        reject("attachment ownership rejected")
    root = Path(config["attachmentRoot"])
    expected_uid, expected_gid = attachment_owner_ids()
    sessions_root = root / "work-sessions"
    session_root = sessions_root / session_id
    for directory in (root, sessions_root, session_root):
        validate_owned_path(directory, 0o700, expected_uid, expected_gid, True)

    verified = []
    identities: set[str] = set()
    total_bytes = 0
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != ATTACHMENT_REFERENCE_KEYS:
            reject("attachment ownership rejected")
        attachment_id = reference.get("attachmentId")
        try:
            canonical_attachment = str(uuid.UUID(attachment_id))
        except (ValueError, TypeError, AttributeError):
            canonical_attachment = None
        if canonical_attachment != attachment_id or attachment_id in identities:
            reject("attachment ownership rejected")
        content_type = reference.get("contentType")
        size_bytes = reference.get("sizeBytes")
        digest = reference.get("sha256")
        if (
            content_type not in ATTACHMENT_TYPES
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or not (1 <= size_bytes <= MAX_ATTACHMENT_BYTES)
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            reject("attachment ownership rejected")
        attachment_root = session_root / attachment_id
        validate_owned_path(attachment_root, 0o700, expected_uid, expected_gid, True)
        metadata_path = attachment_root / "metadata.json"
        content_path = attachment_root / "content"
        metadata_stat = validate_owned_path(
            metadata_path, 0o600, expected_uid, expected_gid, False
        )
        content_stat = validate_owned_path(
            content_path, 0o600, expected_uid, expected_gid, False
        )
        try:
            metadata = json.loads(
                read_owned_file(metadata_path, metadata_stat, 16 * 1024).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            reject("attachment ownership rejected")
        expected_metadata = {
            "protocolVersion": "worksession-attachment/v1",
            "workerId": ATTACHMENT_WORKER_ID,
            "sessionId": session_id,
            "attachmentId": attachment_id,
            "storageIdentity": f"work-sessions/{session_id}/{attachment_id}/content",
            "source": "OPERATOR_UPLOAD",
            "kind": "IMAGE",
            "contentType": content_type,
            "sizeBytes": size_bytes,
            "retentionClass": "SESSION",
            "sha256": digest,
            "syntheticFixture": False,
            "projectIdentity": PROJECT_ID,
            "workspaceIdentity": request["workspaceIdentity"],
            "storageScope": "REAL_SESSION",
        }
        if (
            not isinstance(metadata, dict)
            or set(metadata) != ATTACHMENT_METADATA_KEYS
            or any(metadata.get(key) != value for key, value in expected_metadata.items())
            or not isinstance(metadata.get("createdAt"), str)
            or not metadata["createdAt"].endswith("Z")
            or not isinstance(metadata.get("storedAt"), str)
            or not metadata["storedAt"].endswith("Z")
            or content_stat.st_size != size_bytes
        ):
            reject("attachment ownership rejected")
        content = read_owned_file(content_path, content_stat, MAX_ATTACHMENT_BYTES)
        if hashlib.sha256(content).hexdigest() != digest or not content_matches_type(
            content_type, content[:12]
        ):
            reject("attachment ownership rejected")
        identities.add(attachment_id)
        total_bytes += size_bytes
        verified.append(VerifiedAttachment(
            attachment_id, content_type, size_bytes, digest, content_path
        ))
    if total_bytes > MAX_ATTACHMENT_TOTAL_BYTES:
        reject("attachment ownership rejected")
    return verified


def materialization_owner_ids() -> tuple[int, int, int, int]:
    try:
        return (
            0,
            grp.getgrnam(ATTACHMENT_GROUP).gr_gid,
            pwd.getpwnam("jose").pw_uid,
            pwd.getpwnam("jose").pw_gid,
        )
    except KeyError:
        reject("attachment materialization rejected")


def cleanup_exact_materialization(
    execution_root: Path,
    created: list[MaterializedAttachment],
) -> bool:
    _root_uid, _group_id, jose_uid, jose_gid = materialization_owner_ids()
    try:
        directory_stat = execution_root.lstat()
        entries = sorted(execution_root.iterdir(), key=lambda path: path.name)
    except OSError:
        return False
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or stat.S_IMODE(directory_stat.st_mode) != 0o700
        or directory_stat.st_uid != jose_uid
        or directory_stat.st_gid != jose_gid
        or [path.name for path in entries] != sorted(item.path.name for item in created)
    ):
        return False
    identities = {item.path.name: item for item in created}
    for path in entries:
        expected = identities[path.name]
        try:
            observed = path.lstat()
        except OSError:
            return False
        if (
            not stat.S_ISREG(observed.st_mode)
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_uid not in {0, jose_uid}
            or observed.st_gid != jose_gid
            or observed.st_nlink != 1
            or observed.st_dev != expected.device
            or observed.st_ino != expected.inode
        ):
            return False
        content = read_owned_file(path, observed, MAX_ATTACHMENT_BYTES)
        if (
            len(content) != expected.size_bytes
            or hashlib.sha256(content).hexdigest() != expected.sha256
            or not content_matches_type(expected.content_type, content[:12])
        ):
            return False
    try:
        for path in reversed(entries):
            path.unlink()
        execution_root.rmdir()
    except OSError:
        return False
    return True


def expected_materialized_names(attachments: Any) -> list[str] | None:
    if not isinstance(attachments, list) or not (1 <= len(attachments) <= 4):
        return None
    extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    names = []
    identities = set()
    for position, attachment in enumerate(attachments, start=1):
        if not isinstance(attachment, dict) or set(attachment) != ATTACHMENT_REFERENCE_KEYS:
            return None
        attachment_id = attachment.get("attachmentId")
        content_type = attachment.get("contentType")
        try:
            canonical = str(uuid.UUID(attachment_id))
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if (
            canonical != attachment_id
            or attachment_id in identities
            or content_type not in extensions
            or not isinstance(attachment.get("sizeBytes"), int)
            or isinstance(attachment.get("sizeBytes"), bool)
            or not (1 <= attachment["sizeBytes"] <= MAX_ATTACHMENT_BYTES)
            or not isinstance(attachment.get("sha256"), str)
            or SHA256_PATTERN.fullmatch(attachment["sha256"]) is None
        ):
            return None
        identities.add(attachment_id)
        names.append(f"{position:02d}-{attachment_id}{extensions[content_type]}")
    return names


def reconcile_materializations(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "executions"}:
        reject("attachment reconciliation rejected")
    if payload.get("schemaVersion") != "codex-image-reconciliation-state-v1":
        reject("attachment reconciliation rejected")
    records: dict[str, dict[str, Any]] = {}
    executions = payload.get("executions")
    if not isinstance(executions, list):
        reject("attachment reconciliation rejected")
    for record in executions:
        if not isinstance(record, dict) or set(record) != {
            "executionId", "status", "attachments"
        }:
            reject("attachment reconciliation rejected")
        execution_id = record.get("executionId")
        try:
            canonical = str(uuid.UUID(execution_id))
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if (
            canonical != execution_id
            or execution_id in records
            or record.get("status") not in TERMINAL_EXECUTION_STATES | NON_TERMINAL_EXECUTION_STATES
            or not isinstance(record.get("attachments"), list)
        ):
            reject("attachment reconciliation rejected")
        records[execution_id] = record

    root_uid, group_id, jose_uid, jose_gid = materialization_owner_ids()
    validate_owned_path(MATERIALIZATION_ROOT, 0o710, root_uid, group_id, True)
    removed = 0
    retained = 0
    ambiguous = 0
    removable: list[tuple[Path, list[Path]]] = []
    try:
        candidates = sorted(MATERIALIZATION_ROOT.iterdir(), key=lambda path: path.name)
    except OSError:
        reject("attachment reconciliation rejected")
    for candidate in candidates:
        try:
            canonical = str(uuid.UUID(candidate.name))
            directory_stat = candidate.lstat()
        except (ValueError, TypeError, AttributeError, OSError):
            canonical = None
            directory_stat = None
        record = records.get(candidate.name)
        if (
            canonical != candidate.name
            or directory_stat is None
            or not stat.S_ISDIR(directory_stat.st_mode)
            or stat.S_IMODE(directory_stat.st_mode) != 0o700
            or directory_stat.st_uid != jose_uid
            or directory_stat.st_gid != jose_gid
        ):
            ambiguous += 1
            continue
        if record is not None and record["status"] in NON_TERMINAL_EXECUTION_STATES:
            retained += 1
            continue
        try:
            entries = sorted(candidate.iterdir(), key=lambda path: path.name)
        except OSError:
            ambiguous += 1
            continue
        expected_names = None if record is None else expected_materialized_names(record["attachments"])
        if record is not None and expected_names is None:
            ambiguous += 1
            continue
        if expected_names is not None and [path.name for path in entries] != expected_names:
            ambiguous += 1
            continue
        valid_entries = True
        expected_by_name = (
            {}
            if record is None
            else dict(zip(expected_names or [], record["attachments"], strict=True))
        )
        for path in entries:
            try:
                observed = path.lstat()
            except OSError:
                valid_entries = False
                break
            if record is not None:
                reference = expected_by_name[path.name]
                content = read_owned_file(path, observed, MAX_ATTACHMENT_BYTES)
                if (
                    len(content) != reference["sizeBytes"]
                    or hashlib.sha256(content).hexdigest() != reference["sha256"]
                    or not content_matches_type(reference["contentType"], content[:12])
                ):
                    valid_entries = False
                    break
            if (
                MATERIALIZED_NAME.fullmatch(path.name) is None
                or not stat.S_ISREG(observed.st_mode)
                or stat.S_IMODE(observed.st_mode) != 0o600
                or observed.st_uid != jose_uid
                or observed.st_gid != jose_gid
                or observed.st_nlink != 1
            ):
                valid_entries = False
                break
        if not valid_entries or (record is None and len(entries) > 4):
            ambiguous += 1
            continue
        removable.append((candidate, entries))
    if ambiguous:
        reject("attachment reconciliation rejected")
    for candidate, entries in removable:
        try:
            for path in reversed(entries):
                path.unlink()
            candidate.rmdir()
        except OSError:
            reject("attachment reconciliation rejected")
        removed += 1
    return {
        "schemaVersion": "codex-image-reconciliation-v1",
        "state": "PASS",
        "removed": removed,
        "retained": retained,
        "ambiguous": 0,
        "valuesExposed": False,
    }


@contextlib.contextmanager
def materialize_attachments(
    attachments: list[VerifiedAttachment],
    execution_id: str,
):
    if not attachments:
        yield []
        return
    try:
        canonical_execution = str(uuid.UUID(execution_id))
    except (ValueError, TypeError, AttributeError):
        canonical_execution = None
    if canonical_execution != execution_id:
        reject("attachment materialization rejected")
    root_uid, group_id, jose_uid, jose_gid = materialization_owner_ids()
    validate_owned_path(MATERIALIZATION_ROOT, 0o710, root_uid, group_id, True)
    execution_root = MATERIALIZATION_ROOT / execution_id
    try:
        execution_root.mkdir(mode=0o700)
        os.chown(execution_root, jose_uid, jose_gid)
    except OSError:
        reject("attachment materialization rejected")

    created: list[MaterializedAttachment] = []
    extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def interrupt_materialization(_signum: int, _frame: Any) -> None:
        raise InterruptedError("bounded image materialization interrupted")

    signal.signal(signal.SIGTERM, interrupt_materialization)
    try:
        try:
            expected_uid, expected_gid = attachment_owner_ids()
            for position, attachment in enumerate(attachments, start=1):
                source_stat = validate_owned_path(
                    attachment.content_path, 0o600, expected_uid, expected_gid, False
                )
                content = read_owned_file(
                    attachment.content_path, source_stat, MAX_ATTACHMENT_BYTES
                )
                if (
                    len(content) != attachment.size_bytes
                    or hashlib.sha256(content).hexdigest() != attachment.sha256
                    or not content_matches_type(attachment.content_type, content[:12])
                ):
                    reject("attachment materialization rejected")
                target = execution_root / (
                    f"{position:02d}-{attachment.attachment_id}"
                    + extensions[attachment.content_type]
                )
                try:
                    descriptor = os.open(
                        target,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                    )
                    try:
                        opened = os.fstat(descriptor)
                        created.append(MaterializedAttachment(
                            attachment.attachment_id,
                            attachment.content_type,
                            target,
                            opened.st_dev,
                            opened.st_ino,
                            attachment.size_bytes,
                            attachment.sha256,
                        ))
                        try:
                            os.fchmod(descriptor, 0o600)
                            os.fchown(descriptor, jose_uid, jose_gid)
                            written = 0
                            while written < len(content):
                                written += os.write(descriptor, content[written:])
                            os.fsync(descriptor)
                        except BaseException:
                            try:
                                current = target.lstat()
                                opened = os.fstat(descriptor)
                                if (
                                    current.st_dev == opened.st_dev
                                    and current.st_ino == opened.st_ino
                                ):
                                    target.unlink()
                                    created.pop()
                            except OSError:
                                pass
                            raise
                    finally:
                        os.close(descriptor)
                except OSError:
                    reject("attachment materialization rejected")
            yield created
        finally:
            if not cleanup_exact_materialization(execution_root, created):
                reject("attachment materialization rejected")
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


def checked(command: list[str], cwd: Path) -> str:
    if command and command[0] == "git":
        command = ["git", "-c", f"safe.directory={cwd}", *command[1:]]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        reject("worktree fingerprint rejected")
    return result.stdout.strip()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def change_workspace_owner_ids() -> tuple[int, set[int], int]:
    try:
        service_uid = pwd.getpwnam(CHANGE_WORKSPACE_OWNER).pw_uid
        return service_uid, {
            service_uid, pwd.getpwnam("jose").pw_uid,
        }, grp.getgrnam(CHANGE_WORKSPACE_GROUP).gr_gid
    except KeyError:
        reject("workspace ownership rejected")


def checked_bytes(command: list[str], cwd: Path) -> bytes:
    if command and command[0] == "git":
        command = ["git", "-c", f"safe.directory={cwd}", *command[1:]]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        reject("worktree fingerprint rejected")
    if len(result.stdout) > MAX_CHANGE_FINGERPRINT_BYTES:
        reject("worktree fingerprint rejected")
    return result.stdout


def read_change_workspace_record(
    worktree: Path, ownership: dict[str, Any]
) -> dict[str, Any]:
    service_uid, _owner_uids, owner_gid = change_workspace_owner_ids()
    root = worktree.parent
    record_path = root / "workspace-v1.json"
    try:
        root_stat = root.lstat()
        worktree_stat = worktree.lstat()
        record_stat = record_path.lstat()
        record = json.loads(
            record_path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object_pairs,
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        reject("workspace ownership rejected")
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root.is_symlink()
        or stat.S_IMODE(root_stat.st_mode) not in {0o700, 0o770}
        or root_stat.st_uid != service_uid
        or root_stat.st_gid != owner_gid
        or not stat.S_ISDIR(worktree_stat.st_mode)
        or worktree.is_symlink()
        or worktree_stat.st_uid != service_uid
        or worktree_stat.st_gid != owner_gid
        or not stat.S_ISREG(record_stat.st_mode)
        or record_path.is_symlink()
        or stat.S_IMODE(record_stat.st_mode) != 0o600
        or record_stat.st_uid != service_uid
        or record_stat.st_gid != owner_gid
        or not isinstance(record, dict)
        or set(record) != CHANGE_WORKSPACE_RECORD_KEYS
        or SHA256_PATTERN.fullmatch(
            str(record.get("initialSourceFingerprintSha256", ""))
        ) is None
        or SHA256_PATTERN.fullmatch(str(record.get("recordSha256", ""))) is None
    ):
        reject("workspace ownership rejected")
    sealed = dict(record)
    seal = sealed.pop("recordSha256", None)
    if not isinstance(seal, str) or canonical_sha256(sealed) != seal:
        reject("workspace ownership rejected")
    expected = {
        "schemaVersion": 1,
        "protocolVersion": "development-change-workspace/v1",
        "changeKey": ownership["changeKey"],
        "databaseProjectId": ownership["databaseProjectId"],
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "repositoryBranch": BRANCH,
        "baseCommit": ownership["baseCommit"],
        "workspaceBranch": f"atenea/change-{ownership['changeKey']}",
        "workspaceIdentity": ownership["workspaceIdentity"],
        "workerId": ATTACHMENT_WORKER_ID,
    }
    if any(record.get(key) != value for key, value in expected.items()):
        reject("workspace ownership rejected")
    return record


def prepare_change_workspace_access(
    worktree: Path, owner_uids: set[int], owner_gid: int
) -> None:
    candidates = [worktree.parent]
    try:
        for directory, names, files in os.walk(worktree, followlinks=False):
            directory_path = Path(directory)
            candidates.append(directory_path)
            candidates.extend(directory_path / name for name in names)
            candidates.extend(directory_path / name for name in files)
        if len(candidates) > 200_000:
            reject("workspace ownership rejected")
        for candidate in candidates:
            observed = candidate.lstat()
            if stat.S_ISLNK(observed.st_mode):
                continue
            if (
                not (stat.S_ISDIR(observed.st_mode) or stat.S_ISREG(observed.st_mode))
                or observed.st_uid not in owner_uids
                or observed.st_gid != owner_gid
                or observed.st_mode & 0o002
            ):
                reject("workspace ownership rejected")
            mode = stat.S_IMODE(observed.st_mode)
            os.chmod(candidate, mode | ((mode & 0o700) >> 3), follow_symlinks=False)
    except OSError:
        reject("workspace ownership rejected")


def change_source_fingerprint(
    worktree: Path, record: dict[str, Any], head: str
) -> tuple[str, bool]:
    status = checked_bytes(
        ["git", "status", "--porcelain=v2", "-z", "--untracked-files=all"],
        worktree,
    )
    if not status and head == record["baseCommit"]:
        return record["initialSourceFingerprintSha256"], False
    diff = checked_bytes(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD"], worktree
    )
    raw_paths = checked_bytes(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], worktree
    )
    try:
        paths = [part.decode("utf-8") for part in raw_paths.split(b"\0") if part]
    except UnicodeDecodeError:
        reject("worktree fingerprint rejected")
    if len(paths) > 4096:
        reject("worktree fingerprint rejected")
    untracked = []
    total = 0
    for relative in sorted(paths):
        candidate = worktree / relative
        try:
            observed = candidate.lstat()
            if stat.S_ISLNK(observed.st_mode):
                data = os.readlink(candidate).encode("utf-8")
            elif stat.S_ISREG(observed.st_mode):
                total += observed.st_size
                if total > MAX_CHANGE_FINGERPRINT_BYTES:
                    reject("worktree fingerprint rejected")
                data = candidate.read_bytes()
            else:
                reject("worktree fingerprint rejected")
        except OSError:
            reject("worktree fingerprint rejected")
        untracked.append({
            "pathSha256": hashlib.sha256(relative.encode()).hexdigest(),
            "contentSha256": hashlib.sha256(data).hexdigest(),
        })
    return canonical_sha256({
        "initialSourceFingerprintSha256": record["initialSourceFingerprintSha256"],
        "headCommit": head,
        "statusSha256": hashlib.sha256(status).hexdigest(),
        "diffSha256": hashlib.sha256(diff).hexdigest(),
        "untracked": untracked,
    }), bool(status)


def observe_change_worktree(
    request: dict[str, Any], worktree: Path
) -> ChangeSourceObservation:
    ownership = request["changeOwnership"]
    record = read_change_workspace_record(worktree, ownership)
    root = checked(["git", "rev-parse", "--show-toplevel"], worktree)
    remote = checked(["git", "remote", "get-url", "origin"], worktree)
    common_value = Path(checked(["git", "rev-parse", "--git-common-dir"], worktree))
    common_dir = (
        common_value if common_value.is_absolute() else worktree / common_value
    ).resolve()
    try:
        common_stat = GIT_COMMON_DIR.lstat()
    except OSError:
        reject("worktree fingerprint rejected")
    branch = checked(["git", "symbolic-ref", "--quiet", "HEAD"], worktree)
    head = checked(["git", "rev-parse", "--verify", "HEAD^{commit}"], worktree)
    branch_head = checked(
        [
            "git", "--git-dir", str(common_dir), "rev-parse", "--verify",
            f"refs/heads/atenea/change-{ownership['changeKey']}^{{commit}}",
        ],
        worktree,
    )
    canonical = checked(
        [
            "git", "--git-dir", str(common_dir), "rev-parse", "--verify",
            f"refs/remotes/origin/{BRANCH}^{{commit}}",
        ],
        worktree,
    )
    if (
        Path(root) != worktree
        or remote != REPOSITORY
        or common_dir != GIT_COMMON_DIR
        or not stat.S_ISDIR(common_stat.st_mode)
        or GIT_COMMON_DIR.is_symlink()
        or branch != f"refs/heads/atenea/change-{ownership['changeKey']}"
        or head != branch_head
        or canonical != ownership["expectedCanonicalCommit"]
    ):
        reject("worktree fingerprint rejected")
    source_fingerprint, workspace_dirty = change_source_fingerprint(
        worktree, record, head
    )
    head_after = checked(["git", "rev-parse", "--verify", "HEAD^{commit}"], worktree)
    branch_head_after = checked(
        [
            "git", "--git-dir", str(common_dir), "rev-parse", "--verify",
            f"refs/heads/atenea/change-{ownership['changeKey']}^{{commit}}",
        ],
        worktree,
    )
    source_fingerprint_after, workspace_dirty_after = change_source_fingerprint(
        worktree, record, head_after
    )
    ownership_fingerprint = canonical_sha256({
        "recordSha256": record["recordSha256"],
        "branchHead": branch_head,
        "workspaceIdentity": ownership["workspaceIdentity"],
    })
    if (
        source_fingerprint_after != source_fingerprint
        or workspace_dirty_after != workspace_dirty
        or head_after != head
        or branch_head_after != branch_head
    ):
        reject("worktree fingerprint rejected")
    return ChangeSourceObservation(
        common_dir,
        source_fingerprint,
        ownership_fingerprint,
        workspace_dirty,
    )


def validate_change_worktree(
    request: dict[str, Any], worktree: Path
) -> Path:
    ownership = request["changeOwnership"]
    observation = observe_change_worktree(request, worktree)
    if (
        observation.source_fingerprint_sha256
            != ownership["sourceFingerprintSha256"]
        or observation.workspace_ownership_fingerprint_sha256
            != ownership["workspaceOwnershipFingerprintSha256"]
    ):
        reject("worktree fingerprint rejected")
    _service_uid, owner_uids, owner_gid = change_workspace_owner_ids()
    prepare_change_workspace_access(worktree, owner_uids, owner_gid)
    return observation.common_dir


def post_run_source_identity(
    request: dict[str, Any], worktree: Path
) -> dict[str, Any]:
    observation = observe_change_worktree(request, worktree)
    ownership = request["changeOwnership"]
    return {
        "changeKey": ownership["changeKey"],
        "databaseWorkSessionId": ownership["databaseWorkSessionId"],
        "remoteSessionId": ownership["remoteSessionId"],
        "workspaceIdentity": ownership["workspaceIdentity"],
        "executionId": request["executionId"],
        "sourceFingerprintSha256": observation.source_fingerprint_sha256,
        "workspaceOwnershipFingerprintSha256": (
            observation.workspace_ownership_fingerprint_sha256
        ),
        "workspaceDirty": observation.workspace_dirty,
    }


def validate_worktree(worktree: Path, record: dict[str, Any]) -> Path:
    root = checked(["git", "rev-parse", "--show-toplevel"], worktree)
    if Path(root) != worktree:
        reject("worktree fingerprint rejected")
    if checked(["git", "remote", "get-url", "origin"], worktree) != REPOSITORY:
        reject("worktree fingerprint rejected")
    common_dir = Path(checked(["git", "rev-parse", "--git-common-dir"], worktree)).resolve()
    if common_dir != GIT_COMMON_DIR or common_dir.is_symlink():
        reject("worktree fingerprint rejected")
    if BASE_COMMIT is None:
        canonical_ref = "refs/remotes/origin/" + BRANCH
        canonical_commit = checked(
            ["git", "--git-dir", str(common_dir), "rev-parse", "--verify", canonical_ref + "^{commit}"],
            worktree,
        )
        if canonical_commit != record["canonicalCommit"]:
            reject("worktree fingerprint rejected")
        if checked(["git", "rev-parse", "--verify", "HEAD^{commit}"], worktree) != canonical_commit:
            reject("worktree fingerprint rejected")
        if checked(["git", "status", "--porcelain=v1", "--untracked-files=all"], worktree):
            reject("worktree fingerprint rejected")
    else:
        checked(["git", "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"], worktree)
    manifest = worktree / "ops" / "atenea-runtime.json"
    try:
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    except OSError:
        reject("worktree fingerprint rejected")
    if digest != MANIFEST_SHA256:
        reject("worktree fingerprint rejected")
    allocation = worktree.parent / "runtime-allocation-v1.json"
    try:
        allocation_digest = hashlib.sha256(allocation.read_bytes()).hexdigest()
    except OSError:
        reject("worktree fingerprint rejected")
    if allocation_digest != record["allocationSha256"]:
        reject("worktree fingerprint rejected")
    return common_dir


def validate_instruction_bundle(worktree: Path, enforce_legacy_bundle_pins: bool = True) -> ReviewedInstructionBundle:
    project_path = worktree / PROJECT_INSTRUCTION_PATH
    forbidden = (
        worktree / "AGENTS.override.md",
        worktree / ".codex",
    )
    try:
        platform_stat = PLATFORM_INSTRUCTION_PATH.stat()
        project_stat = project_path.stat()
        platform = PLATFORM_INSTRUCTION_PATH.read_bytes()
        project = project_path.read_bytes()
    except OSError:
        reject("instruction bundle rejected")
    if (
        not PLATFORM_INSTRUCTION_PATH.is_file()
        or PLATFORM_INSTRUCTION_PATH.is_symlink()
        or platform_stat.st_uid != PLATFORM_INSTRUCTION_UID
        or platform_stat.st_mode & 0o022
        or not project_path.is_file()
        or project_path.is_symlink()
        or project_stat.st_size == 0
        or project_stat.st_size > 32_768
        or any(path.exists() or path.is_symlink() for path in forbidden)
        or hashlib.sha256(platform).hexdigest() != PLATFORM_INSTRUCTION_SHA256
        or (enforce_legacy_bundle_pins and hashlib.sha256(project).hexdigest() != PROJECT_INSTRUCTION_SHA256)
    ):
        reject("instruction bundle rejected")
    try:
        tracked = subprocess.run(
            ["git", "-c", f"safe.directory={worktree}", "cat-file", "blob",
             "HEAD:" + PROJECT_INSTRUCTION_PATH],
            cwd=worktree,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        reject("instruction bundle rejected")
    if tracked != project:
        reject("instruction bundle rejected")
    if enforce_legacy_bundle_pins and hashlib.sha256(
            INSTRUCTION_BUNDLE_REVISION.encode("ascii")
            + b"\0" + platform + b"\0" + project
        ).hexdigest() != INSTRUCTION_BUNDLE_SHA256:
        reject("instruction bundle rejected")
    try:
        return ReviewedInstructionBundle(
            developer_instructions=(
                platform.decode("utf-8")
                + "\n\n# Reviewed repository contract: "
                + PROJECT_INSTRUCTION_PATH
                + "\n\n"
                + project.decode("utf-8")
            ),
            project_bytes=project,
        )
    except UnicodeDecodeError:
        reject("instruction bundle rejected")


def prepare_instruction_projection(
    temporary_root: Path,
    project_bytes: bytes,
) -> InstructionProjection:
    jose = pwd.getpwnam("jose")
    ambient_mask = temporary_root / "empty-instructions"
    project_source = temporary_root / "project-instructions"
    ambient_mask.write_bytes(b"")
    project_source.write_bytes(project_bytes)
    for path in (ambient_mask, project_source):
        os.chmod(path, 0o600)
        os.chown(path, jose.pw_uid, jose.pw_gid)
    return InstructionProjection(ambient_mask, project_source)


def sandbox_command(
    workload: dict[str, Any],
    worktree: Path,
    common_dir: Path,
    final_path: Path,
    resolv_path: Path,
    instruction_mask_path: Path,
    instruction_bundle: str,
    execution_id: str,
    materialized_attachments: list[MaterializedAttachment] | tuple[MaterializedAttachment, ...] = (),
) -> list[str]:
    project_instruction_path = instruction_mask_path.with_name(
        "project-instructions"
    )
    command = [
        "/usr/bin/systemd-run",
        "--wait", "--pipe", "--collect", "--quiet", "--service-type=exec",
        "--unit", "atenea-project-codex-" + execution_id.replace("-", ""),
        "--property", "User=jose",
        "--property", "Group=atenea",
        "--property", "NoNewPrivileges=yes",
        "--property", "PrivateDevices=yes",
        # A private Bubblewrap proc mount supplies the user-namespace boundary.
        # systemd's proc overlays for tunables/logs would prevent that mount.
        "--property", "ProtectKernelModules=yes",
        "--property", "ProtectControlGroups=yes",
        "--property", "RestrictSUIDSGID=yes",
        "--property", "LockPersonality=yes",
        "--property", "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
        "--property", "IPAddressDeny=127.0.0.0/8",
        "--property", "IPAddressDeny=10.0.0.0/8",
        "--property", "IPAddressDeny=100.64.0.0/10",
        "--property", "IPAddressDeny=169.254.0.0/16",
        "--property", "IPAddressDeny=172.16.0.0/12",
        "--property", "IPAddressDeny=192.168.0.0/16",
        "--property", "IPAddressDeny=::1/128",
        "--property", "IPAddressDeny=fc00::/7",
        "--property", "IPAddressDeny=fe80::/10",
        "--",
        "/usr/bin/bwrap",
        "--die-with-parent", "--new-session", "--unshare-all", "--share-net",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", str(final_path.parent),
        "--bind", str(final_path.parent), str(final_path.parent),
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--dir", "/etc",
        "--ro-bind", "/etc/ssl", "/etc/ssl",
        "--ro-bind", str(resolv_path), "/etc/resolv.conf",
        "--ro-bind", "/etc/hosts", "/etc/hosts",
        "--ro-bind", "/etc/nsswitch.conf", "/etc/nsswitch.conf",
        "--ro-bind", "/etc/passwd", "/etc/passwd",
        "--ro-bind", "/etc/group", "/etc/group",
        "--dir", "/home", "--dir", "/home/jose",
        "--bind", "/home/jose/.codex", "/home/jose/.codex",
        "--ro-bind", str(instruction_mask_path), "/home/jose/.codex/AGENTS.md",
        "--ro-bind", str(instruction_mask_path), "/home/jose/.codex/AGENTS.override.md",
        "--dir", "/srv", "--dir", "/srv/atenea", "--dir", "/srv/atenea/workspaces",
        "--dir", "/srv/atenea/workspaces/sessions",
        "--dir", str(worktree.parent),
        "--bind", str(worktree), str(worktree),
        "--ro-bind", str(project_instruction_path), str(worktree / PROJECT_INSTRUCTION_PATH),
        "--dir", "/srv/atenea/repositories",
        "--bind", str(common_dir), str(common_dir),
        "--setenv", "HOME", "/home/jose",
        "--setenv", "USER", "jose",
        "--setenv", "LOGNAME", "jose",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "GIT_CONFIG_COUNT", "1",
        "--setenv", "GIT_CONFIG_KEY_0", "safe.directory",
        "--setenv", "GIT_CONFIG_VALUE_0", str(worktree),
        "--chdir", str(worktree),
        CODEX, "exec",
        "--ignore-user-config", "--ignore-rules",
        "--config", "project_doc_max_bytes=0",
        "--config", "developer_instructions=" + json.dumps(instruction_bundle),
        # The reviewed Bubblewrap namespace is the workspace-write boundary.
        # A second Codex Bubblewrap namespace is unsupported by this kernel.
        "--sandbox", "danger-full-access",
        "-C", str(worktree),
        "--json", "--output-last-message", str(final_path),
    ]
    if materialized_attachments:
        mounts = [
            "--dir", str(MATERIALIZATION_ROOT.parent.parent),
            "--dir", str(MATERIALIZATION_ROOT.parent),
            "--dir", str(MATERIALIZATION_ROOT),
        ]
        mounts.extend(["--dir", str(materialized_attachments[0].path.parent)])
        for attachment in materialized_attachments:
            mounts.extend(["--ro-bind", str(attachment.path), str(attachment.path)])
        mount_index = command.index("--setenv")
        command[mount_index:mount_index] = mounts
    if workload["kind"] == CHANGE_CAPABILITY:
        workspace_index = command.index("--dir", command.index("/srv/atenea/workspaces"))
        # The path is derived from the sealed change identity; no caller path is mounted.
        command[workspace_index + 2:workspace_index + 2] = [
            "--dir", str(CHANGE_WORKSPACE_PARENT),
        ]
    if workload["kind"] in {
        PROFILED_CAPABILITY, IMAGE_CAPABILITY, CHANGE_CAPABILITY,
    }:
        command.extend([
            "--model", workload["modelId"],
            "--config", "model_reasoning_effort=" + json.dumps(workload["reasoningEffort"]),
        ])
    if workload["threadId"] is not None:
        command.append("resume")
        for attachment in materialized_attachments:
            command.extend(["--image", str(attachment.path)])
        command.extend([workload["threadId"], "-"])
    else:
        for attachment in materialized_attachments:
            command.extend(["--image", str(attachment.path)])
        command.append("-")
    return command


def execute(
    workload: dict[str, Any],
    worktree: Path,
    common_dir: Path,
    instruction_bundle: ReviewedInstructionBundle,
    execution_id: str,
    timeout: int,
    materialized_attachments: list[MaterializedAttachment] | tuple[MaterializedAttachment, ...] = (),
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".atenea-codex-result-",
        dir=worktree.parent,
    ) as temporary:
        jose = pwd.getpwnam("jose")
        os.chmod(temporary, 0o700)
        os.chown(temporary, jose.pw_uid, jose.pw_gid)
        final_path = Path(temporary) / "final.txt"
        resolv_path = Path(temporary) / "resolv.conf"
        resolv_path.write_text("nameserver 1.1.1.1\noptions timeout:2 attempts:2\n", encoding="ascii")
        os.chmod(resolv_path, 0o600)
        os.chown(resolv_path, jose.pw_uid, jose.pw_gid)
        projection = prepare_instruction_projection(
            Path(temporary),
            instruction_bundle.project_bytes,
        )
        command = sandbox_command(
            workload,
            worktree,
            common_dir,
            final_path,
            resolv_path,
            projection.ambient_mask,
            instruction_bundle.developer_instructions,
            execution_id,
            materialized_attachments,
        )
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        def terminate(_signum: int, _frame: Any) -> None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        previous_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, terminate)
        try:
            try:
                stream, error_stream = process.communicate(
                    workload["message"], timeout=timeout
                )
            except subprocess.TimeoutExpired:
                terminate(signal.SIGTERM, None)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                reject("Codex execution failed")
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
        if process.returncode != 0:
            reject(codex_failure_reason(error_stream))
        thread_id = workload["threadId"]
        for line in stream.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                thread_id = event["thread_id"]
        if thread_id is None:
            reject("Codex execution failed")
        try:
            final_answer = final_path.read_text(encoding="utf-8").strip()
        except OSError:
            reject("Codex execution failed")
        if not final_answer or len(final_answer.encode()) > 262_144:
            reject("Codex execution failed")
        result = {
            "threadId": thread_id,
            "turnId": execution_id,
            "finalAnswer": final_answer,
            "outputSummary": f"{CAPABILITY} completed",
        }
        if workload["kind"] in {
            PROFILED_CAPABILITY, IMAGE_CAPABILITY, CHANGE_CAPABILITY,
        }:
            result.update({
                "outputSummary": f"{workload['kind']} completed",
                "progressEvents": normalize_codex_events(stream),
                **effective_profile(workload),
            })
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--reconcile-materializations", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or not (30 <= args.timeout <= 3600):
        reject("project configuration rejected")
    runner = Path(__file__).resolve()
    config = load_json(args.config)
    if args.reconcile_materializations:
        validate_config(config, runner, require_execution=False)
        try:
            reconciliation = json.load(sys.stdin)
        except (json.JSONDecodeError, UnicodeDecodeError):
            reject("attachment reconciliation rejected")
        result = reconcile_materializations(reconciliation)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        reject("workspace ownership rejected")
    workload_value = request.get("workload") if isinstance(request, dict) else None
    capability = workload_value.get("kind") if isinstance(workload_value, dict) else None
    validate_config(config, runner, legacy_registry_required=capability != CHANGE_CAPABILITY)
    workload, worktree = validate_request(request, config)
    validate_codex_version(workload)
    if workload["kind"] == CHANGE_CAPABILITY:
        common_dir = validate_change_worktree(request, worktree)
    else:
        record = config["workspaces"][request["workspaceIdentity"]]
        common_dir = validate_worktree(worktree, record)
    instruction_bundle = validate_instruction_bundle(worktree, workload["kind"] != CHANGE_CAPABILITY)
    verified_attachments = validate_attachment_references(request, workload, config)
    try:
        with materialize_attachments(
            verified_attachments, request["executionId"]
        ) as materialized:
            result = execute(
                workload,
                worktree,
                common_dir,
                instruction_bundle,
                request["executionId"],
                args.timeout,
                materialized,
            )
            if workload["kind"] == CHANGE_CAPABILITY:
                result["sourceIdentity"] = post_run_source_identity(
                    request, worktree
                )
    except SystemExit:
        raise
    except Exception as exception:
        reject(internal_failure_reason(exception))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exception:
        reject(internal_failure_reason(exception))
