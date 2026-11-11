#!/usr/bin/python3
"""Owner-only redacted legacy offsite recipe inspection, no mutation or remote connection."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

SOURCE = Path("/usr/local/sbin/kmj-elite-offsite-backup")
EXPECTED = "d66fd2c2cc33c53c1d0a82f1c259640ee642b666feb2c4aaee6cf887dfe98848"
UNIT = "kmj-elite-offsite-backup.service"
VERBS = ("pg_dump", "pg_basebackup", "tar", "age", "rsync", "ssh", "sftp", "rclone",
         "sha256sum", "scp", "openssl", "gpg", "zstd", "gzip", "find", "cp", "mv")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C", "LC_ALL": "C"}

class Blocked(Exception):
    pass

def root_regular_file(path: Path) -> bytes:
    d = path.parent
    while True:
        meta = os.lstat(d)
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise Blocked("UNSAFE_PARENT")
        if d == Path("/"):
            break
        d = d.parent
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | getattr(os,"O_CLOEXEC",0))
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0
            or before.st_mode & 0o022 or before.st_nlink != 1
            or not 1 <= before.st_size <= 1048576):
            raise Blocked("UNSAFE_SOURCE")
        data = os.read(fd,1048577)
        after = os.fstat(fd)
        if len(data) != before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise Blocked("SOURCE_CHANGED")
        if hashlib.sha256(data).hexdigest() != EXPECTED:
            raise Blocked("SOURCE_HASH_MISMATCH")
        return data
    finally:
        os.close(fd)

def prop(key):
    if key not in {"User","ExecStart","DropInPaths","Result","ExecMainStatus"}:
        raise Blocked("UNAPPROVED_PROPERTY")
    try:
        p = subprocess.run(["/usr/bin/systemctl","show",UNIT,f"--property={key}","--value","--no-pager"],
                           stdin=subprocess.DEVNULL,capture_output=True,timeout=8,env=ENV,cwd="/",check=False)
    except (OSError,subprocess.TimeoutExpired):
        return None
    return p.stdout.decode("utf-8","replace").strip() if p.returncode == 0 and len(p.stdout) <= 8192 else None

def static_scan(data):
    # Static source-word hints only: not parsed shell execution evidence.
    lines = []
    for number,line in enumerate(data.decode("utf-8","replace").splitlines(),1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        found = [verb for verb in VERBS if re.search(
            r"(?<![A-Za-z0-9_-])" + re.escape(verb) + r"(?=[ \t;|)\"']|$)",stripped)]
        if found:
            lines.append((number,found,stripped))
    if len(lines) > 120:
        raise Blocked("PIPELINE_SCAN_TOO_LARGE")
    seq = ",".join(str(n)+":"+"+".join(v) for n,v,_ in lines[:35]) or "NONE"
    if len(seq) > 1500:
        raise Blocked("PIPELINE_SEQUENCE_TOO_LONG")
    print("PIPELINE_STATIC_VERB_SEQUENCE="+seq)
    for verb in VERBS:
        print("REFERENCES_"+verb.upper()+"="+("YES" if any(verb in verbs for _,verbs,_ in lines) else "NO"))
    rsync = [raw for _,verbs,raw in lines if "rsync" in verbs]
    print("RSYNC_MATCHING_LINES="+str(len(rsync)))
    print("RSYNC_HAS_DELETE_FLAG="+("YES" if any(re.search(r"(^|[ \t])--delete([ =]|$)",r) for r in rsync) else "NO"))
    print("RSYNC_AGE_SUFFIX_LITERAL="+("YES" if any(".age" in r for r in rsync) else "NOT_SEEN"))
    print("AGE_VAULT_LITERAL="+("YES" if b"/var/backups/kmj-elite-offsite-encrypted" in data else "NOT_SEEN"))
    print("STATIC_SOURCE_HINTS_ARE_EXECUTION_PROOF=NO")
    print("RSYNC_REQUIRES_UNRESTRICTED_REMOTE_SERVER=YES")
    print("REPLACE_LEGACY_SERVICE_AUTOMATICALLY=NO")

def main():
    if len(sys.argv) != 1 or os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        print("LEGACY_RECIPE=BLOCKED_HOST_ROOT_OR_ARGUMENTS")
        return 2
    try:
        data = root_regular_file(SOURCE)
        exe=prop("ExecStart")
        found=re.findall(r"\bpath=([^\s;]+)",exe or "")
        if len(found)!=1 or found[0]!=str(SOURCE):
            raise Blocked("UNEXPECTED_UNIT_EXEC")
        print("LEGACY_EXECSTART_HASH=PASS")
        print("LEGACY_SYSTEMD_USER="+("ROOT" if prop("User") in ("","root") else "UNKNOWN_OR_OTHER"))
        drops=prop("DropInPaths")
        print("LEGACY_DROPINS="+("ABSENT" if drops=="" else ("PRESENT" if drops else "UNKNOWN")))
        print("LEGACY_255_STILL_RECORDED="+("YES" if prop("ExecMainStatus")=="255" and prop("Result")=="exit-code" else "NO_OR_UNKNOWN"))
        static_scan(data)
    except (Blocked,OSError,ValueError,UnicodeError):
        print("LEGACY_RECIPE=BLOCKED_PROTECTED_SOURCE_OR_STATE")
        return 3
    print("LEGACY_RECIPE=READ_ONLY_COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
