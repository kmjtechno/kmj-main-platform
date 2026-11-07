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
    def original_storage_writable_and_unchanged(self): return True
    def restore_owned_maintenance(self, state): self.call("restore_owned_maintenance")


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
        with self.assertRaises(m.Blocked): self.tx.apply("cd958" + "0" * 35)
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
        with self.assertRaises(OSError): self.store.read()
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
        self.assertIsNone(self.store.read())

    def test_fsync_failure_does_not_publish(self):
        with patch.object(os, "fsync", side_effect=OSError("simulated")), self.assertRaises(OSError):
            self.store.write({"phase": "prepared"})
        self.assertIsNone(self.store.read())

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
