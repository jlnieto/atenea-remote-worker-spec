#!/usr/bin/env python3
"""Closed read-only channel proof using local signed identity and durable receipts."""
import importlib.util
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch, Mock
from jsonschema import Draft202012Validator

spec=importlib.util.spec_from_file_location("android_observation_release",Path(__file__).with_name("release-control-v1.py"))
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class AndroidObservationTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.plan=str(uuid.uuid4());self.operation=str(uuid.uuid4());self.source="1"*40
        self.current={"sourceCommit":self.source,"versionCode":1000012,"certificateSha256":"b"*64,
                      "manifest":{"versionCode":1000012,"versionName":"0.6.12","sha256":"a"*64,
                                  "apkUrl":"https://private-channel/not-for-client","sourceCommit":self.source}}
        self.target=Mock();self.target.inspect.side_effect=lambda:json.loads(json.dumps(self.current))
        self.c=m.Controller(self.root,Mock(),{"ANDROID_STABLE":self.target})
        for name in ("trusted","trusted_directory"):
            p=patch.object(m,name,side_effect=lambda path,mode=None:path);p.start();self.addCleanup(p.stop)
        record={"protocol":m.PROTOCOL,"planId":self.plan,"target":"ANDROID_STABLE","sourceCommit":self.source,
                "state":"SUCCEEDED","errorCode":None,"operationId":self.operation,"finishedAt":1,
                "effectiveSourceCommit":self.source,"resultSha256":"a"*64,"expiresAt":1,
                "artifact":{"versionCode":1000012},"predecessor":{}}
        record["planSha256"]=m.digest({k:record[k] for k in ("protocol","planId","target","sourceCommit","artifact","predecessor","expiresAt")})
        m.save(self.c.path(self.plan)/"operation.json",record);m.save(self.c.path(self.plan)/"receipt.json",self.current)

    def test_exact_public_projection_schema_and_no_writes_or_effects(self):
        before={p:p.read_bytes() for p in self.root.rglob("*.json")}
        value=self.c.dispatch({"operation":"OBSERVE_ANDROID"})
        schema=json.loads((Path(__file__).parents[2]/"runtime-contract/release-control-v1.android-observation.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(value)
        self.assertEqual(1000012,value["versionCode"]);self.assertEqual(self.plan,value["planId"])
        self.assertNotIn("private-channel",json.dumps(value));self.assertNotIn("apkUrl",value)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob("*.json")})
        self.assertEqual({"inspect"},{call[0] for call in self.target.method_calls})

    def test_unsigned_unattributed_or_moved_channel_never_becomes_included(self):
        for field,value in (("versionCode",1000013),("sourceCommit","2"*40),("certificateSha256","c"*64)):
            original=self.current[field];self.current[field]=value
            with self.subTest(field=field),self.assertRaises(m.Rejected):self.c.dispatch({"operation":"OBSERVE_ANDROID"})
            self.current[field]=original

    def test_active_publication_and_arbitrary_input_rejected(self):
        for field in ("path","command","versionCode","sourceCommit","target"):
            with self.subTest(field=field),self.assertRaises(m.Rejected):self.c.dispatch({"operation":"OBSERVE_ANDROID",field:"foreign"})
        record=self.c.read(self.plan);record["state"]="APPLYING";m.save(self.c.path(self.plan)/"operation.json",record)
        with self.assertRaises(m.Rejected):self.c.dispatch({"operation":"OBSERVE_ANDROID"})

if __name__=="__main__":unittest.main()
