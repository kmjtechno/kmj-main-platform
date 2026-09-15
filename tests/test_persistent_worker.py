import json
import os
import unittest
from unittest.mock import patch

from controller.persistent_worker import (
    GitHubClient,
    extract_model_json,
    patch_paths,
    paths_conflict,
    task_risk,
    validate_patch,
    worker_capacity,
)


class PersistentWorkerSafetyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
