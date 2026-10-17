"""Zero-cost exact-head PR verifier integration using a synthetic local repo.

Never contacts GitHub, needs no credentials and does not touch production.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/ci/verify-live-pr-head.sh"


@unittest.skipUnless(os.name == "posix" and shutil.which("git") and shutil.which("bash"), "requires POSIX Git/Bash")
class LivePRHeadContractTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="kmj-qa-contract-")
        self.addCleanup(self.scratch.cleanup)
        root = Path(self.scratch.name)
        self.repo = root / "kmj-main-platform"
        self.repo.mkdir(mode=0o700)
        script_dir = self.repo / "scripts" / "ci"
        script_dir.mkdir(parents=True)
        self.script = script_dir / "verify-live-pr-head.sh"
        self.script.write_bytes(SOURCE.read_bytes())
        for name in (
            "verify-codebridge-dashboard-pr.sh",
            "verify-super-admin-pr.sh",
            "verify-postgres-staging.sh",
        ):
            script = script_dir / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'test -z "$POTENTIAL_PRODUCTION_SECRET"\n'
                'echo "SYNTHETIC_VERIFIER=PASS"\n',
                encoding="utf-8",
            )
        plat = self.repo / "apps" / "platform"
        plat.mkdir(parents=True)
        (plat / "composer.lock").write_text('{"lock":"A"}\n', encoding="utf-8")
        (plat / "package-lock.json").write_text('{"lock":"B"}\n', encoding="utf-8")
        self.git = shutil.which("git")
        subprocess.run([self.git, "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run([self.git, "config", "user.email", "ci@localhost"], cwd=self.repo, check=True)
        subprocess.run([self.git, "config", "user.name", "KMJ Synthetic QA"], cwd=self.repo, check=True)
        subprocess.run([self.git, "add", "."], cwd=self.repo, check=True)
        subprocess.run([self.git, "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.sha = subprocess.check_output(
            [self.git, "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        self.fakebin = root / "fakebin"
        self.fakebin.mkdir()
        fake_git = self.fakebin / "git"
        fake_git.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == '-C' && \"$3\" == 'remote' && \"$4\" == 'get-url' ]]; then\n"
            "  echo 'https://github.com/kmjtechno/kmj-main-platform.git'; exit 0\n"
            "fi\n"
            "if [[ \"$1\" == '-C' && \"$3\" == 'ls-remote' ]]; then\n"
            "  printf '%s\\t%s\\n' \"$MOCK_PR_HEAD\" \"$6\"; exit 0\n"
            "fi\n"
            "exec \"$SYNTHETIC_REAL_GIT\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_git.chmod(0o700)
        fake_id = self.fakebin / "id"
        fake_id.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == '-u' ]]; then echo 1000; else /usr/bin/id \"$@\"; fi\n",
            encoding="utf-8",
        )
        fake_id.chmod(0o700)

    def run_qa(self, *args, pr_head=None):
        env = os.environ.copy()
        env.update(
            PATH=f"{self.fakebin}:{env.get('PATH', '')}",
            SYNTHETIC_REAL_GIT=str(self.git),
            MOCK_PR_HEAD=pr_head or self.sha,
            POTENTIAL_PRODUCTION_SECRET="SECRET_MUST_NOT_REACH_VERIFIER",
        )
        return subprocess.run(
            ["bash", str(self.script), *args],
            cwd=self.repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )

    def test_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SOURCE)], text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_safe_frontend_admin_and_postgres_profiles(self):
        for profile in ("frontend", "admin", "postgres"):
            with self.subTest(profile=profile):
                result = self.run_qa("445", self.sha, profile)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("QA_VERIFIED_REMOTE_HEAD=" + self.sha, result.stdout)
                self.assertIn("SYNTHETIC_VERIFIER=PASS", result.stdout)
                self.assertIn("QA_GITHUB_ACTIONS_STATUS=NOT_VERIFIED", result.stdout)
                self.assertNotIn("SECRET_MUST_NOT_REACH_VERIFIER", result.stdout)

    def test_invalid_pr_sha_and_profile_are_blocked(self):
        for args in (
            ("0", self.sha, "frontend"),
            ("445;exit 0", self.sha, "frontend"),
            ("445", "not-a-sha", "frontend"),
            ("445", self.sha, "../../bad"),
        ):
            with self.subTest(args=args):
                result = self.run_qa(*args)
                self.assertEqual(result.returncode, 2)

    def test_stale_remote_head_fails_before_candidate_execution(self):
        result = self.run_qa("445", self.sha, "frontend", pr_head="a" * 40)
        self.assertEqual(result.returncode, 3)
        self.assertIn("PR head advanced", result.stderr)
        self.assertNotIn("SYNTHETIC_VERIFIER=PASS", result.stdout)

    def test_dependency_lockfile_drift_fails_closed(self):
        (self.repo / "apps/platform/composer.lock").write_text('{"lock":"DRIFT"}\n', encoding="utf-8")
        # A tracked main-file edit is a stricter check than dependency drift.
        result = self.run_qa("445", self.sha, "frontend")
        self.assertEqual(result.returncode, 3)
        self.assertIn("uncommitted changes", result.stderr)
        self.assertNotIn("SYNTHETIC_VERIFIER=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
