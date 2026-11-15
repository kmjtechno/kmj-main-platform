#!/usr/bin/python3
"""Review-only, create-only V3 local daily restore-directory publisher.

NOT INSTALLED. NO BACKUP SERVICE, NO POSTGRES QUERY, NO FILE DELETION.
Only publishes an already built/verified *complete* legacy-compatible snapshot
from a separate private STAGING root into the protected daily backup root via
same-filesystem renameat2(RENAME_NOREPLACE). Staging must not be under the
monitored daily root: otherwise incomplete platform.dump could falsely satisfy
health line 25. A trusted owner-approved integration must separately produce
the staged DB, full storage and config and attest SAME-invocation remote SFTP
readback. This library validates caller-provided receipt digest, it does not
authenticate the remote transfer or independently restore any archive.

Only certbot-standard relative config/letsencrypt/live/<lineage> links to
archive/<same-lineage>/<numbered-certificate>.pem may be preserved after
nofollow root-owned target verification and digest match. Other symlinks,
hardlinks/special files remain rejected. Never overwrite or prune.
"""
from __future__ import annotations
import ctypes
import errno
import hashlib
import os
import posixpath
from pathlib import Path
import re
import stat
import sys
import time

STAMP=re.compile(r"20[0-9]{6}T[0-9]{6}Z\Z",re.ASCII)
SHA=re.compile(r"[a-f0-9]{64}\Z",re.ASCII)
TOP_FILES=("platform.dump","app.env","RECOVERY-METADATA.txt","SHA256SUMS")
TOP_DIRS=("platform-storage","config")
STORAGE_DIRS=("app","framework","logs")
CONFIG_DIRS=("letsencrypt","codebridge-stage","sites-available")
MAX_ENTRIES=50000
MAX_BYTES=8*1024**3
MAX_DEPTH=20
MIN_FREE=2*1024**3
RENAME_NOREPLACE=1


class Deny(Exception):
    pass


def private_dir_fd(path,expected_uid):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=expected_uid
            or stat.S_IMODE(s.st_mode)!=0o700):
            raise Deny("ROOT_DIR_UNTRUSTED")
        return fd
    except BaseException:
        os.close(fd)
        raise


def child_dir(fd,name,allowed_uids,mode=0o700):
    handle=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
    try:
        s=os.fstat(handle)
        if not stat.S_ISDIR(s.st_mode) or s.st_uid not in allowed_uids or stat.S_IMODE(s.st_mode)!=mode:
            raise Deny("SNAPSHOT_DIR_UNTRUSTED")
        return handle
    except BaseException:
        os.close(handle)
        raise


def regular(fd,name,allowed_uids,*,restricted=False):
    f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
    try:
        s=os.fstat(f)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid not in allowed_uids
            or s.st_nlink!=1 or s.st_mode&0o022
            or (secret and stat.S_IMODE(s.st_mode)!=0o600)):
            raise Deny("SNAPSHOT_FILE_UNSAFE")
        return f,s
    except BaseException:
        os.close(f)
        raise


def safe_name(name):
    return (isinstance(name,str) and 0<len(name)<=255 and name not in (".","..")
            and "/" not in name and not any(ord(c)<32 or ord(c)==127 for c in name))


CERTBOT_FILES=("cert.pem","chain.pem","fullchain.pem","privkey.pem")
CERTBOT_NOFOLLOW=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC

def certbot_link_target(rootfd,linkfd,relative_dir,name,allowed_uids):
    """Standard same-lineage Certbot live->archive link, never follow symlinks.

    rootfd identifies a pinned Let’s Encrypt directory. Target is checked
    only with O_NOFOLLOW directory/regular-file descriptors and bounded SHA.
    No raw paths, link text or certificate/private key contents are printed.
    """
    parts=relative_dir.split("/")
    if (len(parts)!=2 or parts[0]!="live"
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}",parts[1]) is None
            or name not in CERTBOT_FILES or not allowed_uids):
        raise Deny("CERTBOT_LINK_NOT_STANDARD_LIVE_FILE")
    lineage=parts[1]
    before=os.stat(name,dir_fd=linkfd,follow_symlinks=False)
    if (not stat.S_ISLNK(before.st_mode) or before.st_uid not in allowed_uids
            or before.st_nlink!=1):
        raise Deny("CERTBOT_LINK_METADATA_UNTRUSTED")
    target=os.readlink(name,dir_fd=linkfd)
    stem=name[:-4]
    pattern=rf"\.\./\.\./archive/{re.escape(lineage)}/{stem}[1-9][0-9]{{0,4}}\.pem"
    if (not isinstance(target,str) or len(target)>255
            or re.fullmatch(pattern,target,flags=re.ASCII) is None
            or posixpath.normpath(posixpath.join(relative_dir,target))
            !=target.removeprefix("../../")):
        raise Deny("CERTBOT_LINK_TARGET_NOT_PINNED_IN_TREE")
    base=os.fstat(rootfd)
    if (not stat.S_ISDIR(base.st_mode) or base.st_uid not in allowed_uids
            or base.st_mode&0o022):
        raise Deny("CERTBOT_ROOT_UNTRUSTED")
    handle=os.dup(rootfd)
    try:
        for component in ("archive",lineage):
            nextfd=os.open(component,CERTBOT_NOFOLLOW,dir_fd=handle)
            os.close(handle)
            handle=nextfd
            state=os.fstat(handle)
            if (not stat.S_ISDIR(state.st_mode) or state.st_uid not in allowed_uids
                    or state.st_mode&0o022):
                raise Deny("CERTBOT_TARGET_DIRECTORY_UNTRUSTED")
        filename=target.rsplit("/",1)[-1]
        filefd=os.open(filename,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=handle)
        try:
            original=os.fstat(filefd)
            if (not stat.S_ISREG(original.st_mode)
                    or original.st_uid not in allowed_uids
                    or original.st_nlink!=1 or original.st_mode&0o022
                    or not 1<=original.st_size<=1048576):
                raise Deny("CERTBOT_TARGET_FILE_UNTRUSTED")
            sha=hashlib.sha256()
            size=0
            while True:
                chunk=os.read(filefd,131072)
                if not chunk:break
                size+=len(chunk)
                if size>1048576:
                    raise Deny("CERTBOT_TARGET_FILE_SIZE_LIMIT")
                sha.update(chunk)
            end=os.fstat(filefd)
            if (size!=original.st_size or
                    (original.st_dev,original.st_ino,original.st_size,original.st_mtime_ns,original.st_ctime_ns)
                    !=(end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns)):
                raise Deny("CERTBOT_TARGET_FILE_CHANGED")
        finally:
            os.close(filefd)
    finally:
        os.close(handle)
    after=os.stat(name,dir_fd=linkfd,follow_symlinks=False)
    if ((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)
            !=(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns)
            or not stat.S_ISLNK(after.st_mode)
            or os.readlink(name,dir_fd=linkfd)!=target):
        raise Deny("CERTBOT_LINK_CHANGED_DURING_VERIFY")
    return target,sha.hexdigest()


def snapshot_manifest(fd,uid):
    f,st=regular(fd,"SHA256SUMS",{uid},restricted=True)
    try:
        if not 80<=st.st_size<=65536:
            raise Deny("SNAPSHOT_MANIFEST_SIZE_UNEXPECTED")
        raw=os.read(f,65537)
        if len(raw)!=st.st_size:
            raise Deny("SNAPSHOT_MANIFEST_CHANGED")
    finally:os.close(f)
    seen={}
    for line in raw.decode("ascii",errors="strict").splitlines():
        match=re.fullmatch(r"([a-f0-9]{64})  ([^\r\n]{1,2000})",line)
        if match is None or match.group(2) in seen:
            raise Deny("SNAPSHOT_MANIFEST_INVALID_LINE_OR_DUPLICATE")
        name=match.group(2)
        if name.startswith("/") or ".." in name.split("/") or "\x00" in name:
            raise Deny("SNAPSHOT_MANIFEST_UNSAFE_PATH")
        seen[name]=match.group(1)
    return seen


def walk_tree(fd,allowed_uids,stats,depth=0,*,relative="",certrootfd=None,manifest=None):
    if depth>MAX_DEPTH:
        raise Deny("SNAPSHOT_TREE_TOO_DEEP")
    for name in os.listdir(fd):
        if not safe_name(name):
            raise Deny("SNAPSHOT_UNSAFE_NAME")
        stats["entries"]+=1
        if stats["entries"]>MAX_ENTRIES:
            raise Deny("SNAPSHOT_TREE_ENTRY_LIMIT")
        s=os.stat(name,dir_fd=fd,follow_symlinks=False)
        if stat.S_ISDIR(s.st_mode):
            if s.st_uid not in allowed_uids or s.st_mode&0o022:
                raise Deny("SNAPSHOT_UNTRUSTED_DIRECTORY")
            sub=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            try:
                current=os.fstat(sub)
                if (current.st_dev,current.st_ino)!=(s.st_dev,s.st_ino):
                    raise Deny("SNAPSHOT_DIRECTORY_RACE")
                walk_tree(sub,allowed_uids,stats,depth+1,
                          relative=(relative+"/"+name).lstrip("/"),
                          certrootfd=certrootfd,manifest=manifest)
            finally:
                os.close(sub)
        elif stat.S_ISREG(s.st_mode):
            if s.st_uid not in allowed_uids or s.st_mode&0o022 or s.st_nlink!=1:
                raise Deny("SNAPSHOT_UNTRUSTED_FILE")
            stats["bytes"]+=s.st_size
            if stats["bytes"]>MAX_BYTES:
                raise Deny("SNAPSHOT_BYTES_LIMIT")
        elif stat.S_ISLNK(s.st_mode):
            if (certrootfd is None or manifest is None
                    or not relative.startswith("config/letsencrypt/")):
                raise Deny("SNAPSHOT_LINK_OR_SPECIAL_FILE")
            link_dir=relative[len("config/letsencrypt/"):]
            target,digest=certbot_link_target(
                certrootfd,fd,link_dir,name,allowed_uids)
            if manifest.get(relative+"/"+name)!=digest:
                raise Deny("CERTBOT_LINK_MANIFEST_SHA_MISMATCH")
            stats["certbot_links"]=stats.get("certbot_links",0)+1
        else:
            # Other links, sockets, FIFOs and devices remain blocked.
            raise Deny("SNAPSHOT_LINK_OR_SPECIAL_FILE")


def pgdump_and_manifest(fd,allowed_uids):
    dump,st=regular(fd,"platform.dump",allowed_uids,restricted=True)
    try:
        if st.st_size<32 or st.st_size>MAX_BYTES:
            raise Deny("DATABASE_DUMP_SIZE_INVALID")
        if os.read(dump,5)!=b"PGDMP":
            raise Deny("DATABASE_DUMP_MAGIC_INVALID")
        os.lseek(dump,0,os.SEEK_SET)
        h=hashlib.sha256()
        total=0
        while True:
            chunk=os.read(dump,1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>MAX_BYTES:raise Deny("DATABASE_DUMP_SIZE_LIMIT")
            h.update(chunk)
        if total!=st.st_size:
            raise Deny("DATABASE_DUMP_CHANGED")
        digest=h.hexdigest()
    finally:
        os.close(dump)
    mf,mstat=regular(fd,"SHA256SUMS",allowed_uids,restricted=True)
    try:
        if not 80<=mstat.st_size<=65536:
            raise Deny("MANIFEST_SIZE_UNEXPECTED")
        data=os.read(mf,65537)
        if len(data)!=mstat.st_size:
            raise Deny("MANIFEST_CHANGED")
        matched=False
        for row in data.splitlines():
            if row==f"{digest}  platform.dump".encode():
                matched=True
        if not matched:
            raise Deny("MANIFEST_PLATFORM_DIGEST_MISSING_OR_WRONG")
    finally:
        os.close(mf)
    return digest


def verify_snapshot(fd,expected_uid,allowed_uids):
    if expected_uid not in allowed_uids:
        raise Deny("MISSING_ROOT_OWNERSHIP_GRANT")
    # Exact critical names; additional legacy-compatible files are inspected
    # recursively and must pass the safe tree rules as well.
    for name in TOP_FILES:
        f,s=regular(fd,name,{expected_uid},restricted=True)
        os.close(f)
        if s.st_size==0:raise Deny("REQUIRED_TOP_FILE_EMPTY")
    for name in TOP_DIRS:
        handle=child_dir(fd,name,allowed_uids)
        os.close(handle)
    storage=child_dir(fd,"platform-storage",allowed_uids)
    try:
        for name in STORAGE_DIRS:
            sfd=child_dir(storage,name,allowed_uids)
            os.close(sfd)
    finally:os.close(storage)
    config=child_dir(fd,"config",allowed_uids)
    try:
        for name in CONFIG_DIRS:
            sfd=child_dir(config,name,allowed_uids)
            os.close(sfd)
    finally:os.close(config)
    digest=pgdump_and_manifest(fd,{expected_uid})
    hashes=snapshot_manifest(fd,expected_uid)
    configfd=child_dir(fd,"config",allowed_uids)
    try:
        certfd=child_dir(configfd,"letsencrypt",allowed_uids)
    finally:
        os.close(configfd)
    try:
        counts={"entries":0,"bytes":0,"certbot_links":0}
        walk_tree(fd,allowed_uids,counts,certrootfd=certfd,manifest=hashes)
        return digest,counts
    finally:
        os.close(certfd)


def rename_dir_noreplace(from_fd,name,to_fd,target):
    if not STAMP.fullmatch(target):
        raise Deny("STAMP_INVALID")
    src=os.stat(name,dir_fd=from_fd,follow_symlinks=False)
    dst=os.fstat(to_fd)
    if not stat.S_ISDIR(src.st_mode) or src.st_dev!=dst.st_dev:
        raise Deny("STAGING_NOT_DIRECTORY_OR_SAME_FILESYSTEM")
    try:os.stat(target,dir_fd=to_fd,follow_symlinks=False)
    except FileNotFoundError:pass
    else:raise Deny("DAILY_DESTINATION_ALREADY_EXISTS")
    libc=ctypes.CDLL(None,use_errno=True)
    fn=getattr(libc,"renameat2",None)
    if fn is None:raise Deny("RENAMEAT2_UNAVAILABLE")
    fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    fn.restype=ctypes.c_int
    if fn(from_fd,os.fsencode(name),to_fd,os.fsencode(target),RENAME_NOREPLACE):
        if ctypes.get_errno()==errno.EEXIST:
            raise Deny("DAILY_DESTINATION_RACE_COLLISION")
        raise Deny("DAILY_ATOMIC_RENAME_FAILED")
    os.fsync(to_fd)
    os.fsync(from_fd)


def publish_after_separately_verified_remote_readback(
    staging_root: Path,daily_root: Path,stamp: str,remote_cipher_sha: str,
    *, expected_uid: int=0,allowed_uids: tuple[int,...]|None=None,
    fixture_fault_before_commit: bool=False,
):
    """Commit prebuilt full daily snapshot; remote assertion is CALLER'S job.

    No CLI or implicit trusted receipt conversion is implemented here.
    """
    if (not STAMP.fullmatch(stamp) or SHA.fullmatch(remote_cipher_sha) is None
            or type(expected_uid) is not int):
        raise Deny("INPUT_OR_RECEIPT_SHAPE_INVALID")
    allow=set(allowed_uids or (expected_uid,))
    if type(expected_uid) is not int or not all(type(u) is int and u>=0 for u in allow):
        raise Deny("UNSAFE_OWNER_ALLOWLIST")
    a=Path(staging_root)
    b=Path(daily_root)
    if (not a.is_absolute() or not b.is_absolute() or a==b
        or ".." in a.parts or ".." in b.parts
        or a in b.parents or b in a.parents):
        raise Deny("STAGING_DAILY_ROOTS_NOT_SEPARATED")
    stagefd=private_dir_fd(a,expected_uid)
    try:
        dailyfd=private_dir_fd(b,expected_uid)
        try:
            if os.fstat(stagefd).st_dev!=os.fstat(dailyfd).st_dev:
                raise Deny("STAGING_AND_DAILY_FILESYSTEM_DIFFER")
            folder="stage-"+stamp
            sample=child_dir(stagefd,folder,{expected_uid})
            try:
                src=os.fstat(sample)
                digest,stats=verify_snapshot(sample,expected_uid,allow)
                dumpstat=os.stat("platform.dump",dir_fd=sample,follow_symlinks=False)
            finally:os.close(sample)
            now=time.time()
            if not 0<=now-dumpstat.st_mtime<48*3600:
                raise Deny("DAILY_DUMP_NOT_CURRENT")
            free=os.fstatvfs(dailyfd)
            if free.f_bavail*free.f_frsize<MIN_FREE:
                raise Deny("DAILY_DISK_RESERVE_LOW")
            if fixture_fault_before_commit:
                raise Deny("INJECTED_PRECOMMIT_NO_MUTATION")
            again=os.stat(folder,dir_fd=stagefd,follow_symlinks=False)
            if (src.st_dev,src.st_ino,src.st_mtime_ns)!=(again.st_dev,again.st_ino,again.st_mtime_ns):
                raise Deny("STAGING_CHANGED_BEFORE_COMMIT")
            rename_dir_noreplace(stagefd,folder,dailyfd,stamp)
            published=os.stat(stamp,dir_fd=dailyfd,follow_symlinks=False)
            if (published.st_dev,published.st_ino)!=(src.st_dev,src.st_ino):
                raise Deny("PUBLISHED_DIRECTORY_IDENTITY_CHANGED")
            return {"daily_snapshot_published":True,"platform_dump_sha256":digest,
                    "files_checked":stats["entries"],
                    "remote_cipher_sha_supplied":remote_cipher_sha,
                    "independent_remote_restore_verified":False}
        finally:os.close(dailyfd)
    finally:os.close(stagefd)


if __name__=="__main__":
    print("KMJ_V3_DAILY_PUBLISHER=SOURCE_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
