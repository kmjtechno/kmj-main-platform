import importlib.util
import tempfile
from pathlib import Path
import shutil
import unittest

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

    def test_unreviewed_symlink_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "source"
            source.mkdir()
            (source / "not-approved").symlink_to(root)
            with self.assertRaisesRegex(module.UnsafeTree, "UNREVIEWED_SYMLINK"):
                module.inspect_tree(source, root)

    def test_does_not_create_deployment_permission(self):
        text = p.read_text()
        self.assertIn('"owner_release_approved": False', text)
        self.assertIn('"offsite_restore_verified": False', text)
        self.assertIn('"copy_verified": False', text)

if __name__ == "__main__":
    unittest.main()
