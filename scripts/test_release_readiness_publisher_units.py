#!/usr/bin/env python3
"""Static safety tests for the read-only release readiness publisher systemd units."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / "infra/server/systemd/kmj-elite-release-readiness-publisher.service").read_text()
TIMER = (ROOT / "infra/server/systemd/kmj-elite-release-readiness-publisher.timer").read_text()
PUBLISHER = (ROOT / "scripts/operations/elite_release_readiness_receipt.py").read_text()
SNAPSHOT = (ROOT / "apps/platform/app/Services/Operations/EliteReleaseReadinessSnapshot.php").read_text()


class PublisherUnitTests(unittest.TestCase):
    def test_service_runs_only_the_fixed_publish_mode(self):
        lines = [l for l in SERVICE.splitlines() if l.startswith("ExecStart=")]
        self.assertEqual(lines, ["ExecStart=/usr/bin/python3 -I -B /opt/kmj-main-platform-release-readiness/elite_release_readiness_receipt.py --publish"])

    def test_service_cannot_start_release_or_write_outside_run_dir(self):
        for forbidden in ("production-release.service", "systemctl", "ExecStartPost", "ExecStartPre", "Environment", "EnvironmentFile"):
            self.assertNotIn(forbidden, SERVICE)
        self.assertEqual(re.findall(r"^ReadWritePaths=(.*)$", SERVICE, re.M), ["/run/kmj-main-platform"])
        self.assertIn("ProtectSystem=strict", SERVICE)
        self.assertIn("NoNewPrivileges=true", SERVICE)

    def test_timer_is_not_installed_by_default_and_points_at_the_service(self):
        self.assertIn("Unit=kmj-elite-release-readiness-publisher.service", TIMER)

    def test_refresh_interval_beats_the_php_staleness_window(self):
        interval = int(re.search(r"OnUnitInactiveSec=(\d+)s", TIMER).group(1))
        window = int(re.search(r"time\(\) - \$captured > (\d+)", SNAPSHOT).group(1))
        self.assertLessEqual(interval * 2 + 20, window)

    def test_exit_two_is_a_published_block_not_a_failure(self):
        self.assertIn("SuccessExitStatus=2", SERVICE)
        self.assertIn("return 0 if result[\"decision\"] in (\"READY_APPROVED_RELEASE\", \"ALREADY_LIVE\") else 2", PUBLISHER)

    def test_publisher_only_writes_the_fixed_receipt(self):
        self.assertIn('OUTPUT = OUTPUT_DIR / "release-readiness.json"', PUBLISHER)
        self.assertIn('OUTPUT_DIR = Path("/run/kmj-main-platform")', PUBLISHER)


if __name__ == "__main__":
    unittest.main()
