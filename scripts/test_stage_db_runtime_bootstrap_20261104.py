"""Synthetic root-only fixed-scope tests; never contact actual PostgreSQL."""
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_DB_RUNTIME_BOOTSTRAP_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_db_runtime", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class IsolatedDbRuntimeTests(unittest.TestCase):
    def test_fixed_candidate_and_no_live_dependencies(self):
        s = SOURCE.read_text()
        compile(s, str(SOURCE), "exec")
        self.assertEqual(m.SHA, "a9796a25a2801cd303a69f5ad468aa9a704e5fff")
        self.assertEqual(m.DB, "kmj_stage_a9796a25")
        self.assertEqual(m.ROLE, "kmjstage_a9796a25")
        self.assertEqual(str(m.RUNTIME_PARENT), "/var/lib/kmj-main-platform-stage-runtime")
        self.assertIn("platform-574e443a2c75", s)
        self.assertIn("b2e69decab3acd861e94e11992cd8a4cff4f2b94", s)
        for forbidden in (
            "systemctl ", "nginx -s", "ssh ", "git reset ", "git clean ",
            "DROP ROLE", "DROP DATABASE", "ALTER DATABASE kmj_main",
            "CREATE ROLE kmj ", "psql -c", "shell=True", "pg_dump",
            "subprocess.Popen(", "os.symlink(",
        ):
            self.assertNotIn(forbidden, s)

    def test_role_and_db_scoped_sql(self):
        with patch.object(m, "pg", return_value=b"0") as call:
            self.assertEqual(m.catalog("role"), 0)
            args = call.call_args.args[0]
            self.assertEqual(args[:6], ["-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres"])
            self.assertIn("pg_catalog.pg_roles", args[-1])
        self.assertIn("REVOKE ALL ON DATABASE", SOURCE.read_text())
        with self.assertRaises(SystemExit):
            m.catalog("prod")
        with patch.object(m, "pg", return_value=b"2"):
            with self.assertRaises(SystemExit):
                m.catalog("role")

    def test_rejects_unprivileged_or_wrong_host_before_mutation(self):
        with patch.object(m.os, "geteuid", return_value=1000), \
             patch.object(m, "exact_pointers", side_effect=AssertionError("no access")), \
             patch.object(m, "new_dir", side_effect=AssertionError("no write")):
            with self.assertRaises(SystemExit):
                m.main()
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="wronghost"), \
             patch.object(m, "new_dir", side_effect=AssertionError("no write")):
            with self.assertRaises(SystemExit):
                m.main()

    def test_runtime_missing_role_or_db_gate_aborts_without_create(self):
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(m, "exact_pointers", return_value=True), \
             patch.object(m, "mirror_ready"), \
             patch.object(m, "root_dir"), \
             patch.object(m.os.path, "lexists", return_value=False), \
             patch.object(m, "catalog", side_effect=[1]), \
             patch.object(m, "new_dir", side_effect=AssertionError("no writes")):
            with self.assertRaises(SystemExit):
                m.main()

    @unittest.skipUnless(os.geteuid() == 0, "disposable CI root only")
    def test_full_synthetic_bootstrap_no_real_db_or_prod(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / "private-runtime"
            candidate = base / m.SHA
            creds = candidate / "credentials"
            secret = creds / "postgres-password"
            storage = candidate / "storage"
            state = {"role": 0, "db": 0, "revoked": False}
            captured_sql = []

            def fake_sql(sql):
                captured_sql.append(sql)
                if sql.startswith("CREATE ROLE "):
                    state["role"] = 1
                elif sql.startswith("CREATE DATABASE "):
                    state["db"] = 1
                elif sql.startswith("REVOKE ALL "):
                    state["revoked"] = True
                else:
                    raise AssertionError("unexpected SQL")

            def fake_pwd(name):
                if name == "kmjstage":
                    return SimpleNamespace(pw_uid=27777)
                if name == "postgres":
                    return SimpleNamespace(pw_uid=200)
                raise AssertionError("unexpected account")

            with patch.multiple(m, RUNTIME_PARENT=base, RUNTIME=candidate,
                                SECRET_DIR=creds, SECRET_FILE=secret,
                                STORAGE=storage), \
                 patch.object(m.os, "geteuid", return_value=0), \
                 patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
                 patch.object(m, "exact_pointers", return_value=True), \
                 patch.object(m, "root_dir"), \
                 patch.object(m, "mirror_ready"), \
                 patch.object(m, "catalog", side_effect=lambda which: state[which]), \
                 patch.object(m, "sql_stdin", side_effect=fake_sql), \
                 patch.object(m, "database_owned_by_role", side_effect=lambda: state["role"] == 1 and state["db"] == 1), \
                 patch.object(m.pwd, "getpwnam", side_effect=fake_pwd), \
                 patch.object(m.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=27777)):
                self.assertEqual(m.main(), 0)

            self.assertTrue(state["revoked"])
            self.assertTrue(secret.is_file())
            self.assertEqual(stat.S_IMODE(secret.stat().st_mode), 0o600)
            self.assertEqual(secret.stat().st_uid, 0)
            self.assertEqual(stat.S_IMODE(creds.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o711)
            self.assertEqual(stat.S_IMODE(candidate.stat().st_mode), 0o711)
            self.assertEqual(stat.S_IMODE(storage.stat().st_mode), 0o700)
            self.assertEqual(storage.stat().st_uid, 27777)
            self.assertEqual((storage / "app/private").stat().st_uid, 27777)
            self.assertEqual(len(captured_sql), 3)
            self.assertTrue(re.fullmatch("[0-9a-f]{64}\n", secret.read_text()))
            self.assertIn(secret.read_text().strip(), captured_sql[0])
            self.assertNotIn(secret.read_text().strip(), captured_sql[1])
            self.assertFalse((candidate / ".env").exists())
            self.assertFalse((storage / "framework/views").exists())

    def test_preexisting_runtime_parent_means_no_sql_mutations(self):
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(m, "exact_pointers", return_value=True), \
             patch.object(m, "mirror_ready"), \
             patch.object(m, "root_dir"), \
             patch.object(m.os.path, "lexists", return_value=True), \
             patch.object(m, "sql_stdin", side_effect=AssertionError("do not create")):
            with self.assertRaises(SystemExit):
                m.main()


if __name__ == "__main__":
    unittest.main()
