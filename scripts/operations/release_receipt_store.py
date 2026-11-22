#!/usr/bin/env python3
"""Strict reader for root-protected evidence receipts (source only, read-only).

One receipt per kind and candidate: <dir>/<kind>-<sha12>.json. Each file must be a
single-link regular file owned by the trusted uid, mode 0600-or-stricter, in a
directory owned by that uid and not group/other writable. Symlinks are refused.
The trusted uid is 0 in production; tests pass their own uid. This module never
writes a file and never creates an admission.
"""
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main_platform_autopublish_gate as gate  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

MAX_BYTES = 4096


def read_protected(path, trusted_uid=0):
    """Return parsed JSON or None. Never follows a symlink; fails closed."""
    try:
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != trusted_uid
                or stat.S_IMODE(parent.st_mode) & 0o022):
            return None
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != trusted_uid
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077
                    or not 2 <= info.st_size <= MAX_BYTES):
                return None
            data = os.read(fd, MAX_BYTES + 1)
            after = os.fstat(fd)
            if (len(data) != info.st_size or after.st_size != info.st_size
                    or after.st_mtime_ns != info.st_mtime_ns):
                return None
            return gate.parse_protected_json(data)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError):
        return None


def load_receipts(directory, sha, trusted_uid=0):
    """Read every expected receipt for this candidate; unreadable ones are skipped."""
    directory = Path(directory)
    receipts = []
    for kind in ra.KIND_TO_FLAG:
        data = read_protected(directory / "{}-{}.json".format(kind, sha[:12]), trusted_uid)
        if data is not None:
            receipts.append(data)
    return receipts


def evaluate(directory, sha, expected, owner_authorized, now, trusted_uid=0):
    """Return (admission_or_None, blockers). Pure decision; writes nothing."""
    if not isinstance(sha, str) or not ra.SHA_RE.fullmatch(sha):
        return None, ["INPUT_IDENTITY"]
    return ra.build_admission(load_receipts(directory, sha, trusted_uid),
                              sha, expected, owner_authorized, now)
