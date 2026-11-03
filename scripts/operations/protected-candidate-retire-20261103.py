#!/usr/bin/env python3
"""Fail-closed created-inode retirement via a ROOT-ONLY protected quarantine.

Integration candidate for PR #777. A writable candidate directory cannot host
the verified-but-not-yet-unlinked temporary pathname: another kmjprod process
can replace it. Only unlink AFTER atomic rename into a trusted root-only
directory on the SAME filesystem. Never execute this file as root from a
writable source tree; owner installation must pin and attest reviewed bytes.
No network, backup, service, approval, or production-pointer operations.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat

MAX_ENV_BYTES = 1 << 20
INODE = re.compile(r"[1-9][0-9]*:[1-9][0-9]*\Z")
KINDS = {"env": (".env", "f"), "storage": ("storage", "l")}


class Blocked(Exception):
    pass


def _ident(info: os.stat_result) -> str:
    return f"{info.st_dev}:{info.st_ino}"


def _validated_quarantine(qfd: int, source_fd: int, *, trusted_uid: int = 0) -> None:
    """The calling root wrapper must ALSO attest /root and every ancestor."""
    q = os.fstat(qfd)
    source = os.fstat(source_fd)
    if (not stat.S_ISDIR(q.st_mode) or q.st_uid != trusted_uid
            or stat.S_IMODE(q.st_mode) != 0o700
            or q.st_dev != source.st_dev):
        raise Blocked("PRIVATE_QUARANTINE_NOT_TRUSTED_OR_DIFFERENT_FILESYSTEM")


def _source_digest(handle: int) -> tuple[bytes, os.stat_result] | None:
    before = os.fstat(handle)
    if (not stat.S_ISREG(before.st_mode) or before.st_size < 1
            or before.st_size > MAX_ENV_BYTES):
        return None
    digest = hashlib.sha256()
    remaining = MAX_ENV_BYTES + 1
    while remaining > 0:
        data = os.read(handle, min(65536, remaining))
        if not data:
            break
        remaining -= len(data)
        digest.update(data)
    if remaining == 0:
        return None
    after = os.fstat(handle)
    stamp = lambda item: (
        item.st_dev, item.st_ino, item.st_size,
        item.st_mtime_ns, item.st_ctime_ns,
    )
    return (digest.digest(), after) if stamp(before) == stamp(after) else None


def _parked_is_ours(qfd: int, name: str, expected: str, kind: str,
                    live_fd: int | None, *, created_uid: int) -> bool:
    """qfd is protected against unprivileged pathname replacement."""
    try:
        observed = os.stat(name, dir_fd=qfd, follow_symlinks=False)
        if _ident(observed) != expected:
            return False
        if kind == "l":
            if (not stat.S_ISLNK(observed.st_mode)
                    or observed.st_uid != created_uid
                    or observed.st_nlink != 1):
                return False
            if os.readlink(name, dir_fd=qfd) != "../storage/app/public":
                return False
            again = os.stat(name, dir_fd=qfd, follow_symlinks=False)
            return (stat.S_ISLNK(again.st_mode)
                    and _ident(again) == expected
                    and again.st_ctime_ns == observed.st_ctime_ns)
        if kind != "f" or live_fd is None:
            return False
        with_owned = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=qfd)
        try:
            candidate = os.fstat(with_owned)
            if (not stat.S_ISREG(candidate.st_mode)
                    or candidate.st_uid != created_uid
                    or candidate.st_nlink != 1
                    or stat.S_IMODE(candidate.st_mode) != 0o600
                    or _ident(candidate) != expected):
                return False
            content = _source_digest(with_owned)
            source = os.open(".env", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=live_fd)
            try:
                baseline = _source_digest(source)
            finally:
                os.close(source)
            if content is None or baseline is None or content[0] != baseline[0]:
                return False
            fresh = os.stat(name, dir_fd=qfd, follow_symlinks=False)
            return (stat.S_ISREG(fresh.st_mode)
                    and _ident(fresh) == expected
                    and fresh.st_size == candidate.st_size
                    and fresh.st_mtime_ns == candidate.st_mtime_ns
                    and fresh.st_ctime_ns == candidate.st_ctime_ns)
        finally:
            os.close(with_owned)
    except OSError:
        return False


def retire_created(source_fd: int, quarantine_fd: int, *, name: str,
                   expected_inode: str, kind: str, created_uid: int,
                   live_fd: int | None = None, trusted_uid: int = 0) -> str:
    """Root wrapper supplies fixed descriptor-opened candidate and /root qdir.

    The only os.unlink targets the trusted qdir; never the writable candidate.
    If the candidate name swaps before rename, the foreign inode is parked but
    never deleted; owner reviews the protected quarantine manually.
    """
    if (name, kind) not in KINDS.values() or not INODE.fullmatch(expected_inode):
        raise Blocked("UNTRUSTED_FIXED_NAME_OR_INODE")
    _validated_quarantine(quarantine_fd, source_fd, trusted_uid=trusted_uid)
    try:
        initial = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "ABSENT"
    if _ident(initial) != expected_inode:
        return "MISMATCH"
    if kind == "f" and not stat.S_ISREG(initial.st_mode):
        return "MISMATCH"
    if kind == "l" and not stat.S_ISLNK(initial.st_mode):
        return "MISMATCH"
    ticket = "kmj-protected-" + os.urandom(20).hex()
    # O_EXCL semantics: mkdir must create a NEW root-only ticket, and rename
    # never replaces a preexisting user-owned or previous-review object.
    os.mkdir(ticket, mode=0o700, dir_fd=quarantine_fd)
    ticket_fd = os.open(ticket, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=quarantine_fd)
    try:
        _validated_quarantine(ticket_fd, source_fd, trusted_uid=trusted_uid)
        try:
            os.rename(name, "object", src_dir_fd=source_fd, dst_dir_fd=ticket_fd)
        except FileNotFoundError:
            os.rmdir(ticket, dir_fd=quarantine_fd)
            return "ABSENT"
        if not _parked_is_ours(ticket_fd, "object", expected_inode, kind,
                              live_fd, created_uid=created_uid):
            return "QUARANTINED_OWNER_REVIEW"
        try:
            # The only unlink targets an inode under a root-owned private dir.
            os.unlink("object", dir_fd=ticket_fd)
            os.rmdir(ticket, dir_fd=quarantine_fd)
        except OSError:
            return "QUARANTINED_OWNER_REVIEW"
        return "REMOVED"
    finally:
        os.close(ticket_fd)


if __name__ == "__main__":
    # No arbitrary standalone root invocation. Owner-controlled wrapper must
    # supply preopened directory FDs and attest this code's immutable digest.
    print("KMJ_PROTECTED_RETIRE=LIBRARY_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
