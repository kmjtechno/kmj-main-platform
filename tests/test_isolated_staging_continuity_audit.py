"""Read-only stage storage and schema continuity checks."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/audit-isolated-staging-continuity-20261027.sh"


class StageContinuityAuditSafety(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=10)

    def test_rejects_invalid_sha_before_any_host_access(self):
        run = subprocess.run(["bash", str(SCRIPT), "main"], capture_output=True, text=True, timeout=8)
        self.assertEqual(run.returncode, 2)
        self.assertIn("KMJ_STAGE_AUDIT=BLOCKED_INVALID_SHA", run.stdout)

    def test_rejects_non_kmj_host(self):
        run = subprocess.run(["bash", str(SCRIPT), "f" * 40], capture_output=True, text=True, timeout=8)
        self.assertEqual(run.returncode, 2)
        self.assertIn("KMJ_STAGE_AUDIT=BLOCKED_WRONG_HOST", run.stdout)

    def test_scoped_sources_and_migration_readback(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for clause in (
            "/home/kmjstage/releases", "/home/kmjstage/htdocs/staging.kmjtechno.com",
            "/home/kmjprod/current", "STAGING_ENV_PARITY",
            "for name in ('storage', 'public/storage')",
            "name.upper().replace('/', '_') + '_CONTINUITY='",
            "STAGING_DB_SCOPE", "STAGING_PENDING_MIGRATIONS",
            "STAGING_APPROVED_HEAD_MATCH", "migrate:status",
            "PRODUCTION_POINTER=UNCHANGED", "STAGING_POINTER=UNCHANGED",
            "KMJ_STAGE_AUDIT=READ_ONLY_COMPLETE",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, source)

    def test_no_mutating_commands_or_secret_logging(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl start", "systemctl reload", "systemctl restart",
            "ln -s", "mv -T", "git reset", "git clean", "git fetch",
            "artisan migrate --force", "artisan migrate:fresh",
            "php artisan db", "rm -rf", "source .env", "cat .env",
            "print(values)", "print(a)", "print(b)",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
