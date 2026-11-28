#!/usr/bin/env python3
"""Offline safety tests; never touch the installed Elite gate."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations/upgrade-elite-autopublish-shared-storage-20261128.py"
spec = importlib.util.spec_from_file_location("upgrade", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GateUpgradeTest(unittest.TestCase):
    def test_exact_git_blob(self):
        self.assertEqual(mod.blob(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")
        self.assertNotEqual(mod.OLD_BLOB, mod.NEW_BLOB)

    def test_approval_cannot_be_inferred(self):
        import json
        approval = {"approvedSha": mod.LIVE_SHA,
                    "expectedCurrentRelease": "platform-" + "a" * 12,
                    "backupVerified": True, "rollbackVerified": True}
        for key, value in (("approvedSha", "b" * 40),
                           ("backupVerified", "true"), ("rollbackVerified", False)):
            with self.assertRaises(mod.Blocked):
                mod.exact_approval(json.dumps(dict(approval, **{key: value})))
        with self.assertRaises(mod.Blocked):
            mod.exact_approval(b'{"approvedSha":"a","approvedSha":"b"}')

    def test_backup_cannot_overwrite_unknown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "backup"
            backup.write_bytes(b"unknown")
            with patch.object(mod, "BACKUP", backup), patch.object(
                    mod, "stable_read", return_value=b"unknown"), patch.object(mod, "stage") as stage:
                with self.assertRaises(mod.Blocked):
                    mod.ensure_backup(b"old")
                stage.assert_not_called()
                self.assertEqual(backup.read_bytes(), b"unknown")

    def test_no_implicit_owner_apply(self):
        with patch("sys.argv", ["upgrade", "--apply"]), patch.object(mod, "run") as run:
            self.assertEqual(mod.main(), 2)
            run.assert_not_called()

    def test_no_release_activation_or_approval_mutation(self):
        text = SOURCE.read_text()
        for token in ("systemctl", "shell=True", "os.system(", "os.symlink(", "git reset", "git clean"):
            self.assertNotIn(token, text)
        self.assertIn("os.replace(temp, GATE)", text)
        self.assertIn("stable_read(APPROVAL, 0o600, 4096) == approval", text)
        self.assertIn("APPROVAL_WRITE_REQUESTED=NO", text)


if __name__ == "__main__":
    unittest.main()
