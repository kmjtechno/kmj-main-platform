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

    def test_already_live_requires_real_owner_evidence(self):
        live = "platform-" + SHA[:12]
        self.assertEqual(verdict(live=live), "ALREADY_LIVE")
        self.assertEqual(verdict(approval={}, live=live),
                         "BLOCKED_APPROVAL_SCHEMA")
        self.assertEqual(verdict(approval=dict(BASE_APPROVAL, backupVerified=False),
                                 live=live), "BLOCKED_PROTECTED_APPROVAL")
        self.assertEqual(verdict(evidence={}, live=live),
                         "BLOCKED_ACCEPTANCE_SCHEMA")
        self.assertEqual(verdict(evidence=dict(BASE_EVIDENCE,
                                             ownerAuthenticatedQaPass=False),
                                 live=live), "BLOCKED_ACCEPTANCE_EVIDENCE")
        self.assertEqual(verdict(evidence=dict(BASE_EVIDENCE,
                                             standingOwnerAuthorization=False),
                                 live=live), "BLOCKED_OWNER_AUTHORIZATION")
        self.assertEqual(verdict(remote="c" * 40, live=live),
                         "BLOCKED_STAGING_APPROVAL_DRIFT")
        self.assertEqual(verdict(candidate="c" * 40, live=live),
                         "BLOCKED_CANDIDATE_IDENTITY")

    def test_already_live_requires_fresh_exact_public_https(self):
        source = SOURCE.read_text()
        self.assertIn("if result == \"ALREADY_LIVE\":", source)
        self.assertIn("exact_https_sha_ok(public_https_response(), target)",
                      source)
        self.assertIn("KMJ_AUTOPUBLISH=BLOCKED_ALREADY_LIVE_HEALTH", source)
        self.assertIn("KMJ_AUTOPUBLISH=ALREADY_LIVE_SHA_VERIFIED", source)
        from unittest.mock import patch
        good = ("HTTP/2 200\\r\\nx-kmj-deploy-sha: " + SHA +
                "\\r\\n\\r\\nKMJ_HTTP_STATUS=200")
        with patch.object(mod, "fixed_run", return_value=good) as fixed:
            self.assertEqual(mod.public_https_response(), good)
        argv = fixed.call_args.args[0]
        self.assertIn("--max-redirs", argv)
        self.assertIn("0", argv)
        self.assertIn("--proto", argv)
        self.assertIn("=https", argv)
        self.assertEqual(argv[-1], mod.URL)
        self.assertTrue(mod.exact_https_sha_ok(good, SHA))
        self.assertFalse(mod.exact_https_sha_ok(good.replace(SHA, "c" * 40), SHA))

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
        good = "HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA + (
            "\r\ncontent-type: text/html\r\n\r\nKMJ_HTTP_STATUS=200")
        self.assertTrue(mod.exact_https_sha_ok(good, SHA))
        for bad in (
            good.replace(SHA, "c" * 40),
            good.replace("HTTP/2 200", "HTTP/2 302"),
            good.replace("KMJ_HTTP_STATUS=200", "KMJ_HTTP_STATUS=404"),
            good.replace("x-kmj-deploy-sha:", "x-other-header:"),
            good.replace("content-type:", "x-kmj-deploy-sha: " + SHA + "\r\ncontent-type:"),
            "HTTP/1.1 200\r\n\r\n" + good,
            "",
        ):
            self.assertFalse(mod.exact_https_sha_ok(bad, SHA))

    def test_protected_manifest_parent_and_same_fd_required(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "approval.json"
            path.write_text("{}")
            with patch.object(mod.os, "open", side_effect=AssertionError(
                    "untrusted parent must be rejected before opening")):
                self.assertIsNone(mod.protected_json(path))
        source = SOURCE.read_text()
        self.assertIn("os.O_NOFOLLOW", source)
        self.assertIn("os.fstat(fd)", source)
        self.assertIn("os.read(fd, 4097)", source)
        self.assertNotIn("path.read_bytes()", source)

    def test_systemctl_exit_code_cannot_be_ignored(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout="")):
            self.assertFalse(mod.fixed_run(["/usr/bin/systemctl", "start",
                                            mod.UNIT], return_success=True))
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout="")):
            self.assertTrue(mod.fixed_run(["/usr/bin/systemctl", "start",
                                           mod.UNIT], return_success=True))

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
