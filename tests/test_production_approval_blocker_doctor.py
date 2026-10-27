"""Guardrails for read-only protected Main Platform production diagnostics."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/audit-production-approval-blockers-20261027.py"


class ProductionApprovalDoctorContract(unittest.TestCase):
    def test_syntax(self):
        # Compile source in memory; do not write pyc.
        compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")

    def test_non_production_host_fails_before_touching_live_paths(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)], capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED_WRONG_HOST", proc.stdout)

    def test_rejects_caller_selected_target(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "f" * 40],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED_ARGUMENTS", proc.stdout)

    def test_git_inspection_uses_system_sbin_paths(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", source)
        self.assertIn('"/usr/sbin/runuser", "-u", "kmjprod"', source)
        self.assertIn("NO_GIT_METADATA", source)
        self.assertIn("BLOCKED_GIT_SHA_UNVERIFIED", source)
        self.assertIn("BLOCKED_ARTIFACT_MISSING", source)

    def test_checks_all_current_protected_dependencies(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for term in (
            "/home/kmjprod", "main-platform-production-release.json",
            "approvedSha", "expectedCurrentRelease",
            "backupVerified", "rollbackVerified",
            "pre-deploy-", "backupSha256",
            "CURRENT_MAIN_CANDIDATE", "CANDIDATE_RUNTIME_ENV",
            "MANIFEST_EXPECTED_CURRENT", "MANIFEST_TARGET_ALREADY_CURRENT",
            "TARGET_BACKUP_WITNESS", "TARGET_BACKUP_ARCHIVE",
            "REMOTE_MAIN_SHA", "refs/heads/staging-approved",
            "DISPOSABLE_RESTORE_EVIDENCE", "CANDIDATE_OWNER_AUTH_QA",
            "APPROVAL_RENEWAL", "NOT_PERFORMED", "READ_ONLY_COMPLETE",
        ):
            with self.subTest(term=term):
                self.assertIn(term, source)

    def test_no_mutations_auth_bypass_or_secret_echo(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "os.replace", "os.symlink", "os.remove", "os.unlink",
            ".write_text(", ".write_bytes(", "mkdir(",
            "shutil.copy", "shutil.move", "systemctl restart",
            "systemctl reload", "artisan migrate", "pg_restore",
            "git reset", "git clean", "curl -k", "shell=True",
            "source .env", "cat .env", "print(approval)",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
