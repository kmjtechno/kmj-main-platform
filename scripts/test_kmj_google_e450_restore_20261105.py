"""Source-only contracts for the exact e450 Google independent restore.
Never touches Google, ELITE, any real backup, or production data.
"""
from pathlib import Path
import re
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parent / "operations/kmj-google-e450-independent-restore-20261105.sh"
CANDIDATE = "e450c6829cf19246b658c263abee4ec6c1f77bd6"
CIPHER_SHA = "a8d4a58f129dbf21ad5d5271e5dea9e12a7cb229a1974f44f9b3feb3da71e4a3"
SOURCE_SHA = "706b735bf8d2dd7712a19f5cfc42fb4bd4b363adf04459eae68dd8af4c9832c5"

class GoogleE450RecoverySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_locked_receipt_digest_candidate_and_size(self):
        s = self.text
        for x in (
            "N='offsite-e450c6829cf1.tar.gz.age'",
            "E='" + CIPHER_SHA + "'",
            "L='" + SOURCE_SHA + "'",
            "--candidate-sha " + CANDIDATE,
            "--expected-release platform-574e443a2c75",
            "349227",
        ):
            self.assertIn(x, s)
        self.assertNotIn("offsite-b07a7165373e.tar.gz.age", s)
        self.assertNotIn("--candidate-sha b07a7165373e0f2555f0623713943ea9bba94cea", s)

    def test_no_new_key_or_production_change(self):
        s = self.text
        self.assertIn("$(id -un) == info", s)
        self.assertIn("$(hostname -s) == google-vps1", s)
        self.assertIn("[[ $# == 0 ]]", s)
        self.assertIn("O_NOFOLLOW", s)
        self.assertIn("stat -c '%u:%a:%h:%s'", s)
        self.assertIn("sha256sum", s)
        self.assertIn("KMJ_ACK_ISOLATED_RECOVERY=YES", s)
        self.assertIn("KMJ_EXPECTED_ENCRYPTED_SHA256=\"$E\"", s)
        self.assertIn("KMJ_EXPECTED_SOURCE_LOCAL_SHA256=\"$L\"", s)
        self.assertIn("GOOGLE_E450_RESTORE=INDEPENDENT_DISPOSABLE_PASS", s)
        for forbidden in (
            "systemctl restart", "systemctl reload", "ALTER ROLE",
            "DROP DATABASE", "git reset", "git clean",
            "StrictHostKeyChecking=no", "curl -k", "chmod 777", "curl | bash",
        ):
            self.assertNotIn(forbidden, s)

    def test_pinned_independently_verified_release_neutral_sources(self):
        s = self.text
        self.assertIn("https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/b07a7165373e0f2555f0623713943ea9bba94cea", s)
        for digest in (
            "adbb341ae298dcfb3ec3e017dcd7010ac4fde47b4a46042afcff6f36ef6a75f2",
            "4e0a7c61f317d1ecacfe6bf8a3c3199bb3fdaaf33b92c23b25e34f45c57de166",
            "a5cc97d5395f7ab4ed5a0a1f426f13a5dd26cfc575323b213276c5cee1bb9171",
        ):
            self.assertIn(digest, s)
        self.assertIn("sha256sum -c -", s)
        self.assertNotIn("curl -k", s)

    def test_operator_refuses_bad_host_or_extra_arguments_before_any_io(self):
        p = subprocess.run(["bash", str(SCRIPT), "--unexpected"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("GOOGLE_E450_RESTORE=BLOCKED_NO_ARGS", p.stdout)
        self.assertTrue(re.search(r"^GOOGLE_E450_RESTORE=BLOCKED_NO_ARGS$", p.stdout, re.M))

if __name__ == "__main__":
    unittest.main()
