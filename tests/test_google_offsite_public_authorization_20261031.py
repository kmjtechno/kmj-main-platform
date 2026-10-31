"""Offline negative contracts for Google offsite SSH public-only enrollment."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/operations/authorize-google-offsite-key-20261031.py"
spec = importlib.util.spec_from_file_location("kmj_google_offsite", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GoogleOffsiteAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(mode=0o700)
        self.file = self.ssh / "authorized_keys"
        self.prior = "restrict ssh-ed25519 " + ("A" * 68) + " existing\n"
        self.file.write_text(self.prior)
        os.chmod(self.file, 0o600)

    def run_auth(self, mode):
        return m.process(mode, home=self.home, uid=os.geteuid())

    def test_public_blob_matches_owner_fingerprint(self):
        m.valid_public_key()
        self.assertEqual(m.EXPECTED_FP, "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk")

    def test_check_is_readonly_before_enrollment(self):
        self.assertEqual(self.run_auth("--check"), "NOT_REGISTERED")
        self.assertEqual(self.file.read_text(), self.prior)

    def test_authorize_preserves_prior_bytes_and_is_idempotent(self):
        self.assertEqual(self.run_auth("--authorize"), "APPENDED_RESTRICTED")
        self.assertEqual(self.file.read_text(), self.prior + m.RESTRICTED_LINE + "\n")
        self.assertEqual(self.run_auth("--check"), "ALREADY_AUTHORIZED_RESTRICTED")
        self.assertEqual(self.run_auth("--authorize"), "ALREADY_AUTHORIZED_RESTRICTED")
        self.assertEqual(self.file.read_text().count(m.PUBLIC_B64), 1)
        self.assertEqual(os.stat(self.file).st_mode & 0o077, 0)

    def test_missing_trailing_newline_preserves_old_contents(self):
        self.file.write_text("old-other-key-without-newline")
        self.assertEqual(self.run_auth("--authorize"), "APPENDED_RESTRICTED")
        self.assertEqual(self.file.read_text(), "old-other-key-without-newline\n" + m.RESTRICTED_LINE + "\n")

    def test_existing_unrestricted_same_key_is_not_normalized_or_replaced(self):
        before = "ssh-ed25519 " + m.PUBLIC_B64 + " unsafe\n"
        self.file.write_text(before)
        with self.assertRaisesRegex(m.Blocked, "DUPLICATE_OR_UNRESTRICTED"):
            self.run_auth("--authorize")
        self.assertEqual(self.file.read_text(), before)

    def test_existing_duplicate_key_fails_closed(self):
        before = (m.RESTRICTED_LINE + "\n") * 2
        self.file.write_text(before)
        with self.assertRaisesRegex(m.Blocked, "DUPLICATE_OR_UNRESTRICTED"):
            self.run_auth("--authorize")
        self.assertEqual(self.file.read_text(), before)

    def test_symlinked_file_refused_without_mutation(self):
        self.file.unlink()
        external = Path(self.tmp.name) / "external"
        external.write_text(self.prior)
        self.file.symlink_to(external)
        with self.assertRaises(m.Blocked):
            self.run_auth("--authorize")
        self.assertEqual(external.read_text(), self.prior)

    def test_hardlink_refused_without_mutation(self):
        duplicate = self.ssh / "another-name"
        os.link(self.file, duplicate)
        with self.assertRaisesRegex(m.Blocked, "AUTHORIZED_KEYS_UNSAFE"):
            self.run_auth("--authorize")
        self.assertEqual(self.file.read_text(), self.prior)

    def test_world_writable_directory_refused(self):
        os.chmod(self.ssh, 0o777)
        with self.assertRaisesRegex(m.Blocked, "OWNER_SSH_DIRECTORY_UNSAFE"):
            self.run_auth("--authorize")
        self.assertEqual(self.file.read_text(), self.prior)

    def test_unsafe_file_mode_refused(self):
        os.chmod(self.file, 0o666)
        with self.assertRaisesRegex(m.Blocked, "AUTHORIZED_KEYS_UNSAFE"):
            self.run_auth("--authorize")
        self.assertEqual(self.file.read_text(), self.prior)

    def test_no_new_authorized_keys_file_created(self):
        self.file.unlink()
        with self.assertRaisesRegex(m.Blocked, "AUTHORIZED_KEYS_MISSING"):
            self.run_auth("--authorize")
        self.assertFalse(self.file.exists())

    def test_root_wrong_machine_wrong_user_blocked(self):
        with patch.object(m.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(m.Blocked, "ROOT_NOT_ALLOWED"):
                m.allowed_owner()
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m.pwd, "getpwuid", return_value=type("P", (), {"pw_name": "info"})()), \
             patch.object(m.socket, "gethostname", return_value="not-google-vps1"):
            with self.assertRaisesRegex(m.Blocked, "WRONG_HOST_OR_ACCOUNT"):
                m.allowed_owner()
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m.pwd, "getpwuid", return_value=type("P", (), {"pw_name": "ubuntu"})()), \
             patch.object(m.socket, "gethostname", return_value="google-vps1"):
            with self.assertRaisesRegex(m.Blocked, "WRONG_HOST_OR_ACCOUNT"):
                m.allowed_owner()

    def test_main_error_never_dumps_path_or_key(self):
        with patch.object(m, "process", side_effect=m.Blocked("SECRET_PASSWORD")), \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(m.main(["--authorize"]), 3)
        output = stdout.getvalue()
        self.assertNotIn("SECRET", output)
        self.assertNotIn(m.PUBLIC_B64, output)

    def test_no_shell_network_or_service_reload(self):
        src = SRC.read_text()
        for danger in ("shell=True", "systemctl", "ssh-keyscan", "ssh-copy-id", "subprocess.run", "os.system(", "os.remove(", "os.unlink(", "chmod -R"):
            self.assertNotIn(danger, src)


if __name__ == "__main__":
    unittest.main()
