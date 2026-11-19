#!/usr/bin/env python3
"""KMJ-elite: real disposable upload-file restore from a local root backup.

This is NOT an approval or production release. The existing exact-release
backup runner already proved PostgreSQL restoration but only *listed* the
storage tar; this independently extracts storage/app and .env into private
scratch, verifies every restored byte, and binds the proof to the existing
root-owned exact-candidate bundle and SHA witness.

No production database connections, no network, no symlinks, no services,
no persistent restore file, no approval writes, and no live pointer mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import tarfile
import tempfile

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
RELEASE = re.compile(r"platform-[0-9a-f]{12}\Z")
MAX_ARCHIVE = 4 * 1024**3
MAX_UNPACKED = 64 * 1024**3
MAX_ENTRIES = 100_000
RESERVE = 4 * 1024**3
BACKUP = Path("/var/backups/kmj-platform")
LIVE = Path("/home/kmjprod/current")


class Blocked(Exception):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise Blocked(reason)


def digest(stream) -> str:
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
    return h.hexdigest()


def read_protected(path: Path, maximum: int, uid: int) -> bytes:
    """One regular root-owned inode; reject link/race and noncanonical bytes."""
    try:
        original = os.lstat(path)
        require(stat.S_ISREG(original.st_mode) and original.st_uid == uid
                and original.st_nlink == 1 and 0 < original.st_size <= maximum
                and not original.st_mode & 0o077, "PROTECTED_FILE_INVALID")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            current = os.fstat(fd)
            require((current.st_dev, current.st_ino) ==
                    (original.st_dev, original.st_ino), "PROTECTED_INODE_CHANGED")
            data = bytearray()
            while len(data) <= maximum:
                block = os.read(fd, min(1024 * 1024, maximum + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            after = os.fstat(fd)
            path_now = os.lstat(path)
            fields = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns,
                                x.st_ctime_ns, x.st_mode, x.st_uid, x.st_nlink)
            require(fields(original) == fields(current) ==
                    fields(after) == fields(path_now) and
                    len(data) == original.st_size, "PROTECTED_FILE_CHANGED")
            return bytes(data)
        finally:
            os.close(fd)
    except (OSError, ValueError):
        raise Blocked("PROTECTED_FILE_READ_FAILED") from None


def unique_pairs(pairs):
    values = {}
    for key, value in pairs:
        require(key not in values, "DUPLICATE_WITNESS_KEY")
        values[key] = value
    return values


def verify_witness(path: Path, sha: str, predecessor: str, uid: int) -> str:
    raw = read_protected(path, 4096, uid)
    try:
        record = json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError):
        raise Blocked("WITNESS_JSON_INVALID") from None
    require(isinstance(record, dict) and set(record) ==
            {"approvedSha", "currentRelease", "backupSha256"},
            "WITNESS_SCHEMA_INVALID")
    require(record["approvedSha"] == sha and
            record["currentRelease"] == predecessor and
            isinstance(record["backupSha256"], str) and
            HEX64.fullmatch(record["backupSha256"]) is not None,
            "WITNESS_CANDIDATE_MISMATCH")
    return record["backupSha256"]


def safe_member_name(name: str) -> tuple[str, ...]:
    require(isinstance(name, str) and len(name) <= 4096, "TAR_MEMBER_UNSAFE")
    raw = name.rstrip("/")
    parts = raw.split("/")
    require(raw and not raw.startswith("/") and
            all(p not in ("", ".", "..") and len(p) <= 255 and
                not any(ord(c) < 32 or c in "\\:" for c in p) for p in parts),
            "TAR_MEMBER_UNSAFE")
    return tuple(parts)


def read_tar_member(archive: tarfile.TarFile, item: tarfile.TarInfo,
                    max_bytes: int, save_to: Path | None = None) -> str:
    require(item.isfile() and 0 <= item.size <= max_bytes and
            item.sparse is None, "TAR_MEMBER_INVALID")
    member = archive.extractfile(item)
    require(member is not None, "TAR_MEMBER_UNREADABLE")
    h = hashlib.sha256()
    actual = 0
    fd = None
    if save_to is not None:
        fd = os.open(save_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with member:
            while chunk := member.read(1024 * 1024):
                actual += len(chunk)
                require(actual <= item.size, "TAR_MEMBER_OVERRUN")
                h.update(chunk)
                if fd is not None:
                    view = memoryview(chunk)
                    while view:
                        used = os.write(fd, view)
                        require(used > 0, "TAR_MEMBER_SHORT_WRITE")
                        view = view[used:]
        require(actual == item.size, "TAR_MEMBER_TRUNCATED")
        if fd is not None:
            os.fsync(fd)
    finally:
        if fd is not None:
            os.close(fd)
    return h.hexdigest()


def verify_inner_and_restore(inner: Path, scratch: Path) -> tuple[int, int]:
    """Validate all names/types/capacity, extract into root-private scratch, rehash."""
    expected: dict[str, tuple[int, str]] = {}
    directories = set()
    seen = set()
    total_bytes = 0
    with tarfile.open(inner, "r:gz") as archive:
        for item in archive:
            parts = safe_member_name(item.name)
            key = "/".join(parts)
            require(key not in seen and len(seen) < MAX_ENTRIES,
                    "DUPLICATE_OR_EXCESS_STORAGE_MEMBER")
            seen.add(key)
            require(key == ".env" or parts[:2] == ("storage", "app"),
                    "STORAGE_MEMBER_OUTSIDE_ALLOWED_ROOT")
            require(item.isfile() or item.isdir(), "STORAGE_MEMBER_LINK_OR_SPECIAL")
            require(item.size >= 0 and item.sparse is None,
                    "STORAGE_MEMBER_UNSAFE_SIZE")
            if key == ".env":
                require(item.isfile(), "ENV_NOT_REGULAR")
            elif key == "storage/app":
                require(item.isdir(), "STORAGE_APP_NOT_DIRECTORY")
            if item.isdir():
                directories.add(key)
                continue
            total_bytes += item.size
            require(total_bytes <= MAX_UNPACKED, "STORAGE_CAP_EXCEEDED")
            expected[key] = (item.size, read_tar_member(archive, item, MAX_UNPACKED))
    require("storage/app" in directories and ".env" in expected and
            len(expected) >= 2, "STORAGE_OR_ENV_MISSING")
    free = shutil.disk_usage(scratch).free
    require(free > total_bytes + RESERVE, "STORAGE_RESTORE_DISK_INSUFFICIENT")

    restored = scratch / "restored"
    restored.mkdir(mode=0o700)
    with tarfile.open(inner, "r:gz") as archive:
        second_seen = set()
        for item in archive:
            parts = safe_member_name(item.name)
            key = "/".join(parts)
            require(key in seen and key not in second_seen,
                    "STORAGE_ARCHIVE_CHANGED")
            second_seen.add(key)
            destination = restored.joinpath(*parts)
            if item.isdir():
                require(key in directories, "STORAGE_DIRECTORY_CHANGED")
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                actual = read_tar_member(archive, item, MAX_UNPACKED, destination)
                require(actual == expected[key][1], "EXTRACTED_CONTENT_MISMATCH")
        require(second_seen == seen, "STORAGE_MEMBER_SET_CHANGED")
    for name, (size, sha) in expected.items():
        p = restored.joinpath(*name.split("/"))
        st = os.lstat(p)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and
                st.st_size == size and st.st_uid == os.geteuid() and
                not st.st_mode & 0o077, "RESTORED_FILE_IDENTITY")
        with p.open("rb") as stream:
            require(digest(stream) == sha, "RESTORED_FILE_SHA_READBACK")
    return len(expected) - 1, total_bytes - expected[".env"][0]


def verify_archive(archive: Path, witness: Path, sha: str, predecessor: str,
                   scratch: Path, *, uid: int) -> tuple[int, int]:
    require(HEX40.fullmatch(sha) is not None and
            RELEASE.fullmatch(predecessor) is not None and
            predecessor != "platform-" + sha[:12], "RELEASE_IDENTITY_INVALID")
    wanted = verify_witness(witness, sha, predecessor, uid)
    # Bound both the serialized bundle bytes and its logical entries.
    content = read_protected(archive, MAX_ARCHIVE, uid)
    require(hashlib.sha256(content).hexdigest() == wanted,
            "BUNDLE_WITNESS_SHA_MISMATCH")
    archive_path = scratch / "original.tar.gz"
    with archive_path.open("xb") as out:
        out.write(content)
    allowed = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
    fingerprints = {}
    sizes = {}
    with tarfile.open(archive_path, "r:gz") as bundle:
        entries = bundle.getmembers()
        require(len(entries) == 4 and {m.name for m in entries} == allowed,
                "BUNDLE_LAYOUT_INVALID")
        for entry in entries:
            require(entry.isfile() and entry.size >= 0 and
                    entry.size <= MAX_ARCHIVE, "BUNDLE_ENTRY_UNSAFE")
            sizes[entry.name] = entry.size
            fingerprints[entry.name] = read_tar_member(
                bundle, entry, MAX_ARCHIVE,
                scratch / "storage.tar.gz" if entry.name == "storage.tar.gz" else None)
        md = bundle.extractfile("metadata.txt")
        sums = bundle.extractfile("SHA256SUMS")
        require(md is not None and sums is not None and
                sizes["metadata.txt"] <= 512 and sizes["SHA256SUMS"] <= 512,
                "BUNDLE_METADATA_OVERSIZED")
        metadata = md.read().decode("ascii", "strict").splitlines()
        checksum_rows = sums.read().decode("ascii", "strict").splitlines()
    require(metadata == [
        "current_release=" + predecessor,
        "approved_sha=" + sha,
        "backup_kind=local_unencrypted_root_only",
    ], "BUNDLE_METADATA_MISMATCH")
    checked = {}
    for row in checksum_rows:
        found = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9.]+)", row)
        require(found is not None and found.group(2) not in checked,
                "BUNDLE_SHA_LIST_INVALID")
        checked[found.group(2)] = found.group(1)
    require(checked == {key: fingerprints[key]
                        for key in ("database.dump", "storage.tar.gz", "metadata.txt")},
            "BUNDLE_CONTENT_SHA_MISMATCH")
    return verify_inner_and_restore(scratch / "storage.tar.gz", scratch)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--expected-release", required=True)
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] ==
                "KMJ-elite", "ROOT_ELITE_ONLY")
        sha, previous = args.candidate_sha, args.expected_release
        require(HEX40.fullmatch(sha) is not None and
                RELEASE.fullmatch(previous) is not None, "INVALID_ARGUMENT")
        expected = Path("/home/kmjprod/releases") / previous
        require(LIVE.is_symlink() and LIVE.resolve(strict=True) == expected,
                "LIVE_POINTER_CHANGED")
        info = os.lstat(BACKUP)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
                not info.st_mode & 0o022, "BACKUP_DIR_NOT_ROOT_PROTECTED")
        bundle = BACKUP / ("pre-deploy-" + sha[:12] + ".tar.gz")
        witness = BACKUP / ("pre-deploy-" + sha[:12] + ".json")
        with tempfile.TemporaryDirectory(dir=BACKUP,
                                         prefix=".kmj-uploads-restore-") as directory:
            files, size = verify_archive(bundle, witness, sha, previous,
                                         Path(directory), uid=0)
            require(LIVE.is_symlink() and LIVE.resolve(strict=True) == expected,
                    "LIVE_POINTER_CHANGED")
        print("ELITE_UPLOADS_BACKUP_SHA256=PASS")
        print("ELITE_UPLOADS_DISPOSABLE_RESTORE=PASS")
        print("ELITE_UPLOADS_BYTE_SHA_READBACK=PASS")
        print(f"ELITE_UPLOADS_FILES_RESTORED={files}")
        print(f"ELITE_UPLOADS_BYTES_RESTORED={size}")
        print("ELITE_PG_RESTORE=NOT_ATTESTED_BY_THIS_TOOL")
        print("ROLLBACK_REHEARSAL=NOT_ATTESTED")
        print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
        print("APPROVAL_MUTATION=NONE")
        return 0
    except (Blocked, OSError, tarfile.TarError, UnicodeError, ValueError,
            KeyError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else "UNVERIFIED"
        print("ELITE_UPLOADS_DISPOSABLE_RESTORE=BLOCKED_" + reason)
        print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
        print("APPROVAL_MUTATION=NONE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
