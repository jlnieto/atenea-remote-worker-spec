#!/usr/bin/env python3
"""Canonical fail-closed development-change workspace mediator for AX42."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
PROTOCOL_VERSION = "development-change-workspace/v1"
PUBLICATION_PROTOCOL_VERSION = "development-change-branch-publication/v1"
WORKER_ID = "ax42-01"
PROJECT_ID = "atenea"
REPOSITORY = "https://github.com/jlnieto/atenea.git"
PUBLICATION_REPOSITORY = "git@github.com:jlnieto/atenea.git"
REPOSITORY_BRANCH = "main"
PUBLICATION_CREDENTIAL_NAME = "atenea-publication-deploy-key"
PUBLICATION_CREDENTIALS_DIRECTORY = Path(
    "/run/credentials/atenea-agent-run-worker-v1.service"
)
PUBLICATION_RUNTIME_DIRECTORY = Path("/run/atenea-publication")
PUBLICATION_KNOWN_HOSTS = Path("/etc/atenea-worker/github-known-hosts")
MIRROR = Path("/srv/atenea/repositories/atenea.git")
WORKSPACE_PARENT = Path("/srv/atenea/workspaces/changes")
LOCK_FILE = Path("/srv/atenea/worker/agent-runs-v1/development-change-workspace-v1.lock")
GIT_TIMEOUT_SECONDS = 30
MAX_GIT_OUTPUT_BYTES = 64 * 1024 * 1024

SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
OPERATIONS = {"PROVISION", "INSPECT", "RECONCILE"}
PUBLICATION_OPERATION = "PUBLISH"
SOURCE_UPDATE_PROTOCOL = "development-change-source-update/v1"
SOURCE_UPDATE_OPERATIONS = {"PREPARE", "INSPECT", "RECONCILE"}
SOURCE_FINALIZATION_PROTOCOL = "development-change-source-finalization/v1"
SOURCE_FINALIZATION_OPERATIONS = {"FINALIZE", "INSPECT"}
REQUEST_KEYS = {
    "schemaVersion",
    "protocolVersion",
    "effect",
    "operationId",
    "idempotencyKey",
    "operation",
    "predecessorOperationId",
    "changeKey",
    "databaseProjectId",
    "projectId",
    "repository",
    "repositoryBranch",
    "baseCommit",
    "sourceCommit",
    "workspaceBranch",
    "workspaceIdentity",
    "workerId",
    "sourceRevision",
    "sourceFingerprintSha256",
    "requestFingerprintSha256",
}
RECORD_KEYS = {
    "schemaVersion",
    "protocolVersion",
    "changeKey",
    "databaseProjectId",
    "projectId",
    "baseCommit",
    "workspaceBranch",
    "workspaceIdentity",
    "workerId",
}
LEGACY_RECORD_KEYS = RECORD_KEYS | {
    "repository",
    "repositoryBranch",
    "initialSourceFingerprintSha256",
    "recordSha256",
}
PUBLICATION_REQUEST_KEYS = {
    "schemaVersion",
    "protocolVersion",
    "effect",
    "operationId",
    "idempotencyKey",
    "operation",
    "changeKey",
    "databaseProjectId",
    "projectId",
    "repository",
    "repositoryBranch",
    "baseCommit",
    "sourceCommit",
    "workspaceBranch",
    "workspaceIdentity",
    "workerId",
    "sourceRevision",
    "sourceFingerprintSha256",
    "requestFingerprintSha256",
}
PUBLICATION_RECORD_KEYS = PUBLICATION_REQUEST_KEYS | {
    "state",
    "originalHeadSha",
    "expectedTreeSha",
    "publishedHeadSha",
    "remoteDisposition",
    "publicationReceiptSha256",
    "recordSha256",
}
SOURCE_UPDATE_REQUEST_KEYS = PUBLICATION_REQUEST_KEYS | {
    "targetMainCommit", "publicationReceiptSha256",
}
SOURCE_UPDATE_RECORD_KEYS = SOURCE_UPDATE_REQUEST_KEYS | {
    "state", "intentSha256", "ownerRecordSha256", "preparedTreeSha",
    "conflictFiles", "preparedFingerprintSha256", "recordSha256",
}
SOURCE_FINALIZATION_REQUEST_KEYS = PUBLICATION_REQUEST_KEYS | {
    "targetMainCommit", "publicationReceiptSha256", "preparationOperationId",
    "preparationReceiptSha256", "validationProjectionSha256",
}
SOURCE_FINALIZATION_RECORD_KEYS = SOURCE_FINALIZATION_REQUEST_KEYS | {
    "state", "intentSha256", "ownerRecordSha256", "expectedTreeSha", "publishedHeadSha",
    "finalizationReceiptSha256", "recordSha256",
}


class ContractError(Exception):
    """A sanitized fail-closed contract error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON field")
        result[key] = value
    return result


def strict_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw, object_pairs_hook=strict_object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ContractError) as error:
        raise ContractError("invalid JSON") from error
    if not isinstance(parsed, dict):
        raise ContractError("request must be an object")
    return parsed


def canonical_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise ContractError("invalid UUID")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise ContractError("invalid UUID") from error
    if str(parsed) != value:
        raise ContractError("UUID is not canonical")
    return value


def regular_directory(path: Path, expected_uid: int | None = None) -> os.stat_result:
    try:
        observed = path.lstat()
    except OSError as error:
        raise ContractError("required directory is unavailable") from error
    if not stat.S_ISDIR(observed.st_mode) or path.is_symlink():
        raise ContractError("required directory is unsafe")
    if expected_uid is not None and observed.st_uid != expected_uid:
        raise ContractError("required directory ownership is unsafe")
    return observed


def validate_request(value: dict[str, Any], operation: str) -> dict[str, Any]:
    if set(value) != REQUEST_KEYS or operation not in OPERATIONS:
        raise ContractError("request fields are invalid")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise ContractError("schema version is invalid")
    if value.get("protocolVersion") != PROTOCOL_VERSION:
        raise ContractError("protocol version is invalid")
    if value.get("operation") != operation:
        raise ContractError("operation is invalid")
    expected_effect = "CREATE_IF_ABSENT_EXACT" if operation == "PROVISION" else "OBSERVE_ONLY"
    if value.get("effect") != expected_effect:
        raise ContractError("effect is invalid")

    operation_id = canonical_uuid(value.get("operationId"))
    idempotency_key = canonical_uuid(value.get("idempotencyKey"))
    change_key = canonical_uuid(value.get("changeKey"))
    predecessor = value.get("predecessorOperationId")
    if operation == "RECONCILE":
        predecessor = canonical_uuid(predecessor)
    elif predecessor is not None:
        raise ContractError("predecessor is invalid")
    if operation == "RECONCILE" and predecessor == operation_id:
        raise ContractError("predecessor cycle is invalid")

    database_project_id = value.get("databaseProjectId")
    source_revision = value.get("sourceRevision")
    if (
        not isinstance(database_project_id, int)
        or isinstance(database_project_id, bool)
        or database_project_id <= 0
        or not isinstance(source_revision, int)
        or isinstance(source_revision, bool)
        or source_revision < 0
    ):
        raise ContractError("numeric identity is invalid")
    if (
        value.get("projectId") != PROJECT_ID
        or value.get("repository") != REPOSITORY
        or value.get("repositoryBranch") != REPOSITORY_BRANCH
        or value.get("workerId") != WORKER_ID
        or value.get("workspaceBranch") != f"atenea/change-{change_key}"
        or value.get("workspaceIdentity") != f"remote:{WORKER_ID}:change:{change_key}"
    ):
        raise ContractError("server-owned identity is invalid")
    if not GIT_COMMIT.fullmatch(str(value.get("baseCommit", ""))):
        raise ContractError("base commit is invalid")
    if not GIT_COMMIT.fullmatch(str(value.get("sourceCommit", ""))):
        raise ContractError("source commit is invalid")
    source_fingerprint = value.get("sourceFingerprintSha256")
    if source_fingerprint is not None and not SHA256.fullmatch(str(source_fingerprint)):
        raise ContractError("source fingerprint is invalid")
    if not SHA256.fullmatch(str(value.get("requestFingerprintSha256", ""))):
        raise ContractError("request fingerprint is invalid")

    fingerprint_input = dict(value)
    supplied_fingerprint = fingerprint_input.pop("requestFingerprintSha256")
    if canonical_sha256(fingerprint_input) != supplied_fingerprint:
        raise ContractError("request fingerprint does not match")
    return {
        **value,
        "operationId": operation_id,
        "idempotencyKey": idempotency_key,
        "changeKey": change_key,
        "predecessorOperationId": predecessor,
    }


def validate_publication_request(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != PUBLICATION_REQUEST_KEYS:
        raise ContractError("publication request fields are invalid")
    if (
        value.get("schemaVersion") != SCHEMA_VERSION
        or value.get("protocolVersion") != PUBLICATION_PROTOCOL_VERSION
        or value.get("effect") != "PUBLISH_EXACT_CHANGE_BRANCH"
        or value.get("operation") != PUBLICATION_OPERATION
    ):
        raise ContractError("publication contract identity is invalid")
    operation_id = canonical_uuid(value.get("operationId"))
    idempotency_key = canonical_uuid(value.get("idempotencyKey"))
    change_key = canonical_uuid(value.get("changeKey"))
    database_project_id = value.get("databaseProjectId")
    source_revision = value.get("sourceRevision")
    if (
        not isinstance(database_project_id, int)
        or isinstance(database_project_id, bool)
        or database_project_id <= 0
        or not isinstance(source_revision, int)
        or isinstance(source_revision, bool)
        or source_revision < 0
    ):
        raise ContractError("publication numeric identity is invalid")
    if (
        value.get("projectId") != PROJECT_ID
        or value.get("repository") != REPOSITORY
        or value.get("repositoryBranch") != REPOSITORY_BRANCH
        or value.get("workerId") != WORKER_ID
        or value.get("workspaceBranch") != f"atenea/change-{change_key}"
        or value.get("workspaceIdentity") != f"remote:{WORKER_ID}:change:{change_key}"
    ):
        raise ContractError("publication server-owned identity is invalid")
    for field in ("baseCommit", "sourceCommit"):
        if not GIT_COMMIT.fullmatch(str(value.get(field, ""))):
            raise ContractError("publication Git identity is invalid")
    source_fingerprint = value.get("sourceFingerprintSha256")
    if source_fingerprint is not None and not SHA256.fullmatch(str(source_fingerprint)):
        raise ContractError("publication fingerprint is invalid")
    if not SHA256.fullmatch(str(value.get("requestFingerprintSha256", ""))):
        raise ContractError("publication fingerprint is invalid")
    fingerprint_input = dict(value)
    supplied_fingerprint = fingerprint_input.pop("requestFingerprintSha256")
    if canonical_sha256(fingerprint_input) != supplied_fingerprint:
        raise ContractError("publication request fingerprint does not match")
    return {
        **value,
        "operationId": operation_id,
        "idempotencyKey": idempotency_key,
        "changeKey": change_key,
    }


def validate_source_update_request(value: dict[str, Any], operation: str) -> dict[str, Any]:
    effects = {"PREPARE": "PREPARE_PINNED_MAIN", "INSPECT": "OBSERVE_ONLY",
               "RECONCILE": "OBSERVE_OR_RESUME_EXACT"}
    if (set(value) != SOURCE_UPDATE_REQUEST_KEYS
            or operation not in SOURCE_UPDATE_OPERATIONS
            or type(value.get("schemaVersion")) is not int
            or value.get("protocolVersion") != SOURCE_UPDATE_PROTOCOL
            or value.get("operation") != operation
            or value.get("effect") != effects[operation]
            or value.get("sourceFingerprintSha256") is not None
            or any(not isinstance(value.get(field), str) for field in (
                "baseCommit", "sourceCommit", "targetMainCommit", "publicationReceiptSha256", "requestFingerprintSha256"))
            or not GIT_COMMIT.fullmatch(str(value.get("targetMainCommit")))
            or not SHA256.fullmatch(str(value.get("publicationReceiptSha256")))):
        raise ContractError("source update request is invalid")
    # Reuse the closed publication identities, not its effects or credentials.
    publication = {key: value[key] for key in PUBLICATION_REQUEST_KEYS}
    publication.update(protocolVersion=PUBLICATION_PROTOCOL_VERSION,
                       effect="PUBLISH_EXACT_CHANGE_BRANCH", operation="PUBLISH")
    publication["requestFingerprintSha256"] = canonical_sha256({
        key: item for key, item in publication.items() if key != "requestFingerprintSha256"})
    validate_publication_request(publication)
    if (isinstance(value["schemaVersion"], bool)
            or canonical_sha256({key: item for key, item in value.items()
                                 if key != "requestFingerprintSha256"})
            != value["requestFingerprintSha256"]):
        raise ContractError("source update fingerprint is invalid")
    return dict(value)


def source_update_intent(request: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in request.items()
                             if key not in {"operation", "effect", "requestFingerprintSha256"}})


def validate_source_finalization_request(value: dict[str, Any], operation: str) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != SOURCE_FINALIZATION_REQUEST_KEYS
            or operation not in SOURCE_FINALIZATION_OPERATIONS or value.get("operation") != operation
            or value.get("protocolVersion") != SOURCE_FINALIZATION_PROTOCOL
            or value.get("effect") != ("FINALIZE_VALIDATED_SOURCE" if operation == "FINALIZE" else "OBSERVE_ONLY")
            or any(not isinstance(value.get(key), str) or not SHA256.fullmatch(value[key]) for key in
                   ("publicationReceiptSha256", "preparationReceiptSha256", "validationProjectionSha256"))
            or not isinstance(value.get("targetMainCommit"), str)
            or not GIT_COMMIT.fullmatch(value["targetMainCommit"])
            or canonical_uuid(value.get("preparationOperationId")) != value.get("preparationOperationId")
            or isinstance(value.get("schemaVersion"), bool)):
        raise ContractError("source finalization request is invalid")
    publication = {key: value[key] for key in PUBLICATION_REQUEST_KEYS}
    publication.update(protocolVersion=PUBLICATION_PROTOCOL_VERSION, operation="PUBLISH", effect="PUBLISH_EXACT_CHANGE_BRANCH")
    # The publication validator is the authority for all fixed owner fields.
    publication["requestFingerprintSha256"] = canonical_sha256({key: item for key, item in publication.items()
                                                               if key != "requestFingerprintSha256"})
    validate_publication_request(publication)
    if value["requestFingerprintSha256"] != canonical_sha256({key: item for key, item in value.items()
                                                               if key != "requestFingerprintSha256"}):
        raise ContractError("source finalization request is invalid")
    return dict(value)


def approved_validation_commit(root: Path, owner: dict[str, Any], uid: int, gid: int) -> str:
    """Read-only source authority; the immutable creation base is never replaced."""
    path = root / "source-update-v1.json"
    if not path.exists() and not path.is_symlink():
        return owner["baseCommit"]
    metadata = regular_directory(root, uid)
    if metadata.st_gid != gid or stat.S_IMODE(metadata.st_mode) not in {0o700, 0o770}:
        raise ContractError("validation source authority root is unsafe")
    def sealed(file: Path, keys: set[str]) -> dict[str, Any]:
        observed = file.lstat()
        if (not stat.S_ISREG(observed.st_mode) or observed.st_uid != uid or observed.st_gid != gid
                or stat.S_IMODE(observed.st_mode) != 0o600 or observed.st_nlink != 1 or observed.st_size > 65536):
            raise ContractError("validation source authority record is unsafe")
        record = strict_json(file.read_bytes())
        if (set(record) != keys or record["recordSha256"] != canonical_sha256(
                {key: item for key, item in record.items() if key != "recordSha256"})):
            raise ContractError("validation source authority seal is invalid")
        return record
    record = sealed(path, SOURCE_UPDATE_RECORD_KEYS)
    request = {key: record[key] for key in SOURCE_UPDATE_REQUEST_KEYS}
    validate_source_update_request(request, "PREPARE")
    identity = ("changeKey", "databaseProjectId", "projectId", "baseCommit", "workspaceBranch", "workspaceIdentity", "workerId")
    if (any(owner.get(key) != record[key] for key in identity)
            or record["ownerRecordSha256"] != canonical_sha256(owner)
            or record["intentSha256"] != source_update_intent(request)
            or record["state"] not in {"NEEDS_RESOLUTION", "READY_TO_FINALIZE"}
            or not GIT_COMMIT.fullmatch(str(record["preparedTreeSha"]))):
        raise ContractError("validation source preparation identity is invalid")
    publication = sealed(root / "branch-publication-v1.json", PUBLICATION_RECORD_KEYS)
    if (publication["state"] != "PUBLISHED" or any(publication.get(key) != record[key] for key in identity)
            or publication["publishedHeadSha"] != record["sourceCommit"]
            or publication["publicationReceiptSha256"] != record["publicationReceiptSha256"]
            or publication["sourceRevision"] != record["sourceRevision"]):
        raise ContractError("validation source predecessor publication is invalid")
    return record["sourceCommit"]


class WorkspaceMediator:
    def __init__(
        self,
        mirror: Path = MIRROR,
        workspace_parent: Path = WORKSPACE_PARENT,
        lock_file: Path = LOCK_FILE,
        *,
        test_mode: bool = False,
        publication_remote: str = REPOSITORY,
        publication_transport: str = PUBLICATION_REPOSITORY,
        publication_known_hosts: Path = PUBLICATION_KNOWN_HOSTS,
        publication_runtime_directory: Path = PUBLICATION_RUNTIME_DIRECTORY,
    ) -> None:
        self.mirror = Path(mirror)
        self.workspace_parent = Path(workspace_parent)
        self.lock_file = Path(lock_file)
        self.publication_remote = publication_remote
        self.publication_transport = publication_transport
        self.publication_known_hosts = Path(publication_known_hosts)
        self.publication_runtime_directory = Path(publication_runtime_directory)
        if not test_mode and (
            self.mirror != MIRROR
            or self.workspace_parent != WORKSPACE_PARENT
            or self.lock_file != LOCK_FILE
            or self.publication_remote != REPOSITORY
            or self.publication_transport != PUBLICATION_REPOSITORY
            or self.publication_known_hosts != PUBLICATION_KNOWN_HOSTS
            or self.publication_runtime_directory != PUBLICATION_RUNTIME_DIRECTORY
        ):
            raise ContractError("production roots are fixed")
        self.test_mode = test_mode

    @contextmanager
    def lock(self) -> Iterator[None]:
        regular_directory(self.lock_file.parent, os.geteuid())
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.lock_file, flags, 0o600)
        except OSError as error:
            raise ContractError("workspace lock is unavailable") from error
        try:
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_uid != os.geteuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
            ):
                raise ContractError("workspace lock is unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as error:
                raise ContractError("workspace lock failed") from error
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def execute(self, request: dict[str, Any], operation: str) -> dict[str, Any]:
        exact = validate_request(request, operation)
        with self.lock():
            self._validate_roots()
            if operation == "PROVISION":
                self._provision_if_absent(exact)
            return self._observe(exact)

    def publish(self, request: dict[str, Any]) -> dict[str, Any]:
        exact = validate_publication_request(request)
        with self.lock():
            self._validate_roots()
            return self._publish_exact(exact)

    def finalize_source(self, request: dict[str, Any], operation: str) -> dict[str, Any]:
        exact = validate_source_finalization_request(request, operation)
        with self.lock():
            self._validate_roots()
            root = self._root(exact["changeKey"])
            root_metadata = regular_directory(root, os.geteuid())
            if stat.S_IMODE(root_metadata.st_mode) not in {0o700, 0o770}:
                raise ContractError("source finalization workspace root mode is unsafe")
            path = root / "source-finalization-v1.json"
            if not path.exists() and not path.is_symlink() and operation == "INSPECT":
                return {**exact, "state": "ABSENT", "publishedHeadSha": None,
                        "expectedTreeSha": None, "finalizationReceiptSha256": None, "valuesExposed": False}
            preparation = self._read_sealed_record(root / "source-update-v1.json", SOURCE_UPDATE_RECORD_KEYS)
            retained = {key: preparation[key] for key in SOURCE_UPDATE_REQUEST_KEYS}
            validate_source_update_request(retained, "PREPARE")
            identity = ("changeKey", "databaseProjectId", "projectId", "repository", "repositoryBranch",
                        "baseCommit", "sourceCommit", "workspaceBranch", "workspaceIdentity", "workerId",
                        "targetMainCommit", "publicationReceiptSha256")
            owner_hash = canonical_sha256(self._read_record(self._record_path(exact["changeKey"])))
            if (any(exact[key] != preparation[key] for key in identity)
                    or preparation["operationId"] != exact["preparationOperationId"]
                    or preparation["recordSha256"] != exact["preparationReceiptSha256"]
                    or preparation["ownerRecordSha256"] != owner_hash
                    or preparation["state"] not in {"NEEDS_RESOLUTION", "READY_TO_FINALIZE"}
                    or exact["sourceRevision"] <= preparation["sourceRevision"]):
                raise ContractError("source finalization preparation is incompatible")
            exists = path.exists() or path.is_symlink()
            worktree = self._worktree(exact["changeKey"])
            if exists:
                record = self._read_sealed_record(path, SOURCE_FINALIZATION_RECORD_KEYS)
                if (source_update_intent(exact) != record["intentSha256"]
                        or record["ownerRecordSha256"] != owner_hash
                        or record["state"] not in {"PREPARED", "PUBLISHED"}
                        or not GIT_COMMIT.fullmatch(str(record["publishedHeadSha"]))
                        or not GIT_COMMIT.fullmatch(str(record["expectedTreeSha"]))):
                    raise ContractError("source finalization durable identity is incompatible")
            else:
                self._source_update_idle()
                self._source_update_owner(retained)
                self._source_update_refs(retained)
                observation = self._workspace_observation_for_publication(exact)
                if (observation["state"] != "OWNED" or observation["sourceCommit"] != exact["sourceCommit"]
                        or observation["sourceFingerprintSha256"] != exact["sourceFingerprintSha256"]
                        or self._safe_update_git("ls-files", "--unmerged", cwd=worktree)):
                    raise ContractError("source finalization source changed")
                tree = self._write_worktree_tree(worktree)
                files = self._update_files(tree)  # rejects symlinks/submodules and unsafe paths
                for name in preparation["conflictFiles"]:
                    if name in files:
                        data = self._safe_update_git("cat-file", "blob", files[name][1], git_dir=True)
                        if re.search(rb"(?m)^(?:<{7}|={7}|>{7}|\|{7})(?: |$)", data):
                            raise ContractError("source finalization unresolved markers")
                # No hooks, merge drivers, caller command, or caller commit text.
                # Seal the exact candidate BEFORE moving the owned branch.
                timestamp = self._safe_update_git("show", "-s", "--format=%ct", exact["sourceCommit"], git_dir=True).decode().strip()
                if not re.fullmatch(r"[0-9]{1,12}", timestamp):
                    raise ContractError("source finalization predecessor timestamp is invalid")
                head = self._safe_update_git("commit-tree", tree, "-p", exact["sourceCommit"],
                    "-p", exact["targetMainCommit"], "-m", "Atenea pinned source update " + exact["operationId"],
                    git_dir=True, env_extra={"GIT_AUTHOR_NAME": "Atenea", "GIT_AUTHOR_EMAIL": "atenea@localhost",
                    "GIT_COMMITTER_NAME": "Atenea", "GIT_COMMITTER_EMAIL": "atenea@localhost",
                    "GIT_AUTHOR_DATE": "@" + str(int(timestamp) + 1) + " +0000",
                    "GIT_COMMITTER_DATE": "@" + str(int(timestamp) + 1) + " +0000"}).decode().strip()
                record = {**exact, "state": "PREPARED", "intentSha256": source_update_intent(exact),
                    "ownerRecordSha256": owner_hash, "expectedTreeSha": tree, "publishedHeadSha": head,
                    "finalizationReceiptSha256": None}
                self._pin_finalization_candidate(exact, head, create=True)
                self._save_source_update(path, record)
                record = self._read_sealed_record(path, SOURCE_FINALIZATION_RECORD_KEYS)
            # JSON is not a GC root. Keep the candidate behind a fixed private
            # ref, including an interruption between pinning and journal write.
            self._pin_finalization_candidate(exact, record["publishedHeadSha"], create=False)
            if record["state"] == "PUBLISHED":
                # Inspection of a completed receipt is proof, not an invitation
                # to re-push a remotely moved branch or accept a later edit.
                actual = self._safe_update_git("rev-parse", "HEAD", cwd=worktree).decode().strip()
                self._source_update_owner(retained, expected_head=record["publishedHeadSha"])
                if (actual != record["publishedHeadSha"]
                        or self._safe_update_git("status", "--porcelain=v2", "-z", "--untracked-files=all", cwd=worktree)
                        or self._remote_branch_head(exact, worktree) != record["publishedHeadSha"]):
                    raise ContractError("source finalization published identity moved")
            if operation != "INSPECT":
                self._source_update_idle()
                self._resume_source_finalization(exact, retained, record, path)
                record = self._read_sealed_record(path, SOURCE_FINALIZATION_RECORD_KEYS)
            return {**exact, "state": record["state"], "publishedHeadSha": record["publishedHeadSha"],
                    "expectedTreeSha": record["expectedTreeSha"],
                    "finalizationReceiptSha256": record["finalizationReceiptSha256"], "valuesExposed": False}

    def _pin_finalization_candidate(self, request: dict[str, Any], head: str, *, create: bool) -> None:
        if not GIT_COMMIT.fullmatch(head):
            raise ContractError("source finalization candidate is invalid")
        ref = f"refs/atenea/source-finalizations/{request['changeKey']}/{request['operationId']}"
        found = self._git_result(*self._update_git_options(), "show-ref", "--verify", "--quiet", ref,
                                 git_dir=True, env_extra=self._update_git_environment())
        if found.returncode == 1 and create:
            self._safe_update_git("update-ref", ref, head, "0" * len(head), git_dir=True)
        elif found.returncode != 0 or self._safe_update_git("rev-parse", ref, git_dir=True).decode().strip() != head:
            raise ContractError("source finalization candidate ref is incompatible")

    def _resume_source_finalization(self, request: dict[str, Any], retained: dict[str, Any],
                                    record: dict[str, Any], path: Path) -> None:
        worktree = self._worktree(request["changeKey"])
        head = record["publishedHeadSha"]
        tree = record["expectedTreeSha"]
        parents = self._safe_update_git("rev-list", "--parents", "-n", "1", head, git_dir=True).decode().split()
        if (parents != [head, request["sourceCommit"], request["targetMainCommit"]]
                or self._safe_update_git("rev-parse", f"{head}^{{tree}}", git_dir=True).decode().strip() != tree):
            raise ContractError("source finalization candidate is incompatible")
        actual = self._safe_update_git("rev-parse", "HEAD", cwd=worktree).decode().strip()
        self._source_update_owner(retained, expected_head=actual)
        if actual not in {request["sourceCommit"], head} or self._write_worktree_tree(worktree) != tree:
            raise ContractError("source finalization later edit requires attention")
        remote = self._remote_branch_head(request, worktree)
        if record["state"] != "PUBLISHED":
            # Verify retained main again, before EACH effect/recovery. No fetch.
            self._source_update_refs({**retained, "sourceCommit": remote})
            if remote not in {request["sourceCommit"], head}:
                raise ContractError("source finalization remote head moved")
            if actual == request["sourceCommit"]:
                observation = self._workspace_observation_for_publication(request)
                if observation["sourceFingerprintSha256"] != request["sourceFingerprintSha256"]:
                    raise ContractError("source finalization source changed")
                self._safe_update_git("update-ref", self._branch_ref(request), head, actual, git_dir=True)
            # Resume an interruption after update-ref without modifying any file.
            self._safe_update_git("read-tree", tree, cwd=worktree)
        if self._safe_update_git("status", "--porcelain=v2", "-z", "--untracked-files=all", cwd=worktree):
            raise ContractError("source finalization worktree is not clean")
        if remote == request["sourceCommit"]:
            # Only a normal fast-forward push is permitted. Git receive-pack
            # checks its advertised old ref atomically; never request force.
            ref = self._branch_ref(request)
            self._safe_update_git("push", "--porcelain", "--no-force",
                                  self.publication_transport, f"{head}:{ref}", cwd=worktree, publication=True)
        elif remote != head:
            raise ContractError("source finalization remote head moved")
        if self._remote_branch_head(request, worktree) != head:
            raise ContractError("source finalization remote verification failed")
        receipt = canonical_sha256({"intentSha256": record["intentSha256"], "expectedTreeSha": tree,
                                   "publishedHeadSha": head, "predecessorReceiptSha256": request["publicationReceiptSha256"]})
        if record["state"] == "PUBLISHED":
            if record["finalizationReceiptSha256"] != receipt:
                raise ContractError("source finalization receipt changed")
            return
        self._save_source_update(path, {**{key: value for key, value in record.items() if key != "recordSha256"},
                                       "state": "PUBLISHED", "finalizationReceiptSha256": receipt})

    def update_source(self, request: dict[str, Any], operation: str) -> dict[str, Any]:
        exact = validate_source_update_request(request, operation)
        with self.lock():
            self._validate_roots()
            path = self._root(exact["changeKey"]) / "source-update-v1.json"
            exists = path.exists() or path.is_symlink()
            if not exists and operation != "PREPARE":
                return self._source_update_response(exact, None)
            self._source_update_owner(exact)
            if operation != "INSPECT":
                self._source_update_idle()
            if exists:
                record = self._read_sealed_record(path, SOURCE_UPDATE_RECORD_KEYS)
                validate_source_update_request({key: record[key] for key in SOURCE_UPDATE_REQUEST_KEYS}, "PREPARE")
                if (record["intentSha256"] != source_update_intent(exact)
                        or record["ownerRecordSha256"] != canonical_sha256(
                            self._read_record(self._record_path(exact["changeKey"])))
                        or record["state"] not in {"PREPARED", "NEEDS_RESOLUTION", "READY_TO_FINALIZE"}
                        or not GIT_COMMIT.fullmatch(str(record["preparedTreeSha"]))
                        or not isinstance(record["conflictFiles"], list)
                        or any(not isinstance(item, str) for item in record["conflictFiles"])):
                    raise ContractError("source update durable identity is incompatible")
            else:
                # No local/remote moving ref is selected implicitly. Both are
                # observations of the exact target approved by App.
                self._source_update_refs(exact)
                worktree = self._worktree(exact["changeKey"])
                if self._safe_update_git("status", "--porcelain=v2", "-z",
                                         "--untracked-files=all", cwd=worktree):
                    raise ContractError("source update workspace is not clean")
                self._update_files(exact["sourceCommit"])
                result = self._git_result(
                    *self._update_git_options(), "merge-tree", "--write-tree", "--name-only",
                    "--no-messages", "-z", exact["sourceCommit"], exact["targetMainCommit"], git_dir=True,
                    env_extra=self._update_git_environment())
                parts = result.stdout.split(b"\0")
                if result.returncode not in {0, 1} or len(result.stdout) > MAX_GIT_OUTPUT_BYTES:
                    raise ContractError("source update merge preparation failed")
                try:
                    tree = parts[0].decode("ascii").strip()
                    conflicts = sorted(set(part.decode("utf-8") for part in parts[1:] if part))
                except UnicodeDecodeError as error:
                    raise ContractError("source update paths are unsupported") from error
                if not GIT_COMMIT.fullmatch(tree) or (result.returncode == 0 and conflicts):
                    raise ContractError("source update merge preparation is invalid")
                if any(not name or "\\" in name or name.startswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in name)
                       or any(part in {"", ".", ".."} or part.lower() == ".git"
                              for part in name.split("/")) for name in conflicts):
                    raise ContractError("source update conflict path is unsupported")
                self._update_files(tree)
                self._source_update_refs(exact)
                record = {**exact, "state": "PREPARED", "intentSha256": source_update_intent(exact),
                          "ownerRecordSha256": canonical_sha256(self._read_record(self._record_path(exact["changeKey"]))),
                          "preparedTreeSha": tree, "conflictFiles": conflicts,
                          "preparedFingerprintSha256": None}
                # Intention and immutable trees precede every worktree effect.
                self._save_source_update(path, record)
            self._pin_source_update_tree(record, create=operation != "INSPECT" and record["state"] == "PREPARED")
            if operation != "INSPECT" and record["state"] == "PREPARED":
                self._resume_source_update(exact, record, path)
            return self._source_update_response(exact, record)

    def _pin_source_update_tree(self, record: dict[str, Any], *, create: bool) -> None:
        # Git GC does not read our JSON journal. Retain the prepared conflict
        # blobs/tree behind a private, server-derived ref, never a branch ref.
        ref = f"refs/atenea/source-updates/{record['changeKey']}/{record['operationId']}"
        found = self._git_result(*self._update_git_options(), "show-ref", "--verify", "--quiet", ref,
                                 git_dir=True, env_extra=self._update_git_environment())
        if found.returncode == 0:
            if self._safe_update_git("rev-parse", "--verify", ref, git_dir=True).decode().strip() != record["preparedTreeSha"]:
                raise ContractError("source update retained tree ref is incompatible")
        elif found.returncode == 1 and create:
            tree = record["preparedTreeSha"]
            if self._safe_update_git("cat-file", "-t", tree, git_dir=True).strip() != b"tree":
                raise ContractError("source update prepared tree is unavailable")
            self._safe_update_git("update-ref", ref, tree, "0" * len(tree), git_dir=True)
        elif found.returncode != 1 or record["state"] != "PREPARED":
            raise ContractError("source update retained tree ref is unavailable")

    @staticmethod
    def _update_git_options() -> tuple[str, ...]:
        return ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                "-c", "rerere.enabled=false", "-c", "merge.autoStash=false")

    def _safe_update_git(self, *args: str, **kwargs: Any) -> bytes:
        extra = {**self._update_git_environment(), **kwargs.pop("env_extra", {})}
        return self._git(*self._update_git_options(), *args,
                         env_extra=extra, **kwargs)

    @staticmethod
    def _update_git_environment() -> dict[str, str]:
        return {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1"}

    def _source_update_idle(self) -> None:
        path = self.lock_file.parent / "executions.json"
        try:
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ContractError("source update worker state is unsafe")
            state = strict_json(path.read_bytes())
        except OSError as error:
            raise ContractError("source update worker state is unavailable") from error
        if (state.get("protocol") != "agent-run-worker/v1" or state.get("workerId") != WORKER_ID
                or not isinstance(state.get("executions"), dict)
                or not isinstance(state.get("validations"), dict)):
            raise ContractError("source update worker state is invalid")
        terminal_validations = {"SUCCEEDED", "CANDIDATE_FAILED", "INFRASTRUCTURE_FAILED",
                                "POLICY_FAILED", "VALIDATION_FAILED", "OWNERSHIP_FAILED", "CANCELLED"}
        if (any(not isinstance(item, dict) or item.get("status") not in {"SUCCEEDED", "FAILED", "CANCELLED"}
                for item in state["executions"].values())
                or any(not isinstance(item, dict) or item.get("state") not in terminal_validations
                       for item in state["validations"].values())):
            raise ContractError("source update execution or validation is active")

    def _source_update_owner(self, request: dict[str, Any], *, expected_head: str | None = None) -> None:
        worktree = self._worktree(request["changeKey"])
        root = regular_directory(self._root(request["changeKey"]), os.geteuid())
        if stat.S_IMODE(root.st_mode) not in {0o700, 0o770}:
            raise ContractError("source update workspace root mode is unsafe")
        regular_directory(worktree, os.geteuid())
        owner = self._read_record(self._record_path(request["changeKey"]))
        # Creation base stays immutable even after main is incorporated.
        workspace_request = {**request, "protocolVersion": PROTOCOL_VERSION}
        if not self._record_matches_request(owner, workspace_request):
            raise ContractError("source update workspace owner is incompatible")
        keys = self._git("config", "--name-only", "--list", cwd=worktree,
                         env_extra=self._update_git_environment()).decode().lower().splitlines()
        if any(key.startswith(("filter.", "include.", "includeif."))
               or (key.startswith("merge.") and key.endswith(".driver"))
               or key in {"core.fsmonitor", "core.attributesfile", "core.worktree"}
               for key in keys):
            raise ContractError("source update external Git configuration is forbidden")
        common = self._safe_update_git("rev-parse", "--git-common-dir", cwd=worktree).decode().strip()
        if not Path(common).is_absolute():
            common = str(worktree / common)
        if (Path(common).resolve() != self.mirror.resolve()
                or self._safe_update_git("symbolic-ref", "--quiet", "HEAD", cwd=worktree).decode().strip()
                    != self._branch_ref(request)
                or self._safe_update_git("rev-parse", "--verify", "HEAD^{commit}", cwd=worktree).decode().strip()
                    != (request["sourceCommit"] if expected_head is None else expected_head)
                or self._safe_update_git("rev-parse", "--show-toplevel", cwd=worktree).decode().strip()
                    != str(worktree)):
            raise ContractError("source update local head or identity moved")
        if self._git_result(*self._update_git_options(), "merge-base", "--is-ancestor",
                            request["baseCommit"], request["sourceCommit"], git_dir=True,
                            env_extra=self._update_git_environment()).returncode != 0:
            raise ContractError("source update creation base is not an ancestor")
        publication = self._read_publication_record(self._publication_record_path(request["changeKey"]))
        if (publication["state"] != "PUBLISHED"
                or publication["publishedHeadSha"] != request["sourceCommit"]
                or publication["publicationReceiptSha256"] != request["publicationReceiptSha256"]
                or any(publication[key] != request[key] for key in (
                    "changeKey", "databaseProjectId", "projectId", "repository", "repositoryBranch",
                    "baseCommit", "workspaceBranch", "workspaceIdentity", "workerId", "sourceRevision"))):
            raise ContractError("source update predecessor publication is incompatible")

    def _source_update_refs(self, request: dict[str, Any]) -> None:
        target = request["targetMainCommit"]
        local = self._safe_update_git("rev-parse", "--verify", "refs/remotes/origin/main^{commit}", git_dir=True).decode().strip()
        remote = self._safe_update_git("ls-remote", "--heads", self.publication_transport,
                                       "refs/heads/main", self._branch_ref(request),
                                       git_dir=True, publication=True).decode().splitlines()
        refs = dict(line.split("\t", 1)[::-1] for line in remote if "\t" in line)
        if (len(remote) != 2 or local != target
                or refs != {"refs/heads/main": target, self._branch_ref(request): request["sourceCommit"]}):
            raise ContractError("source update retained main or published head moved")
        if self._git_result(*self._update_git_options(), "merge-base", "--is-ancestor",
                            request["baseCommit"], target, git_dir=True,
                            env_extra=self._update_git_environment()).returncode != 0:
            raise ContractError("source update target is not a descendant of creation base")

    def _update_files(self, tree: str) -> dict[str, tuple[str, str]]:
        files = {}
        raw = self._safe_update_git("ls-tree", "-r", "-z", tree, git_dir=True)
        try:
            for entry in raw.split(b"\0"):
                if not entry:
                    continue
                header, raw_name = entry.split(b"\t", 1)
                mode, kind, blob = header.decode("ascii").split()
                name = raw_name.decode("utf-8")
                parts = name.split("/")
                if (mode not in {"100644", "100755"} or kind != "blob"
                        or any(part in {"", ".", ".."} or part.lower() == ".git" for part in parts)
                        or "\\" in name or name.startswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in name)
                        or not GIT_COMMIT.fullmatch(blob)):
                    raise ContractError("source update file type or path is unsupported")
                files[name] = (mode, blob)
        except (UnicodeDecodeError, ValueError) as error:
            raise ContractError("source update tree is invalid") from error
        return files

    def _resume_source_update(self, request: dict[str, Any], record: dict[str, Any], path: Path) -> None:
        # Recover only bytes belonging to the retained predecessor or prepared
        # tree. A later edit is never silently reset, even after an interruption.
        worktree = self._worktree(request["changeKey"])
        before = self._update_files(request["sourceCommit"])
        after = self._update_files(record["preparedTreeSha"])
        self._require_update_files(worktree, before, after)
        # This changes the editable index/tree, never HEAD, creation ownership,
        # publication receipt or a remote branch. No MERGE_HEAD/hook is created.
        self._safe_update_git("read-tree", "--reset", "-u", record["preparedTreeSha"], cwd=worktree)
        self._require_update_files(worktree, after, after)
        if self._safe_update_git("write-tree", cwd=worktree).decode().strip() != record["preparedTreeSha"]:
            raise ContractError("source update index postcondition failed")
        observation = self._workspace_observation_for_publication(request)
        if observation["state"] != "OWNED" or observation["sourceCommit"] != request["sourceCommit"]:
            raise ContractError("source update postcondition failed")
        for name in after:
            descriptor = os.open(worktree / name, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        # Directory entries (including deletions) must precede the terminal
        # receipt, not merely file bytes and the Git index.
        for directory, _, _ in os.walk(worktree):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        git_directory = Path(self._safe_update_git("rev-parse", "--absolute-git-dir", cwd=worktree).decode().strip())
        with (git_directory / "index").open("rb") as index:
            os.fsync(index.fileno())
        record.update(state="NEEDS_RESOLUTION" if record["conflictFiles"] else "READY_TO_FINALIZE",
                      preparedFingerprintSha256=observation["sourceFingerprintSha256"])
        self._save_source_update(path, record)

    def _require_update_files(self, worktree: Path, before: dict[str, tuple[str, str]],
                              after: dict[str, tuple[str, str]]) -> None:
        actual = set()
        for directory, children, names in os.walk(worktree, followlinks=False):
            regular_directory(Path(directory), os.geteuid())
            for child in children:
                regular_directory(Path(directory) / child, os.geteuid())
            for name in names:
                candidate = Path(directory) / name
                relative = candidate.relative_to(worktree).as_posix()
                if relative == ".git":
                    continue
                actual.add(relative)
                info = candidate.lstat()
                choices = [entry for entry in (before.get(relative), after.get(relative)) if entry]
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or info.st_nlink != 1 or info.st_size > MAX_GIT_OUTPUT_BYTES or not choices):
                    raise ContractError("source update unexpected retained file")
                content = candidate.read_bytes()
                if not any(bool(info.st_mode & 0o111) == (mode == "100755")
                           and content == self._safe_update_git("cat-file", "blob", blob, git_dir=True)
                           for mode, blob in choices):
                    raise ContractError("source update later edit requires attention")
        if not (set(before) & set(after)).issubset(actual):
            raise ContractError("source update retained file is missing")

    def _save_source_update(self, path: Path, record: dict[str, Any]) -> None:
        body = {key: value for key, value in record.items() if key != "recordSha256"}
        record["recordSha256"] = canonical_sha256(body)
        self._write_record(path, record)

    def _source_update_response(self, request: dict[str, Any], record: dict[str, Any] | None) -> dict[str, Any]:
        return {**request, "state": record["state"] if record else "ABSENT",
                "preparedTreeSha": record["preparedTreeSha"] if record else None,
                "conflictFiles": record["conflictFiles"] if record else [],
                "preparedFingerprintSha256": record["preparedFingerprintSha256"] if record else None,
                "receiptSha256": record["recordSha256"] if record else None,
                "valuesExposed": False}

    def _validate_roots(self) -> None:
        regular_directory(self.mirror, os.geteuid())
        regular_directory(self.workspace_parent, os.geteuid())
        if not self.test_mode:
            mode = stat.S_IMODE(self.workspace_parent.lstat().st_mode)
            if mode != 0o2770:
                raise ContractError("workspace parent mode is unsafe")
        if self._git("remote", "get-url", "origin", git_dir=True).decode().strip() != self.publication_remote:
            raise ContractError("canonical mirror remote is invalid")
        if self._git("rev-parse", "--is-bare-repository", git_dir=True).decode().strip() != "true":
            raise ContractError("canonical mirror is not bare")

    def _root(self, change_key: str) -> Path:
        return self.workspace_parent / change_key

    def _worktree(self, change_key: str) -> Path:
        return self._root(change_key) / PROJECT_ID

    def _record_path(self, change_key: str) -> Path:
        return self._root(change_key) / "workspace-v1.json"

    def _publication_record_path(self, change_key: str) -> Path:
        return self._root(change_key) / "branch-publication-v1.json"

    def _branch_ref(self, request: dict[str, Any]) -> str:
        return f"refs/heads/{request['workspaceBranch']}"

    def _branch_exists(self, request: dict[str, Any]) -> bool:
        completed = self._git_result(
            "show-ref", "--verify", "--quiet", self._branch_ref(request), git_dir=True
        )
        if completed.returncode not in {0, 1}:
            raise ContractError("workspace branch state is unavailable")
        return completed.returncode == 0

    def _workspace_observation_for_publication(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        workspace_request = {
            "schemaVersion": SCHEMA_VERSION,
            "protocolVersion": PROTOCOL_VERSION,
            "effect": "OBSERVE_ONLY",
            "operationId": request["operationId"],
            "idempotencyKey": request["idempotencyKey"],
            "operation": "INSPECT",
            "predecessorOperationId": None,
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "repository": request["repository"],
            "repositoryBranch": request["repositoryBranch"],
            "baseCommit": request["baseCommit"],
            "sourceCommit": request["sourceCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "sourceRevision": request["sourceRevision"],
            "sourceFingerprintSha256": request["sourceFingerprintSha256"],
        }
        workspace_request["requestFingerprintSha256"] = canonical_sha256(
            workspace_request
        )
        return self._observe(workspace_request)

    def _publish_exact(self, request: dict[str, Any]) -> dict[str, Any]:
        publication_path = self._publication_record_path(request["changeKey"])
        if publication_path.exists() or publication_path.is_symlink():
            record = self._read_publication_record(publication_path)
            self._require_publication_record_owner(record, request)
            return self._resume_publication(request, record, publication_path)

        observation = self._workspace_observation_for_publication(request)
        if (
            observation["state"] != "OWNED"
            or observation["sourceCommit"] != request["sourceCommit"]
            or observation["sourceFingerprintSha256"]
                != request["sourceFingerprintSha256"]
        ):
            raise ContractError("publication source identity is stale or foreign")

        worktree = self._worktree(request["changeKey"])
        original_head = self._git(
            "rev-parse", "--verify", "HEAD^{commit}", cwd=worktree
        ).decode().strip()
        expected_tree = self._write_worktree_tree(worktree)
        record = self._publication_record(
            request,
            state="PREPARED",
            original_head=original_head,
            expected_tree=expected_tree,
        )
        self._write_record(publication_path, record)
        return self._resume_publication(request, record, publication_path)

    def _resume_publication(
        self,
        request: dict[str, Any],
        record: dict[str, Any],
        publication_path: Path,
    ) -> dict[str, Any]:
        worktree = self._worktree(request["changeKey"])
        published_head = record["publishedHeadSha"]
        if published_head is None:
            current_head = self._git(
                "rev-parse", "--verify", "HEAD^{commit}", cwd=worktree
            ).decode().strip()
            if current_head == record["originalHeadSha"]:
                observation = self._workspace_observation_for_publication(request)
                if (
                    observation["state"] != "OWNED"
                    or observation["sourceFingerprintSha256"]
                        != request["sourceFingerprintSha256"]
                ):
                    raise ContractError("prepared publication source changed")
                published_head = self._create_publication_commit(
                    request, record, worktree
                )
            else:
                self._require_recoverable_publication_commit(
                    current_head, record, worktree
                )
                published_head = current_head
            self._git("reset", "--mixed", published_head, cwd=worktree)
            if self._git(
                "status", "--porcelain=v2", "-z", "--untracked-files=all",
                cwd=worktree,
            ):
                raise ContractError("published worktree is not reproducible")
            record = self._publication_record(
                request,
                state="COMMITTED",
                original_head=record["originalHeadSha"],
                expected_tree=record["expectedTreeSha"],
                published_head=published_head,
            )
            self._write_record(publication_path, record)

        self._require_exact_local_publication(request, record, worktree)
        remote_head = self._remote_branch_head(request, worktree)
        if remote_head is None:
            branch_ref = self._branch_ref(request)
            self._git(
                "push",
                "--porcelain",
                self.publication_transport,
                f"{branch_ref}:{branch_ref}",
                cwd=worktree,
                publication=True,
            )
            remote_disposition = "CREATED"
        elif remote_head == published_head:
            remote_disposition = record["remoteDisposition"] or "IDENTICAL"
        else:
            raise ContractError("remote publication branch is incompatible")
        if self._remote_branch_head(request, worktree) != published_head:
            raise ContractError("remote publication verification failed")

        receipt = canonical_sha256({
            "changeKey": request["changeKey"],
            "sourceRevision": request["sourceRevision"],
            "sourceCommit": request["sourceCommit"],
            "sourceFingerprintSha256": request["sourceFingerprintSha256"],
            "workspaceBranch": request["workspaceBranch"],
            "publishedHeadSha": published_head,
        })
        if record["state"] != "PUBLISHED":
            record = self._publication_record(
                request,
                state="PUBLISHED",
                original_head=record["originalHeadSha"],
                expected_tree=record["expectedTreeSha"],
                published_head=published_head,
                remote_disposition=remote_disposition,
                receipt=receipt,
            )
            self._write_record(publication_path, record)
        elif record["publicationReceiptSha256"] != receipt:
            raise ContractError("publication receipt changed")
        return self._publication_response(request, record)

    def _write_worktree_tree(self, worktree: Path) -> str:
        descriptor, index_path = tempfile.mkstemp(
            prefix=".publication-index-", dir=worktree.parent
        )
        os.close(descriptor)
        os.unlink(index_path)
        try:
            extra = {"GIT_INDEX_FILE": index_path}
            self._git("read-tree", "HEAD", cwd=worktree, env_extra=extra)
            self._git("add", "-A", "--", ".", cwd=worktree, env_extra=extra)
            tree = self._git("write-tree", cwd=worktree, env_extra=extra).decode().strip()
            if not GIT_COMMIT.fullmatch(tree):
                raise ContractError("publication tree is invalid")
            return tree
        finally:
            if os.path.exists(index_path):
                os.unlink(index_path)

    def _create_publication_commit(
        self, request: dict[str, Any], record: dict[str, Any], worktree: Path
    ) -> str:
        original_head = record["originalHeadSha"]
        expected_tree = record["expectedTreeSha"]
        original_tree = self._git(
            "rev-parse", f"{original_head}^{{tree}}", cwd=worktree
        ).decode().strip()
        if expected_tree == original_tree:
            published_head = original_head
        else:
            message = (
                f"Publish DevelopmentChange {request['changeKey']} source r"
                f"{request['sourceRevision']}"
            )
            trace = (
                "Atenea-Dirty-Source-Fingerprint: "
                + request["sourceFingerprintSha256"]
                if request["sourceFingerprintSha256"] is not None
                else "Atenea-Source-Commit: " + request["sourceCommit"]
            )
            published_head = self._git(
                "commit-tree",
                expected_tree,
                "-p",
                original_head,
                "-m",
                message,
                "-m",
                trace,
                cwd=worktree,
                env_extra={
                    "GIT_AUTHOR_NAME": "Atenea",
                    "GIT_AUTHOR_EMAIL": "atenea@localhost",
                    "GIT_COMMITTER_NAME": "Atenea",
                    "GIT_COMMITTER_EMAIL": "atenea@localhost",
                },
            ).decode().strip()
            if not GIT_COMMIT.fullmatch(published_head):
                raise ContractError("publication commit is invalid")
            self._git(
                "update-ref",
                self._branch_ref(request),
                published_head,
                original_head,
                git_dir=True,
            )
        return published_head

    def _require_recoverable_publication_commit(
        self, current_head: str, record: dict[str, Any], worktree: Path
    ) -> None:
        parent = self._git(
            "rev-parse", f"{current_head}^1^{{commit}}", cwd=worktree
        ).decode().strip()
        tree = self._git(
            "rev-parse", f"{current_head}^{{tree}}", cwd=worktree
        ).decode().strip()
        if parent != record["originalHeadSha"] or tree != record["expectedTreeSha"]:
            raise ContractError("prepared publication head is ambiguous")

    def _require_exact_local_publication(
        self, request: dict[str, Any], record: dict[str, Any], worktree: Path
    ) -> None:
        published_head = record["publishedHeadSha"]
        branch_head = self._git(
            "rev-parse", "--verify", f"{self._branch_ref(request)}^{{commit}}",
            git_dir=True,
        ).decode().strip()
        worktree_head = self._git(
            "rev-parse", "--verify", "HEAD^{commit}", cwd=worktree
        ).decode().strip()
        current_branch = self._git(
            "symbolic-ref", "--quiet", "HEAD", cwd=worktree
        ).decode().strip()
        dirty = self._git(
            "status", "--porcelain=v2", "-z", "--untracked-files=all",
            cwd=worktree,
        )
        ancestor = self._git_result(
            "merge-base", "--is-ancestor", request["baseCommit"], published_head,
            cwd=worktree,
        )
        changed = self._git_result(
            "diff", "--quiet", request["baseCommit"], published_head,
            cwd=worktree,
        )
        if (
            branch_head != published_head
            or worktree_head != published_head
            or current_branch != self._branch_ref(request)
            or dirty
            or ancestor.returncode != 0
            or changed.returncode != 1
        ):
            raise ContractError("local publication identity is not exact")

    def _remote_branch_head(
        self, request: dict[str, Any], worktree: Path
    ) -> str | None:
        branch_ref = self._branch_ref(request)
        raw = self._git(
            "ls-remote", "--heads", self.publication_transport, branch_ref,
            cwd=worktree, publication=True,
        ).decode().strip()
        if not raw:
            return None
        lines = raw.splitlines()
        if len(lines) != 1:
            raise ContractError("remote publication ownership is ambiguous")
        parts = lines[0].split()
        if len(parts) != 2 or parts[1] != branch_ref or not GIT_COMMIT.fullmatch(parts[0]):
            raise ContractError("remote publication identity is invalid")
        return parts[0]

    def _publication_record(
        self,
        request: dict[str, Any],
        *,
        state: str,
        original_head: str,
        expected_tree: str,
        published_head: str | None = None,
        remote_disposition: str | None = None,
        receipt: str | None = None,
    ) -> dict[str, Any]:
        body = {
            **request,
            "state": state,
            "originalHeadSha": original_head,
            "expectedTreeSha": expected_tree,
            "publishedHeadSha": published_head,
            "remoteDisposition": remote_disposition,
            "publicationReceiptSha256": receipt,
        }
        return {**body, "recordSha256": canonical_sha256(body)}

    def _read_publication_record(self, path: Path) -> dict[str, Any]:
        record = self._read_sealed_record(path, PUBLICATION_RECORD_KEYS)
        if (
            record["state"] not in {"PREPARED", "COMMITTED", "PUBLISHED"}
            or not GIT_COMMIT.fullmatch(str(record["originalHeadSha"]))
            or not GIT_COMMIT.fullmatch(str(record["expectedTreeSha"]))
            or (record["publishedHeadSha"] is not None
                and not GIT_COMMIT.fullmatch(str(record["publishedHeadSha"])))
            or record["remoteDisposition"] not in {None, "CREATED", "IDENTICAL"}
            or (record["publicationReceiptSha256"] is not None
                and not SHA256.fullmatch(str(record["publicationReceiptSha256"])))
        ):
            raise ContractError("publication record values are invalid")
        return record

    def _require_publication_record_owner(
        self, record: dict[str, Any], request: dict[str, Any]
    ) -> None:
        if any(record.get(key) != value for key, value in request.items()):
            raise ContractError("publication record belongs to another source identity")

    def _publication_response(
        self, request: dict[str, Any], record: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "protocolVersion": PUBLICATION_PROTOCOL_VERSION,
            "state": "PUBLISHED",
            "effect": request["effect"],
            "operationId": request["operationId"],
            "idempotencyKey": request["idempotencyKey"],
            "operation": request["operation"],
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "repositoryBranch": request["repositoryBranch"],
            "baseCommit": request["baseCommit"],
            "sourceCommit": request["sourceCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "sourceRevision": request["sourceRevision"],
            "sourceFingerprintSha256": request["sourceFingerprintSha256"],
            "publishedHeadSha": record["publishedHeadSha"],
            "remoteDisposition": record["remoteDisposition"],
            "requestFingerprintSha256": request["requestFingerprintSha256"],
            "publicationReceiptSha256": record["publicationReceiptSha256"],
            "valuesExposed": False,
        }

    def _expected_record(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "protocolVersion": PROTOCOL_VERSION,
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "baseCommit": request["baseCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
        }

    def _record_matches_request(
        self, record: dict[str, Any], request: dict[str, Any]
    ) -> bool:
        stable = {
            "schemaVersion": request["schemaVersion"],
            "protocolVersion": request["protocolVersion"],
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "baseCommit": request["baseCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
        }
        return all(record.get(key) == value for key, value in stable.items())

    def _provision_if_absent(self, request: dict[str, Any]) -> None:
        root = self._root(request["changeKey"])
        branch_exists = self._branch_exists(request)
        if root.exists() or root.is_symlink() or branch_exists:
            return
        self._git("cat-file", "-e", f"{request['baseCommit']}^{{commit}}", git_dir=True)
        try:
            previous_umask = os.umask(0o007)
            try:
                root.mkdir(mode=0o770)
                os.chmod(root, 0o770)
                self._git(
                    "worktree",
                    "add",
                    "-b",
                    request["workspaceBranch"],
                    str(self._worktree(request["changeKey"])),
                    request["baseCommit"],
                    git_dir=True,
                )
            finally:
                os.umask(previous_umask)
            self._write_record(self._record_path(request["changeKey"]), self._expected_record(request))
        except (OSError, ContractError):
            # A partial resource is deliberately retained for fail-closed diagnosis.
            raise

    def _observe(self, request: dict[str, Any]) -> dict[str, Any]:
        root = self._root(request["changeKey"])
        record_path = self._record_path(request["changeKey"])
        worktree = self._worktree(request["changeKey"])
        root_present = root.exists() or root.is_symlink()
        branch_present = self._branch_exists(request)
        if not root_present and not branch_present:
            return self._response(request, "ABSENT")
        if not root_present or not branch_present:
            return self._foreign(request, "partial")
        try:
            regular_directory(root, os.geteuid())
            if stat.S_IMODE(root.lstat().st_mode) not in {0o700, 0o770}:
                return self._foreign(request, "root-mode")
            regular_directory(worktree, os.geteuid())
            record = self._read_record(record_path)
            if not self._record_matches_request(record, request):
                return self._foreign(request, "record")
            branch_head = self._git(
                "rev-parse", "--verify", f"{self._branch_ref(request)}^{{commit}}", git_dir=True
            ).decode().strip()
            worktree_head = self._git("rev-parse", "--verify", "HEAD^{commit}", cwd=worktree).decode().strip()
            current_branch = self._git("symbolic-ref", "--quiet", "HEAD", cwd=worktree).decode().strip()
            remote = self._git("remote", "get-url", "origin", cwd=worktree).decode().strip()
            if (
                branch_head != worktree_head
                or current_branch != self._branch_ref(request)
                or remote != self.publication_remote
            ):
                return self._foreign(request, "git-identity")
            self._git("cat-file", "-e", f"{request['baseCommit']}^{{commit}}", git_dir=True)
            ancestor = self._git_result(
                "merge-base", "--is-ancestor", request["baseCommit"], worktree_head,
                cwd=worktree,
            )
            if ancestor.returncode != 0:
                return self._foreign(request, "base-commit")
            status = self._git("status", "--porcelain=v2", "-z", "--untracked-files=all", cwd=worktree)
            dirty = bool(status)
            source_fingerprint = (
                self._dirty_source_fingerprint(worktree, worktree_head, status)
                if dirty else None
            )
            return self._response(
                request,
                "OWNED",
                source_commit=worktree_head,
                source_fingerprint=source_fingerprint,
                workspace_dirty=dirty,
                retained_draft=dirty,
            )
        except (OSError, ContractError, UnicodeDecodeError):
            return self._foreign(request, "observation")

    def _dirty_source_fingerprint(
        self, worktree: Path, head: str, status: bytes
    ) -> str:
        digest = hashlib.sha256()

        def add(label: bytes, data: bytes) -> None:
            digest.update(len(label).to_bytes(4, "big"))
            digest.update(label)
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)

        add(b"head", head.encode("ascii"))
        add(b"status", status)
        add(b"diff", self._git(
            "diff", "--binary", "--no-ext-diff", "HEAD", cwd=worktree
        ))
        raw = self._git("ls-files", "--others", "--exclude-standard", "-z", cwd=worktree)
        paths = [part.decode("utf-8") for part in raw.split(b"\0") if part]
        if len(paths) > 4096:
            raise ContractError("too many untracked paths")
        total = 0
        for relative in sorted(paths):
            candidate = worktree / relative
            try:
                observed = candidate.lstat()
            except OSError as error:
                raise ContractError("untracked path is unavailable") from error
            if stat.S_ISLNK(observed.st_mode):
                data = os.readlink(candidate).encode("utf-8")
            elif stat.S_ISREG(observed.st_mode):
                total += observed.st_size
                if total > MAX_GIT_OUTPUT_BYTES:
                    raise ContractError("untracked content exceeds limit")
                data = candidate.read_bytes()
            else:
                raise ContractError("untracked path type is unsafe")
            add(b"untracked-path", relative.encode("utf-8"))
            add(b"untracked-content", data)
        return digest.hexdigest()

    def _foreign(self, request: dict[str, Any], classification: str) -> dict[str, Any]:
        return self._response(request, "FOREIGN")

    def _response(
        self,
        request: dict[str, Any],
        state: str,
        *,
        source_commit: str | None = None,
        source_fingerprint: str | None = None,
        workspace_dirty: bool | None = None,
        retained_draft: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": request["schemaVersion"],
            "protocolVersion": request["protocolVersion"],
            "state": state,
            "effect": request["effect"],
            "operationId": request["operationId"],
            "idempotencyKey": request["idempotencyKey"],
            "operation": request["operation"],
            "predecessorOperationId": request["predecessorOperationId"],
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "repository": request["repository"],
            "repositoryBranch": request["repositoryBranch"],
            "baseCommit": request["baseCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "sourceRevision": request["sourceRevision"],
            "sourceCommit": source_commit,
            "sourceFingerprintSha256": source_fingerprint,
            "workspaceDirty": workspace_dirty,
            "retainedDraft": retained_draft,
            "requestFingerprintSha256": request["requestFingerprintSha256"],
            "valuesExposed": False,
        }

    def _read_record(self, path: Path) -> dict[str, Any]:
        try:
            observed = path.lstat()
            if (
                not stat.S_ISREG(observed.st_mode)
                or path.is_symlink()
                or observed.st_uid != os.geteuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
            ):
                raise ContractError("workspace record is unsafe")
            parsed = strict_json(path.read_bytes())
        except OSError as error:
            raise ContractError("workspace record is unavailable") from error
        if set(parsed) != RECORD_KEYS and set(parsed) != LEGACY_RECORD_KEYS:
            raise ContractError("workspace record fields are invalid")
        return parsed

    def _read_sealed_record(
        self, path: Path, expected_keys: set[str]
    ) -> dict[str, Any]:
        try:
            observed = path.lstat()
            if (
                not stat.S_ISREG(observed.st_mode)
                or path.is_symlink()
                or observed.st_uid != os.geteuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
            ):
                raise ContractError("workspace record is unsafe")
            parsed = strict_json(path.read_bytes())
        except OSError as error:
            raise ContractError("workspace record is unavailable") from error
        if set(parsed) != expected_keys:
            raise ContractError("workspace record fields are invalid")
        body = dict(parsed)
        seal = body.pop("recordSha256", None)
        if not isinstance(seal, str) or canonical_sha256(body) != seal:
            raise ContractError("workspace record seal is invalid")
        return parsed

    def _write_record(self, path: Path, record: dict[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".workspace-v1-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(canonical_bytes(record) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _publication_credential(self) -> tuple[Path, os.stat_result]:
        raw_directory = os.environ.get("CREDENTIALS_DIRECTORY")
        if not raw_directory:
            raise ContractError("publication authentication is unavailable")
        directory = Path(raw_directory)
        if (
            not directory.is_absolute()
            or (not self.test_mode and directory != PUBLICATION_CREDENTIALS_DIRECTORY)
        ):
            raise ContractError("publication authentication is unavailable")
        try:
            directory_state = directory.lstat()
        except OSError as error:
            raise ContractError("publication authentication is unavailable") from error
        if not stat.S_ISDIR(directory_state.st_mode) or directory.is_symlink():
            raise ContractError("publication authentication is unavailable")

        credential = directory / PUBLICATION_CREDENTIAL_NAME
        if credential.parent != directory:
            raise ContractError("publication authentication is unavailable")
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(credential, flags)
        except OSError as error:
            raise ContractError("publication authentication is unavailable") from error
        try:
            credential_state = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        expected_uid = os.geteuid() if self.test_mode else 0
        if (
            not stat.S_ISREG(credential_state.st_mode)
            or credential_state.st_uid != expected_uid
            or credential_state.st_nlink != 1
            or credential_state.st_size < 1
            or credential_state.st_size > 1024 * 1024
            or stat.S_IMODE(credential_state.st_mode) not in {0o400, 0o440}
        ):
            raise ContractError("publication authentication is unavailable")
        return credential, credential_state

    def _require_publication_runtime_directory(self) -> None:
        path = self.publication_runtime_directory
        try:
            observed = path.lstat()
        except OSError as error:
            raise ContractError("publication authentication is unavailable") from error
        if (
            not path.is_absolute()
            or not stat.S_ISDIR(observed.st_mode)
            or path.is_symlink()
            or observed.st_uid != os.geteuid()
            or stat.S_IMODE(observed.st_mode) != 0o700
        ):
            raise ContractError("publication authentication is unavailable")

    @contextmanager
    def _runtime_publication_credential(self) -> Iterator[Path]:
        self._require_publication_runtime_directory()
        credential, expected_source = self._publication_credential()
        source_descriptor = -1
        runtime_descriptor = -1
        runtime_credential: Path | None = None
        runtime_identity: tuple[int, int] | None = None
        cleanup_failed = False
        try:
            source_flags = os.O_RDONLY | os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                source_flags |= os.O_NOFOLLOW
            source_descriptor = os.open(credential, source_flags)
            source_state = os.fstat(source_descriptor)
            if (
                source_state.st_dev != expected_source.st_dev
                or source_state.st_ino != expected_source.st_ino
                or source_state.st_mode != expected_source.st_mode
                or source_state.st_uid != expected_source.st_uid
                or source_state.st_nlink != expected_source.st_nlink
                or source_state.st_size != expected_source.st_size
            ):
                raise ContractError("publication authentication is unavailable")

            runtime_descriptor, runtime_name = tempfile.mkstemp(
                prefix="identity-", dir=self.publication_runtime_directory
            )
            runtime_credential = Path(runtime_name)
            os.fchmod(runtime_descriptor, 0o600)
            copied = 0
            while True:
                chunk = os.read(source_descriptor, 64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > expected_source.st_size:
                    raise ContractError("publication authentication is unavailable")
                view = memoryview(chunk)
                while view:
                    written = os.write(runtime_descriptor, view)
                    if written < 1:
                        raise OSError("short publication credential write")
                    view = view[written:]
            if copied != expected_source.st_size:
                raise ContractError("publication authentication is unavailable")
            os.fsync(runtime_descriptor)
            runtime_state = os.fstat(runtime_descriptor)
            runtime_identity = (runtime_state.st_dev, runtime_state.st_ino)
            if (
                not stat.S_ISREG(runtime_state.st_mode)
                or runtime_state.st_uid != os.geteuid()
                or runtime_state.st_nlink != 1
                or runtime_state.st_size != expected_source.st_size
                or stat.S_IMODE(runtime_state.st_mode) != 0o600
            ):
                raise ContractError("publication authentication is unavailable")
            os.close(source_descriptor)
            source_descriptor = -1
            os.close(runtime_descriptor)
            runtime_descriptor = -1

            self._require_publication_runtime_directory()
            final_state = runtime_credential.lstat()
            if (
                runtime_credential.is_symlink()
                or not stat.S_ISREG(final_state.st_mode)
                or (final_state.st_dev, final_state.st_ino) != runtime_identity
                or final_state.st_uid != os.geteuid()
                or final_state.st_nlink != 1
                or final_state.st_size != expected_source.st_size
                or stat.S_IMODE(final_state.st_mode) != 0o600
            ):
                raise ContractError("publication authentication is unavailable")
            yield runtime_credential
        except OSError as error:
            raise ContractError("publication authentication is unavailable") from error
        finally:
            if source_descriptor >= 0:
                os.close(source_descriptor)
            if runtime_descriptor >= 0:
                os.close(runtime_descriptor)
            if runtime_credential is not None:
                try:
                    current = runtime_credential.lstat()
                    if (
                        runtime_identity is None
                        or runtime_credential.is_symlink()
                        or not stat.S_ISREG(current.st_mode)
                        or (current.st_dev, current.st_ino) != runtime_identity
                    ):
                        cleanup_failed = True
                    os.unlink(runtime_credential)
                    if runtime_credential.exists() or runtime_credential.is_symlink():
                        cleanup_failed = True
                except OSError:
                    cleanup_failed = True
            if cleanup_failed:
                raise ContractError("publication authentication cleanup failed")

    def _require_publication_known_hosts(self) -> None:
        path = self.publication_known_hosts
        try:
            observed = path.lstat()
            raw = path.read_bytes()
        except OSError as error:
            raise ContractError("publication trust is unavailable") from error
        if (
            not stat.S_ISREG(observed.st_mode)
            or path.is_symlink()
            or observed.st_nlink != 1
            or len(raw) < 1
            or len(raw) > 64 * 1024
            or (
                not self.test_mode
                and (observed.st_uid != 0 or stat.S_IMODE(observed.st_mode) != 0o644)
            )
        ):
            raise ContractError("publication trust is unavailable")
        try:
            records = [line.split() for line in raw.decode("ascii").splitlines() if line]
            compatible = (
                len(records) == 1
                and len(records[0]) == 3
                and records[0][0] == "github.com"
                and records[0][1] == "ssh-ed25519"
                and bool(base64.b64decode(records[0][2], validate=True))
            )
        except (UnicodeDecodeError, ValueError):
            compatible = False
        if not compatible:
            raise ContractError("publication trust is unavailable")

    def _publication_git_environment(self, credential: Path) -> dict[str, str]:
        ssh_command = " ".join(
            shlex.quote(value)
            for value in (
                "/usr/bin/ssh",
                "-F", "/dev/null",
                "-i", str(credential),
                "-o", "IdentitiesOnly=yes",
                "-o", "IdentityAgent=none",
                "-o", "BatchMode=yes",
                "-o", "PasswordAuthentication=no",
                "-o", "KbdInteractiveAuthentication=no",
                "-o", "PreferredAuthentications=publickey",
                "-o", "StrictHostKeyChecking=yes",
                "-o", f"UserKnownHostsFile={self.publication_known_hosts}",
                "-o", "GlobalKnownHostsFile=/dev/null",
            )
        )
        return {
            "GIT_SSH_COMMAND": ssh_command,
            "GIT_SSH_VARIANT": "ssh",
            "GIT_ALLOW_PROTOCOL": "file:ssh" if self.test_mode else "ssh",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
        }

    def _git_result(
        self,
        *arguments: str,
        git_dir: bool = False,
        cwd: Path | None = None,
        env_extra: dict[str, str] | None = None,
        publication: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        command = ["/usr/bin/git"]
        if git_dir:
            command.append(f"--git-dir={self.mirror}")
        command.extend(arguments)
        environment = {"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
        if env_extra:
            environment.update(env_extra)

        def run() -> subprocess.CompletedProcess[bytes]:
            try:
                return subprocess.run(
                    command,
                    cwd=cwd,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=GIT_TIMEOUT_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as error:
                raise ContractError("Git operation is unavailable") from error

        if not publication:
            return run()
        self._require_publication_known_hosts()
        with self._runtime_publication_credential() as credential:
            environment.update(self._publication_git_environment(credential))
            return run()

    def _git(
        self,
        *arguments: str,
        git_dir: bool = False,
        cwd: Path | None = None,
        env_extra: dict[str, str] | None = None,
        publication: bool = False,
    ) -> bytes:
        completed = self._git_result(
            *arguments, git_dir=git_dir, cwd=cwd, env_extra=env_extra,
            publication=publication,
        )
        if completed.returncode != 0 or len(completed.stdout) > MAX_GIT_OUTPUT_BYTES:
            raise ContractError("Git operation failed closed")
        return completed.stdout


def main() -> int:
    updates = {f"{operation.lower()}-update": operation for operation in SOURCE_UPDATE_OPERATIONS}
    finalizations = {f"{operation.lower()}-source": operation for operation in SOURCE_FINALIZATION_OPERATIONS}
    if len(sys.argv) != 2 or sys.argv[1].upper() not in OPERATIONS | {PUBLICATION_OPERATION} and sys.argv[1] not in updates | finalizations:
        print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65
    try:
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) < 2 or len(raw) > 65_536:
            raise ContractError("request size is invalid")
        request = strict_json(raw)
        operation = sys.argv[1].upper()
        mediator = WorkspaceMediator()
        if sys.argv[1] in finalizations:
            response = mediator.finalize_source(request, finalizations[sys.argv[1]])
        elif sys.argv[1] in updates:
            response = mediator.update_source(request, updates[sys.argv[1]])
        else:
            response = mediator.publish(request) if operation == PUBLICATION_OPERATION else mediator.execute(request, operation)
        sys.stdout.buffer.write(canonical_bytes(response) + b"\n")
        return 0
    except (ContractError, OSError, UnicodeError, ValueError) as error:
        if sys.argv[1] in updates | finalizations:
            code = {
                "source update retained main or published head moved": "SOURCE_UPDATE_REF_MOVED",
                "source update local head or identity moved": "SOURCE_UPDATE_REF_MOVED",
                "source update workspace is not clean": "SOURCE_UPDATE_DIRTY_WORKSPACE",
                "source update later edit requires attention": "SOURCE_UPDATE_LATER_EDIT",
                "source update execution or validation is active": "SOURCE_UPDATE_EXECUTION_ACTIVE",
                "source update durable identity is incompatible": "SOURCE_UPDATE_IDENTITY_CONFLICT",
            }.get(str(error), "SOURCE_UPDATE_REJECTED")
            print(json.dumps({"code": code}, separators=(",", ":")), file=sys.stderr)
        else:
            print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
