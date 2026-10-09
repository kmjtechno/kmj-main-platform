"""Free-first workflow invariants; no GitHub billing/network interaction."""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = (
    "codebridge-contract.yml",
    "codebridge-device-pairing-ci.yml",
    "codebridge-oauth-link-ci.yml",
)
GROUP = r"group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}"


class CodeBridgeFreeFirstWorkflowTests(unittest.TestCase):
    def test_stale_runs_cancel_per_pr_or_ref(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow):
                text = (ROOT / ".github/workflows" / workflow).read_text()
                self.assertEqual(1, len(re.findall(r"(?m)^concurrency:$", text)))
                self.assertIn(GROUP, text)
                self.assertRegex(text, r"(?m)^  cancel-in-progress: true$")

    def test_standard_runner_and_bounded_timeout(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow):
                text = (ROOT / ".github/workflows" / workflow).read_text()
                runners = re.findall(r"(?m)^    runs-on: (.+)$", text)
                self.assertTrue(runners)
                self.assertEqual(["ubuntu-latest"] * len(runners), runners)
                timeouts = [int(t) for t in re.findall(r"(?m)^    timeout-minutes: (\d+)$", text)]
                self.assertEqual(len(runners), len(timeouts))
                self.assertTrue(all(0 < t <= 20 for t in timeouts))

    def test_documented_zero_metered_budget_keeps_quality_gates(self):
        text = (ROOT / "docs/ops/GITHUB_ZERO_OVERAGE_POLICY.md").read_text()
        for contract in ("USD 0", "Stop usage when budget limit is reached",
                         "cannot verify or modify", "required check"):
            self.assertIn(contract, text)


if __name__ == "__main__":
    unittest.main()
