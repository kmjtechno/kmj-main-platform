#!/usr/bin/python3
"""KMJ-elite P0: root-private, SHA-fenced V3 source bundle and guarded onepass.

Opt-in only. --selftest and --inspect do not mutate host. --prepare copies
reviewed modules to NEW private root-owned create-only files (not backups).
--preflight invokes the original SHA-pinned read-only V2+V3 preflight.
--run-once invokes ONE reviewed fresh V3 backup that emits its own exact
native systemd health receipt. All fixed argv; no arbitrary root shell.

Publisher's six local "secret" parameter spellings are deterministically
converted to the exact GH-reviewed "restricted" spelling only in the new
root-private copy. Original CodeBridge files and units remain untouched.
Fail closed if local source, conversion result, or owner runner bytes drift.
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

LOCAL=Path("/srv/kmj-codebridge-projects/kmj-main-platform/scripts")
PRIVATE=Path("/usr/local/libexec/kmj-v3-owner-sources-certbot-20261115")
OWNER_NAME="KMJ_OFFSITE_V3_HEALTH_ONEPASS_OWNER_REVIEW_20261115.py"
OWNER_SOURCE_SHA="1f5f4d7bf30c0f7977a48c510233c948b314aa327d67fffa8a7cd33d14c4e137"
OWNER_REVIEWED_SHA="94fc8c7a2edf1a088bd1730e4350d4e8ee2f4d9bb4bb26374fde7438d81b4093"
PUB_NAME="KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py"
PUB_SOURCE_SHA="4e30509de13e5c6126f742f4a9f32499d1c95c8467185591c0f8b25a26e1fc76"
PUB_REVIEWED_SHA="58a5eb0c9d875620148cbe112e8d76793c103e9c413f1528023ea4523993e4de"
PINS={
    "KMJ_OFFSITE_V3_DUAL_ARTIFACT_POLICY_REVIEW_20261115.py":
        "2d3fdc5456c3ee7a75fdb133fdab5e7713e036ed659cc7008c5ec2a8df0139c7",
    "KMJ_OFFSITE_V3_LOCAL_CIPHER_PUBLISHER_REVIEW_20261115.py":
        "22c85a6a5e239055b69697d47c733e7afe07c9c5cd74cf70478d3577dc3ebc3f",
    PUB_NAME:PUB_REVIEWED_SHA,
    "KMJ_OFFSITE_V3_DAILY_SOURCE_BUILDER_REVIEW_20261115.py":
        "ef310b88c2a2295c2fd7126f7e560372a164771c1baba872e5396755041a20fc",
    "KMJ_OFFSITE_V3_TRANSFER_BOUND_TRANSACTION_REVIEW_20261115.py":
        "cebc9366412ef689e4887d0ebac958989842c55fade1feff607f754c1bd209ea",
    "KMJ_OFFSITE_V3_PINNED_V2_ADMISSION_REVIEW_20261115.py":
        "a476833c2185f2271693ee5f957fc1434a782284a9c0050001ca3b2fd44594ed",
}
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","HOME":"/root","LANG":"C","LC_ALL":"C"}
ROOT_PATHS=(Path("/"),Path("/usr"),Path("/usr/local"),Path("/usr/local/libexec"))
F_OPEN=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC
F_DIR=F_OPEN|os.O_DIRECTORY

class Deny(Exception):
    pass

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def require_root_host():
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        raise Deny("ROOT_KMJ_ELITE_ONLY")

def read_pinned(path,sha,owner=None,cap=262144):
    if not re.fullmatch(r"[a-f0-9]{64}",sha):
        raise Deny("PIN_SHAPE")
    before=os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or
        before.st_mode&0o022 or not 128<=before.st_size<=cap or
        (owner is not None and before.st_uid!=owner)):
        raise Deny("PINNED_FILE_METADATA_DRIFT")
    fd=os.open(path,F_OPEN)
    try:
        start=os.fstat(fd)
        raw=os.read(fd,cap+1)
        end=os.fstat(fd)
    finally:
        os.close(fd)
    sig=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,
                  s.st_mtime_ns,s.st_ctime_ns)
    if sig(before)!=sig(start) or sig(start)!=sig(end):
        raise Deny("PINNED_FILE_RACED")
    if len(raw)!=start.st_size or digest(raw)!=sha:
        raise Deny("PINNED_FILE_SHA_MISMATCH")
    return raw

def convert_publisher(raw):
    """Exact six token changes, accepting no other bytes."""
    if digest(raw)!=PUB_SOURCE_SHA or raw.count(b"secret")!=6:
        raise Deny("PUBLISHER_LOCAL_SOURCE_CHANGED")
    output=raw.replace(b"secret",b"restricted")
    if digest(output)!=PUB_REVIEWED_SHA:
        raise Deny("PUBLISHER_REVIEWED_SOURCE_SHA_MISMATCH")
    return output

def convert_owner(raw):
    """One exact call signature fix; no code or branch downloads."""
    if digest(raw)!=OWNER_SOURCE_SHA:
        raise Deny("OWNER_LOCAL_SOURCE_CHANGED")
    old=b'daily.regular(fd,"SHA256SUMS",{0},secret=[REDACTED]
    new=b'daily.regular(fd,"SHA256SUMS",{0},restricted=True)'
    if raw.count(old)!=1:
        raise Deny("OWNER_REVIEWED_API_SHAPE_CHANGED")
    output=raw.replace(old,new)
    if digest(output)!=OWNER_REVIEWED_SHA:
        raise Deny("OWNER_REVIEWED_SOURCE_SHA_MISMATCH")
    return output

def build_immutable_files():
    names={}
    for name,sha in PINS.items():
        if name==PUB_NAME:
            source=read_pinned(LOCAL/name,PUB_SOURCE_SHA)
            names[name]=(convert_publisher(source),PUB_REVIEWED_SHA)
        else:
            names[name]=(read_pinned(LOCAL/name,sha),sha)
    names[OWNER_NAME]=(convert_owner(read_pinned(
        LOCAL/OWNER_NAME,OWNER_SOURCE_SHA)),OWNER_REVIEWED_SHA)
    if len(names)!=7 or any(digest(raw)!=sha for raw,sha in names.values()):
        raise Deny("OWNER_SOURCE_SET_INCOMPLETE")
    return names

def root_parents_guard():
    for path in ROOT_PATHS:
        st=os.lstat(path)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or
            st.st_mode&0o022):
            raise Deny("ROOT_SOURCE_PARENT_UNTRUSTED")

def checked_root_source_dir(*,create=False):
    root_parents_guard()
    if create:
        try:
            os.mkdir(PRIVATE,0o700)
        except FileExistsError:
            pass
    st=os.lstat(PRIVATE)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or
        stat.S_IMODE(st.st_mode)!=0o700):
        raise Deny("ROOT_BUNDLE_DIR_UNTRUSTED")
    fd=os.open(PRIVATE,F_DIR)
    if (os.fstat(fd).st_dev,os.fstat(fd).st_ino)!=(st.st_dev,st.st_ino):
        os.close(fd)
        raise Deny("ROOT_BUNDLE_DIRECTORY_RACE")
    return fd

def write_fresh_only(fd,name,data,sha):
    try:
        os.stat(name,dir_fd=fd,follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        # An existing bundle is accepted ONLY if exact byte SHA and 0600 root
        # ownership remain unchanged. Never truncate or replace it.
        read_pinned(PRIVATE/name,sha,owner=0)
        return False
    out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                0o600,dir_fd=fd)
    try:
        os.fchmod(out,0o600)
        os.fchown(out,0,0)
        pos=0
        while pos<len(data):
            n=os.write(out,data[pos:])
            if n<=0:
                raise Deny("ROOT_BUNDLE_SHORT_WRITE")
            pos+=n
        os.fsync(out)
    finally:
        os.close(out)
    read_pinned(PRIVATE/name,sha,owner=0)
    return True

def check_installed_source_set():
    fd=checked_root_source_dir()
    try:
        expected={**PINS,OWNER_NAME:OWNER_REVIEWED_SHA}
        names=set(os.listdir(fd))
        if names!=set(expected):
            raise Deny("ROOT_BUNDLE_UNEXPECTED_CONTENTS")
        for name,sha in expected.items():
            read_pinned(PRIVATE/name,sha,owner=0)
        return True
    finally:
        os.close(fd)

def prepare():
    # First pre-validate every source & transformation before any root writes.
    src=build_immutable_files()
    fd=checked_root_source_dir(create=True)
    created=0
    try:
        for name,(raw,sha) in sorted(src.items()):
            if write_fresh_only(fd,name,raw,sha):
                created+=1
        os.fsync(fd)
    finally:
        os.close(fd)
    check_installed_source_set()
    print("ROOT_PRIVATE_SOURCE_BUNDLE=7_SHA256_PINNED_FILES")
    print("ROOT_BUNDLE_NEW_FILES="+str(created))
    print("CODEBRIDGE_PROJECT_SOURCES_MODIFIED=NO")
    print("ORIGINAL_V2_BACKUP_TIMER_MODIFIED=NO")
    print("RESULT=PINNED_PRIVATE_SOURCE_PREPARED")
    return 0

def owner_call(mode):
    check_installed_source_set()
    cmd=["/usr/bin/python3","-I","-B",str(PRIVATE/OWNER_NAME),mode]
    try:
        result=subprocess.run(cmd,env=ENV,cwd="/",stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                              timeout=1500 if mode=="--run-once" else 90,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise Deny("PINNED_OWNER_EXECUTION_FAILED")
    if len(result.stdout)>32768:
        raise Deny("OWNER_OUTPUT_TOO_LARGE")
    body=result.stdout.decode("utf-8",errors="replace")
    for line in body.splitlines():
        if not re.fullmatch(r"[A-Z0-9_.:-]{1,116}(?:=[A-Z0-9_.:-]{1,128})?",line):
            raise Deny("OWNER_OUTPUT_SHAPE_UNTRUSTED")
        print(line,flush=True)
    if result.returncode!=0:
        print("PINNED_OWNER_RETURN_CODE="+str(result.returncode))
        raise Deny("OWNER_"+("PREFLIGHT" if mode=="--preflight" else "RECOVERY")+"_BLOCKED")
    if mode=="--preflight" and "RESULT=GUARDED_ONEPASS_PREFLIGHT_PASS" not in body:
        raise Deny("OWNER_PREFLIGHT_RECEIPT_MISSING")
    if mode=="--run-once":
        for marker in ("FRESH_REMOTE_SFTP_SHA_READBACK=PASS",
                       "FRESH_LOCAL_CIPHER_SIDECAR=PASS",
                       "FRESH_LOCAL_DAILY_PGDMP_STORAGE_CONFIG=PASS",
                       "HEALTH_UNIT_OWN_INVOCATION=SUCCESS_EXIT0",
                       "RESULT=FRESH_DUAL_LOCAL_HEALTH_ONEPASS_PASS"):
            if marker not in body:
                raise Deny("OWNER_RECOVERY_RECEIPT_MISSING")
    return 0

def selftest():
    assert len(PINS)==6 and len(set(PINS.values()))==6
    assert len(OWNER_SOURCE_SHA)==64 and len(OWNER_REVIEWED_SHA)==64
    assert PUB_SOURCE_SHA!=PUB_REVIEWED_SHA
    print("KMJ_P0_V3_BUNDLE_OFFLINE_SELFTEST=PASS")
    print("HOST_OR_BACKUP_MUTATION=NONE")
    return 0

def main():
    os.umask(0o077)
    if len(sys.argv)!=2 or sys.argv[1] not in (
            "--selftest","--inspect","--prepare","--preflight","--run-once"):
        print("RESULT=BLOCKED_ARGS")
        return 2
    if sys.argv[1]=="--selftest":
        return selftest()
    try:
        require_root_host()
        if sys.argv[1]=="--inspect":
            build_immutable_files()
            print("PINNED_LOCAL_SOURCE_SET=PASS")
            print("HOST_OR_BACKUP_MUTATION=NONE")
            return 0
        if sys.argv[1]=="--prepare":
            return prepare()
        if sys.argv[1]=="--preflight":
            return owner_call("--preflight")
        return owner_call("--run-once")
    except Exception as error:
        detail=str(error)
        if not re.fullmatch(r"[A-Z0-9_]{4,96}",detail):
            detail=type(error).__name__.upper()
        print("BLOCKER="+detail)
        print("NATIVE_HEALTH_EXIT0=NOT_ATTESTED")
        print("RESULT=BLOCKED_FAIL_CLOSED")
        return 3

if __name__=="__main__":
    raise SystemExit(main())
