#!/usr/bin/env python3
"""KMJ-elite fixed-path staging home/anchor trust audit.

Read-only: metadata only. No file contents, no traversal of stage user files,
no subprocess, no networking, chmod, chown, service control or release switch.
This is advisory evidence and NEVER approves staging or production.
"""
from __future__ import annotations

import os
import pwd
import socket
import stat
import sys
from pathlib import Path

CANDIDATE = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_RELEASE = "platform-574e443a2c75"
STAGE_BASE = Path("/home/kmjstage")
RELEASES = STAGE_BASE / "releases"
STAGE_WEB = STAGE_BASE / "htdocs"
STAGE_LINK = STAGE_WEB / "staging.kmjtechno.com"
STAGE_PREVIOUS = RELEASES / OLD_STAGE / "apps/platform"
STAGE_NEW = RELEASES / CANDIDATE / "apps/platform"
PROD_LINK = Path("/home/kmjprod/current")
ANCHOR_PARENT = Path("/var/lib")
PRIVATE_ANCHOR = ANCHOR_PARENT / "kmj-main-platform-stage-releases"


def emit(key: str, value: str) -> None:
    print(key + "=" + value, flush=True)


def stop(code: str) -> None:
    emit("KMJ_STAGE_HOME_AUDIT", "BLOCKED_" + code)
    raise SystemExit(2)


def classify_owner(uid: int, stage_uid: int) -> str:
    return "ROOT" if uid == 0 else ("KMJSTAGE" if uid == stage_uid else "OTHER")


def meta_dir(path: Path, stage_uid: int) -> tuple[str, str, str, str, str, str]:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return ("ABSENT", "NA", "NA", "NA", "NA", "NA")
    except OSError:
        return ("UNREADABLE", "NA", "NA", "NA", "NA", "NA")
    kind = "DIRECTORY" if stat.S_ISDIR(st.st_mode) else ("SYMLINK" if stat.S_ISLNK(st.st_mode) else "NOT_DIRECTORY")
    owner = classify_owner(st.st_uid, stage_uid)
    mode = format(stat.S_IMODE(st.st_mode), "04o")
    writable = "YES" if (st.st_mode & 0o022) else "NO"
    if kind != "DIRECTORY":
        return (kind, owner, mode, writable, "NA", "NA")
    try:
        names = os.listxattr(path, follow_symlinks=False)
    except OSError:
        acl = "UNKNOWN"
    else:
        acl = ("PRESENT" if any(s in ("system.posix_acl_access", "system.posix_acl_default")
                                for s in names) else "NONE")
    return (kind, owner, mode, writable, acl, "YES" if os.path.ismount(path) else "NO")


def pointer(path: Path, expected: set[str]) -> str:
    try:
        meta = os.lstat(path)
        if not stat.S_ISLNK(meta.st_mode):
            return "NOT_SYMLINK"
        return "EXPECTED" if os.readlink(path) in expected else "DRIFT"
    except OSError:
        return "MISSING_OR_UNVERIFIED"


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        stop("ROOT_HOST_ARGS")
    stage_uid = pwd.getpwnam("kmjstage").pw_uid
    emit("KMJ_STAGE_HOME_AUDIT", "READ_ONLY_V1")
    paths = {
        "ROOT": Path("/"),
        "HOME_ROOT": Path("/home"),
        "STAGE_HOME": STAGE_BASE,
        "STAGE_RELEASES": RELEASES,
        "STAGE_HTDOCS": STAGE_WEB,
        "OLD_STAGE_APP": STAGE_PREVIOUS,
        "NEW_STAGE_APP": STAGE_NEW,
        "ALT_ROOT_PARENT": ANCHOR_PARENT,
        "ALT_ROOT_ANCHOR": PRIVATE_ANCHOR,
    }
    records = {}
    for label, path in paths.items():
        row = meta_dir(path, stage_uid)
        records[label] = row
        for k, v in zip(("TYPE", "OWNER", "MODE", "GROUP_WRITE", "ACL", "MOUNTPOINT"), row):
            emit(label + "_" + k, v)
    emit("STAGING_POINTER", pointer(STAGE_LINK, {
        str(STAGE_PREVIOUS),
        f"../releases/{OLD_STAGE}/apps/platform",
    }))
    emit("PRODUCTION_POINTER", pointer(PROD_LINK, {
        f"/home/kmjprod/releases/{PROD_RELEASE}",
        f"releases/{PROD_RELEASE}",
    }))
    if records["STAGE_HOME"][1] == "KMJSTAGE":
        emit("STAGE_HOME_ROOT_TRUST", "BLOCKED_USER_OWNED_ANCESTOR")
    elif records["STAGE_HOME"][1] == "ROOT" and records["STAGE_HOME"][3] == "NO":
        emit("STAGE_HOME_ROOT_TRUST", "ROOT_OWNER_MODE_ONLY_ADVISORY")
    else:
        emit("STAGE_HOME_ROOT_TRUST", "BLOCKED_UNTRUSTED_METADATA")
    a = records["ALT_ROOT_PARENT"]
    emit("ALTERNATE_ROOT_ANCHOR_FEASIBILITY",
         ("ADVISORY_PARENT_ROOT_OWNED" if a[0] == "DIRECTORY" and a[1] == "ROOT"
          and a[3] == "NO" and a[4] == "NONE" else "UNVERIFIED"))
    emit("STAGING_OWNER_SEAL", "NOT_VERIFIED")
    emit("STAGING_APPROVAL", "NOT_MODIFIED")
    emit("LEGACY_BACKUP", "NOT_MODIFIED")
    emit("PRODUCTION_POINTER_CHANGED", "NO")
    emit("STAGING_POINTER_CHANGED", "NO")
    emit("STAGING_MUTATIONS", "NONE")
    emit("KMJ_STAGE_HOME_AUDIT", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError):
        emit("KMJ_STAGE_HOME_AUDIT", "BLOCKED_HOST_METADATA")
        raise SystemExit(2)
