import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/operations/plan-elite-a892-persistent-stage-mount-20261128.py"
spec=importlib.util.spec_from_file_location("stage_mount_plan",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MountPlanTests(unittest.TestCase):
    def test_candidate_only(self):
        text=m.unit_bytes().decode()
        self.assertIn("What="+str(m.SOURCE)+"\n",text)
        self.assertIn("Where="+str(m.TARGET)+"\n",text)
        self.assertNotIn("/home/kmjprod",text)
        self.assertNotIn("php8.4-fpm.service",text)

    def test_restrictive_mount_and_boot_enable(self):
        text=m.unit_bytes().decode()
        self.assertIn("Options=bind,nosuid,nodev,noexec\n",text)
        self.assertIn("WantedBy=multi-user.target\n",text)
        self.assertNotIn("RequiredBy=",text)

    def test_deterministic_bytes(self):
        self.assertEqual(m.unit_bytes(),m.unit_bytes())
        self.assertTrue(m.unit_bytes().endswith(b"\n"))


if __name__=="__main__":
    unittest.main()
