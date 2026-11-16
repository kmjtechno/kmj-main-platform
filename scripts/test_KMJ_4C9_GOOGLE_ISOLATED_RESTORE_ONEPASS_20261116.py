"""4C9 Google isolated restore: source contracts and adversarial CLI negatives."""
from pathlib import Path
import subprocess
import unittest

SRC = Path(__file__).with_name("KMJ_4C9_GOOGLE_ISOLATED_RESTORE_ONEPASS_20261116.sh")
SHA = "4c9d59103b99a6cfe675bb7b8961fc956eb294f0"
PREV = "platform-ce6ad7dc9d89"
PINS = (
    "adbb341ae298dcfb3ec3e017dcd7010ac4fde47b4a46042afcff6f36ef6a75f2",
    "4e0a7c61f317d1ecacfe6bf8a3c3199bb3fdaaf33b92c23b25e34f45c57de166",
    "a5cc97d5395f7ab4ed5a0a1f426f13a5dd26cfc575323b213276c5cee1bb9171",
)


class Google4C9SourceSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = SRC.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        result = subprocess.run(["bash", "-n", str(SRC)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_identity_is_constant(self):
        self.assertIn("readonly CANDIDATE=" + SHA, self.s)
        self.assertIn("readonly PREDECESSOR=" + PREV, self.s)
        self.assertIn("readonly SHORT=4c9d59103b99", self.s)

    def test_all_four_independently_exact_pinned_sources(self):
        for pin in PINS:
            self.assertEqual(self.s.count(pin), 1)
        self.assertIn("KMJ_GOOGLE_SOURCE_HASHES 4_PASS", self.s)
        self.assertIn('checked "$work/repo/scripts/$RESTORE" "$RESTORE_SHA"', self.s)
        self.assertIn('checked "$work/repo/scripts/$BUNDLE" "$BUNDLE_SHA"', self.s)
        self.assertIn('checked "$work/repo/scripts/$PARITY" "$PARITY_SHA"', self.s)
        self.assertIn("readonly IMPORTER_SHA=7229c1cdcacab3353a7566636ddd62e4bbdb48d74f65a755ff65c5dd1707be7b", self.s)
        self.assertIn('checked "$SCRIPTS/$IMPORTER" "$IMPORTER_SHA"', self.s)
        self.assertIn('blocked EXACT_VAULT_CIPHER_IMPORT', self.s)

    def test_never_uses_root_prod_db_or_mutates_release(self):
        for forbidden in ("sudo ", "systemctl", "php artisan", "git reset",
                          "git clean", "curl -k", "ln -s", "rm -rf",
                          "/home/kmjprod/current", "/etc/kmj-codebridge/main-platform-production-release.json",
                          "exec('", "eval ", "ssh -o StrictHostKeyChecking=no"):
            self.assertNotIn(forbidden, self.s)
        for required in ("GOOGLE_NONROOT_IDENTITY", "SCRATCH_NOT_USER_PRIVATE",
                         "CIPHER_IMPORT_NOT_PRIVATE", "CIPHER_SHA_MISMATCH",
                         "SOURCE_SHA_MISMATCH", "SOURCE_WRITABLE_BY_OTHERS",
                         "SNAPSHOT_INSTALL", "RECEIPT_IDENTITY OPERATOR_SUPPLIED_NOT_INDEPENDENTLY_ATTESTED",
                         "PRODUCTION_ACTIVATION NOT_ATTEMPTED"):
            self.assertIn(required, self.s)

    def test_no_external_environment_leaks_to_restorer(self):
        self.assertIn("env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/info", self.s)
        self.assertIn("KMJ_ACK_ISOLATED_RECOVERY=YES", self.s)
        self.assertIn('KMJ_EXPECTED_ENCRYPTED_SHA256="$encrypted_sha"', self.s)
        self.assertIn('KMJ_EXPECTED_SOURCE_LOCAL_SHA256="$source_sha"', self.s)
        self.assertIn('TMPDIR="$SCRATCH"', self.s)

    def test_cli_rejects_bad_shapes_before_host_or_key_checks(self):
        cases = [
            [], ["--restore"],
            ["--restore", "--encrypted-sha256", "x" * 64, "--source-local-sha256", "a" * 64],
            ["--restore", "--encrypted-sha256", "a" * 64, "--source-local-sha256", "B" * 64],
            ["--restore", "--encrypted-sha256", "a" * 64],
            ["--inspect", "junk"], ["--prepare"],
            ["--restore", "--source-local-sha256", "a" * 64, "--encrypted-sha256", "b" * 64],
        ]
        for args in cases:
            with self.subTest(args=args):
                p = subprocess.run(["bash", str(SRC), *args], capture_output=True,
                                   check=False, timeout=10)
                self.assertEqual(p.returncode, 2)
                self.assertTrue(p.stdout.startswith(b"KMJ_4C9_GOOGLE_RESTORE=BLOCKED_"))


if __name__ == "__main__":
    unittest.main()
