#!/usr/bin/env python3
"""Fail-closed, no-dereference storage inventory for exact release materialization.

Prints a deterministic manifest digest of regular-file bytes, metadata, paths,
and raw symlink targets. Does NOT attest linked target bytes, writer quiescence,
or independent offsite restore. Ignores only regular .gitignore placeholders.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


def inventory(root: Path) -> dict[str, object]:
    root = Path(root)
    root_stat = os.lstat(root)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError("STORAGE_ROOT_NOT_REAL_DIRECTORY")

    entries: list[list[object]] = []
    counts = {"regular": 0, "symlinks": 0, "directories": 0}

    def visit(directory: Path, prefix: str) -> None:
        before = os.lstat(directory)
        if not stat.S_ISDIR(before.st_mode):
            raise ValueError("DIRECTORY_REPLACED")
        with os.scandir(directory) as scan:
            children = sorted(scan, key=lambda item: item.name)
        for child in children:
            path = directory / child.name
            relative = f"{prefix}/{child.name}" if prefix else child.name
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                entries.append(["d", relative])
                counts["directories"] += 1
                visit(path, relative)
            elif stat.S_ISREG(info.st_mode):
                if child.name == ".gitignore":
                    continue
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(path, flags)
                try:
                    opened = os.fstat(fd)
                    if not stat.S_ISREG(opened.st_mode) or (
                        opened.st_dev, opened.st_ino
                    ) != (info.st_dev, info.st_ino):
                        raise ValueError("FILE_REPLACED_DURING_SCAN")
                    digest = hashlib.sha256()
                    while chunk := os.read(fd, 1024 * 1024):
                        digest.update(chunk)
                    after = os.fstat(fd)
                    now = os.lstat(path)
                    if (opened.st_dev, opened.st_ino, opened.st_size,
                        opened.st_mtime_ns, opened.st_ctime_ns) != (
                        after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns
                    ) or (now.st_dev, now.st_ino) != (opened.st_dev, opened.st_ino):
                        raise ValueError("FILE_CHANGED_DURING_SCAN")
                finally:
                    os.close(fd)
                entries.append(["f", relative, opened.st_size, digest.hexdigest(),
                                stat.S_IMODE(opened.st_mode), opened.st_uid,
                                opened.st_gid, opened.st_mtime_ns])
                counts["regular"] += 1
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                now = os.lstat(path)
                if (info.st_dev, info.st_ino, info.st_mtime_ns) != (
                    now.st_dev, now.st_ino, now.st_mtime_ns
                ):
                    raise ValueError("SYMLINK_CHANGED_DURING_SCAN")
                entries.append(["l", relative, target, info.st_uid, info.st_gid,
                                info.st_mtime_ns])
                counts["symlinks"] += 1
            else:
                raise ValueError("UNSUPPORTED_STORAGE_ENTRY")
        after = os.lstat(directory)
        if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_mtime_ns
        ):
            raise ValueError("DIRECTORY_CHANGED_DURING_SCAN")

    visit(root, "")
    payload = json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(payload).hexdigest(), **counts}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("STORAGE_MANIFEST=BLOCKED_USAGE", file=sys.stderr)
        return 2
    try:
        result = inventory(Path(argv[1]))
    except (OSError, ValueError) as exc:
        print(f"STORAGE_MANIFEST=BLOCKED_{type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
