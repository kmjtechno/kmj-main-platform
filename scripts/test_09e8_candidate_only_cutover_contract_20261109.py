#!/usr/bin/env python3
"""Fake-adapter fail-closed tests for the 09e8 candidate-only cutover contract."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = (Path(__file__).resolve().parent / "operations" /
          "09e8-candidate-only-cutover-review/transaction_contract.py")
spec = importlib.util.spec_from_file_location("kmj_candidate_only_contract", SOURCE)
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)


class Store:
    def __init__(self, record=None):
        self.record = record
        self.history = []

    def read(self):
        return self.record

    def write_durable(self, record):
        self.record = record
        self.history.append(record.phase)


class Adapter:
    def __init__(self, stop=None, admission=None, post=None, planned=None):
        self.calls = []
        self.stop = stop
        self.admission = admission if admission is not None else dict.fromkeys(model.ADMISSION, True)
        self.post = post if post is not None else dict.fromkeys(model.SWITCH, True)
        self.planned = planned if planned is not None else {
            "ready": True, "plan_id": "c651c450b3941f3a",
            "target": model.CANDIDATE_APP, "mutated": False,
            "persistent_conflicts": [], "to_copy": 0
        }
        self.guard = False
        self.resumed = False

    def call(self, name):
        self.calls.append(name)
        if self.stop == name:
            raise model.Refused("INJECTED_" + name)

    def preflight_exact(self):
        self.call("preflight")
        return dict.fromkeys(model.PREFLIGHT, True)

    def install_admission_guard(self):
        self.call("guard")
        self.guard = True

    def attest_admission_and_drain(self):
        self.call("drain")
        return self.admission

    def fresh_candidate_v6_plan(self):
        self.call("plan")
        return self.planned

    def v6_switch_candidate_storage(self, plan_id):
        self.call("candidate_switch")
        if not self.guard:
            raise AssertionError("guard missing")
        if plan_id != "c651c450b3941f3a":
            raise AssertionError("plan changed")

    def attest_candidate_only_switch(self):
        self.call("verify_switch")
        return self.post

    def resume_original_services(self):
        self.call("resume")
        self.resumed = True

    def attest_services_resumed(self):
        self.call("verify_resume")
        return self.resumed

    def remove_only_owned_guard(self):
        self.call("remove_guard")
        self.guard = False

    def attest_guard_absent(self):
        self.call("guard_absent")
        return not self.guard

    def attest_original_candidate_and_live_unchanged(self):
        self.call("no_switch_proven")
        return self.stop != "original_changed"

    def recover_original_admission_without_switch(self):
        self.call("recover_pre_switch")
        self.resumed = True
        self.guard = False


class CandidateCutoverContractTests(unittest.TestCase):
    def run_model(self, adapter=None, store=None):
        adapter = adapter or Adapter()
        store = store or Store()
        return model.run_review_contract(
            store, adapter, model.SOURCE_CANDIDATE_SHA, model.SOURCE_CURRENT_RELEASE
        )

    def test_exact_candidate_only_baseline(self):
        self.assertEqual(model.SOURCE_CURRENT_RELEASE, "platform-bce4100d005e")
        self.assertEqual(model.SOURCE_CANDIDATE_SHA,
                         "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(model.CANDIDATE_APP,
                         "/home/kmjprod/releases/platform-09e8a224cd37/apps/platform")
        self.assertNotEqual(model.LIVE_APP, model.CANDIDATE_APP)
        self.assertTrue(model.SHARED_STORAGE.startswith("/home/kmjprod/shared"))

    def test_success_order_requires_guard_and_fresh_plan(self):
        adapter, store = Adapter(), Store()
        result = self.run_model(adapter, store)
        self.assertEqual(result.phase, model.COMPLETED_PHASE)
        self.assertTrue(result.switch_intent)
        self.assertTrue(result.switch_verified)
        self.assertEqual(result.plan_id, "c651c450b3941f3a")
        self.assertEqual(adapter.calls, [
            "preflight", "guard", "drain", "plan", "candidate_switch",
            "verify_switch", "resume", "verify_resume",
            "remove_guard", "guard_absent"
        ])
        self.assertLess(store.history.index("candidate_switch_intent"),
                        store.history.index("candidate_switch_verified"))
        self.assertFalse(adapter.guard)
        self.assertFalse(model.release_gate(result))

    def test_exact_sha_or_expected_current_rejection_happens_before_host_touch(self):
        for target, current in (
            ("cd9580701d3cea19d7d4e4c96ebe70c0553fbf37", model.SOURCE_CURRENT_RELEASE),
            (model.SOURCE_CANDIDATE_SHA, "platform-574e443a2c75"),
        ):
            adapter, store = Adapter(), Store()
            with self.subTest(target=target), self.assertRaises(model.Refused):
                model.run_review_contract(store, adapter, target, current)
            self.assertEqual(adapter.calls, [])
            self.assertEqual(store.history, [])

    def test_existing_transaction_refuses_before_preflight(self):
        store, adapter = Store(model.Record(1, "recovery_required",
                                            model.SOURCE_CANDIDATE_SHA,
                                            model.SOURCE_CURRENT_RELEASE)), Adapter()
        with self.assertRaises(model.Refused):
            self.run_model(adapter, store)
        self.assertEqual(adapter.calls, [])

    def test_missing_admission_proof_keeps_guard_and_records_recovery(self):
        admission = dict.fromkeys(model.ADMISSION, True)
        admission["production_fpm_still_quiescent"] = True if "production_fpm_still_quiescent" in admission else True
        admission["queue_cgroup_empty"] = False
        # Extra unknown evidence is also forbidden.
        admission.pop("production_fpm_still_quiescent", None)
        adapter, store = Adapter(admission=admission), Store()
        with self.assertRaisesRegex(model.Refused, "WRITER_DRAIN_NOT_ATTESTED"):
            self.run_model(adapter, store)
        self.assertEqual(store.read().phase, "recovery_required")
        self.assertFalse(store.read().switch_intent)
        self.assertTrue(adapter.guard)
        self.assertNotIn("candidate_switch", adapter.calls)
        self.assertNotIn("resume", adapter.calls)

    def test_missing_preflight_prevents_guard_and_store(self):
        adapter, store = Adapter(), Store()
        adapter.preflight_exact = lambda: {**dict.fromkeys(model.PREFLIGHT, True),
                                            "unreviewed": True}
        with self.assertRaisesRegex(model.Refused, "PREFLIGHT_NOT_ATTESTED"):
            self.run_model(adapter, store)
        self.assertFalse(adapter.guard)
        self.assertEqual(store.history, [])

    def test_wrong_target_plan_blocks_before_switch(self):
        planned = Adapter().planned | {"target": model.LIVE_APP}
        adapter, store = Adapter(planned=planned), Store()
        with self.assertRaisesRegex(model.Refused, "CANDIDATE_FRESH_PLAN_NOT_READY"):
            self.run_model(adapter, store)
        self.assertTrue(adapter.guard)
        self.assertEqual(store.read().phase, "recovery_required")
        self.assertFalse(store.read().switch_intent)
        self.assertNotIn("candidate_switch", adapter.calls)

    def test_failed_switch_never_drops_guard_or_resumes_workers(self):
        adapter, store = Adapter(stop="candidate_switch"), Store()
        with self.assertRaisesRegex(model.Refused, "INJECTED_candidate_switch"):
            self.run_model(adapter, store)
        self.assertEqual(store.read().phase, "recovery_required")
        self.assertTrue(store.read().switch_intent)
        self.assertFalse(store.read().switch_verified)
        self.assertTrue(adapter.guard)
        self.assertNotIn("resume", adapter.calls)
        self.assertNotIn("remove_guard", adapter.calls)
        with self.assertRaisesRegex(model.Refused, "SCANNER_RECOVERY_AND_MANUAL_REVIEW_REQUIRED"):
            model.review_pre_switch_abort(store, adapter)

    def test_false_switch_receipt_keeps_guard_even_after_v6_return(self):
        post = dict.fromkeys(model.SWITCH, True)
        post["live_storage_link_unchanged"] = False
        adapter, store = Adapter(post=post), Store()
        with self.assertRaisesRegex(model.Refused, "CANDIDATE_SWITCH_NOT_ATTESTED"):
            self.run_model(adapter, store)
        self.assertTrue(store.read().switch_intent)
        self.assertTrue(adapter.guard)
        self.assertNotIn("resume", adapter.calls)

    def test_resume_failure_retains_guard_and_recovery(self):
        adapter, store = Adapter(stop="resume"), Store()
        with self.assertRaises(model.Refused):
            self.run_model(adapter, store)
        self.assertEqual(store.read().phase, "recovery_required")
        self.assertTrue(store.read().switch_verified)
        self.assertTrue(adapter.guard)
        self.assertNotIn("remove_guard", adapter.calls)

    def test_pre_switch_abort_only_if_candidate_original_attested(self):
        adapter, store = Adapter(stop="plan"), Store()
        with self.assertRaises(model.Refused):
            self.run_model(adapter, store)
        self.assertFalse(store.read().switch_intent)
        recovered = model.review_pre_switch_abort(store, adapter)
        self.assertEqual(recovered.phase, "aborted_original_preserved")
        self.assertIn("no_switch_proven", adapter.calls)
        self.assertFalse(adapter.guard)
        self.assertTrue(adapter.resumed)
        self.assertFalse(model.release_gate(recovered))

    def test_pre_switch_abort_refuses_if_original_changed(self):
        adapter, store = Adapter(stop="original_changed"), Store(
            model.Record(1, "recovery_required", model.SOURCE_CANDIDATE_SHA,
                         model.SOURCE_CURRENT_RELEASE, switch_intent=False))
        with self.assertRaisesRegex(model.Refused, "CANDIDATE_OR_LIVE_CHANGED"):
            model.review_pre_switch_abort(store, adapter)
        self.assertNotIn("recover_pre_switch", adapter.calls)

    def test_no_host_entrypoint_and_no_protected_approval_writer(self):
        source = SOURCE.read_text("utf-8")
        for forbidden in (
            "subprocess", "os.symlink", "os.rename", "os.unlink", "os.system",
            "os.exec", "systemctl", "nft -", "--apply", "chmod(", "chown(",
            "git reset", "shutil", "prod_approval", "production_activate",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("REVIEW_ONLY_NO_NATIVE_ADAPTER_OR_HOST_ENTRYPOINT", source)


if __name__ == "__main__":
    unittest.main()
