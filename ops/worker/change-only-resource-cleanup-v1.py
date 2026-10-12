#!/usr/bin/env python3
"""One-off operator retirement of the reviewed change-only trial set.

No caller targets, commands, versions, paths, hosts, symlinks or operation IDs.
The operation is offline, backed up, resumable, and never publishes a release
receipt before every absence/protection postcondition has been checked.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import tarfile
import tempfile

SPEC = importlib.util.spec_from_file_location("resource_plan", Path(__file__).with_name("change-only-resource-plan-v1.py"))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
OPERATION = p.OPERATION
ARCHIVE = Path("/srv/atenea/backups/ax42") / OPERATION
RECEIPT = Path("/etc/atenea-release-v1/change-only-resources.json")
REGISTRY = Path("/etc/atenea-worker/beautips-project-codex-v1.json")
MIRRORS = Path("/srv/atenea/repositories")
SERVICES = ("atenea-agent-run-worker-v1.service", "atenea-session-preview-v1.service",
            "atenea-worksession-attachment-v1.service", "atenea-release-control-v1.service")
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
VALIDATION_TERMINAL = TERMINAL | {"VALIDATION_FAILED", "CANDIDATE_FAILED", "INFRASTRUCTURE_FAILED",
                                  "OWNERSHIP_FAILED", "CANCELLED"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def normalized_resources(values):
    # Docker derives Mounts from a map and does not promise array order.
    # Keep every field and duplicate; only ordering has no ownership meaning.
    result = json.loads(json.dumps(values))
    for item in result:
        if item["kind"] == "container":
            item["mounts"] = sorted(item.get("mounts", []), key=lambda m: canonical(m))
    return sorted(result, key=lambda r: (r["slot"], r["kind"], r["id"]))


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def authority(path, directory=False):
    s = path.lstat()
    p.require(not path.is_symlink() and s.st_uid == 0 and (directory or s.st_gid == 0)
              and not stat.S_IMODE(s.st_mode) & 0o022
              and (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1),
              "ROOT_AUTHORITY_REQUIRED")
    p.require(not {"system.posix_acl_access", "system.posix_acl_default"}.intersection(os.listxattr(path)),
              "FOREIGN_AUTHORITY_ACL")


def private_directory(path):
    if not path.exists():
        authority(path.parent, True)
        path.mkdir(mode=0o700)
    authority(path, True)
    p.require(stat.S_IMODE(path.stat().st_mode) == 0o700, "PRIVATE_ARCHIVE_REQUIRED")


def write_private(path, value):
    authority(path.parent, True)
    if path.exists():
        authority(path)
    fd, temporary = tempfile.mkstemp(prefix=".cleanup-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(canonical(value)); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def replace_fixed_worker_state(value, expected_sha):
    # The worker owns its index; do not broaden the root-private journal writer
    # to arbitrary owners or paths. This is the single fixed data contraction.
    raw, before = p.read_regular(p.EXECUTIONS)
    p.require(p.digest(raw) == expected_sha and before.st_uid == 999
              and stat.S_IMODE(before.st_mode) == 0o600, "WORKER_STATE_AUTHORITY_MOVED")
    fd, temporary = tempfile.mkstemp(prefix=".change-only-state-", dir=p.EXECUTIONS.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value)); stream.flush()
            os.fchown(stream.fileno(), before.st_uid, before.st_gid)
            os.fchmod(stream.fileno(), 0o600); os.fsync(stream.fileno())
        current, _ = p.read_regular(p.EXECUTIONS)
        p.require(p.digest(current) == expected_sha, "WORKER_STATE_MOVED")
        os.replace(temporary, p.EXECUTIONS)
        directory = os.open(p.EXECUTIONS.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def inventory_tree(root):
    """No link traversal, hardlink reads, sockets, devices or executable input."""
    p.require(root.exists() and not root.is_symlink(), "ARCHIVE_SOURCE_UNAVAILABLE")
    nodes = []
    def visit(path):
        s = path.lstat()
        relative = str(path.relative_to(root))
        item = {"path": relative, "mode": stat.S_IMODE(s.st_mode), "uid": s.st_uid, "gid": s.st_gid}
        if stat.S_ISLNK(s.st_mode):
            item.update(kind="link", target=os.readlink(path))
        elif stat.S_ISDIR(s.st_mode):
            item["kind"] = "dir"
            nodes.append(item)
            for child in sorted(path.iterdir()): visit(child)
            return
        else:
            p.require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "UNEXPECTED_ARCHIVE_STRUCTURE")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                observed = os.fstat(fd)
                p.require((s.st_ino, s.st_dev) == (observed.st_ino, observed.st_dev), "ARCHIVE_SOURCE_MOVED")
                h = hashlib.sha256()
                with os.fdopen(os.dup(fd), "rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
                after = os.fstat(fd)
                p.require((observed.st_size, observed.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "ARCHIVE_SOURCE_MOVED")
                item.update(kind="file", size=after.st_size, sha256=h.hexdigest())
            finally: os.close(fd)
        nodes.append(item)
    visit(root)
    p.require(len(nodes) <= 250000, "ARCHIVE_LIMIT_EXCEEDED")
    return sorted(nodes, key=lambda n: n["path"])


def archive_tree(source, output):
    before = inventory_tree(source)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as raw:
        with tarfile.open(fileobj=raw, mode="w", dereference=False) as archive:
            for node in before:
                path = source if node["path"] == "." else source / node["path"]
                info = archive.gettarinfo(str(path), arcname=node["path"])
                if node["kind"] == "file":
                    source_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(source_fd, "rb") as stream: archive.addfile(info, stream)
                else: archive.addfile(info)
        raw.flush(); os.fsync(raw.fileno())
    p.require(before == inventory_tree(source), "ARCHIVE_SOURCE_MOVED")
    result = {"nodes": before, "sha256": file_hash(output), "size": output.stat().st_size}
    verify_archive(output, result)
    return result


def verify_archive(path, evidence):
    p.require(file_hash(path) == evidence["sha256"] and path.stat().st_size == evidence["size"], "ARCHIVE_CHECKSUM_MISMATCH")
    expected = {n["path"]: n for n in evidence["nodes"]}
    seen = set()
    with tarfile.open(path, "r") as archive:
        for member in archive:
            p.require(member.name in expected and member.name not in seen, "ARCHIVE_STRUCTURE_MISMATCH")
            seen.add(member.name); node = expected[member.name]
            p.require((member.mode, member.uid, member.gid) == (node["mode"], node["uid"], node["gid"]), "ARCHIVE_METADATA_MISMATCH")
            if node["kind"] == "file":
                p.require(member.isfile() and member.size == node["size"], "ARCHIVE_STRUCTURE_MISMATCH")
                h = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
                p.require(h.hexdigest() == node["sha256"], "ARCHIVE_CONTENT_MISMATCH")
            elif node["kind"] == "dir": p.require(member.isdir(), "ARCHIVE_STRUCTURE_MISMATCH")
            else: p.require(member.issym() and member.linkname == node["target"], "ARCHIVE_STRUCTURE_MISMATCH")
    p.require(seen == set(expected), "ARCHIVE_STRUCTURE_MISMATCH")


def filtered_worker_state(raw):
    state = json.loads(raw)
    p.require(set(state) == {"workerId", "protocol", "executions", "validations", "unactivatedWorkspaceReleases"}
              and state["workerId"] == "ax42-01" and state["protocol"] == "agent-run-worker/v1"
              and isinstance(state["executions"], dict), "WORKER_STATE_AUTHORITY_MOVED")
    p.require(all(e.get("status") in TERMINAL for e in state["executions"].values())
              and all(v.get("state") in VALIDATION_TERMINAL for v in state["validations"].values())
              and not state["unactivatedWorkspaceReleases"], "NON_TERMINAL_OPERATION")
    identity = "remote:ax42-01:change:" + p.REAL_CHANGE
    state["executions"] = {k: v for k, v in state["executions"].items() if v.get("workspaceIdentity") == identity}
    p.require(all(v.get("workspaceIdentity") == identity for v in state["validations"].values()), "FOREIGN_VALIDATION_HISTORY")
    return state


class Host:
    """Only fixed operator commands. The manifest is pinned, never client input."""
    def __init__(self, manifest):
        self.manifest = manifest

    def fenced(self):
        for name in SERVICES:
            state = p.command(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", name])
            p.require(state == "inactive", "WORKER_MAINTENANCE_REQUIRED")
        # Existing operator SSH transport, read-only. No new key or root SSH.
        response = p.command(["/usr/sbin/runuser", "-u", "jose", "--", "/usr/bin/ssh",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
            "-o", "IdentityAgent=/home/jose/.config/dev/common/ssh-agent.sock", "jose@atenea.yudri.es",
            "/usr/bin/docker inspect --format '{{json .State}}' atenea-backend-prod"])
        p.require(json.loads(response).get("Running") is False, "APP_MAINTENANCE_REQUIRED")
        installer = Path("/usr/local/libexec/atenea/install-agent-run-worker-v1.sh")
        authority(installer)
        installed, _ = p.read_regular(installer)
        start = installed.find(b"\nverify_project_change_only_configuration() {\n")
        end = installed.find(b"\n}\n", start) if start >= 0 else -1
        p.require(start >= 0 and end >= 0 and p.digest(installed[start + 1:end + 3]) ==
                  self.manifest["changeOnlyVerifierSha256"], "CHANGE_ONLY_PLATFORM_INSTALL_REQUIRED")

    def refs(self):
        result = {}
        for name in self.manifest["mirrorConfigurationSha256"]:
            mirror = MIRRORS / name
            raw, _ = p.read_regular(mirror / "config")
            p.require(p.digest(raw) == self.manifest["mirrorConfigurationSha256"][name], "MIRROR_CONFIGURATION_MOVED")
            result[name] = dict(line.split(" ", 1) for line in p.git(mirror, "for-each-ref", "--format=%(refname) %(objectname)").splitlines())
        return result

    def protected(self):
        real = p.WORKSPACES / "changes" / p.REAL_CHANGE
        config, _ = p.read_regular(p.CONFIG)
        codex = Path("/srv/atenea/worker/codex-releases-v1")
        refs = {name: {ref: sha for ref, sha in values.items() if ref not in self.manifest["retireBranchRefs"].get(name, {})}
                for name, values in self.refs().items()}
        return {"realTreeSha256": p.digest(canonical(inventory_tree(real))), "refs": refs,
                "projectConfigurationSha256": p.digest(config),
                "codexCurrent": os.readlink(codex / "current"), "codexPrevious": os.readlink(codex / "previous")}

    def paths(self):
        roots = [p.WORKSPACES / r["kind"] / r["id"] for r in self.manifest["reviewedRoots"] if r["disposition"] == "TRIAL"]
        ancillary = {Path(path) for r in self.manifest["reviewedRoots"] if r["disposition"] == "TRIAL" for path in r["ancillaryPaths"]}
        ancillary.update(map(Path, self.manifest["supplementalTrialPaths"]))
        paths = roots + sorted(ancillary)
        p.require(all(p.REAL_CHANGE not in str(path) and "e18f3461-1489-43cc-a7ad-99d60e84b8c5" not in str(path) for path in paths), "PROTECTED_OWNER_SELECTED")
        return paths

    def capture(self):
        config, _ = p.read_regular(p.CONFIG)
        p.require(p.digest(config) == self.manifest["projectConfigurationSha256"], "PROJECT_CONFIGURATION_MOVED")
        roots = p.observe_roots(self.manifest)
        expected = self.manifest["reviewedRoots"]
        p.require(len(roots) == len(expected), "WORKSPACE_SET_MOVED")
        for row in roots:
            old = next((r for r in expected if (r["kind"], r["id"]) == (row["kind"], row["id"])), None)
            p.require(old is not None and not row.get("unexpectedStructure") and row["records"] == old["records"]
                      and (row.get("head"), row.get("branch"), row.get("dirty")) == (old["head"], old["branch"], old["dirty"]), "WORKSPACE_IDENTITY_MOVED")
        refs = self.refs()
        for name, targets in self.manifest["retireBranchRefs"].items():
            p.require(all(refs[name].get(ref) == sha for ref, sha in targets.items()), "BRANCH_REF_MOVED")
        raw, _ = p.read_regular(p.EXECUTIONS)
        p.require(p.digest(raw) == self.manifest["workerStateSha256"], "WORKER_STATE_MOVED")
        filtered = filtered_worker_state(raw)
        registry, _ = p.read_regular(REGISTRY)
        p.require(p.digest(registry) == self.manifest["beautipsRegistryRetirement"]["before"], "BEAUTIPS_REGISTRY_MOVED")
        resources = self.runtime_observation()
        p.require(normalized_resources(resources["targets"]) == normalized_resources(self.manifest["runtimeResources"]), "RUNTIME_OWNERSHIP_MOVED")
        return {"protected": self.protected(), "protectedRuntime": resources["protected"], "filteredWorkerState": filtered,
                "workerStateBefore": p.digest(raw), "registryBefore": p.digest(registry),
                "paths": [str(path) for path in self.paths() if path.exists()]}

    def runtime_observation(self):
        targets, protected, all_identifiers, running_targets = [], [], [], []
        owners = {r["id"] for r in self.manifest["reviewedRoots"] if r["disposition"] == "TRIAL"} | set(self.manifest["trialRemoteSessionIds"].values())
        volumes = {(r["slot"], r["name"]) for r in self.manifest["runtimeResources"] if r["kind"] == "volume"}
        for slot, engine in enumerate(p.ENGINES):
            base = ["/usr/bin/docker", "--host=" + engine]
            for kind in ("container", "network", "volume"):
                listing = ["ps", "-aq", "--no-trunc"] if kind == "container" else [kind, "ls", "-q"]
                for identifier in p.command(base + listing).splitlines():
                    obj = json.loads(p.command(base + [kind, "inspect", identifier]))[0]
                    all_identifiers.append((slot, kind, obj.get("Id") or obj["Name"]))
                    labels = (obj.get("Config", {}) if kind == "container" else obj).get("Labels") or {}
                    owned = labels.get("com.atenea.session") in owners
                    if not owned:
                        if kind == "container":
                            protected.append({"slot": slot, "id": obj["Id"], "image": obj["Image"], "running": obj["State"]["Running"]})
                            for mount in obj.get("Mounts", []):
                                p.require((slot, mount.get("Name")) not in volumes, "VOLUME_HAS_FOREIGN_CONSUMER")
                        continue
                    row = {"slot": slot, "kind": kind, "id": obj.get("Id") or obj["Name"], "name": obj["Name"],
                           "labels": {k: v for k, v in labels.items() if k.startswith("com.atenea.")}}
                    p.require(slot > 0 and labels.get("com.atenea.engine") == "atenea-runtime-engine-v1", "FOREIGN_RUNTIME_AUTHORITY")
                    if kind == "container":
                        if obj["State"]["Running"]: running_targets.append(obj["Id"])
                        row.update(image=obj["Image"], mounts=[{k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")} for m in obj.get("Mounts", [])], ports=obj["HostConfig"]["PortBindings"])
                        p.require(all(m["Type"] == "volume" and (slot, m["Name"]) in volumes for m in row["mounts"]), "UNAUTHORIZED_RUNTIME_MOUNT")
                    elif kind == "network": row.update(driver=obj["Driver"], containers=sorted((obj.get("Containers") or {}).keys()))
                    else:
                        row.update(driver=obj["Driver"], options=obj.get("Options"), mountpoint=obj["Mountpoint"])
                        expected = f"/var/lib/atenea-slots/slot{slot}/.local/share/docker/volumes/{obj['Name']}/_data"
                        p.require(row["driver"] == "local" and row["options"] is None and row["mountpoint"] == expected, "UNAUTHORIZED_VOLUME_ROOT")
                    targets.append(row)
        return {"targets": sorted(targets, key=lambda r: (r["slot"], r["kind"], r["id"])),
                "protected": sorted(protected, key=lambda r: (r["slot"], r["id"])),
                "allIdentifiers": all_identifiers, "runningTargets": running_targets}

    def docker(self, item, action):
        p.require(item in self.manifest["runtimeResources"], "UNREVIEWED_RUNTIME_TARGET")
        observation = self.runtime_observation()
        key = item["slot"], item["kind"], item["id"]
        if key not in observation["allIdentifiers"]:
            p.require(action == "remove", "CONTAINER_DISAPPEARED_BEFORE_BACKUP")
            return  # Lost acknowledgement: absence was proven in this engine.
        current = next((r for r in observation["targets"] if (r["slot"], r["kind"], r["id"]) == key), None)
        p.require(current is not None, "RUNTIME_OWNERSHIP_MOVED")
        comparable = dict(current)
        if item["kind"] == "network":
            p.require(set(current["containers"]).issubset(item["containers"]), "NETWORK_HAS_FOREIGN_CONSUMER")
            comparable["containers"] = item["containers"]
        p.require(normalized_resources([comparable]) == normalized_resources([item]), "RUNTIME_OWNERSHIP_MOVED")
        p.require(all(any((r["slot"], r["kind"], r["id"]) == (e["slot"], e["kind"], e["id"])
                              for e in self.manifest["runtimeResources"])
                      for r in observation["targets"]), "UNREVIEWED_RUNTIME_RESOURCE")
        base = ["/usr/bin/docker", "--host=" + p.ENGINES[item["slot"]]]
        if action == "stop": p.command(base + ["stop", "--time=20", item["id"]])
        elif item["kind"] == "container": p.command(base + ["rm", item["id"]])
        else: p.command(base + [item["kind"], "rm", item["id"]])

    def bundle(self, name, output):
        p.git(MIRRORS / name, "bundle", "create", str(output), "--all")
        p.git(MIRRORS / name, "bundle", "verify", str(output))

    def remove_worktree(self, row):
        root = p.WORKSPACES / row["kind"] / row["id"]
        tree = root / row["projectId"]
        mirror = MIRRORS / row["mirrorName"]
        if tree.exists():
            p.require(p.git(tree, "rev-parse", "HEAD") == row["head"] and p.git(tree, "symbolic-ref", "--quiet", "HEAD") == row["branch"], "WORKTREE_IDENTITY_MOVED")
            p.git(mirror, "worktree", "remove", "--force", str(tree))
        p.require(not tree.exists(), "WORKTREE_REMOVAL_NOT_CONFIRMED")

    def remove_ref(self, name, ref, sha):
        current = self.refs()[name].get(ref)
        if current is not None:
            p.require(current == sha, "BRANCH_REF_MOVED")
            p.git(MIRRORS / name, "update-ref", "-d", ref, sha)
        p.require(ref not in self.refs()[name], "BRANCH_REMOVAL_NOT_CONFIRMED")


class Cleanup:
    def __init__(self, host, archive=ARCHIVE, receipt=RECEIPT):
        self.host, self.archive, self.receipt = host, archive, receipt
        self.journal_path = archive / "journal.json"
        self.journal = None

    def persist(self):
        write_private(self.journal_path, self.journal)

    def step(self, key, action):
        if key in self.journal["done"]: return
        self.host.fenced()
        self.journal["pending"] = key; self.persist()
        action()
        self.journal["done"].append(key); self.journal["pending"] = None; self.persist()

    def backup(self, source):
        name = p.digest(str(source).encode()) + ".tar"
        evidence = self.journal["archives"].get(str(source))
        if evidence is not None:
            verify_archive(self.archive / name, evidence); return
        path = self.archive / name
        if path.exists():
            # A fully written tar can outlive its acknowledgement. Reconcile
            # only against the unchanged source and verify every member/hash.
            evidence = {"nodes": inventory_tree(source), "sha256": file_hash(path), "size": path.stat().st_size}
            verify_archive(path, evidence)
        else:
            evidence = archive_tree(source, path)
        self.journal["archives"][str(source)] = evidence; self.persist()

    def verify_backups(self):
        for source, evidence in self.journal["archives"].items():
            verify_archive(self.archive / (p.digest(source.encode()) + ".tar"), evidence)
        for name, sha in self.journal["bundles"].items():
            p.require(file_hash(self.archive / name) == sha, "BUNDLE_CHECKSUM_MISMATCH")

    def quarantine(self, source, removed_project=None):
        evidence = self.journal["archives"][str(source)]
        expected = evidence["nodes"]
        if removed_project:
            expected = [n for n in expected if n["path"] != removed_project and not n["path"].startswith(removed_project + "/")]
        destination = self.archive / "retired" / p.digest(str(source).encode())
        if source.exists():
            p.require(not destination.exists() and inventory_tree(source) == expected, "RETIREMENT_SOURCE_MOVED")
            os.rename(source, destination)
        p.require(not source.exists() and destination.exists() and inventory_tree(destination) == expected, "RETIREMENT_NOT_CONFIRMED")

    def replace_worker_state(self):
        target = self.journal["before"]["filteredWorkerState"]
        data, info = p.read_regular(p.EXECUTIONS)
        if json.loads(data) == target: return
        p.require(p.digest(data) == self.journal["before"]["workerStateBefore"], "WORKER_STATE_MOVED")
        replace_fixed_worker_state(target, self.journal["before"]["workerStateBefore"])

    def retire_registry(self):
        transition = self.host.manifest["beautipsRegistryRetirement"]
        data, _ = p.read_regular(REGISTRY)
        if p.digest(data) == transition["after"]: return
        p.require(p.digest(data) == transition["before"], "BEAUTIPS_REGISTRY_MOVED")
        write_private(REGISTRY, transition["final"]); os.chmod(REGISTRY, 0o644)
        p.require(file_hash(REGISTRY) == transition["after"], "REGISTRY_RETIREMENT_NOT_CONFIRMED")

    def remove_worktree(self, row):
        root = p.WORKSPACES / row["kind"] / row["id"]
        if (root / row["projectId"]).exists():
            # HEAD equality alone does not protect newly modified/untracked
            # content. Every byte/permission/link must match the verified tar.
            p.require(inventory_tree(root) == self.journal["archives"][str(root)]["nodes"],
                      "WORKTREE_CONTENT_MOVED_AFTER_BACKUP")
        self.host.remove_worktree(row)

    def verify(self):
        self.host.fenced(); self.verify_backups()
        p.require(self.host.protected() == self.journal["before"]["protected"], "PROTECTED_RESOURCES_MOVED")
        runtime = self.host.runtime_observation()
        p.require(not runtime["targets"] and runtime["protected"] == self.journal["before"]["protectedRuntime"], "RUNTIME_POSTCONDITION_FAILED")
        p.require(all(not Path(path).exists() for path in self.journal["before"]["paths"]), "TRIAL_FILES_REMAIN")
        refs = self.host.refs()
        p.require(all(ref not in refs[name] for name, targets in self.host.manifest["retireBranchRefs"].items() for ref in targets), "TRIAL_BRANCHES_REMAIN")
        data, _ = p.read_regular(p.EXECUTIONS)
        p.require(json.loads(data) == self.journal["before"]["filteredWorkerState"], "WORKER_INVENTORY_POSTCONDITION_FAILED")
        p.require(file_hash(REGISTRY) == self.host.manifest["beautipsRegistryRetirement"]["after"], "REGISTRY_POSTCONDITION_FAILED")

    def apply(self):
        self.host.fenced()
        private_directory(self.archive)
        private_directory(self.archive / "retired")
        if self.journal_path.exists():
            authority(self.journal_path)
            self.journal = json.loads(self.journal_path.read_bytes())
            p.require(self.journal.get("operation") == OPERATION and self.journal.get("manifestSha256") == p.MANIFEST_SHA256, "RECOVERY_IDENTITY_MOVED")
        else:
            before = self.host.capture()
            p.require(all(Path(path).stat().st_dev == self.archive.stat().st_dev for path in before["paths"]),
                      "RETIREMENT_FILESYSTEM_REQUIRES_REVIEW")
            self.journal = {"schemaVersion": "change-only-resource-cleanup-journal-v1", "operation": OPERATION,
                            "manifestSha256": p.MANIFEST_SHA256, "state": "IN_PROGRESS", "before": before,
                            "archives": {}, "bundles": {}, "done": [], "pending": None,
                            "createdAt": datetime.now(timezone.utc).isoformat()}
            self.persist()
        # Code, records, configuration and terminal history are backed up
        # before quiescing the three exact sandbox containers.
        for source in [*map(Path, self.journal["before"]["paths"]), p.EXECUTIONS, REGISTRY]:
            self.step("archive:" + str(source), lambda source=source: self.backup(source))
        for name in self.host.manifest["mirrorConfigurationSha256"]:
            def bundle(name=name):
                output = self.archive / (name + ".bundle")
                if output.name in self.journal["bundles"]:
                    p.require(file_hash(output) == self.journal["bundles"][output.name], "BUNDLE_CHECKSUM_MISMATCH")
                    return
                p.require(not output.exists(), "UNACKNOWLEDGED_BUNDLE_REQUIRES_REVIEW")
                self.host.bundle(name, output)
                os.chmod(output, 0o600)
                self.journal["bundles"][output.name] = file_hash(output); self.persist()
            self.step("bundle:" + name, bundle)
        self.verify_backups()
        for item in self.host.manifest["runtimeResources"]:
            if item["kind"] == "container": self.step("stop:" + item["id"], lambda item=item: self.host.docker(item, "stop"))
        for item in self.host.manifest["runtimeResources"]:
            if item["kind"] == "volume":
                p.require(not self.host.runtime_observation()["runningTargets"], "VOLUME_BACKUP_REQUIRES_QUIESCENCE")
                source = Path(item["mountpoint"])
                self.step("volume-backup:" + item["id"], lambda source=source: self.backup(source))
        self.verify_backups()
        for kind in ("container", "network", "volume"):
            for item in self.host.manifest["runtimeResources"]:
                if item["kind"] == kind: self.step("remove:" + item["id"], lambda item=item: self.host.docker(item, "remove"))
        self.step("registry", self.retire_registry)
        for row in self.host.manifest["reviewedRoots"]:
            if row["disposition"] != "TRIAL": continue
            self.step("worktree:" + row["id"], lambda row=row: self.remove_worktree(row))
        for name, targets in self.host.manifest["retireBranchRefs"].items():
            for ref, sha in targets.items():
                self.step("ref:" + ref, lambda name=name, ref=ref, sha=sha: self.host.remove_ref(name, ref, sha))
        for source in map(Path, self.journal["before"]["paths"]):
            row = next((r for r in self.host.manifest["reviewedRoots"] if source == p.WORKSPACES / r["kind"] / r["id"]), None)
            self.step("retire:" + str(source), lambda source=source, row=row: self.quarantine(source, row["projectId"] if row else None))
        self.step("worker-state", self.replace_worker_state)
        self.verify()
        self.journal["state"] = "RELEASED"; self.persist()
        result = {"schemaVersion": "change-only-resource-cleanup-receipt-v1", "operation": OPERATION, "state": "RELEASED",
                  "preservedChangeKey": p.REAL_CHANGE, "trialSessionIds": self.host.manifest["trialSessionIds"],
                  "trialChangeKeys": self.host.manifest["trialChangeKeys"], "nonTerminalExecutions": 0,
                  "archiveSha256": p.digest(canonical({"archives": self.journal["archives"], "bundles": self.journal["bundles"]})),
                  "manifestSha256": p.MANIFEST_SHA256, "journalSha256": file_hash(self.journal_path)}
        if self.receipt.exists():
            authority(self.receipt); p.require(json.loads(self.receipt.read_bytes()) == result, "RECEIPT_IDENTITY_MOVED")
        else: write_private(self.receipt, result)
        return result


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    group = parser.add_mutually_exclusive_group(required=True)
    for mode in ("plan", "apply", "verify"): group.add_argument("--" + mode, action="store_true")
    return parser.parse_args(argv)


def main():
    args = parse_arguments()
    p.require(os.geteuid() == 0 and socket.gethostname() == "codex-worker-01", "FIXED_AX42_ROOT_OPERATOR_REQUIRED")
    manifest = p.load_manifest(); host = Host(manifest)
    if args.plan:
        before = host.capture()
        print(json.dumps({"operation": OPERATION, "state": "READY_FOR_MAINTENANCE",
                          "trialRoots": sum(r["disposition"] == "TRIAL" for r in manifest["reviewedRoots"]),
                          "runtimeResources": len(manifest["runtimeResources"]), "retiredBranches": sum(map(len, manifest["retireBranchRefs"].values())),
                          "preservedChangeKey": p.REAL_CHANGE, "maintenanceRequired": True, "mutationsPerformed": False}, sort_keys=True))
        return
    for source in (Path(__file__), Path(__file__).with_name("change-only-resource-plan-v1.py"), p.MANIFEST):
        authority(source)
        for parent in source.parents: authority(parent, True)
    for parent in (Path("/srv/atenea/backups"), ARCHIVE.parent): authority(parent, True)
    for parent in RECEIPT.parents: authority(parent, True)
    private_directory(ARCHIVE)
    lock_path = ARCHIVE / "operation.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        task = Cleanup(host)
        if args.verify:
            authority(task.journal_path); task.journal = json.loads(task.journal_path.read_bytes())
            p.require(task.journal["state"] == "RELEASED", "RELEASE_NOT_COMPLETED")
            task.verify(); print("CHANGE_ONLY_RESOURCE_VERIFY PASS")
        else:
            result = task.apply(); print(json.dumps(result, sort_keys=True))
    finally: os.close(fd)


if __name__ == "__main__":
    try: main()
    except (p.Refused, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        raise SystemExit("RESOURCE_CLEANUP_STOPPED: " + (str(error) if isinstance(error, p.Refused) else type(error).__name__))
