#!/usr/bin/env python3
"""Derive the migration-storage receipt from two already-protected receipts.

Owner-accepted definition (2026-11-22): migration-and-storage continuity is true only
when BOTH a valid rollback-rehearsal receipt (additive migration, code and schema
rollback on a disposable DB) AND a valid disposable-restore receipt (byte-verified
uploads restore) exist for the same SHA and predecessor. It inspects no live layout
and runs nothing. Not a live storage-link check.

  --check <sha> <expected-release> | --write <sha> <expected-release>
"""
import hashlib
import os
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402
import elite_collect_staging_origin_receipt as common  # noqa: E402

PARTS = ("rollback-rehearsal", "disposable-restore")


def derive(receipts, sha, expected, now):
    by_kind = {}
    for r in receipts:
        if isinstance(r, dict) and r.get("kind") in PARTS:
            if r["kind"] in by_kind:
                raise ValueError("DUPLICATE_PART")
            by_kind[r["kind"]] = r
    digest = hashlib.sha256()
    for kind in PARTS:
        r = by_kind.get(kind)
        if r is None or ra.receipt_problem(r, sha, expected, now) is not None:
            raise ValueError("PART_MISSING_OR_INVALID:" + kind)
        digest.update(kind.encode() + b"\0" + r["artifactSha256"].encode() + b"\0")
    return {"schema": ra.RECEIPT_SCHEMA, "kind": "migration-storage", "host": ra.HOST,
            "approvedSha": sha, "expectedCurrentRelease": expected, "capturedAt": int(now),
            "result": "pass", "artifactSha256": digest.hexdigest()}


def main(argv, directory=common.RECEIPT_DIR, uid=0):
    if len(argv) != 4 or argv[1] not in ("--check", "--write"):
        print("usage: --check|--write <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("MIGRATION_STORAGE_RECEIPT=BLOCKED_INPUT")
        return 2
    if argv[1] == "--write" and (os.geteuid() != 0
                                 or socket.gethostname().split(".")[0] != "KMJ-elite"):
        print("MIGRATION_STORAGE_RECEIPT=BLOCKED_OPERATOR_HOST")
        return 2
    try:
        receipt = derive(store.load_receipts(directory, sha, uid), sha, expected, time.time())
        if argv[1] == "--write":
            common.write_receipt(receipt, directory, uid)
    except (OSError, ValueError) as exc:
        print("MIGRATION_STORAGE_RECEIPT=FAIL REASON=" + type(exc).__name__)
        return 1
    print("MIGRATION_STORAGE_RECEIPT=PASS WRITTEN=" + ("YES" if argv[1] == "--write" else "NO"))
    print("PRODUCTION_RELEASE=NOT_ATTEMPTED ADMISSION_WRITTEN=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
