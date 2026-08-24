#!/usr/bin/env python3

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("atenea-validation-v1.py")
SPEC = importlib.util.spec_from_file_location("atenea_validation_v1", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClosedValidationSandboxTests(unittest.TestCase):
    def test_catalog_retains_only_the_four_symbolic_definitions(self):
        self.assertEqual(
            {
                "BACKEND_TEST",
                "WEB_BUILD",
                "ANDROID_BUILD",
                "PLAYWRIGHT_ACCEPTANCE",
            },
            set(MODULE.DEFINITIONS),
        )
        self.assertEqual(("./mvnw", "-q", "test"), MODULE.sandbox_operation_command("BACKEND_TEST"))
        self.assertEqual(("./scripts/web-build.sh",), MODULE.sandbox_operation_command("WEB_BUILD"))
        with self.assertRaises(MODULE.Rejected):
            MODULE.sandbox_operation_command("ANDROID_BUILD")
        with self.assertRaises(MODULE.Rejected):
            MODULE.sandbox_operation_command("sh -c id")

    def test_systemd_and_bubblewrap_command_seal_identity_resources_and_mounts(self):
        definition = MODULE.DEFINITIONS["BACKEND_TEST"]
        source = Path("/srv/atenea/artifacts/validations/session/.validation-run/source")
        artifacts = Path("/srv/atenea/artifacts/validations/session/.validation-run/artifacts")
        resolv = Path("/srv/atenea/artifacts/validations/session/.validation-run/resolv.conf")
        command = MODULE.sandbox_command(
            "BACKEND_TEST",
            "11111111-1111-4111-8111-111111111111",
            definition,
            "atenea-slot2",
            1102,
            source,
            artifacts,
            resolv,
        )
        rendered = "\0".join(command)
        for required in (
            "User=atenea-slot2",
            "Group=atenea-slot2",
            "CPUQuota=200%",
            "MemoryMax=4G",
            "TasksMax=512",
            "RuntimeMaxSec=900s",
            "LimitFSIZE=67108864",
            "TemporaryFileSystem=/work:rw,nosuid,nodev,size=6G",
            f"BindReadOnlyPaths={source}:/source",
            f"BindReadOnlyPaths={resolv}:/validation-resolv.conf",
            f"BindPaths={artifacts}:/artifacts",
            "NoNewPrivileges=yes",
            "IPAddressDeny=100.64.0.0/10",
            "--sandbox-supervise\0BACKEND_TEST",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("User=root", rendered)
        self.assertNotIn("/run/user/1102/docker.sock", rendered)
        bubblewrap = "\0".join(MODULE.bubblewrap_command("BACKEND_TEST"))
        self.assertIn("/usr/bin/bwrap", bubblewrap)
        self.assertIn("--unshare-all", bubblewrap)
        self.assertIn("--share-net", bubblewrap)
        self.assertIn("--sandbox-exec\0BACKEND_TEST", bubblewrap)
        self.assertNotIn("/artifacts", bubblewrap)
        git_command = MODULE.git_observation_command(Path("/owned/worktree"), ["status"])
        self.assertIn("core.hooksPath=/dev/null", git_command)
        self.assertIn("core.fsmonitor=false", git_command)

    def test_playwright_container_has_no_network_or_host_authority(self):
        prefix = ["runuser", "docker"]
        command = MODULE.playwright_docker_command(
            prefix,
            "11111111-1111-4111-8111-111111111111",
            Path("/slot/toolchain"),
            Path("/owned/static"),
            Path("/owned/artifacts"),
        )
        rendered = "\0".join(command)
        for required in (
            "--network\0none",
            "--cap-drop\0ALL",
            "--security-opt\0no-new-privileges",
            "--read-only",
            "--cpus\0" + "2",
            "--memory\0" + "1g",
            "--pids-limit\0" + "256",
            "/tmp:rw,noexec,nosuid,nodev,size=256m",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("--privileged", command)
        self.assertNotIn("/srv/atenea/workspaces", rendered)

    def test_android_uses_reviewed_dockerfile_and_bounded_rootless_container(self):
        calls = []

        def fake_call(_prefix, arguments, _timeout, _output=None, capture=False):
            calls.append(arguments)
            stdout = "a" * 64 + "\n" if capture else None
            return subprocess.CompletedProcess(arguments, 0, stdout=stdout)

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "docker").mkdir()
            (source / "docker/android-builder.Dockerfile").write_text("reviewed\n")
            with mock.patch.object(MODULE, "sha256_file", return_value=MODULE.ANDROID_DOCKERFILE_SHA256), mock.patch.object(MODULE, "docker_call", side_effect=fake_call):
                result = MODULE.run_android(
                    ["rootless-docker"],
                    "11111111-1111-4111-8111-111111111111",
                    source,
                    MODULE.DEFINITIONS["ANDROID_BUILD"],
                    io.StringIO(),
                )
        self.assertEqual(0, result)
        build = calls[0]
        create = calls[1]
        self.assertEqual("default", build[build.index("--network") + 1])
        self.assertIn("10g", build)
        for required in (
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--read-only",
            "--cpus",
            "4",
            "--memory",
            "10g",
            "--pids-limit",
            "2048",
            "/workspace:rw,nosuid,nodev,size=12g",
            f"type=bind,src={source},dst=/source,readonly",
            "cp -a /source/. /workspace/ && cd /workspace/android && exec gradle :app:assembleDebug",
        ):
            self.assertIn(required, create)
        self.assertNotIn("--privileged", create)

    def test_android_rejects_an_unregistered_builder_before_docker(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "docker").mkdir()
            (source / "docker/android-builder.Dockerfile").write_text("foreign\n")
            with mock.patch.object(MODULE, "docker_call") as docker_call:
                with self.assertRaises(MODULE.Rejected):
                    MODULE.run_android(
                        ["rootless-docker"],
                        "11111111-1111-4111-8111-111111111111",
                        source,
                        MODULE.DEFINITIONS["ANDROID_BUILD"],
                        io.StringIO(),
                    )
            docker_call.assert_not_called()

    def test_artifact_publication_refuses_existing_or_surplus_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            for name in ("desktop.png", "mobile.png", "report.json"):
                (stage / name).write_text(name)
            destination = root / "validation-id"
            MODULE.publish_browser_artifacts(stage, destination)
            self.assertEqual(
                {"desktop.png", "mobile.png", "report.json"},
                {path.name for path in destination.iterdir()},
            )
            with self.assertRaises(MODULE.Rejected):
                MODULE.publish_browser_artifacts(stage, destination)

            foreign_stage = root / "foreign-stage"
            foreign_stage.mkdir()
            for name in ("desktop.png", "mobile.png", "report.json", "foreign"):
                (foreign_stage / name).write_text(name)
            with self.assertRaises(MODULE.Rejected):
                MODULE.publish_browser_artifacts(foreign_stage, root / "foreign-id")

    def test_durable_start_replays_exact_unit_and_conflict_fails_closed(self):
        session_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        arguments = ["BACKEND_TEST", session_id, "a" * 64, operation_id]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(
                MODULE, "require_root"
            ), mock.patch.object(
                MODULE, "unit_active", side_effect=[False, True]
            ), mock.patch.object(MODULE, "launch_durable_unit") as launch:
                first = MODULE.start_durable(arguments)
                second = MODULE.start_durable(list(arguments))
                conflicting = list(arguments)
                conflicting[2] = "b" * 64
                with self.assertRaises(MODULE.Rejected):
                    MODULE.start_durable(conflicting)
        self.assertEqual("RUNNING", first["state"])
        self.assertEqual(first, second)
        launch.assert_called_once()

    def test_inactive_confirmed_start_fails_without_second_execution(self):
        arguments = [
            "BACKEND_TEST",
            str(uuid.uuid4()),
            "a" * 64,
            str(uuid.uuid4()),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(
                MODULE, "require_root"
            ), mock.patch.object(
                MODULE, "unit_active", return_value=False
            ), mock.patch.object(MODULE, "launch_durable_unit") as launch:
                first = MODULE.start_durable(arguments)
                replay = MODULE.start_durable(list(arguments))
        self.assertEqual("RUNNING", first["state"])
        self.assertEqual("INFRASTRUCTURE_FAILED", replay["state"])
        launch.assert_called_once()

    def test_durable_cancel_is_exact_repeatable_and_terminal(self):
        session_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        arguments = ["WEB_BUILD", session_id, "a" * 64, operation_id]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(
                MODULE, "require_root"
            ), mock.patch.object(
                MODULE, "unit_active", return_value=False
            ), mock.patch.object(MODULE, "launch_durable_unit"):
                MODULE.start_durable(arguments)
                first = MODULE.cancel_durable(arguments)
                second = MODULE.cancel_durable(list(arguments))
        self.assertEqual("CANCELLED", first["state"])
        self.assertEqual("CANCELLED", first["terminalCause"])
        self.assertEqual(first, second)

    def test_durable_terminal_result_survives_fresh_inspection(self):
        session_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        arguments = ["BACKEND_TEST", session_id, "a" * 64, operation_id]
        result = {
            "validationId": operation_id,
            "sessionId": session_id,
            "operation": "BACKEND_TEST",
            "definitionRevision": "atenea-backend-test-v1",
            "sourceTreeFingerprintSha256": "a" * 64,
            "status": "SUCCEEDED",
            "exitCode": 0,
            "durationMillis": 9,
            "artifactManifestSha256": "b" * 64,
            "summary": "Closed validation passed",
            "valuesExposed": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(
                MODULE, "require_root"
            ), mock.patch.object(
                MODULE, "unit_active", return_value=False
            ), mock.patch.object(MODULE, "launch_durable_unit"), mock.patch.object(
                MODULE, "execute_validation", return_value=result
            ):
                MODULE.start_durable(arguments)
                MODULE.execute_durable(arguments)
                recovered = MODULE.inspect_durable(list(arguments))
        self.assertEqual("SUCCEEDED", recovered["state"])
        self.assertEqual("NONE", recovered["terminalCause"])
        self.assertEqual("b" * 64, recovered["artifactManifestSha256"])

    def test_durable_coordinator_unit_preserves_bounded_symbolic_authority(self):
        arguments = [
            "ANDROID_BUILD",
            "11111111-1111-4111-8111-111111111111",
            "a" * 64,
            "22222222-2222-4222-8222-222222222222",
        ]
        identity = MODULE.durable_identity(arguments)
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            MODULE.launch_durable_unit(identity)
        command = run.call_args.args[0]
        rendered = "\0".join(command)
        for required in (
            "--no-block",
            "RuntimeMaxSec=1320s",
            "KillMode=control-group",
            "ProtectSystem=strict",
            "RestrictAddressFamilies=AF_UNIX",
            f"ReadOnlyPaths={MODULE.WORKSPACE_ROOT} {MODULE.CONFIG.parent} /run/user",
            "--durable-execute\0ANDROID_BUILD",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("--shell", rendered)
        self.assertNotIn("--privileged", rendered)


if __name__ == "__main__":
    unittest.main()
