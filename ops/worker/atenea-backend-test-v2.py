#!/usr/bin/env python3
"""Fixed preparation inside the isolated BACKEND_TEST container, never on AX42."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/work")
SOURCE = Path("/source")
CACHE = Path("/opt/atenea-m2")
PG_BIN = Path("/usr/lib/postgresql/16/bin")


def prepare() -> int:
    if os.geteuid() == 0 or not SOURCE.is_dir() or SOURCE.is_symlink():
        return 64
    if any((ROOT / name).exists() or (ROOT / name).is_symlink()
           for name in ("repo", "m2", "postgres", "pgsocket", "home")):
        return 64
    (ROOT / "home").mkdir(mode=0o700)
    (ROOT / "pgsocket").mkdir(mode=0o700)
    # Test only candidate source: never adopt a host Git pointer or stale
    # compiled outputs/caches as evidence of a fresh Maven build.
    def ignore(directory: str, names: list[str]) -> list[str]:
        relative = Path(directory).relative_to(SOURCE).as_posix()
        if relative == ".":
            return [name for name in names if name in {".git", "target"}]
        if relative == "android":
            return [name for name in names if name in {".cache", ".gradle", "build"}]
        if relative.startswith("android/") and relative.count("/") == 1:
            return [name for name in names if name == "build"]
        return []

    shutil.copytree(SOURCE, ROOT / "repo", symlinks=True, ignore=ignore)
    shutil.copytree(CACHE, ROOT / "m2")
    # No caller can select a database, path, port, command or credential.
    commands = (
        [str(PG_BIN / "initdb"), "-D", str(ROOT / "postgres"),
         "--username=atenea", "--auth=trust", "--no-locale", "--encoding=UTF8"],
        [str(PG_BIN / "pg_ctl"), "-D", str(ROOT / "postgres"),
         "-l", str(ROOT / "postgres.log"), "-w", "-t", "30",
         "-o", "-h 127.0.0.1 -p 5432 -k /work/pgsocket", "start"],
        [str(PG_BIN / "createdb"), "-h", "127.0.0.1", "-p", "5432",
         "-U", "atenea", "atenea_test"],
    )
    for command in commands:
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, check=False, timeout=45)
        if completed.returncode != 0:
            return 70
    return 0


def main() -> int:
    if sys.argv[1:] != ["--prepare"]:
        return 64
    try:
        return prepare()
    except (OSError, subprocess.SubprocessError):
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
