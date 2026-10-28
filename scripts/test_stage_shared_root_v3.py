"""Offline negative tests for the V3 root ownership diagnostic."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).parent / "operations" / "assess_stage_shared_root_v3.py"
spec = importlib.util.spec_from_file_location("shared_v3", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

BASE = {
    "SCHEMA": "KMJ_STAGE_SHARED_ROOT_V3",
    "ROOT_CHECK": "BLOCKED",
    "KMJSTAGE_UID": "995",
    "SHARED_KIND": "directory",
    "SHARED_IS_SYMLINK": "NO",
    "SHARED_IS_DIRECTORY": "YES",
    "SHARED_UID": "0",
    "SHARED_GID": "0",
    "SHARED_MODE": "755",
    "SHARED_OWNER_IS_KMJSTAGE": "NO",
    "SHARED_RESOLVED_SCOPE": "EXACT",
    "SHARED_PARENT_KIND": "directory",
    "SHARED_PARENT_UID": "995",
    "OLD_UPLOAD_SCOPE": "RELEASE_BOUND",
    "OLD_UPLOAD_KIND": "symlink",
    "PRODUCTION_POINTER": "UNCHANGED",
    "CUSTOMER_FILES_MODIFIED": "NO",
    "STAGING_POINTER_MODIFIED": "NO",
    "PRODUCTION_MODIFIED": "NO",
    "OWNERSHIP_OR_PERMISSIONS_MODIFIED": "NO",
}


def receipt(**changes):
    data = dict(BASE, **changes)
    return "\n".join(f"{key}={value}" for key, value in data.items()) + "\n"


class SharedRootV3Safety(unittest.TestCase):
    def check(self, raw, reason):
        result = module.evaluate(raw)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertFalse(result["staging_switch_authorized"])
        self.assertFalse(result["production_activation_authorized"])
        self.assertFalse(result["shared_root_mutation_authorized"])

    def test_actual_sanitized_v3_receipt(self):
        self.check(receipt(), "PARENT_MUTABILITY_NOT_ATTESTED")

    def test_root_owned_shared_directory_is_not_automatically_chowned(self):
        self.check(
            receipt(SHARED_PARENT_UID="0"),
            "RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION",
        )

    def test_staging_owned_shared_root_needs_review(self):
        self.check(
            receipt(SHARED_UID="995", SHARED_OWNER_IS_KMJSTAGE="YES"),
            "UNPRIVILEGED_SHARED_ROOT_NEEDS_REVIEW",
        )

    def test_symlink_root_denied(self):
        self.check(
            receipt(SHARED_KIND="symlink", SHARED_IS_SYMLINK="YES"),
            "UNTRUSTED_SHARED_PATH",
        )

    def test_group_writable_root_denied(self):
        self.check(receipt(SHARED_MODE="775"),
                   "SHARED_ROOT_GROUP_OR_WORLD_WRITABLE")

    def test_owner_field_contradiction_denied(self):
        self.check(receipt(SHARED_OWNER_IS_KMJSTAGE="YES"),
                   "OWNER_FIELD_CONTRADICTION")

    def test_production_pointer_drift_denied(self):
        self.check(receipt(PRODUCTION_POINTER="DIFFERENT_OR_UNVERIFIED"),
                   "READ_ONLY_OR_PRODUCTION_DRIFT")

    def test_missing_duplicate_and_unknown_fields_denied(self):
        for raw in ("", receipt() + "SHARED_UID=0\n",
                    receipt() + "SECRET=foo\n"):
            self.check(raw, "INVALID_OR_MISSING_RECEIPT")

    def test_parent_root_does_not_approve_even_if_source_shared(self):
        self.check(
            receipt(SHARED_PARENT_UID="0",
                    OLD_UPLOAD_SCOPE="PERSISTENT_SHARED"),
            "FULL_INVENTORY_BACKUP_AND_OWNER_QA_PENDING",
        )


if __name__ == "__main__":
    unittest.main()
