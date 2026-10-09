#!/usr/bin/env python3
"""Main advancement on synthetic repositories only; no shared runtime or network."""
import importlib.util
import json
import os
import subprocess
import unittest
import uuid
from pathlib import Path
from unittest import mock
from jsonschema import Draft202012Validator, FormatChecker, RefResolver

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_finalization_fixtures", HERE / "test-development-change-source-finalization-v1.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module = fixtures.module


class SourceContinuationTest(fixtures.SourceFinalizationTest):
    # Only this class's new scenarios; importing a fixture must not repeat its suite.
    def advance_main(self, *, conflict=False):
        (self.source / "later-main.txt").write_text("later main\n")
        self.advances=getattr(self,"advances",0)+1
        if self.advances>1:
            (self.source / f"later-main-{self.advances}.txt").write_text("another main advance\n")
        if conflict:
            (self.source / "README.md").write_text("later main README\n")
        self._git("-C", str(self.source), "add", ".")
        self._git("-C", str(self.source), "commit", "-m", "later main")
        self.target = self._git("-C", str(self.source), "rev-parse", "HEAD", capture=True).strip()
        self._git("-C", str(self.source), "push", str(self.remote), "main:main")
        self._git(f"--git-dir={self.mirror}", "fetch", str(self.remote), "main:refs/remotes/origin/main")

    def continuation(self, final_request, *, published=None, parent_path=None):
        parent = json.loads((parent_path or self.path).read_text())
        observation = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        return self.exact({**{key: parent[key] for key in module.SOURCE_UPDATE_REQUEST_KEYS},
            "protocolVersion": module.SOURCE_CONTINUATION_PROTOCOL,
            "operation": "PREPARE", "effect": "PREPARE_PINNED_MAIN",
            "operationId": str(uuid.uuid4()), "idempotencyKey": str(uuid.uuid4()), "targetMainCommit": self.target,
            "sourceCommit": published["publishedHeadSha"] if published else parent["sourceCommit"],
            "sourceRevision": final_request["sourceRevision"],
            "sourceFingerprintSha256": observation["sourceFingerprintSha256"],
            "publicationReceiptSha256": published["finalizationReceiptSha256"] if published else parent["publicationReceiptSha256"],
            "publishedSourceRevision": final_request["sourceRevision"] if published else parent.get("publishedSourceRevision",parent["sourceRevision"]),
            "predecessorPreparationOperationId": parent["operationId"],
            "predecessorPreparationReceiptSha256": parent["recordSha256"]})

    def finalization(self, request, prepared):
        observation = self.mediator.execute(self.request("INSPECT"), "INSPECT")
        return self.exact({**{key: request[key] for key in module.SOURCE_UPDATE_REQUEST_KEYS},
            "protocolVersion": module.SOURCE_FINALIZATION_PROTOCOL, "operation": "FINALIZE", "effect": "FINALIZE_VALIDATED_SOURCE",
            "operationId": str(uuid.uuid4()), "idempotencyKey": str(uuid.uuid4()),
            "sourceRevision": request["sourceRevision"]+1, "sourceFingerprintSha256": observation["sourceFingerprintSha256"],
            "preparationOperationId": request["operationId"], "preparationReceiptSha256": prepared["receiptSha256"],
            "validationProjectionSha256": "f"*64})

    def test_continue_before_publication_retains_resolved_files_and_original_head(self):
        final_request = self.fixture()
        self.advance_main()
        request = self.continuation(final_request)
        prepared = self.mediator.update_source(request, "PREPARE")
        self.assertEqual("READY_TO_FINALIZE", prepared["state"])
        self.assertEqual("ticket and main resolved\n", (self.worktree / "README.md").read_text())
        self.assertEqual("later main\n", (self.worktree / "later-main.txt").read_text())
        self.assertEqual(self.head, self._git("-C", str(self.worktree), "rev-parse", "HEAD", capture=True).strip())
        self.assertEqual(self.preparation_bytes, self.path.read_bytes())
        self.assertEqual(self.owner,(self.path.parent / "workspace-v1.json").read_bytes())
        self.assertEqual(self.publication,(self.path.parent / "branch-publication-v1.json").read_bytes())
        self.assertEqual(self.head,module.approved_validation_commit(self.path.parent,json.loads(self.owner),os.getuid(),os.getgid()))
        result = self.mediator.finalize_source(self.finalization(request,prepared), "FINALIZE")
        self.assertEqual("PUBLISHED",result["state"])
        self.assertEqual(self.head,self._git(f"--git-dir={self.mirror}","rev-parse",result["publishedHeadSha"]+"^1",capture=True).strip())
        self.assertEqual(self.target,self._git(f"--git-dir={self.mirror}","rev-parse",result["publishedHeadSha"]+"^2",capture=True).strip())

    def test_continue_after_publication_uses_same_branch_and_sealed_new_head(self):
        final_request = self.fixture()
        published = self.mediator.finalize_source(final_request, "FINALIZE")
        old_final = self.final_path.read_bytes()
        self.advance_main()
        request = self.continuation(final_request,published=published)
        prepared = self.mediator.update_source(request,"PREPARE")
        self.assertEqual(published["publishedHeadSha"],module.approved_validation_commit(
            self.path.parent,json.loads(self.owner),os.getuid(),os.getgid()))
        result = self.mediator.finalize_source(self.finalization(request,prepared),"FINALIZE")
        self.assertEqual(request["sourceCommit"],self._git(f"--git-dir={self.mirror}","rev-parse",result["publishedHeadSha"]+"^1",capture=True).strip())
        self.assertEqual(old_final,self.final_path.read_bytes())
        self.assertEqual(self.preparation_bytes,self.path.read_bytes())
        self.assertEqual(result["publishedHeadSha"],self._git(f"--git-dir={self.remote}","rev-parse",request["workspaceBranch"],capture=True).strip())

    def test_duplicate_and_inspection_preserve_one_checkpoint_and_pointer(self):
        final_request = self.fixture();self.advance_main();request=self.continuation(final_request)
        first=self.mediator.update_source(request,"PREPARE")
        pointer=self.path.parent / "source-update-active-v1.json"
        before=pointer.read_bytes()
        self.assertEqual(first,self.mediator.update_source(request,"PREPARE"))
        self.assertEqual(first["receiptSha256"],self.mediator.update_source(self.exact(request,operation="INSPECT",effect="OBSERVE_ONLY"),"INSPECT")["receiptSha256"])
        self.assertEqual(before,pointer.read_bytes())
        self.assertEqual(1,len(list(self.path.parent.glob("source-update-*-v2.json"))))

    def test_prepared_interruption_is_read_only_then_recovers_captured_input(self):
        final_request=self.fixture();self.advance_main();request=self.continuation(final_request)
        with mock.patch.object(self.mediator,"_resume_source_update",side_effect=module.ContractError("synthetic interruption")):
            with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        before=(self.worktree / "README.md").read_bytes()
        with self.assertRaises(module.ContractError):
            module.approved_validation_commit(self.path.parent,json.loads(self.owner),os.getuid(),os.getgid())
        self.assertEqual("PREPARED",self.mediator.update_source(self.exact(request,operation="INSPECT",effect="OBSERVE_ONLY"),"INSPECT")["state"])
        self.assertEqual(before,(self.worktree / "README.md").read_bytes())
        self.assertEqual("READY_TO_FINALIZE",self.mediator.update_source(self.exact(request,operation="RECONCILE",effect="OBSERVE_OR_RESUME_EXACT"),"RECONCILE")["state"])

    def test_changed_files_after_interruption_are_never_reset(self):
        final_request=self.fixture();self.advance_main();request=self.continuation(final_request)
        with mock.patch.object(self.mediator,"_resume_source_update",side_effect=module.ContractError("synthetic interruption")):
            with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        (self.worktree / "README.md").write_text("keep later edits\n")
        with self.assertRaisesRegex(module.ContractError,"later edit"):
            self.mediator.update_source(self.exact(request,operation="RECONCILE",effect="OBSERVE_OR_RESUME_EXACT"),"RECONCILE")
        self.assertEqual("keep later edits\n",(self.worktree / "README.md").read_text())

    def test_foreign_parent_hash_or_main_rejected_before_effect(self):
        final_request=self.fixture();self.advance_main();request=self.continuation(final_request)
        before=(self.worktree / "README.md").read_bytes()
        for overrides in ({"predecessorPreparationReceiptSha256":"a"*64},{"predecessorPreparationOperationId":str(uuid.uuid4())},
                          {"targetMainCommit":self.head},{"sourceFingerprintSha256":"b"*64}):
            with self.assertRaises(module.ContractError): self.mediator.update_source(self.exact(request,**overrides),"PREPARE")
        self.assertEqual(before,(self.worktree / "README.md").read_bytes())
        self.assertFalse((self.path.parent / "source-update-active-v1.json").exists())

    def test_uncertain_publication_cannot_be_superseded(self):
        final_request=self.interrupted("push");self.advance_main()
        request=self.continuation(final_request)
        with self.assertRaises(module.ContractError): self.mediator.update_source(request,"PREPARE")
        self.assertFalse((self.path.parent / "source-update-active-v1.json").exists())

    def test_three_generations_keep_published_and_unpublished_lineage(self):
        final_request=self.fixture();published=self.mediator.finalize_source(final_request,"FINALIZE")
        self.advance_main();second=self.continuation(final_request,published=published)
        result=self.mediator.update_source(second,"PREPARE")
        second_path=self.path.parent / f"source-update-{second['operationId']}-v2.json"
        second_bytes=second_path.read_bytes()
        self.advance_main();third=self.continuation({"sourceRevision":second["sourceRevision"]+1},parent_path=second_path)
        prepared=self.mediator.update_source(third,"PREPARE")
        self._git(f"--git-dir={self.mirror}","gc","--prune=now")
        final=self.mediator.finalize_source(self.finalization(third,prepared),"FINALIZE")
        self.assertEqual("PUBLISHED",final["state"])
        self.assertEqual(second_bytes,second_path.read_bytes())
        self.assertEqual(self.preparation_bytes,self.path.read_bytes())
        self.assertEqual("ticket and main resolved\n",(self.worktree / "README.md").read_text())

    def test_new_conflicts_include_previous_resolution_and_new_main(self):
        final_request=self.fixture();self.advance_main(conflict=True);request=self.continuation(final_request)
        prepared=self.mediator.update_source(request,"PREPARE")
        self.assertEqual("NEEDS_RESOLUTION",prepared["state"])
        content=(self.worktree / "README.md").read_text()
        self.assertIn("ticket and main resolved",content);self.assertIn("later main README",content)
        self.assertEqual(self.preparation_bytes,self.path.read_bytes())

    def test_v2_schemas_and_worker_accept_only_exact_closed_request_and_response(self):
        final_request=self.fixture();self.advance_main();request=self.continuation(final_request)
        contract_root=HERE.parent.parent / "runtime-contract"
        schema=json.loads((contract_root / "development-change-source-update-v2.request.schema.json").read_text())
        response_schema=json.loads((contract_root / "development-change-source-update-v2.response.schema.json").read_text())
        resolver=RefResolver.from_schema(schema,store={schema["$id"]:schema})
        for definition in (schema,response_schema): Draft202012Validator.check_schema(definition)
        validator=Draft202012Validator(schema,resolver=resolver,format_checker=FormatChecker());validator.validate(request)
        response=self.mediator.update_source(request,"PREPARE")
        Draft202012Validator(response_schema,resolver=resolver,format_checker=FormatChecker()).validate(response)
        worker=fixtures.fixtures.worker_module;state=self.worker()
        with mock.patch.object(worker,"RELEASE_INSTALLED_MARKER",self.root / "absent-marker"), \
                mock.patch.object(state,"_invoke_source_update_mediator",return_value=subprocess.CompletedProcess([],0,json.dumps(response),"")) as invoke:
            self.assertEqual(response,state.update_development_change_source(request,"PREPARE"))
            for change in ({"command":"id"},{"path":"/arbitrary"},{"protocolVersion":module.SOURCE_UPDATE_PROTOCOL}):
                with self.assertRaises(worker.ProtocolError): state.update_development_change_source({**request,**change},"PREPARE")
                self.assertTrue(list(validator.iter_errors({**request,**change})))
            self.assertEqual(1,invoke.call_count)


if __name__ == "__main__":
    suite=unittest.TestSuite(SourceContinuationTest(name) for name in SourceContinuationTest.__dict__ if name.startswith("test_"))
    result=unittest.TextTestRunner().run(suite)
    raise SystemExit(not result.wasSuccessful())
