#!/usr/bin/env python3
"""Source-only P0 real-backup local-restore operator safety gates."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/prepare-codebridge-public-agent-local-recovery-20261024.sh"
SOURCE = FILE.read_text(encoding="utf-8")

class P0RecoveryContracts(unittest.TestCase):
    def test_shell_syntax(self):
        out = subprocess.run(["bash","-n",str(FILE)],capture_output=True,text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_candidate_and_current_pinned(self):
        self.assertIn("readonly TARGET_SHA=b1d672bbc83a51ca3f8271435692825072444c8e",SOURCE)
        self.assertIn("readonly SHORT_SHA=b1d672bbc83a",SOURCE)
        self.assertIn("[[ \"$OLD_NAME\" == platform-8070dad72c55 ]]",SOURCE)
        self.assertIn("WRONG_CANDIDATE_SHA",SOURCE)
        self.assertIn("CURRENT_RELEASE_CHANGED",SOURCE)
        self.assertNotIn("f4b6d3ff96b0",SOURCE)

    def test_candidate_never_imports_production_secrets(self):
        self.assertIn("CANDIDATE_ENV_PRESENT",SOURCE)
        self.assertIn("CANDIDATE_FRONTEND_MISSING",SOURCE)
        self.assertNotIn("CANDIDATE_PUBLIC_UNREADABLE",SOURCE)
        self.assertNotIn("chown -R",SOURCE)

    def test_backup_real_local_and_disposable(self):
        for proof in (
            "'/usr/bin/pg_dump'", "PRODUCTION_DATABASE_DUMP=PASS",
            "LOCAL_BACKUP_INTEGRITY", "LOCAL_DISPOSABLE_POSTGRES_RESTORE",
            "LOCAL_SCHEMA_VERIFICATION", "LOCAL_BACKUP_WITNESS",
            "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
            "ROLLBACK_DRILL NOT_VERIFIED",
            "APPROVAL_UPDATED NO",
            "PRODUCTION_SWITCH NOT_ATTEMPTED",
            "--auth-host=reject", "listen_addresses=''",
            "--exit-on-error", "--no-owner", "--no-acl",
            "os.O_EXCL", "os.O_NOFOLLOW",
            "BACKUP_DIR_OWNER", "PRODUCTION_RELEASE_IN_PROGRESS",
        ):
            self.assertIn(proof,SOURCE,proof)

    def test_no_production_mutations_or_false_gates(self):
        for forbidden in (
            "systemctl restart", "systemctl reload", "systemctl start",
            "artisan migrate", "ln -s", "git reset --hard",
            "ALTER ROLE", "backupVerified", "rollbackVerified",
            "/etc/kmj-codebridge/main-platform-production-release.json",
            "rclone copy", "curl | bash",
        ):
            self.assertNotIn(forbidden,SOURCE,forbidden)
        self.assertIn("[[ ! -e \"$ARCHIVE\"",SOURCE)
        self.assertIn("sha256sum -c",SOURCE)

if __name__ == "__main__":
    unittest.main()
