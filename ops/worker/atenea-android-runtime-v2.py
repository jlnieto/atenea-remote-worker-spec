#!/usr/bin/env python3
"""Fixed, image-internal Android seeding/sealing/preparation; no caller paths."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath

SOURCE = Path("/source")
ROOT = Path("/work")
BUILD_CACHE = Path("/opt/atenea-build-gradle/caches/modules-2")
CACHE = Path("/opt/atenea-android-cache-v2")
MODULES = {"app": "app", "api": "api", "secure": "secure",
           "core-console": "coreconsole", "voice-runtime": "voiceruntime"}
MAX_FILES = 60000
MAX_BYTES = 3 * 1024 ** 3


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and path.as_posix() == name
            and all(part not in {".", ".."} for part in path.parts)
            and "\\" not in name and len(name) <= 1024)


def files(root: Path, *, root_owned: bool = False) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("cache directory is invalid")
    observed_root = root.lstat()
    if root_owned and (observed_root.st_uid != 0 or observed_root.st_gid != 0 or observed_root.st_mode & 0o022):
        raise ValueError("cache directory ownership is invalid")
    result = []
    total = 0
    for directory, children, names in os.walk(root, followlinks=False):
        for name in children + names:
            path = Path(directory) / name
            observed = path.lstat()
            if not (stat.S_ISREG(observed.st_mode) or stat.S_ISDIR(observed.st_mode)):
                raise ValueError("cache contains non-regular objects")
            if root_owned and (observed.st_uid != 0 or observed.st_gid != 0 or observed.st_mode & 0o022):
                raise ValueError("cache ownership is invalid")
            if stat.S_ISREG(observed.st_mode):
                if observed.st_nlink != 1 or not safe_name(path.relative_to(root).as_posix()):
                    raise ValueError("cache file is invalid")
                result.append(path)
                total += observed.st_size
                if len(result) > MAX_FILES or total > MAX_BYTES:
                    raise ValueError("cache exceeds its fixed bound")
    return sorted(result)


def seed() -> None:
    if os.geteuid() != 0 or SOURCE.is_symlink():
        raise ValueError("seeding is restricted to the trusted image build")
    for module, package in MODULES.items():
        base = SOURCE / "android" / module / "src"
        main = base / "main"
        code = main / "kotlin" / "com" / "atenea" / "validationseed" / package
        code.mkdir(parents=True)
        application = '<application android:label="Atenea validation seed"/>' if module == "app" else ""
        (main / "AndroidManifest.xml").write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            + application + '</manifest>\n', encoding="utf-8")
        (code / "DependencyCacheProbe.kt").write_text(
            f"package com.atenea.validationseed.{package}\ninternal class DependencyCacheProbe\n",
            encoding="utf-8")
        # secure has no declared test framework; its empty test task is still
        # selected. Other modules exercise the exact declared JUnit runtime.
        if module != "secure":
            test = base / "test" / "kotlin"
            test.mkdir(parents=True)
            (test / "DependencyCacheProbeTest.kt").write_text(
                f"package com.atenea.validationseed.{package}\n"
                "class DependencyCacheProbeTest {\n"
                "  @kotlin.test.Test fun cacheIsUsable() { kotlin.test.assertTrue(true) }\n}\n",
                encoding="utf-8")


def seal() -> None:
    if os.geteuid() != 0 or CACHE.exists() or CACHE.is_symlink():
        raise ValueError("sealing requires a fresh trusted image build")
    observed = files(BUILD_CACHE)
    selected = [path for path in observed if not path.name.endswith(".lock") and path.name != "gc.properties"]
    if not selected:
        raise ValueError("empty dependency cache")
    CACHE.mkdir(mode=0o755)
    entries = {}
    for source in selected:
        name = source.relative_to(BUILD_CACHE).as_posix()
        destination = CACHE / "modules-2" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o644)
        entries["modules-2/" + name] = digest(destination)
    manifest = {"schemaVersion": 1, "gradleVersion": "8.10.2", "files": entries}
    (CACHE / "cache-manifest-v1.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    for directory, _children, _names in os.walk(CACHE):
        Path(directory).chmod(0o755)
    (CACHE / "cache-manifest-v1.json").chmod(0o644)


def verified_cache() -> list[Path]:
    observed = files(CACHE, root_owned=True)
    manifest_path = CACHE / "cache-manifest-v1.json"
    if manifest_path not in observed or manifest_path.stat().st_size > 16 * 1024 ** 2:
        raise ValueError("cache manifest is invalid")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (set(manifest) != {"schemaVersion", "gradleVersion", "files"}
            or manifest["schemaVersion"] != 1 or manifest["gradleVersion"] != "8.10.2"
            or not isinstance(manifest["files"], dict) or not manifest["files"]):
        raise ValueError("cache manifest is conflicting")
    entries = manifest["files"]
    actual = {path.relative_to(CACHE).as_posix(): path for path in observed if path != manifest_path}
    if set(entries) != set(actual):
        raise ValueError("cache inventory is conflicting")
    for name, expected in entries.items():
        if (not safe_name(name) or not name.startswith("modules-2/")
                or not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None
                or digest(actual[name]) != expected):
            raise ValueError("cache integrity is invalid")
    return list(actual.values())


def prepare() -> None:
    if os.geteuid() == 0 or SOURCE.is_symlink() or not SOURCE.is_dir():
        raise ValueError("candidate preparation requires the isolated non-root runtime")
    if any((ROOT / name).exists() or (ROOT / name).is_symlink()
           for name in ("repo", "gradle-home", "android-home", "home")):
        raise ValueError("runtime must be fresh")
    entries = verified_cache()
    for name in ("gradle-home", "android-home", "home"):
        (ROOT / name).mkdir(mode=0o700)
    # Only dependency artifacts/metadata are copied. No init scripts, global
    # properties, credentials, daemon state or task-output caches are adopted.
    for source in entries:
        destination = ROOT / "gradle-home" / "caches" / source.relative_to(CACHE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o600)
    # A candidate's old build outputs cannot satisfy a new validation.
    def ignore(directory: str, names: list[str]) -> list[str]:
        relative = Path(directory).relative_to(SOURCE).as_posix()
        if relative == ".":
            return [name for name in names if name == ".git"]
        if relative == "android" or relative in {"android/" + name for name in MODULES}:
            return [name for name in names if name in {".gradle", ".cache", "build", "local.properties"}]
        return []
    shutil.copytree(SOURCE, ROOT / "repo", symlinks=True, ignore=ignore)


def main() -> int:
    actions = {"--seed": seed, "--seal": seal, "--prepare": prepare}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        return 64
    try:
        actions[sys.argv[1]]()
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print("Android validation preparation rejected", file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
