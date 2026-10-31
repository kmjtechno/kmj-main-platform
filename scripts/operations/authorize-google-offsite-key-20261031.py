#!/usr/bin/env python3
"""Google VPS owner-only additive enrollment of exactly one approved ELITE public key.

Runs on google-vps1 as the existing 'info' account only. Never accepts caller
keys, paths, usernames, env variables, SSH commands or remote addresses. The
private key remains on KMJ-elite. --check is read-only; --authorize can only
append one restricted line to the existing owner-managed authorized_keys file.
Neither operation proves SSH login, transfer, backup, restore or release.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import sys

EXPECTED_FP = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
PUBLIC_B64 = "AAAAC3NzaC1lZDI1NTE5AAAAIBAk4YE9gWVeGIEsG7NyHzwdfZr9HRJHnNbXWfULzPzn"
ALLOWED_HOST = "google-vps1"
ALLOWED_USER = "info"
RESTRICTED_LINE = "restrict ssh-ed25519 " + PUBLIC_B64 + " kmj-elite-offsite-20261031"
MAX_AUTH_BYTES = 512 * 1024


class Blocked(Exception):
    pass


def valid_public_key():
    try:
        blob = base64.b64decode(PUBLIC_B64, validate=True)
    except (ValueError, base64.binascii.Error):
        raise Blocked("PUBLIC_KEY_INVALID") from None
    if len(blob) != 51 or blob[:19] != (
        b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
    ):
        raise Blocked("PUBLIC_KEY_INVALID")
    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(blob).digest()
    ).decode("ascii").rstrip("=")
    if fingerprint != EXPECTED_FP:
        raise Blocked("PUBLIC_FINGERPRINT_MISMATCH")


def allowed_owner():
    if os.geteuid() == 0:
        raise Blocked("ROOT_NOT_ALLOWED")
    try:
        name = pwd.getpwuid(os.geteuid()).pw_name
    except (KeyError, OSError):
        raise Blocked("OWNER_IDENTITY_UNKNOWN") from None
    if name != ALLOWED_USER or socket.gethostname().split(".")[0] != ALLOWED_HOST:
        raise Blocked("WRONG_HOST_OR_ACCOUNT")
    valid_public_key()
    home = Path(pwd.getpwnam(ALLOWED_USER).pw_dir)
    if home == Path("/") or ".." in home.parts or not home.is_absolute():
        raise Blocked("OWNER_HOME_UNSAFE")
    return home


def safe_dir(path, uid):
    try:
        st = os.lstat(path)
    except OSError:
        raise Blocked("OWNER_SSH_DIRECTORY_MISSING") from None
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != uid
        or st.st_mode & 0o022):
        raise Blocked("OWNER_SSH_DIRECTORY_UNSAFE")


def exact_key_count(data: bytes):
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeError:
        raise Blocked("AUTHORIZED_KEYS_ENCODING") from None
    if "\x00" in text:
        raise Blocked("AUTHORIZED_KEYS_ENCODING")
    matches = []
    for row in text.splitlines():
        if not row.strip() or row.lstrip().startswith("#"):
            continue
        columns = row.split()
        for i, word in enumerate(columns):
            if word != "ssh-ed25519":
                continue
            if i + 1 < len(columns) and columns[i + 1] == PUBLIC_B64:
                matches.append(row)
    return matches, text


def process(mode, *, home=None, uid=None):
    if mode not in ("--check", "--authorize"):
        raise Blocked("INVALID_MODE")
    if home is None:
        home = allowed_owner()
    if uid is None:
        uid = os.geteuid()
    valid_public_key()
    ssh = home / ".ssh"
    target = ssh / "authorized_keys"
    safe_dir(home, uid)
    safe_dir(ssh, uid)
    # Existing file only: no file creation, deletion or permissions changes.
    # Require existing Google owner SSH enrollment before additive mutation.
    flags = os.O_RDONLY if mode == "--check" else os.O_RDWR | os.O_APPEND
    flags |= os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(target, flags)
    except FileNotFoundError:
        raise Blocked("AUTHORIZED_KEYS_MISSING") from None
    except OSError:
        raise Blocked("AUTHORIZED_KEYS_UNAVAILABLE") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH if mode == "--check" else fcntl.LOCK_EX)
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid
            or st.st_nlink != 1 or st.st_mode & 0o077
            or st.st_size > MAX_AUTH_BYTES):
            raise Blocked("AUTHORIZED_KEYS_UNSAFE")
        try:
            path_state = os.lstat(target)
        except OSError:
            raise Blocked("AUTHORIZED_KEYS_PATH_CHANGED") from None
        if ((path_state.st_dev, path_state.st_ino) != (st.st_dev, st.st_ino)
            or not stat.S_ISREG(path_state.st_mode)):
            raise Blocked("AUTHORIZED_KEYS_PATH_CHANGED")
        data = os.read(fd, st.st_size + 1)
        if len(data) != st.st_size:
            raise Blocked("AUTHORIZED_KEYS_CHANGED")
        matches, text = exact_key_count(data)
        if matches:
            if len(matches) != 1 or matches[0] != RESTRICTED_LINE:
                raise Blocked("DUPLICATE_OR_UNRESTRICTED_KEY")
            status = "ALREADY_AUTHORIZED_RESTRICTED"
        elif mode == "--check":
            status = "NOT_REGISTERED"
        else:
            # Ensure the original inode remains the pathname target just
            # before appending; O_APPEND + locked descriptor preserves bytes.
            live = os.lstat(target)
            if (live.st_dev, live.st_ino) != (st.st_dev, st.st_ino):
                raise Blocked("AUTHORIZED_KEYS_PATH_CHANGED")
            if os.fstat(fd).st_size != st.st_size:
                raise Blocked("AUTHORIZED_KEYS_CHANGED")
            payload = (b"" if not data or data.endswith(b"\n") else b"\n")
            payload += (RESTRICTED_LINE + "\n").encode("ascii")
            if st.st_size + len(payload) > MAX_AUTH_BYTES:
                raise Blocked("AUTHORIZED_KEYS_SIZE_LIMIT")
            if os.write(fd, payload) != len(payload):
                raise Blocked("AUTHORIZED_KEYS_WRITE_INCOMPLETE")
            os.fsync(fd)
            status = "APPENDED_RESTRICTED"
        return status
    finally:
        os.close(fd)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in ("--check", "--authorize"):
        print("GOOGLE_OFFSITE_AUTH=BLOCKED_INVALID_MODE")
        return 2
    try:
        status = process(args[0])
    except (Blocked, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, Blocked) else "LOCAL_ERROR"
        # All error codes are fixed classifications, never raw paths, keys or
        # journal records; do not emit exception tracebacks to console.
        if not re.fullmatch(r"[A-Z_]{2,60}", code):
            code = "LOCAL_ERROR"
        print("GOOGLE_OFFSITE_AUTH=BLOCKED_" + code)
        return 3
    print("GOOGLE_OFFSITE_AUTH=" + status)
    print("AUTHORIZED_CLIENT_FINGERPRINT=" + EXPECTED_FP)
    print("PREVIOUS_AUTHORIZED_KEYS=PRESERVED")
    print("PRIVATE_KEY_TRANSFERRED=NO")
    print("SSHD_RESTARTED=NO")
    print("SSH_LOGIN_VERIFIED=NO")
    print("BACKUP_VERIFIED=NO")
    print("RESTORE_VERIFIED=NO")
    print("MAIN_PRODUCTION_CHANGED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
