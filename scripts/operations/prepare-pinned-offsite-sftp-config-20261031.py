#!/usr/bin/env python3
"""Owner-only, no-overwrite pinning of the EXACT verified Google SFTP transport.

The old kmj-elite-offsite-backup.service uses a different rsync/SSH path and
remains untouched. This ONLY creates a protected local config for the distinct,
already reviewed scripts/operations/push-offsite-pinned-sftp-20261030.sh.

No arguments beyond --check/--install, no new keys, remote connections,
transfers, credentials, service commands, backup claims or production changes.
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

PARENT = Path("/etc/kmj-codebridge")
TARGET = PARENT / "offsite-sftp.conf"
PRIVATE = Path("/root/.ssh/kmj-google-offsite-20261031-ed25519")
PUBLIC = Path(str(PRIVATE) + ".pub")
CLIENT_FP = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
HOST_FP = "SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
CONFIG = (
    "HOST=34.63.5.14\n"
    "PORT=22\n"
    "USER=info\n"
    "REMOTE_DIR=/home/info/kmj-recovery-scratch\n"
    "IDENTITY_FILE=/root/.ssh/kmj-google-offsite-20261031-ed25519\n"
    "HOSTKEY_SHA256=" + HOST_FP + "\n"
).encode("ascii")
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/root"}


class Blocked(Exception):
    pass


def protected_directory(path: Path):
    s = os.lstat(path)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
        raise Blocked("DIRECTORY_OWNER_MODE_UNSAFE")


def protected_file(path: Path, *, private=False, maximum=65536):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_nlink != 1
            or s.st_mode & (0o077 if private else 0o022)
            or not 32 < s.st_size <= maximum):
            raise Blocked("FILE_OWNER_MODE_UNSAFE")
        data = os.read(fd, maximum + 1)
        if len(data) != s.st_size:
            raise Blocked("FILE_CHANGED_DURING_READ")
        return data
    finally:
        os.close(fd)


def key_fingerprint(public: str):
    words = public.strip().split()
    if len(words) not in (2, 3) or words[0] != "ssh-ed25519":
        raise Blocked("PUBLIC_FORMAT_INVALID")
    try:
        blob = base64.b64decode(words[1], validate=True)
    except (ValueError, base64.binascii.Error):
        raise Blocked("PUBLIC_BLOB_INVALID") from None
    if len(blob) != 51 or blob[:19] != b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20":
        raise Blocked("PUBLIC_BLOB_INVALID")
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def verify_keypair():
    for d in (Path("/root"), Path("/root/.ssh")):
        protected_directory(d)
    protected_file(PRIVATE, private=True)
    pub = protected_file(PUBLIC, maximum=8192).decode("ascii", "strict").strip()
    if key_fingerprint(pub) != CLIENT_FP:
        raise Blocked("CLIENT_FINGERPRINT_MISMATCH")
    try:
        r = subprocess.run(
            ["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(PRIVATE)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=10, cwd="/", env=ENV,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("KEY_DERIVATION_FAILED") from None
    if r.returncode != 0 or len(r.stdout) > 8192:
        raise Blocked("KEY_DERIVATION_FAILED")
    derived = r.stdout.decode("ascii", "strict").split()
    if len(derived) < 2 or derived[:2] != pub.split()[:2]:
        raise Blocked("PUBLIC_PRIVATE_MISMATCH")


def existing_config():
    try:
        raw = protected_file(TARGET, private=True, maximum=4096)
    except FileNotFoundError:
        return "MISSING"
    except OSError:
        raise Blocked("CONFIG_UNSAFE_OR_UNREADABLE") from None
    if raw != CONFIG:
        raise Blocked("EXISTING_CONFIG_DIFFERS")
    return "EXACT_MATCH_UNCHANGED"


def prepare(mode: str):
    if mode not in ("--check", "--install"):
        raise Blocked("INVALID_MODE")
    for d in (Path("/"), Path("/etc"), PARENT):
        protected_directory(d)
    verify_keypair()
    state = existing_config()
    if state != "MISSING":
        return state
    if mode == "--check":
        return "MISSING_NO_CHANGE"
    # O_EXCL ensures a preexisting symlink/file is never replaced or truncated.
    dirfd = os.open(PARENT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(dirfd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise Blocked("CONFIG_PARENT_CHANGED")
        fd = os.open(TARGET.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=dirfd)
        try:
            os.fchmod(fd, 0o600)
            if os.write(fd, CONFIG) != len(CONFIG):
                raise Blocked("CONFIG_WRITE_INCOMPLETE")
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(dirfd)
    except FileExistsError:
        raise Blocked("CONFIG_ALREADY_CREATED_BY_OTHER")
    finally:
        os.close(dirfd)
    if existing_config() != "EXACT_MATCH_UNCHANGED":
        raise Blocked("POST_WRITE_VERIFY_FAILED")
    return "INSTALLED_NEW_NO_OVERWRITE"


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if (len(args) != 1 or args[0] not in ("--check", "--install")
        or os.geteuid() != 0
        or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        print("OFFSITE_SFTP_CONFIG=BLOCKED_HOST_ROOT_OR_ARGUMENTS")
        return 2
    try:
        result = prepare(args[0])
    except (Blocked, OSError, UnicodeError, ValueError):
        print("OFFSITE_SFTP_CONFIG=BLOCKED_SAFETY_OR_STATE")
        return 3
    print("OFFSITE_SFTP_CONFIG=" + result)
    print("EXPECTED_PUBLIC_CLIENT_KEY=VERIFIED")
    print("GOOGLE_HOST_FINGERPRINT_PIN=CONFIGURED_NOT_REPROBED")
    print("OLD_BACKUP_SERVICE=UNCHANGED")
    print("REMOTE_AUTH=NOT_RETESTED")
    print("BACKUP_CREATED=NO")
    print("RESTORE_VERIFIED=NO")
    print("PRODUCTION_CHANGED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
