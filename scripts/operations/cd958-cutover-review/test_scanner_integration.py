"""Exercise runner recovery against the pinned scanner on disposable trees."""

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import native_ops as native
import test_main_platform_storage_switch as fixture


class ScannerRecoveryIntegration(fixture.Base):
    def setUp(self):
        super().setUp()
        raw = Path(fixture.sw.__file__).read_bytes()
        self.assertIn(native.PINS["scanner"], {
            hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(raw + b"\n").hexdigest(),
        })
        self.real_immutable = os.environ.get("KMJ_REQUIRE_REAL_IMMUTABLE") == "1"
        if self.real_immutable:
            fixture.sw.FREEZER = fixture.sw.Freezer()

    def tearDown(self):
        if self.real_immutable:
            fixture.force_thaw(self.root)
        super().tearDown()

    def recover_after_crash(self, phase, expect_shared):
        plan_id = self.plan()["plan_id"]
        self.crash(phase)
        ops = native.NativeOps.__new__(native.NativeOps)
        ops.pointer = Mock()
        ops.release_lock = SimpleNamespace(verify=Mock())
        ops.guard_counter = Mock()
        ops.unit_empty = Mock(return_value=True)
        ops.fpm_children = Mock(return_value=[])
        ops.socket_empty = Mock(return_value=True)
        ops.module = Mock(return_value=fixture.sw)
        original = fixture.sw.cmd_recover

        def run_in_fixture(args):
            args.allowed_root = str(self.root)
            args.proc_root = str(self.root / "proc")
            return original(args)

        with (
            patch.object(native, "APP", self.live.parent),
            patch.object(native, "SHARED", str(self.shared)),
            patch.object(native, "SCANNER_STATE", str(self.root / "state")),
            patch.object(native.p, "properties", return_value=({"ActiveState": "inactive"}, "hash")),
            patch.object(fixture.sw, "cmd_recover", side_effect=run_in_fixture),
        ):
            self.assertTrue(ops.recover_active_scanner({"phase": "switch_intent", "plan_id": plan_id}))
        self.assertEqual(self.live.is_symlink(), expect_shared)
        self.assertEqual(self.journals(), [])
        self.assertEqual((self.live / "app/private/live-only.json").read_bytes(), b"{}")
        self.assertTrue(fixture.sw.tree_clean(self.open_directory(self.shared), True))

    def open_directory(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.addCleanup(os.close, fd)
        return fd

    def test_reverts_frozen_tree(self):
        self.recover_after_crash("both_frozen", False)

    def test_reverts_interrupted_exchange(self):
        self.recover_after_crash("exchanged", False)

    def test_completes_preserved_switch(self):
        self.recover_after_crash("preserved", True)
