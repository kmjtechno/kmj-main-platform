#!/usr/bin/env python3
"""Root-only, read-only attestor for one exact successful KMJ-elite V3 run.

Verifies installed immutable V3 + DNS transport SHA256, exact unit/drop-in/
timer, current successful unit invocation, 48h monotonic recency and 9 journal
markers. No raw journal, IPs, keys, paths, identifiers, sizes or hashes printed.
Does not authenticate to the remote receiver, open DB, write files, run backups,
change services, or approve the platform release. Not a physical restore.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

UNIT="kmj-elite-offsite-backup.service"
TIMER="kmj-elite-offsite-backup.timer"
V3=Path("/usr/local/libexec/kmj-offsite-fresh-x25519-v3-20261112.py")
PARENT=Path("/usr/local/libexec/KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py")
DROPIN=Path("/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf")
V3_SHA="2834ff3361027536bee0b971fae6dddb00677460f15adf3e8d81e7821853016f"
PARENT_SHA="8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c"
UNIT_CONTENT=("[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -B "+
              str(V3)+" --scheduled-run\nTimeoutStartSec=1800s\nUMask=0077\n").encode("ascii")
SERVICE_FIELDS=("Id","LoadState","Type","User","ActiveState","Result","ExecMainStatus",
                "InvocationID","ExecMainExitTimestampMonotonic","ExecStart","DropInPaths")
TIMER_FIELDS=("Id","LoadState","ActiveState","UnitFileState","Unit")
NEEDED=(
 "FRESH_PGDMP=PASS","RESOLVED_STORAGE_BACKUP=PASS","SOURCE_MANIFEST=PASS",
 "NEW_X25519_CIPHER=PASS","OFFSITE_TRANSFER=PASS","SHA256_READBACK=PASS",
 "REMOTE_SFTP_SHA_READBACK=PASS","SFTP_HOSTKEY=PIN_MATCH",
 "RESULT=FRESH_PGDUMP_X25519_GOOGLE_TRANSFER_PASS")
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","HOME":"/root"}
MAX_OUTPUT=262144
class Block(Exception):pass

def cmd(argv,limit=32768,timeout=15):
    try:
        result=subprocess.run(argv,cwd="/",env=ENV,stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                     timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise Block("FIXED_READONLY_COMMAND_UNAVAILABLE") from None
    if result.returncode!=0 or len(result.stdout)>limit:
        raise Block("FIXED_READONLY_COMMAND_FAILED")
    return result.stdout

def safe_source(path,expected,mode,cap=131072):
    for dirname in ("/usr","/usr/local","/usr/local/libexec") if path.parent==V3.parent else (
                     "/etc","/etc/systemd","/etc/systemd/system",str(DROPIN.parent)):
        meta=os.lstat(dirname)
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=0 or meta.st_mode&0o022:
            raise Block("PROTECTED_PARENT_CHANGED")
    a=os.lstat(path)
    if (not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1
        or stat.S_IMODE(a.st_mode)!=mode or not 10<=a.st_size<=cap):
        raise Block("IMMUTABLE_FILE_METADATA_CHANGED")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        first=os.fstat(fd)
        raw=os.read(fd,cap+1)
        last=os.fstat(fd)
    finally:os.close(fd)
    keys=("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")
    if any(getattr(a,k)!=getattr(first,k) or getattr(first,k)!=getattr(last,k) for k in keys):
        raise Block("IMMUTABLE_FILE_RACE")
    if len(raw)!=a.st_size:
        raise Block("IMMUTABLE_FILE_SIZE_CHANGED")
    if expected is not None and hashlib.sha256(raw).hexdigest()!=expected:
        raise Block("INSTALLED_SHA_MISMATCH")
    return raw

def props(unit,keys):
    argv=["/usr/bin/systemctl","show","--no-pager","--property="+",".join(keys),unit]
    output=cmd(argv,limit=12000).decode("ascii","strict")
    result={}
    for row in output.splitlines():
        name,sep,value=row.partition("=")
        if not sep or name not in keys or name in result or len(value)>8192:
            raise Block("SYSTEMD_PROPERTY_FORMAT")
        result[name]=value
    if set(result)!=set(keys) or result["Id"]!=unit:
        raise Block("SYSTEMD_PROPERTY_IDENTITY")
    return result

def service_contract():
    u=props(UNIT,SERVICE_FIELDS)
    t=props(TIMER,TIMER_FIELDS)
    exact="argv[]=/usr/bin/python3 -I -B "+str(V3)+" --scheduled-run"
    if (u["LoadState"]!="loaded" or u["Type"]!="oneshot" or
        u["User"] not in ("","root") or u["ActiveState"]!="inactive" or
        u["Result"]!="success" or u["ExecMainStatus"]!="0" or
        u["DropInPaths"]!=str(DROPIN) or
        u["ExecStart"].count(exact)!=1 or
        len(re.findall(r"\bpath=([^ ;]+)",u["ExecStart"]))!=1 or
        "path=/usr/bin/python3" not in u["ExecStart"]):
        raise Block("LAST_SUCCESSFUL_V3_UNIT_UNVERIFIED")
    if (t["LoadState"]!="loaded" or t["ActiveState"]!="active" or
        t["UnitFileState"]!="enabled" or t["Unit"]!=UNIT):
        raise Block("V3_SCHEDULED_TIMER_UNVERIFIED")
    if safe_source(DROPIN,None,0o644,2048)!=UNIT_CONTENT:
        raise Block("V3_DROPIN_BYTES_MISMATCH")
    safe_source(V3,V3_SHA,0o600)
    safe_source(PARENT,PARENT_SHA,0o600)
    invocation=u["InvocationID"]
    if not re.fullmatch(r"[a-fA-F0-9]{32}",invocation) or invocation=="0"*32:
        raise Block("INVOCATION_ID_UNAVAILABLE")
    stamp=u["ExecMainExitTimestampMonotonic"]
    if not re.fullmatch(r"[0-9]{1,20}",stamp):
        raise Block("MONOTONIC_EXIT_TIMESTAMP_UNVERIFIED")
    age_us=time.monotonic_ns()//1000-int(stamp)
    if not 0<=age_us<=48*3600*1000000:
        raise Block("EXIT_OUTSIDE_48_HOURS")
    return invocation,age_us//60000000

def receipt_rows(raw):
    if len(raw)>MAX_OUTPUT:raise Block("JOURNAL_BYTES_EXCEEDED")
    try:
        data=raw.decode("utf8","strict").splitlines()
    except UnicodeError:
        raise Block("JOURNAL_ENCODING_UNVERIFIED") from None
    if len(data)>350:
        raise Block("JOURNAL_LINES_EXCEEDED")
    rows=set(data)
    required=set(NEEDED)
    found=sum(item in rows for item in NEEDED)
    if found!=len(NEEDED):
        raise Block("EXACT_INVOCATION_RECEIPT_INCOMPLETE")
    sha=[s for s in rows if re.fullmatch(r"CIPHER_SHA256_UPPER=[A-F0-9]{64}",s)]
    sizes=[s for s in rows if re.fullmatch(r"CIPHER_BYTES=[0-9]{1,15}",s)]
    if len(sha)!=1 or len(sizes)!=1 or int(sizes[0].split("=")[1])<128:
        raise Block("CIPHER_RECEIPT_SHAPE_UNVERIFIED")
    # The receipt attests V3's previous remote SFTP SHA readback, not a fresh
    # independent download and not independent physical PostgreSQL restore.
    return found

def main(args):
    if args!=["--inspect"]:
        print("KMJ_V3_SUCCESS_ATTESTOR=BLOCKED_ARGUMENTS")
        return 2
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        print("KMJ_V3_SUCCESS_ATTESTOR=BLOCKED_ROOT_ELITE_ONLY")
        return 2
    try:
        invocation,age=service_contract()
        journal=cmd(["/usr/bin/journalctl","--no-pager","-o","cat","-n","350",
                     "_SYSTEMD_INVOCATION_ID="+invocation],limit=MAX_OUTPUT,timeout=20)
        count=receipt_rows(journal)
    except (Block,OSError,UnicodeError) as exc:
        reason=str(exc) if isinstance(exc,Block) else "PROTECTED_RUNTIME_ERROR"
        if not re.fullmatch(r"[A-Z0-9_]{3,70}",reason):reason="UNCLASSIFIED"
        print("KMJ_V3_SUCCESS_ATTESTOR=BLOCKED_"+reason)
        print("PRODUCTION_APPROVAL=UNCHANGED")
        return 3
    print("KMJ_V3_SUCCESS_ATTESTOR=READ_ONLY_PASS")
    print("INSTALLED_V3_SOURCE_SHA=PASS")
    print("INSTALLED_DNS_TRANSPORT_SHA=PASS")
    print("EXACT_SUCCESSFUL_UNIT=PASS")
    print("SCHEDULED_TIMER=PASS")
    print("LAST_EXIT_AGE_MINUTES="+str(age))
    print("EXACT_INVOCATION_MARKERS="+str(count)+"/"+str(len(NEEDED)))
    print("V3_SFTP_REMOTE_READBACK_JOURNAL=PASS")
    print("FRESH_REMOTE_FETCH_IN_THIS_ATTESTOR=NO")
    print("INDEPENDENT_REMOTE_RESTORE=NOT_VERIFIED")
    print("P520_PHYSICAL_RESTORE=NOT_VERIFIED")
    print("PRODUCTION_RELEASE=UNCHANGED")
    print("SYSTEMD_DB_SFTP_MUTATION=NONE")
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))
