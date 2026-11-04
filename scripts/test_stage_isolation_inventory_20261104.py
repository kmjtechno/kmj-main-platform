"""Offline guard tests for the fixed, read-only staging group + PG inventory."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_ISOLATION_INVENTORY_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_isolation", FILE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class StageIsolationTests(unittest.TestCase):
    def test_compiles_pinned_names(self):
        compile(FILE.read_text(), str(FILE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.STAGE_DATABASE, "kmj_stage_a9796a25")
        self.assertEqual(m.STAGE_ROLE, "kmjstage_a9796a25")
        self.assertEqual(str(m.BASE), "/var/lib/kmj-main-platform-stage-serving")

    def test_source_has_no_host_mutations(self):
        source = FILE.read_text()
        tree = ast.parse(source)
        calls = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    calls.append(f.value.id + "." + f.attr)
        for forbidden in (
            "os.chown", "os.fchown", "os.chmod", "os.mkdir", "os.makedirs",
            "os.rename", "os.replace", "os.unlink", "os.remove",
            "os.system", "os.popen", "subprocess.Popen", "Path.write_text",
            "Path.unlink", "Path.mkdir", "socket.socket",
        ):
            self.assertNotIn(forbidden, calls)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("CREATE ROLE", source)
        self.assertNotIn("CREATE DATABASE", source)
        self.assertNotIn("GRANT ", source)
        self.assertNotIn("php artisan", source)
        self.assertNotIn("systemctl ", source)
        self.assertIn("READ_ONLY_COMPLETE", source)

    def test_access_denies_writes(self):
        with patch.object(m, "test_as", side_effect=lambda usr, op, path: {
            "-r": True, "-w": False
        }.get(op)):
            self.assertEqual(m.access_class("kmjstage", Path("/x")), "PASS_READ_NO_WRITE")
        with patch.object(m, "test_as", side_effect=lambda usr, op, path: {
            "-r": False, "-w": False
        }.get(op)):
            self.assertEqual(m.access_class("www-data", Path("/x"), False), "PASS_DENIED_NO_WRITE")
        with patch.object(m, "test_as", side_effect=lambda usr, op, path: {
            "-r": True, "-w": True
        }.get(op)):
            self.assertEqual(m.access_class("www-data", Path("/x")), "BLOCKED_WRITABLE")

    def test_pg_sql_allowlist(self):
        self.assertEqual(m.pg_exists("pg_authid", "rolpassword", "test"), "UNVERIFIED")
        self.assertEqual(m.pg_exists("pg_database", "datname", "arbitrary"), "UNVERIFIED")
        self.assertEqual(m.pg_exists("pg_roles", "rolname", "postgres"), "UNVERIFIED")

    def test_unprivileged_process_no_db_or_file_probe(self):
        with patch.object(m.os, "geteuid", return_value=1001), \
             patch.object(m, "pg_exists", side_effect=AssertionError("DB forbidden")), \
             patch.object(m, "metadata", side_effect=AssertionError("FS forbidden")):
            self.assertEqual(m.main(), 2)

    def test_no_raw_values_or_secret_read(self):
        s = FILE.read_text()
        for name in ("STAGING_FPM_CODE_READ", "STAGING_NGINX_STATIC_READ",
                     "STAGING_FPM_STATIC_DENIAL", "STAGING_NGINX_CODE_DENIAL",
                     "STAGING_FRESH_DATABASE", "STAGING_FRESH_DB_ROLE",
                     "STAGING_PROTECTED_APPROVAL", "NOT_MODIFIED",
                     "PRODUCTION_POINTER_CHANGED", "NO"):
            self.assertIn(name, s)
        self.assertNotIn(".read_text(", s)
        self.assertNotIn(".read_bytes(", s)
        self.assertNotIn("print(p.stdout", s)

    def test_stage_pointer_fixed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "staging"
            self.assertEqual(m.pointer(path, {"expected"}), "MISSING")
            path.symlink_to("expected")
            self.assertEqual(m.pointer(path, {"expected"}), "EXPECTED")
            self.assertEqual(m.pointer(path, {"wrong"}), "DRIFT")
            path.unlink()
            path.mkdir()
            self.assertEqual(m.pointer(path, {"expected"}), "UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
