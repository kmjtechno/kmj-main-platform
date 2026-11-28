import hashlib
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parent / "operations" / "sync-elite-rehearsal-toolkit-20261128.py"
spec = importlib.util.spec_from_file_location("sync_rehearsal", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ToolkitSyncTests(unittest.TestCase):
    def test_git_blob_and_exact_scope(self):
        self.assertEqual(mod.blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(len(mod.PINS), 4)
        self.assertEqual(mod.SOURCE, "5e356f95fc742812f4cad5746a940bc4e9fcb93b")

    def test_mixed_pin_set_refused(self):
        with patch.object(mod, "read_file", side_effect=lambda path: path.name.encode()), \
             patch.object(mod, "blob", side_effect=lambda data: mod.PINS[data.decode()][0]
                          if data.decode() == next(iter(mod.PINS)) else mod.PINS[data.decode()][1]):
            with self.assertRaisesRegex(ValueError, "MIXED_OR_UNKNOWN"):
                mod.classify()

    def test_transaction_rolls_back_on_second_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            dest = root / "dest"
            dest.mkdir()
            old = {n: ("old:" + n).encode() for n in mod.PINS}
            new = {n: ("new:" + n).encode() for n in mod.PINS}
            pins = {n: (mod.blob(old[n]), mod.blob(new[n])) for n in old}
            for n, data in old.items():
                (dest / n).write_bytes(data)
            original = mod.replace
            attempts = []
            def replace(path, data):
                if path.parent == dest and data in new.values():
                    attempts.append(path)
                    if len(attempts) == 2:
                        raise OSError("synthetic failure")
                original(path, data)
            with patch.object(mod, "PINS", pins), \
                 patch.object(mod, "read_file", side_effect=lambda p: p.read_bytes()), \
                 patch.object(mod, "replace", side_effect=replace):
                with self.assertRaises(OSError):
                    mod.apply(dest, old, new, root / "backup")
                self.assertEqual(mod.classify(dest)[0], "OLD")
            self.assertTrue((root / "backup").is_dir())
            for n in old:
                self.assertEqual((dest / n).read_bytes(), old[n])
                self.assertEqual((root / "backup" / n).read_bytes(), old[n])


if __name__ == "__main__":
    unittest.main()
