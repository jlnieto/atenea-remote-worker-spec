#!/usr/bin/env python3
"""Target tests use ephemeral fixtures and substitute all external commands."""
import copy
import importlib.util
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location("targets",Path(__file__).with_name("release-control-v1.py"))
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
OLD="1"*40; NEW="2"*40; CERT="3"*64

class AndroidTargetTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="release-apk-unit-"); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.apk=self.root/"android"; self.apk.mkdir(); (self.apk/"releases").mkdir()
        self.stage=self.root/"stage"; self.stage.mkdir()
        self.old=b"previous signed apk"; self.new=b"new signed apk"
        (self.apk/"atenea-debug.apk").write_bytes(self.old)
        self.manifest={"sourceCommit":OLD,"versionCode":140,"versionName":"0.5.107", "sha256":r.file_digest(self.apk/"atenea-debug.apk"),
            "apkUrl":"https://atenea.yudri.es/apk/"+"t"*24+"/android/atenea-debug.apk"}
        r.save(self.apk/"manifest.json",self.manifest,mode=0o644)
        self.target=r.AndroidTarget({"androidCertificateSha256":CERT})
        self.target.APK_ROOT=self.apk
        self.commands=[]
        def command(argv,**kwargs):
            self.commands.append(argv)
            if argv[1:3]==["verify","--print-certs"]: return ("Signer #1 certificate SHA-256 digest: "+CERT+"\n").encode()
            if argv[1:3]==["dump","badging"]: return b"package: name='com.atenea.android' versionCode='141' versionName='0.5.108'"
            if argv[1]=="sign": (self.stage/"signed.apk").write_bytes(self.new); return b""
            raise AssertionError("Unexpected command")
        for name,value in (("trusted",lambda path,mode=None:path),("trusted_directory",lambda path,mode:None),("command",command)):
            patcher=patch.object(r,name,side_effect=value); patcher.start(); self.addCleanup(patcher.stop)
        self.plan={"sourceCommit":NEW,"artifact":{"versionCode":141,"versionName":"0.5.108"},"predecessor":self.target.inspect()}
        (self.stage/"app-unsigned.apk").write_bytes(b"unsigned")

    def test_signature_compatibility_and_monotonic_version_checked_before_publish(self):
        self.target.stage(self.plan,self.stage)
        self.assertTrue((self.stage/"signed.json").is_file())
        with self.assertRaises(r.Rejected): self.target.stage({**self.plan,"artifact":{"versionCode":140,"versionName":"0.5.107"}},self.stage)
        self.assertEqual(self.manifest,json.loads((self.apk/"manifest.json").read_bytes()))
    def test_signer_certificate_must_match_installed_app(self):
        self.target.config["androidCertificateSha256"]="4"*64
        with self.assertRaises(r.Rejected): self.target.certificate(self.apk/"atenea-debug.apk")
    def test_legacy_channel_has_explicit_unknown_source_without_invented_git_commit(self):
        manifest={key:value for key,value in self.manifest.items() if key!="sourceCommit"}
        r.save(self.apk/"manifest.json",manifest,mode=0o644)
        observed=self.target.inspect()
        self.assertIsNone(observed["sourceCommit"])
        self.assertEqual(140,observed["versionCode"])
        self.assertEqual(CERT,observed["certificateSha256"])
    def test_publication_uses_immutable_generations_and_preserves_legacy_previous(self):
        self.target.stage(self.plan,self.stage); self.target.apply(self.plan,self.stage)
        final=json.loads((self.apk/"manifest.json").read_bytes())
        self.assertEqual(141,final["versionCode"]); self.assertIn("/releases/141/",final["apkUrl"])
        self.assertEqual(self.old,(self.apk/"releases/140/atenea-debug.apk").read_bytes())
        self.assertEqual(self.new,(self.apk/"releases/141/atenea-debug.apk").read_bytes())
        self.assertIn("/releases/140/",final["previousRelease"]["apkUrl"])
        self.assertEqual(0o644,(self.apk/"manifest.json").stat().st_mode&0o777)
    def test_channel_rollback_retains_audited_immutable_apk_and_restores_manifest(self):
        self.target.stage(self.plan,self.stage); self.target.apply(self.plan,self.stage)
        self.target.rollback(self.plan,self.stage)
        self.assertEqual(self.manifest,json.loads((self.apk/"manifest.json").read_bytes()))
        self.assertTrue((self.apk/"releases/141/atenea-debug.apk").is_file())
    def test_foreign_channel_and_mutated_signed_apk_cannot_publish(self):
        self.target.stage(self.plan,self.stage)
        self.plan["predecessor"]["manifest"]["apkUrl"]="https://foreign.example/apk"
        with self.assertRaises(r.Rejected): self.target.apply(self.plan,self.stage)
        self.assertFalse((self.apk/"releases/141").exists())
        self.plan["predecessor"]["manifest"]["apkUrl"]=self.manifest["apkUrl"]
        (self.stage/"signed.apk").write_bytes(b"foreign")
        with self.assertRaises(r.Rejected): self.target.apply(self.plan,self.stage)

class AppTargetTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="release-app-unit-"); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.stage=self.root/"stage"; self.stage.mkdir()
        self.stack=self.root/"stack"; self.stack.mkdir(); self.override=self.stack/"docker-compose.release-v1.json"
        self.old={"services":{"atenea-backend-prod":{"image":"sha256:"+"1"*64,"environment":{"ATENEA_CODEX_MANAGED_UPDATES_ENABLED":"true","EXISTING_FLAG":"preserved"}}}}
        r.save(self.override,self.old); (self.stack/".env").touch()
        self.backup=self.root/"backups"; self.backup.mkdir()
        # Fixed production backup path is substituted only inside the unit fixture.
        real_path=r.Path
        def path(value): return self.backup if value=="/srv/atenea/backups/prod" else real_path(value)
        for name,value in (("STACK",self.stack),("OVERRIDE",self.override)):
            patcher=patch.object(r,name,value); patcher.start(); self.addCleanup(patcher.stop)
        patcher=patch.object(r,"Path",side_effect=path); patcher.start(); self.addCleanup(patcher.stop)
        patcher=patch.object(r,"trusted",side_effect=lambda p,mode=None:p); patcher.start(); self.addCleanup(patcher.stop)
        patcher=patch.object(r,"trusted_directory",return_value=None); patcher.start(); self.addCleanup(patcher.stop)
        self.target=r.AppTarget({"composeFiles":[str(self.override)]})
        self.commands=[]
        def command(argv,**kwargs):
            self.commands.append(argv)
            if argv[-2:]==["pg_dump","--version"]: return b"pg_dump (PostgreSQL) 16.15\n"
            if argv[-2:]==["pg_restore","--version"]: return b"pg_restore (PostgreSQL) 16.15\n"
            if "pg_dump" in argv[-1]: kwargs["output"].write(b"consistent pg16 custom dump"); return None
            if "pg_restore" in argv and "--list" in argv:
                self.assertEqual(b"consistent pg16 custom dump",kwargs["stdin"].read()); return b"TOC"
            return b""
        patcher=patch.object(r,"command",side_effect=command); patcher.start(); self.addCleanup(patcher.stop)
        r.save(self.stage/"image.json",{"imageId":"sha256:"+"2"*64})
        self.plan={"operationId":str(uuid.uuid4()),"sourceCommit":NEW,"predecessor":{"sourceCommit":OLD,"override":copy.deepcopy(self.old)}}
    def test_apply_preserves_flags_and_updates_only_backend_after_pg16_backup(self):
        self.target.apply(self.plan,self.stage)
        final=json.loads(self.override.read_bytes())
        self.assertEqual(self.old["services"]["atenea-backend-prod"]["environment"],final["services"]["atenea-backend-prod"]["environment"])
        self.assertEqual("sha256:"+"2"*64,final["services"]["atenea-backend-prod"]["image"])
        self.assertEqual(self.old,self.plan["predecessor"]["override"])
        self.assertEqual(["up","-d","--no-deps","--no-build","atenea-backend-prod"],self.commands[-1][-5:])
        self.assertFalse(any("down" in argv or "atenea-backend-dev" in argv for argv in self.commands))
        self.assertTrue((self.stage/"backup.json").is_file())
    def test_rollback_recreates_only_backend_and_does_not_restore_postgresql(self):
        self.target.verify=Mock(return_value={"sourceCommit":OLD})
        self.target.rollback(self.plan,self.stage)
        self.assertEqual(self.old,json.loads(self.override.read_bytes()))
        self.assertTrue(all("pg_restore" not in argv for argv in self.commands))
        self.assertEqual("atenea-backend-prod",self.commands[-1][-1])
    def test_unsafe_compose_paths_are_rejected(self):
        self.target.config["composeFiles"]= [str(self.override),str(self.stack/"../foreign.yml")]
        with self.assertRaises(r.Rejected): self.target.compose("up")
    def test_postcondition_detects_changed_flags_even_if_app_and_postgres_are_healthy(self):
        predecessor={**self.plan["predecessor"],"postgresId":"retained-container", "postgresMountsSha256":"1"*64,
                     "composeContractSha256":"2"*64}
        self.target.inspect=Mock(return_value={"sourceCommit":NEW,"postgresId":"retained-container",
            "postgresMountsSha256":"1"*64,"composeContractSha256":"3"*64})
        with patch.object(r.urllib.request,"urlopen",return_value=io.BytesIO(b'{"status":"UP"}')):
            with self.assertRaises(r.Rejected) as error: self.target.verify({**self.plan,"predecessor":predecessor},self.stage)
        self.assertEqual("APP_POSTCONDITION_FAILED",error.exception.code)

class PlatformTargetTest(unittest.TestCase):
    def test_installer_verify_cannot_hide_changed_codex_links_or_recovery_plan(self):
        target=r.PlatformTarget(); target.protected_state=Mock(return_value={"current":"releases/new"})
        plan={"sourceCommit":NEW,"planId":str(uuid.uuid4()),"predecessor":{"protectedState":{"current":"releases/original"}}}
        with patch.object(r,"command",return_value=b"PASS"), self.assertRaises(r.Rejected):
            target.verify(plan,Path("/unused"))

if __name__=="__main__": unittest.main()
