"""Fixture tests for scripts/kmj-vault-sidecar-check.sh (no root, no keys, synthetic bytes)."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-vault-sidecar-check.sh")


class VaultSidecarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-vault-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.vault = self.tmp / "vault"
        self.vault.mkdir()
        self.receipts = self.tmp / "receipts"

    def pair(self, stamp, data=b"synthetic", sidecar_hash=None, sidecar=True):
        c = self.vault / f"{stamp}.tar.age"
        c.write_bytes(data)
        if sidecar:
            h = sidecar_hash or hashlib.sha256(data).hexdigest()
            (self.vault / f"{stamp}.tar.age.sha256").write_text(f"{h}  {c.name}\n")

    def run_check(self):
        env = {**os.environ, "KMJ_ALLOW_NONROOT_FOR_TESTS": "1", "KMJ_VAULT_DIR": str(self.vault),
               "KMJ_VAULT_RECEIPT_DIR": str(self.receipts)}
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)

    def test_all_match_passes_with_counts_only(self):
        self.pair("20261126T133036Z")
        self.pair("20261126T023521Z", b"other")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("COUNTS ciphers=2 match=2 mismatch=0 bad_format=0 missing_sidecar=0", r.stdout)
        text = next(self.receipts.glob("vault-sidecar.*.txt")).read_text()
        self.assertNotIn("2026112", text)
        self.assertIn("decrypted=no", text)

    def test_mismatch_fails(self):
        self.pair("20261126T133036Z", sidecar_hash="0" * 64)
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("mismatch=1", r.stdout)

    def test_missing_sidecar_and_bad_format_fail(self):
        self.pair("20261126T133036Z", sidecar=False)
        self.assertEqual(self.run_check().returncode, 1)
        self.pair("20261126T023521Z", sidecar_hash="zz")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_format=1", r.stdout)

    def test_empty_vault_fails_closed(self):
        self.assertEqual(self.run_check().returncode, 1)


if __name__ == "__main__":
    unittest.main()
