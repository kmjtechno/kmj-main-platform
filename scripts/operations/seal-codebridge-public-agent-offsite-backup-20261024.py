#!/usr/bin/env python3
"""Prepare one age-encrypted, sanitized offsite copy of the verified P0 backup.

Operator-only, non-deploying, never imports the production .env into the
transferable bundle. This script does NOT transfer data or establish offsite
restore/production approval. The original root-owned witnessed local archive
is never modified.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path("/var/backups/kmj-platform")
ORIGINAL = ROOT / "pre-deploy-b1d672bbc83a.tar.gz"
WITNESS = ROOT / "pre-deploy-b1d672bbc83a.json"
OUTPUT = ROOT / "offsite-b1d672bbc83a.tar.gz.age"
CURRENT = Path("/home/kmjprod/current")
EXPECTED_RELEASE = Path("/home/kmjprod/releases/platform-8070dad72c55")
TARGET_SHA = "b1d672bbc83a51ca3f8271435692825072444c8e"
RECIPIENT = "age1952vsyz25elfzn8slyhuc4k586dhw0er45yy26myhvv3lcp9qeps8mj7f5"
MEMBERS = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
MAX_FILES = 100_000
MAX_STORAGE_UNCOMPRESSED = 256 * 1024 * 1024 * 1024


def fail(reason: str) -> None:
    raise RuntimeError(reason)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for part in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verify_root_only(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        fail("SOURCE_NOT_ROOT_ONLY")


def validate_manifest(directory: Path) -> None:
    lines = (directory / "SHA256SUMS").read_text("ascii").splitlines()
    match = [re.fullmatch(r"([0-9a-f]{64})  (database\.dump|storage\.tar\.gz|metadata\.txt)", line) for line in lines]
    if len(match) != 3 or any(item is None for item in match):
        fail("MANIFEST_INVALID")
    entries = {item.group(2): item.group(1) for item in match if item}
    if set(entries) != MEMBERS - {"SHA256SUMS"}:
        fail("MANIFEST_FILENAMES_INVALID")
    for filename, expected in entries.items():
        if digest(directory / filename) != expected:
            fail("SOURCE_COMPONENT_DIGEST_MISMATCH")


def repack_verified_local(original: Path, witness: Path, scratch: Path) -> tuple[Path, str]:
    """Fail closed and return a standard 4-member archive with no root .env."""
    verify_root_only(original)
    verify_root_only(witness)
    record = json.loads(witness.read_text("utf-8"))
    if record.get("approvedSha") != TARGET_SHA or record.get("currentRelease") != EXPECTED_RELEASE.name:
        fail("WITNESS_RELEASE_MISMATCH")
    source_hash = digest(original)
    if record.get("backupSha256") != source_hash:
        fail("WITNESS_DIGEST_MISMATCH")

    with tarfile.open(original, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != 4 or {m.name for m in members} != MEMBERS:
            fail("SOURCE_BUNDLE_MEMBERS_INVALID")
        if any(not m.isfile() or m.size <= 0 for m in members):
            fail("SOURCE_BUNDLE_NONREGULAR_MEMBER")
        if any(m.size > 16384 for m in members if m.name in {"metadata.txt", "SHA256SUMS"}):
            fail("SOURCE_BUNDLE_METADATA_TOO_LARGE")
        for member in members:
            stream = archive.extractfile(member)
            if stream is None:
                fail("SOURCE_BUNDLE_UNREADABLE")
            with stream, (scratch / member.name).open("xb") as out:
                shutil.copyfileobj(stream, out, 1024 * 1024)

    validate_manifest(scratch)
    metadata = (scratch / "metadata.txt").read_text("utf-8")
    if (
        f"approved_sha={TARGET_SHA}" not in metadata.splitlines()
        or f"current_release={EXPECTED_RELEASE.name}" not in metadata.splitlines()
    ):
        fail("SOURCE_METADATA_MISMATCH")

    sanitized = scratch / "sanitized-storage.tar.gz"
    env_seen = 0
    storage_seen = 0
    path_seen: set[str] = set()
    file_count = 0
    total_bytes = 0
    with tarfile.open(scratch / "storage.tar.gz", "r:gz") as source:
        with tarfile.open(sanitized, "w:gz") as target:
            for member in source:
                file_count += 1
                total_bytes += member.size
                name = member.name.rstrip("/")
                normal = PurePosixPath(name)
                if (
                    not name or name != normal.as_posix() or normal.is_absolute()
                    or ".." in normal.parts or "\\" in name
                    or name in path_seen or member.sparse is not None
                    or file_count > MAX_FILES or total_bytes > MAX_STORAGE_UNCOMPRESSED
                    or not (member.isfile() or member.isdir())
                ):
                    fail("UNSAFE_STORAGE_ARCHIVE_MEMBER")
                path_seen.add(name)
                if name == ".env":
                    if not member.isfile():
                        fail("ENV_MEMBER_NOT_REGULAR")
                    env_seen += 1
                    continue
                if name != "storage/app" and not name.startswith("storage/app/"):
                    fail("UNEXPECTED_STORAGE_ARCHIVE_MEMBER")
                storage_seen += 1
                stream = source.extractfile(member) if member.isfile() else None
                try:
                    target.addfile(member, stream)
                finally:
                    if stream is not None:
                        stream.close()
    if env_seen != 1 or storage_seen < 1:
        fail("SOURCE_STORAGE_CONTRACT_MISMATCH")

    # Build a new manifest; do not reuse the source one after stripping .env.
    (scratch / "storage.tar.gz").unlink()
    sanitized.rename(scratch / "storage.tar.gz")
    (scratch / "metadata.txt").write_text(
        "backup_kind=offsite_sanitized_local_witness\n"
        f"source_local_sha256={source_hash}\n"
        f"target_sha={TARGET_SHA}\n"
        f"current_release={EXPECTED_RELEASE.name}\n"
        "production_env_excluded=YES\n",
        encoding="ascii",
    )
    with (scratch / "SHA256SUMS").open("w", encoding="ascii") as manifest:
        for filename in ("database.dump", "storage.tar.gz", "metadata.txt"):
            manifest.write(f"{digest(scratch / filename)}  {filename}\n")
    validate_manifest(scratch)

    outer = scratch / "bundle.tar.gz"
    with tarfile.open(outer, "w:gz") as bundle:
        for filename in ("database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"):
            path = scratch / filename
            entry = tarfile.TarInfo(name=filename)
            entry.size = path.stat().st_size
            entry.mode = 0o600
            with path.open("rb") as inp:
                bundle.addfile(entry, inp)
    return outer, source_hash


def main() -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        fail("WRONG_OPERATOR_OR_HOST")
    if not CURRENT.is_symlink() or CURRENT.resolve(strict=True) != EXPECTED_RELEASE:
        fail("PRODUCTION_RELEASE_CHANGED")
    dir_stat = ROOT.lstat()
    if not stat.S_ISDIR(dir_stat.st_mode) or dir_stat.st_uid != 0:
        fail("BACKUP_DIRECTORY_UNSAFE")
    if OUTPUT.exists() or OUTPUT.is_symlink():
        fail("ENCRYPTED_OUTPUT_EXISTS")
    if shutil.which("age") is None:
        fail("MISSING_AGE")
    verify_root_only(ORIGINAL)
    verify_root_only(WITNESS)
    free = shutil.disk_usage(ROOT).free
    required = max(512 * 1024 * 1024, ORIGINAL.stat().st_size * 4 + 256 * 1024 * 1024)
    if free < required:
        fail("INSUFFICIENT_ENCRYPTION_SCRATCH")
    lock = os.open(
        "/run/lock/kmj-main-platform-production-release.lock",
        os.O_CREAT | os.O_WRONLY | os.O_CLOEXEC, 0o600,
    )
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix=".kmj-seal-offsite-", dir=ROOT) as tempdir:
            scratch = Path(tempdir)
            outer, source_hash = repack_verified_local(ORIGINAL, WITNESS, scratch)
            sealed = scratch / "sealed.age"
            check = subprocess.run(
                ["age", "-r", RECIPIENT, "-o", str(sealed), str(outer)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,
                check=False,
            )
            if check.returncode or not sealed.is_file() or not sealed.stat().st_size:
                fail("AGE_ENCRYPTION_FAILED")
            os.chmod(sealed, 0o600)
            if CURRENT.resolve(strict=True) != EXPECTED_RELEASE:
                fail("PRODUCTION_RELEASE_CHANGED")
            # Atomic hardlink, same filesystem; never overwrite an existing file.
            os.link(sealed, OUTPUT)
            print("SOURCE_WITNESS=PASS")
            print("SOURCE_LOCAL_SHA256=" + source_hash)
            print("ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS")
            print("ENCRYPTED_OFFSITE_BUNDLE=PASS")
            print("ENCRYPTED_SHA256=" + digest(OUTPUT))
            print("ENCRYPTED_BYTES=" + str(OUTPUT.stat().st_size))
            print("OFFSITE_TRANSFER=NOT_ATTEMPTED")
            print("PRODUCTION_RELEASE=UNCHANGED")
            print("PRODUCTION_DB=UNTOUCHED")
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as exc:
        reason = str(exc)
        print("OFFSITE_SEAL=BLOCKED " + (reason if re.fullmatch(r"[A-Z0-9_]+", reason) else "VALIDATION_FAILED"))
        sys.exit(2)
