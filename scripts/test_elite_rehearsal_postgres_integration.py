"""Real PostgreSQL integration, ONLY on ephemeral GitHub hosted CI."""
import os
import pathlib
import secrets
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "operations"))
import elite_prepare_rehearsal as pr


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true" and
                     os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
                     os.geteuid() == 0, "ephemeral hosted CI only")
class PostgresCleanupIntegration(unittest.TestCase):
    def test_real_owner_nonce_and_nonforce_cleanup(self):
        name = pr.names(secrets.token_hex(20))
        nonce, password = secrets.token_hex(16), secrets.token_hex(16)
        self.assertFalse(pr.query_cleanup_owner(name, nonce))
        pr.psql(pr.sql_create(name, password, nonce))
        self.assertTrue(pr.query_cleanup_owner(name, nonce))
        self.assertFalse(pr.query_cleanup_owner(name, "0" * 32))
        pr.psql(['COMMENT ON ROLE "' + name + '" IS NULL'])
        self.assertFalse(pr.query_cleanup_owner(name, nonce))
        pr.psql(["COMMENT ON ROLE \"" + name + "\" IS 'kmj-disposable-rehearsal:" + nonce + "'"])
        self.assertTrue(pr.query_cleanup_owner(name, nonce))
        pr.psql(pr.sql_drop(name, nonce))
        self.assertFalse(pr.query_cleanup_owner(name, nonce))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PostgresCleanupIntegration)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # CI must actually exercise the integration test, not silently skip.
    sys.exit(0 if result.wasSuccessful() and result.testsRun == 1 and not result.skipped else 1)
