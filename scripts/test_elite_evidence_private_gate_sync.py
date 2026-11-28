"""Offline private gate synchronization contract tests."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations/sync-elite-evidence-private-gate-20261128.py"
spec = importlib.util.spec_from_file_location("private_gate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrivateGateSyncTest(unittest.TestCase):
    def test_only_private_target(self):
        self.assertNotEqual(mod.GATE, mod.PRIMARY)
        self.assertEqual(mod.GATE.parent.name, "kmj-main-platform-release-evidence")
        self.assertEqual(mod.BACKUP.parent, mod.GATE.parent)

    def test_primary_mismatch_blocks_before_any_write(self):
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
                mod.socket, "gethostname", return_value="KMJ-elite"), patch.object(
                mod, "reviewed_bytes", return_value=(b"old", b"new")), patch.object(
                mod, "stable_read", return_value=b"wrong"), patch.object(mod, "stage") as stage:
            with self.assertRaisesRegex(mod.Blocked, "PRIMARY_GATE_PIN_MISMATCH"):
                mod.run(True)
            stage.assert_not_called()

    def test_no_unapproved_apply(self):
        with patch("sys.argv", ["sync", "--apply"]), patch.object(mod, "run") as run:
            self.assertEqual(mod.main(), 2)
            run.assert_not_called()

    def test_no_deploy_or_receipt_writes(self):
        source = SOURCE.read_text()
        self.assertNotIn("systemctl", source)
        self.assertNotIn("shell=True", source)
        self.assertIn("os.replace(temp, GATE)", source)
        self.assertNotIn("os.replace(temp, PRIMARY)", source)
        self.assertIn("stable_read(PRIMARY, 0o500) == new", source)
        self.assertIn("APPROVAL_WRITE_REQUESTED=NO", source)


if __name__ == "__main__":
    unittest.main()
