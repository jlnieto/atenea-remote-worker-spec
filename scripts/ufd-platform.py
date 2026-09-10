#!/usr/bin/env python3
"""Execute the isolated Atenea platform UFD T1 pilot."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from contract_checks.validate import ContractError, digest, loads, require, validate_policy, validate_result
from delivery.cli import classify, snapshot_policy
from delivery.git import Git


POLICY = ".delivery/policy.json"
SELECTED_GROUP = "codex-session-negative-contract"
EXPECTED_TEST_COUNT = 5
TEST_COMMAND = ["python3", "ops/worker/test-codex-session-operations-contract-v1.py"]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def plan(base, head, wheel, output):
    git = Git(".")
    base, head = git.resolve(base), git.resolve(head)
    require(git.resolve("HEAD") == head, "checkout-head-mismatch")
    result, policy = classify(".", base, head, POLICY, runner="platform-local", engine_wheel=wheel)
    require(result["evaluation"]["state"] == "evaluated", "unevaluable-plan")
    output.mkdir(parents=True, exist_ok=True)
    write(output / "plan.json", result)
    write(output / "policy.json", policy)
    write(output / "context.json", {"base": base, "head": head, "wheel": str(Path(wheel).resolve())})
    print(json.dumps({"tier": result["tier"], "tests": result["blocking_tests"]["ids"]}))


def run(output):
    context = json.loads((output / "context.json").read_text())
    policy = loads((output / "policy.json").read_bytes())
    result = loads((output / "plan.json").read_bytes())
    validate_policy(policy)
    require(Git(".").resolve("HEAD") == context["head"], "checkout-head-mismatch")
    require(digest(policy) == result["policy_digest"], "policy-digest-mismatch")
    require(result["evaluation"]["state"] == "evaluated", "unevaluable-plan")
    require(result["tier"] == "T1", "unsupported-tier")
    groups = result["blocking_tests"]["ids"]
    require(groups == [SELECTED_GROUP], "unsupported-test-group")
    require(result["required_checks"]["ids"] == ["ufd-policy"], "unsupported-check")
    definition = policy["test_groups"].get(SELECTED_GROUP)
    require(definition is not None, "missing-test-group")
    require(definition["operation"] == "python-unittest", "unsupported-test-operation")
    require(definition["selectors"] == [{"kind": "file", "value": TEST_COMMAND[1]}], "unsupported-selector")
    require(definition["expected_count"] == {"state": "known", "value": EXPECTED_TEST_COUNT, "basis": "unittest-summary"}, "unexpected-test-count")

    completed = subprocess.run(TEST_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require(completed.returncode == 0, "failed-tests")
    match = re.search(r"Ran (\d+) tests? in ", completed.stdout)
    require(match is not None and int(match.group(1)) == EXPECTED_TEST_COUNT, "empty-selector")
    require(re.search(r"^OK$", completed.stdout, re.MULTILINE) is not None, "failed-tests")
    evidence = {
        "schema_version": 1,
        "plan_digest": digest(result),
        "input_digest": result["input_digest"],
        "state": "passed",
        "executions": [{
            "kind": "check", "id": "ufd-policy", "status": "passed", "exit_code": 0,
            "selectors": [],
            "test_count": {"state": "unknown", "basis": "not_reported"},
            "duration_ms": {"state": "unknown", "basis": "not_calibrated"}
        }, {
            "kind": "test", "id": SELECTED_GROUP, "status": "passed", "exit_code": 0,
            "selectors": [{"kind": "file", "value": TEST_COMMAND[1], "matches": EXPECTED_TEST_COUNT}],
            "test_count": {"state": "known", "value": EXPECTED_TEST_COUNT, "basis": "unittest-summary"},
            "duration_ms": {"state": "unknown", "basis": "not_calibrated"}
        }],
        "phases": [], "artifacts": [],
        "smoke": {"state": "not_applicable", "executed": []},
        "fallback": {"state": "not_used", "from_tier": "T1", "to_tier": "T1", "reason": "none"},
        "errors": []
    }
    validate_result(evidence, result, policy)
    write(output / "result.json", evidence)
    print(json.dumps({"state": "passed", "tier": "T1", "executions": [SELECTED_GROUP]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "run"))
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--wheel")
    parser.add_argument("--output", type=Path, default=Path("target/ufd"))
    args = parser.parse_args()
    try:
        if args.command == "plan":
            require(args.base and args.wheel, "missing-plan-input")
            plan(args.base, args.head, args.wheel, args.output)
        else:
            run(args.output)
    except ContractError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
