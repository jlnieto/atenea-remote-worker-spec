#!/usr/bin/python3
"""Fixed offline preparation/export inside the rootless web test container."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path('/work')
SOURCE = Path('/source')
DEPENDENCIES = Path('/opt/atenea-web-deps')
MANIFESTS = {
    'package.json': '6dff9531573c26f3143cfbf8849308dded874d13362a686517c7dd2f9383a5f3',
    'package-lock.json': '62ea4d444da58e7e27bd83cb53ebcf49bcc9bf27dd5641e3d12ed8dd86ff21bc',
}
MAX_STATIC_BYTES = 16 * 1024 * 1024
MAX_STATIC_FILES = 512

def manifests_match(root: Path) -> bool:
    return all(not (root / name).is_symlink() and (root / name).is_file()
               and hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
               for name, digest in MANIFESTS.items())

def prepare() -> int:
    if os.geteuid() == 0 or not SOURCE.is_dir() or SOURCE.is_symlink():
        return 64
    if (SOURCE / 'web').is_symlink() or not manifests_match(SOURCE / 'web'):
        return 64
    if not manifests_match(DEPENDENCIES):
        return 70
    for name in ('repo', 'home'):
        if (ROOT / name).exists() or (ROOT / name).is_symlink():
            return 64
    for name in ('typescript', 'vite', 'esbuild'):
        if not (DEPENDENCIES / 'node_modules' / name).is_dir():
            return 70
    (ROOT / 'home').mkdir(mode=0o700)
    # Never reuse candidate node_modules, built output, npmrc, Git pointers or
    # compiler caches as evidence of a fresh build. Candidate code stays offline.
    def ignore(directory: str, names: list[str]) -> list[str]:
        return [name for name in names if name in {
            '.git', 'node_modules', 'target', '.npmrc', '.npm', '.env',
        } or name.startswith('.env.') or name.endswith('.tsbuildinfo')]
    repo = ROOT / 'repo'
    shutil.copytree(SOURCE, repo, symlinks=True, ignore=ignore)
    static = repo / 'src/main/resources/static'
    if any(path.is_symlink() for path in (repo / 'web', repo / 'src',
                                         repo / 'src/main', repo / 'src/main/resources', static)):
        return 64
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(DEPENDENCIES / 'node_modules', repo / 'web/node_modules', symlinks=True)
    # This marker now represents exactly the checked lockfile, not a candidate
    # cache. Avoid a reinstall caused only by checkout/copy timestamp differences.
    os.utime(repo / 'web/node_modules/.package-lock.json', None)
    return 0

def export_static() -> int:
    static = ROOT / 'repo/src/main/resources/static'
    if static.is_symlink() or not static.is_dir():
        return 64
    files = {}
    total = 0
    for path in sorted(static.rglob('*')):
        observed = path.lstat()
        if stat.S_ISDIR(observed.st_mode):
            continue
        if not stat.S_ISREG(observed.st_mode):
            return 64
        if observed.st_size > MAX_STATIC_BYTES - total or len(files) >= MAX_STATIC_FILES:
            return 64
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return 64
            data = stream.read(MAX_STATIC_BYTES - total + 1)
        total += len(data)
        if total > MAX_STATIC_BYTES:
            return 64
        files[path.relative_to(static).as_posix()] = base64.b64encode(data).decode('ascii')
    if not files.get('index.html'):
        return 64
    print(json.dumps({'schemaVersion': 1, 'files': files}, separators=(',', ':')))
    return 0

def main() -> int:
    action = {'--prepare': prepare, '--export-static': export_static}
    if len(sys.argv) != 2 or sys.argv[1] not in action:
        return 64
    try:
        return action[sys.argv[1]]()
    except (OSError, ValueError):
        return 70

if __name__ == '__main__':
    raise SystemExit(main())
