#!/usr/bin/env python3
"""Closed installer recovery for the exact activated AX42 0.157.0 package.

No caller-selected paths, releases, identities or commands. Historical stage,
activation and inventory evidence is preserved byte-for-byte. No canary run.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import grp
import pwd
import stat
import subprocess
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True

ROOT = Path('/srv/atenea/worker/codex-releases-v1')
REGISTRY = Path('/etc/atenea-worker/codex-release-stage-v1.json')
EXECUTIONS = Path('/srv/atenea/worker/agent-runs-v1/executions.json')
RECEIPT = Path('/srv/atenea/release-v1/codex-runtime-access-v1.json')
CURRENT = 'releases/0.157.0-c30a04c5791c1953'
PREVIOUS = 'releases/0.145.0-56da3312ccb2109a'
CANDIDATE = '1d586e4a-0409-453a-9ea9-762e99d1438a'
PLAN = '5494d0d2-000d-412a-81b0-163d67151095'
ARCHIVE_SHA = 'c30a04c5791c19534ba5d2586a63b3766272951e559ea0056cc5192b03d3abc9'
MANIFEST_SHA = '4a0bf195bdcf65d9cd219a8c1b7326791814da3c744d762e339a25ee1619927f'
SCHEMA_SHA = '4f8862adb294f9d6714fe5ede5f056974210d1fab7275c746f55298f455ce70e'
CATALOG = '1372647bd09888c3305147b9a7cf6889b5b4526e04d332971f7e3a43ccb7efc7'
VERSION = 'codex-cli 0.157.0'
USER = 'jose'
GROUP = 'atenea'
STAGE_PATH = Path(__file__).with_name('codex-release-stage-v1.py')
STAGE_SHA = '43a769e8c5c1944e7a8a07d2c5c7c60f112e091a1adfe264c5945f94214a75d1'

def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def regular(path, owner):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        and info.st_uid == owner and not info.st_mode & 0o022, 'UNSAFE_RECORD')
    return json.loads(path.read_bytes())

def stage_module():
    require(digest(STAGE_PATH) == STAGE_SHA and not STAGE_PATH.is_symlink(), 'STAGE_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location('reviewed_stage', STAGE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def protected():
    paths = sorted(ROOT.rglob('*.json'))
    require(len(paths) < 2000, 'EVIDENCE_LIMIT')
    values = {}
    for path in [REGISTRY, *paths]:
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'EVIDENCE_TYPE_CHANGED')
        values[str(path)] = digest(path)
    values['current'] = os.readlink(ROOT / 'current')
    values['previous'] = os.readlink(ROOT / 'previous')
    return values

def inspect():
    require(os.geteuid() == 0, 'ROOT_REQUIRED')
    owner = pwd.getpwnam('atenea-worker').pw_uid
    group = grp.getgrnam(GROUP).gr_gid
    stage = stage_module()
    for path, uid in ((ROOT,0), (ROOT/'releases',owner)):
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
            and info.st_gid == group and stat.S_IMODE(info.st_mode) == 0o750, 'ROOT_IDENTITY_CHANGED')
    for name, expected in (('current',CURRENT),('previous',PREVIOUS)):
        path = ROOT/name
        require(path.is_symlink() and path.lstat().st_uid == 0
            and os.readlink(path) == expected, 'LINK_IDENTITY_CHANGED')
    state = regular(EXECUTIONS, owner)
    require(not any(item['status'] not in ('SUCCEEDED','FAILED','CANCELLED')
        for item in state['executions'].values()), 'ACTIVE_AGENT_RUN')
    require(not any(item['state'] not in ('SUCCEEDED','CANDIDATE_FAILED','INFRASTRUCTURE_FAILED',
        'POLICY_FAILED','VALIDATION_FAILED','OWNERSHIP_FAILED','CANCELLED')
        for item in state.get('validations',{}).values()), 'ACTIVE_VALIDATION')
    registry = regular(REGISTRY,0)
    candidate = {'planId':PLAN,'candidateId':CANDIDATE,'codexVersion':'0.157.0',
        'releaseDigestSha256':ARCHIVE_SHA,'catalogRevision':CATALOG}
    require(registry['schemaVersion']=='codex-release-stage-v1' and registry['workerId']=='ax42-01'
        and registry['candidates'].get(CANDIDATE)==candidate, 'CANDIDATE_CHANGED')
    archive = ROOT/'inbox'/ (CANDIDATE+'.tar.gz')
    info = archive.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==0
        and not info.st_mode & 0o022 and digest(archive)==ARCHIVE_SHA, 'ARCHIVE_CHANGED')
    matches = []
    for path in (ROOT/'operations').glob('*.json'):
        result = regular(path,owner).get('result',{})
        if result.get('planId')==PLAN and result.get('candidateId')==CANDIDATE:
            require(result.get('state')=='STAGED' and result.get('releaseDigestSha256')==ARCHIVE_SHA
                and result.get('releaseManifestSha256')==MANIFEST_SHA
                and result.get('schemaManifestSha256')==SCHEMA_SHA
                and result.get('catalogRevision')==CATALOG, 'STAGE_EVIDENCE_CHANGED')
            matches.append(result)
    require(matches, 'STAGE_EVIDENCE_MISSING')
    activations = [regular(path,0).get('result',{}) for path in (ROOT/'activations').glob('*.json')]
    require(len(activations)==1 and activations[0].get('planId')==PLAN
        and activations[0].get('candidateId')==CANDIDATE
        and activations[0].get('state')=='ACTIVATED'
        and activations[0].get('releaseDigestSha256')==ARCHIVE_SHA, 'ACTIVATION_EVIDENCE_CHANGED')
    release = ROOT/CURRENT
    entries = stage.runtime_access_entries(release,owner,group)
    require(stage.release_manifest(release)==MANIFEST_SHA, 'PACKAGE_CONTENT_CHANGED')
    return stage, release, entries, protected()

def persist(value):
    parent = RECEIPT.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid==0
        and stat.S_IMODE(parent.st_mode)==0o700, 'RECEIPT_AUTHORITY_CHANGED')
    fd, name = tempfile.mkstemp(prefix='.codex-access-',dir=RECEIPT.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            os.fchmod(stream.fileno(),0o600)
            stream.write((json.dumps(value,sort_keys=True)+'\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name,RECEIPT)
        descriptor = os.open(RECEIPT.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if os.path.exists(name): os.unlink(name)

def runtime_probe():
    # Only --version. No project, prompt, auth directory, other releases or canary.
    current = str(ROOT/'current')
    command = ['/usr/bin/systemd-run','--wait','--pipe','--collect','--quiet','--service-type=exec',
        '--unit','atenea-codex-access-'+uuid.uuid4().hex,
        '--property','User='+USER,'--property','Group='+GROUP,'--property','NoNewPrivileges=yes',
        '--property','PrivateDevices=yes','--property','RestrictSUIDSGID=yes',
        '--property','ProtectKernelModules=yes','--property','ProtectControlGroups=yes',
        '--property','LockPersonality=yes','--','/usr/bin/bwrap','--die-with-parent','--new-session',
        '--unshare-all','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
        '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib',
        '--symlink','usr/lib64','/lib64','--dir','/srv','--dir','/srv/atenea','--dir','/srv/atenea/worker',
        '--dir',str(ROOT),'--ro-bind',current,current,current+'/bin/codex','--version']
    result = subprocess.run(command,capture_output=True,text=True,timeout=30)
    require(result.returncode==0 and result.stdout.strip()==VERSION, 'EXECUTION_IDENTITY_PROBE_FAILED')

def operate(action):
    stage,release,entries,evidence = inspect()
    saved = regular(RECEIPT,0) if RECEIPT.exists() or RECEIPT.is_symlink() else None
    if saved:
        require(saved.get('protocol')=='codex-runtime-access/v1'
            and saved.get('current')==CURRENT and saved.get('protected')==evidence
            and saved.get('state') in ('APPLYING','SUCCEEDED'), 'RECEIPT_CONFLICT')
        original = saved['entries']
        require([{k:v for k,v in e.items() if k!='beforeMode'} for e in original]
            == [{k:v for k,v in e.items() if k!='beforeMode'} for e in entries], 'RETAINED_TREE_CHANGED')
    else:
        original = entries
    if action=='plan':
        return {'state':'READY','current':CURRENT,'previous':PREVIOUS,
            'permissionChanges':sum(e['beforeMode']!=e['afterMode'] for e in entries),
            'linksChanged':False,'versionsChanged':False}
    if action=='verify':
        require(all(e['beforeMode']==e['afterMode'] for e in entries), 'RUNTIME_MODES_NOT_READY')
        require(saved and saved['state']=='SUCCEEDED', 'DURABLE_RECEIPT_REQUIRED')
        runtime_probe()
        return {'state':'VERIFIED','codexVersion':VERSION,'runtimeIdentity':USER+':'+GROUP,
            'operationId':saved['operationId'],'linksChanged':False}
    if saved and saved['state']=='SUCCEEDED':
        require(all(e['beforeMode']==e['afterMode'] for e in entries), 'RUNTIME_MODES_CHANGED')
        runtime_probe()
        return {'state':'SUCCEEDED','operationId':saved['operationId'],'replayed':True}
    record = saved or {'protocol':'codex-runtime-access/v1','operationId':str(uuid.uuid4()),
        'current':CURRENT,'previous':PREVIOUS,'entries':original,'protected':evidence}
    record['state']='APPLYING'
    persist(record)
    try:
        stage.set_runtime_modes(release,original)
        runtime_probe()
        require(protected()==evidence,'PROTECTED_STATE_CHANGED')
    except Exception:
        stage.set_runtime_modes(release,original,restore=True)
        record['state']='ROLLED_BACK'; persist(record)
        raise
    record['state']='SUCCEEDED';persist(record)
    return {'state':'SUCCEEDED','operationId':record['operationId'],'replayed':False,
        'codexVersion':VERSION,'runtimeIdentity':USER+':'+GROUP,'linksChanged':False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=('plan','apply','verify'))
    args = parser.parse_args()
    try:
        print(json.dumps(operate(args.action),sort_keys=True))
    except Exception as error:
        print(json.dumps({'state':'REJECTED','reason':str(error)}))
        raise SystemExit(2)

if __name__=='__main__':
    main()
