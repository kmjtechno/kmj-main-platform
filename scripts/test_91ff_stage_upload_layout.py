"""Offline fail-closed tests: no production/staging filesystem access."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations" / "assess_91ff_stage_upload_layout.py"
spec = importlib.util.spec_from_file_location("stage_layout", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

BASE = {
    "SCHEMA": module.SCHEMA,
    "OLD_STAGE_SHA": module.OLD,
    "NEW_CANDIDATE_SHA": module.NEW,
    "OLD_UPLOAD_LINK_KIND": "symlink",
    "OLD_UPLOAD_RESOLVED": "/home/kmjstage/releases/" + module.OLD + "/apps/platform/storage/app",
    "OLD_UPLOAD_FILES": "15",
    "OLD_UPLOAD_SYMLINKS": "0",
    "OLD_UPLOAD_BYTES": "1024",
    "OLD_UPLOAD_RECENT_WRITES_10M": "0",
    "OLD_UPLOAD_RELEASE_REFERENCES": "2",
    "OLD_PUBLIC_STORAGE_KIND": "symlink",
    "PRODUCT_ARTWORK_TARGET": "shared_exact",
    "NEW_CANDIDATE_UPLOAD_KIND": "directory",
    "SHARED_TARGET_STATE": "available",
    "SOURCE_AND_SHARED_SAME_FILESYSTEM": "yes",
    "SHARED_DISK_AVAILABLE_KB": "50000",
    "PRODUCTION_ACTIVATION": "NOT_ATTEMPTED",
    "CUSTOMER_UPLOADS_MODIFIED": "NO",
    "STAGING_POINTER_MODIFIED": "NO",
}


def receipt(**overrides):
    data = dict(BASE, **overrides)
    return "\n".join(f"{key}={value}" for key, value in data.items()) + "\n"


V3_BASE = {
    "SCHEMA": module.V3_SCHEMA,
    "ROOT_CHECK": "BLOCKED",  # old diagnostic rejects secure root-owned parent
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


def v3_receipt(**overrides):
    data = dict(V3_BASE, **overrides)
    return "\n".join(f"{key}={value}" for key, value in data.items()) + "\n"


class StageStorageLayoutSafety(unittest.TestCase):
    def assert_blocked(self, raw, expected):
        result = module.evaluate(raw)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], expected)
        self.assertFalse(result["stage_switch_authorized"])
        self.assertFalse(result["production_activation_authorized"])
        self.assertTrue(result["requires_owner_review"])

    def test_actual_v3_root_parent_is_safe_but_uploads_still_blocked(self):
        self.assert_blocked(v3_receipt(),
                            "RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION")

    def test_v3_root_parent_does_not_require_recursive_chown(self):
        self.assert_blocked(v3_receipt(OLD_UPLOAD_SCOPE="PERSISTENT_SHARED"),
                            "OWNER_APPROVED_STAGE_AND_RECOVERY_GATES_PENDING")

    def test_v3_rejects_world_writable_and_untrusted_root_parent(self):
        self.assert_blocked(v3_receipt(SHARED_MODE="777"),
                            "SHARED_ROOT_POLICY_UNSAFE")
        self.assert_blocked(v3_receipt(SHARED_UID="123", SHARED_MODE="755"),
                            "SHARED_ROOT_POLICY_UNSAFE")

    def test_v3_rejects_shared_symlink_or_untrusted_path(self):
        self.assert_blocked(v3_receipt(SHARED_IS_SYMLINK="YES"),
                            "SHARED_ROOT_TOPOLOGY_UNSAFE")
        self.assert_blocked(v3_receipt(SHARED_RESOLVED_SCOPE="OTHER"),
                            "SHARED_ROOT_TOPOLOGY_UNSAFE")

    def test_v3_rejects_false_no_mutation_or_production_drift(self):
        self.assert_blocked(v3_receipt(CUSTOMER_FILES_MODIFIED="YES"),
                            "IDENTITY_OR_READ_ONLY_INVARIANT")
        self.assert_blocked(v3_receipt(PRODUCTION_POINTER="DRIFT"),
                            "IDENTITY_OR_READ_ONLY_INVARIANT")

    def test_v3_rejects_untrusted_user_id_or_missing_parent(self):
        self.assert_blocked(v3_receipt(KMJSTAGE_UID="0"),
                            "UNTRUSTED_STAGE_UID")
        self.assert_blocked(v3_receipt(SHARED_PARENT_KIND="symlink"),
                            "SHARED_ROOT_TOPOLOGY_UNSAFE")

    def test_v3_rejects_duplicates_unknown_and_nul(self):
        self.assert_blocked(v3_receipt() + "SHARED_UID=0\n",
                            "INVALID_OR_MISSING_RECEIPT")
        self.assert_blocked(v3_receipt() + "EXTRA=NO\n",
                            "INVALID_OR_MISSING_RECEIPT")
        self.assert_blocked(v3_receipt() + "\x00",
                            "INVALID_OR_MISSING_RECEIPT")

    def test_v3_cannot_authorize_release_for_any_valid_source_scope(self):
        for scope in ("RELEASE_BOUND", "PERSISTENT_SHARED", "UNVERIFIED"):
            result = module.evaluate(v3_receipt(OLD_UPLOAD_SCOPE=scope))
            self.assertFalse(result["stage_switch_authorized"])
            self.assertFalse(result["production_activation_authorized"])

    def test_release_bound_data_must_not_be_relinked_or_deleted(self):
        self.assert_blocked(
            receipt(), "RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION"
        )

    def test_missing_receipt_never_passes(self):
        self.assert_blocked("", "INVALID_OR_MISSING_RECEIPT")

    def test_duplicate_field_is_rejected(self):
        self.assert_blocked(receipt() + "OLD_UPLOAD_FILES=0\n", "INVALID_OR_MISSING_RECEIPT")

    def test_forged_readonly_flag_is_rejected(self):
        self.assert_blocked(
            receipt(PRODUCTION_ACTIVATION="PERFORMED"),
            "IDENTITY_OR_READ_ONLY_INVARIANT",
        )

    def test_untrusted_target_is_rejected(self):
        self.assert_blocked(
            receipt(OLD_UPLOAD_RESOLVED="/tmp/uploads"),
            "UNAPPROVED_SHARED_UPLOAD_TARGET",
        )

    def test_canonical_layout_still_does_not_authorize_release(self):
        self.assert_blocked(
            receipt(OLD_UPLOAD_RESOLVED=module.CANONICAL, SHARED_TARGET_STATE="occupied"),
            "OWNER_APPROVED_STAGE_AND_RECOVERY_GATES_PENDING",
        )

    def test_canonical_layout_with_recent_writes_is_blocked(self):
        self.assert_blocked(
            receipt(
                OLD_UPLOAD_RESOLVED=module.CANONICAL,
                OLD_UPLOAD_RECENT_WRITES_10M="4",
            ),
            "RECENT_WRITES_REQUIRE_QUIESCENCE",
        )

    def test_product_artwork_separation_must_be_preserved(self):
        self.assert_blocked(
            receipt(OLD_UPLOAD_RESOLVED=module.CANONICAL, PRODUCT_ARTWORK_TARGET="not_shared"),
            "PRODUCT_ARTWORK_CONTINUITY_UNVERIFIED",
        )

    def test_bad_counters_fail_closed(self):
        self.assert_blocked(
            receipt(OLD_UPLOAD_FILES="-1"), "INVALID_COUNTER"
        )

    def test_new_candidate_symlink_is_not_accepted(self):
        self.assert_blocked(
            receipt(NEW_CANDIDATE_UPLOAD_KIND="symlink"),
            "CANDIDATE_STORAGE_NOT_SCAFFOLD",
        )

    def test_no_automatic_success_path(self):
        for path in (
            module.CANONICAL,
            "/home/kmjstage/releases/" + module.OLD + "/apps/platform/storage/app",
            "/home/kmjstage/shared/other",
        ):
            self.assertFalse(
                module.evaluate(receipt(OLD_UPLOAD_RESOLVED=path))["stage_switch_authorized"]
            )


if __name__ == "__main__":
    unittest.main()
