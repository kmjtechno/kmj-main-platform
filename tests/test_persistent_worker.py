import asyncio
import json
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx

from controller.persistent_worker import (
    GitHubClient,
    PENDING_LABEL,
    BLOCKED_LABEL,
    CHECKPOINT_PREFIX,
    github_failure,
    validate_checkpoint,
    submit_prepared_pr,
    resume_prepared_prs,
    extract_model_json,
    patch_paths,
    propose_patch,
    paths_conflict,
    task_risk,
    validate_patch,
    worker_capacity,
    task_files,
    task_context,
    execute_one,
    worker_failure,
)


class PersistentWorkerSafetyTests(unittest.TestCase):
    def test_worker_failure_retains_safe_categories_only(self):
        self.assertEqual(worker_failure(RuntimeError("PATCH_CHECK_FAILED:error: corrupt patch at line 8")), "PATCH_CHECK_FAILED/CORRUPT_DIFF")
        self.assertEqual(worker_failure(RuntimeError("PATCH_CHECK_FAILED:private response body")), "PATCH_CHECK_FAILED")
        self.assertEqual(worker_failure(RuntimeError("secret-token-value")), "RuntimeError")

    def test_explicit_context_scope_rejects_sensitive_or_ambiguous_paths(self):
        for path in (".env", "docs/../secrets/key.md", "docs/.env.md", "controller/main.py"):
            with self.assertRaises(ValueError):
                task_files({"body": f"## Task files\n- `{path}`\n"})
        self.assertEqual(task_files({"body": "An older bounded task"}), [])
        self.assertEqual(task_files({"body": "## Task files\n- `docs/a.md`\n\n## Acceptance\nKeep concise"}), ["docs/a.md"])

    def test_context_is_bounded_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs/a.md").write_text("Current source")
            self.assertIn("Current source", task_context(["docs/a.md"], root))
            (root / "docs/link.md").symlink_to(root / "docs/a.md")
            with self.assertRaisesRegex(ValueError, "SYMLINK"):
                task_context(["docs/link.md"], root)
            (root / "docs/a.md").write_text("x" * 24001)
            with self.assertRaisesRegex(ValueError, "TOO_LARGE"):
                task_context(["docs/a.md"], root)

    def test_overlapping_declared_scope_does_not_call_ai(self):
        gh = Mock()
        issue = {"number": 200, "body": "## Task files\n- `docs/a.md`\n"}
        with patch("controller.persistent_worker.select_issue", return_value=issue), patch("controller.persistent_worker.propose_patch") as propose:
            self.assertEqual(execute_one(gh, {"docs/a.md"}), (False, set()))
            propose.assert_not_called()

    def test_patch_outside_declared_scope_is_never_applied(self):
        gh = Mock()
        issue = {"number": 200, "body": "## Task files\n- `docs/a.md`\n"}
        payload = {"patch": "diff --git a/docs/b.md b/docs/b.md\n--- a/docs/b.md\n+++ b/docs/b.md\n"}
        with patch("controller.persistent_worker.select_issue", return_value=issue), patch("controller.persistent_worker.prepare_branch"), patch("controller.persistent_worker.task_context", return_value="source"), patch("controller.persistent_worker.propose_patch", return_value=(payload, {})), patch("controller.persistent_worker.apply_patch") as apply:
            execute_one(gh)
            apply.assert_not_called()
            gh.add_labels.assert_any_call(200, [BLOCKED_LABEL])

    def test_invalid_patch_shape_is_reprompted_before_returning(self):
        issue = {"number": 142, "body": "## Task files\n- `docs/a.md`\n"}
        bad = {"response": {"choices": [{"message": {"content": json.dumps({"patch": "not-a-diff"})}}]}}
        good_patch = "diff --git a/docs/a.md b/docs/a.md\n--- a/docs/a.md\n+++ b/docs/a.md\n@@ -1 +1 @@\n-old\n+new\n"
        good = {"response": {"choices": [{"message": {"content": json.dumps({"summary": "fix", "patch": good_patch, "tests": []})}}]}}
        router = Mock()
        router.complete = AsyncMock(side_effect=[bad, good])
        with patch("controller.persistent_worker.FreeCloudRouter", return_value=router):
            payload, _ = asyncio.run(propose_patch(issue, "FILE docs/a.md\nold\nEND FILE", ["docs/a.md"]))
        self.assertEqual(payload["patch"], good_patch)
        self.assertEqual(router.complete.await_count, 2)

    def test_invalid_model_output_remains_retryable_instead_of_blocked(self):
        gh = Mock()
        issue = {"number": 142, "body": "## Task files\n- `docs/a.md`\n"}
        with patch("controller.persistent_worker.select_issue", return_value=issue), \
             patch("controller.persistent_worker.prepare_branch"), \
             patch("controller.persistent_worker.task_context", return_value="source"), \
             patch("controller.persistent_worker.propose_patch", side_effect=ValueError("PATCH_NOT_UNIFIED_DIFF")):
            self.assertEqual(execute_one(gh), (False, set()))
        self.assertNotIn((142, [BLOCKED_LABEL]), [call.args for call in gh.add_labels.call_args_list])
        gh.remove_label.assert_any_call(142, "autonomous-running")
        self.assertTrue(any("retry" in str(call.args[1]).lower() for call in gh.comment.call_args_list))

    def test_extracts_json_after_short_introduction_or_fence(self):
        payload = {"summary": "Guide", "patch": "diff --git a/docs/a.md b/docs/a.md\n", "tests": []}
        for content in (json.dumps(payload), "Here is the patch:\n" + json.dumps(payload), "Here is the patch:\n```json\n" + json.dumps(payload) + "\n```\nDone."):
            result = {"response": {"choices": [{"message": {"content": content}}]}}
            self.assertEqual(extract_model_json(result), payload)

    def test_malformed_json_is_not_repaired_into_an_accepted_patch(self):
        for content in ('{"patch":"unescaped\nnewline"}', '{"patch":null}', 'An execution plan only'):
            result = {"response": {"choices": [{"message": {"content": content}}]}}
            with self.assertRaises(ValueError):
                extract_model_json(result)

    def test_accepts_allowlisted_platform_patch(self):
        patch_text = """diff --git a/apps/platform/example.txt b/apps/platform/example.txt
--- a/apps/platform/example.txt
+++ b/apps/platform/example.txt
@@ -1 +1 @@
-old
+new
"""
        self.assertEqual(validate_patch(patch_text), ["apps/platform/example.txt"])

    def test_rejects_workflow_modification(self):
        patch_text = """diff --git a/.github/workflows/x.yml b/.github/workflows/x.yml
--- a/.github/workflows/x.yml
+++ b/.github/workflows/x.yml
@@ -1 +1 @@
-old
+new
"""
        with self.assertRaisesRegex(ValueError, "DENIED_PATH"):
            validate_patch(patch_text)

    def test_extracts_unique_paths(self):
        patch_text = """diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -1 +1 @@
-a
+b
"""
        self.assertEqual(patch_paths(patch_text), ["docs/a.md"])

    def test_high_risk_task_is_blocked(self):
        self.assertEqual(task_risk("rotate the production signing key"), "production")

    def test_safe_task_has_no_risk(self):
        self.assertIsNone(task_risk("improve sandbox entitlement empty state"))

    def test_worker_capacity_defaults_to_one(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker_capacity(), 1)

    def test_worker_capacity_is_bounded(self):
        with patch.dict(os.environ, {"KMJ_WORKER_MAX_TASKS_PER_CYCLE": "99"}, clear=True):
            self.assertEqual(worker_capacity(), 3)

    def test_invalid_worker_capacity_fails_closed_to_one(self):
        with patch.dict(os.environ, {"KMJ_WORKER_MAX_TASKS_PER_CYCLE": "invalid"}, clear=True):
            self.assertEqual(worker_capacity(), 1)

    def test_overlapping_paths_conflict(self):
        self.assertTrue(paths_conflict({"apps/platform/a.php"}, {"apps/platform/a.php"}))
        self.assertTrue(paths_conflict({"docs/runbook"}, {"docs/runbook/a.md"}))

    def test_disjoint_paths_do_not_conflict(self):
        self.assertFalse(paths_conflict({"apps/platform/a.php"}, {"docs/a.md"}))


    def test_rejects_denied_deletion_hidden_beside_allowed_patch(self):
        patch_text = """diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -1 +1 @@
-old
+new
diff --git a/controller/main.py b/controller/main.py
deleted file mode 100644
--- a/controller/main.py
+++ /dev/null
@@ -1 +0,0 @@
-old
"""
        with self.assertRaisesRegex(ValueError, "DENIED_PATH"):
            validate_patch(patch_text)

    def test_rejects_rename_or_symlink_patch(self):
        for patch_text in (
            "diff --git a/controller/main.py b/docs/a.md\n+++ b/docs/a.md\n",
            "diff --git a/docs/link b/docs/link\nnew file mode 120000\n+++ b/docs/link\n",
        ):
            with self.subTest(patch=patch_text), self.assertRaises(ValueError):
                validate_patch(patch_text)

    def test_required_checks_cannot_be_skipped(self):
        client = object.__new__(GitHubClient)
        for conclusion in ("skipped", "neutral", "success"):
            with patch.object(client, "request", return_value={"check_runs": [
                {"name": "verify", "status": "completed", "conclusion": conclusion},
            ]}):
                self.assertEqual(client.checks_green("sha", False), conclusion == "success")


class PreparedPullRequestTests(unittest.TestCase):
    def setUp(self):
        self.issue = {"number": 42, "title": "Add operator guide", "labels": [{"name": PENDING_LABEL}]}
        self.record = {"branch": "agent/auto-42-123", "sha": "a" * 40, "paths": ["docs/guide.md"], "model": "opencode/big-pickle"}
        self.gh = Mock()
        self.gh.request.return_value = {"object": {"sha": "a" * 40}}
        self.gh.open_agent_prs.return_value = []
        self.gh.create_pr.return_value = {"number": 43}

    def failure(self, status, message):
        response = httpx.Response(status, json={"message": message}, request=httpx.Request("POST", "https://api.github.com/repos/test/repo/pulls?token=never-log"))
        return httpx.HTTPStatusError("private error text", request=response.request, response=response)

    def test_checkpoint_rejects_wrong_issue_sha_and_denied_paths(self):
        self.assertEqual(validate_checkpoint(self.record, 42), self.record)
        for override in ({"branch": "agent/auto-43-123"}, {"sha": "bad"}, {"paths": [".github/workflows/x.yml"]}, {"paths": ["docs/../secrets/x"]}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                validate_checkpoint({**self.record, **override}, 42)

    def test_error_diagnostic_does_not_echo_body_query_or_credentials(self):
        detail = github_failure(self.failure(403, "GitHub Actions is not permitted to create or approve pull requests. secret=never-log"))
        self.assertEqual(detail["reason"], "ACTIONS_PR_CREATION_DISABLED")
        self.assertEqual(detail["status"], 403)
        self.assertNotIn("never-log", json.dumps(detail))
        self.assertNotIn("private error text", json.dumps(detail))

    def test_permission_failure_preserves_pending_branch_and_blocks_retry(self):
        self.gh.create_pr.side_effect = self.failure(403, "GitHub Actions is not permitted to create or approve pull requests.")
        self.assertFalse(submit_prepared_pr(self.gh, self.issue, self.record))
        self.gh.add_labels.assert_called_once_with(42, [BLOCKED_LABEL])
        self.gh.remove_label.assert_not_called()

    def test_transient_failure_keeps_checkpoint_retryable(self):
        self.gh.create_pr.side_effect = self.failure(503, "Service unavailable")
        self.assertFalse(submit_prepared_pr(self.gh, self.issue, self.record))
        self.gh.add_labels.assert_not_called()
        self.gh.remove_label.assert_not_called()

    def test_resume_uses_exact_prepared_commit_without_ai_generation(self):
        self.gh.pending_issues.return_value = [self.issue]
        self.gh.prepared_checkpoint.return_value = self.record
        with patch("controller.persistent_worker.propose_patch") as generate:
            self.assertTrue(resume_prepared_prs(self.gh))
            generate.assert_not_called()
        self.assertEqual(self.gh.create_pr.call_args.args[1], self.record["branch"])
        self.gh.remove_label.assert_called_once_with(42, PENDING_LABEL)

    def test_native_permission_block_is_not_retried_automatically(self):
        self.gh.pending_issues.return_value = [{**self.issue, "labels": [{"name": BLOCKED_LABEL}]}]
        self.assertFalse(resume_prepared_prs(self.gh))
        self.gh.prepared_checkpoint.assert_not_called()
        self.gh.create_pr.assert_not_called()

    def test_moved_branch_cannot_reuse_old_verification(self):
        self.gh.request.return_value = {"object": {"sha": "b" * 40}}
        with self.assertRaisesRegex(ValueError, "BRANCH_MOVED"):
            submit_prepared_pr(self.gh, self.issue, self.record)
        self.gh.create_pr.assert_not_called()

    def test_existing_pr_is_adopted_without_duplicate_submission(self):
        self.gh.open_agent_prs.return_value = [{"number": 43, "head": {"ref": self.record["branch"]}}]
        self.assertTrue(submit_prepared_pr(self.gh, self.issue, self.record))
        self.gh.create_pr.assert_not_called()
        self.gh.remove_label.assert_called_once_with(42, PENDING_LABEL)

    def test_untrusted_checkpoint_comment_is_not_accepted(self):
        gh = object.__new__(GitHubClient)
        body = CHECKPOINT_PREFIX + json.dumps(self.record)
        with patch.object(gh, "request", return_value=[{"user": {"login": "someone"}, "body": body}]):
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_MISSING"):
                gh.prepared_checkpoint(42)
        with patch.object(gh, "request", return_value=[{"user": {"login": "github-actions[bot]"}, "body": "Verification output:\n" + body}]):
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_MISSING"):
                gh.prepared_checkpoint(42)
        with patch.object(gh, "request", return_value=[{"user": {"login": "github-actions[bot]"}, "body": body}]):
            self.assertEqual(gh.prepared_checkpoint(42), self.record)


if __name__ == "__main__":
    unittest.main()
