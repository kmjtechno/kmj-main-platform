#!/usr/bin/env python3
"""Exact bce410 -> 09e8 root-private crash journal directory provisioner.

--inspect is read-only. --prepare creates ONLY the previously missing fixed
root-owned 0700 empty directory /var/lib/kmj-main-platform-09e8-candidate-cutover.
Never repair, remove, chmod or overwrite existing state or ambiguous entries.
Does not execute the native adapter, install admission guard, drain services,
run V6 scanner, materialize candidate, alter any approval or deploy.
"""
from __future__ import annotations

import argparse
import os
import socket
import stat
import sys

PARENT_PARTS = ("var", "lib")
DIRECTORY = "kmj-main-platform-09e8-candidate-cutover"
ROOT_UID = 0
ROOT_GID = 0
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class Refused(RuntimeError):
    pass


def require(ok: bool, label: str) -> None:
    if not ok:
        raise Refused(label)


def identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
            st.st_nlink)


def protected_parent_fd() -> int:
    """Anchor each ancestor, rejecting symlinks or writable parents."""
    fd = os.open("/", DIR_FLAGS)
    try:
        root = os.fstat(fd)
        require(stat.S_ISDIR(root.st_mode) and root.st_uid == ROOT_UID
                and root.st_gid == ROOT_GID and not root.st_mode & 0o022,
                "ROOT_PARENT_UNTRUSTED")
        for component in PARENT_PARTS:
            next_fd = os.open(component, DIR_FLAGS, dir_fd=fd)
            try:
                st = os.fstat(next_fd)
                require(stat.S_ISDIR(st.st_mode) and st.st_uid == ROOT_UID
                        and st.st_gid == ROOT_GID and not st.st_mode & 0o022,
                        "PARENT_UNTRUSTED")
            except BaseException:
                os.close(next_fd)
                raise
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def inspect(parent_fd: int) -> str:
    try:
        child = os.open(DIRECTORY, DIR_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        return "MISSING"
    except OSError as exc:
        raise Refused("STATE_DIR_UNTRUSTED") from exc
    try:
        before = os.fstat(child)
        named = os.stat(DIRECTORY, dir_fd=parent_fd, follow_symlinks=False)
        require(stat.S_ISDIR(before.st_mode) and
                before.st_uid == ROOT_UID and before.st_gid == ROOT_GID and
                stat.S_IMODE(before.st_mode) == 0o700 and
                identity(before) == identity(named),
                "STATE_DIR_UNTRUSTED")
        # A partial/old recovery journal may have crash evidence: never erase,
        # repair or mark the directory "ready" if it contains anything.
        require(os.listdir(child) == [], "EXISTING_TRANSACTION_RECOVERY_REQUIRED")
        after = os.fstat(child)
        require(identity(before) == identity(after), "STATE_DIR_CHANGED")
        return "ROOT_PRIVATE_EMPTY"
    finally:
        os.close(child)


def prepare(parent_fd: int) -> str:
    state = inspect(parent_fd)
    if state == "ROOT_PRIVATE_EMPTY":
        return "ALREADY_ROOT_PRIVATE_EMPTY"
    require(state == "MISSING", "UNEXPECTED_EXISTING_STATE")
    # mkdirat is atomic and fails on a competing entry; no mode/owner repair.
    os.mkdir(DIRECTORY, 0o700, dir_fd=parent_fd)
    os.fsync(parent_fd)
    require(inspect(parent_fd) == "ROOT_PRIVATE_EMPTY",
            "CREATED_STATE_NOT_ATTESTED")
    return "CREATED_ROOT_PRIVATE_EMPTY"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    args = parser.parse_args(argv)
    print("SCHEMA=kmj.09e8.transaction-state-root-provision.v1")
    status = "BLOCKED_UNVERIFIABLE"
    mutated = "NO"
    rc = 2
    try:
        require(os.geteuid() == 0 and
                socket.gethostname().split(".")[0] == "KMJ-elite",
                "ROOT_ELITE_ONLY")
        fd = protected_parent_fd()
        try:
            status = prepare(fd) if args.prepare else inspect(fd)
            mutated = "YES" if status == "CREATED_ROOT_PRIVATE_EMPTY" else "NO"
            rc = 0
        finally:
            os.close(fd)
    except (Refused, OSError, ValueError, RuntimeError):
        # Omit raw exception text, paths, environment, and owner data.
        status = "BLOCKED_UNVERIFIABLE"
        rc = 2
    print("TRANSACTION_STATE_DIR=" + status)
    print("TRANSACTION_STATE_DIR_CREATED=" + mutated)
    print("WRITER_ADMISSION=NOT_ATTESTED")
    print("STORAGE_APPLY_ALLOWED=NO")
    print("PRODUCTION_APP_MUTATION=NONE")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
