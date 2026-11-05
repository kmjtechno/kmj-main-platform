#!/usr/bin/env python3
"""One-directory owner-only correction for KMJ staging releases, fail closed.

MAY change ONLY the UID of /home/kmjstage/releases from kmjstage to root.
Never recursively change ownership, modify permissions, follow links, or change a
stage/production pointer. Do not use when the stage home ancestry is
kmjstage-owned/writable: in that case an owning stage user could rename the
entire releases directory, defeating a root-owned releases inode.
"""
from __future__ import annotations
import os
import pwd
import socket
import stat
import sys

ROOT = "/"
RELEASES = "/home/kmjstage/releases"
STAGE_LINK = "/home/kmjstage/htdocs/staging.kmjtechno.com"
PROD_LINK = "/home/kmjprod/current"
OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD = "platform-574e443a2c75"
FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def say(k: str, v: str) -> None:
    print(f"{k}={v}", flush=True)


def stop(reason: str) -> None:
    say("KMJ_STAGE_PARENT_FIX", "BLOCKED_" + reason)
    raise SystemExit(2)


def trusted_chain() -> tuple[int, int]:
    # Open each trusted ancestor through a directory FD, never follow a link.
    fd = os.open(ROOT, FLAGS)
    try:
        for part in ("home", "kmjstage"):
            current = os.fstat(fd)
            if not stat.S_ISDIR(current.st_mode) or current.st_uid != 0 or current.st_mode & 0o022:
                stop("ANCESTOR_UNTRUSTED")
            child = os.open(part, FLAGS, dir_fd=fd)
            info = os.fstat(child)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or info.st_mode & 0o022):
                os.close(child)
                stop("HOME_ANCESTOR_USER_OWNED_OR_WRITABLE")
            os.close(fd)
            fd = child
        child = os.open("releases", FLAGS, dir_fd=fd)
        return fd, child
    except BaseException:
        os.close(fd)
        raise


def pointer(path: str, allowed: set[str]) -> str:
    try:
        if not stat.S_ISLNK(os.lstat(path).st_mode):
            return "UNTRUSTED"
        return "EXPECTED" if os.readlink(path) in allowed else "DRIFT"
    except OSError:
        return "MISSING"


def extended_acl(fd: int) -> bool:
    # An ACL may still authorize a stage user after plain mode bits look safe.
    for name in os.listxattr(fd):
        if name in ("system.posix_acl_access", "system.posix_acl_default"):
            return True
    return False


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        stop("WRONG_HOST_ROOT_OR_ARGS")
    stage_expected = {
        f"/home/kmjstage/releases/{OLD}/apps/platform",
        f"../releases/{OLD}/apps/platform",
    }
    prod_expected = {f"/home/kmjprod/releases/{PROD}", f"releases/{PROD}"}
    if pointer(PROD_LINK, prod_expected) != "EXPECTED":
        stop("PRODUCTION_POINTER_DRIFT")
    if pointer(STAGE_LINK, stage_expected) != "EXPECTED":
        stop("STAGING_POINTER_DRIFT")
    stage_uid = pwd.getpwnam("kmjstage").pw_uid
    homefd = releasefd = None
    try:
        homefd, releasefd = trusted_chain()
        before = os.fstat(releasefd)
        at_name = os.stat("releases", dir_fd=homefd, follow_symlinks=False)
        if ((before.st_dev, before.st_ino) != (at_name.st_dev, at_name.st_ino)
                or not stat.S_ISDIR(before.st_mode) or
                before.st_uid not in (0, stage_uid) or
                stat.S_IMODE(before.st_mode) != 0o755):
            stop("RELEASES_METADATA_UNEXPECTED")
        if extended_acl(releasefd):
            stop("RELEASES_EXTENDED_ACL")
        say("KMJ_STAGE_PARENT_PREVIOUS_OWNER", "ROOT" if before.st_uid == 0 else "KMJSTAGE")
        if before.st_uid != 0:
            # Correct only the directory inode, keep group/mode/children
            # unchanged. Never recurse into live staging releases.
            os.fchown(releasefd, 0, -1)
        now = os.fstat(releasefd)
        at_name = os.stat("releases", dir_fd=homefd, follow_symlinks=False)
        if ((now.st_dev, now.st_ino) != (at_name.st_dev, at_name.st_ino)
                or now.st_uid != 0 or stat.S_IMODE(now.st_mode) != 0o755):
            stop("OWNERSHIP_READBACK_FAILED")
        if pointer(PROD_LINK, prod_expected) != "EXPECTED":
            stop("PRODUCTION_POINTER_CHANGED")
        if pointer(STAGE_LINK, stage_expected) != "EXPECTED":
            stop("STAGING_POINTER_CHANGED")
        say("KMJ_STAGE_RELEASES_PARENT", "ROOT_OWNER_0755_VERIFIED")
        say("KMJ_STAGE_PARENT_FIX", "PASS_ALREADY_ROOT" if before.st_uid == 0 else "PASS_OWNER_CORRECTED")
        say("KMJ_STAGE_CHILDREN_CHANGED", "NO")
        say("KMJ_STAGING_POINTER", "UNCHANGED")
        say("KMJ_PRODUCTION_POINTER", "UNCHANGED")
        say("KMJ_STAGE_SOURCE_BUILD", "NOT_ATTEMPTED")
        return 0
    finally:
        if releasefd is not None:
            os.close(releasefd)
        if homefd is not None:
            os.close(homefd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError):
        say("KMJ_STAGE_PARENT_FIX", "BLOCKED_FILESYSTEM_OR_ACCOUNT")
        raise SystemExit(2)
