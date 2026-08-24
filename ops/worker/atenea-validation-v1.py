#!/usr/bin/env python3
"""Closed, root-coordinated validation runner for the Atenea project."""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import pwd
import re
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
JOURNAL_ROOT = Path("/srv/atenea/worker/validation-broker-v1")
WORKSPACE_ROOT = Path("/srv/atenea/workspaces/sessions")
PLAYWRIGHT_CHECK = Path("/usr/local/libexec/atenea/atenea-playwright-validation-v1.js")
PLAYWRIGHT_IMAGE = (
    "mcr.microsoft.com/playwright:v1.60.0-noble@"
    "sha256:9bd26ad900bb5e0f4dee75839e957a89ae89c2b7ab1e76050e559790e946b948"
)
PLAYWRIGHT_CHECK_SHA256 = (
    "4196efbfa306edd95955683f1123cffa96645938441f81717ad9032052d68ed9"
)
ANDROID_DOCKERFILE_SHA256 = (
    "4b61f515954c2062606508ce2c9ccc65a599b1c0582ade4d0708e56f5cb409c2"
)
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
        "atenea-backend-test-v1", 900, "200%", "4G", 512, "6G", "sandbox"
    ),
    "WEB_BUILD": Definition(
        "atenea-web-build-v1", 600, "200%", "3G", 512, "4G", "sandbox"
    ),
    "ANDROID_BUILD": Definition(
        "atenea-android-build-v1", 1200, "400%", "10G", 2048, "12G", "android"
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


def resolve_authority(session_id: str) -> tuple[Path, str, int, Path, Path]:
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
    slot_user = f"atenea-{slot}"
    try:
        account = pwd.getpwnam(slot_user)
    except KeyError:
        reject()
    expected_uid = 1100 + int(slot.removeprefix("slot"))
    slot_home = Path(f"/var/lib/atenea-slots/{slot.removeprefix('slot')}")
    # The deployed account home is /var/lib/atenea-slots/slotN. Keep accepting
    # only that exact form; the separate expression above prevents caller input.
    slot_home = Path(f"/var/lib/atenea-slots/{slot}")
    if (
        account.pw_uid != expected_uid
        or account.pw_gid != expected_uid
        or Path(account.pw_dir) != slot_home
    ):
        reject()
    runtime_dir = Path(f"/run/user/{account.pw_uid}")
    socket = runtime_dir / "docker.sock"
    return worktree, slot_user, account.pw_uid, slot_home, socket


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
        "ProtectKernelTunables=yes",
        "--property",
        "ProtectKernelModules=yes",
        "--property",
        "ProtectKernelLogs=yes",
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
        "USER": str(pwd.getpwuid(os.getuid()).pw_name),
        "LOGNAME": str(pwd.getpwuid(os.getuid()).pw_name),
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def sandbox_operation_command(operation: str) -> tuple[str, ...]:
    command = {
        "BACKEND_TEST": ("./mvnw", "-q", "test"),
        "WEB_BUILD": ("./scripts/web-build.sh",),
        "PLAYWRIGHT_ACCEPTANCE": ("./scripts/web-build.sh",),
    }.get(operation)
    if command is None or DEFINITIONS[operation].runner not in {"sandbox", "playwright"}:
        reject()
    return command


def sandbox_exec(operation: str) -> int:
    if os.geteuid() == 0 or operation not in DEFINITIONS:
        reject()
    source = Path("/source")
    worktree = Path("/work/repo")
    home = Path("/work/home")
    if worktree.exists() or not source.is_dir() or source.is_symlink():
        reject()
    home.mkdir(mode=0o700)
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


def docker_slot_prefix(slot_user: str, slot_uid: int, socket: Path) -> list[str]:
    return [
        "/usr/sbin/runuser",
        "-u",
        slot_user,
        "--",
        "/usr/bin/env",
        f"HOME=/var/lib/atenea-slots/slot{slot_uid - 1100}",
        f"XDG_RUNTIME_DIR=/run/user/{slot_uid}",
        f"DOCKER_HOST=unix://{socket}",
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


def run_android(
    prefix: list[str],
    validation_id: str,
    source_root: Path,
    definition: Definition,
    output: IO[str],
) -> int:
    deadline = time.monotonic() + definition.timeout

    def remaining(cap: int) -> float:
        value = min(float(cap), deadline - time.monotonic())
        if value <= 0:
            raise subprocess.TimeoutExpired(prefix, definition.timeout)
        return value

    dockerfile = source_root / "docker/android-builder.Dockerfile"
    if sha256_file(dockerfile) != ANDROID_DOCKERFILE_SHA256:
        reject()
    # Only the reviewed builder definition can create the validation-specific
    # rootless image. Candidate code is not allowed to choose build options.
    image = f"atenea-android-validation:{validation_id}"
    build = docker_call(
        prefix,
        [
            "build",
            "--file",
            str(dockerfile),
            "--network",
            # The reviewed builder needs its fixed public downloads. Rootless
            # Docker's isolated default network is explicit; candidate Gradle
            # code runs later with no network at all.
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
            "com.atenea.validation=android-builder-v1",
            str(source_root),
        ],
        remaining(definition.timeout),
        output,
    )
    if build.returncode != 0:
        return build.returncode
    name = "atenea-android-" + validation_id.replace("-", "")
    create = docker_call(
        prefix,
        [
            "create",
            "--name",
            name,
            "--label",
            "com.atenea.validation=android-v1",
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
            "4",
            "--memory",
            definition.memory_max.lower(),
            "--pids-limit",
            str(definition.tasks_max),
            "--tmpfs",
            f"/workspace:rw,nosuid,nodev,size={definition.storage_max.lower()}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=512m",
            "--tmpfs",
            "/root/.gradle:rw,nosuid,nodev,size=3g",
            "--tmpfs",
            "/root/.android:rw,nosuid,nodev,size=64m",
            "--mount",
            f"type=bind,src={source_root},dst=/source,readonly",
            "--workdir",
            "/workspace",
            image,
            "/bin/sh",
            "-c",
            "cp -a /source/. /workspace/ && cd /workspace/android && exec gradle :app:assembleDebug",
        ],
        remaining(60),
        capture=True,
    )
    if create.returncode != 0:
        docker_call(prefix, ["image", "rm", image], 60)
        return create.returncode
    container_id = str(create.stdout).strip()
    if re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        docker_call(prefix, ["image", "rm", image], 60)
        reject()
    try:
        started = docker_call(
            prefix,
            ["start", "--attach", container_id],
            remaining(definition.timeout),
            output,
        )
        return started.returncode
    finally:
        docker_call(prefix, ["rm", "--force", container_id], 60)
        docker_call(prefix, ["image", "rm", image], 60)


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
            user = (stat.st_mode & 0o700) >> 6
            os.chmod(path, (stat.st_mode & 0o700) | (user << 3))


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
    parent = ARTIFACT_ROOT.parent
    try:
        if not parent.is_dir() or parent.is_symlink() or parent.resolve() != parent:
            reject()
    except OSError:
        reject()
    for path in (ARTIFACT_ROOT, ARTIFACT_ROOT / session_id):
        if path.exists() or path.is_symlink():
            try:
                stat = path.lstat()
            except OSError:
                reject()
            if (
                not path.is_dir()
                or path.is_symlink()
                or stat.st_uid != 0
                or stat.st_gid != 0
                or stat.st_mode & 0o7777 != 0o750
            ):
                reject()
        else:
            path.mkdir(mode=0o750)
    return ARTIFACT_ROOT / session_id


def execute_validation(arguments: list[str]) -> dict:
    if os.geteuid() != 0 or len(arguments) != 4:
        reject()
    operation, session_id, source_sha, validation_id = arguments
    definition = DEFINITIONS.get(operation)
    if (
        definition is None
        or not canonical_uuid(session_id)
        or not canonical_uuid(validation_id)
        or SHA256_RE.fullmatch(source_sha) is None
    ):
        reject()
    worktree, slot_user, slot_uid, slot_home, socket = resolve_authority(session_id)
    expected = command_output(
        git_observation_command(worktree, ["rev-parse", "--verify", "HEAD^{commit}"])
    )
    config_commit = load_json(CONFIG).get("commit")
    if expected != config_commit or COMMIT_RE.fullmatch(expected) is None:
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
    run_root = Path(tempfile.mkdtemp(prefix=".validation-run.", dir=session_artifacts))
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
        with output_path.open("x", encoding="utf-8") as output:
            try:
                if definition.runner in {"sandbox", "playwright"}:
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
                        reject()
                    prefix = docker_slot_prefix(slot_user, slot_uid, socket)
                    exit_code = run_android(
                        prefix, validation_id, source_root, definition, output
                    )
                if exit_code == 0 and definition.runner == "playwright":
                    prefix = docker_slot_prefix(slot_user, slot_uid, socket)
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
            except subprocess.TimeoutExpired:
                exit_code = 124
                output.write("validation timed out\n")
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
        manifest = hashlib.sha256(
            "\0".join(
                (
                    validation_id,
                    definition.revision,
                    source_sha,
                    str(exit_code),
                    str(duration),
                    output_sha,
                )
            ).encode("ascii")
        ).hexdigest()
        if exit_code == 0:
            status, summary, public_exit = "SUCCEEDED", "Closed validation passed", 0
        elif exit_code in {124, 137}:
            status, summary, public_exit = (
                "BLOCKED",
                "Closed validation exceeded its finite timeout",
                None,
            )
        else:
            status, summary, public_exit = "FAILED", "Closed validation failed", exit_code
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
        }
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def run_validation(arguments: list[str]) -> int:
    print(json.dumps(execute_validation(arguments), separators=(",", ":")))
    return 0


def durable_unit_name(operation_id: str) -> str:
    if not canonical_uuid(operation_id):
        reject()
    return "atenea-validation-broker-" + operation_id.replace("-", "")


def durable_identity(arguments: list[str]) -> dict[str, str]:
    if len(arguments) != 4:
        reject()
    operation, session_id, source_sha, operation_id = arguments
    definition = DEFINITIONS.get(operation)
    if (
        definition is None
        or not canonical_uuid(session_id)
        or not canonical_uuid(operation_id)
        or SHA256_RE.fullmatch(source_sha) is None
    ):
        reject()
    return {
        "operation": operation,
        "sessionId": session_id,
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
    if (
        record.get("protocolVersion") != DURABLE_PROTOCOL
        or record.get("requestFingerprintSha256") != durable_fingerprint(identity)
        or any(record.get(key) != value for key, value in identity.items())
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


def launch_durable_unit(identity: dict[str, str]) -> None:
    definition = DEFINITIONS[identity["operation"]]
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
        "RestrictAddressFamilies=AF_UNIX",
        "--property",
        "CapabilityBoundingSet=CAP_SETUID CAP_SETGID CAP_CHOWN CAP_DAC_OVERRIDE",
        "--property",
        f"ReadWritePaths={ARTIFACT_ROOT.parent} {JOURNAL_ROOT}",
        "--property",
        f"ReadOnlyPaths={WORKSPACE_ROOT} {CONFIG.parent} /run/user",
        "--",
        "/usr/bin/python3",
        str(helper),
        "--durable-execute",
        identity["operation"],
        identity["sessionId"],
        identity["sourceTreeFingerprintSha256"],
        identity["operationId"],
    ]
    completed = subprocess.run(
        command,
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
        cause = {
            "SUCCEEDED": "NONE",
            "CANDIDATE_FAILED": "CANDIDATE",
            "INFRASTRUCTURE_FAILED": "INFRASTRUCTURE",
        }[state]
        terminal = {
            "state": state,
            "terminalCause": cause,
            "exitCode": result["exitCode"],
            "durationMillis": result["durationMillis"],
            "artifactManifestSha256": result["artifactManifestSha256"],
            "summary": {
                "SUCCEEDED": "Closed validation passed",
                "CANDIDATE_FAILED": "Closed validation failed",
                "INFRASTRUCTURE_FAILED": "Closed validation failed in infrastructure",
            }[state],
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
        if len(sys.argv) == 6 and sys.argv[1] == "--durable-execute":
            return execute_durable(sys.argv[2:])
        if len(sys.argv) == 6 and sys.argv[1] in {"start", "inspect", "cancel"}:
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
