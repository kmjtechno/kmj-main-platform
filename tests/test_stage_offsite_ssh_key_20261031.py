"""P0 offsite client key staging contract: no overwrite, no backup action."""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/stage-offsite-ssh-key-20261031.py"
spec = importlib.util.spec_from_file_location("offsite_stage_key", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class KeyStageTests(unittest.TestCase):
    def test_root_and_host_and_argument_gates_precede_file_access(self):
        for argv, uid, host in [
            (["--prepare", "other"], 0, "kmj-elite"),
            (["--prepare"], 1000, "kmj-elite"),
            (["--prepare"], 0, "not-kmj-elite"),
            (["--wrong"], 0, "kmj-elite"),
        ]:
            with patch.object(m.os, "geteuid", return_value=uid), \
                 patch.object(m.socket, "gethostname", return_value=host), \
                 patch.object(m, "stage", side_effect=AssertionError("invoked!")), \
                 redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(argv), 2)
                self.assertIn("BLOCKED_HOST_ROOT_OR_ARGS", out.getvalue())

    def test_no_key_generation_when_checking_missing_pair(self):
        with patch.object(m, "protected_dir"), \
             patch.object(m, "protected_file", side_effect=[False, False]), \
             patch.object(m, "run_keygen", side_effect=AssertionError("must not run")), \
             redirect_stdout(io.StringIO()) as out:
            m.stage("--check")
        self.assertIn("OFFSITE_KEYPAIR=ABSENT", out.getvalue())

    def test_existing_keys_never_replaced_or_regenerated(self):
        with patch.object(m, "protected_dir"), \
             patch.object(m, "protected_file", side_effect=[True, True]), \
             patch.object(m, "run_keygen", side_effect=AssertionError("must not generate")), \
             patch.object(m, "public_key", return_value="public"), \
             redirect_stdout(io.StringIO()) as out:
            m.stage("--prepare")
        self.assertIn("EXISTS_UNCHANGED", out.getvalue())

    def test_partial_keypair_fails_closed(self):
        for a, b in [(True, False), (False, True)]:
            with patch.object(m, "protected_dir"), \
                 patch.object(m, "protected_file", side_effect=[a, b]), \
                 patch.object(m, "run_keygen", side_effect=AssertionError("must not generate")):
                with self.assertRaisesRegex(m.Blocked, "PARTIAL_KEYPAIR"):
                    m.stage("--prepare")

    def test_keygen_is_fixed_no_passphrase_and_safe_mode(self):
        argv = []
        def fake(cmd, **kwargs):
            argv.append(cmd)
            return b""
        with patch.object(m, "protected_dir"), \
             patch.object(m, "protected_file", side_effect=[False, False, True, True]), \
             patch.object(m, "run_keygen", side_effect=fake), \
             patch.object(m, "public_key", return_value="public"), \
             redirect_stdout(io.StringIO()) as out:
            m.stage("--prepare")
        self.assertEqual(len(argv), 1)
        self.assertEqual(argv[0][:7], ["-q", "-t", "ed25519", "-a", "100", "-N", ""])
        self.assertEqual(argv[0][-2:], ["-f", str(m.PRIVATE)])
        self.assertIn("STAGED_NEW", out.getvalue())

    def test_rejects_symlink_and_untrusted_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            with patch.object(m, "DIRECTORY", d), patch.object(m, "PRIVATE", d / "key"), patch.object(m, "PUBLIC", d / "key.pub"):
                (d / "key").symlink_to("/etc/passwd")
                with self.assertRaises(m.Blocked):
                    m.protected_file(d / "key", private=True)
                (d / "key").unlink()
                (d / "key").write_text("private")
                with self.assertRaises(m.Blocked):
                    m.protected_file(d / "key", private=True)

    def test_real_keygen_creates_public_that_matches_private_in_disposable_directory(self):
        with tempfile.TemporaryDirectory(prefix="kmj-offsite-key-test-") as tmp:
            key = Path(tmp) / "one"
            proc = subprocess.run(
                [m.KEYGEN, "-q", "-t", "ed25519", "-N", "", "-a", "16",
                 "-f", str(key), "-C", "test-only"],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=12,
                check=False, env=m.ENV,
            )
            self.assertEqual(proc.returncode, 0)
            pub = (key.with_suffix(".pub")).read_text().strip().split()
            derived = subprocess.run([m.KEYGEN, "-y", "-P", "", "-f", str(key)],
                capture_output=True, text=True, timeout=12, check=True, env=m.ENV).stdout.strip().split()
            self.assertEqual(pub[:2], derived[:2])
            self.assertIsNotNone(m.PUBLIC_RE.fullmatch(" ".join(pub)))
            self.assertEqual(os.stat(key).st_mode & 0o077, 0)

    def test_output_never_emits_secret_even_if_keygen_fails(self):
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(m, "stage", side_effect=m.Blocked("SECRET/private/path")), \
             redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(["--prepare"]), 3)
        self.assertNotIn("SECRET", out.getvalue())
        self.assertNotIn("/root/", out.getvalue())

    def test_source_never_writes_authorized_keys_or_starts_backup_service(self):
        raw = SRC.read_text()
        self.assertNotIn("shell=True", raw)
        self.assertNotIn("systemctl", raw)
        self.assertNotIn("authorized_keys", raw.split('class Blocked')[1])
        self.assertNotIn("sftp ", raw)
        self.assertNotIn("chmod -R", raw)
        self.assertNotIn("ssh-copy-id", raw)
        self.assertIn("REMOTE_AUTHORIZATION=NOT_VERIFIED", raw)


if __name__ == "__main__":
    unittest.main()
