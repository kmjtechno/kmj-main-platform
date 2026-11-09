#!/usr/bin/env python3
"""Offline Linux filesystem tests for the fixed 09e8 root materializer installer."""
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
          "operations/install-09e8-materializer-root-20261109.py")
MATERIALIZER = (Path(__file__).resolve().parent /
                "operations/materialize-main-platform-candidate-runtime.sh")
spec = importlib.util.spec_from_file_location("kmj_09e8_materializer_installer", SOURCE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class MaterializerInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exact_bytes = MATERIALIZER.read_bytes()
        mod.verify_payload(cls.exact_bytes)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fd = os.open(self.tmp.name,
                          os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.addCleanup(lambda: os.close(self.fd))
        patch = mock.patch.object(mod, "ROOT_UID", os.getuid())
        patch.start()
        self.addCleanup(patch.stop)
        self.dest = Path(self.tmp.name) / mod.DEST

    def test_source_commit_sha_and_fixed_destination(self):
        self.assertEqual(mod.SOURCE_COMMIT, "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(mod.EXPECTED_SHA256,
                         "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f")
        self.assertEqual(str(mod.BASE), "/usr/local/libexec/kmj-codebridge")
        self.assertEqual(mod.DEST, "main-platform-candidate-materialize-v2.sh")
        self.assertEqual(mod.inspect_fd(self.fd), "MISSING")

    def test_real_atomic_create_and_idempotent_no_clobber(self):
        self.assertEqual(mod.install_fd(self.fd, self.exact_bytes), "INSTALLED_ROOT_PROTECTED")
        self.assertEqual(mod.inspect_fd(self.fd), "ROOT_PROTECTED_PINNED")
        before = self.dest.stat()
        self.assertEqual(stat.S_IMODE(before.st_mode), 0o600)
        self.assertEqual(before.st_nlink, 1)
        self.assertEqual(before.st_uid, os.getuid())
        self.assertEqual(self.dest.read_bytes(), self.exact_bytes)
        self.assertEqual(mod.install_fd(self.fd, self.exact_bytes), "ALREADY_PINNED")
        self.assertEqual(self.dest.stat().st_ino, before.st_ino)
        self.assertFalse(any(p.name.startswith(".kmj-materializer-")
                             for p in Path(self.tmp.name).iterdir()))

    def test_existing_different_file_is_never_overwritten(self):
        self.dest.write_bytes(b"existing-operator-file")
        self.dest.chmod(0o600)
        before = self.dest.stat().st_ino
        with self.assertRaises(mod.Refused):
            mod.install_fd(self.fd, self.exact_bytes)
        self.assertEqual(self.dest.read_bytes(), b"existing-operator-file")
        self.assertEqual(self.dest.stat().st_ino, before)

    def test_existing_symlink_fails_nofollow(self):
        outside = Path(self.tmp.name) / "outside"
        outside.write_bytes(b"keep-me")
        self.dest.symlink_to(outside)
        with self.assertRaises(mod.Refused):
            mod.install_fd(self.fd, self.exact_bytes)
        self.assertEqual(outside.read_bytes(), b"keep-me")
        self.assertTrue(self.dest.is_symlink())

    def test_existing_hardlinked_file_never_mutated(self):
        original = Path(self.tmp.name) / "original"
        original.write_bytes(self.exact_bytes)
        original.chmod(0o600)
        os.link(original, self.dest)
        with self.assertRaisesRegex(mod.Refused, "MATERIALIZER_MODE_UNSAFE"):
            mod.install_fd(self.fd, self.exact_bytes)
        self.assertEqual(original.read_bytes(), self.exact_bytes)
        self.assertEqual(original.stat().st_nlink, 2)

    def test_existing_world_readable_or_nonregular_file_refused(self):
        self.dest.write_bytes(self.exact_bytes)
        self.dest.chmod(0o644)
        with self.assertRaises(mod.Refused):
            mod.inspect_fd(self.fd)
        self.dest.unlink()
        self.dest.mkdir()
        with self.assertRaises(mod.Refused):
            mod.inspect_fd(self.fd)

    def test_invalid_payload_and_truncation_do_not_create_file(self):
        for content in (b"", b"bad", self.exact_bytes[:-1],
                        self.exact_bytes + b"x", b"X" * 65537):
            with self.subTest(length=len(content)), self.assertRaises(mod.Refused):
                mod.install_fd(self.fd, content)
        self.assertEqual(mod.inspect_fd(self.fd), "MISSING")

    def test_atomic_noreplace_race_preserves_new_destination(self):
        original = mod.rename_noreplace
        def racing(parent_fd, src, dst):
            self.dest.write_bytes(b"racer")
            self.dest.chmod(0o600)
            return original(parent_fd, src, dst)
        with mock.patch.object(mod, "rename_noreplace", side_effect=racing):
            with self.assertRaises(FileExistsError):
                mod.install_fd(self.fd, self.exact_bytes)
        self.assertEqual(self.dest.read_bytes(), b"racer")
        self.assertFalse(any(p.name.startswith(".kmj-materializer-")
                             for p in Path(self.tmp.name).iterdir()))

    def test_redirects_fail_closed(self):
        with self.assertRaises(mod.Refused):
            mod.NoRedirect().redirect_request(None, None, 302, "Moved", {},
                                               "http://evil.invalid/source")
        self.assertTrue(mod.URL.startswith("https://raw.githubusercontent.com/"))
        self.assertIn(mod.SOURCE_COMMIT, mod.URL)

    def test_inspect_only_no_network_and_no_mutation(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(mod, "open_protected_parent",
                               side_effect=lambda: os.dup(self.fd)), \
             mock.patch.object(mod, "fetch_exact", side_effect=AssertionError("network")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = mod.main(["--inspect"])
        self.assertEqual(result, 0)
        self.assertIn("ROOT_MATERIALIZER=MISSING", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertFalse(self.dest.exists())

    def test_main_install_is_only_root_private_artifact(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             mock.patch.object(mod, "open_protected_parent",
                               side_effect=lambda: os.dup(self.fd)), \
             mock.patch.object(mod, "fetch_exact", return_value=self.exact_bytes):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = mod.main(["--install"])
        self.assertEqual(result, 0)
        self.assertIn("ROOT_MATERIALIZER=INSTALLED_ROOT_PROTECTED", out.getvalue())
        self.assertEqual(mod.inspect_fd(self.fd), "ROOT_PROTECTED_PINNED")
        self.assertIn("PRODUCTION_MUTATION=NONE", out.getvalue())

    def test_root_parent_no_untrusted_ancestors(self):
        with mock.patch.object(mod, "BASE", Path(self.tmp.name)):
            with self.assertRaises(mod.Refused):
                mod.open_protected_parent()

    def test_no_root_shell_and_no_service_or_release_control(self):
        source = SOURCE.read_text("utf-8")
        import ast
        syntax = ast.parse(source)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertFalse(any(n.name in {"subprocess", "shutil"} for n in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"subprocess", "shutil"})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__"})
        for bad in ("systemctl stop", "systemctl start", "git reset",
                    "os.system(", "shell=True", " --apply", "main-platform-approval.json"):
            self.assertNotIn(bad, source)


if __name__ == "__main__":
    unittest.main()
