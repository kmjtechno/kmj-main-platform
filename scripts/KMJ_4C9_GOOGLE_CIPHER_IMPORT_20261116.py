#!/usr/bin/python3
"""No-overwrite, nonroot exact-SHA Google 4C9 age ciphertext vault import.

Runs without accessing the AGE key or a database. Never returns release credit.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import sys

NAME = "offsite-4c9d59103b99.tar.gz.age"
VAULT = Path("/home/info/kmj-recovery-vault")
SCRATCH = Path("/home/info/kmj-recovery-scratch")
SHA = re.compile(r"[a-f0-9]{64}\Z")
MAX_BYTES = 10 * 1024 ** 3


class Block(Exception):
    pass


def dir_checked(path: Path, uid: int, exact_mode: int | None = None):
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o022:
        raise Block("UNSAFE_DIR")
    if exact_mode is not None and stat.S_IMODE(st.st_mode) != exact_mode:
        raise Block("UNSAFE_DIR_MODE")
    return st


def fd_checked(fd: int, uid: int):
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1
            or stat.S_IMODE(st.st_mode) != 0o600
            or not 256 <= st.st_size <= MAX_BYTES):
        raise Block("UNSAFE_CIPHER_FILE")
    return st


def digest(fd: int, size: int) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    h = hashlib.sha256()
    n = 0
    while n < size:
        chunk = os.read(fd, min(size - n, 1024 * 1024))
        if not chunk:
            raise Block("TRUNCATED")
        h.update(chunk)
        n += len(chunk)
    if os.read(fd, 1):
        raise Block("GROWN")
    return h.hexdigest()


def source_one(vault: Path, uid: int) -> Path:
    root = dir_checked(vault, uid)
    matches = []
    visits = 0
    stack = [(vault, 0)]
    while stack:
        folder, depth = stack.pop()
        if dir_checked(folder, uid).st_dev != root.st_dev:
            raise Block("MOUNT_CROSSING")
        with os.scandir(folder) as listing:
            for item in listing:
                visits += 1
                if visits > 50000:
                    raise Block("SCAN_CAP")
                if item.is_symlink():
                    if item.name == NAME:
                        raise Block("SOURCE_SYMLINK")
                    continue
                if item.is_dir(follow_symlinks=False):
                    if depth >= 7:
                        raise Block("SCAN_DEPTH")
                    stack.append((Path(item.path), depth + 1))
                elif item.name == NAME:
                    if not item.is_file(follow_symlinks=False):
                        raise Block("NOT_REGULAR")
                    matches.append(Path(item.path))
                    if len(matches) > 1:
                        raise Block("AMBIGUOUS")
    if len(matches) != 1:
        raise Block("NOT_FOUND_ONE")
    return matches[0]


def import_exact(vault: Path, scratch: Path, expected: str, uid: int) -> str:
    if not SHA.fullmatch(expected):
        raise Block("INVALID_SHA")
    dir_checked(scratch, uid, 0o700)
    destination = scratch / NAME
    try:
        existing = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        pass
    except OSError:
        raise Block("EXISTING_TARGET_UNSAFE") from None
    else:
        try:
            st = fd_checked(existing, uid)
            if digest(existing, st.st_size) != expected:
                raise Block("EXISTING_TARGET_MISMATCH")
            return "ALREADY_PRESENT_EXACT_SHA"
        finally:
            os.close(existing)
    source = source_one(vault, uid)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = fd_checked(fd, uid)
        if digest(fd, st.st_size) != expected:
            raise Block("VAULT_SHA_MISMATCH")
        before = os.fstat(fd)
        if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns):
            raise Block("SOURCE_DRIFT")
        written = None
        try:
            written = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            os.lseek(fd, 0, os.SEEK_SET)
            n = 0
            while n < st.st_size:
                data = os.read(fd, min(1024 * 1024, st.st_size - n))
                if not data:
                    raise Block("SOURCE_TRUNCATED")
                n += len(data)
                view = memoryview(data)
                while view:
                    count = os.write(written, view)
                    if count <= 0:
                        raise Block("WRITE_FAILED")
                    view = view[count:]
            os.fsync(written)
            after = os.fstat(fd)
            if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise Block("SOURCE_DRIFT_DURING_COPY")
            os.close(written)
            written = None
            result = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                out_stat = fd_checked(result, uid)
                if out_stat.st_size != st.st_size or digest(result, out_stat.st_size) != expected:
                    raise Block("IMPORTED_SHA_MISMATCH")
            finally:
                os.close(result)
        except BaseException:
            if written is not None:
                os.close(written)
            try:
                destination.unlink()
            except OSError:
                pass
            raise
    finally:
        os.close(fd)
    return "COPIED_EXACT_SHA"


def main(args: list[str]) -> int:
    if len(args) != 3 or args[1] != "--encrypted-sha256" or not SHA.fullmatch(args[2]):
        print("KMJ_4C9_GOOGLE_IMPORT=BLOCKED_EXACT_SHA_ARGUMENT")
        return 2
    if (os.geteuid() == 0 or socket.gethostname().split(".")[0] != "google-vps1"
            or os.environ.get("HOME") != "/home/info"):
        print("KMJ_4C9_GOOGLE_IMPORT=BLOCKED_NONROOT_GOOGLE_HOST")
        return 2
    try:
        user = pwd.getpwuid(os.geteuid())
        if user.pw_name != "info" or user.pw_dir != "/home/info":
            raise Block("BAD_USER")
        result = import_exact(VAULT, SCRATCH, args[2], os.geteuid())
    except (Block, OSError, ValueError):
        print("KMJ_4C9_GOOGLE_IMPORT=BLOCKED_VALIDATION")
        return 2
    print("KMJ_4C9_GOOGLE_IMPORT=" + result)
    print("IMPORTED_SHA256=EXACT_MATCH")
    print("AGE_KEY_ACCESSED=NO")
    print("PRODUCTION_MUTATION=NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
