import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("legacy_hba", Path(__file__).resolve().parent /
    "operations/plan-elite-legacy-stage-hba-20261128.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
DB = "kmj_stage_example"
ROLE = "kmjstage_example"


class LegacyStageHbaPlan(unittest.TestCase):
    def test_scope_and_preserve_baseline(self):
        old = b"# baseline\nhost all all 127.0.0.1/32 scram-sha-256\n"
        for host in ("127.0.0.1", "localhost", "/var/run/postgresql"):
            result = m.proposal(old, DB, ROLE, host)
            self.assertEqual(result, m.prefix(DB, ROLE, host) + old)
            rules = result[:-len(old)].decode().splitlines()
            self.assertIn(f"local replication {ROLE} reject", rules)
            self.assertIn(f"host replication {ROLE} all reject", rules)
            self.assertIn(f"local all {ROLE} reject", rules)
            self.assertIn(f"host all {ROLE} all reject", rules)
            self.assertTrue(all(ROLE in line for line in rules if not line.startswith("#")))
            self.assertEqual(any("::1/128" in line for line in rules), host == "localhost")
            self.assertEqual(any(line.startswith(f"local {DB} ") for line in rules),
                             host == "/var/run/postgresql")

    def test_invalid_identity_or_prefix_rejected(self):
        for db, role, host in (("postgres", ROLE, "localhost"), (DB, "all", "localhost"),
                               (DB, ROLE, "example.com"), (DB, "kmjstage_x\nhost all all", "localhost")):
            with self.assertRaises(ValueError):
                m.prefix(db, role, host)
        with self.assertRaisesRegex(ValueError, "EXISTING_KMJ_PREFIX"):
            m.proposal(m.prefix(DB, ROLE, "localhost"), DB, ROLE, "localhost")

    def test_env_strict_no_duplicate_or_dsn(self):
        raw = (f"APP_ENV=staging\nAPP_URL=https://staging.kmjtechno.com\nDB_CONNECTION=pgsql\n"
               f"DB_DATABASE={DB}\nDB_USERNAME={ROLE}\nDB_HOST=127.0.0.1\n"
               "DB_PASSWORD=example-test-value\n").encode()
        self.assertEqual(m.identity(raw)[:3], (DB, ROLE, "127.0.0.1"))
        for extra in (b"DB_URL=postgres://example\n", b"DB_USERNAME=kmjstage_other\n"):
            with self.assertRaises(ValueError):
                m.identity(raw + extra)

    def test_only_explicit_hba_rejection_counts(self):
        self.assertTrue(m.explicitly_rejected(SimpleNamespace(returncode=2, stderr=b"pg_hba.conf rejects connection")))
        for err in (b"password authentication failed", b"no password supplied", b"Connection refused"):
            self.assertFalse(m.explicitly_rejected(SimpleNamespace(returncode=2, stderr=err)))
        self.assertFalse(m.explicitly_rejected(SimpleNamespace(returncode=0, stderr=b"")))


class LegacyStageHbaInstaller(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parent / "operations/install-elite-legacy-stage-hba-20261128.py"
        spec = importlib.util.spec_from_file_location("installer", path)
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)

    def test_plan_pin_matches(self):
        import hashlib
        raw = Path(m.__file__).read_bytes()
        self.assertEqual(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                         self.installer.PLAN_BLOB)

    def test_live_proof_never_sends_password_to_other_database(self):
        from unittest.mock import patch
        secret = "test-only"
        seen = []
        def probe(db, role, host, password=None):
            seen.append((db, host, password))
            if db == DB and host == "127.0.0.1":
                return SimpleNamespace(returncode=0, stdout=(DB+":"+ROLE).encode(), stderr=b"")
            return SimpleNamespace(returncode=2, stderr=b"pg_hba.conf rejects connection")
        with patch.object(m, "probe", side_effect=probe), patch.object(m, "catalog", return_value=[DB, "postgres"]):
            self.assertEqual(self.installer.live_proof(m, DB, ROLE, "127.0.0.1", secret, [DB, "postgres"]), 5)
        self.assertEqual(seen[0], (DB, "127.0.0.1", secret))
        self.assertTrue(all(p is None for _, _, p in seen[1:]))

    def test_auth_challenge_is_not_isolation(self):
        from unittest.mock import patch
        def probe(db, role, host, password=None):
            if db == DB and password is not None:
                return SimpleNamespace(returncode=0, stdout=(DB+":"+ROLE).encode(), stderr=b"")
            return SimpleNamespace(returncode=2, stderr=b"no password supplied")
        with patch.object(m, "probe", side_effect=probe):
            with self.assertRaisesRegex(ValueError, "OTHER_DB_NOT_EXPLICITLY_REJECTED"):
                self.installer.live_proof(m, DB, ROLE, "127.0.0.1", "test-only", [DB, "postgres"])

    def test_failed_live_proof_restores_original_bytes(self):
        import tempfile
        from unittest.mock import patch
        i = self.installer
        old, new = b"old", b"new"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "pg_hba.conf"
            path.write_bytes(old)
            names = [DB, "postgres"]
            original = (b"env", DB, ROLE, "127.0.0.1", "test-only", names, path, old)
            def replace(_plan, _path, expected, payload):
                self.assertEqual(path.read_bytes(), expected)
                path.write_bytes(payload)
            with patch.object(i, "snapshot", return_value=original), \
                 patch.object(i, "own_login"), patch.object(i, "replace", side_effect=replace), \
                 patch.object(i, "reload_config") as reload, \
                 patch.object(i, "validate_loaded", side_effect=ValueError("TEST_DENIAL")), \
                 patch.object(m, "hba", side_effect=lambda: (path, path.read_bytes())), \
                 patch.object(m, "pg", return_value="0"):
                with self.assertRaisesRegex(ValueError, "TEST_DENIAL"):
                    i.install(m, original, new, i.sha(old), i.sha(new), root=root)
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(reload.call_count, 2)


if __name__ == "__main__":
    unittest.main()
