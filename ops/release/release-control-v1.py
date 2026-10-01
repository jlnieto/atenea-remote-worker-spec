#!/usr/bin/env python3
"""Durable, fixed-target Atenea release executor, outside the App lifecycle.

VPS: Unix socket for the App; AX42: authenticated private HTTP for the VPS.
Only reviewed successful GitHub main artifacts can become an executable plan.
No source builds, caller commands, caller paths or general SSH authority.
"""
from __future__ import annotations

import contextlib
import copy
import fcntl
import grp
import hashlib
import hmac
import http.server
import json
import os
import re
import shutil
import socketserver
import stat
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import sys
from pathlib import Path

PROTOCOL = "atenea-release/v1"
CONFIG = Path("/etc/atenea-release-v1/config.json")
ROOT = Path("/srv/atenea/release-v1")
SOCKET = Path("/run/atenea/release-v1/control.sock")
GITHUB_TOKEN = Path("/etc/atenea-release-v1/github.token")
PEER_TOKEN = Path("/etc/atenea-release-v1/ax42.token")
WORKER_TOKEN = Path("/etc/atenea-release-v1/worker.token")
STACK = Path("/srv/atenea/platform/stacks/prod")
OVERRIDE = STACK / "docker-compose.release-v1.json"
CURRENT = ROOT / "platform-current.json"
ADMISSION = Path("/run/atenea/release-v1/admission.lock")
INSTALLED_MARKER = Path("/etc/atenea-worker/release-control-v1.installed")
TARGETS = {"APP_PROD": "jlnieto/atenea", "ANDROID_STABLE": "jlnieto/atenea",
           "AX42_PLATFORM": "jlnieto/atenea-remote-worker-spec"}
TERMINAL = {"SUCCEEDED", "ROLLED_BACK", "FAILED", "BLOCKED", "ROLLBACK_FAILED"}
HEX = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class Rejected(Exception):
    def __init__(self, code="RELEASE_REJECTED"):
        self.code = code


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Rejected("CLOSED_REQUEST_REQUIRED")


def identity(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
        return value
    except ValueError:
        raise Rejected("INVALID_IDENTITY")


def trusted(path, mode=None):
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise Rejected("INSTALLED_AUTHORITY_INVALID")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or info.st_mode & 0o022 or (mode is not None and stat.S_IMODE(info.st_mode) != mode)):
        raise Rejected("INSTALLED_AUTHORITY_INVALID")
    return path


def trusted_directory(path, mode):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != mode:
        raise Rejected("INSTALLED_AUTHORITY_INVALID")
    for parent in path.parents:
        observed = parent.lstat()
        if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != 0 or observed.st_mode & 0o022:
            raise Rejected("INSTALLED_AUTHORITY_INVALID")


def save(path, value, *, mode=0o600):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".record.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def command(arguments, *, timeout=120, input=None, stdin=None, output=None):
    try:
        result = subprocess.run(arguments, stdin=stdin if stdin is not None else (subprocess.DEVNULL if input is None else None),
                                input=input, stdout=output or subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False,
                                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})
        if result.returncode != 0:
            raise Rejected("RELEASE_COMMAND_FAILED")
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise Rejected("RELEASE_COMMAND_FAILED")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubArtifacts:
    """The fixed workflow/run/artifact identity, plus GitHub's archive digest."""
    def api(self, path):
        token = trusted(GITHUB_TOKEN, 0o600).read_text().strip()
        request = urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            return json.load(response)

    def prepare(self, target, commit, destination):
        repo = TARGETS[target]
        current = self.api(f"/repos/{repo}/git/ref/heads/main")["object"]["sha"]
        if current != commit:
            raise Rejected("CANONICAL_MAIN_MOVED")
        runs = self.api(f"/repos/{repo}/actions/workflows/release-artifacts-v1.yml/runs?"
                        + urllib.parse.urlencode({"head_sha": commit, "branch": "main", "per_page": 100}))
        valid = [run for run in runs["workflow_runs"] if run["head_sha"] == commit
                 and run["head_branch"] == "main" and run["event"] == "push"
                 and run["head_repository"]["full_name"] == repo
                 and run["path"] == ".github/workflows/release-artifacts-v1.yml"]
        if not valid:
            raise Rejected("RELEASE_BUILD_PENDING")
        run = max(valid, key=lambda item: item["id"])
        if run["status"] != "completed":
            raise Rejected("RELEASE_BUILD_PENDING")
        if run["conclusion"] != "success":
            raise Rejected("RELEASE_BUILD_FAILED")
        artifacts = self.api(f"/repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100")
        name = "atenea-release-" + target.lower() + "-" + commit
        matches = [item for item in artifacts["artifacts"] if item["name"] == name and not item["expired"]]
        if len(matches) != 1 or not re.fullmatch(r"sha256:[0-9a-f]{64}", matches[0].get("digest", "")):
            raise Rejected("RELEASE_ARTIFACT_AMBIGUOUS")
        artifact = matches[0]
        metadata = {"runId": run["id"], "artifactId": artifact["id"],
                    "archiveSha256": artifact["digest"][7:]}
        token = trusted(GITHUB_TOKEN, 0o600).read_text().strip()
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact['id']}/zip",
            headers={"Authorization": "Bearer " + token})
        try:
            urllib.request.build_opener(NoRedirect).open(request, timeout=30)
            raise Rejected("ARTIFACT_REDIRECT_REQUIRED")
        except urllib.error.HTTPError as error:
            if error.code != 302:
                raise Rejected("ARTIFACT_DOWNLOAD_FAILED")
            location = error.headers["Location"]
        parsed = urllib.parse.urlparse(location)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}
                or not parsed.hostname or not (parsed.hostname.endswith(".blob.core.windows.net")
                        or parsed.hostname.endswith(".githubusercontent.com"))):
            raise Rejected("ARTIFACT_REDIRECT_REJECTED")
        archive = destination / "artifact.zip"
        with urllib.request.build_opener(NoRedirect).open(location, timeout=60) as response, archive.open("xb") as output:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > 6 * 1024**3:
                    raise Rejected("ARTIFACT_BOUND_EXCEEDED")
                output.write(block)
        if file_digest(archive) != metadata["archiveSha256"]:
            raise Rejected("ARTIFACT_DIGEST_MISMATCH")
        payload = {"APP_PROD": "image.tar", "ANDROID_STABLE": "app-unsigned.apk",
                   "AX42_PLATFORM": "platform.tar"}[target]
        with zipfile.ZipFile(archive) as bundle:
            if set(bundle.namelist()) != {"manifest.json", payload} or len(bundle.infolist()) != 2:
                raise Rejected("ARTIFACT_STRUCTURE_REJECTED")
            for item in bundle.infolist():
                if (item.file_size > 6 * 1024**3 or stat.S_ISLNK(item.external_attr >> 16)
                        or (item.filename == "manifest.json" and item.file_size > 16384)):
                    raise Rejected("ARTIFACT_STRUCTURE_REJECTED")
                with bundle.open(item) as source, (destination / item.filename).open("xb") as output:
                    shutil.copyfileobj(source, output)
        manifest = json.loads((destination / "manifest.json").read_bytes())
        exact(manifest, {"protocol", "target", "sourceCommit", "payloadSha256", "versionCode", "versionName", "flywayVersion"})
        if (manifest["protocol"] != PROTOCOL or manifest["target"] != target
                or manifest["sourceCommit"] != commit
                or not isinstance(manifest["payloadSha256"], str) or not DIGEST.fullmatch(manifest["payloadSha256"])
                or file_digest(destination / payload) != manifest["payloadSha256"]):
            raise Rejected("ARTIFACT_MANIFEST_MISMATCH")
        if target != "ANDROID_STABLE" and (manifest["versionCode"] is not None or manifest["versionName"] is not None):
            raise Rejected("ARTIFACT_MANIFEST_MISMATCH")
        if target != "APP_PROD" and manifest["flywayVersion"] is not None:
            raise Rejected("ARTIFACT_MANIFEST_MISMATCH")
        return {**metadata, **manifest}


class PlatformTarget:
    @staticmethod
    def protected_state():
        # Code installation must not select a Codex release, re-stage a
        # candidate or rewrite the reconciled release/ownership evidence.
        root = Path("/srv/atenea/worker/codex-releases-v1")
        observed = {}
        for name in ("current", "previous"):
            path = root / name
            if path.is_symlink():
                if path.lstat().st_uid != 0:
                    raise Rejected("CODEX_LINK_AUTHORITY_INVALID")
                target = os.readlink(path)
                parts = Path(target).parts
                if not parts or Path(target).is_absolute() or ".." in parts or parts[0] != "releases":
                    raise Rejected("CODEX_LINK_AUTHORITY_INVALID")
                observed[name] = target
            elif path.exists():
                raise Rejected("CODEX_LINK_AUTHORITY_INVALID")
            else:
                observed[name] = None
        for name in ("project-codex-v1.json", "codex-release-stage-v1.json"):
            path = Path("/etc/atenea-worker") / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise Rejected("PROTECTED_STATE_INVALID")
            observed[name] = file_digest(path)
        records = list(root.rglob("*.json"))
        if len(records) > 2000:
            raise Rejected("PROTECTED_STATE_INVALID")
        for path in sorted(records):
            if path.is_symlink() or not path.is_file():
                raise Rejected("PROTECTED_STATE_INVALID")
            value = json.loads(path.read_bytes())
            if path.name == "activation-v1.json" and value.get("state") not in {"SUCCEEDED", "FAILED", "ROLLED_BACK", "ROLLBACK_FAILED"}:
                raise Rejected("CODEX_OPERATION_NONTERMINAL")
            observed[str(path.relative_to(root))] = file_digest(path)
        return observed

    @contextlib.contextmanager
    def guard(self):
        trusted(ADMISSION, 0o640)
        with ADMISSION.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def inspect(self):
        record = json.loads(trusted(CURRENT, 0o600).read_bytes())
        if not HEX.fullmatch(record["sourceCommit"]):
            raise Rejected("BASELINE_INVALID")
        if set(record["installedFiles"]) != {"agent-run-worker-v1.py", "atenea-validation-v1.py", "project-codex-runner-v1.py"}:
            raise Rejected("BASELINE_INVALID")
        identity(record["artifactPlanId"])
        baseline = ROOT / "plans" / record["artifactPlanId"] / "platform/ops/worker/install-agent-run-worker-v1.sh"
        command(["/bin/bash", str(trusted(baseline)), "verify"])
        for name, expected in record["installedFiles"].items():
            if name not in {"agent-run-worker-v1.py", "atenea-validation-v1.py", "project-codex-runner-v1.py"}:
                raise Rejected("BASELINE_INVALID")
            if file_digest(trusted(Path("/usr/local/libexec/atenea") / name)) != expected:
                raise Rejected("PLATFORM_BASELINE_MOVED")
        state = json.loads(Path("/srv/atenea/worker/agent-runs-v1/executions.json").read_bytes())
        if (any(run["status"] not in {"SUCCEEDED", "FAILED", "CANCELLED"} for run in state["executions"].values())
                or any(run["state"] not in {"SUCCEEDED", "CANDIDATE_FAILED", "INFRASTRUCTURE_FAILED",
                    "POLICY_FAILED", "VALIDATION_FAILED", "OWNERSHIP_FAILED", "CANCELLED"}
                       for run in state.get("validations", {}).values())):
            raise Rejected("ACTIVE_WORKLOAD")
        return {**record, "protectedState": self.protected_state()}

    def stage(self, plan, directory):
        tree = directory / "platform"
        tree.mkdir(mode=0o700)
        with tarfile.open(directory / "platform.tar") as archive:
            members = archive.getmembers()
            if len(members) > 5000:
                raise Rejected("PLATFORM_BUNDLE_REJECTED")
            for member in members:
                parts = Path(member.name).parts
                if (not parts or Path(member.name).is_absolute() or ".." in parts
                        or parts[0] not in {"ops", "runtime-contract", "AGENTS.md"}
                        or not (member.isfile() or member.isdir()) or member.size > 32 * 1024**2):
                    raise Rejected("PLATFORM_BUNDLE_REJECTED")
                path = tree / member.name
                if member.isdir():
                    path.mkdir(mode=0o700, parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, path.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    path.chmod(0o700 if member.mode & 0o111 else 0o600)
        script = tree / "ops/worker/install-agent-run-worker-v1.sh"
        trusted(script)
        command(["/bin/bash", str(script), "plan"])

    def apply(self, plan, directory):
        command(["/usr/bin/env", "ATENEA_CONTROL_PLANE_TAILSCALE_IP=100.88.252.28", "/bin/bash",
                 str(directory / "platform/ops/worker/install-agent-run-worker-v1.sh"), "apply"], timeout=240)

    def verify(self, plan, directory):
        command(["/bin/bash", str(directory / "platform/ops/worker/install-agent-run-worker-v1.sh"), "verify"], timeout=120)
        if "predecessor" in plan and self.protected_state() != plan["predecessor"]["protectedState"]:
            raise Rejected("PROTECTED_STATE_MOVED")
        return {"sourceCommit": plan["sourceCommit"], "installedFiles": {
            name: file_digest(trusted(Path("/usr/local/libexec/atenea") / name)) for name in
            ("agent-run-worker-v1.py", "atenea-validation-v1.py", "project-codex-runner-v1.py")},
            "artifactPlanId": plan["planId"]}

    def rollback(self, plan, directory):
        previous = ROOT / "plans" / plan["predecessor"]["artifactPlanId"]
        self.apply(plan, previous)
        result = self.verify({"sourceCommit": plan["predecessor"]["sourceCommit"],
                              "planId": plan["predecessor"]["artifactPlanId"]}, previous)
        if self.protected_state() != plan["predecessor"]["protectedState"]:
            raise Rejected("PROTECTED_STATE_NOT_RESTORED")
        return result

    def commit(self, receipt):
        save(CURRENT, receipt)


class AppTarget:
    def __init__(self, config):
        self.config = config

    def guard(self):
        return contextlib.nullcontext()

    def compose(self, *args):
        files = self.config["composeFiles"]
        if (not isinstance(files, list) or not files or any(Path(path).parent != STACK for path in files)
                or str(OVERRIDE) not in files):
            raise Rejected("COMPOSE_AUTHORITY_INVALID")
        result = ["/usr/bin/docker", "compose"]
        for path in files:
            trusted(Path(path))
            result += ["-f", path]
        return result + ["--env-file", str(trusted(STACK / ".env")), *args]

    def inspect(self):
        backend = json.loads(command(["/usr/bin/docker", "inspect", "atenea-backend-prod"]))[0]
        postgres = json.loads(command(["/usr/bin/docker", "inspect", "atenea-postgres-prod"]))[0]
        effective = json.loads(command(self.compose("config", "--format", "json")))
        if (backend["Config"]["Labels"].get("com.docker.compose.project") != effective.get("name")
                or backend["Config"]["Labels"].get("com.docker.compose.service") != "atenea-backend-prod"
                or not postgres["State"]["Running"]):
            raise Rejected("COMPOSE_PROJECT_MISMATCH")
        source = backend["Config"]["Labels"].get("org.opencontainers.image.revision")
        if not source:
            image = json.loads(command(["/usr/bin/docker", "image", "inspect", backend["Image"]]))[0]
            source = image["Config"]["Labels"].get("org.opencontainers.image.revision")
        if not source or not HEX.fullmatch(source) or not backend["State"]["Running"]:
            raise Rejected("APP_BASELINE_INVALID")
        worker = self.worker_health()
        contract = copy.deepcopy(effective)
        contract["services"]["atenea-backend-prod"].pop("image",None)
        return {"sourceCommit": source, "imageId": backend["Image"], "postgresId": postgres["Id"],
                "postgresMountsSha256": digest(postgres["Mounts"]), "composeSha256": digest(effective),
                "composeContractSha256": digest(contract),
                "override": json.loads(trusted(OVERRIDE).read_bytes())}

    def worker_health(self):
        request = urllib.request.Request("http://100.81.98.93:8787/v1/health", headers={
            "Authorization": "Bearer " + trusted(WORKER_TOKEN, 0o600).read_text().strip()})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
            worker = json.load(response)
        if (worker.get("workerId") != "ax42-01" or worker.get("healthy") is not True
                or "project-codex-v4" not in worker.get("capabilities", [])
                or worker.get("normalInUse") != 0 or worker.get("queued") != 0):
            raise Rejected("WORKER_NOT_IDLE_OR_HEALTHY")
        return worker

    def stage(self, plan, directory):
        if not isinstance(plan["artifact"]["flywayVersion"], int) or isinstance(plan["artifact"]["flywayVersion"], bool) or plan["artifact"]["flywayVersion"] < 1:
            raise Rejected("FLYWAY_MANIFEST_REJECTED")
        with tarfile.open(directory / "image.tar") as archive:
            entries = archive.getmembers()
            if (len(entries) > 10000 or len({item.name for item in entries}) != len(entries)
                    or any((not item.isfile() and not item.isdir()) or Path(item.name).is_absolute()
                           or ".." in Path(item.name).parts for item in entries)):
                raise Rejected("IMAGE_ARCHIVE_REJECTED")
            manifests = [item for item in entries if item.name == "manifest.json"]
            if len(manifests) != 1 or manifests[0].size > 65536:
                raise Rejected("IMAGE_ARCHIVE_REJECTED")
            manifest = json.load(archive.extractfile(manifests[0]))
            if len(manifest) != 1 or manifest[0]["RepoTags"] != ["atenea-app:" + plan["sourceCommit"]]:
                raise Rejected("IMAGE_TAG_REJECTED")
            config_name = manifest[0]["Config"]
            item = archive.getmember(config_name)
            if not item.isfile() or item.size > 1024**2:
                raise Rejected("IMAGE_ARCHIVE_REJECTED")
            image_config = json.load(archive.extractfile(item))
            if image_config["config"]["Labels"].get("org.opencontainers.image.revision") != plan["sourceCommit"]:
                raise Rejected("IMAGE_REVISION_MISMATCH")
        command(["/usr/bin/docker", "image", "load", "--input", str(directory / "image.tar")], timeout=300)
        image = json.loads(command(["/usr/bin/docker", "image", "inspect", "atenea-app:" + plan["sourceCommit"]]))[0]
        save(directory / "image.json", {"imageId": image["Id"]})

    def apply(self, plan, directory):
        restore_version = command(["/usr/bin/docker", "exec", "atenea-postgres-prod", "pg_restore", "--version"])
        version = command(["/usr/bin/docker", "exec", "atenea-postgres-prod", "pg_dump", "--version"])
        if not version.startswith(b"pg_dump (PostgreSQL) 16.") or not restore_version.startswith(b"pg_restore (PostgreSQL) 16."):
            raise Rejected("POSTGRES_BACKUP_VERSION_REJECTED")
        backup = Path("/srv/atenea/backups/prod") / ("atenea_prod_release_" + plan["operationId"] + ".dump")
        directory_authority = backup.parent
        trusted_directory(directory_authority, 0o700)
        if not backup.exists():
            with backup.open("xb") as output:
                os.fchmod(output.fileno(), 0o600)
                command(["/usr/bin/docker", "exec", "atenea-postgres-prod", "/bin/sh", "-c",
                         'exec pg_dump -U "$POSTGRES_USER" -d atenea_prod -Fc'], output=output, timeout=600)
            with backup.open("rb") as source:
                command(["/usr/bin/docker", "exec", "-i", "atenea-postgres-prod", "pg_restore", "--list"],
                        stdin=source, timeout=120)
            save(directory / "backup.json", {"sha256": file_digest(backup), "sizeBytes": backup.stat().st_size,
                                               "createdAt": int(time.time())})
        else:
            evidence = json.loads(trusted(directory / "backup.json", 0o600).read_bytes())
            if file_digest(trusted(backup, 0o600)) != evidence["sha256"]:
                raise Rejected("POSTGRES_BACKUP_EVIDENCE_MISMATCH")
        override = copy.deepcopy(plan["predecessor"]["override"])
        override["services"]["atenea-backend-prod"]["image"] = json.loads((directory / "image.json").read_bytes())["imageId"]
        save(OVERRIDE, override)
        command(self.compose("up", "-d", "--no-deps", "--no-build", "atenea-backend-prod"), timeout=180)

    def verify(self, plan, directory):
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8081/actuator/health", timeout=3) as response:
                    if json.load(response).get("status") == "UP":
                        break
            except (OSError, ValueError):
                pass
            time.sleep(2)
        else:
            raise Rejected("APP_HEALTH_FAILED")
        observed = self.inspect()
        if (observed["sourceCommit"] != plan["sourceCommit"]
                or observed["postgresId"] != plan["predecessor"]["postgresId"]
                or observed["postgresMountsSha256"] != plan["predecessor"]["postgresMountsSha256"]
                or observed["composeContractSha256"] != plan["predecessor"]["composeContractSha256"]):
            raise Rejected("APP_POSTCONDITION_FAILED")
        with urllib.request.build_opener(NoRedirect).open("https://atenea.yudri.es", timeout=15) as response:
            if response.status != 200:
                raise Rejected("APP_PUBLIC_SMOKE_FAILED")
        failed = command(["/usr/bin/docker", "exec", "atenea-postgres-prod", "/bin/sh", "-c",
            'exec psql -U "$POSTGRES_USER" -d atenea_prod -Atc "SELECT count(*) FROM flyway_schema_history WHERE NOT success"'])
        if failed.strip() != b"0":
            raise Rejected("FLYWAY_FAILED")
        if plan["sourceCommit"] != plan["predecessor"]["sourceCommit"]:
            version = command(["/usr/bin/docker", "exec", "atenea-postgres-prod", "/bin/sh", "-c",
                'exec psql -U "$POSTGRES_USER" -d atenea_prod -Atc "SELECT version FROM flyway_schema_history WHERE success ORDER BY installed_rank DESC LIMIT 1"'])
            if version.strip() != str(plan["artifact"]["flywayVersion"]).encode():
                raise Rejected("FLYWAY_VERSION_MISMATCH")
        return observed

    def rollback(self, plan, directory):
        save(OVERRIDE, plan["predecessor"]["override"])
        command(self.compose("up", "-d", "--no-deps", "--no-build", "atenea-backend-prod"), timeout=180)
        return self.verify({**plan, "sourceCommit": plan["predecessor"]["sourceCommit"]}, directory)

    def commit(self, receipt):
        pass


class AndroidTarget:
    APK_ROOT = Path("/srv/atenea/apk-public-secret/android")
    KEY = Path("/etc/atenea-release-v1/android.keystore")
    PASSWORD = Path("/etc/atenea-release-v1/android-keystore.pass")

    def __init__(self, config):
        self.config = config

    def guard(self):
        return contextlib.nullcontext()

    def certificate(self, path):
        output = command(["/usr/bin/apksigner", "verify", "--print-certs", str(path)]).decode()
        values = re.findall(r"(?m)^Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-f]{64})$", output)
        if values != [self.config["androidCertificateSha256"]]:
            raise Rejected("APK_SIGNATURE_INCOMPATIBLE")
        return values[0]

    def inspect(self):
        manifest = json.loads(trusted(self.APK_ROOT / "manifest.json", 0o644).read_bytes())
        if (not isinstance(manifest["versionCode"], int) or isinstance(manifest["versionCode"], bool)
                or manifest["versionCode"] <= 0):
            raise Rejected("APK_BASELINE_INVALID")
        self.channel(manifest["apkUrl"])
        apk = self.APK_ROOT / "releases" / str(manifest["versionCode"]) / "atenea-debug.apk"
        if not apk.is_file():
            apk = self.APK_ROOT / "atenea-debug.apk"
        if file_digest(trusted(apk, 0o644)) != manifest["sha256"]:
            raise Rejected("APK_BASELINE_MOVED")
        source = manifest.get("sourceCommit")
        if source is not None and (not isinstance(source,str) or not HEX.fullmatch(source)):
            raise Rejected("APK_BASELINE_INVALID")
        # Legacy provenance can be UNKNOWN; never invent a predecessor Git commit.
        return {"sourceCommit": source,
                "versionCode": manifest["versionCode"], "manifest": manifest,
                "certificateSha256": self.certificate(apk)}

    @staticmethod
    def channel(url):
        if not isinstance(url, str) or not re.fullmatch(r"https://atenea\.yudri\.es/apk/[A-Za-z0-9_-]{16,200}/android/(?:releases/[0-9]+/)?atenea-debug\.apk", url):
            raise Rejected("APK_CHANNEL_REJECTED")
        return url.split("/android/")[0] + "/android/"

    def stage(self, plan, directory):
        artifact = plan["artifact"]
        if (not isinstance(artifact["versionCode"], int) or isinstance(artifact["versionCode"], bool)
                or artifact["versionCode"] <= plan["predecessor"]["versionCode"]
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", artifact["versionName"])):
            raise Rejected("APK_VERSION_NOT_NEWER")
        output = command(["/usr/bin/aapt", "dump", "badging", str(directory / "app-unsigned.apk")]).decode()
        expected = ("package: name='com.atenea.android' versionCode='" + str(artifact["versionCode"])
                    + "' versionName='" + artifact["versionName"] + "'")
        if not output.startswith(expected):
            raise Rejected("APK_IDENTITY_REJECTED")
        command(["/usr/bin/apksigner", "sign", "--ks", str(trusted(self.KEY, 0o600)),
                 "--ks-pass", "file:" + str(trusted(self.PASSWORD, 0o600)),
                 "--out", str(directory / "signed.apk"), str(directory / "app-unsigned.apk")])
        self.certificate(directory / "signed.apk")
        save(directory / "signed.json", {"sha256": file_digest(directory / "signed.apk")})

    def apply(self, plan, directory):
        artifact = plan["artifact"]
        base = self.channel(plan["predecessor"]["manifest"]["apkUrl"])
        signed = directory / "signed.apk"
        if file_digest(signed) != json.loads((directory / "signed.json").read_bytes())["sha256"]:
            raise Rejected("SIGNED_APK_MOVED")
        self.certificate(signed)
        release = self.APK_ROOT / "releases" / str(artifact["versionCode"])
        trusted_directory(self.APK_ROOT / "releases", 0o755)
        release.mkdir(mode=0o755)
        shutil.copyfile(signed, release / "atenea-debug.apk")
        (release / "atenea-debug.apk").chmod(0o644)
        previous = copy.deepcopy(plan["predecessor"]["manifest"])
        previous.pop("previousRelease", None)
        previous_apk = self.APK_ROOT / "releases" / str(previous["versionCode"]) / "atenea-debug.apk"
        if not previous_apk.is_file():
            legacy = self.APK_ROOT / "atenea-debug.apk"
            if file_digest(trusted(legacy, 0o644)) != previous["sha256"]:
                raise Rejected("APK_BASELINE_MOVED")
            previous_apk.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            shutil.copyfile(legacy, previous_apk)
            previous_apk.chmod(0o644)
        if file_digest(trusted(previous_apk, 0o644)) != previous["sha256"]:
            raise Rejected("APK_BASELINE_MOVED")
        previous["apkUrl"] = base + "releases/" + str(previous["versionCode"]) + "/atenea-debug.apk"
        manifest = {"versionCode": artifact["versionCode"], "versionName": artifact["versionName"],
                    "apkUrl": base + "releases/" + str(artifact["versionCode"]) + "/atenea-debug.apk",
                    "sha256": file_digest(signed), "sizeBytes": signed.stat().st_size,
                    "sourceCommit": plan["sourceCommit"], "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "previousRelease": previous}
        save(release / "manifest.json", manifest, mode=0o644)
        (release / "manifest.json").chmod(0o644)
        # URLs reference immutable APK generations; only the manifest is replaced.
        save(self.APK_ROOT / "manifest.json", manifest, mode=0o644)
        (self.APK_ROOT / "manifest.json").chmod(0o644)

    def verify(self, plan, directory):
        observed = self.inspect()
        if observed["sourceCommit"] != plan["sourceCommit"]:
            raise Rejected("APK_POSTCONDITION_FAILED")
        with urllib.request.build_opener(NoRedirect).open(observed["manifest"]["apkUrl"], timeout=60) as response:
            value = hashlib.sha256()
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                value.update(chunk)
        if value.hexdigest() != observed["manifest"]["sha256"]:
            raise Rejected("APK_DOWNLOAD_FAILED")
        return observed

    def rollback(self, plan, directory):
        save(self.APK_ROOT / "manifest.json", plan["predecessor"]["manifest"], mode=0o644)
        (self.APK_ROOT / "manifest.json").chmod(0o644)
        return self.inspect()

    def commit(self, receipt):
        pass


class Peer:
    """VPS to AX42 only. The worker holds no VPS/PROD credentials."""
    def request(self, value):
        token = trusted(PEER_TOKEN, 0o600).read_text().strip()
        request = urllib.request.Request("http://100.81.98.93:8791/v1/release", data=canonical(value),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            payload = json.load(response)
        if not payload.get("ok"):
            raise Rejected(payload.get("errorCode", "PEER_REJECTED"))
        return payload["result"]


class Controller:
    def __init__(self, root, artifacts, targets):
        self.root, self.artifacts, self.targets = root, artifacts, targets
        self.lock = threading.RLock()
        self.execution_lock = threading.Lock()

    def path(self, plan_id):
        return self.root / "plans" / identity(plan_id)

    def read(self, plan_id):
        try:
            return json.loads(trusted(self.path(plan_id) / "operation.json", 0o600).read_bytes())
        except FileNotFoundError:
            raise Rejected("PLAN_NOT_FOUND")

    @staticmethod
    def public(record):
        return {key: record.get(key) for key in ("protocol", "planId", "target", "sourceCommit",
            "artifactSha256", "predecessorCommit", "planSha256", "state", "errorCode", "operationId",
            "versionCode", "versionName", "createdAt", "expiresAt", "finishedAt", "effectiveSourceCommit", "resultSha256")}

    def dispatch(self, request):
        if request.get("operation") == "PLAN":
            return self.plan(request)
        if request.get("operation") == "INSPECT":
            exact(request, {"operation", "planId"})
            return self.public(self.read(request["planId"]))
        if request.get("operation") == "EXECUTE":
            return self.accept(request)
        raise Rejected("CLOSED_REQUEST_REQUIRED")

    def plan(self, request):
        exact(request, {"operation", "planId", "target", "sourceCommit"})
        identity(request["planId"])
        if request["target"] not in self.targets or not isinstance(request["sourceCommit"], str) or not HEX.fullmatch(request["sourceCommit"]):
            raise Rejected("TARGET_REJECTED")
        with self.lock:
            path = self.path(request["planId"])
            if (path / "operation.json").exists():
                record = self.read(request["planId"])
                if record["target"] != request["target"] or record["sourceCommit"] != request["sourceCommit"]:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return self.public(record)
            for existing in (self.root / "plans").glob("*/operation.json"):
                other = json.loads(trusted(existing, 0o600).read_bytes())
                if other["state"] in {"PREPARING", "ROLLBACK_FAILED"} or (other["operationId"] and other["state"] not in TERMINAL):
                    raise Rejected("RELEASE_IN_PROGRESS")
            target = self.targets[request["target"]]
            predecessor = target.inspect()
            if predecessor["sourceCommit"] == request["sourceCommit"]:
                raise Rejected("ALREADY_CURRENT")
            path.mkdir(mode=0o700, parents=True)
            now = int(time.time())
            record = {"protocol": PROTOCOL, **request, "predecessor": predecessor,
                      "predecessorCommit": predecessor["sourceCommit"], "state": "PREPARING",
                      "createdAt": now, "errorCode": None, "operationId": None, "finishedAt": None}
            save(path / "operation.json", record)
            threading.Thread(target=self.prepare, args=(record["planId"],), daemon=False).start()
            return self.public(record)

    def prepare(self, plan_id):
        record, path = self.read(plan_id), self.path(plan_id)
        try:
            deadline = int(time.time()) + 2700
            while True:
                try:
                    artifact = self.artifacts.prepare(record["target"], record["sourceCommit"], path)
                    break
                except Rejected as error:
                    if error.code != "RELEASE_BUILD_PENDING" or int(time.time()) >= deadline:
                        raise
                    record["errorCode"] = "RELEASE_BUILD_PENDING"
                    save(path / "operation.json",record)
                    time.sleep(10)
            record.update(artifact=artifact, artifactSha256=artifact["payloadSha256"],
                          expiresAt=int(time.time()) + 600, versionCode=artifact["versionCode"],
                          versionName=artifact["versionName"],errorCode=None)
            record["planSha256"] = digest({key: record[key] for key in
                ("protocol", "planId", "target", "sourceCommit", "artifact", "predecessor", "expiresAt")})
            self.targets[record["target"]].stage(record, path)
            record["state"] = "READY"
        except Exception as error:
            record.update(state="BLOCKED", errorCode=error.code if isinstance(error, Rejected)
                          else "ARTIFACT_PREPARATION_FAILED", finishedAt=int(time.time()))
        save(path / "operation.json", record)

    def accept(self, request):
        exact(request, {"operation", "planId", "planSha256", "operationId"})
        identity(request["operationId"])
        with self.lock:
            record = self.read(request["planId"])
            if not isinstance(request["planSha256"], str) or not DIGEST.fullmatch(request["planSha256"]) or record.get("planSha256") != request["planSha256"]:
                raise Rejected("PLAN_FINGERPRINT_MISMATCH")
            if record["operationId"] is not None:
                if record["operationId"] != request["operationId"]:
                    raise Rejected("IDEMPOTENCY_CONFLICT")
                return self.public(record)
            if record["state"] != "READY":
                raise Rejected("PLAN_NOT_READY")
            try:
                if record.get("expiresAt", 0) <= int(time.time()):
                    raise Rejected("PLAN_EXPIRED")
                for path in (self.root / "plans").glob("*/operation.json"):
                    other = json.loads(trusted(path, 0o600).read_bytes())
                    if other["state"] == "ROLLBACK_FAILED" or (other["operationId"] and other["state"] not in TERMINAL):
                        raise Rejected("RELEASE_IN_PROGRESS")
                if self.targets[record["target"]].inspect() != record["predecessor"]:
                    raise Rejected("TARGET_STATE_MOVED")
            except Exception as error:
                # Persist a no-effect rejection with the accepted request identity.
                # An App confirmation must not become permanently ambiguous when
                # expiry or a preflight rejects execution before any effects.
                record.update(state="BLOCKED", operationId=request["operationId"],
                              errorCode=error.code if isinstance(error, Rejected) else "PREFLIGHT_FAILED",
                              finishedAt=int(time.time()))
                save(self.path(record["planId"]) / "operation.json", record)
                return self.public(record)
            record.update(state="ACCEPTED", operationId=request["operationId"])
            save(self.path(record["planId"]) / "operation.json", record)
            threading.Thread(target=self.execute, args=(record["planId"],), daemon=False).start()
            return self.public(record)

    def execute(self, plan_id, *, recovered=False):
        with self.execution_lock:
            record = self.read(plan_id)
            if record["state"] in TERMINAL:
                return
            target, path = self.targets[record["target"]], self.path(plan_id)
            try:
                with target.guard():
                    self._execute_guarded(record, path, target)
            except Exception as error:
                record.update(state="ROLLBACK_FAILED" if record["state"] in {"APPLYING", "ROLLING_BACK"}
                              else "BLOCKED", errorCode=error.code if isinstance(error, Rejected) else "EXECUTOR_FAILED")
            record["finishedAt"] = int(time.time())
            save(path / "operation.json", record)

    def _execute_guarded(self, record, path, target):
        try:
            payload = {"APP_PROD": "image.tar", "ANDROID_STABLE": "app-unsigned.apk",
                       "AX42_PLATFORM": "platform.tar"}[record["target"]]
            if file_digest(path / payload) != record["artifactSha256"]:
                raise Rejected("ARTIFACT_DIGEST_MISMATCH")
            if record["state"] == "ROLLING_BACK":
                receipt = target.rollback(record, path)
                target.commit(receipt)
                save(path / "rollback-receipt.json", receipt)
                record["state"] = "ROLLED_BACK"
                record["effectiveSourceCommit"] = receipt["sourceCommit"]
            else:
                if record["state"] == "ACCEPTED":
                    if target.inspect() != record["predecessor"]:
                        raise Rejected("TARGET_STATE_MOVED")
                    record["state"] = "APPLYING"
                    save(path / "operation.json", record)
                    target.apply(record, path)
                # A recovered APPLYING operation never applies twice.
                receipt = target.verify(record, path)
                target.commit(receipt)
                save(path / "receipt.json", receipt)
                record.update(state="SUCCEEDED", errorCode=None)
                record["effectiveSourceCommit"] = receipt["sourceCommit"]
                record["resultSha256"] = receipt.get("manifest", {}).get("sha256")
        except Exception as error:
            record["errorCode"] = error.code if isinstance(error, Rejected) else "EXECUTOR_FAILED"
            if record["state"] in {"APPLYING", "ROLLING_BACK"}:
                record["state"] = "ROLLING_BACK"
                save(path / "operation.json", record)
                try:
                    receipt = target.rollback(record, path)
                    target.commit(receipt)
                    save(path / "rollback-receipt.json", receipt)
                    record["state"] = "ROLLED_BACK"
                    record["effectiveSourceCommit"] = receipt["sourceCommit"]
                except Exception:
                    record["state"] = "ROLLBACK_FAILED"
            else:
                record["state"] = "BLOCKED"

    def recover(self):
        for path in (self.root / "plans").glob("*/operation.json"):
            record = json.loads(trusted(path, 0o600).read_bytes())
            if record["operationId"] and record["state"] not in TERMINAL:
                self.execute(record["planId"], recovered=True)
            elif record["state"] == "PREPARING":
                record.update(state="BLOCKED", errorCode="PREPARATION_INTERRUPTED", finishedAt=int(time.time()))
                save(path, record)


def configuration():
    if os.geteuid() != 0:
        raise Rejected("ROOT_EXECUTOR_REQUIRED")
    config = json.loads(trusted(CONFIG, 0o600).read_bytes())
    if config["mode"] not in {"VPS", "AX42"}:
        raise Rejected("INSTALLATION_MODE_NOT_SUPPORTED")
    exact(config, {"mode", "composeFiles", "androidCertificateSha256"} if config["mode"] == "VPS" else {"mode"})
    for token in (GITHUB_TOKEN, PEER_TOKEN):
        value = trusted(token, 0o600).read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,255}", value):
            raise Rejected("INSTALLED_TOKEN_INVALID")
    if config["mode"] == "VPS":
        if not isinstance(config["androidCertificateSha256"], str) or not DIGEST.fullmatch(config["androidCertificateSha256"]):
            raise Rejected("SIGNING_AUTHORITY_INVALID")
        AppTarget(config).compose("config", "--format", "json")
        trusted(AndroidTarget.KEY, 0o600)
        trusted(AndroidTarget.PASSWORD, 0o600)
        trusted(WORKER_TOKEN, 0o600)
    return config


def prepare_runtime(config):
    ROOT.mkdir(mode=0o700, parents=False, exist_ok=True)
    trusted_directory(ROOT, 0o700)
    SOCKET.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    trusted_directory(SOCKET.parent, 0o755)
    if config["mode"] == "AX42":
        group = grp.getgrnam("atenea").gr_gid
        try:
            descriptor = os.open(ADMISSION, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        except FileExistsError:
            trusted(ADMISSION, 0o640)
            if ADMISSION.stat().st_gid != group:
                raise Rejected("ADMISSION_AUTHORITY_INVALID")
        else:
            try:
                os.fchown(descriptor, 0, group)
                os.fchmod(descriptor, 0o640)
            finally:
                os.close(descriptor)
        # Non-secret marker is visible to the rootless worker; the private
        # executor config/tokens remain in a root-only directory.
        if INSTALLED_MARKER.exists() or INSTALLED_MARKER.is_symlink():
            if json.loads(trusted(INSTALLED_MARKER, 0o644).read_bytes()) != {"protocol":PROTOCOL}:
                raise Rejected("ADMISSION_AUTHORITY_INVALID")
        else:
            save(INSTALLED_MARKER,{"protocol":PROTOCOL},mode=0o644)


def bootstrap_platform(config):
    if config["mode"] != "AX42" or CURRENT.exists() or CURRENT.is_symlink():
        raise Rejected("BASELINE_ALREADY_PRESENT_OR_FOREIGN")
    with PlatformTarget().guard():
        artifacts = GitHubArtifacts()
        source = artifacts.api("/repos/jlnieto/atenea-remote-worker-spec/git/ref/heads/main")["object"]["sha"]
        if not HEX.fullmatch(source):
            raise Rejected("CANONICAL_MAIN_INVALID")
        plan_id = str(uuid.uuid4())
        destination = ROOT / "plans" / plan_id
        destination.mkdir(mode=0o700, parents=True)
        artifact = artifacts.prepare("AX42_PLATFORM", source, destination)
        plan = {"planId": plan_id, "sourceCommit": source}
        target = PlatformTarget()
        target.stage(plan, destination)
        # verify is read-only; bootstrap does NOT apply or restart the worker.
        receipt = target.verify(plan, destination)
        state = json.loads(Path("/srv/atenea/worker/agent-runs-v1/executions.json").read_bytes())
        if any(run["status"] not in {"SUCCEEDED", "FAILED", "CANCELLED"} for run in state["executions"].values()):
            raise Rejected("ACTIVE_WORKLOAD")
        save(destination / "baseline.json", {"protocol": PROTOCOL, "sourceCommit": source,
              "artifact": artifact, "receipt": receipt, "createdAt": int(time.time())})
        target.commit(receipt)
    print(canonical({"state": "ADOPTED", "sourceCommit": source, "artifactPlanId": plan_id}).decode())


def main():
    config = configuration()
    arguments = sys.argv[1:]
    if arguments == ["--preflight-install"]:
        if ROOT.exists() or ROOT.is_symlink():
            trusted_directory(ROOT,0o700)
            for path in (ROOT / "plans").glob("*/operation.json"):
                record=json.loads(trusted(path,0o600).read_bytes())
                if record["state"] == "PREPARING" or (record["operationId"] and record["state"] not in TERMINAL):
                    raise Rejected("RELEASE_IN_PROGRESS")
        print("Release installation preflight passed")
        return
    if arguments == ["--verify-config"]:
        print("Release configuration verified")
        return
    if arguments == ["--installation-mode"]:
        print(config["mode"])
        return
    if arguments == ["--prepare-runtime"]:
        prepare_runtime(config)
        return
    if arguments == ["--bootstrap-platform"]:
        bootstrap_platform(config)
        return
    if arguments == ["--verify-runtime"]:
        trusted_directory(ROOT, 0o700)
        trusted_directory(SOCKET.parent, 0o755)
        if config["mode"] == "AX42":
            trusted(ADMISSION, 0o640)
            trusted(INSTALLED_MARKER, 0o644)
        elif not stat.S_ISSOCK(SOCKET.lstat().st_mode) or SOCKET.lstat().st_uid != 0 or SOCKET.lstat().st_gid != 1001 or stat.S_IMODE(SOCKET.lstat().st_mode) != 0o660:
            raise Rejected("SOCKET_AUTHORITY_INVALID")
        print("Release runtime verified")
        return
    if arguments:
        raise Rejected("CLOSED_COMMAND_REQUIRED")
    trusted_directory(ROOT, 0o700)
    trusted_directory(SOCKET.parent, 0o755)
    targets = {"APP_PROD": AppTarget(config), "ANDROID_STABLE": AndroidTarget(config)} if config["mode"] == "VPS" else {"AX42_PLATFORM": PlatformTarget()}
    controller = Controller(ROOT, GitHubArtifacts(), targets)
    peer = Peer() if config["mode"] == "VPS" else None

    peer_lock = threading.RLock()

    def dispatch(request):
        if peer and (request.get("target") == "AX42_PLATFORM" or request.get("planId") in peer_plans):
            result = peer.request(request)
            if request.get("operation") == "PLAN":
                with peer_lock:
                    peer_plans.add(request["planId"])
                    save(ROOT / "peer-plans.json", sorted(peer_plans))
            return result
        return controller.dispatch(request)

    peer_file = ROOT / "peer-plans.json"
    peer_plans = set(json.loads(trusted(peer_file, 0o600).read_bytes())) if peer_file.exists() else set()

    if config["mode"] == "AX42":
        class HttpHandler(http.server.BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(30)

            def do_POST(self):
                token = trusted(PEER_TOKEN, 0o600).read_text().strip()
                if (self.client_address[0] != "100.88.252.28" or self.path != "/v1/release"
                        or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)):
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 16384:
                        raise Rejected("CLOSED_REQUEST_REQUIRED")
                    result = dispatch(json.loads(self.rfile.read(size)))
                    response = {"ok": True, "result": result}
                except Exception as error:
                    response = {"ok": False, "errorCode": error.code if isinstance(error, Rejected) else "EXECUTOR_FAILED"}
                encoded = canonical(response)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):
                pass
        controller.recover()
        http.server.ThreadingHTTPServer(("100.81.98.93", 8791), HttpHandler).serve_forever()
        return

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(30)
            try:
                line = self.rfile.readline(16385)
                if len(line) > 16384 or not line.endswith(b"\n"):
                    raise Rejected("CLOSED_REQUEST_REQUIRED")
                result = dispatch(json.loads(line))
                response = {"ok": True, "result": result}
            except Exception as error:
                response = {"ok": False, "errorCode": error.code if isinstance(error, Rejected) else "EXECUTOR_FAILED"}
            self.wfile.write(canonical(response) + b"\n")

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = False

    SOCKET.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if SOCKET.exists():
        if not stat.S_ISSOCK(SOCKET.lstat().st_mode) or SOCKET.lstat().st_uid != 0:
            raise Rejected("SOCKET_PATH_FOREIGN")
        SOCKET.unlink()
    server = Server(str(SOCKET), Handler)
    os.chown(SOCKET, 0, 1001)
    SOCKET.chmod(0o660)
    controller.recover()
    server.serve_forever()


if __name__ == "__main__":
    main()
