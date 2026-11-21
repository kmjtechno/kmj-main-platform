#!/usr/bin/env python3
"""Regression tests for the real KMJ-elite health exit-3 cause, no host access."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations" / "elite_health_owner_disabled_offsite.py"
spec = importlib.util.spec_from_file_location("elite_health_policy", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ORIGINAL = (
    b"#!/usr/bin/env bash\n"
    b"set -Eeuo pipefail\n"
    b"systemctl is-active --quiet kmj-main-platform-scheduler.timer\n"
    b"find /var/backups/kmj-elite-daily -mindepth 2 -maxdepth 2 -name platform.dump -type f -mtime -2 | grep -q .\n"
    + mod.OLD +
    b"test -s /root/kmj-bootstrap/offsite-age-recipients.txt\n"
    b"find /var/backups/kmj-elite-offsite-encrypted -mindepth 1 -maxdepth 1 -name '20*.tar.age' -type f -mtime -2 | grep -q .\n"
    b"echo KMJ_ELITE_HEALTH_PASS\n"
)


class OwnerHealthPolicyTests(unittest.TestCase):
    def test_original_exact_policy_changes_only_one_gate(self):
        changed, state = mod.transform(ORIGINAL)
        self.assertEqual(state, "READY_FOR_OWNER_APPLY")
        self.assertEqual(changed, ORIGINAL.replace(mod.OLD, mod.NEW))
        for anchor in mod.ANCHORS:
            self.assertIn(anchor, changed)
        self.assertNotIn(mod.OLD, changed)
        self.assertIn(b"DR=NOT_VERIFIED", changed)
        self.assertIn(b"KMJ_OFFSITE_TIMER=DISABLED_BY_OWNER", changed)
        self.assertIn(b"UNHEALTHY_OFFSITE_TIMER_STATE", changed)
        self.assertIn(b"exit 8", changed)

    def test_second_run_does_not_rewrite_successful_policy(self):
        patched, _ = mod.transform(ORIGINAL)
        again, state = mod.transform(patched)
        self.assertEqual(state, "ALREADY_APPLIED")
        self.assertEqual(patched, again)

    def test_real_bash_syntax_valid(self):
        data, _ = mod.transform(ORIGINAL)
        result = subprocess.run(
            ["/usr/bin/bash", "-n"], input=data, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_missing_backup_freshness(self):
        for anchor in (mod.ANCHORS[2], mod.ANCHORS[4]):
            with self.subTest(anchor=anchor):
                with self.assertRaisesRegex(ValueError, "REQUIRED_LOCAL"):
                    mod.transform(ORIGINAL.replace(anchor, b""))

    def test_refuses_missing_scheduler_or_pass_marker(self):
        for anchor in (mod.ANCHORS[1], mod.ANCHORS[5]):
            with self.subTest(anchor=anchor):
                with self.assertRaises(ValueError):
                    mod.transform(ORIGINAL.replace(anchor, b""))

    def test_refuses_duplicate_offsite_gate(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OFFSITE_POLICY"):
            mod.transform(ORIGINAL.replace(mod.OLD, mod.OLD * 2))

    def test_refuses_unknown_or_mixed_half_patched_gate(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OFFSITE_POLICY"):
            mod.transform(ORIGINAL.replace(mod.OLD, b"true\n"))
        patched, _ = mod.transform(ORIGINAL)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OFFSITE_POLICY"):
            mod.transform(patched + mod.OLD)

    def test_refuses_reordered_checks(self):
        changed = ORIGINAL.replace(
            mod.ANCHORS[4] + mod.ANCHORS[5],
            mod.ANCHORS[5] + mod.ANCHORS[4],
        )
        with self.assertRaisesRegex(ValueError, "HEALTH_CHECK_ORDER"):
            mod.transform(changed)

    def test_refuses_drifted_format_and_modified_owner_marker(self):
        with self.assertRaisesRegex(ValueError, "SCRIPT_FORMAT"):
            mod.transform(ORIGINAL.replace(b"\n", b"\r\n"))
        with self.assertRaises(ValueError):
            mod.transform(ORIGINAL.replace(b"set -Eeuo pipefail", b"set +e"))

    def test_requires_exact_owner_selected_timer_state(self):
        expected_calls = [
            ("kmj-main-platform-scheduler.timer", "is-active", "active"),
            ("kmj-elite-offsite-backup.timer", "is-active", "inactive"),
            ("kmj-elite-offsite-backup.timer", "is-enabled", "disabled"),
        ]

        def good_state(unit, verb):
            for u, v, result in expected_calls:
                if unit == u and verb == v:
                    return result
            raise AssertionError("unexpected timer probe")

        with patch.object(mod, "exact_timer_state", side_effect=good_state):
            mod.require_owner_selected_state()

        for bad in (
            ("inactive", "inactive", "disabled"),
            ("active", "active", "enabled"),
            ("active", "inactive", "enabled"),
            ("active", "failed", "disabled"),
            ("active", "unknown", "unknown"),
        ):
            with self.subTest(states=bad):
                with patch.object(mod, "exact_timer_state", side_effect=list(bad)):
                    with self.assertRaisesRegex(ValueError, "UNEXPECTED_TIMER_STATE"):
                        mod.require_owner_selected_state()

    def test_no_automatic_unit_start_or_remote_network_operation(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn('"start", "kmj-elite-health-check', text)
        self.assertNotIn('systemctl start', text)
        self.assertNotIn('curl ', text)
        self.assertNotIn('StrictHostKeyChecking=no', text)
        self.assertIn('mode.add_argument("--inspect"', text)
        self.assertIn('mode.add_argument("--apply"', text)
        self.assertIn("HEALTH_UNIT_INVOCATION=NOT_EXECUTED", text)


if __name__ == "__main__":
    unittest.main()
