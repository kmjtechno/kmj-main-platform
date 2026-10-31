"""Staging storage collision doctor only hashes files; never changes release trees."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/audit-active-staging-storage-collisions-20261027.py"
spec = importlib.util.spec_from_file_location("stage_storage_collision_audit", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ActiveStageStorageAuditTests(unittest.TestCase):
    def test_bad_sha_refused_before_host_or_files(self):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "main"],
                              capture_output=True, text=True, timeout=8)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED_EXACT_SHA_REQUIRED", proc.stdout)

    def test_non_kmj_host_cannot_inspect_files(self):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "a" * 40],
                              capture_output=True, text=True, timeout=8)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED_WRONG_HOST_OR_USER", proc.stdout)

    def test_hashes_no_file_contents_disclosed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            try:
                module.STAGE_HOME = base
                old = base / "old"
                active = base / "new"
                old.mkdir()
                active.mkdir()
                (old / "log.txt").write_text("private text never log", encoding="utf-8")
                (active / "log.txt").write_text("other private text", encoding="utf-8")
                old_files, old_total, old_links = module.scan_storage(old)
                active_files, active_total, active_links = module.scan_storage(active)
                self.assertEqual(old_links, {})
                self.assertEqual(active_links, {})
                self.assertEqual(old_total, len("private text never log"))
                self.assertEqual(active_total, len("other private text"))
                self.assertNotEqual(old_files["log.txt"], active_files["log.txt"])
                self.assertNotIn("private text", repr(old_files))
            finally:
                module.STAGE_HOME = original

    def test_nested_symlinks_classified_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            try:
                module.STAGE_HOME = base
                root = base / "files"
                root.mkdir()
                (root / "ordinary.txt").write_text("local content")
                (root / "escape").symlink_to("/etc", target_is_directory=True)
                (root / "in_scope").symlink_to(root / "ordinary.txt")
                (root / "broken").symlink_to(root / "absent")
                files, size, links = module.scan_storage(root)
                self.assertEqual(len(files), 1)
                self.assertEqual(size, len("local content"))
                self.assertEqual(links["escape"][0], "OUTSIDE_STAGE")
                self.assertEqual(links["in_scope"][0], "IN_STAGE")
                self.assertEqual(links["broken"][0], "IN_STAGE")
                self.assertNotIn("escape", files)
                self.assertNotIn("in_scope", files)
            finally:
                module.STAGE_HOME = original

    def test_symlink_only_child_does_not_expose_outside_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            try:
                module.STAGE_HOME = base
                root = base / "files"
                root.mkdir()
                out = base.parent
                (root / "linked_parent").symlink_to(out, target_is_directory=True)
                files, size, links = module.scan_storage(root)
                self.assertEqual(files, {})
                self.assertEqual(size, 0)
                self.assertEqual(links["linked_parent"][0], "OUTSIDE_STAGE")
            finally:
                module.STAGE_HOME = original

    def test_nested_directory_scan_is_fd_anchored(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            try:
                module.STAGE_HOME = base
                root = base / "files"
                (root / "nested").mkdir(parents=True)
                (root / "nested" / "ok.txt").write_bytes(b"safe")
                (root / "nested" / "outside").symlink_to("/etc/passwd")
                files, size, links = module.scan_storage(root)
                self.assertEqual(set(files), {"nested/ok.txt"})
                self.assertEqual(size, 4)
                self.assertEqual(links["nested/outside"][0], "OUTSIDE_STAGE")
            finally:
                module.STAGE_HOME = original

    def test_total_read_budget_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            original_limit = module.MAX_TOTAL_HASH_BYTES
            try:
                module.STAGE_HOME = base
                module.MAX_TOTAL_HASH_BYTES = 3
                root = base / "files"
                root.mkdir()
                (root / "oversize.txt").write_bytes(b"1234")
                with self.assertRaisesRegex(module.AuditBlocked, "STORAGE_EXCEEDS_READ_BUDGET"):
                    module.scan_storage(root)
            finally:
                module.STAGE_HOME = original
                module.MAX_TOTAL_HASH_BYTES = original_limit

    def test_hardlinked_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            try:
                module.STAGE_HOME = base
                root = base / "files"
                root.mkdir()
                first = root / "first.txt"
                first.write_bytes(b"private")
                import os
                os.link(first, root / "second.txt")
                with self.assertRaisesRegex(module.AuditBlocked, "STORAGE_HARDLINK_UNVERIFIED"):
                    module.scan_storage(root)
            finally:
                module.STAGE_HOME = original

    def test_file_swap_to_outside_symlink_refused_at_open(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            real_open = module.os.open
            try:
                module.STAGE_HOME = base
                root = base / "files"
                root.mkdir()
                victim = root / "victim.txt"
                victim.write_bytes(b"original")
                swapped = [False]

                def swap_then_open(path, flags, *args, **kwargs):
                    if path == "victim.txt" and kwargs.get("dir_fd") is not None:
                        victim.rename(root / "old.txt")
                        victim.symlink_to("/etc/passwd")
                        swapped[0] = True
                    return real_open(path, flags, *args, **kwargs)

                with mock.patch.object(module.os, "open", side_effect=swap_then_open):
                    with self.assertRaises(OSError):
                        module.scan_storage(root)
                self.assertTrue(swapped[0])
            finally:
                module.STAGE_HOME = original

    def test_file_growth_during_hash_is_bounded(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = module.STAGE_HOME
            real_fdopen = module.os.fdopen
            try:
                module.STAGE_HOME = base
                root = base / "files"
                root.mkdir()
                victim = root / "grow.txt"
                victim.write_bytes(b"1234")

                def grow_then_read(fd, *args, **kwargs):
                    with victim.open("ab") as out:
                        out.write(b"unexpected extra bytes")
                    return real_fdopen(fd, *args, **kwargs)

                with mock.patch.object(module.os, "fdopen", side_effect=grow_then_read):
                    with self.assertRaisesRegex(
                            module.AuditBlocked, "STORAGE_STREAM_EXCEEDS_BUDGET"):
                        module.scan_storage(root)
            finally:
                module.STAGE_HOME = original

    def test_source_uses_directory_descriptors(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("os.fwalk(", source)
        self.assertIn("dir_fd=parent_fd", source)
        self.assertIn("STORAGE_STREAM_EXCEEDS_BUDGET", source)
        self.assertNotIn("os.walk(root", source)

    def test_logical_buckets_do_not_publish_individual_paths(self):
        self.assertEqual(module.category("app/public/image.png"), "PUBLIC_UPLOADS")
        self.assertEqual(module.category("app/private/token.txt"), "PRIVATE_APP")
        self.assertEqual(module.category("framework/cache/data/entry"), "FRAMEWORK")
        self.assertEqual(module.category("logs/laravel.log"), "LOGS")
        self.assertEqual(module.category("unclassified.txt"), "OTHER")

    def test_source_contains_no_write_or_deploy_operation(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "shutil.copy", "shutil.move", "os.replace", "os.rename", "os.unlink",
            "os.remove", "os.symlink", "os.mkdir", "mkdir(", ".write_text(",
            "write_bytes(", "open(\"w\"", "systemctl", "artisan migrate",
            "subprocess.Popen", "shell=True", "rm -rf", "chmod(", "chown(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
