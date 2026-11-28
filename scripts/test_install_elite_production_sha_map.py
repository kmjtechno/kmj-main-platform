import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import patch

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

    def test_qualification_requires_actual_new_execution(self):
        snapshot = ("a" * 40, {})
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "qualification"
            with patch.object(m, "QUALIFICATION", marker), patch.object(m, "protected_dir"), \
                    patch.object(m, "guard_live", return_value=snapshot), \
                    patch.object(m, "journal_witness", return_value=None), \
                    patch.object(m, "fixed"):
                with self.assertRaisesRegex(ValueError, "SERVICE_NOT_EXECUTED"):
                    m.qualify_service(snapshot)
                self.assertFalse(marker.exists())
            with patch.object(m, "QUALIFICATION", marker), patch.object(m, "protected_dir"), \
                    patch.object(m, "guard_live", return_value=snapshot), \
                    patch.object(m, "journal_witness", return_value="a" * 32), \
                    patch.object(m, "fixed"):
                m.qualify_service(snapshot)
                self.assertFalse(marker.exists())

    def test_qualification_does_not_remove_preexisting_marker(self):
        snapshot = ("a" * 40, {})
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "qualification"
            marker.write_text("existing")
            with patch.object(m, "QUALIFICATION", marker), patch.object(m, "protected_dir"), \
                    patch.object(m, "guard_live", return_value=snapshot), \
                    patch.object(m, "journal_witness", return_value=None), \
                    patch.object(m, "fixed") as start:
                with self.assertRaises(FileExistsError):
                    m.qualify_service(snapshot)
                start.assert_not_called()
                self.assertEqual(marker.read_text(), "existing")

    def test_journal_requires_fresh_root_exact_service_marker(self):
        entry = {"_SYSTEMD_UNIT": m.UNIT, "_UID": "0",
                 "MESSAGE": "PRODUCTION_SHA_MAP=ALREADY_LIVE_VERIFIED",
                 "_SYSTEMD_INVOCATION_ID": "a" * 32, "__MONOTONIC_TIMESTAMP": "200"}
        self.assertEqual(m.qualification_invocation(json.dumps(entry), 100), "a" * 32)
        self.assertIsNone(m.qualification_invocation(json.dumps(entry), 201))
        for field, value in (("_UID", "1000"), ("_SYSTEMD_UNIT", "other.service"),
                             ("MESSAGE", "unrelated"), ("_SYSTEMD_INVOCATION_ID", "invalid")):
            self.assertIsNone(m.qualification_invocation(json.dumps(dict(entry, **{field: value})), 100))
        other = dict(entry, _SYSTEMD_INVOCATION_ID="b" * 32)
        self.assertIsNone(m.qualification_invocation(json.dumps(entry) + "\n" + json.dumps(other), 100))

if __name__ == "__main__":
    unittest.main()
