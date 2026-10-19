#!/usr/bin/env python3
"""Root-only receipt reads and deliberately lossy failure symbols."""
import hashlib,importlib.util,json,os,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('diagnostic_mediator',Path(__file__).with_name('atenea-validation-v1.py'))
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class SymbolsTest(unittest.TestCase):
    def test_versioned_schemas_are_draft202012_and_reject_operational_inputs(self):
        from jsonschema import Draft202012Validator,FormatChecker
        root=Path(__file__).resolve().parents[2]/'runtime-contract'
        for name in ('request','response'):
            schema=json.loads((root/f'closed-validation-diagnostic-v1.{name}.schema.json').read_text())
            Draft202012Validator.check_schema(schema)
        schema=json.loads((root/'closed-validation-diagnostic-v1.request.schema.json').read_text())
        validator=Draft202012Validator(schema,format_checker=FormatChecker());uid=str(uuid.uuid4())
        request={'schemaVersion':1,'protocolVersion':'closed-validation-broker/v1','operationId':uid,'sessionId':uid,
                 'workspaceIdentity':'remote:ax42-01:change:'+uid,'projectId':'atenea'}
        self.assertTrue(validator.is_valid(request))
        for k in ('path','command','shell','credential','host'):
            self.assertFalse(validator.is_valid({**request,k:'foreign'}))
    def test_only_failed_method_type_and_line_not_candidate_text(self):
        output='''[ERROR] com.atenea.api.MobileTest.inbox -- Time elapsed: 0.2 s <<< FAILURE!
org.opentest4j.AssertionFailedError: expected SECRET but was /srv/private
    at com.atenea.api.MobileTest.inbox(MobileTest.java:123)
[INFO] com.atenea.api.PassingTest
'''
        self.assertEqual([{'testClass':'com.atenea.api.MobileTest','testMethod':'inbox',
            'failureType':'org.opentest4j.AssertionFailedError','sourceLine':123}],m.test_failure_symbols(output))
        self.assertNotIn('SECRET',json.dumps(m.test_failure_symbols(output)))
        self.assertEqual([],m.test_failure_symbols('[INFO] com.atenea.api.PassingTest SECRET'))
    def test_parameterized_test_does_not_retain_arguments(self):
        result=m.test_failure_symbols('[ERROR] com.atenea.FooTest.example(String)[1] -- Time elapsed: 0.1 s <<< ERROR!\n')
        self.assertEqual([],result) # unrecognised forms are not invented as evidence

@unittest.skipUnless(os.geteuid()==0,'root authority tests')
class ReceiptReadTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.session=str(uuid.uuid4());self.operation=str(uuid.uuid4());self.change=str(uuid.uuid4())
        self.args=['BACKEND_TEST',self.session,'remote:ax42-01:change:'+self.change,'a'*64,self.operation]
        self.identity=m.durable_identity(self.args)
        self.journal=self.root/'journal';self.journal.mkdir(mode=0o750)
        # Match install_exact_directory root atenea 0750, not a synthetic root:root parent.
        os.chown(self.journal,0,98888)
        self.enterContext(mock.patch.object(m.grp,'getgrnam',return_value=SimpleNamespace(gr_gid=98888)))
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o750)
        (self.artifacts/self.session).mkdir(mode=0o750)
        self.enterContext(mock.patch.object(m,'JOURNAL_ROOT',self.journal))
        self.enterContext(mock.patch.object(m,'ARTIFACT_ROOT',self.artifacts))
        self.directory=m.operation_directory(self.identity)
        self.output=self.root/'output';self.output.write_text('''[ERROR] com.atenea.FooTest.broken -- Time elapsed: 0.1 s <<< FAILURE!
org.opentest4j.AssertionFailedError: SECRET
    at com.atenea.FooTest.broken(FooTest.java:42)
'''+('[INFO] Subsequent successful test\n'*5000))
        digest=m.persist_diagnostic(self.artifacts/self.session,self.args,m.DEFINITIONS['BACKEND_TEST'],
            m.RunOutcome(1,'TESTS','TESTS_FAILED','CANDIDATE'),self.output,50)
        manifest=hashlib.sha256('\0'.join((self.operation,m.DEFINITIONS['BACKEND_TEST'].revision,'a'*64,'1','50',m.sha256_file(self.output),digest)).encode()).hexdigest()
        self.record={**m.new_operation(self.identity),'state':'CANDIDATE_FAILED','terminalCause':'CANDIDATE',
            'exitCode':1,'durationMillis':50,'artifactManifestSha256':manifest}
        m.write_operation(self.directory,self.record)
        self.path=self.artifacts/self.session/(self.operation+'-diagnostic-v1.json')
    def test_exact_read_is_idempotent_and_changes_no_bytes_or_metadata(self):
        before={str(p.relative_to(self.root)):(p.lstat().st_mode,p.lstat().st_mtime_ns,p.read_bytes() if p.is_file() else None) for p in self.root.rglob('*')}
        proof=m.read_diagnostic(self.args);self.assertEqual(proof,m.read_diagnostic(self.args))
        self.assertEqual('RECORDED',proof['failureDetailsState']);self.assertEqual(42,proof['diagnostic']['testFailures'][0]['sourceLine'])
        self.assertEqual(before,{str(p.relative_to(self.root)):(p.lstat().st_mode,p.lstat().st_mtime_ns,p.read_bytes() if p.is_file() else None) for p in self.root.rglob('*')})
        self.assertNotIn('SECRET',json.dumps(proof))
        from jsonschema import Draft202012Validator,FormatChecker
        schema=json.loads((Path(__file__).resolve().parents[2]/'runtime-contract/closed-validation-diagnostic-v1.response.schema.json').read_text())
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(proof)
    def test_historical_receipt_without_failure_details_is_truthful(self):
        value=json.loads(self.path.read_bytes());value.pop('testFailures');encoded=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        self.path.write_bytes(encoded)
        self.record['artifactManifestSha256']=hashlib.sha256('\0'.join((self.operation,value['definitionRevision'],'a'*64,'1','50',value['outputSha256'],hashlib.sha256(encoded).hexdigest())).encode()).hexdigest()
        m.write_operation(self.directory,self.record)
        proof=m.read_diagnostic(self.args);self.assertEqual('NOT_RECORDED',proof['failureDetailsState']);self.assertEqual([],proof['diagnostic']['testFailures'])
    def test_foreign_or_absent_operation_does_not_create_directories(self):
        before=list(self.root.rglob('*'))
        for index,value in ((1,str(uuid.uuid4())),(2,'remote:ax42-01:change:'+str(uuid.uuid4())),(3,'b'*64),(4,str(uuid.uuid4()))):
            with self.subTest(index=index),self.assertRaises((m.Rejected,OSError)):
                args=list(self.args);args[index]=value;m.read_diagnostic(args)
        self.assertEqual(before,list(self.root.rglob('*')))
    def test_tamper_permissions_symlink_and_nonterminal_rejected(self):
        original=self.path.read_bytes()
        self.path.write_bytes(original.replace(b'TESTS_FAILED',b'OTHER_FAILED'))
        with self.assertRaises(m.Rejected):m.read_diagnostic(self.args)
        self.path.write_bytes(original);self.path.chmod(0o644)
        with self.assertRaises(m.Rejected):m.read_diagnostic(self.args)
        self.path.chmod(0o600);self.path.unlink();self.path.symlink_to(self.output)
        with self.assertRaises(OSError):m.read_diagnostic(self.args)
        self.record['state']='RUNNING';m.write_operation(self.directory,self.record)
        with self.assertRaises(m.Rejected):m.read_diagnostic(self.args)

    def test_only_installer_journal_group_and_root_private_children_are_accepted(self):
        for gid in (0,98887):
            os.chown(self.journal,0,gid)
            with self.assertRaises(m.Rejected):m.read_diagnostic(self.args)
        os.chown(self.journal,0,98888)
        os.chown(self.directory,0,98888)
        with self.assertRaises(m.Rejected):m.read_diagnostic(self.args)

if __name__=='__main__':unittest.main()
