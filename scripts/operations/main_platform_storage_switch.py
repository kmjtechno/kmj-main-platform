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
import re
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

    def require_ready(self, probe_dir: str | None = None) -> None:
        need(os.geteuid() == 0, "ROOT_REQUIRED_FOR_ENFORCED_FREEZE")
        need(probe_dir is not None, "PROBE_DIR_REQUIRED")
        # Root uid alone proves nothing: prove CAP_LINUX_IMMUTABLE + filesystem support
        # with a throwaway file on the SAME filesystem as the trees.
        path = os.path.join(probe_dir, f".kmj-probe-{secrets.token_hex(6)}")
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            self.set_immutable(fd, True)
            try:
                os.write(fd, b"x")
                raise Blocked("FREEZE_NOT_ENFORCED_BY_FILESYSTEM")
            except PermissionError:
                pass
        except OSError as exc:
            raise Blocked(f"FREEZE_UNSUPPORTED_{exc.errno}") from exc
        finally:
            try:
                self.set_immutable(fd, False)
            finally:
                os.close(fd)
                os.unlink(path)


FREEZER: Freezer = Freezer()


def _visit_tree(root_fd: int, include_top: bool, action) -> int:
    """Depth-first, one directory fd per level (bounded by tree depth, closed on every path)."""
    seen = 0
    changed = 0

    def inode(fd: int) -> None:
        nonlocal seen, changed
        seen += 1
        need(seen <= MAX_ENTRIES, "TOO_MANY_ENTRIES")
        changed += 1 if action(fd) else 0

    def descend(dfd: int) -> None:
        for name in os.listdir(dfd):
            st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                child = os.open(name, DIR_FLAGS, dir_fd=dfd)
                try:
                    inode(child)  # freeze the directory BEFORE descending: entry creation closes first
                    descend(child)
                finally:
                    os.close(child)
            elif stat.S_ISREG(st.st_mode):
                f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dfd)
                try:
                    inode(f)
                finally:
                    os.close(f)
            else:
                raise Blocked("SYMLINK_OR_SPECIAL_ENTRY")

    if include_top:
        inode(root_fd)
    descend(root_fd)
    return changed


def _precheck_tree(root_fd: int, include_top: bool) -> None:
    """Read-only: every inode supports the flag ioctl and carries NO immutable/append flag."""
    def check(fd: int) -> bool:
        try:
            flags = FREEZER.flags(fd)
        except OSError as exc:
            raise Blocked(f"FREEZE_UNSUPPORTED_{exc.errno}") from exc
        need(not (flags & (FS_IMMUTABLE_FL | FS_APPEND_FL)), "ALREADY_IMMUTABLE_OR_APPEND_REVIEW")
        return False

    _visit_tree(root_fd, include_top, check)


def set_tree(root_fd: int, on: bool, include_top: bool) -> int:
    def act(fd: int) -> bool:
        before = FREEZER.flags(fd)
        FREEZER.set_immutable(fd, on)
        return FREEZER.flags(fd) != before

    total = 0
    for _ in range(6):
        try:
            changed = _visit_tree(root_fd, include_top, act)
        except OSError as exc:
            raise Blocked(f"FREEZE_FAILED_{exc.errno}") from exc
        total += changed
        if changed == 0:
            return total
    raise Blocked("TREE_NOT_STABLE_UNDER_FREEZE")


def tree_clean(root_fd: int, include_top: bool) -> bool:
    """True when no inode in the tree carries the immutable flag."""
    flagged = []

    def look(fd: int) -> bool:
        if FREEZER.flags(fd) & FS_IMMUTABLE_FL:
            flagged.append(1)
        return False

    _visit_tree(root_fd, include_top, look)
    return not flagged


def freeze(root_fd: int, include_top: bool) -> int:
    _precheck_tree(root_fd, include_top)  # nothing is mutated until the whole tree is known flag-clean
    try:
        return set_tree(root_fd, True, include_top)
    except (Blocked, OSError):
        thaw(root_fd, include_top)  # all-clean precondition => clearing restores the exact original state
        raise


def thaw(root_fd: int, include_top: bool) -> int:
    return set_tree(root_fd, False, include_top)


def ensure_frozen(root_fd: int, include_top: bool) -> int:
    """Idempotent recovery freeze: no admission precheck (a half-thawed tree is a legal crash state)."""
    return set_tree(root_fd, True, include_top)


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


_LOCKS: list[int] = []
PHASES = {"begin", "live_frozen", "both_frozen", "link_created", "exchanged", "preserved", "complete",
          "rollback_begin", "rollback_shared_frozen", "rollback_old_thawed", "rollback_exchanged",
          "rollback_parked", "verified"}
NAME_RE = __import__("re").compile(r"\A(\.kmj-storage-link-[0-9a-f]{16}|storage\.pre-shared-\d{8}T\d{6}Z)\Z")


def context(args: argparse.Namespace) -> Ctx:
    allowed = os.path.realpath(args.allowed_root)
    app, shared = Path(args.app_dir), Path(args.shared)
    for p in (app, shared):
        need(str(p) == os.path.abspath(p) == os.path.realpath(p), "PATH_NOT_CANONICAL")
        need(os.path.commonpath([allowed, str(p)]) == allowed and str(p) != allowed, "PATH_OUTSIDE_ALLOWED_ROOT")
    sp, ap = str(shared), str(app)
    need(not (sp == ap or sp.startswith(ap + "/") or ap.startswith(sp + "/")), "NESTED_OR_SAME_TARGET")
    c = Ctx()
    c.app, c.shared, c.args = app, shared, args
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
    c.key = hashlib.sha256(ap.encode()).hexdigest()[:12]
    c.state_fd = None
    return c


def open_state(c: Ctx) -> None:
    """Protected transaction state: owned by the (root) caller, 0700, no group/other-writable ancestor."""
    path = Path(c.args.state_dir)
    need(str(path) == os.path.abspath(path) == os.path.realpath(path), "STATE_DIR_NOT_CANONICAL")
    need(not str(path).startswith((str(c.app) + "/", str(c.shared) + "/")) and str(path) not in (str(c.app), str(c.shared)),
         "STATE_DIR_INSIDE_TREES")
    if not path.exists():
        need(os.geteuid() == 0, "STATE_DIR_MISSING")
        os.mkdir(path, 0o700)
    fd = open_dir(path)
    st = os.fstat(fd)
    need(st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) & 0o077 == 0, "STATE_DIR_NOT_PROTECTED")
    cur = Path("/")
    for part in path.parent.parts[1:]:
        cur = cur / part
        ast = os.lstat(cur)
        need(not (ast.st_mode & 0o022) or (ast.st_mode & stat.S_ISVTX), "STATE_DIR_ANCESTOR_WRITABLE")
    c.state_fd = fd


def _journal_name(c: Ctx) -> str:
    return f"{c.key}.journal"


def _validate(entry) -> dict:
    need(isinstance(entry, dict) and entry.get("phase") in PHASES and isinstance(entry.get("t"), int), "JOURNAL_INVALID")
    for k in ("link", "kept"):
        if k in entry:
            need(isinstance(entry[k], str) and NAME_RE.match(entry[k]) is not None, "JOURNAL_INVALID")
    for k in ("plan", "shared_plan"):
        if k in entry:
            need(isinstance(entry[k], str) and re.fullmatch(r"[0-9a-f]{16}", entry[k]) is not None, "JOURNAL_INVALID")
    return entry


def journal_write(c: Ctx, phase: str, **extra) -> None:
    fd = os.open(_journal_name(c), os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                 dir_fd=c.state_fd)
    try:
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_uid == os.geteuid()
             and stat.S_IMODE(st.st_mode) & 0o077 == 0 and st.st_size < 65536, "JOURNAL_FILE_UNSAFE")
        if st.st_size:
            last = os.pread(fd, 1, st.st_size - 1)
            need(last == b"\n", "JOURNAL_TORN_TAIL_RUN_RECOVER")
        _write_all(fd, (json.dumps(_validate({"t": int(time.time()), "phase": phase, **extra})) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(c.state_fd)


def _journal_open_checked(c: Ctx, flags: int):
    fd = os.open(_journal_name(c), flags | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=c.state_fd)
    st = os.fstat(fd)
    if not (stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) & 0o077 == 0 and st.st_size <= 65536):
        os.close(fd)
        raise Blocked("JOURNAL_FILE_UNSAFE")
    return fd


def journal_read(c: Ctx) -> tuple[list[dict], int, bool]:
    """(complete validated entries, byte length of the complete prefix, file_exists).

    Every record is one newline-terminated write. Only an UNTERMINATED final fragment (a torn append from a
    crash) is tolerated and discarded; any malformed newline-terminated record is internal corruption."""
    try:
        fd = _journal_open_checked(c, os.O_RDONLY)
    except FileNotFoundError:
        return [], 0, False
    try:
        raw = os.read(fd, 65537)
    finally:
        os.close(fd)
    prefix = raw[: raw.rfind(b"\n") + 1]  # drop anything after the last newline (torn tail, possibly all of it)
    lines = prefix.split(b"\n")[:-1]
    need(len(lines) <= 200, "JOURNAL_INVALID")
    entries = []
    for line in lines:
        try:
            entries.append(_validate(json.loads(line.decode("utf-8", "strict"))))
        except (ValueError, RecursionError):  # JSONDecodeError and UnicodeDecodeError are ValueErrors
            raise Blocked("JOURNAL_INVALID")
    return entries, len(prefix), True


def journal_entries(c: Ctx) -> list[dict]:
    return journal_read(c)[0]


def journal_repair(c: Ctx, keep: int) -> bool:
    """Truncate a torn tail so later appends cannot fuse with it. Returns True when bytes were removed."""
    fd = _journal_open_checked(c, os.O_RDWR)
    try:
        if os.fstat(fd).st_size == keep:
            return False
        os.ftruncate(fd, keep)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(c.state_fd)
    return True


def journal_close(c: Ctx) -> None:
    os.rename(_journal_name(c), f"{_journal_name(c)}.done-{int(time.time())}", src_dir_fd=c.state_fd,
              dst_dir_fd=c.state_fd)
    os.fsync(c.state_fd)


def pinned(c: Ctx, live_fd: int | None) -> None:
    need(identity(c.shared) == fd_id(c.shared_fd), "SHARED_PATH_REPLACED")
    need(identity(c.app) == fd_id(c.app_fd), "APP_PATH_REPLACED")
    if live_fd is not None:
        st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
        need(stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == fd_id(live_fd), "LIVE_STORAGE_REPLACED")


def top_meta(fd: int) -> tuple:
    st = os.fstat(fd)
    return stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid


def top_dir_holders(tree: str | Path, proc_root: str = "/proc") -> list[int]:
    """Narrow supplement (not the enforcement): processes whose cwd/fd IS the unfrozen top directory."""
    real = os.path.realpath(tree)
    out, me = [], str(os.getpid())
    for pid in os.listdir(proc_root):
        if not pid.isdigit() or pid == me:
            continue
        base = Path(proc_root) / pid
        try:
            targets = [os.readlink(base / "cwd")]
            for fd in os.listdir(base / "fd"):
                try:
                    targets.append(os.readlink(base / "fd" / fd))
                except FileNotFoundError:
                    continue
        except FileNotFoundError:
            continue
        except OSError:
            raise Blocked("PROCESS_TABLE_UNREADABLE_CANNOT_CHECK_TOP_DIR_HANDLES")
        if real in targets:
            out.append(int(pid))
    return out


def restore_original(c: Ctx, link: str | None, kept: str | None, thaw_live: bool = True,
                     thaw_shared: bool = True) -> None:
    """Idempotent: make `storage` the original real directory again and thaw everything we froze.
    Only valid while both trees are still frozen (so the swap back hides no accepted write)."""
    if os.path.islink(c.app / "storage"):
        holder = kept if kept and os.path.isdir(c.app / kept) else link
        need(holder is not None and os.path.isdir(c.app / holder) and not os.path.islink(c.app / holder), "NO_ORIGINAL_DIR_FOUND")
        hfd = os.open(holder, DIR_FLAGS, dir_fd=c.app_fd)
        FREEZER.set_immutable(hfd, False)  # top may be frozen: a frozen dir cannot be renamed
        if holder != link:
            link = link or LINK + secrets.token_hex(8)
            renameat2(c.app_fd, holder, link, RENAME_NOREPLACE)
        else:
            link = holder
        os.fsync(c.app_fd)
        renameat2(c.app_fd, "storage", link, RENAME_EXCHANGE)
        os.fsync(c.app_fd)
        if os.path.islink(c.app / link):
            os.rename(c.app / link, c.app / (PARKED + "reverted-" + secrets.token_hex(4)))
            os.fsync(c.app_fd)
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
    # Only transaction-owned freezes are cleared: a tree that was never frozen by us keeps its original flags.
    if thaw_shared:
        thaw(c.shared_fd, include_top=True)
        need(tree_clean(c.shared_fd, True), "THAW_NOT_VERIFIED")
    if thaw_live:
        thaw(live_fd, include_top=False)
        need(tree_clean(live_fd, False), "THAW_NOT_VERIFIED")


# ------------------------------------------------------------------- commands
def cmd_plan(args) -> dict:
    c = context(args)
    st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
    need(stat.S_ISDIR(st.st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
    ld, sd = {}, {}
    live, sh = scan(live_fd, ld), scan(c.shared_fd, sd)
    copy, block, benign = diff(live, sh)
    meta_ok = top_meta(live_fd) == top_meta(c.shared_fd)
    return {"command": "plan", "live_files": len(live), "shared_files": len(sh), "to_copy": len(copy),
            "persistent_conflicts": sorted(block), "benign_log_divergence": len(benign),
            "plan_id": plan_id(live, ld), "persistent_only_plan_id": True,
            "top_dir_meta_live_mode_uid_gid": list(top_meta(live_fd)),
            "top_dir_meta_shared_mode_uid_gid": list(top_meta(c.shared_fd)),
            "ready": not block and meta_ok, "enforced_freeze_possible_here": os.geteuid() == 0,
            "inventory_only_not_release_readiness": True, "mutated": False}


def cmd_switch(args) -> dict:
    need(args.apply and args.plan_id, "APPLY_AND_PLAN_ID_REQUIRED")
    c = context(args)
    FREEZER.require_ready(str(c.app))
    open_state(c)
    need(not journal_entries(c), "JOURNAL_PRESENT_RUN_RECOVER")
    need(stat.S_ISDIR(os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False).st_mode), "LIVE_STORAGE_NOT_A_DIRECTORY")
    live_fd = os.open("storage", DIR_FLAGS, dir_fd=c.app_fd)
    need(top_meta(live_fd) == top_meta(c.shared_fd), "TOP_DIR_MODE_OWNER_MISMATCH_LIVE_VS_SHARED")
    need(not top_dir_holders(c.app / "storage", args.proc_root), "LIVE_TOP_DIR_HELD_OPEN")
    _precheck_tree(live_fd, include_top=False)  # both trees known flag-clean BEFORE the first mutation/journal:
    _precheck_tree(c.shared_fd, include_top=True)  # every later crash state is exactly "ours to thaw"
    link = LINK + secrets.token_hex(8)
    kept = PRE + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    journal_write(c, "begin", link=link, kept=kept, plan=args.plan_id)
    live_frozen = shared_frozen = committed = False
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
        journal_write(c, "both_frozen", shared_plan=plan_id(sh, sd))
        fault("both_frozen")
        sd2 = {}
        need(plan_id(scan(c.shared_fd, sd2), sd2) == plan_id(sh, sd), "SHARED_CHANGED_UNDER_FREEZE")
        ld1 = {}
        need(plan_id(scan(live_fd, ld1), ld1) == plan_id(live, ld), "LIVE_CHANGED_UNDER_FREEZE")  # late top-level entry
        need(not top_dir_holders(c.app / "storage", args.proc_root), "LIVE_TOP_DIR_HELD_OPEN")
        pinned(c, live_fd)
        os.sync()
        os.symlink(str(c.shared), link, dir_fd=c.app_fd)
        os.fsync(c.app_fd)
        journal_write(c, "link_created")
        renameat2(c.app_fd, "storage", link, RENAME_EXCHANGE)
        os.fsync(c.app_fd)
        journal_write(c, "exchanged")
        fault("exchanged")
        now = os.open("storage", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=c.app_fd)  # follows our symlink
        need(fd_id(now) == fd_id(c.shared_fd), "NEW_STORAGE_NOT_SHARED_IDENTITY")
        d3 = {}
        need(plan_id(scan(now, d3), d3) == plan_id(sh, sd), "NEW_STORAGE_TREE_MISMATCH")
        renameat2(c.app_fd, link, kept, RENAME_NOREPLACE)
        os.fsync(c.app_fd)
        journal_write(c, "preserved")
        fault("preserved")
        old = os.open(kept, DIR_FLAGS, dir_fd=c.app_fd)
        FREEZER.set_immutable(old, True)  # closes the retained-top-FD window; final compare below sees anything that slipped in
        d4 = {}
        need(plan_id(scan(old, d4), d4) == plan_id(live, ld), "PRESERVED_TREE_CHANGED")
        journal_write(c, "verified")  # durable proof the old tree matched; shared is still frozen until now
        fault("before_thaw")
        committed = True  # from here the new tree is the live one: never swap back over accepted writes
        thaw(c.shared_fd, include_top=True)
        shared_frozen = False
        journal_write(c, "complete")
        journal_close(c)
        return {"command": "switch", "status": "OK", "preserved_dir": kept, "sync": synced,
                "preserved_dir_left_frozen": True, "deleted_anything": False}
    except (Blocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else f"OS_ERROR_{type(exc).__name__}_{getattr(exc, 'errno', '')}"
        try:
            if committed:  # switch already took effect; finish the thaw, never revert
                thaw(c.shared_fd, include_top=True)
                need(tree_clean(c.shared_fd, True), "THAW_NOT_VERIFIED")
                journal_write(c, "complete")
                journal_close(c)
                return {"command": "switch", "status": "OK", "preserved_dir": kept, "deleted_anything": False,
                        "note": "thaw needed a retry: " + reason}
            restore_original(c, link, kept, thaw_live=live_frozen, thaw_shared=shared_frozen)
            journal_close(c)
            return {"command": "switch", "status": "BLOCKED_" + reason, "reverted": True, "deleted_anything": False}
        except (Blocked, OSError) as inner:
            return {"command": "switch", "status": "BLOCKED_RECOVERY_REQUIRED_JOURNAL_OPEN",
                    "switched": committed, "first_error": reason, "second_error": str(inner),
                    "deleted_anything": False}


def cmd_rollback(args) -> dict:
    need(args.apply, "APPLY_REQUIRED")
    c = context(args)
    FREEZER.require_ready(str(c.app))
    open_state(c)
    need(not journal_entries(c), "JOURNAL_PRESENT_RUN_RECOVER")
    st = os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False)
    need(stat.S_ISLNK(st.st_mode) and os.path.realpath(c.app / "storage") == os.path.realpath(c.shared),
         "STORAGE_NOT_LINKED_TO_SHARED")
    names = [n for n in os.listdir(c.app_fd) if n.startswith(PRE)]
    need(len(names) == 1 and NAME_RE.match(names[0]) is not None, "EXACTLY_ONE_PRESERVED_DIR_REQUIRED")
    kept = names[0]
    old_fd = os.open(kept, DIR_FLAGS, dir_fd=c.app_fd)
    _precheck_tree(c.shared_fd, include_top=True)
    journal_write(c, "rollback_begin", kept=kept)
    fault("rollback_begin")
    shared_frozen = False
    try:
        freeze(c.shared_fd, include_top=True)
        shared_frozen = True
        journal_write(c, "rollback_shared_frozen", kept=kept)
        fault("rollback_shared_frozen")
        thaw(old_fd, include_top=True)
        journal_write(c, "rollback_old_thawed", kept=kept)
        fault("rollback_old_thawed")
        od, nd = {}, {}
        old, new = scan(old_fd, od), scan(c.shared_fd, nd)
        updated = sorted(r for r in old if r in new and old[r] != new[r] and klass(r) == "persistent")
        deleted = sorted(r for r in old if r not in new and klass(r) == "persistent")
        if updated or deleted:
            raise Blocked("UPDATED_OR_DELETED_SINCE_SWITCH:" + json.dumps({"updated": updated, "deleted": deleted}))
        back = sync_additive(c.shared_fd, old_fd)
        need(back["status"] == "OK", back["status"])
        pinned(c, None)
        os.sync()
        renameat2(c.app_fd, "storage", kept, RENAME_EXCHANGE)
        os.fsync(c.app_fd)
        journal_write(c, "rollback_exchanged", kept=kept)
        fault("rollback_exchanged")
        parked = PARKED + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        renameat2(c.app_fd, kept, parked, RENAME_NOREPLACE)
        os.fsync(c.app_fd)
        journal_write(c, "rollback_parked", kept=kept)
        ensure_frozen(c.shared_fd, include_top=True)  # deactivated tree stays protected: retained FDs cannot write to it
        journal_close(c)
        return {"command": "rollback", "status": "OK", "reverse_sync": back, "link_parked_as": parked,
                "deactivated_shared_left_frozen": True, "deleted_anything": False}
    except (Blocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else f"OS_ERROR_{type(exc).__name__}_{getattr(exc, 'errno', '')}"
        try:
            if os.path.islink(c.app / "storage"):  # exchange did not happen: put the evidence copy back as it was
                ensure_frozen(old_fd, include_top=True)
                if shared_frozen:
                    thaw(c.shared_fd, include_top=True)
                journal_close(c)
                return {"command": "rollback", "status": "BLOCKED_" + reason, "deleted_anything": False}
        except (Blocked, OSError):
            pass
        return {"command": "rollback", "status": "BLOCKED_RECOVERY_REQUIRED_JOURNAL_OPEN", "first_error": reason,
                "deleted_anything": False}


def cmd_recover(args) -> dict:
    c = context(args)
    open_state(c)
    entries, keep, exists = journal_read(c)
    torn = exists and keep != os.stat(_journal_name(c), dir_fd=c.state_fd).st_size
    names = sorted(n for n in os.listdir(c.app_fd) if n.startswith((LINK, PRE, PARKED)))
    state = "symlink" if os.path.islink(c.app / "storage") else "directory"
    out = {"command": "recover", "status": "OK", "journal_phase": entries[-1]["phase"] if entries else None,
           "storage_is": state, "leftover_names": names, "journal_torn_tail": bool(torn), "mutated": False}
    if not args.apply:
        return out
    if torn:
        journal_repair(c, keep)  # durable before any recovery append
    if exists and not entries:  # crashed while writing the very first record: nothing was mutated yet
        journal_close(c)
        return {**out, "mutated": bool(torn), "recovered": "torn_begin_discarded"}
    if not entries:
        return out
    FREEZER.require_ready(str(c.app))  # probe lives in the (never frozen) app dir, not in a frozen tree
    rollback = entries[-1]["phase"].startswith("rollback_")
    link = next((e["link"] for e in reversed(entries) if "link" in e), None)
    kept = next((e["kept"] for e in reversed(entries) if "kept" in e), None)
    plan = next((e["plan"] for e in entries if "plan" in e), None)
    shared_plan = next((e["shared_plan"] for e in entries if "shared_plan" in e), None)
    verified = any(e["phase"] == "verified" for e in entries)
    kept_dir = bool(kept) and os.path.isdir(c.app / kept) and not os.path.islink(c.app / kept)
    link_dir = bool(link) and os.path.isdir(c.app / link) and not os.path.islink(c.app / link)
    shared_live = os.path.realpath(c.app / "storage") == os.path.realpath(c.shared)
    if rollback:
        if state == "symlink" and shared_live and kept_dir:  # exchange never happened: shared is live again
            ensure_frozen(os.open(kept, DIR_FLAGS, dir_fd=c.app_fd), include_top=True)
            thaw(c.shared_fd, include_top=True)
            how = "rollback_not_exchanged"
        else:  # exchanged: old directory is live again, deactivated shared must stay protected
            thaw(os.open("storage", DIR_FLAGS, dir_fd=c.app_fd), include_top=True)
            ensure_frozen(c.shared_fd, include_top=True)
            if kept and os.path.islink(c.app / kept):
                os.rename(c.app / kept, c.app / (PARKED + "recovered-" + secrets.token_hex(4)))
                os.fsync(c.app_fd)
            how = "rollback_exchanged"
    elif state == "symlink" and shared_live and kept_dir and not link_dir:
        if not verified:  # layout alone proves nothing: re-verify old and shared against the journalled identities
            old = os.open(kept, DIR_FLAGS, dir_fd=c.app_fd)
            ensure_frozen(old, include_top=True)
            ensure_frozen(c.shared_fd, include_top=True)  # shared has not been thawed before "verified"
            d_old, d_sh = {}, {}
            ok = (plan is not None and shared_plan is not None
                  and plan_id(scan(old, d_old), d_old) == plan and plan_id(scan(c.shared_fd, d_sh), d_sh) == shared_plan)
            if not ok:
                restore_original(c, link, kept)  # shared never accepted a write while frozen: reverting hides nothing
                journal_close(c)
                return {**out, "mutated": True, "recovered": "switch_reverted_unverified"}
            journal_write(c, "verified")
        thaw(c.shared_fd, include_top=True)  # verified: only the final thaw/close was missing
        need(tree_clean(c.shared_fd, True), "THAW_NOT_VERIFIED")
        how = "switch_complete"
    else:
        restore_original(c, link, kept)
        how = "switch_reverted"
    journal_close(c)
    return {**out, "mutated": True, "recovered": how}


def cmd_release_shared(args) -> dict:
    """Deliberate, separate step: unfreeze the deactivated shared tree after a rollback."""
    need(args.apply, "APPLY_REQUIRED")
    c = context(args)
    FREEZER.require_ready(str(c.app))
    open_state(c)
    need(not journal_entries(c), "JOURNAL_PRESENT_RUN_RECOVER")
    need(stat.S_ISDIR(os.stat("storage", dir_fd=c.app_fd, follow_symlinks=False).st_mode), "STORAGE_IS_LINKED_TO_SHARED")
    thaw(c.shared_fd, include_top=True)
    need(tree_clean(c.shared_fd, True), "THAW_NOT_VERIFIED")
    return {"command": "release-shared", "status": "OK", "note": "restart any process that kept shared handles open before reuse",
            "deleted_anything": False}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "switch", "rollback", "recover", "release-shared"])
    ap.add_argument("--app-dir", required=True, help="release apps/platform directory")
    ap.add_argument("--shared", required=True, help="shared storage directory")
    ap.add_argument("--allowed-root", default="/home/kmjprod")
    ap.add_argument("--state-dir", default="/var/lib/kmj-main-platform-storage-switch")
    ap.add_argument("--proc-root", default="/proc", help=argparse.SUPPRESS)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--plan-id")
    args = ap.parse_args(argv)
    try:
        result = {"plan": cmd_plan, "switch": cmd_switch, "rollback": cmd_rollback,
                  "recover": cmd_recover, "release-shared": cmd_release_shared}[args.command](args)
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
