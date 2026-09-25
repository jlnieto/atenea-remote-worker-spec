#!/usr/bin/env python3
"""Version-bound local gates bundled with the managed Codex 0.157.0 release."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = "0.157.0"
BIN_SHA256 = "1a822376d4634ac32dddc030e5117c63359f7f8cd4b1b64382c68190287d0258"
RELEASE = Path(__file__).resolve().parent.parent
CODEX = RELEASE / "bin" / "codex"
REQUIRED_EXEC_OPTIONS = (
    "--ignore-user-config", "--ignore-rules", "--model", "--config",
    "--sandbox", "--json", "--output-last-message",
)


def run(*arguments: str) -> str:
    result = subprocess.run(
        [str(CODEX), *arguments], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=45, check=True, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    return result.stdout


def check_package() -> None:
    package = json.loads((RELEASE / "codex-package.json").read_text(encoding="utf-8"))
    if (package.get("version") != VERSION
            or package.get("target") != "x86_64-unknown-linux-musl"
            or package.get("entrypoint") != "bin/codex"
            or not CODEX.is_file()):
        raise ValueError("managed package identity differs")
    hasher = hashlib.sha256()
    with CODEX.open("rb") as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != BIN_SHA256 or run("--version").strip() != f"codex-cli {VERSION}":
        raise ValueError("managed Codex binary differs")


def check_exec_contract() -> str:
    help_text = run("exec", "--help")
    if any(option not in help_text for option in REQUIRED_EXEC_OPTIONS):
        raise ValueError("required Codex exec option is absent")
    return hashlib.sha256(help_text.encode("utf-8")).hexdigest()


def generate_schemas(output: Path) -> None:
    check_package()
    cli_help_digest = check_exec_contract()
    with tempfile.TemporaryDirectory(prefix="codex-0157-schemas-") as temporary:
        run("app-server", "generate-json-schema", "--out", temporary)
        source = Path(temporary) / "codex_app_server_protocol.schemas.json"
        app_schema = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(app_schema, dict):
        raise ValueError("generated app-server schema is invalid")
    app_schema["x-codex-version"] = VERSION
    cli_schema = {
        "type": "object",
        "x-codex-version": VERSION,
        "x-codex-exec-help-sha256": cli_help_digest,
        "properties": {
            "model": {"type": "string"},
            "reasoningEffort": {"enum": ["low", "medium", "high", "xhigh", "max"]},
        },
        "required": ["model", "reasoningEffort"],
    }
    for name, value in (("app-server.schema.json", app_schema),
                        ("cli.schema.json", cli_schema)):
        (output / name).write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )


def check_schemas() -> None:
    generated = RELEASE / "generated-schemas"
    for name in ("app-server.schema.json", "cli.schema.json"):
        data = json.loads((generated / name).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("x-codex-version") != VERSION:
            raise ValueError("staged schema version differs")
    cli = json.loads((generated / "cli.schema.json").read_text(encoding="utf-8"))
    if cli.get("x-codex-exec-help-sha256") != check_exec_contract():
        raise ValueError("staged CLI contract differs")


def main() -> None:
    gate = Path(sys.argv[0]).name
    if gate == "generate-schemas" and len(sys.argv) == 2:
        generate_schemas(Path(sys.argv[1]))
    elif gate == "run-focused-contracts" and len(sys.argv) == 1:
        check_package()
        check_schemas()
    elif gate == "health-check" and len(sys.argv) == 1:
        check_package()
        if (RELEASE.parent.parent / "current").resolve(strict=True) != RELEASE:
            raise ValueError("managed current link differs")
    elif gate == "run-canary" and len(sys.argv) == 1:
        check_package()
        check_schemas()
        if run("app-server", "generate-json-schema", "--help").find("--out") < 0:
            raise ValueError("app-server schema command is unavailable")
    else:
        raise ValueError("unknown release gate")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"Codex 0.157.0 release gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
