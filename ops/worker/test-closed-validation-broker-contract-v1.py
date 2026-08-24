#!/usr/bin/env python3

import json
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - AX42 intentionally validates elsewhere
    Draft202012Validator = None
    FormatChecker = None


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "runtime-contract"


class ClosedValidationBrokerContractTest(unittest.TestCase):
    def setUp(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed")
        self.schemas = {
            name: json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))
            for name in (
                "closed-validation-start-v1.request.schema.json",
                "closed-validation-inspect-v1.request.schema.json",
                "closed-validation-cancel-v1.request.schema.json",
                "closed-validation-operation-v1.schema.json",
            )
        }
        for schema in self.schemas.values():
            Draft202012Validator.check_schema(schema)

        self.exact = {
            "schemaVersion": 1,
            "protocolVersion": "closed-validation-broker/v1",
            "operationId": "11111111-1111-4111-8111-111111111111",
            "sessionId": "22222222-2222-4222-8222-222222222222",
            "workspaceIdentity": (
                "remote:ax42-01:work-session:22222222-2222-4222-8222-222222222222"
            ),
            "projectId": "atenea",
        }
        self.start = {
            **self.exact,
            "repository": "https://github.com/jlnieto/atenea.git",
            "branch": "main",
            "commit": "a" * 40,
            "manifestSha256": "b" * 64,
            "operation": "BACKEND_TEST",
            "definitionRevision": "atenea-backend-test-v1",
            "sourceTreeFingerprintSha256": "c" * 64,
        }
        self.operation = {
            **self.exact,
            "sourceRevision": "a" * 40,
            "sourceTreeFingerprintSha256": "c" * 64,
            "validationDefinition": "BACKEND_TEST",
            "definitionRevision": "atenea-backend-test-v1",
            "state": "RECONCILING",
            "terminalCause": "NONE",
            "transportState": "UNCERTAIN",
            "exitCode": None,
            "durationMillis": 0,
            "artifactManifestSha256": None,
            "summary": "Recovering the durable validation state",
            "createdAt": "2026-08-24T12:00:00Z",
            "startedAt": "2026-08-24T12:00:01Z",
            "finishedAt": None,
            "updatedAt": "2026-08-24T12:00:02Z",
            "revision": 3,
            "valuesExposed": False,
        }

    def validate(self, schema_name, document):
        validator = Draft202012Validator(
            self.schemas[schema_name], format_checker=FormatChecker()
        )
        errors = list(validator.iter_errors(document))
        self.assertEqual([], errors)

    def test_start_inspect_cancel_and_operation_are_draft_2020_12(self):
        self.validate("closed-validation-start-v1.request.schema.json", self.start)
        self.validate("closed-validation-inspect-v1.request.schema.json", self.exact)
        self.validate("closed-validation-cancel-v1.request.schema.json", self.exact)
        self.validate("closed-validation-operation-v1.schema.json", self.operation)

    def test_four_symbolic_definitions_remain_exact(self):
        revisions = {
            "BACKEND_TEST": "atenea-backend-test-v1",
            "WEB_BUILD": "atenea-web-build-v1",
            "ANDROID_BUILD": "atenea-android-build-v1",
            "PLAYWRIGHT_ACCEPTANCE": "atenea-playwright-acceptance-v1",
        }
        for operation, revision in revisions.items():
            document = {
                **self.start,
                "operation": operation,
                "definitionRevision": revision,
            }
            self.validate("closed-validation-start-v1.request.schema.json", document)

    def test_contract_rejects_added_authority_and_mismatched_definition(self):
        validator = Draft202012Validator(
            self.schemas["closed-validation-start-v1.request.schema.json"],
            format_checker=FormatChecker(),
        )
        for key, value in (
            ("command", "id"),
            ("path", "/srv/private"),
            ("slot", "slot2"),
            ("host", "ax42"),
            ("credential", "secret"),
        ):
            self.assertFalse(validator.is_valid({**self.start, key: value}))
        self.assertFalse(
            validator.is_valid(
                {**self.start, "definitionRevision": "atenea-web-build-v1"}
            )
        )

    def test_public_state_exposes_no_execution_authority(self):
        serialized = json.dumps(self.operation, sort_keys=True)
        for forbidden in (
            '"command"', '"shell"', '"path"', '"slot"', '"host"',
            '"credential"', '"environment"',
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
