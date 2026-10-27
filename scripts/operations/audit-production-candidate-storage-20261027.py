#!/usr/bin/env python3
"""No-write production candidate storage diff: filenames and hashes are private."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

BASE = Path("/home/kmjprod")
CURRENT = BASE / "current"
RELEASES = BASE / "releases"
CAP_BYTES = 256 * 1024 * 1024
CAP_FILES = 100000

def stop(reason):
    print("KMJ_PROD_STORAGE_AUDIT=BLOCKED_" + reason)
    raise SystemExit(2)

def require(condition, reason):
    if not condition: stop(reason)

def git_head(path):
    result = subprocess.run(
        ["/usr/sbin/runuser", "-u", "kmjprod", "--", "git",
         "-C", str(path), "rev-parse", "--verify", "HEAD"],
        check=False, capture_output=True, text=True, timeout=15)
    require(result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()),
            "GIT_UNVERIFIED")
    return result.stdout.strip()

def inventory(root):
    require(root.is_dir() and not root.is_symlink(), "STORAGE_APP_ROOT_UNSAFE")
    require(root.resolve(strict=True).is_relative_to(BASE), "STORAGE_OUTSIDE_PRODUCTION")
    files, symlinks = {}, 0
    budget = 0
    for directory, subdirs, filenames in os.walk(root, followlinks=False):
        parent = Path(directory)
        for d in list(subdirs):
            entry = parent / d
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode):
                subdirs.remove(d)
                symlinks += 1
            else:
                require(stat.S_ISDIR(mode), "UNEXPECTED_DIRECTORY_TYPE")
        for f in filenames:
            path = parent / f
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                symlinks += 1
                continue
            require(stat.S_ISREG(mode), "UNEXPECTED_FILE_TYPE")
            relative = path.relative_to(root).as_posix()
            opened = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                before = os.fstat(opened)
                require(stat.S_ISREG(before.st_mode), "FILE_RACE")
                budget += before.st_size
                require(budget <= CAP_BYTES and len(files) < CAP_FILES, "INVENTORY_BUDGET")
                digest = hashlib.sha256()
                with os.fdopen(opened, "rb", closefd=False) as stream:
                    for block in iter(lambda: stream.read(1024*1024), b""):
                        digest.update(block)
                after = os.fstat(opened)
                require(before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns,
                        "CONCURRENT_FILE_CHANGE")
                files[relative] = (before.st_size, digest.hexdigest())
            finally:
                os.close(opened)
    return files, symlinks

def main():
    require(len(sys.argv) == 2 and re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]) is not None,
            "EXACT_SHA")
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
            "HOST")
    target = sys.argv[1]
    require(CURRENT.is_symlink(), "LIVE_LINK")
    old_release = CURRENT.resolve(strict=True)
    require(old_release.is_relative_to(RELEASES) and
            re.fullmatch(r"platform-[0-9a-f]{12}", old_release.name) is not None,
            "LIVE_RELEASE")
    candidate = RELEASES / ("platform-" + target[:12])
    require(candidate.is_dir() and not candidate.is_symlink(), "CANDIDATE_MISSING")
    require(git_head(candidate) == target, "CANDIDATE_SHA")
    print("LIVE_RELEASE=" + old_release.name)
    print("CANDIDATE_SHA=" + target)
    for disk in ("public", "private"):
        old = old_release / "apps/platform/storage/app" / disk
        new = candidate / "apps/platform/storage/app" / disk
        a, al = inventory(old)
        b, bl = inventory(new)
        ka, kb = set(a), set(b)
        shared = ka & kb
        same = sum(a[k] == b[k] for k in shared)
        conflict = len(shared) - same
        label = disk.upper()
        print(f"{label}_OLD_FILES={len(a)}")
        print(f"{label}_CANDIDATE_FILES={len(b)}")
        print(f"{label}_MATCHING_FILES={same}")
        print(f"{label}_CONFLICTS={conflict}")
        print(f"{label}_OLD_ONLY={len(ka-kb)}")
        print(f"{label}_CANDIDATE_ONLY={len(kb-ka)}")
        print(f"{label}_OLD_SYMLINKS={al}")
        print(f"{label}_CANDIDATE_SYMLINKS={bl}")
        print(f"{label}_CONTINUITY=" +
              ("IDENTICAL_CONTENT" if a == b and al == bl == 0 else
               "NEEDS_GUARDED_PRESERVATION"))
    require(CURRENT.resolve(strict=True) == old_release, "PRODUCTION_POINTER_CHANGED")
    print("PRODUCTION_POINTER=UNCHANGED")
    print("KMJ_PROD_STORAGE_AUDIT=READ_ONLY_COMPLETE")
if __name__ == "__main__":
    try: main()
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError):
        stop("UNVERIFIED_RUNTIME")
