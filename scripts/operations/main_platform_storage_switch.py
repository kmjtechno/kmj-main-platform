#!/usr/bin/env python3
"""Lossless, additive, reversible Main Platform storage -> shared switch.

Replaces "drain writers + atomic cutover" with a design that needs neither a
service stop nor root:

* nothing is ever deleted or overwritten; copies are create-only (link(2) of a
  fully written temp file, so an existing name always wins);
* the live ``storage`` directory is swapped for a symlink to the shared
  directory with one renameat2(RENAME_EXCHANGE); the original directory is kept
  under ``storage.pre-shared-<stamp>`` for rollback;
* writes that land in the old directory during the swap are merged into shared
  by a final additive reconcile (``reconcile`` can be re-run at any time);
* any divergent persistent file (same path, different bytes) blocks the run and
  is reported by path only - never resolved automatically.

Mutating commands need ``--apply`` and the ``--plan-id`` printed by ``plan``
for the exact current trees, so a changed tree invalidates the review.
Everything is descriptor-relative with O_NOFOLLOW; symlinks, special files and
hard-linked files in storage are refused.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path

REGENERABLE = ("framework/views/", "framework/cache/")
LOG = ("logs/",)
MAX_ENTRIES = 20000
MAX_FILE = 8 * 1024**3
RENAME_NOREPLACE = 1
RENAME_EXCHANGE = 2
PRE = "storage.pre-shared-"
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class Blocked(Exception):
    pass


def need(cond: bool, reason: str) -> None:
    if not cond:
        raise Blocked(reason)


def klass(rel: str) -> str:
    if rel.startswith(REGENERABLE):
        return "regenerable"
    if rel.startswith(LOG):
        return "log"
    return "persistent"


def open_dir(path: str | Path) -> int:
    fd = os.open("/", DIR_FLAGS)
    try:
        for part in Path(os.path.abspath(path)).parts[1:]:
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except OSError as exc:
        os.close(fd)
        raise Blocked("NOT_A_REAL_DIRECTORY") from exc


def _hash_fd(fd: int, size: int) -> str:
    h = hashlib.sha256()
    left = size
    while left:
        block = os.read(fd, min(left, 1 << 20))
        need(bool(block), "SHORT_READ")
        left -= len(block)
        h.update(block)
    return h.hexdigest()


def scan(root_fd: int) -> dict[str, tuple[str, int, int]]:
    """rel path -> (sha256, size, mode). Directories are implied by files."""
    out: dict[str, tuple[str, int, int]] = {}
    count = 0

    def visit(fd: int, prefix: str) -> None:
        nonlocal count
        for name in sorted(os.listdir(fd)):
            count += 1
            need(count <= MAX_ENTRIES, "TOO_MANY_ENTRIES")
            rel = f"{prefix}{name}"
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
                try:
                    need(os.fstat(child).st_ino == st.st_ino, "DIR_SWAPPED")
                    visit(child, rel + "/")
                finally:
                    os.close(child)
            elif stat.S_ISREG(st.st_mode):
                if name == ".gitignore":
                    continue
                need(st.st_nlink == 1 and st.st_size <= MAX_FILE, "UNSAFE_FILE")
                f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
                try:
                    a = os.fstat(f)
                    need((a.st_ino, a.st_size) == (st.st_ino, st.st_size), "FILE_SWAPPED")
                    digest = _hash_fd(f, a.st_size)
                    b = os.fstat(f)
                    need((a.st_mtime_ns, a.st_size) == (b.st_mtime_ns, b.st_size), "FILE_CHANGED")
                finally:
                    os.close(f)
                out[rel] = (digest, st.st_size, stat.S_IMODE(st.st_mode))
            else:
                raise Blocked("SYMLINK_OR_SPECIAL_ENTRY")

    visit(root_fd, "")
    return out


def diff(src: dict, dst: dict) -> tuple[list[str], list[str], list[str]]:
    """(missing_in_dst to copy, blocking persistent conflicts, benign conflicts)."""
    copy, block, benign = [], [], []
    for rel, meta in src.items():
        if rel not in dst:
            if klass(rel) != "regenerable":
                copy.append(rel)
        elif dst[rel][0] != meta[0]:
            (block if klass(rel) == "persistent" else benign).append(rel)
    return copy, block, benign


def copy_create_only(src_root: int, dst_root: int, rel: str, expect: tuple[str, int, int]) -> None:
    *dirs, name = rel.split("/")
    sfd, dfd = os.dup(src_root), os.dup(dst_root)
    try:
        for d in dirs:
            try:
                os.mkdir(d, 0o700, dir_fd=dfd)
            except FileExistsError:
                pass
            s2 = os.open(d, DIR_FLAGS, dir_fd=sfd)
            d2 = os.open(d, DIR_FLAGS, dir_fd=dfd)
            os.close(sfd)
            os.close(dfd)
            sfd, dfd = s2, d2
        tmp = f".kmj-tmp-{secrets.token_hex(8)}"
        src = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
        out = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        try:
            h = hashlib.sha256()
            while block := os.read(src, 1 << 20):
                h.update(block)
                os.write(out, block)
            need(h.hexdigest() == expect[0], "SOURCE_CHANGED_DURING_COPY")
            os.fchmod(out, expect[2])
            if os.geteuid() == 0:
                st = os.fstat(src)
                os.fchown(out, st.st_uid, st.st_gid)
            os.fsync(out)
        finally:
            os.close(src)
            os.close(out)
        try:
            os.link(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
        except FileExistsError:
            pass  # someone created it first: never clobber; conflict check below
        finally:
            os.unlink(tmp, dir_fd=dfd)
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
        try:
            need(_hash_fd(f, os.fstat(f).st_size) == expect[0], "DESTINATION_CONFLICT_AFTER_COPY")
        finally:
            os.close(f)
    finally:
        os.close(sfd)
        os.close(dfd)


def reconcile(src_fd: int, dst_fd: int, apply: bool) -> dict:
    src, dst = scan(src_fd), scan(dst_fd)
    copy, block, benign = diff(src, dst)
    if block:
        return {"status": "BLOCKED_PERSISTENT_CONFLICT", "conflicts": sorted(block), "copied": 0}
    if apply:
        for rel in copy:
            copy_create_only(src_fd, dst_fd, rel, src[rel])
        again = diff(src, scan(dst_fd))
        need(not again[0] and not again[1], "RECONCILE_VERIFY_FAILED")
    return {"status": "OK", "to_copy": len(copy), "copied": len(copy) if apply else 0,
            "benign_log_divergence": len(benign)}


def renameat2(dfd: int, old: str, new: str, flags: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(dfd, os.fsencode(old), dfd, os.fsencode(new), flags):
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def plan_id(a: dict, b: dict) -> str:
    return hashlib.sha256(json.dumps([sorted(a.items()), sorted(b.items())]).encode()).hexdigest()[:16]


def context(args: argparse.Namespace):
    allowed = Path(args.allowed_root).resolve()
    app, shared = Path(args.app_dir).absolute(), Path(args.shared).absolute()
    for p in (app, shared):
        need(allowed in p.parents, "PATH_OUTSIDE_ALLOWED_ROOT")
    app_fd, shared_fd = open_dir(app), open_dir(shared)
    need(os.fstat(app_fd).st_dev == os.fstat(shared_fd).st_dev, "CROSS_FILESYSTEM")
    need(os.fstat(shared_fd).st_mode & 0o022 == 0, "SHARED_NOT_PRIVATE")
    for n in os.listdir(app_fd):
        need(not n.startswith(".kmj-storage-link-"), "LEFTOVER_LINK_REVIEW")
    return app, shared, app_fd, shared_fd


def cmd_plan(args) -> dict:
    app, shared, app_fd, shared_fd = context(args)
    st = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
    need(stat.S_ISDIR(st.st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=app_fd)
    live, shared_tree = scan(live_fd), scan(shared_fd)
    copy, block, benign = diff(live, shared_tree)
    return {"command": "plan", "live_files": len(live), "shared_files": len(shared_tree),
            "to_copy": len(copy), "persistent_conflicts": sorted(block),
            "benign_log_divergence": len(benign), "plan_id": plan_id(live, shared_tree),
            "ready": not block, "mutated": False}


def cmd_switch(args) -> dict:
    need(args.apply and args.plan_id, "APPLY_AND_PLAN_ID_REQUIRED")
    app, shared, app_fd, shared_fd = context(args)
    st = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
    need(stat.S_ISDIR(st.st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=app_fd)
    need(plan_id(scan(live_fd), scan(shared_fd)) == args.plan_id, "PLAN_ID_STALE_REVIEW_AGAIN")
    pre = reconcile(live_fd, shared_fd, apply=True)
    need(pre["status"] == "OK", pre["status"])
    link = f".kmj-storage-link-{secrets.token_hex(8)}"
    os.symlink(str(shared), link, dir_fd=app_fd)
    renameat2(app_fd, "storage", link, RENAME_EXCHANGE)  # atomic: storage -> shared
    kept = PRE + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    renameat2(app_fd, link, kept, RENAME_NOREPLACE)       # old dir preserved
    old_fd = os.open(kept, DIR_FLAGS, dir_fd=app_fd)
    final = reconcile(old_fd, shared_fd, apply=True)       # merge stragglers
    out = {"command": "switch", "preserved_dir": kept, "pre_sync": pre, "final_sync": final,
           "storage_is_symlink": os.path.islink(app / "storage"),
           "resolves_to_shared": os.path.realpath(app / "storage") == os.path.realpath(shared),
           "deleted_anything": False}
    if final["status"] != "OK":
        out["status"] = "BLOCKED_REVIEW_THEN_ROLLBACK"
        return out
    out["status"] = "OK"
    return out


def cmd_reconcile(args) -> dict:
    need(args.src_dir, "SRC_DIR_REQUIRED")
    app, shared, app_fd, shared_fd = context(args)
    src_fd = open_dir(Path(args.app_dir) / args.src_dir)
    need(args.src_dir.startswith(PRE), "SRC_MUST_BE_PRESERVED_DIR")
    return {"command": "reconcile", **reconcile(src_fd, shared_fd, apply=args.apply)}


def cmd_rollback(args) -> dict:
    need(args.apply, "APPLY_REQUIRED")
    app, shared, app_fd, shared_fd = context(args)
    st = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
    need(stat.S_ISLNK(st.st_mode) and os.path.realpath(app / "storage") == os.path.realpath(shared),
         "STORAGE_NOT_LINKED_TO_SHARED")
    kept = [n for n in os.listdir(app_fd) if n.startswith(PRE)]
    need(len(kept) == 1, "EXACTLY_ONE_PRESERVED_DIR_REQUIRED")
    old_fd = open_dir(app / kept[0])
    back = reconcile(shared_fd, old_fd, apply=True)  # shared -> old, additive only
    need(back["status"] == "OK", back["status"])
    renameat2(app_fd, "storage", kept[0], RENAME_EXCHANGE)  # storage is the real dir again
    parked = f"storage.shared-link-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    renameat2(app_fd, kept[0], parked, RENAME_NOREPLACE)
    return {"command": "rollback", "status": "OK", "reverse_sync": back, "link_parked_as": parked,
            "storage_is_directory": os.path.isdir(app / "storage") and not os.path.islink(app / "storage"),
            "deleted_anything": False}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "switch", "reconcile", "rollback"])
    ap.add_argument("--app-dir", required=True, help="release apps/platform directory")
    ap.add_argument("--shared", required=True, help="shared storage directory")
    ap.add_argument("--allowed-root", default="/home/kmjprod")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--plan-id")
    ap.add_argument("--src-dir")
    args = ap.parse_args(argv)
    try:
        result = {"plan": cmd_plan, "switch": cmd_switch, "reconcile": cmd_reconcile,
                  "rollback": cmd_rollback}[args.command](args)
    except (Blocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else f"OS_ERROR_{type(exc).__name__}"
        print(json.dumps({"status": "BLOCKED_" + reason, "deleted_anything": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status", "OK") == "OK" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
