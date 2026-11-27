#!/usr/bin/env python3
"""Free-only GitHub workflow regression guards; no packages or network calls."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class FreeActionsBudgetSafetyTest(unittest.TestCase):
    def test_staging_watchdog_cannot_consume_15_minute_hosted_runs(self) -> None:
        source = (WORKFLOWS / "staging-vps-deploy-fixed.yml").read_text()
        self.assertIn("cron: '17 */6 * * *'", source)
        self.assertNotIn("*/15 * * * *", source)

    def test_staging_promotion_and_manual_triggers_remain_intact(self) -> None:
        source = (WORKFLOWS / "staging-vps-deploy-fixed.yml").read_text()
        self.assertIn("workflow_run:", source)
        self.assertIn("- Staging Promotion Gate", source)
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("environment: staging", source)
        self.assertIn("cancel-in-progress: true", source)

    def test_infra_checks_cancel_obsolete_runs_but_keep_triggers(self) -> None:
        source = (WORKFLOWS / "server-infra-ci.yml").read_text()
        self.assertIn("verify-server-infra:", source)
        self.assertIn("pull_request:", source)
        self.assertIn("push:", source)
        self.assertIn("'infra/server/**'", source)
        self.assertRegex(
            source,
            re.compile(r"concurrency:\s+group: server-infra-.*\n\s+cancel-in-progress: true"),
        )


if __name__ == "__main__":
    unittest.main()
