"""Fixture tests for scripts/kmj-backup-restore-rowcount-drill.sh (fake psql/runuser/pg_restore, no real data)."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("kmj-backup-restore-rowcount-drill.sh")

FAKE_RUNUSER = "#!/bin/bash\nshift 3\nexec \"$@\"\n"
FAKE_PSQL = r'''#!/bin/bash
db=""; sql=""
while [[ $# -gt 0 ]]; do
  case "$1" in -d) db="$2"; shift 2;; -c) sql="$2"; shift 2;; *) shift;; esac
done
[[ -z "$sql" ]] && { cat >/dev/null; exit 0; }
case "$db" in kmj_drill_*) db=scratch;; esac
case "$sql" in
  "CREATE DATABASE"*) echo create >>"$FAKE/log"; ;;
  "DROP DATABASE"*) echo drop >>"$FAKE/log"; ;;
  *"from pg_database"*) echo 0 ;;
  *pg_tables*) cat "$FAKE/tables_$db" ;;
  *"count(*) from public."*) t="${sql#*public.\"}"; t="${t%%\"*}"; cat "$FAKE/count_${db}_$t" ;;
esac
'''
FAKE_PG_RESTORE = "#!/bin/bash\n[[ -n \"$FAKE_RESTORE_FAIL\" ]] && exit 3\necho 'SET transaction_timeout = 0;'\necho 'select 1;'\n"


class DrillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-drill-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"; self.bin.mkdir()
        self.fake = self.tmp / "fake"; self.fake.mkdir()
        for name, body in (("runuser", FAKE_RUNUSER), ("psql", FAKE_PSQL), ("pg_restore", FAKE_PG_RESTORE)):
            f = self.bin / name; f.write_text(body); f.chmod(f.stat().st_mode | stat.S_IEXEC)
        self.daily = self.tmp / "daily"; self.daily.mkdir()
        d = self.daily / "20261126T023521Z"; d.mkdir()
        (d / "platform.dump").write_bytes(b"dump")
        (d / "SHA256SUMS").write_text(f"{hashlib.sha256(b'dump').hexdigest()}  platform.dump\n")
        self.receipts = self.tmp / "receipts"
        self.tables("scratch", {"users": 5, "orders": 3})
        self.tables("livedb", {"users": 5, "orders": 4})

    def tables(self, db, counts):
        (self.fake / f"tables_{db}").write_text("".join(f"{t}\n" for t in counts))
        for t, n in counts.items():
            (self.fake / f"count_{db}_{t}").write_text(f"{n}\n")

    def run_drill(self, live="livedb", **extra):
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE": str(self.fake),
               "KMJ_ALLOW_NONROOT_FOR_TESTS": "1", "KMJ_DAILY_DIR": str(self.daily),
               "KMJ_DRILL_PG_RESTORE": str(self.bin / "pg_restore"), "KMJ_DRILL_LIVE_DB": live,
               "KMJ_DRILL_RECEIPT_DIR": str(self.receipts), **extra}
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)

    def test_pass_with_upward_drift_and_receipt(self):
        r = self.run_drill()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RESTORE_DRILL=PASS", r.stdout)
        text = next(self.receipts.glob("*.txt")).read_text()
        self.assertIn("equal=1 drift_up=1 shrunk=0", text)
        self.assertIn("row_level_equality_claimed=no", text)
        self.assertEqual((self.fake / "log").read_text().split(), ["create", "drop"])

    def test_fail_when_snapshot_has_more_rows_than_live(self):
        self.tables("livedb", {"users": 5, "orders": 1})
        r = self.run_drill()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("RESTORE_DRILL=FAIL", r.stdout)
        self.assertIn("SHRUNK", next(self.receipts.glob("*.txt")).read_text())

    def test_fail_on_table_set_difference(self):
        self.tables("livedb", {"users": 5, "orders": 3, "extra": 1})
        self.assertNotEqual(self.run_drill().returncode, 0)

    def test_restore_failure_drops_scratch_and_writes_no_receipt(self):
        r = self.run_drill(FAKE_RESTORE_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("RESTORE_FAILED", r.stderr)
        self.assertEqual((self.fake / "log").read_text().split(), ["create", "drop"])
        self.assertFalse(self.receipts.exists())

    def test_checksum_mismatch_blocks_before_scratch(self):
        (self.daily / "20261126T023521Z" / "platform.dump").write_bytes(b"tampered")
        r = self.run_drill()
        self.assertIn("SNAPSHOT_CHECKSUM_MISMATCH", r.stderr)
        self.assertFalse((self.fake / "log").exists())

    def test_invalid_live_db_name_and_root_required(self):
        self.assertIn("LIVE_DB_NAME_INVALID", self.run_drill(live="a;b").stderr)
        env = {**os.environ, "KMJ_DRILL_LIVE_DB": "x"}
        env.pop("KMJ_ALLOW_NONROOT_FOR_TESTS", None)
        if os.geteuid() != 0:
            r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
            self.assertIn("ROOT_REQUIRED", r.stderr)


if __name__ == "__main__":
    unittest.main()
