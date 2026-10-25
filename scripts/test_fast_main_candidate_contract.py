"""Local, hardware-free safety contracts for the one-origin staging helper."""
import os
from pathlib import Path
import re
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parent / "operations" / "stage-fast-main-candidate-no-activation.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")


class OneDomainFastStageContract(unittest.TestCase):
    def call(self, *args: str):
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=8)

    def test_requires_exact_40_character_sha_before_filesystem_or_network(self):
        for arguments in [(), ("a" * 39,), ("not-a-commit",), ("a" * 41,)]:
            result = self.call(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertIn("KMJ_FAST_STAGE=BLOCKED_EXACT_SHA_REQUIRED", result.stdout)

    def test_wrong_machine_refuses_even_with_valid_sha(self):
        if os.geteuid() == 0 and os.uname().nodename.split(".")[0] == "KMJ-elite":
            self.skipTest("Do not exercise privileged host with a fake SHA")
        result = self.call("a" * 40)
        self.assertEqual(result.returncode, 2)
        self.assertIn("KMJ_FAST_STAGE=BLOCKED_WRONG_HOST", result.stdout)

    def test_pinned_main_and_private_isolation(self):
        self.assertIn("refs/heads/main", SOURCE)
        self.assertIn("REMOTE_MAIN_SHA_CHANGED", SOURCE)
        self.assertIn("git -C \"$dest\" checkout --detach -q FETCH_HEAD", SOURCE)
        self.assertIn("git -C \"$dest\" rev-parse HEAD", SOURCE)
        self.assertIn("flock -n 9", SOURCE)
        self.assertIn("runuser -u kmjprod -- env HOME=", SOURCE)
        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund", SOURCE)
        self.assertIn("composer install --no-dev --no-interaction", SOURCE)
        self.assertIn("CANDIDATE_DIRTY", SOURCE)
        self.assertIn("CANDIDATE_STATUS_UNAVAILABLE", SOURCE)
        self.assertIn("RUNTIME_ENV_REQUIRES_REVIEW", SOURCE)
        self.assertIn("LIVE_POINTER_CHANGED", SOURCE)

    def test_never_changes_production_or_demands_public_staging(self):
        self.assertIn("KMJ_PUBLIC_ORIGIN_POLICY=https://kmjtechno.com", SOURCE)
        self.assertIn("KMJ_PUBLIC_STAGING_REQUIRED=NO", SOURCE)
        self.assertIn("KMJ_PRODUCTION=UNCHANGED", SOURCE)
        self.assertIn("NEW_BACKUP_RESTORE_OWNER_APPROVAL_AND_GUARDED_ACTIVATION", SOURCE)
        self.assertNotIn("staging.kmjtechno.com", SOURCE)
        self.assertNotIn("systemctl reload", SOURCE)
        self.assertNotIn("systemctl restart", SOURCE)
        self.assertNotIn("php artisan migrate", SOURCE)
        self.assertNotIn("ln -sfn", SOURCE)
        self.assertNotIn("git reset", SOURCE)
        self.assertNotIn("git clean", SOURCE)
        self.assertNotIn("main-platform-production-release.json", SOURCE)
        self.assertRegex(SOURCE, r"rm -rf -- \"\$scratch\"")
        self.assertNotRegex(SOURCE, r"rm -rf -- \"\$ROOT")

if __name__ == "__main__":
    unittest.main()
