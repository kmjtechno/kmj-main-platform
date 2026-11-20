#!/usr/bin/env python3
"""Read-only exact-invocation offsite phase+public hostkey check (no SSH auth).

Does not execute an offsite backup, load secrets, use an SSH client identity,
touch a production service, or publish any raw journal, DNS IP, key or path.
Only the exact expected V2/V3 source hash may authorize the bounded public
ssh-keyscan (which is not proof of SFTP login or successful backup).
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

UNIT="kmj-elite-offsite-backup.service"
DROPIN="/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf"
SRC={
 "V2":("/usr/local/libexec/kmj-offsite-fresh-x25519-v2-20261112.py",
       "fb6ec4a4c5f0189562d35141765dcfcea84bc1cec3d8f4b79362e33d884b281e"),
 "V3":("/usr/local/libexec/kmj-offsite-fresh-x25519-v3-20261112.py",
       "2834ff3361027536bee0b971fae6dddb00677460f15adf3e8d81e7821853016f"),
}
PUBLIC_HOST="offsite.kmjtechno.com"
HOSTKEY_PIN="SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","HOME":"/root"}
KEYS=("Id","LoadState","ActiveState","Result","ExecMainStatus","InvocationID","ExecStart","DropInPaths")
MAX=131072
INV=re.compile(r"[0-9a-fA-F]{32}\Z")

def call(args,timeout=12):
    p=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL,cwd="/",env=ENV,
                     timeout=timeout,check=False)
    if len(p.stdout)>MAX:raise ValueError("CAPTURE_TOO_LARGE")
    return p.returncode,p.stdout

def snapshot(raw):
    result={}
    for line in raw.decode("utf8","replace").splitlines():
        k,eq,v=line.partition("=")
        if not eq or k not in KEYS or k in result or len(v)>8192:
            raise ValueError("BAD_UNIT_META")
        result[k]=v
    if (set(result)!=set(KEYS) or result["Id"]!=UNIT or
        result["LoadState"]!="loaded" or result["ActiveState"]!="failed" or
        result["Result"]!="exit-code" or result["ExecMainStatus"]!="3" or
        not INV.fullmatch(result["InvocationID"]) or
        result["InvocationID"].lower()=="0"*32):
        raise ValueError("EXIT3_UNIT_UNVERIFIED")
    return result

def phase(log):
    if len(log)>MAX:raise ValueError("JOURNAL_OVERSIZE")
    lines=set(log.decode("utf8","replace").splitlines())
    schemas=[v for v in SRC if
      "SCHEMA=KMJ_OFFSITE_FRESH_PGDUMP_X25519_GOOGLE_SFTP_"+v in lines]
    if len(schemas)!=1:return "OTHER","SCHEMA_NOT_MATCHED"
    v=schemas[0]
    if "RESULT=BLOCKED_SAFE" not in lines:return v,"BLOCKED_SAFE_NOT_OBSERVED"
    if "RESULT=INSPECT_PASS" not in lines:return v,"PREFLIGHT_NOT_COMPLETE"
    if "SFTP_HOSTKEY=PIN_MATCH" in lines:return v,"AFTER_HOSTKEY"
    return v,"AFTER_PREFLIGHT_BEFORE_HOSTKEY_PASS"

def attest_source(meta,version):
    if version not in SRC:return "NO_REVIEWED_VERSION"
    path,pin=SRC[version]
    raw=meta.get("ExecStart","")
    expect="/usr/bin/python3 -I -B "+path+" --scheduled-run"
    match=re.search(r"\bargv\[\]=([^;]+)",raw)
    executable=re.search(r"\bpath=([^ ;]+)",raw)
    if (meta.get("DropInPaths")!=DROPIN or not match or
        match.group(1).strip()!=expect or
        not executable or executable.group(1)!="/usr/bin/python3"):
        return "EXECSTART_OR_DROPIN_MISMATCH"
    try:
        s=os.lstat(path)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or
            s.st_nlink!=1 or s.st_mode&0o022 or not 1024<=s.st_size<=65536):
            return "SOURCE_FILE_UNTRUSTED"
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            before=os.fstat(fd)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns):
                return "SOURCE_FILE_UNTRUSTED"
            data=os.read(fd,65537)
            after=os.fstat(fd)
            if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns):
                return "SOURCE_FILE_UNTRUSTED"
        finally:
            os.close(fd)
        if len(data)!=s.st_size or hashlib.sha256(data).hexdigest()!=pin:
            return "SOURCE_SHA_MISMATCH"
    except (OSError,ValueError):
        return "SOURCE_FILE_UNREADABLE"
    return "EXACT_SOURCE_SHA_PASS"

def probe():
    # Unauthenticated public SSH hostkey scan only: no SFTP, secrets, upload,
    # payment, remote modification, or customer-data network transfer.
    try:
        addresses=socket.getaddrinfo(PUBLIC_HOST,22,family=socket.AF_INET,
                                     type=socket.SOCK_STREAM)
        unique={row[4][0] for row in addresses if row[0]==socket.AF_INET}
        if len(unique)!=1:return "DNS_UNIQUE_IPV4_NOT_PROVEN"
        packed=socket.inet_aton(next(iter(unique)))
        if (len(packed)!=4 or packed[0] in (0,10,127) or packed[0]>=224 or
            (packed[0]==169 and packed[1]==254) or
            (packed[0]==192 and packed[1]==168) or
            (packed[0]==172 and 16<=packed[1]<=31) or
            (packed[0]==100 and 64<=packed[1]<=127)):
            return "DNS_ADDRESS_UNSAFE"
    except (OSError,IndexError):
        return "DNS_RESOLUTION_FAILED"
    try:
        rc,body=call(["/usr/bin/ssh-keyscan","-T","12","-t","ed25519",
                      "-p","22",PUBLIC_HOST],24)
    except (OSError,subprocess.TimeoutExpired,ValueError):
        return "SSH_HOSTKEY_SCAN_UNAVAILABLE"
    if rc!=0:return "SSH_HOSTKEY_SCAN_FAILED"
    try:
        lines=[x.strip() for x in body.decode("ascii","strict").splitlines()
               if x.strip() and not x.lstrip().startswith("#")]
        if len(lines)!=1:return "SSH_HOSTKEY_RESPONSE_UNEXPECTED"
        parts=lines[0].split()
        if len(parts)!=3 or parts[0]!=PUBLIC_HOST or parts[1]!="ssh-ed25519":
            return "SSH_HOSTKEY_RESPONSE_UNEXPECTED"
        blob=base64.b64decode(parts[2],validate=True)
        fingerprint="SHA256:"+base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
        if fingerprint!=HOSTKEY_PIN:return "SSH_HOSTKEY_PIN_MISMATCH"
    except (UnicodeError,ValueError,IndexError):
        return "SSH_HOSTKEY_RESPONSE_UNEXPECTED"
    return "SSH_HOSTKEY_PIN_PASS"

def main(argv):
    if argv!=["--inspect"]:
        print("KMJ_EXIT3_PHASE=BLOCKED_ARGUMENTS")
        return 2
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        print("KMJ_EXIT3_PHASE=BLOCKED_IDENTITY")
        return 2
    try:
        cmd=["/usr/bin/systemctl","show","--no-pager",
             "--property="+",".join(KEYS),UNIT]
        rc,out=call(cmd)
        if rc:raise ValueError("METADATA_FAILED")
        before=snapshot(out)
        rc,raw=call(["/usr/bin/journalctl","--no-pager","-o","cat",
                     "-n","200","_SYSTEMD_INVOCATION_ID="+before["InvocationID"]],16)
        if rc:raise ValueError("JOURNAL_FAILED")
        rc,out=call(cmd)
        if rc or snapshot(out)!=before:raise ValueError("INVOCATION_CHANGED")
        variant,stage=phase(raw)
        source=attest_source(before,variant)
        network=probe() if (source=="EXACT_SOURCE_SHA_PASS" and
                            stage=="AFTER_PREFLIGHT_BEFORE_HOSTKEY_PASS") else "NOT_PROBED"
    except (ValueError,OSError,subprocess.TimeoutExpired):
        print("KMJ_EXIT3_PHASE=BLOCKED_EXACT_INVOCATION_UNVERIFIED")
        return 2
    print("KMJ_EXIT3_PHASE=READ_ONLY")
    print("JOURNAL_SCOPE=EXACT_INVOCATION")
    print("SOURCE_VARIANT="+variant)
    print("FAILURE_STAGE="+stage)
    print("INSTALLED_SOURCE="+source)
    print("PUBLIC_HOSTKEY_PROBE="+network)
    print("SFTP_AUTH_ATTEMPTED=NO")
    print("BACKUP_REPAIR=NOT_ATTEMPTED")
    print("PRODUCTION_APPROVAL=UNCHANGED")
    return 0

if __name__=="__main__":
    sys.exit(main(sys.argv[1:]))
