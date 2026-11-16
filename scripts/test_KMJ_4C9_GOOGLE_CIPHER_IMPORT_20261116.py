"""Offline adversarial fixtures for exact 4C9 no-overwrite age ciphertext import."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("KMJ_4C9_GOOGLE_CIPHER_IMPORT_20261116.py")
spec = importlib.util.spec_from_file_location("google_4c9_import", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class VaultImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.vault, self.scratch = root / "vault", root / "scratch"
        self.vault.mkdir(mode=0o700)
        self.scratch.mkdir(mode=0o700)
        self.uid = os.geteuid()
        self.payload = b"age-encryption.org/v1\n" + b"A" * 512
        self.expected = hashlib.sha256(self.payload).hexdigest()
        self.file = self.vault / m.NAME
        self.file.write_bytes(self.payload)
        self.file.chmod(0o600)

    def test_copy_and_idempotence(self):
        self.assertEqual(m.import_exact(self.vault, self.scratch, self.expected, self.uid), "COPIED_EXACT_SHA")
        out = self.scratch / m.NAME
        self.assertEqual(out.read_bytes(), self.payload)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertEqual(m.import_exact(self.vault, self.scratch, self.expected, self.uid), "ALREADY_PRESENT_EXACT_SHA")

    def test_wrong_digest_never_writes(self):
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, "0" * 64, self.uid)
        self.assertFalse((self.scratch / m.NAME).exists())

    def test_existing_bad_file_not_replaced(self):
        out = self.scratch / m.NAME
        out.write_bytes(b"X" * 300)
        out.chmod(0o600)
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)
        self.assertEqual(out.read_bytes(), b"X" * 300)

    def test_duplicate_name_rejected(self):
        nested = self.vault / "nested"
        nested.mkdir(mode=0o700)
        f = nested / m.NAME
        f.write_bytes(self.payload)
        f.chmod(0o600)
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)

    def test_symlink_and_hardlink_rejected(self):
        self.file.unlink()
        self.file.symlink_to("/etc/passwd")
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)
        self.file.unlink()
        self.file.write_bytes(self.payload)
        self.file.chmod(0o600)
        os.link(self.file, self.vault / "other")
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)

    def test_permissions_and_size_rejected(self):
        self.file.chmod(0o666)
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)
        self.file.chmod(0o600)
        self.file.write_bytes(b"tiny")
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, hashlib.sha256(b"tiny").hexdigest(), self.uid)

    def test_unsafe_scratch_and_symlink_target_rejected(self):
        self.scratch.chmod(0o777)
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)
        self.scratch.chmod(0o700)
        (self.scratch / m.NAME).symlink_to("/etc/passwd")
        with self.assertRaises(m.Block):
            m.import_exact(self.vault, self.scratch, self.expected, self.uid)

    def test_bad_cli_denied_before_host_and_key(self):
        p = subprocess.run([sys.executable, str(SOURCE), "--encrypted-sha256", "G" * 64], capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertIn(b"BLOCKED_EXACT_SHA_ARGUMENT", p.stdout)


if __name__ == "__main__":
    unittest.main()
