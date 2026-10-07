"""Queue regression tests use real SQLite databases and independent connections."""
import concurrent.futures
import importlib.util
from pathlib import Path
import tempfile
import unittest

try:
    from controller.task_queue import TaskQueue, LeaseLost
except ModuleNotFoundError:
    TaskQueue = None
    LeaseLost = RuntimeError


class TaskQueueTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(TaskQueue, "durable queue implementation is missing")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tasks.db"
        self.q = TaskQueue(self.path)

    def test_idempotence_survives_reopen_and_rejects_changed_payload(self):
        self.q.enqueue("a", "repo", {"prompt": "one"})
        reopened = TaskQueue(self.path)
        reopened.enqueue("a", "repo", {"prompt": "one"})
        with self.assertRaises(ValueError):
            reopened.enqueue("a", "repo", {"prompt": "two"})
        self.assertEqual(reopened.claim("w", now=10)["payload"], {"prompt": "one"})
        self.assertIsNone(reopened.claim("w2", now=10))

    def test_project_exclusion_and_global_two_worker_limit(self):
        for key, project in [("a", "p"), ("b", "p"), ("c", "q"), ("d", "r")]:
            self.q.enqueue(key, project, {})
        first = self.q.claim("w1", now=10)
        second = self.q.claim("w2", now=10)
        self.assertEqual([first["id"], second["id"]], ["a", "c"])
        self.assertIsNone(self.q.claim("w3", now=10))
        self.q.complete("a", first["token"], {"ok": True}, now=11)
        self.assertEqual(self.q.claim("w3", now=11)["id"], "b")

    def test_expired_claim_is_recovered_and_old_token_fenced(self):
        self.q.enqueue("a", "p", {})
        first = self.q.claim("w1", lease_seconds=10, now=10)
        self.q.checkpoint("a", first["token"], {"stage": "patch"}, now=11)
        second = TaskQueue(self.path).claim("w2", now=20)
        self.assertNotEqual(first["token"], second["token"])
        self.assertEqual(second["checkpoint"], {"stage": "patch"})
        for operation in [
            lambda: self.q.complete("a", first["token"], {}, now=21),
            lambda: self.q.checkpoint("a", first["token"], {}, now=21),
            lambda: self.q.heartbeat("a", first["token"], now=21),
            lambda: self.q.fail("a", first["token"], "bad", now=21),
        ]:
            with self.assertRaises(LeaseLost):
                operation()
        self.q.complete("a", second["token"], {"artifact": "x"}, now=21)
        self.assertEqual(TaskQueue(self.path).get("a")["result"], {"artifact": "x"})

    def test_heartbeat_extends_lease_but_cannot_revive_expired_owner(self):
        self.q.enqueue("a", "p", {})
        task = self.q.claim("w", lease_seconds=10, now=10)
        self.q.heartbeat("a", task["token"], lease_seconds=10, now=19)
        self.assertIsNone(self.q.claim("w2", now=20))
        with self.assertRaises(LeaseLost):
            self.q.heartbeat("a", task["token"], now=29)

    def test_not_before_failure_backoff_and_bounded_attempts(self):
        self.q.enqueue("a", "p", {}, max_attempts=2, not_before=10)
        self.assertIsNone(self.q.claim("w", now=9))
        first = self.q.claim("w", now=10)
        self.q.fail("a", first["token"], "unavailable", retry_delay=20, now=11)
        self.assertIsNone(self.q.claim("w", now=30))
        second = self.q.claim("w", lease_seconds=1, now=31)
        self.assertEqual(second["attempts"], 2)
        self.assertIsNone(self.q.claim("w", now=32))
        self.assertEqual(self.q.get("a")["state"], "failed")

    def test_simultaneous_claims_cannot_double_claim_or_exceed_capacity(self):
        for key in range(12):
            self.q.enqueue(str(key), "p" + str(key % 3), {})
        def claim(index):
            return TaskQueue(self.path).claim(str(index), now=10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            claimed = [x for x in pool.map(claim, range(8)) if x]
        self.assertEqual(len(claimed), 2)
        self.assertEqual(len({x["id"] for x in claimed}), 2)
        self.assertEqual(len({x["project"] for x in claimed}), 2)

    def test_clock_is_sampled_after_transaction_lock_for_all_lease_operations(self):
        # A lock wait crosses expiry; using the pre-lock time admits a stale owner.
        from contextlib import contextmanager
        from unittest.mock import patch
        from controller import task_queue
        original_tx = self.q._tx
        clock = [19]
        @contextmanager
        def delayed_tx():
            with original_tx() as db:
                clock[0] = 21
                yield db
        for operation in ("heartbeat", "checkpoint", "complete", "fail"):
            with self.subTest(operation=operation):
                self.q = TaskQueue(Path(self.tmp.name) / (operation + ".db"))
                original_tx = self.q._tx
                task_id = "expiry-" + operation
                self.q.enqueue(task_id, task_id, {})
                task = self.q.claim("worker", lease_seconds=10, now=10)
                clock[0] = 19
                args = {
                    "heartbeat": (), "checkpoint": ({},),
                    "complete": ({},), "fail": ("failure",),
                }[operation]
                with patch.object(self.q, "_tx", delayed_tx):
                    with patch.object(task_queue.time, "time", side_effect=lambda: clock[0]):
                        with self.assertRaises(LeaseLost):
                            getattr(self.q, operation)(task_id, task["token"], *args)

    def test_claim_uses_post_lock_clock_for_recovery_and_new_lease(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from controller import task_queue
        self.q.enqueue("a", "p", {})
        first = self.q.claim("first", lease_seconds=10, now=10)
        original_tx = self.q._tx
        clock = [19]
        @contextmanager
        def delayed_tx():
            with original_tx() as db:
                clock[0] = 21
                yield db
        with patch.object(self.q, "_tx", delayed_tx):
            with patch.object(task_queue.time, "time", side_effect=lambda: clock[0]):
                second = self.q.claim("second", lease_seconds=10)
        self.assertIsNotNone(second)
        self.assertNotEqual(first["token"], second["token"])
        self.assertEqual(second["lease_until"], 31)

    def test_provider_deferral_preserves_attempt_budget_and_obeys_backoff(self):
        self.assertTrue(hasattr(self.q, "defer"), "provider deferral is missing")
        self.q.enqueue("a", "p", {}, max_attempts=1)
        task = self.q.claim("w", now=10)
        deferred = self.q.defer("a", task["token"], "NO_FREE_ROUTE", retry_delay=300, now=11)
        self.assertEqual(deferred["state"], "queued")
        self.assertEqual(deferred["attempts"], 0)
        self.assertIsNone(deferred["token"])
        self.assertIsNone(TaskQueue(self.path).claim("w2", now=310))
        second = TaskQueue(self.path).claim("w2", now=311)
        self.assertEqual(second["attempts"], 1)
        with self.assertRaises(LeaseLost):
            self.q.defer("a", task["token"], "NO_FREE_ROUTE", now=312)
        self.q.complete("a", second["token"], {"ok": True}, now=312)

    def test_expired_claim_cannot_defer_or_restore_budget(self):
        self.assertTrue(hasattr(self.q, "defer"), "provider deferral is missing")
        self.q.enqueue("a", "p", {}, max_attempts=1)
        task = self.q.claim("w", lease_seconds=1, now=10)
        with self.assertRaises(LeaseLost):
            self.q.defer("a", task["token"], "NO_FREE_ROUTE", now=11)
        self.assertEqual(self.q.get("a")["attempts"], 1)

    def test_invalid_parameters_do_not_admit_unbounded_work(self):
        for value in (0, 3, True):
            with self.assertRaises(ValueError):
                TaskQueue(self.path, max_concurrency=value)
        for value in (0, 11, True):
            with self.assertRaises(ValueError):
                self.q.enqueue("a", "p", {}, max_attempts=value)
        with self.assertRaises(ValueError):
            self.q.enqueue("a", "", {})
        self.q.enqueue("a", "p", {})
        with self.assertRaises(ValueError):
            self.q.claim("w", lease_seconds=0, now=10)


if __name__ == "__main__":
    unittest.main()
