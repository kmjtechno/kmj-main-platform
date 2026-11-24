"""Fixture tests for scripts/kmj-owner-key-backup-vault.sh (no root, no real data)."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-owner-key-backup-vault.sh")
HAVE_AGE = shutil.which("age") and shutil.which("age-keygen")


@unittest.skipUnless(HAVE_AGE, "age is required for this contract test")
class OwnerKeyVaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-owner-vault-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.daily = self.tmp / "daily"
        self.out = self.tmp / "vault"
        self.daily.mkdir()
        self.key = self.tmp / "key.txt"
        gen = subprocess.run(["age-keygen", "-o", str(self.key)], capture_output=True, text=True, check=True)
        public = [l.split()[-1] for l in (gen.stderr + gen.stdout).splitlines() if "ublic key" in l][0]
        self.rcpt = self.tmp / "recipient.txt"
        self.rcpt.write_text(public + "\n")
        self.snapshot("20261124T145907Z", b"dump-bytes")

    def snapshot(self, stamp, payload):
        d = self.daily / stamp
        (d / "platform-storage").mkdir(parents=True)
        (d / "platform.dump").write_bytes(payload)
        (d / "platform-storage" / "a.txt").write_text("storage")
        sums = "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(d)}\n"
            for p in sorted(d.rglob("*")) if p.is_file()
        )
        (d / "SHA256SUMS").write_text(sums)
        return d

    def run_script(self, rcpt=None):
        env = {
            "PATH": os.environ["PATH"],
            "KMJ_DAILY_DIR": str(self.daily),
            "KMJ_OWNER_VAULT_DIR": str(self.out),
            "KMJ_OWNER_RECIPIENT_FILE": str(rcpt or self.rcpt),
            "KMJ_ALLOW_NONROOT_FOR_TESTS": "1",
        }
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)

    def test_newest_snapshot_is_sealed_and_owner_can_decrypt(self):
        self.snapshot("20261125T010101Z", b"newer-dump")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OWNER_VAULT=PASS", r.stdout)
        self.assertIn("STAMP=20261125T010101Z", r.stdout)
        cipher = self.out / "20261125T010101Z.tar.age"
        self.assertTrue(cipher.is_file())
        side = (self.out / "20261125T010101Z.tar.age.sha256").read_text().split()[0]
        self.assertEqual(side, hashlib.sha256(cipher.read_bytes()).hexdigest())
        plain = self.tmp / "plain.tar"
        subprocess.run(["age", "-d", "-i", str(self.key), "-o", str(plain), str(cipher)], check=True)
        with tarfile.open(plain) as t:
            data = t.extractfile("20261125T010101Z/platform.dump").read()
        self.assertEqual(data, b"newer-dump")

    def test_rerun_never_overwrites(self):
        self.assertEqual(self.run_script().returncode, 0)
        cipher = self.out / "20261124T145907Z.tar.age"
        before = cipher.read_bytes()
        r = self.run_script()
        self.assertEqual(r.returncode, 0)
        self.assertIn("ALREADY_PRESENT", r.stdout)
        self.assertEqual(cipher.read_bytes(), before)

    def test_tampered_snapshot_is_refused(self):
        (self.daily / "20261124T145907Z" / "platform.dump").write_bytes(b"tampered")
        r = self.run_script()
        self.assertEqual(r.returncode, 5)
        self.assertIn("SNAPSHOT_CHECKSUM_MISMATCH", r.stderr)
        self.assertFalse(list(self.out.glob("*.tar.age")))

    def test_bad_recipient_is_refused(self):
        bad = self.tmp / "bad.txt"
        bad.write_text("ssh-ed25519 AAAA codex-agent\n")
        r = self.run_script(bad)
        self.assertEqual(r.returncode, 3)
        self.assertIn("RECIPIENT_NOT_AGE_PUBLIC_KEY", r.stderr)

    def test_stray_directory_names_are_ignored(self):
        (self.daily / "notes").mkdir()
        (self.daily / "20261124T145907Z-copy").mkdir()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("STAMP=20261124T145907Z", r.stdout)

    def test_no_snapshot_is_refused(self):
        shutil.rmtree(self.daily / "20261124T145907Z")
        r = self.run_script()
        self.assertEqual(r.returncode, 4)
        self.assertIn("NO_DAILY_SNAPSHOT", r.stderr)

    def test_non_root_is_refused_without_test_flag(self):
        if os.geteuid() == 0:
            self.skipTest("running as root")
        env = {"PATH": os.environ["PATH"], "KMJ_DAILY_DIR": str(self.daily),
               "KMJ_OWNER_VAULT_DIR": str(self.out), "KMJ_OWNER_RECIPIENT_FILE": str(self.rcpt)}
        r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ROOT_REQUIRED", r.stderr)


if __name__ == "__main__":
    unittest.main()
