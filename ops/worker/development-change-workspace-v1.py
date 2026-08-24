#!/usr/bin/env python3
"""Canonical fail-closed development-change workspace mediator for AX42."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
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
REPOSITORY_BRANCH = "main"
MIRROR = Path("/srv/atenea/repositories/atenea.git")
WORKSPACE_PARENT = Path("/srv/atenea/workspaces/changes")
LOCK_FILE = Path("/srv/atenea/worker/agent-runs-v1/development-change-workspace-v1.lock")
GIT_TIMEOUT_SECONDS = 30
MAX_GIT_OUTPUT_BYTES = 64 * 1024 * 1024

SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
OPERATIONS = {"PROVISION", "INSPECT", "RECONCILE"}
PUBLICATION_OPERATION = "PUBLISH"
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
    "expectedCanonicalCommit",
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
    "repository",
    "repositoryBranch",
    "baseCommit",
    "workspaceBranch",
    "workspaceIdentity",
    "workerId",
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
    "expectedCanonicalCommit",
    "workspaceBranch",
    "workspaceIdentity",
    "workerId",
    "sourceRevision",
    "sourceFingerprintSha256",
    "workspaceOwnershipFingerprintSha256",
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
    if not GIT_COMMIT.fullmatch(str(value.get("expectedCanonicalCommit", ""))):
        raise ContractError("canonical commit is invalid")
    if not SHA256.fullmatch(str(value.get("sourceFingerprintSha256", ""))):
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
    for field in ("baseCommit", "expectedCanonicalCommit"):
        if not GIT_COMMIT.fullmatch(str(value.get(field, ""))):
            raise ContractError("publication Git identity is invalid")
    for field in (
        "sourceFingerprintSha256",
        "workspaceOwnershipFingerprintSha256",
        "requestFingerprintSha256",
    ):
        if not SHA256.fullmatch(str(value.get(field, ""))):
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


class WorkspaceMediator:
    def __init__(
        self,
        mirror: Path = MIRROR,
        workspace_parent: Path = WORKSPACE_PARENT,
        lock_file: Path = LOCK_FILE,
        *,
        test_mode: bool = False,
        publication_remote: str = REPOSITORY,
    ) -> None:
        self.mirror = Path(mirror)
        self.workspace_parent = Path(workspace_parent)
        self.lock_file = Path(lock_file)
        self.publication_remote = publication_remote
        if not test_mode and (
            self.mirror != MIRROR
            or self.workspace_parent != WORKSPACE_PARENT
            or self.lock_file != LOCK_FILE
            or self.publication_remote != REPOSITORY
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
            "expectedCanonicalCommit": request["expectedCanonicalCommit"],
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
            or observation["canonicalCommit"] != request["expectedCanonicalCommit"]
            or observation["sourceFingerprintSha256"]
                != request["sourceFingerprintSha256"]
            or observation["ownershipFingerprintSha256"]
                != request["workspaceOwnershipFingerprintSha256"]
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
                    or observation["ownershipFingerprintSha256"]
                        != request["workspaceOwnershipFingerprintSha256"]
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
                "origin",
                f"{branch_ref}:{branch_ref}",
                cwd=worktree,
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
                "Atenea-Source-Fingerprint: "
                + request["sourceFingerprintSha256"]
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
            "ls-remote", "--heads", "origin", branch_ref, cwd=worktree
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
            "expectedCanonicalCommit": request["expectedCanonicalCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "sourceRevision": request["sourceRevision"],
            "expectedSourceFingerprintSha256": request["sourceFingerprintSha256"],
            "expectedWorkspaceOwnershipFingerprintSha256":
                request["workspaceOwnershipFingerprintSha256"],
            "publishedHeadSha": record["publishedHeadSha"],
            "remoteDisposition": record["remoteDisposition"],
            "requestFingerprintSha256": request["requestFingerprintSha256"],
            "publicationReceiptSha256": record["publicationReceiptSha256"],
            "valuesExposed": False,
        }

    def _expected_record(self, request: dict[str, Any]) -> dict[str, Any]:
        body = {
            "schemaVersion": SCHEMA_VERSION,
            "protocolVersion": PROTOCOL_VERSION,
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "repository": request["repository"],
            "repositoryBranch": request["repositoryBranch"],
            "baseCommit": request["baseCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "initialSourceFingerprintSha256": request["sourceFingerprintSha256"],
        }
        return {**body, "recordSha256": canonical_sha256(body)}

    def _record_matches_request(
        self, record: dict[str, Any], request: dict[str, Any]
    ) -> bool:
        stable = {
            "schemaVersion": request["schemaVersion"],
            "protocolVersion": request["protocolVersion"],
            "changeKey": request["changeKey"],
            "databaseProjectId": request["databaseProjectId"],
            "projectId": request["projectId"],
            "repository": request["repository"],
            "repositoryBranch": request["repositoryBranch"],
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
            return self._response(request, "ABSENT", canonical_sha256({
                "state": "ABSENT",
                "changeKey": request["changeKey"],
                "workspaceIdentity": request["workspaceIdentity"],
            }))
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
            canonical_commit = self._git(
                "rev-parse",
                "--verify",
                f"refs/remotes/origin/{REPOSITORY_BRANCH}^{{commit}}",
                git_dir=True,
            ).decode().strip()
            if not GIT_COMMIT.fullmatch(canonical_commit):
                raise ContractError("canonical commit is invalid")
            status = self._git("status", "--porcelain=v2", "-z", "--untracked-files=all", cwd=worktree)
            dirty = bool(status)
            source_fingerprint = record["initialSourceFingerprintSha256"]
            if dirty or worktree_head != request["baseCommit"]:
                diff = self._git("diff", "--binary", "--no-ext-diff", "HEAD", cwd=worktree)
                source_fingerprint = canonical_sha256({
                    "initialSourceFingerprintSha256": record["initialSourceFingerprintSha256"],
                    "headCommit": worktree_head,
                    "statusSha256": hashlib.sha256(status).hexdigest(),
                    "diffSha256": hashlib.sha256(diff).hexdigest(),
                    "untracked": self._untracked_fingerprints(worktree),
                })
            ownership = canonical_sha256({
                "recordSha256": record["recordSha256"],
                "branchHead": branch_head,
                "workspaceIdentity": request["workspaceIdentity"],
            })
            return self._response(
                request,
                "OWNED",
                ownership,
                canonical_commit=canonical_commit,
                source_fingerprint=source_fingerprint,
                workspace_dirty=dirty,
                retained_draft=dirty,
            )
        except (OSError, ContractError, UnicodeDecodeError):
            return self._foreign(request, "observation")

    def _untracked_fingerprints(self, worktree: Path) -> list[dict[str, str]]:
        raw = self._git("ls-files", "--others", "--exclude-standard", "-z", cwd=worktree)
        paths = [part.decode("utf-8") for part in raw.split(b"\0") if part]
        if len(paths) > 4096:
            raise ContractError("too many untracked paths")
        result: list[dict[str, str]] = []
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
            result.append({"pathSha256": hashlib.sha256(relative.encode()).hexdigest(),
                           "contentSha256": hashlib.sha256(data).hexdigest()})
        return result

    def _foreign(self, request: dict[str, Any], classification: str) -> dict[str, Any]:
        return self._response(request, "FOREIGN", canonical_sha256({
            "state": "FOREIGN",
            "classification": classification,
            "changeKey": request["changeKey"],
            "workspaceIdentity": request["workspaceIdentity"],
        }))

    def _response(
        self,
        request: dict[str, Any],
        state: str,
        ownership_fingerprint: str,
        *,
        canonical_commit: str | None = None,
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
            "expectedCanonicalCommit": request["expectedCanonicalCommit"],
            "workspaceBranch": request["workspaceBranch"],
            "workspaceIdentity": request["workspaceIdentity"],
            "workerId": request["workerId"],
            "sourceRevision": request["sourceRevision"],
            "expectedSourceFingerprintSha256": request["sourceFingerprintSha256"],
            "canonicalCommit": canonical_commit,
            "sourceFingerprintSha256": source_fingerprint,
            "workspaceDirty": workspace_dirty,
            "retainedDraft": retained_draft,
            "requestFingerprintSha256": request["requestFingerprintSha256"],
            "ownershipFingerprintSha256": ownership_fingerprint,
            "valuesExposed": False,
        }

    def _read_record(self, path: Path) -> dict[str, Any]:
        return self._read_sealed_record(path, RECORD_KEYS)

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

    def _git_result(
        self,
        *arguments: str,
        git_dir: bool = False,
        cwd: Path | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        command = ["/usr/bin/git"]
        if git_dir:
            command.append(f"--git-dir={self.mirror}")
        command.extend(arguments)
        environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
        if env_extra:
            environment.update(env_extra)
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

    def _git(
        self,
        *arguments: str,
        git_dir: bool = False,
        cwd: Path | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> bytes:
        completed = self._git_result(
            *arguments, git_dir=git_dir, cwd=cwd, env_extra=env_extra
        )
        if completed.returncode != 0 or len(completed.stdout) > MAX_GIT_OUTPUT_BYTES:
            raise ContractError("Git operation failed closed")
        return completed.stdout


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].upper() not in OPERATIONS | {PUBLICATION_OPERATION}:
        print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65
    try:
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) < 2 or len(raw) > 65_536:
            raise ContractError("request size is invalid")
        request = strict_json(raw)
        operation = sys.argv[1].upper()
        mediator = WorkspaceMediator()
        response = (
            mediator.publish(request)
            if operation == PUBLICATION_OPERATION
            else mediator.execute(request, operation)
        )
        sys.stdout.buffer.write(canonical_bytes(response) + b"\n")
        return 0
    except ContractError:
        print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
