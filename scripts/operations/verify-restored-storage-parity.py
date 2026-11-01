#!/usr/bin/env python3
"""Verify every restored scratch storage file against the validated inner tar.

Read-only: no production access, credentials, network, or file names in stdout.
The operator's parent recovery script must first validate the encrypted bundle
and extract into fresh, private scratch storage.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
import tarfile

MAX_ENTRIES = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024 * 1024


class StorageParityError(Exception):
    pass


def fail() -> None:
    raise StorageParityError("RESTORED_STORAGE_UNVERIFIED")


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def archive_inventory(source: Path) -> tuple[dict[str, tuple[int, str]], set[str]]:
    files: dict[str, tuple[int, str]] = {}
    directories = {"storage", "storage/app"}
    seen: set[str] = set()
    total = 0
    with tarfile.open(source, "r:gz") as archive:
        for item in archive:
            raw = item.name.rstrip("/")
            parts = raw.split("/")
            if (not raw or raw.startswith("/") or "\\" in raw
                or any(part in ("", ".", "..") for part in parts)
                or parts[:2] != ["storage", "app"]
                or raw in seen or len(seen) >= MAX_ENTRIES
                or item.size < 0 or item.sparse is not None
                or not (item.isdir() or item.isfile())):
                fail()
            seen.add(raw)
            for length in range(1, len(parts)):
                directories.add("/".join(parts[:length]))
            if item.isdir():
                directories.add(raw)
                continue
            if raw == "storage/app" or raw in directories:
                fail()
            total += item.size
            if total > MAX_FILE_BYTES:
                fail()
            payload = archive.extractfile(item)
            if payload is None:
                fail()
            with payload:
                files[raw] = (item.size, sha256_stream(payload))
    if "storage/app" not in seen:
        fail()
    if any(name in files for name in directories):
        fail()
    return files, directories


def open_restored_root(root: Path) -> int:
    """Pin every restored-root ancestor, rejecting symlink redirection."""
    if not root.is_absolute() or ".." in root.parts:
        fail()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for component in root.parts[1:]:
            child = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError:
        os.close(fd)
        fail()


def restored_inventory(root: Path) -> tuple[dict[str, tuple[int, str]], set[str]]:
    # os.walk + lstat followed by open(path) is vulnerable to a swapped
    # intermediate directory. Anchor both enumeration and file reads to
    # directory descriptors; O_NOFOLLOW on the final filename alone is not
    # sufficient to prevent an ancestor symlink race.
    root_fd = open_restored_root(root)
    pinned_root = os.fstat(root_fd)
    files: dict[str, tuple[int, str]] = {}
    directories: set[str] = set()
    # A pinned root alone is insufficient: a nested restored directory may
    # be replaced after its contents have been hashed. Remember each visited
    # directory's inode so the final pathname walk can detect that swap.
    directory_inodes: dict[str, tuple[int, int]] = {}
    # Detect byte-identical file replacement after the initial hash pass.
    file_metadata: dict[str, tuple[int, int, int, int, int, int]] = {}
    total = 0

    def onerror(error: OSError) -> None:
        fail()

    try:
        for parent, subdirs, filenames, dirfd in os.fwalk(
            ".", dir_fd=root_fd, follow_symlinks=False, onerror=onerror
        ):
            rel_parent = Path(parent)
            rel_key = rel_parent.as_posix()
            parent_info = os.fstat(dirfd)
            if not stat.S_ISDIR(parent_info.st_mode) or rel_key in directory_inodes:
                fail()
            directory_inodes[rel_key] = (parent_info.st_dev, parent_info.st_ino)
            for name in subdirs:
                info = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    fail()
                directories.add((rel_parent / name).as_posix())
            for name in filenames:
                before_path = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if not stat.S_ISREG(before_path.st_mode):
                    fail()
                fd = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=dirfd,
                )
                try:
                    before = os.fstat(fd)
                    # A byte-identical hardlink to a live file is not an
                    # independently restored file. The inner archive rejects
                    # hardlink members, so every restored regular file must
                    # have exactly one link throughout verification.
                    if (not stat.S_ISREG(before.st_mode)
                        or before.st_nlink != 1
                        or ((before.st_dev, before.st_ino, before.st_size,
                             before.st_mtime_ns, before.st_ctime_ns, before.st_nlink)
                            != (before_path.st_dev, before_path.st_ino, before_path.st_size,
                                before_path.st_mtime_ns, before_path.st_ctime_ns,
                                before_path.st_nlink))):
                        fail()
                    with os.fdopen(os.dup(fd), "rb") as stream:
                        checksum = sha256_stream(stream)
                    after = os.fstat(fd)
                    if (after.st_nlink != 1 or
                        (before.st_dev, before.st_ino, before.st_size,
                         before.st_mtime_ns, before.st_ctime_ns, before.st_nlink)
                        != (after.st_dev, after.st_ino, after.st_size,
                            after.st_mtime_ns, after.st_ctime_ns, after.st_nlink)):
                        fail()
                    rel = (rel_parent / name).as_posix()
                    files[rel] = (before.st_size, checksum)
                    file_metadata[rel] = (after.st_dev, after.st_ino, after.st_size,
                                          after.st_mtime_ns, after.st_ctime_ns, after.st_nlink)
                    total += before.st_size
                    if len(files) + len(directories) > MAX_ENTRIES or total > MAX_FILE_BYTES:
                        fail()
                finally:
                    os.close(fd)
        # Reopen the full directory hierarchy after hashing. A swap of an
        # interior directory leaves root_fd unchanged, but must not allow a
        # successful attestation for a different restored pathname.
        seen_dirs: set[str] = set()
        seen_files: set[str] = set()
        for parent, _subdirs, filenames, dirfd in os.fwalk(
            ".", dir_fd=root_fd, follow_symlinks=False, onerror=onerror
        ):
            key = Path(parent).as_posix()
            info = os.fstat(dirfd)
            if (key in seen_dirs or not stat.S_ISDIR(info.st_mode)
                or directory_inodes.get(key) != (info.st_dev, info.st_ino)):
                fail()
            seen_dirs.add(key)
            # A symlink introduced after the first walk is reported in
            # fwalk's subdirs but not descended into. Ignoring subdirs here
            # would let a new unverified symlink survive a successful PASS.
            for name in _subdirs:
                try:
                    child = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                except OSError:
                    fail()
                if (not stat.S_ISDIR(child.st_mode)
                    or (Path(parent) / name).as_posix() not in directories):
                    fail()
            for name in filenames:
                rel = (Path(parent) / name).as_posix()
                if rel in seen_files:
                    fail()
                seen_files.add(rel)
                try:
                    info = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                except OSError:
                    fail()
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or file_metadata.get(rel) != (
                        info.st_dev, info.st_ino, info.st_size,
                        info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)):
                    fail()
        if seen_files != set(file_metadata):
            fail()
        if seen_dirs != set(directory_inodes):
            fail()
        # The walk is descriptor-anchored, but the caller will later use the
        # restored pathname. Reject a root that was renamed or redirected
        # while hashing rather than attesting a now-different pathname.
        check_fd = open_restored_root(root)
        try:
            current_root = os.fstat(check_fd)
            if (pinned_root.st_dev, pinned_root.st_ino) != (current_root.st_dev, current_root.st_ino):
                fail()
        finally:
            os.close(check_fd)
    finally:
        os.close(root_fd)
    return files, directories


def verify_details(source: Path, restored: Path) -> tuple[int, int]:
    expected, expected_dirs = archive_inventory(source)
    actual, actual_dirs = restored_inventory(restored)
    if expected != actual or expected_dirs != actual_dirs:
        fail()
    return len(expected), sum(size for size, _checksum in actual.values())


def verify(source: Path, restored: Path) -> int:
    # Preserve the library API used by existing callers and tests.
    return verify_details(source, restored)[0]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or any(not Path(p).is_absolute() for p in argv):
        print("RECOVERED_STORAGE_CONTENT_PARITY=BLOCKED_ARGUMENTS")
        return 2
    try:
        files, bytes_verified = verify_details(Path(argv[0]), Path(argv[1]))
    except (StorageParityError, OSError, ValueError, tarfile.TarError):
        print("RECOVERED_STORAGE_CONTENT_PARITY=FAIL")
        return 2
    print("RECOVERED_STORAGE_CONTENT_PARITY=PASS")
    print(f"RECOVERED_STORAGE_FILES_VERIFIED={files}")
    print(f"RECOVERED_STORAGE_BYTES_VERIFIED={bytes_verified}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
