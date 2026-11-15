#!/usr/bin/env python3
"""KMJ staging root-owned release ANCHOR bootstrap, never activation.

Only allowed mutation: create the missing root:root 0700 directory at
/var/lib/kmj-main-platform-stage-releases. Refuses untrusted ancestors,
ACLs, links, pointer drift or unexpected pre-existing content. No recursion,
root ownership changes, production or staging service/control changes.
The private anchor CANNOT serve traffic until separately reviewed root
owned staging vhost + release runner/owner seal are installed and approved.
"""
from __future__ import annotations

import errno
import os
import pwd
import socket
import stat
import sys
from pathlib import Path

PARENT = "/var/lib"
NAME = "kmj-main-platform-stage-releases"
ANCHOR = PARENT + "/" + NAME
STAGE_HOME = "/home/kmjstage"
STAGE_RELEASES = STAGE_HOME + "/releases"
STAGE_SITE = STAGE_HOME + "/htdocs/staging.kmjtechno.com"
EXACT_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_SITE = "/home/kmjprod/current"
PROD_RELEASE = "platform-574e443a2c75"
NEW_SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def emit(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def deny(code: str) -> None:
    emit("KMJ_ROOT_STAGE_ANCHOR", "BLOCKED_" + code)
    raise SystemExit(2)


def exact_link(path: str, allowed: tuple[str, ...]) -> bool:
    try:
        meta = os.lstat(path)
        return stat.S_ISLNK(meta.st_mode) and os.readlink(path) in allowed
    except OSError:
        return False


def root_parent_fd() -> int:
    fd = os.open("/", FLAGS)
    try:
        for component in ("var", "lib"):
            st = os.fstat(fd)
            if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0
                    or st.st_mode & 0o022):
                deny("ROOT_ANCESTOR_UNTRUSTED")
            next_fd = os.open(component, FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            deny("ROOT_PARENT_UNTRUSTED")
        names = os.listxattr(fd)
        if any(x in ("system.posix_acl_access", "system.posix_acl_default") for x in names):
            deny("ROOT_PARENT_ACL")
        return fd
    except BaseException:
        os.close(fd)
        raise


def anchor_fd(fd: int) -> tuple[int, bool]:
    created = False
    try:
        os.mkdir(NAME, mode=0o700, dir_fd=fd)
        created = True
    except FileExistsError:
        pass
    child = os.open(NAME, FLAGS, dir_fd=fd)
    st = os.fstat(child)
    named = os.stat(NAME, dir_fd=fd, follow_symlinks=False)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0
            or stat.S_IMODE(st.st_mode) != 0o700
            or st.st_dev != named.st_dev or st.st_ino != named.st_ino):
        os.close(child)
        deny("ANCHOR_UNTRUSTED")
    if any(x in ("system.posix_acl_access", "system.posix_acl_default") for x in os.listxattr(child)):
        os.close(child)
        deny("ANCHOR_ACL")
    return child, created


def stage_home_scope(stage_uid: int) -> bool:
    for path, mode in ((STAGE_HOME, 0o750), (STAGE_RELEASES, 0o750)):
        info = os.lstat(path)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != stage_uid
                or stat.S_IMODE(info.st_mode) != mode):
            return False
    return True


def stage_expected() -> bool:
    return exact_link(STAGE_SITE, (
        f"/home/kmjstage/releases/{EXACT_STAGE}/apps/platform",
        f"../releases/{EXACT_STAGE}/apps/platform",
    ))


def prod_expected() -> bool:
    return exact_link(PROD_SITE, (
        f"/home/kmjprod/releases/{PROD_RELEASE}",
        f"releases/{PROD_RELEASE}",
    ))


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        deny("ROOT_HOST_ARGS")
    stage_uid = pwd.getpwnam("kmjstage").pw_uid
    if not prod_expected() or not stage_expected():
        deny("CURRENT_RELEASE_POINTER_DRIFT")
    if not stage_home_scope(stage_uid):
        deny("STAGE_HOME_SCOPE_CHANGED")
    fd = -1
    child = -1
    try:
        fd = root_parent_fd()
        child, created = anchor_fd(fd)
        if not prod_expected() or not stage_expected():
            deny("POST_CREATE_RELEASE_POINTER_DRIFT")
        if not stage_home_scope(stage_uid):
            deny("POST_CREATE_STAGE_HOME_DRIFT")
        emit("KMJ_ROOT_STAGE_ANCHOR", "PASS_CREATED" if created else "PASS_EXISTING")
        emit("KMJ_ROOT_STAGE_ANCHOR_MODE", "ROOT_ONLY_0700")
        emit("KMJ_ROOT_STAGE_RELEASE_CANDIDATE", "NOT_PREPARED")
        emit("KMJ_ROOT_STAGE_WEB_SERVING", "NOT_CONFIGURED")
        emit("KMJ_STAGE_HOME_OWNER", "KMJSTAGE_UNCHANGED")
        emit("KMJ_STAGING_POINTER", "UNCHANGED")
        emit("KMJ_PRODUCTION_POINTER", "UNCHANGED")
        emit("KMJ_STAGING_APPROVAL", "NOT_MODIFIED")
        emit("KMJ_OFFSITE_BACKUP_SERVICE", "NOT_MODIFIED")
        emit("KMJ_ROOT_STAGE_ANCHOR_PREP", "PASS_PRIVATE_DIRECTORY_ONLY")
        return 0
    finally:
        if child >= 0:
            os.close(child)
        if fd >= 0:
            os.close(fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError):
        emit("KMJ_ROOT_STAGE_ANCHOR", "BLOCKED_IO_OR_STAGE_USER")
        raise SystemExit(2)
