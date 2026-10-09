#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

def load(name):
    spec = importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ACCESS = load('codex-release-runtime-access-v1')
STAGE = load('codex-release-stage-v1')

class RuntimeAccessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root/'package'
        self.release.mkdir(mode=0o700)
        (self.release/'bin').mkdir(mode=0o755)
        (self.release/'bin/codex').write_text('#!/bin/sh\necho codex-cli 0.157.0\n')
        (self.release/'bin/codex').chmod(0o700)
        (self.release/'package.json').write_text('{}')
        (self.release/'package.json').chmod(0o600)
        self.entries = STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid())
        self.evidence = {'current':ACCESS.CURRENT,'previous':ACCESS.PREVIOUS,'inventory':'fixed-hash'}
        self.receipt = self.root/'receipt.json'

    def invoke(self, action, probe=None):
        current_entries = STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid())
        def save(value):
            self.receipt.write_text(json.dumps(value))
        with patch.object(ACCESS,'inspect',return_value=(STAGE,self.release,current_entries,self.evidence)), \
                patch.object(ACCESS,'RECEIPT',self.receipt), \
                patch.object(ACCESS,'regular',side_effect=lambda path,owner:json.loads(path.read_text())), \
                patch.object(ACCESS,'persist',side_effect=save), \
                patch.object(ACCESS,'protected',return_value=self.evidence), \
                patch.object(ACCESS,'runtime_probe',side_effect=probe):
            return ACCESS.operate(action)

    def test_exact_repair_durable_and_idempotent_without_evidence_or_links_change(self):
        before = STAGE.release_manifest(self.release)
        result = self.invoke('apply')
        self.assertEqual('SUCCEEDED',result['state'])
        self.assertFalse(result['replayed'])
        self.assertEqual(0o750,self.release.stat().st_mode & 0o777)
        self.assertEqual(0o750,(self.release/'bin/codex').stat().st_mode & 0o777)
        self.assertEqual(0o640,(self.release/'package.json').stat().st_mode & 0o777)
        self.assertEqual(before,STAGE.release_manifest(self.release))
        receipt = self.receipt.read_bytes()
        replay = self.invoke('apply')
        self.assertTrue(replay['replayed'])
        self.assertEqual(result['operationId'],replay['operationId'])
        self.assertEqual(receipt,self.receipt.read_bytes())
        self.assertEqual('VERIFIED',self.invoke('verify')['state'])

    def test_failed_actual_identity_probe_restores_original_permissions(self):
        with self.assertRaisesRegex(RuntimeError,'probe failed'):
            self.invoke('apply',RuntimeError('probe failed'))
        self.assertEqual('ROLLED_BACK',json.loads(self.receipt.read_text())['state'])
        for entry in self.entries:
            self.assertEqual(entry['beforeMode'],(self.release/entry['path']).stat().st_mode & 0o777)
        with self.assertRaisesRegex(RuntimeError,'RECEIPT_CONFLICT'):
            self.invoke('apply')

    def test_changed_record_and_post_repair_permissions_rejected(self):
        self.invoke('apply')
        value = json.loads(self.receipt.read_text());value['current']='foreign'
        self.receipt.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'RECEIPT_CONFLICT'):
            self.invoke('apply')

    def test_plan_is_read_only_and_verify_cannot_claim_private_package_ready(self):
        self.assertEqual('READY',self.invoke('plan')['state'])
        self.assertFalse(self.receipt.exists())
        with self.assertRaisesRegex(RuntimeError,'RUNTIME_MODES_NOT_READY'):
            self.invoke('verify')
        self.assertEqual(0o700,self.release.stat().st_mode & 0o777)

    def test_foreign_owner_group_modes_links_and_hardlinks_fail_closed(self):
        with self.assertRaises(STAGE.StageError):
            STAGE.runtime_access_entries(self.release,os.getuid()+1,os.getgid())
        with self.assertRaises(STAGE.StageError):
            STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid()+1)
        for mode in (0o777,0o6755,0o775):
            (self.release/'bin/codex').chmod(mode)
            with self.assertRaises(STAGE.StageError):
                STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid())
        (self.release/'bin/codex').chmod(0o700)
        (self.release/'foreign').symlink_to('/etc/passwd')
        with self.assertRaises(STAGE.StageError):
            STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid())
        (self.release/'foreign').unlink()
        os.link(self.release/'package.json',self.release/'foreign')
        with self.assertRaises(STAGE.StageError):
            STAGE.runtime_access_entries(self.release,os.getuid(),os.getgid())

    def test_caller_authority_is_not_accepted(self):
        for arguments in (['apply','/tmp/foreign'],['apply','--version','0.145.0'],['execute']):
            completed = subprocess.run(['python3',str(Path(ACCESS.__file__)),*arguments],capture_output=True)
            self.assertNotEqual(0,completed.returncode)

    def test_probe_only_exposes_managed_current_read_only_and_uses_runner_identity(self):
        with patch.object(ACCESS.subprocess,'run',return_value=subprocess.CompletedProcess([],0,ACCESS.VERSION+'\n','')) as run:
            ACCESS.runtime_probe()
        command = run.call_args.args[0]
        self.assertIn('User=jose',command)
        self.assertIn('Group=atenea',command)
        self.assertEqual([str(ACCESS.ROOT/'current/bin/codex'),'--version'],command[-2:])
        self.assertEqual(2,command.count(str(ACCESS.ROOT/'current')))
        self.assertNotIn('exec',command)
        self.assertNotIn('/home/jose/.codex',command)
        self.assertNotIn(str(ACCESS.ROOT/'releases'),command)

class DistinctIdentityNamespaceTest(unittest.TestCase):
    @unittest.skipUnless(os.geteuid()==0 and Path('/usr/bin/bwrap').exists(), 'requires root and Bubblewrap for distinct UID acceptance')
    def test_private_package_fails_then_actual_other_uid_executes_read_only(self):
        user = pwd.getpwnam('nobody')
        with tempfile.TemporaryDirectory(prefix='codex-access-distinct-') as temporary:
            root = Path(temporary);root.chmod(0o755)
            package = root/'release';package.mkdir(mode=0o700)
            os.chown(package,0,user.pw_gid)
            binary = package/'codex';binary.write_text('#!/bin/sh\necho codex-cli 0.157.0\n')
            binary.chmod(0o700);os.chown(binary,0,user.pw_gid)
            cmd = ['/usr/sbin/runuser','-u','nobody','-g',str(user.pw_gid),'--']
            # runuser takes a group name, not a numeric group argument.
            import grp
            cmd[4]=grp.getgrgid(user.pw_gid).gr_name
            cmd += ['/usr/bin/bwrap','--unshare-all','--ro-bind','/usr','/usr',
                '--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
                '--ro-bind',str(package),'/runtime','/runtime/codex']
            denied = subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(0,denied.returncode)
            self.assertIn('Permission denied',denied.stderr)
            STAGE.set_runtime_modes(package,STAGE.runtime_access_entries(package,0,user.pw_gid))
            accepted = subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(0,accepted.returncode,accepted.stderr)
            self.assertEqual(ACCESS.VERSION,accepted.stdout.strip())
            write = subprocess.run(cmd[:-1]+['/bin/sh','-c','touch /runtime/foreign'],capture_output=True,text=True)
            self.assertNotEqual(0,write.returncode)
            self.assertIn('Read-only file system',write.stderr)
            self.assertFalse((package/'foreign').exists())

@unittest.skipUnless(os.geteuid()==0,'root-owned isolated evidence fixture')
class RetainedEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'managed';self.root.mkdir(mode=0o750)
        for name in ('releases','inbox','operations','activations'):
            (self.root/name).mkdir(mode=0o750)
        self.release = self.root/ACCESS.CURRENT;self.release.mkdir(mode=0o700)
        (self.release/'bin').mkdir(mode=0o700)
        (self.release/'bin/codex').write_bytes(b'synthetic binary');(self.release/'bin/codex').chmod(0o700)
        (self.root/ACCESS.PREVIOUS).mkdir(mode=0o750)
        (self.root/'current').symlink_to(ACCESS.CURRENT);(self.root/'previous').symlink_to(ACCESS.PREVIOUS)
        self.archive = self.root/'inbox'/(ACCESS.CANDIDATE+'.tar.gz');self.archive.write_bytes(b'synthetic archive')
        archive_sha = ACCESS.digest(self.archive)
        manifest_sha = STAGE.release_manifest(self.release)
        self.registry = self.root/'registry.json'
        self.state = self.root/'executions.json'
        self.save(self.registry,{'schemaVersion':'codex-release-stage-v1','workerId':'ax42-01','candidates':{
            ACCESS.CANDIDATE:{'planId':ACCESS.PLAN,'candidateId':ACCESS.CANDIDATE,'codexVersion':'0.157.0',
                'releaseDigestSha256':archive_sha,'catalogRevision':ACCESS.CATALOG}}})
        self.save(self.state,{'executions':{},'validations':{}})
        self.stage_record = self.root/'operations'/'staged.json'
        self.save(self.stage_record,{'result':{'state':'STAGED','planId':ACCESS.PLAN,'candidateId':ACCESS.CANDIDATE,
            'releaseDigestSha256':archive_sha,'releaseManifestSha256':manifest_sha,
            'schemaManifestSha256':ACCESS.SCHEMA_SHA,'catalogRevision':ACCESS.CATALOG}})
        self.activation = self.root/'activations'/'activated.json'
        self.save(self.activation,{'result':{'state':'ACTIVATED','planId':ACCESS.PLAN,
            'candidateId':ACCESS.CANDIDATE,'releaseDigestSha256':archive_sha}})
        for name,value in (('ROOT',self.root),('REGISTRY',self.registry),('EXECUTIONS',self.state),
                           ('ARCHIVE_SHA',archive_sha),('MANIFEST_SHA',manifest_sha)):
            item = patch.object(ACCESS,name,value);item.start();self.addCleanup(item.stop)
        for target,value in ((ACCESS.pwd,'getpwnam'),(ACCESS.grp,'getgrnam')):
            item = patch.object(target,value,return_value=types.SimpleNamespace(pw_uid=0,gr_gid=os.getgid()))
            item.start();self.addCleanup(item.stop)
        item = patch.object(ACCESS,'stage_module',return_value=STAGE);item.start();self.addCleanup(item.stop)

    def save(self,path,value):
        path.write_text(json.dumps(value));path.chmod(0o600)

    def test_exact_evidence_only_observed_without_permission_mutation(self):
        module,release,entries,evidence = ACCESS.inspect()
        self.assertEqual(STAGE,module);self.assertEqual(self.release,release)
        self.assertEqual(0o700,entries[0]['beforeMode'])
        self.assertEqual(ACCESS.CURRENT,evidence['current'])
        self.assertEqual(0o700,self.release.stat().st_mode & 0o777)

    def test_moved_link_active_agent_or_validation_rejected(self):
        (self.root/'current').unlink();(self.root/'current').symlink_to(ACCESS.PREVIOUS)
        with self.assertRaisesRegex(RuntimeError,'LINK_IDENTITY_CHANGED'):ACCESS.inspect()
        (self.root/'current').unlink();(self.root/'current').symlink_to(ACCESS.CURRENT)
        self.save(self.state,{'executions':{'foreign':{'status':'RUNNING'}},'validations':{}})
        with self.assertRaisesRegex(RuntimeError,'ACTIVE_AGENT_RUN'):ACCESS.inspect()
        self.save(self.state,{'executions':{},'validations':{'foreign':{'state':'RUNNING'}}})
        with self.assertRaisesRegex(RuntimeError,'ACTIVE_VALIDATION'):ACCESS.inspect()

    def test_wrong_candidate_and_missing_activation_fail_closed(self):
        value = json.loads(self.registry.read_text());value['candidates'][ACCESS.CANDIDATE]['codexVersion']='0.145.0'
        self.save(self.registry,value)
        with self.assertRaisesRegex(RuntimeError,'CANDIDATE_CHANGED'):ACCESS.inspect()
        value['candidates'][ACCESS.CANDIDATE]['codexVersion']='0.157.0';self.save(self.registry,value)
        self.activation.unlink()
        with self.assertRaisesRegex(RuntimeError,'ACTIVATION_EVIDENCE_CHANGED'):ACCESS.inspect()

    def test_changed_archive_stage_manifest_or_package_rejected(self):
        self.archive.write_bytes(b'foreign')
        with self.assertRaisesRegex(RuntimeError,'ARCHIVE_CHANGED'):ACCESS.inspect()
        self.archive.write_bytes(b'synthetic archive')
        value = json.loads(self.stage_record.read_text());value['result']['releaseManifestSha256']='f'*64
        self.save(self.stage_record,value)
        with self.assertRaisesRegex(RuntimeError,'STAGE_EVIDENCE_CHANGED'):ACCESS.inspect()
        value['result']['releaseManifestSha256']=ACCESS.MANIFEST_SHA;self.save(self.stage_record,value)
        (self.release/'bin/codex').write_bytes(b'foreign')
        with self.assertRaisesRegex(RuntimeError,'PACKAGE_CONTENT_CHANGED'):ACCESS.inspect()

if __name__=='__main__':
    unittest.main()
