"""No-production-change preflight contracts for the one-shot offsite evidence chain."""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/prepare-full-offsite-evidence-20261031.sh"
TEXT = SRC.read_text()


class FullOffsiteEvidenceContract(unittest.TestCase):
    def test_shell_syntax_and_fails_before_root_for_bad_inputs(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(SRC)], capture_output=True).returncode, 0)
        for args in [[], ["not-a-sha"], ["--candidate-sha", "invalid", "--expected-release", "platform-574e443a2c75"],
                     ["--candidate-sha", "a"*40, "--expected-release", "unknown"]]:
            r = subprocess.run(["bash", str(SRC), *args], capture_output=True, timeout=8)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(b"KMJ_OFFSITE_RECOVERY=BLOCKED_", r.stdout)
            self.assertNotIn(b"KMJ_PHASE=", r.stdout)

    def test_exact_sha_locked_sources(self):
        self.assertIn("SOURCE_COMMIT=5da955a03ccf9b98afc62e138325d454a65dca6d", TEXT)
        sources = {
            "STAGE_SHA": "ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24",
            "LOCAL_SHA": "9812f831841ede684cc7a62c378ca35f43fb557dbc402c881785e506b508ff6f",
            "SEAL_SHA": "410f4348a4a0bbb7101f36345c1df09162660cb72a7aaf13ed35337951ae18ef",
            "PUSH_SHA": "547e624cc031045406add6b653d5925a46aa5d1aa6563a12f13dedc3c2aebdff",
        }
        for name, expected in sources.items():
            self.assertIn(f"{name}={expected}", TEXT)
            self.assertEqual(len(expected), 64)
        self.assertEqual(TEXT.count('sha256sum -c -'), 1)
        self.assertEqual(TEXT.count('download "$'), 4)
        self.assertIn("--proto '=https' --tlsv1.2", TEXT)

    def test_order_of_stages_and_no_unattested_credit(self):
        ordered = [TEXT.index("KMJ_PHASE="+p) for p in (
            "ISOLATED_CANDIDATE_BUILD",
            "REAL_LOCAL_DATABASE_AND_UPLOADS_BACKUP_RESTORE",
            "AGE_ENCRYPTION_OF_SANITIZED_BACKUP",
            "PINNED_GOOGLE_SFTP_NO_CLOBBER_AND_READBACK",
        )]
        self.assertEqual(ordered, sorted(ordered))
        self.assertIn("GOOGLE_INDEPENDENT_RESTORE=NOT_VERIFIED", TEXT)
        self.assertIn("PRODUCTION_RELEASE=UNCHANGED", TEXT)
        self.assertNotIn("PRODUCTION_RELEASE=LIVE", TEXT)

    def test_fixed_pinned_paths_and_no_live_cutover(self):
        self.assertIn("LIVE=/home/kmjprod/current", TEXT)
        self.assertIn("offsite-sftp.conf", TEXT)
        self.assertIn("LIVE_CHANGED_AFTER_UPLOAD", TEXT)
        for forbidden in ("systemctl ", "git reset", "git clean", "rsync --delete",
                          "ln -s ", "ln -sfn", "nginx -s reload", "migrate --force",
                          "database restore into production", "ssh-copy-id",
                          "StrictHostKeyChecking=no", "curl -k", "curl --insecure"):
            self.assertNotIn(forbidden, TEXT)
        self.assertIn("EXPECTED_RELEASE", TEXT)
        self.assertIn("EXACT_ARGS", TEXT)

    def test_correct_executables_for_each_pinned_script(self):
        self.assertIn('bash "$work/$STAGE_SCRIPT" "$CANDIDATE"', TEXT)
        self.assertIn('bash "$work/$LOCAL_SCRIPT" "$CANDIDATE" "$EXPECTED"', TEXT)
        self.assertIn('python3 -I "$work/$SEAL_SCRIPT" --candidate-sha "$CANDIDATE" --expected-release "$EXPECTED"', TEXT)
        self.assertIn('bash "$work/$PUSH_SCRIPT" --candidate-sha "$CANDIDATE"', TEXT)


if __name__ == "__main__":
    unittest.main()
