"""Contract for linking only an offline staging candidate to current stage storage."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/prepare-isolated-stage-storage-20261027.sh"


class StageStoragePreparationSafety(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=10)

    def test_bad_sha_fails_before_host_access(self):
        r = subprocess.run(["bash", str(SCRIPT), "--prepare", "main"], capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED_SHA", r.stdout)

    def test_non_kmj_host_fails_closed(self):
        r = subprocess.run(["bash", str(SCRIPT), "--inspect", "a" * 40], capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED_HOST", r.stdout)

    def test_candidate_only_shared_storage_and_site_pointer_guards(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for expected in (
            "refs/heads/staging-approved", "/home/kmjstage/releases",
            "/home/kmjstage/htdocs/staging.kmjtechno.com", "/home/kmjprod/current",
            "STAGING_LIVE_SOURCE_SHA", "APPROVED_SHA_MOVED", "STAGING_ENV",
            "ENV_MISMATCH", "OLD_STORAGE_LINKS", "OLD_PUBLIC_STORAGE_MISSING",
            "CANDIDATE_LIVE", "runuser -u kmjstage -- ln -s",
            "STAGING_POINTER=UNCHANGED", "PRODUCTION_POINTER=UNCHANGED",
            "STAGING_BACKUP_AND_RESTORE=NOT_YET_VERIFIED",
            "STAGING_ACTIVATION=NOT_ATTEMPTED", "OLD_RELEASE_RETAIN_REQUIRED",
            "restore_on_failure", "flock -n 9",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, s)

    def test_no_live_production_or_database_mutations(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "artisan migrate", "pg_restore", "dropdb", "createdb",
            "systemctl restart", "systemctl reload", "systemctl enable",
            "nginx -s", "git reset", "git clean", "rm -rf", "curl -k",
            "source .env", "cat .env", "ln -s -f", "mv -Tf",
            "mv -T -- \"$stage\"", "mv -T -- \"$prod\"",
            "chmod 777",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
