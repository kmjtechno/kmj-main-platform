#!/usr/bin/env python3
"""Read-only, fail-closed stage uploads content integrity and copy verifier.

No filenames or file contents are included in its bounded CodeBridge receipt.
Compare includes source/destination ownership, mode and mtime parity, not just bytes.
A matching tree is NOT an encrypted backup, writer-quiescence or owner approval.
It never copies, deletes, chmods, chowns, links, deploys or signs anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat

STAGE_SHA = "9d15e14e39564ffb1e66085a483feb8331f9718f"
PROD_RELEASE = "platform-8070dad72c55"
STAGE_APP = Path("/home/kmjstage/releases") / STAGE_SHA / "apps/platform"
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_LINK = Path("/home/kmjprod/current")
SOURCE_LINK = STAGE_APP / "storage/app"
SHARED = Path("/home/kmjstage/shared")
ARTWORK = SHARED / "product-artwork"
DEST = SHARED / "kmj-platform-uploads"
QA = Path("/srv/kmj-codebridge-projects/kmj-main-platform/work/qa")

class UnsafeTree(ValueError):
    pass


def stable_stat(st: os.stat_result) -> tuple[int, ...]:
    """Detect inode, metadata or ownership swaps during descriptor scans."""
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_mode, st.st_uid, st.st_gid, st.st_nlink)


def sha256_file(dirfd: int, name: str, expected: os.stat_result) -> str:
    """Open by anchored directory FD, never following a mutable symlink."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or stable_stat(before) != stable_stat(expected)):
            raise UnsafeTree("UNSAFE_FILE")
        digest = hashlib.sha256()
        while True:
            part = os.read(fd, 1024 * 1024)
            if not part:
                break
            digest.update(part)
        after = os.fstat(fd)
        if stable_stat(before) != stable_stat(after):
            raise UnsafeTree("SOURCE_CHANGED_DURING_SCAN")
        return digest.hexdigest()
    finally:
        os.close(fd)


def inspect_tree(base: Path, artwork: Path = ARTWORK) -> dict[str, object]:
    """Hash relative names/content internally; use anchored no-follow directory FDs."""
    if not base.is_dir() or base.is_symlink():
        raise UnsafeTree("TREE_ROOT_UNSAFE")
    records: list[tuple[object, ...]] = []
    counts = {"files": 0, "symlinks": 0, "dirs": 0, "bytes": 0}
    visited: set[tuple[int, int]] = set()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

    def visit(dirfd: int, rel: Path) -> None:
        current = os.fstat(dirfd)
        if not stat.S_ISDIR(current.st_mode):
            raise UnsafeTree("DIRECTORY_UNSAFE")
        identity = (current.st_dev, current.st_ino)
        if identity in visited:
            raise UnsafeTree("DIRECTORY_LOOP")
        visited.add(identity)
        with os.scandir(dirfd) as iterator:
            names = sorted(entry.name for entry in iterator)
        for name in names:
            child_rel = rel / name
            relative_name = child_rel.as_posix()
            st = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISDIR(st.st_mode):
                subfd = os.open(name, directory_flags, dir_fd=dirfd)
                try:
                    opened = os.fstat(subfd)
                    if stable_stat(opened) != stable_stat(st):
                        raise UnsafeTree("DIRECTORY_CHANGED_DURING_SCAN")
                    counts["dirs"] += 1
                    records.append(("dir", relative_name, "", mode,
                                    st.st_uid, st.st_gid, st.st_mtime_ns))
                    visit(subfd, child_rel)
                finally:
                    os.close(subfd)
            elif stat.S_ISREG(st.st_mode):
                counts["files"] += 1
                counts["bytes"] += st.st_size
                records.append(("file", relative_name, sha256_file(dirfd, name, st),
                                    mode, st.st_uid, st.st_gid, st.st_mtime_ns))
            elif stat.S_ISLNK(st.st_mode):
                # Only the exact canonical artwork link is permitted.
                if relative_name != "private/product-artwork":
                    raise UnsafeTree("UNREVIEWED_SYMLINK")
                link_value = os.readlink(name, dir_fd=dirfd)
                if not artwork.is_dir() or artwork.is_symlink():
                    raise UnsafeTree("ARTWORK_TARGET_UNSAFE")
                # Re-resolve relative to the original parent; no data is read
                # through this symlink and the inode is rechecked below.
                link_path = base / child_rel
                if (link_path.parent / link_value).resolve(strict=True) != artwork.resolve(strict=True):
                    raise UnsafeTree("ARTWORK_LINK_ESCAPE")
                after_link = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
                if (after_link.st_dev, after_link.st_ino,
                    after_link.st_mtime_ns, after_link.st_ctime_ns) != (
                    st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns
                ):
                    raise UnsafeTree("ARTWORK_LINK_CHANGED_DURING_SCAN")
                counts["symlinks"] += 1
                records.append(("link", relative_name, "canonical-shared-artwork",
                                    mode, st.st_uid, st.st_gid, st.st_mtime_ns))
            else:
                raise UnsafeTree("SPECIAL_NODE")
        if stable_stat(current) != stable_stat(os.fstat(dirfd)):
            raise UnsafeTree("DIRECTORY_CHANGED_DURING_SCAN")

    fd = os.open(base, directory_flags)
    try:
        root_stat = os.fstat(fd)
        records.append(("root", ".", "", stat.S_IMODE(root_stat.st_mode),
                        root_stat.st_uid, root_stat.st_gid, root_stat.st_mtime_ns))
        visit(fd, Path("."))
    finally:
        os.close(fd)
    canonical = json.dumps(records, separators=(",", ":"), ensure_ascii=True)
    result: dict[str, object] = dict(counts)
    result["tree_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result


def check_live_preflight() -> Path:
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        raise UnsafeTree("OWNER_ROOT_HOST_REQUIRED")
    if (not STAGE_LINK.is_symlink()
        or STAGE_LINK.resolve(strict=True) != STAGE_APP
        or not PROD_LINK.is_symlink()
        or PROD_LINK.resolve(strict=True) != Path("/home/kmjprod/releases") / PROD_RELEASE):
        raise UnsafeTree("LIVE_RELEASE_DRIFT")
    if (not SHARED.is_dir() or SHARED.is_symlink()
        or (SHARED.lstat().st_uid, SHARED.lstat().st_gid,
            stat.S_IMODE(SHARED.lstat().st_mode)) != (0, 0, 0o755)):
        raise UnsafeTree("SHARED_PARENT_POLICY")
    if not SOURCE_LINK.is_symlink():
        raise UnsafeTree("STAGING_SOURCE_LINK_MISSING")
    source = SOURCE_LINK.resolve(strict=True)
    if not re.fullmatch(
        r"/home/kmjstage/releases/[0-9a-f]{40}/apps/platform/storage/app",
        str(source),
    ) or source.is_symlink():
        raise UnsafeTree("STAGING_SOURCE_SCOPE")
    if source.lstat().st_uid != 995:
        raise UnsafeTree("STAGING_SOURCE_OWNER_DRIFT")
    return source


def write_receipt(result: dict[str, object], *, compare: bool) -> None:
    if not QA.is_dir() or QA.is_symlink():
        raise UnsafeTree("QA_RECEIPT_PARENT_UNSAFE")
    filename = ("KMJ_STAGE_UPLOAD_COMPARE_V5_20261028.json" if compare
                else "KMJ_STAGE_UPLOAD_CONTENT_V5_20261028.json")
    path = QA / filename
    data = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 4096:
        raise UnsafeTree("RECEIPT_TOO_LARGE")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def run(compare: bool) -> int:
    source = check_live_preflight()
    before = inspect_tree(source)
    result: dict[str, object] = {
        "schema": "kmj.stage.upload-integrity.v5",
        "source_release_bound": True,
        "source_files": before["files"],
        "source_symlinks": before["symlinks"],
        "source_bytes": before["bytes"],
        "source_tree_sha256": before["tree_sha256"],
        "customer_files_modified": False,
        "prod_and_stage_pointers_modified": False,
        "offsite_restore_verified": False,
        "owner_release_approved": False,
        "copy_verified": False,
    }
    if compare:
        if not DEST.is_dir() or DEST.is_symlink():
            raise UnsafeTree("PERSISTENT_DESTINATION_MISSING")
        after = inspect_tree(DEST)
        result["copy_verified"] = before == after
        if not result["copy_verified"]:
            raise UnsafeTree("PERSISTENT_COPY_MISMATCH")
    write_receipt(result, compare=compare)
    print("KMJ_STAGE_UPLOAD_V5=" + ("COPY_IDENTICAL" if compare else "SOURCE_AUDITED"))
    # Evidence alone never authorizes changing links or production.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    try:
        return run(compare=args.compare)
    except (OSError, ValueError, RuntimeError) as exc:
        label = str(exc)
        if not re.fullmatch(r"[A-Z_]+", label):
            label = "FILESYSTEM_OR_INTEGRITY"
        print("KMJ_STAGE_UPLOAD_V5=BLOCKED_" + label)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
