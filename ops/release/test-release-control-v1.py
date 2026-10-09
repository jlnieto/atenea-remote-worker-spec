#!/usr/bin/env python3
"""Focal tests: no live services, containers, identities or publication."""
import contextlib
import copy
import importlib.util
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location("release_control", Path(__file__).with_name("release-control-v1.py"))
release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release
spec.loader.exec_module(release)

OLD = "1" * 40
NEW = "2" * 40


class InlineThread:
    def __init__(self, target, args=(), **kwargs): self.target, self.args = target, args
    def start(self): self.target(*self.args)


class Artifacts:
    def prepare(self, target, commit, destination):
        (destination / "image.tar").write_bytes(b"immutable reviewed image")
        return {"payloadSha256": release.file_digest(destination / "image.tar"),
                "versionCode": None, "versionName": None}


class Target:
    def __init__(self):
        self.current = {"sourceCommit": OLD, "configuration": "unchanged"}
        self.current["imageId"] = "sha256:" + "a" * 64
        self.applies = self.rollbacks = self.stages = 0
        self.health = True
        self.locked = False

    @contextlib.contextmanager
    def guard(self):
        self.locked = True
        try: yield
        finally: self.locked = False

    def inspect(self): return copy.deepcopy(self.current)
    def observe_current(self):
        return {"sourceCommit": self.current["sourceCommit"], "imageId": self.current["imageId"],
                "healthy": self.health, "instanceId": "private-container-id"}
    def stage(self, plan, path): self.stages += 1
    def apply(self, plan, path):
        assert self.locked
        self.applies += 1
        self.current["sourceCommit"] = plan["sourceCommit"]
        self.current["imageId"] = "sha256:" + "b" * 64
    def verify(self, plan, path):
        assert self.locked
        if not self.health or self.current["sourceCommit"] != plan["sourceCommit"]:
            raise release.Rejected("HEALTH_FAILED")
        return self.inspect()
    def rollback(self, plan, path):
        assert self.locked, "Rollback must remain within the admission guard"
        self.rollbacks += 1
        self.current = copy.deepcopy(plan["predecessor"])
        return self.inspect()
    def commit(self, receipt): pass


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release-unit-")
        self.root = Path(self.temp.name)
        self.target = Target()
        self.controller = release.Controller(self.root, Artifacts(), {"APP_PROD": self.target})
        # Test fixtures are unprivileged and beneath /tmp, unlike installation.
        self.trust = patch.object(release, "trusted", side_effect=lambda path, mode=None: path)
        self.thread = patch.object(release.threading, "Thread", InlineThread)
        self.trust.start(); self.thread.start()
        directory = patch.object(release, "trusted_directory")
        directory.start(); self.addCleanup(directory.stop)
        self.addCleanup(self.trust.stop); self.addCleanup(self.thread.stop); self.addCleanup(self.temp.cleanup)
        self.id = str(uuid.uuid4())
        self.operation_id = str(uuid.uuid4())

    def plan(self):
        self.controller.dispatch({"operation": "PLAN", "planId": self.id, "target": "APP_PROD", "sourceCommit": NEW})
        return self.controller.dispatch({"operation": "INSPECT", "planId": self.id})

    def execute(self, plan):
        return self.controller.dispatch({"operation": "EXECUTE", "planId": self.id,
            "planSha256": plan["planSha256"], "operationId": self.operation_id})

    def test_plan_has_no_effect_and_public_projection_has_no_authority(self):
        plan = self.plan()
        self.assertEqual("READY", plan["state"])
        self.assertEqual(0, self.target.applies)
        self.assertEqual(OLD, self.target.current["sourceCommit"])
        self.assertNotIn("predecessor", plan)
        self.assertNotIn("artifact", plan)
        self.assertNotIn("configuration", json.dumps(plan))
        self.assertEqual(0o600, stat.S_IMODE((self.controller.path(self.id) / "operation.json").stat().st_mode))

    def test_plan_and_execution_idempotent(self):
        plan = self.plan()
        self.assertEqual(plan, self.plan())
        self.execute(plan); self.execute(plan)
        self.assertEqual(1, self.target.stages)
        self.assertEqual(1, self.target.applies)
        self.assertEqual("SUCCEEDED", self.controller.read(self.id)["state"])

    def test_foreign_fields_and_target_rejected(self):
        for field in ("command", "path", "host", "token", "version", "symlink"):
            with self.subTest(field=field), self.assertRaises(release.Rejected):
                self.controller.dispatch({"operation": "PLAN", "planId": self.id,
                    "target": "APP_PROD", "sourceCommit": NEW, field: "arbitrary"})
        with self.assertRaises(release.Rejected):
            self.controller.dispatch({"operation": "PLAN", "planId": self.id,
                    "target": "FOREIGN", "sourceCommit": NEW})

    def test_plan_identity_cannot_choose_another_sha(self):
        self.plan()
        with self.assertRaises(release.Rejected):
            self.controller.dispatch({"operation": "PLAN", "planId": self.id,
                    "target": "APP_PROD", "sourceCommit": "3" * 40})

    def test_wrong_hash_and_operation_id_rejected(self):
        plan = self.plan()
        with self.assertRaises(release.Rejected): self.execute({**plan, "planSha256": "0" * 64})
        self.execute(plan)
        self.operation_id = str(uuid.uuid4())
        with self.assertRaises(release.Rejected): self.execute(plan)

    def test_state_drift_blocks_before_apply(self):
        plan = self.plan()
        self.target.current["configuration"] = "foreign"
        receipt = self.execute(plan)
        self.assertEqual("BLOCKED", receipt["state"])
        self.assertEqual("TARGET_STATE_MOVED", receipt["errorCode"])
        self.assertEqual(self.operation_id, receipt["operationId"])
        self.assertEqual(receipt, self.execute(plan))
        self.assertEqual(0, self.target.applies)

    def test_corrupt_payload_blocks_without_apply_or_rollback(self):
        plan = self.plan()
        (self.controller.path(self.id) / "image.tar").write_bytes(b"foreign")
        self.execute(plan)
        self.assertEqual("BLOCKED", self.controller.read(self.id)["state"])
        self.assertEqual((0, 0), (self.target.applies, self.target.rollbacks))

    def test_health_failure_automatically_rolls_back_under_guard(self):
        plan = self.plan(); self.target.health = False
        self.execute(plan)
        final = self.controller.read(self.id)
        self.assertEqual("ROLLED_BACK", final["state"])
        self.assertEqual("HEALTH_FAILED", final["errorCode"])
        self.assertEqual(OLD, self.target.current["sourceCommit"])
        self.assertTrue((self.controller.path(self.id) / "rollback-receipt.json").is_file())

    def test_rollback_failure_is_terminal_and_not_retried(self):
        plan = self.plan(); self.target.health = False
        self.target.rollback = Mock(side_effect=release.Rejected("ROLLBACK_FAILURE"))
        self.execute(plan); self.controller.recover()
        self.assertEqual("ROLLBACK_FAILED", self.controller.read(self.id)["state"])
        self.assertEqual(1, self.target.rollback.call_count)
        with self.assertRaises(release.Rejected):
            self.controller.dispatch({"operation":"PLAN", "planId":str(uuid.uuid4()),
                "target":"APP_PROD", "sourceCommit":"3"*40})

    def test_restart_after_apply_observes_without_applying_twice(self):
        self.plan()
        record = self.controller.read(self.id)
        record.update(state="APPLYING", operationId=self.operation_id)
        release.save(self.controller.path(self.id) / "operation.json", record)
        self.target.current["sourceCommit"] = NEW
        restarted = release.Controller(self.root, Artifacts(), {"APP_PROD": self.target})
        restarted.recover()
        self.assertEqual("SUCCEEDED", restarted.read(self.id)["state"])
        self.assertEqual(0, self.target.applies)

    def test_restart_before_any_apply_restores_not_reissues_an_ambiguous_apply(self):
        self.plan()
        record = self.controller.read(self.id)
        record.update(state="APPLYING", operationId=self.operation_id)
        release.save(self.controller.path(self.id) / "operation.json", record)
        self.controller.recover()
        self.assertEqual("ROLLED_BACK", self.controller.read(self.id)["state"])
        self.assertEqual(0, self.target.applies)

    def test_restart_reconciles_durable_acceptance(self):
        self.plan()
        record = self.controller.read(self.id)
        record.update(state="ACCEPTED", operationId=self.operation_id)
        release.save(self.controller.path(self.id) / "operation.json", record)
        self.controller.recover(); self.controller.recover()
        self.assertEqual(1, self.target.applies)

    def test_stage_failure_persists_blocker_and_replay_does_not_restage(self):
        self.target.stage = Mock(side_effect=release.Rejected("STAGE_REJECTED"))
        plan = self.plan()
        self.assertEqual("BLOCKED", plan["state"])
        self.assertEqual("STAGE_REJECTED", plan["errorCode"])
        self.plan()
        self.assertEqual(1, self.target.stage.call_count)

    def test_waiting_for_main_artifact_retains_one_plan_and_never_deploys(self):
        original=self.controller.artifacts.prepare
        calls=[]
        def pending(target,commit,path):
            calls.append((target,commit,path))
            if len(calls)==1: raise release.Rejected("RELEASE_BUILD_PENDING")
            return original(target,commit,path)
        self.controller.artifacts.prepare=pending
        with patch.object(release.time,"sleep") as sleep:
            plan=self.plan()
        self.assertEqual("READY",plan["state"])
        self.assertIsNone(plan["errorCode"])
        self.assertEqual(2,len(calls)); self.assertEqual(calls[0],calls[1])
        sleep.assert_called_once_with(10)
        self.assertEqual(0,self.target.applies)
        self.assertEqual(1,len(list((self.root/"plans").glob("*/operation.json"))))

    def test_expired_plan_cannot_be_confirmed(self):
        plan = self.plan()
        with patch.object(release.time, "time", return_value=plan["expiresAt"] + 1):
            receipt = self.execute(plan)
        self.assertEqual("BLOCKED", receipt["state"])
        self.assertEqual("PLAN_EXPIRED", receipt["errorCode"])
        self.assertEqual(self.operation_id, receipt["operationId"])
        self.assertEqual((0,0),(self.target.applies,self.target.rollbacks))

    def completed_observation(self):
        self.execute(self.plan())
        return self.controller.dispatch({"operation": "OBSERVE_APP"})

    def test_observation_is_read_only_preserves_receipts_and_has_no_authority(self):
        self.completed_observation()
        snapshot = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.root.rglob("*") if p.is_file()}
        for _ in range(2):
            observed = self.controller.dispatch({"operation": "OBSERVE_APP"})
            self.assertEqual(NEW, observed["sourceCommit"])
            self.assertEqual(self.id, observed["planId"])
            self.assertEqual(self.operation_id, observed["operationId"])
            self.assertTrue(observed["healthy"])
            self.assertEqual(11, len(observed))
            self.assertNotIn("private-container-id", json.dumps(observed))
            self.assertNotIn("configuration", json.dumps(observed))
        self.assertEqual(snapshot, {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                         for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual((1, 0, 1), (self.target.applies, self.target.rollbacks, self.target.stages))

    def test_observation_contracts_are_closed_draft_2020_12(self):
        from jsonschema import Draft202012Validator
        root = Path(__file__).parents[2] / "runtime-contract"
        request = json.loads((root / "release-control-v1.request.schema.json").read_bytes())
        response = json.loads((root / "release-control-v1.observation.schema.json").read_bytes())
        for schema in (request, response): Draft202012Validator.check_schema(schema)
        Draft202012Validator(request).validate({"operation": "OBSERVE_APP"})
        Draft202012Validator(response).validate(self.completed_observation())
        for field in ("target", "path", "command", "token", "sourceCommit", "planId"):
            value = {"operation": "OBSERVE_APP", field: "foreign"}
            with self.subTest(field=field):
                self.assertFalse(Draft202012Validator(request).is_valid(value))
                with self.assertRaises(release.Rejected): self.controller.dispatch(value)
        with self.assertRaises(release.Rejected):
            release.Controller(self.root, Artifacts(), {}).dispatch({"operation": "OBSERVE_APP"})

    def test_unattributed_runtime_and_image_or_plan_hash_mismatch_fail_closed(self):
        self.completed_observation()
        original = self.controller.read(self.id)
        for key, value in (("effectiveSourceCommit", OLD), ("planSha256", "0" * 64)):
            with self.subTest(key=key):
                release.save(self.controller.path(self.id) / "operation.json", {**original, key: value})
                with self.assertRaises(release.Rejected): self.controller.dispatch({"operation": "OBSERVE_APP"})
        release.save(self.controller.path(self.id) / "operation.json", original)
        self.target.current["imageId"] = "sha256:" + "c" * 64
        with self.assertRaises(release.Rejected): self.controller.dispatch({"operation": "OBSERVE_APP"})
        self.target.current["sourceCommit"] = OLD
        with self.assertRaises(release.Rejected): self.controller.dispatch({"operation": "OBSERVE_APP"})

    def test_active_release_runtime_drift_and_unhealthy_runtime_are_not_success(self):
        self.completed_observation()
        original = self.controller.read(self.id)
        for state in ("ACCEPTED", "APPLYING", "ROLLING_BACK", "ROLLBACK_FAILED"):
            release.save(self.controller.path(self.id) / "operation.json", {**original, "state": state})
            with self.assertRaises(release.Rejected): self.controller.dispatch({"operation": "OBSERVE_APP"})
        release.save(self.controller.path(self.id) / "operation.json", original)
        self.target.health = False
        self.assertFalse(self.controller.dispatch({"operation": "OBSERVE_APP"})["healthy"])
        before = self.target.observe_current()
        self.target.observe_current = Mock(side_effect=[before, {**before, "instanceId": "replacement"}])
        with self.assertRaises(release.Rejected): self.controller.dispatch({"operation": "OBSERVE_APP"})


class AuthorityTest(unittest.TestCase):
    def test_installer_preflight_refuses_active_durable_release_before_restart(self):
        with tempfile.TemporaryDirectory(prefix="release-install-preflight-") as name:
            root=Path(name); path=root/"plans"/str(uuid.uuid4())/"operation.json"
            release.save(path,{"state":"APPLYING","operationId":str(uuid.uuid4())})
            with patch.object(release,"configuration",return_value={"mode":"AX42"}),\
                 patch.object(release,"ROOT",root),\
                 patch.object(release,"trusted_directory"),\
                 patch.object(release,"trusted",side_effect=lambda p,mode=None:p),\
                 patch.object(sys,"argv",["release-control-v1.py","--preflight-install"]):
                with self.assertRaises(release.Rejected) as error: release.main()
                self.assertEqual("RELEASE_IN_PROGRESS",error.exception.code)

    def test_all_release_schemas_are_closed_draft_2020_12(self):
        import jsonschema
        root = Path(__file__).parents[2] / "runtime-contract"
        for path in root.glob("release-control-v1.*.schema.json"):
            schema = json.loads(path.read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
        schema = json.loads((root / "release-control-v1.request.schema.json").read_text())
        validator = jsonschema.Draft202012Validator(schema)
        valid = {"operation":"PLAN", "target":"APP_PROD", "planId":str(uuid.uuid4()), "sourceCommit":NEW}
        validator.validate(valid)
        for field in ("path", "command", "host", "version", "token"):
            self.assertTrue(list(validator.iter_errors({**valid, field:"foreign"})))

    def test_parent_owned_by_another_user_is_rejected(self):
        fake = Mock(spec=Path)
        fake.parents = [Mock()]
        fake.parents[0].lstat.return_value = Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=1000)
        with self.assertRaises(release.Rejected): release.trusted(fake)

    def test_symlink_is_not_trusted(self):
        fake = Mock(spec=Path); fake.parents = []
        fake.lstat.return_value = Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=0, st_nlink=1)
        with self.assertRaises(release.Rejected): release.trusted(fake)

    def test_redirects_do_not_forward_a_bearer_token(self):
        self.assertIsNone(release.NoRedirect().redirect_request(None, None, 302, None, None, "http://foreign"))

    def test_only_fixed_repo_main_and_workflow_accepted(self):
        artifacts = release.GitHubArtifacts()
        artifacts.api = Mock(return_value={"object": {"sha": OLD}})
        with self.assertRaises(release.Rejected) as caught:
            artifacts.prepare("APP_PROD", NEW, Path("/unused"))
        self.assertEqual("CANONICAL_MAIN_MOVED", caught.exception.code)


if __name__ == "__main__": unittest.main()
