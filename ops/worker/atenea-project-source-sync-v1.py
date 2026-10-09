#!/usr/bin/env python3
"""Root-only, closed canonical promotion; not an AgentRun or public API."""
import base64
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import uuid

OLD = "847a2f240e3d64af2cf3f166ff3c70ad7cc8497f"
NEW = "07fdf9f56333ff8002450d7bc2719ac4000fe4a7"
OLD_HASH = "beb08afbab13a65d46ad6b80f8a8df2368391521daaaffc39d6cecb413d3baf0"
NEW_HASH = "c6d651e15fdd103df2cef306844f21384510c9f509f3b99cb26423e875266c0c"
REPOSITORY = "https://github.com/jlnieto/atenea.git"
REF = "refs/remotes/origin/main"
MIRROR = Path("/srv/atenea/repositories/atenea.git")
CONFIG = Path("/etc/atenea-worker/project-codex-v1.json")
INSTALLER = Path("/usr/local/libexec/atenea/install-agent-run-worker-v1.sh")
TOKEN = Path("/etc/atenea-release-v1/github.token")
LOCK = Path("/run/atenea/release-v1/admission.lock")
JOURNAL = Path("/srv/atenea/release-v1/project-source-sync-v1")
RECORD = JOURNAL / "operation-v1.json"
BACKUP = JOURNAL / "config-before.json"
CODEX = Path("/srv/atenea/worker/codex-releases-v1")
CODEX_REGISTRY = Path("/etc/atenea-worker/codex-release-stage-v1.json")
CHANGE = Path("/srv/atenea/workspaces/changes/59315b6e-59bc-4884-9def-356e1ca86ef4")
HEAD = "d364ccef201526821b65600dd7301a90586eeb9a"
BRANCH = "atenea/change-59315b6e-59bc-4884-9def-356e1ca86ef4"
WORKSPACE_HASH = "f8bfec8dc81547a99c2f06536792a24f95ff46e8ddba928d3ad0b3727daac225"
PUBLICATION_HASH = "beaa65864edb0fdd3e56c4ff566f359d72f9108145376d56ab23c02a69ecd1b9"
SERVICE = "atenea-agent-run-worker-v1.service"


class Rejected(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def trusted(path, mode=None):
    value = path.lstat()
    if (not stat.S_ISREG(value.st_mode) or value.st_uid != 0
            or value.st_nlink != 1 or value.st_mode & 0o022
            or (mode is not None and stat.S_IMODE(value.st_mode) != mode)):
        raise Rejected("FILE_AUTHORITY_INVALID")
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise Rejected("PARENT_AUTHORITY_INVALID")
    return path


def command(args, env=None):
    result = subprocess.run(args, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=120, check=False)
    if result.returncode:
        # Git/HTTP errors may contain a credential. Never forward them.
        raise Rejected("SUPPORTED_COMMAND_FAILED")
    return result.stdout.decode().strip()


def git(*args, env=None):
    return command(["/usr/bin/git", "-c", "core.hooksPath=/dev/null",
                    "-c", "core.fsmonitor=false", "-c", "gc.auto=0",
                    "-c", "maintenance.auto=false", "-c", "credential.helper=",
                    "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never",
                    f"--git-dir={MIRROR}", *args], env=env or git_environment())


def git_environment():
    return {"PATH": "/usr/bin:/bin", "HOME": "/root", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_OPTIONAL_LOCKS": "0"}


def check():
    trusted(CONFIG, 0o644)
    command(["/bin/bash", str(trusted(INSTALLER, 0o755)), "project-source-sync-check"],
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root"})


def fetch():
    token = trusted(TOKEN, 0o600).read_text().strip()
    if not token or any(char.isspace() for char in token):
        raise Rejected("READ_TOKEN_INVALID")
    env = git_environment()
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
               GIT_CONFIG_VALUE_0=f"Authorization: Basic {auth}")
    # No configured refspec, pruning, tag import or mutable target acceptance.
    git("fetch", "--no-tags", "--refmap=", REPOSITORY, "refs/heads/main", env=env)
    if git("rev-parse", "--verify", "FETCH_HEAD^{commit}") != NEW:
        raise Rejected("AUTHORITATIVE_MAIN_MOVED")
    if git("rev-parse", "--verify", f"{NEW}^{{commit}}") != NEW:
        raise Rejected("TARGET_OBJECT_INVALID")
    git("merge-base", "--is-ancestor", OLD, NEW)


def preserved():
    worktree = CHANGE / "atenea"
    expected = {"workspace-v1.json": WORKSPACE_HASH,
                "branch-publication-v1.json": PUBLICATION_HASH}
    for name, fingerprint in expected.items():
        path = CHANGE / name
        if not stat.S_ISREG(path.lstat().st_mode) or digest(path.read_bytes()) != fingerprint:
            raise Rejected("WS21_EVIDENCE_CHANGED")
    options = ["/usr/bin/git", "-c", f"safe.directory={worktree}", "-c",
               "core.fsmonitor=false", "-C", str(worktree)]
    if (command([*options, "rev-parse", "HEAD"], git_environment()) != HEAD
            or command([*options, "symbolic-ref", "--short", "HEAD"], git_environment()) != BRANCH
            or command([*options, "status", "--porcelain=v1", "--untracked-files=all"],
                       git_environment())):
        raise Rejected("WS21_WORKSPACE_CHANGED")
    state = {"ws21": expected, "codexRegistry": digest(CODEX_REGISTRY.read_bytes())}
    for name in ("current", "previous"):
        path = CODEX / name
        if not path.is_symlink() or path.lstat().st_uid != 0:
            raise Rejected("CODEX_LINK_AUTHORITY_INVALID")
        state[name] = os.readlink(path)
    for path in sorted(CODEX.rglob("*.json")):
        if not stat.S_ISREG(path.lstat().st_mode):
            raise Rejected("CODEX_RECORD_INVALID")
        state[str(path.relative_to(CODEX))] = digest(path.read_bytes())
    return state


def save(path, data, mode=0o600):
    descriptor, temporary = tempfile.mkstemp(prefix=".source-sync-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def persist(record):
    save(RECORD, (json.dumps(record, sort_keys=True) + "\n").encode())


def load():
    record = json.loads(trusted(RECORD, 0o600).read_bytes())
    if (record.get("protocol") != "atenea-project-source-sync/v1"
            or record.get("oldCommit") != OLD or record.get("newCommit") != NEW
            or record.get("oldConfigSha256") != OLD_HASH
            or record.get("newConfigSha256") != NEW_HASH):
        raise Rejected("DURABLE_IDENTITY_INVALID")
    uuid.UUID(record["operationId"])
    return record


def restore(record):
    before = trusted(BACKUP, 0o600).read_bytes()
    config_hash = digest(trusted(CONFIG, 0o644).read_bytes())
    ref = git("rev-parse", "--verify", REF)
    if digest(before) != OLD_HASH or config_hash not in {OLD_HASH, NEW_HASH} or ref not in {OLD, NEW}:
        raise Rejected("ROLLBACK_FOREIGN_STATE")
    if preserved() != record["preserved"]:
        raise Rejected("ROLLBACK_PROTECTED_STATE_CHANGED")
    command(["/usr/bin/systemctl", "stop", SERVICE])
    if config_hash == NEW_HASH:
        save(CONFIG, before, 0o644)
    if ref == NEW:
        git("update-ref", REF, OLD, NEW)
    command(["/usr/bin/systemctl", "start", SERVICE])
    check()
    record["state"] = "ROLLED_BACK"
    persist(record)


def apply_locked():
    if RECORD.exists() or RECORD.is_symlink():
        record = load()
        if record["state"] == "SUCCEEDED":
            check()
            if (digest(CONFIG.read_bytes()) != NEW_HASH
                    or git("rev-parse", "--verify", REF) != NEW
                    or preserved() != record["preserved"]):
                raise Rejected("COMPLETED_STATE_CHANGED")
            return record
        if record["state"] == "APPLYING":
            # An interrupted promotion is restored, never silently repeated.
            try:
                restore(record)
            except Exception:
                record["state"] = "ROLLBACK_FAILED"
                persist(record)
                raise Rejected("ROLLBACK_FAILED") from None
            raise Rejected("INTERRUPTED_OPERATION_RESTORED")
        raise Rejected("TERMINAL_OPERATION_REQUIRES_REVIEW")
    check()
    before = CONFIG.read_bytes()
    if digest(before) != OLD_HASH or git("rev-parse", "--verify", REF) != OLD:
        raise Rejected("PREDECESSOR_NOT_EXACT")
    state = preserved()
    fetch()
    check()
    if CONFIG.read_bytes() != before or preserved() != state:
        raise Rejected("PRECONDITION_MOVED")
    after = before.replace(OLD.encode(), NEW.encode())
    if before.count(OLD.encode()) != 1 or digest(after) != NEW_HASH:
        raise Rejected("CONFIG_REPLACEMENT_NOT_EXACT")
    save(BACKUP, before)
    record = {"protocol": "atenea-project-source-sync/v1", "operationId": str(uuid.uuid4()),
              "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "oldCommit": OLD, "newCommit": NEW, "oldConfigSha256": OLD_HASH,
              "newConfigSha256": NEW_HASH, "state": "APPLYING", "preserved": state}
    persist(record)
    try:
        # Keep the worker stopped across the two-resource commit. A crash
        # cannot release the flock and admit work against a half-updated pair.
        command(["/usr/bin/systemctl", "stop", SERVICE])
        git("update-ref", REF, NEW, OLD)
        save(CONFIG, after, 0o644)
        command(["/usr/bin/systemctl", "start", SERVICE])
        check()
        if preserved() != state:
            raise Rejected("PROTECTED_STATE_CHANGED")
        record["state"] = "SUCCEEDED"
        record["completedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        persist(record)
    except Exception as error:
        record["state"] = "APPLYING"
        record["failureCode"] = str(error) if isinstance(error, Rejected) else "OPERATION_FAILED"
        try:
            restore(record)
        except Exception:
            record["state"] = "ROLLBACK_FAILED"
            persist(record)
            raise Rejected("ROLLBACK_FAILED") from None
        raise Rejected("POSTCONDITION_FAILED_RESTORED") from None
    return record


@contextlib.contextmanager
def guard():
    trusted(LOCK, 0o640)
    with LOCK.open("rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    if os.geteuid() != 0 or sys.argv[1:] not in (["--apply"], ["--inspect"]):
        raise Rejected("ROOT_FIXED_OPERATION_REQUIRED")
    os.umask(0o007)
    with guard():
        if sys.argv[1] == "--inspect":
            record = load()
        else:
            # Authority must be closed even if a journal directory exists.
            for parent in (JOURNAL.parent, *JOURNAL.parent.parents):
                info = parent.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                    raise Rejected("JOURNAL_PARENT_AUTHORITY_INVALID")
            if not JOURNAL.exists() and not JOURNAL.is_symlink():
                JOURNAL.mkdir(mode=0o700)
            info = JOURNAL.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise Rejected("JOURNAL_AUTHORITY_INVALID")
            record = apply_locked()
        print(json.dumps({key: value for key, value in record.items() if key != "preserved"}))


if __name__ == "__main__":
    try:
        main()
    except (Rejected, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"state": "REJECTED", "code": str(error) if isinstance(error, Rejected)
                          else "OPERATION_FAILED"}))
        sys.exit(1)
