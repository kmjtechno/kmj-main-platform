import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "installer", ROOT / "scripts/operations/install-elite-production-sha-map-20261128.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class InstallerContractTests(unittest.TestCase):
    def test_every_source_pin_matches_reviewed_branch_bytes(self):
        for source, _, pin, mode in m.STAGE + m.ENABLE:
            with self.subTest(source=source):
                data = (ROOT / source).read_bytes()
                self.assertEqual(m.blob(data), pin)
                self.assertIn(mode, (0o500, 0o644))

    def test_stage_cannot_replace_broker_or_enable_admission(self):
        self.assertFalse(any(path.name == m.BROKER or path.name == "20-production-sha-map.conf"
                             for _, path, _, _ in m.STAGE))
        self.assertEqual(len(m.ENABLE), 2)

if __name__ == "__main__":
    unittest.main()
