#!/usr/bin/env python3
"""A2: fixed, read-only kmj-elite offsite-backup SSH255 diagnostic.

Requires root to read the actual systemd invocation and root-only SFTP settings.
No arguments, writes, remote calls, authentication attempts, restarts, or raw output.
Never prints host/user/key paths, environment, unit command, journal or secrets.
Its output is diagnostic ONLY; it cannot attest backups, restore, or release.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "kmj-elite-offsite-backup.service"
CONF = Path("/etc/kmj-codebridge/offsite-sftp.conf")
PROPERTIES = ("LoadState", "Result", "ExecMainStatus", "InvocationID", "ExecStart", "User")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
KEYS = frozenset(("HOST", "PORT", "USER", "REMOTE_DIR", "IDENTITY_FILE", "HOSTKEY_SHA256"))
PIN = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
ABS_PATH = re.compile(r"/[A-Za-z0-9._/-]{1,240}\Z")
INVOCATION = re.compile(r"[A-Fa-f0-9]{32}\Z")
FINGERPRINT = re.compile(r"[a-z0-9._-]{1,40}\Z")
CLASSES = (
    ("SSH_AUTH_KEY_REJECTED", re.compile(r"Permission denied \(publickey|Too many authentication failures|no mutual signature|Load key|invalid format|incorrect passphrase", re.I)),
    ("SSH_HOSTKEY", re.compile(r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED|host key is known", re.I)),
    ("NETWORK_OR_REMOTE_DOWN", re.compile(r"Connection (timed out|refused|reset)|No route to host|Network is unreachable|Could not resolve host|Temporary failure in name resolution", re.I)),
    ("DISK_OR_REMOTE_QUOTA", re.compile(r"No space left|Disk quota|quota exceeded", re.I)),
    ("MISSING_FILE_OR_TOOL", re.compile(r"No such file or directory|command not found", re.I)),
    ("LOCAL_OR_REMOTE_PERMISSION", re.compile(r"Permission denied", re.I)),
)


AUTH_SUBCLASSES = (
    ("LOCAL_KEY_LOAD_FAILURE", re.compile(r"Load key|invalid format|incorrect passphrase|UNPROTECTED PRIVATE KEY FILE", re.I)),
    ("TOO_MANY_AUTH_FAILURES", re.compile(r"Too many authentication failures", re.I)),
    ("NO_MUTUAL_SIGNATURE", re.compile(r"no mutual signature", re.I)),
    ("PUBLICKEY_AUTH_DENIED", re.compile(r"Permission denied \\(publickey", re.I)),
)


def classify_auth_subclass(raw: str) -> str:
    """Redacted hints ONLY. Not proof which key was offered or rejected by remote."""
    for name, pattern in AUTH_SUBCLASSES:
        if pattern.search(raw):
            return name
    return "UNCLASSIFIED"


def classify(raw: str) -> str:
    for name, pattern in CLASSES:
        if pattern.search(raw):
            return name
    return "UNCLASSIFIED"


def show_property(name: str) -> str | None:
    """Consume a systemctl property; NEVER relay its untrusted raw text."""
    if name not in PROPERTIES:
        raise ValueError("UNAPPROVED_PROPERTY")
    try:
        p = subprocess.run(
            ["/usr/bin/systemctl", "show", UNIT, f"--property={name}", "--value", "--no-pager"],
            capture_output=True, text=True, timeout=8, check=False, env=ENV,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode or len(p.stdout) > 8192:
        return None
    return p.stdout.strip()


def journal_for_invocation(invocation: str | None) -> str | None:
    if not invocation or not INVOCATION.fullmatch(invocation):
        return None
    try:
        p = subprocess.run(
            ["/usr/bin/journalctl", "--no-pager", "--output=cat", "--lines=200",
             f"_SYSTEMD_INVOCATION_ID={invocation}"],
            capture_output=True, text=True, timeout=12, check=False, env=ENV,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode or len(p.stdout) > 65536:
        return None
    return p.stdout


def private_regular(path: Path, *, owner_uid: int = 0, stop: Path = Path("/")) -> str:
    """Inspect protected owner-only file and its real, non-writable ancestor chain."""
    if not path.is_absolute() or ".." in path.parts or not str(path).startswith("/"):
        return "UNSAFE_PATH"
    cur = path.parent
    try:
        while True:
            st = os.lstat(cur)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != owner_uid or st.st_mode & 0o022:
                return "UNSAFE_PARENT"
            if cur == stop:
                break
            parent = cur.parent
            if parent == cur:
                return "UNSAFE_PARENT"
            cur = parent
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError:
        return "MISSING"
    except OSError:
        return "UNSAFE_FILE"
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != owner_uid or st.st_nlink != 1
                or st.st_mode & 0o077 or st.st_size < 1 or st.st_size > 4096):
            return "UNSAFE_FILE"
        return "PRIVATE"
    finally:
        os.close(fd)


def parse_config(raw: str) -> dict[str, str] | None:
    """Strict parsing only, no sourcing, shell, interpolation or value output."""
    cfg: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"([A-Z0-9_]+)=([^\s]*)", line)
        if m is None or m.group(1) not in KEYS or m.group(1) in cfg:
            return None
        cfg[m.group(1)] = m.group(2)
    if cfg.keys() != KEYS or not all(cfg.values()):
        return None
    if (not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", cfg["HOST"])
            or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", cfg["USER"])
            or not cfg["PORT"].isdigit() or not 1 <= int(cfg["PORT"]) <= 65535
            or not ABS_PATH.fullmatch(cfg["REMOTE_DIR"]) or ".." in cfg["REMOTE_DIR"].split("/")
            or not ABS_PATH.fullmatch(cfg["IDENTITY_FILE"]) or ".." in cfg["IDENTITY_FILE"].split("/")
            or not PIN.fullmatch(cfg["HOSTKEY_SHA256"])):
        return None
    return cfg


def config_checks(*, file: Path = CONF, owner_uid: int = 0, stop: Path = Path("/")) -> tuple[str, str, str]:
    state = private_regular(file, owner_uid=owner_uid, stop=stop)
    if state != "PRIVATE":
        return state, "UNKNOWN", "UNKNOWN"
    try:
        fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != owner_uid or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 4096:
                return "UNSAFE_FILE", "UNKNOWN", "UNKNOWN"
            raw = os.read(fd, 4097).decode("ascii", errors="strict")
        finally:
            os.close(fd)
    except (OSError, UnicodeError):
        return "UNSAFE_FILE", "UNKNOWN", "UNKNOWN"
    cfg = parse_config(raw)
    if cfg is None:
        return "INVALID_CONFIG", "UNKNOWN", "UNKNOWN"
    key_state = private_regular(Path(cfg["IDENTITY_FILE"]), owner_uid=owner_uid, stop=stop)
    return "PRIVATE_VALID", key_state, "PIN_FORMAT_VALID"


def inspect(show=show_property, journal=journal_for_invocation,
            config=config_checks) -> dict[str, str]:
    values = {k: show(k) for k in PROPERTIES}
    status = values["ExecMainStatus"]
    result = values["Result"]
    command = values["ExecStart"]
    user = values["User"]
    # A textual ExecStart match does NOT attest its executable or unit hashes.
    command_kind = "REFERENCE_ONLY" if (command is not None and "offsite" in command.lower()) else "UNKNOWN"
    scope = "UNAVAILABLE"
    category = "UNCLASSIFIED"
    auth_subclass = "NOT_APPLICABLE"
    if status == "255" and result == "exit-code" and values["InvocationID"] and INVOCATION.fullmatch(values["InvocationID"]):
        log = journal(values["InvocationID"])
        if log is not None:
            scope = "EXACT_INVOCATION"
            category = classify(log)
            if category == "SSH_AUTH_KEY_REJECTED":
                auth_subclass = classify_auth_subclass(log)
    try:
        conf, identity, pin = config()
    except (OSError, ValueError):
        conf, identity, pin = "UNVERIFIED", "UNKNOWN", "UNKNOWN"
    load = values["LoadState"]
    return {
        "schema": "kmj.a2.ssh255.readonly.v1",
        "unit": UNIT,
        "unit_load": load if load is not None and FINGERPRINT.fullmatch(load) else "UNKNOWN",
        "exit_255": "YES" if status == "255" and result == "exit-code" else "NOT_PROVEN",
        "systemd_user": "ROOT" if user in ("", "root") else "NONROOT_OR_UNKNOWN",
        "execstart_reference": command_kind,
        "execstart_hash_attested": "NO",
        "journal_scope": scope,
        "journal_failure_class": category,
        "journal_auth_subclass": auth_subclass,
        "sftp_config": conf,
        "sftp_identity": identity,
        "hostkey_pin": pin,
        "backup_created": "NOT_VERIFIED",
        "restore_verified": "NO",
        "production_changed": "NO_THIS_SCRIPT_IS_READ_ONLY",
        "raw_values_emitted": "NO",
    }


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "KMJ-elite":
        print("A2_DIAGNOSTIC=BLOCKED_HOST_ROOT_OR_ARGUMENTS")
        return 2
    for key, value in inspect().items():
        print(f"{key}={value}")
    print("A2_DIAGNOSTIC=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
