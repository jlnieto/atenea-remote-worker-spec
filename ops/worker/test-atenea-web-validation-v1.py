#!/usr/bin/python3
"""Focused closed web toolchain tests; no worker calls or Docker daemon."""
import base64
import contextlib
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True
def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value
RUNNER = module('web_validation_runner_test', 'atenea-validation-v1.py')
RUNTIME = module('web_validation_runtime_test', 'atenea-web-runtime-v1.py')
OPERATION = '11111111-1111-4111-8111-111111111111'
INPUTS = {'web/package.json': b'{"scripts":{"build":"tsc -b && vite build"}}',
          'web/package-lock.json': b'{"lockfileVersion":3}',
          'scripts/web-build.sh': b'#!/bin/bash\nnpm run build\n'}
def projection(files):
    return json.dumps({'schemaVersion': 1, 'files': {
        name: base64.b64encode(value).decode() for name, value in files.items()}})

class WebValidationTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'source'; source.mkdir()
        for name, value in INPUTS.items():
            path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
        (source / 'candidate-secret').write_text('NOT-A-NETWORK-BUILD-INPUT')
        return source

    def invoke(self, root, *, prepare_exit=0, build_exit=0, cleanup_exit=0, invalid_output=False):
        source = self.fixture(root); stage = root / 'artifacts'; stage.mkdir()
        calls = []; contexts = []
        def docker(prefix, args, timeout, output=None, capture=False):
            calls.append(args); code = 0; stdout = ''
            if args[0] == 'build':
                contexts.extend(p.relative_to(args[-1]).as_posix() for p in Path(args[-1]).rglob('*') if p.is_file())
            if args[:2] == ['image', 'inspect']: stdout = 'sha256:' + 'a' * 64
            if args[0] == 'create': stdout = 'b' * 64
            if '--prepare' in args: code = prepare_exit
            if './scripts/web-build.sh' in args:
                code = build_exit
                if code: output.write('error TS2322: synthetic candidate error\n'); output.flush()
            if '--export-static' in args:
                stdout = projection({'../outside': b'bad'}) if invalid_output else projection({'index.html': b'<html>fresh</html>', 'assets/app.js': b'fresh'})
            if args[0] == 'rm': code = cleanup_exit
            return subprocess.CompletedProcess(args, code, stdout)
        with contextlib.ExitStack() as stack:
            for name, filename in (('WEB_DOCKERFILE', 'atenea-web-validation-v1.Dockerfile'), ('WEB_RUNTIME', 'atenea-web-runtime-v1.py')):
                stack.enter_context(mock.patch.object(RUNNER, name, Path(__file__).with_name(filename)))
            stack.enter_context(mock.patch.object(RUNNER, 'WEB_INPUTS', {k:hashlib.sha256(v).hexdigest() for k,v in INPUTS.items()}))
            stack.enter_context(mock.patch.object(RUNNER, 'exact_regular_file', return_value=True))
            stack.enter_context(mock.patch.object(RUNNER, 'make_slot_readable'))
            stack.enter_context(mock.patch.object(RUNNER.pwd, 'getpwnam', return_value=SimpleNamespace(pw_gid=1101)))
            stack.enter_context(mock.patch.object(RUNNER, 'docker_call', side_effect=docker))
            with (root / 'output').open('w') as output:
                result = RUNNER.run_web(['runuser','-u','atenea-slot1','--','docker'], OPERATION, source,
                                        RUNNER.DEFINITIONS['WEB_BUILD'], stage, output)
        return result, calls, contexts

    def test_hash_locked_installed_tools_and_fixed_recipe(self):
        for filename, digest in (('atenea-web-validation-v1.Dockerfile', RUNNER.WEB_DOCKERFILE_SHA256),
                                 ('atenea-web-runtime-v1.py', RUNNER.WEB_RUNTIME_SHA256)):
            self.assertEqual(digest, RUNNER.sha256_file(Path(__file__).with_name(filename)))
        recipe = Path(__file__).with_name('atenea-web-validation-v1.Dockerfile').read_text()
        self.assertIn('@sha256:', recipe)
        self.assertIn('npm ci --ignore-scripts --no-audit --no-fund', recipe)
        self.assertNotIn('COPY . ', recipe)
        self.assertIn('ENV npm_config_userconfig=/dev/null', recipe)
        self.assertIn('ENV npm_config_globalconfig=/opt/atenea-npm-globalrc', recipe)
        self.assertEqual({k.split('/')[-1]:v for k,v in RUNNER.WEB_INPUTS.items() if k.startswith('web/')}, RUNTIME.MANIFESTS)

    def test_only_reviewed_inputs_reach_network_and_candidate_is_offline_nonroot(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls, contexts = self.invoke(Path(temporary))
        self.assertEqual(0, result.exit_code)
        self.assertEqual({'Dockerfile','package.json','package-lock.json','atenea-web-runtime-v1.py'}, set(contexts))
        build = next(c for c in calls if c[0]=='build')
        self.assertEqual('default', build[build.index('--network')+1])
        create = next(c for c in calls if c[0]=='create')
        self.assertEqual('none', create[create.index('--network')+1])
        self.assertEqual('1000:0', create[create.index('--user')+1])
        self.assertIn('--read-only',create); self.assertIn('ALL',create); self.assertIn('no-new-privileges',create)
        mounts = [create[i+1] for i,v in enumerate(create) if v=='--mount']
        self.assertEqual(1,len(mounts)); self.assertTrue(mounts[0].endswith('dst=/source,readonly'))
        rendered=' '.join(create)
        for forbidden in ('/home/jose','/etc/atenea-worker','docker.sock','--privileged','--env-file'):
            self.assertNotIn(forbidden,rendered)
        self.assertTrue(any('./scripts/web-build.sh' in c for c in calls))

    def test_mutated_manifests_scripts_configs_and_parent_symlinks_are_rejected(self):
        for bad in ('manifest','script','npmrc','shrinkwrap','symlink'):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary); source=self.fixture(root)
                with mock.patch.object(RUNNER,'WEB_INPUTS',{k:hashlib.sha256(v).hexdigest() for k,v in INPUTS.items()}):
                    self.assertIsNotNone(RUNNER.web_build_inputs(source))
                    if bad=='manifest': (source/'web/package.json').write_text('foreign')
                    if bad=='script': (source/'scripts/web-build.sh').write_text('foreign')
                    if bad=='npmrc': (source/'web/.npmrc').write_text('registry=https://foreign.invalid')
                    if bad=='shrinkwrap': (source/'web/npm-shrinkwrap.json').write_text('{}')
                    if bad=='symlink':
                        (source/'web').rename(source/'foreign'); (source/'web').symlink_to('foreign')
                    self.assertIsNone(RUNNER.web_build_inputs(source))

    def test_missing_tools_and_candidate_compiler_failures_are_distinguished(self):
        missing = RUNNER.classify_execution(127, '', 'WEB_BUILD')
        self.assertEqual(('TOOLCHAIN','INFRASTRUCTURE'), (missing.phase, missing.failure_class))
        with tempfile.TemporaryDirectory() as temporary:
            result,calls,_=self.invoke(Path(temporary),build_exit=2)
        self.assertEqual(('COMPILATION','CANDIDATE'),(result.phase,result.failure_class))
        self.assertTrue(any(c[0]=='rm' for c in calls))
        self.assertFalse(any('--export-static' in c for c in calls))

    def test_missing_or_foreign_installed_tools_reject_before_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=self.fixture(root); stage=root/'artifacts'; stage.mkdir()
            with mock.patch.object(RUNNER,'exact_regular_file',return_value=False), mock.patch.object(RUNNER,'docker_call') as docker:
                with (root/'output').open('w') as output:
                    result=RUNNER.run_web(['runuser','-u','atenea-slot1','--','docker'],OPERATION,source,RUNNER.DEFINITIONS['WEB_BUILD'],stage,output)
                self.assertEqual('INSTALLED_TOOLCHAIN_INVALID',result.error_code)
                docker.assert_not_called()

    def test_preparation_failure_is_infrastructure_and_always_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            result,calls,_=self.invoke(Path(temporary),prepare_exit=70)
        self.assertEqual('TEST_CACHE_INCOMPLETE',result.error_code)
        self.assertEqual('INFRASTRUCTURE',result.failure_class)
        self.assertFalse(any('./scripts/web-build.sh' in c for c in calls))
        self.assertTrue(any(c[0]=='rm' for c in calls))

    def test_foreign_export_and_cleanup_failure_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            result,_,_=self.invoke(Path(temporary),invalid_output=True)
            self.assertFalse((Path(temporary)/'outside').exists())
        self.assertEqual('WEB_BUILD_OUTPUT_INVALID',result.error_code)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(RUNNER.RuntimeFailure):
            self.invoke(Path(temporary),cleanup_exit=1)

    def test_exports_reject_traversal_absolute_paths_and_prefix_collisions_before_write(self):
        for files in ({'index.html':b'ok','../secret':b'no'}, {'index.html':b'ok','/etc/file':b'no'},
                      {'index.html':b'ok','assets':b'file','assets/x.js':b'child'}):
            with tempfile.TemporaryDirectory() as temporary:
                stage=Path(temporary)
                self.assertFalse(RUNNER.receive_web_static(projection(files),stage,1101))
                self.assertFalse((stage/'static').exists())

    def test_prepare_discards_candidate_caches_outputs_and_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); source=self.fixture(base); root=base/'work'; root.mkdir()
            deps=base/'deps'; deps.mkdir()
            for name in ('package.json','package-lock.json'): (deps/name).write_bytes(INPUTS['web/'+name])
            for name in ('typescript','vite','esbuild'): (deps/'node_modules'/name).mkdir(parents=True)
            (deps/'node_modules/.package-lock.json').write_text('{}')
            (source/'web/node_modules').mkdir(); (source/'web/node_modules/evil').write_text('old')
            (source/'web/tsconfig.app.tsbuildinfo').write_text('old')
            (source/'.env.production').write_text('secret')
            static=source/'src/main/resources/static'; static.mkdir(parents=True); (static/'index.html').write_text('old')
            hashes={k.split('/')[-1]:hashlib.sha256(v).hexdigest() for k,v in INPUTS.items() if k.startswith('web/')}
            with mock.patch.object(RUNTIME,'ROOT',root), mock.patch.object(RUNTIME,'SOURCE',source), mock.patch.object(RUNTIME,'DEPENDENCIES',deps), mock.patch.object(RUNTIME.os,'geteuid',return_value=1000), mock.patch.object(RUNTIME,'MANIFESTS',hashes):
                self.assertEqual(0,RUNTIME.prepare())
                self.assertEqual(64,RUNTIME.prepare())
            for name in ('web/node_modules/evil','web/tsconfig.app.tsbuildinfo','.env.production','src/main/resources/static/index.html'):
                self.assertFalse((root/'repo'/name).exists())
            self.assertTrue((root/'repo/web/node_modules/vite').is_dir())

    def test_export_rejects_symlinks_and_requires_fresh_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); static=root/'repo/src/main/resources/static'; static.mkdir(parents=True)
            with mock.patch.object(RUNTIME,'ROOT',root):
                self.assertEqual(64,RUNTIME.export_static())
                (static/'index.html').write_text('fresh')
                (static/'foreign.js').symlink_to('/etc/passwd')
                self.assertEqual(64,RUNTIME.export_static())

    def test_export_enforces_actual_byte_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); static=root/'repo/src/main/resources/static'; static.mkdir(parents=True)
            (static/'index.html').write_bytes(b'12345')
            with mock.patch.object(RUNTIME,'ROOT',root), mock.patch.object(RUNTIME,'MAX_STATIC_BYTES',4):
                self.assertEqual(64,RUNTIME.export_static())

if __name__=='__main__':
    unittest.main()
