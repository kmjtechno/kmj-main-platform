"""Rejected patches stay private; only stable validation codes enter retries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from controller.autonomy_worker import AutonomyWorker
from controller.task_queue import TaskQueue

VALID = "diff --git a/docs/example.md b/docs/example.md\n--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n"

class Replies:
    def __init__(self, *contents):
        self.contents = iter(contents)
        self.messages = []

    async def complete(self, messages, **kwargs):
        self.messages.append(messages)
        content = next(self.contents)
        if isinstance(content, Exception):
            raise content
        return {"provider":"test", "model":"test", "response":{"choices":[{"message":{"content":content}}]}}

class PatchArtifactDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = TaskQueue(self.root / "queue.sqlite")
        self.queue.enqueue("private-task-id", "private-project", {"kind":"patch", "prompt":"PROMPT_SECRET_SENTINEL"})
        self.artifacts = self.root / "artifacts"

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def execute(self, router):
        worker = AutonomyWorker(self.queue, self.artifacts, router=router)
        task = self.queue.claim("test", now=10000000000)
        with self.assertLogs("kmj.autonomy", level="WARNING") as captured:
            await worker._execute(task)
        return worker, task, "\n".join(captured.output)

    async def test_rejected_patch_is_private_and_queue_has_static_code(self):
        worker, task, logs = await self.execute(Replies("OUTPUT_SECRET_SENTINEL not a diff"))
        saved = self.queue.get("private-task-id")
        self.assertEqual(saved["state"], "queued")
        self.assertEqual(saved["error"], "PATCH_NOT_UNIFIED_DIFF")
        name = "rejected-" + hashlib.sha256((task["id"] + ":" + task["token"]).encode()).hexdigest() + ".json"
        path = self.artifacts / name
        diagnostic = json.loads(path.read_text())
        self.assertEqual(diagnostic["stage"], "patch_rejected")
        self.assertEqual(diagnostic["validation_code"], "PATCH_NOT_UNIFIED_DIFF")
        self.assertEqual(diagnostic["content"], "OUTPUT_SECRET_SENTINEL not a diff")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("PROMPT_SECRET_SENTINEL", path.read_text())
        self.assertNotIn("OUTPUT_SECRET_SENTINEL", logs)
        self.assertNotIn("PROMPT_SECRET_SENTINEL", logs)
        self.assertNotIn("OUTPUT_SECRET_SENTINEL", json.dumps(saved))
        self.assertEqual(worker.completed, 0)

    async def test_path_bearing_validation_error_never_enters_logs_or_queue(self):
        patch = "diff --git a/secrets/PRIVATE_TOKEN b/secrets/PRIVATE_TOKEN\n--- a/secrets/PRIVATE_TOKEN\n+++ b/secrets/PRIVATE_TOKEN\n@@ -1 +1 @@\n-old\n+new\n"
        worker, task, logs = await self.execute(Replies(patch))
        self.assertEqual(self.queue.get(task["id"])["error"], "DENIED_PATH")
        self.assertNotIn("PRIVATE_TOKEN", logs)
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(self.queue.get(task["id"])))
        self.assertIn("DENIED_PATH", logs)

    async def test_retry_receives_only_safe_feedback_and_remains_strict(self):
        router = Replies("PREVIOUS_OUTPUT_SECRET fenced prose", VALID)
        worker, task, logs = await self.execute(router)
        retried = self.queue.claim("retry", now=10000000031)
        await worker._execute(retried)
        instruction = router.messages[1][0]["content"]
        self.assertIn("PATCH_NOT_UNIFIED_DIFF", instruction)
        self.assertIn("unified", instruction)
        self.assertIn("no Markdown fences", instruction)
        self.assertNotIn("PREVIOUS_OUTPUT_SECRET", json.dumps(router.messages[1]))
        self.assertEqual(self.queue.get(task["id"])["state"], "completed")

    async def test_oversized_patch_diagnostic_content_is_bounded_utf8(self):
        worker, task, logs = await self.execute(Replies("é" * 100001))
        self.assertEqual(self.queue.get(task["id"])["error"], "INVALID_MODEL_OUTPUT")
        files = list(self.artifacts.glob("rejected-*.json"))
        self.assertEqual(len(files), 1)
        diagnostic = json.loads(files[0].read_text())
        self.assertLessEqual(len(diagnostic["content"].encode()), 100000)
        self.assertTrue(diagnostic["truncated"])
        self.assertEqual(diagnostic["original_bytes"], 200002)
        self.assertEqual(worker.completed, 0)

    async def test_unrelated_exception_cannot_spoof_validation_code(self):
        worker, task, logs = await self.execute(Replies(ValueError("DENIED_PATH:UNRELATED_SECRET")))
        self.assertEqual(self.queue.get(task["id"])["error"], "ValueError")
        self.assertNotIn("UNRELATED_SECRET", logs)
        self.assertEqual(list(self.artifacts.glob("rejected-*.json")), [])
