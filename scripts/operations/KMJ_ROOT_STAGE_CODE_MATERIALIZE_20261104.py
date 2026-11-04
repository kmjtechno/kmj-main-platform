#!/usr/bin/env python3
"""Prepare exact built Main Platform CODE snapshot inside private root staging anchor.

Copies the already-isolated, exact-SHA unprivileged-built production candidate
into /var/lib/kmj-main-platform-stage-releases. NEVER copies runtime .env,
storage, build node_modules or bootstrap executable cache. Does not execute
application code, change the staging/production pointers, deploy, back up or
create approval/seal. Source may be user-controlled: copy uses descriptor-based
no-follow opens and rejects special files, hardlinks and content drift.
Output is an INACTIVE, INCOMPLETE source snapshot, not a release.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

SHA = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
STAGE_OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD_OLD = "platform-574e443a2c75"
SRC = Path("/home/kmjprod/releases/platform-" + SHA[:12])
ANCHOR = Path("/var/lib/kmj-main-platform-stage-releases")
PROD_LINK = Path("/home/kmjprod/current")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
GIT = "/usr/bin/git"
RUNUSER = "/usr/sbin/runuser"
ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin", "LANG": "C", "LC_ALL": "C", "HOME": "/home/kmjprod"}
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
MAX_FILES = 130000
MAX_BYTES = 2_000_000_000
MAX_DEPTH = 36
SKIP_EXACT = {
    "apps/platform/storage",
    "apps/platform/node_modules",
    "apps/platform/bootstrap/cache",
    "apps/platform/vendor/bin",
}
BLOCK_NAME = {".env", ".ssh", ".aws", ".gnupg"}
KEY_NAME = re.compile(r"(?i)(?:^id_(?:rsa|ed25519|ecdsa)$|.*\.(?:pem|key|p12|pfx))")


def say(k: str, v: str) -> None:
    print(k + "=" + v, flush=True)


def fail(code: str) -> None:
    say("KMJ_ROOT_STAGE_SOURCE", "BLOCKED_" + code)
    raise SystemExit(2)


def exact_pointers() -> bool:
    try:
        return (stat.S_ISLNK(os.lstat(PROD_LINK).st_mode)
                and os.readlink(PROD_LINK) in {
                    "/home/kmjprod/releases/" + PROD_OLD,
                    "releases/" + PROD_OLD,
                }
                and stat.S_ISLNK(os.lstat(STAGE_LINK).st_mode)
                and os.readlink(STAGE_LINK) in {
                    "/home/kmjstage/releases/" + STAGE_OLD + "/apps/platform",
                    "../releases/" + STAGE_OLD + "/apps/platform",
                })
    except OSError:
        return False


def dirfd_nofollow(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        fail("INVALID_PATH")
    fd = os.open("/", DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            new = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def trusted_anchor() -> tuple[int, os.stat_result]:
    fd = os.open("/", DIR_FLAGS)
    try:
        for part in ("var", "lib", ANCHOR.name):
            cur = os.fstat(fd)
            if not stat.S_ISDIR(cur.st_mode) or cur.st_uid != 0 or cur.st_mode & 0o022:
                fail("ANCHOR_PARENT_NOT_TRUSTED")
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0
                or stat.S_IMODE(st.st_mode) != 0o700):
            fail("ANCHOR_UNTRUSTED")
        if any(v in ("system.posix_acl_access", "system.posix_acl_default") for v in os.listxattr(fd)):
            fail("ANCHOR_EXTENDED_ACL")
        return fd, st
    except BaseException:
        os.close(fd)
        raise


def git_probe() -> bool:
    # Only unprivileged kmjprod executes Git in the user-owned checkout.
    args = [RUNUSER, "-u", "kmjprod", "--", GIT, "-C", str(SRC)]
    try:
        head = subprocess.run(args + ["rev-parse", "HEAD"], capture_output=True,
                              timeout=12, env=ENV, check=False)
        status = subprocess.run(args + ["status", "--porcelain", "--untracked-files=normal"],
                                capture_output=True, timeout=20, env=ENV, check=False)
        return (head.returncode == 0 and head.stdout.strip() == SHA.encode()
                and status.returncode == 0 and status.stdout == b""
                and len(status.stderr) < 65536)
    except (OSError, subprocess.TimeoutExpired):
        return False


def allow_entry(name: str, relative: str) -> bool:
    if not name or name in (".", "..") or "/" in name or "\x00" in name:
        fail("UNSAFE_ENTRY_NAME")
    if relative in SKIP_EXACT:
        return False
    if name in BLOCK_NAME or KEY_NAME.fullmatch(name):
        return False
    return True


def copy_file(source_fd: int, entry: str, target: Path, seen: dict) -> None:
    src_fd = os.open(entry, FILE_FLAGS, dir_fd=source_fd)
    try:
        st = os.fstat(src_fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_size < 0 or st.st_size > MAX_BYTES
                or st.st_mode & 0o022):
            fail("SOURCE_FILE_UNTRUSTED")
        seen["files"] += 1
        seen["bytes"] += st.st_size
        if seen["files"] > MAX_FILES or seen["bytes"] > MAX_BYTES:
            fail("COPY_LIMIT")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        hasher = hashlib.sha256()
        size = 0
        try:
            while True:
                data = os.read(src_fd, 1 << 20)
                if not data:
                    break
                os.write(fd, data)
                hasher.update(data)
                size += len(data)
            os.fchmod(fd, 0o500 if st.st_mode & 0o111 else 0o400)
            os.fsync(fd)
        finally:
            os.close(fd)
        later = os.fstat(src_fd)
        if (size != st.st_size or
                (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) !=
                (later.st_dev, later.st_ino, later.st_size, later.st_mtime_ns, later.st_ctime_ns)):
            fail("SOURCE_FILE_CHANGED")
        seen["digests"].append((str(target.name), hasher.hexdigest()))
    finally:
        os.close(src_fd)


def copy_tree(source_fd: int, output: Path, prefix: str, depth: int, seen: dict, device: int) -> None:
    if depth > MAX_DEPTH:
        fail("DEPTH_LIMIT")
    for name in sorted(os.listdir(source_fd)):
        relative = (prefix + "/" + name).lstrip("/")
        if not allow_entry(name, relative):
            continue
        info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        if info.st_dev != device or info.st_mode & 0o022:
            fail("SOURCE_METADATA_UNTRUSTED")
        dst = output / name
        if stat.S_ISDIR(info.st_mode):
            if info.st_nlink < 1:
                fail("SOURCE_DIR_UNTRUSTED")
            os.mkdir(dst, 0o700)
            child = os.open(name, DIR_FLAGS, dir_fd=source_fd)
            try:
                opened = os.fstat(child)
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    fail("SOURCE_DIR_CHANGED")
                copy_tree(child, dst, relative, depth + 1, seen, device)
                after = os.fstat(child)
                if (opened.st_dev, opened.st_ino, opened.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_mtime_ns):
                    fail("SOURCE_DIR_CHANGED")
                os.chmod(dst, 0o500)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            copy_file(source_fd, name, dst, seen)
        else:
            fail("SOURCE_SYMLINK_OR_SPECIAL")
    if prefix == "apps/platform":
        for name in ("storage", "bootstrap/cache"):
            (output / name).mkdir(parents=True, exist_ok=True, mode=0o500)


def inspect_copy(tmp: Path) -> bool:
    head = tmp / ".git/HEAD"
    app = tmp / "apps/platform"
    manifest = app / "public/build/manifest.json"
    vendor = app / "vendor/autoload.php"
    if not (head.is_file() and head.read_text().strip() == SHA
            and manifest.is_file() and vendor.is_file()
            and not (app / ".env").exists()):
        return False
    try:
        payload = json.loads(manifest.read_bytes())
    except (ValueError, OSError):
        return False
    value = payload.get("resources/js/pages/services/codebridge-workspace.tsx")
    asset = value.get("file") if isinstance(value, dict) else None
    return (isinstance(asset, str) and asset.startswith("assets/")
            and ".." not in Path(asset).parts
            and (app / "public/build" / asset).is_file())


def publish_noclobber(temp: Path, parent_fd: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        fail("NO_RENAME_NOREPLACE")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(temp), parent_fd, SHA.encode("ascii"), 1) != 0:
        code = errno.errorcode.get(ctypes.get_errno(), "IO")
        fail("NO_CLOBBER_" + code)


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        fail("WRONG_ROOT_HOST_OR_ARGS")
    if not exact_pointers():
        fail("POINTER_DRIFT")
    if not git_probe():
        fail("SOURCE_GIT_NOT_EXACT_CLEAN")
    anchorfd, anchorinfo = trusted_anchor()
    temp = None
    published = False
    try:
        if shutil.disk_usage(ANCHOR).free < 4 * 1024**3:
            fail("SPACE_UNDER_4GIB")
        try:
            os.stat(SHA, dir_fd=anchorfd, follow_symlinks=False)
            fail("CANDIDATE_ALREADY_EXISTS")
        except FileNotFoundError:
            pass
        # Copy from a candidate checkout only. Never invoke root Git or PHP.
        sourcefd = dirfd_nofollow(SRC)
        try:
            srcinfo = os.fstat(sourcefd)
            temp = Path(tempfile.mkdtemp(prefix=".kmj-copy-" + SHA[:12] + "-", dir=ANCHOR))
            seen = {"files": 0, "bytes": 0, "digests": []}
            copy_tree(sourcefd, temp, "", 0, seen, srcinfo.st_dev)
        finally:
            os.close(sourcefd)
        if not inspect_copy(temp):
            fail("COPY_ASSETS_OR_HEAD_INVALID")
        if not git_probe():
            fail("SOURCE_CHANGED_POSTCOPY")
        if not exact_pointers():
            fail("POINTER_CHANGED")
        if os.fstat(anchorfd).st_ino != anchorinfo.st_ino:
            fail("ANCHOR_CHANGED")
        publish_noclobber(temp, anchorfd)
        published = True
        say("KMJ_ROOT_STAGE_SOURCE", "PASS_CODE_SNAPSHOT_ONLY")
        say("STAGING_CANDIDATE_SHA", SHA)
        say("STAGING_FILES_COPIED", str(seen["files"]))
        say("STAGING_SOURCE_BYTES_COPIED", str(seen["bytes"]))
        say("STAGING_CODE_OWNER", "ROOT_ONLY")
        say("STAGING_RUNTIME_ENV", "NOT_PRESENT")
        say("STAGING_STORAGE", "NOT_MIGRATED")
        say("STAGING_EXECUTABLE_CACHE", "NOT_COMPILED")
        say("STAGING_SEAL", "NOT_CREATED")
        say("STAGING_APPROVAL", "NOT_CREATED")
        say("STAGING_WEB_ROUTE", "NOT_CHANGED")
        say("STAGING_ACTIVATION", "NOT_ATTEMPTED")
        say("PRODUCTION_POINTER", "UNCHANGED")
        return 0
    finally:
        os.close(anchorfd)
        # Cleanup only our still-private scratch, never an existing release.
        if temp is not None and not published:
            shutil.rmtree(temp)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PermissionError):
        say("KMJ_ROOT_STAGE_SOURCE", "BLOCKED_FILE_IO")
        raise SystemExit(2)
