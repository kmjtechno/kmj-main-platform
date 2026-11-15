#!/usr/bin/python3
"""V3 source-review ONLY: order an authenticated SFTP transfer before local commits.

NOT AN INSTALLER, NO CLI, NO SCHEDULE, NO LIVE CREDENTIALS OR TRANSPORT.
Production caller MUST bind transport to the SHA-pinned, root-admitted V2
transport inside an owner-signed V3 scheduled run. Supplying a fake transport
here is a test injection, NOT an independently authenticated remote receipt.

This source verifies that local publishing cannot begin before the SAME
function call to transport.transfer returns normally (V2 transfer checks upload,
remote SHA-256 readback and final readback). It checks the current release
before/after that call, then publishes cipher+sidecar before the daily snapshot.
No existing backup is overwritten or deleted, no retention, no health edits.
A partial commit remains visible and blocks transaction completion; no false
"all artifacts backed up" assertion or independent remote restore assertion.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import time

DIR=Path(__file__).parent


def admitted_module(filename, label):
    # Review-only import; signed owner installation must verify pinned byte
    # digests, file modes and parent chains before calling any of these.
    path=DIR/filename
    spec=importlib.util.spec_from_file_location(label,path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REVIEW_MODULE_NOT_FOUND")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pair=admitted_module(
    "KMJ_OFFSITE_V3_LOCAL_CIPHER_PUBLISHER_REVIEW_20261115.py",
    "kmj_v3_local_cipher_publisher_review",
)
daily=admitted_module(
    "KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py",
    "kmj_v3_daily_publisher_review",
)
policy=pair.policy


class Deny(Exception):
    pass


class IncompleteTransaction(Deny):
    def __init__(self,phase,reason):
        self.phase=phase
        self.reason=reason
        super().__init__("INCOMPLETE_"+phase)


def _fresh_source_and_daily_preflight(
    vault, cipher, stage_root, daily_root, stamp, owner_uid
):
    if (type(owner_uid) is not int or owner_uid<0
            or not isinstance(stamp,str) or not policy.valid_stamp(stamp)):
        raise Deny("TRANSACTION_INPUTS_UNVERIFIED")
    source=pair.root_source_guard(vault,cipher,owner_uid)
    cipher_hash,cipher_bytes=policy.read_private_cipher_hash(
        source,expected_uid=owner_uid,
    )
    stage_root=Path(stage_root)
    daily_root=Path(daily_root)
    if (not stage_root.is_absolute() or not daily_root.is_absolute()
            or stage_root==daily_root or stage_root in daily_root.parents
            or daily_root in stage_root.parents or ".." in stage_root.parts
            or ".." in daily_root.parts):
        raise Deny("DAILY_AND_STAGE_ROOTS_NOT_SEPARATED")
    stage_fd=daily.private_dir_fd(stage_root,owner_uid)
    try:
        daily_fd=daily.private_dir_fd(daily_root,owner_uid)
        try:
            if os.fstat(stage_fd).st_dev!=os.fstat(daily_fd).st_dev:
                raise Deny("DAILY_STAGE_NOT_SAME_FILESYSTEM")
            # A completed atomic publish has consumed its staging directory.
            # Reject an already-published UTC stamp BEFORE opening the stage;
            # report the real collision, never interpret it as a missing backup.
            try:
                os.stat(stamp,dir_fd=daily_fd,follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise Deny("DAILY_TIMESTAMP_ALREADY_PUBLISHED")
            staging_name="stage-"+stamp
            snapshot_fd=daily.child_dir(stage_fd,staging_name,{owner_uid})
            try:
                digest,counts=daily.verify_snapshot(
                    snapshot_fd,owner_uid,{owner_uid},
                )
                if counts["entries"]<6:
                    raise Deny("DAILY_SNAPSHOT_TOO_SMALL")
                dump=os.stat("platform.dump",dir_fd=snapshot_fd,
                             follow_symlinks=False)
                age=time.time()-dump.st_mtime
                if not 0<=age<48*3600:
                    raise Deny("DAILY_PGDMP_NOT_FRESH")
            finally:
                os.close(snapshot_fd)
            space=os.fstatvfs(daily_fd)
            if space.f_bavail*space.f_frsize<daily.MIN_FREE:
                raise Deny("DAILY_FREE_SPACE_INSUFFICIENT")
            try:
                os.stat(stamp,dir_fd=daily_fd,follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise Deny("DAILY_TIMESTAMP_ALREADY_PUBLISHED")
        finally:
            os.close(daily_fd)
    finally:
        os.close(stage_fd)
    vault_fd=policy.open_vault(Path(vault),expected_uid=owner_uid)
    try:
        policy.check_free_space(vault_fd,cipher_bytes)
        # Fail before invoking remote SFTP if final local artifact names collide.
        pair.check_destination_absent(vault_fd,policy.cipher_name(stamp))
        pair.check_destination_absent(vault_fd,stamp+".sha256")
    finally:
        os.close(vault_fd)
    return source,cipher_hash,cipher_bytes,digest


def commit_after_same_invocation_v2_readback(
    *,
    transport,
    pinned_live_release_probe,
    expected_release,
    vault,
    fresh_cipher,
    stage_root,
    daily_root,
    stamp,
    expected_uid=0,
):
    """SOURCE-ONLY integration boundary; cannot authenticate passed transport.

    For real usage the owner-signed V3 entrypoint must establish and verify
    the pinned V2 implementation + transport + release identities before
    this function. Tests inject a simulated transport to check ordering.
    """
    if not callable(pinned_live_release_probe) or not expected_release:
        raise Deny("TRUSTED_RELEASE_PROBE_NOT_SUPPLIED")
    if pinned_live_release_probe()!=expected_release:
        raise Deny("LIVE_RELEASE_CHANGED_BEFORE_TRANSFER")
    path,sha,nbytes,pg_sha=_fresh_source_and_daily_preflight(
        vault,fresh_cipher,stage_root,daily_root,stamp,expected_uid,
    )
    if pinned_live_release_probe()!=expected_release:
        raise Deny("LIVE_RELEASE_CHANGED_DURING_PREFLIGHT")
    if not callable(getattr(transport,"transfer",None)):
        raise Deny("V2_TRANSPORT_UNAVAILABLE")
    if not callable(getattr(transport,"digest_cipher",None)):
        raise Deny("V2_DIGEST_UNAVAILABLE")
    if not callable(getattr(transport,"host_key",None)):
        raise Deny("V2_HOSTKEY_UNAVAILABLE")
    observed=transport.digest_cipher(path)
    if observed!=sha:
        raise Deny("TRANSPORT_CIPHER_SHA_MISMATCH")
    hostline=transport.host_key()
    # The only point that can establish SAME-RUN remote readback success:
    # V2 transfer() raises unless the remote SHA and final object pass.
    transfer_result=transport.transfer(path,sha,hostline)
    if transfer_result is not None:
        raise Deny("V2_TRANSFER_RETURN_CONTRACT_CHANGED")
    if pinned_live_release_probe()!=expected_release:
        raise IncompleteTransaction("REMOTE_ONLY","LIVE_RELEASE_CHANGED_AFTER_READBACK")
    phase="REMOTE_VERIFIED_LOCAL_NOT_COMMITTED"
    try:
        receipt=pair.publish_after_verified_remote_readback(
            Path(vault),path,stamp,sha,nbytes,expected_uid=expected_uid,
        )
        if receipt.get("sidecar_pair_verified") is not True:
            raise Deny("LOCAL_CIPHER_SIDECAR_RECEIPT_INVALID")
        phase="REMOTE_AND_CIPHER_PAIR_COMMITTED"
        if pinned_live_release_probe()!=expected_release:
            raise Deny("LIVE_RELEASE_CHANGED_BEFORE_DAILY_COMMIT")
        daily_receipt=daily.publish_after_separately_verified_remote_readback(
            Path(stage_root),Path(daily_root),stamp,sha,
            expected_uid=expected_uid,allowed_uids=(expected_uid,),
        )
        if daily_receipt.get("daily_snapshot_published") is not True:
            raise Deny("DAILY_COMMIT_RECEIPT_INVALID")
        if daily_receipt.get("platform_dump_sha256")!=pg_sha:
            raise Deny("DAILY_POSTCOMMIT_HASH_DRIFT")
        # A release change during the final atomic daily publication must
        # never be returned as an all-green completed backup. Both local
        # artifacts now exist, so preserve them for owner reconciliation.
        phase="REMOTE_CIPHER_AND_DAILY_COMMITTED_RELEASE_UNVERIFIED"
        if pinned_live_release_probe()!=expected_release:
            raise Deny("LIVE_RELEASE_CHANGED_AFTER_DAILY_COMMIT")
    except Exception as exc:
        # Never delete an old/new local artifact, remote object or stage.
        # An owner-audited recovery state machine must explicitly reconcile
        # any remote-only or local-pair-only crash window before retry.
        raise IncompleteTransaction(phase,type(exc).__name__) from None
    return {
        "remote_sha_readback_same_invocation":True,
        "local_cipher_sidecar_verified":True,
        "local_daily_snapshot_verified":True,
        "local_complete":True,
        "independent_remote_decrypt_restore_verified":False,
        "remote_cipher_sha256":sha,
        "platform_dump_sha256":pg_sha,
    }


if __name__=="__main__":
    print("KMJ_V3_TRANSFER_BOUND_TRANSACTION=SOURCE_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
