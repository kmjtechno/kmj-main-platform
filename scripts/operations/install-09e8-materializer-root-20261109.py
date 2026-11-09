#!/usr/bin/env python3
"""Install ONLY a SHA-pinned Main Platform materializer in a root-private directory.

Fixed exact source: 09e8a224cd37445c42588a073a6b52d207475a09.
Fixed destination: /usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh.
No arbitrary input path, URL, candidate, release or shell commands accepted.
Uses Linux renameat2(RENAME_NOREPLACE), so never overwrites an existing entry.

Modes: --inspect (NO network or mutation), --install (root owner action).
Installing does NOT run the materializer, change storage, services, approvals or
production, and does NOT authorize any subsequent cutover.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
from pathlib import Path
import secrets
import socket
import stat
import sys
import urllib.error
import urllib.request

SOURCE_COMMIT = "09e8a224cd37445c42588a073a6b52d207475a09"
EXPECTED_SHA256 = "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f"
BASE = Path("/usr/local/libexec/kmj-codebridge")
DEST = "main-platform-candidate-materialize-v2.sh"
URL = (
    "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/"
    + SOURCE_COMMIT
    + "/scripts/operations/materialize-main-platform-candidate-runtime.sh"
)
MAX_BYTES = 65536
ROOT_UID = 0
RENAME_NOREPLACE = 1
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class Refused(Exception):
    pass


def insist(value: bool, reason: str) -> None:
    if not value:
        raise Refused(reason)


def stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def verify_payload(raw: bytes) -> None:
    insist(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "SOURCE_SIZE_INVALID")
    insist(hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256,
           "SOURCE_SHA_MISMATCH")


def open_protected_parent() -> int:
    """FD walk: no symlinks; all ancestors root-owned and not writable by others."""
    fd = os.open("/", DIR_FLAGS)
    try:
        for part in BASE.parts[1:]:
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            info = os.fstat(child)
            if not (stat.S_ISDIR(info.st_mode) and info.st_uid == ROOT_UID
                    and not stat.S_IMODE(info.st_mode) & 0o022):
                os.close(child)
                raise Refused("DEPENDENCY_PARENT_UNTRUSTED")
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def inspect_fd(parent_fd: int) -> str:
    """Only a regular root-owned 0600, one-link, byte-pinned file can pass."""
    try:
        fd = os.open(DEST, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent_fd)
    except FileNotFoundError:
        return "MISSING"
    except OSError as exc:
        raise Refused("MATERIALIZER_ENTRY_UNSAFE") from exc
    try:
        before = os.fstat(fd)
        insist(stat.S_ISREG(before.st_mode) and before.st_uid == ROOT_UID
               and stat.S_IMODE(before.st_mode) == 0o600
               and before.st_nlink == 1 and 0 < before.st_size <= MAX_BYTES,
               "MATERIALIZER_MODE_UNSAFE")
        raw = bytearray()
        while len(raw) <= MAX_BYTES:
            part = os.read(fd, min(16384, MAX_BYTES + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        insist(len(raw) == before.st_size, "MATERIALIZER_TRUNCATED")
        verify_payload(bytes(raw))
        after = os.fstat(fd)
        path = os.stat(DEST, dir_fd=parent_fd, follow_symlinks=False)
        insist(stamp(before) == stamp(after) == stamp(path),
               "MATERIALIZER_ENTRY_CHANGED")
        return "ROOT_PROTECTED_PINNED"
    finally:
        os.close(fd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refused("SOURCE_REDIRECT_NOT_ALLOWED")


def fetch_exact() -> bytes:
    # Fixed HTTPS host and commit; do not inherit the caller's proxy settings.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(),
        NoRedirect()
    )
    response = opener.open(
        urllib.request.Request(URL, method="GET",
                               headers={"Accept": "application/octet-stream"}),
        timeout=30
    )
    with response:
        insist(response.status == 200 and response.geturl() == URL,
               "SOURCE_URL_CHANGED")
        data = response.read(MAX_BYTES + 1)
    verify_payload(data)
    return data


def rename_noreplace(parent_fd: int, source: str, destination: str) -> None:
    """Atomic Linux rename: destination exists => fail, never replace."""
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                   ctypes.c_char_p, ctypes.c_uint)
    fn.restype = ctypes.c_int
    if fn(parent_fd, os.fsencode(source), parent_fd,
          os.fsencode(destination), RENAME_NOREPLACE):
        value = ctypes.get_errno()
        raise OSError(value, os.strerror(value))


def install_fd(parent_fd: int, raw: bytes) -> str:
    """Create in the verified directory, fsync, then no-replace rename."""
    verify_payload(raw)
    existing = inspect_fd(parent_fd)
    if existing == "ROOT_PROTECTED_PINNED":
        return "ALREADY_PINNED"
    insist(existing == "MISSING", "PREEXISTING_MATERIALIZER_UNTRUSTED")
    temporary = ".kmj-materializer-" + secrets.token_hex(12)
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
                 | os.O_CLOEXEC, 0o600, dir_fd=parent_fd)
    published = False
    try:
        info = os.fstat(fd)
        insist(stat.S_ISREG(info.st_mode) and info.st_uid == ROOT_UID
               and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
               "TEMPORARY_FILE_UNTRUSTED")
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            insist(n > 0, "INSTALL_SHORT_WRITE")
            view = view[n:]
        os.fsync(fd)
        insist(os.fstat(fd).st_size == len(raw), "INSTALL_SIZE_MISMATCH")
        rename_noreplace(parent_fd, temporary, DEST)
        published = True
        os.fsync(parent_fd)
    finally:
        os.close(fd)
        if not published:
            # Our O_EXCL private temporary name, never an operator file.
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    insist(inspect_fd(parent_fd) == "ROOT_PROTECTED_PINNED",
           "POST_INSTALL_PROVENANCE_NOT_ATTESTED")
    return "INSTALLED_ROOT_PROTECTED"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)
    print("SCHEMA=kmj.09e8.materializer.root-install.v1")
    try:
        insist(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
               "WRONG_HOST_OR_USER")
        parent_fd = open_protected_parent()
        try:
            current = inspect_fd(parent_fd)
            if args.inspect:
                outcome = current
            elif current == "ROOT_PROTECTED_PINNED":
                outcome = "ALREADY_PINNED"
            else:
                insist(current == "MISSING", "PREEXISTING_ENTRY_UNTRUSTED")
                content = fetch_exact()
                outcome = install_fd(parent_fd, content)
            print("ROOT_MATERIALIZER=" + outcome)
            print("STORAGE_APPLY_ALLOWED=NO")
            print("PRODUCTION_MUTATION=NONE")
            return 0
        finally:
            os.close(parent_fd)
    except (Refused, OSError, OverflowError, urllib.error.URLError) as exc:
        # No raw path, credentials, HTTP status detail, or filesystem data.
        reason = str(exc) if isinstance(exc, Refused) else "RUNTIME_UNVERIFIABLE"
        print("ROOT_MATERIALIZER=BLOCKED_" + reason)
        print("STORAGE_APPLY_ALLOWED=NO")
        print("PRODUCTION_MUTATION=NONE")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
