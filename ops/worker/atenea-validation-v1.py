#!/usr/bin/env python3
"""Closed, root-coordinated validation runner for the Atenea project."""

from __future__ import annotations

import base64
import dataclasses
import fcntl
import grp
import hashlib
import json
import os
import pwd
import re
import runpy
import resource
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator, NoReturn


CONFIG = Path("/etc/atenea-worker/project-codex-v1.json")
ARTIFACT_ROOT = Path("/srv/atenea/artifacts/validations")
RUNTIME_ROOT = Path("/srv/atenea/validation-runtime-v1")
JOURNAL_ROOT = Path("/srv/atenea/worker/validation-broker-v1")
WORKSPACE_ROOT = Path("/srv/atenea/workspaces/sessions")
CHANGE_WORKSPACE_ROOT = Path("/srv/atenea/workspaces/changes")
SOURCE_AUTHORITY_MEDIATOR = Path("/usr/local/libexec/atenea/development-change-workspace-v1.py")
RUNTIME_ADMISSION = Path("/usr/local/libexec/atenea/runtime-admission-v1.sh")
WORKER_USER = "atenea-worker"
PLAYWRIGHT_CHECK = Path("/usr/local/libexec/atenea/atenea-playwright-validation-v1.js")
PLAYWRIGHT_IMAGE = (
    "mcr.microsoft.com/playwright:v1.60.0-noble@"
    "sha256:9bd26ad900bb5e0f4dee75839e957a89ae89c2b7ab1e76050e559790e946b948"
)
PLAYWRIGHT_CHECK_SHA256 = (
    "92ebd40e97fb805b0950f0a50eb49dff727a9dd4df794c1236f503016d4a3824"
)
ANDROID_DOCKERFILE_SHA256 = (
    "4b61f515954c2062606508ce2c9ccc65a599b1c0582ade4d0708e56f5cb409c2"
)
ANDROID_INPUTS = Path("/usr/local/libexec/atenea/atenea-android-inputs-v2.json")
ANDROID_FRAGMENT = Path("/usr/local/libexec/atenea/atenea-android-validation-v2.Dockerfile")
ANDROID_RUNTIME = Path("/usr/local/libexec/atenea/atenea-android-runtime-v2.py")
ANDROID_INPUTS_SHA256 = "bd78708d54aadda01ecd0961eed742bd7d43838e4952740c9d300cd34fc52729"
ANDROID_FRAGMENT_SHA256 = "60dec6885b030ba5a4f3287b80e58d51a046fcf905cba2db67122bda7b8f4d74"
ANDROID_RUNTIME_SHA256 = "964586ac5953ad5e5e781a917890c68b60d8319b6de6b55552cd14c0a9c0b105"
BACKEND_DOCKERFILE = Path("/usr/local/libexec/atenea/atenea-backend-test-v2.Dockerfile")
BACKEND_PREPARER = Path("/usr/local/libexec/atenea/atenea-backend-test-v2.py")
BACKEND_DOCKERFILE_SHA256 = "8e9464d3cf93e8100b60deec53ee91974dca2565bb15002b88cedfa41e551fa4"
BACKEND_PREPARER_SHA256 = "0dc8b1856a67e13c3eb35fb4c3637dd7f19a1df3049db7051da8747b8b7c790f"
BACKEND_POM_SHA256 = "948f346ea55fa1a3b124a7a742b52cb1fdb037c4a3efd0b4aee6ff7b01556a6f"
WEB_DOCKERFILE = Path("/usr/local/libexec/atenea/atenea-web-validation-v1.Dockerfile")
WEB_RUNTIME = Path("/usr/local/libexec/atenea/atenea-web-runtime-v1.py")
WEB_DOCKERFILE_SHA256 = "e8d0a10e39aea1ecf49869cc7596717bf54cdf472d19dd28a8f725d2f6d9c34f"
WEB_RUNTIME_SHA256 = "ccd154a0ccc7a87a91d4a1a36dbd863fcc8f9f45fd355fd00bfe8a2aaab2126f"
WEB_INPUTS = {
    "web/package.json": "6dff9531573c26f3143cfbf8849308dded874d13362a686517c7dd2f9383a5f3",
    "web/package-lock.json": "62ea4d444da58e7e27bd83cb53ebcf49bcc9bf27dd5641e3d12ed8dd86ff21bc",
    "scripts/web-build.sh": "afaa847d2171e7ba5a7258384e2501d63945138a21e186fa755c835215ba8f7b",
}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DURABLE_PROTOCOL = "closed-validation-broker/v1"
DURABLE_NON_TERMINAL = {"QUEUED", "RUNNING", "CANCELLING", "RECONCILING"}
DURABLE_TERMINAL = {
    "SUCCEEDED", "CANDIDATE_FAILED", "INFRASTRUCTURE_FAILED",
    "POLICY_FAILED", "VALIDATION_FAILED", "OWNERSHIP_FAILED", "CANCELLED",
}


@dataclasses.dataclass(frozen=True)
class Definition:
    revision: str
    timeout: int
    cpu_quota: str
    memory_max: str
    tasks_max: int
    storage_max: str
    runner: str


# This is the complete privileged catalog. No command, path, host, slot, image,
# or resource bound is accepted from the worker client.
DEFINITIONS = {
    "BACKEND_TEST": Definition(
        "atenea-backend-test-v2", 900, "200%", "4G", 512, "6G", "backend"
    ),
    "WEB_BUILD": Definition(
        "atenea-web-build-v1", 600, "200%", "3G", 512, "4G", "web"
    ),
    "ANDROID_BUILD": Definition(
        "atenea-android-build-v2", 1200, "400%", "10G", 2048, "12G", "android"
    ),
    "PLAYWRIGHT_ACCEPTANCE": Definition(
        "atenea-playwright-acceptance-v1",
        600,
        "200%",
        "3G",
        512,
        "4G",
        "playwright",
    ),
}

PROJECT_CONFIG_KEYS = {
    "schemaVersion",
    "selectionEnabled",
    "executionEnabled",
    "projectId",
    "repository",
    "branch",
    "commit",
    "manifestSha256",
    "runner",
    "attachmentRoot",
    "workspaces",
}
WORKSPACE_KEYS = {"sessionId", "worktree", "allocationSha256", "canonicalCommit"}
ALLOCATION_KEYS = {
    "schemaVersion",
    "sessionId",
    "projectId",
    "branch",
    "mirrorPath",
    "worktreePath",
    "runtimeId",
    "manifestRelativePath",
    "slot",
    "workloadClass",
    "state",
    "runtimeNames",
    "runtimeRoot",
    "logsPath",
    "artifactsRoot",
    "cacheRoot",
    "allocatedPorts",
}


class Rejected(RuntimeError):
    pass


def reject() -> NoReturn:
    raise Rejected("validation authority rejected")


def require_root() -> None:
    if os.geteuid() != 0:
        reject()


def canonical_uuid(value: str) -> bool:
    if UUID_RE.fullmatch(value) is None:
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def exact_regular_file(path: Path, mode: int, uid: int = 0, gid: int = 0) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return False
    return (
        path.is_file()
        and not path.is_symlink()
        and stat.st_uid == uid
        and stat.st_gid == gid
        and stat.st_mode & 0o7777 == mode
    )


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        reject()
    if not isinstance(value, dict):
        reject()
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_output(command: list[str]) -> str:
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        reject()


def git_observation_command(worktree: Path, arguments: list[str]) -> list[str]:
    return [
        "/usr/bin/git",
        "-c",
        f"safe.directory={worktree}",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(worktree),
        *arguments,
    ]


def slot_authority(slot: str) -> tuple[str, int, Path, Path]:
    if re.fullmatch(r"slot[1-4]", slot) is None:
        reject()
    slot_user = f"atenea-{slot}"
    try:
        account = pwd.getpwnam(slot_user)
    except KeyError:
        reject()
    expected_uid = 1100 + int(slot.removeprefix("slot"))
    slot_home = Path(f"/var/lib/atenea-slots/{slot}")
    if (
        account.pw_uid != expected_uid
        or account.pw_gid != expected_uid
        or Path(account.pw_dir) != slot_home
    ):
        reject()
    return slot_user, account.pw_uid, slot_home, Path(f"/run/user/{account.pw_uid}/docker.sock")


def load_source_authority() -> dict[str, Any]:
    if not exact_regular_file(SOURCE_AUTHORITY_MEDIATOR, 0o755, uid=0, gid=0):
        reject()
    return runpy.run_path(str(SOURCE_AUTHORITY_MEDIATOR))


def resolve_authority(
    session_id: str, workspace_identity: str
) -> tuple[Path, tuple[str, int, Path, Path] | None, str]:
    change_prefix = "remote:ax42-01:change:"
    if workspace_identity.startswith(change_prefix):
        change_key = workspace_identity.removeprefix(change_prefix)
        if not canonical_uuid(change_key):
            reject()
        root = CHANGE_WORKSPACE_ROOT / change_key
        worktree = root / "atenea"
        record_path = root / "workspace-v1.json"
        try:
            worker_account = pwd.getpwnam(WORKER_USER)
            worker_uid = worker_account.pw_uid
            # Match the fixed systemd Group=atenea and SGID workspace parent,
            # not the account's potentially different login/primary group.
            worker_gid = grp.getgrnam("atenea").gr_gid
        except KeyError:
            reject()
        if not exact_regular_file(record_path, 0o600, uid=worker_uid, gid=worker_gid):
            reject()
        record = load_json(record_path)
        if (
            set(record) not in ({
                "schemaVersion", "protocolVersion", "changeKey", "databaseProjectId",
                "projectId", "baseCommit", "workspaceBranch", "workspaceIdentity", "workerId",
            }, {
                "schemaVersion", "protocolVersion", "changeKey", "databaseProjectId",
                "projectId", "repository", "repositoryBranch", "baseCommit",
                "workspaceBranch", "workspaceIdentity", "workerId",
                "initialSourceFingerprintSha256", "recordSha256",
            })
            or record.get("schemaVersion") != 1
            or record.get("protocolVersion") != "development-change-workspace/v1"
            or record.get("changeKey") != change_key
            or record.get("projectId") != "atenea"
            or record.get("workspaceIdentity") != workspace_identity
            or record.get("workspaceBranch") != f"atenea/change-{change_key}"
            or record.get("workerId") != "ax42-01"
            or not COMMIT_RE.fullmatch(str(record.get("baseCommit", "")))
        ):
            reject()
        try:
            observed = worktree.lstat()
        except OSError:
            reject()
        if not worktree.is_dir() or worktree.is_symlink() or observed.st_uid != worker_uid:
            reject()
        try:
            expected_commit = record["baseCommit"]
            if (root / "source-update-v1.json").exists() or (root / "source-update-v1.json").is_symlink():
                expected_commit = load_source_authority()["approved_validation_commit"](root, record, worker_uid, worker_gid)
        except Exception:
            reject()
        return worktree, None, expected_commit

    if workspace_identity != f"remote:ax42-01:work-session:{session_id}":
        reject()
    if not exact_regular_file(CONFIG, 0o644):
        reject()
    config = load_json(CONFIG)
    # The installer owns this exact schema. Surplus authority fails closed.
    accepted_config_keys = {
        frozenset(PROJECT_CONFIG_KEYS),
        frozenset(PROJECT_CONFIG_KEYS - {"attachmentRoot"}),
    }
    if frozenset(config) not in accepted_config_keys:
        reject()
    identity = f"remote:ax42-01:work-session:{session_id}"
    worktree = WORKSPACE_ROOT / session_id / "atenea"
    workspace = config.get("workspaces", {}).get(identity)
    if (
        config.get("schemaVersion") != "project-codex-v1"
        or config.get("projectId") != "atenea"
        or config.get("repository") != "https://github.com/jlnieto/atenea.git"
        or config.get("branch") != "main"
        or not isinstance(workspace, dict)
        or set(workspace) != WORKSPACE_KEYS
        or workspace.get("sessionId") != session_id
        or workspace.get("worktree") != str(worktree)
        or not COMMIT_RE.fullmatch(str(workspace.get("canonicalCommit", "")))
        or not SHA256_RE.fullmatch(str(workspace.get("allocationSha256", "")))
        or workspace.get("canonicalCommit") != config.get("commit")
    ):
        reject()
    try:
        if not worktree.is_dir() or worktree.is_symlink():
            reject()
    except OSError:
        reject()

    allocation_path = WORKSPACE_ROOT / session_id / "runtime-allocation-v1.json"
    if allocation_path.is_symlink() or not allocation_path.is_file():
        reject()
    if sha256_file(allocation_path) != workspace["allocationSha256"]:
        reject()
    allocation = load_json(allocation_path)
    # The identity and selected slot remain exact and server-derived.
    allocation_keys = set(allocation)
    if allocation.get("workloadClass") == "heavy":
        expected_allocation_keys = ALLOCATION_KEYS | {"heavyPermit"}
    else:
        expected_allocation_keys = ALLOCATION_KEYS
    if (
        allocation_keys != expected_allocation_keys
        or allocation.get("schemaVersion") != 1
        or allocation.get("sessionId") != session_id
        or allocation.get("projectId") != "atenea"
        or allocation.get("worktreePath") != str(worktree)
        or allocation.get("state") != "allocated"
    ):
        reject()
    slot = allocation.get("slot")
    if not isinstance(slot, str) or re.fullmatch(r"slot[1-4]", slot) is None:
        reject()
    return worktree, slot_authority(slot), config["commit"]


def admission_call(operation: str, session_id: str) -> dict[str, Any]:
    if operation not in {"acquire-normal", "acquire-heavy", "release-heavy", "release-normal"}:
        reject()
    completed = subprocess.run(
        [
            "/usr/sbin/runuser", "-u", WORKER_USER, "--",
            str(RUNTIME_ADMISSION), "--json", operation, session_id,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=45,
        check=False,
    )
    if completed.returncode != 0:
        reject()
    try:
        response = json.loads(completed.stdout)
    except (json.JSONDecodeError, UnicodeError):
        reject()
    if not isinstance(response, dict) or response.get("sessionId") != session_id:
        reject()
    return response


@contextmanager
def validation_slot(
    session_id: str,
    definition: Definition,
    retained: tuple[str, int, Path, Path] | None,
) -> Iterator[tuple[str, int, Path, Path]]:
    if retained is not None:
        yield retained
        return
    normal = admission_call("acquire-normal", session_id)
    record = normal.get("record")
    slot = record.get("normal", {}).get("slot") if isinstance(record, dict) else None
    if not isinstance(slot, str):
        reject()
    heavy = definition.runner in {"android", "playwright"}
    heavy_acquired = False
    try:
        if heavy:
            admission_call("acquire-heavy", session_id)
            heavy_acquired = True
        yield slot_authority(slot)
    finally:
        if heavy_acquired:
            try:
                admission_call("release-heavy", session_id)
            finally:
                admission_call("release-normal", session_id)
        else:
            admission_call("release-normal", session_id)


def sandbox_command(
    operation: str,
    validation_id: str,
    definition: Definition,
    slot_user: str,
    slot_uid: int,
    source_root: Path,
    artifact_stage: Path,
    resolv_path: Path,
) -> list[str]:
    unit = "atenea-validation-sandbox-" + validation_id.replace("-", "")
    helper = Path(__file__).resolve()
    runtime_limit = 300 if definition.runner == "playwright" else definition.timeout
    tmpfs = (
        f"/work:rw,nosuid,nodev,size={definition.storage_max},"
        f"mode=0700,uid={slot_uid},gid={slot_uid}"
    )
    # Do not mask the outer /proc with ProtectKernelTunables/ProtectKernelLogs:
    # that prevents rootless Bubblewrap from mounting its own PID-namespace /proc.
    # Candidate code stays inside Bubblewrap, not a bind of the host /proc.
    command = [
        "/usr/bin/systemd-run",
        "--wait",
        "--pipe",
        "--collect",
        "--quiet",
        "--service-type=exec",
        "--unit",
        unit,
        "--property",
        f"User={slot_user}",
        "--property",
        f"Group={slot_user}",
        "--property",
        f"CPUQuota={definition.cpu_quota}",
        "--property",
        f"MemoryMax={definition.memory_max}",
        "--property",
        f"TasksMax={definition.tasks_max}",
        "--property",
        f"RuntimeMaxSec={runtime_limit}s",
        "--property",
        "LimitFSIZE=67108864",
        "--property",
        f"TemporaryFileSystem={tmpfs}",
        "--property",
        f"BindReadOnlyPaths={source_root}:/source",
        "--property",
        f"BindReadOnlyPaths={resolv_path}:/validation-resolv.conf",
        "--property",
        f"BindPaths={artifact_stage}:/artifacts",
        "--property",
        "NoNewPrivileges=yes",
        "--property",
        "PrivateDevices=yes",
        "--property",
        "ProtectSystem=strict",
        "--property",
        "ProtectHome=yes",
        "--property",
        "ProtectKernelModules=yes",
        "--property",
        "ProtectControlGroups=yes",
        "--property",
        "RestrictSUIDSGID=yes",
        "--property",
        "LockPersonality=yes",
        "--property",
        "RestrictRealtime=yes",
        "--property",
        "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
    ]
    for cidr in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ):
        command.extend(("--property", f"IPAddressDeny={cidr}"))
    command.extend(
        (
            "--",
            "/usr/bin/python3",
            str(helper),
            "--sandbox-supervise",
            operation,
        )
    )
    return command


def bubblewrap_command(operation: str) -> list[str]:
    helper = Path(__file__).resolve()
    return [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--share-net",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/sbin",
        "/sbin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--dir",
        "/etc",
        "--ro-bind",
        "/etc/alternatives",
        "/etc/alternatives",
        "--ro-bind",
        "/etc/java-21-openjdk",
        "/etc/java-21-openjdk",
        "--ro-bind",
        "/etc/ssl",
        "/etc/ssl",
        "--ro-bind",
        "/validation-resolv.conf",
        "/etc/resolv.conf",
        "--ro-bind",
        "/etc/hosts",
        "/etc/hosts",
        "--ro-bind",
        "/etc/nsswitch.conf",
        "/etc/nsswitch.conf",
        "--ro-bind",
        "/etc/passwd",
        "/etc/passwd",
        "--ro-bind",
        "/etc/group",
        "/etc/group",
        "--ro-bind",
        "/source",
        "/source",
        "--bind",
        "/work",
        "/work",
        "--symlink",
        "work/tmp",
        "/tmp",
        "--ro-bind",
        str(helper),
        "/runner.py",
        "--setenv",
        "HOME",
        "/work/home",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--chdir",
        "/work",
        "/usr/bin/python3",
        "/runner.py",
        "--sandbox-exec",
        operation,
    ]


def clean_environment() -> dict[str, str]:
    return {
        "HOME": "/work/home",
        "TMPDIR": "/work/tmp",
        "USER": str(pwd.getpwuid(os.getuid()).pw_name),
        "LOGNAME": str(pwd.getpwuid(os.getuid()).pw_name),
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def sandbox_operation_command(operation: str) -> tuple[str, ...]:
    command = {
        "WEB_BUILD": ("./scripts/web-build.sh",),
        "PLAYWRIGHT_ACCEPTANCE": ("./scripts/web-build.sh",),
    }.get(operation)
    if command is None or DEFINITIONS[operation].runner not in {"sandbox", "playwright"}:
        reject()
    return command


@dataclasses.dataclass(frozen=True)
class RunOutcome:
    exit_code: int
    phase: str
    error_code: str
    failure_class: str


class RuntimeFailure(RuntimeError):
    def __init__(self, outcome: RunOutcome):
        super().__init__(outcome.error_code)
        self.outcome = outcome


def bounded_output(path: Path) -> str:
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        return stream.read(65536).decode("utf-8", errors="replace")


def classify_execution(exit_code: int, output: str, phase: str) -> RunOutcome:
    if exit_code == 0:
        return RunOutcome(0, phase, "NONE", "NONE")
    if exit_code in {124, 137}:
        return RunOutcome(exit_code, phase, "RESOURCE_LIMIT", "INFRASTRUCTURE")
    if phase == "WEB_BUILD":
        if exit_code == 127:
            return RunOutcome(exit_code, "TOOLCHAIN", "TEST_TOOLCHAIN_UNAVAILABLE", "INFRASTRUCTURE")
        if re.search(r"error TS[0-9]+:|error during build:", output):
            return RunOutcome(exit_code, "COMPILATION", "COMPILATION_FAILED", "CANDIDATE")
    if re.search(r"(?m)^(?:bwrap:|Failed to (?:start|mount)|Error occurred during initialization of VM)", output):
        return RunOutcome(exit_code, "SANDBOX", "SANDBOX_SETUP_FAILED", "INFRASTRUCTURE")
    if phase == "ANDROID_BUILD" and any(marker in output for marker in (
        "No cached version of", "No cached resource available for offline mode",
        "Could not resolve plugin artifact", "was not found in any of the following sources",
    )):
        return RunOutcome(exit_code, "DEPENDENCIES", "TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE")
    if phase == "ANDROID_BUILD":
        if "Compilation error" in output or "Compilation failed" in output:
            return RunOutcome(exit_code, "COMPILATION", "COMPILATION_FAILED", "CANDIDATE")
        if "There were failing tests" in output:
            return RunOutcome(exit_code, "TESTS", "TESTS_FAILED", "CANDIDATE")
    if phase == "BACKEND_TEST":
        if any(marker in output for marker in (
            "Could not resolve dependencies", "has not been downloaded",
            "Cannot access central", "could not be resolved",
        )):
            return RunOutcome(exit_code, "DEPENDENCIES", "TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE")
        if "COMPILATION ERROR" in output:
            return RunOutcome(exit_code, "COMPILATION", "COMPILATION_FAILED", "CANDIDATE")
        if "There are test failures" in output or re.search(r"Failures: [1-9]|Errors: [1-9]", output):
            return RunOutcome(exit_code, "TESTS", "TESTS_FAILED", "CANDIDATE")
    # An unexplained nonzero exit is not evidence of a candidate defect.
    return RunOutcome(exit_code, phase, "EXECUTION_FAILED", "VALIDATION")


def sandbox_exec(operation: str) -> int:
    if os.geteuid() == 0 or operation not in DEFINITIONS:
        reject()
    source = Path("/source")
    if not source.is_dir() or source.is_symlink():
        reject()
    worktree = prepare_sandbox_directories(Path("/work"))
    shutil.copytree(source, worktree, symlinks=True)
    environment = clean_environment()
    command = sandbox_operation_command(operation)
    completed = subprocess.run(
        command,
        cwd=worktree,
        env=environment,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode


def prepare_sandbox_directories(work_root: Path) -> Path:
    worktree = work_root / "repo"
    home = work_root / "home"
    temporary = work_root / "tmp"
    if any(path.exists() or path.is_symlink() for path in (worktree, home, temporary)):
        reject()
    home.mkdir(mode=0o700)
    temporary.mkdir(mode=0o700)
    return worktree


def sandbox_supervise(operation: str) -> int:
    if os.geteuid() == 0 or operation not in DEFINITIONS:
        reject()
    sandbox_operation_command(operation)
    completed = subprocess.run(
        bubblewrap_command(operation),
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode == 0 and operation == "PLAYWRIGHT_ACCEPTANCE":
        static = Path("/work/repo/src/main/resources/static")
        target = Path("/artifacts/static")
        if target.exists() or not (static / "index.html").is_file():
            reject()
        shutil.copytree(static, target, symlinks=True)
    return completed.returncode


def docker_slot_prefix(slot_user: str, slot_uid: int, socket: Path, client_config: Path) -> list[str]:
    return [
        "/usr/sbin/runuser",
        "-u",
        slot_user,
        "--",
        "/usr/bin/env",
        "-i",
        "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
        f"HOME=/var/lib/atenea-slots/slot{slot_uid - 1100}",
        f"XDG_RUNTIME_DIR=/run/user/{slot_uid}",
        f"DOCKER_HOST=unix://{socket}",
        f"DOCKER_CONFIG={client_config}",
        "/usr/bin/docker",
    ]


def limit_validation_output() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))


def docker_call(
    prefix: list[str],
    arguments: list[str],
    timeout: int,
    output: IO[str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    if output is not None and capture:
        raise ValueError("docker output mode is ambiguous")
    return subprocess.run(
        [*prefix, *arguments],
        stdin=subprocess.DEVNULL,
        stdout=(
            subprocess.PIPE
            if capture
            else output if output is not None else subprocess.DEVNULL
        ),
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        preexec_fn=limit_validation_output,
        check=False,
    )


def run_backend(
    prefix: list[str], validation_id: str, source_root: Path,
    definition: Definition, output: IO[str],
) -> RunOutcome:
    deadline = time.monotonic() + definition.timeout

    def remaining(cap: int) -> float:
        value = min(float(cap), deadline - time.monotonic())
        if value <= 0:
            raise subprocess.TimeoutExpired(prefix, definition.timeout)
        return value

    for path, digest in (
        (BACKEND_DOCKERFILE, BACKEND_DOCKERFILE_SHA256),
        (BACKEND_PREPARER, BACKEND_PREPARER_SHA256),
    ):
        if not exact_regular_file(path, 0o644) or sha256_file(path) != digest:
            return RunOutcome(70, "TOOLCHAIN", "INSTALLED_TOOLCHAIN_INVALID", "INFRASTRUCTURE")
    pom = source_root / "pom.xml"
    if pom.is_symlink() or not pom.is_file() or sha256_file(pom) != BACKEND_POM_SHA256:
        return RunOutcome(64, "TOOLCHAIN", "UNSUPPORTED_DEPENDENCY_MANIFEST", "POLICY")
    if any((source_root / ".mvn" / name).exists() or (source_root / ".mvn" / name).is_symlink()
           for name in ("maven.config", "jvm.config", "extensions.xml")):
        return RunOutcome(64, "TOOLCHAIN", "UNSUPPORTED_DEPENDENCY_MANIFEST", "POLICY")

    context = source_root.parent / "backend-build"
    context.mkdir(mode=0o700)
    for source, name in ((BACKEND_DOCKERFILE, "Dockerfile"),
                         (BACKEND_PREPARER, "atenea-backend-test-v2.py"), (pom, "pom.xml")):
        shutil.copyfile(source, context / name)
    slot_user = prefix[prefix.index("-u") + 1]
    make_slot_readable(context, pwd.getpwnam(slot_user).pw_gid)
    image = f"atenea-backend-validation:{validation_id}"
    built = docker_call(prefix, ["build", "--network", "default", "--memory", "4g",
                        "--cpu-quota", "200000", "--tag", image,
                        "--label", f"com.atenea.validation-id={validation_id}", str(context)],
                        remaining(definition.timeout), output)
    if built.returncode != 0:
        return RunOutcome(built.returncode, "TOOLCHAIN", "TEST_TOOLCHAIN_BUILD_FAILED", "INFRASTRUCTURE")
    container_id = None
    image_id = None
    try:
        inspected = docker_call(prefix, ["image", "inspect", "--format", "{{.Id}}", image],
                                remaining(30), capture=True)
        image_id = str(inspected.stdout).strip()
        if inspected.returncode != 0 or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            return RunOutcome(70, "TOOLCHAIN", "TEST_IMAGE_INVALID", "INFRASTRUCTURE")
        created = docker_call(prefix, [
            "create", "--name", "atenea-backend-" + validation_id.replace("-", ""),
            "--label", f"com.atenea.validation-id={validation_id}",
            "--label", "com.atenea.validation=backend-v2",
            "--network", "none", "--user", "1000:0", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--read-only",
            "--cpus", "2", "--memory", definition.memory_max.lower(),
            "--pids-limit", str(definition.tasks_max),
            "--tmpfs", "/work:rw,nosuid,nodev,size=5g,uid=1000,gid=0,mode=0700",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
            "--mount", f"type=bind,src={source_root},dst=/source,readonly",
            "--env", "SPRING_DATASOURCE_URL=jdbc:postgresql://127.0.0.1:5432/atenea_test",
            "--env", "SPRING_DATASOURCE_USERNAME=atenea",
            "--env", "SPRING_DATASOURCE_PASSWORD=atenea",
            "--env", "SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=0",
            "--env", "SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=5",
            "--env", "ATENEA_WORKSPACE_ROOT=/workspace/repos",
            image_id, "/bin/sleep", "infinity",
        ], remaining(30), capture=True)
        candidate_id = str(created.stdout).strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", candidate_id) is None:
            return RunOutcome(70, "CONTAINER", "TEST_CONTAINER_CREATE_FAILED", "INFRASTRUCTURE")
        container_id = candidate_id
        started = docker_call(prefix, ["start", container_id], remaining(30), output)
        if started.returncode != 0:
            return RunOutcome(started.returncode, "CONTAINER", "TEST_CONTAINER_START_FAILED", "INFRASTRUCTURE")
        prepared = docker_call(prefix, ["exec", container_id, "/usr/bin/python3",
                              "/opt/atenea-backend-test-v2.py", "--prepare"], remaining(120), output)
        if prepared.returncode != 0:
            return RunOutcome(prepared.returncode, "TEST_DATABASE", "TEST_DATABASE_SETUP_FAILED", "INFRASTRUCTURE")
        tested = docker_call(prefix, ["exec", "--workdir", "/work/repo", container_id,
                            "/usr/share/maven/bin/mvn", "--offline", "-B", "-q",
                            "-Dmaven.repo.local=/work/m2", "test"], remaining(definition.timeout), output)
        output.flush()
        return classify_execution(tested.returncode, bounded_output(Path(output.name)), "BACKEND_TEST")
    finally:
        cleanup_failed = False
        try:
            if container_id is not None:
                cleanup_failed = docker_call(prefix, ["rm", "--force", container_id], 60).returncode != 0
            # A tag may move. Delete only the immutable image identity observed
            # for this operation, never a foreign or unverified tag.
            if image_id is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
                cleanup_failed |= docker_call(prefix, ["image", "rm", image_id], 60).returncode != 0
        except (OSError, subprocess.SubprocessError):
            cleanup_failed = True
        if cleanup_failed:
            raise RuntimeFailure(RunOutcome(70, "CLEANUP", "TEST_RUNTIME_CLEANUP_FAILED", "INFRASTRUCTURE"))


def web_build_inputs(source_root: Path) -> dict[str, bytes] | None:
    # npm config/shrinkwrap cannot override the reviewed lock or registry.
    if any((source_root / name).exists() or (source_root / name).is_symlink()
           for name in (".npmrc", "web/.npmrc", "web/npm-shrinkwrap.json")):
        return None
    result = {}
    for name, digest in WEB_INPUTS.items():
        path = source_root
        for part in Path(name).parts:
            path = path / part
            if path.is_symlink():
                return None
        if not path.is_file() or path.stat().st_size > 256 * 1024:
            return None
        value = path.read_bytes()
        if hashlib.sha256(value).hexdigest() != digest:
            return None
        result[name] = value
    return result


def receive_web_static(value: str, stage: Path, slot_gid: int) -> bool:
    # Never extract a candidate tar or follow candidate links on the host.
    # Validate the complete bounded projection before materializing files in
    # one server-owned scratch subtree; clients do not select output paths.
    if len(value) > 24 * 1024 * 1024:
        return False
    try:
        projection = json.loads(value)
        if set(projection) != {"schemaVersion", "files"} or projection["schemaVersion"] != 1:
            return False
        files = projection["files"]
        if not isinstance(files, dict) or not files.get("index.html") or len(files) > 512:
            return False
        decoded = {}
        total = 0
        for name, encoded in files.items():
            if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}", name) is None:
                return False
            if any(part in {"", ".", ".."} for part in name.split("/")):
                return False
            data = base64.b64decode(encoded, validate=True)
            total += len(data)
            if total > 16 * 1024 * 1024:
                return False
            decoded[name] = data
        if any(parent.as_posix() in decoded for name in decoded for parent in Path(name).parents
               if parent != Path(".")):
            return False
    except (ValueError, TypeError, KeyError):
        return False
    destination = stage / "static"
    if destination.exists() or destination.is_symlink():
        return False
    destination.mkdir(mode=0o700)
    for name, data in decoded.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    make_slot_readable(destination, slot_gid)
    return True


def run_web(
    prefix: list[str], validation_id: str, source_root: Path,
    definition: Definition, stage: Path, output: IO[str],
) -> RunOutcome:
    deadline = time.monotonic() + definition.timeout
    def remaining(cap: int) -> float:
        value = min(float(cap), deadline - time.monotonic())
        if value <= 0:
            raise subprocess.TimeoutExpired(prefix, definition.timeout)
        return value
    for path, digest in ((WEB_DOCKERFILE, WEB_DOCKERFILE_SHA256), (WEB_RUNTIME, WEB_RUNTIME_SHA256)):
        if not exact_regular_file(path, 0o644) or sha256_file(path) != digest:
            return RunOutcome(70, "TOOLCHAIN", "INSTALLED_TOOLCHAIN_INVALID", "INFRASTRUCTURE")
    inputs = web_build_inputs(source_root)
    if inputs is None:
        return RunOutcome(64, "TOOLCHAIN", "UNSUPPORTED_DEPENDENCY_MANIFEST", "POLICY")
    context = source_root.parent / "web-build"
    context.mkdir(mode=0o700)
    # Only npm manifests and root-owned recipes cross the network boundary.
    for name in ("package.json", "package-lock.json"):
        (context / name).write_bytes(inputs["web/" + name])
    shutil.copyfile(WEB_DOCKERFILE, context / "Dockerfile")
    shutil.copyfile(WEB_RUNTIME, context / "atenea-web-runtime-v1.py")
    slot_user = prefix[prefix.index("-u") + 1]
    slot_gid = pwd.getpwnam(slot_user).pw_gid
    make_slot_readable(context, slot_gid)
    image = "atenea-web-validation:" + validation_id
    built = docker_call(prefix, ["build", "--network", "default", "--memory", "3g",
                        "--cpu-quota", "200000", "--tag", image,
                        "--label", f"com.atenea.validation-id={validation_id}", str(context)],
                        remaining(definition.timeout), output)
    if built.returncode != 0:
        return RunOutcome(built.returncode, "TOOLCHAIN", "TEST_TOOLCHAIN_BUILD_FAILED", "INFRASTRUCTURE")
    container_id = None
    image_id = None
    try:
        inspected = docker_call(prefix, ["image", "inspect", "--format", "{{.Id}}", image], remaining(30), capture=True)
        image_id = str(inspected.stdout).strip()
        if inspected.returncode != 0 or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            return RunOutcome(70, "TOOLCHAIN", "TEST_IMAGE_INVALID", "INFRASTRUCTURE")
        created = docker_call(prefix, [
            "create", "--name", "atenea-web-" + validation_id.replace("-", ""),
            "--label", f"com.atenea.validation-id={validation_id}",
            "--label", "com.atenea.validation=web-v1",
            "--network", "none", "--user", "1000:0", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--read-only",
            "--cpus", "2", "--memory", definition.memory_max.lower(),
            "--pids-limit", str(definition.tasks_max),
            "--tmpfs", "/work:rw,exec,nosuid,nodev,size=4g,uid=1000,gid=0,mode=0700",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=256m,uid=1000,gid=0,mode=0700",
            "--mount", f"type=bind,src={source_root},dst=/source,readonly",
            image_id, "/bin/sleep", "infinity",
        ], remaining(30), capture=True)
        candidate_id = str(created.stdout).strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", candidate_id) is None:
            return RunOutcome(70, "CONTAINER", "TEST_CONTAINER_CREATE_FAILED", "INFRASTRUCTURE")
        container_id = candidate_id
        started = docker_call(prefix, ["start", container_id], remaining(30), output)
        if started.returncode != 0:
            return RunOutcome(started.returncode, "CONTAINER", "TEST_CONTAINER_START_FAILED", "INFRASTRUCTURE")
        prepared = docker_call(prefix, ["exec", container_id, "/usr/bin/python3",
                              "/opt/atenea-web-runtime-v1.py", "--prepare"], remaining(120), output)
        if prepared.returncode != 0:
            return RunOutcome(prepared.returncode, "DEPENDENCIES", "TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE")
        tested = docker_call(prefix, ["exec", "--workdir", "/work/repo", container_id,
                            "/bin/bash", "./scripts/web-build.sh"], remaining(definition.timeout), output)
        output.flush()
        outcome = classify_execution(tested.returncode, bounded_output(Path(output.name)), "WEB_BUILD")
        if outcome.exit_code:
            return outcome
        exported = docker_call(prefix, ["exec", container_id, "/usr/bin/python3",
                              "/opt/atenea-web-runtime-v1.py", "--export-static"], remaining(30), capture=True)
        if exported.returncode != 0 or not receive_web_static(exported.stdout, stage, slot_gid):
            return RunOutcome(70, "ARTIFACTS", "WEB_BUILD_OUTPUT_INVALID", "VALIDATION")
        return outcome
    finally:
        cleanup_failed = False
        try:
            if container_id is not None:
                cleanup_failed = docker_call(prefix, ["rm", "--force", container_id], 60).returncode != 0
            if image_id is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
                cleanup_failed |= docker_call(prefix, ["image", "rm", image_id], 60).returncode != 0
        except (OSError, subprocess.SubprocessError):
            cleanup_failed = True
        if cleanup_failed:
            raise RuntimeFailure(RunOutcome(70, "CLEANUP", "TEST_RUNTIME_CLEANUP_FAILED", "INFRASTRUCTURE"))


def normalized_android_application(value: bytes) -> bytes | None:
    # APK labels are not toolchain versions. Only plain numeric literals may
    # vary; all executable Gradle structure remains hash-locked. The trusted
    # prefetch build always receives these fixed synthetic labels.
    patterns = (
        (rb"(?m)^        versionCode = [1-9][0-9]{0,8}$", b"        versionCode = 1"),
        (rb'(?m)^        versionName = "[0-9]{1,4}\.[0-9]{1,6}\.[0-9]{1,6}"$',
         b'        versionName = "0.0.0"'),
    )
    for pattern, replacement in patterns:
        value, count = re.subn(pattern, replacement, value)
        if count != 1:
            return None
    return value


def android_build_inputs(source_root: Path) -> dict[str, bytes] | None:
    # Groovy alternatives/buildSrc can override a reviewed .kts graph. Lock
    # all automatically adopted build authority, not merely the primary files.
    roots = ("android", "android/app", "android/api", "android/secure",
             "android/core-console", "android/voice-runtime")
    forbidden = [source_root / root / name for root in roots for name in (
        "build.gradle", "settings.gradle", "buildSrc", "gradle.lockfile")]
    forbidden += [source_root / "android/gradle" / name for name in (
        "verification-metadata.xml", "dependency-locks")]
    if any(path.exists() or path.is_symlink() for path in forbidden):
        return None
    manifest = load_json(ANDROID_INPUTS)
    common = manifest["common"]
    for bundle in manifest["bundles"]:
        expected = {**common, **bundle["files"]}
        observed = {}
        for name, digest in expected.items():
            # The root-owned, hash-locked manifest is the authority. Never
            # follow a candidate link, including links in parent components.
            current = source_root
            valid = True
            for part in Path(name).parts:
                current = current / part
                if current.is_symlink():
                    valid = False
                    break
            if not valid or not current.is_file() or current.stat().st_size > 256 * 1024:
                break
            value = current.read_bytes()
            if name == "android/app/build.gradle.kts":
                value = normalized_android_application(value)
                if value is None:
                    break
            if hashlib.sha256(value).hexdigest() != digest:
                break
            observed[name] = value
        if len(observed) == len(expected):
            return observed
    return None


def run_android(
    prefix: list[str],
    validation_id: str,
    source_root: Path,
    definition: Definition,
    output: IO[str],
) -> RunOutcome:
    deadline = time.monotonic() + definition.timeout

    def remaining(cap: int) -> float:
        value = min(float(cap), deadline - time.monotonic())
        if value <= 0:
            raise subprocess.TimeoutExpired(prefix, definition.timeout)
        return value

    for path, digest in ((ANDROID_INPUTS, ANDROID_INPUTS_SHA256),
                         (ANDROID_FRAGMENT, ANDROID_FRAGMENT_SHA256),
                         (ANDROID_RUNTIME, ANDROID_RUNTIME_SHA256)):
        if not exact_regular_file(path, 0o644) or sha256_file(path) != digest:
            return RunOutcome(70, "TOOLCHAIN", "INSTALLED_TOOLCHAIN_INVALID", "INFRASTRUCTURE")
    inputs = android_build_inputs(source_root)
    if inputs is None:
        return RunOutcome(64, "TOOLCHAIN", "UNSUPPORTED_DEPENDENCY_MANIFEST", "POLICY")
    context = source_root.parent / "android-build"
    context.mkdir(mode=0o700)
    for name, value in inputs.items():
        if name == "docker/android-builder.Dockerfile":
            continue
        destination = context / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value)
    (context / "Dockerfile").write_bytes(
        inputs["docker/android-builder.Dockerfile"] + b"\n" + ANDROID_FRAGMENT.read_bytes())
    shutil.copyfile(ANDROID_RUNTIME, context / "atenea-android-runtime-v2.py")
    slot_user = prefix[prefix.index("-u") + 1]
    make_slot_readable(context, pwd.getpwnam(slot_user).pw_gid)
    # Only these reviewed configurations and synthetic trusted probes execute
    # with network. Source, buildSrc, init scripts and secrets are not inputs.
    image = f"atenea-android-validation:{validation_id}"
    build = docker_call(
        prefix,
        [
            "build",
            "--network",
            "default",
            "--memory",
            definition.memory_max.lower(),
            "--cpu-quota",
            "400000",
            "--ulimit",
            f"nproc={definition.tasks_max}:{definition.tasks_max}",
            "--tag",
            image,
            "--label",
            "com.atenea.validation=android-builder-v2",
            "--label",
            f"com.atenea.validation-id={validation_id}",
            str(context),
        ],
        remaining(definition.timeout),
        output,
    )
    if build.returncode != 0:
        return RunOutcome(build.returncode, "TOOLCHAIN", "TEST_TOOLCHAIN_BUILD_FAILED", "INFRASTRUCTURE")
    container_id = None
    image_id = None
    try:
        inspected = docker_call(prefix, ["image", "inspect", "--format", "{{.Id}}", image],
                                remaining(30), capture=True)
        image_id = str(inspected.stdout).strip()
        if inspected.returncode != 0 or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            return RunOutcome(70, "TOOLCHAIN", "TEST_IMAGE_INVALID", "INFRASTRUCTURE")
        created = docker_call(prefix, [
            "create", "--name", "atenea-android-" + validation_id.replace("-", ""),
            "--label", "com.atenea.validation=android-v2",
            "--label", f"com.atenea.validation-id={validation_id}",
            "--network", "none", "--user", "1000:0", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--read-only",
            "--cpus", "4", "--memory", definition.memory_max.lower(),
            "--pids-limit", str(definition.tasks_max),
            "--tmpfs", f"/work:rw,exec,nosuid,nodev,size={definition.storage_max.lower()},uid=1000,gid=0,mode=0700",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
            "--mount", f"type=bind,src={source_root},dst=/source,readonly",
            image_id, "/bin/sleep", "infinity",
        ], remaining(30), capture=True)
        candidate_id = str(created.stdout).strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", candidate_id) is None:
            return RunOutcome(70, "CONTAINER", "TEST_CONTAINER_CREATE_FAILED", "INFRASTRUCTURE")
        container_id = candidate_id
        started = docker_call(prefix, ["start", container_id], remaining(30), output)
        if started.returncode != 0:
            return RunOutcome(started.returncode, "CONTAINER", "TEST_CONTAINER_START_FAILED", "INFRASTRUCTURE")
        prepared = docker_call(prefix, ["exec", container_id, "/usr/bin/python3",
                              "/opt/atenea-android-runtime-v2.py", "--prepare"], remaining(180), output)
        if prepared.returncode != 0:
            return RunOutcome(prepared.returncode, "DEPENDENCIES", "TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE")
        tested = docker_call(prefix, ["exec", "--workdir", "/work/repo/android", container_id,
                            "/opt/gradle/bin/gradle", "--offline", "--no-daemon", "--console", "plain",
                            "-Pkotlin.compiler.execution.strategy=in-process",
                            ":app:assembleDebug", "testDebugUnitTest"],
                            remaining(definition.timeout), output)
        output.flush()
        return classify_execution(tested.returncode, bounded_output(Path(output.name)), "ANDROID_BUILD")
    finally:
        cleanup_failed = False
        try:
            if container_id is not None:
                cleanup_failed = docker_call(prefix, ["rm", "--force", container_id], 60).returncode != 0
            if image_id is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
                cleanup_failed |= docker_call(prefix, ["image", "rm", image_id], 60).returncode != 0
        except (OSError, subprocess.SubprocessError):
            cleanup_failed = True
        if cleanup_failed:
            raise RuntimeFailure(RunOutcome(70, "CLEANUP", "TEST_RUNTIME_CLEANUP_FAILED", "INFRASTRUCTURE"))


def playwright_docker_command(
    prefix: list[str], validation_id: str, module: Path, static: Path, artifacts: Path
) -> list[str]:
    name = "atenea-playwright-" + validation_id.replace("-", "")
    return [
        *prefix,
        "run",
        "--rm",
        "--name",
        name,
        "--label",
        "com.atenea.validation=playwright-v1",
        "--label",
        f"com.atenea.validation-id={validation_id}",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--cpus",
        "2",
        "--memory",
        "1g",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=256m",
        "--mount",
        f"type=bind,src={module},dst=/opt/atenea-playwright-module-v1,readonly",
        "--mount",
        f"type=bind,src={PLAYWRIGHT_CHECK},dst=/opt/atenea-check.js,readonly",
        "--mount",
        f"type=bind,src={static},dst=/work/static,readonly",
        "--mount",
        f"type=bind,src={artifacts},dst=/artifacts",
        "-e",
        "NODE_PATH=/opt/atenea-playwright-module-v1/node_modules",
        PLAYWRIGHT_IMAGE,
        "node",
        "/opt/atenea-check.js",
    ]


def run_playwright(
    prefix: list[str],
    validation_id: str,
    slot_uid: int,
    slot_home: Path,
    stage: Path,
    timeout: int,
    output: IO[str],
) -> int:
    module = slot_home / "toolchain/playwright-module-v1"
    static = stage / "static"
    artifacts = stage / "browser"
    if (
        module.is_symlink()
        or not (module / "node_modules/playwright").is_dir()
        or not exact_regular_file(PLAYWRIGHT_CHECK, 0o644)
        or sha256_file(PLAYWRIGHT_CHECK) != PLAYWRIGHT_CHECK_SHA256
        or not (static / "index.html").is_file()
    ):
        reject()
    artifacts.mkdir(mode=0o700)
    os.chown(artifacts, slot_uid, slot_uid)
    command = playwright_docker_command(prefix, validation_id, module, static, artifacts)
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        preexec_fn=limit_validation_output,
        check=False,
    )
    if completed.returncode == 0:
        report = load_json(artifacts / "report.json")
        viewports = report.get("viewports")
        if (
            report.get("schemaVersion") != 1
            or report.get("valuesExposed") is not False
            or not isinstance(viewports, list)
            or len(viewports) != 2
            or not all(
                item.get("horizontalOverflow") is False
                and item.get("criticalVisible") is True
                for item in viewports
                if isinstance(item, dict)
            )
            or len([item for item in viewports if isinstance(item, dict)]) != 2
        ):
            reject()
    return completed.returncode


def snapshot(worktree: Path, destination: Path) -> None:
    shutil.copytree(
        worktree,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git"),
    )


def make_slot_readable(root: Path, slot_gid: int) -> None:
    """Expose one immutable snapshot to its slot without granting writes."""
    for current_root, directories, files in os.walk(root, followlinks=False):
        paths = [Path(current_root), *(Path(current_root) / name for name in directories)]
        paths.extend(Path(current_root) / name for name in files)
        for path in paths:
            if path.is_symlink():
                continue
            stat = path.stat()
            os.chown(path, 0, slot_gid)
            # The slot may read/traverse, never write the root-owned snapshot/recipe.
            os.chmod(path, (stat.st_mode & 0o700) | ((stat.st_mode & 0o500) >> 3))


def prepare_validation_runtime(validation_id: str, slot_uid: int) -> Path:
    """Private per-operation scratch, separate from root-only durable evidence."""
    if not canonical_uuid(validation_id) or slot_uid not in range(1101, 1105):
        reject()
    try:
        observed = RUNTIME_ROOT.lstat()
        if (not stat_module.S_ISDIR(observed.st_mode) or RUNTIME_ROOT.resolve() != RUNTIME_ROOT
                or (observed.st_uid, observed.st_gid, observed.st_mode & 0o7777) != (0, 0, 0o711)
                or {"system.posix_acl_access", "system.posix_acl_default"}.intersection(os.listxattr(RUNTIME_ROOT))):
            reject()
        # No adoption/reuse of an existing scratch directory, including after a crash.
        root = RUNTIME_ROOT / validation_id
        root.mkdir(mode=0o700)
        os.chown(root, 0, slot_uid)
        root.chmod(0o710)
        client = root / "docker-client"
        client.mkdir(mode=0o700)
        os.chown(client, slot_uid, slot_uid)
        return root
    except OSError:
        reject()


def publish_browser_artifacts(stage: Path, destination: Path) -> None:
    expected = {"desktop.png", "mobile.png", "report.json"}
    try:
        observed = {path.name for path in stage.iterdir()}
    except OSError:
        reject()
    if observed != expected or destination.exists() or destination.is_symlink():
        reject()
    temporary = destination.with_name("." + destination.name + ".publishing")
    if temporary.exists() or temporary.is_symlink():
        reject()
    temporary.mkdir(mode=0o750)
    try:
        for name in sorted(expected):
            source = stage / name
            if not source.is_file() or source.is_symlink():
                reject()
            shutil.copyfile(source, temporary / name)
            os.chmod(temporary / name, 0o640)
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def prepare_session_artifacts(session_id: str) -> Path:
    if not canonical_uuid(session_id):
        reject()
    parent = ARTIFACT_ROOT.parent
    try:
        parent_stat = parent.lstat()
        worker = pwd.getpwnam(WORKER_USER)
        if (
            not stat_module.S_ISDIR(parent_stat.st_mode)
            or parent.resolve() != parent
            or parent_stat.st_uid != worker.pw_uid
            or parent_stat.st_gid != worker.pw_gid
            or parent_stat.st_mode & 0o7777 != 0o2770
        ):
            reject()
    except (OSError, KeyError):
        reject()

    paths = (ARTIFACT_ROOT, ARTIFACT_ROOT / session_id)
    states = [artifact_directory_state(path, worker.pw_gid) for path in paths]
    if states[0][0] == "ABSENT" and states[1][0] != "ABSENT":
        reject()
    for path, (state, observed) in zip(paths, states):
        if state == "ABSENT":
            path.mkdir(mode=0o750)
            state, observed = artifact_directory_state(path, worker.pw_gid)
        if state == "INHERITED":
            normalize_inherited_artifact_directory(path, observed)
        if artifact_directory_state(path, worker.pw_gid)[0] != "CURRENT":
            reject()
    return ARTIFACT_ROOT / session_id


def artifact_directory_state(path: Path, inherited_gid: int) -> tuple[str, os.stat_result | None]:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return "ABSENT", None
    except OSError:
        reject()
    if not stat_module.S_ISDIR(observed.st_mode) or observed.st_uid != 0:
        reject()
    mode = observed.st_mode & 0o7777
    if observed.st_gid == 0 and mode == 0o750:
        return "CURRENT", observed
    # Only the exact root-owned state inherited from the fixed setgid parent
    # may be adopted. Foreign owners, modes and symlinks remain fail-closed.
    if observed.st_gid == inherited_gid and mode == 0o2750:
        return "INHERITED", observed
    reject()


def normalize_inherited_artifact_directory(path: Path, observed: os.stat_result) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (
                (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino)
                or opened.st_uid != observed.st_uid
                or opened.st_gid != observed.st_gid
                or opened.st_mode & 0o7777 != observed.st_mode & 0o7777
            ):
                reject()
            os.fchown(descriptor, 0, 0)
            os.fchmod(descriptor, 0o750)
            final = os.fstat(descriptor)
            visible = path.lstat()
            if (
                final.st_uid != 0
                or final.st_gid != 0
                or final.st_mode & 0o7777 != 0o750
                or (visible.st_dev, visible.st_ino) != (final.st_dev, final.st_ino)
            ):
                reject()
        finally:
            os.close(descriptor)
    except OSError:
        reject()


def persist_diagnostic(
    parent: Path, arguments: list[str], definition: Definition,
    outcome: RunOutcome, output_path: Path, duration: int,
) -> str:
    operation, session_id, _identity, source_sha, validation_id = arguments
    output = bounded_output(output_path)
    # Never persist candidate stdout, environment, command arguments or host
    # paths. Only bounded symbolic facts and test class identities survive.
    failures = sorted(set(re.findall(
        r"\bcom\.atenea\.[A-Za-z0-9_.]{1,160}(?:Test|Tests)\b", output
    )))[:8]
    diagnostic = {
        "schemaVersion": 1, "operationId": validation_id, "sessionId": session_id,
        "operation": operation, "definitionRevision": definition.revision,
        "sourceTreeFingerprintSha256": source_sha,
        "phase": outcome.phase, "errorCode": outcome.error_code,
        "failureClass": outcome.failure_class, "exitCode": outcome.exit_code,
        "durationMillis": duration, "outputSha256": sha256_file(output_path),
        "testClasses": failures, "valuesExposed": False,
    }
    encoded = json.dumps(diagnostic, sort_keys=True, separators=(",", ":")).encode("utf-8")
    destination = parent / (validation_id + "-diagnostic-v1.json")
    if destination.exists() or destination.is_symlink():
        if not exact_regular_file(destination, 0o600) or destination.read_bytes() != encoded:
            reject()
        return hashlib.sha256(encoded).hexdigest()
    descriptor, temporary_name = tempfile.mkstemp(prefix=".diagnostic.", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # Publish without replacing an existing receipt, even under a race.
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            if not exact_regular_file(destination, 0o600) or destination.read_bytes() != encoded:
                reject()
        parent_fd = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(encoded).hexdigest()


def execute_validation(arguments: list[str]) -> dict:
    if os.geteuid() != 0 or len(arguments) not in {4, 5}:
        reject()
    if len(arguments) == 4:
        operation, session_id, source_sha, validation_id = arguments
        workspace_identity = f"remote:ax42-01:work-session:{session_id}"
        arguments = [operation, session_id, workspace_identity, source_sha, validation_id]
    else:
        operation, session_id, workspace_identity, source_sha, validation_id = arguments
    definition = DEFINITIONS.get(operation)
    if (
        definition is None
        or not canonical_uuid(session_id)
        or not canonical_uuid(validation_id)
        or SHA256_RE.fullmatch(source_sha) is None
    ):
        reject()
    worktree, retained_slot, expected_commit = resolve_authority(
        session_id, workspace_identity
    )
    with validation_slot(session_id, definition, retained_slot) as slot:
        return execute_validation_in_slot(
            arguments, definition, worktree, expected_commit, slot
        )


def execute_validation_in_slot(
    arguments: list[str],
    definition: Definition,
    worktree: Path,
    expected_commit: str,
    slot: tuple[str, int, Path, Path],
) -> dict:
    operation, session_id, _workspace_identity, source_sha, validation_id = arguments
    slot_user, slot_uid, slot_home, socket = slot
    expected = command_output(
        git_observation_command(worktree, ["rev-parse", "--verify", "HEAD^{commit}"])
    )
    if expected != expected_commit or COMMIT_RE.fullmatch(expected) is None:
        reject()
    before = command_output(
        git_observation_command(
            worktree, ["status", "--porcelain=v2", "--untracked-files=all"]
        )
    )

    session_artifacts = prepare_session_artifacts(session_id)
    published_artifacts = session_artifacts / validation_id
    if (
        definition.runner == "playwright"
        and (published_artifacts.exists() or published_artifacts.is_symlink())
    ):
        reject()
    run_root = prepare_validation_runtime(validation_id, slot_uid)
    source_root = run_root / "source"
    artifact_stage = run_root / "artifacts"
    output_path = run_root / "output"
    resolv_path = run_root / "resolv.conf"
    try:
        os.chown(run_root, 0, slot_uid)
        os.chmod(run_root, 0o710)
        snapshot(worktree, source_root)
        make_slot_readable(source_root, slot_uid)
        resolv_path.write_text(
            "nameserver 1.1.1.1\noptions timeout:2 attempts:2\n", encoding="ascii"
        )
        os.chown(resolv_path, 0, slot_uid)
        os.chmod(resolv_path, 0o640)
        artifact_stage.mkdir(mode=0o700)
        os.chown(artifact_stage, slot_uid, slot_uid)
        started = time.monotonic()
        outcome = None
        with output_path.open("x", encoding="utf-8") as output:
            try:
                if definition.runner == "sandbox":
                    sandbox_timeout = (
                        330 if definition.runner == "playwright" else definition.timeout + 30
                    )
                    completed = subprocess.run(
                        sandbox_command(
                            operation,
                            validation_id,
                            definition,
                            slot_user,
                            slot_uid,
                            source_root,
                            artifact_stage,
                            resolv_path,
                        ),
                        stdin=subprocess.DEVNULL,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=sandbox_timeout,
                        preexec_fn=limit_validation_output,
                        check=False,
                    )
                    exit_code = completed.returncode
                else:
                    if not socket.is_socket():
                        outcome = RunOutcome(70, "CONTAINER", "TEST_RUNTIME_UNAVAILABLE", "INFRASTRUCTURE")
                        exit_code = outcome.exit_code
                    else:
                        prefix = docker_slot_prefix(slot_user, slot_uid, socket, run_root / "docker-client")
                        if definition.runner == "backend":
                            outcome = run_backend(prefix, validation_id, source_root, definition, output)
                            exit_code = outcome.exit_code
                        elif definition.runner in {"web", "playwright"}:
                            outcome = run_web(prefix, validation_id, source_root, definition, artifact_stage, output)
                            exit_code = outcome.exit_code
                        else:
                            outcome = run_android(prefix, validation_id, source_root, definition, output)
                            exit_code = outcome.exit_code
                if exit_code == 0 and definition.runner == "playwright":
                    prefix = docker_slot_prefix(slot_user, slot_uid, socket, run_root / "docker-client")
                    remaining = max(
                        1, definition.timeout - int(time.monotonic() - started)
                    )
                    exit_code = run_playwright(
                        prefix,
                        validation_id,
                        slot_uid,
                        slot_home,
                        artifact_stage,
                        remaining,
                        output,
                    )
                    # Browser failure must not retain a successful build outcome.
                    outcome = classify_execution(exit_code, bounded_output(output_path), operation)
            except subprocess.TimeoutExpired:
                exit_code = 124
                output.write("validation timed out\n")
            except RuntimeFailure as error:
                outcome = error.outcome
                exit_code = outcome.exit_code
        duration = int((time.monotonic() - started) * 1000)
        after = command_output(
            git_observation_command(
                worktree, ["status", "--porcelain=v2", "--untracked-files=all"]
            )
        )
        if before != after:
            reject()
        if exit_code == 0 and definition.runner == "playwright":
            publish_browser_artifacts(artifact_stage / "browser", published_artifacts)
        output_sha = sha256_file(output_path)
        if outcome is None:
            outcome = classify_execution(exit_code, bounded_output(output_path), operation)
        diagnostic_sha = persist_diagnostic(
            session_artifacts, arguments, definition, outcome, output_path, duration
        )
        manifest = hashlib.sha256(
            "\0".join(
                (
                    validation_id,
                    definition.revision,
                    source_sha,
                    str(exit_code),
                    str(duration),
                    output_sha,
                    diagnostic_sha,
                )
            ).encode("ascii")
        ).hexdigest()
        if exit_code == 0:
            status, summary, public_exit = "SUCCEEDED", "Closed validation passed", 0
        elif outcome.failure_class != "CANDIDATE":
            status, summary, public_exit = "BLOCKED", f"{operation}/{outcome.phase}: {outcome.error_code}", None
        else:
            status, summary, public_exit = "FAILED", f"{operation}/{outcome.phase}: {outcome.error_code}", exit_code
        return {
            "validationId": validation_id,
            "sessionId": session_id,
            "operation": operation,
            "definitionRevision": definition.revision,
            "sourceTreeFingerprintSha256": source_sha,
            "status": status,
            "exitCode": public_exit,
            "durationMillis": duration,
            "artifactManifestSha256": manifest,
            "summary": summary,
            "valuesExposed": False,
            "failureClass": outcome.failure_class,
        }
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def run_validation(arguments: list[str]) -> int:
    result = execute_validation(arguments)
    result.pop("failureClass", None)
    print(json.dumps(result, separators=(",", ":")))
    return 0


def durable_unit_name(operation_id: str) -> str:
    if not canonical_uuid(operation_id):
        reject()
    return "atenea-validation-broker-" + operation_id.replace("-", "")


def durable_identity(arguments: list[str]) -> dict[str, str]:
    if len(arguments) not in {4, 5}:
        reject()
    if len(arguments) == 4:
        operation, session_id, source_sha, operation_id = arguments
        workspace_identity = f"remote:ax42-01:work-session:{session_id}"
    else:
        operation, session_id, workspace_identity, source_sha, operation_id = arguments
    definition = DEFINITIONS.get(operation)
    if (
        definition is None
        or not canonical_uuid(session_id)
        or not canonical_uuid(operation_id)
        or not (
            workspace_identity == f"remote:ax42-01:work-session:{session_id}"
            or (
                workspace_identity.startswith("remote:ax42-01:change:")
                and canonical_uuid(workspace_identity.rsplit(":", 1)[-1])
            )
        )
        or SHA256_RE.fullmatch(source_sha) is None
    ):
        reject()
    return {
        "operation": operation,
        "sessionId": session_id,
        "workspaceIdentity": workspace_identity,
        "sourceTreeFingerprintSha256": source_sha,
        "operationId": operation_id,
        "definitionRevision": definition.revision,
    }


def operation_directory(identity: dict[str, str]) -> Path:
    owner = os.geteuid()
    try:
        root_stat = JOURNAL_ROOT.lstat()
    except OSError:
        reject()
    if (
        not JOURNAL_ROOT.is_dir()
        or JOURNAL_ROOT.is_symlink()
        or root_stat.st_uid != owner
        or root_stat.st_mode & 0o7777 != 0o750
    ):
        reject()
    current = JOURNAL_ROOT
    for name in (identity["sessionId"], identity["operationId"]):
        current = current / name
        if not current.exists():
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
        try:
            observed = current.lstat()
        except OSError:
            reject()
        if (
            not current.is_dir()
            or current.is_symlink()
            or observed.st_uid != owner
            or observed.st_mode & 0o7777 != 0o700
        ):
            reject()
    return current


@contextmanager
def locked_operation(identity: dict[str, str]) -> Iterator[Path]:
    directory = operation_directory(identity)
    lock_path = directory / "operation-v1.lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        observed = os.fstat(descriptor)
        if (
            not stat_module.S_ISREG(observed.st_mode)
            or observed.st_uid != os.geteuid()
            or observed.st_mode & 0o7777 != 0o600
        ):
            reject()
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield directory
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def durable_fingerprint(identity: dict[str, str]) -> str:
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_operation(directory: Path, identity: dict[str, str]) -> dict[str, Any] | None:
    path = directory / "operation-v1.json"
    if not path.exists():
        return None
    if not exact_regular_file(
        path, 0o600, uid=os.geteuid(), gid=os.getegid()
    ):
        reject()
    record = load_json(path)
    retained_identity = identity
    legacy_revision = {"BACKEND_TEST": "atenea-backend-test-v1",
                       "ANDROID_BUILD": "atenea-android-build-v1"}.get(identity["operation"])
    if (legacy_revision is not None
            and record.get("definitionRevision") == legacy_revision
            and record.get("state") in DURABLE_TERMINAL):
        # Historical v1 receipts remain inspectable with their original
        # fingerprint. They are never adopted as executable v2 operations.
        retained_identity = {**identity, "definitionRevision": legacy_revision}
    if (
        record.get("protocolVersion") != DURABLE_PROTOCOL
        or record.get("requestFingerprintSha256") != durable_fingerprint(retained_identity)
        or any(record.get(key) != value for key, value in retained_identity.items())
        or record.get("state") not in DURABLE_NON_TERMINAL | DURABLE_TERMINAL
        or not isinstance(record.get("cancelRequested"), bool)
    ):
        reject()
    return record


def write_operation(directory: Path, record: dict[str, Any]) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".operation-v1.", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, directory / "operation-v1.json")
        directory_descriptor = os.open(directory, os.O_RDONLY | os.O_CLOEXEC)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def new_operation(identity: dict[str, str]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "protocolVersion": DURABLE_PROTOCOL,
        **identity,
        "requestFingerprintSha256": durable_fingerprint(identity),
        "state": "QUEUED",
        "terminalCause": "NONE",
        "cancelRequested": False,
        "exitCode": None,
        "durationMillis": 0,
        "artifactManifestSha256": None,
        "summary": "Closed validation is queued for admission",
        "valuesExposed": False,
    }


def public_operation(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "schemaVersion", "protocolVersion", "operationId", "sessionId",
            "operation", "definitionRevision", "sourceTreeFingerprintSha256",
            "state", "terminalCause", "exitCode", "durationMillis",
            "artifactManifestSha256", "summary", "valuesExposed",
        )
    }


def unit_active(operation_id: str) -> bool:
    completed = subprocess.run(
        ["/usr/bin/systemctl", "is-active", "--quiet", durable_unit_name(operation_id)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode in {3, 4}:
        return False
    reject()


def durable_unit_command(identity: dict[str, str]) -> list[str]:
    definition = DEFINITIONS[identity["operation"]]
    # BuildKit's trusted registry-token provider runs in the client process.
    # It needs DNS/HTTPS for the hash-locked backend/Android recipes, not just
    # the Unix daemon socket. Candidate containers remain --network=none.
    families = "AF_UNIX AF_INET AF_INET6" if definition.runner in {"backend", "android", "web", "playwright"} else "AF_UNIX"
    helper = Path(__file__).resolve()
    command = [
        "/usr/bin/systemd-run",
        "--no-block",
        "--collect",
        "--quiet",
        "--service-type=exec",
        "--unit",
        durable_unit_name(identity["operationId"]),
        "--property",
        f"RuntimeMaxSec={definition.timeout + 120}s",
        "--property",
        "KillMode=control-group",
        "--property",
        "PrivateTmp=yes",
        "--property",
        "PrivateDevices=yes",
        "--property",
        "ProtectSystem=strict",
        "--property",
        "ProtectHome=read-only",
        "--property",
        "ProtectKernelTunables=yes",
        "--property",
        "ProtectKernelModules=yes",
        "--property",
        "ProtectControlGroups=yes",
        "--property",
        "RestrictSUIDSGID=yes",
        "--property",
        "LockPersonality=yes",
        "--property",
        f"RestrictAddressFamilies={families}",
        "--property",
        "CapabilityBoundingSet=CAP_SETUID CAP_SETGID CAP_CHOWN CAP_DAC_OVERRIDE",
        "--property",
        f"ReadWritePaths={ARTIFACT_ROOT.parent} {JOURNAL_ROOT} /srv/atenea/worker/runtime-admission-v1 {RUNTIME_ROOT}",
        "--property",
        f"ReadOnlyPaths={WORKSPACE_ROOT} {CHANGE_WORKSPACE_ROOT} {CONFIG.parent} /run/user {RUNTIME_ADMISSION}",
        "--",
        "/usr/bin/python3",
        str(helper),
        "--durable-execute",
        identity["operation"],
        identity["sessionId"],
        identity["workspaceIdentity"],
        identity["sourceTreeFingerprintSha256"],
        identity["operationId"],
    ]
    return command


def launch_durable_unit(identity: dict[str, str]) -> None:
    completed = subprocess.run(
        durable_unit_command(identity),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        reject()


def start_durable(arguments: list[str]) -> dict[str, Any]:
    require_root()
    identity = durable_identity(arguments)
    with locked_operation(identity) as directory:
        record = load_operation(directory, identity)
        if record is None:
            record = new_operation(identity)
            write_operation(directory, record)
        if record["state"] in DURABLE_TERMINAL:
            return public_operation(record)
        if unit_active(identity["operationId"]):
            record["state"] = "CANCELLING" if record["cancelRequested"] else "RUNNING"
            record["summary"] = (
                "Closed validation cancellation is in progress"
                if record["cancelRequested"]
                else "Closed validation is running"
            )
            write_operation(directory, record)
            return public_operation(record)
        if record["state"] != "QUEUED":
            if record["cancelRequested"]:
                record.update(
                    state="CANCELLED", terminalCause="CANCELLED",
                    summary="Closed validation was cancelled",
                )
            else:
                record.update(
                    state="INFRASTRUCTURE_FAILED", terminalCause="INFRASTRUCTURE",
                    summary="Closed validation failed in infrastructure",
                )
            write_operation(directory, record)
            return public_operation(record)
        launch_durable_unit(identity)
        latest = load_operation(directory, identity)
        if latest is not None and latest["state"] in DURABLE_TERMINAL:
            return public_operation(latest)
        record["state"] = "RUNNING"
        record["summary"] = "Closed validation is running"
        write_operation(directory, record)
        return public_operation(record)


def inspect_durable(arguments: list[str]) -> dict[str, Any]:
    require_root()
    identity = durable_identity(arguments)
    with locked_operation(identity) as directory:
        record = load_operation(directory, identity)
        if record is None:
            reject()
        if record["state"] in DURABLE_TERMINAL:
            return public_operation(record)
        if unit_active(identity["operationId"]):
            record["state"] = "CANCELLING" if record["cancelRequested"] else "RUNNING"
            record["summary"] = (
                "Closed validation cancellation is in progress"
                if record["cancelRequested"]
                else "Closed validation is running"
            )
        elif record["state"] == "QUEUED":
            pass
        elif record["cancelRequested"]:
            record.update(
                state="CANCELLED", terminalCause="CANCELLED",
                summary="Closed validation was cancelled",
            )
        else:
            record.update(
                state="INFRASTRUCTURE_FAILED", terminalCause="INFRASTRUCTURE",
                summary="Closed validation failed in infrastructure",
            )
        write_operation(directory, record)
        return public_operation(record)


def cancel_durable(arguments: list[str]) -> dict[str, Any]:
    require_root()
    identity = durable_identity(arguments)
    active = False
    with locked_operation(identity) as directory:
        record = load_operation(directory, identity)
        if record is None:
            reject()
        if record["state"] in DURABLE_TERMINAL:
            return public_operation(record)
        active = unit_active(identity["operationId"])
        record["cancelRequested"] = True
        if active:
            record["state"] = "CANCELLING"
            record["summary"] = "Closed validation cancellation is in progress"
        else:
            record.update(
                state="CANCELLED", terminalCause="CANCELLED",
                summary="Closed validation was cancelled",
            )
        write_operation(directory, record)
    if active:
        completed = subprocess.run(
            ["/usr/bin/systemctl", "stop", durable_unit_name(identity["operationId"])],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            return inspect_durable(arguments)
        with locked_operation(identity) as directory:
            record = load_operation(directory, identity)
            if record is None:
                reject()
            if record["state"] not in DURABLE_TERMINAL:
                record.update(
                    state="CANCELLED", terminalCause="CANCELLED",
                    summary="Closed validation was cancelled",
                )
                write_operation(directory, record)
            return public_operation(record)
    return inspect_durable(arguments)


def execute_durable(arguments: list[str]) -> int:
    identity = durable_identity(arguments)
    require_root()
    with locked_operation(identity) as directory:
        record = load_operation(directory, identity)
        if record is None:
            reject()
        if record["state"] in DURABLE_TERMINAL:
            return 0
        if record["cancelRequested"]:
            record.update(
                state="CANCELLED", terminalCause="CANCELLED",
                summary="Closed validation was cancelled",
            )
            write_operation(directory, record)
            return 0
        record["state"] = "RUNNING"
        record["summary"] = "Closed validation is running"
        write_operation(directory, record)
    try:
        result = execute_validation(arguments)
        state = {
            "SUCCEEDED": "SUCCEEDED",
            "FAILED": "CANDIDATE_FAILED",
            "BLOCKED": "INFRASTRUCTURE_FAILED",
        }[result["status"]]
        if result["status"] != "SUCCEEDED":
            state = {
                "CANDIDATE": "CANDIDATE_FAILED", "INFRASTRUCTURE": "INFRASTRUCTURE_FAILED",
                "POLICY": "POLICY_FAILED", "VALIDATION": "VALIDATION_FAILED",
            }.get(result.get("failureClass"), state)
        cause = {
            "SUCCEEDED": "NONE",
            "CANDIDATE_FAILED": "CANDIDATE",
            "INFRASTRUCTURE_FAILED": "INFRASTRUCTURE",
            "POLICY_FAILED": "POLICY",
            "VALIDATION_FAILED": "VALIDATION",
        }[state]
        terminal = {
            "state": state,
            "terminalCause": cause,
            "exitCode": result["exitCode"] if state in {"SUCCEEDED", "CANDIDATE_FAILED"} else None,
            "durationMillis": result["durationMillis"],
            "artifactManifestSha256": result["artifactManifestSha256"],
            "summary": result["summary"],
        }
    except Rejected:
        terminal = {
            "state": "OWNERSHIP_FAILED",
            "terminalCause": "OWNERSHIP",
            "exitCode": None,
            "durationMillis": 0,
            "artifactManifestSha256": None,
            "summary": "Closed validation ownership was rejected",
        }
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        terminal = {
            "state": "INFRASTRUCTURE_FAILED",
            "terminalCause": "INFRASTRUCTURE",
            "exitCode": None,
            "durationMillis": 0,
            "artifactManifestSha256": None,
            "summary": "Closed validation failed in infrastructure",
        }
    with locked_operation(identity) as directory:
        record = load_operation(directory, identity)
        if record is None:
            reject()
        if record["cancelRequested"]:
            record.update(
                state="CANCELLED", terminalCause="CANCELLED", exitCode=None,
                artifactManifestSha256=None,
                summary="Closed validation was cancelled",
            )
        else:
            record.update(terminal)
        write_operation(directory, record)
    return 0


def main() -> int:
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--sandbox-exec":
            return sandbox_exec(sys.argv[2])
        if len(sys.argv) == 3 and sys.argv[1] == "--sandbox-supervise":
            return sandbox_supervise(sys.argv[2])
        if len(sys.argv) in {6, 7} and sys.argv[1] == "--durable-execute":
            return execute_durable(sys.argv[2:])
        if len(sys.argv) in {6, 7} and sys.argv[1] in {"start", "inspect", "cancel"}:
            result = {
                "start": start_durable,
                "inspect": inspect_durable,
                "cancel": cancel_durable,
            }[sys.argv[1]](sys.argv[2:])
            print(json.dumps(result, separators=(",", ":")))
            return 0
        return run_validation(sys.argv[1:])
    except Rejected as error:
        print(str(error), file=sys.stderr)
        return 64
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print("validation authority rejected", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
