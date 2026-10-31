#!/usr/bin/env python3
"""KMJ P0: real read-only single-key SSH admission to the independently pinned Google VPS.

No arbitrary host/user/key/command, no arguments, no saved host-key changes,
no backup or remote file writes. Authenticate only after exact host ED25519
fingerprint and fixed root-owned private+public identity independently verify.
Remote executes only /bin/true; no TTY, agent, forwards or password fallback.
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
HOST_KEY_FP = "SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
CLIENT_KEY_FP = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
PRIV = Path("/root/.ssh/kmj-google-offsite-20261031-ed25519")
PUB = Path(str(PRIV) + ".pub")
CLEAN_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/root", "LANG": "C", "LC_ALL": "C"}
KEY_PATTERN = re.compile(r"ssh-ed25519 ([A-Za-z0-9+/]{60,120}={0,2})(?: [A-Za-z0-9_.@-]{1,80})?\Z")


class Blocked(Exception):
    pass


def ed25519_fp(encoded):
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        raise Blocked("KEY_BLOB_INVALID") from None
    if len(blob) != 51 or blob[:19] != b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20":
        raise Blocked("KEY_WIRE_INVALID")
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def safe_file(path, *, private=False):
    st = os.lstat(path)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
        or st.st_mode & (0o077 if private else 0o022)
        or not 40 < st.st_size <= (65536 if private else 8192)):
        raise Blocked("LOCAL_KEY_METADATA_UNSAFE")
    return st


def safe_parent():
    for p in (Path("/root"), Path("/root/.ssh")):
        st = os.lstat(p)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise Blocked("LOCAL_KEY_PARENT_UNSAFE")


def run(argv, *, timeout, input_bytes=None):
    try:
        return subprocess.run(
            argv, input=input_bytes, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
            cwd="/", env=CLEAN_ENV,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def identity():
    safe_parent()
    safe_file(PRIV, private=True)
    safe_file(PUB)
    fd = os.open(PUB, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o022:
            raise Blocked("PUBLIC_KEY_METADATA_UNSAFE")
        data = os.read(fd, 8193).decode("ascii", "strict").strip()
    finally:
        os.close(fd)
    m = KEY_PATTERN.fullmatch(data)
    if m is None or ed25519_fp(m[1]) != CLIENT_KEY_FP:
        raise Blocked("CLIENT_FINGERPRINT_MISMATCH")
    # Confirms private matches the pinned public, no private bytes emitted.
    result = run(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(PRIV)], timeout=10)
    if result is None or result.returncode != 0 or len(result.stdout) > 8192:
        raise Blocked("PRIVATE_KEY_UNUSABLE")
    words = result.stdout.decode("ascii", "strict").split()
    if len(words) < 2 or words[:2] != data.split()[:2]:
        raise Blocked("PUBLIC_PRIVATE_MISMATCH")


def parse_scan(raw):
    if len(raw) > 8192:
        raise Blocked("HOSTKEY_SCAN_OVERSIZED")
    records = set()
    for line in raw.decode("ascii", "strict").splitlines():
        parts = line.split()
        if not parts or line.startswith("#"):
            continue
        if len(parts) != 3 or parts[0] != HOST or parts[1] != "ssh-ed25519":
            raise Blocked("HOSTKEY_UNEXPECTED")
        if ed25519_fp(parts[2]) != HOST_KEY_FP:
            raise Blocked("HOSTKEY_PIN_MISMATCH")
        records.add(line)
    if len(records) != 1:
        raise Blocked("HOSTKEY_AMBIGUOUS")
    return next(iter(records))


def host_key():
    probe = run(
        ["/usr/bin/ssh-keyscan", "-4", "-T", "7", "-p", "22", "-t", "ed25519", HOST],
        timeout=12,
    )
    if probe is None or probe.returncode != 0:
        raise Blocked("HOSTKEY_SCAN_UNAVAILABLE")
    return parse_scan(probe.stdout)


def ssh_probe(line):
    # Private temporary trust file, populated only after cryptographic pin;
    # never modifies root's known_hosts or trusts TOFU.
    with tempfile.TemporaryDirectory(prefix="kmj-google-ssh-proof-") as tmp:
        hostfile = Path(tmp) / "known_hosts"
        fd = os.open(hostfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, (line + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        command = [
            "/usr/bin/ssh", "-F", "/dev/null", "-T", "-n", "-p", "22",
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "IdentityAgent=none",
            "-o", "PreferredAuthentications=publickey",
            "-o", "PubkeyAuthentication=yes",
            "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + str(hostfile),
            "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=8",
            "-o", "ConnectionAttempts=1",
            "-o", "NumberOfPasswordPrompts=0",
            "-o", "ControlMaster=no",
            "-o", "ControlPath=none",
            "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes",
            "-o", "ProxyCommand=none",
            "-o", "PermitLocalCommand=no",
            "-o", "LogLevel=ERROR",
            "-i", str(PRIV),
            "info@" + HOST, "/bin/true",
        ]
        reply = run(command, timeout=25)
        if reply is None:
            return "SSH_PROBE_UNAVAILABLE"
        if reply.returncode == 0:
            return "SSH_READONLY_AUTH_PASS"
        err = reply.stderr[:4096].decode("utf-8", "replace")
        if re.search(r"Permission denied \(publickey|Too many authentication failures|no mutual signature", err, re.I):
            return "SSH_PUBLICKEY_REJECTED"
        if re.search(r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED", err, re.I):
            return "SSH_HOSTKEY_REJECTED"
        if re.search(r"timed out|refused|No route|Network is unreachable|Could not resolve|reset by peer", err, re.I):
            return "SSH_NETWORK_FAILURE"
        return "SSH_NO_SUCCESS_UNCLASSIFIED"


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if (args or os.geteuid() != 0
        or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        print("GOOGLE_SSH_VERIFY=BLOCKED_HOST_ROOT_OR_ARGS")
        return 2
    try:
        identity()
        print("CLIENT_KEYPAIR=EXACT_MATCH")
        pinned_host_line = host_key()
        print("GOOGLE_ED25519_HOSTPIN=PASS")
        result = ssh_probe(pinned_host_line)
    except (Blocked, OSError, ValueError, UnicodeError):
        print("GOOGLE_SSH_VERIFY=BLOCKED_SAFETY_OR_STATE")
        return 3
    print("GOOGLE_SSH_VERIFY=" + result)
    print("REMOTE_COMMAND=TRUE_ONLY")
    print("REMOTES_WRITTEN=NONE")
    print("PRIVATE_KEYS_EXPORTED=NO")
    print("BACKUP_STARTED=NO")
    print("INDEPENDENT_RESTORE=NOT_VERIFIED")
    print("PRODUCTION_CHANGED=NO")
    return 0 if result == "SSH_READONLY_AUTH_PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
