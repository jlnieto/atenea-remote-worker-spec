#!/usr/bin/env python3
"""Focused contract tests; no real worker, Docker daemon or database is mutated."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


RUNNER = module("backend_validation_test", "atenea-validation-v1.py")
PREPARER = module("backend_preparer_test", "atenea-backend-test-v2.py")
OPERATION = "11111111-1111-4111-8111-111111111111"
SESSION = "22222222-2222-4222-8222-222222222222"


class BackendValidationTest(unittest.TestCase):
    def invoke(self, root, *, preparation_exit=0, test_exit=0, test_output="", wrong_pom=False,
               wrong_owner=False, cleanup_exit=0, extra_maven_config=False):
        source = root / "source"
        source.mkdir()
        pom = source / "pom.xml"
        pom.write_text("<project/>")
        if extra_maven_config:
            (source / ".mvn").mkdir()
            (source / ".mvn/maven.config").write_text("-DskipTests=true")
        calls = []

        def docker(prefix, arguments, timeout, output=None, capture=False):
            calls.append(arguments)
            result = 0
            stdout = ""
            if arguments[:2] == ["image", "inspect"]:
                stdout = "sha256:" + "a" * 64
            if arguments[0] == "create":
                stdout = "b" * 64
            if "--prepare" in arguments:
                result = preparation_exit
            if "test" in arguments:
                result = test_exit
                output.write(test_output)
            if arguments[0] == "rm":
                result = cleanup_exit
            return subprocess.CompletedProcess(arguments, result, stdout)

        with mock.patch.object(RUNNER, "BACKEND_DOCKERFILE", Path(__file__).with_name("atenea-backend-test-v2.Dockerfile")), \
                mock.patch.object(RUNNER, "BACKEND_PREPARER", Path(__file__).with_name("atenea-backend-test-v2.py")), \
                mock.patch.object(RUNNER, "exact_regular_file", return_value=not wrong_owner), \
                mock.patch.object(RUNNER, "BACKEND_POM_SHA256", "0" * 64 if wrong_pom else RUNNER.sha256_file(pom)), \
                mock.patch.object(RUNNER, "make_slot_readable"), \
                mock.patch.object(RUNNER.pwd, "getpwnam", return_value=SimpleNamespace(pw_gid=1101)), \
                mock.patch.object(RUNNER, "docker_call", side_effect=docker):
            with (root / "output").open("w") as output:
                result = RUNNER.run_backend(["runuser", "-u", "atenea-slot1", "--", "docker"],
                                           OPERATION, source, RUNNER.DEFINITIONS["BACKEND_TEST"], output)
        return result, calls

    def test_exact_hashes_match_the_versioned_toolchain(self):
        for filename, expected in (
            ("atenea-backend-test-v2.Dockerfile", RUNNER.BACKEND_DOCKERFILE_SHA256),
            ("atenea-backend-test-v2.py", RUNNER.BACKEND_PREPARER_SHA256),
        ):
            self.assertEqual(expected, RUNNER.sha256_file(Path(__file__).with_name(filename)))

    def test_prefetch_uses_the_same_central_repository_identity_as_offline_execution(self):
        recipe = Path(__file__).with_name("atenea-backend-test-v2.Dockerfile").read_text()
        self.assertIn("<id>central</id><mirrorOf>*</mirrorOf>", recipe)
        self.assertIn("https://repo.maven.apache.org/maven2", recipe)
        self.assertEqual(4, recipe.count("mvn -s /opt/atenea-build/settings.xml"))
        self.assertIn("dependency:resolve -DincludeScope=test", recipe)
        self.assertIn("-Dartifact=org.junit.platform:junit-platform-launcher:1.11.4", recipe)
        self.assertNotIn("COPY settings.xml", recipe)

    def test_backend_has_private_loopback_database_offline_tests_and_no_host_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary))
        self.assertEqual("NONE", result.failure_class)
        create = next(call for call in calls if call[0] == "create")
        self.assertEqual("none", create[create.index("--network") + 1])
        self.assertEqual("1000:0", create[create.index("--user") + 1])
        self.assertIn("--read-only", create)
        self.assertIn("ALL", create)
        self.assertIn("SPRING_DATASOURCE_URL=jdbc:postgresql://127.0.0.1:5432/atenea_test", create)
        self.assertIn("SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=0", create)
        self.assertIn("SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=5", create)
        self.assertIn("ATENEA_WORKSPACE_ROOT=/workspace/repos", create)
        self.assertIn("JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2", create)
        tmpfs = [create[index + 1] for index, value in enumerate(create) if value == "--tmpfs"]
        self.assertEqual([
            "/work:rw,nosuid,nodev,size=5g,uid=1000,gid=0,mode=0700",
            "/workspace:rw,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
            "/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
        ], tmpfs)
        mounts = [create[index + 1] for index, value in enumerate(create) if value == "--mount"]
        self.assertEqual(1, len(mounts))
        self.assertTrue(mounts[0].endswith("dst=/source,readonly"))
        rendered = "\0".join(create)
        for forbidden in ("host", "docker.sock", "/srv/atenea", "/etc/atenea", "credentials", "--privileged"):
            self.assertNotIn(forbidden, rendered)
        test = next(call for call in calls if "test" in call)
        self.assertIn("--offline", test)
        self.assertIn("-Dmaven.repo.local=/work/m2", test)
        self.assertIn("-Dspring.test.context.cache.maxSize=1", test)
        self.assertLess(calls.index(next(call for call in calls if "--prepare" in call)), calls.index(test))
        self.assertEqual(["rm", "--force", "b" * 64], calls[-2])

    def test_context_budget_keeps_the_full_suite_and_existing_resource_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary))
        self.assertEqual("NONE", result.failure_class)
        create = next(call for call in calls if call[0] == "create")
        self.assertEqual("2", create[create.index("--cpus") + 1])
        self.assertEqual("512", create[create.index("--pids-limit") + 1])
        self.assertEqual("4g", create[create.index("--memory") + 1])
        self.assertEqual(1, create.count("JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2"))
        test = next(call for call in calls if "test" in call)
        self.assertEqual("test", test[-1])
        self.assertEqual(1, test.count("-Dspring.test.context.cache.maxSize=1"))
        self.assertFalse(any(value.startswith(("-Dtest=", "-Dskip", "-Dmaven.test.skip"))
                             for value in test))
        self.assertEqual(900, RUNNER.DEFINITIONS["BACKEND_TEST"].timeout)

    def test_database_preparation_failure_is_infrastructure_and_never_starts_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary), preparation_exit=70)
        self.assertEqual(("TEST_DATABASE", "TEST_DATABASE_SETUP_FAILED", "INFRASTRUCTURE"),
                         (result.phase, result.error_code, result.failure_class))
        self.assertFalse(any("test" in call for call in calls))
        self.assertEqual("rm", calls[-2][0])

    def test_wrong_pom_fails_closed_before_build_or_candidate_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary), wrong_pom=True)
        self.assertEqual("POLICY", result.failure_class)
        self.assertEqual([], calls)

    def test_untrusted_toolchain_owner_fails_before_any_docker_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary), wrong_owner=True)
        self.assertEqual("INSTALLED_TOOLCHAIN_INVALID", result.error_code)
        self.assertEqual([], calls)

    def test_candidate_cannot_override_the_closed_maven_command_via_local_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.invoke(Path(temporary), extra_maven_config=True)
        self.assertEqual("UNSUPPORTED_DEPENDENCY_MANIFEST", result.error_code)
        self.assertEqual([], calls)

    def test_failed_cleanup_cannot_be_reported_as_successful_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RUNNER.RuntimeFailure) as error:
                self.invoke(Path(temporary), cleanup_exit=1)
        self.assertEqual("TEST_RUNTIME_CLEANUP_FAILED", error.exception.outcome.error_code)

    def test_failed_assertion_and_unexplained_exit_are_not_both_candidate_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, _ = self.invoke(Path(temporary), test_exit=1, test_output="[ERROR] There are test failures")
        self.assertEqual(("TESTS", "TESTS_FAILED", "CANDIDATE"),
                         (result.phase, result.error_code, result.failure_class))
        unknown = RUNNER.classify_execution(1, "unclassified failure", "BACKEND_TEST")
        self.assertEqual("VALIDATION", unknown.failure_class)
        setup = RUNNER.classify_execution(1, "bwrap: mount /proc failed", "WEB_BUILD")
        self.assertEqual("INFRASTRUCTURE", setup.failure_class)

    def test_missing_android_plugin_cache_is_not_a_candidate_test_failure(self):
        result = RUNNER.classify_execution(1,
            "Plugin [id: 'com.android.application'] was not found in any of the following sources",
            "ANDROID_BUILD")
        self.assertEqual(("DEPENDENCIES", "TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE"),
                         (result.phase, result.error_code, result.failure_class))

    def test_durable_diagnostic_retains_only_bounded_symbolic_facts_after_output_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            output.write_text("password=secret-pass token=abc /srv/private\n"
                              "com.atenea.operations.MonitoringTest\n[ERROR] There are test failures\n")
            arguments = ["BACKEND_TEST", SESSION, "remote:ax42-01:change:" + OPERATION, "a" * 64, OPERATION]
            digest = RUNNER.persist_diagnostic(root, arguments, RUNNER.DEFINITIONS["BACKEND_TEST"],
                       RUNNER.RunOutcome(1, "TESTS", "TESTS_FAILED", "CANDIDATE"), output, 10)
            output.unlink()
            destination = root / (OPERATION + "-diagnostic-v1.json")
            encoded = destination.read_bytes()
            self.assertEqual(digest, hashlib.sha256(encoded).hexdigest())
            self.assertEqual(0o600, destination.stat().st_mode & 0o777)
            self.assertEqual(os.geteuid(), destination.stat().st_uid)
            document = json.loads(encoded)
            self.assertEqual("TESTS_FAILED", document["errorCode"])
            self.assertEqual(["com.atenea.operations.MonitoringTest"], document["testClasses"])
            for forbidden in (b"password", b"secret-pass", b"token=abc", b"/srv/private"):
                self.assertNotIn(forbidden, encoded)


class BackendPreparationTest(unittest.TestCase):
    def test_non_root_fixed_database_cache_and_clean_source_are_prepared_before_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, source, cache = (base / name for name in ("work", "source", "cache"))
            for directory in (root, source, cache):
                directory.mkdir()
            (source / "pom.xml").write_text("<project/>")
            (source / ".git").write_text("gitdir: /host/unavailable")
            (source / "target").mkdir()
            (source / "target/stale.class").write_text("old compiled output")
            (source / "android/.cache").mkdir(parents=True)
            (source / "android/.cache/stale").write_text("old Android cache")
            (source / "android/app/build").mkdir(parents=True)
            (source / "android/app/build/stale").write_text("old Android output")
            (source / "src/main/java").mkdir(parents=True)
            (source / "src/main/java/Current.java").write_text("current source")
            (cache / "dependency").write_text("cached")
            with mock.patch.object(PREPARER, "ROOT", root), mock.patch.object(PREPARER, "SOURCE", source), \
                    mock.patch.object(PREPARER, "CACHE", cache), mock.patch.object(PREPARER.os, "geteuid", return_value=1000), \
                    mock.patch.object(PREPARER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(0, PREPARER.prepare())
                self.assertEqual(64, PREPARER.prepare())
            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(commands[0][0].endswith("/16/bin/initdb"))
            self.assertIn("--auth=trust", commands[0])
            self.assertIn("-h 127.0.0.1 -p 5432 -k /work/pgsocket", commands[1])
            self.assertEqual("atenea_test", commands[2][-1])
            self.assertEqual("cached", (root / "m2/dependency").read_text())
            self.assertEqual("current source", (root / "repo/src/main/java/Current.java").read_text())
            for stale in (".git", "target", "android/.cache", "android/app/build"):
                self.assertFalse((root / "repo" / stale).exists(), stale)

    def test_root_or_unexpected_arguments_are_rejected_without_execution(self):
        with mock.patch.object(PREPARER.os, "geteuid", return_value=0), \
                mock.patch.object(PREPARER.subprocess, "run") as run:
            self.assertEqual(64, PREPARER.prepare())
            run.assert_not_called()
        with mock.patch.object(sys, "argv", ["preparer", "--prepare", "/arbitrary"]):
            self.assertEqual(64, PREPARER.main())


if __name__ == "__main__":
    unittest.main()
