#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
from pathlib import Path

if __name__ == "__main__":
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch("[0-9a-f]{40}", source):
        raise SystemExit("Invalid source identity")
    root = Path("target/release-platform")
    sha = hashlib.sha256()
    with (root / "platform.tar").open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""): sha.update(block)
    (root / "manifest.json").write_text(json.dumps({"protocol": "atenea-release/v1",
        "target": "AX42_PLATFORM", "sourceCommit": source, "payloadSha256": sha.hexdigest(),
        "versionCode": None, "versionName": None, "flywayVersion": None}, sort_keys=True, separators=(",", ":")) + "\n")
