#!/usr/bin/env python3
"""Rescue tests: fake targets/commands; never connects to shared services."""
import contextlib
import copy
import importlib.util
import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import Mock,patch
from jsonschema import Draft202012Validator,FormatChecker

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
r=load("rescue_release","release-control-v1.py")
m=load("rescue","release-rescue-v1.py")

class Inline:
    def __init__(self,target,args=(),**kwargs):self.target,self.args=target,args
    def start(self):self.target(*self.args)

class RescueTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rescue-test-");self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.target=Mock()
        self.target.observe_current.return_value={"sourceCommit":"1"*40,"healthy":True}
        self.target.worker_health.return_value={"healthy":True,"capabilities":["project-codex-v4"]}
        self.controller=r.Controller(self.root,None,{"APP_PROD":self.target})
        self.config={"protocol":m.PROTOCOL,"allowedLogin":"operator@example.test","origin":"https://vps.tailtest.ts.net:8443"}
        self.model=m.Rescue(r,self.controller,self.config)
        self.before={"containerId":"a"*64,"imageId":"sha256:"+"b"*64,"sourceCommit":"1"*40,
            "postgresId":"c"*64,"postgresMountsSha256":"d"*64,"composeSha256":"e"*64,"startedAt":"before","running":True,"restarting":False}
        self.current=copy.deepcopy(self.before)
        for patcher in (patch.object(r,"trusted",side_effect=lambda path,mode=None:path),patch.object(r,"trusted_directory"),
                patch.object(self.model,"snapshot",side_effect=lambda:copy.deepcopy(self.current)),
                patch.object(self.model,"require_idle"),patch.object(self.model,"admission",side_effect=
                    lambda:contextlib.nullcontext(Mock(poll=Mock(return_value=None))))):
            patcher.start();self.addCleanup(patcher.stop)
        self.identifier=str(uuid.uuid4())

    def test_plan_is_read_only_and_duplicate_retains_same_intent(self):
        with patch.object(r,"command") as command:
            first=self.model.plan(self.identifier);self.assertEqual(first,self.model.plan(self.identifier));command.assert_not_called()
        self.assertEqual("READY",first["state"]);self.assertNotIn("predecessor",first)
        schema=json.loads((Path(__file__).resolve().parents[2]/"runtime-contract/release-rescue-v1.operation.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema);Draft202012Validator(schema,format_checker=FormatChecker()).validate(first)
        self.assertEqual(1,len(list((self.root/"rescue").iterdir())))
        self.assertEqual(0o600,self.model.path(self.identifier).stat().st_mode&0o777)

    def command(self,args,**kwargs):
        self.assertEqual(["/usr/bin/docker","restart","--time","15","a"*64],args)
        self.current["startedAt"]="after";return b""

    def test_confirm_restarts_only_retained_backend_once_and_preserves_all_identities(self):
        self.model.plan(self.identifier)
        with patch.object(m.threading,"Thread",Inline),patch.object(r,"command",side_effect=self.command) as command:
            result=self.model.execute(self.identifier);self.model.execute(self.identifier);self.model.inspect(self.identifier)
        self.assertEqual("SUCCEEDED",result["state"]);command.assert_called_once()
        self.assertEqual(self.before["postgresId"],self.current["postgresId"])
        self.assertEqual(self.before["imageId"],self.current["imageId"])

    def test_moved_identity_and_active_work_reject_before_restart(self):
        self.model.plan(self.identifier);self.current["imageId"]="sha256:"+"f"*64
        with patch.object(m.threading,"Thread",Inline),patch.object(r,"command") as command:
            result=self.model.execute(self.identifier)
        self.assertEqual("BLOCKED",result["state"]);command.assert_not_called()
        with patch.object(self.model,"require_idle",side_effect=r.Rejected("WORK_ACTIVE")),patch.object(r,"command") as command:
            with self.assertRaises(r.Rejected):self.model.plan(str(uuid.uuid4()))
        command.assert_not_called()

    def test_uncertain_restart_is_not_repeated_and_inspection_can_settle_ack(self):
        self.model.plan(self.identifier)
        def uncertain(args,**kwargs):self.command(args,**kwargs);raise r.Rejected("LOST_ACK")
        with patch.object(m.threading,"Thread",Inline),patch.object(r,"command",side_effect=uncertain) as command:
            self.assertEqual("ATTENTION",self.model.execute(self.identifier)["state"])
            self.model.execute(self.identifier);command.assert_called_once()
            with self.assertRaises(r.Rejected):self.model.require_settled()
            self.assertEqual("SUCCEEDED",self.model.inspect(self.identifier)["state"])
            self.model.require_settled();command.assert_called_once()

    def test_failed_health_never_changes_version_or_restores_database(self):
        self.model.plan(self.identifier);self.target.observe_current.return_value["healthy"]=False
        with patch.object(m.threading,"Thread",Inline),patch.object(m.time,"sleep"),patch.object(r,"command",side_effect=self.command) as command:
            result=self.model.execute(self.identifier);self.model.execute(self.identifier)
        self.assertEqual("ATTENTION",result["state"]);command.assert_called_once()
        self.assertEqual("RESCUE_HEALTH_FAILED",result["errorCode"])
        self.assertEqual("FAILED",self.model.inspect(self.identifier)["state"])
        self.model.require_settled()

    def test_lost_dispatch_before_effect_can_be_closed_without_repeating_restart(self):
        self.model.plan(self.identifier);record=self.model.read(self.identifier);record["state"]="ACCEPTED"
        r.save(self.model.path(self.identifier),record)
        with patch.object(r,"command") as command:
            self.assertEqual("BLOCKED",self.model.inspect(self.identifier)["state"]);command.assert_not_called()
        self.model.require_settled()

    def test_schema_and_idle_checks_are_fixed_read_only_and_fail_closed(self):
        # Remove the fixture override solely to exercise the real query contract.
        idle=m.Rescue.require_idle.__get__(self.model)
        good={"schema":99,"flywayFailures":0,"runs":0,"validations":0,"publications":0,"updates":0,"repairs":0}
        for value in (good,{**good,"runs":1},{**good,"schema":98}):
            with patch.object(r,"command",return_value=json.dumps(value).encode()) as command:
                if value==good:idle()
                else:
                    with self.assertRaises(r.Rejected):idle()
                self.assertEqual(self.model.psql(),command.call_args.args[0])
                sql=command.call_args.kwargs["input"].decode()
                self.assertTrue(sql.startswith("BEGIN READ ONLY;"));self.assertNotIn("UPDATE ",sql)

    def server(self):
        server=m.http.server.ThreadingHTTPServer(("127.0.0.1",0),m.handler(self.model))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join,3);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def request(self,url,fields=None,**headers):
        data=urllib.parse.urlencode(fields).encode() if fields is not None else None
        req=urllib.request.Request(url,data=data,headers={"Host":"vps.tailtest.ts.net:8443",
            "Tailscale-User-Login":"operator@example.test",**({"Origin":self.config["origin"],
            "Content-Type":"application/x-www-form-urlencoded"} if data is not None else {}),**headers})
        try:
            with urllib.request.urlopen(req,timeout=3) as result:return result.status,result.read().decode(),dict(result.headers)
        except urllib.error.HTTPError as error:return error.code,error.read().decode(),dict(error.headers)

    def test_private_http_auth_csrf_closed_actions_and_double_submit(self):
        url=self.server();code,page,headers=self.request(url)
        self.assertEqual(200,code);self.assertEqual("no-store",headers["Cache-Control"])
        csrf=re.search('name="csrf" value="([a-f0-9]+)"',page)[1]
        fields={"csrf":csrf,"action":"prepare","operationId":""}
        with patch.object(r,"command") as command:
            self.assertEqual(200,self.request(url+"/action",fields)[0]);self.request(url+"/action",fields)
            command.assert_not_called()
        self.assertEqual(1,len(self.model.records()))
        for changed in ({"csrf":"foreign"},{"action":"command"},{"path":"/etc"}):
            self.request(url+"/action",{**fields,**changed})
        self.assertEqual(1,len(self.model.records()))
        self.assertEqual(403,self.request(url,**{"Tailscale-User-Login":"foreign@example.test"})[0])
        code,body,_=self.request(url+"/action",fields,**{"Tailscale-User-Login":"foreign@example.test"})
        self.assertEqual(403,code);self.assertNotIn("Versión conservada",body);self.assertNotIn('name="csrf"',body)
        for origin in ("https://evil.invalid","null"):
            self.request(url+"/action",fields,Origin=origin)
        self.assertEqual(1,len(self.model.records()))

    def test_root_authority_configuration_is_closed_and_origin_private(self):
        path=self.root/"config.json";path.write_text(json.dumps(self.config))
        with patch.object(m,"CONFIG",path):
            self.assertEqual(self.config,m.configuration(r))
            schema=json.loads((Path(__file__).resolve().parents[2]/"runtime-contract/release-rescue-v1.operator.schema.json").read_bytes())
            Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(self.config)
            for changes in ({"origin":"https://public.example.com"},{"allowedLogin":"*"},{"command":"anything"}):
                path.write_text(json.dumps({**self.config,**changes}))
                with self.assertRaises(r.Rejected):m.configuration(r)

if __name__=="__main__":unittest.main()
