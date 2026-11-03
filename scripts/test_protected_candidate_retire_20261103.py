"""Adversarial offline tests for root-only protected quarantine rollback design.

This module is a stand-alone review candidate for materializer PR #777; the
root entrypoint is intentionally not installed or wired to production.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/protected-candidate-retire-20261103.py"
spec = importlib.util.spec_from_file_location("kmj_protected_candidate_retire", SOURCE)
retire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire)


class RootQuarantineRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.candidate = self.base / "candidate"
        self.live = self.base / "live"
        self.private = self.base / "private-root-only-quarantine"
        for directory in (self.candidate, self.live, self.private):
            directory.mkdir(mode=0o700)
        self.uid = os.geteuid()
        self.candidate_fd = os.open(self.candidate, os.O_RDONLY | os.O_DIRECTORY)
        self.live_fd = os.open(self.live, os.O_RDONLY | os.O_DIRECTORY)
        self.private_fd = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)

    def tearDown(self):
        for fd in (self.candidate_fd, self.live_fd, self.private_fd):
            os.close(fd)
        self.temp.cleanup()

    def inode(self, path, *, follow=True):
        info = path.stat() if follow else path.lstat()
        return f"{info.st_dev}:{info.st_ino}"

    def env(self):
        text = b"APP_KEY=base64:test\nDB_CONNECTION=pgsql\n"
        live = self.live / ".env"
        candidate = self.candidate / ".env"
        live.write_bytes(text)
        candidate.write_bytes(text)
        candidate.chmod(0o600)
        return candidate

    def run_retire(self, name, kind, inode):
        return retire.retire_created(
            self.candidate_fd, self.private_fd, name=name,
            expected_inode=inode, kind=kind, created_uid=self.uid,
            live_fd=self.live_fd if kind == "f" else None,
            trusted_uid=self.uid,
        )

    def test_created_env_removed_only_from_private_parent(self):
        created = self.env()
        receipt = self.inode(created)
        self.assertEqual(self.run_retire(".env", "f", receipt), "REMOVED")
        self.assertFalse(created.exists())
        self.assertEqual(list(self.private.iterdir()), [])
        self.assertEqual((self.live / ".env").read_bytes(),
                         b"APP_KEY=base64:test\nDB_CONNECTION=pgsql\n")

    def test_created_storage_link_is_removed_with_target_attestation(self):
        link = self.candidate / "storage"
        link.symlink_to("../storage/app/public")
        receipt = self.inode(link, follow=False)
        self.assertEqual(self.run_retire("storage", "l", receipt), "REMOVED")
        self.assertFalse(link.is_symlink())
        self.assertEqual(list(self.private.iterdir()), [])

    def test_wrong_receipt_never_moves_or_deletes_candidate(self):
        created = self.env()
        self.assertEqual(
            self.run_retire(".env", "f", f"{created.stat().st_dev}:1"),
            "MISMATCH",
        )
        self.assertTrue(created.exists())
        self.assertEqual(list(self.private.iterdir()), [])

    def test_foreign_inode_swapped_between_prefilter_and_rename_survives(self):
        created = self.env()
        receipt = self.inode(created)
        foreign = self.candidate / "foreign"
        foreign.write_bytes(b"FOREIGN_OWNER_DATA")
        original_rename = os.rename

        def concurrent_swap(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
            if src == ".env" and dst == "object":
                original_rename(self.candidate / ".env", self.candidate / "ours")
                original_rename(self.candidate / "foreign", self.candidate / ".env")
            return original_rename(src, dst,
                                   src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

        with patch.object(retire.os, "rename", side_effect=concurrent_swap):
            state = self.run_retire(".env", "f", receipt)

        self.assertEqual(state, "QUARANTINED_OWNER_REVIEW")
        self.assertEqual((self.candidate / "ours").read_bytes(),
                         b"APP_KEY=base64:test\nDB_CONNECTION=pgsql\n")
        tickets = list(self.private.iterdir())
        self.assertEqual(len(tickets), 1)
        self.assertEqual((tickets[0] / "object").read_bytes(), b"FOREIGN_OWNER_DATA")
        self.assertFalse((self.candidate / ".env").exists())

    def test_untrusted_quarantine_permissions_block_without_mutation(self):
        created = self.env()
        self.private.chmod(0o777)
        with self.assertRaisesRegex(retire.Blocked, "PRIVATE_QUARANTINE"):
            self.run_retire(".env", "f", self.inode(created))
        self.assertTrue(created.exists())

    def test_changed_live_source_never_deletes_candidate(self):
        created = self.env()
        receipt = self.inode(created)
        (self.live / ".env").write_bytes(b"APP_KEY=altered\n")
        self.assertEqual(self.run_retire(".env", "f", receipt),
                         "QUARANTINED_OWNER_REVIEW")
        tickets = list(self.private.iterdir())
        self.assertEqual(len(tickets), 1)
        self.assertEqual((tickets[0] / "object").read_bytes(),
                         b"APP_KEY=base64:test\nDB_CONNECTION=pgsql\n")

    def test_preexisting_quarantine_ticket_cannot_be_overwritten(self):
        created = self.env()
        fixed_random = bytes(20)
        existing = self.private / ("kmj-protected-" + "00" * 20)
        existing.mkdir()
        sentinel = existing / "object"
        sentinel.write_bytes(b"DO_NOT_REPLACE")
        with patch.object(retire.os, "urandom", return_value=fixed_random):
            with self.assertRaises(FileExistsError):
                self.run_retire(".env", "f", self.inode(created))
        self.assertEqual(sentinel.read_bytes(), b"DO_NOT_REPLACE")
        self.assertTrue(created.exists())

    def test_no_unlink_in_candidate_and_no_live_root_entrypoint(self):
        source = SOURCE.read_text()
        self.assertIn("dir_fd=ticket_fd", source)
        self.assertIn("os.mkdir(ticket, mode=0o700", source)
        self.assertIn("PRIVATE_QUARANTINE_NOT_TRUSTED", source)
        self.assertNotIn("os.unlink(name, dir_fd=source_fd)", source)
        self.assertIn("LIBRARY_ONLY_NOT_INSTALLED", source)
        self.assertIn("QUARANTINED_OWNER_REVIEW", source)


if __name__ == "__main__":
    unittest.main()
