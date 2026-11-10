#!/usr/bin/env python3
"""Exact 09e8 candidate-only native adapter source isolation tests.

No CLI, real systemctl, nftables, PHP or storage writes are permitted.
Mocks inspect the binding between separately scoped live runtime and candidate
storage scanner, including protected root materializer source.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import native_ops as n
import native_plan as p
import orchestrator as o


class CandidateNativeTests(unittest.TestCase):
    def test_release_geometry_is_not_old_cd958(self):
        self.assertEqual(o.LIVE, "/home/kmjprod/releases/platform-bce4100d005e")
        self.assertEqual(o.CANDIDATE_SHA, "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(o.CANDIDATE, "/home/kmjprod/releases/platform-09e8a224cd37")
        self.assertEqual(n.APP, Path(o.LIVE) / "apps/platform")
        self.assertEqual(n.TARGET_APP, Path(o.CANDIDATE) / "apps/platform")
        self.assertNotEqual(n.APP, n.TARGET_APP)
        self.assertEqual(n.LIVE_SHA, "bce4100d005e8624509cab989c096d7eaab1ba79")
        self.assertEqual(n.STATE, "/var/lib/kmj-main-platform-09e8-candidate-cutover")
        self.assertEqual(p.MATERIALIZER_SOURCE,
                         "/usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh")
        self.assertEqual(p.EXPECTED_ARGV_HASHES, {
            "queue": "b4fb53ed7753d56393a150900faab65e38a4f2dd5db298e2ba4c23227def8359",
            "scheduler": "6539b4d3319d25bcb4d6f2490f4f827537c06604a21838d3545fe6e82afdbffe",
        })

    def test_scanner_plan_uses_only_candidate_app_never_live(self):
        operations = n.NativeOps.__new__(n.NativeOps)
        lock = Mock()
        lock.fd = 79
        operations.release_lock = lock
        verified_raw = b"scanner-test-fake-source"
        result = types.SimpleNamespace(stdout=b'{"command":"plan","ready":true}',
                                       stderr=b"", returncode=0)
        with patch.object(n.p, "read_file", return_value=verified_raw) as read, \
             patch.object(n.p, "digest", return_value=o.PINS["scanner"]), \
             patch.object(n.subprocess, "run", return_value=result) as run:
            got = operations.scanner_run("plan")
        self.assertEqual(got["command"], "plan")
        args = run.call_args.args[0]
        self.assertEqual(args[args.index("--app-dir") + 1], str(n.TARGET_APP))
        self.assertNotIn(str(n.APP), args)
        self.assertNotIn("--apply", args)
        self.assertEqual(run.call_args.kwargs["pass_fds"][1], 79)
        read.assert_called_once_with(p.DEPENDENCIES["scanner"], protected=True)
        lock.verify.assert_called()

    def test_scanner_no_wrong_id_and_no_unapproved_command(self):
        operations = n.NativeOps.__new__(n.NativeOps)
        with self.assertRaises(o.Blocked):
            operations.scanner_run("arbitrary-command")
        operations.release_lock = Mock(fd=8)
        with patch.object(n.p, "read_file", return_value=b"scanner"), \
             patch.object(n.p, "digest", return_value=o.PINS["scanner"]):
            with self.assertRaises(o.Blocked):
                operations.scanner_run("switch", "not-exact-plan-id")

    @staticmethod
    def candidate_scanner_plan():
        # Exact schema emitted by the SHA-pinned, installed v6 scanner.
        return {
            "command": "plan", "live_files": 3, "shared_files": 26,
            "to_copy": 0, "persistent_conflicts": [],
            "benign_log_divergence": 0,
            "plan_id": "c651c450b3941f3a",
            "persistent_only_plan_id": True,
            "top_dir_meta_live_mode_uid_gid": [448, 1001, 1001],
            "top_dir_meta_shared_mode_uid_gid": [448, 1001, 1001],
            "ready": True, "enforced_freeze_possible_here": True,
            "inventory_only_not_release_readiness": True, "mutated": False,
        }

    def test_fresh_candidate_only_plan_rejects_late_copy_or_conflict(self):
        doc = self.candidate_scanner_plan()
        self.assertEqual(n.candidate_only_v6_plan(doc),
                         {"ready": True, "plan_id": "c651c450b3941f3a"})
        for key, bad in (
            ("to_copy", 1), ("to_copy", True), ("persistent_conflicts", ["private/file"]),
            ("persistent_conflicts", None), ("ready", "True"), ("ready", False),
            ("command", "switch"), ("mutated", True),
            ("inventory_only_not_release_readiness", False),
            ("persistent_only_plan_id", False),
            ("enforced_freeze_possible_here", False),
            ("top_dir_meta_shared_mode_uid_gid", [493, 1001, 1001]),
            ("plan_id", "NOTHEX"), ("plan_id", "0" * 17),
            ("live_files", -1), ("shared_files", "26"),
            ("benign_log_divergence", True),
            ("top_dir_meta_live_mode_uid_gid", [True, 1001, 1001]),
        ):
            changed = dict(doc)
            changed[key] = bad
            with self.subTest(field=key, bad=str(bad)), self.assertRaises(o.Blocked):
                n.candidate_only_v6_plan(changed)
        changed = dict(doc, unreviewed=True)
        with self.assertRaises(o.Blocked):
            n.candidate_only_v6_plan(changed)
        changed = dict(doc)
        del changed["persistent_conflicts"]
        with self.assertRaises(o.Blocked):
            n.candidate_only_v6_plan(changed)

    def test_post_drain_fresh_plan_rechecks_zero_copy_before_switch_intent(self):
        ops = n.NativeOps.__new__(n.NativeOps)
        ops.evidence = {"marker_removed": True}
        ops.drain_proofs = Mock(return_value={})
        copied = self.candidate_scanner_plan()
        copied["to_copy"] = 1
        ops.scanner_run = Mock(return_value=copied)
        with patch.object(n.os.path, "lexists", return_value=False):
            with self.assertRaisesRegex(o.Blocked, "V6_CANDIDATE_PLAN_ZERO_COPY_CONFLICT"):
                ops.fresh_plan()
        ops.scanner_run.assert_called_once_with("plan")
        ops.drain_proofs.assert_called_once()
        ops.scanner_run.reset_mock()
        ops.scanner_run.return_value = self.candidate_scanner_plan()
        with patch.object(n.os.path, "lexists", return_value=False):
            proof = ops.fresh_plan()
        self.assertEqual(proof, {"ready": True, "plan_id": "c651c450b3941f3a"})
        ops.scanner_run.assert_called_once_with("plan")

    def test_candidate_preflight_and_post_drain_share_identical_validator(self):
        source = (Path(__file__).resolve().parent / "native_ops.py").read_text("utf-8")
        self.assertIn('candidate_only_v6_plan(plan)', source)
        self.assertIn('return candidate_only_v6_plan(value)', source)
        self.assertIn('"--app-dir", str(TARGET_APP)', source)
        self.assertNotIn('"--app-dir", str(APP)', source)

    def test_switched_receipt_attests_only_candidate_and_keeps_live_link(self):
        operations = n.NativeOps.__new__(n.NativeOps)
        operations.pointer = Mock()
        operations.store = Mock(read=Mock(return_value={"plan_id": "c651c450b3941f3a"}))
        operations.snapshot_name = Mock(return_value="storage.pre-shared-20261109T100000Z")
        operations.completed_receipt = Mock(return_value=[{"plan":"c651c450b3941f3a"}])
        helper = Mock()
        operations.module = Mock(return_value=helper)
        with tempfile.TemporaryDirectory() as d:
            shared = Path(d) / "shared"
            shared.mkdir()
            live = Path(d) / "live"
            live.mkdir()
            (live / "storage").symlink_to(shared)
            with patch.object(n, "APP", live), patch.object(n, "SHARED", str(shared)):
                proof = operations.switched_proofs()
        self.assertEqual(set(proof), set(o.SWITCHED))
        self.assertTrue(all(value is True for value in proof.values()))
        operations.snapshot_name.assert_called_once_with(n.TARGET_APP)
        operations.completed_receipt.assert_called_once_with(
            n.TARGET_APP, "storage.pre-shared-20261109T100000Z"
        )
        self.assertEqual(helper.attest_snapshot.call_count, 1)
        self.assertEqual(helper.attest_snapshot.call_args.kwargs["release_root"], o.CANDIDATE)

    def test_live_link_changed_blocks_candidate_receipt_before_attestation(self):
        operations = n.NativeOps.__new__(n.NativeOps)
        operations.pointer = Mock()
        operations.store = Mock(read=Mock(return_value={"plan_id": "c651c450b3941f3a"}))
        operations.snapshot_name = Mock(return_value="storage.pre-shared-20261109T100000Z")
        operations.completed_receipt = Mock(return_value=[{"plan":"c651c450b3941f3a"}])
        helper = Mock()
        operations.module = Mock(return_value=helper)
        with tempfile.TemporaryDirectory() as d:
            live, shared, wrong = (Path(d) / x for x in ("live","shared","wrong"))
            for folder in (live, shared, wrong):
                folder.mkdir()
            (live / "storage").symlink_to(wrong)
            with patch.object(n, "APP", live), patch.object(n, "SHARED", str(shared)):
                with self.assertRaisesRegex(o.Blocked, "LIVE_LINK_CHANGED"):
                    operations.switched_proofs()
        helper.attest_snapshot.assert_not_called()

    def test_source_has_no_direct_root_runner_and_never_conflates_app_paths(self):
        source = (Path(__file__).resolve().parent / "native_ops.py").read_text("utf-8")
        controller = (Path(__file__).resolve().parent / "orchestrator.py").read_text("utf-8")
        self.assertIn('TARGET_APP = Path(CANDIDATE) / "apps/platform"', source)
        self.assertIn('"--app-dir", str(TARGET_APP)', source)
        self.assertNotIn('"--app-dir", str(APP)', source)
        self.assertNotIn("snapshot_name(APP)", source)
        self.assertNotIn("completed_receipt(APP,", source)
        self.assertNotIn("helper.attest_snapshot(str(APP)", source)
        self.assertNotIn("574e443a2c75", source + controller)
        self.assertNotIn("cd9580701d3c", source + controller)
        self.assertIn("BLOCKED_NATIVE_ADAPTER_NOT_IMPLEMENTED", controller)
        self.assertEqual(o.SWITCHED[-1], "pointer_bce_unchanged")
        self.assertIn("live_shared_link_unchanged", o.SWITCHED)


if __name__ == "__main__":
    unittest.main()
