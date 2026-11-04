#!/usr/bin/env python3
"""Owner-root, fail-closed private rollback-quarantine preparation on KMJ-elite.

Only authorized mutation: create the missing, root-owned 0700 directory
/var/lib/kmj-main-platform-rollback-quarantine, after attesting the exact
existing candidate's filesystem. Does not deploy, upload, delete, restart,
modify SSH credentials, edit approvals, or touch production.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import stat
import sys

CANDIDATE = "/home/kmjprod/releases/platform-a9796a25a280/apps/platform"
PRODUCTION_POINTER = "/home/kmjprod/current"
EXPECTED_LIVE = "/home/kmjprod/releases/platform-574e443a2c75"
QUARANTINE = "kmj-main-platform-rollback-quarantine"
STAGING_CANDIDATE = "/home/kmjstage/releases/a9796a25a2801cd303a69f5ad468aa9a704e5fff/apps/platform"
STAGING_SITE = "/home/kmjstage/htdocs/staging.kmjtechno.com"
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def status(label: str, value: str) -> None:
    print(f"{label}={value}", flush=True)


def block(code: str) -> None:
    status("KMJ_ROOT_QUARANTINE", "BLOCKED_" + code)
    raise SystemExit(2)


def anchored_directory(path: str, *, root_only: bool = False) -> int:
    """Traverse all components with openat O_NOFOLLOW; caller closes returned fd."""
    if not path.startswith("/") or "//" in path or any(x in (".", "..") for x in path.split("/")):
        block("PATH_INVALID")
    fd = os.open("/", DIR_FLAGS)
    try:
        root = os.fstat(fd)
        if not stat.S_ISDIR(root.st_mode):
            block("ROOT_INVALID")
        for part in filter(None, path.split("/")):
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            try:
                info = os.fstat(nxt)
                if not stat.S_ISDIR(info.st_mode):
                    block("COMPONENT_NOT_DIRECTORY")
                if root_only and (info.st_uid != 0 or info.st_mode & 0o022):
                    block("ROOT_PARENT_UNTRUSTED")
            except BaseException:
                os.close(nxt)
                raise
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def check_pointer(path: str, expected: str) -> None:
    try:
        if not stat.S_ISLNK(os.lstat(path).st_mode):
            block("PRODUCTION_POINTER_NOT_SYMLINK")
        actual = os.readlink(path)
        allowed = {expected, "releases/" + Path(expected).name}
        if actual not in allowed:
            block("PRODUCTION_POINTER_CHANGED")
    except OSError:
        block("PRODUCTION_POINTER_UNREADABLE")


def optional_stage() -> str:
    # Advisory only: absence must never emit a false blocked root receipt.
    try:
        item = os.lstat(STAGING_CANDIDATE)
    except OSError:
        return "NOT_ATTESTED"
    return "DIRECTORY_PRESENT_NOT_SEALED" if stat.S_ISDIR(item.st_mode) else "NOT_ATTESTED"


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        block("WRONG_HOST_ROOT_OR_ARGS")
    status("KMJ_ROOT_SCRIPT", "SHA_PINNED_PRIVATE_QUARANTINE_V2")
    check_pointer(PRODUCTION_POINTER, EXPECTED_LIVE)
    status("KMJ_PRODUCTION_RELEASE", "platform-574e443a2c75")
    try:
        candidate_fd = anchored_directory(CANDIDATE)
        parent_fd = anchored_directory("/var/lib", root_only=True)
    except OSError:
        block("CANDIDATE_OR_PARENT_NOT_PRESENT")
    try:
        candidate = os.fstat(candidate_fd)
        parent = os.fstat(parent_fd)
        if candidate.st_dev != parent.st_dev:
            block("CANDIDATE_CROSS_FILESYSTEM")
        status("KMJ_CANDIDATE_FILESYSTEM", "SAME_DEVICE_VERIFIED")
        try:
            os.mkdir(QUARANTINE, 0o700, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            created = False
        try:
            qfd = os.open(QUARANTINE, DIR_FLAGS, dir_fd=parent_fd)
        except OSError:
            block("QUARANTINE_NOT_TRUSTED")
        try:
            q = os.fstat(qfd)
            if (not stat.S_ISDIR(q.st_mode) or q.st_uid != 0
                    or stat.S_IMODE(q.st_mode) != 0o700 or q.st_dev != candidate.st_dev):
                block("QUARANTINE_OWNER_MODE_OR_DEVICE")
        finally:
            os.close(qfd)
        status("KMJ_ROOT_QUARANTINE", "PASS_CREATED" if created else "PASS_EXISTING")
        status("KMJ_STAGING_CANDIDATE", optional_stage())
        status("KMJ_LEGACY_OFFSITE_SERVICE", "UNTOUCHED")
        status("KMJ_STAGING_APPROVAL", "NOT_CHANGED")
        status("KMJ_PRODUCTION_POINTER", "UNCHANGED")
        status("KMJ_GOOGLE_RESTORE", "EXTERNAL_WITNESS_NOT_MODIFIED")
        status("KMJ_ROOT_PREPARATION", "PASS_QUARANTINE_ONLY")
        return 0
    finally:
        os.close(parent_fd)
        os.close(candidate_fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError:
        status("KMJ_ROOT_QUARANTINE", "BLOCKED_IO_ERROR")
        raise SystemExit(2)
