#!/usr/bin/env python3
"""Pure, fail-closed mapping from evidence receipts to the gate admission file.

Source only. This module reads nothing, writes nothing and runs nothing. A fixed
root broker (a later, separately reviewed slice) feeds it receipts that a fixed
root collector produced. The admission flags are derived ONLY from fresh,
exact-SHA, passing receipts; no caller can set a flag directly.
"""
import re

SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
RELEASE_RE = re.compile(r"platform-[0-9a-f]{12}\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT_SCHEMA = "kmj.release.evidence-receipt.v1"
ADMISSION_SCHEMA = "kmj.autopublish.release-admission.elite-local.v2"
HOST = "kmj-elite"
MAX_AGE_SECONDS = 4 * 3600
MAX_FUTURE_SKEW_SECONDS = 60

# receipt kind -> admission flag it alone may justify
KIND_TO_FLAG = {
    "staging-origin": "stagingExactShaPass",
    "authenticated-qa": "ownerAuthenticatedQaPass",
    "public-qa": "publicOriginQaPass",
    "backup-witness": "eliteBackupWitnessShaPass",
    "disposable-restore": "eliteDisposablePgUploadsRestorePass",
    "rollback-rehearsal": "rollbackRehearsalPass",
    "migration-storage": "migrationAndStorageContinuityPass",
}
RECEIPT_KEYS = {
    "schema", "kind", "host", "approvedSha", "expectedCurrentRelease",
    "capturedAt", "result", "artifactSha256",
}


def receipt_problem(receipt, sha, expected, now):
    """Return None when the receipt is acceptable, else a stable reason code."""
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        return "RECEIPT_SCHEMA"
    if receipt["schema"] != RECEIPT_SCHEMA or receipt["kind"] not in KIND_TO_FLAG:
        return "RECEIPT_SCHEMA"
    if receipt["host"] != HOST:
        return "RECEIPT_HOST"
    if receipt["approvedSha"] != sha or receipt["expectedCurrentRelease"] != expected:
        return "RECEIPT_IDENTITY"
    digest = receipt["artifactSha256"]
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        return "RECEIPT_ARTIFACT"
    captured = receipt["capturedAt"]
    if isinstance(captured, bool) or not isinstance(captured, int):
        return "RECEIPT_TIME"
    if captured > now + MAX_FUTURE_SKEW_SECONDS or now - captured > MAX_AGE_SECONDS:
        return "RECEIPT_STALE"
    if receipt["result"] != "pass":
        return "RECEIPT_NOT_PASS"
    return None


def build_admission(receipts, sha, expected, owner_authorized, now):
    """Return (admission_or_None, blockers). Admission only if every flag is proven."""
    if (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
            or not isinstance(expected, str) or not RELEASE_RE.fullmatch(expected)
            or isinstance(now, bool) or not isinstance(now, int)):
        return None, ["INPUT_IDENTITY"]
    blockers = []
    proven = {}
    seen = set()
    for receipt in receipts if isinstance(receipts, list) else []:
        kind = receipt.get("kind") if isinstance(receipt, dict) else None
        if kind in seen:
            blockers.append("RECEIPT_DUPLICATE:" + str(kind))
            continue
        seen.add(kind)
        problem = receipt_problem(receipt, sha, expected, now)
        if problem:
            blockers.append(problem + ":" + str(kind))
        else:
            proven[KIND_TO_FLAG[kind]] = True
    for kind, flag in KIND_TO_FLAG.items():
        if flag not in proven and not any(b.endswith(":" + kind) for b in blockers):
            blockers.append("RECEIPT_MISSING:" + kind)
    if owner_authorized is not True:
        blockers.append("OWNER_AUTHORIZATION_MISSING")
    if blockers:
        return None, sorted(set(blockers))
    admission = {
        "schema": ADMISSION_SCHEMA,
        "approvedSha": sha,
        "expectedCurrentRelease": expected,
        "stagingSha": sha,
        "standingOwnerAuthorization": True,
    }
    admission.update({flag: True for flag in KIND_TO_FLAG.values()})
    return admission, []
