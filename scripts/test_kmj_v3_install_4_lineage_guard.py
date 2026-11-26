"""Fixture tests for scripts/kmj-v3-install-4-lineage-guard.sh (no root, no systemd)."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
INSTALLER = HERE / "kmj-v3-install-4-lineage-guard.sh"
GUARD = HERE / "KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261126.py"
OLD = "kmj-v3-dual-local-health-onepass-20261118"
UNIT_TEXT = f"""[Service]
Type=oneshot
ExecStartPre=/usr/bin/sha256sum --check --status LIB/{OLD}.sha256
ExecStart=/usr/bin/python3 -I -B LIB/{OLD}.py --run-once-local
TimeoutStartSec=3600s
"""


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kmj-v3i-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.lib = self.tmp / "libexec"
        self.lib.mkdir()
        self.unit = self.tmp / "unit.service"
        self.unit.write_text(UNIT_TEXT.replace("LIB", str(self.lib)))
        self.pin = hashlib.sha256(GUARD.read_bytes()).hexdigest()

    def run_installer(self, src=GUARD, **extra):
        env = {**os.environ, "KMJ_ALLOW_NONROOT_FOR_TESTS": "1", "KMJ_SKIP_SYSTEMCTL": "1",
               "KMJ_LIBEXEC": str(self.lib), "KMJ_UNIT": str(self.unit), "KMJ_PIN": self.pin, **extra}
        return subprocess.run(["bash", str(INSTALLER), str(src)], capture_output=True, text=True, env=env)

    def test_installs_file_hash_and_repoints_only_the_two_lines(self):
        r = self.run_installer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("V3_GUARD_INSTALL=DONE", r.stdout)
        self.assertIn("BACKUP_NOT_STARTED=YES", r.stdout)
        new = self.lib / "kmj-v3-dual-local-health-onepass-20261126.py"
        self.assertEqual(oct(new.stat().st_mode & 0o777), "0o600")
        self.assertTrue((self.lib / "kmj-v3-dual-local-health-onepass-20261126.sha256").exists())
        text = self.unit.read_text()
        self.assertIn("onepass-20261126.py --run-once-local", text)
        self.assertIn("onepass-20261126.sha256", text)
        self.assertNotIn("20261118", text)
        self.assertIn("TimeoutStartSec=3600s", text)
        self.assertEqual(len(list(self.tmp.glob("unit.service.bak.*"))), 1)

    def test_wrong_pin_changes_nothing(self):
        r = self.run_installer(KMJ_PIN="0" * 64)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(list(self.lib.iterdir()), [])
        self.assertIn("20261118", self.unit.read_text())

    def test_unexpected_unit_changes_nothing(self):
        self.unit.write_text("[Service]\nExecStart=/bin/true\n")
        r = self.run_installer()
        self.assertEqual(r.returncode, 4)
        self.assertEqual(list(self.lib.iterdir()), [])

    def test_second_run_refuses(self):
        self.assertEqual(self.run_installer().returncode, 0)
        self.assertEqual(self.run_installer().returncode, 4)


if __name__ == "__main__":
    unittest.main()
