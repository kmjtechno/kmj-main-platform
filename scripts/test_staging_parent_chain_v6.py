"""Offline negative tests for fixed-host V6 parent-chain audit."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

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

    def test_fixed_scope_no_customer_mutation_calls(self):
        text = SOURCE.read_text()
        for forbidden in ("shutil.copy", "os.rename(", "os.unlink(", "subprocess.run(",
                          "os.chown(", "os.chmod(", "systemctl", "git reset", "pg_dump"):
            self.assertNotIn(forbidden, text)
        self.assertIn("os.O_NOFOLLOW", text)
        self.assertIn("os.O_EXCL", text)
        self.assertIn("os.fchmod(out.fileno(), 0o640)", text)
        self.assertIn('"migration_authorized": False', text)

    def test_untrusted_runner_does_not_create_receipt(self):
        if sys.platform != "linux":
            self.skipTest("Linux-only host guard")
        result = subprocess.run([sys.executable, "-B", str(SOURCE)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED_HOST_ROOT_OR_ARGS", result.stdout)


if __name__ == "__main__":
    unittest.main()
