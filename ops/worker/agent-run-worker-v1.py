#!/usr/bin/env python3
"""Canonical AX42 AgentRun worker with exact project opt-in."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import signal
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

PROTOCOL = "agent-run-worker/v1"
SYNTHETIC_CAPABILITY = "synthetic-routing-v1"
PROJECT_CAPABILITY = "project-codex-v1"
PROJECT_V2_CAPABILITY = "project-codex-v2"
PROJECT_V3_CAPABILITY = "project-codex-v3"
PROJECT_V4_CAPABILITY = "project-codex-v4"
CODEX_CATALOG_CAPABILITY = "codex-model-catalog-v1"
CODEX_UPDATE_STAGE_CAPABILITY = "codex-update-stage-v1"
CODEX_UPDATE_ACTIVATE_CAPABILITY = "codex-update-activate-v1"
CODEX_UPDATE_ROLLBACK_CAPABILITY = "codex-update-rollback-v1"
DEVELOPMENT_CHANGE_WORKSPACE_CAPABILITY = "development-change-workspace/v1"
DEVELOPMENT_CHANGE_WORKSPACE_PATH_PREFIX = "/v1/development-changes/workspaces/"
CODEX_CATALOG_SCHEMA = "codex-model-catalog-v1"
CODEX_VERSION = "0.145.0"
CODEX_MODELS = [
    {
        "modelId": "gpt-5.6-sol",
        "displayName": "GPT-5.6 Sol",
        "supportedEfforts": ["none", "low", "medium", "high", "xhigh", "max"],
        "defaultEffort": "medium",
        "availability": "AVAILABLE",
    }
]
PROGRESS_LIMIT = 200
WORKER_ERROR_SCHEMA = "worker-error-v1"
WORKER_ERROR_MAX_BYTES = 1024
MEDIATOR_ERROR_MAX_BYTES = 4096
WORKER_ERROR_CATEGORIES = {
    "VALIDATION", "POLICY", "OWNERSHIP", "CAPACITY", "PROTOCOL", "TRANSPORT",
}
WORKER_ERROR_NEXT_ACTIONS = {
    "NONE", "WAIT", "RETRY", "REQUEST_RECONCILIATION",
    "CONTACT_PLATFORM_ADMINISTRATOR",
}
WORKER_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
MEDIATOR_ERROR_KEYS = {"code", "blockerSessionId"}
REVIEWED_MEDIATOR_ERRORS = {
    "NORMAL_CAPACITY_EXHAUSTED": ("CAPACITY", True, "WAIT"),
    "HEAVY_CAPACITY_EXHAUSTED": ("CAPACITY", True, "WAIT"),
    "RUNTIME_OWNERSHIP_CONFLICT": (
        "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
    "RECONCILIATION_REQUIRED": (
        "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
    "OPERATION_FAILED": ("POLICY", False, "CONTACT_PLATFORM_ADMINISTRATOR"),
    "ATENEA_WORKSPACE_ACTIVATION_REJECTED": (
        "VALIDATION", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
    "WORKSPACE_RELEASE_PREFLIGHT_REJECTED": (
        "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
    "WORKSPACE_RELEASE_BOUNDARY_UNAVAILABLE": (
        "POLICY", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
    "DEVELOPMENT_CHANGE_WORKSPACE_REJECTED": (
        "OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR",
    ),
}
PROGRESS_CATEGORIES = {
    "ACCEPTED", "QUEUED", "PREPARING_WORKSPACE", "CODEX_STARTED",
    "INSPECTING_PROJECT", "RUNNING_COMMAND", "CHECKING", "WAITING",
    "RECONCILING", "FINALIZING", "COMPLETED", "FAILED", "CANCELLED",
}
RUNNER_PROGRESS_MESSAGES = {
    "CODEX_STARTED": "Codex started the accepted turn.",
    "INSPECTING_PROJECT": "Inspecting the accepted project.",
    "RUNNING_COMMAND": "Running a reviewed project operation.",
    "CHECKING": "Checking the accepted project.",
    "WAITING": "Waiting for a bounded operation.",
    "FINALIZING": "Finalizing the Codex turn.",
}
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
NON_TERMINAL = {"QUEUED", "STARTING", "RUNNING", "CANCELLING", "RECONCILING"}
CREATE_KEYS = {
    "dispatchId", "sessionId", "workspaceIdentity", "workloadClass", "leaseGeneration", "workload"
}
CHANGE_CREATE_KEYS = CREATE_KEYS | {"changeOwnership"}
SYNTHETIC_WORKLOAD_KEYS = {"kind", "message", "durationMs", "steps"}
PROJECT_WORKLOAD_KEYS = {
    "kind", "projectId", "repository", "branch", "commit",
    "manifestSha256", "message", "threadId", "instructionBundleRevision",
    "instructionBundleSha256", "platformInstructionSha256",
    "projectInstructionPath", "projectInstructionSha256",
}
PROJECT_V2_WORKLOAD_KEYS = PROJECT_WORKLOAD_KEYS | {
    "modelId", "reasoningEffort", "catalogRevision", "codexVersion",
}
PROJECT_V3_WORKLOAD_KEYS = PROJECT_V2_WORKLOAD_KEYS | {"attachments"}
PROJECT_V4_WORKLOAD_KEYS = PROJECT_V3_WORKLOAD_KEYS
PROJECT_V3_ATTACHMENT_KEYS = {"attachmentId", "contentType", "sizeBytes", "sha256"}
PROJECT_V3_ATTACHMENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
PROJECT_V3_MAX_ATTACHMENTS = 4
PROJECT_V3_MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
PROJECT_V3_MAX_TOTAL_BYTES = 32 * 1024 * 1024
CHANGE_OWNERSHIP_KEYS = {
    "changeKey", "databaseWorkSessionId", "remoteSessionId",
    "workspaceIdentity", "databaseProjectId", "baseCommit",
    "expectedCanonicalCommit", "sourceRevision",
    "sourceFingerprintSha256", "workspaceOwnershipFingerprintSha256",
}
WORKSPACE_ENSURE_KEYS = {
    "sessionId", "workspaceIdentity", "projectId", "repository", "branch",
    "commit", "manifestSha256", "workspaceBranch",
}
WORKSPACE_RELEASE_PATH = "/v1/project-workspaces/release"
WORKSPACE_RELEASE_PREFLIGHT_PATH = "/v1/project-workspaces/release-preflight"
WORKSPACE_CAPACITY_OWNER_PATH = "/v1/project-workspaces/capacity-owner"
WORKSPACE_READINESS_PATH = "/v1/project-workspaces/readiness"
WORKSPACE_UNACTIVATED_RELEASE_PATH = "/v1/project-workspaces/release-unactivated"
WORKSPACE_RELEASE_PREFLIGHT_SCHEMA = "project-workspace-release-diagnosis-v1"
WORKSPACE_CAPACITY_OWNER_SCHEMA = "project-workspace-capacity-owner-v1"
WORKSPACE_READINESS_SCHEMA = "project-workspace-readiness-v1"
WORKSPACE_UNACTIVATED_DIAGNOSIS_SCHEMA = "project-workspace-unactivated-diagnosis-v1"
WORKSPACE_CAPACITY_OWNER_KEYS = WORKSPACE_ENSURE_KEYS
WORKSPACE_CAPACITY_OWNER_RESPONSE_KEYS = {
    "schemaVersion", "state", "sessionId", "workspaceIdentity", "projectId",
    "workerId", "requestFingerprintSha256", "ownershipFingerprintSha256",
    "valuesExposed",
}
WORKSPACE_READINESS_KEYS = WORKSPACE_ENSURE_KEYS
WORKSPACE_READINESS_RESPONSE_KEYS = {
    "schemaVersion", "state", "sessionId", "workspaceIdentity", "projectId",
    "workerId", "requestedCommit", "canonicalCommit", "retryAllowed",
    "nextAction", "requestFingerprintSha256", "relationshipFingerprintSha256",
    "valuesExposed",
}
WORKSPACE_UNACTIVATED_DIAGNOSIS_KEYS = {
    "schemaVersion", "state", "sessionId", "workspaceIdentity", "projectId",
    "workerId", "requestFingerprintSha256", "absenceFingerprintSha256",
    "valuesExposed",
}
WORKSPACE_RELEASE_SCHEMA = "project-workspace-release-v1"
WORKSPACE_RELEASE_REVISION = 6
WORKSPACE_RELEASE_REQUEST_KEYS = {
    "operationId", "idempotencyKey", "sessionId", "workspaceIdentity",
    "projectId", "repository", "branch", "commit", "manifestSha256",
    "workspaceBranch",
}
WORKSPACE_RELEASE_PREFLIGHT_RESPONSE_KEYS = {
    "schemaVersion", "state", "operationId", "sessionId",
    "workspaceIdentity", "projectId", "workerId",
    "requestFingerprintSha256", "ownershipFingerprintSha256",
    "allocationFingerprintSha256", "valuesExposed",
}
WORKSPACE_RELEASE_RECEIPT_KEYS = {
    "schemaVersion", "state", "operationId", "idempotencyKey", "sessionId",
    "workspaceIdentity", "projectId", "repository", "branch", "commit",
    "manifestSha256", "workspaceBranch", "workerId", "requestFingerprintSha256",
    "revision", "removed", "released", "retained",
    "ownershipFingerprintSha256", "receiptSha256", "valuesExposed",
}
WORKSPACE_RELEASE_REMOVED_KEYS = {
    "runtimeContainers", "runtimeNetworks", "sessionImages", "previewResources",
    "brokerResources", "browserProcesses",
}
WORKSPACE_RELEASE_RELEASED_KEYS = {
    "registration", "normalAdmission", "heavyAdmission", "allocation",
}
WORKSPACE_RELEASE_RETAINED_KEYS = {
    "workspaceRecord", "worktree", "git", "turns", "agentRuns", "attachments",
    "logs", "artifacts", "backups", "policyVolumes",
}
DRAFT_FINGERPRINT_KEYS = {
    "sessionId", "workspaceIdentity", "projectId", "repository", "branch",
    "acceptedCommit", "manifestSha256",
}
SOURCE_TREE_FINGERPRINT_KEYS = {
    "sessionId", "workspaceIdentity", "projectId", "repository", "branch",
    "commit", "manifestSha256",
}
VALIDATION_KEYS = {
    "validationId", "sessionId", "workspaceIdentity", "projectId",
    "repository", "branch", "commit", "manifestSha256", "operation",
    "definitionRevision", "sourceTreeFingerprintSha256",
}
REPOSITORY_ROLE_KEYS = {
    "sessionId", "workspaceIdentity", "changeIdentity", "codeCommit",
}
CODEX_UPDATE_STAGE_KEYS = {
    "operation", "planId", "candidateId", "idempotencyKey",
}
CODEX_UPDATE_STAGE_RESULT_KEYS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "idempotencyKey", "state", "codexVersion", "releaseDigestSha256",
    "catalogRevision", "releaseManifestSha256", "schemaManifestSha256",
    "releaseVerification", "schemaGeneration", "retention",
    "currentLinkFingerprint", "previousLinkFingerprint", "linksChanged",
    "valuesExposed",
}
CODEX_UPDATE_ACTIVATE_KEYS = {
    "operation", "planId", "candidateId", "authorizationId", "idempotencyKey",
}
CODEX_UPDATE_ACTIVATE_RESULT_KEYS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "authorizationId", "idempotencyKey", "state", "codexVersion",
    "releaseDigestSha256", "catalogRevision", "schemaComparison",
    "focusedContracts", "workerHealth", "canary", "currentBeforeFingerprint",
    "previousBeforeFingerprint", "currentAfterFingerprint",
    "previousAfterFingerprint", "automaticRestore", "valuesExposed",
}
CODEX_UPDATE_ROLLBACK_KEYS = {
    "operation", "planId", "candidateId", "activationId", "authorizationId",
    "idempotencyKey",
}
CODEX_UPDATE_ROLLBACK_RESULT_KEYS = {
    "schemaVersion", "operation", "workerId", "planId", "candidateId",
    "activationId", "authorizationId", "idempotencyKey", "state",
    "linkRestore", "workerServiceRestart", "affectedServices",
    "appServerServicesRestarted", "currentBeforeFingerprint",
    "previousBeforeFingerprint", "currentAfterFingerprint",
    "previousAfterFingerprint", "valuesExposed",
}
DEVELOPMENT_CHANGE_WORKSPACE_REQUEST_KEYS = {
    "schemaVersion", "protocolVersion", "effect", "operationId",
    "idempotencyKey", "operation", "predecessorOperationId", "changeKey",
    "databaseProjectId", "projectId", "repository", "repositoryBranch",
    "baseCommit", "expectedCanonicalCommit", "workspaceBranch",
    "workspaceIdentity", "workerId", "sourceRevision",
    "sourceFingerprintSha256", "requestFingerprintSha256",
}
DEVELOPMENT_CHANGE_WORKSPACE_RESPONSE_KEYS = {
    "schemaVersion", "protocolVersion", "state", "effect", "operationId",
    "idempotencyKey", "operation", "predecessorOperationId", "changeKey",
    "databaseProjectId", "projectId", "repository", "repositoryBranch",
    "baseCommit", "expectedCanonicalCommit", "workspaceBranch",
    "workspaceIdentity", "workerId", "sourceRevision",
    "expectedSourceFingerprintSha256", "canonicalCommit",
    "sourceFingerprintSha256", "workspaceDirty", "retainedDraft",
    "requestFingerprintSha256", "ownershipFingerprintSha256", "valuesExposed",
}
EXACT_EXECUTION_OPERATION_KEYS = {
    "executionId", "sessionId", "workspaceIdentity", "leaseGeneration",
}
VALIDATION_DEFINITIONS = {
    "BACKEND_TEST": ("atenea-backend-test-v1", 900),
    "WEB_BUILD": ("atenea-web-build-v1", 600),
    "ANDROID_BUILD": ("atenea-android-build-v1", 1200),
    "PLAYWRIGHT_ACCEPTANCE": ("atenea-playwright-acceptance-v1", 600),
}
PROJECT_ID = "atenea"
PROJECT_REPOSITORY = "https://github.com/jlnieto/atenea.git"
PROJECT_BRANCH = "main"
PROJECT_MANIFEST_SHA256 = "327a0c521017109d7c0067a11e7d8c3ad2079de4ea78d28296848f9de39c164b"
INSTRUCTION_BUNDLE_REVISION = "atenea-reviewed-instruction-bundle-v1"
PLATFORM_INSTRUCTION_SHA256 = "44c578a286eb50b35612be0b6c38d59a503e6fee1ecf6cd0339415af018cdf0d"
PROJECT_INSTRUCTION_PATH = "AGENTS.md"
ATENEA_PROJECT_INSTRUCTION_SHA256 = "a09adc5855ff54490211a0f5c82f413cb84ee7197b2b350e0b0dc40eba7c98dc"
ATENEA_INSTRUCTION_BUNDLE_SHA256 = "ab9f1877c83333945497797e6b8aefd20f67debf8e3bdc6d1b824fc5a3f86c04"
PROJECT_MIRROR = Path("/srv/atenea/repositories/atenea.git")
PROJECT_ATTACHMENT_ROOT = "/srv/atenea/attachments-v1"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BEAUTIPS_PROJECT_ID = "beautips"
BEAUTIPS_PROJECT_REPOSITORY = "https://github.com/jlnieto/beautips.git"
BEAUTIPS_PROJECT_BRANCH = "main"
BEAUTIPS_PROJECT_COMMIT = "e9e0b3c319c518363d4135f5378ebbddced96dfb"
BEAUTIPS_PROJECT_MANIFEST_SHA256 = (
    "365f1c66c51c9018c2c6f48deddbaa619b4588cae2dd463dcd916cde884e2e82"
)
BEAUTIPS_PROJECT_INSTRUCTION_SHA256 = "0e06aa861b11e324610f3a7cd7aef1bff3c2712d7b838a052bb5748542c8e1c7"
BEAUTIPS_INSTRUCTION_BUNDLE_SHA256 = "6e5affe84ca7e300c1c3f0907056013820999699d84fd0e491add924ad685b60"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def strict_json_object(raw: str) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    parsed = json.loads(raw, object_pairs_hook=unique_pairs)
    if not isinstance(parsed, dict):
        raise ValueError("JSON response is not an object")
    return parsed


def validate_workspace_release_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != WORKSPACE_RELEASE_REQUEST_KEYS:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_workspace_release_request",
            "workspace release request fields are invalid",
        )
    canonical: dict[str, str] = {}
    for key in ("operationId", "idempotencyKey", "sessionId"):
        try:
            value = str(uuid.UUID(request.get(key)))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workspace_release_identity",
                "workspace release identity must be a canonical UUID",
            ) from None
        if value != request.get(key):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workspace_release_identity",
                "workspace release identity must be a canonical UUID",
            )
        canonical[key] = value
    session_id = canonical["sessionId"]
    exact = {
        "workspaceIdentity": f"remote:ax42-01:work-session:{session_id}",
        "projectId": PROJECT_ID,
        "repository": PROJECT_REPOSITORY,
        "branch": PROJECT_BRANCH,
        "manifestSha256": PROJECT_MANIFEST_SHA256,
        "workspaceBranch": f"atenea/session-{session_id}",
    }
    if any(request.get(key) != value for key, value in exact.items()):
        raise ProtocolError(
            HTTPStatus.FORBIDDEN,
            "workspace_release_ownership_conflict",
            "workspace release ownership is not exact",
        )
    commit = request.get("commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_workspace_release_commit",
            "workspace release commit is invalid",
        )
    return dict(request)


def validate_workspace_capacity_owner_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != WORKSPACE_CAPACITY_OWNER_KEYS:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_workspace_capacity_owner_request",
            "workspace capacity-owner request fields are invalid",
        )
    session_id = request.get("sessionId")
    try:
        canonical_session = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_workspace_capacity_owner_identity",
            "workspace capacity-owner identity must be canonical",
        ) from None
    exact = {
        "sessionId": canonical_session,
        "workspaceIdentity": f"remote:ax42-01:work-session:{canonical_session}",
        "projectId": PROJECT_ID,
        "repository": PROJECT_REPOSITORY,
        "branch": PROJECT_BRANCH,
        "manifestSha256": PROJECT_MANIFEST_SHA256,
        "workspaceBranch": f"atenea/session-{canonical_session}",
    }
    if session_id != canonical_session or any(
        request.get(key) != value for key, value in exact.items()
    ):
        raise ProtocolError(
            HTTPStatus.FORBIDDEN,
            "workspace_capacity_owner_conflict",
            "workspace capacity-owner identity is not exact",
        )
    commit = request.get("commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_workspace_capacity_owner_commit",
            "workspace capacity-owner commit is invalid",
        )
    return dict(request)


def validate_workspace_capacity_owner_response(
    request: dict[str, Any], worker_id: str, response: dict[str, Any]
) -> dict[str, Any]:
    exact = validate_workspace_capacity_owner_request(request)
    if (
        not isinstance(response, dict)
        or set(response) != WORKSPACE_CAPACITY_OWNER_RESPONSE_KEYS
        or response.get("schemaVersion") != WORKSPACE_CAPACITY_OWNER_SCHEMA
        or response.get("state") != "OWNED"
        or response.get("sessionId") != exact["sessionId"]
        or response.get("workspaceIdentity") != exact["workspaceIdentity"]
        or response.get("projectId") != PROJECT_ID
        or response.get("workerId") != worker_id
        or response.get("requestFingerprintSha256") != canonical_hash(exact)
        or response.get("valuesExposed") is not False
        or not isinstance(response.get("ownershipFingerprintSha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", response["ownershipFingerprintSha256"])
        is None
    ):
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_capacity_owner_response_invalid",
            "workspace capacity-owner response is invalid",
        )
    return dict(response)


def validate_workspace_readiness_request(request: dict[str, Any]) -> dict[str, Any]:
    exact = validate_workspace_capacity_owner_request(request)
    if exact["projectId"] != PROJECT_ID:
        raise ProtocolError(
            HTTPStatus.FORBIDDEN,
            "workspace_readiness_project_conflict",
            "workspace readiness is restricted to canonical Atenea",
        )
    return exact


def validate_workspace_readiness_response(
    request: dict[str, Any], worker_id: str, response: dict[str, Any]
) -> dict[str, Any]:
    exact = validate_workspace_readiness_request(request)
    state = response.get("state") if isinstance(response, dict) else None
    expected_action = {
        "READY_FOR_RETRY": "RETRY_AGENT_RUN",
        "SOURCE_ADVANCED": "START_FRESH_SESSION",
    }.get(state)
    relationship = {
        "requestedCommit": exact["commit"],
        "canonicalCommit": response.get("canonicalCommit")
            if isinstance(response, dict) else None,
        "state": state,
    }
    if (
        not isinstance(response, dict)
        or set(response) != WORKSPACE_READINESS_RESPONSE_KEYS
        or response.get("schemaVersion") != WORKSPACE_READINESS_SCHEMA
        or expected_action is None
        or response.get("sessionId") != exact["sessionId"]
        or response.get("workspaceIdentity") != exact["workspaceIdentity"]
        or response.get("projectId") != PROJECT_ID
        or response.get("workerId") != worker_id
        or response.get("requestedCommit") != exact["commit"]
        or COMMIT_PATTERN.fullmatch(str(response.get("canonicalCommit"))) is None
        or response.get("retryAllowed") is not (state == "READY_FOR_RETRY")
        or response.get("nextAction") != expected_action
        or response.get("requestFingerprintSha256") != canonical_hash(exact)
        or response.get("relationshipFingerprintSha256") != canonical_hash(relationship)
        or response.get("valuesExposed") is not False
    ):
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_readiness_response_invalid",
            "workspace readiness response is invalid",
        )
    return dict(response)


def validate_workspace_release_preflight_response(
    request: dict[str, Any], worker_id: str, response: dict[str, Any]
) -> dict[str, Any]:
    exact = validate_workspace_release_request(request)
    if (
        not isinstance(response, dict)
        or set(response) != WORKSPACE_RELEASE_PREFLIGHT_RESPONSE_KEYS
        or response.get("schemaVersion") != WORKSPACE_RELEASE_PREFLIGHT_SCHEMA
        or response.get("state") != "PREFLIGHT_ACCEPTED"
        or response.get("operationId") != exact["operationId"]
        or response.get("sessionId") != exact["sessionId"]
        or response.get("workspaceIdentity") != exact["workspaceIdentity"]
        or response.get("projectId") != PROJECT_ID
        or response.get("workerId") != worker_id
        or response.get("requestFingerprintSha256") != canonical_hash(exact)
        or response.get("valuesExposed") is not False
    ):
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_release_preflight_response_invalid",
            "workspace release preflight response is invalid",
        )
    for key in ("ownershipFingerprintSha256", "allocationFingerprintSha256"):
        if (
            not isinstance(response.get(key), str)
            or re.fullmatch(r"[0-9a-f]{64}", response[key]) is None
        ):
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "workspace_release_preflight_response_invalid",
                "workspace release preflight fingerprint is invalid",
            )
    return dict(response)


def workspace_release_request_fingerprint(request: dict[str, Any]) -> str:
    return canonical_hash(validate_workspace_release_request(request))


def validate_workspace_release_repetition(
    existing_request: dict[str, Any],
    repeated_request: dict[str, Any],
) -> str:
    existing = validate_workspace_release_request(existing_request)
    repeated = validate_workspace_release_request(repeated_request)
    existing_fingerprint = canonical_hash(existing)
    repeated_fingerprint = canonical_hash(repeated)
    shares_identity = (
        existing["operationId"] == repeated["operationId"]
        or existing["idempotencyKey"] == repeated["idempotencyKey"]
    )
    if shares_identity and existing_fingerprint != repeated_fingerprint:
        raise ProtocolError(
            HTTPStatus.CONFLICT,
            "workspace_release_identity_conflict",
            "workspace release identity already owns another immutable request",
        )
    return repeated_fingerprint


def assert_no_non_terminal_session_execution(
    executions: dict[str, dict[str, Any]],
    session_id: str,
) -> None:
    if any(
        item.get("sessionId") == session_id and item.get("status") in NON_TERMINAL
        for item in executions.values()
    ):
        raise ProtocolError(
            HTTPStatus.CONFLICT,
            "workspace_release_execution_live",
            "workspace release requires every exact execution to be terminal",
        )


def validate_workspace_release_receipt(
    request: dict[str, Any],
    worker_id: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    exact_request = validate_workspace_release_request(request)
    if not isinstance(receipt, dict) or set(receipt) != WORKSPACE_RELEASE_RECEIPT_KEYS:
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_release_receipt_invalid",
            "workspace release receipt fields are invalid",
        )
    ownership_keys = WORKSPACE_RELEASE_REQUEST_KEYS - {"operationId", "idempotencyKey"}
    if (
        receipt.get("schemaVersion") != WORKSPACE_RELEASE_SCHEMA
        or receipt.get("state") != "RELEASED"
        or receipt.get("operationId") != exact_request["operationId"]
        or receipt.get("idempotencyKey") != exact_request["idempotencyKey"]
        or receipt.get("workerId") != worker_id
        or any(receipt.get(key) != exact_request[key] for key in ownership_keys)
        or receipt.get("requestFingerprintSha256") != canonical_hash(exact_request)
        or type(receipt.get("revision")) is not int
        or receipt["revision"] != WORKSPACE_RELEASE_REVISION
        or receipt.get("valuesExposed") is not False
    ):
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_release_receipt_invalid",
            "workspace release receipt ownership is invalid",
        )
    removed = receipt.get("removed")
    released = receipt.get("released")
    retained = receipt.get("retained")
    if (
        not isinstance(removed, dict)
        or set(removed) != WORKSPACE_RELEASE_REMOVED_KEYS
        or any(type(value) is not int or value < 0 for value in removed.values())
        or not isinstance(released, dict)
        or set(released) != WORKSPACE_RELEASE_RELEASED_KEYS
        or any(value is not True for value in released.values())
        or not isinstance(retained, dict)
        or set(retained) != WORKSPACE_RELEASE_RETAINED_KEYS
        or any(value is not True for value in retained.values())
    ):
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_release_receipt_invalid",
            "workspace release receipt projection is invalid",
        )
    for key in ("ownershipFingerprintSha256", "receiptSha256"):
        if not isinstance(receipt.get(key), str) or re.fullmatch(r"[0-9a-f]{64}", receipt[key]) is None:
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "workspace_release_receipt_invalid",
                "workspace release receipt fingerprint is invalid",
            )
    sealed = {key: value for key, value in receipt.items() if key != "receiptSha256"}
    if canonical_hash(sealed) != receipt["receiptSha256"]:
        raise ProtocolError(
            HTTPStatus.BAD_GATEWAY,
            "workspace_release_receipt_invalid",
            "workspace release receipt seal is invalid",
        )
    return dict(receipt)


def worker_error_envelope(
    code: str,
    category: str,
    retryable: bool,
    next_action: str,
    blocker_session_id: str | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(code, str)
        or WORKER_ERROR_CODE_PATTERN.fullmatch(code) is None
        or category not in WORKER_ERROR_CATEGORIES
        or type(retryable) is not bool
        or next_action not in WORKER_ERROR_NEXT_ACTIONS
    ):
        raise ValueError("worker error envelope values are invalid")
    payload: dict[str, Any] = {
        "schemaVersion": WORKER_ERROR_SCHEMA,
        "code": code,
        "category": category,
        "retryable": retryable,
        "nextAction": next_action,
    }
    if blocker_session_id is not None:
        try:
            canonical = str(uuid.UUID(blocker_session_id))
        except (ValueError, AttributeError, TypeError):
            raise ValueError("blockerSessionId must be a canonical UUID") from None
        if canonical != blocker_session_id or category != "CAPACITY":
            raise ValueError("blockerSessionId must be a canonical capacity owner")
        payload["blockerSessionId"] = blocker_session_id
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > WORKER_ERROR_MAX_BYTES:
        raise ValueError("worker error envelope is oversized")
    return payload


def validate_worker_error_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "schemaVersion", "code", "category", "retryable", "nextAction",
        "blockerSessionId",
    }
    if (
        not isinstance(payload, dict)
        or not set(payload).issubset(allowed)
        or set(payload) - {"blockerSessionId"}
        != {"schemaVersion", "code", "category", "retryable", "nextAction"}
        or payload.get("schemaVersion") != WORKER_ERROR_SCHEMA
    ):
        raise ValueError("worker error envelope fields are invalid")
    expected = worker_error_envelope(
        payload.get("code"),
        payload.get("category"),
        payload.get("retryable"),
        payload.get("nextAction"),
        payload.get("blockerSessionId"),
    )
    if payload != expected:
        raise ValueError("worker error envelope is not canonical")
    return dict(expected)


def reviewed_mediator_error_envelope(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, str):
        encoded = raw.encode("utf-8")
    elif isinstance(raw, bytes):
        encoded = raw
    else:
        raise ValueError("mediator error output must be bytes or text")
    if len(encoded) < 2 or len(encoded) > MEDIATOR_ERROR_MAX_BYTES:
        raise ValueError("mediator error output size is invalid")
    try:
        parsed = json.loads(encoded)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("mediator error output is not valid JSON") from None
    if (
        not isinstance(parsed, dict)
        or not set(parsed).issubset(MEDIATOR_ERROR_KEYS)
        or "code" not in parsed
    ):
        raise ValueError("mediator error fields are invalid")
    code = parsed["code"]
    if not isinstance(code, str) or code not in REVIEWED_MEDIATOR_ERRORS:
        raise ValueError("mediator error code is not reviewed")
    category, retryable, next_action = REVIEWED_MEDIATOR_ERRORS[code]
    blocker = parsed.get("blockerSessionId")
    return worker_error_envelope(code, category, retryable, next_action, blocker)


def reviewed_mediator_stderr_envelope(raw: str) -> dict[str, Any]:
    encoded = raw.encode("utf-8")
    if not encoded or len(encoded) > MEDIATOR_ERROR_MAX_BYTES:
        raise ValueError("mediator stderr size is invalid")
    stripped = raw.strip()
    if stripped.startswith("{"):
        return reviewed_mediator_error_envelope(stripped)
    first_line = stripped.splitlines()[0]
    match = re.match(r"^([A-Z][A-Z0-9_]{2,79}):(?: |$)", first_line)
    if match is None or match.group(1) not in REVIEWED_MEDIATOR_ERRORS:
        raise ValueError("mediator stderr code is not reviewed")
    code = match.group(1)
    category, retryable, next_action = REVIEWED_MEDIATOR_ERRORS[code]
    return worker_error_envelope(code, category, retryable, next_action)


def protocol_error_envelope(status: int, code: str) -> dict[str, Any]:
    safe_code = code.upper() if isinstance(code, str) else "PROTOCOL_ERROR"
    if WORKER_ERROR_CODE_PATTERN.fullmatch(safe_code) is None:
        safe_code = "PROTOCOL_ERROR"
    if status in {HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND}:
        values = ("VALIDATION", False, "NONE")
    elif status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        values = ("POLICY", False, "NONE")
    elif status == HTTPStatus.CONFLICT:
        values = ("OWNERSHIP", False, "CONTACT_PLATFORM_ADMINISTRATOR")
    elif status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        values = ("TRANSPORT", True, "REQUEST_RECONCILIATION")
    else:
        values = ("PROTOCOL", False, "NONE")
    return worker_error_envelope(safe_code, *values)


def codex_catalog_revision() -> str:
    return canonical_hash({
        "schemaVersion": CODEX_CATALOG_SCHEMA,
        "codexVersion": CODEX_VERSION,
        "models": sorted(CODEX_MODELS, key=lambda item: item["modelId"]),
    })


class ProtocolError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        safe_error: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.safe_error = validate_worker_error_envelope(
            safe_error or protocol_error_envelope(status, code)
        )


class WorkerState:
    def __init__(
        self,
        state_dir: Path,
        worker_id: str,
        normal_capacity: int = 4,
        heavy_capacity: int = 2,
        project_config: Path | None = None,
        project_runner: Path | None = None,
        project_timeout: int = 1800,
        project_config_uid: int = 0,
        privilege_command: tuple[str, ...] = ("sudo",),
        project_workspace_activator: Path | None = None,
        project_workspace_releaser: Path | None = None,
        beautips_project_config: Path | None = None,
        beautips_project_runner: Path | None = None,
        beautips_workspace_activator: Path | None = None,
        project_validation_mediator: Path | None = None,
        repository_role_mediator: Path | None = None,
        codex_update_mediator: Path | None = None,
        codex_activate_mediator: Path | None = None,
        codex_rollback_mediator: Path | None = None,
        codex_restart_scheduler: Path | None = None,
        codex_update_registry: Path | None = None,
        codex_release_root: Path | None = None,
        reconcile_materializations_on_start: bool = False,
        workspace_lifecycle_timeout: float = 10.0,
        project_readiness_enabled: bool = False,
        unactivated_release_enabled: bool = False,
        development_change_workspace_mediator: Path | None = None,
        development_change_workspace_timeout: float = 45.0,
    ):
        self.state_dir = state_dir
        self.state_file = state_dir / "executions.json"
        self.workspace_lifecycle_lock_file = state_dir / "workspace-lifecycle-v1.lock"
        self.worker_id = worker_id
        self.normal_capacity = normal_capacity
        self.heavy_capacity = heavy_capacity
        self.project_config = project_config
        self.project_runner = project_runner
        self.project_timeout = project_timeout
        self.project_config_uid = project_config_uid
        self.privilege_command = privilege_command
        self.project_workspace_activator = project_workspace_activator
        self.project_workspace_releaser = project_workspace_releaser
        self.beautips_project_config = beautips_project_config
        self.beautips_project_runner = beautips_project_runner
        self.beautips_workspace_activator = beautips_workspace_activator
        self.project_validation_mediator = project_validation_mediator
        self.repository_role_mediator = repository_role_mediator
        self.codex_update_mediator = codex_update_mediator
        self.codex_activate_mediator = codex_activate_mediator
        self.codex_rollback_mediator = codex_rollback_mediator
        self.codex_restart_scheduler = codex_restart_scheduler
        self.codex_update_registry = codex_update_registry
        self.codex_release_root = codex_release_root
        self.reconcile_materializations_on_start = reconcile_materializations_on_start
        self.workspace_lifecycle_timeout = workspace_lifecycle_timeout
        self.project_readiness_enabled = project_readiness_enabled
        self.unactivated_release_enabled = unactivated_release_enabled
        self.development_change_workspace_mediator = development_change_workspace_mediator
        self.development_change_workspace_timeout = development_change_workspace_timeout
        self.lock = threading.RLock()
        self.wakeup = threading.Event()
        self.stop_event = threading.Event()
        self.executions: dict[str, dict[str, Any]] = {}
        self.validations: dict[str, dict[str, Any]] = {}
        self.unactivated_workspace_releases: dict[str, dict[str, Any]] = {}
        self.threads: dict[str, threading.Thread] = {}
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.scheduler: threading.Thread | None = None
        self.codex_update_in_progress = False
        self._load()

    @contextmanager
    def workspace_lifecycle_lock(self) -> Iterator[None]:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.workspace_lifecycle_lock_file, flags, 0o600)
        except OSError as exception:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "workspace_lifecycle_lock_unsafe",
                "workspace lifecycle lock is unavailable or unsafe",
            ) from exception
        acquired = False
        try:
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_uid != os.geteuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_lifecycle_lock_unsafe",
                    "workspace lifecycle lock ownership is unsafe",
                )
            deadline = time.monotonic() + self.workspace_lifecycle_timeout
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ProtocolError(
                            HTTPStatus.LOCKED,
                            "workspace_lifecycle_lock_timeout",
                            "workspace lifecycle operation is already in progress",
                            worker_error_envelope(
                                "WORKSPACE_LIFECYCLE_BUSY", "CAPACITY", True, "WAIT"
                            ),
                        ) from None
                    time.sleep(0.01)
            yield
        finally:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _load(self) -> None:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)
        if not self.state_file.exists():
            return
        parsed = json.loads(self.state_file.read_text(encoding="utf-8"))
        if parsed.get("protocol") != PROTOCOL or not isinstance(parsed.get("executions"), dict):
            raise RuntimeError("durable worker state has an unsupported schema")
        self.executions = parsed["executions"]
        if not isinstance(parsed.get("validations", {}), dict):
            raise RuntimeError("durable worker validation state has an unsupported schema")
        self.validations = parsed.get("validations", {})
        if not isinstance(parsed.get("unactivatedWorkspaceReleases", {}), dict):
            raise RuntimeError("durable unactivated release state has an unsupported schema")
        self.unactivated_workspace_releases = parsed.get(
            "unactivatedWorkspaceReleases", {}
        )
        for value in self.unactivated_workspace_releases.values():
            validate_workspace_release_receipt(
                value.get("request"), self.worker_id, value.get("receipt")
            )
        for validation in self.validations.values():
            if validation.get("status") == "RUNNING":
                validation["status"] = "BLOCKED"
                validation["exitCode"] = None
                validation["durationMillis"] = max(0, int(validation.get("durationMillis") or 0))
                validation["artifactManifestSha256"] = hashlib.sha256(
                    f"{validation.get('validationId')}:worker-restart".encode()
                ).hexdigest()
                validation["summary"] = (
                    "Worker restarted; the persisted validation requires an exact retry"
                )
                validation["finishedAt"] = utc_now()
        for execution in self.executions.values():
            execution.setdefault("progressEvents", [])
            execution.setdefault(
                "nextProgressSequence",
                max((event.get("sequence", 0) for event in execution["progressEvents"]), default=0) + 1,
            )
            if execution["status"] in {"STARTING", "RUNNING", "CANCELLING"}:
                execution["status"] = "RECONCILING"
                execution["statusReason"] = "Worker service restarted; persisted ownership requires reconciliation"
                execution["reconcileRequired"] = True
                execution["revision"] += 1
                execution["updatedAt"] = utc_now()
                self._append_progress(
                    execution,
                    "RECONCILING",
                    "Reconciling persisted execution ownership.",
                )
            else:
                execution.setdefault("reconcileRequired", False)
        self._persist()

    def _persist(self) -> None:
        payload = {
            "protocol": PROTOCOL,
            "workerId": self.worker_id,
            "executions": self.executions,
            "validations": self.validations,
            "unactivatedWorkspaceReleases": self.unactivated_workspace_releases,
        }
        fd, temporary = tempfile.mkstemp(prefix=".executions-", dir=self.state_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.state_file)
            directory_fd = os.open(self.state_dir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def start(self) -> None:
        self._resolve_uncertain_project_executions()
        if self.reconcile_materializations_on_start:
            self._reconcile_materializations()
        self.scheduler = threading.Thread(target=self._schedule_loop, name="agent-run-scheduler", daemon=True)
        self.scheduler.start()
        self.wakeup.set()

    def _resolve_uncertain_project_executions(self) -> None:
        changed = False
        with self.lock:
            for execution in self.executions.values():
                if (
                    execution.get("status") == "RECONCILING"
                    and execution.get("workload", {}).get("kind") in {
                        PROJECT_CAPABILITY, PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY,
                        PROJECT_V4_CAPABILITY,
                    }
                ):
                    execution["status"] = "FAILED"
                    execution["statusReason"] = (
                        "Restart reconciliation refused to duplicate an uncertain Codex turn"
                    )
                    execution["finishedAt"] = utc_now()
                    execution["revision"] += 1
                    execution["updatedAt"] = execution["finishedAt"]
                    self._append_progress(
                        execution,
                        "FAILED",
                        "Execution failed closed during reconciliation.",
                    )
                    changed = True
            if changed:
                self._persist()

    def _reconcile_materializations(self) -> None:
        if self.project_runner is None or self.project_config is None:
            raise RuntimeError("image materialization reconciliation is unavailable")
        payload = {
            "schemaVersion": "codex-image-reconciliation-state-v1",
            "executions": [
                {
                    "executionId": execution.get("executionId"),
                    "status": execution.get("status"),
                    "attachments": (
                        execution.get("workload", {}).get("attachments", [])
                        if execution.get("workload", {}).get("kind") in {
                            PROJECT_V3_CAPABILITY, PROJECT_V4_CAPABILITY,
                        }
                        else []
                    ),
                }
                for execution in sorted(
                    self.executions.values(), key=lambda item: str(item.get("executionId"))
                )
            ],
        }
        try:
            completed = subprocess.run(
                [
                    *self.privilege_command,
                    str(self.project_runner),
                    "--config",
                    str(self.project_config),
                    "--reconcile-materializations",
                ],
                input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=30,
                check=False,
            )
            result = json.loads(completed.stdout) if completed.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            result = None
        if (
            not isinstance(result, dict)
            or set(result) != {
                "schemaVersion", "state", "removed", "retained", "ambiguous",
                "valuesExposed",
            }
            or result.get("schemaVersion") != "codex-image-reconciliation-v1"
            or result.get("state") != "PASS"
            or any(
                not isinstance(result.get(key), int) or isinstance(result.get(key), bool)
                or result[key] < 0
                for key in ("removed", "retained", "ambiguous")
            )
            or result.get("ambiguous") != 0
            or result.get("valuesExposed") is not False
        ):
            raise RuntimeError("image materialization reconciliation failed closed")

    def stop(self) -> None:
        self.stop_event.set()
        self.wakeup.set()
        if self.scheduler:
            self.scheduler.join(timeout=5)
        with self.lock:
            threads = list(self.threads.values())
            processes = list(self.processes.values())
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for thread in threads:
            thread.join(timeout=5)

    def health(self) -> dict[str, Any]:
        with self.lock:
            normal = sum(1 for item in self.executions.values() if item["status"] in {"STARTING", "RUNNING"} )
            heavy = sum(
                1 for item in self.executions.values()
                if item["status"] in {"STARTING", "RUNNING"} and item["workloadClass"] == "HEAVY"
            )
            queued = sum(1 for item in self.executions.values() if item["status"] in {"QUEUED", "RECONCILING"})
            capabilities = [SYNTHETIC_CAPABILITY, CODEX_CATALOG_CAPABILITY]
            project_selection_enabled = self._project_selection_enabled()
            if project_selection_enabled:
                capabilities.extend([PROJECT_CAPABILITY, PROJECT_V2_CAPABILITY])
            change_workspace_available = (
                self.development_change_workspace_mediator is not None
                and self.development_change_workspace_mediator.is_file()
                and not self.development_change_workspace_mediator.is_symlink()
                and os.access(self.development_change_workspace_mediator, os.X_OK)
            )
            if change_workspace_available:
                capabilities.append(DEVELOPMENT_CHANGE_WORKSPACE_CAPABILITY)
                if project_selection_enabled:
                    capabilities.append(PROJECT_V4_CAPABILITY)
            if (
                self.codex_update_mediator is not None
                and self.codex_update_mediator.is_file()
                and self.codex_update_registry is not None
                and self.codex_update_registry.is_file()
                and self.codex_release_root is not None
            ):
                capabilities.append(CODEX_UPDATE_STAGE_CAPABILITY)
                if self.codex_activate_mediator is not None and self.codex_activate_mediator.is_file():
                    capabilities.append(CODEX_UPDATE_ACTIVATE_CAPABILITY)
                    if (self.codex_rollback_mediator is not None
                            and self.codex_rollback_mediator.is_file()
                            and self.codex_restart_scheduler is not None
                            and self.codex_restart_scheduler.is_file()):
                        capabilities.append(CODEX_UPDATE_ROLLBACK_CAPABILITY)
            return {
                "protocolVersion": PROTOCOL,
                "workerId": self.worker_id,
                "healthy": True,
                "capabilities": capabilities,
                "normalCapacity": self.normal_capacity,
                "heavyCapacity": self.heavy_capacity,
                "normalInUse": normal,
                "heavyInUse": heavy,
                "queued": queued,
                "serverTime": utc_now(),
            }

    def execute_development_change_workspace(
        self, request: dict[str, Any], operation: str
    ) -> dict[str, Any]:
        operation = operation.upper()
        if (
            operation not in {"PROVISION", "INSPECT", "RECONCILE"}
            or not isinstance(request, dict)
            or set(request) != DEVELOPMENT_CHANGE_WORKSPACE_REQUEST_KEYS
            or request.get("schemaVersion") != 1
            or request.get("protocolVersion") != DEVELOPMENT_CHANGE_WORKSPACE_CAPABILITY
            or request.get("operation") != operation
        ):
            raise ProtocolError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "development_change_workspace_request_invalid",
                "development change workspace request is invalid",
            )
        mediator = self.development_change_workspace_mediator
        if (
            mediator is None
            or not mediator.is_file()
            or mediator.is_symlink()
            or not os.access(mediator, os.X_OK)
        ):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "development_change_workspace_unavailable",
                "development change workspace capability is unavailable",
            )
        try:
            with self.workspace_lifecycle_lock():
                completed = subprocess.run(
                    [str(mediator), operation.lower()],
                    input=json.dumps(request, sort_keys=True, separators=(",", ":")),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.development_change_workspace_timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            raise ProtocolError(
                HTTPStatus.GATEWAY_TIMEOUT,
                "development_change_workspace_timeout",
                "development change workspace mediator timed out",
            ) from error
        except OSError as error:
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "development_change_workspace_unavailable",
                "development change workspace mediator is unavailable",
            ) from error
        if completed.returncode != 0:
            try:
                safe = reviewed_mediator_stderr_envelope(completed.stderr)
            except ValueError as error:
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "development_change_workspace_response_invalid",
                    "development change workspace mediator failure is invalid",
                ) from error
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "development_change_workspace_rejected",
                "development change workspace mediator rejected the request",
                safe,
            )
        try:
            response = strict_json_object(completed.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "development_change_workspace_response_invalid",
                "development change workspace mediator returned invalid JSON",
            ) from error
        if (
            not isinstance(response, dict)
            or set(response) != DEVELOPMENT_CHANGE_WORKSPACE_RESPONSE_KEYS
            or response.get("state") not in {"ABSENT", "OWNED", "FOREIGN"}
            or response.get("schemaVersion") != request["schemaVersion"]
            or response.get("protocolVersion") != request["protocolVersion"]
            or response.get("effect") != request["effect"]
            or response.get("operationId") != request["operationId"]
            or response.get("idempotencyKey") != request["idempotencyKey"]
            or response.get("operation") != request["operation"]
            or response.get("predecessorOperationId") != request["predecessorOperationId"]
            or response.get("changeKey") != request["changeKey"]
            or response.get("databaseProjectId") != request["databaseProjectId"]
            or response.get("projectId") != request["projectId"]
            or response.get("repository") != request["repository"]
            or response.get("repositoryBranch") != request["repositoryBranch"]
            or response.get("baseCommit") != request["baseCommit"]
            or response.get("expectedCanonicalCommit")
                != request["expectedCanonicalCommit"]
            or response.get("workspaceBranch") != request["workspaceBranch"]
            or response.get("workspaceIdentity") != request["workspaceIdentity"]
            or response.get("workerId") != request["workerId"]
            or response.get("sourceRevision") != request["sourceRevision"]
            or response.get("expectedSourceFingerprintSha256")
                != request["sourceFingerprintSha256"]
            or response.get("requestFingerprintSha256")
                != request["requestFingerprintSha256"]
            or not isinstance(response.get("ownershipFingerprintSha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", response["ownershipFingerprintSha256"])
                is None
            or response.get("valuesExposed") is not False
        ):
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "development_change_workspace_response_invalid",
                "development change workspace mediator response is not exact",
            )
        owned = response["state"] == "OWNED"
        if owned:
            if (
                not isinstance(response.get("canonicalCommit"), str)
                or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", response["canonicalCommit"])
                    is None
                or not isinstance(response.get("sourceFingerprintSha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", response["sourceFingerprintSha256"])
                    is None
                or not isinstance(response.get("workspaceDirty"), bool)
                or not isinstance(response.get("retainedDraft"), bool)
            ):
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "development_change_workspace_response_invalid",
                    "owned workspace observation is invalid",
                )
        elif any(
            response.get(field) is not None
            for field in (
                "canonicalCommit", "sourceFingerprintSha256",
                "workspaceDirty", "retainedDraft",
            )
        ):
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "development_change_workspace_response_invalid",
                "non-owned workspace observation exposed values",
            )
        return response

    def codex_catalog(self) -> dict[str, Any]:
        return {
            "schemaVersion": CODEX_CATALOG_SCHEMA,
            "catalogRevision": codex_catalog_revision(),
            "workerId": self.worker_id,
            "codexVersion": CODEX_VERSION,
            "generatedAt": utc_now(),
            "models": json.loads(json.dumps(CODEX_MODELS)),
        }

    def stage_codex_update(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != CODEX_UPDATE_STAGE_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_stage",
                "exact Codex update stage fields are required")
        if request.get("operation") != "STAGE_CODEX_UPDATE":
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_stage",
                "Codex update stage operation is invalid")
        for field in ("planId", "candidateId", "idempotencyKey"):
            try:
                parsed = str(uuid.UUID(request.get(field)))
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_stage",
                    "Codex update stage identities must be canonical UUIDs")
            if parsed != request[field]:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_stage",
                    "Codex update stage identities must be canonical UUIDs")
        if (
            self.codex_update_mediator is None
            or not self.codex_update_mediator.is_file()
            or self.codex_update_registry is None
            or not self.codex_update_registry.is_file()
            or self.codex_release_root is None
        ):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_stage_unavailable",
                "Codex update stage mediator is unavailable")
        try:
            completed = subprocess.run(
                [str(self.codex_update_mediator),
                 "--registry", str(self.codex_update_registry),
                 "--release-root", str(self.codex_release_root)],
                input=json.dumps(request, sort_keys=True, separators=(",", ":")),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=300, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_stage_failed",
                "Codex update stage mediator failed closed")
        if completed.returncode != 0:
            raise ProtocolError(
                HTTPStatus.CONFLICT, "codex_update_stage_rejected",
                "Codex update stage mediator rejected the persisted candidate")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = None
        digest_fields = (
            "releaseDigestSha256", "catalogRevision", "releaseManifestSha256",
            "schemaManifestSha256", "currentLinkFingerprint",
            "previousLinkFingerprint",
        )
        if (
            not isinstance(result, dict)
            or set(result) != CODEX_UPDATE_STAGE_RESULT_KEYS
            or result.get("schemaVersion") != CODEX_UPDATE_STAGE_CAPABILITY
            or result.get("operation") != request["operation"]
            or result.get("workerId") != self.worker_id
            or any(result.get(field) != request[field]
                   for field in ("planId", "candidateId", "idempotencyKey"))
            or result.get("state") != "STAGED"
            or not isinstance(result.get("codexVersion"), str)
            or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", result["codexVersion"]) is None
            or any(re.fullmatch(r"[0-9a-f]{64}", str(result.get(field))) is None
                   for field in digest_fields)
            or any(result.get(field) != "PASS"
                   for field in ("releaseVerification", "schemaGeneration", "retention"))
            or result.get("linksChanged") is not False
            or result.get("valuesExposed") is not False
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT, "codex_update_stage_result_conflict",
                "Codex update stage result is incomplete or conflicting")
        return result

    def activate_codex_update(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != CODEX_UPDATE_ACTIVATE_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_activation",
                "exact Codex update activation fields are required")
        if request.get("operation") != "ACTIVATE_CODEX_UPDATE":
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_activation",
                "Codex update activation operation is invalid")
        for field in ("planId", "candidateId", "authorizationId", "idempotencyKey"):
            try:
                parsed = str(uuid.UUID(request.get(field)))
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_activation",
                    "Codex update activation identities must be canonical UUIDs")
            if parsed != request[field]:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_activation",
                    "Codex update activation identities must be canonical UUIDs")
        if (
            self.codex_activate_mediator is None
            or not self.codex_activate_mediator.is_file()
            or self.codex_update_registry is None
            or not self.codex_update_registry.is_file()
            or self.codex_release_root is None
        ):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_activation_unavailable",
                "Codex update activation mediator is unavailable")
        with self.lock:
            if self.codex_update_in_progress or any(
                execution["status"] in NON_TERMINAL for execution in self.executions.values()
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_active_execution",
                    "Codex update activation requires zero non-terminal executions")
            self.codex_update_in_progress = True
        try:
            try:
                completed = subprocess.run(
                    [*self.privilege_command, str(self.codex_activate_mediator),
                     "--registry", str(self.codex_update_registry),
                     "--release-root", str(self.codex_release_root),
                     "--release-owner-uid", str(os.geteuid())],
                    input=json.dumps(request, sort_keys=True, separators=(",", ":")),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, timeout=300, check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_activation_failed",
                    "Codex update activation mediator failed closed")
            if completed.returncode != 0:
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_activation_rejected",
                    "Codex update activation gates rejected the persisted candidate")
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                result = None
            digest_fields = (
                "releaseDigestSha256", "catalogRevision", "currentBeforeFingerprint",
                "previousBeforeFingerprint", "currentAfterFingerprint",
                "previousAfterFingerprint",
            )
            if (
                not isinstance(result, dict)
                or set(result) != CODEX_UPDATE_ACTIVATE_RESULT_KEYS
                or result.get("schemaVersion") != CODEX_UPDATE_ACTIVATE_CAPABILITY
                or result.get("operation") != request["operation"]
                or result.get("workerId") != self.worker_id
                or any(result.get(field) != request[field] for field in (
                    "planId", "candidateId", "authorizationId", "idempotencyKey"))
                or result.get("state") != "ACTIVATED"
                or not isinstance(result.get("codexVersion"), str)
                or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", result["codexVersion"]) is None
                or any(re.fullmatch(r"[0-9a-f]{64}", str(result.get(field))) is None
                       for field in digest_fields)
                or any(result.get(field) != "PASS" for field in (
                    "schemaComparison", "focusedContracts", "workerHealth", "canary"))
                or result.get("automaticRestore") not in {"NOT_REQUIRED", "PASS"}
                or result.get("valuesExposed") is not False
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_activation_result_conflict",
                    "Codex update activation result is incomplete or conflicting")
            return result
        finally:
            with self.lock:
                self.codex_update_in_progress = False

    def rollback_codex_update(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != CODEX_UPDATE_ROLLBACK_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_rollback",
                "exact Codex update rollback fields are required")
        if request.get("operation") != "ROLLBACK_CODEX_UPDATE":
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_codex_update_rollback",
                "Codex update rollback operation is invalid")
        identity_fields = (
            "planId", "candidateId", "activationId", "authorizationId", "idempotencyKey",
        )
        for field in identity_fields:
            try:
                parsed = str(uuid.UUID(request.get(field)))
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_rollback",
                    "Codex update rollback identities must be canonical UUIDs")
            if parsed != request[field]:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST, "invalid_codex_update_rollback",
                    "Codex update rollback identities must be canonical UUIDs")
        if (self.codex_rollback_mediator is None
                or not self.codex_rollback_mediator.is_file()
                or self.codex_restart_scheduler is None
                or not self.codex_restart_scheduler.is_file()
                or self.codex_update_registry is None
                or not self.codex_update_registry.is_file()
                or self.codex_release_root is None):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_rollback_unavailable",
                "Codex update rollback mediator is unavailable")
        with self.lock:
            if self.codex_update_in_progress or any(
                execution["status"] in NON_TERMINAL for execution in self.executions.values()
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_active_execution",
                    "Codex update rollback requires zero non-terminal executions")
            self.codex_update_in_progress = True
        try:
            try:
                completed = subprocess.run(
                    [*self.privilege_command, str(self.codex_rollback_mediator),
                     "--registry", str(self.codex_update_registry),
                     "--release-root", str(self.codex_release_root),
                     "--release-owner-uid", str(os.geteuid()),
                     "--restart-scheduler", str(self.codex_restart_scheduler)],
                    input=json.dumps(request, sort_keys=True, separators=(",", ":")),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, timeout=60, check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE, "codex_update_rollback_failed",
                    "Codex update rollback mediator failed closed")
            if completed.returncode != 0:
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_rollback_rejected",
                    "Codex update rollback rejected the exact activation")
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                result = None
            digest_fields = (
                "currentBeforeFingerprint", "previousBeforeFingerprint",
                "currentAfterFingerprint", "previousAfterFingerprint",
            )
            if (not isinstance(result, dict)
                    or set(result) != CODEX_UPDATE_ROLLBACK_RESULT_KEYS
                    or result.get("schemaVersion") != CODEX_UPDATE_ROLLBACK_CAPABILITY
                    or result.get("operation") != request["operation"]
                    or result.get("workerId") != self.worker_id
                    or any(result.get(field) != request[field] for field in identity_fields)
                    or result.get("state") != "ROLLED_BACK"
                    or result.get("linkRestore") != "PASS"
                    or result.get("workerServiceRestart") != "PASS"
                    or result.get("affectedServices") != [
                        "atenea-agent-run-worker-v1.service"]
                    or result.get("appServerServicesRestarted") != 0
                    or any(re.fullmatch(r"[0-9a-f]{64}", str(result.get(field))) is None
                           for field in digest_fields)
                    or result.get("valuesExposed") is not False):
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "codex_update_rollback_result_conflict",
                    "Codex update rollback result is incomplete or conflicting")
            return result
        finally:
            with self.lock:
                self.codex_update_in_progress = False

    def _append_progress(
        self,
        execution: dict[str, Any],
        category: str,
        message: str,
    ) -> bool:
        if category not in PROGRESS_CATEGORIES or not (1 <= len(message) <= 160):
            return False
        events = execution.setdefault("progressEvents", [])
        if events and events[-1]["category"] == category and events[-1]["message"] == message:
            return False
        sequence = execution.setdefault("nextProgressSequence", 1)
        events.append({
            "dispatchId": execution["dispatchId"],
            "executionId": execution["executionId"],
            "sequence": sequence,
            "category": category,
            "occurredAt": utc_now(),
            "message": message,
        })
        execution["nextProgressSequence"] = sequence + 1
        if len(events) > PROGRESS_LIMIT:
            del events[:-PROGRESS_LIMIT]
        return True

    def _append_runner_progress(
        self,
        execution: dict[str, Any],
        events: Any,
    ) -> None:
        if not isinstance(events, list):
            return
        for event in events[:PROGRESS_LIMIT]:
            if not isinstance(event, dict) or set(event) != {"category", "occurredAt", "message"}:
                continue
            category = event.get("category")
            message = event.get("message")
            if RUNNER_PROGRESS_MESSAGES.get(category) != message:
                continue
            self._append_progress(execution, category, message)

    def create(self, request: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        workload = self._validate_dispatch_envelope(request)
        change_aware = workload.get("kind") == PROJECT_V4_CAPABILITY
        if not change_aware:
            self._validate_create(request)
        dispatch_id = request["dispatchId"]
        fingerprint = canonical_hash(request)
        with self.lock:
            if self.codex_update_in_progress:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "codex_update_activation_in_progress",
                    "new execution dispatch is blocked during Codex activation",
                )
            existing = self.executions.get(dispatch_id)
            if existing:
                if existing["requestFingerprint"] != fingerprint:
                    raise ProtocolError(
                        HTTPStatus.CONFLICT,
                        "dispatch_identity_conflict",
                        "dispatchId already owns a different immutable request",
                    )
                return self._public(existing), False

            if change_aware:
                self._validate_change_project_shape(request, workload)
                self._validate_change_project_ownership(request, workload)
                for active in self.executions.values():
                    active_ownership = active.get("changeOwnership")
                    if isinstance(active_ownership, dict) and (
                        active_ownership.get("databaseWorkSessionId")
                            == request["changeOwnership"]["databaseWorkSessionId"]
                        or active_ownership.get("remoteSessionId")
                            == request["changeOwnership"]["remoteSessionId"]
                    ) and any(
                        active_ownership.get(key) != request["changeOwnership"][key]
                        for key in (
                            "changeKey", "databaseWorkSessionId", "remoteSessionId",
                            "workspaceIdentity", "databaseProjectId",
                        )
                    ):
                        raise ProtocolError(
                            HTTPStatus.CONFLICT,
                            "change_session_ownership_conflict",
                            "WorkSession already owns a different development change relationship",
                        )
                    if active.get("status") in NON_TERMINAL and (
                        active.get("sessionId") == request["sessionId"]
                        or active.get("workspaceIdentity") == request["workspaceIdentity"]
                        or (
                            isinstance(active_ownership, dict)
                            and active_ownership.get("databaseWorkSessionId")
                                == request["changeOwnership"]["databaseWorkSessionId"]
                        )
                    ):
                        raise ProtocolError(
                            HTTPStatus.CONFLICT,
                            "change_execution_ownership_conflict",
                            "change workspace or WorkSession already owns a non-terminal execution",
                        )

            now = utc_now()
            execution = {
                "dispatchId": dispatch_id,
                "executionId": str(uuid.uuid4()),
                "sessionId": request["sessionId"],
                "workspaceIdentity": request["workspaceIdentity"],
                "workloadClass": request["workloadClass"],
                "leaseGeneration": request["leaseGeneration"],
                "workload": request["workload"],
                "requestFingerprint": fingerprint,
                "status": "QUEUED",
                "statusReason": "Awaiting worker admission",
                "revision": 1,
                "progress": 0,
                "createdAt": now,
                "updatedAt": now,
                "startedAt": None,
                "finishedAt": None,
                "cancelRequested": False,
                "reconcileRequired": False,
                "result": None,
                "progressEvents": [],
                "nextProgressSequence": 1,
            }
            if change_aware:
                execution["changeOwnership"] = request["changeOwnership"]
            self._append_progress(execution, "ACCEPTED", "Execution request accepted.")
            self._append_progress(execution, "QUEUED", "Execution is queued for admission.")
            self.executions[dispatch_id] = execution
            self._persist()
            self.wakeup.set()
            return self._public(execution), True

    def profiled_project_fingerprint(self, request: dict[str, Any]) -> str:
        workload = self._validate_dispatch_envelope(request)
        if workload.get("kind") not in {PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY}:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workload",
                "profiled project workload is required",
            )
        self._validate_profiled_project(request, workload)
        return canonical_hash(request)

    def ensure_workspace(self, request: dict[str, Any]) -> dict[str, Any]:
        with self.workspace_lifecycle_lock():
            return self._ensure_workspace_locked(request)

    def release_workspace(self, request: dict[str, Any]) -> dict[str, Any]:
        exact_request = validate_workspace_release_request(request)
        with self.workspace_lifecycle_lock():
            with self.lock:
                assert_no_non_terminal_session_execution(
                    self.executions, exact_request["sessionId"]
                )
            releaser = self.project_workspace_releaser
            if releaser is None or not releaser.is_file():
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_release_unavailable",
                    "workspace release is unavailable",
                )
            try:
                completed = subprocess.run(
                    [*self.privilege_command, str(releaser)],
                    input=json.dumps(
                        exact_request, sort_keys=True, separators=(",", ":")
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=300,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ProtocolError(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    "workspace_release_timeout",
                    "workspace release exceeded its finite timeout",
                ) from None
            except OSError:
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_release_unavailable",
                    "workspace release mediator could not be started",
                ) from None
            if completed.returncode != 0:
                try:
                    safe_error = reviewed_mediator_stderr_envelope(completed.stderr)
                except ValueError:
                    safe_error = worker_error_envelope(
                        "WORKSPACE_RELEASE_FAILED",
                        "PROTOCOL",
                        False,
                        "CONTACT_PLATFORM_ADMINISTRATOR",
                    )
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_release_failed",
                    "workspace release failed closed",
                    safe_error,
                )
            try:
                receipt = json.loads(completed.stdout)
            except json.JSONDecodeError:
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "workspace_release_receipt_invalid",
                    "workspace release returned an invalid response",
                ) from None
            return validate_workspace_release_receipt(
                exact_request, self.worker_id, receipt
            )

    def release_unactivated_workspace(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.unactivated_release_enabled:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_unactivated_release_disabled",
                "unactivated workspace release is disabled",
            )
        exact = validate_workspace_release_request(request)
        with self.workspace_lifecycle_lock():
            with self.lock:
                assert_no_non_terminal_session_execution(
                    self.executions, exact["sessionId"]
                )
                if any(
                    item.get("sessionId") == exact["sessionId"]
                    for item in self.executions.values()
                ):
                    raise ProtocolError(
                        HTTPStatus.CONFLICT,
                        "workspace_unactivated_execution_conflict",
                        "unactivated release requires no worker execution",
                    )
                existing = self.unactivated_workspace_releases.get(
                    exact["operationId"]
                )
                if existing is None:
                    existing = next((
                        value
                        for value in self.unactivated_workspace_releases.values()
                        if value["request"]["idempotencyKey"] == exact["idempotencyKey"]
                    ), None)
                if existing is not None:
                    validate_workspace_release_repetition(existing["request"], exact)
                    return validate_workspace_release_receipt(
                        exact, self.worker_id, existing["receipt"]
                    )
            mediator = self.project_workspace_releaser
            if mediator is None or not mediator.is_file():
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_unactivated_release_unavailable",
                    "unactivated workspace release is unavailable",
                )
            try:
                completed = subprocess.run(
                    [*self.privilege_command, str(mediator), "--diagnose-unactivated"],
                    input=json.dumps(exact, sort_keys=True, separators=(",", ":")),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ProtocolError(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    "workspace_unactivated_release_timeout",
                    "unactivated workspace release exceeded its finite timeout",
                ) from None
            except OSError:
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_unactivated_release_unavailable",
                    "unactivated workspace release mediator could not be started",
                ) from None
            if completed.returncode != 0:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_unactivated_release_not_exact",
                    "unactivated workspace absence is not exact",
                )
            try:
                diagnosis = json.loads(completed.stdout)
            except json.JSONDecodeError:
                diagnosis = None
            if (
                not isinstance(diagnosis, dict)
                or set(diagnosis) != WORKSPACE_UNACTIVATED_DIAGNOSIS_KEYS
                or diagnosis.get("schemaVersion")
                    != WORKSPACE_UNACTIVATED_DIAGNOSIS_SCHEMA
                or diagnosis.get("state") != "UNACTIVATED_ABSENCE_CONFIRMED"
                or diagnosis.get("sessionId") != exact["sessionId"]
                or diagnosis.get("workspaceIdentity") != exact["workspaceIdentity"]
                or diagnosis.get("projectId") != PROJECT_ID
                or diagnosis.get("workerId") != self.worker_id
                or diagnosis.get("requestFingerprintSha256") != canonical_hash(exact)
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(diagnosis.get("absenceFingerprintSha256"))
                ) is None
                or diagnosis.get("valuesExposed") is not False
            ):
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "workspace_unactivated_release_response_invalid",
                    "unactivated workspace release returned an invalid diagnosis",
                )
            receipt = {
                "schemaVersion": WORKSPACE_RELEASE_SCHEMA,
                "state": "RELEASED",
                **exact,
                "workerId": self.worker_id,
                "requestFingerprintSha256": canonical_hash(exact),
                "revision": WORKSPACE_RELEASE_REVISION,
                "removed": {key: 0 for key in WORKSPACE_RELEASE_REMOVED_KEYS},
                "released": {key: True for key in WORKSPACE_RELEASE_RELEASED_KEYS},
                "retained": {key: True for key in WORKSPACE_RELEASE_RETAINED_KEYS},
                "ownershipFingerprintSha256": diagnosis["absenceFingerprintSha256"],
                "valuesExposed": False,
            }
            receipt["receiptSha256"] = canonical_hash(receipt)
            receipt = validate_workspace_release_receipt(exact, self.worker_id, receipt)
            with self.lock:
                self.unactivated_workspace_releases[exact["operationId"]] = {
                    "request": exact,
                    "receipt": receipt,
                }
                self._persist()
            return receipt

    def diagnose_workspace_release_preflight(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        exact_request = validate_workspace_release_request(request)
        with self.workspace_lifecycle_lock():
            with self.lock:
                assert_no_non_terminal_session_execution(
                    self.executions, exact_request["sessionId"]
                )
            releaser = self.project_workspace_releaser
            if releaser is None or not releaser.is_file():
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_release_preflight_unavailable",
                    "workspace release preflight is unavailable",
                )
            try:
                completed = subprocess.run(
                    [
                        *self.privilege_command,
                        str(releaser),
                        "--diagnose-release-preflight",
                    ],
                    input=json.dumps(
                        exact_request, sort_keys=True, separators=(",", ":")
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ProtocolError(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    "workspace_release_preflight_timeout",
                    "workspace release preflight exceeded its finite timeout",
                ) from None
            except OSError:
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_release_preflight_unavailable",
                    "workspace release preflight mediator could not be started",
                ) from None
            if completed.returncode != 0:
                try:
                    safe_error = reviewed_mediator_stderr_envelope(completed.stderr)
                except ValueError:
                    safe_error = worker_error_envelope(
                        "WORKSPACE_RELEASE_PREFLIGHT_REJECTED",
                        "OWNERSHIP",
                        False,
                        "CONTACT_PLATFORM_ADMINISTRATOR",
                    )
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_release_preflight_failed",
                    "workspace release preflight failed closed",
                    safe_error,
                )
            try:
                response = json.loads(completed.stdout)
            except json.JSONDecodeError:
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "workspace_release_preflight_response_invalid",
                    "workspace release preflight returned invalid JSON",
                ) from None
            return validate_workspace_release_preflight_response(
                exact_request, self.worker_id, response
            )

    def diagnose_workspace_capacity_owner(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        exact_request = validate_workspace_capacity_owner_request(request)
        with self.workspace_lifecycle_lock():
            releaser = self.project_workspace_releaser
            if releaser is None or not releaser.is_file():
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_capacity_owner_unavailable",
                    "workspace capacity-owner diagnosis is unavailable",
                )
            try:
                completed = subprocess.run(
                    [
                        *self.privilege_command,
                        str(releaser),
                        "--diagnose-capacity-owner",
                    ],
                    input=json.dumps(
                        exact_request, sort_keys=True, separators=(",", ":")
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ProtocolError(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    "workspace_capacity_owner_timeout",
                    "workspace capacity-owner diagnosis exceeded its finite timeout",
                ) from None
            except OSError:
                raise ProtocolError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "workspace_capacity_owner_unavailable",
                    "workspace capacity-owner mediator could not be started",
                ) from None
            if completed.returncode != 0:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_capacity_owner_not_exact",
                    "workspace capacity owner is absent or not exact",
                )
            try:
                response = json.loads(completed.stdout)
            except json.JSONDecodeError:
                raise ProtocolError(
                    HTTPStatus.BAD_GATEWAY,
                    "workspace_capacity_owner_response_invalid",
                    "workspace capacity-owner diagnosis returned invalid JSON",
                ) from None
            return validate_workspace_capacity_owner_response(
                exact_request, self.worker_id, response
            )

    def diagnose_workspace_readiness(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.project_readiness_enabled:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_readiness_disabled",
                "workspace readiness is disabled",
            )
        exact = validate_workspace_readiness_request(request)
        with self.workspace_lifecycle_lock():
            route = self._project_route(PROJECT_ID)
            self._refresh_project_mirror(route)
            canonical_commit = self._observe_project_commit(route)
            requested_commit = exact["commit"]
            if requested_commit == canonical_commit:
                state = "READY_FOR_RETRY"
                next_action = "RETRY_AGENT_RUN"
            elif self._is_project_commit_ancestor(
                route, requested_commit, canonical_commit
            ):
                state = "SOURCE_ADVANCED"
                next_action = "START_FRESH_SESSION"
            else:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "workspace_readiness_source_conflict",
                    "workspace readiness source relationship is not exact",
                )
            relationship = {
                "requestedCommit": requested_commit,
                "canonicalCommit": canonical_commit,
                "state": state,
            }
            response = {
                "schemaVersion": WORKSPACE_READINESS_SCHEMA,
                "state": state,
                "sessionId": exact["sessionId"],
                "workspaceIdentity": exact["workspaceIdentity"],
                "projectId": PROJECT_ID,
                "workerId": self.worker_id,
                "requestedCommit": requested_commit,
                "canonicalCommit": canonical_commit,
                "retryAllowed": state == "READY_FOR_RETRY",
                "nextAction": next_action,
                "requestFingerprintSha256": canonical_hash(exact),
                "relationshipFingerprintSha256": canonical_hash(relationship),
                "valuesExposed": False,
            }
            return validate_workspace_readiness_response(exact, self.worker_id, response)

    def _ensure_workspace_locked(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != WORKSPACE_ENSURE_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workspace_request",
                "workspace request fields are invalid",
            )
        session_id = request["sessionId"]
        try:
            parsed_session = str(uuid.UUID(session_id))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_session",
                "sessionId must be a canonical UUID",
            )
        if parsed_session != session_id:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_session",
                "sessionId must be a canonical UUID",
            )
        workspace_branch = request["workspaceBranch"]
        if (
            not isinstance(workspace_branch, str)
            or workspace_branch != f"atenea/session-{session_id}"
        ):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workspace_branch",
                "workspace branch is not a persisted WorkSession branch",
            )
        project_id = request.get("projectId")
        if project_id == PROJECT_ID:
            route = self._project_route(PROJECT_ID)
            static_identity = {
                "workspaceIdentity": f"remote:ax42-01:work-session:{session_id}",
                "projectId": PROJECT_ID,
                "repository": PROJECT_REPOSITORY,
                "branch": PROJECT_BRANCH,
                "manifestSha256": PROJECT_MANIFEST_SHA256,
            }
            if any(request.get(key) != value for key, value in static_identity.items()):
                raise ProtocolError(
                    HTTPStatus.FORBIDDEN,
                    "workspace_ownership_conflict",
                    "workspace activation identity is not exact",
                )
            self._refresh_project_mirror(route)
            canonical_commit = self._observe_project_commit(route)
            route_identity = {
                "projectId": PROJECT_ID,
                "repository": PROJECT_REPOSITORY,
                "branch": PROJECT_BRANCH,
                "commit": canonical_commit,
                "manifestSha256": PROJECT_MANIFEST_SHA256,
            }
            activator = self.project_workspace_activator
            allowed_slots = {"slot2", "slot3", "slot4"}
        elif project_id == BEAUTIPS_PROJECT_ID:
            canonical_commit = BEAUTIPS_PROJECT_COMMIT
            route_identity = {
                "projectId": BEAUTIPS_PROJECT_ID,
                "repository": BEAUTIPS_PROJECT_REPOSITORY,
                "branch": BEAUTIPS_PROJECT_BRANCH,
                "commit": BEAUTIPS_PROJECT_COMMIT,
                "manifestSha256": BEAUTIPS_PROJECT_MANIFEST_SHA256,
            }
            activator = self.beautips_workspace_activator
            allowed_slots = {"slot2", "slot3", "slot4"}
        else:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_ownership_conflict",
                "workspace activation identity is not exact",
            )
        exact = {
            "workspaceIdentity": f"remote:ax42-01:work-session:{session_id}",
            **route_identity,
        }
        if any(request.get(key) != value for key, value in exact.items()):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_ownership_conflict",
                "workspace activation identity is not exact",
            )
        if activator is None or not activator.is_file():
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "workspace_activation_unavailable",
                "workspace activation is unavailable",
            )
        try:
            completed = subprocess.run(
                [*self.privilege_command, str(activator), "ensure", session_id, workspace_branch],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ProtocolError(
                HTTPStatus.GATEWAY_TIMEOUT,
                "workspace_activation_timeout",
                "workspace activation exceeded its finite timeout",
            )
        if completed.returncode != 0:
            try:
                safe_error = reviewed_mediator_stderr_envelope(completed.stderr)
            except ValueError:
                safe_error = worker_error_envelope(
                    "WORKSPACE_ACTIVATION_FAILED",
                    "PROTOCOL",
                    False,
                    "CONTACT_PLATFORM_ADMINISTRATOR",
                )
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "workspace_activation_failed",
                "workspace activation failed closed",
                safe_error,
            )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "workspace_activation_invalid",
                "workspace activation returned an invalid response",
            )
        if (
            not isinstance(result, dict)
            or result.get("state") != "ready"
            or result.get("sessionId") != session_id
            or result.get("workspaceIdentity") != exact["workspaceIdentity"]
            or result.get("projectId") != project_id
            or result.get("workspaceBranch") != workspace_branch
            or result.get("slot") not in allowed_slots
            or result.get("canonicalCommit") != canonical_commit
            or result.get("valuesExposed") is not False
        ):
            raise ProtocolError(
                HTTPStatus.BAD_GATEWAY,
                "workspace_activation_invalid",
                "workspace activation response ownership is incomplete",
            )
        return result

    def fingerprint_retained_draft(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != DRAFT_FINGERPRINT_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_draft_request",
                "draft fingerprint request fields are invalid",
            )
        try:
            session_id = str(uuid.UUID(request.get("sessionId")))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_session",
                "sessionId must be a canonical UUID",
            )
        if session_id != request.get("sessionId"):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_session",
                "sessionId must be a canonical UUID",
            )
        route = self._project_route(request.get("projectId"))
        exact = {
            "workspaceIdentity": f"remote:{self.worker_id}:work-session:{session_id}",
            "projectId": PROJECT_ID,
            "repository": PROJECT_REPOSITORY,
            "branch": PROJECT_BRANCH,
            "manifestSha256": PROJECT_MANIFEST_SHA256,
        }
        if route is None or request.get("projectId") != PROJECT_ID or any(
            request.get(key) != value for key, value in exact.items()
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "draft_ownership_conflict",
                "retained draft identity is not exact",
            )
        accepted_commit = request.get("acceptedCommit")
        if (
            not isinstance(accepted_commit, str)
            or COMMIT_PATTERN.fullmatch(accepted_commit) is None
            or accepted_commit != self._observe_project_commit(route)
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_moved",
                "accepted canonical source is not current on the worker mirror",
            )
        config = self._read_project_config(route)
        record = config["workspaces"].get(request["workspaceIdentity"])
        if (
            not isinstance(record, dict)
            or set(record) != {"sessionId", "worktree", "allocationSha256", "canonicalCommit"}
            or record.get("sessionId") != session_id
            or not isinstance(record.get("worktree"), str)
            or COMMIT_PATTERN.fullmatch(str(record.get("canonicalCommit"))) is None
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "draft_ownership_conflict",
                "persisted retained draft ownership is incomplete or conflicting",
            )
        with self.lock:
            if any(
                execution["sessionId"] == session_id and execution["status"] in NON_TERMINAL
                for execution in self.executions.values()
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "draft_execution_active",
                    "retained draft still owns a non-terminal execution",
                )

        worktree = Path(record["worktree"])
        if not worktree.is_dir() or worktree.is_symlink():
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "draft_workspace_unavailable",
                "retained draft workspace is unavailable or unsafe",
            )
        head = self._draft_git(worktree, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
        if (
            COMMIT_PATTERN.fullmatch(head) is None
            or head != record["canonicalCommit"]
            or head == accepted_commit
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "draft_not_stale",
                "retained draft is not an exactly identified stale workspace",
            )

        source = self._source_tree_fingerprint(worktree, head)
        if (
            source["stagedChangeCount"]
            + source["unstagedChangeCount"]
            + source["untrackedChangeCount"]
        ) == 0:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "draft_not_dirty",
                "retained draft has no changes to preserve",
            )
        fingerprint = canonical_hash({
            "acceptedCommit": accepted_commit,
            "sourceTreeFingerprintSha256": source["fingerprintSha256"],
        })
        return {
            "state": "draft_blocked_ready",
            "sessionId": session_id,
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "retainedHead": head,
            "acceptedCommit": accepted_commit,
            "fingerprintSha256": fingerprint,
            "stagedChangeCount": source["stagedChangeCount"],
            "unstagedChangeCount": source["unstagedChangeCount"],
            "untrackedChangeCount": source["untrackedChangeCount"],
            "valuesExposed": False,
        }

    def fingerprint_source_tree(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != SOURCE_TREE_FINGERPRINT_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_source_tree_request",
                "source tree fingerprint request fields are invalid",
            )
        try:
            session_id = str(uuid.UUID(request.get("sessionId")))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_session",
                "sessionId must be a canonical UUID",
            )
        route = self._project_route(request.get("projectId"))
        exact = {
            "sessionId": session_id,
            "workspaceIdentity": f"remote:{self.worker_id}:work-session:{session_id}",
            "projectId": PROJECT_ID,
            "repository": PROJECT_REPOSITORY,
            "branch": PROJECT_BRANCH,
            "manifestSha256": PROJECT_MANIFEST_SHA256,
        }
        if (
            request.get("sessionId") != session_id
            or route is None
            or request.get("projectId") != PROJECT_ID
            or any(request.get(key) != value for key, value in exact.items())
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "source_tree_ownership_conflict",
                "source tree identity is not exact",
            )
        commit = request.get("commit")
        config = self._read_project_config(route)
        if (
            not isinstance(commit, str)
            or COMMIT_PATTERN.fullmatch(commit) is None
            or commit != self._observe_project_commit(route)
            or config["commit"] != commit
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_moved",
                "source tree canonical ownership is not current",
            )
        record = config["workspaces"].get(request["workspaceIdentity"])
        if (
            not isinstance(record, dict)
            or set(record) != {"sessionId", "worktree", "allocationSha256", "canonicalCommit"}
            or record.get("sessionId") != session_id
            or record.get("canonicalCommit") != commit
            or not isinstance(record.get("worktree"), str)
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "source_tree_ownership_conflict",
                "persisted source tree ownership is incomplete or conflicting",
            )
        worktree = Path(record["worktree"])
        if not worktree.is_dir() or worktree.is_symlink():
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "source_tree_unavailable",
                "source tree workspace is unavailable or unsafe",
            )
        head = self._draft_git(worktree, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
        if head != commit:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "source_tree_head_moved",
                "source tree HEAD no longer equals its accepted base commit",
            )
        source = self._source_tree_fingerprint(worktree, head)
        return {
            "state": "observed",
            "sessionId": session_id,
            "workspaceIdentity": request["workspaceIdentity"],
            "projectId": PROJECT_ID,
            "headCommit": head,
            **source,
            "valuesExposed": False,
        }

    def run_validation(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != VALIDATION_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_validation_request",
                "validation request fields are invalid",
            )
        try:
            validation_id = str(uuid.UUID(request.get("validationId")))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_validation",
                "validationId must be a canonical UUID",
            )
        operation = request.get("operation")
        definition = VALIDATION_DEFINITIONS.get(operation)
        if (
            validation_id != request.get("validationId")
            or definition is None
            or request.get("definitionRevision") != definition[0]
            or not isinstance(request.get("sourceTreeFingerprintSha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", request["sourceTreeFingerprintSha256"]) is None
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "validation_authority_conflict",
                "validation definition is not exact",
            )
        source_request = {
            key: request[key]
            for key in SOURCE_TREE_FINGERPRINT_KEYS
        }
        source = self.fingerprint_source_tree(source_request)
        if source["fingerprintSha256"] != request["sourceTreeFingerprintSha256"]:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "source_tree_changed",
                "source tree changed before validation admission",
            )

        request_fingerprint = canonical_hash(request)
        with self.lock:
            existing = self.validations.get(validation_id)
            if existing is not None:
                if existing["requestFingerprint"] != request_fingerprint:
                    raise ProtocolError(
                        HTTPStatus.CONFLICT,
                        "validation_identity_conflict",
                        "validationId already owns a different immutable request",
                    )
                return self._public_validation(existing)
            now = utc_now()
            validation = {
                "validationId": validation_id,
                "sessionId": request["sessionId"],
                "workspaceIdentity": request["workspaceIdentity"],
                "operation": operation,
                "definitionRevision": definition[0],
                "sourceTreeFingerprintSha256": request["sourceTreeFingerprintSha256"],
                "requestFingerprint": request_fingerprint,
                "status": "RUNNING",
                "exitCode": None,
                "durationMillis": 0,
                "artifactManifestSha256": None,
                "summary": "Bounded validation is running",
                "valuesExposed": False,
                "createdAt": now,
                "finishedAt": None,
            }
            self.validations[validation_id] = validation
            self._persist()

        started = time.monotonic()
        mediator = self.project_validation_mediator
        if mediator is None or not mediator.is_file():
            return self._finish_validation(
                validation_id,
                "BLOCKED",
                None,
                started,
                hashlib.sha256(b"validation mediator unavailable").hexdigest(),
                "Validation mediator is unavailable",
            )
        try:
            completed = subprocess.run(
                [
                    *self.privilege_command,
                    str(mediator),
                    operation,
                    request["sessionId"],
                    request["sourceTreeFingerprintSha256"],
                    validation_id,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=definition[1],
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._finish_validation(
                validation_id,
                "BLOCKED",
                None,
                started,
                hashlib.sha256(f"{operation}:timeout".encode()).hexdigest(),
                "Validation exceeded its finite timeout",
            )
        except OSError:
            return self._finish_validation(
                validation_id,
                "BLOCKED",
                None,
                started,
                hashlib.sha256(f"{operation}:unavailable".encode()).hexdigest(),
                "Validation mediator could not be started",
            )
        if completed.returncode != 0:
            return self._finish_validation(
                validation_id,
                "BLOCKED",
                None,
                started,
                hashlib.sha256(f"{operation}:mediator-failed".encode()).hexdigest(),
                "Validation mediator failed closed",
            )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = None
        required = {
            "validationId", "sessionId", "operation", "definitionRevision",
            "sourceTreeFingerprintSha256", "status", "exitCode",
            "durationMillis", "artifactManifestSha256", "summary",
            "valuesExposed",
        }
        if (
            not isinstance(result, dict)
            or set(result) != required
            or result.get("validationId") != validation_id
            or result.get("sessionId") != request["sessionId"]
            or result.get("operation") != operation
            or result.get("definitionRevision") != definition[0]
            or result.get("sourceTreeFingerprintSha256")
                != request["sourceTreeFingerprintSha256"]
            or result.get("status") not in {"SUCCEEDED", "FAILED", "BLOCKED"}
            or not isinstance(result.get("durationMillis"), int)
            or result["durationMillis"] < 0
            or not isinstance(result.get("artifactManifestSha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", result["artifactManifestSha256"]) is None
            or not isinstance(result.get("summary"), str)
            or not (1 <= len(result["summary"]) <= 500)
            or result.get("valuesExposed") is not False
            or (
                result["status"] == "SUCCEEDED"
                and result.get("exitCode") != 0
            )
            or (
                result["status"] == "FAILED"
                and (
                    not isinstance(result.get("exitCode"), int)
                    or result["exitCode"] == 0
                )
            )
        ):
            return self._finish_validation(
                validation_id,
                "BLOCKED",
                None,
                started,
                hashlib.sha256(f"{operation}:invalid-result".encode()).hexdigest(),
                "Validation mediator returned an invalid closed result",
            )
        return self._finish_validation(
            validation_id,
            result["status"],
            result["exitCode"],
            started,
            result["artifactManifestSha256"],
            result["summary"],
            duration_millis=result["durationMillis"],
        )

    def ensure_repository_roles(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != REPOSITORY_ROLE_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_repository_roles",
                "repository role request fields are invalid")
        try:
            session_id = str(uuid.UUID(request.get("sessionId")))
            change_id = str(uuid.UUID(request.get("changeIdentity")))
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_repository_roles",
                "repository role identities must be canonical UUIDs")
        exact_identity = f"remote:{self.worker_id}:work-session:{session_id}"
        if (
            session_id != request.get("sessionId")
            or change_id != request.get("changeIdentity")
            or request.get("workspaceIdentity") != exact_identity
            or not isinstance(request.get("codeCommit"), str)
            or re.fullmatch(r"[0-9a-f]{40}", request["codeCommit"]) is None
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN, "repository_role_authority_conflict",
                "repository role ownership is not exact")
        route = self._project_route(PROJECT_ID)
        config = self._read_project_config(route)
        record = config["workspaces"].get(exact_identity)
        if (
            record is None
            or record.get("sessionId") != session_id
            or record.get("canonicalCommit") != request["codeCommit"]
            or config.get("commit") != request["codeCommit"]
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN, "repository_role_ownership_conflict",
                "persisted code role ownership is conflicting")
        mediator = self.repository_role_mediator
        if mediator is None or not mediator.is_file():
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "repository_role_mediator_unavailable",
                "repository role mediator is unavailable")
        try:
            completed = subprocess.run(
                [*self.privilege_command, str(mediator), "ensure",
                 session_id, change_id, request["codeCommit"]],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ProtocolError(
                HTTPStatus.SERVICE_UNAVAILABLE, "repository_role_mediator_failed",
                "repository role mediator failed closed")
        if completed.returncode != 0:
            raise ProtocolError(
                HTTPStatus.CONFLICT, "repository_role_rejected",
                "repository role mediator rejected ownership")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = None
        if (
            not isinstance(result, dict)
            or set(result) != {
                "sessionId", "workspaceIdentity", "changeIdentity", "roles",
                "valuesExposed"}
            or result.get("sessionId") != session_id
            or result.get("workspaceIdentity") != exact_identity
            or result.get("changeIdentity") != change_id
            or result.get("valuesExposed") is not False
            or not isinstance(result.get("roles"), list)
            or len(result["roles"]) != 3
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT, "repository_role_result_conflict",
                "repository role result is incomplete or conflicting")
        role_fields = {
            "role", "authority", "repository", "branch", "commit",
            "mirrorIdentitySha256", "worktreeIdentitySha256",
            "validationProfile", "readiness",
        }
        expected_roles = {
            "ATENEA_CODE": (PROJECT_BRANCH, request["codeCommit"], "atenea-code-v1"),
            "PROGRAMME_OPENSPEC": (
                "program/remote-codex-worker-platform", None, "openspec-strict-v1"),
            "WORKER_SOURCE": (
                "program/remote-codex-worker-platform", None, "worker-contract-v1"),
        }
        seen: set[str] = set()
        program_commits: set[str] = set()
        for role in result["roles"]:
            expected = expected_roles.get(role.get("role")) if isinstance(role, dict) else None
            if (
                not isinstance(role, dict)
                or set(role) != role_fields
                or expected is None
                or role["role"] in seen
                or role.get("authority") != "READ_WRITE"
                or role.get("repository") != PROJECT_REPOSITORY
                or role.get("branch") != expected[0]
                or role.get("validationProfile") != expected[2]
                or role.get("readiness") != "DRAFT"
                or COMMIT_PATTERN.fullmatch(str(role.get("commit"))) is None
                or re.fullmatch(r"[0-9a-f]{64}", str(role.get("mirrorIdentitySha256"))) is None
                or re.fullmatch(r"[0-9a-f]{64}", str(role.get("worktreeIdentitySha256"))) is None
                or (expected[1] is not None and role.get("commit") != expected[1])
            ):
                raise ProtocolError(
                    HTTPStatus.CONFLICT, "repository_role_result_conflict",
                    "repository role result is incomplete or conflicting")
            seen.add(role["role"])
            if role["role"] != "ATENEA_CODE":
                program_commits.add(role["commit"])
        if seen != set(expected_roles) or len(program_commits) != 1:
            raise ProtocolError(
                HTTPStatus.CONFLICT, "repository_role_result_conflict",
                "repository role result is incomplete or conflicting")
        return result

    def _finish_validation(
        self,
        validation_id: str,
        status: str,
        exit_code: int | None,
        started: float,
        artifact_manifest_sha256: str,
        summary: str,
        duration_millis: int | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            validation = self.validations[validation_id]
            validation["status"] = status
            validation["exitCode"] = exit_code
            validation["durationMillis"] = (
                duration_millis
                if duration_millis is not None
                else int((time.monotonic() - started) * 1000)
            )
            validation["artifactManifestSha256"] = artifact_manifest_sha256
            validation["summary"] = summary
            validation["finishedAt"] = utc_now()
            self._persist()
            return self._public_validation(validation)

    def _public_validation(self, validation: dict[str, Any]) -> dict[str, Any]:
        return {
            key: validation.get(key)
            for key in (
                "validationId", "sessionId", "workspaceIdentity", "operation",
                "definitionRevision", "sourceTreeFingerprintSha256", "status",
                "exitCode", "durationMillis", "artifactManifestSha256",
                "summary", "valuesExposed",
            )
        }

    def _source_tree_fingerprint(self, worktree: Path, head: str) -> dict[str, Any]:
        staged = self._z_entries(self._draft_git(worktree, "diff", "--cached", "--name-only", "-z"))
        unstaged = self._z_entries(self._draft_git(worktree, "diff", "--name-only", "-z"))
        untracked = self._z_entries(
            self._draft_git(worktree, "ls-files", "--others", "--exclude-standard", "-z")
        )
        if len(staged) + len(unstaged) + len(untracked) > 10_000:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "source_tree_fingerprint_limit",
                "source tree exceeds the bounded fingerprint entry limit",
            )

        tracked_diff = self._draft_git(worktree, "diff", "--binary", "HEAD")
        if len(tracked_diff) > 256 * 1024 * 1024:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "source_tree_fingerprint_limit",
                "tracked source tree exceeds the bounded fingerprint size limit",
            )
        untracked_digest = hashlib.sha256()
        untracked_size = 0
        for relative_bytes in untracked:
            relative = relative_bytes.decode("utf-8", errors="surrogateescape")
            candidate = worktree / relative
            try:
                metadata = candidate.lstat()
            except OSError:
                metadata = None
            if metadata is None or not stat.S_ISREG(metadata.st_mode):
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "source_tree_unsafe",
                    "source tree contains an unsafe untracked entry",
                )
            untracked_size += metadata.st_size
            if untracked_size > 256 * 1024 * 1024:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "source_tree_fingerprint_limit",
                    "untracked source tree exceeds the bounded fingerprint size limit",
                )
            untracked_digest.update(relative_bytes)
            untracked_digest.update(b"\0")
            file_digest = hashlib.sha256()
            try:
                with candidate.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        file_digest.update(chunk)
            except OSError:
                raise ProtocolError(
                    HTTPStatus.CONFLICT,
                    "source_tree_unavailable",
                    "source tree changed during fingerprinting",
                )
            untracked_digest.update(file_digest.digest())
        fingerprint = canonical_hash({
            "headCommit": head,
            "trackedDiffSha256": hashlib.sha256(tracked_diff).hexdigest(),
            "untrackedManifestSha256": untracked_digest.hexdigest(),
            "stagedChangeCount": len(staged),
            "unstagedChangeCount": len(unstaged),
            "untrackedChangeCount": len(untracked),
        })
        return {
            "fingerprintSha256": fingerprint,
            "stagedChangeCount": len(staged),
            "unstagedChangeCount": len(unstaged),
            "untrackedChangeCount": len(untracked),
        }

    def _draft_git(self, worktree: Path, *arguments: str) -> bytes:
        try:
            completed = subprocess.run(
                ["git", "-c", f"safe.directory={worktree}", "-C", str(worktree), *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=True,
            )
            return completed.stdout
        except (OSError, subprocess.SubprocessError):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "draft_workspace_unavailable",
                "retained draft Git state is unavailable",
            )

    def _z_entries(self, value: bytes) -> list[bytes]:
        return [entry for entry in value.split(b"\0") if entry]

    def get(self, dispatch_id: str) -> dict[str, Any]:
        with self.lock:
            execution = self.executions.get(dispatch_id)
            if not execution:
                raise ProtocolError(HTTPStatus.NOT_FOUND, "execution_not_found", "execution does not exist")
            return self._public(execution)

    def renew(self, dispatch_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != {"executionId", "leaseGeneration"}:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_lease", "lease request fields are invalid")
        with self.lock:
            execution = self._owned(dispatch_id, request["executionId"])
            generation = request["leaseGeneration"]
            if not isinstance(generation, int) or generation < execution["leaseGeneration"]:
                raise ProtocolError(HTTPStatus.CONFLICT, "stale_lease", "lease generation is stale")
            execution["leaseGeneration"] = generation
            execution["updatedAt"] = utc_now()
            self._persist()
            return self._public(execution)

    def cancel(self, dispatch_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) != {"executionId"}:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_cancel", "cancel request fields are invalid")
        with self.lock:
            execution = self._owned(dispatch_id, request["executionId"])
            if execution["status"] in TERMINAL:
                return self._public(execution)
            execution["cancelRequested"] = True
            execution["status"] = "CANCELLING"
            execution["statusReason"] = "Cancellation requested for exact execution"
            execution["revision"] += 1
            execution["updatedAt"] = utc_now()
            self._persist()
            process = self.processes.get(dispatch_id)
            if process and process.poll() is None:
                process.terminate()
            self.wakeup.set()
            return self._public(execution)

    def cancel_exact(self, dispatch_id: str, request: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            execution = self._exact_operation_owned(
                dispatch_id, request, "invalid_exact_cancel"
            )
            execution_id = execution["executionId"]
        return self.cancel(dispatch_id, {"executionId": execution_id})

    def inspect_reconciliation(
        self,
        dispatch_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        with self.lock:
            execution = self._exact_operation_owned(
                dispatch_id, request, "invalid_reconcile_inspection"
            )
            return self._public(execution)

    def doctor(self, dispatch_id: str, request: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            execution = self._exact_operation_owned(
                dispatch_id, request, "invalid_execution_doctor"
            )
            process = self.processes.get(dispatch_id)
            thread = self.threads.get(dispatch_id)
            progress_events = execution.get("progressEvents", [])
            if execution["status"] in TERMINAL:
                observation = "TERMINAL"
            elif execution.get("reconcileRequired"):
                observation = "RECONCILIATION_REQUIRED"
            elif process is not None and process.poll() is None:
                observation = "OWNED_PROCESS_ACTIVE"
            elif thread is not None and thread.is_alive():
                observation = "OWNED_EXECUTION_ACTIVE"
            else:
                observation = "PERSISTED_NO_PROCESS"
            return {
                "schemaVersion": "agent-run-doctor-v1",
                "workerId": self.worker_id,
                "dispatchId": execution["dispatchId"],
                "executionId": execution["executionId"],
                "sessionId": execution["sessionId"],
                "workspaceIdentity": execution["workspaceIdentity"],
                "leaseGeneration": execution["leaseGeneration"],
                "status": execution["status"],
                "revision": execution["revision"],
                "observation": observation,
                "cancelRequested": execution["cancelRequested"],
                "reconcileRequired": execution["reconcileRequired"],
                "latestProgressSequence": (
                    progress_events[-1]["sequence"] if progress_events else None
                ),
                "retainedProgressCount": len(progress_events),
                "valuesExposed": False,
            }

    def _exact_operation_owned(
        self,
        dispatch_id: str,
        request: Any,
        error_code: str,
    ) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != EXACT_EXECUTION_OPERATION_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                error_code,
                "exact execution operation fields are invalid",
            )
        execution = self._owned(dispatch_id, request.get("executionId"))
        if (
            request.get("sessionId") != execution["sessionId"]
            or request.get("workspaceIdentity") != execution["workspaceIdentity"]
            or not isinstance(request.get("leaseGeneration"), int)
            or isinstance(request.get("leaseGeneration"), bool)
            or request["leaseGeneration"] != execution["leaseGeneration"]
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "execution_ownership_conflict",
                "exact execution operation ownership does not match",
            )
        return execution

    def _owned(self, dispatch_id: str, execution_id: Any) -> dict[str, Any]:
        execution = self.executions.get(dispatch_id)
        if not execution:
            raise ProtocolError(HTTPStatus.NOT_FOUND, "execution_not_found", "execution does not exist")
        if not isinstance(execution_id, str) or execution["executionId"] != execution_id:
            raise ProtocolError(HTTPStatus.CONFLICT, "execution_ownership_conflict", "execution identity does not match")
        return execution

    def _validate_create(self, request: Any) -> None:
        workload = self._validate_dispatch_envelope(request)
        if workload["kind"] == SYNTHETIC_CAPABILITY:
            self._validate_synthetic(workload)
        elif workload["kind"] == PROJECT_CAPABILITY:
            self._validate_project(request, workload)
        elif workload["kind"] == PROJECT_V2_CAPABILITY:
            self._validate_profiled_project(request, workload)
        elif workload["kind"] == PROJECT_V3_CAPABILITY:
            self._validate_profiled_project(request, workload)
        elif workload["kind"] == PROJECT_V4_CAPABILITY:
            self._validate_change_project_shape(request, workload)
            self._validate_change_project_ownership(request, workload)
        else:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "unsupported_workload", "workload kind is unsupported")

    def _validate_dispatch_envelope(self, request: Any) -> dict[str, Any]:
        workload = request.get("workload") if isinstance(request, dict) else None
        expected_keys = (
            CHANGE_CREATE_KEYS
            if isinstance(workload, dict)
            and workload.get("kind") == PROJECT_V4_CAPABILITY
            else CREATE_KEYS
        )
        if not isinstance(request, dict) or set(request) != expected_keys:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_dispatch", "dispatch fields are invalid")
        try:
            uuid.UUID(request["dispatchId"])
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_dispatch_id", "dispatchId must be a UUID")
        if not isinstance(request["sessionId"], str) or not request["sessionId"].strip():
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_session", "sessionId is required")
        if not isinstance(request["workspaceIdentity"], str) or not request["workspaceIdentity"].startswith("remote:"):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_workspace", "remote workspace identity is required")
        if request["workloadClass"] not in {"NORMAL", "HEAVY"}:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_workload_class", "workloadClass is invalid")
        if not isinstance(request["leaseGeneration"], int) or request["leaseGeneration"] < 1:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_lease", "leaseGeneration must be positive")
        if not isinstance(workload, dict) or "kind" not in workload:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_workload", "workload fields are invalid")
        return workload

    def _validate_change_project_shape(
        self,
        request: dict[str, Any],
        workload: dict[str, Any],
    ) -> None:
        if set(workload) != PROJECT_V4_WORKLOAD_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workload",
                "change-aware project workload fields are invalid",
            )
        exact_project = {
            "kind": PROJECT_V4_CAPABILITY,
            "projectId": PROJECT_ID,
            "repository": PROJECT_REPOSITORY,
            "branch": PROJECT_BRANCH,
            "manifestSha256": PROJECT_MANIFEST_SHA256,
            "instructionBundleRevision": INSTRUCTION_BUNDLE_REVISION,
            "instructionBundleSha256": ATENEA_INSTRUCTION_BUNDLE_SHA256,
            "platformInstructionSha256": PLATFORM_INSTRUCTION_SHA256,
            "projectInstructionPath": PROJECT_INSTRUCTION_PATH,
            "projectInstructionSha256": ATENEA_PROJECT_INSTRUCTION_SHA256,
        }
        if any(workload.get(key) != value for key, value in exact_project.items()):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "project_ownership_conflict",
                "change-aware project identity is not allowlisted",
            )
        if not isinstance(workload.get("commit"), str) or COMMIT_PATTERN.fullmatch(
            workload["commit"]
        ) is None:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_source", "expected source commit is invalid"
            )
        if not isinstance(workload.get("message"), str) or not (
            1 <= len(workload["message"]) <= 20_000
        ):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST, "invalid_message", "message length is invalid"
            )
        thread_id = workload.get("threadId")
        if thread_id is not None:
            try:
                if str(uuid.UUID(thread_id)) != thread_id:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_thread",
                    "threadId must be null or a canonical UUID",
                ) from None
        model = next(
            (item for item in CODEX_MODELS if item["modelId"] == workload.get("modelId")),
            None,
        )
        if (
            model is None
            or model["availability"] != "AVAILABLE"
            or workload.get("reasoningEffort") not in model["supportedEfforts"]
            or workload.get("catalogRevision") != codex_catalog_revision()
            or workload.get("codexVersion") != CODEX_VERSION
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "profile_ownership_conflict",
                "Codex profile is not in the accepted worker catalog",
            )
        ownership = request.get("changeOwnership")
        if not isinstance(ownership, dict) or set(ownership) != CHANGE_OWNERSHIP_KEYS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "change_ownership_invalid",
                "development change ownership fields are invalid",
            )
        for key in ("changeKey", "remoteSessionId"):
            try:
                if str(uuid.UUID(ownership.get(key))) != ownership.get(key):
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "change_ownership_invalid",
                    "development change ownership identity is invalid",
                ) from None
        change_key = ownership["changeKey"]
        exact_workspace = f"remote:{self.worker_id}:change:{change_key}"
        if (
            request.get("sessionId") != ownership["remoteSessionId"]
            or request.get("workspaceIdentity") != ownership["workspaceIdentity"]
            or ownership["workspaceIdentity"] != exact_workspace
            or workload["commit"] != ownership.get("expectedCanonicalCommit")
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "change_ownership_conflict",
                "development change, WorkSession and workspace ownership do not match",
            )
        database_project_id = ownership.get("databaseProjectId")
        database_work_session_id = ownership.get("databaseWorkSessionId")
        source_revision = ownership.get("sourceRevision")
        if (
            not isinstance(database_project_id, int)
            or isinstance(database_project_id, bool)
            or database_project_id < 1
            or not isinstance(database_work_session_id, int)
            or isinstance(database_work_session_id, bool)
            or database_work_session_id < 1
            or not isinstance(source_revision, int)
            or isinstance(source_revision, bool)
            or source_revision < 0
            or COMMIT_PATTERN.fullmatch(str(ownership.get("baseCommit", ""))) is None
            or COMMIT_PATTERN.fullmatch(
                str(ownership.get("expectedCanonicalCommit", ""))
            ) is None
            or any(
                re.fullmatch(r"[0-9a-f]{64}", str(ownership.get(key, ""))) is None
                for key in (
                    "sourceFingerprintSha256",
                    "workspaceOwnershipFingerprintSha256",
                )
            )
        ):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "change_ownership_invalid",
                "development change source ownership is invalid",
            )
        attachments = workload.get("attachments")
        if not isinstance(attachments, list) or len(attachments) > PROJECT_V3_MAX_ATTACHMENTS:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_attachments",
                "project attachment count is outside the bounded policy",
            )
        if attachments:
            self._validate_project_attachments(attachments)

    def _validate_change_project_ownership(
        self,
        request: dict[str, Any],
        workload: dict[str, Any],
    ) -> None:
        route = self._project_route(workload.get("projectId"))
        if route is None or not self._project_execution_enabled(route):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN, "project_disabled", "project workload is disabled"
            )
        config = self._read_project_config(route, require_execution=True)
        if (
            workload.get("attachments")
            and config.get("attachmentRoot") != PROJECT_ATTACHMENT_ROOT
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "project_disabled",
                "image-bearing project configuration is not activated",
            )
        observed_commit = self._observe_project_commit(route)
        if config["commit"] != observed_commit or workload["commit"] != observed_commit:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_moved",
                "worker mirror canonical source moved before admission",
            )
        ownership = request["changeOwnership"]
        operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, request["dispatchId"] + ":inspect"))
        inspect_request = {
            "schemaVersion": 1,
            "protocolVersion": DEVELOPMENT_CHANGE_WORKSPACE_CAPABILITY,
            "effect": "OBSERVE_ONLY",
            "operationId": operation_id,
            "idempotencyKey": operation_id,
            "operation": "INSPECT",
            "predecessorOperationId": None,
            "changeKey": ownership["changeKey"],
            "databaseProjectId": ownership["databaseProjectId"],
            "projectId": workload["projectId"],
            "repository": workload["repository"],
            "repositoryBranch": workload["branch"],
            "baseCommit": ownership["baseCommit"],
            "expectedCanonicalCommit": ownership["expectedCanonicalCommit"],
            "workspaceBranch": f"atenea/change-{ownership['changeKey']}",
            "workspaceIdentity": ownership["workspaceIdentity"],
            "workerId": self.worker_id,
            "sourceRevision": ownership["sourceRevision"],
            "sourceFingerprintSha256": ownership["sourceFingerprintSha256"],
        }
        inspect_request["requestFingerprintSha256"] = canonical_hash(inspect_request)
        response = self.execute_development_change_workspace(inspect_request, "INSPECT")
        if (
            response.get("state") != "OWNED"
            or response.get("canonicalCommit") != ownership["expectedCanonicalCommit"]
            or response.get("sourceFingerprintSha256")
                != ownership["sourceFingerprintSha256"]
            or response.get("ownershipFingerprintSha256")
                != ownership["workspaceOwnershipFingerprintSha256"]
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "change_workspace_ownership_conflict",
                "development change workspace ownership or source is incompatible",
            )

    def _validate_synthetic(self, workload: dict[str, Any]) -> None:
        if set(workload) != SYNTHETIC_WORKLOAD_KEYS:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_workload", "synthetic workload fields are invalid")
        if not isinstance(workload["message"], str) or not (1 <= len(workload["message"]) <= 2000):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_message", "message length is invalid")
        if not isinstance(workload["durationMs"], int) or not (100 <= workload["durationMs"] <= 300_000):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_duration", "durationMs is outside the bounded policy")
        if not isinstance(workload["steps"], int) or not (1 <= workload["steps"] <= 100):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_steps", "steps is outside the bounded policy")

    def _validate_project(self, request: dict[str, Any], workload: dict[str, Any]) -> None:
        if set(workload) != PROJECT_WORKLOAD_KEYS:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_workload", "project workload fields are invalid")
        route = self._project_route(workload.get("projectId"))
        if route is None:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "project_ownership_conflict",
                "project identity is not allowlisted",
            )
        if not self._project_execution_enabled(route):
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_disabled", "project workload is disabled")
        config = self._read_project_config(route, require_execution=True)
        if config["commit"] != self._observe_project_commit(route):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_moved",
                "worker mirror canonical source moved before admission",
            )
        exact = {
            **route["identity"],
            **route["instructions"],
            "commit": config["commit"],
        }
        if any(workload.get(key) != value for key, value in exact.items()):
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_ownership_conflict", "project identity is not allowlisted")
        if not isinstance(workload["message"], str) or not (1 <= len(workload["message"]) <= 20_000):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_message", "message length is invalid")
        thread_id = workload["threadId"]
        if thread_id is not None:
            try:
                uuid.UUID(thread_id)
            except (ValueError, TypeError, AttributeError):
                raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_thread", "threadId must be null or a UUID")
        if request["workspaceIdentity"] not in config["workspaces"]:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_ownership_conflict",
                "workspace identity is not persistently registered",
            )
        record = config["workspaces"][request["workspaceIdentity"]]
        record_keys = {"sessionId", "worktree", "allocationSha256"}
        if workload["projectId"] == PROJECT_ID:
            record_keys.add("canonicalCommit")
        if (
            not isinstance(record, dict)
            or set(record) != record_keys
            or record["sessionId"] != request["sessionId"]
            or (
                workload["projectId"] == PROJECT_ID
                and record["canonicalCommit"] != workload["commit"]
            )
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "workspace_ownership_conflict",
                "persisted workspace ownership is incomplete or conflicting",
            )

    def _validate_profiled_project(
        self,
        request: dict[str, Any],
        workload: dict[str, Any],
    ) -> None:
        kind = workload.get("kind")
        if kind == PROJECT_V3_CAPABILITY and workload.get("projectId") != PROJECT_ID:
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "project_ownership_conflict",
                "image-bearing project identity is not allowlisted",
            )
        expected_keys = (
            PROJECT_V3_WORKLOAD_KEYS
            if kind == PROJECT_V3_CAPABILITY
            else PROJECT_V2_WORKLOAD_KEYS
        )
        if kind not in {PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY} or set(workload) != expected_keys:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_workload",
                "profiled project workload fields are invalid",
            )
        model = next(
            (item for item in CODEX_MODELS if item["modelId"] == workload.get("modelId")),
            None,
        )
        if (
            model is None
            or model["availability"] != "AVAILABLE"
            or workload.get("reasoningEffort") not in model["supportedEfforts"]
            or workload.get("catalogRevision") != codex_catalog_revision()
            or workload.get("codexVersion") != CODEX_VERSION
        ):
            raise ProtocolError(
                HTTPStatus.FORBIDDEN,
                "profile_ownership_conflict",
                "Codex profile is not in the accepted worker catalog",
            )
        legacy = {
            key: value
            for key, value in workload.items()
            if key not in {
                "modelId", "reasoningEffort", "catalogRevision", "codexVersion", "attachments",
            }
        }
        legacy["kind"] = PROJECT_CAPABILITY
        self._validate_project(request, legacy)
        if kind == PROJECT_V3_CAPABILITY:
            route = self._project_route(workload.get("projectId"))
            if (
                route is None
                or self._read_project_config(
                    route, require_execution=True
                ).get("attachmentRoot") != PROJECT_ATTACHMENT_ROOT
            ):
                raise ProtocolError(
                    HTTPStatus.FORBIDDEN,
                    "project_disabled",
                    "image-bearing project configuration is not activated",
                )
            self._validate_project_attachments(workload["attachments"])

    def _validate_project_attachments(self, attachments: Any) -> None:
        if (
            not isinstance(attachments, list)
            or not (1 <= len(attachments) <= PROJECT_V3_MAX_ATTACHMENTS)
        ):
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_attachments",
                "project attachment count is outside the bounded policy",
            )
        attachment_ids: set[str] = set()
        total_bytes = 0
        for attachment in attachments:
            if not isinstance(attachment, dict) or set(attachment) != PROJECT_V3_ATTACHMENT_KEYS:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_attachments",
                    "project attachment fields are invalid",
                )
            attachment_id = attachment.get("attachmentId")
            try:
                canonical_id = str(uuid.UUID(attachment_id))
            except (ValueError, TypeError, AttributeError):
                canonical_id = None
            if canonical_id != attachment_id or attachment_id in attachment_ids:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_attachments",
                    "project attachment identities must be distinct canonical UUIDs",
                )
            content_type = attachment.get("contentType")
            size_bytes = attachment.get("sizeBytes")
            digest = attachment.get("sha256")
            if content_type not in PROJECT_V3_ATTACHMENT_TYPES:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_attachments",
                    "project attachment media type is not an accepted image",
                )
            if (
                not isinstance(size_bytes, int)
                or isinstance(size_bytes, bool)
                or not (1 <= size_bytes <= PROJECT_V3_MAX_ATTACHMENT_BYTES)
            ):
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_attachments",
                    "project attachment size is outside the bounded policy",
                )
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_attachments",
                    "project attachment SHA-256 is invalid",
                )
            attachment_ids.add(attachment_id)
            total_bytes += size_bytes
        if total_bytes > PROJECT_V3_MAX_TOTAL_BYTES:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_attachments",
                "project attachment total size is outside the bounded policy",
            )

    def _project_route(self, project_id: Any) -> dict[str, Any] | None:
        if project_id == PROJECT_ID:
            return {
                "config": self.project_config,
                "runner": self.project_runner,
                "mirror": PROJECT_MIRROR,
                "identity": {
                    "projectId": PROJECT_ID,
                    "repository": PROJECT_REPOSITORY,
                    "branch": PROJECT_BRANCH,
                    "manifestSha256": PROJECT_MANIFEST_SHA256,
                },
                "instructions": {
                    "instructionBundleRevision": INSTRUCTION_BUNDLE_REVISION,
                    "instructionBundleSha256": ATENEA_INSTRUCTION_BUNDLE_SHA256,
                    "platformInstructionSha256": PLATFORM_INSTRUCTION_SHA256,
                    "projectInstructionPath": PROJECT_INSTRUCTION_PATH,
                    "projectInstructionSha256": ATENEA_PROJECT_INSTRUCTION_SHA256,
                },
            }
        if project_id == BEAUTIPS_PROJECT_ID:
            return {
                "config": self.beautips_project_config,
                "runner": self.beautips_project_runner,
                "mirror": None,
                "identity": {
                    "projectId": BEAUTIPS_PROJECT_ID,
                    "repository": BEAUTIPS_PROJECT_REPOSITORY,
                    "branch": BEAUTIPS_PROJECT_BRANCH,
                    "commit": BEAUTIPS_PROJECT_COMMIT,
                    "manifestSha256": BEAUTIPS_PROJECT_MANIFEST_SHA256,
                },
                "instructions": {
                    "instructionBundleRevision": INSTRUCTION_BUNDLE_REVISION,
                    "instructionBundleSha256": BEAUTIPS_INSTRUCTION_BUNDLE_SHA256,
                    "platformInstructionSha256": PLATFORM_INSTRUCTION_SHA256,
                    "projectInstructionPath": PROJECT_INSTRUCTION_PATH,
                    "projectInstructionSha256": BEAUTIPS_PROJECT_INSTRUCTION_SHA256,
                },
            }
        return None

    def _read_project_config(
        self, route: dict[str, Any], require_execution: bool = False
    ) -> dict[str, Any]:
        project_config = route["config"]
        project_runner = route["runner"]
        if project_config is None:
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_disabled", "project workload is disabled")
        try:
            stat = project_config.stat()
            parsed = json.loads(project_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_disabled", "project configuration is unavailable")
        if stat.st_uid != self.project_config_uid or stat.st_mode & 0o022:
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_disabled", "project configuration ownership is unsafe")
        required = {
            "schemaVersion", "selectionEnabled", "executionEnabled",
            "projectId", "repository", "branch",
            "commit", "manifestSha256", "runner", "workspaces",
        }
        exact = {"schemaVersion": PROJECT_CAPABILITY, **route["identity"]}
        accepted_key_sets = {frozenset(required)}
        if route["identity"]["projectId"] == PROJECT_ID:
            accepted_key_sets.add(frozenset(required | {"attachmentRoot"}))
        if (
            not isinstance(parsed, dict)
            or frozenset(parsed) not in accepted_key_sets
            or any(parsed.get(key) != value for key, value in exact.items())
            or (
                "attachmentRoot" in parsed
                and parsed.get("attachmentRoot") != PROJECT_ATTACHMENT_ROOT
            )
            or not isinstance(parsed.get("commit"), str)
            or COMMIT_PATTERN.fullmatch(parsed["commit"]) is None
            or parsed.get("selectionEnabled") is not True
            or not isinstance(parsed.get("executionEnabled"), bool)
            or (require_execution and parsed.get("executionEnabled") is not True)
            or parsed.get("runner") != str(project_runner)
            or not isinstance(parsed.get("workspaces"), dict)
        ):
            raise ProtocolError(HTTPStatus.FORBIDDEN, "project_disabled", "project configuration is not exact")
        return parsed

    def _observe_project_commit(self, route: dict[str, Any]) -> str:
        if route.get("mirror") is None:
            return self._read_project_config(route)["commit"]
        reference = "refs/remotes/origin/" + route["identity"]["branch"]
        try:
            completed = subprocess.run(
                [
                    "git", "--git-dir", str(route["mirror"]),
                    "rev-parse", "--verify", reference + "^{commit}",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror canonical source is unavailable",
            )
        commit = completed.stdout.strip()
        if COMMIT_PATTERN.fullmatch(commit) is None:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_ambiguous",
                "worker mirror canonical source is ambiguous",
            )
        return commit

    def _refresh_project_mirror(self, route: dict[str, Any]) -> None:
        mirror = route.get("mirror")
        if mirror is None:
            return
        if not mirror.is_dir() or mirror.is_symlink():
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror canonical refresh failed closed",
            )
        try:
            configuration = subprocess.run(
                [
                    "git", "--git-dir", str(mirror), "config", "--get-regexp",
                    r"^remote\.origin\.(url|fetch|pushurl)$",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
                check=True,
            )
            expected_configuration = {
                f"remote.origin.url {route['identity']['repository']}",
                "remote.origin.fetch +refs/heads/*:refs/remotes/origin/*",
            }
            if set(configuration.stdout.splitlines()) != expected_configuration:
                raise subprocess.SubprocessError("canonical mirror remote is not exact")
            subprocess.run(
                ["git", "--git-dir", str(mirror), "fetch", "--prune", "origin"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
                timeout=120,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror canonical refresh failed closed",
            )

    def _is_project_commit_ancestor(
        self, route: dict[str, Any], ancestor: str, descendant: str
    ) -> bool:
        mirror = route.get("mirror")
        if (
            mirror is None
            or not mirror.is_dir()
            or mirror.is_symlink()
            or COMMIT_PATTERN.fullmatch(ancestor) is None
            or COMMIT_PATTERN.fullmatch(descendant) is None
        ):
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror source relationship is unavailable",
            )
        try:
            completed = subprocess.run(
                [
                    "git", "--git-dir", str(mirror), "merge-base",
                    "--is-ancestor", ancestor, descendant,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except OSError:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_unavailable",
                "worker mirror source relationship is unavailable",
            ) from None
        if completed.returncode not in {0, 1}:
            raise ProtocolError(
                HTTPStatus.CONFLICT,
                "canonical_source_ambiguous",
                "worker mirror source relationship is ambiguous",
            )
        return completed.returncode == 0

    def _project_selection_enabled(self) -> bool:
        for project_id in (PROJECT_ID, BEAUTIPS_PROJECT_ID):
            route = self._project_route(project_id)
            try:
                self._read_project_config(route)
                if route["runner"] is not None and route["runner"].is_file():
                    return True
            except ProtocolError:
                continue
        return False

    def _project_execution_enabled(self, route: dict[str, Any]) -> bool:
        try:
            self._read_project_config(route, require_execution=True)
            return route["runner"] is not None and route["runner"].is_file()
        except ProtocolError:
            return False

    def _schedule_loop(self) -> None:
        while not self.stop_event.is_set():
            self.wakeup.wait(timeout=0.25)
            self.wakeup.clear()
            with self.lock:
                active_normal = sum(
                    1 for item in self.executions.values()
                    if item["status"] in {"STARTING", "RUNNING"} and item["dispatchId"] in self.threads
                )
                active_heavy = sum(
                    1 for item in self.executions.values()
                    if item["status"] in {"STARTING", "RUNNING"}
                    and item["dispatchId"] in self.threads
                    and item["workloadClass"] == "HEAVY"
                )
                candidates = sorted(
                    (
                        item for item in self.executions.values()
                        if item["status"] in {"QUEUED", "RECONCILING", "CANCELLING"}
                        and item["dispatchId"] not in self.threads
                    ),
                    key=lambda item: (item["createdAt"], item["dispatchId"]),
                )
                for execution in candidates:
                    if execution["cancelRequested"]:
                        self._finish_cancelled(execution)
                        continue
                    if execution["reconcileRequired"] and execution["workload"]["kind"] in {
                        PROJECT_CAPABILITY, PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY,
                        PROJECT_V4_CAPABILITY,
                    }:
                        execution["status"] = "FAILED"
                        execution["statusReason"] = (
                            "Restart reconciliation refused to duplicate an uncertain Codex turn"
                        )
                        execution["finishedAt"] = utc_now()
                        execution["revision"] += 1
                        execution["updatedAt"] = execution["finishedAt"]
                        self._append_progress(
                            execution,
                            "FAILED",
                            "Execution failed closed during reconciliation.",
                        )
                        self._persist()
                        continue
                    if active_normal >= self.normal_capacity:
                        break
                    if execution["workloadClass"] == "HEAVY" and active_heavy >= self.heavy_capacity:
                        continue
                    execution["status"] = "STARTING"
                    execution["statusReason"] = "Worker permit admitted"
                    execution["revision"] += 1
                    execution["updatedAt"] = utc_now()
                    self._append_progress(
                        execution,
                        "PREPARING_WORKSPACE",
                        "Preparing the accepted workspace.",
                    )
                    self._persist()
                    thread = threading.Thread(
                        target=self._execute,
                        args=(execution["dispatchId"],),
                        name=f"agent-run-{execution['executionId']}",
                        daemon=True,
                    )
                    self.threads[execution["dispatchId"]] = thread
                    active_normal += 1
                    if execution["workloadClass"] == "HEAVY":
                        active_heavy += 1
                    thread.start()

    def _execute(self, dispatch_id: str) -> None:
        try:
            with self.lock:
                execution = self.executions[dispatch_id]
                if execution["cancelRequested"]:
                    self._finish_cancelled(execution)
                    return
                execution["status"] = "RUNNING"
                execution["statusReason"] = (
                    "Exact project Codex execution running"
                    if execution["workload"]["kind"] in {
                        PROJECT_CAPABILITY, PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY,
                        PROJECT_V4_CAPABILITY,
                    }
                    else "Synthetic execution running"
                )
                execution["startedAt"] = execution["startedAt"] or utc_now()
                execution["revision"] += 1
                execution["updatedAt"] = utc_now()
                self._append_progress(
                    execution,
                    "CODEX_STARTED",
                    "Codex started the accepted turn.",
                )
                self._persist()
                if execution["workload"]["kind"] in {
                    PROJECT_CAPABILITY, PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY,
                    PROJECT_V4_CAPABILITY,
                }:
                    request = {
                        "dispatchId": execution["dispatchId"],
                        "executionId": execution["executionId"],
                        "sessionId": execution["sessionId"],
                        "workspaceIdentity": execution["workspaceIdentity"],
                        "workload": execution["workload"],
                    }
                    if execution["workload"]["kind"] == PROJECT_V4_CAPABILITY:
                        request["changeOwnership"] = execution["changeOwnership"]
                else:
                    request = None
                    duration = execution["workload"]["durationMs"] / 1000
                    steps = execution["workload"]["steps"]
                    completed_steps = min(steps, int(execution["progress"] * steps / 100))

            if request is not None:
                self._execute_project(dispatch_id, request)
                return
            delay = duration / steps
            for step in range(completed_steps + 1, steps + 1):
                if self.stop_event.wait(delay):
                    return
                with self.lock:
                    execution = self.executions[dispatch_id]
                    if execution["cancelRequested"]:
                        self._finish_cancelled(execution)
                        return
                    execution["progress"] = int(step * 100 / steps)
                    execution["revision"] += 1
                    execution["updatedAt"] = utc_now()
                    self._persist()

            with self.lock:
                execution = self.executions[dispatch_id]
                workspace_digest = hashlib.sha256(execution["workspaceIdentity"].encode()).hexdigest()[:16]
                execution["status"] = "SUCCEEDED"
                execution["statusReason"] = "Synthetic execution completed"
                execution["result"] = {
                    "threadId": f"synthetic-thread-{workspace_digest}",
                    "turnId": execution["executionId"],
                    "finalAnswer": f"Synthetic remote response: {execution['workload']['message']}",
                    "outputSummary": "synthetic-routing-v1 completed",
                }
                execution["finishedAt"] = utc_now()
                execution["revision"] += 1
                execution["updatedAt"] = execution["finishedAt"]
                self._append_progress(execution, "COMPLETED", "Execution completed.")
                self._persist()
        finally:
            with self.lock:
                self.threads.pop(dispatch_id, None)
                self.wakeup.set()

    def _execute_project(self, dispatch_id: str, request: dict[str, Any]) -> None:
        if request["workload"]["kind"] == PROJECT_V4_CAPABILITY:
            try:
                self._validate_change_project_shape(request, request["workload"])
                self._validate_change_project_ownership(request, request["workload"])
            except ProtocolError:
                self._finish_project(
                    dispatch_id,
                    "FAILED",
                    "Change workspace ownership changed before execution",
                    None,
                )
                return
        route = self._project_route(request["workload"]["projectId"])
        if route is None or route["runner"] is None or route["config"] is None:
            self._finish_project(
                dispatch_id, "FAILED", "Project runner rejected or failed the exact execution", None
            )
            return
        command = [
            *self.privilege_command,
            str(route["runner"]),
            "--config",
            str(route["config"]),
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        with self.lock:
            self.processes[dispatch_id] = process
            execution = self.executions[dispatch_id]
            execution["progress"] = 10
            execution["revision"] += 1
            execution["updatedAt"] = utc_now()
            self._persist()
        try:
            stdout, stderr = process.communicate(
                json.dumps(request, sort_keys=True, separators=(",", ":")),
                timeout=self.project_timeout,
            )
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
            self._finish_project(dispatch_id, "FAILED", "Bounded project execution timed out", None)
            return
        finally:
            with self.lock:
                self.processes.pop(dispatch_id, None)
        with self.lock:
            cancelled = self.executions[dispatch_id]["cancelRequested"]
        if cancelled:
            with self.lock:
                self._finish_cancelled(self.executions[dispatch_id])
            return
        if process.returncode != 0:
            reason = "Project runner rejected or failed the exact execution"
            allowed_runner_reasons = (
                "project configuration rejected",
                "workspace ownership rejected",
                "worktree fingerprint rejected",
                "Codex execution failed: filesystem boundary",
                "Codex execution failed: authentication unavailable",
                "Codex execution failed: CLI contract",
                "Codex execution failed: network unavailable",
                "Codex execution failed: thread persistence unavailable",
                "attachment ownership rejected",
                "attachment materialization rejected",
                "Codex execution failed: unclassified",
                "Project runner internal exception: AttributeError",
                "Project runner internal exception: FileNotFoundError",
                "Project runner internal exception: OSError",
                "Project runner internal exception: PermissionError",
                "Project runner internal exception: TypeError",
                "Project runner internal exception: UnboundLocalError",
                "Project runner internal exception: ValueError",
                "Project runner internal exception: Other",
            )
            sanitized_runner_reason = next(
                (candidate for candidate in allowed_runner_reasons if candidate in stderr),
                None,
            )
            if sanitized_runner_reason is None:
                if "Traceback (most recent call last)" in stderr:
                    sanitized_runner_reason = "Project runner internal exception"
                elif "sudo:" in stderr.lower():
                    sanitized_runner_reason = "Project runner privilege boundary failed"
                elif not stderr.strip():
                    sanitized_runner_reason = "Project runner failed without diagnostic output"
            if sanitized_runner_reason is not None:
                reason = sanitized_runner_reason
            self._finish_project(dispatch_id, "FAILED", reason, None)
            return
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self._finish_project(dispatch_id, "FAILED", "Project runner returned invalid output", None)
            return
        workload = request["workload"]
        required_result = {"threadId", "turnId", "finalAnswer", "outputSummary"}
        if workload["kind"] in {
            PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY, PROJECT_V4_CAPABILITY,
        }:
            required_result |= {
                "modelId", "reasoningEffort", "catalogRevision", "codexVersion",
                "progressEvents",
            }
        progress_events = result.get("progressEvents", []) if isinstance(result, dict) else []
        string_result = {
            key: value for key, value in result.items() if key != "progressEvents"
        } if isinstance(result, dict) else {}
        if (
            not isinstance(result, dict)
            or set(result) != required_result
            or not all(isinstance(value, str) and value for value in string_result.values())
            or result.get("outputSummary") != workload["kind"] + " completed"
            or (
                workload["kind"] in {
                    PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY, PROJECT_V4_CAPABILITY,
                }
                and not isinstance(progress_events, list)
            )
            or (
                workload["kind"] in {
                    PROJECT_V2_CAPABILITY, PROJECT_V3_CAPABILITY, PROJECT_V4_CAPABILITY,
                }
                and any(result[key] != workload[key] for key in (
                    "modelId", "reasoningEffort", "catalogRevision", "codexVersion"
                ))
            )
        ):
            self._finish_project(dispatch_id, "FAILED", "Project runner returned invalid output", None)
            return
        result.pop("progressEvents", None)
        with self.lock:
            execution = self.executions[dispatch_id]
            self._append_runner_progress(execution, progress_events)
            self._append_progress(execution, "FINALIZING", "Finalizing the Codex turn.")
            self._persist()
        self._finish_project(dispatch_id, "SUCCEEDED", "Exact project Codex execution completed", result)

    def _finish_project(
        self, dispatch_id: str, status: str, reason: str, result: dict[str, str] | None
    ) -> None:
        with self.lock:
            execution = self.executions[dispatch_id]
            execution["status"] = status
            execution["statusReason"] = reason
            execution["result"] = result
            execution["progress"] = 100 if status == "SUCCEEDED" else execution["progress"]
            execution["finishedAt"] = utc_now()
            execution["revision"] += 1
            execution["updatedAt"] = execution["finishedAt"]
            self._append_progress(
                execution,
                "COMPLETED" if status == "SUCCEEDED" else "FAILED",
                "Execution completed." if status == "SUCCEEDED" else "Execution failed.",
            )
            self._persist()

    def _finish_cancelled(self, execution: dict[str, Any]) -> None:
        execution["status"] = "CANCELLED"
        execution["statusReason"] = "Exact execution cancelled"
        execution["finishedAt"] = utc_now()
        execution["revision"] += 1
        execution["updatedAt"] = execution["finishedAt"]
        self._append_progress(execution, "CANCELLED", "Execution cancelled.")
        self._persist()

    def _public(self, execution: dict[str, Any]) -> dict[str, Any]:
        return {
            key: execution.get(key)
            for key in (
                "dispatchId", "executionId", "sessionId", "workspaceIdentity",
                "workloadClass", "leaseGeneration", "status", "statusReason",
                "revision", "progress", "createdAt", "updatedAt", "startedAt",
                "finishedAt", "result",
                "progressEvents",
            )
        }


class AgentRunServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: WorkerState, token: str):
        self.state = state
        self.token = token
        super().__init__(address, AgentRunHandler)


class AgentRunHandler(BaseHTTPRequestHandler):
    server: AgentRunServer

    def log_message(self, _message: str, *_args: Any) -> None:
        print(json.dumps({"at": utc_now(), "event": "http_request"}), flush=True)

    def do_GET(self) -> None:
        try:
            self._authenticate()
            path = urlparse(self.path).path
            if path == "/v1/health":
                self._write(HTTPStatus.OK, self.server.state.health())
                return
            if path == "/v1/codex/catalog":
                self._write(HTTPStatus.OK, self.server.state.codex_catalog())
                return
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["v1", "executions"]:
                self._write(HTTPStatus.OK, self.server.state.get(parts[2]))
                return
            raise ProtocolError(HTTPStatus.NOT_FOUND, "not_found", "route does not exist")
        except ProtocolError as error:
            self._write_error(error)

    def do_POST(self) -> None:
        try:
            self._authenticate()
            body = self._body()
            path = urlparse(self.path).path
            if path == "/v1/executions":
                execution, created = self.server.state.create(body)
                self._write(HTTPStatus.CREATED if created else HTTPStatus.OK, execution)
                return
            if path.startswith(DEVELOPMENT_CHANGE_WORKSPACE_PATH_PREFIX):
                operation = path.removeprefix(DEVELOPMENT_CHANGE_WORKSPACE_PATH_PREFIX)
                if operation not in {"provision", "inspect", "reconcile"}:
                    raise ProtocolError(
                        HTTPStatus.NOT_FOUND, "not_found", "route does not exist"
                    )
                self._write(
                    HTTPStatus.OK,
                    self.server.state.execute_development_change_workspace(
                        body, operation
                    ),
                )
                return
            if path == "/v1/project-workspaces/ensure":
                self._write(HTTPStatus.OK, self.server.state.ensure_workspace(body))
                return
            if path == WORKSPACE_RELEASE_PATH:
                self._write(HTTPStatus.OK, self.server.state.release_workspace(body))
                return
            if path == WORKSPACE_UNACTIVATED_RELEASE_PATH:
                self._write(
                    HTTPStatus.OK,
                    self.server.state.release_unactivated_workspace(body),
                )
                return
            if path == WORKSPACE_RELEASE_PREFLIGHT_PATH:
                self._write(
                    HTTPStatus.OK,
                    self.server.state.diagnose_workspace_release_preflight(body),
                )
                return
            if path == WORKSPACE_CAPACITY_OWNER_PATH:
                self._write(
                    HTTPStatus.OK,
                    self.server.state.diagnose_workspace_capacity_owner(body),
                )
                return
            if path == WORKSPACE_READINESS_PATH:
                self._write(
                    HTTPStatus.OK,
                    self.server.state.diagnose_workspace_readiness(body),
                )
                return
            if path == "/v1/project-workspaces/draft-fingerprint":
                self._write(HTTPStatus.OK, self.server.state.fingerprint_retained_draft(body))
                return
            if path == "/v1/project-workspaces/source-tree-fingerprint":
                self._write(HTTPStatus.OK, self.server.state.fingerprint_source_tree(body))
                return
            if path == "/v1/project-workspaces/validations":
                self._write(HTTPStatus.OK, self.server.state.run_validation(body))
                return
            if path == "/v1/project-workspaces/repository-roles/ensure":
                self._write(HTTPStatus.OK, self.server.state.ensure_repository_roles(body))
                return
            if path == "/v1/codex/update/stage":
                self._write(HTTPStatus.OK, self.server.state.stage_codex_update(body))
                return
            if path == "/v1/codex/update/activate":
                self._write(HTTPStatus.OK, self.server.state.activate_codex_update(body))
                return
            if path == "/v1/codex/update/rollback":
                self._write(HTTPStatus.OK, self.server.state.rollback_codex_update(body))
                return
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["v1", "executions"]:
                if parts[3] == "lease":
                    self._write(HTTPStatus.OK, self.server.state.renew(parts[2], body))
                    return
                if parts[3] == "cancel":
                    self._write(HTTPStatus.OK, self.server.state.cancel(parts[2], body))
                    return
                if parts[3] == "cancel-exact":
                    self._write(HTTPStatus.OK, self.server.state.cancel_exact(parts[2], body))
                    return
                if parts[3] == "reconcile":
                    self._write(
                        HTTPStatus.OK,
                        self.server.state.inspect_reconciliation(parts[2], body),
                    )
                    return
                if parts[3] == "doctor":
                    self._write(HTTPStatus.OK, self.server.state.doctor(parts[2], body))
                    return
            raise ProtocolError(HTTPStatus.NOT_FOUND, "not_found", "route does not exist")
        except ProtocolError as error:
            self._write_error(error)

    def _authenticate(self) -> None:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        if not hmac.compare_digest(supplied, expected):
            raise ProtocolError(HTTPStatus.UNAUTHORIZED, "unauthorized", "valid worker credential required")

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_length", "Content-Length is invalid")
        if length < 2 or length > 65_536:
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_length", "request body size is invalid")
        try:
            parsed = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_json", "request body is not valid JSON")
        if not isinstance(parsed, dict):
            raise ProtocolError(HTTPStatus.BAD_REQUEST, "invalid_json", "request body must be an object")
        return parsed

    def _write_error(self, error: ProtocolError) -> None:
        self._write(error.status, error.safe_error)

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def read_token(path: Path) -> str:
    stat = path.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o037:
        raise RuntimeError("token file must be root-owned, group-readable and otherwise private")
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise RuntimeError("token must contain at least 32 characters")
    return token


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--normal-capacity", type=int, default=4)
    parser.add_argument("--heavy-capacity", type=int, default=2)
    parser.add_argument("--project-config", type=Path)
    parser.add_argument("--project-readiness-enabled", action="store_true")
    parser.add_argument("--unactivated-release-enabled", action="store_true")
    parser.add_argument("--project-runner", type=Path)
    parser.add_argument(
        "--project-workspace-activator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/atenea-workspace-activation-v1.sh"),
    )
    parser.add_argument(
        "--project-workspace-releaser",
        type=Path,
        default=Path("/usr/local/libexec/atenea/atenea-workspace-release-v1.py"),
    )
    parser.add_argument("--beautips-project-config", type=Path)
    parser.add_argument("--beautips-project-runner", type=Path)
    parser.add_argument(
        "--beautips-workspace-activator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/beautips-workspace-activation-v1.sh"),
    )
    parser.add_argument(
        "--project-validation-mediator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/atenea-validation-v1.sh"),
    )
    parser.add_argument(
        "--repository-role-mediator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/atenea-multi-repository-v1.sh"),
    )
    parser.add_argument(
        "--codex-update-mediator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/codex-release-stage-v1.py"),
    )
    parser.add_argument(
        "--codex-update-registry",
        type=Path,
        default=Path("/etc/atenea-worker/codex-release-stage-v1.json"),
    )
    parser.add_argument(
        "--codex-activate-mediator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/codex-release-activate-v1.py"),
    )
    parser.add_argument(
        "--codex-rollback-mediator",
        type=Path,
        default=Path("/usr/local/libexec/atenea/codex-release-activate-v1.py"),
    )
    parser.add_argument(
        "--codex-restart-scheduler",
        type=Path,
        default=Path("/usr/local/libexec/atenea/codex-release-restart-v1.sh"),
    )
    parser.add_argument(
        "--codex-release-root",
        type=Path,
        default=Path("/srv/atenea/worker/codex-releases-v1"),
    )
    parser.add_argument(
        "--development-change-workspace-mediator",
        type=Path,
        default=Path(
            "/usr/local/libexec/atenea/development-change-workspace-v1.py"
        ),
    )
    parser.add_argument("--project-timeout", type=int, default=1800)
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        raise SystemExit("port is outside valid range")
    if not (1 <= args.heavy_capacity <= args.normal_capacity <= 64):
        raise SystemExit("capacity is outside policy")

    if not (30 <= args.project_timeout <= 3600):
        raise SystemExit("project timeout is outside policy")
    state = WorkerState(
        args.state_dir,
        args.worker_id,
        args.normal_capacity,
        args.heavy_capacity,
        args.project_config,
        args.project_runner,
        args.project_timeout,
        project_workspace_activator=args.project_workspace_activator,
        project_workspace_releaser=args.project_workspace_releaser,
        beautips_project_config=args.beautips_project_config,
        beautips_project_runner=args.beautips_project_runner,
        beautips_workspace_activator=args.beautips_workspace_activator,
        project_validation_mediator=args.project_validation_mediator,
        repository_role_mediator=args.repository_role_mediator,
        codex_update_mediator=args.codex_update_mediator,
        codex_activate_mediator=args.codex_activate_mediator,
        codex_rollback_mediator=args.codex_rollback_mediator,
        codex_restart_scheduler=args.codex_restart_scheduler,
        codex_update_registry=args.codex_update_registry,
        codex_release_root=args.codex_release_root,
        reconcile_materializations_on_start=True,
        project_readiness_enabled=args.project_readiness_enabled,
        unactivated_release_enabled=args.unactivated_release_enabled,
        development_change_workspace_mediator=(
            args.development_change_workspace_mediator
        ),
    )
    server = AgentRunServer((args.bind, args.port), state, read_token(args.token_file))
    state.start()

    def shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        state.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
