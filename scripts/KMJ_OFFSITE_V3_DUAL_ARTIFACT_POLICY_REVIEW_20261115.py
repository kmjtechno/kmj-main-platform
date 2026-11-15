#!/usr/bin/python3
"""KMJ V3 dual-artifact policy, SOURCE ONLY; CLI is read-only. NOT AN INSTALLER.

Pure helpers for owner review. Never edit health line 25/28 or systemd units.
No local backup, remote transfer, retention deletion or installation is wired.
"""
from __future__ import annotations
import ctypes
import datetime as dt
import errno
import hashlib
import hmac
import os
from pathlib import Path
import re
import socket
import stat
import sys

STAMP=re.compile(r"20[0-9]{6}T[0-9]{6}Z",re.ASCII)
SHA256=re.compile(r"[a-f0-9]{64}",re.ASCII)
CIPHER_LIMIT=8*1024**3
ENTRY_LIMIT=512
MIN_FREE=2*1024**3
RENAME_NOREPLACE=1
VAULT=Path("/var/backups/kmj-elite-offsite-encrypted")
FORMAT="GOOGLE_X25519_AGE_V2"
PAYLOAD="TAR_GZ_4_MEMBERS"

class Deny(Exception):pass

def valid_stamp(value):
    if not isinstance(value,str) or STAMP.fullmatch(value) is None:return False
    try:parsed=dt.datetime.strptime(value,"%Y%m%dT%H%M%SZ")
    except ValueError:return False
    return parsed.strftime("%Y%m%dT%H%M%SZ")==value

def cipher_name(stamp):
    if not valid_stamp(stamp):raise Deny("STAMP_INVALID")
    return stamp+".tar.age"

def sidecar_bytes(stamp,digest):
    if not isinstance(digest,str) or SHA256.fullmatch(digest) is None:
        raise Deny("CIPHER_SHA256_INVALID")
    data=(digest+"  "+cipher_name(stamp)+"\n").encode("ascii")
    if len(data)!=91:raise Deny("SIDECAR_SIZE_INVALID")
    return data

def parse_legacy_sidecar(stamp,data):
    if not isinstance(data,bytes) or len(data)!=91:raise Deny("SIDECAR_SHAPE_INVALID")
    digest=data[:64].decode("ascii",errors="replace")
    expected=sidecar_bytes(stamp,digest)
    if not hmac.compare_digest(expected,data):raise Deny("SIDECAR_SHAPE_INVALID")
    return digest

def format_metadata(stamp,digest):
    """Keep provenance SEPARATE from the exact legacy-compatible sidecar."""
    sidecar_bytes(stamp,digest)
    return (
        "schema=kmj.local.dual.x25519.v3\n"
        f"stamp_utc={stamp}\n"
        f"cipher_format={FORMAT}\n"
        f"payload_format={PAYLOAD}\n"
        "payload_members=database.dump,storage.tar.gz,metadata.txt,SHA256SUMS\n"
        f"cipher_sha256={digest}\n"
        "remote_sha_readback=PASS_REQUIRED_BEFORE_LOCAL_COMMIT\n"
        "remote_restore=NOT_VERIFIED\n"
    ).encode("ascii")

def read_private_cipher_hash(path,*,expected_uid=0):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=expected_uid
            or stat.S_IMODE(before.st_mode)!=0o600 or before.st_nlink!=1
            or not 60<=before.st_size<=CIPHER_LIMIT):
            raise Deny("CIPHER_SOURCE_UNSAFE")
        h=hashlib.sha256();seen=0
        while True:
            block=os.read(fd,1024*1024)
            if not block:break
            seen+=len(block)
            if seen>CIPHER_LIMIT:raise Deny("CIPHER_SOURCE_TOO_LARGE")
            h.update(block)
        after=os.fstat(fd)
        def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
        if identity(before)!=identity(after) or seen!=before.st_size:
            raise Deny("CIPHER_SOURCE_CHANGED")
        return h.hexdigest(),seen
    finally:os.close(fd)

def open_vault(root=VAULT,*,expected_uid=0):
    if root==VAULT:
        for parent in (Path("/var"),Path("/var/backups")):
            s=parent.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
                raise Deny("VAULT_PARENT_UNTRUSTED")
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=expected_uid or s.st_mode&0o022:
            raise Deny("VAULT_UNSAFE")
        return fd
    except BaseException:
        os.close(fd);raise

def vault_inventory(root_fd,*,expected_uid=0):
    names=os.listdir(root_fd)
    if len(names)>ENTRY_LIMIT:raise Deny("VAULT_ENTRY_LIMIT")
    ciphers,sidecars=set(),set()
    for name in names:
        if name.endswith(".tar.age") and valid_stamp(name[:-8]):
            category,stamp="cipher",name[:-8]
        elif name.endswith(".sha256") and valid_stamp(name[:-7]):
            category,stamp="sidecar",name[:-7]
        else:continue
        s=os.stat(name,dir_fd=root_fd,follow_symlinks=False)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=expected_uid
            or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1):
            raise Deny("VAULT_MATCHED_ENTRY_UNSAFE")
        (ciphers if category=="cipher" else sidecars).add(stamp)
    return {
        "paired":tuple(sorted(ciphers&sidecars)),
        "cipher_without_sidecar":tuple(sorted(ciphers-sidecars)),
        "sidecar_without_cipher":tuple(sorted(sidecars-ciphers)),
        "other_entries":len(names)-len(ciphers)-len(sidecars),
    }

def plan_retention(root_fd,*,keep_count,expected_uid=0):
    """READ-ONLY candidate list; no unlink/rmdir and no CLI mutation."""
    if type(keep_count) is not int or not 2<=keep_count<=365:
        raise Deny("RETENTION_NOT_APPROVED")
    found=vault_inventory(root_fd,expected_uid=expected_uid)
    if found["cipher_without_sidecar"] or found["sidecar_without_cipher"]:
        raise Deny("VAULT_ORPHAN_REVIEW_REQUIRED")
    stamps=found["paired"]
    return stamps[:-keep_count] if len(stamps)>keep_count else ()

def check_free_space(root_fd,expected_bytes):
    if type(expected_bytes) is not int or not 60<=expected_bytes<=CIPHER_LIMIT:
        raise Deny("CIPHER_BYTES_NOT_BOUNDED")
    v=os.fstatvfs(root_fd)
    if v.f_frsize*v.f_bavail<MIN_FREE+expected_bytes*2:
        raise Deny("VAULT_SPACE_BELOW_RESERVE")
    return True

def renameat2_noreplace(source_fd,source_name,dest_fd,dest_name):
    """Review-only primitive; only offline disposable fixtures may call this."""
    if not isinstance(source_name,str) or not isinstance(dest_name,str):
        raise Deny("RENAME_NAME_INVALID")
    if (re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",source_name) is None
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",dest_name) is None
        or source_name in (".","..") or dest_name in (".","..")):
        raise Deny("RENAME_NAME_INVALID")
    src=os.stat(source_name,dir_fd=source_fd,follow_symlinks=False)
    dest=os.fstat(dest_fd)
    if src.st_dev!=dest.st_dev or not stat.S_ISREG(src.st_mode) or src.st_nlink!=1:
        raise Deny("RENAME_SOURCE_INVALID")
    if src.st_uid!=os.geteuid() or stat.S_IMODE(src.st_mode)!=0o600:
        raise Deny("RENAME_SOURCE_PERMISSIONS")
    try:os.stat(dest_name,dir_fd=dest_fd,follow_symlinks=False)
    except FileNotFoundError:pass
    else:raise Deny("RENAME_DEST_ALREADY_EXISTS")
    libc=ctypes.CDLL(None,use_errno=True)
    fn=getattr(libc,"renameat2",None)
    if fn is None:raise Deny("RENAME_NOREPLACE_UNAVAILABLE")
    fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    fn.restype=ctypes.c_int
    if fn(source_fd,os.fsencode(source_name),dest_fd,os.fsencode(dest_name),RENAME_NOREPLACE):
        if ctypes.get_errno()==errno.EEXIST:raise Deny("RENAME_DEST_RACE_EXISTS")
        raise Deny("RENAME_NOREPLACE_FAILED")
    os.fsync(dest_fd)
    os.fsync(source_fd)

def main():
    if (sys.argv[1:]!=["--inspect"] or os.geteuid()!=0
        or socket.gethostname().split(".")[0]!="KMJ-elite"):
        print("KMJ_DUAL_POLICY=BLOCKED_HOST_OR_ARGS");return 2
    try:
        fd=open_vault()
        try:
            report=vault_inventory(fd)
            space=os.fstatvfs(fd)
            print("KMJ_DUAL_POLICY=READ_ONLY_REVIEW")
            print("VAULT_PAIRED_STAMPS="+str(len(report["paired"])))
            print("VAULT_ORPHAN_CIPHERS="+str(len(report["cipher_without_sidecar"])))
            print("VAULT_ORPHAN_SIDECARS="+str(len(report["sidecar_without_cipher"])))
            print("VAULT_SPACE_RESERVE_2GIB="+(
                "PASS" if space.f_bavail*space.f_frsize>=MIN_FREE else "BLOCKED"))
            print("SNAPSHOT_WRITTEN=NO")
            print("RETENTION_EXECUTED=NO")
            print("SERVICE_MUTATED=NO")
            return 0
        finally:os.close(fd)
    except (OSError,Deny):
        print("KMJ_DUAL_POLICY=BLOCKED_READ_ONLY");return 3

if __name__=="__main__":raise SystemExit(main())
