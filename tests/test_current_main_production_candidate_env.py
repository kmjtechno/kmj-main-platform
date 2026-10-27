"""Candidate-only public CodeBridge origin depends on actual backup SHA and existing release."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/stage-current-main-production-runtime-env-20261027.py"


class ProductionCandidateEnvContract(unittest.TestCase):
    def test_python_syntax(self):
        compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")

    def test_requires_exact_sha_and_current_release_before_any_write(self):
        for args in ([], ["main"], ["a"*40], ["a"*40, "wrong"]):
            with self.subTest(args=args):
                r = subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                                   capture_output=True, text=True, timeout=8)
                self.assertEqual(r.returncode, 2)
                self.assertIn("EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED", r.stderr)

    def test_host_preflight_does_not_touch_source(self):
        r = subprocess.run([sys.executable, "-B", str(SCRIPT), "a"*40,
                            "platform-8070dad72c55"], capture_output=True,
                           text=True, timeout=8)
        self.assertEqual(r.returncode, 2)
        self.assertIn("WRONG_OPERATOR_OR_HOST", r.stderr)

    def test_backup_identity_and_public_origin_guards(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for clause in (
            "CURRENT_RELEASE_CHANGED", "TARGET_NOT_CURRENT_MAIN",
            "TARGET_MAIN_MOVED", "read_candidate_head()",
            "check_backup()", "BACKUP_WITNESS_DIGEST_MISMATCH",
            "CANDIDATE_ALREADY_CACHED", "CANDIDATE_DIRTY",
            "APP_ENV=production", "APP_URL=https://kmjtechno.com",
            "CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com",
            "LIVE_ENV_PRODUCTION_ORIGIN_UNVERIFIED",
            "os.O_EXCL", "os.O_NOFOLLOW",
            "PRODUCTION_ACTIVATION=NOT_ATTEMPTED",
            "OFFSITE_INDEPENDENT_RESTORE=NOT_VERIFIED_BY_THIS_SCRIPT",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, s)

    def test_does_not_mutate_live_release_or_protected_approval(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl", "artisan migrate", "pg_restore",
            "git reset", "git clean", "shell=True",
            "source .env", "cat .env", "rollbackVerified=True",
            "/etc/kmj-codebridge/main-platform-production-release.json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
