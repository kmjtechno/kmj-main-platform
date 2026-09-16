from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from scripts.delivery_control_bridge import DEFAULT_OUTPUT, build_snapshot, publish_snapshot


class FakeApi:
    def __init__(self, responses):
        self.responses = responses

    def get(self, path):
        return self.responses[path]


class DeliveryControlBridgeTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi({
            "/actions/workflows/autonomous-worker.yml/runs?per_page=10": {
                "workflow_runs": [
                    {
                        "id": 901,
                        "run_number": 120,
                        "run_attempt": 2,
                        "status": "in_progress",
                        "conclusion": None,
                        "run_started_at": "2026-09-16T07:00:00Z",
                    },
                    {
                        "id": 900,
                        "run_number": 119,
                        "run_attempt": 1,
                        "status": "completed",
                        "conclusion": "success",
                    },
                ]
            },
            "/actions/runs/901/jobs?per_page=20": {
                "jobs": [
                    {
                        "name": "autonomous",
                        "status": "in_progress",
                        "steps": [
                            {"name": "Checkout", "status": "completed", "conclusion": "success"},
                            {"name": "Run persistent worker", "status": "in_progress", "conclusion": None},
                        ],
                    }
                ]
            },
            "/issues?state=open&labels=autonomous-running&per_page=10": [
                {"number": 155, "title": "Harden operator state", "labels": [{"name": "autonomous-safe"}, {"name": "autonomous-running"}]}
            ],
            "/issues?state=open&labels=autonomous-blocked&per_page=10": [],
            "/pulls?state=open&per_page=50": [
                {"number": 156, "title": "agent: harden operator state", "state": "open", "head": {"ref": "agent/auto-155-1", "sha": "a" * 40}}
            ],
            f"/commits/{'a' * 40}/check-runs?per_page=100": {
                "check_runs": [
                    {"name": "verify", "status": "completed", "conclusion": "success"},
                    {"name": "platform", "status": "in_progress", "conclusion": None},
                ]
            },
            "/git/ref/heads/main": {"object": {"sha": "b" * 40}},
            "/git/ref/heads/staging-approved": {"object": {"sha": "c" * 40}},
        })

    def test_builds_sanitized_live_delivery_snapshot(self):
        snapshot = build_snapshot(
            self.api,
            runner_count=2,
            busy_runner_count=1,
            monitor_payload={"deployment": {"deployed_sha": "d" * 40}},
            captured_at=datetime(2026, 9, 16, 7, 5, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["version"], 1)
        self.assertEqual(snapshot["status"], "active")
        self.assertEqual(snapshot["current_worker"]["run_number"], 120)
        self.assertEqual(snapshot["current_worker"]["phase"], "Run persistent worker")
        self.assertEqual(snapshot["current_worker"]["retry_count"], 1)
        self.assertEqual(snapshot["current_task"]["issue_number"], 155)
        self.assertEqual(len(snapshot["runners"]), 2)
        self.assertEqual(sum(1 for runner in snapshot["runners"] if runner["busy"]), 1)
        self.assertEqual(snapshot["pull_request"]["number"], 156)
        self.assertEqual(snapshot["ci"]["status"], "in_progress")
        self.assertEqual(snapshot["staging"]["approved_sha"], "c" * 40)
        self.assertEqual(snapshot["staging"]["deployed_sha"], "d" * 40)
        self.assertEqual(len(snapshot["recent_worker_runs"]), 2)
        self.assertTrue(any(stage["key"] == "worker" for stage in snapshot["pipeline"]))

    def test_default_output_uses_shared_runner_directory(self):
        self.assertEqual(DEFAULT_OUTPUT, Path("/var/tmp/kmj-delivery-control/status.json"))
        config = (Path(__file__).resolve().parents[1] / "apps/platform/config/kmj.php").read_text(encoding="utf-8")
        self.assertIn("/var/tmp/kmj-delivery-control/status.json", config)

    def test_publish_is_atomic_and_world_readable_sanitized_evidence(self):
        snapshot = {"version": 1, "status": "idle", "captured_at": "2026-09-16T07:05:00+00:00"}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "delivery-control.json"
            publish_snapshot(target, snapshot)
            self.assertTrue(target.is_file())
            if os.name != "nt":
                self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertIn('"status":"idle"', target.read_text(encoding="utf-8"))

    def test_publish_tolerates_shared_directory_chmod_denied_when_directory_is_writable(self):
        snapshot = {"version": 1, "status": "active", "captured_at": "2026-09-16T07:06:00+00:00"}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "status.json"
            real_chmod = os.chmod

            def chmod_with_foreign_owned_directory(path, mode):
                if Path(path) == target.parent:
                    raise PermissionError("foreign runner owns shared directory")
                return real_chmod(path, mode)

            with patch("scripts.delivery_control_bridge.DEFAULT_OUTPUT", target), \
                 patch("scripts.delivery_control_bridge.os.chmod", side_effect=chmod_with_foreign_owned_directory), \
                 patch("scripts.delivery_control_bridge.os.access", return_value=True):
                publish_snapshot(target, snapshot)

            self.assertTrue(target.is_file())
            self.assertIn('"status":"active"', target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
