#!/usr/bin/env python3
"""Lossless, additive, reversible Main Platform storage -> shared switch.

Nothing is ever deleted or overwritten; copies are create-only (link(2) of a
fully written, re-verified temp file). The live ``storage`` directory is swapped
for a symlink to shared with one renameat2(RENAME_EXCHANGE); the original is
kept as ``storage.pre-shared-<stamp>``.

WRITER SAFETY (review of PR812 finding 1): a reconcile can never capture writes
made through file handles opened before the swap. Therefore mutating commands
REQUIRE proof that no process has the tree open (cwd, root, fd, mmap) via a
/proc scan, and any unreadable process makes the proof fail, so it must run as
root. The operator must first quiesce writers (queue, scheduler, the FPM pool
that serves the release, backup jobs). The scan is repeated after the exchange;
if a holder appears the exchange is immediately reverted (writes then land back
in the live directory) and the run is BLOCKED. A writer that opens the tree in
the microseconds between scan and exchange is detected by the second scan, not
prevented; this is detection plus revert, not a lock.

Rollback is deliberately conservative: it refuses when shared differs from the
preserved directory in any persistent file (updates) or lacks one it had
(deletions), and lists the paths. No deletion/tombstone semantics are invented.

Mutating commands need ``--apply``; ``switch`` also needs the ``--plan-id`` for
the exact trees. Descriptor-relative, O_NOFOLLOW; symlinks, special files,
hard-linked files and POSIX ACL/xattr-bearing entries are refused.
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
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


_LOCKS: list[int] = []


def _no_acl(fd_or_path, follow=False) -> None:
    try:
        names = os.listxattr(fd_or_path, follow_symlinks=follow) if not isinstance(fd_or_path, int) else os.listxattr(fd_or_path)
    except OSError:
        return
    need(not any(n.startswith("system.posix_acl") for n in names), "ACL_PRESENT_NOT_SUPPORTED")


def scan(root_fd: int, dirs: dict | None = None) -> dict[str, tuple[str, int, int]]:
    """rel path -> (sha256, size, mode). Directory metadata goes to ``dirs``."""
    out: dict[str, tuple[str, int, int]] = {}
    count = 0
    dirs = dirs if dirs is not None else {}
    _no_acl(root_fd)

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
                    cs = os.fstat(child)
                    need(cs.st_ino == st.st_ino, "DIR_SWAPPED")
                    _no_acl(child)
                    dirs[rel] = (stat.S_IMODE(cs.st_mode), cs.st_uid, cs.st_gid)
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
                    _no_acl(f)
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


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        need(n > 0, "WRITE_FAILED")
        view = view[n:]


def ensure_dirs(src_root: int, dst_root: int, dirs: list[str], meta: dict) -> None:
    """Create missing directories (parents first) with the source mode/owner."""
    for rel in sorted(dirs, key=lambda d: d.count("/")):
        *parents, name = rel.split("/")
        dfd = os.dup(dst_root)
        try:
            for part in parents:
                nxt = os.open(part, DIR_FLAGS, dir_fd=dfd)
                os.close(dfd)
                dfd = nxt
            try:
                os.mkdir(name, 0o700, dir_fd=dfd)
            except FileExistsError:
                continue
            child = os.open(name, DIR_FLAGS, dir_fd=dfd)
            try:
                mode, uid, gid = meta[rel]
                os.fchmod(child, mode)
                if os.geteuid() == 0:
                    os.fchown(child, uid, gid)
                os.fsync(child)
            finally:
                os.close(child)
            os.fsync(dfd)
        finally:
            os.close(dfd)


def copy_create_only(src_root: int, dst_root: int, rel: str, expect: tuple[str, int, int]) -> None:
    *dirs, name = rel.split("/")
    sfd, dfd = os.dup(src_root), os.dup(dst_root)
    tmp = f".kmj-tmp-{secrets.token_hex(8)}"
    made = False
    try:
        for d in dirs:
            s2 = os.open(d, DIR_FLAGS, dir_fd=sfd)
            d2 = os.open(d, DIR_FLAGS, dir_fd=dfd)
            os.close(sfd)
            os.close(dfd)
            sfd, dfd = s2, d2
        src = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
        out = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        made = True
        try:
            h = hashlib.sha256()
            total = 0
            while block := os.read(src, 1 << 20):
                h.update(block)
                _write_all(out, block)
                total += len(block)
            need(h.hexdigest() == expect[0] and total == expect[1], "SOURCE_CHANGED_DURING_COPY")
            os.fchmod(out, expect[2])
            if os.geteuid() == 0:
                st = os.fstat(src)
                os.fchown(out, st.st_uid, st.st_gid)
            os.fsync(out)
            need(os.fstat(out).st_size == expect[1], "TEMP_SIZE_MISMATCH")
            os.lseek(out, 0, os.SEEK_SET)
            need(_hash_fd(out, expect[1]) == expect[0], "TEMP_CONTENT_MISMATCH")
        finally:
            os.close(src)
            os.close(out)
        try:
            os.link(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
        except FileExistsError:
            pass  # existing name wins; verified below
        os.fsync(dfd)
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
        try:
            need(_hash_fd(f, os.fstat(f).st_size) == expect[0], "DESTINATION_CONFLICT_AFTER_COPY")
        finally:
            os.close(f)
    finally:
        if made:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except FileNotFoundError:
                pass
        os.close(sfd)
        os.close(dfd)


def reconcile(src_fd: int, dst_fd: int, apply: bool) -> dict:
    sdirs, ddirs = {}, {}
    src, dst = scan(src_fd, sdirs), scan(dst_fd, ddirs)
    copy, block, benign = diff(src, dst)
    if block:
        return {"status": "BLOCKED_PERSISTENT_CONFLICT", "conflicts": sorted(block), "copied": 0}
    wanted = sorted(d for d in sdirs if d not in ddirs and klass(d + "/") != "regenerable")
    if apply:
        ensure_dirs(src_fd, dst_fd, wanted, sdirs)
        for rel in copy:
            copy_create_only(src_fd, dst_fd, rel, src[rel])
        again = diff(src, scan(dst_fd))
        need(not again[0] and not again[1], "RECONCILE_VERIFY_FAILED")
    return {"status": "OK", "to_copy": len(copy), "copied": len(copy) if apply else 0,
            "dirs_created": len(wanted) if apply else 0, "benign_log_divergence": len(benign)}


def open_handles(tree: str | Path, proc_root: str = "/proc") -> dict:
    """Processes holding cwd/root/fd/mmap inside ``tree``. Unreadable = unproven."""
    real = os.path.realpath(tree)
    prefix = real.rstrip("/") + "/"
    holders, unreadable = [], 0
    me = str(os.getpid())
    for pid in os.listdir(proc_root):
        if not pid.isdigit() or pid == me:
            continue
        base = Path(proc_root) / pid
        paths: list[str] = []
        try:
            for link in ("cwd", "root"):
                paths.append(os.readlink(base / link))
            for fd in os.listdir(base / "fd"):
                try:
                    paths.append(os.readlink(base / "fd" / fd))
                except FileNotFoundError:
                    continue
            with open(base / "maps", "rb") as fh:
                for line in fh:
                    parts = line.decode("utf-8", "replace").rstrip("\n").split(None, 5)
                    if len(parts) == 6 and parts[5].startswith("/"):
                        paths.append(parts[5])
        except FileNotFoundError:
            continue  # process exited
        except (PermissionError, OSError):
            unreadable += 1
            continue
        if any(x == real or x.startswith(prefix) for x in paths):
            holders.append(int(pid))
    return {"holders": holders, "unreadable_processes": unreadable,
            "proven_quiet": not holders and unreadable == 0}


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
    allowed = os.path.realpath(args.allowed_root)
    app, shared = Path(args.app_dir), Path(args.shared)
    for p in (app, shared):
        need(str(p) == os.path.abspath(p) == os.path.realpath(p), "PATH_NOT_CANONICAL")
        need(os.path.commonpath([allowed, str(p)]) == allowed and str(p) != allowed, "PATH_OUTSIDE_ALLOWED_ROOT")
    sp, ap = str(shared), str(app)
    need(not (sp == ap or sp.startswith(ap + "/") or ap.startswith(sp + "/")), "NESTED_OR_SAME_TARGET")
    app_fd, shared_fd = open_dir(app), open_dir(shared)
    need(os.fstat(app_fd).st_dev == os.fstat(shared_fd).st_dev, "CROSS_FILESYSTEM")
    need(os.fstat(shared_fd).st_mode & 0o022 == 0, "SHARED_NOT_PRIVATE")
    try:
        live = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
        need((live.st_dev, live.st_ino) != (os.fstat(shared_fd).st_dev, os.fstat(shared_fd).st_ino), "SAME_INODE_TARGET")
    except FileNotFoundError:
        raise Blocked("LIVE_STORAGE_MISSING")
    for n in os.listdir(app_fd):
        need(not n.startswith(".kmj-storage-link-") or args.command == "recover", "LEFTOVER_LINK_REVIEW_RUN_RECOVER")
    fcntl.flock(app_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    _LOCKS.append(app_fd)
    return app, shared, app_fd, shared_fd


def same_entry(dirfd: int, name: str, fd: int) -> bool:
    a = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
    b = os.fstat(fd)
    return stat.S_ISDIR(a.st_mode) and (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def fsync_dir(fd: int) -> None:
    os.fsync(fd)


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
            "writers": open_handles(app / "storage", args.proc_root),
            "ready": not block, "inventory_only_not_release_readiness": True, "mutated": False}


def cmd_switch(args) -> dict:
    need(args.apply and args.plan_id, "APPLY_AND_PLAN_ID_REQUIRED")
    app, shared, app_fd, shared_fd = context(args)
    need(stat.S_ISDIR(os.stat("storage", dir_fd=app_fd, follow_symlinks=False).st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=app_fd)
    need(plan_id(scan(live_fd), scan(shared_fd)) == args.plan_id, "PLAN_ID_STALE_REVIEW_AGAIN")
    quiet = open_handles(app / "storage", args.proc_root)
    need(quiet["proven_quiet"], "WRITERS_NOT_PROVEN_QUIET")
    pre = reconcile(live_fd, shared_fd, apply=True)
    need(pre["status"] == "OK", pre["status"])
    need(same_entry(app_fd, "storage", live_fd), "LIVE_STORAGE_REPLACED_BEFORE_EXCHANGE")
    link = f".kmj-storage-link-{secrets.token_hex(8)}"
    os.symlink(str(shared), link, dir_fd=app_fd)
    fsync_dir(app_fd)
    renameat2(app_fd, "storage", link, RENAME_EXCHANGE)  # atomic: storage -> shared
    fsync_dir(app_fd)
    late = open_handles(app / link, args.proc_root)       # old dir is now at ``link``
    if not late["proven_quiet"]:
        renameat2(app_fd, "storage", link, RENAME_EXCHANGE)  # revert: old dir live again
        fsync_dir(app_fd)
        return {"command": "switch", "status": "BLOCKED_WRITER_APPEARED_REVERTED", "late_holders": late["holders"],
                "deleted_anything": False}
    kept = PRE + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    try:
        renameat2(app_fd, link, kept, RENAME_NOREPLACE)
        fsync_dir(app_fd)
    except OSError:
        renameat2(app_fd, "storage", link, RENAME_EXCHANGE)  # restore original live dir
        fsync_dir(app_fd)
        return {"command": "switch", "status": "BLOCKED_PRESERVE_FAILED_REVERTED", "deleted_anything": False}
    old_fd = os.open(kept, DIR_FLAGS, dir_fd=app_fd)
    final = reconcile(old_fd, shared_fd, apply=True)       # evidence only; handles were proven absent
    out = {"command": "switch", "preserved_dir": kept, "pre_sync": pre, "final_sync": final,
           "storage_is_symlink": os.path.islink(app / "storage"),
           "resolves_to_shared": os.path.realpath(app / "storage") == os.path.realpath(shared),
           "deleted_anything": False, "status": "OK" if final["status"] == "OK" else "BLOCKED_REVIEW_THEN_ROLLBACK"}
    return out


def cmd_reconcile(args) -> dict:
    need(args.src_dir and "/" not in args.src_dir and args.src_dir.startswith(PRE), "SRC_MUST_BE_PRESERVED_BASENAME")
    app, shared, app_fd, shared_fd = context(args)
    src_fd = os.open(args.src_dir, DIR_FLAGS, dir_fd=app_fd)
    return {"command": "reconcile", **reconcile(src_fd, shared_fd, apply=args.apply)}


def cmd_rollback(args) -> dict:
    need(args.apply, "APPLY_REQUIRED")
    app, shared, app_fd, shared_fd = context(args)
    st = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
    need(stat.S_ISLNK(st.st_mode) and os.path.realpath(app / "storage") == os.path.realpath(shared),
         "STORAGE_NOT_LINKED_TO_SHARED")
    kept = [n for n in os.listdir(app_fd) if n.startswith(PRE)]
    need(len(kept) == 1, "EXACTLY_ONE_PRESERVED_DIR_REQUIRED")
    old_fd = os.open(kept[0], DIR_FLAGS, dir_fd=app_fd)
    need(open_handles(shared, args.proc_root)["proven_quiet"], "WRITERS_NOT_PROVEN_QUIET")
    old, new = scan(old_fd), scan(shared_fd)
    updated = sorted(r for r in old if r in new and old[r][0] != new[r][0] and klass(r) == "persistent")
    deleted = sorted(r for r in old if r not in new and klass(r) == "persistent")
    if updated or deleted:
        return {"command": "rollback", "status": "BLOCKED_UPDATED_OR_DELETED_SINCE_SWITCH",
                "updated": updated, "deleted": deleted, "deleted_anything": False}
    back = reconcile(shared_fd, old_fd, apply=True)  # only brand-new files remain: additive
    need(back["status"] == "OK", back["status"])
    renameat2(app_fd, "storage", kept[0], RENAME_EXCHANGE)  # storage is the real dir again
    fsync_dir(app_fd)
    parked = f"storage.shared-link-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    renameat2(app_fd, kept[0], parked, RENAME_NOREPLACE)
    fsync_dir(app_fd)
    return {"command": "rollback", "status": "OK", "reverse_sync": back, "link_parked_as": parked,
            "storage_is_directory": os.path.isdir(app / "storage") and not os.path.islink(app / "storage"),
            "deleted_anything": False}


def cmd_recover(args) -> dict:
    """Read-only classification of a half-finished switch; never moves anything."""
    app, shared, app_fd, shared_fd = context(args)
    names = sorted(n for n in os.listdir(app_fd) if n.startswith((".kmj-storage-link-", PRE, "storage.shared-link-")))
    storage = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
    state = "storage_is_symlink" if stat.S_ISLNK(storage.st_mode) else "storage_is_directory"
    return {"command": "recover", "status": "OK", "state": state, "leftover_names": names, "mutated": False,
            "next": "review names; the only automatic moves are the revert paths inside switch/rollback"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "switch", "reconcile", "rollback", "recover"])
    ap.add_argument("--app-dir", required=True, help="release apps/platform directory")
    ap.add_argument("--shared", required=True, help="shared storage directory")
    ap.add_argument("--allowed-root", default="/home/kmjprod")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--plan-id")
    ap.add_argument("--src-dir")
    ap.add_argument("--proc-root", default="/proc", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        result = {"plan": cmd_plan, "switch": cmd_switch, "reconcile": cmd_reconcile,
                  "rollback": cmd_rollback, "recover": cmd_recover}[args.command](args)
    except (Blocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else f"OS_ERROR_{type(exc).__name__}"
        print(json.dumps({"status": "BLOCKED_" + reason, "deleted_anything": False}))
        return 2
    finally:
        while _LOCKS:
            try:
                os.close(_LOCKS.pop())
            except OSError:
                pass
    print(json.dumps(result, sort_keys=True))
    status = result.get("status", "OK")
    return 0 if status == "OK" else 2 if status.startswith("BLOCKED") else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
