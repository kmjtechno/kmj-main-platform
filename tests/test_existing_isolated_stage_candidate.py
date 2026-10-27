"""Tests for staging-only exact-SHA preparation, without live cutover."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/stage-existing-isolated-candidate-20261027.sh"


class StageCandidateSafety(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=10)

    def test_invalid_hash_blocks_before_touching_host(self):
        p = subprocess.run(["bash", str(SCRIPT), "--prepare", "main"], capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 2)
        self.assertIn("BLOCKED_SHA", p.stdout)

    def test_missing_host_authorization_fails_closed(self):
        p = subprocess.run(["bash", str(SCRIPT), "--inspect", "b" * 40], capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 2)
        self.assertIn("BLOCKED_HOST", p.stdout)

    def test_stage_scope_and_approval_guards(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "refs/heads/staging-approved", "APP_ENV=staging",
            "APP_URL=https://staging.kmjtechno.com", "/home/kmjstage/releases",
            "/home/kmjstage/htdocs/staging.kmjtechno.com", "/home/kmjprod/current",
            "STAGING_STORAGE_CONTINUITY=NOT_VERIFIED", "PRODUCTION_POINTER=UNCHANGED",
            "APPROVAL_MOVED", "LIVE_POINTER_CHANGED", "flock -n 9",
            "PREPARED_ISOLATED_NOT_LIVE", "--no-scripts", "--ignore-scripts",
        ):
            with self.subTest(required=required):
                self.assertIn(required, s)

    def test_no_live_switch_or_secret_logging(self):
        s = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl restart", "systemctl reload", "systemctl enable",
            "artisan migrate", "git reset --hard", "git clean", "ln -s",
            "readlink -n", "curl -k", "source .env", "cat .env",
            "chmod 777", "chown -R /home/kmjprod", "rm -rf /home/kmjstage/releases",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
