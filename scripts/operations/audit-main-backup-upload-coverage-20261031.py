#!/usr/bin/env python3
"""Read-only P0 coverage check for the witnessed local storage/app backup.

This is an advisory check, NOT a production approval, filesystem snapshot,
remote-retention proof, or authenticated upload QA. Never prints file names,
contents, credentials, .env, or product/customer identifiers.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import tarfile


class CoverageError(Exception):
    pass


def reject(reason: str) -> None:
    raise CoverageError(reason)


def digest(stream) -> str:
    h = hashlib.sha256()
    for part in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(part)
    return h.hexdigest()


def snapshot_storage(root: Path) -> dict[str, tuple[int, str]]:
    if root.is_symlink() or not root.is_dir():
        reject("STORAGE_APP_NOT_REAL_DIRECTORY")
    result: dict[str, tuple[int, str]] = {}
    # fwalk carries directory descriptors; relative opens are no-follow and
    # inode-bound, unlike pathname-based os.walk/root file reads.
    def fail_walk(error: OSError) -> None:
        reject("LIVE_STORAGE_SCAN_ERROR")

    for parent, dirs, files, dirfd in os.fwalk(root, follow_symlinks=False,
                                               onerror=fail_walk):
        for name in dirs:
            info = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                reject("LIVE_STORAGE_SYMLINK_OR_SPECIAL_DIR")
        for name in files:
            before_path = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
            if not stat.S_ISREG(before_path.st_mode):
                reject("LIVE_STORAGE_NOT_REGULAR")
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(name, flags, dir_fd=dirfd)
            try:
                before = os.fstat(fd)
                if (not stat.S_ISREG(before.st_mode) or
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                     before.st_ctime_ns) !=
                    (before_path.st_dev, before_path.st_ino, before_path.st_size,
                     before_path.st_mtime_ns, before_path.st_ctime_ns)):
                    reject("LIVE_STORAGE_REPLACED")
                with os.fdopen(os.dup(fd), "rb") as stream:
                    checksum = digest(stream)
                after = os.fstat(fd)
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                    before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns):
                    reject("LIVE_STORAGE_CHANGED")
                relative_parent = Path(parent).relative_to(root)
                rel = (relative_parent / name).as_posix()
                result[rel] = (before.st_size, checksum)
            finally:
                os.close(fd)
    return result


def archive_storage(bundle: Path) -> dict[str, tuple[int, str]]:
    with tarfile.open(bundle, "r:gz") as outer:
        members = outer.getmembers()
        required = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
        if len(members) != 4 or {m.name for m in members} != required:
            reject("LOCAL_BUNDLE_LAYOUT")
        if any(not m.isfile() for m in members):
            reject("LOCAL_BUNDLE_NONREGULAR")
        entry = outer.extractfile("storage.tar.gz")
        if entry is None:
            reject("STORAGE_ARCHIVE_MISSING")
        found: dict[str, tuple[int, str]] = {}
        seen: set[str] = set()
        with entry, tarfile.open(fileobj=entry, mode="r|gz") as inner:
            for member in inner:
                name = member.name.rstrip("/")
                if (not name or name.startswith("/") or "\\" in name
                    or any(p in (".", "..", "") for p in name.split("/"))
                    or name in seen):
                    reject("STORAGE_MEMBER_UNSAFE")
                seen.add(name)
                if name == ".env":
                    if not member.isfile():
                        reject("ENV_MEMBER_INVALID")
                    continue
                if name != "storage/app" and not name.startswith("storage/app/"):
                    reject("STORAGE_MEMBER_OUTSIDE_APP")
                if not (member.isdir() or member.isfile()):
                    reject("STORAGE_MEMBER_NOT_REGULAR")
                if member.isfile():
                    if name == "storage/app":
                        reject("STORAGE_APP_NOT_DIRECTORY")
                    stream = inner.extractfile(member)
                    if stream is None:
                        reject("STORAGE_MEMBER_UNREADABLE")
                    with stream:
                        checksum = digest(stream)
                    found[name[len("storage/app/"):]] = (member.size, checksum)
        return found


def audit(release: Path, bundle: Path, witness: Path, candidate: str,
          current: str) -> dict[str, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        reject("CANDIDATE_INVALID")
    if not re.fullmatch(r"platform-[0-9a-f]{12}", current):
        reject("RELEASE_INVALID")
    with witness.open("r", encoding="utf-8") as stream:
        record = json.load(stream)
    if (record.get("approvedSha") != candidate or
        record.get("currentRelease") != current):
        reject("WITNESS_IDENTITY_MISMATCH")
    with bundle.open("rb") as stream:
        if digest(stream) != record.get("backupSha256"):
            reject("LOCAL_BUNDLE_SHA_MISMATCH")
    archived = archive_storage(bundle)
    live = snapshot_storage(release / "apps/platform/storage/app")
    public = release / "apps/platform/public"
    link = public / "storage"
    expected = release / "apps/platform/storage/app/public"
    linked = link.is_symlink() and link.resolve(strict=False) == expected.resolve(strict=False)
    alternate = any((public / name).exists() or (public / name).is_symlink()
                    for name in ("uploads", "media", "product-images"))
    parity = archived == live
    return {
        "ARCHIVED_STORAGE_FILES": str(len(archived)),
        "ARCHIVED_STORAGE_BYTES": str(sum(size for size, _ in archived.values())),
        "LIVE_STORAGE_FILES": str(len(live)),
        "LIVE_STORAGE_BYTES": str(sum(size for size, _ in live.values())),
        "STORAGE_APP_CONTENT_PARITY": "PASS" if parity else "MISMATCH",
        "PUBLIC_STORAGE_LINK": "EXPECTED" if linked else "MISSING_OR_DIFFERENT",
        "ALTERNATE_PUBLIC_UPLOAD_DIRS": "PRESENT_REVIEW" if alternate else "NONE_OBSERVED",
        "ALL_CUSTOMER_UPLOAD_LOCATIONS_VERIFIED": "NO",
        "OWNER_AUTHENTICATED_UPLOAD_QA": "NOT_VERIFIED",
        "PRODUCTION_RELEASE_MODIFIED": "NO",
    }


def protected(path: Path) -> bool:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            return False
        if stat.S_IMODE(info.st_mode) != 0o600:
            return False
        parent = path.parent
        while True:
            p = parent.lstat()
            if (not stat.S_ISDIR(p.st_mode) or p.st_uid != 0
                or stat.S_IMODE(p.st_mode) & 0o022):
                return False
            if parent == parent.parent:
                return True
            parent = parent.parent
    except OSError:
        return False


def main(argv: list[str]) -> int:
    if (len(argv) != 4 or argv[0] != "--candidate-sha" or
        argv[2] != "--expected-release" or
        not re.fullmatch(r"[0-9a-f]{40}", argv[1]) or
        not re.fullmatch(r"platform-[0-9a-f]{12}", argv[3])):
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_ARGUMENTS")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_OPERATOR")
        return 2
    candidate, current = argv[1], argv[3]
    pointer = Path("/home/kmjprod/current")
    release = Path("/home/kmjprod/releases") / current
    backup = Path("/var/backups/kmj-platform")
    bundle = backup / f"pre-deploy-{candidate[:12]}.tar.gz"
    witness = backup / f"pre-deploy-{candidate[:12]}.json"
    try:
        if not pointer.is_symlink() or pointer.resolve(strict=True) != release:
            reject("CURRENT_POINTER_MISMATCH")
        if not protected(bundle) or not protected(witness):
            reject("BACKUP_WITNESS_NOT_ROOT_PROTECTED")
        result = audit(release, bundle, witness, candidate, current)
        for key, value in result.items():
            print(f"{key}={value}")
        if (result["STORAGE_APP_CONTENT_PARITY"] != "PASS" or
            result["PUBLIC_STORAGE_LINK"] != "EXPECTED" or
            result["ALTERNATE_PUBLIC_UPLOAD_DIRS"] != "NONE_OBSERVED"):
            print("BACKUP_UPLOAD_AUDIT=REVIEW_REQUIRED")
            return 2
        print("BACKUP_UPLOAD_AUDIT=STORAGE_APP_ONLY_PASS")
        return 0
    except (CoverageError, OSError, ValueError, KeyError, tarfile.TarError,
            json.JSONDecodeError) as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_]+", reason):
            reason = "READ_FAILED"
        print("BACKUP_UPLOAD_AUDIT=BLOCKED_" + reason)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
