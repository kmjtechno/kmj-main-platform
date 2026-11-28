import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "production_release_sha_map",
    Path(__file__).parent / "operations/production_release_sha_map.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
A = "457481eb652f92cfa016aee022f43fe64c4396b3"
B = "4b74134d287d448e89415dd709595bf195abf874"

class MapTests(unittest.TestCase):
    def test_exact_witness_and_rollback(self):
        old = mod.render([A])
        new = mod.plan(old, A, B, lambda s: s)
        self.assertEqual(set(mod.parse_existing(new)), {A, B})
        self.assertIn("default \"\";", new)
        self.assertEqual(new.count(":/login$"), 2)
        self.assertEqual(mod.plan(new, B, A, lambda s: s), new)

    def test_refuses_invalid_and_collision(self):
        for values in ([], [A, A], [A, A[:12]+"0"*28], ["x"*40], [A, B, "c"*40]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                mod.render(values)

    def test_rejects_tampering(self):
        old = mod.render([A])
        for data in (old.replace(":/login$", ":/.*"), old.replace(A[:12], B[:12], 1),
                     old.replace('default "";', "default "+A+";"), old+"extra"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                mod.parse_existing(data)

    def test_no_current_or_unverified_candidate(self):
        with self.assertRaisesRegex(ValueError, "CURRENT_MAP_MISSING"):
            mod.plan(mod.render([B]), A, B, lambda s: s)
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_RELEASE"):
            mod.plan(mod.render([A]), A, B, lambda s: s if s == A else "")

    def test_same_release_idempotent(self):
        old = mod.render([A])
        self.assertEqual(mod.plan(old, A, A, lambda s: s), old)

if __name__ == "__main__":
    unittest.main()
