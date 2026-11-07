import contextlib
import io
import json
import os
import signal
import unittest
from unittest.mock import Mock, patch

import cutover_runner as r
import orchestrator as o


def call(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = r.main(argv)
    return code, json.loads(out.getvalue())


class RunnerTests(unittest.TestCase):
    def test_exact_candidate_and_fixed_operations_only(self):
        for argv in (["apply", "0" * 40], ["shell", o.CANDIDATE_SHA], ["apply"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                r.main(argv)

    def test_refuses_off_host_before_touching_anything(self):
        with patch.object(r.socket, "gethostname", return_value="not-elite"), patch.object(r, "run") as run:
            code, out = call(["inventory", o.CANDIDATE_SHA])
        self.assertEqual((code, out["reason"]), (2, "ROOT_ELITE_ONLY"))
        run.assert_not_called()

    def test_materialize_requires_completed_storage_receipt_and_never_takes_lock(self):
        for receipt in (None, {"phase": "recovery_required", "candidate_sha": o.CANDIDATE_SHA},
                        {"phase": "aborted_original_restored", "candidate_sha": o.CANDIDATE_SHA}):
            store = Mock(read=Mock(return_value=receipt))
            with patch.object(r.core, "Store", return_value=store), patch.object(r.core, "ReleaseLock") as lock, \
                    patch.object(r.native, "materialize") as materialize:
                with self.assertRaisesRegex(o.Blocked, "MATERIALIZE_REQUIRES_COMPLETED_STORAGE"):
                    r.run("materialize")
            materialize.assert_not_called()
            lock.assert_not_called()
            store.close.assert_called_once()
        store = Mock(read=Mock(return_value={"phase": "storage_complete_materializer_pending",
                                              "candidate_sha": o.CANDIDATE_SHA}))
        with patch.object(r.core, "Store", return_value=store), patch.object(r.core, "ReleaseLock") as lock, \
                patch.object(r.native, "materialize", return_value={"materializer_completed": True}) as materialize:
            result, code = r.run("materialize")
        self.assertEqual(code, 0)
        materialize.assert_called_once_with({"candidate_sha": o.CANDIDATE_SHA, "expected_live": o.LIVE,
                                             "materializer_sha256": o.PINS["materializer"]})
        lock.assert_not_called()

    def test_preflight_never_runs_over_an_existing_transaction(self):
        store = Mock(read=Mock(return_value={"phase": "recovery_required"}))
        adapter = Mock()
        with patch.object(r.core, "ReleaseLock"), patch.object(r.core, "Store", return_value=store), \
                patch.object(r.native, "NativeOps", return_value=adapter):
            with self.assertRaisesRegex(o.Blocked, "EXISTING_TRANSACTION_RECOVER_ONLY"):
                r.run("preflight")
        adapter.preflight.assert_not_called()

    def test_non_terminal_receipt_is_reported_blocked(self):
        store = Mock(read=Mock(return_value={"phase": "recovery_required"}))
        with patch.object(r.core, "ReleaseLock"), patch.object(r.core, "Store", return_value=store), \
                patch.object(r.native, "NativeOps"), patch.object(r.core, "Transaction"):
            with self.assertRaisesRegex(o.Blocked, "TRANSACTION_TERMINAL_RECEIPT_MISSING"):
                r.run("recover")

    def test_rollback_operation_routes_only_to_paused_rollback(self):
        store = Mock(read=Mock(return_value={"phase": "aborted_original_restored"}))
        tx = Mock()
        with patch.object(r.core, "ReleaseLock"), patch.object(r.core, "Store", return_value=store), \
                patch.object(r.native, "NativeOps"), patch.object(r.core, "Transaction", return_value=tx):
            self.assertEqual(r.run("rollback"), ({"operation": "rollback", "phase": "aborted_original_restored"}, 2))
        tx.rollback_paused.assert_called_once_with()
        tx.apply.assert_not_called()
        tx.recover.assert_not_called()

    def test_signal_becomes_ordinary_failure_once_then_is_ignored(self):
        saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        try:
            r.install_signal_guard()
            with self.assertRaisesRegex(o.Blocked, "TERMINATED_BY_SIGNAL"):
                os.kill(os.getpid(), signal.SIGTERM)
                signal.sigtimedwait([], 0) if hasattr(signal, "sigtimedwait") else None
            for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                self.assertIs(signal.getsignal(s), signal.SIG_IGN)
            os.kill(os.getpid(), signal.SIGHUP)  # ignored: recovery must not be cut short
        finally:
            for s, handler in saved.items():
                signal.signal(s, handler)
        self.assertIsInstance(Exception(), Exception)
        self.assertTrue(issubclass(o.Blocked, Exception))  # caught by Transaction's except Exception


if __name__ == "__main__":
    unittest.main()
