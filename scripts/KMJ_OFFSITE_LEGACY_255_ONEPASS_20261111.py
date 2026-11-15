#!/usr/bin/python3
"""Owner-only KMJ-elite diagnostic: legacy systemd vs separately pinned SFTP.

No service/unit/identity changes. A temporary random age-encrypted SFTP canary may
be uploaded and downloaded in the already approved receiver scratch directory.
Neither canary success nor this script is evidence that the legacy backup job ran.
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

UNIT = "kmj-elite-offsite-backup.service"
LEGACY = Path("/usr/local/sbin/kmj-elite-offsite-backup")
LEGACY_SHA = "d66fd2c2cc33c53c1d0a82f1c259640ee642b666feb2c4aaee6cf887dfe98848"
CONF = Path("/etc/kmj-codebridge/offsite-sftp.conf")
IDENTITY = Path("/root/.ssh/kmj-google-offsite-20261031-ed25519")
HOST, PORT, USER = "34.63.5.14", "22", "info"
REMOTE = "/home/info/kmj-recovery-scratch"
CLIENT_PIN = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
HOST_PIN = "SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
RECIPIENT = "age1952vsyz25elfzn8slyhuc4k586dhw0er45yy26myhvv3lcp9qeps8mj7f5"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C", "LC_ALL": "C"}
CONFIG = (f"HOST={HOST}\nPORT={PORT}\nUSER={USER}\nREMOTE_DIR={REMOTE}\n"
          f"IDENTITY_FILE={IDENTITY}\nHOSTKEY_SHA256={HOST_PIN}\n").encode("ascii")
FP_RE = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
INV_RE = re.compile(r"[0-9a-fA-F]{32}\Z")
KEY_BLOB_PREFIX = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"


class Blocked(Exception):
    pass


def emit(key: str, value: str):
    assert re.fullmatch(r"[A-Z][A-Z0-9_]+", key)
    assert re.fullmatch(r"[A-Z0-9_:.-]+", value)
    print(f"{key}={value}", flush=True)


def safe_file(path: Path, maxbytes: int, private: bool) -> bytes:
    if not path.is_absolute() or ".." in path.parts:
        raise Blocked("INVALID_PATH")
    parent = path.parent
    while True:
        metadata = os.lstat(parent)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise Blocked("UNSAFE_PARENT")
        if parent == Path("/"):
            break
        parent = parent.parent
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
    try:
        m = os.fstat(fd)
        if (not stat.S_ISREG(m.st_mode) or m.st_uid != 0 or m.st_nlink != 1
                or m.st_mode & (0o077 if private else 0o022)
                or not 1 <= m.st_size <= maxbytes):
            raise Blocked("UNSAFE_FILE")
        content = os.read(fd, maxbytes + 1)
        if len(content) != m.st_size:
            raise Blocked("CHANGED_FILE")
        return content
    finally:
        os.close(fd)


def run(cmd: list[str], seconds: int = 15) -> subprocess.CompletedProcess[bytes]:
    try:
        output = subprocess.run(cmd, cwd="/", env=ENV, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=seconds, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("TOOL_UNAVAILABLE_OR_TIMEOUT") from None
    if len(output.stdout) > 65536 or len(output.stderr) > 65536:
        raise Blocked("TOOL_OUTPUT_OVERSIZE")
    return output


def shown(key: str) -> str | None:
    allowed = {"LoadState", "User", "ExecStart", "Result", "ExecMainStatus",
               "InvocationID", "DropInPaths", "EnvironmentFiles", "FragmentPath"}
    if key not in allowed:
        raise Blocked("UNIT_PROPERTY_UNAPPROVED")
    r = run(["/usr/bin/systemctl", "show", UNIT, f"--property={key}", "--value", "--no-pager"], 8)
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 and len(r.stdout) <= 8192 else None


def classified_journal(inv: str | None) -> str:
    if not inv or not INV_RE.fullmatch(inv):
        return "UNAVAILABLE"
    r = run(["/usr/bin/journalctl", "--no-pager", "--output=cat", "--lines=200",
             f"_SYSTEMD_INVOCATION_ID={inv}"], 12)
    if r.returncode or len(r.stdout) > 65536:
        return "UNAVAILABLE"
    text = r.stdout.decode("utf-8", "replace")
    if re.search(r"Permission denied \(publickey|Too many authentication failures|no mutual signature", text, re.I):
        return "PUBLICKEY_AUTH_DENIED"
    if re.search(r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED", text, re.I):
        return "HOSTKEY_FAILURE"
    if re.search(r"Connection (timed out|refused|reset)|No route to host|Network is unreachable", text, re.I):
        return "NETWORK_FAILURE"
    if re.search(r"No such file or directory|command not found", text, re.I):
        return "MISSING_FILE"
    return "OTHER_OR_UNKNOWN"


def unit_audit() -> bool:
    load, user = shown("LoadState"), shown("User")
    execstart, drops = shown("ExecStart"), shown("DropInPaths")
    status, result = shown("ExecMainStatus"), shown("Result")
    emit("LEGACY_UNIT_LOADED", "YES" if load == "loaded" else "NO")
    emit("LEGACY_EFFECTIVE_USER", "ROOT" if user in ("", "root") else "OTHER_OR_UNKNOWN")
    emit("LEGACY_DROPINS", "ABSENT" if drops == "" else ("PRESENT" if drops else "UNKNOWN"))
    paths = re.findall(r"\bpath=([^\s;]+)", execstart or "")
    path_ok = len(paths) == 1 and paths[0] == str(LEGACY)
    emit("LEGACY_EXECSTART", "EXPECTED_FIXED_PATH" if path_ok else "UNKNOWN_OR_DIFFERENT")
    sha_ok, reads_pinned = False, False
    if path_ok:
        try:
            source = safe_file(LEGACY, 1048576, private=False)
            sha_ok = hashlib.sha256(source).hexdigest() == LEGACY_SHA
            reads_pinned = bytes(str(CONF), "ascii") in source
        except (OSError, Blocked):
            pass
    emit("LEGACY_EXEC_SHA", "EXPECTED" if sha_ok else "NOT_VERIFIED")
    emit("LEGACY_REFERENCES_PINNED_SFTP", "YES" if sha_ok and reads_pinned else ("NO" if sha_ok else "UNKNOWN"))
    emit("LEGACY_LAST_EXIT", "EXIT_255" if status == "255" and result == "exit-code" else "NOT_EXIT_255_OR_UNKNOWN")
    emit("LEGACY_FAILURE_CLASS", classified_journal(shown("InvocationID")) if status == "255" and result == "exit-code" else "NOT_APPLICABLE")
    return path_ok and sha_ok


def fingerprint(pub: bytes) -> str:
    words = pub.decode("ascii", "strict").strip().split()
    if len(words) < 2 or words[0] != "ssh-ed25519":
        raise Blocked("PUBLIC_KEY_FORMAT")
    try:
        blob = base64.b64decode(words[1], validate=True)
    except (ValueError, base64.binascii.Error):
        raise Blocked("PUBLIC_KEY_ENCODING") from None
    if len(blob) != 51 or not blob.startswith(KEY_BLOB_PREFIX):
        raise Blocked("PUBLIC_KEY_WIRE")
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def sftp_args(known: Path, batch: Path) -> list[str]:
    return ["/usr/bin/sftp", "-F", "/dev/null", "-b", str(batch), "-P", PORT,
            "-i", str(IDENTITY), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "IdentityAgent=none", "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
            "-o", "GSSAPIAuthentication=no", "-o", "ProxyCommand=none",
            "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
            "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "UserKnownHostsFile=" + str(known), "-o", "ConnectTimeout=12",
            "-o", "ConnectionAttempts=1", "--", USER + "@" + HOST]


def pin_preflight() -> str:
    if safe_file(CONF, 4096, True) != CONFIG:
        raise Blocked("PINNED_CONFIG_NOT_EXACT")
    safe_file(IDENTITY, 16384, True)
    pub = safe_file(Path(str(IDENTITY) + ".pub"), 8192, False)
    if fingerprint(pub) != CLIENT_PIN:
        raise Blocked("PINNED_CLIENT_KEY_MISMATCH")
    key = run(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(IDENTITY)], 12)
    if key.returncode != 0 or fingerprint(key.stdout) != CLIENT_PIN:
        raise Blocked("PRIVATE_PUBLIC_MISMATCH")
    emit("SSH_IDENTITY", "PINNED_MATCH")
    scan = run(["/usr/bin/ssh-keyscan", "-T", "12", "-t", "ed25519", "-p", PORT, HOST], 22)
    if scan.returncode != 0:
        raise Blocked("HOSTKEY_SCAN_FAILURE")
    rows = [x.split() for x in scan.stdout.decode("ascii", "strict").splitlines()
            if x.strip() and not x.startswith("#")]
    if len(rows) != 1 or len(rows[0]) != 3 or rows[0][0] != HOST or rows[0][1] != "ssh-ed25519":
        raise Blocked("HOSTKEY_SCAN_AMBIGUOUS")
    pin = fingerprint(" ".join(rows[0][1:]).encode("ascii"))
    if pin != HOST_PIN:
        raise Blocked("HOSTKEY_PIN_MISMATCH")
    emit("HOSTKEY_PIN", "PASS")
    return " ".join(rows[0]) + "\n"


def checked_sftp(known: Path, batch: Path, instructions: str, timeout=40):
    batch.write_text(instructions, encoding="ascii")
    batch.chmod(0o600)
    r = run(sftp_args(known, batch), timeout)
    if r.returncode != 0:
        if re.search(rb"Permission denied \(publickey|Too many authentication failures|no mutual signature", r.stderr, re.I):
            raise Blocked("PINNED_PUBLICKEY_REJECTED")
        raise Blocked("SFTP_COMMAND_FAILED")


def sftp_probe(hostline: str):
    with tempfile.TemporaryDirectory(prefix="kmj-offsite-onepass-", dir="/run") as td:
        base = Path(td)
        known, batch = base / "known_hosts", base / "commands"
        known.write_text(hostline, encoding="ascii")
        known.chmod(0o600)
        options = sftp_args(known, batch)
        required = {"BatchMode=yes", "IdentitiesOnly=yes", "IdentityAgent=none",
                    "PasswordAuthentication=no", "KbdInteractiveAuthentication=no",
                    "StrictHostKeyChecking=yes", "UpdateHostKeys=no",
                    "HostKeyAlgorithms=ssh-ed25519", "ProxyCommand=none"}
        if not required.issubset(set(options)):
            raise Blocked("SFTP_SSH_OPTIONS_NOT_STRICT")
        emit("SSH_OPTIONS", "STRICT_PINNED_ONLY")
        checked_sftp(known, batch, "pwd\n")
        emit("SSH_AUTH", "PASS")
        checked_sftp(known, batch, f"cd {REMOTE}\n")
        emit("SFTP_DIRECTORY", "PASS")

        name = "kmj-bounded-canary-" + os.urandom(16).hex() + ".age"
        plain, sealed, back = base / "plain", base / "encrypted.age", base / "readback.age"
        plain.write_bytes(os.urandom(96))
        plain.chmod(0o600)
        # Encrypt a random canary with the existing public recipient, not live data.
        encrypted = run(["/usr/bin/age", "-r", RECIPIENT, "-o", str(sealed), str(plain)], 12)
        if encrypted.returncode != 0 or not sealed.is_file() or not 1 <= sealed.stat().st_size <= 4096:
            raise Blocked("AGE_CANARY_ENCRYPTION_FAILED")
        sealed.chmod(0o600)
        transfer_error = None
        try:
            checked_sftp(known, batch,
                         f"cd {REMOTE}\nput -p {sealed} {name}\nchmod 600 {name}\nget {name} {back}\n", timeout=60)
            emit("OFFSITE_TRANSFER", "PASS")
            expected = hashlib.sha256(sealed.read_bytes()).hexdigest()
            actual = hashlib.sha256(back.read_bytes()).hexdigest()
            if expected != actual:
                raise Blocked("SFTP_SHA256_MISMATCH")
            emit("SHA256_READBACK", "PASS")
        except (Blocked, OSError) as error:
            transfer_error = error
        finally:
            try:
                checked_sftp(known, batch, f"cd {REMOTE}\nrm {name}\n", timeout=35)
                emit("REMOTE_TEST_CLEANUP", "PASS")
            except (Blocked, OSError):
                emit("REMOTE_TEST_CLEANUP", "UNVERIFIED")
        if transfer_error is not None:
            raise transfer_error


def main() -> int:
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0] != "KMJ-elite"):
        emit("ONEPASS", "BLOCKED_ROOT_HOST_OR_ARGUMENTS")
        return 2
    # Unit audit is passive and never triggers/restarts any service.
    try:
        unit_audit()
        line = pin_preflight()
        sftp_probe(line)
    except (Blocked, OSError, UnicodeError, ValueError) as exc:
        emit("ONEPASS", "BLOCKED_" + (str(exc) if isinstance(exc, Blocked) else "LOCAL_PRECHECK"))
        emit("SERVICE_EXECUTION", "NOT_RUN")
        emit("EXIT_255", "NOT_RESOLVED")
        return 3
    emit("ONEPASS", "TRANSPORT_CANARY_VERIFIED")
    emit("SERVICE_EXECUTION", "NOT_RUN")
    emit("EXIT_255", "NOT_RESOLVED")
    emit("BACKUP_RESTORE", "NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
