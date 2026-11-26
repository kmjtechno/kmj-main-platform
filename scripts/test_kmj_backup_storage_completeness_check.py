"""Fixture tests for scripts/kmj-backup-storage-completeness-check.sh (no root, no real data)."""
from __future__ import annotations

import calendar
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-backup-storage-completeness-check.sh")


class StorageCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-storage-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.daily = self.tmp / "daily"
        self.snap = self.daily / "20261126T023521Z"
        (self.snap / "platform-storage").mkdir(parents=True)
        (self.snap / "platform.dump").write_bytes(b"dump")
        (self.snap / "SHA256SUMS").write_text(f"{hashlib.sha256(b'dump').hexdigest()}  platform.dump\n")
        self.live = self.tmp / "live" / "storage" / "app"
        self.live.mkdir(parents=True)
        self.receipts = self.tmp / "receipts"

    SNAP_EPOCH = calendar.timegm((2026, 11, 26, 2, 35, 21))

    def put(self, root, rel, data, after_snapshot=False):
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        t = self.SNAP_EPOCH + (3600 if after_snapshot else -3600)
        os.utime(p, (t, t))

    def run_check(self):
        env = {**os.environ, "KMJ_ALLOW_NONROOT_FOR_TESTS": "1", "KMJ_DAILY_DIR": str(self.daily),
               "KMJ_LIVE_STORAGE": str(self.live), "KMJ_STORAGE_RECEIPT_DIR": str(self.receipts)}
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)

    def test_identical_changed_and_live_only_pass_with_counts(self):
        s = self.snap / "platform-storage"
        self.put(s, "a.txt", b"one"); self.put(self.live, "a.txt", b"one")
        self.put(s, "b.txt", b"old"); self.put(self.live, "b.txt", b"new")
        self.put(self.live, "c.txt", b"fresh", after_snapshot=True)
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("COUNTS snapshot=2 live=3 identical=1 changed=1 live_only=1 missing_predating_snapshot=0 snapshot_only=0", r.stdout)
        text = next(self.receipts.glob("storage-*.txt")).read_text()
        self.assertIn("names_recorded=no", text)
        self.assertNotIn("a.txt", text + r.stdout)

    def test_live_file_older_than_snapshot_but_absent_from_it_fails(self):
        self.put(self.snap / "platform-storage", "a.txt", b"one"); self.put(self.live, "a.txt", b"one")
        self.put(self.live, "old-unbacked.txt", b"x")  # mtime before the snapshot
        r = self.run_check()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing_predating_snapshot=1", r.stdout)
        self.assertIn("STORAGE_CHECK=FAIL", r.stdout)

    def test_snapshot_only_file_is_reported_not_failed(self):
        self.put(self.snap / "platform-storage", "gone.txt", b"x")
        self.put(self.snap / "platform-storage", "keep.txt", b"y"); self.put(self.live, "keep.txt", b"y")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("snapshot_only=1", r.stdout)

    def test_empty_snapshot_with_live_files_fails(self):
        self.put(self.live, "a.txt", b"x")
        r = self.run_check()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("STORAGE_CHECK=FAIL", r.stdout)

    def test_storage_root_layout_is_matched_against_parent(self):
        s = self.snap / "platform-storage"
        self.put(s, "app/a.txt", b"one"); self.put(self.live, "a.txt", b"one")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("identical=1", r.stdout)
        self.assertIn("layout=storage_root", next(self.receipts.glob("storage-*.txt")).read_text())

    def test_regenerable_views_and_logs_are_not_a_gap_but_other_framework_files_are(self):
        s = self.snap / "platform-storage"
        root = self.live.parent
        self.put(s, "app/a.txt", b"one"); self.put(self.live, "a.txt", b"one")
        self.put(root, "framework/views/x.php", b"compiled")
        self.put(root, "logs/laravel.log", b"log")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("missing_predating_snapshot=0", r.stdout)
        self.put(root, "framework/sessions/sess1", b"s")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing_predating_snapshot=1", r.stdout)

    def test_checksum_mismatch_blocks(self):
        (self.snap / "platform.dump").write_bytes(b"tampered")
        r = self.run_check()
        self.assertIn("SNAPSHOT_CHECKSUM_MISMATCH", r.stderr)
        self.assertFalse(self.receipts.exists())


if __name__ == "__main__":
    unittest.main()
