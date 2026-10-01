#!/usr/bin/env python3
"""Real ZIP/hash/manifest parsing; every GitHub/download call is a fixture."""
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location("release_artifacts",Path(__file__).with_name("release-control-v1.py"))
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
SHA="1"*40


class ArtifactTest(unittest.TestCase):
    def bundle(self,extra=False,symlink=False):
        result=io.BytesIO(); payload=b"reviewed fixture image"
        self.manifest={"protocol":r.PROTOCOL,"target":"APP_PROD","sourceCommit":SHA,
            "payloadSha256":hashlib.sha256(payload).hexdigest(),"versionCode":None,"versionName":None,"flywayVersion":84}
        with zipfile.ZipFile(result,"w") as archive:
            archive.writestr("manifest.json",json.dumps(self.manifest))
            info=zipfile.ZipInfo("image.tar")
            if symlink: info.external_attr=0o120777<<16
            archive.writestr(info,payload)
            if extra: archive.writestr("command.sh",b"not authorized")
        return result.getvalue()

    def client(self,bundle,archive_hash=None):
        client=r.GitHubArtifacts()
        client.api=Mock(side_effect=[{"object":{"sha":SHA}},
            {"workflow_runs":[{"id":9,"head_sha":SHA,"head_branch":"main","event":"push",
                "head_repository":{"full_name":"jlnieto/atenea"},"path":".github/workflows/release-artifacts-v1.yml",
                "status":"completed","conclusion":"success"}]},
            {"artifacts":[{"id":99,"name":"atenea-release-app_prod-"+SHA,"expired":False,
                "digest":"sha256:"+(archive_hash or hashlib.sha256(bundle).hexdigest())}]}])
        return client

    def prepare(self,bundle,archive_hash=None):
        with tempfile.TemporaryDirectory(prefix="release-zip-unit-") as name:
            root=Path(name); token=root/"token"; token.write_text("synthetic-fixture-token")
            opener=Mock()
            opener.open.side_effect=[urllib.error.HTTPError("https://api.github.com/fixture",302,"redirect",
                {"Location":"https://fixture.blob.core.windows.net/reviewed.zip"},None),io.BytesIO(bundle)]
            with patch.object(r,"trusted",return_value=token),patch.object(r.urllib.request,"build_opener",return_value=opener):
                result=self.client(bundle,archive_hash).prepare("APP_PROD",SHA,root)
                self.assertEqual(b"reviewed fixture image",(root/"image.tar").read_bytes())
                # Download redirect must not forward the GitHub bearer.
                self.assertIsInstance(opener.open.call_args_list[1].args[0],str)
                return result

    def test_verified_zip_payload_and_closed_manifest_are_consumed(self):
        value=self.prepare(self.bundle())
        self.assertEqual(84,value["flywayVersion"])
        self.assertEqual(99,value["artifactId"])
        self.assertEqual(self.manifest["payloadSha256"],value["payloadSha256"])

    def test_archive_digest_mismatch_rejected_before_unpack(self):
        with self.assertRaises(r.Rejected) as error: self.prepare(self.bundle(),"0"*64)
        self.assertEqual("ARTIFACT_DIGEST_MISMATCH",error.exception.code)

    def test_extra_file_and_package_symlink_rejected(self):
        for bundle in (self.bundle(extra=True),self.bundle(symlink=True)):
            with self.subTest(bundle=len(bundle)),self.assertRaises(r.Rejected) as error: self.prepare(bundle)
            self.assertEqual("ARTIFACT_STRUCTURE_REJECTED",error.exception.code)

    def test_failed_latest_run_cannot_be_replaced_by_an_older_pass(self):
        client=r.GitHubArtifacts()
        run={"id":9,"head_sha":SHA,"head_branch":"main","event":"push",
            "head_repository":{"full_name":"jlnieto/atenea"},"path":".github/workflows/release-artifacts-v1.yml",
            "status":"completed","conclusion":"failure"}
        client.api=Mock(side_effect=[{"object":{"sha":SHA}},
            {"workflow_runs":[{**run,"id":8,"conclusion":"success"},run]}])
        with self.assertRaises(r.Rejected) as error: client.prepare("APP_PROD",SHA,Path("/not-created"))
        self.assertEqual("RELEASE_BUILD_FAILED",error.exception.code)
        self.assertEqual(2,client.api.call_count)


if __name__=="__main__": unittest.main()
