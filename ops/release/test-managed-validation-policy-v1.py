#!/usr/bin/env python3
"""No production calls: installed-policy observation and publisher binding."""
import importlib.util
import io
import json
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
ROOT=Path(__file__).resolve().parents[2]
r=load("policy_release",ROOT/"ops/release/release-control-v1.py")
w=load("policy_worker",ROOT/"ops/worker/agent-run-worker-v1.py")

class PolicyTest(unittest.TestCase):
    def test_read_only_installed_root_policy_observation_and_unexpected_bytes_rejection(self):
        path=Mock();path.lstat.return_value=SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0,st_gid=0,st_nlink=1)
        path.read_bytes.return_value=(ROOT/"ops/worker/atenea-android-inputs-v2.json").read_bytes()
        worker=SimpleNamespace(worker_id="ax42-01")
        with patch.object(w,"VALIDATION_POLICY_FILE",path):
            value=w.WorkerState.validation_policy(worker)
            self.assertEqual(w.VALIDATION_POLICY_SHA256,value["androidInputsSha256"])
            self.assertEqual({"protocolVersion","workerId","androidInputsSha256"},set(value))
            path.read_bytes.return_value+=b"\n"
            with self.assertRaises(w.ProtocolError):w.WorkerState.validation_policy(worker)
            path.read_bytes.return_value=(ROOT/"ops/worker/atenea-android-inputs-v2.json").read_bytes()
            for key,value in (("st_uid",1000),("st_gid",1000),("st_nlink",2),("st_mode",stat.S_IFLNK|0o644)):
                before=getattr(path.lstat.return_value,key);setattr(path.lstat.return_value,key,value)
                with self.assertRaises(w.ProtocolError):w.WorkerState.validation_policy(worker)
                setattr(path.lstat.return_value,key,before)

    def test_publisher_compares_exact_authenticated_observation_without_effects(self):
        digest=w.VALIDATION_POLICY_SHA256
        value={"protocolVersion":"managed-validation-policy/v1","workerId":"ax42-01","androidInputsSha256":digest}
        token=Mock();token.read_text.return_value="synthetic-test-token"
        opener=Mock();response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener.open.return_value=response
        with patch.object(r,"trusted",return_value=token),patch.object(r.urllib.request,"build_opener",return_value=opener),patch.object(r,"command") as command:
            response.read.return_value=json.dumps(value).encode();r.require_managed_validation_policy({"managedAndroidPolicySha256":digest})
            request=opener.open.call_args.args[0]
            self.assertEqual("http://100.81.98.93:8787/v1/project-workspaces/validation-policy",request.full_url)
            self.assertEqual("GET",request.get_method());self.assertEqual("Bearer synthetic-test-token",request.get_header("Authorization"))
            for changed in ({"androidInputsSha256":"f"*64},{"workerId":"other"},{"path":"/foreign"}):
                response.read.return_value=json.dumps({**value,**changed}).encode()
                with self.assertRaises(r.Rejected):r.require_managed_validation_policy({"managedAndroidPolicySha256":digest})
            command.assert_not_called()

    def test_staging_and_execution_recheck_binding_before_any_app_or_android_effect(self):
        artifact={"managedAndroidPolicySha256":w.VALIDATION_POLICY_SHA256}
        for target in (r.AppTarget({}),r.AndroidTarget({})):
            for operation in (target.stage,target.apply):
                with patch.object(r,"require_managed_validation_policy",side_effect=r.Rejected("MANAGED_VALIDATION_POLICY_MISMATCH")),patch.object(r,"command") as command:
                    with self.assertRaises(r.Rejected):operation({"artifact":artifact},Path("/unused-test-fixture"))
                    command.assert_not_called()

if __name__=="__main__":unittest.main()
