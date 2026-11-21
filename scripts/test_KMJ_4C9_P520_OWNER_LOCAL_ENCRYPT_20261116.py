"""P520-only root candidate source guard; no remote execution."""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile
import unittest

SRC = Path(__file__).with_name("KMJ_4C9_P520_OWNER_LOCAL_ENCRYPT_20261116.sh")
SEAL = SRC.parent / "operations" / "seal-main-platform-p520-20261116.py"
spec = importlib.util.spec_from_file_location("p520_seal", SEAL)
seal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seal)


class P520CandidateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = SRC.read_text()
        cls.seal = SEAL.read_text()

    def test_bash_syntax(self):
        p = subprocess.run(["bash", "-n", str(SRC)], capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr.decode())

    def test_no_google_sftp_or_release_mutation(self):
        for forbidden in ("google-vps", "offsite-sftp.conf", "push-offsite-pinned-sftp", "systemctl", "ln -s", "git reset", "git clean"):
            self.assertNotIn(forbidden, self.s.lower())
        for required in ("P520_REMOTE_READBACK=NOT_VERIFIED", "PRODUCTION_RELEASE=UNCHANGED",
                         "GOOGLE_REMOTE_REQUIRED=NO", "PRODUCTION_APPROVAL=NOT_GRANTED",
                         "f9225fe2eb4270ad81252169500a22e219fa775b37fcf033340a109c9c8b6326"):
            self.assertIn(required, self.s)

    def test_strict_mode_argv(self):
        for args in ([], ["--help"], ["--prepare", "extra"], ["--approve"]):
            p = subprocess.run(["bash", str(SRC), *args], capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 2)
            self.assertIn(b"BLOCKED_EXACT_MODE", p.stdout)

    def test_sanitizes_env_and_p520_only(self):
        self.assertIn('if name == ".env"', self.seal)
        self.assertIn("production_env_excluded=YES", self.seal)
        self.assertIn("offsite-p520-{self.short}.tar.gz.age", self.seal)
        self.assertIn("EXACT_CE6_TO_4C9_REQUIRED", self.seal)
        self.assertNotIn("age1952vsyz25elfzn8slyhuc4k586dhw0er45yy26myhvv3lcp9qeps8mj7f5", self.seal)

    def test_p520_recipient_file_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "recipient"
            path.write_text("age1" + "q"*58 + "\n")
            path.chmod(0o600)
            self.assertEqual(seal.p520_recipient(path, os.geteuid()), "age1" + "q"*58)
            path.chmod(0o660)
            with self.assertRaises(RuntimeError):
                seal.p520_recipient(path, os.geteuid())
            path.chmod(0o600)
            sy = Path(temp) / "symlink"
            sy.symlink_to(path)
            with self.assertRaises(RuntimeError):
                seal.p520_recipient(sy, os.geteuid())
            hard = Path(temp) / "hard"
            hard.hardlink_to(path)
            with self.assertRaises(RuntimeError):
                seal.p520_recipient(path, os.geteuid())


if __name__ == "__main__":
    unittest.main()
