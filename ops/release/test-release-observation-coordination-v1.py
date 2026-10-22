#!/usr/bin/env python3
"""Real controller receipts and concurrent readers; no services or privileged effects."""
import concurrent.futures
import copy
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("coordinated_release", Path(__file__).with_name("release-control-v1.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class ObservationCoordinationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = "1" * 40
        self.app = Mock()
        self.android = Mock()
        self.platform = Mock()
        self.c = m.Controller(self.root, Mock(), {"APP_PROD": self.app, "ANDROID_STABLE": self.android,
                                                "AX42_PLATFORM": self.platform})
        for name in ("trusted", "trusted_directory"):
            p = patch.object(m, name, side_effect=lambda path, mode=None: path)
            p.start()
            self.addCleanup(p.stop)
        self.android_current = {
            "sourceCommit": self.source, "versionCode": 168, "certificateSha256": "b" * 64,
            "manifest": {"versionCode": 168, "versionName": "0.5.135", "sha256": "a" * 64,
                         "sourceCommit": self.source, "apkUrl": "https://private.invalid/secret-not-projected"}}
        self.app_current = {"sourceCommit": self.source, "imageId": "sha256:" + "c" * 64, "healthy": True}
        self.android.inspect.side_effect = lambda: copy.deepcopy(self.android_current)
        self.app.observe_current.side_effect = lambda: copy.deepcopy(self.app_current)
        self.receipt("ANDROID_STABLE", self.android_current, {"versionCode": 168}, "a" * 64)
        self.receipt("APP_PROD", self.app_current, {}, None)
        platform_plan = str(uuid.uuid4())
        self.platform_current = {"sourceCommit": self.source, "artifactPlanId": platform_plan,
                                 "installedFiles": {name: "d" * 64 for name in
                                                    ("agent-run-worker-v1.py", "atenea-validation-v1.py", "project-codex-runner-v1.py")}}
        self.platform.observe_current.side_effect = lambda: copy.deepcopy(self.platform_current)
        self.receipt("AX42_PLATFORM", self.platform_current, {}, None, platform_plan)

    def receipt(self, target, current, artifact, result, plan=None):
        plan = plan or str(uuid.uuid4())
        record = {"protocol": m.PROTOCOL, "planId": plan, "target": target, "sourceCommit": self.source,
                  "state": "SUCCEEDED", "errorCode": None, "operationId": str(uuid.uuid4()), "finishedAt": 1,
                  "effectiveSourceCommit": self.source, "resultSha256": result, "expiresAt": 1,
                  "artifact": artifact, "predecessor": {}}
        record["planSha256"] = m.digest({key: record[key] for key in
            ("protocol", "planId", "target", "sourceCommit", "artifact", "predecessor", "expiresAt")})
        m.save(self.c.path(plan) / "operation.json", record)
        m.save(self.c.path(plan) / "receipt.json", current)

    def files(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.rglob("*.json")}

    def joined_readers(self, load, operation, followers=3, owner=None, method="_observe_android"):
        """Latches prove followers joined the *same flight*, without timing sleeps."""
        started, finish, joined = threading.Event(), threading.Event(), threading.Event()
        future_type = concurrent.futures.Future
        count, lock = 0, threading.Lock()

        class CountedFuture(future_type):
            def result(self, timeout=None):
                nonlocal count
                with lock:
                    count += 1
                    if count == followers:
                        joined.set()
                return super().result(timeout)

        def held(*args, **kwargs):
            started.set()
            if not finish.wait(3):
                raise AssertionError("test reader was not released")
            return load()

        owner = owner or self.c
        dispatch = owner.request if isinstance(owner, m.Peer) else owner.dispatch
        outcomes = []
        def read():
            try:
                outcomes.append(dispatch({"operation": operation}))
            except BaseException as error:
                outcomes.append(error)
        threads = []
        with patch.object(concurrent.futures, "Future", CountedFuture), patch.object(
                owner, method, side_effect=held):
            try:
                leader = threading.Thread(target=read)
                threads.append(leader)
                leader.start()
                self.assertTrue(started.wait(3))
                for _ in range(followers):
                    thread = threading.Thread(target=read)
                    threads.append(thread)
                    thread.start()
                self.assertTrue(joined.wait(3))
            finally:
                finish.set()
                for thread in threads:
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
        return outcomes

    def test_same_target_shares_one_fresh_verification_without_writes_or_effects(self):
        before = self.files()
        original = self.c._observe_android
        values = self.joined_readers(original, "OBSERVE_ANDROID")
        self.assertEqual(4, len(values))
        for value in values:
            self.assertIsInstance(value, dict)
            self.assertEqual("OBSERVED", value["state"])
        self.assertEqual(2, self.android.inspect.call_count)  # before/after once, not per reader
        self.assertEqual(before, self.files())
        values[0]["versionCode"] = 999
        self.assertEqual(168, values[1]["versionCode"])
        self.c.dispatch({"operation": "OBSERVE_ANDROID"})
        self.assertEqual(4, self.android.inspect.call_count)  # no completed cache
        self.assertEqual({"inspect"}, {call[0] for call in self.android.method_calls})
        self.assertNotIn("secret-not-projected", json.dumps(values))

    def test_different_local_readers_wait_instead_of_being_rejected_as_busy(self):
        entered, release, queued = threading.Event(), threading.Event(), threading.Event()
        serial = self.c.observations._serial
        class TrackedGate:
            def acquire(self, timeout):
                if threading.current_thread().name == "app-reader":
                    queued.set()
                return serial.acquire(timeout=timeout)
            def release(self):
                serial.release()
        self.c.observations._serial = TrackedGate()
        def inspect():
            entered.set()
            self.assertTrue(release.wait(3))
            return copy.deepcopy(self.android_current)
        self.android.inspect.side_effect = inspect
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            first = pool.submit(self.c.observe_android)
            self.assertTrue(entered.wait(3))
            outcomes = []
            second = threading.Thread(name="app-reader", target=lambda: outcomes.append(self.c.observe_app()))
            second.start()
            try:
                self.assertTrue(queued.wait(3))
                self.app.observe_current.assert_not_called()
                self.assertFalse(self.c.execution_lock.acquire(blocking=False))
            finally:
                release.set()
                second.join(3)
            self.assertFalse(second.is_alive())
            self.assertEqual("OBSERVED", first.result(3)["state"])
            self.assertEqual("OBSERVED", outcomes[0]["state"])
        self.assertEqual(2, self.app.observe_current.call_count)
        self.assertEqual(2, self.android.inspect.call_count)

    def test_an_effect_still_excludes_every_reader_and_does_not_populate_a_cache(self):
        with self.c.execution_lock:
            for operation, code in (("OBSERVE_APP", "APP_OBSERVATION_BUSY"),
                                    ("OBSERVE_ANDROID", "ANDROID_OBSERVATION_BUSY"),
                                    ("OBSERVE_PLATFORM", "PLATFORM_OBSERVATION_BUSY")):
                with self.subTest(operation=operation), self.assertRaisesRegex(m.Rejected, code):
                    self.c.dispatch({"operation": operation})
        self.assertFalse(self.c.observations._flights)
        self.app.observe_current.assert_not_called()
        self.android.inspect.assert_not_called()
        self.platform.observe_current.assert_not_called()
        self.assertEqual("OBSERVED", self.c.observe_platform()["state"])

    def test_failed_shared_verification_is_not_cached_and_next_read_reverifies_receipts(self):
        self.android_current["certificateSha256"] = "f" * 64
        values = self.joined_readers(self.c._observe_android, "OBSERVE_ANDROID")
        self.assertEqual(4, len(values))
        for error in values:
            self.assertIsInstance(error, m.Rejected)
            self.assertEqual("ANDROID_OBSERVATION_EVIDENCE_MISMATCH", str(error))
        self.assertFalse(self.c.observations._flights)
        self.android_current["certificateSha256"] = "b" * 64
        self.assertEqual("OBSERVED", self.c.observe_android()["state"])

    def test_follower_timeout_does_not_cancel_or_replace_the_running_read(self):
        reads = m.ObservationReads()
        entered, release = threading.Event(), threading.Event()
        def load():
            entered.set()
            self.assertTrue(release.wait(3))
            return {"state": "OBSERVED"}
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            leader = pool.submit(reads.read, "ANDROID_STABLE", load)
            self.assertTrue(entered.wait(3))
            try:
                with patch.object(reads, "WAIT_SECONDS", 0.02):
                    forbidden = Mock(side_effect=AssertionError("must join existing reader"))
                    with self.assertRaisesRegex(m.Rejected, "ANDROID_OBSERVATION_BUSY"):
                        reads.read("ANDROID_STABLE", forbidden)
                    forbidden.assert_not_called()
                self.assertEqual(1, len(reads._flights))
            finally:
                release.set()
            self.assertEqual({"state": "OBSERVED"}, leader.result(3))
        self.assertFalse(reads._flights)
        with self.assertRaisesRegex(m.Rejected, "TARGET_REJECTED"):
            reads.read("/arbitrary/path", load)

    def test_peer_platform_reads_are_grouped_but_publication_requests_are_not(self):
        peer = m.Peer()
        with patch.object(peer, "_request", return_value={"sourceCommit": self.source}) as request:
            values = self.joined_readers(lambda: request({"operation": "OBSERVE_PLATFORM"}), "OBSERVE_PLATFORM",
                                         owner=peer, method="_request")
            self.assertEqual([{"sourceCommit": self.source}] * 4, values)
            self.assertEqual(1, request.call_count)
        entered, release = threading.Event(), threading.Event()
        def remote(request):
            entered.set()
            self.assertTrue(release.wait(3))
            return {"sourceCommit": self.source}
        with patch.object(peer, "_request", side_effect=remote) as request:
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                leader = pool.submit(peer.request, {"operation": "OBSERVE_PLATFORM"})
                self.assertTrue(entered.wait(3))
                try:
                    for field in ("path", "command", "target", "sourceCommit"):
                        with self.assertRaises(m.Rejected):
                            peer.request({"operation": "OBSERVE_PLATFORM", field: "foreign"})
                    # Remote wait is independent of the controller's local read gate.
                    self.assertEqual("OBSERVED", self.c.observe_app()["state"])
                finally:
                    release.set()
                self.assertEqual({"sourceCommit": self.source}, leader.result(3))
            self.assertEqual(1, request.call_count)
        with patch.object(peer, "_request", return_value={}) as request:
            for operation in ("PLAN", "EXECUTE"):
                peer.request({"operation": operation})
                peer.request({"operation": operation})
            self.assertEqual(4, request.call_count)

    def test_other_target_wait_is_bounded_and_does_not_displace_an_existing_reader(self):
        reads = m.ObservationReads()
        entered, release = threading.Event(), threading.Event()
        def load():
            entered.set()
            self.assertTrue(release.wait(3))
            return {"state": "OBSERVED"}
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            leader = pool.submit(reads.read, "ANDROID_STABLE", load)
            self.assertTrue(entered.wait(3))
            forbidden = Mock(side_effect=AssertionError("timed-out reader must not inspect"))
            try:
                with patch.object(reads, "WAIT_SECONDS", 0.02):
                    with self.assertRaisesRegex(m.Rejected, "APP_OBSERVATION_BUSY"):
                        reads.read("APP_PROD", forbidden)
                forbidden.assert_not_called()
                self.assertEqual({"ANDROID_STABLE"}, set(reads._flights))
            finally:
                release.set()
            self.assertEqual({"state": "OBSERVED"}, leader.result(3))
        self.assertEqual({"fresh": True}, reads.read("APP_PROD", lambda: {"fresh": True}))


if __name__ == "__main__":
    unittest.main()
