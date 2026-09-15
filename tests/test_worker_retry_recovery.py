import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = ROOT / "scripts" / "continuity_watchdog.py"
CYCLE_WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-cycle.yml"


class ContinuityWatchdogContractTests(unittest.TestCase):
    def load_watchdog(self):
        self.assertTrue(
            WATCHDOG_PATH.is_file(),
            "continuity watchdog module must exist",
        )
        spec = importlib.util.spec_from_file_location("continuity_watchdog", WATCHDOG_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_only_known_transient_patch_blocks_are_auto_recoverable(self):
        watchdog = self.load_watchdog()

        self.assertTrue(
            watchdog.is_recoverable_block(
                "Autonomous worker stopped safely: `PATCH_CHECK_FAILED/CORRUPT_DIFF`."
            )
        )
        self.assertTrue(
            watchdog.is_recoverable_block(
                "Autonomous worker stopped safely: `PATCH_CHECK_FAILED/CONTEXT_MISMATCH`."
            )
        )
        self.assertFalse(
            watchdog.is_recoverable_block(
                "Autonomous patch failed local verification and was not pushed."
            )
        )
        self.assertFalse(
            watchdog.is_recoverable_block(
                "Autonomous worker blocked this task: high-risk term `production`."
            )
        )

    def test_watchdog_requeues_and_dispatches_once_when_recovery_occurs(self):
        watchdog = self.load_watchdog()

        class FakeGitHub:
            def __init__(self):
                self.removed = []
                self.comments = []
                self.dispatched = 0

            def request(self, method, path, **kwargs):
                if path.startswith("/issues?state=open"):
                    return [{"number": 142}]
                if path == "/issues/142/comments?per_page=100":
                    return [
                        {
                            "user": {"login": "github-actions[bot]"},
                            "body": "Autonomous worker stopped safely: `PATCH_CHECK_FAILED/CORRUPT_DIFF`. No merge/deploy was performed.",
                        }
                    ]
                if path == "/actions/workflows/autonomous-worker.yml/dispatches":
                    self.dispatched += 1
                    return None
                raise AssertionError((method, path, kwargs))

            def remove_label(self, issue_number, label):
                self.removed.append((issue_number, label))

            def comment(self, issue_number, body):
                self.comments.append((issue_number, body))

        gh = FakeGitHub()
        recovered = watchdog.recover_and_restart(gh)

        self.assertEqual(recovered, [142])
        self.assertEqual(gh.removed, [(142, "autonomous-blocked")])
        self.assertEqual(gh.dispatched, 1)
        self.assertTrue(any("requeued" in body.lower() for _, body in gh.comments))

    def test_five_minute_cycle_runs_continuity_watchdog_with_minimum_write_scope(self):
        workflow = CYCLE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("cron: '*/5 * * * *'", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("python3 scripts/continuity_watchdog.py", workflow)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", workflow)


if __name__ == "__main__":
    unittest.main()
