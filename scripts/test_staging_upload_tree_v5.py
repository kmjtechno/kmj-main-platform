import importlib.util
import os
import tempfile
from pathlib import Path
import shutil
import unittest
import stat
from unittest.mock import patch
from types import SimpleNamespace

p = Path(__file__).parent / "operations/verify-staging-upload-tree-v5.py"
spec = importlib.util.spec_from_file_location("upload_v5", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class UploadIntegrityV5Test(unittest.TestCase):
    def test_exact_bytes_and_canonical_artwork(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            artwork = root / "artwork"
            artwork.mkdir()
            source = root / "source"
            (source / "private").mkdir(parents=True)
            (source / "private/product-artwork").symlink_to(artwork)
            for i, value in enumerate((b"one", b"two", b"three")):
                (source / ("sample" + str(i))).write_bytes(value)
            dest = root / "dest"
            shutil.copytree(source, dest, symlinks=True)
            before = module.inspect_tree(source, artwork)
            after = module.inspect_tree(dest, artwork)
            self.assertEqual(before, after)
            self.assertEqual(before["files"], 3)
            self.assertEqual(before["symlinks"], 1)
            self.assertEqual(before["bytes"], 11)
            (dest / "sample0").write_bytes(b"changed")
            self.assertNotEqual(before, module.inspect_tree(dest, artwork))

    def test_identical_bytes_with_changed_mode_or_mtime_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "source"
            source.mkdir()
            original = source / "payload"
            original.write_bytes(b"same bytes")
            dest = root / "dest"
            shutil.copytree(source, dest)
            baseline = module.inspect_tree(source)
            self.assertEqual(baseline, module.inspect_tree(dest))
            copy = dest / "payload"
            copy.chmod(0o600 if (copy.stat().st_mode & 0o777) != 0o600 else 0o644)
            self.assertNotEqual(baseline, module.inspect_tree(dest))
            shutil.copymode(original, copy)
            self.assertEqual(baseline, module.inspect_tree(dest))
            mtime = original.stat().st_mtime_ns
            os.utime(copy, ns=(mtime, mtime + 1_000_000_000))
            self.assertNotEqual(baseline, module.inspect_tree(dest))

    def test_directory_metadata_drift_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "source"
            (source / "nested").mkdir(parents=True)
            (source / "nested/payload").write_bytes(b"same")
            dest = root / "dest"
            shutil.copytree(source, dest)
            self.assertEqual(module.inspect_tree(source), module.inspect_tree(dest))
            (dest / "nested").chmod(0o700)
            self.assertNotEqual(module.inspect_tree(source), module.inspect_tree(dest))

    def test_unreviewed_symlink_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "source"
            source.mkdir()
            (source / "not-approved").symlink_to(root)
            with self.assertRaisesRegex(module.UnsafeTree, "UNREVIEWED_SYMLINK"):
                module.inspect_tree(source, root)

    def test_sanitized_receipt_readable_despite_root_umask_077(self):
        with tempfile.TemporaryDirectory() as t:
            with patch.object(module, "QA", Path(t)):
                with patch.object(module.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=os.getgid())):
                    with patch.object(module.os, "fchown"):
                        former = os.umask(0o077)
                        try:
                            module.write_receipt({
                                "schema": "kmj.stage.upload-integrity.v5",
                                "source_files": 3,
                                "source_symlinks": 1,
                                "source_tree_sha256": "a" * 64,
                                "offsite_restore_verified": False,
                                "owner_release_approved": False,
                                "copy_verified": False,
                            }, compare=False)
                        finally:
                            os.umask(former)
                receipt = Path(t) / "KMJ_STAGE_UPLOAD_CONTENT_V5_20261028.json"
                self.assertEqual(stat.S_IMODE(receipt.stat().st_mode), 0o640)
                self.assertEqual(receipt.stat().st_gid, os.getgid())
                self.assertIn("kmj.stage.upload-integrity.v5", receipt.read_text())
                self.assertNotIn("filename", receipt.read_text())
                with self.assertRaises(FileExistsError):
                    with patch.object(module.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=os.getgid())):
                        module.write_receipt({"schema": "second"}, compare=False)

    def test_receipt_source_rejects_world_readability(self):
        source = p.read_text()
        self.assertIn('grp.getgrnam("kmjcode")', source)
        self.assertIn("os.fchmod(stream.fileno(), 0o640)", source)
        self.assertIn("os.O_EXCL | os.O_NOFOLLOW", source)
        self.assertNotIn("os.fchmod(stream.fileno(), 0o644)", source)

    def test_does_not_create_deployment_permission(self):
        text = p.read_text()
        self.assertIn('"owner_release_approved": False', text)
        self.assertIn('"offsite_restore_verified": False', text)
        self.assertIn('"copy_verified": False', text)

if __name__ == "__main__":
    unittest.main()
