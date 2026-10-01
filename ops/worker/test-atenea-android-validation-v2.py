#!/usr/bin/env python3
"""Focused closed-runtime tests. Never contacts a worker or a Docker daemon."""

import contextlib
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


RUNNER = module("android_closed_runner_test", "atenea-validation-v1.py")
RUNTIME = module("android_closed_runtime_test", "atenea-android-runtime-v2.py")
OPERATION = "11111111-1111-4111-8111-111111111111"
SESSION = "22222222-2222-4222-8222-222222222222"


class AndroidValidationTest(unittest.TestCase):
    def invoke(self, root, *, prepare_exit=0, cleanup_exit=0, wrong_toolchain=False,
               wrong_metadata=False):
        source = root / "source"
        source.mkdir()
        (source / "candidate-secret").write_text("NOT-A-BUILD-INPUT")
        (source / "buildSrc").mkdir()
        (source / "buildSrc/evil.gradle").write_text("NOT-A-BUILD-INPUT")
        calls = []
        contexts = []

        def docker(prefix, args, timeout, output=None, capture=False):
            calls.append(args)
            result, stdout = 0, ""
            if args[0] == "build":
                context = Path(args[-1])
                contexts.extend(path.relative_to(context).as_posix() for path in context.rglob("*") if path.is_file())
                self.assertNotIn("NOT-A-BUILD-INPUT", "\n".join(path.read_text() for path in context.rglob("*") if path.is_file()))
            if args[:2] == ["image", "inspect"]:
                stdout = "sha256:" + "a" * 64
            if args[0] == "create":
                stdout = "b" * 64
            if "--prepare" in args:
                result = prepare_exit
            if args[0] == "rm":
                result = cleanup_exit
            return subprocess.CompletedProcess(args, result, stdout)

        with contextlib.ExitStack() as stack:
            for key, filename in (("ANDROID_INPUTS", "atenea-android-inputs-v2.json"),
                                  ("ANDROID_FRAGMENT", "atenea-android-validation-v2.Dockerfile"),
                                  ("ANDROID_RUNTIME", "atenea-android-runtime-v2.py")):
                stack.enter_context(mock.patch.object(RUNNER, key, Path(__file__).with_name(filename)))
            stack.enter_context(mock.patch.object(RUNNER, "exact_regular_file", return_value=not wrong_toolchain))
            stack.enter_context(mock.patch.object(RUNNER, "android_build_inputs", return_value=None if wrong_metadata else {
                "docker/android-builder.Dockerfile": b"FROM reviewed-sdk\n",
                "android/settings.gradle.kts": b"// reviewed settings\n",
            }))
            stack.enter_context(mock.patch.object(RUNNER, "make_slot_readable"))
            stack.enter_context(mock.patch.object(RUNNER.pwd, "getpwnam", return_value=SimpleNamespace(pw_gid=1101)))
            stack.enter_context(mock.patch.object(RUNNER, "docker_call", side_effect=docker))
            with (root / "output").open("w") as output:
                result = RUNNER.run_android(["runuser", "-u", "atenea-slot1", "--", "docker"],
                           OPERATION, source, RUNNER.DEFINITIONS["ANDROID_BUILD"], output)
        return result, calls, contexts

    def test_registered_files_match_the_exact_reviewed_hashes(self):
        for filename, digest in (
            ("atenea-android-inputs-v2.json", RUNNER.ANDROID_INPUTS_SHA256),
            ("atenea-android-validation-v2.Dockerfile", RUNNER.ANDROID_FRAGMENT_SHA256),
            ("atenea-android-runtime-v2.py", RUNNER.ANDROID_RUNTIME_SHA256),
        ):
            self.assertEqual(digest, RUNNER.sha256_file(Path(__file__).with_name(filename)))

    def test_build_context_excludes_candidate_code_and_runtime_is_nonroot_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls, contexts = self.invoke(Path(temporary))
        self.assertEqual(0, result.exit_code)
        self.assertEqual({"Dockerfile", "android/settings.gradle.kts", "atenea-android-runtime-v2.py"}, set(contexts))
        create = next(call for call in calls if call[0] == "create")
        self.assertEqual("none", create[create.index("--network") + 1])
        self.assertEqual("1000:0", create[create.index("--user") + 1])
        self.assertIn("--read-only", create)
        self.assertIn("no-new-privileges", create)
        tmpfs = [create[index + 1] for index, value in enumerate(create) if value == "--tmpfs"]
        self.assertEqual([
            "/work:rw,exec,nosuid,nodev,size=12g,uid=1000,gid=0,mode=0700",
            "/tmp:rw,noexec,nosuid,nodev,size=512m,uid=1000,gid=0,mode=0700",
        ], tmpfs)
        mounts = [create[index + 1] for index, value in enumerate(create) if value == "--mount"]
        self.assertEqual(1, len(mounts))
        self.assertTrue(mounts[0].endswith("dst=/source,readonly"))
        for forbidden in ("docker.sock", "/srv/atenea", "/root/.gradle", "--privileged", "type=volume"):
            self.assertNotIn(forbidden, "\0".join(create))
        test = next(call for call in calls if ":app:assembleDebug" in call)
        self.assertIn("--offline", test)
        self.assertIn("testDebugUnitTest", test)
        self.assertLess(calls.index(next(call for call in calls if "--prepare" in call)), calls.index(test))
        self.assertIn("sha256:" + "a" * 64, create)
        self.assertEqual(["rm", "--force", "b" * 64], calls[-2])

    def test_recipe_proves_a_cold_relocated_cache_without_network_or_old_outputs(self):
        recipe = Path(__file__).with_name("atenea-android-validation-v2.Dockerfile").read_text()
        self.assertIn("RUN --network=none", recipe)
        self.assertIn("--offline", recipe)
        self.assertIn("--seal", recipe)
        self.assertIn("USER 1000:0", recipe)
        self.assertNotIn("COPY .", recipe)

    def test_bad_registered_toolchain_or_metadata_never_reaches_docker(self):
        for argument, code in (("wrong_toolchain", "INSTALLED_TOOLCHAIN_INVALID"),
                               ("wrong_metadata", "UNSUPPORTED_DEPENDENCY_MANIFEST")):
            with self.subTest(argument=argument), tempfile.TemporaryDirectory() as temporary:
                result, calls, _context = self.invoke(Path(temporary), **{argument: True})
                self.assertEqual(code, result.error_code)
                self.assertEqual([], calls)

    def test_cache_preparation_failure_is_infrastructure_without_candidate_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls, _context = self.invoke(Path(temporary), prepare_exit=70)
        self.assertEqual(("TEST_CACHE_INCOMPLETE", "INFRASTRUCTURE"), (result.error_code, result.failure_class))
        self.assertFalse(any(":app:assembleDebug" in call for call in calls))

    def test_cleanup_failure_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(RUNNER.RuntimeFailure):
            self.invoke(Path(temporary), cleanup_exit=1)

    def test_input_metadata_requires_an_exact_bundle_and_rejects_symlinked_parents(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "android").mkdir()
            config = source / "android/build.gradle.kts"
            config.write_bytes(b"reviewed")
            manifest = {"common": {}, "bundles": [{"files": {
                "android/build.gradle.kts": hashlib.sha256(b"reviewed").hexdigest()}}]}
            with mock.patch.object(RUNNER, "load_json", return_value=manifest):
                self.assertIsNotNone(RUNNER.android_build_inputs(source))
                alternative = source / "android/build.gradle"
                alternative.write_text("tasks.configureEach { enabled = false }")
                self.assertIsNone(RUNNER.android_build_inputs(source))
                alternative.unlink()
                (source / "android/buildSrc").mkdir()
                self.assertIsNone(RUNNER.android_build_inputs(source))
                (source / "android/buildSrc").rmdir()
                config.write_bytes(b"changed")
                self.assertIsNone(RUNNER.android_build_inputs(source))
                config.write_bytes(b"reviewed")
                (source / "android").rename(source / "foreign")
                (source / "android").symlink_to(source / "foreign", target_is_directory=True)
                self.assertIsNone(RUNNER.android_build_inputs(source))

    def test_apk_version_bump_does_not_change_toolchain_but_executable_labels_are_rejected(self):
        first = b'plugins { reviewed() }\n        versionCode = 138\n        versionName = "0.5.105"\n'
        second = first.replace(b"138", b"141").replace(b"0.5.105", b"0.5.108")
        self.assertEqual(RUNNER.normalized_android_application(first), RUNNER.normalized_android_application(second))
        malicious = first.replace(b'"0.5.105"', b'"${Runtime.getRuntime().exec(\"id\")}"')
        self.assertIsNone(RUNNER.normalized_android_application(malicious))
        self.assertIsNone(RUNNER.normalized_android_application(first + b"        versionCode = 2\n"))
        modified = first.replace(b"reviewed()", b"unreviewed()")
        self.assertNotEqual(RUNNER.normalized_android_application(first), RUNNER.normalized_android_application(modified))

    def test_android_legacy_terminal_evidence_is_inspectable_but_not_reexecuted(self):
        args = ["ANDROID_BUILD", SESSION, "a" * 64, OPERATION]
        identity = RUNNER.durable_identity(args)
        legacy = {**identity, "definitionRevision": "atenea-android-build-v1"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o750)
            with mock.patch.object(RUNNER, "JOURNAL_ROOT", root), mock.patch.object(RUNNER, "require_root"), \
                    mock.patch.object(RUNNER, "execute_validation") as execute:
                with RUNNER.locked_operation(identity) as directory:
                    record = RUNNER.new_operation(legacy)
                    record.update(state="INFRASTRUCTURE_FAILED", terminalCause="INFRASTRUCTURE")
                    RUNNER.write_operation(directory, record)
                self.assertEqual("atenea-android-build-v1", RUNNER.inspect_durable(args)["definitionRevision"])
                self.assertEqual(0, RUNNER.execute_durable(args))
                execute.assert_not_called()
                with RUNNER.locked_operation(identity) as directory:
                    record["state"] = "RUNNING"
                    RUNNER.write_operation(directory, record)
                with self.assertRaises(RUNNER.Rejected):
                    RUNNER.inspect_durable(args)


class AndroidCacheTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.source, self.root, self.cache, self.build = (base / name for name in ("source", "work", "cache", "build"))
        for path in (self.source, self.root, self.build):
            path.mkdir()
        for key, value in (("SOURCE", self.source), ("ROOT", self.root), ("CACHE", self.cache), ("BUILD_CACHE", self.build)):
            patcher = mock.patch.object(RUNTIME, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def seal(self):
        (self.build / "dependency.jar").write_bytes(b"cached-dependency")
        (self.build / "metadata.bin").write_bytes(b"cached-metadata")
        (self.build / "cache.lock").write_text("do not copy")
        (self.build / "gc.properties").write_text("do not copy")
        with mock.patch.object(RUNTIME.os, "geteuid", return_value=0):
            RUNTIME.seal()

    @contextlib.contextmanager
    def root_owned_fixture(self):
        # Local fixtures cannot chown to root in this sandbox. Owner rejection
        # is tested separately; retain all structure/hash checks here.
        original = RUNTIME.files
        with mock.patch.object(RUNTIME, "files", side_effect=lambda path, **_kwargs: original(path)):
            yield

    def test_cache_is_sealed_without_locks_and_is_private_and_fresh_for_the_candidate(self):
        self.seal()
        self.assertFalse((self.cache / "modules-2/cache.lock").exists())
        self.assertFalse((self.cache / "modules-2/gc.properties").exists())
        for name in ("android/.gradle/stale", "android/app/build/stale", "android/local.properties"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("must not be adopted")
        (self.source / "android/Candidate.kt").write_text("candidate")
        with self.root_owned_fixture():
            RUNTIME.prepare()
        copy = self.root / "gradle-home/caches/modules-2/dependency.jar"
        self.assertEqual(b"cached-dependency", copy.read_bytes())
        copy.write_bytes(b"candidate mutation")
        self.assertEqual(b"cached-dependency", (self.cache / "modules-2/dependency.jar").read_bytes())
        self.assertFalse((self.root / "gradle-home/init.d").exists())
        for name in ("android/.gradle", "android/app/build", "android/local.properties"):
            self.assertFalse((self.root / "repo" / name).exists())
        self.assertEqual("candidate", (self.root / "repo/android/Candidate.kt").read_text())
        with self.assertRaises(ValueError):
            RUNTIME.prepare()

    def test_corrupt_or_surplus_cache_files_are_rejected_before_candidate_copy(self):
        self.seal()
        (self.cache / "modules-2/dependency.jar").write_bytes(b"unexpected")
        with self.root_owned_fixture(), self.assertRaises(ValueError):
            RUNTIME.prepare()
        self.assertFalse((self.root / "repo").exists())
        (self.cache / "modules-2/dependency.jar").write_bytes(b"cached-dependency")
        (self.cache / "extra").write_bytes(b"unexpected")
        with self.root_owned_fixture(), self.assertRaises(ValueError):
            RUNTIME.prepare()

    def test_symlinked_hardlinked_and_wrong_owner_cache_objects_are_rejected(self):
        target = self.build / "file"
        target.write_text("cached")
        link = self.build / "link"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            RUNTIME.files(self.build)
        link.unlink()
        os.link(target, link)
        with self.assertRaises(ValueError):
            RUNTIME.files(self.build)
        link.unlink()
        if os.geteuid() != 0:
            with self.assertRaises(ValueError):
                RUNTIME.files(self.build, root_owned=True)

    def test_only_dependency_module_files_with_safe_names_can_be_imported(self):
        self.seal()
        document = json.loads((self.cache / "cache-manifest-v1.json").read_text())
        document["files"]["../arbitrary"] = "a" * 64
        (self.cache / "cache-manifest-v1.json").write_text(json.dumps(document))
        with self.root_owned_fixture(), self.assertRaises(ValueError):
            RUNTIME.verified_cache()
        for name in ("../file", "/file", "modules-2/../file", "modules-2//file", "modules-2\\file"):
            self.assertFalse(RUNTIME.safe_name(name))

    def test_seed_uses_only_fixed_synthetic_probes_and_distinct_packages(self):
        with mock.patch.object(RUNTIME.os, "geteuid", return_value=0):
            RUNTIME.seed()
        probes = list(self.source.rglob("DependencyCacheProbe.kt"))
        self.assertEqual(5, len(probes))
        self.assertEqual(5, len({path.read_text().splitlines()[0] for path in probes}))
        self.assertEqual(4, len(list(self.source.rglob("DependencyCacheProbeTest.kt"))))

    def test_root_preparation_and_caller_arguments_are_rejected(self):
        with mock.patch.object(RUNTIME.os, "geteuid", return_value=0), self.assertRaises(ValueError):
            RUNTIME.prepare()
        with mock.patch.object(sys, "argv", ["runtime", "--prepare", "/arbitrary"]):
            self.assertEqual(64, RUNTIME.main())


if __name__ == "__main__":
    unittest.main()
