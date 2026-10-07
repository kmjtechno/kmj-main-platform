import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from controller.github_control import (
    ControlError,
    GitHubControlBridge,
    GitHubStatusWriter,
    normalize_manifest,
)
from controller.task_queue import TaskQueue


REPO = "kmjtechno/kmj-main-platform"
REF = "feat/modelfabric-autonomy-20261007"
SHA1 = "1" * 40
SHA2 = "2" * 40


def manifest(commands, *, repository=REPO, ref=REF):
    return json.dumps({
        "schema_version": 1,
        "repository": repository,
        "ref": ref,
        "commands": commands,
    }).encode()


def command_hash(command):
    from controller.github_control import _canonical_hash
    clean = dict(command)
    clean.pop("content_hash", None)
    return _canonical_hash(clean)


class FakeSource:
    def __init__(self, sha, payload):
        self.sha = sha
        self.payload = payload
        self.calls = 0

    def fetch(self, previous):
        self.calls += 1
        return self.sha, self.payload


class BrokenSource:
    def fetch(self, previous):
        raise ControlError("GITHUB_FETCH_FAILED")


class GitHubControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = TaskQueue(self.root / "queue.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def normalize(self, commands, **kwargs):
        return normalize_manifest(
            manifest(commands, **kwargs),
            repository=REPO,
            ref=REF,
            allowed_projects={"kmj-main-platform"},
        )

    def test_pause_blocks_new_claims_without_touching_active_task(self):
        self.queue.enqueue("active", "project-a", {"kind": "plan", "prompt": "a"})
        self.queue.enqueue("next", "project-b", {"kind": "plan", "prompt": "b"})
        active = self.queue.claim("worker", now=100)
        self.assertEqual(active["id"], "active")
        commands = self.normalize([{"id": "pause-1", "operation": "pause"}])
        self.queue.apply_control_batch(REPO, REF, SHA1, commands, now=101)
        self.assertEqual(self.queue.get("active")["state"], "running")
        self.assertIsNone(self.queue.claim("worker-2", now=101))
        resume = self.normalize([{"id": "resume-1", "operation": "resume"}])
        self.queue.apply_control_batch(REPO, REF, SHA2, resume, now=102)
        claimed = self.queue.claim("worker-2", now=102)
        self.assertEqual(claimed["id"], "next")

    def test_import_is_exactly_once_across_polls_and_bridge_restart(self):
        payload = manifest([{
            "id": "enqueue-1",
            "operation": "enqueue",
            "task": {
                "id": "gh-task-1",
                "project": "kmj-main-platform",
                "kind": "plan",
                "prompt": "Create a bounded test plan",
            },
        }])
        source = FakeSource(SHA1, payload)
        status = self.root / "status.json"
        bridge = GitHubControlBridge(
            self.queue, source, status,
            repository=REPO, ref=REF, allowed_projects={"kmj-main-platform"},
        )
        bridge.poll_once()
        bridge.poll_once()
        restarted = GitHubControlBridge(
            TaskQueue(self.root / "queue.sqlite"), source, status,
            repository=REPO, ref=REF, allowed_projects={"kmj-main-platform"},
        )
        restarted.poll_once()
        with sqlite3.connect(self.root / "queue.sqlite") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM tasks WHERE id='gh-task-1'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM control_commands WHERE id='enqueue-1'").fetchone()[0], 1)

    def test_reused_command_id_with_changed_content_fails_atomically(self):
        first = self.normalize([{"id": "state-1", "operation": "pause"}])
        self.queue.apply_control_batch(REPO, REF, SHA1, first, now=1)
        changed = self.normalize([{"id": "state-1", "operation": "resume"}])
        with self.assertRaisesRegex(ValueError, "CONTROL_REPLAY_CONFLICT"):
            self.queue.apply_control_batch(REPO, REF, SHA2, changed, now=2)
        self.assertTrue(self.queue.control_snapshot()["paused"])

    def test_private_to_public_change_for_same_task_id_fails_closed(self):
        private = self.normalize([{
            "id": "enqueue-private",
            "operation": "enqueue",
            "task": {
                "id": "stable-task",
                "project": "kmj-main-platform",
                "kind": "review",
                "prompt": "Review private code",
            },
        }])
        self.queue.apply_control_batch(REPO, REF, SHA1, private, now=1)
        public = self.normalize([{
            "id": "enqueue-public",
            "operation": "enqueue",
            "task": {
                "id": "stable-task",
                "project": "kmj-main-platform",
                "kind": "review",
                "prompt": "Review private code",
                "data_classification": "public",
            },
        }])
        with self.assertRaisesRegex(ValueError, "CONTROL_TASK_CONFLICT"):
            self.queue.apply_control_batch(REPO, REF, SHA2, public, now=2)
        self.assertEqual(self.queue.get("stable-task")["payload"]["data_classification"], "confidential")

    def test_complete_batch_is_validated_before_any_admission(self):
        commands = [
            {
                "id": "ok",
                "operation": "enqueue",
                "task": {
                    "id": "would-have-been-added",
                    "project": "kmj-main-platform",
                    "kind": "text",
                    "prompt": "safe",
                },
            },
            {
                "id": "bad",
                "operation": "enqueue",
                "task": {
                    "id": "bad-task",
                    "project": "unknown-project",
                    "kind": "text",
                    "prompt": "safe",
                },
            },
        ]
        with self.assertRaisesRegex(ControlError, "CONTROL_PROJECT_DENIED"):
            self.normalize(commands)
        self.assertIsNone(self.queue.get("would-have-been-added"))

    def test_manifest_rejects_wrong_repo_ref_unknown_operation_and_extra_keys(self):
        bad_cases = [
            manifest([{"id": "x", "operation": "pause"}], repository="other/repo"),
            manifest([{"id": "x", "operation": "pause"}], ref="main"),
            manifest([{"id": "x", "operation": "shell"}]),
            manifest([{"id": "x", "operation": "pause", "extra": True}]),
        ]
        for raw in bad_cases:
            with self.subTest(raw=raw), self.assertRaises(ControlError):
                normalize_manifest(
                    raw,
                    repository=REPO,
                    ref=REF,
                    allowed_projects={"kmj-main-platform"},
                )

    def test_only_one_pause_or_resume_mutator_is_allowed_per_batch(self):
        with self.assertRaisesRegex(ControlError, "CONTROL_STATE_AMBIGUOUS"):
            self.normalize([
                {"id": "pause", "operation": "pause"},
                {"id": "resume", "operation": "resume"},
            ])

    def test_connectivity_loss_preserves_last_validated_control_state(self):
        pause = self.normalize([{"id": "pause-1", "operation": "pause"}])
        self.queue.apply_control_batch(REPO, REF, SHA1, pause, now=1)
        bridge = GitHubControlBridge(
            self.queue, BrokenSource(), self.root / "status.json",
            repository=REPO, ref=REF, allowed_projects={"kmj-main-platform"},
        )
        report = bridge.poll_once()
        self.assertTrue(report["stale"])
        self.assertEqual(report["connectivity"], "degraded")
        self.assertEqual(report["last_validated_source_sha"], SHA1)
        self.assertTrue(report["paused"])

    def test_status_writer_reports_read_only_without_separate_credential(self):
        writer = GitHubStatusWriter(REPO, None, None)
        self.assertEqual(writer.publish({"schema_version": 1}), "read_only")

    def test_read_only_writeback_state_survives_duplicate_polls(self):
        payload = manifest([{"id": "status-once", "operation": "status"}])
        source = FakeSource(SHA1, payload)
        status = self.root / "status.json"
        bridge = GitHubControlBridge(
            self.queue, source, status,
            repository=REPO, ref=REF, allowed_projects={"kmj-main-platform"},
        )
        self.assertEqual(bridge.poll_once()["writeback"], "read_only")
        self.assertEqual(bridge.poll_once()["writeback"], "read_only")

    def test_sanitized_status_never_exposes_result_path_or_arbitrary_error(self):
        self.queue.enqueue("t", "p", {"kind": "plan", "prompt": "secret prompt"})
        task = self.queue.claim("w", now=10)
        self.queue.fail("t", task["token"], "safe_code", retry_delay=0, now=11)
        status = self.queue.sanitized_status()
        encoded = json.dumps(status)
        self.assertNotIn("secret prompt", encoded)
        self.assertNotIn("safe_code", encoded)
        self.assertIn("INTERNAL_ERROR", encoded)


if __name__ == "__main__":
    unittest.main()
