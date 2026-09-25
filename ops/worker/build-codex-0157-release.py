#!/usr/bin/env python3
"""Package the official 0.157.0 musl binary for Atenea's managed release stage."""

import argparse
import gzip
import hashlib
import json
import os
import stat
import tarfile
from pathlib import Path


VERSION = "0.157.0"
BIN_SHA256 = "1a822376d4634ac32dddc030e5117c63359f7f8cd4b1b64382c68190287d0258"
GATES = ("generate-schemas", "run-focused-contracts", "health-check", "run-canary")
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_file(bundle: tarfile.TarFile, path: Path, name: str, mode: int) -> int:
    info = tarfile.TarInfo(name)
    info.size = path.stat().st_size
    info.mode = mode
    info.uid = info.gid = info.mtime = 0
    with path.open("rb") as source:
        bundle.addfile(info, source)
    return info.size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("official_package", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    source = args.official_package.resolve(strict=True)
    archive = args.archive.resolve()
    if archive.is_relative_to(source) or archive.exists():
        raise ValueError("archive path must be new and outside the source package")
    manifest = json.loads((source / "codex-package.json").read_text(encoding="utf-8"))
    if (manifest.get("version") != VERSION
            or manifest.get("target") != "x86_64-unknown-linux-musl"
            or manifest.get("entrypoint") != "bin/codex"
            or sha256(source / "bin" / "codex") != BIN_SHA256):
        raise ValueError("official Codex 0.157.0 package identity differs")
    gate = Path(__file__).with_name("codex-0157-release-gate.py")
    if not gate.is_file():
        raise ValueError("release gate source is unavailable")
    total = 0
    with archive.open("wb") as output, gzip.GzipFile(
            filename="", mode="wb", fileobj=output, mtime=0) as compressed, \
            tarfile.open(fileobj=compressed, mode="w") as bundle:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source).as_posix()
            mode = path.lstat().st_mode
            if relative == "codex" and stat.S_ISLNK(mode) and os.readlink(path) == "bin/codex":
                continue
            if stat.S_ISDIR(mode):
                info = tarfile.TarInfo(relative)
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                info.uid = info.gid = info.mtime = 0
                bundle.addfile(info)
            elif stat.S_ISREG(mode):
                total += add_file(bundle, path, relative, 0o700 if mode & 0o111 else 0o600)
            else:
                raise ValueError(f"unsupported official package member: {relative}")
        for name in GATES:
            total += add_file(bundle, gate, "bin/" + name, 0o700)
    if total > MAX_EXTRACTED_BYTES or archive.stat().st_size > MAX_ARCHIVE_BYTES:
        archive.unlink()
        raise ValueError("managed release exceeds stage size policy")
    print(json.dumps({"version": VERSION, "sha256": sha256(archive),
                      "archiveBytes": archive.stat().st_size}, sort_keys=True))


if __name__ == "__main__":
    main()
