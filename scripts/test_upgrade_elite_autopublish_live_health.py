import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/operations/upgrade-elite-autopublish-live-health-20261128.py"
spec = importlib.util.spec_from_file_location("upgrade", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class UpgradeContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / "scripts/operations/main_platform_autopublish_gate.py").read_bytes()
        self.gate = m.load_gate(self.raw)
        self.sha = "a" * 40
        self.live = "platform-" + self.sha[:12]
        self.approval = {"approvedSha": self.sha, "expectedCurrentRelease": "platform-" + "b" * 12,
                         "backupVerified": True, "rollbackVerified": True}
        self.admission = {"schema": "kmj.autopublish.release-admission.elite-local.v2",
                          "approvedSha": self.sha, "expectedCurrentRelease": self.approval["expectedCurrentRelease"],
                          "stagingSha": self.sha, "standingOwnerAuthorization": True,
                          **{key: True for key in self.gate.ELITE_LOCAL_ACCEPTANCE_KEYS}}

    def test_exact_new_pin_and_two_fixed_copies(self):
        self.assertEqual(m.blob(self.raw), m.NEW)
        self.assertEqual(len(m.GATES), 2)
        with self.assertRaisesRegex(ValueError, "SOURCE_PIN"):
            m.load_gate(self.raw + b"\n")

    def test_independent_witness_requires_actual_current_and_historical_admission(self):
        gate = self.gate
        with patch.object(m.os.path, "lexists", return_value=False), \
                patch.object(gate, "protected_json", side_effect=lambda p: self.approval if p == gate.APPROVAL else self.admission), \
                patch.object(gate, "live_release", return_value=self.live), \
                patch.object(gate, "candidate_sha", return_value=self.sha), \
                patch.object(gate, "public_https_response", return_value="HTTP/2 200\r\nx-kmj-deploy-sha: " + self.sha + "\r\n\r\nKMJ_HTTP_STATUS=200"):
            self.assertEqual(m.verify_live(gate)[2], self.live)
            with patch.object(m.os.path, "lexists", return_value=True):
                with self.assertRaisesRegex(ValueError, "PENDING_INTENT"):
                    m.verify_live(gate)
            with patch.object(gate, "candidate_sha", return_value=""):
                with self.assertRaisesRegex(ValueError, "HISTORICAL_ADMISSION"):
                    m.verify_live(gate)
            with patch.object(gate, "public_https_response", return_value=""):
                with self.assertRaisesRegex(ValueError, "PUBLIC_SHA"):
                    m.verify_live(gate)

if __name__ == "__main__":
    unittest.main()
