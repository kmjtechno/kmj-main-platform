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


if __name__ == "__main__":
    unittest.main()
