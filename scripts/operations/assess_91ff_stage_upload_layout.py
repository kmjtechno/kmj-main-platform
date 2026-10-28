#!/usr/bin/env python3
"""Advisory-only 91FF staging upload layout receipt evaluator.

Never accesses VPS storage, changes files, or authorizes a release.
A sanitized receipt is NOT an owner-signed approval or a backup.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OLD = "9d15e14e39564ffb1e66085a483feb8331f9718f"
NEW = "91ff3296597c3901865960d39936816ac9ca4c7a"
SCHEMA = "KMJ_91FF_STAGE_STORAGE_LAYOUT_V1"
EXPECTED = {
    "SCHEMA", "OLD_STAGE_SHA", "NEW_CANDIDATE_SHA",
    "OLD_UPLOAD_LINK_KIND", "OLD_UPLOAD_RESOLVED", "OLD_UPLOAD_FILES",
    "OLD_UPLOAD_SYMLINKS", "OLD_UPLOAD_BYTES", "OLD_UPLOAD_RECENT_WRITES_10M",
    "OLD_UPLOAD_RELEASE_REFERENCES", "OLD_PUBLIC_STORAGE_KIND",
    "PRODUCT_ARTWORK_TARGET", "NEW_CANDIDATE_UPLOAD_KIND",
    "SHARED_TARGET_STATE", "SOURCE_AND_SHARED_SAME_FILESYSTEM",
    "SHARED_DISK_AVAILABLE_KB", "PRODUCTION_ACTIVATION",
    "CUSTOMER_UPLOADS_MODIFIED", "STAGING_POINTER_MODIFIED",
}
CANONICAL = "/home/kmjstage/shared/kmj-platform-uploads"

V3_SCHEMA = "KMJ_STAGE_SHARED_ROOT_V3"
V3_EXPECTED = {
    "SCHEMA", "ROOT_CHECK", "KMJSTAGE_UID", "SHARED_KIND",
    "SHARED_IS_SYMLINK", "SHARED_IS_DIRECTORY", "SHARED_UID", "SHARED_GID",
    "SHARED_MODE", "SHARED_OWNER_IS_KMJSTAGE", "SHARED_RESOLVED_SCOPE",
    "SHARED_PARENT_KIND", "SHARED_PARENT_UID", "OLD_UPLOAD_SCOPE",
    "OLD_UPLOAD_KIND", "PRODUCTION_POINTER", "CUSTOMER_FILES_MODIFIED",
    "STAGING_POINTER_MODIFIED", "PRODUCTION_MODIFIED",
    "OWNERSHIP_OR_PERMISSIONS_MODIFIED",
}


def blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "stage_switch_authorized": False,
        "production_activation_authorized": False,
        "requires_owner_review": True,
    }


def parse_fields(raw: str, expected: set[str]) -> dict[str, str]:
    """Require one bounded, unambiguous, sanitized exact-field receipt."""
    if len(raw.encode("utf-8")) > 8192 or "\\x00" in raw:
        raise ValueError("RECEIPT_SIZE_OR_CONTROL")
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or "=" not in line:
            raise ValueError("MALFORMED_LINE")
        key, value = line.split("=", 1)
        if key not in expected or key in fields or not value or any(
            ord(char) < 32 or ord(char) == 127 for char in value
        ):
            raise ValueError("UNKNOWN_DUPLICATE_OR_CONTROL_FIELD")
        fields[key] = value
    if fields.keys() != expected:
        raise ValueError("INCOMPLETE_FIELDS")
    return fields


def parse_receipt(raw: str) -> dict[str, str]:
    return parse_fields(raw, EXPECTED)


def evaluate_v3(raw: str) -> dict[str, object]:
    """Recognize a secured root-owned parent WITHOUT authorizing migration."""
    try:
        f = parse_fields(raw, V3_EXPECTED)
        if (
            f["SCHEMA"] != V3_SCHEMA
            or f["PRODUCTION_POINTER"] != "UNCHANGED"
            or any(f[key] != "NO" for key in (
                "CUSTOMER_FILES_MODIFIED", "STAGING_POINTER_MODIFIED",
                "PRODUCTION_MODIFIED", "OWNERSHIP_OR_PERMISSIONS_MODIFIED",
            ))
            or f["ROOT_CHECK"] not in ("PASS", "BLOCKED")
        ):
            return blocked("IDENTITY_OR_READ_ONLY_INVARIANT")
        uid = f["KMJSTAGE_UID"]
        if not re.fullmatch(r"[0-9]{1,10}", uid) or uid == "0":
            return blocked("UNTRUSTED_STAGE_UID")
        if not (
            f["SHARED_KIND"] == "directory"
            and f["SHARED_IS_SYMLINK"] == "NO"
            and f["SHARED_IS_DIRECTORY"] == "YES"
            and f["SHARED_RESOLVED_SCOPE"] == "EXACT"
            and f["SHARED_PARENT_KIND"] == "directory"
            and f["SHARED_PARENT_UID"] == uid
        ):
            return blocked("SHARED_ROOT_TOPOLOGY_UNSAFE")
        # A secure root:root 0755 shared parent is acceptable; do NOT chown it.
        # Existing stage-owned parents are also accepted only with safe modes.
        root_owned = (
            f["SHARED_UID"] == "0" and f["SHARED_GID"] == "0"
            and f["SHARED_MODE"] in ("755", "750", "700")
        )
        stage_owned = (
            f["SHARED_UID"] == uid
            and f["SHARED_OWNER_IS_KMJSTAGE"] == "YES"
            and f["SHARED_MODE"] in ("755", "750", "700")
        )
        if not (root_owned or stage_owned):
            return blocked("SHARED_ROOT_POLICY_UNSAFE")
        if f["OLD_UPLOAD_KIND"] not in ("directory", "symlink"):
            return blocked("UNTRUSTED_OLD_UPLOAD_KIND")
        if f["OLD_UPLOAD_SCOPE"] == "RELEASE_BOUND":
            return blocked("RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION")
        if f["OLD_UPLOAD_SCOPE"] == "PERSISTENT_SHARED":
            return blocked("OWNER_APPROVED_STAGE_AND_RECOVERY_GATES_PENDING")
        return blocked("UNVERIFIED_UPLOAD_SCOPE")
    except (ValueError, UnicodeError):
        return blocked("INVALID_OR_MISSING_RECEIPT")


def parse_receipt(raw: str) -> dict[str, str]:
    return parse_fields(raw, EXPECTED)


def evaluate(raw: str) -> dict[str, object]:
    if raw.startswith("SCHEMA=" + V3_SCHEMA + "\\n"):
        return evaluate_v3(raw)
    try:
        f = parse_receipt(raw)
        if (
            f["SCHEMA"] != SCHEMA
            or f["OLD_STAGE_SHA"] != OLD
            or f["NEW_CANDIDATE_SHA"] != NEW
            or f["PRODUCTION_ACTIVATION"] != "NOT_ATTEMPTED"
            or f["CUSTOMER_UPLOADS_MODIFIED"] != "NO"
            or f["STAGING_POINTER_MODIFIED"] != "NO"
        ):
            return blocked("IDENTITY_OR_READ_ONLY_INVARIANT")
        for key in (
            "OLD_UPLOAD_FILES", "OLD_UPLOAD_SYMLINKS", "OLD_UPLOAD_BYTES",
            "OLD_UPLOAD_RECENT_WRITES_10M", "OLD_UPLOAD_RELEASE_REFERENCES",
            "SHARED_DISK_AVAILABLE_KB",
        ):
            if not re.fullmatch(r"[0-9]{1,20}", f[key]):
                return blocked("INVALID_COUNTER")
        if f["OLD_UPLOAD_LINK_KIND"] not in ("directory", "symlink"):
            return blocked("INVALID_SOURCE_KIND")
        if f["NEW_CANDIDATE_UPLOAD_KIND"] != "directory":
            return blocked("CANDIDATE_STORAGE_NOT_SCAFFOLD")
        if f["SHARED_TARGET_STATE"] not in ("available", "occupied"):
            return blocked("INVALID_SHARED_TARGET_STATE")
        if f["SOURCE_AND_SHARED_SAME_FILESYSTEM"] not in ("yes", "no"):
            return blocked("INVALID_FILESYSTEM_IDENTITY")
        path = f["OLD_UPLOAD_RESOLVED"]
        if "//" in path or "/../" in path or "/./" in path:
            return blocked("UNTRUSTED_RESOLVED_PATH")
        if path.startswith("/home/kmjstage/releases/") and path.endswith(
            "/apps/platform/storage/app"
        ):
            return blocked("RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION")
        if path != CANONICAL:
            return blocked("UNAPPROVED_SHARED_UPLOAD_TARGET")
        if f["PRODUCT_ARTWORK_TARGET"] != "shared_exact":
            return blocked("PRODUCT_ARTWORK_CONTINUITY_UNVERIFIED")
        if int(f["OLD_UPLOAD_RECENT_WRITES_10M"]) > 0:
            return blocked("RECENT_WRITES_REQUIRE_QUIESCENCE")
        # Even a perfect read-only layout receipt is not a backup, owner QA,
        # root-signed staging approval, or exact HTTPS proof.
        return blocked("OWNER_APPROVED_STAGE_AND_RECOVERY_GATES_PENDING")
    except (ValueError, UnicodeError):
        return blocked("INVALID_OR_MISSING_RECEIPT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="Sanitized owner diagnostic receipt")
    args = parser.parse_args()
    try:
        raw = args.receipt.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raw = ""
    result = evaluate(raw)
    print(json.dumps(result, sort_keys=True))
    return 2  # Always nonzero: advisory output cannot become an activation gate.


if __name__ == "__main__":
    raise SystemExit(main())
