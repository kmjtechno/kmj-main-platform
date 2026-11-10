import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import orchestrator as m
import readonly_plan as r


class MemoryStore:
    def __init__(self):
        self.value = None
        self.history = []

    def read(self):
        return copy.deepcopy(self.value)

    def write(self, state):
        self.value = copy.deepcopy(state)
        self.history.append(copy.deepcopy(state))


class Lock:
    def __init__(self):
        self.open = True

    def verify(self):
        if not self.open:
            raise m.Blocked("LOCK_CLOSED")

    def close(self):
        self.open = False


class Fake:
    """Protocol model only. No production command or kernel fixture executes."""
    def __init__(self, store, lock):
        self.store, self.lock = store, lock
        self.events = []
        self.fail = None
        self.outcome = "verified_original"
        self.guard = False

    def call(self, name):
        self.events.append(name)
        if name == self.fail:
            raise m.Blocked(name)

    def preflight(self):
        self.call("preflight")
        return dict.fromkeys(m.PREFLIGHT, True), dict.fromkeys(m.UNITS, "active")

    def guard_identity(self):
        return {"table": "kmj_fixture_test", "namespace": [1, 2]}

    def recovery_evidence(self):
        return {"fixture_only": True, "maintenance_existed": False}

    def install_guard(self):
        assert self.store.value["phase"] == "intent_guard"
        self.guard = True
        self.call("install_guard")

    def pause_timer(self): self.call("pause_timer")
    def drain_scheduler(self): self.call("drain_scheduler")
    def maintenance_on(self): self.call("maintenance_on")
    def queue_restart(self): self.call("queue_restart")
    def drain_and_stop_queue(self): self.call("drain_and_stop_queue")
    def drain_fpm(self): self.call("drain_fpm")
    def maintenance_off(self): self.call("maintenance_off")

    def drain_proofs(self):
        self.call("drain_proofs")
        return dict.fromkeys(m.DRAIN, True)

    def fresh_plan(self):
        self.call("fresh_plan")
        assert "maintenance_off" in self.events
        return {"ready": True, "plan_id": "4e95373c30a007b4"}

    def switch(self, plan):
        assert self.store.value["phase"] == "switch_intent"
        assert self.guard
        self.outcome = "uncertain"
        self.call("switch")
        self.outcome = "verified_switched"

    def switched_proofs(self):
        self.call("switched_proofs")
        return dict.fromkeys(m.SWITCHED, True)

    def restore_units(self, original): self.call("restore_units")
    def runtime_restored(self, original):
        self.call("runtime_restored")
        return True

    def remove_owned_guard(self):
        self.call("remove_owned_guard")
        assert "runtime_restored" in self.events
        self.guard = False

    def guard_absent(self): return not self.guard
    def bind_recovery(self, state): return True
    def reconcile_storage_readonly(self): return self.outcome
    def abort_admission_safe(self):
        self.call("abort_admission_safe")
        return self.guard
    def original_storage_writable_and_unchanged(self): return True
    def restore_owned_maintenance(self, state): self.call("restore_owned_maintenance")

    def writers_still_paused(self):
        self.call("writers_still_paused")
        return self.guard

    def rollback_storage(self):
        assert self.store.value["phase"] == "intent_rollback" and self.store.value["rollback_intent"] is True
        self.outcome = "uncertain"
        self.call("rollback_storage")
        self.outcome = "verified_original"


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.store, self.lock = MemoryStore(), Lock()
        self.ops = Fake(self.store, self.lock)
        self.tx = m.Transaction(self.store, self.ops, self.lock)

    def test_success_order_and_unlock_before_materializer(self):
        request = self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "storage_complete_materializer_pending")
        self.assertFalse(self.lock.open)
        self.assertEqual(request["candidate_sha"], m.CANDIDATE_SHA)
        self.assertEqual(request["materializer_sha256"], m.PINS["materializer"])
        order = self.ops.events
        for first, second in (("install_guard", "pause_timer"), ("maintenance_on", "queue_restart"),
                              ("drain_and_stop_queue", "drain_fpm"), ("maintenance_off", "fresh_plan"),
                              ("switch", "restore_units"), ("runtime_restored", "remove_owned_guard")):
            self.assertLess(order.index(first), order.index(second))

    def test_no_candidate_prefix_authorization(self):
        with self.assertRaises(m.Blocked): self.tx.apply("bad09" + "0" * 35)
        self.assertEqual(self.ops.events, [])

    def test_existing_transaction_requires_recovery(self):
        self.store.value = {"phase": "intent_guard"}
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.ops.events, [])

    def test_completed_abort_recovery_never_restores_units_again(self):
        self.ops.fail = "pause_timer"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.events.clear()
        self.tx.recover()
        self.assertEqual(self.ops.events, [])
        self.assertFalse(self.lock.open)

    def test_completed_abort_requires_original_storage_and_absent_guard(self):
        self.ops.fail = "pause_timer"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.guard = True
        self.ops.events.clear()
        with self.assertRaises(m.Blocked):
            self.tx.recover()
        self.assertEqual(self.ops.events, [])

    def test_every_pre_switch_fault_restores_only_verified_original(self):
        for name in ("install_guard", "pause_timer", "drain_scheduler", "maintenance_on", "queue_restart",
                     "drain_and_stop_queue", "drain_fpm", "maintenance_off", "fresh_plan"):
            with self.subTest(name=name):
                self.setUp()
                self.ops.fail = name
                with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
                self.assertEqual(self.store.value["phase"], "aborted_original_restored")
                self.assertFalse(self.ops.guard)
                self.assertNotIn("switch", self.ops.events)

    def test_lost_guard_while_aborting_original_never_restores_live_units(self):
        # The storage inode remained physical and safe, but an external actor
        # removed the admission guard while a pre-switch step failed.
        # Neither maintenance nor queue/FPM may be restarted automatically.
        original_call = self.ops.call
        def lose_guard_at_failure(name):
            if name == "pause_timer":
                self.ops.guard = False
            return original_call(name)
        self.ops.call = lose_guard_at_failure
        self.ops.fail = "pause_timer"
        with self.assertRaisesRegex(m.Blocked, "ABORT_GUARD_NOT_ATTESTED"):
            self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "recovery_required")
        self.assertNotIn("restore_owned_maintenance", self.ops.events)
        self.assertNotIn("restore_units", self.ops.events)
        self.assertNotIn("remove_owned_guard", self.ops.events)

    def test_guard_missing_before_install_never_returns_abort_success(self):
        self.ops.install_guard = lambda: (_ for _ in ()).throw(
            m.Blocked("GUARD_NOT_INSTALLED"))
        with self.assertRaisesRegex(m.Blocked, "ABORT_GUARD_NOT_ATTESTED"):
            self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "recovery_required")
        self.assertFalse(self.ops.guard)
        self.assertNotIn("restore_units", self.ops.events)

    def test_verified_guard_allows_safe_pre_switch_abort_in_correct_order(self):
        self.ops.fail = "pause_timer"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "aborted_original_restored")
        events = self.ops.events
        self.assertLess(events.index("abort_admission_safe"),
                        events.index("restore_owned_maintenance"))
        self.assertLess(events.index("abort_admission_safe"),
                        events.index("restore_units"))
        self.assertLess(events.index("runtime_restored"),
                        events.index("remove_owned_guard"))

    def test_switch_exception_never_removes_guard_or_resumes(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "recovery_required")
        self.assertTrue(self.store.value["switch_uncertain"])
        self.assertTrue(self.ops.guard)
        self.assertNotIn("restore_units", self.ops.events)

    def test_postswitch_verification_failure_retains_guard(self):
        self.ops.fail = "switched_proofs"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertTrue(self.ops.guard)
        self.assertNotIn("restore_units", self.ops.events)

    def test_resume_failure_never_reopens_admission(self):
        self.ops.fail = "restore_units"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertTrue(self.ops.guard)
        self.assertTrue(self.store.value["switch_verified"])

    def test_success_rechecks_guard_after_actual_v6_receipt_before_restart(self):
        self.tx.apply(m.CANDIDATE_SHA)
        events = self.ops.events
        self.assertLess(events.index("switch"), events.index("writers_still_paused"))
        self.assertLess(events.index("writers_still_paused"), events.index("restore_units"))
        self.assertLess(events.index("writers_still_paused"), events.index("remove_owned_guard"))

    def test_lost_guard_after_verified_switch_never_restores_units(self):
        # A stale successful scanner receipt can outlive an nft table flushed
        # by a foreign process. Source-only recovery MUST NOT turn a receipt
        # into authorization to start live queue/FPM before new admission proof.
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.outcome = "verified_switched"
        self.ops.guard = False
        self.ops.events.clear()
        with self.assertRaisesRegex(m.Blocked, "PRE_RESUME_WRITER_GUARD_OR_DRAIN_NOT_ATTESTED"):
            self.tx.recover()
        self.assertEqual(self.store.value["phase"], "recovery_required")
        self.assertNotIn("restore_units", self.ops.events)
        self.assertNotIn("remove_owned_guard", self.ops.events)
        self.assertIn("writers_still_paused", self.ops.events)
        self.assertTrue(self.lock.open)

    def test_guard_present_but_reappearing_writer_denies_resume(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.outcome = "verified_switched"
        self.ops.guard = True
        self.ops.writers_still_paused = lambda: False
        self.ops.events.clear()
        with self.assertRaisesRegex(m.Blocked, "PRE_RESUME_WRITER_GUARD_OR_DRAIN_NOT_ATTESTED"):
            self.tx.recover()
        self.assertNotIn("restore_units", self.ops.events)
        self.assertNotIn("remove_owned_guard", self.ops.events)
        self.assertTrue(self.ops.guard)

    def test_lock_must_be_held_before_resume_writer_proof(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked):
            self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.outcome = "verified_switched"
        self.lock.open = False
        self.ops.events.clear()
        with self.assertRaisesRegex(m.Blocked, "LOCK_CLOSED"):
            self.tx.recover()
        self.assertNotIn("restore_units", self.ops.events)
        self.assertNotIn("remove_owned_guard", self.ops.events)

    def test_missing_fresh_drain_proof_blocks_switch(self):
        self.ops.drain_proofs = lambda: dict.fromkeys(m.DRAIN[:-1], True)
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertNotIn("switch", self.ops.events)

    def test_torn_switch_recovery_retains_guard(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        with self.assertRaises(m.Blocked): self.tx.recover()
        self.assertTrue(self.ops.guard)

    def test_recovery_inspects_actual_switched_state_not_phase(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        self.ops.outcome = "verified_switched"
        self.tx.recover()
        self.assertEqual(self.store.value["phase"], "storage_complete_materializer_pending")
        self.assertFalse(self.ops.guard)

    def test_proof_values_must_be_exact_booleans(self):
        for value in (1, "true", None):
            with self.subTest(value=value), self.assertRaises(m.Blocked):
                m.proofs({"a": value}, ("a",))

    def test_v6_actual_plan_identifier_shape(self):
        for value, accepted in (("4e95373c30a007b4", True), ("c651c450b3941f3a", True),
                                ("a" * 64, False), ("a" * 15, False)):
            with self.subTest(value=value):
                self.setUp()
                self.ops.fresh_plan = lambda: {"ready": True, "plan_id": value}
                if accepted:
                    self.tx.apply(m.CANDIDATE_SHA)
                else:
                    with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
                    self.assertNotIn("switch", self.ops.events)

    def test_invalid_recovery_state_never_reaches_adapter(self):
        self.ops.fail = "switch"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.ops.fail = None
        for key, value in (("candidate_sha", "f" * 40), ("original_units", {}), ("plan_id", "a" * 64),
                           ("switch_uncertain", 1)):
            with self.subTest(key=key):
                old = copy.deepcopy(self.store.value)
                self.store.value[key] = value
                with patch.object(self.ops, "bind_recovery") as bind, self.assertRaises(m.Blocked):
                    self.tx.recover()
                bind.assert_not_called()
                self.store.value = old

    def test_completed_recovery_does_not_restart_units_again(self):
        self.tx.apply(m.CANDIDATE_SHA)
        self.lock = Lock()
        self.tx = m.Transaction(self.store, self.ops, self.lock)
        self.ops.events.clear()
        result = self.tx.recover()
        self.assertEqual(result["candidate_sha"], m.CANDIDATE_SHA)
        self.assertNotIn("restore_units", self.ops.events)
        self.assertNotIn("remove_owned_guard", self.ops.events)

    def test_cli_no_mutation_entrypoint(self):
        with contextlib.redirect_stdout(io.StringIO()) as output, patch.object(os, "open") as op:
            self.assertEqual(m.main(["--apply"]), 2)
        op.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())["mutated"])



class RollbackTests(unittest.TestCase):
    """Explicit rollback from a paused, verified switch whose runtime restore failed."""

    def setUp(self):
        self.store, self.lock = MemoryStore(), Lock()
        self.ops = Fake(self.store, self.lock)
        self.tx = m.Transaction(self.store, self.ops, self.lock)
        self.ops.fail = "runtime_restored"
        with self.assertRaises(m.Blocked): self.tx.apply(m.CANDIDATE_SHA)
        self.assertEqual(self.store.value["phase"], "recovery_required")
        self.assertTrue(self.store.value["switch_verified"] and self.ops.guard)
        self.ops.fail = None
        self.ops.events.clear()
        self.lock.open = True

    def fresh(self):
        return m.Transaction(self.store, self.ops, Lock())

    def test_rollback_restores_original_then_runtime_then_admission(self):
        tx = self.fresh()
        tx.rollback_paused()
        self.assertEqual(self.ops.events, ["writers_still_paused", "rollback_storage", "abort_admission_safe",
                                           "restore_owned_maintenance", "restore_units",
                                           "runtime_restored", "remove_owned_guard"])
        self.assertEqual(self.store.value["phase"], "aborted_original_restored")
        self.assertFalse(tx.lock.open and self.ops.guard)
        phases = [h["phase"] for h in self.store.history]
        self.assertLess(phases.index("intent_rollback"), phases.index("done_rollback"))

    def test_rollback_refused_unless_paused_verified_switch(self):
        for phase, extra in (("storage_complete_materializer_pending", {}), ("switch_intent", {}),
                             ("recovery_required", {"switch_verified": False}), ("aborted_original_restored", {})):
            with self.subTest(phase=phase):
                value = copy.deepcopy(self.store.value)
                value.update(extra, phase=phase)
                self.store.value = value
                self.ops.events.clear()
                with self.assertRaisesRegex(m.Blocked, "ROLLBACK_ONLY_FROM_PAUSED_VERIFIED_SWITCH"):
                    self.fresh().rollback_paused()
                self.assertEqual(self.ops.events, [])

    def test_rollback_refused_when_admission_or_writers_not_owned(self):
        self.ops.guard = False
        with self.assertRaisesRegex(m.Blocked, "ROLLBACK_WRITERS_NOT_PAUSED"):
            self.fresh().rollback_paused()
        self.assertNotIn("rollback_storage", self.ops.events)

    def test_rollback_refused_unless_actual_storage_is_switched(self):
        self.ops.outcome = "uncertain"
        with self.assertRaisesRegex(m.Blocked, "ROLLBACK_REQUIRES_VERIFIED_SWITCH"):
            self.fresh().rollback_paused()
        self.assertNotIn("rollback_storage", self.ops.events)

    def test_failed_rollback_keeps_guard_and_recover_resumes_actual_state(self):
        self.ops.fail = "rollback_storage"
        with self.assertRaises(m.Blocked): self.fresh().rollback_paused()
        self.assertTrue(self.ops.guard)
        self.assertEqual(self.store.value["phase"], "intent_rollback")
        self.ops.fail = None
        self.ops.outcome = "verified_switched"  # v6 refused (data changed): storage still shared
        result = self.fresh().recover(allow_scanner_recovery=True)
        self.assertEqual(self.store.value["phase"], "storage_complete_materializer_pending")
        self.assertEqual(result["candidate_sha"], m.CANDIDATE_SHA)
        self.assertFalse(self.ops.guard)

    def test_interrupted_rollback_that_reached_original_is_finished_by_recover(self):
        self.ops.fail = "rollback_storage"
        with self.assertRaises(m.Blocked): self.fresh().rollback_paused()
        self.ops.fail = None
        self.ops.outcome = "verified_original"
        self.assertIsNone(self.fresh().recover(allow_scanner_recovery=True))
        self.assertEqual(self.store.value["phase"], "aborted_original_restored")
        self.assertFalse(self.ops.guard)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        # Pure fixture bypasses production ancestor policy, not production API.
        self.guard = patch.object(m, "protected_dir", lambda p, owner=0, **kwargs: os.dup(self.fd))
        self.guard.start()
        self.store = m.Store(self.root, os.geteuid())

    def tearDown(self):
        self.store.close()
        self.guard.stop()
        os.close(self.fd)
        self.temp.cleanup()

    def test_durable_roundtrip(self):
        self.assertIsNone(self.store.read())
        self.store.write({"phase": "switch_intent"})
        self.assertEqual(self.store.read(), {"phase": "switch_intent"})
        self.assertEqual((self.root / "transaction.json").stat().st_mode & 0o777, 0o600)

    def test_torn_or_malformed_state_rejected(self):
        for raw in (b'{"phase":"x"}', b'{"a":1,"a":2}\n', b'{}\n{}\n', b'{"a": 1}\n'):
            with self.subTest(raw=raw):
                p = self.root / "transaction.json"
                p.write_bytes(raw)
                p.chmod(0o600)
                with self.assertRaises((m.Blocked, ValueError)): self.store.read()

    def test_symlink_never_followed(self):
        victim = self.root / "victim"
        victim.write_text("preserve")
        (self.root / "transaction.json").symlink_to(victim)
        with self.assertRaises((OSError, m.Blocked)): self.store.read()
        self.assertEqual(victim.read_text(), "preserve")

    def test_hardlink_rejected(self):
        victim = self.root / "victim"
        victim.write_text('{}\n')
        victim.chmod(0o600)
        os.link(victim, self.root / "transaction.json")
        with self.assertRaises(m.Blocked): self.store.read()

    def test_short_writes_are_completed(self):
        real = os.write
        with patch.object(os, "write", lambda fd, raw: real(fd, raw[:1])):
            self.store.write({"phase": "prepared"})
        self.assertEqual(self.store.read()["phase"], "prepared")

    def test_zero_write_cannot_publish(self):
        with patch.object(os, "write", return_value=0), self.assertRaises(m.Blocked):
            self.store.write({"phase": "prepared"})
        with self.assertRaisesRegex(m.Blocked, "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT"):
            self.store.read()
        self.assertTrue(any(p.name.startswith("pending-") for p in self.root.iterdir()))

    def test_fsync_failure_does_not_publish(self):
        with patch.object(os, "fsync", side_effect=OSError("simulated")), self.assertRaises(OSError):
            self.store.write({"phase": "prepared"})
        with self.assertRaisesRegex(m.Blocked, "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT"):
            self.store.read()
        self.assertTrue(any(p.name.startswith("pending-") for p in self.root.iterdir()))

    def test_old_complete_state_plus_crash_pending_must_not_replay(self):
        first = {"phase": "switch_verified"}
        self.store.write(first)
        pending = self.root / ("pending-" + "a" * 32)
        pending.write_bytes(b'{"phase":"recovery_required"')
        pending.chmod(0o600)
        with self.assertRaisesRegex(m.Blocked, "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT"):
            self.store.read()
        with self.assertRaisesRegex(m.Blocked, "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT"):
            self.store.write({"phase": "storage_complete_materializer_pending"})
        self.assertEqual(pending.read_bytes(), b'{"phase":"recovery_required"')
        self.assertEqual((self.root / "transaction.json").read_bytes(),
                         m.canonical_json(first))

    def test_foreign_file_never_silently_overwritten_or_deleted(self):
        self.store.write({"phase": "prepared"})
        outsider = self.root / "owner-incident.txt"
        outsider.write_bytes(b"incident-must-survive")
        with self.assertRaisesRegex(m.Blocked, "UNFINISHED_OR_UNKNOWN_JOURNAL_ARTIFACT"):
            self.store.read()
        with self.assertRaises(m.Blocked):
            self.store.write({"phase": "switch_intent"})
        self.assertEqual(outsider.read_bytes(), b"incident-must-survive")
        self.assertEqual(self.store._entries.__name__, "_entries")

    def test_exact_current_nonce_environment_sidecars_are_allowed(self):
        nonce = "1234567890abcdef1234567890abcdef"
        state = {"phase": "intent_guard", "recovery_evidence": {"nonce": nonce}}
        self.store.write(state)
        for sidecar in (
            "queue-environment-" + nonce + ".json",
            "queue-environment-" + nonce + "-replacement.json",
        ):
            artifact = self.root / sidecar
            artifact.write_bytes(b"fixture-only")
            artifact.chmod(0o600)
        self.assertEqual(self.store.read(), state)
        self.store.write({"phase": "done_guard", "recovery_evidence": {"nonce": nonce}})
        self.assertEqual(self.store.read()["phase"], "done_guard")

    def test_unbound_environment_sidecar_rejected(self):
        nonce = "1234567890abcdef1234567890abcdef"
        foreign = "ffffffffffffffffffffffffffffffff"
        self.store.write({"phase": "prepared", "recovery_evidence": {"nonce": nonce}})
        artifact = self.root / ("queue-environment-" + foreign + ".json")
        artifact.write_bytes(b"do-not-remove")
        with self.assertRaisesRegex(m.Blocked, "FOREIGN_QUEUE_ENVIRONMENT_ARTIFACT"):
            self.store.read()
        self.assertEqual(artifact.read_bytes(), b"do-not-remove")

    def test_environment_without_transaction_never_allows_new_apply(self):
        nonce = "1234567890abcdef1234567890abcdef"
        orphan = self.root / ("queue-environment-" + nonce + ".json")
        orphan.write_bytes(b"orphan-private-context")
        with self.assertRaisesRegex(m.Blocked, "ORPHANED_ENVIRONMENT_WITHOUT_TRANSACTION"):
            self.store.read()
        with self.assertRaises(m.Blocked):
            self.store.write({"phase": "prepared"})
        self.assertEqual(orphan.read_bytes(), b"orphan-private-context")

    def test_replaced_journal_inode_after_open_is_rejected(self):
        from types import SimpleNamespace
        self.store.write({"phase": "prepared"})
        original_stat = os.stat
        def stale_name(name, *args, **kwargs):
            value = original_stat(name, *args, **kwargs)
            if name != "transaction.json":
                return value
            return SimpleNamespace(
                st_dev=value.st_dev, st_ino=value.st_ino + 1,
                st_mode=value.st_mode, st_uid=value.st_uid,
                st_nlink=value.st_nlink, st_size=value.st_size,
            )
        with patch.object(os, "stat", side_effect=stale_name):
            with self.assertRaisesRegex(m.Blocked, "STATE_FILE_REPLACED_DURING_READ"):
                self.store.read()

    def test_lock_close_is_idempotent(self):
        lockfile = self.root / "release.lock"
        lockfile.touch(mode=0o600)
        lock = m.ReleaseLock(lockfile, os.geteuid())
        lock.verify()
        lock.close()
        lock.close()

    def test_lock_inode_replacement_detected(self):
        lockfile = self.root / "release.lock"
        lockfile.touch(mode=0o600)
        lock = m.ReleaseLock(lockfile, os.geteuid())
        replacement = self.root / "replacement"
        replacement.touch(mode=0o600)
        os.replace(replacement, lockfile)
        try:
            with self.assertRaises(m.Blocked): lock.verify()
        finally:
            lock.close()

    def test_sticky_exception_requested_only_by_lock(self):
        lockfile = self.root / "release.lock"
        lockfile.touch(mode=0o600)
        with patch.object(m, "protected_dir", return_value=os.dup(self.fd)) as directory:
            lock = m.ReleaseLock(lockfile, os.geteuid())
        try:
            self.assertEqual(directory.call_args.kwargs, {"allow_sticky": True})
        finally:
            lock.close()


class RulesetTests(unittest.TestCase):
    def doc(self, *chains):
        return {"nftables": [{"chain": chain} for chain in chains]}

    def test_after_all_ipv4_output_base_priorities(self):
        self.assertEqual(r.output_priority(self.doc(
            {"family": "inet", "hook": "output", "prio": -300},
            {"family": "ip", "hook": "output", "prio": 500},
            {"family": "inet", "hook": "input", "prio": 900})), 501)

    def test_empty_starts_at_zero(self):
        self.assertEqual(r.output_priority(self.doc()), 0)

    def test_unknown_or_exhausted_priorities_fail(self):
        for priority in (True, "filter", None, 2**31 - 1, -(2**31) - 1):
            with self.subTest(priority=priority), self.assertRaises(m.Blocked):
                r.output_priority(self.doc({"family": "inet", "hook": "output", "prio": priority}))

    def test_unknown_hooked_family_fails(self):
        for family in ("unknown", "bridge", "netdev"):
            with self.subTest(family=family), self.assertRaises(m.Blocked):
                r.output_priority(self.doc({"family": family, "hook": "output", "prio": 0}))

    def test_readonly_commands_have_no_shell_and_timeout(self):
        with patch.object(r, "protected_bytes"), patch.object(r.subprocess, "run") as run:
            run.return_value.stdout = b"{}"
            self.assertEqual(r.read_command(["/usr/sbin/nft", "-j", "list", "ruleset"]), b"{}")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/usr/sbin/nft", "-j", "list", "ruleset"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 20)


if __name__ == "__main__":
    unittest.main()
