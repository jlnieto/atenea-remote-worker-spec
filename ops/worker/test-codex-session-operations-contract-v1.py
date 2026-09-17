#!/usr/bin/env python3

import copy
import hashlib
import json
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:
    Draft202012Validator = None
    FormatChecker = None


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "runtime-contract"
FIXTURES = CONTRACT / "fixtures/codex-session-operations-v1"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_catalog_revision(catalog):
    revision_input = {
        "schemaVersion": catalog["schemaVersion"],
        "codexVersion": catalog["codexVersion"],
        "models": sorted(catalog["models"], key=lambda item: item["modelId"]),
    }
    encoded = json.dumps(
        revision_input,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def set_path(document, dotted_path, value):
    target = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


class SemanticDenial(ValueError):
    pass


class CodexSessionOperationsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if Draft202012Validator is None:
            raise unittest.SkipTest("jsonschema is not installed")
        cls.schemas = {
            "catalog": read_json(CONTRACT / "codex-model-catalog-v1.schema.json"),
            "dispatch": read_json(
                CONTRACT / "agent-run-project-codex-v2.request.schema.json"
            ),
            "imageDispatch": read_json(
                CONTRACT / "agent-run-project-codex-v3.request.schema.json"
            ),
            "imageResult": read_json(
                CONTRACT / "agent-run-project-codex-v3.result.schema.json"
            ),
            "result": read_json(
                CONTRACT / "agent-run-project-codex-v2.result.schema.json"
            ),
            "progress": read_json(CONTRACT / "agent-run-progress-v1.schema.json"),
            "exactOperation": read_json(
                CONTRACT / "agent-run-exact-operation-v1.request.schema.json"
            ),
            "doctor": read_json(CONTRACT / "agent-run-doctor-v1.schema.json"),
            "api": read_json(
                CONTRACT / "codex-session-operation-api-v1.request.schema.json"
            ),
            "stageResult": read_json(
                CONTRACT / "codex-update-stage-v1.result.schema.json"
            ),
            "reconcileResult": read_json(
                CONTRACT / "codex-update-reconcile-v1.result.schema.json"
            ),
            "activateResult": read_json(
                CONTRACT / "codex-update-activate-v1.result.schema.json"
            ),
            "rollbackResult": read_json(
                CONTRACT / "codex-update-rollback-v1.result.schema.json"
            ),
        }
        cls.validators = {
            name: Draft202012Validator(schema, format_checker=FormatChecker())
            for name, schema in cls.schemas.items()
        }
        cls.catalog = read_json(FIXTURES / "catalog.json")
        cls.dispatch = read_json(FIXTURES / "valid-dispatch.json")
        cls.api_requests = read_json(FIXTURES / "valid-api-requests.json")
        cls.negative_corpus = read_json(FIXTURES / "negative-corpus.json")
        cls.accepted_owner = (
            cls.dispatch["sessionId"],
            cls.dispatch["workspaceIdentity"],
        )

    def assert_schema_valid(self, schema_name, document):
        errors = sorted(
            self.validators[schema_name].iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual([], errors, [error.message for error in errors])

    def validate_catalog_semantics(self, catalog):
        if catalog["models"] != sorted(catalog["models"], key=lambda item: item["modelId"]):
            raise SemanticDenial("catalog models are not canonical")
        model_ids = [model["modelId"] for model in catalog["models"]]
        if len(model_ids) != len(set(model_ids)):
            raise SemanticDenial("catalog model identity is ambiguous")
        for model in catalog["models"]:
            if model["defaultEffort"] not in model["supportedEfforts"]:
                raise SemanticDenial("catalog default effort is unsupported")
        if catalog["catalogRevision"] != canonical_catalog_revision(catalog):
            raise SemanticDenial("catalog revision is stale")

    def validate_dispatch_semantics(self, request):
        expected_workspace = (
            "remote:ax42-01:work-session:" + request["sessionId"]
        )
        owner = (request["sessionId"], request["workspaceIdentity"])
        if request["workspaceIdentity"] != expected_workspace:
            raise SemanticDenial("session/workspace ownership is ambiguous")
        if owner != self.accepted_owner:
            raise SemanticDenial("session/workspace ownership is foreign")
        workload = request["workload"]
        if workload["catalogRevision"] != self.catalog["catalogRevision"]:
            raise SemanticDenial("catalog revision is not accepted")
        if workload["codexVersion"] != self.catalog["codexVersion"]:
            raise SemanticDenial("Codex version is not accepted")
        models = {
            model["modelId"]: model
            for model in self.catalog["models"]
            if model["availability"] == "AVAILABLE"
        }
        model = models.get(workload["modelId"])
        if model is None:
            raise SemanticDenial("model is not accepted")
        if workload["reasoningEffort"] not in model["supportedEfforts"]:
            raise SemanticDenial("effort is not accepted for model")

    def validate_api_semantics(self, request):
        if request["operation"] not in {
            "SET_WORK_SESSION_PROFILE",
            "SET_NEXT_TURN_PROFILE",
        }:
            return
        if request["catalogRevision"] != self.catalog["catalogRevision"]:
            raise SemanticDenial("API catalog revision is not accepted")
        models = {model["modelId"]: model for model in self.catalog["models"]}
        model = models.get(request["modelId"])
        if model is None or model["availability"] != "AVAILABLE":
            raise SemanticDenial("API model is not accepted")
        if request["reasoningEffort"] not in model["supportedEfforts"]:
            raise SemanticDenial("API effort is not accepted for model")

    def test_valid_catalog_dispatch_result_progress_and_api_contracts(self):
        self.assert_schema_valid("catalog", self.catalog)
        self.validate_catalog_semantics(self.catalog)
        self.assert_schema_valid("dispatch", self.dispatch)
        self.validate_dispatch_semantics(self.dispatch)
        for request in self.api_requests:
            self.assert_schema_valid("api", request)
            self.validate_api_semantics(request)

        result = {
            "threadId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "turnId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "finalAnswer": "Synthetic contract accepted.",
            "outputSummary": "project-codex-v2 completed",
            "modelId": "gpt-5.6-sol",
            "reasoningEffort": "high",
            "catalogRevision": self.catalog["catalogRevision"],
            "codexVersion": self.catalog["codexVersion"],
        }
        progress = {
            "dispatchId": self.dispatch["dispatchId"],
            "executionId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "sequence": 1,
            "category": "INSPECTING_PROJECT",
            "occurredAt": "2026-07-31T00:00:00Z",
            "message": "Inspecting the accepted project.",
        }
        self.assert_schema_valid("result", result)
        self.assert_schema_valid("progress", progress)
        stage_result = {
            "schemaVersion": "codex-update-stage-v1",
            "operation": "STAGE_CODEX_UPDATE",
            "workerId": "ax42-01",
            "planId": self.api_requests[3]["planId"],
            "candidateId": self.api_requests[3]["candidateId"],
            "idempotencyKey": self.api_requests[3]["idempotencyKey"],
            "state": "STAGED",
            "codexVersion": self.catalog["codexVersion"],
            "releaseDigestSha256": "a" * 64,
            "catalogRevision": self.catalog["catalogRevision"],
            "releaseManifestSha256": "b" * 64,
            "schemaManifestSha256": "c" * 64,
            "releaseVerification": "PASS",
            "schemaGeneration": "PASS",
            "retention": "PASS",
            "currentLinkFingerprint": "d" * 64,
            "previousLinkFingerprint": "e" * 64,
            "linksChanged": False,
            "valuesExposed": False,
        }
        self.assert_schema_valid("stageResult", stage_result)
        reconcile_result = {
            "schemaVersion": "codex-release-reconcile-v1",
            "operation": "RECONCILE_INSTALLED_CODEX_RELEASES",
            "workerId": "ax42-01", "idempotencyKey": self.api_requests[3]["idempotencyKey"],
            "state": "RECONCILED",
            "planId": "15414500-0000-4000-8000-000000000001",
            "currentInventoryId": "15414500-0000-4000-8000-000000000002",
            "candidateInventoryId": "15414500-0000-4000-8000-000000000003",
            "currentVersion": "0.154.0", "candidateVersion": "0.145.0",
            "currentReleaseDigestSha256":
                "37de474b157b0313c73ddc05928855f61517676138827df51660fe8715dca14f",
            "candidateReleaseDigestSha256":
                "56da3312ccb2109a2f4e0d71b003f08d33244ec6f5863e8fc7f6f24b7a6489c2",
            "candidateCatalogRevision":
                "125b9437e38f83e04cb10996fc70d3ab44c32082009b8e897cb08bb340b13187",
            "currentInstallationState": "INSTALLED", "currentLinkState": "CURRENT",
            "currentCompatibilityState": "UNKNOWN", "candidateInstallationState": "STAGED",
            "candidateLinkState": "NONE", "candidateCompatibilityState": "COMPATIBLE",
            "previousState": "ABSENT", "previousCompatibilityState": "UNKNOWN",
            "structureVerification": "PASS", "permissionVerification": "PASS",
            "metadataVerification": "PASS", "versionVerification": "PASS",
            "hashVerification": "PASS", "zeroNonTerminalRuns": "PASS",
            "currentLinkFingerprint": "d" * 64, "linksChanged": True,
            "inventorySha256": "e" * 64, "planSha256": "f" * 64,
            "registrySha256": "0" * 64, "valuesExposed": False,
            "completedAt": "2026-09-17T00:00:00Z",
        }
        self.assert_schema_valid("reconcileResult", reconcile_result)
        activation_result = {
            "schemaVersion": "codex-update-activate-v1",
            "operation": "ACTIVATE_CODEX_UPDATE",
            "workerId": "ax42-01",
            "planId": self.api_requests[4]["planId"],
            "candidateId": self.api_requests[4]["candidateId"],
            "authorizationId": self.api_requests[4]["authorizationId"],
            "idempotencyKey": self.api_requests[4]["idempotencyKey"],
            "state": "ACTIVATED",
            "codexVersion": self.catalog["codexVersion"],
            "releaseDigestSha256": "a" * 64,
            "catalogRevision": self.catalog["catalogRevision"],
            "schemaComparison": "PASS",
            "focusedContracts": "PASS",
            "workerHealth": "PASS",
            "canary": "PASS",
            "currentBeforeFingerprint": "b" * 64,
            "previousBeforeFingerprint": "c" * 64,
            "currentAfterFingerprint": "d" * 64,
            "previousAfterFingerprint": "e" * 64,
            "automaticRestore": "NOT_REQUIRED",
            "valuesExposed": False,
        }
        self.assert_schema_valid("activateResult", activation_result)
        rollback_result = {
            "schemaVersion": "codex-update-rollback-v1",
            "operation": "ROLLBACK_CODEX_UPDATE",
            "workerId": "ax42-01",
            "planId": self.api_requests[4]["planId"],
            "candidateId": self.api_requests[4]["candidateId"],
            "activationId": self.api_requests[7]["activationId"],
            "authorizationId": self.api_requests[7]["authorizationId"],
            "idempotencyKey": self.api_requests[7]["idempotencyKey"],
            "state": "ROLLED_BACK",
            "linkRestore": "PASS",
            "workerServiceRestart": "PASS",
            "affectedServices": ["atenea-agent-run-worker-v1.service"],
            "appServerServicesRestarted": 0,
            "currentBeforeFingerprint": "a" * 64,
            "previousBeforeFingerprint": "b" * 64,
            "currentAfterFingerprint": "c" * 64,
            "previousAfterFingerprint": "d" * 64,
            "valuesExposed": False,
        }
        self.assert_schema_valid("rollbackResult", rollback_result)

        exact_operation = {
            "executionId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "sessionId": self.dispatch["sessionId"],
            "workspaceIdentity": self.dispatch["workspaceIdentity"],
            "leaseGeneration": self.dispatch["leaseGeneration"],
        }
        doctor = {
            "schemaVersion": "agent-run-doctor-v1",
            "workerId": "ax42-01",
            "dispatchId": self.dispatch["dispatchId"],
            **exact_operation,
            "status": "RUNNING",
            "revision": 4,
            "observation": "OWNED_PROCESS_ACTIVE",
            "cancelRequested": False,
            "reconcileRequired": False,
            "latestProgressSequence": 3,
            "retainedProgressCount": 3,
            "valuesExposed": False,
        }
        self.assert_schema_valid("exactOperation", exact_operation)
        self.assert_schema_valid("doctor", doctor)
        for field, value in (
            ("command", "id"),
            ("host", "foreign.invalid"),
            ("service", "docker"),
            ("path", "/srv/foreign"),
            ("slot", "slot4"),
            ("environment", {"TOKEN": "synthetic"}),
            ("credential", "synthetic-reference"),
        ):
            candidate = {**exact_operation, field: value}
            self.assertTrue(list(self.validators["exactOperation"].iter_errors(candidate)))

    def test_image_dispatch_schema_is_exact_additive_and_bounded(self):
        image_dispatch = copy.deepcopy(self.dispatch)
        image_dispatch["workload"].update({
            "kind": "project-codex-v3",
            "attachments": [
                {
                    "attachmentId": "11111111-1111-4111-8111-111111111111",
                    "contentType": "image/png",
                    "sizeBytes": 1024,
                    "sha256": "1" * 64,
                }
            ],
        })
        self.assert_schema_valid("imageDispatch", image_dispatch)
        self.assert_schema_valid("imageResult", {
            "threadId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "turnId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "finalAnswer": "Synthetic image contract accepted.",
            "outputSummary": "project-codex-v3 completed",
            "modelId": image_dispatch["workload"]["modelId"],
            "reasoningEffort": image_dispatch["workload"]["reasoningEffort"],
            "catalogRevision": image_dispatch["workload"]["catalogRevision"],
            "codexVersion": image_dispatch["workload"]["codexVersion"],
        })

        denied = []
        for mutation in (
            lambda request: request["workload"].__setitem__("attachments", []),
            lambda request: request["workload"]["attachments"][0].__setitem__(
                "contentType", "text/plain"),
            lambda request: request["workload"]["attachments"][0].__setitem__(
                "sizeBytes", 16777217),
            lambda request: request["workload"]["attachments"][0].__setitem__(
                "path", "/srv/foreign"),
            lambda request: request["workload"].__setitem__(
                "attachments", request["workload"]["attachments"] * 5),
        ):
            candidate = copy.deepcopy(image_dispatch)
            mutation(candidate)
            denied.append(candidate)
        for candidate in denied:
            self.assertTrue(list(self.validators["imageDispatch"].iter_errors(candidate)))

    def test_negative_corpus_is_rejected_at_its_declared_boundary(self):
        bases = {
            "dispatch": self.dispatch,
            "profileApi": self.api_requests[0],
            "recoveryApi": self.api_requests[1],
            "updateApi": self.api_requests[3],
        }
        for case in self.negative_corpus:
            with self.subTest(case=case["name"]):
                candidate = copy.deepcopy(bases[case["documentType"]])
                set_path(candidate, case["patch"]["path"], case["patch"]["value"])
                schema_name = "dispatch" if case["documentType"] == "dispatch" else "api"
                schema_errors = list(self.validators[schema_name].iter_errors(candidate))
                if case["expectedLayer"] == "schema":
                    self.assertTrue(schema_errors)
                    continue
                self.assertEqual([], schema_errors)
                with self.assertRaises(SemanticDenial):
                    if schema_name == "dispatch":
                        self.validate_dispatch_semantics(candidate)
                    else:
                        self.validate_api_semantics(candidate)

    def test_catalog_rejects_ambiguous_defaults_and_revision(self):
        duplicate = copy.deepcopy(self.catalog)
        duplicate["models"].append(copy.deepcopy(duplicate["models"][0]))
        with self.assertRaises(SemanticDenial):
            self.validate_catalog_semantics(duplicate)

        unsupported_default = copy.deepcopy(self.catalog)
        unsupported_default["models"][0]["supportedEfforts"] = ["low"]
        with self.assertRaises(SemanticDenial):
            self.validate_catalog_semantics(unsupported_default)

        stale = copy.deepcopy(self.catalog)
        stale["catalogRevision"] = "f" * 64
        with self.assertRaises(SemanticDenial):
            self.validate_catalog_semantics(stale)

    def test_progress_schema_rejects_reasoning_and_raw_authority(self):
        base = {
            "dispatchId": self.dispatch["dispatchId"],
            "executionId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "sequence": 2,
            "category": "RUNNING_COMMAND",
            "occurredAt": "2026-07-31T00:00:00Z",
            "message": "Running a reviewed operation.",
        }
        for field, value in (
            ("reasoning", "hidden detail"),
            ("command", ["sh", "-lc", "id"]),
            ("output", "raw output"),
            ("environment", {"SYNTHETIC": "value"}),
        ):
            candidate = copy.deepcopy(base)
            candidate[field] = value
            self.assertTrue(list(self.validators["progress"].iter_errors(candidate)))


if __name__ == "__main__":
    unittest.main()
