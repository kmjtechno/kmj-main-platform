#!/usr/bin/env python3
"""Safety regression tests: unattended publication must be gated per SHA."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).parent / "operations" / "main_platform_autopublish_gate.py"
spec = importlib.util.spec_from_file_location("kmj_auto_gate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40
OLD = "platform-" + "b" * 12
BASE_APPROVAL = {
    "approvedSha": SHA, "expectedCurrentRelease": OLD,
    "backupVerified": True, "rollbackVerified": True,
}
BASE_EVIDENCE = {
    "schema": "kmj.autopublish.release-admission.v1",
    "approvedSha": SHA, "expectedCurrentRelease": OLD, "stagingSha": SHA,
    "standingOwnerAuthorization": True,
    **{k: True for k in mod.ACCEPTANCE_KEYS},
}

def verdict(approval=None, evidence=None, live=OLD, remote=SHA, candidate=SHA):
    return mod.decision(
        BASE_APPROVAL if approval is None else approval,
        BASE_EVIDENCE if evidence is None else evidence,
        live, remote, candidate,
    )

class AutoPublishSafetyTest(unittest.TestCase):
    def test_all_independent_gates_exact_sha(self):
        self.assertEqual(verdict(), "READY_APPROVED_RELEASE")

    def test_noop_when_already_live(self):
        self.assertEqual(verdict(live="platform-" + SHA[:12]), "ALREADY_LIVE")

    def test_never_publish_without_approval(self):
        self.assertEqual(verdict(approval={}), "BLOCKED_APPROVAL_SCHEMA")
        for key in ("backupVerified", "rollbackVerified"):
            copy_ = dict(BASE_APPROVAL, **{key: "true"})
            self.assertEqual(verdict(approval=copy_), "BLOCKED_PROTECTED_APPROVAL")

    def test_approval_schema_extras_rejected(self):
        copy_ = dict(BASE_APPROVAL, unexpected=True)
        self.assertEqual(verdict(approval=copy_), "BLOCKED_APPROVAL_SCHEMA")

    def test_current_release_race_blocks(self):
        self.assertEqual(verdict(live="platform-" + "c" * 12),
                         "BLOCKED_CURRENT_RELEASE_DRIFT")

    def test_promotion_drift_and_wrong_candidate(self):
        self.assertEqual(verdict(remote="c" * 40),
                         "BLOCKED_STAGING_APPROVAL_DRIFT")
        self.assertEqual(verdict(candidate="c" * 40),
                         "BLOCKED_CANDIDATE_IDENTITY")

    def test_explicit_owner_policy_required(self):
        copy_ = dict(BASE_EVIDENCE, standingOwnerAuthorization=False)
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_OWNER_AUTHORIZATION")
        copy_["standingOwnerAuthorization"] = "true"
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_OWNER_AUTHORIZATION")

    def test_every_acceptance_gate_required(self):
        for gate in mod.ACCEPTANCE_KEYS:
            copy_ = dict(BASE_EVIDENCE, **{gate: False})
            self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_EVIDENCE", gate)

    def test_stale_or_spoofed_acceptance_rejected(self):
        for key, bad in (
            ("approvedSha", "c" * 40),
            ("expectedCurrentRelease", "platform-" + "c" * 12),
            ("stagingSha", "c" * 40),
            ("schema", "wrong"),
        ):
            copy_ = dict(BASE_EVIDENCE, **{key: bad})
            self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_IDENTITY")
        copy_ = dict(BASE_EVIDENCE, extra="true")
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_SCHEMA")

    def test_postactivation_requires_exact_https_deploy_sha(self):
        good = "HTTP/2 200\\r\\nx-kmj-deploy-sha: " + SHA + (
            "\\r\\ncontent-type: text/html\\r\\n\\r\\nKMJ_HTTP_STATUS=200")
        self.assertTrue(mod.exact_https_sha_ok(good, SHA))
        for bad in (
            good.replace(SHA, "c" * 40),
            good.replace("HTTP/2 200", "HTTP/2 302"),
            good.replace("KMJ_HTTP_STATUS=200", "KMJ_HTTP_STATUS=404"),
            good.replace("x-kmj-deploy-sha:", "x-other-header:"),
            good.replace("content-type:", "x-kmj-deploy-sha: " + SHA + "\\r\\ncontent-type:"),
            "HTTP/1.1 200\\r\\n\\r\\n" + good,
            "",
        ):
            self.assertFalse(mod.exact_https_sha_ok(bad, SHA))

    def test_fixed_unit_no_arbitrary_commands_or_bypass(self):
        source = SOURCE.read_text()
        self.assertIn("kmj-main-platform-production-release.service", source)
        self.assertIn("https://kmjtechno.com/login", source)
        self.assertIn('"--activate"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("os.symlink(", source)
        self.assertNotIn("os.replace(", source)
        self.assertNotIn("write_text(", source)

if __name__ == "__main__":
    unittest.main()
