#!/usr/bin/env python3
"""Enforced-exclusion, additive, journaled Main Platform storage -> shared switch.

Why this replaces the earlier versions (PR812 reviews): a userland tool cannot
*observe* its way to writer exclusion (/proc snapshots miss completed transient
writes and later writes through old handles). This tool *enforces* it: before
reading anything it sets the filesystem IMMUTABLE flag (chattr +i, root +
CAP_LINUX_IMMUTABLE) on every inode of the live storage tree (everything below
the top directory) and, after the sync, on the shared tree. An immutable inode
rejects write(2) even on file descriptors opened earlier, and rejects rename,
unlink and entry creation, for every user including root. Writers therefore
fail with EPERM for the (sub-second) transaction instead of silently writing to
a tree we have already read. Nothing is deleted or overwritten.

Transaction (switch): journal -> freeze live -> verify plan-id on the frozen
tree -> create-only sync live->shared -> verify live is a subset of shared ->
freeze shared -> pin identities -> renameat2(RENAME_EXCHANGE) -> verify the new
``storage`` path serves exactly the verified tree -> preserve the old directory
(``storage.pre-shared-<stamp>``, left frozen as evidence) -> thaw shared.
Any failure after the exchange swaps back while BOTH trees are still frozen, so
no write was accepted anywhere and the revert hides nothing. Crash recovery is
driven by an fsynced journal (``recover``; ``recover --apply`` is idempotent).

Rollback is conservative: it refuses when a persistent file in shared was
updated or is missing relative to the preserved directory (paths listed).
Symlinks, special/hard-linked files, xattrs and POSIX ACLs are refused.
"""
from __future__ import annotations

import argparse
import array
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
LINK = ".kmj-storage-link-"
PARKED = "storage.shared-link-"
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FS_IOC_GETFLAGS, FS_IOC_SETFLAGS = 0x80086601, 0x40086602
FS_IMMUTABLE_FL, FS_APPEND_FL = 0x10, 0x20
FAULT: str | None = None  # test hook: raise Crash at a named phase


class Blocked(Exception):
    pass


class Crash(BaseException):
    pass


def need(cond: bool, reason: str) -> None:
    if not cond:
        raise Blocked(reason)


def fault(name: str) -> None:
    if FAULT == name:
        raise Crash(name)


def klass(rel: str) -> str:
    if rel.startswith(REGENERABLE):
        return "regenerable"
    if rel.startswith(LOG):
        return "log"
    return "persistent"


# --------------------------------------------------------------------- freezer
class Freezer:
    """chattr +i via ioctl. Replaceable in tests; the real one needs root."""

    def flags(self, fd: int) -> int:
        buf = array.array("L", [0])
        fcntl.ioctl(fd, FS_IOC_GETFLAGS, buf, True)
        return buf[0]

    def set_immutable(self, fd: int, on: bool) -> None:
        cur = self.flags(fd)
        new = (cur | FS_IMMUTABLE_FL) if on else (cur & ~FS_IMMUTABLE_FL)
        if new != cur:
            fcntl.ioctl(fd, FS_IOC_SETFLAGS, array.array("L", [new]), True)

    def require_ready(self) -> None:
        need(os.geteuid() == 0, "ROOT_REQUIRED_FOR_ENFORCED_FREEZE")


FREEZER: Freezer = Freezer()


def _walk_inodes(root_fd: int, include_top: bool):
    """Yield (fd, is_dir) for every inode; caller must not keep fds. Dirs first."""
    count = 0
    stack = [root_fd]
    order: list[tuple[int, bool]] = []
    if include_top:
        order.append((os.dup(root_fd), True))
    while stack:
        fd = stack.pop()
        for name in os.listdir(fd):
            count += 1
            need(count <= MAX_ENTRIES, "TOO_MANY_ENTRIES")
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
                order.append((os.dup(child), True))
                stack.append(child)
            elif stat.S_ISREG(st.st_mode):
                order.append((os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd), False))
            else:
                raise Blocked("SYMLINK_OR_SPECIAL_ENTRY")
    return order


def set_tree(root_fd: int, on: bool, include_top: bool) -> int:
    """Freeze/thaw a tree until a full pass changes nothing (new entries get caught)."""
    total = 0
    for npass in range(6):
        changed = 0
        for fd, is_dir in sorted(_walk_inodes(root_fd, include_top), key=lambda x: not x[1]):
            try:
                before = FREEZER.flags(fd)
                need(not (before & FS_APPEND_FL), "ALREADY_APPEND_ONLY_REVIEW")
                if on and npass == 0:
                    need(not (before & FS_IMMUTABLE_FL), "ALREADY_IMMUTABLE_REVIEW")
                FREEZER.set_immutable(fd, on)
                if FREEZER.flags(fd) != before:
                    changed += 1
            except OSError as exc:
                raise Blocked(f"FREEZE_UNSUPPORTED_{exc.errno}") from exc
            finally:
                os.close(fd)
        total += changed
        if changed == 0:
            return total
    raise Blocked("TREE_NOT_STABLE_UNDER_FREEZE")


def freeze(root_fd: int, include_top: bool) -> int:
    return set_tree(root_fd, True, include_top)


def thaw(root_fd: int, include_top: bool) -> int:
    return set_tree(root_fd, False, include_top)


# ------------------------------------------------------------------ inventory
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


def _no_xattr(fd: int) -> None:
    try:
        names = os.listxattr(fd)
    except OSError as exc:
        need(exc.errno in (95, 61), "XATTR_INSPECTION_FAILED")  # ENOTSUP / ENODATA mean none
        return
    need(not names, "XATTR_OR_ACL_PRESENT_NOT_SUPPORTED")


def scan(root_fd: int, dirs: dict | None = None) -> dict[str, tuple]:
    """rel -> (sha256, size, mode, uid, gid); directory metadata into ``dirs``."""
    out: dict[str, tuple] = {}
    count = 0
    dirs = dirs if dirs is not None else {}
    _no_xattr(root_fd)

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
                    _no_xattr(child)
                    dirs[rel] = (stat.S_IMODE(cs.st_mode), cs.st_uid, cs.st_gid)
                    visit(child, rel + "/")
                finally:
                    os.close(child)
            elif stat.S_ISREG(st.st_mode):
                if name == ".gitignore" or name.startswith(".kmj-tmp-"):
                    continue
                need(st.st_nlink == 1 and st.st_size <= MAX_FILE, "UNSAFE_FILE")
                f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
                try:
                    a = os.fstat(f)
                    need((a.st_ino, a.st_size) == (st.st_ino, st.st_size), "FILE_SWAPPED")
                    _no_xattr(f)
                    digest = _hash_fd(f, a.st_size)
                    b = os.fstat(f)
                    need((a.st_mtime_ns, a.st_size) == (b.st_mtime_ns, b.st_size), "FILE_CHANGED")
                finally:
                    os.close(f)
                out[rel] = (digest, st.st_size, stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
            else:
                raise Blocked("SYMLINK_OR_SPECIAL_ENTRY")

    visit(root_fd, "")
    return out


def persistent_view(files: dict, dirs: dict) -> list:
    return [sorted((r, m) for r, m in files.items() if klass(r) == "persistent"),
            sorted((r, m) for r, m in dirs.items() if klass(r + "/") == "persistent")]


def plan_id(files: dict, dirs: dict) -> str:
    return hashlib.sha256(json.dumps(persistent_view(files, dirs)).encode()).hexdigest()[:16]


def diff(src: dict, dst: dict) -> tuple[list[str], list[str], list[str]]:
    copy, block, benign = [], [], []
    for rel, meta in src.items():
        if rel not in dst:
            if klass(rel) != "regenerable":
                copy.append(rel)
        elif dst[rel] != meta:
            (block if klass(rel) == "persistent" else benign).append(rel)
    return copy, block, benign


# ------------------------------------------------------------------- mutation
def renameat2(dfd: int, old: str, new: str, flags: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(dfd, os.fsencode(old), dfd, os.fsencode(new), flags):
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        need(n > 0, "WRITE_FAILED")
        view = view[n:]


def ensure_dirs(dst_root: int, dirs: list[str], meta: dict) -> None:
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


def copy_create_only(src_root: int, dst_root: int, rel: str, expect: tuple) -> None:
    *dirs, name = rel.split("/")
    sfd, dfd = os.dup(src_root), os.dup(dst_root)
    tmp = f".kmj-tmp-{secrets.token_hex(8)}"
    made = False
    try:
        for d in dirs:
            s2, d2 = os.open(d, DIR_FLAGS, dir_fd=sfd), os.open(d, DIR_FLAGS, dir_fd=dfd)
            os.close(sfd)
            os.close(dfd)
            sfd, dfd = s2, d2
        src = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
        out = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        made = True
        try:
            h, total = hashlib.sha256(), 0
            while block := os.read(src, 1 << 20):
                h.update(block)
                _write_all(out, block)
                total += len(block)
            need(h.hexdigest() == expect[0] and total == expect[1], "SOURCE_CHANGED_DURING_COPY")
            os.fchmod(out, expect[2])
            if os.geteuid() == 0:
                os.fchown(out, expect[3], expect[4])
            os.fsync(out)
            need(os.fstat(out).st_size == expect[1], "TEMP_SIZE_MISMATCH")
            os.lseek(out, 0, os.SEEK_SET)
            need(_hash_fd(out, expect[1]) == expect[0], "TEMP_CONTENT_MISMATCH")
        finally:
            os.close(src)
            os.close(out)
        try:
            renameat2(dfd, tmp, name, RENAME_NOREPLACE)  # atomic publish; existing name wins
            made = False
        except OSError as exc:
            need(exc.errno == 17, "PUBLISH_FAILED")  # EEXIST: verified below
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


def sync_additive(src_fd: int, dst_fd: int) -> dict:
    sdirs, ddirs = {}, {}
    src, dst = scan(src_fd, sdirs), scan(dst_fd, ddirs)
    copy, block, benign = diff(src, dst)
    if block:
        return {"status": "BLOCKED_PERSISTENT_CONFLICT", "conflicts": sorted(block)}
    wanted = sorted(d for d in sdirs if d not in ddirs and klass(d + "/") != "regenerable")
    ensure_dirs(dst_fd, wanted, sdirs)
    for rel in copy:
        copy_create_only(src_fd, dst_fd, rel, src[rel])
    ndirs = {}
    after = scan(dst_fd, ndirs)
    need(not diff(src, after)[0] and not diff(src, after)[1], "SYNC_VERIFY_FAILED")
    return {"status": "OK", "copied": len(copy), "dirs_created": len(wanted), "benign_log_divergence": len(benign)}


# -------------------------------------------------------------------- context
def identity(path: str | Path) -> tuple[int, int]:
    fd = open_dir(path)
    try:
        st = os.fstat(fd)
        return st.st_dev, st.st_ino
    finally:
        os.close(fd)


def fd_id(fd: int) -> tuple[int, int]:
    st = os.fstat(fd)
    return st.st_dev, st.st_ino


class Ctx:
    pass


def context(args: argparse.Namespace) -> Ctx:
    allowed = os.path.realpath(args.allowed_root)
    app, shared = Path(args.app_dir), Path(args.shared)
    for p in (app, shared):
        need(str(p) == os.path.abspath(p) == os.path.realpath(p), "PATH_NOT_CANONICAL")
        need(os.path.commonpath([allowed, str(p)]) == allowed and str(p) != allowed, "PATH_OUTSIDE_ALLOWED_ROOT")
    sp, ap = str(shared), str(app)
    need(not (sp == ap or sp.startswith(ap + "/") or ap.startswith(sp + "/")), "NESTED_OR_SAME_TARGET")
    c = Ctx()
    c.app, c.shared = app, shared
    c.app_fd, c.shared_fd = open_dir(app), open_dir(shared)
    need(fd_id(c.app_fd)[0] == fd_id(c.shared_fd)[0], "CROSS_FILESYSTEM")
    need(os.fstat(c.shared_fd).st_mode & 0o022 == 0, "SHARED_NOT_PRIVATE")
    try:
        live = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise Blocked("LIVE_STORAGE_MISSING")
    need((live.st_dev, live.st_ino) != fd_id(c.shared_fd), "SAME_INODE_TARGET")
    fcntl.flock(c.app_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    _LOCKS.append(c.app_fd)
    jdir = shared.parent
    need(os.stat(jdir).st_mode & 0o022 == 0, "JOURNAL_DIR_NOT_PRIVATE")
    c.journal = jdir / f".kmj-storage-switch-{hashlib.sha256(ap.encode()).hexdigest()[:12]}.journal"
    c.args = args
    return c


_LOCKS: list[int] = []


def journal_write(c: Ctx, phase: str, **extra) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(c.journal, flags, 0o600)
    try:
        _write_all(fd, (json.dumps({"t": int(time.time()), "phase": phase, **extra}) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = open_dir(c.journal.parent)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def journal_last(c: Ctx) -> dict | None:
    try:
        lines = c.journal.read_text().strip().splitlines()
    except FileNotFoundError:
        return None
    return json.loads(lines[-1]) if lines else None


def journal_close(c: Ctx) -> None:
    os.rename(c.journal, str(c.journal) + f".done-{int(time.time())}")


def pinned(c: Ctx, live_fd: int | None) -> None:
    need(identity(c.shared) == fd_id(c.shared_fd), "SHARED_PATH_REPLACED")
    need(identity(c.app) == fd_id(c.app_fd), "APP_PATH_REPLACED")
    if live_fd is not None:
        st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
        need(stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == fd_id(live_fd), "LIVE_STORAGE_REPLACED")


# ------------------------------------------------------------------- commands
def cmd_plan(args) -> dict:
    c = context(args)
    st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
    need(stat.S_ISDIR(st.st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
    ld, sd = {}, {}
    live, sh = scan(live_fd, ld), scan(c.shared_fd, sd)
    copy, block, benign = diff(live, sh)
    return {"command": "plan", "live_files": len(live), "shared_files": len(sh), "to_copy": len(copy),
            "persistent_conflicts": sorted(block), "benign_log_divergence": len(benign),
            "plan_id": plan_id(live, ld), "persistent_only_plan_id": True, "ready": not block,
            "enforced_freeze_possible_here": os.geteuid() == 0,
            "inventory_only_not_release_readiness": True, "mutated": False}


def cmd_switch(args) -> dict:
    need(args.apply and args.plan_id, "APPLY_AND_PLAN_ID_REQUIRED")
    FREEZER.require_ready()
    c = context(args)
    need(journal_last(c) is None, "JOURNAL_PRESENT_RUN_RECOVER")
    need(stat.S_ISDIR(os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False).st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
    journal_write(c, "begin")
    live_frozen = shared_frozen = exchanged = False
    link = LINK + secrets.token_hex(8)
    try:
        fault("begin")
        freeze(live_fd, include_top=False)
        live_frozen = True
        journal_write(c, "live_frozen")
        ld = {}
        live = scan(live_fd, ld)
        need(plan_id(live, ld) == args.plan_id, "PLAN_ID_STALE_REVIEW_AGAIN")
        synced = sync_additive(live_fd, c.shared_fd)
        need(synced["status"] == "OK", synced["status"])
        sd = {}
        sh = scan(c.shared_fd, sd)
        for rel, meta in live.items():
            need(klass(rel) != "persistent" or sh.get(rel) == meta, "SHARED_MISSING_PERSISTENT_AFTER_SYNC")
        freeze(c.shared_fd, include_top=True)
        shared_frozen = True
        journal_write(c, "both_frozen")
        fault("both_frozen")
        sd2 = {}
        need(plan_id(scan(c.shared_fd, sd2), sd2) == plan_id(sh, sd), "SHARED_CHANGED_UNDER_FREEZE")
        pinned(c, live_fd)
        os.symlink(str(c.shared), link, dir_fd=c.app_fd)
        os.fsync(c.app_fd)
        journal_write(c, "link_created", link=link)
        renameat2(c.app_fd, "storage", link, RENAME_EXCHANGE)
        os.fsync(c.app_fd)
        exchanged = True
        journal_write(c, "exchanged", link=link)
        fault("exchanged")
        now = os.open("storage", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=c.app_fd)  # follows our symlink
        need(fd_id(now) == fd_id(c.shared_fd), "NEW_STORAGE_NOT_SHARED_IDENTITY")
        d3 = {}
        need(plan_id(scan(now, d3), d3) == plan_id(sh, sd), "NEW_STORAGE_TREE_MISMATCH")
        old = os.open(link, DIR_FLAGS, dir_fd=c.app_fd)
        d4 = {}
        need(plan_id(scan(old, d4), d4) == plan_id(live, ld), "PRESERVED_TREE_CHANGED")
        kept = PRE + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        renameat2(c.app_fd, link, kept, RENAME_NOREPLACE)
        os.fsync(c.app_fd)
        journal_write(c, "preserved", kept=kept)
        fault("preserved")
        thaw(c.shared_fd, include_top=True)
        shared_frozen = False
        journal_write(c, "complete", kept=kept)
        journal_close(c)
        return {"command": "switch", "status": "OK", "preserved_dir": kept, "sync": synced,
                "preserved_dir_left_frozen": True, "deleted_anything": False}
    except (Blocked, OSError) as exc:
        if not isinstance(exc, Blocked):
            exc = Blocked(f"OS_ERROR_{type(exc).__name__}_{getattr(exc, 'errno', '')}")
        if exchanged and os.path.islink(c.app / "storage"):
            target = link if os.path.lexists(c.app / link) else None
            if target:
                renameat2(c.app_fd, "storage", link, RENAME_EXCHANGE)  # both trees still frozen: hides nothing
                os.fsync(c.app_fd)
        if shared_frozen:
            thaw(c.shared_fd, include_top=True)
        if live_frozen:
            thaw(live_fd, include_top=False)
        if os.path.islink(c.app / link):
            os.rename(c.app / link, c.app / (PARKED + "aborted-" + secrets.token_hex(4)))
        journal_close(c)
        return {"command": "switch", "status": "BLOCKED_" + str(exc), "reverted": exchanged,
                "deleted_anything": False}


def cmd_rollback(args) -> dict:
    need(args.apply, "APPLY_REQUIRED")
    FREEZER.require_ready()
    c = context(args)
    need(journal_last(c) is None, "JOURNAL_PRESENT_RUN_RECOVER")
    st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
    need(stat.S_ISLNK(st.st_mode) and os.path.realpath(c.app / "storage") == os.path.realpath(c.shared),
         "STORAGE_NOT_LINKED_TO_SHARED")
    kept = [n for n in os.listdir(c.app_fd) if n.startswith(PRE)]
    need(len(kept) == 1, "EXACTLY_ONE_PRESERVED_DIR_REQUIRED")
    old_fd = os.open(kept[0], DIR_FLAGS, dir_fd=c.app_fd)
    journal_write(c, "rollback_begin", kept=kept[0])
    shared_frozen = old_thawed = False
    try:
        freeze(c.shared_fd, include_top=True)
        shared_frozen = True
        thaw(old_fd, include_top=False)
        old_thawed = True
        od, nd = {}, {}
        old, new = scan(old_fd, od), scan(c.shared_fd, nd)
        updated = sorted(r for r in old if r in new and old[r] != new[r] and klass(r) == "persistent")
        deleted = sorted(r for r in old if r not in new and klass(r) == "persistent")
        if updated or deleted:
            raise Blocked("UPDATED_OR_DELETED_SINCE_SWITCH:" + json.dumps({"updated": updated, "deleted": deleted}))
        back = sync_additive(c.shared_fd, old_fd)
        need(back["status"] == "OK", back["status"])
        pinned(c, None)
        renameat2(c.app_fd, "storage", kept[0], RENAME_EXCHANGE)
        os.fsync(c.app_fd)
        parked = PARKED + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        renameat2(c.app_fd, kept[0], parked, RENAME_NOREPLACE)
        os.fsync(c.app_fd)
        thaw(c.shared_fd, include_top=True)
        journal_close(c)
        return {"command": "rollback", "status": "OK", "reverse_sync": back, "link_parked_as": parked,
                "deleted_anything": False}
    except Blocked as exc:
        if old_thawed:
            freeze(old_fd, include_top=False)
        if shared_frozen:
            thaw(c.shared_fd, include_top=True)
        journal_close(c)
        return {"command": "rollback", "status": "BLOCKED_" + str(exc), "deleted_anything": False}


def cmd_recover(args) -> dict:
    c = context(args)
    last = journal_last(c)
    names = sorted(n for n in os.listdir(c.app_fd) if n.startswith((LINK, PRE, PARKED)))
    state = "symlink" if os.path.islink(c.app / "storage") else "directory"
    out = {"command": "recover", "status": "OK", "journal_phase": last and last["phase"], "storage_is": state,
           "leftover_names": names, "mutated": False}
    if not args.apply or last is None:
        return out
    FREEZER.require_ready()
    phase = last["phase"]
    link = next((n for n in names if n.startswith(LINK)), None)
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd) if state == "directory" else None
    if phase in ("exchanged", "link_created") and state == "symlink" and link:
        renameat2(c.app_fd, "storage", link, RENAME_EXCHANGE)  # trees are still frozen: safe to swap back
        os.fsync(c.app_fd)
        live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
        state = "directory"
    if phase in ("begin", "live_frozen", "both_frozen", "link_created", "exchanged") and state == "directory":
        thaw(c.shared_fd, include_top=True)
        thaw(live_fd, include_top=False)
        if link and os.path.islink(c.app / link):
            os.rename(c.app / link, c.app / (PARKED + "recovered-" + secrets.token_hex(4)))
    elif phase == "preserved":
        thaw(c.shared_fd, include_top=True)
    else:
        return {**out, "status": "BLOCKED_MANUAL_REVIEW_PHASE_" + phase}
    journal_close(c)
    return {**out, "mutated": True, "recovered_from": phase}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "switch", "rollback", "recover"])
    ap.add_argument("--app-dir", required=True, help="release apps/platform directory")
    ap.add_argument("--shared", required=True, help="shared storage directory")
    ap.add_argument("--allowed-root", default="/home/kmjprod")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--plan-id")
    args = ap.parse_args(argv)
    try:
        result = {"plan": cmd_plan, "switch": cmd_switch, "rollback": cmd_rollback,
                  "recover": cmd_recover}[args.command](args)
    except (Blocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else f"OS_ERROR_{type(exc).__name__}_{getattr(exc, 'errno', '')}"
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
