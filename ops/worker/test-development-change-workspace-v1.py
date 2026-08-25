#!/usr/bin/env python3
"""Deterministic contract tests for development-change-workspace/v1."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import stat
import subprocess
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator, FormatChecker


SOURCE = Path(__file__).resolve().parent
CONTRACT_ROOT = SOURCE.parent.parent / "runtime-contract"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mediator_module = load(
    "development_change_workspace_v1",
    SOURCE / "development-change-workspace-v1.py",
)
worker_module = load("agent_run_worker_v1", SOURCE / "agent-run-worker-v1.py")


class DevelopmentChangeWorkspaceMediatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="atenea-m2-h2-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.mirror = self.root / "atenea.git"
        self.remote = self.root / "publication.git"
        self.workspaces = self.root / "changes"
        self.state = self.root / "state"
        self.credentials = self.root / "credentials"
        self.publication_runtime = self.root / "publication-runtime"
        self.known_hosts = self.root / "github-known-hosts"
        self.workspaces.mkdir(mode=0o700)
        self.state.mkdir(mode=0o700)
        self.credentials.mkdir(mode=0o700)
        self.publication_runtime.mkdir(mode=0o700)
        self.private_key = self.credentials / "atenea-publication-deploy-key"
        self.private_key.write_text(
            "synthetic-private-key-material\n", encoding="utf-8"
        )
        self.private_key.chmod(0o440)
        self.known_hosts.write_text(
            "github.com ssh-ed25519 "
            "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl\n",
            encoding="ascii",
        )
        self.environment = mock.patch.dict(
            mediator_module.os.environ,
            {"CREDENTIALS_DIRECTORY": str(self.credentials)},
        )
        self.environment.start()
        self._git("init", "--initial-branch=main", str(self.source))
        self._git("-C", str(self.source), "config", "user.name", "Synthetic")
        self._git("-C", str(self.source), "config", "user.email", "synthetic@example.invalid")
        (self.source / "README.md").write_text("synthetic\n", encoding="utf-8")
        self._git("-C", str(self.source), "add", "README.md")
        self._git("-C", str(self.source), "commit", "-m", "synthetic base")
        self.base_commit = self._git(
            "-C", str(self.source), "rev-parse", "HEAD", capture=True
        ).strip()
        self._git("clone", "--bare", str(self.source), str(self.mirror))
        self._git("clone", "--bare", str(self.source), str(self.remote))
        self._git(
            f"--git-dir={self.mirror}",
            "remote",
            "set-url",
            "origin",
            str(self.remote),
        )
        self._git(
            f"--git-dir={self.mirror}",
            "update-ref",
            "refs/remotes/origin/main",
            self.base_commit,
        )
        self.mediator = mediator_module.WorkspaceMediator(
            self.mirror,
            self.workspaces,
            self.state / "workspace.lock",
            test_mode=True,
            publication_remote=str(self.remote),
            publication_transport=str(self.remote),
            publication_known_hosts=self.known_hosts,
            publication_runtime_directory=self.publication_runtime,
        )
        self.change_key = "8bf60472-3c0e-49aa-99bf-6dc3c7e60eaf"

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def _git(self, *arguments: str, capture: bool = False) -> str:
        result = subprocess.run(
            ["/usr/bin/git", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
            check=True,
        )
        return result.stdout if capture else ""

    def request(
        self,
        operation: str = "PROVISION",
        *,
        change_key: str | None = None,
        database_project_id: int = 7,
        predecessor: str | None = None,
    ) -> dict:
        key = change_key or self.change_key
        body = {
            "schemaVersion": 1,
            "protocolVersion": "development-change-workspace/v1",
            "effect": "CREATE_IF_ABSENT_EXACT" if operation == "PROVISION" else "OBSERVE_ONLY",
            "operationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"operation:{operation}:{key}")),
            "idempotencyKey": str(uuid.uuid5(uuid.NAMESPACE_URL, f"idempotency:{operation}:{key}")),
            "operation": operation,
            "predecessorOperationId": predecessor,
            "changeKey": key,
            "databaseProjectId": database_project_id,
            "projectId": "atenea",
            "repository": "https://github.com/jlnieto/atenea.git",
            "repositoryBranch": "main",
            "baseCommit": self.base_commit,
            "expectedCanonicalCommit": self.base_commit,
            "workspaceBranch": f"atenea/change-{key}",
            "workspaceIdentity": f"remote:ax42-01:change:{key}",
            "workerId": "ax42-01",
            "sourceRevision": 0,
            "sourceFingerprintSha256": "a" * 64,
        }
        body["requestFingerprintSha256"] = mediator_module.canonical_sha256(body)
        return body

    def publication_request(self, observation: dict, **overrides) -> dict:
        body = {
            "schemaVersion": 1,
            "protocolVersion": "development-change-branch-publication/v1",
            "effect": "PUBLISH_EXACT_CHANGE_BRANCH",
            "operationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"publish:{self.change_key}")),
            "idempotencyKey": str(uuid.uuid5(uuid.NAMESPACE_URL, f"publish-idempotency:{self.change_key}")),
            "operation": "PUBLISH",
            "changeKey": self.change_key,
            "databaseProjectId": 7,
            "projectId": "atenea",
            "repository": "https://github.com/jlnieto/atenea.git",
            "repositoryBranch": "main",
            "baseCommit": self.base_commit,
            "expectedCanonicalCommit": self.base_commit,
            "workspaceBranch": f"atenea/change-{self.change_key}",
            "workspaceIdentity": f"remote:ax42-01:change:{self.change_key}",
            "workerId": "ax42-01",
            "sourceRevision": 1,
            "sourceFingerprintSha256": observation["sourceFingerprintSha256"],
            "workspaceOwnershipFingerprintSha256": observation["ownershipFingerprintSha256"],
        }
        body.update(overrides)
        body["requestFingerprintSha256"] = mediator_module.canonical_sha256(body)
        return body

    def dirty_publication(self) -> tuple[dict, dict]:
        self.mediator.execute(self.request(), "PROVISION")
        worktree = self.workspaces / self.change_key / "atenea"
        (worktree / "published.txt").write_text("exact change\n", encoding="utf-8")
        observation = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        return self.publication_request(observation), observation

    def test_provision_creates_one_exact_owned_worktree_without_exposing_path(self) -> None:
        request = self.request()
        response = self.mediator.execute(request, "PROVISION")
        self.assertEqual("OWNED", response["state"])
        self.assertEqual(self.base_commit, response["canonicalCommit"])
        self.assertEqual("a" * 64, response["sourceFingerprintSha256"])
        self.assertFalse(response["workspaceDirty"])
        self.assertEqual(
            0o770,
            (self.workspaces / self.change_key).stat().st_mode & 0o777,
        )

    def test_machine_readable_contract_accepts_exact_exchange(self) -> None:
        request_schema = json.loads(
            (CONTRACT_ROOT / "development-change-workspace-v1.request.schema.json")
            .read_text(encoding="utf-8")
        )
        response_schema = json.loads(
            (CONTRACT_ROOT / "development-change-workspace-v1.response.schema.json")
            .read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(request_schema)
        Draft202012Validator.check_schema(response_schema)
        request = self.request()
        response = self.mediator.execute(request, "PROVISION")
        Draft202012Validator(
            request_schema, format_checker=FormatChecker()
        ).validate(request)
        Draft202012Validator(
            response_schema, format_checker=FormatChecker()
        ).validate(response)
        self.assertFalse(response["valuesExposed"])
        self.assertNotIn("workspacePath", response)
        self.assertTrue((self.workspaces / self.change_key / "atenea" / ".git").is_file())
        record = self.workspaces / self.change_key / "workspace-v1.json"
        self.assertEqual(0o600, record.stat().st_mode & 0o777)

    def test_repeated_provision_is_idempotent_and_does_not_add_a_worktree(self) -> None:
        request = self.request()
        first = self.mediator.execute(request, "PROVISION")
        second = self.mediator.execute(request, "PROVISION")
        self.assertEqual(first, second)
        listed = self._git(
            f"--git-dir={self.mirror}", "worktree", "list", "--porcelain", capture=True
        )
        self.assertEqual(2, listed.count("worktree "))

    def test_inspect_absent_is_read_only(self) -> None:
        key = "f1c6f155-6eb5-4e03-a7ec-08db0bc2961e"
        response = self.mediator.execute(self.request("INSPECT", change_key=key), "INSPECT")
        self.assertEqual("ABSENT", response["state"])
        self.assertIsNone(response["canonicalCommit"])
        self.assertFalse((self.workspaces / key).exists())

    def test_reconcile_requires_an_exact_predecessor(self) -> None:
        with self.assertRaises(mediator_module.ContractError):
            self.mediator.execute(self.request("RECONCILE"), "RECONCILE")
        predecessor = "48166062-d262-4a3a-b3a0-a2a01830aa5a"
        response = self.mediator.execute(
            self.request("RECONCILE", predecessor=predecessor), "RECONCILE"
        )
        self.assertEqual("ABSENT", response["state"])

    def test_partial_or_cross_owned_resource_is_foreign_and_not_adopted(self) -> None:
        request = self.request()
        (self.workspaces / self.change_key).mkdir(mode=0o700)
        response = self.mediator.execute(request, "PROVISION")
        self.assertEqual("FOREIGN", response["state"])
        self.assertFalse((self.workspaces / self.change_key / "atenea").exists())

        self.temporary.cleanup()
        self.setUp()
        self.mediator.execute(self.request(), "PROVISION")
        crossed = self.request("INSPECT", database_project_id=8)
        response = self.mediator.execute(crossed, "INSPECT")
        self.assertEqual("FOREIGN", response["state"])

    def test_dirty_source_fingerprint_is_stable_and_sanitized(self) -> None:
        request = self.request()
        self.mediator.execute(request, "PROVISION")
        worktree = self.workspaces / self.change_key / "atenea"
        (worktree / "synthetic.txt").write_text("private synthetic content\n", encoding="utf-8")
        first = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        second = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        self.assertTrue(first["workspaceDirty"])
        self.assertTrue(first["retainedDraft"])
        self.assertEqual(first["sourceFingerprintSha256"], second["sourceFingerprintSha256"])
        self.assertNotEqual("a" * 64, first["sourceFingerprintSha256"])
        self.assertNotIn("private", json.dumps(first))
        advanced = self.request("INSPECT")
        advanced["sourceRevision"] = 1
        advanced["sourceFingerprintSha256"] = first["sourceFingerprintSha256"]
        advanced.pop("requestFingerprintSha256")
        advanced["requestFingerprintSha256"] = mediator_module.canonical_sha256(advanced)
        third = self.mediator.execute(advanced, "INSPECT")
        self.assertEqual("OWNED", third["state"])
        self.assertEqual(first["sourceFingerprintSha256"], third["sourceFingerprintSha256"])

    def test_duplicate_or_unknown_input_fails_closed(self) -> None:
        request = self.request()
        raw = json.dumps(request, separators=(",", ":"))
        duplicated = raw.replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1')
        with self.assertRaises(mediator_module.ContractError):
            mediator_module.strict_json(duplicated.encode())
        request["workspacePath"] = "/client/selected"
        with self.assertRaises(mediator_module.ContractError):
            self.mediator.execute(request, "PROVISION")

    def test_publish_materializes_and_pushes_exact_change_branch(self) -> None:
        request, _ = self.dirty_publication()
        real_run = subprocess.run
        runtime_credentials = []

        def observe_runtime_credential(*args, **kwargs):
            ssh_command = kwargs["env"].get("GIT_SSH_COMMAND")
            if ssh_command:
                ssh_arguments = shlex.split(ssh_command)
                identity = Path(ssh_arguments[ssh_arguments.index("-i") + 1])
                runtime_credentials.append(identity)
                observed = identity.lstat()
                self.assertEqual(self.publication_runtime, identity.parent)
                self.assertTrue(stat.S_ISREG(observed.st_mode))
                self.assertFalse(identity.is_symlink())
                self.assertEqual(os.geteuid(), observed.st_uid)
                self.assertEqual(0o600, stat.S_IMODE(observed.st_mode))
                self.assertEqual(
                    self.private_key.read_bytes(), identity.read_bytes()
                )
            return real_run(*args, **kwargs)

        with mock.patch.object(
            mediator_module.subprocess, "run", side_effect=observe_runtime_credential
        ) as run:
            response = self.mediator.publish(request)
        remote_head = self._git(
            f"--git-dir={self.remote}",
            "rev-parse",
            f"refs/heads/{request['workspaceBranch']}",
            capture=True,
        ).strip()
        self.assertEqual("PUBLISHED", response["state"])
        self.assertEqual(response["publishedHeadSha"], remote_head)
        self.assertEqual("CREATED", response["remoteDisposition"])
        self.assertFalse(response["valuesExposed"])
        self.assertNotIn(str(self.remote), json.dumps(response))
        self.assertEqual(0o440, stat.S_IMODE(self.private_key.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(self.publication_runtime.stat().st_mode))
        self.assertTrue(runtime_credentials)
        self.assertTrue(all(not path.exists() for path in runtime_credentials))
        self.assertEqual([], list(self.publication_runtime.iterdir()))
        publication_calls = []
        non_publication_calls = []
        for call in run.call_args_list:
            command = call.args[0]
            if "ls-remote" in command or "push" in command:
                publication_calls.append(call)
            else:
                non_publication_calls.append(call)
            self.assertNotIn("CREDENTIALS_DIRECTORY", call.kwargs["env"])
        self.assertTrue(publication_calls)
        self.assertTrue(non_publication_calls)
        for call in publication_calls:
            ssh = call.kwargs["env"].get("GIT_SSH_COMMAND", "")
            self.assertNotIn(str(self.private_key), ssh)
            self.assertIn(str(self.publication_runtime), ssh)
            self.assertIn("IdentitiesOnly=yes", ssh)
            self.assertIn("IdentityAgent=none", ssh)
            self.assertIn("BatchMode=yes", ssh)
            self.assertIn("PasswordAuthentication=no", ssh)
            self.assertIn("StrictHostKeyChecking=yes", ssh)
            self.assertIn(f"UserKnownHostsFile={self.known_hosts}", ssh)
            self.assertNotIn("SSH_AUTH_SOCK", call.kwargs["env"])
            self.assertNotIn("credential.helper", ssh)
            self.assertNotIn(
                self.private_key.read_text(encoding="utf-8").strip(),
                json.dumps(call.kwargs["env"]),
            )
        self.assertTrue(all(
            "GIT_SSH_COMMAND" not in call.kwargs["env"]
            for call in non_publication_calls
        ))
        for suffix, value in (("request", request), ("response", response)):
            schema = json.loads((CONTRACT_ROOT /
                f"development-change-branch-publication-v1.{suffix}.schema.json")
                .read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)

    def test_publish_replay_and_lost_response_return_same_exact_head(self) -> None:
        request, _ = self.dirty_publication()
        original_response = self.mediator._publication_response
        with mock.patch.object(
            self.mediator,
            "_publication_response",
            side_effect=RuntimeError("synthetic lost response"),
        ):
            with self.assertRaises(RuntimeError):
                self.mediator.publish(request)
        with mock.patch.object(
            self.mediator, "_publication_response", wraps=original_response
        ):
            recovered = self.mediator.publish(request)
            replayed = self.mediator.publish(request)
        self.assertEqual(recovered, replayed)
        self.assertEqual("PUBLISHED", recovered["state"])

    def test_publish_accepts_remote_branch_already_identical(self) -> None:
        self.mediator.execute(self.request(), "PROVISION")
        worktree = self.workspaces / self.change_key / "atenea"
        (worktree / "committed.txt").write_text("committed\n", encoding="utf-8")
        self._git("-C", str(worktree), "add", "committed.txt")
        self._git("-C", str(worktree), "-c", "user.name=Synthetic", "-c",
                  "user.email=synthetic@example.invalid", "commit", "-m", "already committed")
        observation = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        request = self.publication_request(observation)
        self._git(
            "-C", str(worktree), "push", "origin",
            f"refs/heads/{request['workspaceBranch']}:refs/heads/{request['workspaceBranch']}",
        )
        response = self.mediator.publish(request)
        self.assertEqual("IDENTICAL", response["remoteDisposition"])

    def test_publish_rejects_incompatible_remote_without_force_push(self) -> None:
        request, _ = self.dirty_publication()
        self._git(
            f"--git-dir={self.remote}", "update-ref",
            f"refs/heads/{request['workspaceBranch']}", self.base_commit,
        )
        with mock.patch.object(self.mediator, "_git", wraps=self.mediator._git) as git_call:
            with self.assertRaises(mediator_module.ContractError):
                self.mediator.publish(request)
        flattened = [str(value) for call in git_call.call_args_list for value in call.args]
        self.assertFalse(any("force" in value for value in flattened))
        remote_head = self._git(
            f"--git-dir={self.remote}", "rev-parse",
            f"refs/heads/{request['workspaceBranch']}", capture=True,
        ).strip()
        self.assertEqual(self.base_commit, remote_head)

    def test_publication_transport_is_fixed_and_server_owned(self) -> None:
        fixed = mediator_module.WorkspaceMediator(
            self.mirror,
            self.workspaces,
            self.state / "fixed-transport.lock",
            test_mode=True,
            publication_remote=str(self.remote),
            publication_known_hosts=self.known_hosts,
            publication_runtime_directory=self.publication_runtime,
        )
        with mock.patch.object(
            mediator_module.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, stdout=b"", stderr=b""),
        ) as run:
            fixed._git("ls-remote", "--heads", fixed.publication_transport,
                       "refs/heads/atenea/change-" + self.change_key,
                       publication=True)
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertEqual(
            "git@github.com:jlnieto/atenea.git", fixed.publication_transport
        )
        self.assertEqual(
            Path("/etc/atenea-worker/github-known-hosts"),
            mediator_module.PUBLICATION_KNOWN_HOSTS,
        )
        self.assertIn("git@github.com:jlnieto/atenea.git", command)
        self.assertNotIn("origin", command)
        self.assertEqual("/dev/null", environment["GIT_CONFIG_GLOBAL"])
        self.assertNotIn("SSH_AUTH_SOCK", environment)

    def test_missing_or_unsafe_publication_credential_fails_closed(self) -> None:
        request, _ = self.dirty_publication()
        secret = self.private_key.read_text(encoding="utf-8").strip()
        with mock.patch.dict(mediator_module.os.environ, {}, clear=True):
            with self.assertRaises(mediator_module.ContractError) as missing:
                self.mediator.publish(request)
        self.assertEqual("publication authentication is unavailable", str(missing.exception))
        self.assertNotIn(secret, str(missing.exception))
        self.private_key.chmod(0o644)
        with self.assertRaises(mediator_module.ContractError) as unsafe:
            self.mediator.publish(request)
        self.assertEqual("publication authentication is unavailable", str(unsafe.exception))
        self.assertNotIn(str(self.private_key), str(unsafe.exception))

        self.private_key.unlink()
        symlink_target = self.root / "symlink-target"
        symlink_target.write_text(secret + "\n", encoding="utf-8")
        symlink_target.chmod(0o400)
        self.private_key.symlink_to(symlink_target)
        with self.assertRaises(mediator_module.ContractError) as symlink:
            self.mediator.publish(request)
        self.assertEqual(
            "publication authentication is unavailable", str(symlink.exception)
        )
        self.assertNotIn(secret, str(symlink.exception))

    def test_unsafe_publication_runtime_directory_fails_closed(self) -> None:
        request, _ = self.dirty_publication()
        self.publication_runtime.chmod(0o750)
        with self.assertRaises(mediator_module.ContractError) as unsafe:
            self.mediator.publish(request)
        self.assertEqual(
            "publication authentication is unavailable", str(unsafe.exception)
        )
        self.assertEqual([], list(self.publication_runtime.iterdir()))

    def test_unsafe_runtime_credential_mode_fails_closed_and_cleans_up(self) -> None:
        real_fchmod = os.fchmod

        def impose_unsafe_mode(descriptor, _mode):
            real_fchmod(descriptor, 0o640)

        with mock.patch.object(
            mediator_module.os, "fchmod", side_effect=impose_unsafe_mode
        ):
            with self.assertRaises(mediator_module.ContractError) as unsafe:
                self.mediator._git(
                    "ls-remote", "--heads", self.mediator.publication_transport,
                    "refs/heads/atenea/change-" + self.change_key,
                    publication=True,
                )
        self.assertEqual(
            "publication authentication is unavailable", str(unsafe.exception)
        )
        self.assertEqual([], list(self.publication_runtime.iterdir()))

    def test_publication_cleanup_failure_fails_closed(self) -> None:
        secret = self.private_key.read_text(encoding="utf-8").strip()
        real_unlink = os.unlink
        retained = []

        def reject_runtime_unlink(path, *args, **kwargs):
            candidate = Path(path)
            if candidate.parent == self.publication_runtime:
                retained.append(candidate)
                raise PermissionError("synthetic cleanup rejection")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(
            mediator_module.os, "unlink", side_effect=reject_runtime_unlink
        ):
            with self.assertRaises(mediator_module.ContractError) as rejected:
                self.mediator._git(
                    "ls-remote", "--heads", self.mediator.publication_transport,
                    "refs/heads/atenea/change-" + self.change_key,
                    publication=True,
                )
        self.assertEqual(
            "publication authentication cleanup failed", str(rejected.exception)
        )
        self.assertNotIn(secret, str(rejected.exception))
        self.assertEqual(1, len(retained))
        self.assertEqual(0o600, stat.S_IMODE(retained[0].stat().st_mode))
        retained[0].unlink()

    def test_missing_or_incompatible_fixed_known_hosts_fails_closed(self) -> None:
        request, _ = self.dirty_publication()
        self.known_hosts.write_text(
            "example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
            encoding="ascii",
        )
        with self.assertRaises(mediator_module.ContractError) as incompatible:
            self.mediator.publish(request)
        self.assertEqual("publication trust is unavailable", str(incompatible.exception))
        self.assertNotIn(str(self.known_hosts), str(incompatible.exception))
        self.known_hosts.unlink()
        with self.assertRaises(mediator_module.ContractError) as missing:
            self.mediator.publish(request)
        self.assertEqual("publication trust is unavailable", str(missing.exception))

    def test_git_failure_does_not_expose_secret_or_stderr(self) -> None:
        secret = self.private_key.read_text(encoding="utf-8").strip()
        captured = io.StringIO()
        runtime_credentials = []

        def fail_git(*args, **kwargs):
            ssh_arguments = shlex.split(kwargs["env"]["GIT_SSH_COMMAND"])
            runtime_credentials.append(
                Path(ssh_arguments[ssh_arguments.index("-i") + 1])
            )
            return subprocess.CompletedProcess(
                [], 1, stdout=b"", stderr=("remote:" + secret).encode()
            )

        with mock.patch.object(
            mediator_module.subprocess,
            "run",
            side_effect=fail_git,
        ):
            with redirect_stderr(captured):
                with self.assertRaises(mediator_module.ContractError) as rejected:
                    self.mediator._git(
                        "ls-remote", "--heads", self.mediator.publication_transport,
                        "refs/heads/atenea/change-" + self.change_key,
                        publication=True,
                    )
        public_material = str(rejected.exception) + captured.getvalue()
        self.assertEqual("Git operation failed closed", str(rejected.exception))
        self.assertNotIn(secret, public_material)
        self.assertNotIn(str(self.private_key), public_material)
        self.assertTrue(runtime_credentials)
        self.assertTrue(all(not path.exists() for path in runtime_credentials))
        self.assertEqual([], list(self.publication_runtime.iterdir()))

    def test_publish_rejects_unexpected_canonical_remote(self) -> None:
        request, _ = self.dirty_publication()
        self._git(
            f"--git-dir={self.mirror}", "remote", "set-url", "origin",
            str(self.root / "unexpected.git"),
        )
        with self.assertRaises(mediator_module.ContractError) as rejected:
            self.mediator.publish(request)
        self.assertEqual("canonical mirror remote is invalid", str(rejected.exception))

    def test_publish_rejects_cross_ownership_foreign_stale_and_arbitrary_branch(self) -> None:
        request, observation = self.dirty_publication()
        for overrides in (
            {"databaseProjectId": 8},
            {"sourceFingerprintSha256": "b" * 64},
            {"workspaceBranch": "client/chosen"},
        ):
            crossed = self.publication_request(observation, **overrides)
            with self.assertRaises(mediator_module.ContractError):
                self.mediator.publish(crossed)
        record = self.workspaces / self.change_key / "workspace-v1.json"
        stored = json.loads(record.read_text(encoding="utf-8"))
        stored["databaseProjectId"] = 99
        body = dict(stored)
        body.pop("recordSha256")
        stored["recordSha256"] = mediator_module.canonical_sha256(body)
        record.write_text(json.dumps(stored, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        record.chmod(0o600)
        with self.assertRaises(mediator_module.ContractError):
            self.mediator.publish(request)


class WorkerIntegrationTest(unittest.TestCase):
    def test_health_advertises_capability_only_when_exact_mediator_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="atenea-m2-worker-") as temporary:
            root = Path(temporary)
            state_dir = root / "state"
            mediator = root / "mediator.py"
            mediator.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            mediator.chmod(0o755)
            state = worker_module.WorkerState(
                state_dir,
                "ax42-01",
                development_change_workspace_mediator=mediator,
            )
            self.assertIn(
                "development-change-workspace/v1", state.health()["capabilities"]
            )
            self.assertIn(
                "development-change-branch-publication/v1",
                state.health()["capabilities"],
            )
            mediator.unlink()
            self.assertNotIn(
                "development-change-workspace/v1", state.health()["capabilities"]
            )
            self.assertNotIn(
                "development-change-branch-publication/v1",
                state.health()["capabilities"],
            )

    def test_worker_validates_exact_mediator_response(self) -> None:
        with tempfile.TemporaryDirectory(prefix="atenea-m2-worker-") as temporary:
            root = Path(temporary)
            mediator = root / "mediator.py"
            mediator.write_text(
                """#!/usr/bin/env python3
import hashlib, json, sys
r=json.load(sys.stdin)
out={k:r[k] for k in ('schemaVersion','protocolVersion','effect','operationId','idempotencyKey','operation','predecessorOperationId','changeKey','databaseProjectId','projectId','repository','repositoryBranch','baseCommit','expectedCanonicalCommit','workspaceBranch','workspaceIdentity','workerId','sourceRevision','requestFingerprintSha256')}
out.update({'state':'ABSENT','expectedSourceFingerprintSha256':r['sourceFingerprintSha256'],'canonicalCommit':None,'sourceFingerprintSha256':None,'workspaceDirty':None,'retainedDraft':None,'ownershipFingerprintSha256':hashlib.sha256(b'absent').hexdigest(),'valuesExposed':False})
json.dump(out,sys.stdout,sort_keys=True,separators=(',',':'))
""",
                encoding="utf-8",
            )
            mediator.chmod(0o755)
            state = worker_module.WorkerState(
                root / "state",
                "ax42-01",
                development_change_workspace_mediator=mediator,
            )
            request = self._request()
            response = state.execute_development_change_workspace(request, "inspect")
            self.assertEqual("ABSENT", response["state"])
            self.assertFalse(response["valuesExposed"])

    def test_service_template_changes_only_worker_protocol_boundary(self) -> None:
        service = (SOURCE / "templates" / "atenea-agent-run-worker-v1.service").read_text()
        self.assertIn(
            "--development-change-workspace-mediator /usr/local/libexec/atenea/development-change-workspace-v1.py",
            service,
        )
        self.assertIn("/srv/atenea/workspaces/changes", service)
        self.assertEqual(1, service.count("development-change-workspace-v1.py"))
        self.assertEqual(
            1,
            service.count(
                "LoadCredential=atenea-publication-deploy-key:"
                "/etc/atenea-worker/atenea-publication-deploy-key"
            ),
        )
        self.assertEqual(1, service.count("RuntimeDirectory=atenea-publication"))
        self.assertEqual(1, service.count("RuntimeDirectoryMode=0700"))

    def test_worker_projects_systemd_credentials_only_to_publication_mediator(self) -> None:
        credential_directory = "/run/credentials/atenea-agent-run-worker-v1.service"
        with mock.patch.dict(
            worker_module.os.environ,
            {"CREDENTIALS_DIRECTORY": credential_directory},
        ):
            ordinary = worker_module.subprocess_environment()
            publication = worker_module.subprocess_environment(
                systemd_credentials=True
            )
        self.assertNotIn("CREDENTIALS_DIRECTORY", ordinary)
        self.assertEqual(
            credential_directory, publication["CREDENTIALS_DIRECTORY"]
        )

    def _request(self) -> dict:
        key = "8bf60472-3c0e-49aa-99bf-6dc3c7e60eaf"
        request = {
            "schemaVersion": 1,
            "protocolVersion": "development-change-workspace/v1",
            "effect": "OBSERVE_ONLY",
            "operationId": "17f120f6-79e2-49e4-bd13-23db520d1374",
            "idempotencyKey": "61552669-4b46-431c-811d-344293ab3c67",
            "operation": "INSPECT",
            "predecessorOperationId": None,
            "changeKey": key,
            "databaseProjectId": 7,
            "projectId": "atenea",
            "repository": "https://github.com/jlnieto/atenea.git",
            "repositoryBranch": "main",
            "baseCommit": "1" * 40,
            "expectedCanonicalCommit": "1" * 40,
            "workspaceBranch": f"atenea/change-{key}",
            "workspaceIdentity": f"remote:ax42-01:change:{key}",
            "workerId": "ax42-01",
            "sourceRevision": 0,
            "sourceFingerprintSha256": "a" * 64,
        }
        request["requestFingerprintSha256"] = mediator_module.canonical_sha256(request)
        return request


if __name__ == "__main__":
    unittest.main(verbosity=2)
