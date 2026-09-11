#!/usr/bin/env python3
"""Fail-closed Atenea workspace-release finalizer v1."""

from __future__ import annotations

import hashlib
import json
import os
import grp
import pwd
import re
import socket
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA = "atenea-workspace-release-preflight-v1"
CAPACITY_OWNER_SCHEMA = "project-workspace-capacity-owner-v1"
RELEASE_PREFLIGHT_SCHEMA = "project-workspace-release-diagnosis-v1"
UNACTIVATED_DIAGNOSIS_SCHEMA = "project-workspace-unactivated-diagnosis-v1"
PROJECT_ID = "atenea"
WORKER_ID = "ax42-01"
REPOSITORY = "https://github.com/jlnieto/atenea.git"
BRANCH = "main"
MANIFEST_SHA256 = "327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
FORBIDDEN_IDENTITY = re.compile(r"(?:^|[-_.:/])(beautips|prod|production)(?:$|[-_.:/])")
JOURNAL_SCHEMA = "atenea-workspace-release-journal-v1"
JOURNAL_ROOT = Path("/srv/atenea/worker/workspace-release-v1/sessions")
JOURNAL_STAGES = (
    "PREPARED",
    "EPHEMERAL_RELEASED",
    "UNREGISTERED",
    "ADMISSION_RELEASED",
    "ALLOCATION_RETIRED",
    "RELEASED",
)
JOURNAL_KEYS = {
    "schemaVersion", "operationId", "idempotencyKey", "sessionId",
    "workspaceIdentity", "projectId", "workerId", "requestFingerprintSha256",
    "ownershipFingerprintSha256", "allocationFingerprintSha256", "state",
    "revision", "stageEvidence", "createdAt", "updatedAt", "journalSha256",
    "immutableRequest", "preflightProjection", "candidateCounts",
}
WORKSPACE_ROOT = Path("/srv/atenea/workspaces")
RETIRED_ALLOCATION_NAME = "runtime-allocation-v1.retired.json"
EPHEMERAL_CATEGORIES = (
    "runtimeContainers", "runtimeNetworks", "sessionImages",
    "previewResources", "listeners", "brokerResources", "materializations",
    "browserProcesses",
)
EPHEMERAL_RELEASE_ORDER = (
    "browserProcesses", "materializations", "previewResources", "listeners",
    "brokerResources", "runtimeContainers", "runtimeNetworks", "sessionImages",
)
RETAINED_KEYS = {
    "workspaceRecord", "worktree", "git", "turns", "agentRuns",
    "attachments", "logs", "artifacts", "backups", "policyVolumes",
}

PROJECTION_KEYS = {
    "schemaVersion", "requestFingerprintSha256", "sessionId",
    "workspaceIdentity", "projectId", "workerId", "workspace", "registry",
    "admission", "allocation", "runtimeContainers", "runtimeNetworks",
    "sessionImages", "previewResources", "listeners", "brokerResources",
    "materializations", "browserProcesses", "valuesExposed",
}
OWNERSHIP_KEYS = {
    "workerId", "sessionId", "runtimeId", "projectId",
    "allocationFingerprintSha256", "labels", "productionLike", "ambiguous",
}
CANDIDATE_KEYS = {"resourceId", "ownership", "details"}


class PreflightRejected(Exception):
    """Safe deterministic rejection raised before the first mutation."""

    def __init__(self, code: str = "WORKSPACE_RELEASE_PREFLIGHT_REJECTED"):
        super().__init__(code)
        self.code = code


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _reject() -> None:
    raise PreflightRejected()


def _exact_dict(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _reject()
    return value


def _canonical_uuid(value: Any) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        _reject()
    if canonical != value or UUID_PATTERN.fullmatch(canonical) is None:
        _reject()
    return canonical


def _safe_identity(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 512
        or FORBIDDEN_IDENTITY.search(value.lower()) is not None
    ):
        _reject()
    return value


def _request_identity(request: Any) -> dict[str, str]:
    expected_keys = {
        "operationId", "idempotencyKey", "sessionId", "workspaceIdentity",
        "projectId", "repository", "branch", "commit", "manifestSha256",
        "workspaceBranch",
    }
    change_owned = isinstance(request, dict) and "changeKey" in request
    if change_owned:
        expected_keys = (expected_keys - {"commit", "manifestSha256"}) | {
            "changeKey", "databaseWorkSessionId", "databaseProjectId", "baseCommit", "workerId",
        }
    request = _exact_dict(request, expected_keys)
    session = _canonical_uuid(request.get("sessionId"))
    _canonical_uuid(request.get("operationId"))
    _canonical_uuid(request.get("idempotencyKey"))
    exact = {
        "workspaceIdentity": f"remote:{WORKER_ID}:work-session:{session}",
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "manifestSha256": MANIFEST_SHA256,
        "workspaceBranch": f"atenea/session-{session}",
    }
    if change_owned:
        change_key = _canonical_uuid(request.get("changeKey"))
        exact.pop("manifestSha256")
        exact.update({
            "workspaceIdentity": f"remote:{WORKER_ID}:change:{change_key}",
            "workspaceBranch": f"atenea/change-{change_key}",
            "workerId": WORKER_ID,
        })
        if any(type(request[key]) is not int or request[key] <= 0
               for key in ("databaseWorkSessionId", "databaseProjectId")):
            _reject()
    if any(request.get(key) != value for key, value in exact.items()):
        _reject()
    commit = request.get("baseCommit" if change_owned else "commit")
    if not isinstance(commit, str) or COMMIT.fullmatch(commit) is None:
        _reject()
    return dict(request)


def _change_workspace_record(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "protocolVersion": "development-change-workspace/v1",
        **{key: request[key] for key in (
            "changeKey", "databaseProjectId", "projectId", "baseCommit",
            "workspaceBranch", "workspaceIdentity", "workerId",
        )},
    }


def _capacity_owner_request_identity(request: Any) -> dict[str, str]:
    expected_keys = {
        "sessionId", "workspaceIdentity", "projectId", "repository",
        "branch", "commit", "manifestSha256", "workspaceBranch",
    }
    request = _exact_dict(request, expected_keys)
    session = _canonical_uuid(request.get("sessionId"))
    exact = {
        "workspaceIdentity": f"remote:{WORKER_ID}:work-session:{session}",
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "manifestSha256": MANIFEST_SHA256,
        "workspaceBranch": f"atenea/session-{session}",
    }
    if any(request.get(key) != value for key, value in exact.items()):
        _reject()
    if not isinstance(request.get("commit"), str) or COMMIT.fullmatch(request["commit"]) is None:
        _reject()
    return dict(request)


def _validate_authoritative_roots(
    request: dict[str, str], projection: dict[str, Any]
) -> tuple[str, str, set[int]]:
    session = request["sessionId"]
    runtime = f"ws-{session.replace('-', '')}"
    session_root = f"/srv/atenea/workspaces/sessions/{session}"
    worktree = f"{session_root}/{PROJECT_ID}"
    allocation_path = f"{session_root}/runtime-allocation-v1.json"
    admission_path = f"/srv/atenea/worker/runtime-admission-v1/records/{session}.json"

    workspace = _exact_dict(projection.get("workspace"), {
        "recordPath", "worktreePath", "sessionId", "projectId", "repository",
        "baseBranch", "workspaceBranch", "canonicalCommit", "manifestSha256",
        "state", "owner", "group", "mode", "symlink",
    })
    if workspace != {
        "recordPath": f"{session_root}/workspace-v1.json",
        "worktreePath": worktree,
        "sessionId": session,
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "baseBranch": BRANCH,
        "workspaceBranch": request["workspaceBranch"],
        "canonicalCommit": request["commit"],
        "manifestSha256": MANIFEST_SHA256,
        "state": "ready",
        "owner": "atenea-worker",
        "group": "atenea",
        "mode": 640,
        "symlink": False,
    }:
        _reject()

    allocation = _exact_dict(projection.get("allocation"), {
        "recordPath", "fingerprintSha256", "sessionId", "projectId",
        "runtimeId", "worktreePath", "manifestRelativePath", "slot",
        "heavyPermit", "state", "owner", "group", "mode", "symlink",
        "allocatedPorts",
    })
    allocation_fingerprint = allocation.get("fingerprintSha256")
    slot = allocation.get("slot")
    heavy = allocation.get("heavyPermit")
    ports = allocation.get("allocatedPorts")
    if (
        allocation.get("recordPath") != allocation_path
        or not isinstance(allocation_fingerprint, str)
        or SHA256.fullmatch(allocation_fingerprint) is None
        or allocation.get("sessionId") != session
        or allocation.get("projectId") != PROJECT_ID
        or allocation.get("runtimeId") != runtime
        or allocation.get("worktreePath") != worktree
        or allocation.get("manifestRelativePath") != "ops/atenea-runtime.json"
        or slot not in {"slot1", "slot2", "slot3", "slot4"}
        or heavy not in {"heavy1", "heavy2"}
        or allocation.get("state") != "allocated"
        or allocation.get("owner") != "atenea-worker"
        or allocation.get("group") != "atenea"
        or allocation.get("mode") not in {600, 640}
        or allocation.get("symlink") is not False
        or not isinstance(ports, list)
        or not ports
    ):
        _reject()
    loopback_ports: set[int] = set()
    port_names: set[str] = set()
    for port in ports:
        port = _exact_dict(port, {
            "name", "internalPort", "protocol", "bindAddress", "loopbackPort"
        })
        if (
            not isinstance(port.get("name"), str)
            or re.fullmatch(r"[a-z][a-z0-9-]{1,62}", port["name"]) is None
            or port["name"] in port_names
            or type(port.get("internalPort")) is not int
            or not 1 <= port["internalPort"] <= 65535
            or port.get("protocol") not in {"http", "tcp"}
            or port.get("bindAddress") != "127.0.0.1"
            or type(port.get("loopbackPort")) is not int
            or not 1024 <= port["loopbackPort"] <= 65535
            or port["loopbackPort"] in loopback_ports
        ):
            _reject()
        port_names.add(port["name"])
        loopback_ports.add(port["loopbackPort"])

    registry = _exact_dict(projection.get("registry"), {
        "configurationPath", "selectionEnabled", "executionEnabled",
        "workspaceIdentity", "sessionId", "worktreePath",
        "allocationFingerprintSha256", "canonicalCommit", "projectId",
        "repository", "owner", "group", "mode", "symlink",
    })
    if registry != {
        "configurationPath": "/etc/atenea-worker/project-codex-v1.json",
        "selectionEnabled": True,
        "executionEnabled": True,
        "workspaceIdentity": request["workspaceIdentity"],
        "sessionId": session,
        "worktreePath": worktree,
        "allocationFingerprintSha256": allocation_fingerprint,
        "canonicalCommit": request["commit"],
        "projectId": PROJECT_ID,
        "repository": REPOSITORY,
        "owner": "root",
        "group": "root",
        "mode": 644,
        "symlink": False,
    }:
        _reject()

    admission = _exact_dict(projection.get("admission"), {
        "recordPath", "sessionId", "normal", "heavy", "owner", "group",
        "mode", "symlink",
    })
    if admission != {
        "recordPath": admission_path,
        "sessionId": session,
        "normal": {"slot": slot, "state": "held"},
        "heavy": {"permit": heavy, "state": "held"},
        "owner": "atenea-worker",
        "group": "atenea",
        "mode": 640,
        "symlink": False,
    }:
        _reject()
    return runtime, allocation_fingerprint, loopback_ports


def _expected_labels(session: str, runtime: str, service: str) -> dict[str, str]:
    return {
        "com.atenea.engine": "atenea-runtime-engine-v1",
        "com.atenea.session": session,
        "com.atenea.runtime": runtime,
        "com.atenea.project": PROJECT_ID,
        "com.atenea.service": service,
    }


def _candidate(
    value: Any,
    session: str,
    runtime: str,
    allocation_fingerprint: str,
) -> tuple[str, dict[str, Any]]:
    value = _exact_dict(value, CANDIDATE_KEYS)
    resource_id = _safe_identity(value.get("resourceId"))
    ownership = _exact_dict(value.get("ownership"), OWNERSHIP_KEYS)
    details = value.get("details")
    if not isinstance(details, dict):
        _reject()
    service = details.get("service")
    if (
        ownership.get("workerId") != WORKER_ID
        or ownership.get("sessionId") != session
        or ownership.get("runtimeId") != runtime
        or ownership.get("projectId") != PROJECT_ID
        or ownership.get("allocationFingerprintSha256") != allocation_fingerprint
        or ownership.get("productionLike") is not False
        or ownership.get("ambiguous") is not False
        or not isinstance(service, str)
        or ownership.get("labels") != _expected_labels(session, runtime, service)
    ):
        _reject()
    return resource_id, details


def _validate_candidates(
    projection: dict[str, Any],
    session: str,
    runtime: str,
    allocation_fingerprint: str,
    loopback_ports: set[int],
) -> dict[str, int]:
    seen: set[str] = set()
    previews: dict[str, tuple[int, int, str]] = {}
    preview_listener_counts: dict[str, int] = {}
    runtime_listener_ports: set[int] = set()
    rootless_broker_ports: set[int] = set()
    counts: dict[str, int] = {}

    def each(category: str, validator: Callable[[str, dict[str, Any]], None]) -> None:
        values = projection.get(category)
        if not isinstance(values, list):
            _reject()
        for value in values:
            resource_id, details = _candidate(
                value, session, runtime, allocation_fingerprint
            )
            if resource_id in seen:
                _reject()
            validator(resource_id, details)
            seen.add(resource_id)
        counts[category] = len(values)

    container_services = {"db", "codex-app-server", "atenea-dev", "build", "build-db"}

    def runtime_container(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "state"} or details.get("service") not in container_services:
            _reject()
        if resource_id != f"{runtime}-{details['service']}" or details.get("state") not in {"running", "stopped"}:
            _reject()

    each("runtimeContainers", runtime_container)

    def runtime_network(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "internal"}:
            _reject()
        expected = {
            "runtime": f"{runtime}-network",
            "build": f"{runtime}-build-network",
        }
        if expected.get(details.get("service")) != resource_id or details.get("internal") is not True:
            _reject()

    each("runtimeNetworks", runtime_network)

    def session_image(resource_id: str, details: dict[str, Any]) -> None:
        if (
            set(details) != {"service", "imageId"}
            or details.get("service") != "session-image"
            or resource_id != f"{runtime}-image-{details.get('imageId', '')}"
            or not isinstance(details.get("imageId"), str)
            or SHA256.fullmatch(details["imageId"]) is None
        ):
            _reject()

    each("sessionImages", session_image)

    def preview(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "previewId", "ingressPort", "upstreamPort", "state"}:
            _reject()
        preview_id = _canonical_uuid(details.get("previewId"))
        ingress = details.get("ingressPort")
        upstream = details.get("upstreamPort")
        if (
            details.get("service") != "preview"
            or resource_id != f"preview:{preview_id}"
            or type(ingress) is not int
            or not 1024 <= ingress <= 65535
            or upstream not in loopback_ports
            or details.get("state") not in {"READY", "RECONCILING", "STOPPED", "BLOCKED", "EXPIRED"}
            or preview_id in previews
        ):
            _reject()
        previews[preview_id] = (ingress, upstream, details["state"])

    each("previewResources", preview)

    def listener(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "role", "bindAddress", "port", "previewId"}:
            _reject()
        role = details.get("role")
        port = details.get("port")
        preview_id = details.get("previewId")
        if role == "runtime":
            valid = (
                details.get("service") == "runtime-listener"
                and details.get("bindAddress") == "127.0.0.1"
                and port in loopback_ports
                and preview_id is None
            )
            if valid:
                runtime_listener_ports.add(port)
        elif role == "preview":
            valid = (
                details.get("service") == "preview-listener"
                and isinstance(preview_id, str)
                and preview_id in previews
                and previews[preview_id][0] == port
                and previews[preview_id][2] in {"READY", "RECONCILING"}
                and isinstance(details.get("bindAddress"), str)
                and re.fullmatch(r"100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}", details["bindAddress"]) is not None
            )
            if valid:
                preview_listener_counts[preview_id] = (
                    preview_listener_counts.get(preview_id, 0) + 1
                )
        else:
            valid = False
        if not valid or resource_id != f"listener:tcp:{details.get('bindAddress')}:{port}":
            _reject()

    each("listeners", listener)
    if any(
        preview_listener_counts.get(preview_id, 0)
        != (1 if state in {"READY", "RECONCILING"} else 0)
        for preview_id, (_ingress, _upstream, state) in previews.items()
    ):
        _reject()

    def broker(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "kind", "port"}:
            _reject()
        if details.get("kind") == "rootless-port":
            valid = (
                details.get("service") == "broker"
                and details.get("port") in loopback_ports
                and resource_id == f"broker:rootless:{details['port']}"
            )
            if valid:
                rootless_broker_ports.add(details["port"])
        elif details.get("kind") == "codex-loopback-proxy":
            valid = (
                details.get("service") == "codex-app-server"
                and details.get("port") in loopback_ports
                and resource_id == f"broker:codex:{runtime}:{details['port']}"
            )
        else:
            valid = False
        if not valid:
            _reject()

    each("brokerResources", broker)
    if rootless_broker_ports != runtime_listener_ports:
        _reject()

    def materialization(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "executionId", "path", "terminal"}:
            _reject()
        execution = _canonical_uuid(details.get("executionId"))
        if (
            details.get("service") != "materialization"
            or resource_id != f"materialization:{execution}"
            or details.get("path") != f"/run/atenea/codex-images/{execution}"
            or details.get("terminal") is not True
        ):
            _reject()

    each("materializations", materialization)

    def browser(resource_id: str, details: dict[str, Any]) -> None:
        if set(details) != {"service", "kind", "operationId", "unit"}:
            _reject()
        operation = _canonical_uuid(details.get("operationId"))
        compact = operation.replace("-", "")
        if details.get("kind") == "codex":
            expected_unit = f"atenea-project-codex-{compact}"
        elif details.get("kind") == "playwright":
            expected_unit = f"atenea-playwright-{compact}"
        else:
            _reject()
        if (
            details.get("service") != "browser"
            or details.get("unit") != expected_unit
            or resource_id != f"browser:{expected_unit}"
        ):
            _reject()

    each("browserProcesses", browser)
    return counts


def validate_release_preflight(
    request: Any,
    projection: Any,
) -> dict[str, Any]:
    """Validate one complete internally-observed projection without writing.

    The caller must hold the shared lifecycle lock.  This function performs no
    filesystem, process, socket, registry or runtime operation and returns only
    a sealed safe summary for the later journal stage.
    """

    exact_request = _request_identity(request)
    projection = _exact_dict(projection, PROJECTION_KEYS)
    if (
        projection.get("schemaVersion") != SCHEMA
        or projection.get("requestFingerprintSha256") != canonical_hash(exact_request)
        or projection.get("sessionId") != exact_request["sessionId"]
        or projection.get("workspaceIdentity") != exact_request["workspaceIdentity"]
        or projection.get("projectId") != PROJECT_ID
        or projection.get("workerId") != WORKER_ID
        or projection.get("valuesExposed") is not False
    ):
        _reject()
    if "changeKey" in exact_request:
        workspace = projection.get("workspace")
        root = f"/srv/atenea/workspaces/changes/{exact_request['changeKey']}"
        if (workspace != {
                "recordPath": f"{root}/workspace-v1.json",
                "worktreePath": f"{root}/{PROJECT_ID}",
                "record": _change_workspace_record(exact_request),
                "gitOwned": True,
            }
            or any(projection.get(key) is not None for key in ("registry", "allocation", "admission"))
            or any(projection.get(key) != [] for key in EPHEMERAL_CATEGORIES)):
            _reject()
        runtime, allocation_fingerprint = None, None
        counts = {category: 0 for category in EPHEMERAL_CATEGORIES}
    else:
        runtime, allocation_fingerprint, loopback_ports = _validate_authoritative_roots(
            exact_request, projection
        )
        counts = _validate_candidates(
            projection, exact_request["sessionId"], runtime,
            allocation_fingerprint, loopback_ports,
        )
    return {
        "schemaVersion": SCHEMA,
        "state": "PREFLIGHT_ACCEPTED",
        "sessionId": exact_request["sessionId"],
        "workspaceIdentity": exact_request["workspaceIdentity"],
        "projectId": PROJECT_ID,
        "workerId": WORKER_ID,
        "runtimeId": runtime,
        "allocationFingerprintSha256": allocation_fingerprint,
        "requestFingerprintSha256": canonical_hash(exact_request),
        "ownershipFingerprintSha256": canonical_hash(projection),
        "candidateCounts": counts,
        "valuesExposed": False,
    }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        _reject()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ReleaseJournalStore:
    """Atomic private journal; callers must hold the lifecycle lock."""

    def __init__(
        self,
        root: Path = JOURNAL_ROOT,
        *,
        test_mode: bool = False,
        clock: Callable[[], datetime] | None = None,
    ):
        self.root = Path(root)
        self.expected_uid = os.geteuid()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not test_mode and self.root != JOURNAL_ROOT:
            _reject()
        self._require_directory(self.root)

    def prepare(self, request: Any, projection: Any) -> dict[str, Any]:
        exact_request = _request_identity(request)
        preflight = validate_release_preflight(exact_request, projection)
        session_root = self._session_root(exact_request["sessionId"], create=True)
        target = session_root / "journal-v1.json"
        if target.exists() or target.is_symlink():
            existing = self._read(target)
            self._require_identity(existing, exact_request, preflight)
            return existing
        now = _timestamp(self.clock())
        journal = {
            "schemaVersion": JOURNAL_SCHEMA,
            "operationId": exact_request["operationId"],
            "idempotencyKey": exact_request["idempotencyKey"],
            "sessionId": exact_request["sessionId"],
            "workspaceIdentity": exact_request["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "requestFingerprintSha256": preflight["requestFingerprintSha256"],
            "ownershipFingerprintSha256": preflight["ownershipFingerprintSha256"],
            "allocationFingerprintSha256": preflight[
                "allocationFingerprintSha256"
            ],
            "state": "PREPARED",
            "revision": 1,
            "stageEvidence": {
                "PREPARED": preflight["ownershipFingerprintSha256"],
            },
            "immutableRequest": json.loads(json.dumps(exact_request)),
            "preflightProjection": json.loads(json.dumps(projection)),
            "candidateCounts": dict(preflight["candidateCounts"]),
            "createdAt": now,
            "updatedAt": now,
        }
        return self._write(
            target,
            self._seal(journal),
            must_be_absent=True,
            expected_journal_sha256=None,
        )

    def open_or_prepare(self, request: Any, projection: Any) -> dict[str, Any]:
        exact_request = _request_identity(request)
        session_root = self.root / exact_request["sessionId"]
        if session_root.exists() or session_root.is_symlink():
            self._require_directory(session_root)
            target = session_root / "journal-v1.json"
            if target.exists() or target.is_symlink():
                journal = self._read(target)
                self._require_request_identity(journal, exact_request)
                return journal
        return self.prepare(exact_request, projection)

    def load(self, request: Any) -> dict[str, Any]:
        exact_request = _request_identity(request)
        target = self._session_root(exact_request["sessionId"]) / "journal-v1.json"
        journal = self._read(target)
        self._require_request_identity(journal, exact_request)
        return journal

    def advance(
        self,
        request: Any,
        expected_state: str,
        next_state: str,
        stage_evidence_sha256: str,
    ) -> dict[str, Any]:
        exact_request = _request_identity(request)
        if (
            expected_state not in JOURNAL_STAGES
            or next_state not in JOURNAL_STAGES
            or JOURNAL_STAGES.index(next_state) != JOURNAL_STAGES.index(expected_state) + 1
            or not isinstance(stage_evidence_sha256, str)
            or SHA256.fullmatch(stage_evidence_sha256) is None
        ):
            _reject()
        target = self._session_root(exact_request["sessionId"]) / "journal-v1.json"
        current = self._read(target)
        self._require_request_identity(current, exact_request)
        if current["state"] != expected_state:
            _reject()
        updated = {key: value for key, value in current.items() if key != "journalSha256"}
        updated["state"] = next_state
        updated["revision"] = current["revision"] + 1
        updated["stageEvidence"] = dict(current["stageEvidence"])
        updated["stageEvidence"][next_state] = stage_evidence_sha256
        updated["updatedAt"] = _timestamp(self.clock())
        return self._write(
            target,
            self._seal(updated),
            must_be_absent=False,
            expected_journal_sha256=current["journalSha256"],
        )

    def _session_root(self, session_id: str, create: bool = False) -> Path:
        session_id = _canonical_uuid(session_id)
        target = self.root / session_id
        if create and not (target.exists() or target.is_symlink()):
            try:
                target.mkdir(mode=0o700)
            except OSError:
                _reject()
            self._fsync_directory(self.root)
        self._require_directory(target)
        return target

    def _require_directory(self, path: Path) -> None:
        try:
            observed = path.lstat()
        except OSError:
            _reject()
        if (
            not stat.S_ISDIR(observed.st_mode)
            or stat.S_IMODE(observed.st_mode) != 0o700
            or observed.st_uid != self.expected_uid
        ):
            _reject()

    def _read(self, target: Path) -> dict[str, Any]:
        try:
            descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                observed = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(observed.st_mode)
                    or stat.S_IMODE(observed.st_mode) != 0o600
                    or observed.st_uid != self.expected_uid
                    or observed.st_nlink != 1
                    or observed.st_size > 64 * 1024
                ):
                    _reject()
                with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                    descriptor = -1
                    parsed = json.load(handle)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        except (OSError, ValueError, json.JSONDecodeError):
            _reject()
        return self._validate_journal(parsed)

    def _write(
        self,
        target: Path,
        journal: dict[str, Any],
        *,
        must_be_absent: bool,
        expected_journal_sha256: str | None,
    ) -> dict[str, Any]:
        parent = target.parent
        self._require_directory(parent)
        if target.is_symlink() or (must_be_absent and target.exists()):
            _reject()
        descriptor = -1
        temporary = ""
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".journal-v1.", dir=parent)
            os.fchmod(descriptor, 0o600)
            encoded = (
                json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
            written = 0
            while written < len(encoded):
                written += os.write(descriptor, encoded[written:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            if target.is_symlink() or (must_be_absent and target.exists()):
                _reject()
            if not must_be_absent:
                observed = self._read(target)
                if observed["journalSha256"] != expected_journal_sha256:
                    _reject()
            os.replace(temporary, target)
            temporary = ""
            self._fsync_directory(parent)
        except (OSError, ValueError):
            _reject()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
        return self._read(target)

    @staticmethod
    def _seal(journal: dict[str, Any]) -> dict[str, Any]:
        if "journalSha256" in journal:
            _reject()
        sealed = dict(journal)
        sealed["journalSha256"] = canonical_hash(journal)
        return sealed

    def _validate_journal(self, journal: Any) -> dict[str, Any]:
        journal = _exact_dict(journal, JOURNAL_KEYS)
        state = journal.get("state")
        revision = journal.get("revision")
        if (
            journal.get("schemaVersion") != JOURNAL_SCHEMA
            or state not in JOURNAL_STAGES
            or type(revision) is not int
            or revision != JOURNAL_STAGES.index(state) + 1
            or _canonical_uuid(journal.get("operationId")) != journal["operationId"]
            or _canonical_uuid(journal.get("idempotencyKey")) != journal["idempotencyKey"]
            or _canonical_uuid(journal.get("sessionId")) != journal["sessionId"]
            or journal.get("workspaceIdentity")
            != _request_identity(journal.get("immutableRequest"))["workspaceIdentity"]
            or journal.get("projectId") != PROJECT_ID
            or journal.get("workerId") != WORKER_ID
        ):
            _reject()
        for key in (
            "requestFingerprintSha256", "ownershipFingerprintSha256",
            "allocationFingerprintSha256", "journalSha256",
        ):
            if (key == "allocationFingerprintSha256"
                    and "changeKey" in journal["immutableRequest"]
                    and journal.get(key) is None):
                continue
            if not isinstance(journal.get(key), str) or SHA256.fullmatch(journal[key]) is None:
                _reject()
        evidence = journal.get("stageEvidence")
        if (
            not isinstance(evidence, dict)
            or set(evidence) != set(JOURNAL_STAGES[:revision])
            or any(not isinstance(value, str) or SHA256.fullmatch(value) is None for value in evidence.values())
            or evidence.get("PREPARED") != journal["ownershipFingerprintSha256"]
        ):
            _reject()
        immutable_request = _request_identity(journal.get("immutableRequest"))
        preflight = validate_release_preflight(
            immutable_request, journal.get("preflightProjection")
        )
        if (
            immutable_request["operationId"] != journal["operationId"]
            or immutable_request["idempotencyKey"] != journal["idempotencyKey"]
            or immutable_request["sessionId"] != journal["sessionId"]
            or preflight["requestFingerprintSha256"]
            != journal["requestFingerprintSha256"]
            or preflight["ownershipFingerprintSha256"]
            != journal["ownershipFingerprintSha256"]
            or preflight["allocationFingerprintSha256"]
            != journal["allocationFingerprintSha256"]
            or journal.get("candidateCounts") != preflight["candidateCounts"]
        ):
            _reject()
        for key in ("createdAt", "updatedAt"):
            value = journal.get(key)
            if not isinstance(value, str) or not value.endswith("Z"):
                _reject()
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                _reject()
        if canonical_hash({key: value for key, value in journal.items() if key != "journalSha256"}) != journal["journalSha256"]:
            _reject()
        return dict(journal)

    @staticmethod
    def _require_request_identity(
        journal: dict[str, Any], exact_request: dict[str, str]
    ) -> None:
        if (
            journal["operationId"] != exact_request["operationId"]
            or journal["idempotencyKey"] != exact_request["idempotencyKey"]
            or journal["sessionId"] != exact_request["sessionId"]
            or journal["workspaceIdentity"] != exact_request["workspaceIdentity"]
            or journal["projectId"] != exact_request["projectId"]
            or journal["workerId"] != WORKER_ID
            or journal["requestFingerprintSha256"] != canonical_hash(exact_request)
        ):
            _reject()

    def _require_identity(
        self,
        journal: dict[str, Any],
        exact_request: dict[str, str],
        preflight: dict[str, Any],
    ) -> None:
        self._require_request_identity(journal, exact_request)
        if (
            journal["ownershipFingerprintSha256"]
            != preflight["ownershipFingerprintSha256"]
            or journal["allocationFingerprintSha256"]
            != preflight["allocationFingerprintSha256"]
        ):
            _reject()

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            _reject()


class UnavailableReleaseBoundary:
    """Default-deny boundary until the reviewed mediator is installed."""

    @staticmethod
    def _unavailable(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise PreflightRejected("WORKSPACE_RELEASE_BOUNDARY_UNAVAILABLE")

    release_ephemeral = _unavailable
    unregister_workspace = _unavailable
    release_heavy_admission = _unavailable
    release_normal_admission = _unavailable
    retire_allocation = _unavailable
    verify_retained = _unavailable


class AllocationRetirer:
    """Exact same-directory allocation rename with metadata proof."""

    def __init__(self, workspace_root: Path = WORKSPACE_ROOT, *, test_mode: bool = False):
        self.workspace_root = Path(workspace_root)
        try:
            self.expected_uid = (
                os.geteuid() if test_mode else pwd.getpwnam("atenea-worker").pw_uid
            )
        except KeyError:
            _reject()
        if not test_mode and self.workspace_root != WORKSPACE_ROOT:
            _reject()
        self._require_root()

    def retire(self, session_id: str, allocation_fingerprint: str) -> dict[str, Any]:
        session = _canonical_uuid(session_id)
        if not isinstance(allocation_fingerprint, str) or SHA256.fullmatch(allocation_fingerprint) is None:
            _reject()
        session_root = self.workspace_root / "sessions" / session
        source = session_root / "runtime-allocation-v1.json"
        retired = session_root / RETIRED_ALLOCATION_NAME
        self._require_directory(session_root)
        if source.is_symlink() or retired.is_symlink():
            _reject()
        if not source.exists() and retired.exists():
            observed, retired_hash = self._regular_identity(retired)
            if retired_hash != allocation_fingerprint:
                _reject()
            return self._retirement_result(
                session, allocation_fingerprint, observed, observed, False
            )
        if retired.exists():
            _reject()
        before, content_hash = self._regular_identity(source)
        if content_hash != allocation_fingerprint:
            _reject()
        try:
            os.rename(source, retired)
            self._fsync_directory(session_root)
        except OSError:
            _reject()
        after, retired_hash = self._regular_identity(retired)
        identity_fields = (
            "st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_size",
            "st_mtime_ns",
        )
        if (
            retired_hash != allocation_fingerprint
            or any(getattr(before, key) != getattr(after, key) for key in identity_fields)
            or source.exists()
            or source.is_symlink()
        ):
            _reject()
        return self._retirement_result(
            session, allocation_fingerprint, before, after, True
        )

    @staticmethod
    def _retirement_result(
        session: str,
        allocation_fingerprint: str,
        before: os.stat_result,
        after: os.stat_result,
        changed: bool,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "atenea-allocation-retirement-v1",
            "state": "RETIRED",
            "sessionId": session,
            "sourceName": "runtime-allocation-v1.json",
            "retiredName": RETIRED_ALLOCATION_NAME,
            "fingerprintSha256": allocation_fingerprint,
            "device": before.st_dev,
            "inode": before.st_ino,
            "uid": before.st_uid,
            "gid": before.st_gid,
            "mode": stat.S_IMODE(before.st_mode),
            "size": before.st_size,
            "mtimeNs": before.st_mtime_ns,
            "atimeBeforeNs": before.st_atime_ns,
            "atimeAfterNs": after.st_atime_ns,
            "ctimeBeforeNs": before.st_ctime_ns,
            "ctimeAfterNs": after.st_ctime_ns,
            "changed": changed,
            "valuesExposed": False,
        }

    def _require_root(self) -> None:
        self._require_directory(self.workspace_root)
        self._require_directory(self.workspace_root / "sessions")

    def _require_directory(self, path: Path) -> None:
        try:
            observed = path.lstat()
        except OSError:
            _reject()
        if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != self.expected_uid:
            _reject()

    def _regular_identity(self, path: Path) -> tuple[os.stat_result, str]:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                observed = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(observed.st_mode)
                    or stat.S_IMODE(observed.st_mode) not in {0o600, 0o640}
                    or observed.st_uid != self.expected_uid
                    or observed.st_nlink != 1
                ):
                    _reject()
                digest = hashlib.sha256()
                while chunk := os.read(descriptor, 64 * 1024):
                    digest.update(chunk)
            finally:
                os.close(descriptor)
        except OSError:
            _reject()
        return observed, digest.hexdigest()

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        ReleaseJournalStore._fsync_directory(path)


class ReviewedReleaseBoundary:
    """Narrow mediator over internally projected exact resource identities."""

    def __init__(self, operator: Any, allocation_retirer: Any):
        self.operator = operator
        self.allocation_retirer = allocation_retirer

    def release_ephemeral(
        self, request: dict[str, str], projection: dict[str, Any]
    ) -> dict[str, Any]:
        verifier = getattr(self.operator, "verify_ephemeral_projection", None)
        if verifier is not None:
            verifier(request, projection)
        removed = {category: 0 for category in EPHEMERAL_CATEGORIES}
        changed = {category: 0 for category in EPHEMERAL_CATEGORIES}
        for category in EPHEMERAL_RELEASE_ORDER:
            for candidate in projection[category]:
                result = self.operator.remove_ephemeral(
                    category, candidate["resourceId"], candidate
                )
                result = _exact_dict(result, {
                    "schemaVersion", "state", "category", "resourceId",
                    "sessionId", "changed", "policyVolumeChanged",
                    "valuesExposed",
                })
                if (
                    result.get("schemaVersion")
                    != "atenea-ephemeral-resource-release-v1"
                    or result.get("state") != "RELEASED"
                    or result.get("category") != category
                    or result.get("resourceId") != candidate["resourceId"]
                    or result.get("sessionId") != request["sessionId"]
                    or type(result.get("changed")) is not bool
                    or result.get("policyVolumeChanged") is not False
                    or result.get("valuesExposed") is not False
                ):
                    _reject()
                removed[category] += 1
                changed[category] += int(result["changed"])
        return {
            "schemaVersion": "atenea-ephemeral-release-v1",
            "state": "RELEASED",
            "removed": removed,
            "changed": changed,
            "policyVolumesRetained": True,
            "valuesExposed": False,
        }

    def unregister_workspace(self, request: dict[str, str]) -> dict[str, Any]:
        return self.operator.unregister_workspace(
            request["sessionId"], request["workspaceIdentity"]
        )

    def release_heavy_admission(self, request: dict[str, str]) -> dict[str, Any]:
        return self.operator.release_admission(request["sessionId"], "heavy")

    def release_normal_admission(self, request: dict[str, str]) -> dict[str, Any]:
        return self.operator.release_admission(request["sessionId"], "normal")

    def retire_allocation(
        self, request: dict[str, str], fingerprint: str
    ) -> dict[str, Any]:
        return self.allocation_retirer.retire(request["sessionId"], fingerprint)

    def verify_retained(
        self, request: dict[str, str], projection: dict[str, Any]
    ) -> dict[str, Any]:
        return self.operator.verify_retained(request["sessionId"], projection)


class FixedRootReleaseOperator:
    """Operational adapter derived only from fixed worker-owned roots.

    The first deployed revision accepts only an exact empty ephemeral
    projection.  Any live, stopped, partial or ambiguous runtime candidate is
    rejected before the journal is created; the pure reviewed boundary above
    remains the only place capable of consuming a populated projection.
    """

    CONFIG = Path("/etc/atenea-worker/project-codex-v1.json")
    ADMISSION_TOOL = Path(
        "/srv/atenea/worker/workspace-v1/ops/worker/runtime-admission-v1.sh"
    )
    ADMISSION_ROOT = Path("/srv/atenea/worker/runtime-admission-v1/records")
    PREVIEW_ROOT = Path("/srv/atenea/worker/session-preview-v1/previews")
    MATERIALIZATION_ROOT = Path("/run/atenea/codex-images")

    def __init__(self, root: Path = Path("/"), *, test_mode: bool = False):
        self.root = Path(root)
        self.test_mode = test_mode
        if not test_mode and self.root != Path("/"):
            _reject()
        try:
            self.worker_uid = (
                os.geteuid() if test_mode else pwd.getpwnam("atenea-worker").pw_uid
            )
            self.worker_gid = (
                os.getegid() if test_mode else grp.getgrnam("atenea").gr_gid
            )
        except KeyError:
            _reject()
        self.root_uid = os.geteuid() if test_mode else 0
        self.root_gid = os.getegid() if test_mode else 0
        self.worker_host = "codex-worker" if test_mode else socket.gethostname()

    def _physical(self, canonical: Path) -> Path:
        if not canonical.is_absolute():
            _reject()
        return self.root / canonical.relative_to("/")

    def _json_file(
        self,
        canonical: Path,
        *,
        uid: int,
        gid: int,
        modes: set[int],
    ) -> tuple[dict[str, Any], os.stat_result, bytes]:
        path = self._physical(canonical)
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or observed.st_uid != uid
                or observed.st_gid != gid
                or stat.S_IMODE(observed.st_mode) not in modes
                or observed.st_size < 2
                or observed.st_size > 64 * 1024
            ):
                _reject()
            content = b""
            while len(content) <= 64 * 1024:
                chunk = os.read(descriptor, 64 * 1024 - len(content) + 1)
                if not chunk:
                    break
                content += chunk
            if len(content) > 64 * 1024:
                _reject()
            parsed = json.loads(content)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            _reject()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(parsed, dict):
            _reject()
        return parsed, observed, content

    def build_projection(self, request: Any) -> dict[str, Any]:
        exact = _request_identity(request)
        if "changeKey" in exact:
            return self.build_change_projection(exact)
        session = exact["sessionId"]
        session_root = Path(f"/srv/atenea/workspaces/sessions/{session}")
        worktree = session_root / PROJECT_ID
        workspace_path = session_root / "workspace-v1.json"
        allocation_path = session_root / "runtime-allocation-v1.json"
        admission_path = self.ADMISSION_ROOT / f"{session}.json"

        workspace, workspace_stat, _workspace_bytes = self._json_file(
            workspace_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        allocation, allocation_stat, allocation_bytes = self._json_file(
            allocation_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o600, 0o640},
        )
        admission, admission_stat, _admission_bytes = self._json_file(
            admission_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        registry, registry_stat, _registry_bytes = self._json_file(
            self.CONFIG,
            uid=self.root_uid,
            gid=self.root_gid,
            modes={0o644},
        )
        allocation_sha = hashlib.sha256(allocation_bytes).hexdigest()
        record = registry.get("workspaces", {}).get(exact["workspaceIdentity"])
        runtime = f"ws-{session.replace('-', '')}"
        runtime_root = f"{session_root}/runtime/{runtime}"
        workspace_keys = {
            "schemaVersion", "sessionId", "projectId", "canonicalRemote",
            "baseBranch", "branch", "mirrorPath", "worktreePath",
            "workerHost", "state", "expectedBaseCommit", "headCommit",
        }
        registry_keys = {
            "schemaVersion", "selectionEnabled", "executionEnabled",
            "projectId", "repository", "branch", "commit", "manifestSha256",
            "runner", "workspaces",
        }
        allocation_keys = {
            "schemaVersion", "sessionId", "projectId", "branch", "mirrorPath",
            "worktreePath", "runtimeId", "manifestRelativePath", "slot",
            "workloadClass", "state", "runtimeNames", "runtimeRoot", "logsPath",
            "artifactsRoot", "cacheRoot", "allocatedPorts", "heavyPermit",
        }
        if (
            set(workspace) != workspace_keys
            or workspace.get("schemaVersion") != 1
            or workspace.get("sessionId") != session
            or workspace.get("projectId") != PROJECT_ID
            or workspace.get("canonicalRemote") != REPOSITORY
            or workspace.get("baseBranch") != BRANCH
            or workspace.get("branch") != exact["workspaceBranch"]
            or workspace.get("mirrorPath") != "/srv/atenea/repositories/atenea.git"
            or workspace.get("worktreePath") != str(worktree)
            or workspace.get("workerHost") != self.worker_host
            or workspace.get("state") != "ready"
            or workspace.get("expectedBaseCommit") != exact["commit"]
            or workspace.get("headCommit") != exact["commit"]
            or not isinstance(record, dict)
            or set(record) != {
                "sessionId", "worktree", "allocationSha256", "canonicalCommit"
            }
            or record != {
                "sessionId": session,
                "worktree": str(worktree),
                "allocationSha256": allocation_sha,
                "canonicalCommit": exact["commit"],
            }
            or frozenset(registry) not in {
                frozenset(registry_keys),
                frozenset(registry_keys | {"attachmentRoot"}),
            }
            or registry.get("schemaVersion") != "project-codex-v1"
            or registry.get("projectId") != PROJECT_ID
            or registry.get("repository") != REPOSITORY
            or registry.get("branch") != BRANCH
            or registry.get("commit") != exact["commit"]
            or registry.get("manifestSha256") != MANIFEST_SHA256
            or registry.get("runner")
            != "/usr/local/libexec/atenea/project-codex-runner-v1.py"
            or (
                "attachmentRoot" in registry
                and registry.get("attachmentRoot") != "/srv/atenea/attachments-v1"
            )
            or registry.get("selectionEnabled") is not True
            or registry.get("executionEnabled") is not True
            or registry.get("workspaces") != {exact["workspaceIdentity"]: record}
            or set(admission) != {"schemaVersion", "sessionId", "normal", "heavy"}
            or admission.get("schemaVersion") != 1
            or admission.get("sessionId") != session
            or not isinstance(admission.get("normal"), dict)
            or set(admission["normal"]) != {"slot", "state"}
            or not isinstance(admission.get("heavy"), dict)
            or set(admission["heavy"]) != {"permit", "state"}
            or set(allocation) != allocation_keys
            or allocation.get("schemaVersion") != 1
            or allocation.get("sessionId") != session
            or allocation.get("projectId") != PROJECT_ID
            or allocation.get("branch") != exact["workspaceBranch"]
            or allocation.get("mirrorPath") != "/srv/atenea/repositories/atenea.git"
            or allocation.get("runtimeId") != runtime
            or allocation.get("worktreePath") != str(worktree)
            or allocation.get("manifestRelativePath") != "ops/atenea-runtime.json"
            or allocation.get("workloadClass") != "heavy"
            or allocation.get("state") != "allocated"
            or allocation.get("runtimeNames") != {
                "composeProject": f"{runtime}-compose",
                "network": f"{runtime}-network",
                "volumePrefix": f"{runtime}-volume",
                "processUnit": f"atenea-{runtime}.service",
                "tomcatBase": f"{runtime_root}/tomcat",
            }
            or allocation.get("runtimeRoot") != runtime_root
            or allocation.get("logsPath")
            != f"/srv/atenea/artifacts/sessions/{session}/runtime/logs"
            or allocation.get("artifactsRoot")
            != f"/srv/atenea/artifacts/sessions/{session}/runs"
            or allocation.get("cacheRoot")
            != f"/srv/atenea/caches/sessions/{session}"
            or admission.get("normal")
            != {"slot": allocation.get("slot"), "state": "held"}
            or admission.get("heavy")
            != {"permit": allocation.get("heavyPermit"), "state": "held"}
        ):
            _reject()
        manifest = self._physical(worktree / "ops/atenea-runtime.json")
        try:
            if (
                manifest.is_symlink()
                or not manifest.is_file()
                or hashlib.sha256(manifest.read_bytes()).hexdigest()
                != MANIFEST_SHA256
            ):
                _reject()
        except OSError:
            _reject()
        self._require_directory(self._physical(worktree), self.worker_uid)
        if not self.test_mode:
            physical_worktree = self._physical(worktree)
            remote = self._run(
                [
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "remote", "get-url", "origin",
                ],
                15,
            ).stdout.strip()
            head = self._run(
                [
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "rev-parse", "--verify",
                    "HEAD^{commit}",
                ],
                15,
            ).stdout.strip()
            if remote != REPOSITORY or head != exact["commit"]:
                _reject()
        self._assert_no_ephemeral(session, allocation)
        ports = allocation.get("allocatedPorts")
        if not isinstance(ports, list):
            _reject()
        projection = {
            "schemaVersion": SCHEMA,
            "requestFingerprintSha256": canonical_hash(exact),
            "sessionId": session,
            "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "workspace": {
                "recordPath": str(workspace_path),
                "worktreePath": str(worktree),
                "sessionId": session,
                "projectId": PROJECT_ID,
                "repository": REPOSITORY,
                "baseBranch": BRANCH,
                "workspaceBranch": exact["workspaceBranch"],
                "canonicalCommit": exact["commit"],
                "manifestSha256": MANIFEST_SHA256,
                "state": "ready",
                "owner": "atenea-worker",
                "group": "atenea",
                "mode": int(f"{stat.S_IMODE(workspace_stat.st_mode):o}"),
                "symlink": False,
            },
            "registry": {
                "configurationPath": str(self.CONFIG),
                "selectionEnabled": True,
                "executionEnabled": True,
                "workspaceIdentity": exact["workspaceIdentity"],
                "sessionId": session,
                "worktreePath": str(worktree),
                "allocationFingerprintSha256": allocation_sha,
                "canonicalCommit": exact["commit"],
                "projectId": PROJECT_ID,
                "repository": REPOSITORY,
                "owner": "root",
                "group": "root",
                "mode": int(f"{stat.S_IMODE(registry_stat.st_mode):o}"),
                "symlink": False,
            },
            "admission": {
                "recordPath": str(admission_path),
                "sessionId": session,
                "normal": admission["normal"],
                "heavy": admission["heavy"],
                "owner": "atenea-worker",
                "group": "atenea",
                "mode": int(f"{stat.S_IMODE(admission_stat.st_mode):o}"),
                "symlink": False,
            },
            "allocation": {
                "recordPath": str(allocation_path),
                "fingerprintSha256": allocation_sha,
                "sessionId": session,
                "projectId": PROJECT_ID,
                "runtimeId": allocation["runtimeId"],
                "worktreePath": str(worktree),
                "manifestRelativePath": "ops/atenea-runtime.json",
                "slot": allocation.get("slot"),
                "heavyPermit": allocation.get("heavyPermit"),
                "state": "allocated",
                "owner": "atenea-worker",
                "group": "atenea",
                "mode": int(f"{stat.S_IMODE(allocation_stat.st_mode):o}"),
                "symlink": False,
                "allocatedPorts": ports,
            },
            **{category: [] for category in EPHEMERAL_CATEGORIES},
            "valuesExposed": False,
        }
        validate_release_preflight(exact, projection)
        return projection

    def build_change_projection(self, request: dict[str, Any]) -> dict[str, Any]:
        exact = _request_identity(request)
        root = Path(f"/srv/atenea/workspaces/changes/{exact['changeKey']}")
        worktree = root / PROJECT_ID
        mirror = Path("/srv/atenea/repositories/atenea.git")
        for directory in (root.parent, root, worktree, mirror):
            physical = self._physical(directory)
            if physical.resolve() != physical:
                _reject()
            self._require_directory(physical, self.worker_uid)
        record, _observed, _content = self._json_file(
            root / "workspace-v1.json", uid=self.worker_uid,
            gid=self.worker_gid, modes={0o600},
        )
        expected = _change_workspace_record(exact)
        # Both existing workspace record shapes describe the same change authority.
        if set(record) == set(expected) | {
                "repository", "repositoryBranch", "initialSourceFingerprintSha256", "recordSha256"}:
            if (record["repository"] != REPOSITORY or record["repositoryBranch"] != BRANCH
                    or record["recordSha256"] != canonical_hash({
                        key: value for key, value in record.items() if key != "recordSha256"})):
                _reject()
            record = {key: record[key] for key in expected}
        if record != expected or any(type(record[key]) is not type(expected[key]) for key in expected):
            _reject()
        physical_worktree = self._physical(worktree)
        physical_mirror = self._physical(mirror)

        def git(*arguments: str, bare: bool = False) -> str:
            directory = physical_mirror if bare else physical_worktree
            return self._run([
                "/usr/bin/git", "-c", f"safe.directory={directory}",
                "-C", str(directory), *arguments,
            ], 15).stdout.strip()

        branch = f"refs/heads/{exact['workspaceBranch']}"
        head = git("rev-parse", "--verify", "HEAD^{commit}")
        if (git("symbolic-ref", "--quiet", "HEAD") != branch
                or git("remote", "get-url", "origin") != REPOSITORY
                or git("remote", "get-url", "origin", bare=True) != REPOSITORY
                or git("rev-parse", "--is-bare-repository", bare=True) != "true"
                or git("rev-parse", "--path-format=absolute", "--git-common-dir") != str(physical_mirror)
                or git("rev-parse", "--show-toplevel") != str(physical_worktree)
                or git("rev-parse", "--verify", f"{branch}^{{commit}}", bare=True) != head):
            _reject()
        registrations = [entry.splitlines() for entry in
                         git("worktree", "list", "--porcelain", bare=True).split("\n\n")
                         if f"branch {branch}" in entry.splitlines()]
        if (len(registrations) != 1 or f"worktree {physical_worktree}" not in registrations[0]
                or f"HEAD {head}" not in registrations[0]):
            _reject()
        git("merge-base", "--is-ancestor", exact["baseCommit"], head)
        # v4 has no session allocation/registration. Retain source and historical
        # evidence; only finalize after incompatible ephemeral resources are absent.
        self._assert_unactivated_ephemeral_absent(exact["sessionId"])
        self._assert_process_resources_absent()
        projection = {
            "schemaVersion": SCHEMA,
            "requestFingerprintSha256": canonical_hash(exact),
            "sessionId": exact["sessionId"], "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID, "workerId": WORKER_ID,
            "workspace": {"recordPath": str(root / "workspace-v1.json"),
                          "worktreePath": str(worktree), "record": record, "gitOwned": True},
            "registry": None, "allocation": None, "admission": None,
            **{category: [] for category in EPHEMERAL_CATEGORIES}, "valuesExposed": False,
        }
        validate_release_preflight(exact, projection)
        return projection

    def diagnose_capacity_owner(self, request: Any) -> dict[str, Any]:
        """Prove one caller-identified canonical owner without mutating state.

        Only the fixed Atenea registry, workspace, admission and allocation
        roots are read.  Paths, slots, ports and record contents never cross
        the mediator boundary.
        """

        exact = _capacity_owner_request_identity(request)
        session = exact["sessionId"]
        session_root = Path(f"/srv/atenea/workspaces/sessions/{session}")
        workspace_path = session_root / "workspace-v1.json"
        allocation_path = session_root / "runtime-allocation-v1.json"
        admission_path = self.ADMISSION_ROOT / f"{session}.json"
        worktree = session_root / PROJECT_ID

        workspace, _workspace_stat, _workspace_bytes = self._json_file(
            workspace_path, uid=self.worker_uid, gid=self.worker_gid, modes={0o640}
        )
        allocation, _allocation_stat, allocation_bytes = self._json_file(
            allocation_path, uid=self.worker_uid, gid=self.worker_gid,
            modes={0o600, 0o640}
        )
        admission, _admission_stat, _admission_bytes = self._json_file(
            admission_path, uid=self.worker_uid, gid=self.worker_gid, modes={0o640}
        )
        registry, _registry_stat, _registry_bytes = self._json_file(
            self.CONFIG, uid=self.root_uid, gid=self.root_gid, modes={0o644}
        )

        allocation_sha = hashlib.sha256(allocation_bytes).hexdigest()
        record = registry.get("workspaces", {}).get(exact["workspaceIdentity"])
        runtime = f"ws-{session.replace('-', '')}"
        runtime_root = f"{session_root}/runtime/{runtime}"
        workspace_keys = {
            "schemaVersion", "sessionId", "projectId", "canonicalRemote",
            "baseBranch", "branch", "mirrorPath", "worktreePath",
            "workerHost", "state", "expectedBaseCommit", "headCommit",
        }
        allocation_keys = {
            "schemaVersion", "sessionId", "projectId", "branch", "mirrorPath",
            "worktreePath", "runtimeId", "manifestRelativePath", "slot",
            "workloadClass", "state", "runtimeNames", "runtimeRoot", "logsPath",
            "artifactsRoot", "cacheRoot", "allocatedPorts", "heavyPermit",
        }
        registry_keys = {
            "schemaVersion", "selectionEnabled", "executionEnabled",
            "projectId", "repository", "branch", "commit", "manifestSha256",
            "runner", "workspaces",
        }
        if (
            set(workspace) != workspace_keys
            or workspace.get("schemaVersion") != 1
            or workspace.get("sessionId") != session
            or workspace.get("projectId") != PROJECT_ID
            or workspace.get("canonicalRemote") != REPOSITORY
            or workspace.get("baseBranch") != BRANCH
            or workspace.get("branch") != exact["workspaceBranch"]
            or workspace.get("mirrorPath") != "/srv/atenea/repositories/atenea.git"
            or workspace.get("worktreePath") != str(worktree)
            or workspace.get("workerHost") != self.worker_host
            or workspace.get("state") != "ready"
            or workspace.get("expectedBaseCommit") != exact["commit"]
            or workspace.get("headCommit") != exact["commit"]
            or not isinstance(record, dict)
            or set(record) != {
                "sessionId", "worktree", "allocationSha256", "canonicalCommit"
            }
            or record != {
                "sessionId": session,
                "worktree": str(worktree),
                "allocationSha256": allocation_sha,
                "canonicalCommit": exact["commit"],
            }
            or frozenset(registry) not in {
                frozenset(registry_keys), frozenset(registry_keys | {"attachmentRoot"})
            }
            or registry.get("schemaVersion") != "project-codex-v1"
            or registry.get("selectionEnabled") is not True
            or registry.get("executionEnabled") is not True
            or registry.get("projectId") != PROJECT_ID
            or registry.get("repository") != REPOSITORY
            or registry.get("branch") != BRANCH
            or registry.get("commit") != exact["commit"]
            or registry.get("manifestSha256") != MANIFEST_SHA256
            or registry.get("runner")
            != "/usr/local/libexec/atenea/project-codex-runner-v1.py"
            or (
                "attachmentRoot" in registry
                and registry.get("attachmentRoot") != "/srv/atenea/attachments-v1"
            )
            or registry.get("workspaces") != {exact["workspaceIdentity"]: record}
            or set(admission) != {"schemaVersion", "sessionId", "normal", "heavy"}
            or admission.get("schemaVersion") != 1
            or admission.get("sessionId") != session
            or not isinstance(admission.get("normal"), dict)
            or not isinstance(admission.get("heavy"), dict)
            or set(admission["normal"]) != {"slot", "state"}
            or set(admission["heavy"]) != {"permit", "state"}
            or set(allocation) != allocation_keys
            or allocation.get("schemaVersion") != 1
            or allocation.get("sessionId") != session
            or allocation.get("projectId") != PROJECT_ID
            or allocation.get("branch") != exact["workspaceBranch"]
            or allocation.get("mirrorPath") != "/srv/atenea/repositories/atenea.git"
            or allocation.get("worktreePath") != str(worktree)
            or allocation.get("runtimeId") != runtime
            or allocation.get("manifestRelativePath") != "ops/atenea-runtime.json"
            or allocation.get("workloadClass") != "heavy"
            or allocation.get("state") != "allocated"
            or allocation.get("runtimeNames") != {
                "composeProject": f"{runtime}-compose",
                "network": f"{runtime}-network",
                "volumePrefix": f"{runtime}-volume",
                "processUnit": f"atenea-{runtime}.service",
                "tomcatBase": f"{runtime_root}/tomcat",
            }
            or allocation.get("runtimeRoot") != runtime_root
            or allocation.get("logsPath")
            != f"/srv/atenea/artifacts/sessions/{session}/runtime/logs"
            or allocation.get("artifactsRoot")
            != f"/srv/atenea/artifacts/sessions/{session}/runs"
            or allocation.get("cacheRoot")
            != f"/srv/atenea/caches/sessions/{session}"
            or allocation.get("slot") not in {"slot1", "slot2", "slot3", "slot4"}
            or allocation.get("heavyPermit") not in {"heavy1", "heavy2"}
            or admission["normal"] != {
                "slot": allocation.get("slot"), "state": "held"
            }
            or admission["heavy"] != {
                "permit": allocation.get("heavyPermit"), "state": "held"
            }
        ):
            _reject()

        ports = allocation.get("allocatedPorts")
        if not isinstance(ports, list) or not ports:
            _reject()
        port_names: set[str] = set()
        loopback_ports: set[int] = set()
        for port in ports:
            port = _exact_dict(port, {
                "name", "internalPort", "protocol", "bindAddress", "loopbackPort",
            })
            if (
                not isinstance(port.get("name"), str)
                or re.fullmatch(r"[a-z][a-z0-9-]{1,62}", port["name"]) is None
                or port["name"] in port_names
                or type(port.get("internalPort")) is not int
                or not 1 <= port["internalPort"] <= 65535
                or port.get("protocol") not in {"http", "tcp"}
                or port.get("bindAddress") != "127.0.0.1"
                or type(port.get("loopbackPort")) is not int
                or not 1024 <= port["loopbackPort"] <= 65535
                or port["loopbackPort"] in loopback_ports
            ):
                _reject()
            port_names.add(port["name"])
            loopback_ports.add(port["loopbackPort"])

        self._require_directory(self._physical(worktree), self.worker_uid)
        if not self.test_mode:
            physical_worktree = self._physical(worktree)
            remote = self._run(
                [
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "remote", "get-url", "origin",
                ],
                15,
            ).stdout.strip()
            head = self._run(
                [
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "rev-parse", "--verify",
                    "HEAD^{commit}",
                ],
                15,
            ).stdout.strip()
            if remote != REPOSITORY or head != exact["commit"]:
                _reject()

        sealed = {
            "schemaVersion": CAPACITY_OWNER_SCHEMA,
            "state": "OWNED",
            "sessionId": session,
            "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "requestFingerprintSha256": canonical_hash(exact),
            "ownershipFingerprintSha256": canonical_hash({
                "sessionId": session,
                "workspaceIdentity": exact["workspaceIdentity"],
                "projectId": PROJECT_ID,
                "workerId": WORKER_ID,
                "canonicalCommit": exact["commit"],
                "allocationFingerprintSha256": allocation_sha,
            }),
            "valuesExposed": False,
        }
        return sealed

    def diagnose_unactivated(self, request: Any) -> dict[str, Any]:
        """Attest exact absence for a session that never acquired ownership."""

        exact = _request_identity(request)
        session = exact["sessionId"]
        session_root = Path(f"/srv/atenea/workspaces/sessions/{session}")
        workspace_path = session_root / "workspace-v1.json"
        worktree = session_root / PROJECT_ID
        allocation = session_root / "runtime-allocation-v1.json"
        retired = session_root / RETIRED_ALLOCATION_NAME
        admission = self.ADMISSION_ROOT / f"{session}.json"
        registry, _registry_stat, _registry_bytes = self._json_file(
            self.CONFIG, uid=self.root_uid, gid=self.root_gid, modes={0o644}
        )
        required_registry = {
            "schemaVersion", "selectionEnabled", "executionEnabled",
            "projectId", "repository", "branch", "commit", "manifestSha256",
            "runner", "workspaces",
        }
        if (
            frozenset(registry) not in {
                frozenset(required_registry),
                frozenset(required_registry | {"attachmentRoot"}),
            }
            or registry.get("schemaVersion") != "project-codex-v1"
            or registry.get("projectId") != PROJECT_ID
            or registry.get("repository") != REPOSITORY
            or registry.get("branch") != BRANCH
            or not isinstance(registry.get("commit"), str)
            or COMMIT.fullmatch(registry["commit"]) is None
            or registry.get("manifestSha256") != MANIFEST_SHA256
            or registry.get("runner")
            != "/usr/local/libexec/atenea/project-codex-runner-v1.py"
            or not isinstance(registry.get("selectionEnabled"), bool)
            or not isinstance(registry.get("executionEnabled"), bool)
            or not isinstance(registry.get("workspaces"), dict)
            or (
                "attachmentRoot" in registry
                and registry.get("attachmentRoot") != "/srv/atenea/attachments-v1"
            )
        ):
            _reject()
        for identity, record in registry["workspaces"].items():
            if (
                identity == exact["workspaceIdentity"]
                or not isinstance(record, dict)
                or record.get("sessionId") == session
                or record.get("worktree") == str(worktree)
            ):
                _reject()
        for forbidden in (allocation, retired, admission):
            physical = self._physical(forbidden)
            if physical.exists() or physical.is_symlink():
                _reject()

        physical_root = self._physical(session_root)
        workspace_retained = physical_root.exists() or physical_root.is_symlink()
        workspace_fingerprint = hashlib.sha256(b"absent").hexdigest()
        if workspace_retained:
            self._require_directory(physical_root, self.worker_uid)
            workspace, _workspace_stat, workspace_bytes = self._json_file(
                workspace_path,
                uid=self.worker_uid,
                gid=self.worker_gid,
                modes={0o640},
            )
            expected_workspace = {
                "schemaVersion", "sessionId", "projectId", "canonicalRemote",
                "baseBranch", "branch", "mirrorPath", "worktreePath",
                "workerHost", "state", "expectedBaseCommit", "headCommit",
            }
            if (
                set(workspace) != expected_workspace
                or workspace.get("schemaVersion") != 1
                or workspace.get("sessionId") != session
                or workspace.get("projectId") != PROJECT_ID
                or workspace.get("canonicalRemote") != REPOSITORY
                or workspace.get("baseBranch") != BRANCH
                or workspace.get("branch") != exact["workspaceBranch"]
                or workspace.get("mirrorPath")
                != "/srv/atenea/repositories/atenea.git"
                or workspace.get("worktreePath") != str(worktree)
                or workspace.get("workerHost") != self.worker_host
                or workspace.get("state") != "ready"
                or workspace.get("expectedBaseCommit") != exact["commit"]
                or workspace.get("headCommit") != exact["commit"]
            ):
                _reject()
            self._require_directory(self._physical(worktree), self.worker_uid)
            if not self.test_mode:
                physical_worktree = self._physical(worktree)
                remote = self._run([
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "remote", "get-url", "origin",
                ], 15).stdout.strip()
                head = self._run([
                    "/usr/bin/git", "-c", f"safe.directory={physical_worktree}",
                    "-C", str(physical_worktree), "rev-parse", "--verify",
                    "HEAD^{commit}",
                ], 15).stdout.strip()
                if remote != REPOSITORY or head != exact["commit"]:
                    _reject()
            workspace_fingerprint = hashlib.sha256(workspace_bytes).hexdigest()

        self._assert_unactivated_ephemeral_absent(session)
        absence = {
            "sessionId": session,
            "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "registrationPresent": False,
            "admissionPresent": False,
            "activeAllocationPresent": False,
            "retiredAllocationPresent": False,
            "ephemeralPresent": False,
            "workspaceRetained": workspace_retained,
            "workspaceFingerprintSha256": workspace_fingerprint,
        }
        return {
            "schemaVersion": UNACTIVATED_DIAGNOSIS_SCHEMA,
            "state": "UNACTIVATED_ABSENCE_CONFIRMED",
            "sessionId": session,
            "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "requestFingerprintSha256": canonical_hash(exact),
            "absenceFingerprintSha256": canonical_hash(absence),
            "valuesExposed": False,
        }

    def _assert_unactivated_ephemeral_absent(self, session: str) -> None:
        if self.test_mode:
            marker = self.root / "synthetic-ephemeral-present"
            if marker.exists() or marker.is_symlink():
                _reject()
            self._assert_no_owned_preview(session)
            return
        runtime = f"ws-{session.replace('-', '')}"
        docker = Path("/usr/bin/docker")
        hosts = ["unix:///run/docker.sock"] + [
            f"unix:///run/atenea-runtime/{slot}/docker.sock"
            for slot in ("slot1", "slot2", "slot3", "slot4")
        ]
        for host in hosts:
            if not Path(host.removeprefix("unix://")).exists():
                continue
            for arguments in (
                ("ps", "-aq", "--filter", f"label=com.atenea.session={session}"),
                ("ps", "-aq", "--filter", f"name={runtime}"),
                ("network", "ls", "-q", "--filter", f"label=com.atenea.session={session}"),
                ("network", "ls", "-q", "--filter", f"name={runtime}"),
                ("image", "ls", "-q", "--filter", f"label=com.atenea.session={session}"),
                ("image", "ls", "-q", f"{runtime}*"),
            ):
                if self._run([str(docker), "--host", host, *arguments], 20).stdout.strip():
                    _reject()
        self._assert_no_owned_preview(session)

    def diagnose_release_preflight(
        self,
        request: Any,
        journal_store: ReleaseJournalStore | None = None,
    ) -> dict[str, Any]:
        """Validate the complete release boundary without creating a journal.

        This deliberately accepts the closed release request rather than the
        smaller capacity-owner request.  It exercises the exact persisted
        operation identity, fixed roots and release projection while stopping
        before the first namespace or file mutation.
        """

        exact = _request_identity(request)
        store = journal_store or ReleaseJournalStore()
        session_root = store.root / exact["sessionId"]
        if session_root.exists() or session_root.is_symlink():
            store._require_directory(session_root)
            journal_path = session_root / "journal-v1.json"
            if journal_path.exists() or journal_path.is_symlink():
                projection = store.load(exact)["preflightProjection"]
            else:
                projection = self.build_projection(exact)
        else:
            projection = self.build_projection(exact)
        if "changeKey" in exact and projection != self.build_change_projection(exact):
            _reject()
        preflight = validate_release_preflight(exact, projection)
        return {
            "schemaVersion": RELEASE_PREFLIGHT_SCHEMA,
            "state": "PREFLIGHT_ACCEPTED",
            "operationId": exact["operationId"],
            "sessionId": exact["sessionId"],
            "workspaceIdentity": exact["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "workerId": WORKER_ID,
            "requestFingerprintSha256": preflight["requestFingerprintSha256"],
            "ownershipFingerprintSha256": preflight[
                "ownershipFingerprintSha256"
            ],
            "allocationFingerprintSha256": preflight[
                "allocationFingerprintSha256"
            ],
            "valuesExposed": False,
        }

    def _assert_no_ephemeral(
        self, session: str, allocation: dict[str, Any]
    ) -> None:
        if self.test_mode:
            marker = self.root / "synthetic-ephemeral-present"
            if marker.exists() or marker.is_symlink():
                _reject()
            self._assert_no_owned_preview(session)
            return
        runtime = allocation["runtimeId"]
        slot = allocation.get("slot")
        if slot not in {"slot1", "slot2", "slot3", "slot4"}:
            _reject()
        docker = Path("/usr/bin/docker")
        hosts = ["unix:///run/docker.sock"] + [
            f"unix:///run/atenea-runtime/{observed_slot}/docker.sock"
            for observed_slot in ("slot1", "slot2", "slot3", "slot4")
        ]
        for host in hosts:
            socket_path = Path(host.removeprefix("unix://"))
            if not socket_path.exists():
                continue
            for arguments in (
                ("ps", "-aq", "--filter", f"label=com.atenea.session={session}"),
                ("ps", "-aq", "--filter", f"name={runtime}"),
                ("network", "ls", "-q", "--filter", f"label=com.atenea.session={session}"),
                ("network", "ls", "-q", "--filter", f"name={runtime}"),
                ("image", "ls", "-q", "--filter", f"label=com.atenea.session={session}"),
                ("image", "ls", "-q", f"{runtime}*"),
            ):
                completed = self._run([str(docker), "--host", host, *arguments], 20)
                if completed.stdout.strip():
                    _reject()
        allocated_ports = {
            item.get("loopbackPort")
            for item in allocation.get("allocatedPorts", [])
            if isinstance(item, dict) and type(item.get("loopbackPort")) is int
        }
        completed = self._run(["/usr/bin/ss", "-H", "-lnt"], 10)
        for line in completed.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 4:
                try:
                    port = int(fields[3].rsplit(":", 1)[1])
                except (ValueError, IndexError):
                    continue
                if port in allocated_ports:
                    _reject()
        self._assert_no_owned_preview(session)
        self._assert_process_resources_absent()

    def _assert_process_resources_absent(self) -> None:
        if self.test_mode:
            return
        materialization_root = self._physical(self.MATERIALIZATION_ROOT)
        if materialization_root.exists():
            try:
                if any(materialization_root.iterdir()):
                    _reject()
            except OSError:
                _reject()
        units = self._run(
            [
                "/usr/bin/systemctl", "list-units", "--all", "--no-legend",
                "--plain", "atenea-project-codex-*", "atenea-playwright-*",
            ],
            15,
        )
        if units.stdout.strip():
            _reject()

    def _assert_no_owned_preview(self, session: str) -> None:
        preview_root = self._physical(self.PREVIEW_ROOT)
        if preview_root.exists():
            try:
                records = sorted(preview_root.glob("*/record.json"))
            except OSError:
                _reject()
            for record_path in records:
                try:
                    if record_path.is_symlink() or record_path.stat().st_size > 64 * 1024:
                        _reject()
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    _reject()
                if isinstance(record, dict) and (
                    record.get("workSessionId") == session
                    or record.get("runtimeSessionId") == session
                ):
                    _reject()

    @staticmethod
    def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            _reject()
        if completed.returncode != 0 or len(completed.stdout.encode()) > 64 * 1024:
            _reject()
        return completed

    @staticmethod
    def _require_directory(path: Path, uid: int) -> None:
        try:
            observed = path.lstat()
        except OSError:
            _reject()
        if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != uid:
            _reject()

    def remove_ephemeral(
        self, _category: str, _resource_id: str, _candidate: dict[str, Any]
    ) -> dict[str, Any]:
        raise PreflightRejected("WORKSPACE_RELEASE_BOUNDARY_UNAVAILABLE")

    def verify_ephemeral_projection(
        self, request: dict[str, str], projection: dict[str, Any]
    ) -> None:
        if any(projection[category] for category in EPHEMERAL_CATEGORIES):
            raise PreflightRejected("WORKSPACE_RELEASE_BOUNDARY_UNAVAILABLE")
        self._assert_no_ephemeral(request["sessionId"], projection["allocation"])

    def unregister_workspace(
        self, session: str, workspace_identity: str
    ) -> dict[str, Any]:
        config, _observed, content = self._json_file(
            self.CONFIG,
            uid=self.root_uid,
            gid=self.root_gid,
            modes={0o644},
        )
        workspaces = config.get("workspaces")
        if not isinstance(workspaces, dict):
            _reject()
        changed = workspace_identity in workspaces
        if changed:
            record = workspaces.get(workspace_identity)
            if not isinstance(record, dict) or record.get("sessionId") != session:
                _reject()
            if workspaces != {workspace_identity: record}:
                _reject()
            updated = dict(config)
            updated["selectionEnabled"] = False
            updated["executionEnabled"] = False
            updated["workspaces"] = {}
            self._atomic_json(
                self.CONFIG,
                updated,
                0o644,
                self.root_uid,
                self.root_gid,
                hashlib.sha256(content).hexdigest(),
            )
        elif (
            workspaces != {}
            or config.get("selectionEnabled") is not False
            or config.get("executionEnabled") is not False
        ):
            _reject()
        return {
            "schemaVersion": "atenea-workspace-unregistration-v1",
            "state": "UNREGISTERED",
            "sessionId": session,
            "workspaceIdentity": workspace_identity,
            "registrationRemoved": changed,
            "selectionEnabled": False,
            "executionEnabled": False,
            "remainingRegistrations": 0,
            "valuesExposed": False,
        }

    def release_admission(self, session: str, kind: str) -> dict[str, Any]:
        if kind not in {"heavy", "normal"}:
            _reject()
        record_path = self.ADMISSION_ROOT / f"{session}.json"
        before, _observed, content = self._json_file(
            record_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        current = before.get(kind)
        if not isinstance(current, dict) or current.get("state") not in {"held", "released"}:
            _reject()
        changed = current["state"] == "held"
        if self.test_mode:
            updated = json.loads(json.dumps(before))
            updated[kind]["state"] = "released"
            self._atomic_json(
                record_path,
                updated,
                0o640,
                self.worker_uid,
                self.worker_gid,
                hashlib.sha256(content).hexdigest(),
            )
        elif changed:
            command = [
                "/usr/sbin/runuser", "-u", "atenea-worker", "--",
                str(self.ADMISSION_TOOL), "--json", f"release-{kind}", session,
            ]
            completed = self._run(command, 45)
            if len(completed.stdout.encode()) > 4096:
                _reject()
        after, _after_stat, _after_content = self._json_file(
            record_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        if not isinstance(after.get(kind), dict) or after[kind].get("state") != "released":
            _reject()
        if kind == "normal" and (
            not isinstance(after.get("heavy"), dict)
            or after["heavy"].get("state") != "released"
        ):
            _reject()
        return {
            "schemaVersion": "atenea-admission-release-v1",
            "state": "RELEASED",
            "sessionId": session,
            "kind": kind,
            "changed": changed,
            "valuesExposed": False,
        }

    def verify_retained(
        self, session: str, projection: dict[str, Any]
    ) -> dict[str, Any]:
        session_root = Path(f"/srv/atenea/workspaces/sessions/{session}")
        workspace_path = session_root / "workspace-v1.json"
        self._json_file(
            workspace_path,
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        self._require_directory(self._physical(session_root / PROJECT_ID), self.worker_uid)
        config, _config_stat, _config_bytes = self._json_file(
            self.CONFIG,
            uid=self.root_uid,
            gid=self.root_gid,
            modes={0o644},
        )
        admission, _admission_stat, _admission_bytes = self._json_file(
            self.ADMISSION_ROOT / f"{session}.json",
            uid=self.worker_uid,
            gid=self.worker_gid,
            modes={0o640},
        )
        active = self._physical(session_root / "runtime-allocation-v1.json")
        retired = self._physical(session_root / RETIRED_ALLOCATION_NAME)
        if (
            config.get("workspaces") != {}
            or config.get("selectionEnabled") is not False
            or config.get("executionEnabled") is not False
            or admission.get("normal", {}).get("state") != "released"
            or admission.get("heavy", {}).get("state") != "released"
            or active.exists()
            or active.is_symlink()
            or not retired.is_file()
            or retired.is_symlink()
        ):
            _reject()
        self._assert_no_ephemeral(session, projection["allocation"])
        return {
            "schemaVersion": "atenea-workspace-release-proof-v1",
            "state": "RELEASED",
            "sessionId": session,
            "ephemeralRemaining": 0,
            "registrationPresent": False,
            "normalAdmission": "released",
            "heavyAdmission": "released",
            "activeAllocationPresent": False,
            "retiredAllocationPresent": True,
            "retained": {key: True for key in sorted(RETAINED_KEYS)},
            "valuesExposed": False,
        }

    def _atomic_json(
        self,
        canonical: Path,
        payload: dict[str, Any],
        mode: int,
        uid: int,
        gid: int,
        expected_sha256: str,
    ) -> None:
        target = self._physical(canonical)
        descriptor = -1
        temporary = ""
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            os.fchmod(descriptor, mode)
            if not self.test_mode:
                os.fchown(descriptor, uid, gid)
            encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
            written = 0
            while written < len(encoded):
                written += os.write(descriptor, encoded[written:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            _current, _current_stat, current_content = self._json_file(
                canonical, uid=uid, gid=gid, modes={mode}
            )
            if hashlib.sha256(current_content).hexdigest() != expected_sha256:
                _reject()
            os.replace(temporary, target)
            temporary = ""
            ReleaseJournalStore._fsync_directory(target.parent)
        except OSError:
            _reject()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


class WorkspaceReleaseFinalizer:
    """Ordered exact release orchestration over a reviewed internal boundary."""

    def __init__(
        self,
        journal_store: ReleaseJournalStore,
        boundary: Any | None = None,
    ):
        self.journal_store = journal_store
        self.boundary = boundary or UnavailableReleaseBoundary()

    def release(self, request: Any, projection: Any) -> dict[str, Any]:
        exact_request = _request_identity(request)
        journal = self.journal_store.open_or_prepare(exact_request, projection)
        stored_projection = journal["preflightProjection"]
        preflight = validate_release_preflight(exact_request, stored_projection)

        if "changeKey" in exact_request:
            # No legacy resources are fabricated or removed. Recheck direct ownership
            # on retries, including RELEASED, before returning the exact durable receipt.
            observed = self.boundary.operator.build_change_projection(exact_request)
            if observed != stored_projection:
                _reject()
            for previous, following in zip(JOURNAL_STAGES, JOURNAL_STAGES[1:]):
                if journal["state"] == previous:
                    journal = self.journal_store.advance(
                        exact_request, previous, following,
                        preflight["ownershipFingerprintSha256"],
                    )
            return self._result(exact_request, preflight, journal)

        if journal["state"] == "PREPARED":
            ephemeral = self.boundary.release_ephemeral(
                exact_request, stored_projection
            )
            ephemeral = self._validate_ephemeral(ephemeral, preflight)
            journal = self.journal_store.advance(
                exact_request,
                "PREPARED",
                "EPHEMERAL_RELEASED",
                canonical_hash(ephemeral),
            )

        if journal["state"] == "EPHEMERAL_RELEASED":
            registration = self.boundary.unregister_workspace(exact_request)
            registration = self._validate_registration(registration, exact_request)
            journal = self.journal_store.advance(
                exact_request,
                "EPHEMERAL_RELEASED",
                "UNREGISTERED",
                canonical_hash(registration),
            )

        if journal["state"] == "UNREGISTERED":
            heavy = self.boundary.release_heavy_admission(exact_request)
            heavy = self._validate_admission(heavy, exact_request, "heavy")
            normal = self.boundary.release_normal_admission(exact_request)
            normal = self._validate_admission(normal, exact_request, "normal")
            journal = self.journal_store.advance(
                exact_request,
                "UNREGISTERED",
                "ADMISSION_RELEASED",
                canonical_hash({"heavy": heavy, "normal": normal}),
            )

        if journal["state"] == "ADMISSION_RELEASED":
            allocation = self.boundary.retire_allocation(
                exact_request, preflight["allocationFingerprintSha256"]
            )
            allocation = self._validate_allocation(
                allocation, exact_request, preflight
            )
            journal = self.journal_store.advance(
                exact_request,
                "ADMISSION_RELEASED",
                "ALLOCATION_RETIRED",
                canonical_hash(allocation),
            )

        if journal["state"] == "ALLOCATION_RETIRED":
            retained = self.boundary.verify_retained(
                exact_request, stored_projection
            )
            retained = self._validate_retained(retained, exact_request)
            journal = self.journal_store.advance(
                exact_request,
                "ALLOCATION_RETIRED",
                "RELEASED",
                canonical_hash(retained),
            )
        return self._result(exact_request, preflight, journal)

    @staticmethod
    def _validate_ephemeral(
        result: Any, preflight: dict[str, Any]
    ) -> dict[str, Any]:
        result = _exact_dict(result, {
            "schemaVersion", "state", "removed", "changed",
            "policyVolumesRetained", "valuesExposed",
        })
        counts = preflight["candidateCounts"]
        if (
            result.get("schemaVersion") != "atenea-ephemeral-release-v1"
            or result.get("state") != "RELEASED"
            or result.get("removed") != {
                category: counts[category] for category in EPHEMERAL_CATEGORIES
            }
            or not isinstance(result.get("changed"), dict)
            or set(result["changed"]) != set(EPHEMERAL_CATEGORIES)
            or any(
                type(result["changed"].get(category)) is not int
                or not 0 <= result["changed"][category] <= counts[category]
                for category in EPHEMERAL_CATEGORIES
            )
            or result.get("policyVolumesRetained") is not True
            or result.get("valuesExposed") is not False
        ):
            _reject()
        return dict(result)

    @staticmethod
    def _validate_registration(
        result: Any, request: dict[str, str]
    ) -> dict[str, Any]:
        result = _exact_dict(result, {
            "schemaVersion", "state", "sessionId", "workspaceIdentity",
            "registrationRemoved", "selectionEnabled", "executionEnabled",
            "remainingRegistrations", "valuesExposed",
        })
        if (
            result.get("schemaVersion") != "atenea-workspace-unregistration-v1"
            or result.get("state") != "UNREGISTERED"
            or result.get("sessionId") != request["sessionId"]
            or result.get("workspaceIdentity") != request["workspaceIdentity"]
            or type(result.get("registrationRemoved")) is not bool
            or result.get("selectionEnabled") is not False
            or result.get("executionEnabled") is not False
            or result.get("remainingRegistrations") != 0
            or result.get("valuesExposed") is not False
        ):
            _reject()
        return dict(result)

    @staticmethod
    def _validate_admission(
        result: Any, request: dict[str, str], kind: str
    ) -> dict[str, Any]:
        result = _exact_dict(result, {
            "schemaVersion", "state", "sessionId", "kind", "changed",
            "valuesExposed",
        })
        if (
            result.get("schemaVersion") != "atenea-admission-release-v1"
            or result.get("state") != "RELEASED"
            or result.get("sessionId") != request["sessionId"]
            or result.get("kind") != kind
            or type(result.get("changed")) is not bool
            or result.get("valuesExposed") is not False
        ):
            _reject()
        return dict(result)

    @staticmethod
    def _validate_allocation(
        result: Any,
        request: dict[str, str],
        preflight: dict[str, Any],
    ) -> dict[str, Any]:
        result = _exact_dict(result, {
            "schemaVersion", "state", "sessionId", "sourceName",
            "retiredName", "fingerprintSha256", "device", "inode", "uid",
            "gid", "mode", "size", "mtimeNs", "atimeBeforeNs",
            "atimeAfterNs", "ctimeBeforeNs", "ctimeAfterNs", "changed",
            "valuesExposed",
        })
        numeric = (
            "device", "inode", "uid", "gid", "mode", "size", "mtimeNs",
            "atimeBeforeNs", "atimeAfterNs", "ctimeBeforeNs", "ctimeAfterNs",
        )
        if (
            result.get("schemaVersion") != "atenea-allocation-retirement-v1"
            or result.get("state") != "RETIRED"
            or result.get("sessionId") != request["sessionId"]
            or result.get("sourceName") != "runtime-allocation-v1.json"
            or result.get("retiredName") != RETIRED_ALLOCATION_NAME
            or result.get("fingerprintSha256")
            != preflight["allocationFingerprintSha256"]
            or any(type(result.get(key)) is not int or result[key] < 0 for key in numeric)
            or result.get("mode") not in {0o600, 0o640}
            or type(result.get("changed")) is not bool
            or result.get("atimeAfterNs") < result.get("atimeBeforeNs")
            or result.get("ctimeAfterNs") < result.get("ctimeBeforeNs")
            or result.get("valuesExposed") is not False
        ):
            _reject()
        return dict(result)

    @staticmethod
    def _validate_retained(
        result: Any, request: dict[str, str]
    ) -> dict[str, Any]:
        result = _exact_dict(result, {
            "schemaVersion", "state", "sessionId", "ephemeralRemaining",
            "registrationPresent", "normalAdmission", "heavyAdmission",
            "activeAllocationPresent", "retiredAllocationPresent", "retained",
            "valuesExposed",
        })
        if (
            result.get("schemaVersion") != "atenea-workspace-release-proof-v1"
            or result.get("state") != "RELEASED"
            or result.get("sessionId") != request["sessionId"]
            or result.get("ephemeralRemaining") != 0
            or result.get("registrationPresent") is not False
            or result.get("normalAdmission") != "released"
            or result.get("heavyAdmission") != "released"
            or result.get("activeAllocationPresent") is not False
            or result.get("retiredAllocationPresent") is not True
            or not isinstance(result.get("retained"), dict)
            or set(result["retained"]) != RETAINED_KEYS
            or any(value is not True for value in result["retained"].values())
            or result.get("valuesExposed") is not False
        ):
            _reject()
        return dict(result)

    @staticmethod
    def _result(
        request: dict[str, str],
        preflight: dict[str, Any],
        journal: dict[str, Any],
    ) -> dict[str, Any]:
        counts = preflight["candidateCounts"]
        receipt = {
            "schemaVersion": "project-workspace-release-v1",
            "state": "RELEASED",
            "operationId": request["operationId"],
            "idempotencyKey": request["idempotencyKey"],
            "sessionId": request["sessionId"],
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "repository": request["repository"],
            "branch": request["branch"],
            "commit": request.get("commit"),
            "manifestSha256": request.get("manifestSha256"),
            "workspaceBranch": request["workspaceBranch"],
            "workerId": WORKER_ID,
            "revision": journal["revision"],
            "requestFingerprintSha256": journal["requestFingerprintSha256"],
            "ownershipFingerprintSha256": journal["ownershipFingerprintSha256"],
            "removed": {
                "runtimeContainers": counts["runtimeContainers"],
                "runtimeNetworks": counts["runtimeNetworks"],
                "sessionImages": counts["sessionImages"],
                "previewResources": counts["previewResources"] + counts["listeners"],
                "brokerResources": counts["brokerResources"],
                "browserProcesses": counts["materializations"] + counts["browserProcesses"],
            },
            "released": {
                "registration": True,
                "normalAdmission": True,
                "heavyAdmission": True,
                "allocation": True,
            },
            "retained": {key: True for key in sorted(RETAINED_KEYS)},
            "valuesExposed": False,
        }
        if "changeKey" in request:
            receipt.pop("commit")
            receipt.pop("manifestSha256")
            receipt.update({key: request[key] for key in (
                "changeKey", "databaseWorkSessionId", "databaseProjectId", "baseCommit",
            )})
            receipt["released"] = {key: False for key in receipt["released"]}
        receipt["receiptSha256"] = canonical_hash(receipt)
        return receipt


def main() -> int:
    diagnose = sys.argv[1:] == ["--diagnose-capacity-owner"]
    diagnose_release = sys.argv[1:] == ["--diagnose-release-preflight"]
    diagnose_unactivated = sys.argv[1:] == ["--diagnose-unactivated"]
    if len(sys.argv) != 1 and not diagnose and not diagnose_release and not diagnose_unactivated:
        print(json.dumps({"code": "WORKSPACE_RELEASE_PREFLIGHT_REJECTED"}), file=sys.stderr)
        return 64
    try:
        encoded = sys.stdin.buffer.read(65_537)
        if len(encoded) < 2 or len(encoded) > 65_536:
            _reject()
        request = json.loads(encoded)
        if diagnose:
            diagnosis = FixedRootReleaseOperator().diagnose_capacity_owner(request)
            print(json.dumps(diagnosis, sort_keys=True, separators=(",", ":")))
            return 0
        if diagnose_release:
            diagnosis = FixedRootReleaseOperator().diagnose_release_preflight(request)
            print(json.dumps(diagnosis, sort_keys=True, separators=(",", ":")))
            return 0
        if diagnose_unactivated:
            diagnosis = FixedRootReleaseOperator().diagnose_unactivated(request)
            print(json.dumps(diagnosis, sort_keys=True, separators=(",", ":")))
            return 0
        exact = _request_identity(request)
        store = ReleaseJournalStore()
        journal_path = JOURNAL_ROOT / exact["sessionId"] / "journal-v1.json"
        operator = FixedRootReleaseOperator()
        if journal_path.exists() or journal_path.is_symlink():
            projection = store.load(exact)["preflightProjection"]
        else:
            projection = operator.build_projection(exact)
        finalizer = WorkspaceReleaseFinalizer(
            store,
            ReviewedReleaseBoundary(operator, AllocationRetirer()),
        )
        receipt = finalizer.release(exact, projection)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0
    except (json.JSONDecodeError, UnicodeDecodeError, PreflightRejected) as error:
        code = (
            error.code
            if isinstance(error, PreflightRejected)
            else "WORKSPACE_RELEASE_PREFLIGHT_REJECTED"
        )
        print(json.dumps({"code": code}, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 65
    except Exception:
        print(json.dumps({"code": "OPERATION_FAILED"}), file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
