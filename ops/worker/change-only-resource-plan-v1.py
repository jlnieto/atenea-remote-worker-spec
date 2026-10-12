#!/usr/bin/env python3
"""Closed, read-only preflight for the one-off change-only cleanup.

This is deliberately NOT a producer of a RELEASED receipt. Presence is not
release; an uncorrelated root or a non-session WIP branch is not disposable.
No install, stop, Docker mutation, Git mutation, backup or unlink is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess

OPERATION = "change-only-20261012"
REAL_CHANGE = "59315b6e-59bc-4884-9def-356e1ca86ef4"
WORKSPACES = Path("/srv/atenea/workspaces")
CONFIG = Path("/etc/atenea-worker/project-codex-v1.json")
EXECUTIONS = Path("/srv/atenea/worker/agent-runs-v1/executions.json")
MANIFEST = Path(__file__).with_name("change-only-resource-manifest-v1.json")
MANIFEST_SHA256 = "6fc6d26697bf27958440248e5f311e5d01966f588659a5b1210562feed221b51"
ENGINES = ("unix:///run/user/1000/docker.sock",) + tuple(
    f"unix:///run/atenea-runtime/slot{i}/docker.sock" for i in range(1, 5))
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}


class Refused(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise Refused(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path, limit=16 * 1024 * 1024):
    # Never follow a caller/package link even for a read-only observation.
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "SYMLINK_AUTHORITY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                "AMBIGUOUS_FILE_AUTHORITY")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        require((info.st_ino, info.st_size, info.st_mtime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns), "OBSERVATION_MOVED")
        return data, info
    finally:
        os.close(fd)


def load_manifest():
    data, _ = read_regular(MANIFEST)
    require(digest(data) == MANIFEST_SHA256, "MANIFEST_BYTES_MOVED")
    value = json.loads(data)
    require(value["operation"] == OPERATION and value["preservedChangeKey"] == REAL_CHANGE,
            "MANIFEST_IDENTITY_MOVED")
    return value


def command(argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, env=ENV, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0, "READ_ONLY_OBSERVATION_UNAVAILABLE")
    return result.stdout.decode("utf-8").strip()


def git(tree, *arguments):
    return command(["/usr/bin/git", "--no-pager", "--no-optional-locks",
                    "-c", f"safe.directory={tree}", "-c", "core.fsmonitor=false",
                    "-c", "core.hooksPath=/dev/null", *arguments], cwd=tree)


def observe_roots(manifest):
    reviewed = {(r["kind"], r["id"]): r for r in manifest["reviewedRoots"]}
    result = []
    for kind in ("sessions", "changes"):
        parent = WORKSPACES / kind
        require(parent.is_dir() and not parent.is_symlink(), "WORKSPACE_PARENT_UNAVAILABLE")
        for root in sorted(parent.iterdir()):
            row = {"kind": kind, "id": root.name, "records": {}}
            if not root.is_dir() or root.is_symlink() or (kind, root.name) not in reviewed:
                row["unexpectedStructure"] = True
                result.append(row)
                continue
            expected = reviewed[kind, root.name]
            for name in expected["records"]:
                data, info = read_regular(root / name)
                row["records"][name] = {"sha256": digest(data), "uid": info.st_uid,
                                        "mode": oct(stat.S_IMODE(info.st_mode))}
            # Mirror commands are read-only and only run after the reviewed
            # config and gitdir have been verified. Unknown projects are held.
            project = expected["projectId"]
            tree = root / project
            if project in manifest["mirrorConfigurationSha256"] and tree.is_dir():
                mirror = Path("/srv/atenea/repositories") / (project + ".git")
                config_bytes, _ = read_regular(mirror / "config")
                require(digest(config_bytes) == manifest["mirrorConfigurationSha256"][project],
                        "MIRROR_CONFIGURATION_MOVED")
                marker, _ = read_regular(tree / ".git")
                require(marker.startswith(b"gitdir: "), "WORKTREE_AUTHORITY_MOVED")
                gitdir = Path(marker.decode().strip()[8:])
                require(gitdir.is_absolute() and gitdir.parent == mirror / "worktrees"
                        and gitdir.resolve() == gitdir, "WORKTREE_AUTHORITY_MOVED")
                common, _ = read_regular(gitdir / "commondir")
                require((gitdir / common.decode().strip()).resolve() == mirror,
                        "FOREIGN_GIT_COMMON_DIRECTORY")
                row.update(head=git(tree, "rev-parse", "HEAD"),
                           branch=git(tree, "symbolic-ref", "--quiet", "HEAD"),
                           dirty=bool(git(tree, "status", "--porcelain=v1", "--untracked-files=all")))
            result.append(row)
    return result


def observe_runtime_resources(manifest):
    # Inspect all namespaces, not just the allocation's claimed slot. Only
    # matching ownership labels are returned; Env, mounts and secrets are not.
    owners = set(manifest["trialRemoteSessionIds"].values()) | {
        r["id"] for r in manifest["reviewedRoots"] if r["kind"] == "sessions"}
    resources = []
    for engine in ENGINES:
        base = ["/usr/bin/docker", "--host=" + engine]
        for kind in ("container", "network", "volume"):
            listing = ["ps", "--all", "--quiet", "--no-trunc"] if kind == "container" else [kind, "ls", "--quiet"]
            ids = command(base + listing).splitlines()
            for resource_id in ids:
                require(resource_id and not resource_id.startswith("-"), "UNEXPECTED_RUNTIME_ID")
                obj = json.loads(command(base + [kind, "inspect", resource_id]))[0]
                labels = (obj.get("Config", {}) if kind == "container" else obj).get("Labels") or {}
                owner = labels.get("com.atenea.session")
                if owner in owners:
                    resources.append({"kind": kind, "owner": owner,
                                      "projectId": labels.get("com.atenea.project"), "id": resource_id})
    return resources


def plan(manifest, roots, active, resources, config_hash):
    expected = {(r["kind"], r["id"]): r for r in manifest["reviewedRoots"]}
    blockers, candidates = [], []
    seen = set()
    def block(code, kind=None, identity=None):
        blockers.append({"code": code, "kind": kind, "id": identity})
    if active:
        block("NON_TERMINAL_EXECUTION")
    if config_hash != manifest["projectConfigurationSha256"]:
        block("PROJECT_CONFIGURATION_MOVED")
    for row in roots:
        key = row["kind"], row["id"]
        if key in seen:
            block("DUPLICATE_ROOT", *key); continue
        seen.add(key)
        old = expected.get(key)
        if old is None or row.get("unexpectedStructure"):
            block("UNREVIEWED_ROOT", *key); continue
        if row["records"] != old["records"]:
            block("WORKSPACE_RECORD_MOVED", *key); continue
        if old["disposition"] == "UNBOUND_REVIEW_REQUIRED":
            block("UNBOUND_ROOT_NOT_CORRELATED_WITH_PROD", *key); continue
        if old["head"] is not None and (row.get("head"), row.get("branch"), row.get("dirty")) != (
                old["head"], old["branch"], old["dirty"]):
            block("WORKTREE_OBSERVATION_MOVED", *key); continue
        if old["disposition"] == "TRIAL":
            branch = "refs/heads/atenea/" + ("session-" if key[0] == "sessions" else "change-") + key[1]
            if row.get("branch") != branch:
                block("NON_SESSION_BRANCH_MUST_BE_PRESERVED", *key); continue
            candidates.append({"kind": key[0], "id": key[1], "dirty": bool(row.get("dirty"))})
    for key in expected.keys() - seen:
        block("REVIEWED_ROOT_MISSING", *key)
    for resource in resources:
        block("OWNED_RUNTIME_STILL_PRESENT", resource["kind"], resource["owner"])
    return {"schemaVersion": "change-only-resource-plan-v1", "operation": OPERATION,
            "state": "BLOCKED" if blockers else "READY_FOR_ARCHIVE",
            "preservedChangeKey": REAL_CHANGE, "nonTerminalExecutions": len(active),
            "archiveCandidates": sorted(candidates, key=lambda r: (r["kind"], r["id"])),
            "blockers": sorted(blockers, key=lambda r: (r["code"], r["kind"] or "", r["id"] or "")),
            "receiptEmitted": False, "mutationsPerformed": False}


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--plan", required=True, action="store_true")
    return parser.parse_args(argv)


def main():
    parse_arguments()
    require(os.geteuid() == 0 and socket.gethostname() == "codex-worker-01", "AX42_OPERATOR_REQUIRED")
    manifest = load_manifest()
    before, _ = read_regular(EXECUTIONS)
    executions = json.loads(before).get("executions")
    require(isinstance(executions, (list, dict)), "EXECUTION_AUTHORITY_UNAVAILABLE")
    if isinstance(executions, dict):
        executions = list(executions.values())
    active = [e.get("executionId") for e in executions if e.get("status") not in ("SUCCEEDED", "FAILED", "CANCELLED")]
    config, _ = read_regular(CONFIG)
    roots = observe_roots(manifest)
    resources = observe_runtime_resources(manifest)
    after, _ = read_regular(EXECUTIONS)
    require(before == after, "EXECUTION_OBSERVATION_MOVED")
    config_after, _ = read_regular(CONFIG)
    require(config == config_after, "PROJECT_CONFIGURATION_MOVED")
    print(json.dumps(plan(manifest, roots, active, resources, digest(config)), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refused, OSError, ValueError, subprocess.SubprocessError) as error:
        # No paths, credentials or Docker stderr in the diagnostic contract.
        raise SystemExit(str(error) if isinstance(error, Refused) else "READ_ONLY_PREFLIGHT_UNAVAILABLE")
