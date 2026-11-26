"""Fixture tests for scripts/kmj-owner-run-backup-checks.sh (local git, fake check scripts, no root)."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-owner-run-backup-checks.sh")
DRILL = "kmj-backup-restore-rowcount-drill.sh"
STORAGE = "kmj-backup-storage-completeness-check.sh"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-launcher-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        self.drill = '#!/bin/bash\necho "RESTORE_DRILL=PASS db=$KMJ_DRILL_LIVE_DB"\n'
        self.storage = '#!/bin/bash\necho "STORAGE_CHECK=PASS"\nexit 0\n'
        (self.repo / "scripts" / DRILL).write_text(self.drill)
        (self.repo / "scripts" / STORAGE).write_text(self.storage)
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.env_file = self.tmp / "app.env"
        self.env_file.write_text('APP_NAME=x\nDB_DATABASE="kmj_platform"\r\n')

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def run_launcher(self, pin_drill=None, pin_storage=None):
        env = {**os.environ, "KMJ_ALLOW_NONROOT_FOR_TESTS": "1", "KMJ_SKIP_FETCH": "1",
               "KMJ_REPO": str(self.repo), "KMJ_ENV_FILE": str(self.env_file),
               "KMJ_PIN_DRILL": pin_drill or sha(self.drill), "KMJ_PIN_STORAGE": pin_storage or sha(self.storage)}
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)

    def test_runs_both_pinned_scripts_and_writes_readable_summary(self):
        r = self.run_launcher()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BACKUP_CHECKS=DONE drill_exit=0 storage_exit=0", r.stdout)
        summary = next((self.repo / "work/qa/kmj-receipts").glob("summary.*.txt")).read_text()
        self.assertIn("RESTORE_DRILL=PASS db=kmj_platform", summary)
        self.assertIn("STORAGE_CHECK=PASS", summary)

    def test_hash_mismatch_blocks_before_running_anything(self):
        r = self.run_launcher(pin_drill="0" * 64)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BLOCKED_HASH_MISMATCH", r.stderr)
        self.assertFalse((self.repo / "work/qa/kmj-receipts").exists())

    def test_missing_script_on_origin_main_blocks(self):
        (self.repo / "scripts" / STORAGE).unlink()
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "rm")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        r = self.run_launcher()
        self.assertIn("SCRIPT_NOT_ON_ORIGIN_MAIN", r.stderr)

    def test_failing_check_is_reported_not_hidden(self):
        self.storage = '#!/bin/bash\necho "STORAGE_CHECK=FAIL"\nexit 1\n'
        (self.repo / "scripts" / STORAGE).write_text(self.storage)
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "f")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        r = self.run_launcher()
        self.assertIn("storage_exit=1", r.stdout)


if __name__ == "__main__":
    unittest.main()
