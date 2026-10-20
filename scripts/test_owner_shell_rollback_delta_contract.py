#!/usr/bin/env python3
"""Pure negative controls for immutable source rollback-delta gate."""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

source = pathlib.Path(__file__).resolve().parent / "ci" / "verify-owner-shell-rollback-delta-20261020.py"
spec = importlib.util.spec_from_file_location("owner_shell_delta", source)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RollbackDeltaContract(unittest.TestCase):
    def test_actual_expected_file_set_is_safe(self):
        module.validate_delta(dict(module.EXPECTED))
        self.assertEqual(len(module.EXPECTED), 13)

    def test_added_migration_fails_closed(self):
        altered = dict(module.EXPECTED)
        altered["apps/platform/database/migrations/2026_new_role.php"] = "A"
        with self.assertRaisesRegex(AssertionError, "PROTECTED_RUNTIME_SOURCE_CHANGED"):
            module.validate_delta(altered)

    def test_modified_payment_backend_fails_closed(self):
        altered = dict(module.EXPECTED)
        altered["apps/platform/app/Services/Payments/Charge.php"] = "M"
        with self.assertRaisesRegex(AssertionError, "PROTECTED_RUNTIME_SOURCE_CHANGED"):
            module.validate_delta(altered)

    def test_mismatched_file_status_fails_closed(self):
        altered = dict(module.EXPECTED)
        altered["apps/platform/resources/js/app.tsx"] = "A"
        with self.assertRaisesRegex(AssertionError, "EXACT_RELEASE_SOURCE_DELTA_MISMATCH"):
            module.validate_delta(altered)

    def test_missing_file_fails_closed(self):
        altered = dict(module.EXPECTED)
        altered.pop("apps/platform/resources/css/owner-module-shell.css")
        with self.assertRaisesRegex(AssertionError, "EXACT_RELEASE_SOURCE_DELTA_MISMATCH"):
            module.validate_delta(altered)

    def test_no_production_side_effects(self):
        content = source.read_text()
        for unsafe in (
            "systemctl restart",
            "systemctl reload",
            "artisan migrate",
            "rclone copy",
            "ssh ",
            "ln -s",
            "git reset",
            "/etc/kmj-codebridge/main-platform-production-release.json",
        ):
            self.assertNotIn(unsafe, content)
        for important in (
            "REAL_PRODUCTION_ROLLBACK_DRILL=NOT_VERIFIED",
            "INDEPENDENT_OFFSITE_RESTORE=NOT_VERIFIED",
            "PRODUCTION_SWITCH=NOT_ATTEMPTED",
        ):
            self.assertIn(important, content)


if __name__ == "__main__":
    unittest.main()
