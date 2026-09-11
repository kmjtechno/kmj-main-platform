import unittest

from controller.persistent_worker import patch_paths, task_risk, validate_patch


class PersistentWorkerSafetyTests(unittest.TestCase):
    def test_accepts_allowlisted_platform_patch(self):
        patch = """diff --git a/apps/platform/example.txt b/apps/platform/example.txt
--- a/apps/platform/example.txt
+++ b/apps/platform/example.txt
@@ -1 +1 @@
-old
+new
"""
        self.assertEqual(validate_patch(patch), ["apps/platform/example.txt"])

    def test_rejects_workflow_modification(self):
        patch = """diff --git a/.github/workflows/x.yml b/.github/workflows/x.yml
--- a/.github/workflows/x.yml
+++ b/.github/workflows/x.yml
@@ -1 +1 @@
-old
+new
"""
        with self.assertRaisesRegex(ValueError, "DENIED_PATH"):
            validate_patch(patch)
    def test_extracts_unique_paths(self):
        patch = """diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -1 +1 @@
-a
+b
"""
        self.assertEqual(patch_paths(patch), ["docs/a.md"])

    def test_high_risk_task_is_blocked(self):
        self.assertEqual(task_risk("rotate the production signing key"), "production")

    def test_safe_task_has_no_risk(self):
        self.assertIsNone(task_risk("improve sandbox entitlement empty state"))


if __name__ == "__main__":
    unittest.main()
