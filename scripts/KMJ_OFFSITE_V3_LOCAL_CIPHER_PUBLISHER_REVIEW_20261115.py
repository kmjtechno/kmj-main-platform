#!/usr/bin/python3
"""Source-only V3 X25519 local ciphertext+SHA sidecar publisher.

NOT INSTALLED / NOT A BACKUP SERVICE / NOT A REMOTE RESTORE ATTESTATION.
An independently reviewed caller must first prove the exact same invocation's
REMOTE_SFTP_SHA_READBACK=PASS and provide its expected cipher SHA and size.
This library only checks equality to those supplied values; it cannot itself
attest a remote operation. Do not wire to V2 service without owner approval.

Bounded root-owned, same-filesystem staging, nofollow, create-only publishes,
fsync before publish, renameat2(RENAME_NOREPLACE) and verified exact legacy
91-byte sidecar. If a crash/fault occurs between cipher and sidecar commits,
the orphan remains visible and retention is blocked; never delete or rewrite
a previous snapshot in this routine. CLI is deliberately unavailable.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys

POLICY_PATH=Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_ARTIFACT_POLICY_REVIEW_20261115.py")
POLICY_SPEC=importlib.util.spec_from_file_location("kmj_v3_pair_policy",POLICY_PATH)
if POLICY_SPEC is None or POLICY_SPEC.loader is None:
    raise RuntimeError("POLICY_IMPORT_UNAVAILABLE")
policy=importlib.util.module_from_spec(POLICY_SPEC)
POLICY_SPEC.loader.exec_module(policy)

SOURCE_DIR_RE=re.compile(r"\.kmj-fresh-x25519-[A-Za-z0-9._-]{1,50}\Z",re.ASCII)
LOCK_NAME=".kmj-v3-local-publish.lock"


class PublishError(Exception):
    pass


def safe_stat(fd,uid,mode,kind):
    s=os.fstat(fd)
    if (s.st_uid!=uid or stat.S_IMODE(s.st_mode)!=mode
            or (kind=="file" and (not stat.S_ISREG(s.st_mode) or s.st_nlink!=1))
            or (kind=="dir" and not stat.S_ISDIR(s.st_mode))):
        raise PublishError("UNTRUSTED_"+kind.upper())
    return s


def root_source_guard(vault,source,uid):
    vault=Path(vault)
    source=Path(source)
    if (not vault.is_absolute() or ".." in vault.parts
            or not source.is_absolute() or ".." in source.parts
            or source.parent.parent!=vault or source.name!="fresh.age"
            or not SOURCE_DIR_RE.fullmatch(source.parent.name)):
        raise PublishError("FRESH_CIPHER_SOURCE_OUTSIDE_PINNED_LAYOUT")
    fd=os.open(source.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        safe_stat(fd,uid,0o700,"dir")
    finally:
        os.close(fd)
    return source


def check_destination_absent(root_fd,name):
    try:
        os.stat(name,dir_fd=root_fd,follow_symlinks=False)
    except FileNotFoundError:
        return
    raise PublishError("DESTINATION_ALREADY_EXISTS")


def create_file(dir_fd,name,content,uid):
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
               0o600,dir_fd=dir_fd)
    try:
        safe_stat(fd,uid,0o600,"file")
        offset=0
        while offset<len(content):
            wrote=os.write(fd,content[offset:])
            if wrote<=0:
                raise PublishError("SHORT_SIDE_CAR_WRITE")
            offset+=wrote
        os.fsync(fd)
    finally:
        os.close(fd)


def stage_cipher(src,dest_fd,uid,expected_sha,expected_bytes):
    srcfd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=safe_stat(srcfd,uid,0o600,"file")
        if before.st_size!=expected_bytes:
            raise PublishError("FRESH_CIPHER_SIZE_DRIFT")
        dst=os.open("fresh.age",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                    0o600,dir_fd=dest_fd)
        try:
            safe_stat(dst,uid,0o600,"file")
            total=0
            sha=hashlib.sha256()
            while True:
                block=os.read(srcfd,1024*1024)
                if not block:
                    break
                total+=len(block)
                if total>policy.CIPHER_LIMIT:
                    raise PublishError("FRESH_CIPHER_SIZE_LIMIT")
                sha.update(block)
                offset=0
                while offset<len(block):
                    sent=os.write(dst,block[offset:])
                    if sent<=0:
                        raise PublishError("SHORT_CIPHER_COPY")
                    offset+=sent
            os.fsync(dst)
        finally:
            os.close(dst)
        after=os.fstat(srcfd)
        original=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
        observed=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
        if original!=observed or total!=expected_bytes or sha.hexdigest()!=expected_sha:
            raise PublishError("FRESH_CIPHER_SOURCE_INTEGRITY_DRIFT")
    finally:
        os.close(srcfd)


def read_sidecar(root_fd,name):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=root_fd)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=91:
            raise PublishError("PUBLISHED_SIDECAR_FORMAT_DRIFT")
        out=os.read(fd,92)
    finally:
        os.close(fd)
    return out


def publish_after_verified_remote_readback(
    vault: Path, fresh_cipher: Path, utc_stamp: str,
    remote_readback_sha: str, remote_readback_bytes: int,
    *, expected_uid: int=0, fixture_fault_after_cipher: bool=False,
):
    """Publish one local cipher+sidecar pair. No recovery or retention in same run.

    The caller must independently authenticate the REMOTE SFTP receipt from
    the SAME invocation and pass its digest/size. This function proves only
    local equivalence to those supplied values, not independent remote restore.
    """
    if (not policy.valid_stamp(utc_stamp)
            or not isinstance(remote_readback_sha,str)
            or policy.SHA256.fullmatch(remote_readback_sha) is None
            or type(remote_readback_bytes) is not int
            or not 60<=remote_readback_bytes<=policy.CIPHER_LIMIT):
        raise PublishError("REMOTE_RECEIPT_ARGUMENTS_INVALID")
    source=root_source_guard(vault,fresh_cipher,expected_uid)
    rootfd=policy.open_vault(Path(vault),expected_uid=expected_uid)
    try:
        existing_sha,existing_size=policy.read_private_cipher_hash(source,expected_uid=expected_uid)
        if (existing_sha,existing_size)!=(remote_readback_sha,remote_readback_bytes):
            raise PublishError("REMOTE_LOCAL_CIPHER_DIGEST_MISMATCH")
        policy.check_free_space(rootfd,remote_readback_bytes)
        ciphername=policy.cipher_name(utc_stamp)
        sidecarname=utc_stamp+".sha256"
        check_destination_absent(rootfd,ciphername)
        check_destination_absent(rootfd,sidecarname)
        lockfd=os.open(LOCK_NAME,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,
                       0o600,dir_fd=rootfd)
        try:
            safe_stat(lockfd,expected_uid,0o600,"file")
            try:
                fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                raise PublishError("CONCURRENT_PUBLISH_LOCKED") from None
            check_destination_absent(rootfd,ciphername)
            check_destination_absent(rootfd,sidecarname)
            stagedirname=".kmj-v3-publish-"+utc_stamp
            os.mkdir(stagedirname,mode=0o700,dir_fd=rootfd)
            os.fsync(rootfd)
            stagefd=os.open(stagedirname,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=rootfd)
            try:
                safe_stat(stagefd,expected_uid,0o700,"dir")
                stage_cipher(source,stagefd,expected_uid,remote_readback_sha,remote_readback_bytes)
                sidecar=policy.sidecar_bytes(utc_stamp,remote_readback_sha)
                create_file(stagefd,"sidecar",sidecar,expected_uid)
                os.fsync(stagefd)
                # Each destination is O_NOFOLLOW and create-only. Crash between
                # these two commits leaves an orphan, never a false pair.
                policy.renameat2_noreplace(stagefd,"fresh.age",rootfd,ciphername)
                if fixture_fault_after_cipher:
                    raise PublishError("INJECTED_AFTER_CIPHER_COMMIT_REVIEW_REQUIRED")
                policy.renameat2_noreplace(stagefd,"sidecar",rootfd,sidecarname)
                actual_sha,size=policy.read_private_cipher_hash(
                    Path(vault)/ciphername,expected_uid=expected_uid)
                if (actual_sha,size)!=(remote_readback_sha,remote_readback_bytes):
                    raise PublishError("POSTCOMMIT_CIPHER_INTEGRITY_FAILED")
                if policy.parse_legacy_sidecar(utc_stamp,read_sidecar(rootfd,sidecarname))!=actual_sha:
                    raise PublishError("POSTCOMMIT_SIDECAR_INTEGRITY_FAILED")
            finally:
                os.close(stagefd)
            os.rmdir(stagedirname,dir_fd=rootfd)  # only our now-empty private stage
            os.fsync(rootfd)
            return {"local_cipher_committed":True,"sidecar_pair_verified":True,
                    "remote_restore_verified":False,"bytes":remote_readback_bytes}
        finally:
            os.close(lockfd)
    finally:
        os.close(rootfd)


if __name__=="__main__":
    # Explicitly no CLI or service entry point. Tests import this module.
    print("KMJ_V3_LOCAL_CIPHER_PUBLISHER=SOURCE_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
