#!/usr/bin/env python3
"""Offline adversarial tests for 09e8 native candidate storage witness (no host I/O)."""
from __future__ import annotations
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SRC = (Path(__file__).resolve().parent / "operations" /
       "09e8-native-candidate-witness-readonly-20261109.py")
spec = importlib.util.spec_from_file_location("kmj09e8candidatewitness", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def real_plan():
    return {
        "command": "plan", "mutated": False,
        "inventory_only_not_release_readiness": True,
        "persistent_only_plan_id": True, "ready": True,
        "to_copy": 0, "persistent_conflicts": [],
        "plan_id": "c651c450b3941f3a",
        "top_dir_meta_live_mode_uid_gid": [448, 1001, 1001],
        "top_dir_meta_shared_mode_uid_gid": [448, 1001, 1001],
    }


class Helper:
    def __init__(self, plan=None, source_valid=True):
        self.plan = plan if plan is not None else real_plan()
        self.source_valid = source_valid
        self.git_calls = []
        self.attest_calls = []

    def git_identity(self, candidate, sha):
        self.git_calls.append((candidate, sha))
        if sha != mod.CANDIDATE_SHA:
            raise RuntimeError("UNEXPECTED_SHA")

    def load_scanner(self, path, candidate, shared, state):
        self.attest_calls.append((path, candidate, shared, state))
        return self

    def cmd_plan(self, args):
        if args.apply or args.plan_id is not None:
            raise AssertionError("PLAN_MUTATION_ARG")
        return self.plan

    def check_source(self, **kwargs):
        self.attest_calls.append(kwargs)
        if not self.source_valid:
            return "wrong/path/"
        return "apps/platform/" + kwargs["snapshot_name"] + "/"


class NativeCandidateWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "owner"
        self.current_release = self.root / "releases/platform-bce4100d005e"
        self.candidate = self.root / "releases/platform-09e8a224cd37"
        self.liveapp = self.current_release / "apps/platform"
        self.candapp = self.candidate / "apps/platform"
        self.shared = self.root / "shared/storage"
        self.liveapp.mkdir(parents=True)
        self.candapp.mkdir(parents=True)
        self.shared.mkdir(parents=True)
        (self.root / "current").symlink_to(self.current_release)
        (self.liveapp / "storage").symlink_to(self.shared)
        (self.candapp / "storage").mkdir()
        self.state = self.root / "state"
        items = {"ROOT": self.root, "LIVE": self.current_release,
                 "CANDIDATE": self.candidate, "CAND_APP": self.candapp,
                 "LIVE_APP": self.liveapp, "CURRENT": self.root / "current",
                 "SHARED": self.shared, "STATE": str(self.state)}
        for key, value in items.items():
            p = mock.patch.object(mod, key, value)
            p.start()
            self.addCleanup(p.stop)

    def test_exact_release_and_integrity_pins(self):
        self.assertEqual(mod.CANDIDATE_SHA,
                         "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(mod.LIVE_RELEASE, "platform-bce4100d005e")
        self.assertEqual(mod.SCANNER_SHA,
                         "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba")
        self.assertEqual(mod.MATERIALIZER_SHA,
                         "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f")

    def test_live_identity_stable_exact_shared_inode(self):
        first = mod.live_identity()
        self.assertEqual(first, mod.live_identity())
        self.assertEqual(first[2], (self.shared.stat().st_dev, self.shared.stat().st_ino))
        (self.liveapp / "storage").unlink()
        (self.liveapp / "storage").symlink_to(self.candapp / "storage")
        with self.assertRaisesRegex(mod.Refused, "LIVE_STORAGE_NOT_APPROVED_SHARED"):
            mod.live_identity()

    def test_live_pointer_mismatch_blocks(self):
        (self.root / "current").unlink()
        (self.root / "current").symlink_to(self.candidate)
        with self.assertRaisesRegex(mod.Refused, "CURRENT_POINTER_NOT_EXACT"):
            mod.live_identity()

    def test_pre_validated_candidate_physical_plan(self):
        helper = Helper()
        result = mod.pre(helper)
        self.assertEqual(result["CANDIDATE_STORAGE"], "PHYSICAL")
        self.assertEqual(result["STORAGE_PLAN_ID"], "c651c450b3941f3a")
        self.assertEqual(result["STORAGE_PLAN_READY"], "YES")
        self.assertEqual(helper.git_calls, [(self.candidate, mod.CANDIDATE_SHA)])
        self.assertEqual(len(helper.attest_calls), 1)

    def test_pre_rejects_env_already_materialized(self):
        (self.candapp / ".env").write_text("PRIVATE_SECRET=never_print")
        with self.assertRaisesRegex(mod.Refused, "CANDIDATE_ALREADY_MATERIALIZED"):
            mod.pre(Helper())

    def test_pre_rejects_symlink_candidate_storage(self):
        (self.candapp / "storage").rmdir()
        (self.candapp / "storage").symlink_to(self.shared)
        with self.assertRaisesRegex(mod.Refused, "CANDIDATE_STORAGE_NOT_PHYSICAL"):
            mod.pre(Helper())

    def test_zero_copy_conflicts_and_metadata_required(self):
        for key, value in (
            ("command", "switch"), ("mutated", True), ("ready", "True"),
            ("ready", False), ("to_copy", 1), ("to_copy", "0"),
            ("persistent_conflicts", ["PRIVATE_UPLOAD_NOT_SYNCED"]),
            ("plan_id", "x"),
            ("inventory_only_not_release_readiness", False),
            ("persistent_only_plan_id", False),
            ("top_dir_meta_live_mode_uid_gid", [7, 8, 9]),
        ):
            plan = real_plan()
            plan[key] = value
            with self.subTest(key=key), self.assertRaises(mod.Refused):
                mod.sanitized_plan(plan)

    def test_post_verifies_exact_candidate_snapshot_and_source(self):
        (self.candapp / "storage").rmdir()
        (self.candapp / "storage").symlink_to(self.shared)
        (self.candapp / "storage.pre-shared-20261109T100500Z").mkdir()
        helper = Helper()
        result = mod.post(helper)
        self.assertEqual(result["CANDIDATE_V6_CLOSED_RECEIPT"], "ROOT_ATTESTED")
        self.assertEqual(result["SHARED_STORAGE_THAWED"], "ROOT_ATTESTED")
        self.assertEqual(len(helper.attest_calls), 1)
        self.assertEqual(helper.attest_calls[0]["expected_sha"], mod.CANDIDATE_SHA)

    def test_post_refuses_ambiguous_or_bad_snapshot(self):
        (self.candapp / "storage").rmdir()
        (self.candapp / "storage").symlink_to(self.shared)
        for item in ("storage.pre-shared-20261109T100500Z",
                     "storage.pre-shared-20261109T100501Z"):
            (self.candapp / item).mkdir()
        with self.assertRaisesRegex(mod.Refused, "CANDIDATE_SNAPSHOT_NOT_UNIQUE"):
            mod.post(Helper())

    def test_post_refuses_failed_root_source_attestation(self):
        (self.candapp / "storage").rmdir()
        (self.candapp / "storage").symlink_to(self.shared)
        (self.candapp / "storage.pre-shared-20261109T100500Z").mkdir()
        with self.assertRaisesRegex(mod.Refused, "CANDIDATE_ROOT_SNAPSHOT_NOT_ATTESTED"):
            mod.post(Helper(source_valid=False))

    def test_main_pre_success_no_mutation_or_release_authorization(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \\
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \\
             mock.patch.object(mod, "verify_pinned", return_value=b"trusted-source"), \\
             mock.patch.object(mod, "load_helper", return_value=Helper()):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = mod.main(["--pre"])
        self.assertEqual(result, 0)
        self.assertIn("NATIVE_CANDIDATE_WITNESS=READ_ONLY_COMPLETE", output.getvalue())
        self.assertIn("PINNED_ROOT_MATERIALIZER=YES", output.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", output.getvalue())
        self.assertFalse((self.candapp / ".env").exists())

    def test_root_failure_does_not_print_sensitive_exception_or_pass(self):
        def fail(*args):
            raise ValueError("PRIVATE_CUSTOMER_PATH")
        with mock.patch.object(mod.os, "geteuid", return_value=0), \\
             mock.patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \\
             mock.patch.object(mod, "verify_pinned", side_effect=fail):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = mod.main(["--pre"])
        self.assertEqual(result, 2)
        self.assertNotIn("PRIVATE_CUSTOMER_PATH", output.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", output.getvalue())
        self.assertIn("PRODUCTION_MUTATION=NONE", output.getvalue())

    def test_no_host_mutation_controls_in_source(self):
        import ast
        source = SRC.read_text("utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name in {"subprocess", "shutil"} for alias in node.names
            ):
                self.fail("mutation-capable module imported")
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"subprocess", "shutil"})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id,
                                 {"eval", "open", "__import__", "system"})
        for bad in ("systemctl stop", "systemctl restart", " --apply",
                    "os.symlink(", "os.unlink(", "os.replace(",
                    "os.chmod(", "os.chown(", "git reset", "nft add",
                    "curl -"):
            self.assertNotIn(bad, source)


if __name__ == "__main__":
    unittest.main()
