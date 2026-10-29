#!/usr/bin/env python3
"""Descriptor-relative, no-follow storage inventory with access metadata."""
from __future__ import annotations
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

def _directory(path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for name in Path(os.path.abspath(path)).parts[1:]:
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError as error:
        os.close(fd)
        raise ValueError("STORAGE_ROOT_NOT_REAL_DIRECTORY") from error

def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def inventory(root: Path) -> dict[str, object]:
    root_fd = _directory(root)
    entries = []
    counts = {"regular": 0, "symlinks": 0, "directories": 0}
    def visit(fd, prefix):
        before = os.fstat(fd)
        entries.append(["d", prefix, stat.S_IMODE(before.st_mode), before.st_uid, before.st_gid])
        for name in sorted(os.listdir(fd)):
            relative = prefix + "/" + name if prefix else name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if _stamp(os.fstat(child)) != _stamp(info):
                        raise ValueError("DIRECTORY_REPLACED")
                    counts["directories"] += 1
                    visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if name == ".gitignore":
                    continue
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    if not stat.S_ISREG(opened.st_mode) or _stamp(opened) != _stamp(info):
                        raise ValueError("FILE_REPLACED_DURING_SCAN")
                    digest = hashlib.sha256()
                    while chunk := os.read(child, 1024 * 1024):
                        digest.update(chunk)
                    if _stamp(os.fstat(child)) != _stamp(opened):
                        raise ValueError("FILE_CHANGED_DURING_SCAN")
                finally:
                    os.close(child)
                entries.append(["f", relative, opened.st_size, digest.hexdigest(),
                    stat.S_IMODE(opened.st_mode), opened.st_uid, opened.st_gid, opened.st_mtime_ns])
                counts["regular"] += 1
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(name, dir_fd=fd)
                entries.append(["l", relative, target, info.st_uid, info.st_gid, info.st_mtime_ns])
                counts["symlinks"] += 1
            else:
                raise ValueError("UNSUPPORTED_STORAGE_ENTRY")
            if _stamp(os.stat(name, dir_fd=fd, follow_symlinks=False)) != _stamp(info):
                raise ValueError("ENTRY_CHANGED_DURING_SCAN")
        if _stamp(os.fstat(fd)) != _stamp(before):
            raise ValueError("DIRECTORY_CHANGED_DURING_SCAN")
    try:
        visit(root_fd, "")
        current = _directory(root)
        try:
            if _stamp(os.fstat(current)) != _stamp(os.fstat(root_fd)):
                raise ValueError("STORAGE_ROOT_REPLACED")
        finally:
            os.close(current)
    finally:
        os.close(root_fd)
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
