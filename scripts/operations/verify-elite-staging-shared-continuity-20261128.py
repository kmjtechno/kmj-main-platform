#!/usr/bin/env python3
"""Read-only exact staging storage continuity verifier; never mutates the seal,
storage, approval, database, web configuration or release pointers.

The current candidate may use the canonical shared app directory, but its
public/storage symlink is forbidden by the installed executable-tree seal.
Public URL serving must be separately verified at the staging web server.
"""
import hashlib
import os
from pathlib import Path
import socket
import stat

STAGE = Path("/home/kmjstage")
OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
NEW = "710c6f3ca10310457bc7243caabc0e48476ec110"
LIVE = "platform-72e7c9ada190"
SHARED = STAGE / "shared/storage-app-b2e69decab3a"
ARTWORK = STAGE / "shared/product-artwork"


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def real_dir(path):
    return path.is_dir() and not path.is_symlink() and path.resolve(strict=True) == path


def exact_link(path, target):
    return path.is_symlink() and path.resolve(strict=True) == target and real_dir(target)


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_uid,
            s.st_gid, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def inventory(root, artwork=ARTWORK):
    need(real_dir(root), "TREE_ROOT_UNSAFE")
    entries = {}
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    def walk(fd, rel):
        before = os.fstat(fd)
        for name in sorted(os.listdir(fd)):
            p = rel / name
            s = os.stat(name, dir_fd=fd, follow_symlinks=False)
            need(s.st_dev == before.st_dev, "CROSS_DEVICE")
            if stat.S_ISDIR(s.st_mode):
                child = os.open(name, flags, dir_fd=fd)
                try:
                    need(stamp(os.fstat(child)) == stamp(s), "DIR_DRIFT")
                    entries[p.as_posix()] = ("dir", "")
                    walk(child, p)
                finally:
                    os.close(child)
            elif stat.S_ISREG(s.st_mode):
                need(s.st_nlink == 1, "HARDLINK")
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                with os.fdopen(child, "rb") as stream:
                    need(stamp(os.fstat(stream.fileno())) == stamp(s), "FILE_DRIFT")
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    need(stamp(os.fstat(stream.fileno())) == stamp(s), "FILE_DRIFT")
                entries[p.as_posix()] = ("file", digest)
            elif stat.S_ISLNK(s.st_mode):
                need(p.as_posix() == "private/product-artwork" and real_dir(artwork),
                     "UNREVIEWED_LINK")
                need(os.readlink(name, dir_fd=fd) == str(artwork), "ARTWORK_TARGET")
                entries[p.as_posix()] = ("link", "canonical-artwork")
            else:
                raise ValueError("SPECIAL_NODE")
            need(stamp(os.stat(name, dir_fd=fd, follow_symlinks=False)) == stamp(s), "ENTRY_DRIFT")
        need(stamp(os.fstat(fd)) == stamp(before), "DIRECTORY_DRIFT")
    fd = os.open(root, flags)
    try:
        walk(fd, Path("."))
    finally:
        os.close(fd)
    return entries


def compare(old, new):
    # A missing canonical artwork link (or an empty scaffold at that exact
    # path) is the only allowed structural difference before repair.
    key = "private/product-artwork"
    if old.get(key) != ("link", "canonical-artwork"):
        return False
    if new.get(key) not in (None, ("dir", ""), ("link", "canonical-artwork")):
        return False
    return {k: v for k, v in old.items() if k != key} == {
        k: v for k, v in new.items() if k != key}


def main():
    try:
        need(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "HOST_ROOT")
        previous = STAGE / "releases" / OLD / "apps/platform"
        candidate = STAGE / "releases" / NEW / "apps/platform"
        need(exact_link(STAGE / "htdocs/staging.kmjtechno.com", previous), "STAGE_DRIFT")
        need(exact_link(Path("/home/kmjprod/current"), Path("/home/kmjprod/releases") / LIVE), "LIVE_DRIFT")
        need(real_dir(candidate) and real_dir(SHARED) and real_dir(ARTWORK), "ROOT_SCOPE")
        need(exact_link(previous / "storage/app", SHARED), "SOURCE_LINK_DRIFT")
        old = inventory(SHARED)
        need(old.get("private/product-artwork") == ("link", "canonical-artwork"), "ARTWORK_MISSING")
        dst = candidate / "storage/app"
        shared = exact_link(dst, SHARED)
        new = old if shared else inventory(dst)
        need(compare(old, new), "FILE_CONTENT_MISMATCH")
        print("STAGE_REGULAR_FILE_AND_DIRECTORY_PARITY=PASS")
        print("STAGE_SHARED_APP=" + ("EXACT" if shared else "NOT_LINKED"))
        print("STAGE_ARTWORK=" + ("EXACT" if new.get("private/product-artwork") == ("link", "canonical-artwork") else "MISSING"))
        print("STAGE_PUBLIC_MAPPING=EXTERNAL_WEB_SERVER_VERIFICATION_REQUIRED")
        print("STAGE_STORAGE_ATTESTATION=NOT_ISSUED MODIFICATIONS=NONE")
        return 0
    except (ValueError, OSError) as exc:
        print("STAGE_STORAGE_CHECK=BLOCKED_" + (str(exc) if isinstance(exc, ValueError) else "FILESYSTEM"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
