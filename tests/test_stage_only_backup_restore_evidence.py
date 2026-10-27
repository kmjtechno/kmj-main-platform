"""Staging only restore evidence must not touch production or live databases."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/backup-restore-isolated-stage-20261027.sh"


class StagingRecoverySafety(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(FILE)], check=True, timeout=10)

    def test_non_sha_refused_immediately(self):
        r = subprocess.run(["bash", str(FILE), "main"], capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED_SHA", r.stdout)

    def test_non_kmj_host_refused(self):
        r = subprocess.run(["bash", str(FILE), "a" * 40], capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED_HOST", r.stdout)

    def test_staging_only_backup_and_restore_gates(self):
        s = FILE.read_text(encoding="utf-8")
        for needle in (
            "/home/kmjstage/htdocs/staging.kmjtechno.com",
            "/home/kmjstage/releases", "refs/heads/staging-approved",
            "/root/kmj-stage-backups", "STAGING_DB_DISPOSABLE_RESTORE=PASS",
            "STAGING_DB_TABLE_COUNT_MATCH=PASS", "STAGING_STORAGE_SNAPSHOT=PASS",
            "STAGING_BACKUP_LOCAL_ROOT_ONLY=PASS", "STAGING_OFFSITE_BACKUP=NOT_VERIFIED",
            "STAGING_POINTER=UNCHANGED", "PRODUCTION_POINTER=UNCHANGED",
            "SHARED_STORAGE_NOT_PREPARED", "DB_SCOPE", "SCRATCH_PREEXISTS",
            "STAGING_DB_SNAPSHOT=PASS", "flock -n 9",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, s)

    def test_allows_only_scratch_postgres_restore(self):
        s = FILE.read_text(encoding="utf-8")
        self.assertIn('runuser -u postgres -- createdb --template=template0', s)
        self.assertIn('runuser -u postgres -- pg_restore', s)
        self.assertIn('runuser -u postgres -- dropdb --if-exists', s)
        for forbidden in (
            "artisan migrate", "db:wipe", "artisan db:seed",
            "systemctl restart", "systemctl reload", "systemctl enable",
            "ln -s", "mv -T", "git reset", "git clean", "rm -rf",
            "curl -k", "source .env", "cat .env", "DROP DATABASE kmj_stage",
            "DROP DATABASE kmjprod",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
