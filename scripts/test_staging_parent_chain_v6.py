"""Offline negative tests for fixed-host V6 parent-chain audit."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
import os
import tempfile
from unittest import mock

SOURCE = Path(__file__).resolve().parent / "operations/audit-staging-parent-chain-v6-20261029.py"
spec = importlib.util.spec_from_file_location("stage_parent_v6", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows(stage_mode=0o755, stage_uid=995, shared_uid=0, acl="ABSENT", shared_dev=1):
    return [
        {"uid": 0, "gid": 0, "mode": 0o755, "dev": 1, "acl": acl},
        {"uid": stage_uid, "gid": 995, "mode": stage_mode, "dev": 1, "acl": acl},
        {"uid": shared_uid, "gid": 0, "mode": 0o755, "dev": shared_dev, "acl": acl},
    ]


class ParentChainV6Contract(unittest.TestCase):
    def test_untrusted_home_parent_owner_is_explicitly_blocked(self):
        chain = rows(stage_mode=0o555)
        chain[0]["uid"] = 995
        result = module.assess(chain, 995)
        self.assertIn("HOME_PARENT_NOT_ROOT_OWNED", result["blockers"])
        self.assertFalse(result["migration_authorized"])

    def test_unexpected_stage_parent_owner_is_explicitly_blocked(self):
        chain = rows(stage_mode=0o555, stage_uid=996)
        result = module.assess(chain, 995)
        self.assertFalse(result["stage_parent_uid_matches"])
        self.assertIn("STAGE_PARENT_OWNER_MISMATCH", result["blockers"])
        self.assertFalse(result["staging_switch_authorized"])

    def test_stage_owned_parent_can_replace_root_owned_child(self):
        result = module.assess(rows(stage_mode=0o755), 995)
        self.assertTrue(result["stage_parent_write_execute"])
        self.assertTrue(result["shared_root_owned_0755"])
        self.assertIn("STAGE_PARENT_WRITE_EXEC", result["blockers"])
        self.assertFalse(result["migration_authorized"])

    def test_owner_can_chmod_0555_parent_then_rename_root_owned_child(self):
        mount = {"mountinfo_checked": True,
                 "stage_parent_explicit_mount": False,
                 "shared_explicit_mount": False}
        result = module.assess(rows(stage_mode=0o555), 995, mount)
        self.assertFalse(result["stage_parent_write_execute"])
        self.assertTrue(result["shared_root_owned_0755"])
        self.assertIn("STAGE_PARENT_OWNER_CAN_CHMOD", result["blockers"])
        self.assertNotIn("OWNER_REVIEW_AND_BACKUP_STILL_REQUIRED", result["blockers"])
        self.assertFalse(result["migration_authorized"])
        self.assertFalse(result["staging_switch_authorized"])
        self.assertFalse(result["production_activation_authorized"])

    def test_group_writable_parent_is_blocked(self):
        result = module.assess(rows(stage_mode=0o775, stage_uid=0), 995)
        self.assertTrue(result["stage_parent_write_execute"])
        self.assertIn("STAGE_PARENT_WRITE_EXEC", result["blockers"])

    def test_sticky_parent_does_not_override_approval(self):
        result = module.assess(rows(stage_mode=0o1755), 995)
        self.assertTrue(result["stage_parent_sticky"])
        self.assertFalse(result["staging_switch_authorized"])

    def test_acl_unknown_or_present_blocks(self):
        for acl in ("UNKNOWN", "PRESENT", "ERROR"):
            with self.subTest(acl=acl):
                result = module.assess(rows(stage_mode=0o555, acl=acl), 995)
                self.assertIn("ACL_UNVERIFIED_OR_PRESENT", result["blockers"])

    def test_mount_boundary_and_non_root_shared_block(self):
        result = module.assess(rows(stage_mode=0o555, shared_uid=995, shared_dev=2), 995)
        self.assertIn("SHARED_ROOT_POLICY", result["blockers"])
        self.assertIn("MOUNT_BOUNDARY_REVIEW", result["blockers"])

    def test_explicit_same_device_mountpoint_requires_review(self):
        mount = {"mountinfo_checked": True,
                 "stage_parent_explicit_mount": False,
                 "shared_explicit_mount": True}
        result = module.assess(rows(stage_mode=0o555), 995, mount)
        self.assertTrue(result["shared_parent_same_device"])
        self.assertIn("EXPLICIT_MOUNTPOINT_REVIEW", result["blockers"])
        self.assertFalse(result["migration_authorized"])

    def test_unavailable_mountinfo_is_not_treated_as_safe(self):
        result = module.assess(rows(stage_mode=0o555), 995)
        self.assertIn("MOUNTINFO_UNVERIFIED", result["blockers"])
        self.assertFalse(result["mountinfo_checked"])

    def test_even_ideal_chain_is_not_release_approval(self):
        result = module.assess(rows(stage_mode=0o555), 995)
        self.assertFalse(result["migration_authorized"])
        self.assertFalse(result["encrypted_offsite_restore_verified"])
        self.assertFalse(result["owner_approval_attested"])

    def test_named_directory_swap_after_open_is_rejected(self):
        # Disposable local directory only: simulate a rename between the
        # initial fd open and final anchored name revalidation.
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="kmj-v6-test-") as root:
            shared = Path(root) / "shared"
            shared.mkdir()
            parts = ("tmp", Path(root).name, "shared")
            original_stat = os.stat
            calls = 0

            def swap_on_second_stat(path, *args, **kwargs):
                nonlocal calls
                if path == "shared" and kwargs.get("dir_fd") is not None:
                    calls += 1
                    if calls == 2:
                        shared.rename(Path(root) / "shared-old")
                        shared.mkdir()
                return original_stat(path, *args, **kwargs)

            with mock.patch.object(module, "PARTS", parts):
                with mock.patch.object(module.os, "stat", side_effect=swap_on_second_stat):
                    with self.assertRaisesRegex(module.AuditBlocked, "CHAIN_CHANGED"):
                        module.snapshot_chain()
            self.assertEqual(calls, 2)

    def test_fixed_scope_no_customer_mutation_calls(self):
        text = SOURCE.read_text()
        for forbidden in ("shutil.copy", "os.rename(", "os.unlink(", "subprocess.run(",
                          "os.chown(", "os.chmod(", "systemctl", "git reset", "pg_dump"):
            self.assertNotIn(forbidden, text)
        self.assertIn("os.O_NOFOLLOW", text)
        self.assertIn("os.O_EXCL", text)
        self.assertIn("os.fchmod(out.fileno(), 0o640)", text)
        self.assertIn('"migration_authorized": False', text)

    def test_root_receipt_rejects_world_writable_qa_without_creating_file(self):
        with tempfile.TemporaryDirectory() as root:
            qa = Path(root) / "qa"
            qa.mkdir()
            qa.chmod(0o777)
            with mock.patch.object(module, "QA", qa):
                with mock.patch.object(module.pwd, "getpwnam") as stage_user:
                    stage_user.return_value.pw_uid = -1
                    with self.assertRaisesRegex(module.AuditBlocked, "QA_DIRECTORY_UNTRUSTED"):
                        module.write_receipt({"schema": "test"})
            self.assertFalse((qa / module.RECEIPT).exists())

    def test_root_receipt_rejects_staging_owned_qa_even_if_not_writable(self):
        with tempfile.TemporaryDirectory() as root:
            qa = Path(root) / "qa"
            qa.mkdir()
            qa.chmod(0o555)
            with mock.patch.object(module, "QA", qa):
                with mock.patch.object(module.pwd, "getpwnam") as stage_user:
                    stage_user.return_value.pw_uid = qa.stat().st_uid
                    with self.assertRaisesRegex(module.AuditBlocked, "QA_DIRECTORY_UNTRUSTED"):
                        module.write_receipt({"schema": "test"})
            self.assertFalse((qa / module.RECEIPT).exists())

    def test_untrusted_runner_does_not_create_receipt(self):
        if sys.platform != "linux":
            self.skipTest("Linux-only host guard")
        result = subprocess.run([sys.executable, "-B", str(SOURCE)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED_HOST_ROOT_OR_ARGS", result.stdout)


if __name__ == "__main__":
    unittest.main()
