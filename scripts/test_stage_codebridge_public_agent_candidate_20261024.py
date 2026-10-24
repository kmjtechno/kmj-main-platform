#!/usr/bin/env python3
"""No-server CI contracts for the immutable non-activating KMJ P0 candidate."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/stage-codebridge-agent-public-origin-candidate-20261024.sh"
CODE = SCRIPT.read_text(encoding="utf-8")


class StageCodeBridgePublicOriginSafety(unittest.TestCase):
    def test_shell_parses(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_pinned_commit_not_floating_main(self):
        self.assertIn("b1d672bbc83a51ca3f8271435692825072444c8e", CODE)
        self.assertIn('checkout --detach -q FETCH_HEAD', CODE)
        self.assertIn('rev-parse HEAD)', CODE)
        self.assertNotIn("git pull", CODE)

    def test_fails_on_unexpected_live_release(self):
        self.assertIn('EXPECTED_ACTIVE="$ROOT/releases/platform-8070dad72c55"', CODE)
        self.assertIn("CURRENT_RELEASE_CHANGED", CODE)
        self.assertIn("CURRENT_POINTER_CHANGED", CODE)
        self.assertIn("/run/lock/kmj-main-platform-production-release.lock", CODE)

    def test_never_stages_real_production_credentials(self):
        self.assertIn('cp -- .env.example .env', CODE)
        self.assertIn("trap 'rm -f -- .env' EXIT", CODE)
        self.assertIn('CANDIDATE_ENV=ABSENT', CODE)
        self.assertIn('CANDIDATE_CONTAINS_ENV', CODE)
        self.assertNotIn('"$active/apps/platform/.env"', CODE)
        self.assertNotIn('"$ROOT/current/apps/platform/.env"', CODE)
        self.assertNotRegex(CODE, r"\bsource\s+.*\.env")

    def test_never_activates_or_mutates_production(self):
        for prohibited in [
            "systemctl restart", "systemctl reload", "systemctl stop",
            "artisan migrate", "artisan queue:", "ALTER ROLE", "rsync ",
            "git reset --hard", "ln -s", "ln -sf", "ln -sfn",
            "postconf ", "opendkim", "MAIL_MAILER=", "KMJ_BREVO_ACTIVATED=",
            "/etc/kmj-codebridge/main-platform-production-release.json",
            "pre-deploy-", "rclone ", "scp ", "sftp ",
        ]:
            self.assertNotIn(prohibited, CODE, prohibited)
        self.assertIn('PRODUCTION_ACTIVATION=NOT_ATTEMPTED', CODE)
        self.assertIn('LIVE_POINTER=UNCHANGED', CODE)

    def test_real_build_is_non_deploying(self):
        for expected in [
            "composer install --no-dev",
            "npm ci --ignore-scripts",
            "npm run build",
            "public/build/manifest.json",
            "vendor/autoload.php",
            "CANDIDATE_DIRTY_AFTER_BUILD",
            "verify_artifacts",
            "mv -T --", "flock -n 9",
        ]:
            self.assertIn(expected, CODE)


if __name__ == "__main__":
    unittest.main()
