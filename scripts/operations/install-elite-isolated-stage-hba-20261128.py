#!/usr/bin/env python3
"""Explicit owner-only installation of a reviewed candidate-role HBA prefix.

Preserve every original rule and existing ACL. Require exact reviewed old/new
SHA256 pins, root-controlled config ancestry, absent candidate role, valid
server configuration and rollback on failed validation/reload. No role or
database creation. This script cannot attest live candidate login isolation.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("hba_plan", Path(__file__).resolve().parent / "plan-elite-isolated-stage-hba-20261128.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
ROLE = plan.ROLE
LIVE = Path("/home/kmjprod/current")
EXPECTED = Path("/home/kmjprod/releases/platform-72e7c9ada190")


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def trusted_parent(path):
    for p in (path.parent, *path.parent.parents):
        s = p.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "HBA_PARENT_UNTRUSTED")
        require(not any(x.startswith("system.posix_acl_") for x in os.listxattr(p, follow_symlinks=False)),
                "HBA_PARENT_ACL")


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace(path, expected, payload, metadata):
    require(plan.read_hba(path) == expected, "HBA_CONTENT_DRIFT")
    current = path.lstat()
    require((current.st_dev, current.st_ino, current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode))
            == (metadata.st_dev, metadata.st_ino, metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)),
            "HBA_INODE_DRIFT")
    require(not os.listxattr(path, follow_symlinks=False), "HBA_EXTENDED_ATTRIBUTES")
    fd, tmp = tempfile.mkstemp(prefix=".kmj-hba-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fchown(handle.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fsync(handle.fileno())
        require(plan.read_hba(path) == expected, "HBA_CONTENT_DRIFT")
        os.replace(tmp, path)
        sync_dir(path.parent)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def live_guard():
    require(LIVE.is_symlink() and LIVE.resolve(strict=True) == EXPECTED, "LIVE_POINTER_DRIFT")
    require(plan.pg(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}'") == "0",
            "CANDIDATE_ROLE_EXISTS")
    require(plan.pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
            "HBA_PARSE_ERRORS")


def reload():
    require(plan.pg("SELECT pg_reload_conf()") == "t", "RELOAD_SIGNAL_FAILED")
    # This is a signal acknowledgement, not live-policy attestation.
    require(plan.pg("SELECT 1") == "1", "ADMIN_CONNECTION_FAILED")


def install(path, old, new, backup_parent=Path("/root")):
    metadata = path.lstat()
    backup_dir = Path(tempfile.mkdtemp(prefix="kmj-stage-hba-backup-", dir=backup_parent))
    backup = backup_dir / "pg_hba.conf.original"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(old)
        handle.flush()
        os.fsync(handle.fileno())
    sync_dir(backup_dir)
    sync_dir(backup_dir.parent)
    print("HBA_BACKUP=" + str(backup), flush=True)
    try:
        live_guard()
        atomic_replace(path, old, new, metadata)
        require(plan.read_hba(path) == new, "HBA_WRITE_READBACK")
        live_guard()
        reload()
        live_guard()
        require(plan.read_hba(path) == new, "HBA_POST_RELOAD_DRIFT")
    except BaseException:
        # Restore only our exact replacement, never overwrite unrelated drift.
        if plan.read_hba(path) == new:
            atomic_replace(path, new, old, path.lstat())
            reload()
            require(plan.read_hba(path) == old, "HBA_ROLLBACK_READBACK")
            print("HBA_ROLLBACK=ORIGINAL_BYTES_RESTORED_RELOAD_SIGNAL_SENT", flush=True)
        elif plan.read_hba(path) != old:
            print("HBA_ROLLBACK=BLOCKED_UNEXPECTED_DRIFT", flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0].lower() == "kmj-elite", "HOST_ROOT")
        require(args.confirm == "OWNER_APPROVES_REVIEWED_CANDIDATE_HBA_ONLY", "OWNER_CONFIRMATION")
        require(all(re.fullmatch(r"[0-9a-f]{64}", x) for x in
                    (args.baseline_sha256, args.proposal_sha256)), "PIN_FORMAT")
        # /run/lock may be world-writable; use a root-controlled lock directory.
        lock = Path("/root/.kmj-stage-hba-install.lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            st = os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and st.st_nlink == 1
                    and stat.S_IMODE(st.st_mode) == 0o600, "LOCK_METADATA")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            live_guard()
            path = Path(plan.pg("SHOW hba_file"))
            trusted_parent(path)
            old = plan.read_hba(path)
            new = plan.proposal(old)
            require(sha(old) == args.baseline_sha256 and sha(new) == args.proposal_sha256,
                    "REVIEWED_PINS_MISMATCH")
            install(path, old, new)
        finally:
            os.close(fd)
        print("HBA_INSTALL=PASS_DISK_AND_RELOAD_SIGNAL")
        print("HBA_LIVE_CANDIDATE_ISOLATION=NOT_TESTED")
        print("EXISTING_DATABASE_GRANTS_CHANGED=NO CANDIDATE_ROLE_CREATED=NO")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = str(exc)
        print("HBA_INSTALL=BLOCKED_" + (reason if re.fullmatch("[A-Z_]+", reason) else "SYSTEM_OR_FORMAT"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
