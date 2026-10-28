#!/usr/bin/env python3
"""Root-only read-only staging parent-chain evidence; NEVER a release gate PASS.

Creates only a bounded sanitized receipt. No customer files are opened.
Requires separate exact-source owner review before any host execution.
"""
from __future__ import annotations

import errno
import grp
import json
import os
from pathlib import Path
import socket
import stat

STAGE_SHA = "9d15e14e39564ffb1e66085a483feb8331f9718f"
PROD_RELEASE = "platform-8070dad72c55"
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD = Path("/home/kmjprod/current")
HOME = Path("/home/kmjstage")
SHARED = HOME / "shared"
QA = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa")
RECEIPT = "KMJ_STAGE_PARENT_CHAIN_V6_20261029.json"


class UnsafeEvidence(ValueError):
    pass


def acl_status(path: Path) -> str:
    """An inaccessible/unsupported ACL must never be classified as absent."""
    try:
        os.getxattr(path, "system.posix_acl_access", follow_symlinks=False)
        return "PRESENT"
    except OSError as exc:
        if exc.errno in (errno.ENODATA, getattr(errno, "ENOATTR", errno.ENODATA)):
            return "ABSENT"
        return "UNKNOWN"


def directory(path: Path) -> os.stat_result:
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        raise UnsafeEvidence("UNTRUSTED_DIRECTORY_CHAIN")
    return st


def collect_chain(home: Path = HOME, shared: Path = SHARED) -> dict[str, object]:
    """Metadata snapshot only; not proof of writer quiescence or backup."""
    parent = directory(home)
    child = directory(shared)
    # Parent write+execute grants rename authority regardless of child owner.
    owner_wx = (parent.st_mode & 0o300) == 0o300
    group_wx = (parent.st_mode & 0o030) == 0o030
    other_wx = (parent.st_mode & 0o003) == 0o003
    parent_acl = acl_status(home)
    child_acl = acl_status(shared)
    rename_risk = "YES" if (owner_wx or group_wx or other_wx) else "UNKNOWN"
    return {
        "schema": "kmj.stage.parent-chain.v6",
        "parent_uid": parent.st_uid,
        "parent_mode": format(stat.S_IMODE(parent.st_mode), "04o"),
        "parent_sticky": bool(parent.st_mode & stat.S_ISVTX),
        "parent_acl": parent_acl,
        "shared_uid": child.st_uid,
        "shared_gid": child.st_gid,
        "shared_mode": format(stat.S_IMODE(child.st_mode), "04o"),
        "shared_acl": child_acl,
        "same_device": parent.st_dev == child.st_dev,
        "shared_mountpoint": os.path.ismount(shared),
        "parent_rename_risk": rename_risk,
        "release_bound_uploads": True,
        "staging_switch_authorized": False,
        "production_activation_authorized": False,
        "backup_restore_verified": False,
        "owner_release_approved": False,
        "status": "BLOCKED_PARENT_CHAIN_AND_RELEASE_GATES",
    }


def write_receipt(data: dict[str, object]) -> None:
    qa = directory(QA)
    if qa.st_mode & 0o002:
        raise UnsafeEvidence("WORLD_WRITABLE_RECEIPT_PARENT")
    raw = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(raw) > 2048:
        raise UnsafeEvidence("RECEIPT_TOO_LARGE")
    gid = grp.getgrnam("kmjcode").gr_gid
    fd = os.open(QA / RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchown(stream.fileno(), 0, gid)
        os.fchmod(stream.fileno(), 0o640)
        os.fsync(stream.fileno())


def main() -> int:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("KMJ_STAGE_PARENT_CHAIN_V6=BLOCKED_OWNER_ROOT_HOST")
        return 2
    try:
        expected_stage = Path("/home/kmjstage/releases") / STAGE_SHA / "apps/platform"
        expected_prod = Path("/home/kmjprod/releases") / PROD_RELEASE
        if (not STAGE.is_symlink() or STAGE.resolve(strict=True) != expected_stage
                or not PROD.is_symlink() or PROD.resolve(strict=True) != expected_prod):
            raise UnsafeEvidence("LIVE_POINTER_DRIFT")
        directory(HOME.parent)
        result = collect_chain()
        result["live_pointer_identity"] = "MATCHED_OLD_BASELINE"
        write_receipt(result)
        print("KMJ_STAGE_PARENT_CHAIN_V6=EVIDENCE_ONLY_BLOCKED")
        return 0
    except (OSError, UnsafeEvidence, KeyError) as exc:
        label = str(exc)
        if label not in {"LIVE_POINTER_DRIFT", "UNTRUSTED_DIRECTORY_CHAIN",
                         "WORLD_WRITABLE_RECEIPT_PARENT", "RECEIPT_TOO_LARGE"}:
            label = "UNVERIFIED_HOST_STATE"
        print("KMJ_STAGE_PARENT_CHAIN_V6=BLOCKED_" + label)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
