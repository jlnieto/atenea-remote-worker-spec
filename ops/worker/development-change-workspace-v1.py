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


class WorkspaceMediator:
    def __init__(
        self,
        mirror: Path = MIRROR,
        workspace_parent: Path = WORKSPACE_PARENT,
        lock_file: Path = LOCK_FILE,
        *,
        test_mode: bool = False,
    ) -> None:
        self.mirror = Path(mirror)
        self.workspace_parent = Path(workspace_parent)
        self.lock_file = Path(lock_file)
        if not test_mode and (
            self.mirror != MIRROR
            or self.workspace_parent != WORKSPACE_PARENT
            or self.lock_file != LOCK_FILE
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

    def _validate_roots(self) -> None:
        regular_directory(self.mirror, os.geteuid())
        regular_directory(self.workspace_parent, os.geteuid())
        if not self.test_mode:
            mode = stat.S_IMODE(self.workspace_parent.lstat().st_mode)
            if mode != 0o2770:
                raise ContractError("workspace parent mode is unsafe")
        if self._git("remote", "get-url", "origin", git_dir=True).decode().strip() != REPOSITORY:
            raise ContractError("canonical mirror remote is invalid")
        if self._git("rev-parse", "--is-bare-repository", git_dir=True).decode().strip() != "true":
            raise ContractError("canonical mirror is not bare")

    def _root(self, change_key: str) -> Path:
        return self.workspace_parent / change_key

    def _worktree(self, change_key: str) -> Path:
        return self._root(change_key) / PROJECT_ID

    def _record_path(self, change_key: str) -> Path:
        return self._root(change_key) / "workspace-v1.json"

    def _branch_ref(self, request: dict[str, Any]) -> str:
        return f"refs/heads/{request['workspaceBranch']}"

    def _branch_exists(self, request: dict[str, Any]) -> bool:
        completed = self._git_result(
            "show-ref", "--verify", "--quiet", self._branch_ref(request), git_dir=True
        )
        if completed.returncode not in {0, 1}:
            raise ContractError("workspace branch state is unavailable")
        return completed.returncode == 0

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
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            self._git(
                "worktree",
                "add",
                "-b",
                request["workspaceBranch"],
                str(self._worktree(request["changeKey"])),
                request["baseCommit"],
                git_dir=True,
            )
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
            if stat.S_IMODE(root.lstat().st_mode) != 0o700:
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
                or remote != REPOSITORY
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
        if set(parsed) != RECORD_KEYS:
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
        self, *arguments: str, git_dir: bool = False, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        command = ["/usr/bin/git"]
        if git_dir:
            command.append(f"--git-dir={self.mirror}")
        command.extend(arguments)
        environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
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
        self, *arguments: str, git_dir: bool = False, cwd: Path | None = None
    ) -> bytes:
        completed = self._git_result(*arguments, git_dir=git_dir, cwd=cwd)
        if completed.returncode != 0 or len(completed.stdout) > MAX_GIT_OUTPUT_BYTES:
            raise ContractError("Git operation failed closed")
        return completed.stdout


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].upper() not in OPERATIONS:
        print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65
    try:
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) < 2 or len(raw) > 65_536:
            raise ContractError("request size is invalid")
        request = strict_json(raw)
        response = WorkspaceMediator().execute(request, sys.argv[1].upper())
        sys.stdout.buffer.write(canonical_bytes(response) + b"\n")
        return 0
    except ContractError:
        print("DEVELOPMENT_CHANGE_WORKSPACE_REJECTED", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
