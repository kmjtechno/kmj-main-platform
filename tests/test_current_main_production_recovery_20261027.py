"""No-cutover recovery script accepts only exact main and exact current release."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/prepare-current-main-production-recovery-20261027.sh"


class CurrentMainRecoveryContract(unittest.TestCase):
    def test_bash_parse(self):
        subprocess.run(["bash", "-n", str(FILE)], check=True, timeout=10)

    def test_exact_arguments_only(self):
        for args in ([], ["main"], ["a" * 40], ["a" * 40, "not_release"]):
            with self.subTest(args=args):
                r = subprocess.run(["bash", str(FILE), *args], capture_output=True, text=True, timeout=8)
                self.assertEqual(r.returncode, 2)
                self.assertIn("KMJ_LOCAL_RECOVERY=BLOCKED", r.stdout)

    def test_other_host_does_not_start_backup(self):
        r = subprocess.run(
            ["bash", str(FILE), "a" * 40, "platform-8070dad72c55"],
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("WRONG_HOST", r.stdout)

    def test_exact_sha_and_current_link_gates(self):
        s = FILE.read_text(encoding="utf-8")
        for term in (
            'readonly TARGET_SHA="$1"', 'readonly EXPECTED_CURRENT_RELEASE="$2"',
            "MAIN_REMOTE_UNAVAILABLE", "TARGET_NOT_CURRENT_MAIN",
            "CURRENT_SOURCE_MISMATCH", "CURRENT_RELEASE_CHANGED",
            "TARGET_ALREADY_LIVE", "CANDIDATE_ARTIFACT_MISSING",
            "STORAGE_APP_HAS_LINKS", "REMOTE_MAIN_MOVED",
            "CURRENT_RELEASE_MOVED",
            "LOCAL_DISPOSABLE_POSTGRES_RESTORE", "LOCAL_BACKUP_WITNESS",
            "OFFSITE_INDEPENDENT_RESTORE", "NOT_VERIFIED",
            "ROLLBACK_DRILL", "NOT_VERIFIED",
            "PRODUCTION_SWITCH", "NOT_ATTEMPTED",
            "APPROVAL_UPDATED", "NO",
            "/var/backups/kmj-platform",
        ):
            with self.subTest(term=term):
                self.assertIn(term, s)

    def test_no_production_writes_or_fake_approval(self):
        s = FILE.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl restart", "systemctl reload", "artisan migrate",
            "ALTER ROLE", "DROP DATABASE", "git reset", "git clean",
            "ln -s", "os.replace", "backupVerified=True",
            "rollbackVerified=True", "/etc/kmj-codebridge/main-platform-production-release.json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
