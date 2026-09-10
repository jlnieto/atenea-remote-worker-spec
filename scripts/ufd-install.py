#!/usr/bin/env python3
"""Install the pinned immutable UFD release outside this checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def gh_json(endpoint):
    return json.loads(subprocess.check_output(["gh", "api", endpoint]))


def main(base, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    lock = json.loads(subprocess.check_output(["git", "show", f"{base}:.delivery/engine-lock.json"]))
    release = gh_json(f"repos/{lock['repository']}/releases/{lock['release_id']}")
    require(release["immutable"] and release["tag_name"] == lock["tag"], "release-not-immutable")
    tag = gh_json(f"repos/{lock['repository']}/git/ref/tags/{lock['tag']}")["object"]
    require(tag["type"] == "commit" and tag["sha"] == lock["commit"], "tag-commit-mismatch")
    asset = next(item for item in release["assets"] if item["id"] == lock["asset_id"])
    require(asset["name"] == lock["filename"] and asset["digest"] == "sha256:" + lock["sha256"], "asset-mismatch")
    wheel = destination / lock["filename"]
    with wheel.open("wb") as stream:
        subprocess.run(["gh", "api", f"repos/{lock['repository']}/releases/assets/{asset['id']}",
                        "-H", "Accept: application/octet-stream"], check=True, stdout=stream)
    require(hashlib.sha256(wheel.read_bytes()).hexdigest() == lock["sha256"], "wheel-digest-mismatch")
    subprocess.run([sys.executable, "-m", "venv", str(destination / "venv")], check=True)
    python = str(destination / "venv/bin/python")
    subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:", str(wheel)], check=True)
    info = json.loads(subprocess.check_output([python, "-I", "-m", "delivery.cli", "--engine-info", "--engine-wheel", str(wheel)]))
    require(info == {"version": lock["version"], "digest": "sha256:" + lock["sha256"]}, "engine-install-mismatch")
    print(json.dumps({"python": python, "wheel": str(wheel), "engine": info}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    main(args.base, args.destination)
