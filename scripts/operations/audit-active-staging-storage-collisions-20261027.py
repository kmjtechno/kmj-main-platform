#!/usr/bin/env python3
"""Secret-free, read-only inventory of two isolated KMJ staging storage trees.

Compare content fingerprints without printing file names, bytes, hashes or .env.
Does NOT authorize copying, linking, cleanup, backup, or deployment.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

STAGE_HOME = Path("/home/kmjstage")
RELEASES = STAGE_HOME / "releases"
ACTIVE_LINK = STAGE_HOME / "htdocs/staging.kmjtechno.com"
PROD_LINK = Path("/home/kmjprod/current")
OLD_SHA = "babf9060684d15b6188384386149466816140a98"
MAX_TOTAL_HASH_BYTES = 512 * 1024 * 1024
MAX_FILES = 100000


class AuditBlocked(Exception):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise AuditBlocked(reason)


def git_head(release: Path) -> str:
    p = subprocess.run(
        ["runuser", "-u", "kmjstage", "--", "git", "-C", str(release),
         "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        timeout=12, check=False,
    )
    require(p.returncode == 0, "GIT_UNAVAILABLE")
    return p.stdout.strip()


def safe_inside_stage(path: Path) -> bool:
    try:
        return path.is_relative_to(STAGE_HOME) and path != STAGE_HOME
    except ValueError:
        return False


def category(relative: str) -> str:
    segments = relative.split("/")
    if segments[:2] == ["app", "public"]:
        return "PUBLIC_UPLOADS"
    if segments[:2] == ["app", "private"]:
        return "PRIVATE_APP"
    if segments[0] == "framework":
        return "FRAMEWORK"
    if segments[0] == "logs":
        return "LOGS"
    return "OTHER"


def scan_storage(root: Path) -> tuple[dict[str, tuple[int, str]], int]:
    require(root.is_dir(), "STORAGE_DIRECTORY_MISSING")
    require(safe_inside_stage(root.resolve(strict=True)), "STORAGE_OUT_OF_SCOPE")
    files: dict[str, tuple[int, str]] = {}
    total = 0
    for parent, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        parent_path = Path(parent)
        for entry in directories + filenames:
            info = (parent_path / entry).lstat()
            require(not stat.S_ISLNK(info.st_mode), "STORAGE_TREE_HAS_SYMLINKS")
            require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                    "STORAGE_TREE_NONREGULAR_ENTRY")
        for name in filenames:
            path = parent_path / name
            relative = path.relative_to(root).as_posix()
            require(relative not in files, "STORAGE_DUPLICATE_PATH")
            before = path.lstat()
            require(stat.S_ISREG(before.st_mode), "STORAGE_NONREGULAR_FILE")
            total += before.st_size
            require(total <= MAX_TOTAL_HASH_BYTES, "STORAGE_EXCEEDS_READ_BUDGET")
            require(len(files) < MAX_FILES, "STORAGE_TOO_MANY_FILES")
            digest = hashlib.sha256()
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
            fd = os.open(path, flags)
            try:
                opened = os.fstat(fd)
                require(stat.S_ISREG(opened.st_mode), "STORAGE_OPENED_NONREGULAR")
                require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
                        "STORAGE_FILE_CHANGED")
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                after = os.fstat(fd)
                require((before.st_size, before.st_mtime_ns) ==
                        (after.st_size, after.st_mtime_ns), "STORAGE_FILE_CHANGED")
            finally:
                os.close(fd)
            files[relative] = (before.st_size, digest.hexdigest())
    return files, total


def public_storage_status(app: Path) -> str:
    public = app / "public" / "storage"
    if public.is_symlink():
        target = public.resolve(strict=False)
        return "LINK_WITHIN_STAGE" if safe_inside_stage(target) else "UNSAFE_LINK"
    if public.is_dir():
        return "DIRECTORY"
    if public.exists():
        return "UNEXPECTED_FILE"
    return "MISSING"


def main() -> None:
    require(len(sys.argv) == 2 and re.fullmatch(r"[a-f0-9]{40}", sys.argv[1]) is not None,
            "EXACT_SHA_REQUIRED")
    sha = sys.argv[1]
    require(socket.gethostname().split(".")[0] == "KMJ-elite" and os.geteuid() == 0,
            "WRONG_HOST_OR_USER")
    require(ACTIVE_LINK.is_symlink() and PROD_LINK.is_symlink(), "LIVE_LINK_MISSING")

    actual = ACTIVE_LINK.resolve(strict=True)
    production = PROD_LINK.resolve(strict=True)
    require(actual == RELEASES / sha / "apps/platform", "ACTIVE_STAGE_SHA_DRIFT")
    require(str(production).startswith("/home/kmjprod/releases/platform-"),
            "PRODUCTION_SCOPE_CHANGED")
    old_release = RELEASES / OLD_SHA
    current_release = RELEASES / sha
    old = old_release / "apps/platform"
    current = current_release / "apps/platform"
    require(old.is_dir() and current.is_dir(), "RELEASES_NOT_FOUND")
    require(git_head(old_release) == OLD_SHA, "OLD_RELEASE_GIT_MISMATCH")
    require(git_head(current_release) == sha, "ACTIVE_RELEASE_GIT_MISMATCH")
    old_storage = old / "storage"
    current_storage = current / "storage"
    old_real = old_storage.resolve(strict=True)
    current_real = current_storage.resolve(strict=True)
    require(safe_inside_stage(old_real) and safe_inside_stage(current_real),
            "STORAGE_OUT_OF_SCOPE")

    old_files, old_bytes = scan_storage(old_real)
    current_files, current_bytes = scan_storage(current_real)
    old_keys, current_keys = set(old_files), set(current_files)
    common = old_keys & current_keys
    unchanged = sum(old_files[k] == current_files[k] for k in common)
    conflicts = len(common) - unchanged
    old_only = old_keys - current_keys
    active_only = current_keys - old_keys

    print("STAGING_ACTIVE_SHA=" + sha)
    print("STAGING_OLD_SHA=" + OLD_SHA)
    print("STORAGE_SAME_REALPATH=" + ("YES" if old_real == current_real else "NO"))
    print("STORAGE_OLD_FILES=" + str(len(old_files)))
    print("STORAGE_ACTIVE_FILES=" + str(len(current_files)))
    print("STORAGE_OLD_BYTES=" + str(old_bytes))
    print("STORAGE_ACTIVE_BYTES=" + str(current_bytes))
    print("STORAGE_SAME_PATH_SAME_CONTENT=" + str(unchanged))
    print("STORAGE_SAME_PATH_DIFFERENT_CONTENT=" + str(conflicts))
    print("STORAGE_OLD_ONLY=" + str(len(old_only)))
    print("STORAGE_ACTIVE_ONLY=" + str(len(active_only)))
    for kind in ("PUBLIC_UPLOADS", "PRIVATE_APP", "FRAMEWORK", "LOGS", "OTHER"):
        old_count = sum(category(key) == kind for key in old_only)
        new_count = sum(category(key) == kind for key in active_only)
        conflict_count = sum(category(key) == kind and
                             old_files[key] != current_files[key] for key in common)
        print("STORAGE_" + kind + "_OLD_ONLY=" + str(old_count))
        print("STORAGE_" + kind + "_ACTIVE_ONLY=" + str(new_count))
        print("STORAGE_" + kind + "_CONFLICTS=" + str(conflict_count))
    print("STAGING_OLD_PUBLIC_STORAGE=" + public_storage_status(old))
    print("STAGING_ACTIVE_PUBLIC_STORAGE=" + public_storage_status(current))
    require(ACTIVE_LINK.resolve(strict=True) == actual and
            PROD_LINK.resolve(strict=True) == production, "LINKS_CHANGED_DURING_AUDIT")
    print("STORAGE_CROSS_RELEASE_COPY=NOT_PERFORMED")
    print("STORAGE_CONSISTENCY=READ_ONLY_NONTRANSACTIONAL_SNAPSHOT")
    print("STAGING_POINTER=UNCHANGED")
    print("PRODUCTION_POINTER=UNCHANGED")
    print("KMJ_STORAGE_COLLISION_AUDIT=READ_ONLY_COMPLETE")


if __name__ == "__main__":
    try:
        main()
    except (AuditBlocked, OSError, subprocess.TimeoutExpired, UnicodeError,
            ValueError) as exc:
        reason = str(exc) if isinstance(exc, AuditBlocked) else "IO_OR_RUNTIME_UNVERIFIED"
        print("KMJ_STORAGE_COLLISION_AUDIT=BLOCKED_" + reason)
        raise SystemExit(2) from None
