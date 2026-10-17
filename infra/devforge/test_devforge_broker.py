#!/usr/bin/env python3
"""Offline, host-independent unit tests for the root-owned DevForge broker."""
import importlib.util
import pathlib
import subprocess
import threading
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("kmj_devforge_broker", ROOT / "devforge-broker.py")
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class BrokerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertFalse(broker.LOCK.locked())
        broker.RUNTIME.update(last_action=None, last_error=None, completed_at=None)

    def test_rejects_untrusted_action_and_extra_parameters(self):
        self.assertEqual(broker.reply({"action": "shell"})["error"], "ACTION_NOT_ALLOWED")
        self.assertEqual(broker.reply({"action": "install", "path": "/root"})["error"], "INVALID_REQUEST")
        self.assertEqual(broker.reply({"action": ["status"]})["error"], "ACTION_NOT_ALLOWED")
        self.assertEqual(broker.reply("status")["error"], "INVALID_REQUEST")
        self.assertFalse(broker.LOCK.locked())

    def test_one_action_at_a_time(self):
        self.assertTrue(broker.LOCK.acquire(blocking=False))
        try:
            self.assertEqual(broker.reply({"action": "install"})["error"], "OPERATION_IN_PROGRESS")
        finally:
            broker.LOCK.release()

    def test_mutation_is_asynchronous_and_does_not_claim_success(self):
        with mock.patch.object(broker.threading, "Thread") as thread:
            accepted = broker.reply({"action": "install"})
        self.assertEqual(accepted, {"ok": True, "accepted": True, "action": "install"})
        thread.assert_called_once()
        self.assertTrue(broker.LOCK.locked())
        broker.LOCK.release()

    def test_wrong_container_image_can_never_count_as_healthy(self):
        with mock.patch.object(broker, "command") as call, mock.patch.object(broker.urllib.request, "urlopen") as urlopen:
            call.side_effect = [
                subprocess.CompletedProcess(["docker"], 0, stdout="running\n", stderr=""),
                subprocess.CompletedProcess(["docker"], 0, stdout="someone-else:latest\n", stderr=""),
            ]
            state = broker.service_state()
        self.assertEqual(state["state"], "unexpected_container")
        self.assertFalse(state["healthy"])
        urlopen.assert_not_called()

    def test_existing_container_blocks_reinstall(self):
        self.assertTrue(broker.LOCK.acquire(blocking=False))
        with mock.patch.object(broker, "ensure_preconditions"), mock.patch.object(broker, "service_state", return_value={"state": "running"}):
            broker.perform("install")
        self.assertEqual(broker.RUNTIME["last_error"], "ALREADY_INSTALLED_OR_CONTAINER_CONFLICT")
        self.assertFalse(broker.LOCK.locked())

    def test_status_has_no_credential_payload(self):
        with mock.patch.object(broker, "service_state", return_value={
            "broker_ready": True, "healthy": False, "state": "not_installed",
        }):
            state = broker.reply({"action": "status"})
        self.assertTrue(state["ok"])
        self.assertNotIn("password", str(state).lower())
        self.assertNotIn("token", str(state).lower())


if __name__ == "__main__":
    unittest.main()
