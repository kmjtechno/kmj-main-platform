#!/usr/bin/env python3
"""Read-only, exact-host-key-pinned SFTP authentication and directory probe.

Fixed KMJ-elite -> existing Google receiver only. Never uploads, creates,
deletes, restarts, changes credentials, or emits raw SSH output/key paths.
The legacy rsync/SSH systemd service remains untouched and unverified.
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
import tempfile

HOST = "34.63.5.14"
USER = "info"
PORT = "22"
REMOTE_DIR = "/home/info/kmj-recovery-scratch"
IDENTITY = Path("/root/.ssh/kmj-google-offsite-20261031-ed25519")
CONFIG_PATH = Path("/etc/kmj-codebridge/offsite-sftp.conf")
CLIENT_PIN = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
SERVER_PIN = "SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
CONFIG_BYTES = (
    "HOST=" + HOST + "\nPORT=" + PORT + "\nUSER=" + USER
    + "\nREMOTE_DIR=" + REMOTE_DIR
    + "\nIDENTITY_FILE=" + str(IDENTITY)
    + "\nHOSTKEY_SHA256=" + SERVER_PIN + "\n"
).encode("ascii")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C", "LC_ALL": "C"}
WIRE_PREFIX = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"


class Blocked(Exception):
    pass


def read_protected(path: Path, *, private: bool, limit: int = 16384) -> bytes:
    if not path.is_absolute() or ".." in path.parts:
        raise Blocked("UNSAFE_PATH")
    cur = path.parent
    while True:
        st = os.lstat(cur)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise Blocked("UNSAFE_PARENT")
        if cur == Path("/"):
            break
        cur = cur.parent
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
                or st.st_mode & (0o077 if private else 0o022)
                or not 0 < st.st_size <= limit):
            raise Blocked("UNSAFE_FILE")
        data = os.read(fd, limit + 1)
        if len(data) != st.st_size:
            raise Blocked("UNSAFE_READ")
        return data
    finally:
        os.close(fd)


def fingerprint_public_line(line: str) -> str:
    words = line.split()
    if len(words) < 2 or words[0] != "ssh-ed25519":
        raise Blocked("PUBLIC_KEY_TYPE")
    try:
        blob = base64.b64decode(words[1], validate=True)
    except (ValueError, base64.binascii.Error):
        raise Blocked("PUBLIC_KEY_ENCODING") from None
    if len(blob) != 51 or not blob.startswith(WIRE_PREFIX):
        raise Blocked("PUBLIC_KEY_WIRE")
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def pinned_scan(scan: str) -> str:
    rows = [s.strip() for s in scan.splitlines() if s.strip() and not s.startswith("#")]
    if len(rows) != 1:
        raise Blocked("HOSTKEY_RESPONSE_COUNT")
    words = rows[0].split()
    if len(words) != 3 or words[0] != HOST:
        raise Blocked("HOSTKEY_RESPONSE_HOST")
    if fingerprint_public_line(" ".join(words[1:])) != SERVER_PIN:
        raise Blocked("HOSTKEY_FINGERPRINT")
    return rows[0] + "\n"


def run(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    try:
        outcome = subprocess.run(
            args, cwd="/", env=ENV, stdin=subprocess.DEVNULL, capture_output=True,
            check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("COMMAND_UNAVAILABLE_OR_TIMEOUT") from None
    if len(outcome.stdout) > 65536 or len(outcome.stderr) > 65536:
        raise Blocked("TOOL_OUTPUT_TOO_LARGE")
    return outcome


def preflight() -> None:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0] != "KMJ-elite"):
        raise Blocked("HOST_ROOT_OR_ARGUMENTS")
    if read_protected(CONFIG_PATH, private=True, limit=4096) != CONFIG_BYTES:
        raise Blocked("PINNED_CONFIG_MISMATCH")
    read_protected(IDENTITY, private=True)
    public = read_protected(Path(str(IDENTITY) + ".pub"), private=False, limit=8192)
    if fingerprint_public_line(public.decode("ascii", "strict")) != CLIENT_PIN:
        raise Blocked("CLIENT_PUBLIC_FINGERPRINT")
    derived = run(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(IDENTITY)], timeout=12)
    if derived.returncode != 0 or fingerprint_public_line(derived.stdout.decode("ascii", "strict")) != CLIENT_PIN:
        raise Blocked("PRIVATE_PUBLIC_KEY_MISMATCH")
    print("LOCAL_PINNED_CONFIG_AND_KEYPAIR=PASS")


def sftp_args(known_hosts: Path, batch: Path) -> list[str]:
    return [
        "/usr/bin/sftp", "-F", "/dev/null", "-b", str(batch), "-P", PORT,
        "-i", str(IDENTITY), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "IdentityAgent=none", "-o", "PreferredAuthentications=publickey",
        "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
        "-o", "GSSAPIAuthentication=no", "-o", "ProxyCommand=none",
        "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "UserKnownHostsFile=" + str(known_hosts),
        "-o", "ConnectTimeout=15", "-o", "ConnectionAttempts=1",
        "--", USER + "@" + HOST,
    ]


def probe() -> int:
    preflight()
    scanned = run(["/usr/bin/ssh-keyscan", "-T", "15", "-t", "ed25519", "-p", PORT, HOST], timeout=25)
    if scanned.returncode != 0:
        raise Blocked("HOSTKEY_FETCH_FAILED")
    host_line = pinned_scan(scanned.stdout.decode("ascii", "strict"))
    print("EXACT_HOSTKEY_PIN=PASS")
    with tempfile.TemporaryDirectory(prefix="kmj-offsite-auth-", dir="/run") as td:
        tmp = Path(td)
        known = tmp / "known_hosts"
        known.write_text(host_line, encoding="ascii")
        known.chmod(0o600)
        batch = tmp / "batch"
        batch.write_text("pwd\n", encoding="ascii")
        batch.chmod(0o600)
        auth = run(sftp_args(known, batch), timeout=35)
        if auth.returncode != 0:
            if re.search(rb"Permission denied \(publickey|Too many authentication failures|no mutual signature", auth.stderr, re.I):
                print("PINNED_REMOTE_AUTH=FAIL:PUBLICKEY_REJECTED")
            else:
                print("PINNED_REMOTE_AUTH=FAIL:UNCLASSIFIED")
            return 1
        print("PINNED_REMOTE_AUTH=PASS")
        batch.write_text("cd " + REMOTE_DIR + "\n", encoding="ascii")
        directory = run(sftp_args(known, batch), timeout=35)
        if directory.returncode != 0:
            print("PINNED_REMOTE_DIRECTORY=NOT_ACCESSIBLE")
            return 1
        print("PINNED_REMOTE_DIRECTORY=PASS")
    print("PROBE=PASS_READ_ONLY")
    print("LEGACY_OFFSITE_SERVICE=UNCHANGED")
    print("BACKUP_RESTORE=NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(probe())
    except (Blocked, OSError, UnicodeError, ValueError) as exc:
        # Only own constant error code; never relay command/config/journal output.
        reason = exc.args[0] if isinstance(exc, Blocked) else "LOCAL_PRECHECK_EXCEPTION"
        print("PROBE=BLOCKED:" + str(reason))
        raise SystemExit(2)
