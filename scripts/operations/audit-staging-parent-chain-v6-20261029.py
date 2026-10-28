#!/usr/bin/env python3
"""Fixed-host read-only staging parent-chain audit; never grants migration approval.

Only creates one bounded sanitized CodeBridge QA receipt. No customer files,
release pointers, permissions, database, or services are modified.
"""
from __future__ import annotations

import errno
import grp
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import sys

QA = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa")
RECEIPT = "KMJ_STAGE_PARENT_CHAIN_V6_20261029.json"
STAGE_SHA = "9d15e14e39564ffb1e66085a483feb8331f9718f"
EXPECTED_STAGE = Path("/home/kmjstage/releases") / STAGE_SHA / "apps/platform"
EXPECTED_PROD = Path("/home/kmjprod/releases/platform-8070dad72c55")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_LINK = Path("/home/kmjprod/current")
PARTS = ("home", "kmjstage", "shared")


class AuditBlocked(RuntimeError):
    pass


def acl_state(fd: int) -> str:
    """Unknown is not equivalent to absent ACL; inspect access and default ACLs."""
    statuses = []
    for key in ("system.posix_acl_access", "system.posix_acl_default"):
        try:
            value = os.getxattr(fd, key)
            statuses.append("PRESENT" if value else "UNKNOWN")
        except OSError as exc:
            if exc.errno == errno.ENODATA:
                statuses.append("ABSENT")
            elif exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS):
                statuses.append("UNKNOWN")
            else:
                statuses.append("ERROR")
    if "PRESENT" in statuses:
        return "PRESENT"
    if "ERROR" in statuses:
        return "ERROR"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "ABSENT"


def stat_identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_uid, st.st_gid, st.st_mode,
            st.st_mtime_ns, st.st_ctime_ns)


def snapshot_chain() -> list[dict[str, object]]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fds = [os.open("/", flags)]
    rows = []
    try:
        for part in PARTS:
            parent = fds[-1]
            before = os.stat(part, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise AuditBlocked("NON_DIRECTORY_OR_SYMLINK")
            fd = os.open(part, flags, dir_fd=parent)
            fds.append(fd)
            opened = os.fstat(fd)
            if stat_identity(before) != stat_identity(opened):
                raise AuditBlocked("PATH_CHANGED")
            rows.append({
                "uid": opened.st_uid,
                "gid": opened.st_gid,
                "mode": stat.S_IMODE(opened.st_mode),
                "dev": opened.st_dev,
                "ino": opened.st_ino,
                "acl": acl_state(fd),
            })
        for fd, row in zip(fds[1:], rows):
            now = os.fstat(fd)
            if (now.st_dev != row["dev"] or now.st_ino != row["ino"] or
                    now.st_uid != row["uid"] or now.st_gid != row["gid"] or
                    stat.S_IMODE(now.st_mode) != row["mode"]):
                raise AuditBlocked("CHAIN_CHANGED")
        return rows
    finally:
        for fd in reversed(fds):
            os.close(fd)


def mount_context() -> dict[str, object]:
    """Check explicit parent/shared mountpoints, including same-device bind mounts.

    Mountinfo is only a read-only diagnostic. It does not authorize copying.
    """
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as stream:
            data = stream.read(1_048_577)
        if len(data) > 1_048_576:
            raise AuditBlocked("MOUNTINFO_OVERSIZED")
        points = set()
        for line in data.splitlines():
            if " - " not in line:
                raise AuditBlocked("MOUNTINFO_MALFORMED")
            left = line.split(" - ", 1)[0].split()
            if len(left) < 5:
                raise AuditBlocked("MOUNTINFO_MALFORMED")
            points.add(left[4])
        return {
            "mountinfo_checked": True,
            "stage_parent_explicit_mount": "/home/kmjstage" in points,
            "shared_explicit_mount": "/home/kmjstage/shared" in points,
        }
    except (OSError, UnicodeError, AuditBlocked):
        return {
            "mountinfo_checked": False,
            "stage_parent_explicit_mount": None,
            "shared_explicit_mount": None,
        }


def assess(rows: list[dict[str, object]], stage_uid: int,
           mount: dict[str, object] | None = None) -> dict[str, object]:
    """Pure fail-closed interpretation, suitable for offline negative tests."""
    if len(rows) != 3:
        raise AuditBlocked("INCOMPLETE_CHAIN")
    home, stage, shared = rows
    stage_mode = int(stage["mode"])
    parent_write_execute = bool(
        (stage["uid"] == stage_uid and stage_mode & 0o300 == 0o300) or
        (stage_mode & 0o030 == 0o030) or
        (stage_mode & 0o003 == 0o003)
    )
    shared_root_owned = (shared["uid"] == 0 and shared["gid"] == 0 and
                         shared["mode"] == 0o755)
    acl_status = [str(row["acl"]) for row in rows]
    all_acls_absent = all(value == "ABSENT" for value in acl_status)
    same_device = stage["dev"] == shared["dev"]
    if mount is None:
        mount = {"mountinfo_checked": False,
                 "stage_parent_explicit_mount": None,
                 "shared_explicit_mount": None}
    reasons = []
    if not mount["mountinfo_checked"]:
        reasons.append("MOUNTINFO_UNVERIFIED")
    elif mount["stage_parent_explicit_mount"] or mount["shared_explicit_mount"]:
        reasons.append("EXPLICIT_MOUNTPOINT_REVIEW")

    if parent_write_execute:
        reasons.append("STAGE_PARENT_WRITE_EXEC")
    if not shared_root_owned:
        reasons.append("SHARED_ROOT_POLICY")
    if not all_acls_absent:
        reasons.append("ACL_UNVERIFIED_OR_PRESENT")
    if not same_device:
        reasons.append("MOUNT_BOUNDARY_REVIEW")
    if home["uid"] != 0:
        reasons.append("HOME_PARENT_NOT_ROOT_OWNED")
    # A directory owner can chmod its own 0555 parent back to writable,
    # then rename a root-owned child. Current mode alone is not protection.
    if stage["uid"] == stage_uid:
        reasons.append("STAGE_PARENT_OWNER_CAN_CHMOD")
    else:
        reasons.append("STAGE_PARENT_OWNER_MISMATCH")
    if home["mode"] & 0o022:
        reasons.append("HOME_PARENT_GROUP_OR_WORLD_WRITABLE")
    if not reasons:
        reasons.append("OWNER_REVIEW_AND_BACKUP_STILL_REQUIRED")
    return {
        "schema": "kmj.stage.parent-chain.v6",
        "audit": "READ_ONLY",
        "stage_parent_uid_matches": stage["uid"] == stage_uid,
        "stage_parent_mode_octal": format(stage_mode, "04o"),
        "stage_parent_sticky": bool(stage_mode & stat.S_ISVTX),
        "stage_parent_write_execute": parent_write_execute,
        "shared_root_owned_0755": shared_root_owned,
        "shared_parent_same_device": same_device,
        "mountinfo_checked": mount["mountinfo_checked"],
        "stage_parent_explicit_mount": mount["stage_parent_explicit_mount"],
        "shared_explicit_mount": mount["shared_explicit_mount"],

        "acl_states": acl_status,
        "blockers": reasons,
        "migration_authorized": False,
        "staging_switch_authorized": False,
        "production_activation_authorized": False,
        "encrypted_offsite_restore_verified": False,
        "writer_quiescence_verified": False,
        "owner_approval_attested": False,
        "customer_data_modified": False,
    }


def pointer_matches(link: Path, expected: Path) -> bool:
    return link.is_symlink() and link.resolve(strict=True) == expected


def write_receipt(data: dict[str, object]) -> None:
    payload = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(payload) > 4096:
        raise AuditBlocked("RECEIPT_TOO_LARGE")
    if QA.is_symlink() or not QA.is_dir():
        raise AuditBlocked("QA_DIRECTORY_UNSAFE")
    gid = grp.getgrnam("kmjcode").gr_gid
    dirfd = os.open(QA, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
            os.fchown(out.fileno(), 0, gid)
            os.fchmod(out.fileno(), 0o640)
            os.fsync(out.fileno())
    finally:
        os.close(dirfd)


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0 or
            socket.gethostname().split(".")[0] != "KMJ-elite"):
        print("KMJ_STAGE_PARENT_CHAIN_V6=BLOCKED_HOST_ROOT_OR_ARGS")
        return 2
    try:
        stage_uid = pwd.getpwnam("kmjstage").pw_uid
        rows = snapshot_chain()
        result = assess(rows, stage_uid, mount_context())
        result["production_pointer_exact"] = pointer_matches(PROD_LINK, EXPECTED_PROD)
        result["staging_pointer_exact"] = pointer_matches(STAGE_LINK, EXPECTED_STAGE)
        if not result["production_pointer_exact"] or not result["staging_pointer_exact"]:
            result["blockers"].append("RELEASE_POINTER_DRIFT")
        write_receipt(result)
    except (OSError, KeyError, AuditBlocked, RuntimeError) as exc:
        print("KMJ_STAGE_PARENT_CHAIN_V6=BLOCKED_PREFLIGHT_" + type(exc).__name__)
        return 2
    print("KMJ_STAGE_PARENT_CHAIN_V6=READ_ONLY_RECEIPT_CREATED")
    print("MIGRATION_AUTHORIZED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
