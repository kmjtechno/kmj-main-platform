#!/usr/bin/env python3
"""Real Linux tempfile tests for fixed 09e8 root-private transaction-state guard.

Tests use a mocked effective root UID/GID only for ordinary user-owned
temporary directories. Never access /var/lib production namespace.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = (Path(__file__).resolve().parent /
          "operations/09e8-root-transaction-state-provision-20261110.py")
spec = importlib.util.spec_from_file_location("kmj09e8_state_provision", SOURCE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class StateProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / mod.DIRECTORY
        self.fd = os.open(self.directory,
                          os.O_RDONLY | os.O_DIRECTORY |
                          os.O_NOFOLLOW | os.O_CLOEXEC)
        self.addCleanup(lambda: os.close(self.fd))
        for name, val in (("ROOT_UID", os.getuid()),
                          ("ROOT_GID", os.getgid())):
            patch = mock.patch.object(mod, name, val)
            patch.start()
            self.addCleanup(patch.stop)

    def test_exact_fixed_directory_contract(self):
        self.assertEqual(mod.PARENT_PARTS, ("var", "lib"))
        self.assertEqual(mod.DIRECTORY, "kmj-main-platform-09e8-candidate-cutover")
        self.assertEqual(mod.inspect(self.fd), "MISSING")

    def test_create_only_empty_private_and_idempotence(self):
        self.assertEqual(mod.prepare(self.fd), "CREATED_ROOT_PRIVATE_EMPTY")
        self.assertEqual(mod.inspect(self.fd), "ROOT_PRIVATE_EMPTY")
        info = self.path.stat()
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o700)
        self.assertEqual(info.st_uid, os.getuid())
        self.assertEqual(info.st_gid, os.getgid())
        self.assertEqual(mod.prepare(self.fd), "ALREADY_ROOT_PRIVATE_EMPTY")
        self.assertEqual(self.path.stat().st_ino, info.st_ino)
        self.assertEqual(tuple(self.path.iterdir()), ())

    def test_existing_partial_journal_preserved_without_deletion(self):
        self.path.mkdir(mode=0o700)
        artifact = self.path / "transaction.json"
        artifact.write_bytes(b"crash-evidence-private")
        with self.assertRaisesRegex(mod.Refused, "EXISTING_TRANSACTION_RECOVERY_REQUIRED"):
            mod.prepare(self.fd)
        self.assertEqual(artifact.read_bytes(), b"crash-evidence-private")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o700)

    def test_existing_unsafe_mode_not_repaired(self):
        self.path.mkdir(mode=0o755)
        before = self.path.stat()
        with self.assertRaisesRegex(mod.Refused, "STATE_DIR_UNTRUSTED"):
            mod.prepare(self.fd)
        after = self.path.stat()
        self.assertEqual(stat.S_IMODE(after.st_mode), 0o755)
        self.assertEqual(after.st_ino, before.st_ino)

    def test_symlink_never_followed_and_target_untouched(self):
        outside = self.directory / "operator"
        outside.mkdir()
        (outside / "record").write_bytes(b"keep")
        self.path.symlink_to(outside)
        with self.assertRaises(mod.Refused):
            mod.prepare(self.fd)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual((outside / "record").read_bytes(), b"keep")

    def test_non_dir_existing_file_not_overwritten(self):
        self.path.write_bytes(b"operator-owned")
        before = self.path.stat().st_ino
        with self.assertRaises(mod.Refused):
            mod.prepare(self.fd)
        self.assertEqual(self.path.read_bytes(), b"operator-owned")
        self.assertEqual(self.path.stat().st_ino, before)

    def test_competing_entry_at_mkdir_never_deleted(self):
        real_mkdir = mod.os.mkdir
        def racing(name, mode, *, dir_fd):
            self.path.write_bytes(b"racing-admin")
            return real_mkdir(name, mode, dir_fd=dir_fd)
        with mock.patch.object(mod.os, "mkdir", side_effect=racing):
            with self.assertRaises(FileExistsError):
                mod.prepare(self.fd)
        self.assertEqual(self.path.read_bytes(), b"racing-admin")

    def test_inspect_never_mkdir_or_fsync(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(mod, "protected_parent_fd",
                               side_effect=lambda: os.dup(self.fd)), \
             mock.patch.object(mod.os, "mkdir", side_effect=AssertionError("mkdir")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--inspect"])
        self.assertEqual(rc, 0)
        self.assertIn("TRANSACTION_STATE_DIR=MISSING", out.getvalue())
        self.assertIn("TRANSACTION_STATE_DIR_CREATED=NO", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertFalse(self.path.exists())

    def test_root_prepare_changes_only_fixed_private_state_dir(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(mod, "protected_parent_fd",
                               side_effect=lambda: os.dup(self.fd)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--prepare"])
        self.assertEqual(rc, 0)
        self.assertIn("TRANSACTION_STATE_DIR=CREATED_ROOT_PRIVATE_EMPTY", out.getvalue())
        self.assertIn("TRANSACTION_STATE_DIR_CREATED=YES", out.getvalue())
        self.assertIn("PRODUCTION_APP_MUTATION=NONE", out.getvalue())
        self.assertTrue(self.path.is_dir())

    def test_failed_prepare_after_creation_never_claims_no_mutation(self):
        def fail_fsync(_fd):
            raise OSError("PRIVATE_ENV_VALUE")
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(mod, "protected_parent_fd",
                               side_effect=lambda: os.dup(self.fd)), \
             mock.patch.object(mod.os, "fsync", side_effect=fail_fsync):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--prepare"])
        self.assertEqual(rc, 2)
        self.assertIn("TRANSACTION_STATE_DIR_CREATED=UNVERIFIED", out.getvalue())
        self.assertIn("TRANSACTION_STATE_DIR=BLOCKED_UNVERIFIABLE", out.getvalue())
        self.assertNotIn("PRIVATE_ENV_VALUE", out.getvalue())
        self.assertTrue(self.path.is_dir())

    def test_fail_closed_root_scope_and_no_exec_capability(self):
        with mock.patch.object(mod.os, "geteuid", return_value=10001):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--inspect"])
        self.assertEqual(rc, 2)
        self.assertIn("TRANSACTION_STATE_DIR=BLOCKED_UNVERIFIABLE", out.getvalue())
        import ast
        source = SOURCE.read_text("utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertNotIn("subprocess", [alias.name for alias in node.names])
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"subprocess", "shutil"})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"eval", "exec", "compile", "__import__"})
        for fragment in ("systemctl start", "systemctl stop", "nft add",
                         "nft delete", " --apply", "git reset", "os.unlink(",
                         "os.rename(", "os.replace(", "os.symlink(", "os.chmod("):
            self.assertNotIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
