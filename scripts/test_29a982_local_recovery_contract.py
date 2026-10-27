"""Offline source-only contract for exact-SHA local backup/restore helper."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parent / "operations/prepare-29a982-p0-local-recovery-20261027.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")

class ExactCandidateBackupContract(unittest.TestCase):
    def test_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=10)

    def test_sha_and_owner_guards(self):
        for marker in (
            "readonly TARGET_SHA=29a98250b463998959fc52ac41b012aed1e76dba",
            "readonly SHORT_SHA=29a98250b463",
            '[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]]',
            '[[ "$OLD_NAME" == platform-8070dad72c55 ]]',
            "WRONG_CANDIDATE_SHA",
            "CANDIDATE_ENV_PRESENT",
            "EXISTING_EVIDENCE_REQUIRES_MANUAL_REVIEW",
            "flock -n 9", "export GIT_OPTIONAL_LOCKS=0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_real_local_restore_and_no_cutover(self):
        for marker in (
            "PRODUCTION_DATABASE_DUMP=PASS", "pg_dump",
            "storage/app .env", "pg_restore",
            "--auth-host=reject", "listen_addresses=''",
            "unix_socket_permissions=0700",
            "LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS",
            "LOCAL_SCHEMA_VERIFICATION PASS",
            "os.O_EXCL | os.O_NOFOLLOW",
            "LOCAL_BACKUP_WITNESS PASS",
            "PUBLISHED_BACKUP_DIGEST",
            "OFFSITE_BACKUP NOT_VERIFIED",
            "ROLLBACK_VERIFIED NOT_YET",
            "APPROVAL_UPDATED NO",
            "PRODUCTION_SWITCH NOT_ATTEMPTED",
            "trap cleanup EXIT", "os.fsync",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)
        for bad in ("b1d672bbc83a", "systemctl reload", "systemctl restart",
                    "artisan migrate", "ln -sfn", "ln -sf", "git reset --hard",
                    "git clean -fd", "main-platform-production-release.json",
                    "staging.kmjtechno.com"):
            with self.subTest(forbidden=bad):
                self.assertNotIn(bad, SOURCE)

if __name__ == "__main__":
    unittest.main()
