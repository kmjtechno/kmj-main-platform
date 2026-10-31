#!/usr/bin/env python3
"""A2b: fixed, read-only comparison of the identity the offsite-backup SERVICE really uses.

Answers one question without any authentication attempt: does the effective systemd ExecStart
(unit file + drop-ins) run a root-protected executable that reads the root-only SFTP config, and does the
config IdentityFile have a PUBLIC fingerprint on the owner-maintained allowlist of keys authorized at Google?

Requires root on KMJ-elite. No arguments, no network, no writes, no service start, no key rotation.
Emits only enums, booleans, the executable sha256 and PUBLIC key fingerprints. Never emits paths, hosts,
users, private key material, environment, unit text or journal text. Diagnostic only: it attests no backup,
restore or release.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "kmj-elite-offsite-backup.service"
CONF = Path("/etc/kmj-codebridge/offsite-sftp.conf")
ALLOW = Path("/etc/kmj-codebridge/offsite-authorized-fingerprints")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
FP = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
ABS = re.compile(r"/[A-Za-z0-9._/@+-]{1,240}\Z")
MAX_EXEC = 1 << 20


def sh(argv, *, stdin: bytes | None = None, timeout=8) -> str | None:
    try:
        p = subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout, check=False, env=ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode or len(p.stdout) > 65536:
        return None
    try:
        return p.stdout.decode("utf-8", "strict")
    except UnicodeError:
        return None


def prop(name: str) -> str | None:
    out = sh(["/usr/bin/systemctl", "show", UNIT, f"--property={name}", "--value", "--no-pager"])
    return None if out is None else out.strip()


def protected_chain(path: Path, *, uid: int = 0, stop: Path = Path("/")) -> bool:
    cur = path.parent
    while True:
        try:
            st = os.lstat(cur)
        except OSError:
            return False
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o022:
            return False
        if cur == stop or cur.parent == cur:
            return True
        cur = cur.parent


def read_protected(path: Path, *, uid: int = 0, maxsize: int, private: bool, stop: Path = Path("/")) -> bytes | None:
    """Open one root-owned regular file via a single no-follow descriptor; None on any doubt."""
    if not path.is_absolute() or ".." in path.parts or not protected_chain(path, uid=uid, stop=stop):
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        bad = st.st_mode & (0o077 if private else 0o022)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1 or bad or st.st_size > maxsize:
            return None
        data = os.read(fd, maxsize + 1)
        return data if len(data) <= maxsize else None
    finally:
        os.close(fd)


def exec_path(execstart: str | None) -> Path | None:
    """First `path=` of systemd's ExecStart rendering, but only when exactly ONE command exists."""
    if not execstart or execstart.count("path=") != 1:
        return None
    m = re.search(r"path=(\S+)", execstart)
    if not m or not ABS.fullmatch(m.group(1)) or ".." in m.group(1).split("/"):
        return None
    return Path(m.group(1))


def conf_identity(raw: bytes | None) -> Path | None:
    if raw is None:
        return None
    found = None
    for line in raw.decode("ascii", "replace").splitlines():
        if line.startswith("IDENTITY_FILE="):
            if found is not None:
                return None
            v = line.split("=", 1)[1]
            if not ABS.fullmatch(v) or ".." in v.split("/"):
                return None
            found = Path(v)
    return found


def public_fingerprint(key: Path, *, run=sh) -> str | None:
    """Derive the PUBLIC fingerprint from a private key file without a passphrase prompt or key output."""
    pub = run(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(key)], stdin=b"")
    if not pub:
        return None
    out = run(["/usr/bin/ssh-keygen", "-l", "-E", "sha256", "-f", "-"], stdin=pub.encode())
    m = re.match(r"\d+ (SHA256:[A-Za-z0-9+/]{43}) ", out or "")
    return m.group(1) if m else None


def allowlist(raw: bytes | None) -> set[str] | None:
    if raw is None:
        return None
    out = set()
    for line in raw.decode("ascii", "replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if not FP.fullmatch(line):
                return None
            out.add(line)
    return out or None


def compare(*, show=prop, reader=read_protected, fingerprint=public_fingerprint, conf=CONF, allow=ALLOW) -> dict[str, str]:
    r = {"schema": "kmj.a2.unit-identity.readonly.v1", "unit": UNIT}
    load = show("LoadState")
    dropins = show("DropInPaths")
    r["unit_loaded"] = "YES" if load == "loaded" else "NO"
    r["dropins_present"] = "UNKNOWN" if dropins is None else ("YES" if dropins else "NO")
    exe = exec_path(show("ExecStart"))
    r["single_execstart"] = "YES" if exe else "NO_OR_AMBIGUOUS"
    body = reader(exe, maxsize=MAX_EXEC, private=False) if exe else None
    r["executable_protected"] = "YES" if body is not None else "NO_OR_UNKNOWN"
    r["executable_sha256"] = hashlib.sha256(body).hexdigest() if body is not None else "UNKNOWN"
    # Does the executable consult the root-only config (not an embedded/other key)?
    uses_conf = body is not None and str(conf).encode() in body
    r["executable_reads_sftp_config"] = "YES" if uses_conf else ("NO" if body is not None else "UNKNOWN")
    embedded = body is not None and re.search(rb"(?:^|\s)-i\s+/|IdentityFile\s+/|id_(?:rsa|ed25519|ecdsa)", body) is not None
    r["executable_embeds_other_identity"] = "YES" if embedded else ("NO" if body is not None else "UNKNOWN")
    key = conf_identity(reader(conf, maxsize=4096, private=True))
    r["config_identity_present"] = "YES" if key else "NO_OR_INVALID"
    keybytes = reader(key, maxsize=8192, private=True) if key else None
    r["config_identity_protected"] = "YES" if keybytes is not None else "NO_OR_UNKNOWN"
    fp = fingerprint(key) if keybytes is not None else None
    r["config_identity_fingerprint"] = fp or "UNREADABLE_OR_ENCRYPTED"
    allowed = allowlist(reader(allow, maxsize=4096, private=False))
    if allowed is None:
        r["authorized_fingerprint_match"] = "UNKNOWN_NO_OWNER_ALLOWLIST"
    elif fp is None:
        r["authorized_fingerprint_match"] = "UNKNOWN"
    else:
        r["authorized_fingerprint_match"] = "YES" if fp in allowed else "NO"
    clean = (r["single_execstart"] == "YES" and r["executable_protected"] == "YES"
             and r["executable_reads_sftp_config"] == "YES" and r["executable_embeds_other_identity"] == "NO"
             and r["dropins_present"] == "NO")
    r["service_identity_source"] = "SFTP_CONFIG_ONLY" if clean else "NOT_PROVEN"
    r["repair_precondition_met"] = "YES" if clean and r["authorized_fingerprint_match"] == "NO" else "NO"
    r["backup_created"] = "NOT_VERIFIED"
    r["restore_verified"] = "NO"
    r["mutations"] = "NONE"
    r["raw_values_emitted"] = "NO"
    return r


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "KMJ-elite":
        print("A2B_COMPARE=BLOCKED_HOST_ROOT_OR_ARGUMENTS")
        return 2
    for k, v in compare().items():
        print(f"{k}={v}")
    print("A2B_COMPARE=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
