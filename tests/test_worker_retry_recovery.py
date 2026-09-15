import unittest
from unittest.mock import Mock, patch

from controller.persistent_worker import BLOCKED_LABEL, execute_one


class TransientPatchRecoveryTests(unittest.TestCase):
    def test_corrupt_generated_diff_stays_retryable(self):
        gh = Mock()
        issue = {
            "number": 142,
            "body": "## Task files\n- `docs/a.md`\n",
        }
        payload = {
            "summary": "small safe change",
            "patch": (
                "diff --git a/docs/a.md b/docs/a.md\n"
                "--- a/docs/a.md\n"
                "+++ b/docs/a.md\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            ),
        }

        with (
            patch("controller.persistent_worker.select_issue", return_value=issue),
            patch("controller.persistent_worker.prepare_branch"),
            patch("controller.persistent_worker.task_context", return_value="source"),
            patch(
                "controller.persistent_worker.propose_patch",
                return_value=(payload, {"model": "verified-free"}),
            ),
            patch(
                "controller.persistent_worker.apply_patch",
                side_effect=RuntimeError(
                    "PATCH_CHECK_FAILED:error: corrupt patch at line 8"
                ),
            ),
        ):
            self.assertEqual(execute_one(gh), (False, set()))

        blocked_calls = [call.args for call in gh.add_labels.call_args_list]
        self.assertNotIn((142, [BLOCKED_LABEL]), blocked_calls)
        gh.remove_label.assert_any_call(142, "autonomous-running")
        self.assertTrue(
            any(
                "retry" in str(call.args[1]).lower()
                for call in gh.comment.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
