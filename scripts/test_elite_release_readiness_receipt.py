#!/usr/bin/env python3
"""Pure negative tests: root Elite preflight receipt never stages or deploys."""
import importlib.util
import re
from pathlib import Path
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations" / "elite_release_readiness_receipt.py"
spec = importlib.util.spec_from_file_location("elite_receipt", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40
OLD = "platform-" + "b" * 12


class FixedGate:
    APPROVAL = Path("/fake/approval")
    ADMISSION_DIR = Path("/fake/admission")
    SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
    RELEASE_RE = re.compile(r"platform-[a-f0-9]{12}\Z")
    decision_value = "READY_APPROVED_RELEASE"
    healthy_https = True

    def protected_json(self, path):
        if path == self.APPROVAL:
            return {
                "approvedSha": SHA,
                "expectedCurrentRelease": OLD,
                "backupVerified": True,
                "rollbackVerified": True,
            }
        return {"schema": "kmj.autopublish.release-admission.elite-local.v2"}

    def live_release(self):
        return OLD

    def remote_sha(self):
        return SHA

    def candidate_sha(self, sha):
        return sha

    def decision(self, approval, admission, current, remote, candidate):
        return self.decision_value

    def public_https_response(self):
        return "opaque bounded fixed https result"

    def exact_https_sha_ok(self, response, sha):
        return self.healthy_https


class EliteReceiptTests(unittest.TestCase):
    def test_ready_decision_only_reports_preflight_not_deploy(self):
        result = mod.snapshot(FixedGate(), 200)
        self.assertEqual(result["decision"], "READY_APPROVED_RELEASE")
        self.assertEqual(result["host"], "KMJ-elite")
        self.assertEqual(result["approved_sha"], SHA)
        for key in ("staging_origin_verified", "scheduled_run_proven",
                    "independent_dr_verified", "deploy_triggered"):
            self.assertIs(result[key], False)

    def test_already_live_with_bad_public_https_is_blocked(self):
        gate = FixedGate()
        gate.decision_value = "ALREADY_LIVE"
        gate.healthy_https = False
        self.assertEqual(mod.snapshot(gate, 5)["decision"], "BLOCKED_ALREADY_LIVE_HEALTH")
        gate.healthy_https = True
        self.assertEqual(mod.snapshot(gate, 6)["decision"], "ALREADY_LIVE")

    def test_invalid_source_approval_cannot_invent_sha(self):
        gate = FixedGate()
        gate.protected_json = lambda _: {}
        data = mod.snapshot(gate, 1)
        self.assertIsNone(data["approved_sha"])
        self.assertIsNone(data["promoted_sha"])
        self.assertIsNone(data["candidate_sha"])

    def test_rejects_owner_unapproved_execution_and_untrusted_gate_paths(self):
        source = SOURCE.read_text()
        self.assertIn('mode.add_argument("--inspect"', source)
        self.assertIn('mode.add_argument("--publish"', source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("StrictHostKeyChecking=no", source)
        self.assertNotIn("os.symlink(", source)
        self.assertIn("/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py", source)
        self.assertIn("/run/kmj-main-platform", source)

    def test_publisher_refuses_untrusted_directory_even_with_valid_payload(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            directory.chmod(0o777)
            with patch.object(mod, "OUTPUT_DIR", directory), patch.object(
                mod, "OUTPUT", directory / "status.json"
            ):
                with self.assertRaisesRegex(ValueError, "BLOCKED_OUTPUT_PARENT"):
                    mod.publish({"schema": "kmj.elite.release-readiness.v1"})
                self.assertFalse((directory / "status.json").exists())


if __name__ == "__main__":
    unittest.main()
