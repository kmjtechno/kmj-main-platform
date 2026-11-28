#!/usr/bin/env python3
"""Offline tests for the read-only candidate diagnostic."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations/diagnose-elite-release-candidate-readonly.py"
spec = importlib.util.spec_from_file_location("diagnostic", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40


class CandidateDiagnosticTest(unittest.TestCase):
    def test_distinguishes_git_failure_from_diff(self):
        self.assertEqual(mod.diff_state(0), "CLEAN")
        self.assertEqual(mod.diff_state(1), "DIFFERS")
        for code in (-1, 2, 128):
            self.assertEqual(mod.diff_state(code), "UNAVAILABLE")

    def test_storage_only_never_masks_index_or_source_drift(self):
        for index, outside, expected in (
            ("CLEAN", "CLEAN", "SHARED_STORAGE_DIFF_ONLY"),
            ("DIFFERS", "CLEAN", "INDEX_DIFFERS"),
            ("CLEAN", "DIFFERS", "NON_STORAGE_DIFFERS"),
            ("CLEAN", "UNAVAILABLE", "NON_STORAGE_UNAVAILABLE"),
        ):
            self.assertEqual(mod.classify(True, index, "DIFFERS", outside,
                                         "EXACT_SHARED_LINK", True), expected)
        self.assertEqual(mod.classify(True, "CLEAN", "DIFFERS", "CLEAN",
                                     "WRONG_LINK_TARGET", True), "FULL_DIFF_DIFFERS")
        self.assertEqual(mod.classify(True, "CLEAN", "DIFFERS", "CLEAN",
                                     "EXACT_SHARED_LINK", False), "LIVE_POINTER_CHANGED")

    def test_real_symlink_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app"
            app.mkdir()
            shared = root / "shared"
            shared.mkdir()
            storage = app / "storage"
            storage.symlink_to(shared, target_is_directory=True)
            self.assertEqual(mod.storage_state(app, shared), "EXACT_SHARED_LINK")
            storage.unlink()
            storage.symlink_to(app, target_is_directory=True)
            self.assertEqual(mod.storage_state(app, shared), "WRONG_LINK_TARGET")
            storage.unlink()
            storage.mkdir()
            self.assertEqual(mod.storage_state(app, shared), "DIRECTORY")

    def test_exact_pointer_and_head_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            releases = root / "releases"
            releases.mkdir()
            folder = releases / ("platform-" + SHA[:12])
            (folder / "apps/platform").mkdir(parents=True)
            live = root / "current"
            live.symlink_to(folder)
            with patch.multiple(mod, LIVE=live, RELEASES=releases, SHARED=root / "shared"):
                with patch.object(mod, "git_probe", return_value=(0, b"b" * 40)) as probe:
                    self.assertEqual(mod.inspect(SHA)["DIAGNOSIS"], "HEAD_UNVERIFIED")
                    probe.assert_called_once()
                live.unlink()
                live.symlink_to(releases)
                with patch.object(mod, "git_probe") as probe:
                    self.assertEqual(mod.inspect(SHA)["DIAGNOSIS"], "LIVE_IDENTITY_MISMATCH")
                    probe.assert_not_called()

    def test_no_activation_or_approval_authority(self):
        source = SOURCE.read_text()
        self.assertIn("AUTHORIZATION=NOT_GRANTED", source)
        self.assertIn("PRODUCTION_MUTATION=NONE", source)
        for forbidden in ("systemctl", "git reset", "git clean", "shell=True",
                          "os.replace(", "write_text(", "ls-remote"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
