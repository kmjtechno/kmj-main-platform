#!/usr/bin/env python3
"""Read-only diagnostic for the Elite autopublish candidate identity check.

No deploy, repair, approval, backup, network access or source mutation.
Run as root on KMJ-elite with the exact expected live SHA. Git runs as
kmjprod. Output is categorical only; no paths, diff, config or secrets.
"""
import argparse
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

ROOT = Path("/home/kmjprod")
RELEASES = ROOT / "releases"
LIVE = ROOT / "current"
SHARED = ROOT / "shared/storage"
SHA = re.compile(r"[0-9a-f]{40}")
STORAGE = "apps/platform/storage"


def git_probe(folder, *args):
    try:
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", "kmjprod", "--", "/usr/bin/git",
             "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-C", str(folder), *args],
            cwd="/", env={"PATH": "/usr/bin:/bin", "HOME": "/root",
                          "LANG": "C", "GIT_OPTIONAL_LOCKS": "0",
                          "GIT_TERMINAL_PROMPT": "0"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=25, check=False,
        )
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return -1, b""


def diff_state(code):
    return {0: "CLEAN", 1: "DIFFERS"}.get(code, "UNAVAILABLE")


def storage_state(app, shared):
    try:
        path = app / "storage"
        info = path.lstat()
        if not stat.S_ISLNK(info.st_mode):
            return "DIRECTORY" if stat.S_ISDIR(info.st_mode) else "UNEXPECTED"
        if shared.is_symlink() or not shared.is_dir():
            return "SHARED_TARGET_UNVERIFIED"
        return ("EXACT_SHARED_LINK" if path.resolve(strict=True)
                == shared.resolve(strict=True) else "WRONG_LINK_TARGET")
    except (OSError, RuntimeError):
        return "UNAVAILABLE"


def classify(head, index, whole, outside, storage, stable):
    if not stable:
        return "LIVE_POINTER_CHANGED"
    if not head:
        return "HEAD_UNVERIFIED"
    if index != "CLEAN":
        return "INDEX_" + index
    if outside != "CLEAN":
        return "NON_STORAGE_" + outside
    if whole == "DIFFERS" and storage == "EXACT_SHARED_LINK":
        return "SHARED_STORAGE_DIFF_ONLY"
    if whole == "CLEAN":
        return "TRACKED_TREE_CLEAN"
    return "FULL_DIFF_" + whole


def inspect(target):
    folder = RELEASES / ("platform-" + target[:12])
    try:
        if (not LIVE.is_symlink() or folder.is_symlink()
                or not folder.is_dir() or LIVE.resolve(strict=True) != folder):
            return {"DIAGNOSIS": "LIVE_IDENTITY_MISMATCH"}
        if folder.resolve(strict=True) != folder:
            return {"DIAGNOSIS": "RELEASE_PATH_UNVERIFIED"}
        app = folder / "apps/platform"
        if app.resolve(strict=True) != app or not app.is_dir():
            return {"DIAGNOSIS": "APP_PATH_UNVERIFIED"}
        code, head = git_probe(folder, "rev-parse", "--verify", "HEAD")
        exact = code == 0 and head.strip() == target.encode("ascii")
        if not exact:
            return {"HEAD": "UNVERIFIED", "DIAGNOSIS": "HEAD_UNVERIFIED"}
        index = diff_state(git_probe(folder, "diff", "--cached",
                                     "--no-ext-diff", "--quiet", "HEAD", "--")[0])
        whole = diff_state(git_probe(folder, "diff", "--no-ext-diff",
                                     "--quiet", "HEAD", "--")[0])
        outside = diff_state(git_probe(folder, "diff", "--no-ext-diff",
                                       "--quiet", "HEAD", "--", ".",
                                       ":(literal,exclude)" + STORAGE)[0])
        layout = storage_state(app, SHARED)
        code2, head2 = git_probe(folder, "rev-parse", "--verify", "HEAD")
        stable = (LIVE.is_symlink() and LIVE.resolve(strict=True) == folder
                  and code2 == 0 and head2.strip() == head.strip())
        return {
            "HEAD": "EXACT",
            "INDEX": index,
            "FULL_TRACKED_TREE": whole,
            "NON_STORAGE_TRACKED_TREE": outside,
            "STORAGE_LAYOUT": layout,
            "DIAGNOSIS": classify(exact, index, whole, outside, layout, stable),
        }
    except (OSError, RuntimeError):
        return {"DIAGNOSIS": "HOST_READBACK_UNAVAILABLE"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("DIAGNOSIS=WRONG_HOST_OR_OPERATOR")
        return 2
    if not SHA.fullmatch(args.sha):
        print("DIAGNOSIS=INVALID_SHA")
        return 2
    for key, value in inspect(args.sha).items():
        print(f"{key}={value}")
    print("AUTHORIZATION=NOT_GRANTED")
    print("PRODUCTION_MUTATION=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
