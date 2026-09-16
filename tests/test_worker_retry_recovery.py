import asyncio
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from controller.persistent_worker import commit_and_push, propose_patch, task_risk


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = ROOT / "scripts" / "continuity_watchdog.py"
CYCLE_WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-cycle.yml"


class WorkerPatchPreflightTests(unittest.TestCase):
    def test_unappliable_generated_patch_is_reprompted_before_returning(self):
        issue = {
            "number": 142,
            "title": "Accessibility fix",
            "body": "## Task files\n- `docs/a.md`\n",
        }
        bad_patch = (
            "diff --git a/docs/a.md b/docs/a.md\n"
            "--- a/docs/a.md\n"
            "+++ b/docs/a.md\n"
            "@@ -1 +1 @@\n"
            "-wrong-context\n"
            "+new\n"
        )
        good_patch = (
            "diff --git a/docs/a.md b/docs/a.md\n"
            "--- a/docs/a.md\n"
            "+++ b/docs/a.md\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        bad = {
            "response": {
                "choices": [
                    {"message": {"content": json.dumps({"summary": "first", "patch": bad_patch, "tests": []})}}
                ]
            }
        }
        good = {
            "response": {
                "choices": [
                    {"message": {"content": json.dumps({"summary": "fixed", "patch": good_patch, "tests": []})}}
                ]
            }
        }
        router = Mock()
        router.complete = AsyncMock(side_effect=[bad, good])
        check_runner = Mock(
            side_effect=[
                Mock(returncode=1, stdout="", stderr="error: corrupt patch at line 8"),
                Mock(returncode=0, stdout="", stderr=""),
            ]
        )

        with (
            patch("controller.persistent_worker.FreeCloudRouter", return_value=router),
            patch("controller.persistent_worker.run", check_runner),
        ):
            payload, _ = asyncio.run(
                propose_patch(issue, "FILE docs/a.md\nold\nEND FILE", ["docs/a.md"])
            )

        self.assertEqual(payload["patch"], good_patch)
        self.assertEqual(router.complete.await_count, 2)
        apply_checks = [
            call.args[0]
            for call in check_runner.call_args_list
            if call.args and call.args[0][:3] == ["git", "apply", "--check"]
        ]
        self.assertEqual(len(apply_checks), 2)

    def test_commit_stages_only_verified_patch_paths(self):
        target = "apps/platform/resources/js/components/alert-error.tsx"
        runner = Mock(
            side_effect=[
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=1, stdout="", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]
        )

        with patch("controller.persistent_worker.run", runner):
            commit_and_push(
                "agent/auto-152-1",
                {"title": "Scoped accessibility fix"},
                "summary",
                [target],
            )

        add_calls = [
            call.args[0]
            for call in runner.call_args_list
            if call.args and call.args[0][:2] == ["git", "add"]
        ]
        self.assertEqual(add_calls, [["git", "add", "--", target]])
        self.assertNotIn(["git", "add", "--all"], add_calls)


class RiskConstraintClassificationTests(unittest.TestCase):
    def test_explicit_negative_high_risk_constraints_are_not_actions(self):
        for text in (
            "No production changes.",
            "Do not modify DNS.",
            "Production remains untouched.",
            "Do not change billing or payment settings.",
            "Never rotate the signing key.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(task_risk(text))

    def test_real_high_risk_actions_remain_blocked(self):
        for text, expected in (
            ("deploy production now", "production"),
            ("modify DNS for the live domain", "dns"),
            ("change billing settings", "billing"),
            ("rotate a signing key", "signing key"),
            ("drop database customers", "drop database"),
        ):
            with self.subTest(text=text):
                self.assertEqual(task_risk(text), expected)

    def test_negative_constraint_does_not_hide_another_real_high_risk_action(self):
        self.assertEqual(
            task_risk("No production changes; modify DNS for the live domain."),
            "dns",
        )


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

    def test_watchdog_dispatches_worker_when_safe_work_is_idle(self):
        watchdog = self.load_watchdog()

        class FakeGitHub:
            def __init__(self):
                self.dispatched = 0

            def request(self, method, path, **kwargs):
                if path == "/issues?state=open&labels=autonomous-safe&per_page=50":
                    return [
                        {
                            "number": 201,
                            "labels": [{"name": "autonomous-safe"}],
                        }
                    ]
                if path == "/actions/workflows/autonomous-worker.yml/dispatches":
                    self.dispatched += 1
                    return None
                raise AssertionError((method, path, kwargs))

        gh = FakeGitHub()
        dispatched = watchdog.ensure_safe_work_progress(gh)

        self.assertTrue(dispatched)
        self.assertEqual(gh.dispatched, 1)

    def test_watchdog_does_not_duplicate_active_blocked_or_pending_work(self):
        watchdog = self.load_watchdog()

        for state_label in (
            "autonomous-running",
            "autonomous-blocked",
            "autonomous-pr-pending",
        ):
            with self.subTest(state_label=state_label):
                class FakeGitHub:
                    def __init__(self):
                        self.dispatched = 0

                    def request(self, method, path, **kwargs):
                        if path == "/issues?state=open&labels=autonomous-safe&per_page=50":
                            return [
                                {
                                    "number": 202,
                                    "labels": [
                                        {"name": "autonomous-safe"},
                                        {"name": state_label},
                                    ],
                                }
                            ]
                        if path == "/actions/workflows/autonomous-worker.yml/dispatches":
                            self.dispatched += 1
                            return None
                        raise AssertionError((method, path, kwargs))

                gh = FakeGitHub()
                dispatched = watchdog.ensure_safe_work_progress(gh)

                self.assertFalse(dispatched)
                self.assertEqual(gh.dispatched, 0)

    def test_five_minute_cycle_runs_continuity_watchdog_with_minimum_write_scope(self):
        workflow = CYCLE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("cron: '*/5 * * * *'", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("python3 scripts/continuity_watchdog.py", workflow)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", workflow)


if __name__ == "__main__":
    unittest.main()
