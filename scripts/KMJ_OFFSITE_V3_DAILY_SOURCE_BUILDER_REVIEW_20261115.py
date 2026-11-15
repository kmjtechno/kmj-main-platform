#!/usr/bin/python3
"""V3 review-only bounded builder of a COMPLETE local daily snapshot staging tree.

NOT INSTALLED, no CLI, remote transfer, live DB query, prune, or service change.
Inputs must come from an independently reviewed owner-locked manifest and a
trusted already-complete PostgreSQL custom dump. This creates new files under a
PRIVATE staging root outside the monitored daily directory. No local backup is
credited until a separate authenticated same-invocation remote SHA readback,
owner-approved atomic publication, actual restore and health-unit proof.

Snapshot input sets: dump, release storage root (app/framework/logs),
three independently pinned config directories, and app env. No credentials
or source paths are printed. Unsafe source symlinks/hardlinks/special files
are rejected and no pre-existing snapshots are overwritten or removed.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import time

DAILY_PUBLISHER=Path(__file__).with_name("KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_v3_daily_publisher",DAILY_PUBLISHER)
if spec is None or spec.loader is None:
    raise RuntimeError("DAILY_PUBLISHER_SOURCE_UNAVAILABLE")
daily=importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)

STAMP=daily.STAMP
STORAGE=("app","framework","logs")
CONFIG=("letsencrypt","codebridge-stage","sites-available")
MAX_BYTES=daily.MAX_BYTES
MAX_ENTRIES=daily.MAX_ENTRIES
MAX_DEPTH=daily.MAX_DEPTH
MIN_FREE=daily.MIN_FREE


class Deny(Exception):
    pass


def path_guard(path):
    obj=Path(path)
    if (not obj.is_absolute() or ".." in obj.parts or
            str(obj) in ("","/") or "\x00" in str(obj)):
        raise Deny("SOURCE_PATH_NOT_ABSOLUTE_BOUNDED")
    return obj


def owned_dir(path,owners,strict=False):
    obj=path_guard(path)
    fd=os.open(obj,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    st=os.fstat(fd)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid not in owners
            or (strict and stat.S_IMODE(st.st_mode)!=0o700)
            or st.st_mode&0o022):
        os.close(fd)
        raise Deny("SOURCE_DIRECTORY_MODE_OR_OWNER")
    return fd


def checked_file(dirfd,name,owners,exact_private=False):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=dirfd)
    st=os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid not in owners
            or st.st_nlink!=1 or st.st_mode&0o022
            or (exact_private and stat.S_IMODE(st.st_mode)!=0o600)):
        os.close(fd)
        raise Deny("SOURCE_FILE_MODE_OWNER_OR_LINK")
    return fd,st


def checked_open_file(path,owners,exact_private=False):
    obj=path_guard(path)
    directory=owned_dir(obj.parent,owners)
    try:
        return checked_file(directory,obj.name,owners,exact_private)
    finally:
        os.close(directory)


def safe_entry(name):
    return (isinstance(name,str) and 0<len(name)<=255
            and name not in (".","..") and "/" not in name
            and all(32<=ord(ch)<127 for ch in name))


def write_all(fd,data):
    offset=0
    while offset<len(data):
        length=os.write(fd,data[offset:])
        if length<=0:raise Deny("SHORT_PRIVATE_WRITE")
        offset+=length


def new_private_file(fd,name,data):
    out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                0o600,dir_fd=fd)
    try:
        os.fchmod(out,0o600)
        write_all(out,data)
        os.fsync(out)
    finally:os.close(out)


def copy_fd(fd,stat_before,target_fd,name,limit,stats):
    if stat_before.st_size>limit or stats["bytes"]+stat_before.st_size>MAX_BYTES:
        raise Deny("INPUT_TOTAL_BYTES_EXCEEDED")
    out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                0o600,dir_fd=target_fd)
    sha=hashlib.sha256()
    amount=0
    try:
        os.fchmod(out,0o600)
        while True:
            block=os.read(fd,1024*1024)
            if not block:break
            amount+=len(block)
            if amount>limit or stats["bytes"]+amount>MAX_BYTES:
                raise Deny("INPUT_TOTAL_BYTES_EXCEEDED")
            sha.update(block)
            write_all(out,block)
        os.fsync(out)
    finally:os.close(out)
    after=os.fstat(fd)
    if ((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
            !=(stat_before.st_dev,stat_before.st_ino,stat_before.st_size,
               stat_before.st_mtime_ns,stat_before.st_ctime_ns)
            or amount!=stat_before.st_size):
        raise Deny("SOURCE_CHANGED_DURING_COPY")
    stats["bytes"]+=amount
    return sha.hexdigest()


def copy_file(source,targetfd,name,owners,stats,*,private=False):
    src,meta=checked_open_file(source,owners,exact_private=private)
    try:return copy_fd(src,meta,targetfd,name,MAX_BYTES,stats)
    finally:os.close(src)


def copy_tree(src_path,dstfd,owners,stats,manifest,prefix,depth=0):
    if depth>MAX_DEPTH:raise Deny("SOURCE_TREE_DEPTH_LIMIT")
    src=owned_dir(src_path,owners)
    try:
        initial=os.fstat(src)
        children=os.listdir(src)
        if len(children)>MAX_ENTRIES:raise Deny("SOURCE_DIRECTORY_ENTRIES_LIMIT")
        for name in sorted(children):
            if not safe_entry(name):raise Deny("SOURCE_NAME_UNSAFE")
            stats["entries"]+=1
            if stats["entries"]>MAX_ENTRIES:raise Deny("SOURCE_TREE_ENTRY_LIMIT")
            before=os.stat(name,dir_fd=src,follow_symlinks=False)
            if before.st_uid not in owners or before.st_mode&0o022:
                raise Deny("SOURCE_ENTRY_OWNER_OR_MODE")
            if stat.S_ISREG(before.st_mode):
                child,meta=checked_file(src,name,owners)
                try:
                    digest=copy_fd(child,meta,dstfd,name,MAX_BYTES,stats)
                finally:os.close(child)
                manifest.append((prefix+"/"+name,digest))
            elif stat.S_ISDIR(before.st_mode):
                os.mkdir(name,0o700,dir_fd=dstfd)
                sub=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,
                            dir_fd=dstfd)
                try:
                    os.fchmod(sub,0o700)
                    copy_tree(Path(src_path)/name,sub,owners,stats,manifest,
                              prefix+"/"+name,depth+1)
                    os.fsync(sub)
                finally:os.close(sub)
            else:
                raise Deny("SOURCE_LINK_OR_SPECIAL_ENTRY")
        finish=os.fstat(src)
        if ((initial.st_dev,initial.st_ino,initial.st_mtime_ns,initial.st_ctime_ns)
                !=(finish.st_dev,finish.st_ino,finish.st_mtime_ns,finish.st_ctime_ns)):
            raise Deny("SOURCE_DIRECTORY_CHANGED_DURING_COPY")
    finally:os.close(src)


def read_pgdmp_magic(source,owners):
    fd,meta=checked_open_file(source,owners)
    try:
        if meta.st_size<32 or os.read(fd,5)!=b"PGDMP":
            raise Deny("SOURCE_PGDMP_MAGIC_INVALID")
    finally:os.close(fd)


def preflight(stage_root,daily_root,stamp,dump_source,storage_source,
              config_sources,env_source,uid,storage_uid):
    if (not isinstance(stamp,str) or STAMP.fullmatch(stamp) is None
            or type(uid) is not int or type(storage_uid) is not int
            or uid<0 or storage_uid<0):
        raise Deny("SOURCE_INPUTS_UNVERIFIED")
    s=path_guard(stage_root)
    d=path_guard(daily_root)
    if (s==d or s in d.parents or d in s.parents
            or s==Path("/var/backups/kmj-elite-daily")
            or Path("/var/backups/kmj-elite-daily") in s.parents):
        raise Deny("STAGING_ROOT_INSIDE_HEALTH_MONITOR")
    if set(config_sources)!=set(CONFIG):
        raise Deny("CONFIG_SOURCE_MATRIX_INCOMPLETE")
    if (path_guard(dump_source)==path_guard(env_source)
            or path_guard(dump_source)==path_guard(storage_source)):
        raise Deny("SOURCE_INPUTS_COLLIDE")
    stagefd=owned_dir(s,{uid},strict=True)
    try:
        disk=os.fstatvfs(stagefd)
        if disk.f_frsize*disk.f_bavail<MIN_FREE:
            raise Deny("STAGING_DISK_RESERVE_LOW")
    finally:os.close(stagefd)
    read_pgdmp_magic(dump_source,{uid,storage_uid})
    for path in (storage_source,*(config_sources[name] for name in CONFIG)):
        fd=owned_dir(path,{uid,storage_uid} if path==storage_source else {uid})
        os.close(fd)
    fd,_=checked_open_file(env_source,{uid},exact_private=True)
    os.close(fd)


def build_preverified_snapshot(
    stage_root:Path,daily_root:Path,stamp:str,dump_source:Path,
    storage_source:Path,config_sources:dict[str,Path],env_source:Path,
    *,expected_uid:int=0,storage_owner_uid:int=0,
    fixture_fault_after_dump:bool=False,
):
    """Build complete private staging tree only; NEVER publish to daily root.

    The external owner-reviewed wrapper must attest the exact V2 dump source,
    quiescence requirements and remote readback. This function neither checks
    a remote receipt nor performs PostgreSQL restore.
    """
    preflight(stage_root,daily_root,stamp,dump_source,storage_source,
              config_sources,env_source,expected_uid,storage_owner_uid)
    stagefd=owned_dir(stage_root,{expected_uid},strict=True)
    try:
        name="stage-"+stamp
        os.mkdir(name,0o700,dir_fd=stagefd)
        os.fsync(stagefd)
        work=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,
                     dir_fd=stagefd)
        try:
            os.fchmod(work,0o700)
            manifest=[]
            stats={"bytes":0,"entries":0}
            digest=copy_file(dump_source,work,"platform.dump",
                             {expected_uid,storage_owner_uid},stats)
            manifest.append(("platform.dump",digest))
            if fixture_fault_after_dump:
                raise Deny("INJECTED_PARTIAL_STAGING_NO_HEALTH_CREDIT")
            digest_env=copy_file(env_source,work,"app.env",{expected_uid},stats,private=True)
            manifest.append(("app.env",digest_env))
            for literal in ("platform-storage","config"):
                os.mkdir(literal,0o700,dir_fd=work)
            storage=os.open("platform-storage",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=work)
            try:
                os.fchmod(storage,0o700)
                for subname in STORAGE:
                    os.mkdir(subname,0o700,dir_fd=storage)
                    out=os.open(subname,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=storage)
                    try:
                        copy_tree(Path(storage_source)/subname,out,
                                  {expected_uid,storage_owner_uid},
                                  stats,manifest,"platform-storage/"+subname)
                        os.fsync(out)
                    finally:os.close(out)
                os.fsync(storage)
            finally:os.close(storage)
            config=os.open("config",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=work)
            try:
                os.fchmod(config,0o700)
                for subname in CONFIG:
                    os.mkdir(subname,0o700,dir_fd=config)
                    out=os.open(subname,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=config)
                    try:
                        copy_tree(config_sources[subname],out,{expected_uid},
                                  stats,manifest,"config/"+subname)
                        os.fsync(out)
                    finally:os.close(out)
                os.fsync(config)
            finally:os.close(config)
            record=("schema=kmj.local.full.daily.v3\n"
                    "source=already_verified_pg_dump_storage_and_config\n"
                    "independent_remote_restore=NOT_ATTESTED\n"
                    "time_utc="+stamp+"\n").encode("ascii")
            new_private_file(work,"RECOVERY-METADATA.txt",record)
            manifest.append(("RECOVERY-METADATA.txt",hashlib.sha256(record).hexdigest()))
            body="".join(f"{sha}  {path}\n" for path,sha in sorted(manifest)).encode("ascii")
            new_private_file(work,"SHA256SUMS",body)
            os.fsync(work)
            # Assert the same exact structure expected by the read-only V3
            # atomic daily publisher before this staging directory can be used.
            digest_again,counts=daily.verify_snapshot(work,expected_uid,{expected_uid})
            if digest_again!=digest:raise Deny("DAILY_SOURCE_AND_MANIFEST_DRIFT")
            os.fsync(work)
        finally:os.close(work)
        os.fsync(stagefd)
    finally:os.close(stagefd)
    return {"private_staging_written":True,
            "preverified_snapshot":True,
            "daily_published":False,
            "offsite_readback_verified":False,
            "independent_restore_verified":False,
            "platform_dump_sha256":digest,
            "files_hashed":len(manifest),
            "copied_bytes":stats["bytes"]}


if __name__=="__main__":
    print("KMJ_V3_DAILY_SOURCE_BUILDER=REVIEW_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
