#!/usr/bin/env python3
"""Opt-in operator smoke: real trusted build + synthetic offline test, no ticket run."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("toolchain_network_runner", Path(__file__).with_name("atenea-validation-v1.py"))
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def smoke_inner():
    if os.geteuid() != 0:
        return 64
    # Hold the same exclusive operator gate as a Platform rollout. Never
    # compete with a ticket run or invent a WorkSession/admission record.
    spec = importlib.util.spec_from_file_location("toolchain_release_guard", "/usr/local/libexec/atenea/release-control-v1.py")
    release = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = release
    spec.loader.exec_module(release)
    with release.PlatformTarget().guard():
        state = json.loads(Path("/srv/atenea/worker/agent-runs-v1/executions.json").read_text())
        if (any(v["status"] not in {"SUCCEEDED", "FAILED", "CANCELLED"}
                for v in state["executions"].values()) or
                any(v["state"] not in {"SUCCEEDED", "CANDIDATE_FAILED", "INFRASTRUCTURE_FAILED",
                    "POLICY_FAILED", "VALIDATION_FAILED", "OWNERSHIP_FAILED", "CANCELLED"}
                    for v in state.get("validations", {}).values())):
            return 64
        slot_user, uid, _, socket = RUNNER.slot_authority("slot1")
        operation = str(uuid.uuid4())
        root = RUNNER.prepare_validation_runtime(operation, uid)
        try:
            source = root / "source"
            source.mkdir(mode=0o700)
            # Fixed canonical authority, never a client's path or candidate recipe.
            pom = subprocess.check_output([
                "/usr/bin/git", "--git-dir=/srv/atenea/repositories/atenea.git",
                "show", "847a2f240e3d64af2cf3f166ff3c70ad7cc8497f:pom.xml",
            ])
            (source / "pom.xml").write_bytes(pom)
            if RUNNER.sha256_file(source / "pom.xml") != RUNNER.BACKEND_POM_SHA256:
                return 64
            test = source / "src/test/java/com/atenea/ToolchainNetworkSmokeTest.java"
            test.parent.mkdir(parents=True)
            test.write_text('''package com.atenea;
import java.sql.DriverManager;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ToolchainNetworkSmokeTest {
 @Test void offlinePrivateDatabaseAndNoHostAuthority() throws Exception {
  try (var connection = DriverManager.getConnection(
      "jdbc:postgresql://127.0.0.1:5432/atenea_test", "atenea", "atenea");
       var statement = connection.createStatement();
       var result = statement.executeQuery("SELECT 1")) {
   assertTrue(result.next()); assertEquals(1, result.getInt(1));
  }
  // network=none must expose no external IPv4 route, only private loopback.
  assertEquals(1, Files.readAllLines(Path.of("/proc/net/route")).size());
  assertFalse(Files.exists(Path.of("/srv/atenea")));
  assertFalse(Files.exists(Path.of("/etc/atenea-worker")));
  assertFalse(Files.exists(Path.of("/run/docker.sock")));
  System.out.println("OFFLINE_SYNTHETIC_TEST_PASS");
 }
}
''')
            RUNNER.make_slot_readable(source, uid)
            prefix = RUNNER.docker_slot_prefix(slot_user, uid, socket, root / "docker-client")
            with (root / "output").open("x") as output:
                result = RUNNER.run_backend(prefix, operation, source, RUNNER.DEFINITIONS["BACKEND_TEST"], output)
            observed_output = (root / "output").read_text()
            print(observed_output[-16000:], flush=True)
            print("TOOLCHAIN_SMOKE", json.dumps({"phase": result.phase, "errorCode": result.error_code,
                   "failureClass": result.failure_class, "exitCode": result.exit_code}), flush=True)
            # A zero Maven exit without executing the fixture is not acceptance.
            return result.exit_code or (0 if "OFFLINE_SYNTHETIC_TEST_PASS" in observed_output else 70)
        finally:
            shutil.rmtree(root)


class ToolchainNetworkSmokeTest(unittest.TestCase):
    def test_candidate_is_still_offline_and_preparation_inputs_are_closed(self):
        text = Path(__file__).with_name("atenea-validation-v1.py").read_text()
        self.assertIn('"--network", "none", "--user", "1000:0"', text)
        self.assertIn('"--offline", "-B", "-q"', text)
        self.assertIn('sha256_file(pom) != BACKEND_POM_SHA256', text)
        self.assertIn('sha256_file(path) != digest', text)

    @unittest.skipUnless(os.geteuid() == 0 and os.environ.get("ATENEA_TOOLCHAIN_NETWORK_SMOKE") == "1",
                         "requires explicit operator root opt-in; builds only reviewed toolchain/synthetic test")
    def test_real_build_and_synthetic_offline_test_in_exact_coordinator_sandbox(self):
        identity = RUNNER.durable_identity([
            "BACKEND_TEST", str(uuid.uuid4()), "a" * 64, str(uuid.uuid4()),
        ])
        command = RUNNER.durable_unit_command(identity)
        command.remove("--no-block")
        command[1:1] = ["--wait", "--pipe"]
        unit = command.index("--unit") + 1
        command[unit] = command[unit].replace("-broker-", "-toolchain-smoke-")
        command[command.index("--") + 1:] = ["/usr/bin/python3", str(Path(__file__).resolve()), "--smoke-inner"]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, timeout=1020, check=False)
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke-inner"]:
        raise SystemExit(smoke_inner())
    unittest.main()
