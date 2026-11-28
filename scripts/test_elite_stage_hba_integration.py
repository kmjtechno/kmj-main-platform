"""Verify candidate HBA isolation against an independent temporary PG cluster.

Only on ephemeral GitHub-hosted CI; never edits an installed cluster.
"""
import importlib.util
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent / 'operations'))
import elite_prepare_rehearsal as rehearsal
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("hba", Path(__file__).resolve().parent / "operations/plan-elite-isolated-stage-hba-20261128.py")
hba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hba)
verify_spec = importlib.util.spec_from_file_location("hba_verify", Path(__file__).resolve().parent / "operations/verify-elite-isolated-stage-hba-20261128.py")
verify = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verify)
install_spec = importlib.util.spec_from_file_location("hba_install", Path(__file__).resolve().parent / "operations/install-elite-isolated-stage-hba-20261128.py")
installer = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(installer)


class HbaPolicyTests(unittest.TestCase):
    def test_installer_rollback_preserves_original_on_reload_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "pg_hba.conf"
            old = b"local all all peer\n"
            new = hba.proposal(old)
            config.write_bytes(old)
            config.chmod(0o600)
            def read(path):
                return path.read_bytes()
            with patch.object(installer.plan, "read_hba", side_effect=read), \
                 patch.object(installer, "live_guard"), \
                 patch.object(installer, "reload", side_effect=[ValueError("RELOAD_FAILED"), None]):
                with self.assertRaisesRegex(ValueError, "RELOAD_FAILED"):
                    installer.install(config, old, new, root)
            self.assertEqual(config.read_bytes(), old)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(root.glob("kmj-stage-hba-backup-*/pg_hba.conf.original"))[0].read_bytes(), old)

    def test_live_probe_requires_explicit_rejection(self):
        self.assertTrue(verify.rejected(SimpleNamespace(returncode=2, stderr=b"pg_hba.conf rejects connection")))
        for error in (b"password authentication failed", b"connection refused", b"database does not exist"):
            self.assertFalse(verify.rejected(SimpleNamespace(returncode=2, stderr=error)))
        self.assertFalse(verify.rejected(SimpleNamespace(returncode=0, stderr=b"pg_hba.conf rejects connection")))
        with patch.object(verify.plan, "pg", return_value=verify.DB+"\nother_app"):
            self.assertEqual(verify.database_names(), [verify.DB, "other_app"])
        with patch.object(verify.plan, "pg", return_value=verify.DB+"\nhost=bad"):
            with self.assertRaisesRegex(ValueError, "DATABASE_NAME_UNSUPPORTED"):
                verify.database_names()

    def test_exact_role_first_match_and_original_bytes(self):
        old = b"local all all peer\nhost all all 127.0.0.1/32 scram-sha-256\n"
        planned = hba.proposal(old)
        self.assertTrue(planned.startswith(hba.prefix()))
        self.assertTrue(planned.endswith(old))
        self.assertIn(f"host {hba.DB} {hba.ROLE} 127.0.0.1/32 scram-sha-256".encode(), planned)
        self.assertIn(f"local all {hba.ROLE} reject".encode(), planned)
        self.assertIn(f"host all {hba.ROLE} all reject".encode(), planned)
        self.assertIn(f"host replication {hba.ROLE} all reject".encode(), planned)
        with self.assertRaisesRegex(ValueError, "CANDIDATE_HBA_ALREADY_REFERENCED"):
            hba.proposal(planned)


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true" and
                     os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
                     os.geteuid() == 0, "ephemeral hosted CI only")
class HbaRealIntegration(unittest.TestCase):
    def test_candidate_role_cannot_connect_to_other_public_database(self):
        pg = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
        self.assertTrue((pg / "initdb").is_file())
        account = pwd.getpwnam("postgres")
        with tempfile.TemporaryDirectory(prefix="kmj-ci-hba-") as tmp:
            base = Path(tmp)
            os.chown(base, account.pw_uid, account.pw_gid)
            data = base / "data"
            sock = base / "socket"
            sock.mkdir(mode=0o700)
            os.chown(sock, account.pw_uid, account.pw_gid)
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            def as_pg(program, *args):
                return subprocess.run(["/usr/sbin/runuser", "-u", "postgres", "--",
                                       str(pg / program), *map(str,args)], cwd="/",
                                      capture_output=True, timeout=60, check=True)
            as_pg("initdb", "-D", data, "-A", "trust", "--no-locale", "--no-sync")
            hba_file = data / "pg_hba.conf"
            old = b"local all all trust\nhost all all 127.0.0.1/32 scram-sha-256\n"
            hba_file.write_bytes(old)
            passwd = secrets.token_hex(24)
            passfile = base / "pgpass"
            passfile.write_text("*:*:*:"+hba.ROLE+":"+passwd+"\n")
            passfile.chmod(0o600)
            env = {"PATH":"/usr/bin:/bin", "LANG":"C", "LC_ALL":"C",
                   "PGPASSFILE":str(passfile), "PGCONNECT_TIMEOUT":"3"}
            def query(database, user, host, sql="SELECT current_database() || ':' || current_user;"):
                return subprocess.run([str(pg / "psql"), "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1",
                                       "-p", str(port), "-h", str(host), "-U", user, "-d", database],
                                      input=sql.encode(), env=env, cwd="/",
                                      capture_output=True, timeout=8)
            running = False
            try:
                as_pg("pg_ctl", "-D", data, "-l", base / "server.log", "-o",
                      f"-p {port} -h 127.0.0.1 -k {sock}", "-w", "start")
                running = True
                for sql in (f"CREATE ROLE {hba.ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '{passwd}';",
                            f"CREATE DATABASE {hba.DB} OWNER {hba.ROLE};",
                            "CREATE DATABASE other_app;"):
                    self.assertEqual(query("postgres", "postgres", sock, sql).returncode, 0)
                self.assertEqual(query("other_app", hba.ROLE, "127.0.0.1").returncode, 0)
                hba_file.write_bytes(hba.proposal(old))
                as_pg("pg_ctl", "-D", data, "reload")
                # Reload is asynchronous. Require an explicit HBA rejection,
                # not a missing DB, wrong password or unavailable listener.
                for _ in range(30):
                    result = query("other_app", hba.ROLE, "127.0.0.1")
                    if result.returncode != 0 and b"pg_hba.conf rejects connection" in result.stderr:
                        break
                    time.sleep(0.2)
                else:
                    self.fail("role-specific rejection never became active")
                self.assertEqual(query(hba.DB, hba.ROLE, "127.0.0.1").stdout.strip(),
                                 f"{hba.DB}:{hba.ROLE}".encode())
                for database, host in (("other_app", "127.0.0.1"), ("postgres", "127.0.0.1"),
                                       ("other_app", sock), (hba.DB, sock)):
                    denied = query(database, hba.ROLE, host)
                    self.assertNotEqual(denied.returncode, 0)
                    self.assertIn(b"pg_hba.conf rejects connection", denied.stderr)
                self.assertEqual(query("other_app", "postgres", sock).returncode, 0)
                self.assertEqual(query("postgres", "postgres", sock,
                    "SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;").stdout.strip(), b"0")
                # Exercise actual rehearsal rules and locally-generated SCRAM verifier
                # in this independent temporary cluster, preserving prior stage policy.
                name = rehearsal.names(secrets.token_hex(20))
                pw, nonce = secrets.token_hex(16), secrets.token_hex(16)
                with passfile.open("a") as f:
                    f.write("*:*:*:" + name + ":" + pw + "\n")
                current = hba_file.read_bytes()
                hba_file.write_bytes(rehearsal.isolation.proposal(current, name))
                as_pg("pg_ctl", "-D", data, "reload")
                for _ in range(30):
                    denied = query("other_app", name, "127.0.0.1")
                    if rehearsal.isolation.rejected(denied):
                        break
                    time.sleep(0.2)
                else:
                    self.fail("rehearsal role rejection not active before creation")
                for sql in rehearsal.sql_create(name, pw, nonce):
                    self.assertEqual(query("postgres", "postgres", sock, sql).returncode, 0)
                self.assertEqual(query(name, name, "127.0.0.1").stdout.strip(),
                                 f"{name}:{name}".encode())
                for database, host in (("other_app", "127.0.0.1"), ("postgres", "127.0.0.1"),
                                       ("other_app", sock), (name, sock)):
                    self.assertTrue(rehearsal.isolation.rejected(query(database, name, host)))
                self.assertEqual(query("other_app", "postgres", sock).returncode, 0)
            finally:
                if running:
                    as_pg("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    if "--pure" in sys.argv:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(HbaPolicyTests)
        expected = 3
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(HbaRealIntegration)
        expected = 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() and result.testsRun == expected and not result.skipped else 1)
