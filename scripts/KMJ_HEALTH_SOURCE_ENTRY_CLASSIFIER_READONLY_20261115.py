#!/usr/bin/python3
"""P0 KMJ-elite read-only classifier for V3 backup source-tree entry failures.

No file contents read, no symlink followed, no raw paths/names/link values
printed, no backup/service/snapshot/credential mutation, no network except the
existing pinned V2 --inspect prerequisite in the exact owner source admission.
Classifies which of the six V3 copy roots contains a symlink or special entry.
A relative link lexically inside a source root is NOT automatically safe.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import posixpath
import re
import socket
import stat
import sys
import time
import types

ONEPASS=Path("/srv/kmj-codebridge-projects/kmj-main-platform/scripts/KMJ_OFFSITE_V3_HEALTH_ONEPASS_OWNER_REVIEW_20261115.py")
ONEPASS_SHA="69088262ec932983484b4937f891d14d34d55ac7a21e56fd0ff9bda33c724877"
SCAN_MAX=50000
SCAN_SECONDS=30
ROOT_LABELS=("STORAGE_APP","STORAGE_FRAMEWORK","STORAGE_LOGS",
             "CONFIG_LETSENCRYPT","CONFIG_CODEBRIDGE_STAGE","CONFIG_SITES_AVAILABLE")
READ_FLAGS=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC

class Blocked(Exception):
    pass

def _relative_link_class(parent,link):
    if not isinstance(link,str) or not link or "\x00" in link:
        return "LINK_VALUE_INVALID"
    if posixpath.isabs(link):
        return "ABSOLUTE_LINK"
    normalized=posixpath.normpath(posixpath.join(parent,link))
    if normalized==".." or normalized.startswith("../"):
        return "RELATIVE_LINK_ESCAPES_SOURCE_ROOT"
    if normalized in (".",""):
        return "RELATIVE_LINK_TO_SOURCE_ROOT"
    return "RELATIVE_LINK_LEXICALLY_IN_TREE"

def _record_type(name,mode,source_fd,relative_dir):
    if stat.S_ISLNK(mode):
        target=os.readlink(name,dir_fd=source_fd)
        return _relative_link_class(relative_dir,target)
    if stat.S_ISSOCK(mode):return "UNIX_SOCKET"
    if stat.S_ISFIFO(mode):return "FIFO"
    if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):return "DEVICE_NODE"
    return "OTHER_SPECIAL"

def scan_tree(root,*,cap=SCAN_MAX,clock=time.monotonic):
    """Metadata-only, fd-relative, nofollow tree scan with bounded output."""
    if type(cap) is not int or not 1<=cap<=SCAN_MAX:
        raise Blocked("SCANNER_BOUND_INVALID")
    if not root.is_absolute() or ".." in root.parts:
        raise Blocked("SCAN_ROOT_UNTRUSTED")
    fd=os.open(root,READ_FLAGS)
    pending=[(fd,"",0)]
    kinds={}
    counts={"regular":0,"directories":0,"symlinks":0,"special":0}
    scanned=0
    start=clock()
    try:
        while pending:
            if clock()-start>SCAN_SECONDS:
                raise Blocked("SCAN_TIMEOUT")
            current,rel,depth=pending.pop()
            try:
                if depth>20:raise Blocked("SCAN_DEPTH_LIMIT")
                before=os.fstat(current)
                if not stat.S_ISDIR(before.st_mode) or before.st_mode&0o002:
                    raise Blocked("SCAN_DIRECTORY_UNTRUSTED")
                with os.scandir(current) as children:
                    for child in children:
                        scanned+=1
                        if scanned>cap:raise Blocked("SCAN_ENTRY_LIMIT")
                        if clock()-start>SCAN_SECONDS:raise Blocked("SCAN_TIMEOUT")
                        name=child.name
                        if not isinstance(name,str) or "/" in name or name in (".",".."):
                            raise Blocked("SCAN_UNSAFE_NAME")
                        st=os.stat(name,dir_fd=current,follow_symlinks=False)
                        if stat.S_ISREG(st.st_mode):
                            counts["regular"]+=1
                        elif stat.S_ISDIR(st.st_mode):
                            counts["directories"]+=1
                            nextfd=os.open(name,READ_FLAGS,dir_fd=current)
                            check=os.fstat(nextfd)
                            if ((st.st_dev,st.st_ino)!=(check.st_dev,check.st_ino)):
                                os.close(nextfd)
                                raise Blocked("DIRECTORY_CHANGED")
                            pending.append((nextfd,posixpath.join(rel,name),depth+1))
                        else:
                            if stat.S_ISLNK(st.st_mode):
                                counts["symlinks"]+=1
                            else:
                                counts["special"]+=1
                            category=_record_type(name,st.st_mode,current,rel)
                            kinds[category]=kinds.get(category,0)+1
                after=os.fstat(current)
                if (before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns):
                    raise Blocked("SCAN_TREE_CHANGED")
            finally:
                os.close(current)
                fd=-1
        return {"counts":counts,"kinds":kinds,"scanned":scanned}
    finally:
        for openfd,_,_ in pending:
            try:os.close(openfd)
            except OSError:pass
        # If an exception happens before the first loop, also close root fd.
        if fd>=0:
            try:os.close(fd)
            except OSError:pass

def admit_onepass():
    st=os.lstat(ONEPASS)
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1
            or st.st_mode&0o022 or st.st_size>35000):
        raise Blocked("ONEPASS_PINNED_SOURCE_METADATA")
    f=os.open(ONEPASS,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        after=os.fstat(f)
        raw=os.read(f,35001)
    finally:os.close(f)
    if (after.st_dev,after.st_ino,after.st_size)!=(st.st_dev,st.st_ino,st.st_size):
        raise Blocked("ONEPASS_SOURCE_CHANGED")
    if len(raw)!=st.st_size or hashlib.sha256(raw).hexdigest()!=ONEPASS_SHA:
        raise Blocked("ONEPASS_SOURCE_SHA_CHANGED")
    mod=types.ModuleType("kmj_owner_pinned_onepass_readonly")
    mod.__file__=str(ONEPASS)
    exec(compile(raw,str(ONEPASS),"exec"),mod.__dict__)
    return mod

def inspect():
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        raise Blocked("ROOT_HOST_REQUIRED")
    owner=admit_onepass()
    # The exact unchanged V2 admission also verifies pinned executable,
    # systemd unit, original health source, and source top-level parents.
    _,_,_,user,_,_,storage,_=owner.runtime_sources()
    roots=(
        ("STORAGE_APP",storage.parent/"app"),
        ("STORAGE_FRAMEWORK",storage.parent/"framework"),
        ("STORAGE_LOGS",storage.parent/"logs"),
        ("CONFIG_LETSENCRYPT",owner.CONFIG["letsencrypt"]),
        ("CONFIG_CODEBRIDGE_STAGE",owner.CONFIG["codebridge-stage"]),
        ("CONFIG_SITES_AVAILABLE",owner.CONFIG["sites-available"]),
    )
    if tuple(label for label,_ in roots)!=ROOT_LABELS:
        raise Blocked("SOURCE_ROOT_MATRIX_CHANGED")
    grand={"regular":0,"directories":0,"symlinks":0,"special":0}
    all_kinds={}
    for label,root in roots:
        result=scan_tree(root)
        print("TREE_"+label+"_ENTRIES="+str(result["scanned"]))
        print("TREE_"+label+"_LINKS="+str(result["counts"]["symlinks"]))
        print("TREE_"+label+"_SPECIAL="+str(result["counts"]["special"]))
        for kind,count in result["kinds"].items():
            key=(label,kind)
            all_kinds[key]=count
            grand["symlinks"]+=0
        for k in grand:grand[k]+=result["counts"][k]
    for (label,kind),count in sorted(all_kinds.items()):
        if not re.fullmatch(r"[A-Z_]{3,50}",kind):
            raise Blocked("OUTPUT_CLASS_UNTRUSTED")
        print("ENTRY_"+label+"_"+kind+"="+str(count))
    print("TOTAL_LINKS="+str(grand["symlinks"]))
    print("TOTAL_SPECIAL="+str(grand["special"]))
    print("SOURCE_PATH_OR_LINK_VALUE_PRINTED=NO")
    print("SYMLINK_FOLLOWED=NO")
    print("SNAPSHOT_BACKUP_AND_SERVICE_MUTATION=NONE")
    print("RESULT=READ_ONLY_SOURCE_ENTRY_CLASSIFIER_COMPLETE")
    return 0

def selftest():
    assert _relative_link_class("live/domain","../../archive/domain/cert1.pem")=="RELATIVE_LINK_LEXICALLY_IN_TREE"
    assert _relative_link_class("app/a","../../../../etc/passwd")=="RELATIVE_LINK_ESCAPES_SOURCE_ROOT"
    assert _relative_link_class("app","/etc/passwd")=="ABSOLUTE_LINK"
    assert _relative_link_class("","")=="LINK_VALUE_INVALID"
    print("KMJ_SOURCE_ENTRY_CLASSIFIER_OFFLINE_SELFTEST=PASS")
    print("PRODUCTION_MUTATION=NONE")
    return 0

def main():
    if sys.argv[1:]==["--selftest"]:
        return selftest()
    if sys.argv[1:]!=["--inspect"]:
        print("RESULT=BLOCKED_ARGS")
        return 2
    try:return inspect()
    except (OSError,Blocked,ValueError,UnicodeError,AttributeError) as exc:
        code=str(exc)
        if re.fullmatch(r"[A-Z_]{5,70}",code) is None:
            code="ROOT_SOURCE_SCAN_UNVERIFIED"
        print("BLOCKER="+code)
        print("PRODUCTION_MUTATION=NONE")
        print("RESULT=BLOCKED_READ_ONLY")
        return 3

if __name__=="__main__":
    raise SystemExit(main())
