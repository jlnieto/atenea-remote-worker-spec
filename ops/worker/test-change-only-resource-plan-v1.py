import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("resource_plan", Path(__file__).with_name("change-only-resource-plan-v1.py"))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class ResourcePlanTest(unittest.TestCase):
    def setUp(self):
        self.manifest = p.load_manifest()
        self.roots = [{"kind": r["kind"], "id": r["id"], "records": copy.deepcopy(r["records"]),
                       "head": r["head"], "branch": r["branch"], "dirty": r["dirty"]}
                      for r in self.manifest["reviewedRoots"]]

    def plan(self, **kwargs):
        return p.plan(self.manifest, self.roots, kwargs.get("active", []),
                      kwargs.get("resources", []), kwargs.get("config_hash", self.manifest["projectConfigurationSha256"]))

    def codes(self, result):
        return {b["code"] for b in result["blockers"]}

    def test_manifest_is_pinned_and_matches_the_database_cleanup_scope(self):
        self.assertEqual([2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20], self.manifest["trialSessionIds"])
        self.assertNotIn(21, self.manifest["trialSessionIds"])
        self.assertNotIn(p.REAL_CHANGE, self.manifest["trialChangeKeys"])
        self.assertEqual(25, len(self.roots))

    def test_unbound_roots_are_not_inferred_to_be_disposable(self):
        self.manifest["reviewedRoots"][0]["disposition"] = "UNBOUND_REVIEW_REQUIRED"
        result = self.plan()
        self.assertEqual("BLOCKED", result["state"])
        self.assertIn("UNBOUND_ROOT_NOT_CORRELATED_WITH_PROD", self.codes(result))
        self.assertFalse(result["receiptEmitted"])
        self.assertFalse(result["mutationsPerformed"])

    def test_real_apache_is_always_preserved(self):
        result = self.plan()
        self.assertNotIn(p.REAL_CHANGE, {r["id"] for r in result["archiveCandidates"]})
        self.assertEqual(p.REAL_CHANGE, result["preservedChangeKey"])

    def test_exact_wip_branch_is_authorized_but_not_a_variant(self):
        for r in self.roots:
            if r["id"] == "2ac2a5fd-2981-49cf-8fac-8132e46a2d64":
                r.update(head="b2f798e0ae3dec1b43bbfe4189aeadddd6287db8",
                         branch="refs/heads/ax42-beautips-wip-preservation-2ac2a5fd", dirty=False)
        result = self.plan()
        self.assertIn("2ac2a5fd-2981-49cf-8fac-8132e46a2d64", {r["id"] for r in result["archiveCandidates"]})
        row = next(r for r in self.roots if r["id"] == "2ac2a5fd-2981-49cf-8fac-8132e46a2d64")
        row["branch"] += "-foreign"
        self.assertIn("WORKTREE_OBSERVATION_MOVED", self.codes(self.plan()))

    def test_active_runtime_and_non_terminal_execution_block_the_entire_release(self):
        result = self.plan(active=["synthetic-active"], resources=[
            {"owner": "2ac2a5fd-2981-49cf-8fac-8132e46a2d64", "kind": "container"}])
        self.assertEqual("BLOCKED", result["state"])
        self.assertEqual(1, result["nonTerminalExecutions"])
        self.assertTrue({"NON_TERMINAL_EXECUTION", "OWNED_RUNTIME_STILL_PRESENT"}.issubset(self.codes(result)))

    def test_record_hash_permissions_or_owner_drift_block_cleanup(self):
        for field, value in (("sha256", "0" * 64), ("mode", "0o666"), ("uid", 1000)):
            with self.subTest(field=field):
                original = copy.deepcopy(self.roots[1])
                self.roots[1]["records"]["workspace-v1.json"][field] = value
                self.assertIn("WORKSPACE_RECORD_MOVED", self.codes(self.plan()))
                self.roots[1] = original

    def test_new_or_missing_roots_and_configuration_drift_are_not_accepted(self):
        self.roots.append({"kind": "sessions", "id": "synthetic-unknown", "records": {}})
        self.assertIn("UNREVIEWED_ROOT", self.codes(self.plan()))
        self.roots.pop(); self.roots.pop()
        self.assertIn("REVIEWED_ROOT_MISSING", self.codes(self.plan()))
        self.assertIn("PROJECT_CONFIGURATION_MOVED", self.codes(self.plan(config_hash="0" * 64)))

    def test_dirty_ws19_and_ws6_must_be_archived_not_erased(self):
        dirty = {r["id"] for r in self.plan()["archiveCandidates"] if r["dirty"]}
        self.assertEqual({"6547081d-895e-4be1-a8fd-d115b7743cdf", "c750641d-3226-44c3-81dc-d9149aac0de1"}, dirty)

    def test_symlinks_and_hardlinks_are_rejected_before_reading(self):
        with tempfile.TemporaryDirectory(prefix="resource-plan-test-") as temporary:
            root = Path(temporary); source = root / "source"; source.write_bytes(b"synthetic")
            link = root / "link"; link.symlink_to(source)
            with self.assertRaisesRegex(p.Refused, "SYMLINK_AUTHORITY"):
                p.read_regular(link)
            link.unlink(); link.hardlink_to(source)
            with self.assertRaisesRegex(p.Refused, "AMBIGUOUS_FILE_AUTHORITY"):
                p.read_regular(source)

    def test_no_apply_paths_commands_hosts_or_manifest_override_are_accepted(self):
        p.parse_arguments(["--plan"])
        for args in (["--apply"], ["--plan", "--path", "/tmp"], ["--plan", "--command", "id"],
                     ["--plan", "--manifest", "/tmp/fake.json"], ["--pla"], ["--plan", "--host", "foreign"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                p.parse_arguments(args)

    def test_docker_observation_uses_all_five_engines_and_never_mutates(self):
        invoked = []
        def command(args, cwd=None):
            invoked.append(args)
            return ""
        with patch.object(p, "command", side_effect=command):
            self.assertEqual([], p.observe_runtime_resources(self.manifest))
        self.assertEqual(15, len(invoked))
        self.assertEqual(set(p.ENGINES), {args[1].split("=", 1)[1] for args in invoked})
        self.assertFalse(any(set(args) & {"stop", "rm", "prune", "kill", "down", "exec"} for args in invoked))

    def test_same_snapshot_produces_identical_plan_and_cannot_be_a_release_receipt(self):
        first = self.plan(); second = self.plan()
        self.assertEqual(first, second)
        self.assertNotEqual("change-only-resource-cleanup-receipt-v1", first["schemaVersion"])
        self.assertNotEqual("RELEASED", first["state"])


if __name__ == "__main__":
    unittest.main()
