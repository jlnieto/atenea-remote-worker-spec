#!/usr/bin/env python3

import importlib.util
import io
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = Path(__file__).with_name("atenea-validation-v1.py")
SPEC = importlib.util.spec_from_file_location("atenea_validation_v1", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClosedValidationSandboxTests(unittest.TestCase):
    def test_artifact_directory_state_accepts_only_exact_root_owned_forms(self):
        path = Path("/fixed/artifact-directory")

        def classify(kind, mode, uid, gid):
            observed = SimpleNamespace(st_mode=kind | mode, st_uid=uid, st_gid=gid)
            with mock.patch.object(Path, "lstat", return_value=observed):
                return MODULE.artifact_directory_state(path, 988)[0]

        self.assertEqual("CURRENT", classify(stat.S_IFDIR, 0o750, 0, 0))
        self.assertEqual("INHERITED", classify(stat.S_IFDIR, 0o2750, 0, 988))
        for kind, mode, uid, gid in (
            (stat.S_IFDIR, 0o2770, 0, 988),
            (stat.S_IFDIR, 0o2750, 999, 988),
            (stat.S_IFDIR, 0o2750, 0, 987),
            (stat.S_IFLNK, 0o2750, 0, 988),
        ):
            with self.subTest(kind=kind, mode=mode, uid=uid, gid=gid):
                with self.assertRaises(MODULE.Rejected):
                    classify(kind, mode, uid, gid)

    def test_artifact_directory_rejects_non_uuid_session(self):
        with self.assertRaises(MODULE.Rejected):
            MODULE.prepare_session_artifacts("../foreign")

    @unittest.skipUnless(os.geteuid() == 0, "requires root-owned artifact directory test")
    def test_artifact_recovery_normalizes_inherited_dirs_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "artifacts"
            parent.mkdir()
            os.chown(parent, 99999, 98888)
            parent.chmod(0o2770)
            artifact_root = parent / "validations"
            artifact_root.mkdir(mode=0o750)
            session_id = str(uuid.uuid4())
            session_root = artifact_root / session_id
            session_root.mkdir(mode=0o750)
            self.assertEqual(0o2750, artifact_root.stat().st_mode & 0o7777)
            self.assertEqual(98888, session_root.stat().st_gid)
            original_inodes = (artifact_root.stat().st_ino, session_root.stat().st_ino)
            worker = SimpleNamespace(pw_uid=99999, pw_gid=98888)
            with mock.patch.object(MODULE, "ARTIFACT_ROOT", artifact_root), mock.patch.object(
                MODULE.pwd, "getpwnam", return_value=worker
            ):
                self.assertEqual(session_root, MODULE.prepare_session_artifacts(session_id))
                self.assertEqual(session_root, MODULE.prepare_session_artifacts(session_id))
            for path, inode in zip((artifact_root, session_root), original_inodes):
                observed = path.stat()
                self.assertEqual((0, 0, 0o750, inode), (
                    observed.st_uid, observed.st_gid, observed.st_mode & 0o7777, observed.st_ino
                ))

    @unittest.skipUnless(os.geteuid() == 0, "requires root-owned artifact directory test")
    def test_artifact_recovery_rejects_foreign_session_before_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "artifacts"
            parent.mkdir()
            os.chown(parent, 99999, 98888)
            parent.chmod(0o2770)
            artifact_root = parent / "validations"
            artifact_root.mkdir(mode=0o750)
            session_id = str(uuid.uuid4())
            session_root = artifact_root / session_id
            session_root.mkdir(mode=0o750)
            session_root.chmod(0o2770)
            worker = SimpleNamespace(pw_uid=99999, pw_gid=98888)
            with mock.patch.object(MODULE, "ARTIFACT_ROOT", artifact_root), mock.patch.object(
                MODULE.pwd, "getpwnam", return_value=worker
            ):
                with self.assertRaises(MODULE.Rejected):
                    MODULE.prepare_session_artifacts(session_id)
            self.assertEqual(0o2750, artifact_root.stat().st_mode & 0o7777)
            self.assertEqual(0o2770, session_root.stat().st_mode & 0o7777)

    @unittest.skipUnless(os.geteuid() == 0, "requires root-owned artifact directory test")
    def test_artifact_recovery_rejects_parent_drift_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "artifacts"
            parent.mkdir()
            os.chown(parent, 99999, 98888)
            parent.chmod(0o2775)
            artifact_root = parent / "validations"
            artifact_root.mkdir(mode=0o750)
            session_id = str(uuid.uuid4())
            session_root = artifact_root / session_id
            session_root.mkdir(mode=0o750)
            worker = SimpleNamespace(pw_uid=99999, pw_gid=98888)
            with mock.patch.object(MODULE, "ARTIFACT_ROOT", artifact_root), mock.patch.object(
                MODULE.pwd, "getpwnam", return_value=worker
            ):
                with self.assertRaises(MODULE.Rejected):
                    MODULE.prepare_session_artifacts(session_id)
            self.assertEqual(0o2750, artifact_root.stat().st_mode & 0o7777)
            self.assertEqual(0o2750, session_root.stat().st_mode & 0o7777)

    @unittest.skipUnless(os.geteuid() == 0, "requires root-owned artifact directory test")
    def test_artifact_creation_under_setgid_parent_is_canonical_on_first_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "artifacts"
            parent.mkdir()
            os.chown(parent, 99999, 98888)
            parent.chmod(0o2770)
            artifact_root = parent / "validations"
            session_id = str(uuid.uuid4())
            worker = SimpleNamespace(pw_uid=99999, pw_gid=98888)
            with mock.patch.object(MODULE, "ARTIFACT_ROOT", artifact_root), mock.patch.object(
                MODULE.pwd, "getpwnam", return_value=worker
            ):
                session_root = MODULE.prepare_session_artifacts(session_id)
            for path in (artifact_root, session_root):
                observed = path.stat()
                self.assertEqual((0, 0, 0o750), (
                    observed.st_uid, observed.st_gid, observed.st_mode & 0o7777
                ))

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
        self.assertEqual("backend", MODULE.DEFINITIONS["BACKEND_TEST"].runner)
        self.assertEqual("atenea-backend-test-v2", MODULE.DEFINITIONS["BACKEND_TEST"].revision)
        with self.assertRaises(MODULE.Rejected):
            MODULE.sandbox_operation_command("BACKEND_TEST")
        self.assertEqual(("./scripts/web-build.sh",), MODULE.sandbox_operation_command("WEB_BUILD"))
        with self.assertRaises(MODULE.Rejected):
            MODULE.sandbox_operation_command("ANDROID_BUILD")
        with self.assertRaises(MODULE.Rejected):
            MODULE.sandbox_operation_command("sh -c id")

    def test_systemd_and_bubblewrap_command_seal_identity_resources_and_mounts(self):
        definition = MODULE.DEFINITIONS["WEB_BUILD"]
        source = Path("/srv/atenea/artifacts/validations/session/.validation-run/source")
        artifacts = Path("/srv/atenea/artifacts/validations/session/.validation-run/artifacts")
        resolv = Path("/srv/atenea/artifacts/validations/session/.validation-run/resolv.conf")
        command = MODULE.sandbox_command(
            "WEB_BUILD",
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
            "MemoryMax=3G",
            "TasksMax=512",
            "RuntimeMaxSec=600s",
            "LimitFSIZE=67108864",
            "TemporaryFileSystem=/work:rw,nosuid,nodev,size=4G",
            f"BindReadOnlyPaths={source}:/source",
            f"BindReadOnlyPaths={resolv}:/validation-resolv.conf",
            f"BindPaths={artifacts}:/artifacts",
            "NoNewPrivileges=yes",
            "IPAddressDeny=100.64.0.0/10",
            "--sandbox-supervise\0WEB_BUILD",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("User=root", rendered)
        self.assertNotIn("/run/user/1102/docker.sock", rendered)
        bubblewrap = "\0".join(MODULE.bubblewrap_command("WEB_BUILD"))
        self.assertIn("/usr/bin/bwrap", bubblewrap)
        self.assertIn("--unshare-all", bubblewrap)
        self.assertIn("--share-net", bubblewrap)
        self.assertIn("--sandbox-exec\0WEB_BUILD", bubblewrap)
        self.assertIn("--symlink\0work/tmp\0/tmp", bubblewrap)
        self.assertNotIn("--bind\0/tmp\0/tmp", bubblewrap)
        self.assertNotIn("--ro-bind\0/tmp\0/tmp", bubblewrap)
        self.assertNotIn("/artifacts", bubblewrap)
        git_command = MODULE.git_observation_command(Path("/owned/worktree"), ["status"])
        self.assertIn("core.hooksPath=/dev/null", git_command)
        self.assertIn("core.fsmonitor=false", git_command)

    def test_private_temporary_directory_is_prepared_for_maven_without_host_tmp(self):
        with tempfile.TemporaryDirectory() as root:
            work_root = Path(root)
            worktree = MODULE.prepare_sandbox_directories(work_root)
            self.assertEqual(work_root / "repo", worktree)
            self.assertFalse(worktree.exists())
            self.assertEqual(0o700, (work_root / "tmp").stat().st_mode & 0o777)
            self.assertEqual(0o700, (work_root / "home").stat().st_mode & 0o777)
            self.assertEqual("/work/tmp", MODULE.clean_environment()["TMPDIR"])
            with self.assertRaises(MODULE.Rejected):
                MODULE.prepare_sandbox_directories(work_root)

    def test_nested_proc_preserves_other_systemd_protections_without_host_proc_bind(self):
        for operation in ("BACKEND_TEST", "WEB_BUILD", "PLAYWRIGHT_ACCEPTANCE"):
            with self.subTest(operation=operation):
                command = MODULE.sandbox_command(
                    operation,
                    "11111111-1111-4111-8111-111111111111",
                    MODULE.DEFINITIONS[operation],
                    "atenea-slot1",
                    1101,
                    Path("/fixed/source"),
                    Path("/fixed/artifacts"),
                    Path("/fixed/resolv.conf"),
                )
                for required in (
                    "NoNewPrivileges=yes", "PrivateDevices=yes", "ProtectSystem=strict",
                    "ProtectHome=yes", "ProtectKernelModules=yes", "ProtectControlGroups=yes",
                    "RestrictSUIDSGID=yes", "LockPersonality=yes", "RestrictRealtime=yes",
                    "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
                    "IPAddressDeny=127.0.0.0/8", "IPAddressDeny=100.64.0.0/10",
                ):
                    self.assertIn(required, command)
                self.assertNotIn("ProtectKernelTunables=yes", command)
                self.assertNotIn("ProtectKernelLogs=yes", command)
                bubblewrap = "\0".join(MODULE.bubblewrap_command(operation))
                self.assertIn("--unshare-all", bubblewrap)
                self.assertIn("--proc\0/proc", bubblewrap)
                self.assertNotIn("--bind\0/proc", bubblewrap)
                self.assertNotIn("--ro-bind\0/proc", bubblewrap)

    @unittest.skipUnless(
        os.geteuid() == 0 and os.environ.get("ATENEA_VALIDATION_SANDBOX_SMOKE") == "true",
        "requires explicit root opt-in for the systemd/Bubblewrap smoke",
    )
    def test_opt_in_systemd_bubblewrap_java_startup_and_kernel_access(self):
        slot = pwd.getpwnam("atenea-slot1")
        with tempfile.TemporaryDirectory(prefix="atenea-validation-preflight.") as temporary:
            root = Path(temporary)
            root.chmod(0o755)
            source = root / "source"
            source.mkdir(mode=0o755)
            artifacts = root / "artifacts"
            artifacts.mkdir(mode=0o700)
            os.chown(artifacts, slot.pw_uid, slot.pw_gid)
            resolv = root / "resolv.conf"
            resolv.write_text("nameserver 1.1.1.1\n", encoding="ascii")
            resolv.chmod(0o644)
            helper = root / "helper.py"
            shutil.copyfile(MODULE_PATH, helper)
            helper.chmod(0o644)
            with mock.patch.object(MODULE, "__file__", str(helper)):
                command = MODULE.sandbox_command(
                    "BACKEND_TEST", str(uuid.uuid4()), MODULE.DEFINITIONS["BACKEND_TEST"],
                    slot.pw_name, slot.pw_uid, source, artifacts, resolv,
                )
                bubblewrap = MODULE.bubblewrap_command("BACKEND_TEST")
            unit_index = command.index("--unit") + 1
            unit = command[unit_index].replace("-sandbox-", "-preflight-")
            command[unit_index] = unit
            # Keep both generated sandbox layers; replace only the candidate
            # entrypoint with a fixed, non-mutating Java/kernel-access probe.
            entrypoint = bubblewrap.index("/usr/bin/python3")
            bubblewrap[entrypoint:] = [
                "/usr/bin/sh", "-c",
                "test ! -w /proc/sys/kernel/hostname && "
                "test ! -r /proc/kmsg && test ! -e /dev/kmsg && "
                "exec /usr/bin/java -XshowSettings:security -version",
            ]
            command[command.index("--") + 1:] = bubblewrap
            try:
                completed = subprocess.run(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, timeout=30, check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stdout)
                self.assertIn("openjdk version", completed.stdout)
            finally:
                subprocess.run(
                    ["/usr/bin/systemctl", "stop", unit], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=10, check=False,
                )

    def test_bubblewrap_mounts_only_fixed_java_config_read_only(self):
        command = MODULE.bubblewrap_command("BACKEND_TEST")
        read_only = [
            (command[index + 1], command[index + 2])
            for index, value in enumerate(command)
            if value == "--ro-bind"
        ]
        writable = [
            (command[index + 1], command[index + 2])
            for index, value in enumerate(command)
            if value == "--bind"
        ]
        self.assertEqual(
            1,
            read_only.count(("/etc/java-21-openjdk", "/etc/java-21-openjdk")),
        )
        self.assertNotIn(("/etc", "/etc"), read_only)
        self.assertNotIn(("/etc/java-21-openjdk", "/etc/java-21-openjdk"), writable)
        self.assertEqual([("/work", "/work")], writable)

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
        # The execution/mount/context contract is covered by the dedicated
        # test-atenea-android-validation-v2.py without a real Docker daemon.
        definition = MODULE.DEFINITIONS["ANDROID_BUILD"]
        self.assertEqual("atenea-android-build-v2", definition.revision)
        self.assertEqual((1200, "400%", "10G", 2048, "12G"), (
            definition.timeout, definition.cpu_quota, definition.memory_max,
            definition.tasks_max, definition.storage_max))

    def test_android_rejects_an_unregistered_builder_before_docker(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "docker").mkdir()
            (source / "docker/android-builder.Dockerfile").write_text("foreign\n")
            with mock.patch.object(MODULE, "exact_regular_file", return_value=False), \
                    mock.patch.object(MODULE, "docker_call") as docker_call:
                result = MODULE.run_android(
                        ["rootless-docker"],
                        "11111111-1111-4111-8111-111111111111",
                        source,
                        MODULE.DEFINITIONS["ANDROID_BUILD"],
                        io.StringIO(),
                    )
                self.assertEqual("INSTALLED_TOOLCHAIN_INVALID", result.error_code)
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
            "definitionRevision": "atenea-backend-test-v2",
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

    def test_retained_v1_terminal_evidence_is_readable_but_cannot_execute_as_v2(self):
        arguments = ["BACKEND_TEST", str(uuid.uuid4()), "a" * 64, str(uuid.uuid4())]
        identity = MODULE.durable_identity(arguments)
        legacy = {**identity, "definitionRevision": "atenea-backend-test-v1"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(MODULE, "require_root"), \
                    mock.patch.object(MODULE, "execute_validation") as execute:
                with MODULE.locked_operation(identity) as directory:
                    record = MODULE.new_operation(legacy)
                    record.update(state="CANDIDATE_FAILED", terminalCause="CANDIDATE", exitCode=1)
                    MODULE.write_operation(directory, record)
                result = MODULE.inspect_durable(arguments)
                self.assertEqual("atenea-backend-test-v1", result["definitionRevision"])
                self.assertEqual("CANDIDATE_FAILED", result["state"])
                self.assertEqual(0, MODULE.execute_durable(arguments))
                execute.assert_not_called()
                with MODULE.locked_operation(identity) as directory:
                    record["state"] = "RUNNING"
                    MODULE.write_operation(directory, record)
                with self.assertRaises(MODULE.Rejected):
                    MODULE.inspect_durable(arguments)

    def test_infrastructure_diagnostic_survives_fresh_inspection_without_becoming_candidate_failure(self):
        session_id, operation_id = str(uuid.uuid4()), str(uuid.uuid4())
        arguments = ["BACKEND_TEST", session_id, "a" * 64, operation_id]
        result = {
            "status": "BLOCKED", "failureClass": "INFRASTRUCTURE",
            "exitCode": None, "durationMillis": 3,
            "artifactManifestSha256": "b" * 64,
            "summary": "BACKEND_TEST/TEST_DATABASE: TEST_DATABASE_SETUP_FAILED",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(MODULE, "JOURNAL_ROOT", root), mock.patch.object(MODULE, "require_root"), \
                    mock.patch.object(MODULE, "unit_active", return_value=False), \
                    mock.patch.object(MODULE, "launch_durable_unit"), \
                    mock.patch.object(MODULE, "execute_validation", return_value=result):
                MODULE.start_durable(arguments)
                MODULE.execute_durable(arguments)
                recovered = MODULE.inspect_durable(list(arguments))
        self.assertEqual("INFRASTRUCTURE_FAILED", recovered["state"])
        self.assertEqual("INFRASTRUCTURE", recovered["terminalCause"])
        self.assertEqual(result["summary"], recovered["summary"])
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
            f"ReadOnlyPaths={MODULE.WORKSPACE_ROOT} {MODULE.CHANGE_WORKSPACE_ROOT} "
            f"{MODULE.CONFIG.parent} /run/user {MODULE.RUNTIME_ADMISSION}",
            "ReadWritePaths=/srv/atenea/artifacts /srv/atenea/worker/validation-broker-v1 "
            "/srv/atenea/worker/runtime-admission-v1",
            "--durable-execute\0ANDROID_BUILD",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("--shell", rendered)
        self.assertNotIn("--privileged", rendered)

    def test_change_identity_is_exact_and_ephemeral_slot_is_released(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        change_key = "33333333-3333-4333-8333-333333333333"
        operation_id = "22222222-2222-4222-8222-222222222222"
        identity = MODULE.durable_identity([
            "ANDROID_BUILD",
            session_id,
            f"remote:ax42-01:change:{change_key}",
            "a" * 64,
            operation_id,
        ])
        self.assertEqual(f"remote:ax42-01:change:{change_key}", identity["workspaceIdentity"])
        calls = []

        def admission(operation, observed_session):
            calls.append((operation, observed_session))
            return {
                "sessionId": session_id,
                "record": {"normal": {"slot": "slot3"}},
            }

        slot = ("atenea-slot3", 1103, Path("/var/lib/atenea-slots/slot3"), Path("/run/user/1103/docker.sock"))
        with mock.patch.object(MODULE, "admission_call", side_effect=admission), mock.patch.object(
            MODULE, "slot_authority", return_value=slot
        ):
            with MODULE.validation_slot(session_id, MODULE.DEFINITIONS["ANDROID_BUILD"], None) as observed:
                self.assertEqual(slot, observed)
        self.assertEqual(
            [
                ("acquire-normal", session_id),
                ("acquire-heavy", session_id),
                ("release-heavy", session_id),
                ("release-normal", session_id),
            ],
            calls,
        )

        with self.assertRaises(MODULE.Rejected):
            MODULE.durable_identity([
                "ANDROID_BUILD", session_id, "remote:ax42-01:change:../../foreign",
                "a" * 64, operation_id,
            ])

    def test_failed_heavy_admission_releases_the_normal_slot(self):
        session_id = "11111111-1111-4111-8111-111111111111"
        calls = []

        def admission(operation, observed_session):
            calls.append((operation, observed_session))
            if operation == "acquire-heavy":
                raise MODULE.Rejected("validation authority rejected")
            return {
                "sessionId": session_id,
                "record": {"normal": {"slot": "slot2"}},
            }

        with mock.patch.object(MODULE, "admission_call", side_effect=admission):
            with self.assertRaises(MODULE.Rejected):
                with MODULE.validation_slot(
                    session_id, MODULE.DEFINITIONS["ANDROID_BUILD"], None
                ):
                    self.fail("heavy validation must not start")
        self.assertEqual(
            [
                ("acquire-normal", session_id),
                ("acquire-heavy", session_id),
                ("release-normal", session_id),
            ],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
