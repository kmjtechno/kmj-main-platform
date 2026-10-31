#!/usr/bin/env python3
"""Stage ONE non-overwriting ELITE->Google offsite SSH client key.

This ONLY prepares a fresh local public/private keypair for owner-controlled
remote enrollment. It NEVER modifies the installed backup unit, SSH config,
remote authorized_keys, production, backup archives, or the release pointer.
The private key is never printed, copied or included in a receipt.

Modes: --check (read-only); --prepare (explicit owner-side key creation).
Do NOT consider a keypair or a fingerprint proof of remote authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

DIRECTORY = Path("/root/.ssh")
PRIVATE = DIRECTORY / "kmj-google-offsite-20261031-ed25519"
PUBLIC = DIRECTORY / "kmj-google-offsite-20261031-ed25519.pub"
KEYGEN = "/usr/bin/ssh-keygen"
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/root"}
PUBLIC_RE = re.compile(r"ssh-ed25519 ([A-Za-z0-9+/]{60,120}={0,2})(?: [A-Za-z0-9_.@-]{1,80})?\Z")
FP_RE = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")


class Blocked(Exception):
    pass


def protected_dir():
    for path, mode in ((Path("/root"), None), (DIRECTORY, 0o700)):
        try:
            st = os.lstat(path)
        except OSError:
            raise Blocked("ROOT_SSH_DIRECTORY_MISSING") from None
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise Blocked("ROOT_SSH_DIRECTORY_UNSAFE")
        if mode is not None and stat.S_IMODE(st.st_mode) != mode:
            raise Blocked("ROOT_SSH_DIRECTORY_UNSAFE")


def protected_file(path: Path, *, private: bool) -> bool:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        raise Blocked("KEY_FILE_METADATA_UNAVAILABLE") from None
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
        or st.st_mode & 0o077 or not 20 < st.st_size < (65536 if private else 8192)):
        raise Blocked("KEY_FILE_METADATA_UNSAFE")
    return True


def run_keygen(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run([KEYGEN, *args], stdin=subprocess.PIPE,
            input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=20, check=False, cwd="/", env=ENV)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("KEYGEN_UNAVAILABLE") from None
    if result.returncode or len(result.stdout) > 8192:
        raise Blocked("KEYGEN_OPERATION_FAILED")
    return result.stdout


def public_key() -> str:
    # Verify actual private key corresponds to the public key without
    # revealing the private key's contents, and without a passphrase prompt.
    derived = run_keygen(["-y", "-P", "", "-f", str(PRIVATE)])
    if not derived or len(derived) > 1000:
        raise Blocked("DERIVED_PUBLIC_KEY_INVALID")
    derived_words = derived.decode("ascii", "strict").strip().split()
    if len(derived_words) < 2 or derived_words[0] != "ssh-ed25519":
        raise Blocked("DERIVED_PUBLIC_KEY_INVALID")
    fd = os.open(PUBLIC, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Blocked("PUBLIC_KEY_METADATA_UNSAFE")
        pub = os.read(fd, 8193).decode("ascii", "strict").strip()
    finally:
        os.close(fd)
    if not PUBLIC_RE.fullmatch(pub):
        raise Blocked("PUBLIC_KEY_FORMAT_INVALID")
    words = pub.split()
    if words[:2] != derived_words[:2]:
        raise Blocked("PUBLIC_PRIVATE_KEY_MISMATCH")
    result = run_keygen(["-l", "-E", "sha256", "-f", "-"], input_bytes=(pub + "\n").encode())
    tokens = result.decode("ascii", "strict").split()
    if len(tokens) < 2 or not FP_RE.fullmatch(tokens[1]):
        raise Blocked("FINGERPRINT_INVALID")
    print("OFFSITE_PUBLIC_FINGERPRINT=" + tokens[1])
    # Public key is intentionally emitted only for explicit owner enrollment.
    print("OFFSITE_PUBLIC_KEY=" + pub)
    print("REMOTE_AUTHORIZATION=NOT_VERIFIED")
    print("BACKUP_CREATED=NO")
    print("RESTORE_VERIFIED=NO")
    print("PRODUCTION_CHANGED=NO")
    return pub


def stage(mode: str):
    protected_dir()
    priv = protected_file(PRIVATE, private=True)
    pub = protected_file(PUBLIC, private=False)
    if priv and pub:
        print("OFFSITE_KEYPAIR=EXISTS_UNCHANGED")
    elif priv or pub:
        raise Blocked("PARTIAL_KEYPAIR_REQUIRES_OWNER_REVIEW")
    elif mode == "--check":
        print("OFFSITE_KEYPAIR=ABSENT")
        print("REMOTE_AUTHORIZATION=NOT_VERIFIED")
        return
    else:
        # The fixed private path and its public sidecar must both be absent.
        # ssh-keygen's no-overwrite behavior is independently checked above.
        previous = os.umask(0o077)
        try:
            run_keygen(["-q", "-t", "ed25519", "-a", "100", "-N", "",
                        "-C", "kmj-google-offsite-20261031", "-f", str(PRIVATE)])
        finally:
            os.umask(previous)
        if not (protected_file(PRIVATE, private=True) and protected_file(PUBLIC, private=False)):
            raise Blocked("NEW_KEY_METADATA_UNSAFE")
        print("OFFSITE_KEYPAIR=STAGED_NEW")
    if priv or mode == "--prepare":
        public_key()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if (len(args) != 1 or args[0] not in ("--check", "--prepare")
        or os.geteuid() != 0
        or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        print("OFFSITE_KEY_STAGE=BLOCKED_HOST_ROOT_OR_ARGS")
        return 2
    try:
        stage(args[0])
    except (Blocked, OSError, UnicodeError, ValueError):
        print("OFFSITE_KEY_STAGE=BLOCKED_SAFETY_OR_STATE")
        return 3
    print("OFFSITE_KEY_STAGE=LOCAL_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
