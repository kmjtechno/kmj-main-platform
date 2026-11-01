#!/usr/bin/env python3
"""Offline, strict verifier for the offsite backup -> SFTP -> Google restore witness chain.

Inputs are the three sanitized KEY=VALUE receipts produced by the reviewed scripts
(seal-main-platform-offsite-20261030.py, push-offsite-pinned-sftp-20261030.sh,
verify-main-platform-google-sftp-restore-20261030.sh) plus the values the operator
and reviewer expect (candidate SHA, release, ciphertext SHA, source SHA).

It performs no network, subprocess, key, config or journal access and writes nothing.
Each receipt must be a regular, non-symlink file whose SHA-256 equals a digest recorded
through an independent channel (e.g. mailbox), so a receipt edited afterwards is rejected.
That is tamper evidence, not cryptographic authorship: the output says so
(PROVENANCE=OPERATOR_REPORTED_DIGEST_BOUND) and never grants release authority.

Result is only ever PARTIAL_PASS or BLOCKED. App QA, SMTP, owner sign-off, matching
production approval and remote retention stay NOT_VERIFIED by construction.
"""
from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
import sys
from pathlib import Path

MAX_BYTES = 16384
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
RELEASE = re.compile(r"platform-[0-9a-f]{12}\Z")
LINE = re.compile(r"([A-Z][A-Z0-9_]{1,80})=([A-Za-z0-9_.:+-]{1,128})\Z")

SEAL = {
    "SOURCE_WITNESS": "PASS", "SOURCE_LOCAL_SHA256": HEX64, "ENV_EXCLUDED_FROM_OFFSITE_COPY": "PASS",
    "ENCRYPTED_OFFSITE_BUNDLE": "PASS", "ENCRYPTED_SHA256": HEX64, "ENCRYPTED_BYTES": re.compile(r"[1-9][0-9]{0,12}\Z"),
    "OFFSITE_TRANSFER": "NOT_ATTEMPTED", "PRODUCTION_RELEASE": "UNCHANGED", "PRODUCTION_DB": "UNTOUCHED",
}
PUSH = {
    "HOSTKEY_PIN": "PASS", "LOCAL_ENCRYPTED_SHA256": HEX64, "REMOTE_CAPABILITY_PROBE": "PASS",
    "SFTP_UPLOAD": "PASS", "REMOTE_COMMIT_NO_CLOBBER": "PASS", "REMOTE_READBACK_MODE_0600": "PASS",
    "REMOTE_READBACK_SHA256": "PASS", "OFFSITE_PUSH": "PASS", "OFFSITE_RESTORE": "NOT_VERIFIED",
    "PRODUCTION_CHANGED": "NO",
}
PUSH_OPTIONAL = {"REMOTE_COMMIT_NO_CLOBBER": {"PASS", "TARGET_EXISTS_OR_FAILED"}}
RESTORE = {
    "SFTP_IMPORTED_ENCRYPTED_SHA256": "PASS", "SFTP_IMPORT_COPY": "PASS", "OFFSITE_RCLONE_RETRIEVAL": "NOT_ATTEMPTED",
    "BACKUP_ARCHIVE_INTEGRITY": "PASS", "BUNDLE_METADATA_BINDING": "PASS", "DATABASE_PHASE_OS_SANDBOX": "PASS",
    "STORAGE_EXTRACTION_CAPACITY": "PASS", "STORAGE_EXTRACTION_PARITY_CONTENT_SHA256": "PASS",
    "STORAGE_REGULAR_FILES": re.compile(r"[0-9]{1,9}\Z"), "STORAGE_BYTES": re.compile(r"[0-9]{1,15}\Z"),
    "DISPOSABLE_POSTGRES_RESTORE": "PASS", "RECOVERED_APP_SCHEMA": "PASS", "RECOVERED_STORAGE": "PASS",
    "POSTGRES_NETWORK_LISTENER": "DISABLED", "PRODUCTION_DATABASE_MODIFIED": "NO",
    "RECOVERED_APP_FUNCTIONAL_QA": "NOT_VERIFIED", "SMTP_INBOX_DELIVERY": "NOT_VERIFIED",
    "OWNER_VISUAL_SIGNOFF": "NOT_VERIFIED", "MATCHING_PRODUCTION_APPROVAL": "NOT_VERIFIED",
    "SAFE_TO_ACTIVATE_PRODUCTION": "NOT_PROVEN", "GOOGLE_VPS_INDEPENDENT_RESTORE": "PASS",
    "OFFSITE_REMOTE_ARCHIVE_RETENTION": "NOT_VERIFIED", "RESTORE_CANDIDATE_SHA": HEX40,
}


class Block(Exception):
    pass


def parse(text: str, spec: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if raw != raw.strip():
            raise Block("NONCANONICAL_LINE")
        line = raw
        if not line:
            continue
        match = LINE.fullmatch(line)
        if match is None:
            raise Block("MALFORMED_LINE")
        key, value = match.groups()
        if key not in spec:
            raise Block("UNKNOWN_KEY")
        if key in values:
            raise Block("DUPLICATE_KEY")
        allowed = PUSH_OPTIONAL.get(key) if spec is PUSH else None
        want = spec[key]
        ok = (value in allowed) if allowed else (value == want if isinstance(want, str) else want.fullmatch(value) is not None)
        if not ok:
            raise Block("BAD_VALUE")
        values[key] = value
    if set(values) != set(spec):
        raise Block("MISSING_KEY")
    return values


def load(arg: str) -> str:
    name, _, digest = arg.rpartition(":")
    if not name or not HEX64.fullmatch(digest):
        raise Block("RECEIPT_ARGUMENT")
    path = Path(name)
    # Open the exact inode once, with no-follow and nonblocking semantics.
    # path.is_file()/stat()/read_bytes() has a substitution window and can
    # open a raced symlink or wait indefinitely on a FIFO.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EISDIR):
            raise Block("RECEIPT_FILE") from None
        raise
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise Block("RECEIPT_FILE")
        data = os.read(fd, MAX_BYTES + 1)
        after = os.fstat(fd)
        if len(data) > MAX_BYTES or (before.st_dev, before.st_ino, before.st_size,
                                    before.st_mtime_ns, before.st_ctime_ns) != (
                                        after.st_dev, after.st_ino, after.st_size,
                                        after.st_mtime_ns, after.st_ctime_ns):
            raise Block("RECEIPT_FILE_CHANGED")
    finally:
        os.close(fd)
    if hashlib.sha256(data).hexdigest() != digest:
        raise Block("RECEIPT_DIGEST_MISMATCH")
    try:
        return data.decode("ascii")
    except UnicodeDecodeError:
        raise Block("RECEIPT_NOT_ASCII") from None


def verify(seal: str, push: str, restore: str, *, candidate: str, release: str,
           encrypted: str, source: str, min_files: int) -> dict[str, str]:
    if not (HEX40.fullmatch(candidate) and RELEASE.fullmatch(release) and HEX64.fullmatch(encrypted)
            and HEX64.fullmatch(source) and 1 <= min_files <= 10**9):
        raise Block("EXPECTATION_INVALID")
    if release != "platform-" + candidate[:12]:
        raise Block("RELEASE_CANDIDATE_MISMATCH")
    s, p, r = parse(seal, SEAL), parse(push, PUSH), parse(restore, RESTORE)
    if s["ENCRYPTED_SHA256"] != encrypted or p["LOCAL_ENCRYPTED_SHA256"] != encrypted:
        raise Block("ENCRYPTED_SHA_UNBOUND")
    if s["SOURCE_LOCAL_SHA256"] != source:
        raise Block("SOURCE_SHA_UNBOUND")
    if r["RESTORE_CANDIDATE_SHA"] != candidate:
        raise Block("CANDIDATE_UNBOUND")
    if int(r["STORAGE_REGULAR_FILES"]) < min_files:
        raise Block("UPLOAD_COVERAGE_BELOW_EXPECTED")
    return {
        "WITNESS": "PARTIAL_PASS", "PROVENANCE": "OPERATOR_REPORTED_DIGEST_BOUND",
        "CANDIDATE_SHA": candidate, "ENCRYPTED_SHA256": encrypted, "SOURCE_LOCAL_SHA256": source,
        "REMOTE_READBACK_MODE_0600": "PASS", "INDEPENDENT_RESTORE": "PASS",
        "RESTORED_REGULAR_FILES": r["STORAGE_REGULAR_FILES"],
        "RELEASE_AUTHORITY": "NO", "PRODUCTION_SWITCH_ALLOWED": "NO",
        "NOT_VERIFIED": "APP_QA,SMTP,OWNER_SIGNOFF,PRODUCTION_APPROVAL,REMOTE_RETENTION",
    }


def main(argv: list[str]) -> int:
    opts: dict[str, str] = {}
    keys = ("--candidate-sha", "--expected-release", "--encrypted-sha256", "--source-local-sha256",
            "--min-storage-files", "--seal", "--push", "--restore")
    args = argv[1:]
    if len(args) != 2 * len(keys):
        print("WITNESS=BLOCKED USAGE")
        return 2
    for key, value in zip(args[0::2], args[1::2]):
        if key not in keys or key in opts:
            print("WITNESS=BLOCKED USAGE")
            return 2
        opts[key] = value
    try:
        if not opts["--min-storage-files"].isdigit():
            raise Block("EXPECTATION_INVALID")
        result = verify(load(opts["--seal"]), load(opts["--push"]), load(opts["--restore"]),
                        candidate=opts["--candidate-sha"], release=opts["--expected-release"],
                        encrypted=opts["--encrypted-sha256"], source=opts["--source-local-sha256"],
                        min_files=int(opts["--min-storage-files"]))
    except (Block, OSError) as exc:
        print("WITNESS=BLOCKED " + (str(exc) if isinstance(exc, Block) else "IO_ERROR"))
        return 2
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
