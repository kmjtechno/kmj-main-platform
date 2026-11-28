import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "operations" / "verify-elite-staging-shared-continuity-20261128.py"
spec = importlib.util.spec_from_file_location("stage_continuity", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class StageContinuityTests(unittest.TestCase):
    def test_exact_link_difference_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            old, new, art = [root / x for x in ("old", "new", "artwork")]
            art.mkdir()
            for p in (old, new):
                (p / "private").mkdir(parents=True)
                (p / "public").mkdir()
                (p / "private/sample").write_bytes(b"test")
            (old / "private/product-artwork").symlink_to(art)
            a = mod.inventory(old, art)
            self.assertTrue(mod.compare(a, mod.inventory(new, art)))
            (new / "private/product-artwork").mkdir()
            self.assertTrue(mod.compare(a, mod.inventory(new, art)))
            (new / "private/product-artwork/unexpected").write_bytes(b"unexpected")
            self.assertFalse(mod.compare(a, mod.inventory(new, art)))

    def test_different_content_and_unreviewed_links_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            old, new, art = [root / x for x in ("old", "new", "artwork")]
            art.mkdir()
            for p in (old, new):
                (p / "private").mkdir(parents=True)
                (p / "private/sample").write_bytes(p.name.encode())
            (old / "private/product-artwork").symlink_to(art)
            self.assertFalse(mod.compare(mod.inventory(old, art), mod.inventory(new, art)))
            (new / "unexpected").symlink_to(art)
            with self.assertRaisesRegex(ValueError, "UNREVIEWED_LINK"):
                mod.inventory(new, art)


if __name__ == "__main__":
    unittest.main()
