#!/usr/bin/env python3
"""Fail-closed OFFLINE classifier for a sanitized V3 staging-root receipt.

This program never connects to a VPS, reads customer files, or authorizes a
migration, staging switch, owner approval, or production deployment.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXPECTED = {
    "SCHEMA", "ROOT_CHECK", "KMJSTAGE_UID", "SHARED_KIND",
    "SHARED_IS_SYMLINK", "SHARED_IS_DIRECTORY", "SHARED_UID",
    "SHARED_GID", "SHARED_MODE", "SHARED_OWNER_IS_KMJSTAGE",
    "SHARED_RESOLVED_SCOPE", "SHARED_PARENT_KIND", "SHARED_PARENT_UID",
    "OLD_UPLOAD_SCOPE", "OLD_UPLOAD_KIND", "PRODUCTION_POINTER",
    "CUSTOMER_FILES_MODIFIED", "STAGING_POINTER_MODIFIED",
    "PRODUCTION_MODIFIED", "OWNERSHIP_OR_PERMISSIONS_MODIFIED",
}


def blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "staging_switch_authorized": False,
        "production_activation_authorized": False,
        "shared_root_mutation_authorized": False,
        "requires_owner_review": True,
    }


def parse(raw: str) -> dict[str, str]:
    if not raw or len(raw.encode("utf-8")) > 8192 or "\x00" in raw:
        raise ValueError("INVALID_SIZE")
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or "=" not in line:
            raise ValueError("INVALID_LINE")
        key, value = line.split("=", 1)
        if (key not in EXPECTED or key in fields or not value or
                any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
            raise ValueError("INVALID_FIELD")
        fields[key] = value
    if set(fields) != EXPECTED:
        raise ValueError("INCOMPLETE_FIELDS")
    return fields


def evaluate(raw: str) -> dict[str, object]:
    try:
        f = parse(raw)
        if f["SCHEMA"] != "KMJ_STAGE_SHARED_ROOT_V3":
            return blocked("WRONG_SCHEMA")
        if (f["PRODUCTION_POINTER"] != "UNCHANGED" or
                any(f[k] != "NO" for k in (
                    "CUSTOMER_FILES_MODIFIED", "STAGING_POINTER_MODIFIED",
                    "PRODUCTION_MODIFIED", "OWNERSHIP_OR_PERMISSIONS_MODIFIED"
                ))):
            return blocked("READ_ONLY_OR_PRODUCTION_DRIFT")
        if (f["SHARED_KIND"] != "directory" or
                f["SHARED_IS_SYMLINK"] != "NO" or
                f["SHARED_IS_DIRECTORY"] != "YES" or
                f["SHARED_RESOLVED_SCOPE"] != "EXACT" or
                f["SHARED_PARENT_KIND"] != "directory"):
            return blocked("UNTRUSTED_SHARED_PATH")
        for key in ("KMJSTAGE_UID", "SHARED_UID", "SHARED_GID",
                    "SHARED_PARENT_UID"):
            if not re.fullmatch(r"[0-9]{1,10}", f[key]):
                return blocked("INVALID_IDENTITY")
        if not re.fullmatch(r"[0-7]{3,4}", f["SHARED_MODE"]):
            return blocked("INVALID_MODE")
        mode = int(f["SHARED_MODE"], 8)
        if mode & 0o022:
            return blocked("SHARED_ROOT_GROUP_OR_WORLD_WRITABLE")
        stage_uid = int(f["KMJSTAGE_UID"])
        shared_uid = int(f["SHARED_UID"])
        parent_uid = int(f["SHARED_PARENT_UID"])
        if f["SHARED_OWNER_IS_KMJSTAGE"] != (
            "YES" if shared_uid == stage_uid else "NO"
        ):
            return blocked("OWNER_FIELD_CONTRADICTION")
        if shared_uid not in (0, stage_uid):
            return blocked("UNEXPECTED_SHARED_ROOT_OWNER")
        if shared_uid == stage_uid:
            return blocked("UNPRIVILEGED_SHARED_ROOT_NEEDS_REVIEW")
        # Root-owned 0755 is NOT evidence that its parent prevents renames.
        # V3 does not attest the parent's mode/sticky bit or mount identity.
        if parent_uid != 0:
            return blocked("PARENT_MUTABILITY_NOT_ATTESTED")
        if f["OLD_UPLOAD_SCOPE"] == "RELEASE_BOUND":
            return blocked("RELEASE_BOUND_UPLOADS_REQUIRE_LOSSLESS_MIGRATION")
        return blocked("FULL_INVENTORY_BACKUP_AND_OWNER_QA_PENDING")
    except (ValueError, UnicodeError):
        return blocked("INVALID_OR_MISSING_RECEIPT")


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps(blocked("RECEIPT_ARGUMENT_REQUIRED"), sort_keys=True))
        return 2
    try:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raw = ""
    print(json.dumps(evaluate(raw), sort_keys=True))
    return 2  # Always fail closed. Never use as a release admission signal.


if __name__ == "__main__":
    raise SystemExit(main())
