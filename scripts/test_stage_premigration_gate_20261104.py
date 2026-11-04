"""Offline safety tests for no-write staging pre-migration inspection."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_PREMIGRATION_GATE_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_premigration", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class PremigrationSafety(unittest.TestCase):
    def test_compiles_and_pins_exact_candidate(self):
        compile(SOURCE.read_text(), str(SOURCE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.DB, "kmj_stage_a9796a25")
        self.assertEqual(m.ROLE, "kmjstage_a9796a25")
        self.assertEqual(m.OLD_PROD, "platform-574e443a2c75")
        self.assertEqual(m.OLD_STAGE, "b2e69decab3acd861e94e11992cd8a4cff4f2b94")

    def test_no_mutations_or_secret_stdout(self):
        code = SOURCE.read_text()
        tree = ast.parse(code)
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    calls.append(f.value.id + "." + f.attr)
        for bad in (
            "os.chmod", "os.fchmod", "os.chown", "os.fchown",
            "os.mkdir", "os.makedirs", "os.replace", "os.rename",
            "os.unlink", "os.remove", "os.symlink", "subprocess.Popen",
            "Path.write_text", "Path.write_bytes", "os.system", "os.popen",
            "socket.socket",
        ):
            self.assertNotIn(bad, calls)
        for bad in (
            "CREATE ROLE", "CREATE DATABASE", "ALTER ROLE", "DROP DATABASE",
            "php artisan", "systemctl ", "nginx -s", "git reset",
            "shell=True", "DB_PASSWORD=", "APP_KEY=",
        ):
            self.assertNotIn(bad, code)
        self.assertIn('STAGING_FPM_CONFIG", "NOT_MODIFIED"', code)
        self.assertIn('PRODUCTION_MUTATIONS", "NONE"', code)

    def test_env_classification_private_and_exact(self):
        values = {
            "APP_ENV": "staging", "APP_DEBUG": "false",
            "APP_URL": "https://staging.kmjtechno.com",
            "DB_CONNECTION": "pgsql", "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432", "DB_DATABASE": m.DB,
            "DB_USERNAME": m.ROLE, "DB_PASSWORD": "a" * 64,
            "LARAVEL_STORAGE_PATH": str(m.STORAGE),
            "APP_KEY": "base64:" + "A" * 43 + "=",
            "MAIL_MAILER": "log", "CODEBRIDGE_OAUTH_ENABLED": "false",
            "PUBLIC_INDEXING_ENABLED": "false",
        }
        src = ("\n".join(k + "=" + v for k, v in values.items()) + "\n").encode("ascii")
        self.assertEqual(m.parse_env(src, b"a" * 64 + b"\n"), "CANDIDATE_SCOPE_MATCH")
        self.assertEqual(m.parse_env(src, b"b" * 64 + b"\n"), "SECRET_MISMATCH")
        self.assertEqual(m.parse_env(src + b"DB_DATABASE=kmj_main\n", b"a" * 64 + b"\n"), "INVALID")
        self.assertEqual(m.parse_env(src.replace(b"APP_DEBUG=false", b"APP_DEBUG=true"),
                                     b"a" * 64 + b"\n"), "CANDIDATE_SCOPE_MISMATCH")
        self.assertEqual(m.parse_env(None, b"a" * 64 + b"\n"), "UNVERIFIED")
        self.assertEqual(m.parse_env(src, None), "UNVERIFIED")

    def test_php_early_probe_only_vendor_application_and_no_artisan(self):
        self.assertIn("vendor/autoload.php", m.PHP_PROBE)
        self.assertIn("new \\Illuminate\\Foundation\\Application", m.PHP_PROBE)
        self.assertNotIn("artisan", m.PHP_PROBE)
        self.assertNotIn("bootstrap/app.php", m.PHP_PROBE)
        good = SimpleNamespace(returncode=0, stdout=b"MATCH\n", stderr=b"")
        with patch.object(m.subprocess, "run", return_value=good) as run:
            self.assertEqual(m.early_php_probe(), "EXPLICIT_EARLY_BIND_MATCH")
            args = run.call_args.args[0]
            self.assertIn("LARAVEL_STORAGE_PATH=" + str(m.STORAGE), args)
            self.assertEqual(args[-2], "-r")
            self.assertEqual(args[-1], m.PHP_PROBE)
            self.assertEqual(args[0:4], ["/usr/sbin/runuser", "-u", "kmjstage", "--"])
            self.assertNotIn("DB_PASSWORD", repr(args))
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(
                returncode=9, stdout=b"secret", stderr=b"")):
            self.assertEqual(m.early_php_probe(), "UNVERIFIED")

    def test_fpm_pool_setting_classifies_missing_and_duplicate(self):
        tests = [
            (b"[kmjstage]\nuser=kmjstage\n", "MISSING"),
            (b"; env[LARAVEL_STORAGE_PATH]=/etc/private\n", "MISSING"),
            (b"env[LARAVEL_STORAGE_PATH] = " + str(m.STORAGE).encode() + b"\n", "EXACT_MATCH"),
            (b"env[LARAVEL_STORAGE_PATH]=/bad\n", "DRIFT_OR_DUPLICATE"),
            (b"env[LARAVEL_STORAGE_PATH]=/bad\nenv[LARAVEL_STORAGE_PATH]=/bad\n", "DRIFT_OR_DUPLICATE"),
        ]
        for raw, expected in tests:
            with self.subTest(expected=expected, raw=raw), patch.object(
                    m, "trusted_file", return_value=raw):
                self.assertEqual(m.fpm_pool_binding(), expected)

    def test_fresh_db_catalog_only_and_empty_schema_gate(self):
        out = [b"MATCH", b"0", b"2"]
        with patch.object(m, "fixed_run", side_effect=out) as run:
            self.assertEqual(m.db_catalog(), "RESTRICTED_OWNER_MATCH")
            sql = run.call_args.args[0][-1]
            self.assertIn("pg_database", sql)
            self.assertIn("pg_roles", sql)
            self.assertEqual(m.database_empty(), "EMPTY_PUBLIC_SCHEMA")
            self.assertEqual(m.database_empty(), "NOT_EMPTY")

    def test_non_root_cannot_read_files_or_db(self):
        with patch.object(sys, "argv", ["preflight.py"]), \
             patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m, "trusted_file", side_effect=AssertionError("no file read")), \
             patch.object(m, "db_catalog", side_effect=AssertionError("no DB read")):
            self.assertEqual(m.main(), 2)

    def test_pointer_fixed_symlink_and_no_untrusted_path(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "target"
            self.assertFalse(m.expected_links())
            self.assertEqual(m.trusted_file(p, 0, 0, 0o600, 100), None)


if __name__ == "__main__":
    unittest.main()
