"""Offline create-only Laravel staging ENV tests; no real KMJ paths or credentials."""
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_CANDIDATE_ENV_PREP_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_candidate_env", FILE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class CandidateEnvTests(unittest.TestCase):
    def test_pinned_candidate_scope_and_syntax(self):
        compile(FILE.read_text(), str(FILE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.DB, "kmj_stage_a9796a25")
        self.assertEqual(m.ROLE, "kmjstage_a9796a25")
        self.assertIn("platform-574e443a2c75", FILE.read_text())
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", FILE.read_text())
        for bad in ("git reset", "git clean", "php artisan", "systemctl ",
                    "nginx -s", "DROP DATABASE", "CREATE ROLE", "os.symlink(",
                    "os.rename(", "os.unlink(", "shell=True", "secret.txt"):
            self.assertNotIn(bad, FILE.read_text())

    def test_env_generated_only_for_candidate_private_no_debug(self):
        password = "a" * 64
        key = "base64:" + ("A" * 43) + "="
        value = m.env_bytes(password, key).decode("ascii")
        self.assertIn("APP_ENV=staging\n", value)
        self.assertIn("APP_DEBUG=false\n", value)
        self.assertIn("APP_URL=https://staging.kmjtechno.com\n", value)
        self.assertIn("DB_DATABASE=kmj_stage_a9796a25\n", value)
        self.assertIn("DB_USERNAME=kmjstage_a9796a25\n", value)
        self.assertIn("LARAVEL_STORAGE_PATH=/var/lib/kmj-main-platform-stage-runtime/", value)
        self.assertIn("MAIL_MAILER=log\n", value)
        self.assertIn("CODEBRIDGE_OAUTH_ENABLED=false\n", value)
        self.assertIn("PUBLIC_INDEXING_ENABLED=false\n", value)
        self.assertNotIn("DB_DATABASE=kmj_main", value)
        self.assertNotIn("APP_ENV=production", value)
        self.assertNotIn("APP_DEBUG=true", value)
        self.assertEqual(value.count("DB_PASSWORD="), 1)
        self.assertEqual(value.count("APP_KEY="), 1)

    def test_password_and_key_validation_rejects_injection(self):
        for password, key in (
            ("xx", "base64:" + "A" * 43 + "="),
            ("a" * 64 + "\nAPP_DEBUG=true", "base64:" + "A" * 43 + "="),
            ("a" * 64, "bad-key"),
        ):
            with self.assertRaises(SystemExit):
                m.env_bytes(password, key)

    @unittest.skipUnless(os.geteuid() == 0, "CI synthetic root fixture only")
    def test_fd_create_only_synthetic_permission_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fd = os.open(root, m.D_FLAGS)
            contents = m.env_bytes("1" * 64, "base64:" + "A" * 43 + "=")
            try:
                m.create_new_env(fd, contents, os.getgid())
                e = root / ".env"
                self.assertEqual(stat.S_IMODE(e.stat().st_mode), 0o640)
                self.assertEqual(e.stat().st_uid, 0)
                self.assertEqual(e.stat().st_nlink, 1)
                self.assertEqual(e.read_bytes(), contents)
                with self.assertRaises(SystemExit):
                    m.create_new_env(fd, contents, os.getgid())
                self.assertEqual(e.read_bytes(), contents)
            finally:
                os.close(fd)

    def test_symlink_collision_refused_in_sandbox(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").symlink_to("/etc/passwd")
            fd = os.open(root, m.D_FLAGS)
            try:
                with self.assertRaises(SystemExit):
                    m.create_new_env(fd, b"DATA\n", os.getgid())
                self.assertTrue((root / ".env").is_symlink())
            finally:
                os.close(fd)

    def test_root_and_host_gate_before_secret_access(self):
        with patch.object(sys, "argv", ["env-prep.py"]), \
             patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m, "private_password", side_effect=AssertionError("root gate")):
            with self.assertRaises(SystemExit) as err:
                m.main()
            self.assertEqual(err.exception.code, 2)
        with patch.object(sys, "argv", ["env-prep.py"]), \
             patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="different-host"), \
             patch.object(m, "private_password", side_effect=AssertionError("host gate")):
            with self.assertRaises(SystemExit):
                m.main()

    def test_fresh_candidate_db_check_is_readonly(self):
        sql = "SELECT count(*)"
        with patch.object(m.subprocess, "run") as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = b"1\n"
            self.assertTrue(m.fresh_db_owned())
            cmd = runner.call_args.args[0]
            self.assertIn("-c", cmd)
            self.assertIn("SELECT count(*) FROM pg_catalog.pg_database", cmd[-1])
            self.assertNotIn("DB_PASSWORD=", repr(cmd))
        with patch.object(m.subprocess, "run") as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = b"0\n"
            self.assertFalse(m.fresh_db_owned())


if __name__ == "__main__":
    unittest.main()
