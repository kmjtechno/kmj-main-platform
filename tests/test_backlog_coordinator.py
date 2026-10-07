import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from controller.backlog_coordinator import (
    BacklogCoordinator,
    BacklogError,
    load_backlog,
    load_codebridge_status,
)
from controller.task_queue import TaskQueue


NOW = 1791364000.0
SHA = "a" * 40


class BacklogCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.backlog = self.root / "backlog.json"
        self.codebridge = self.state / "codebridge-status.json"
        self.queue_db = self.state / "queue.sqlite"
        self.status = self.state / "backlog-status.json"
        self.write_backlog()
        self.write_codebridge()

    def tearDown(self):
        self.temp.cleanup()

    def write_backlog(self, **overrides):
        value = {
            "schema_version": 1,
            "repository": "kmjtechno/kmj-main-platform",
            "codebridge": {
                "device": "main-platform-kmjtechnonetgmailcom",
                "project": "kmj-main-platform",
                "branch": "main",
            },
            "tasks": [{
                "id": "KMJ-PLATFORM-REVIEW-001",
                "project": "kmj-main-platform",
                "kind": "review",
                "prompt": "Produce a bounded review artifact only.",
                "data_classification": "confidential",
                "max_attempts": 3,
                "auto_enqueue": True,
            }],
        }
        value.update(overrides)
        self.backlog.write_text(json.dumps(value))

    def write_codebridge(self, **overrides):
        value = {
            "schema_version": 1,
            "repository": "kmjtechno/kmj-main-platform",
            "device": "main-platform-kmjtechnonetgmailcom",
            "project": "kmj-main-platform",
            "branch": "main",
            "connection": "connected",
            "version": "0.2.3",
            "writable": True,
            "gates": ["fast", "platform", "full"],
            "checkout_sha": SHA,
            "observed_utc_epoch": NOW - 10,
            "source": "kmj-codebridge-inspect",
        }
        value.update(overrides)
        self.codebridge.write_text(json.dumps(value))

    def coordinator(self):
        return BacklogCoordinator(
            backlog_path=self.backlog,
            codebridge_status_path=self.codebridge,
            queue_db=self.queue_db,
            state_root=self.state,
            status_path=self.status,
        )

    def test_correct_identity_enqueues_exactly_once_across_sync(self):
        coordinator = self.coordinator()
        first = coordinator.sync_once(now=NOW)
        second = coordinator.sync_once(now=NOW + 1)
        self.assertEqual(first["codebridge"]["project"], "kmj-main-platform")
        self.assertEqual(second["tasks"][0]["stage"], "queued")
        queue = TaskQueue(self.queue_db)
        self.assertIsNotNone(queue.get("backlog:KMJ-PLATFORM-REVIEW-001"))
        self.assertEqual(queue.get("backlog:KMJ-PLATFORM-REVIEW-001")["project"], "kmj-main-platform")

    def test_wrong_repo_project_device_or_branch_fails_closed(self):
        bad_backlogs = [
            {"repository": "kmjtechno/other"},
            {"codebridge": {"device": "wrong", "project": "kmj-main-platform", "branch": "main"}},
            {"codebridge": {"device": "main-platform-kmjtechnonetgmailcom", "project": "wrong", "branch": "main"}},
            {"codebridge": {"device": "main-platform-kmjtechnonetgmailcom", "project": "kmj-main-platform", "branch": "feature"}},
        ]
        for change in bad_backlogs:
            with self.subTest(change=change):
                self.write_backlog(**change)
                with self.assertRaises(BacklogError):
                    load_backlog(self.backlog)
        self.write_backlog()
        for field, value in [
            ("repository", "other/repo"),
            ("device", "wrong"),
            ("project", "wrong"),
            ("branch", "feature"),
        ]:
            with self.subTest(field=field):
                self.write_codebridge(**{field: value})
                with self.assertRaises(BacklogError):
                    load_codebridge_status(self.codebridge, now=NOW)
        self.write_codebridge()

    def test_stale_or_disconnected_codebridge_blocks_admission(self):
        self.write_codebridge(observed_utc_epoch=NOW - 901)
        with self.assertRaisesRegex(BacklogError, "STALE"):
            self.coordinator().sync_once(now=NOW)
        self.assertIsNone(TaskQueue(self.queue_db).get("backlog:KMJ-PLATFORM-REVIEW-001"))
        self.write_codebridge(connection="error")
        with self.assertRaisesRegex(BacklogError, "NOT_READY"):
            self.coordinator().sync_once(now=NOW)
        self.assertIsNone(TaskQueue(self.queue_db).get("backlog:KMJ-PLATFORM-REVIEW-001"))

    def test_completed_queue_item_is_only_artifact_ready(self):
        coordinator = self.coordinator()
        coordinator.sync_once(now=NOW)
        queue = TaskQueue(self.queue_db)
        task = queue.claim("worker", now=NOW + 1)
        queue.complete(task["id"], task["token"], {"artifact": "/private/path"}, now=NOW + 2)
        report = coordinator.sync_once(now=NOW + 3)
        self.assertEqual(report["tasks"][0]["stage"], "artifact_ready")
        self.assertFalse(report["tasks"][0]["product_complete"])
        self.assertNotIn("/private/path", json.dumps(report))

    def write_evidence(self, value):
        directory = self.state / "backlog-evidence"
        directory.mkdir(exist_ok=True)
        (directory / "KMJ-PLATFORM-REVIEW-001.json").write_text(json.dumps(value))

    def test_trusted_candidate_evidence_advances_only_to_candidate_tested(self):
        self.write_evidence({
            "task_id": "KMJ-PLATFORM-REVIEW-001",
            "stage": "candidate_tested",
            "validation_sha256": "b" * 64,
            "base_sha": SHA,
            "product_complete": False,
        })
        report = self.coordinator().sync_once(now=NOW)
        self.assertEqual(report["tasks"][0]["stage"], "candidate_tested")
        self.assertTrue(report["tasks"][0]["tests_executed"])
        self.assertFalse(report["product_complete"])

    def test_release_requires_deployed_and_health_verified_but_not_product_complete(self):
        self.write_evidence({
            "task_id": "KMJ-PLATFORM-REVIEW-001",
            "stage": "release",
            "release_sha": SHA,
            "deployed": True,
            "health_verified": True,
            "product_complete": False,
        })
        report = self.coordinator().sync_once(now=NOW)
        self.assertEqual(report["tasks"][0]["stage"], "release")
        self.assertFalse(report["tasks"][0]["product_complete"])

    def test_fake_product_completion_is_rejected(self):
        self.write_evidence({
            "task_id": "KMJ-PLATFORM-REVIEW-001",
            "stage": "release",
            "release_sha": SHA,
            "deployed": True,
            "health_verified": True,
            "product_complete": True,
        })
        with self.assertRaisesRegex(BacklogError, "PRODUCT_COMPLETION_FORBIDDEN"):
            self.coordinator().sync_once(now=NOW)

    def test_backlog_hash_binds_status_to_versioned_input(self):
        report = self.coordinator().sync_once(now=NOW)
        self.assertEqual(
            report["backlog_sha256"],
            hashlib.sha256(self.backlog.read_bytes()).hexdigest(),
        )

    def test_unsupported_task_kind_and_attempt_budget_rejected(self):
        data = json.loads(self.backlog.read_text())
        data["tasks"][0]["kind"] = "deploy"
        self.backlog.write_text(json.dumps(data))
        with self.assertRaisesRegex(BacklogError, "KIND_DENIED"):
            load_backlog(self.backlog)
        self.write_backlog()
        data = json.loads(self.backlog.read_text())
        data["tasks"][0]["max_attempts"] = 99
        self.backlog.write_text(json.dumps(data))
        with self.assertRaisesRegex(BacklogError, "MAX_ATTEMPTS"):
            load_backlog(self.backlog)


if __name__ == "__main__":
    unittest.main()
