"""Fixture tests for scripts/kmj-backup-job-inventory.sh (stub systemctl, no root)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-backup-job-inventory.sh")

STUB = """#!/usr/bin/env bash
case "$1" in
  list-timers) echo "Thu 2026-11-27 15:45:00 IST 23h Thu 2026-11-26 15:45:01 IST 20min ago kmj-v3-dual-local-health.timer kmj-v3-dual-local-health.service";;
  list-units) echo "kmj-v3-dual-local-health.service loaded inactive dead KMJ V3";;
  show) case "$3" in Result) echo success;; ExecMainStatus) echo 0;; *) echo "Thu 2026-11-26 15:45:01 IST";; esac;;
esac
"""


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-inv-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.daily = self.tmp / "daily"
        (self.daily / "20261126T023521Z" / "platform-storage").mkdir(parents=True)
        (self.daily / "20261126T023521Z" / "platform-storage" / "secret-name.pdf").write_text("x")
        (self.daily / "20261126T023521Z" / "record.txt").write_text("schema=kmj.local.full.daily.v2\n")
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "systemctl").write_text(STUB)
        (self.bin / "systemctl").chmod(0o755)
        self.receipts = self.tmp / "receipts"

    def run_script(self, **extra):
        env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "KMJ_ALLOW_NONROOT_FOR_TESTS": "1",
            "KMJ_DAILY_DIR": str(self.daily),
            "KMJ_INVENTORY_RECEIPT_DIR": str(self.receipts),
            **extra,
        }
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)

    def test_reports_counts_and_unit_state_without_file_names(self):
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BACKUP_INVENTORY=DONE", proc.stdout)
        text = next(self.receipts.glob("backup-job-inventory.*.txt")).read_text()
        self.assertIn("20261126T023521Z storage_files=1 top_entries=2", text)
        self.assertIn("schema=kmj.local.full.daily.v2", text)
        self.assertIn("--- unit executables", text)
        self.assertIn("kmj-v3-dual-local-health", text)
        self.assertIn("result=success", text)
        self.assertNotIn("secret-name", text)
        self.assertNotIn("secret-name", proc.stdout)

    def test_fails_closed_without_root_or_daily_dir(self):
        if os.geteuid() != 0:
            proc = self.run_script(KMJ_ALLOW_NONROOT_FOR_TESTS="0")
            self.assertEqual(proc.returncode, 2)
        shutil.rmtree(self.daily)
        proc = self.run_script()
        self.assertEqual(proc.returncode, 4)


if __name__ == "__main__":
    unittest.main()
