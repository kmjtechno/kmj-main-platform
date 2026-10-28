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


class StageStorageLayoutSafety(unittest.TestCase):
    def assert_blocked(self, raw, expected):
        result = module.evaluate(raw)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], expected)
        self.assertFalse(result["stage_switch_authorized"])
        self.assertFalse(result["production_activation_authorized"])
        self.assertTrue(result["requires_owner_review"])

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
