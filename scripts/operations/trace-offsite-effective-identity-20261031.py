#!/usr/bin/env python3
"""A2c: fixed, read-only trace of the SSH identity candidates the offsite-backup service could really use.

Context: the owner-run A2b showed the unit's single protected ExecStart does NOT reference offsite-sftp.conf and
embeds no `-i`/IdentityFile. So the identity must come from elsewhere (the unit user's ~/.ssh defaults, an ssh_config,
an env file, or another path referenced inside the executable). This enumerates those candidates WITHOUT
authenticating: no network, no `ssh -G`, no writes, no args, no rotation, no TOFU.

Output: enums, counts, 12-hex path ids (sha256 of the path), env KEY NAMES from a fixed allowlist, and PUBLIC key
fingerprints. Never paths, values, hosts, users, key material or journal text. Remote authorization stays NO: a local
fingerprint cannot prove the remote side accepts the key.
"""
from __future__ import annotations

import hashlib
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "kmj-elite-offsite-backup.service"
ALLOW = Path("/etc/kmj-codebridge/offsite-authorized-fingerprints")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
PROPS = ("User", "EnvironmentFiles", "WorkingDirectory", "ExecStart", "DropInPaths")
TOOLS = (b"ssh", b"sftp", b"scp", b"rsync", b"rclone", b"curl", b"gsutil", b"gcloud", b"aws", b"restic", b"borg", b"sshpass", b"lftp")
ENV_NAMES = frozenset(("SSH_KEY", "SSH_IDENTITY", "IDENTITY_FILE", "SSH_KEY_FILE", "SFTP_KEY", "OFFSITE_KEY", "RCLONE_CONFIG", "SSH_CONFIG", "OFFSITE_HOST"))
FP = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
ABS = re.compile(rb"/(?:etc|root|home|var|opt|usr/local|srv|run)/[A-Za-z0-9._/@+-]{1,200}")
MAX_BODY, MAX_SMALL, MAX_PATHS = 1 << 20, 16384, 64


def sh(argv, stdin=None, timeout=8):
    try:
        p = subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout, check=False, env=ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 and len(p.stdout) <= 65536 else None


def prop(name):
    out = sh(["/usr/bin/systemctl", "show", UNIT, f"--property={name}", "--value", "--no-pager"])
    return None if out is None else out.strip()


def pid(path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:12]


def fingerprint(key: Path, run=sh):
    pub = run(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(key)], b"")
    out = run(["/usr/bin/ssh-keygen", "-l", "-E", "sha256", "-f", "-"], pub.encode()) if pub else None
    m = re.match(r"\d+ (SHA256:[A-Za-z0-9+/]{43}) ", out or "")
    return m.group(1) if m else None


def read_small(path: Path, uid_ok=(0,), limit=MAX_SMALL):
    """(kind, bytes|None): no-follow single descriptor; owner must be root (or the unit user); never group/other writable."""
    try:
        st0 = os.lstat(path)
    except FileNotFoundError:
        return "MISSING", None
    except OSError:
        return "UNREADABLE", None
    if stat.S_ISLNK(st0.st_mode):
        return "SYMLINK", None
    if stat.S_ISDIR(st0.st_mode):
        return "DIR", None
    if not stat.S_ISREG(st0.st_mode):
        return "SPECIAL", None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return "UNREADABLE", None
    try:
        st = os.fstat(fd)
        if (st.st_ino, st.st_dev) != (st0.st_ino, st0.st_dev) or st.st_nlink != 1:
            return "RACE_OR_HARDLINK", None
        if st.st_uid not in uid_ok or st.st_mode & 0o022:
            return "UNTRUSTED_OWNER_OR_MODE", None
        if st.st_size > limit:
            return "TOO_LARGE", None
        return "FILE", os.read(fd, limit)
    finally:
        os.close(fd)


def classify(path: Path, uid_ok, run=sh):
    """Describe one referenced file as a candidate; reveals only enums, key NAMES and public fingerprints."""
    kind, data = read_small(path, uid_ok)
    row = {"id": pid(path), "kind": kind, "role": "NONE", "fps": [], "env_keys": []}
    if data is None:
        return row
    if b"PRIVATE KEY" in data[:200]:
        fp = fingerprint(path, run)
        row.update(role="PRIVATE_KEY", fps=[fp] if fp else [], kind="FILE" if fp else "KEY_ENCRYPTED_OR_INVALID")
        return row
    text = data.decode("utf-8", "replace")
    idents = re.findall(r"(?im)^\s*IdentityFile\s+(\S+)", text)
    if idents:
        row["role"] = "SSH_CONFIG"
        for i in idents[:8]:
            i = i.replace("~", str(Path(path).parent.parent), 1) if i.startswith("~") else i
            if i.startswith("/") and ".." not in i.split("/"):
                fp = fingerprint(Path(i), run)
                if fp:
                    row["fps"].append(fp)
        return row
    keys = [m.group(1) for m in re.finditer(r"(?m)^\s*(?:export\s+)?([A-Z][A-Z0-9_]{1,40})=", text)]
    hit = sorted(set(keys) & ENV_NAMES)
    if hit:
        row.update(role="ENV_WITH_KEY_REF", env_keys=hit)
    return row


def trace(show=prop, read_body=None, classify_fn=classify, home_of=lambda u: pwd.getpwnam(u).pw_dir, allow_raw=None):
    r = {"schema": "kmj.a2c.effective-identity.readonly.v1", "unit": UNIT}
    user = show("User") or "root"
    r["unit_user"] = "ROOT" if user == "root" else "NONROOT"
    r["dropins_present"] = "YES" if show("DropInPaths") else "NO"
    es = show("ExecStart") or ""
    m = re.search(r"path=(/[A-Za-z0-9._/@+-]{1,240})", es) if es.count("path=") == 1 else None
    exe = Path(m.group(1)) if m else None
    kind, body = (read_body or (lambda p: read_small(p, (0,), MAX_BODY)))(exe) if exe else ("NO_SINGLE_EXECSTART", None)
    r["executable"] = kind
    uid_ok = (0,)
    cands, tools, extra = [], [], []
    if body is not None:
        tools = sorted(t.decode() for t in TOOLS if re.search(rb"(?<![A-Za-z0-9_-])" + t + rb"(?![A-Za-z0-9_-])", body))
        paths = sorted({p.decode() for p in ABS.findall(body)})[:MAX_PATHS]
        extra = [Path(p) for p in paths]
    r["tools_referenced"] = ",".join(tools) or "NONE"
    r["referenced_paths_scanned"] = str(len(extra))
    # Default OpenSSH identity locations of the unit user are candidates even though the script names none.
    try:
        home = Path(home_of(user))
    except (KeyError, OSError):
        home = None
    r["unit_home_resolved"] = "YES" if home else "NO"
    defaults = [home / ".ssh" / n for n in ("id_ed25519", "id_ecdsa", "id_rsa", "config")] if home else []
    envfiles = [Path(p) for p in re.findall(r"path=(/[A-Za-z0-9._/@+-]{1,240})", show("EnvironmentFiles") or "") if "-" not in p[:1]]
    for p in dict.fromkeys(extra + defaults + envfiles):
        row = classify_fn(p, (0,) if user == "root" else (0, 0))
        if row["role"] != "NONE" or row["kind"] in ("SYMLINK", "UNTRUSTED_OWNER_OR_MODE", "RACE_OR_HARDLINK"):
            cands.append(row)
    fps = sorted({f for c in cands for f in c["fps"]})
    r["candidate_files"] = str(len(cands))
    for i, c in enumerate(cands[:12]):
        r[f"candidate_{i}"] = f"id={c['id']} role={c['role']} kind={c['kind']} keys={'+'.join(c['env_keys']) or '-'} fps={'+'.join(c['fps']) or '-'}"
    r["candidate_fingerprints"] = ",".join(fps) or "NONE"
    allowed = None
    if allow_raw:
        lines = [l.strip() for l in allow_raw.decode("ascii", "replace").splitlines() if l.strip() and not l.startswith("#")]
        allowed = set(lines) if lines and all(FP.fullmatch(l) for l in lines) else None
    r["authorized_overlap"] = "UNKNOWN_NO_OWNER_ALLOWLIST" if allowed is None else ("YES" if allowed & set(fps) else "NO")
    r["effective_identity"] = ("SINGLE_CANDIDATE_UNPROVEN" if len(fps) == 1 and r["dropins_present"] == "NO" and r["executable"] == "FILE"
                               else "NONE_FOUND" if not fps else "AMBIGUOUS_OR_UNPROVEN")
    r["remote_auth_witnessed"] = "NO"
    r["repair_allowed"] = "NO"
    r["backup_created"] = "NOT_VERIFIED"
    r["restore_verified"] = "NO"
    r["mutations"] = "NONE"
    r["raw_values_emitted"] = "NO"
    return r


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "KMJ-elite":
        print("A2C_TRACE=BLOCKED_HOST_ROOT_OR_ARGUMENTS")
        return 2
    kind, raw = read_small(ALLOW, (0,), 4096)
    for k, v in trace(allow_raw=raw).items():
        print(f"{k}={v}")
    print("A2C_TRACE=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
