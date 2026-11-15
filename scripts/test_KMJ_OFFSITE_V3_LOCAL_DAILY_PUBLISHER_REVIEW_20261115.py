"""Disposable fixture tests for source-only daily snapshot atomic publication.

These run without root, live PostgreSQL, real config/env, SFTP or backup units.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

SRC=Path(__file__).with_name("KMJ_OFFSITE_V3_LOCAL_DAILY_PUBLISHER_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_daily_atomic_source_only",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DailySnapshotSourceOnlyFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.staging=self.root/"staging"
        self.daily=self.root/"daily"
        for path in (self.staging,self.daily):
            path.mkdir(mode=0o700)
            path.chmod(0o700)
        self.stamp="20261115T072031Z"
        self.staged=self.staging/("stage-"+self.stamp)
        self.staged.mkdir(mode=0o700)
        self.staged.chmod(0o700)
        self.uid=os.geteuid()
        self.sha="b"*64
        for path in [self.staged/"platform-storage",self.staged/"config"]:
            path.mkdir(mode=0o700);path.chmod(0o700)
        for name in m.STORAGE_DIRS:
            path=self.staged/"platform-storage"/name
            path.mkdir(mode=0o700);path.chmod(0o700)
        for name in m.CONFIG_DIRS:
            path=self.staged/"config"/name
            path.mkdir(mode=0o700);path.chmod(0o700)
        self.dump=self.staged/"platform.dump"
        self.dump.write_bytes(b"PGDMP"+b"fake-disposable-database-bytes"*7)
        self.dump.chmod(0o600)
        self.mkfile("app.env",b"fixture=no-secret-data\n")
        self.mkfile("RECOVERY-METADATA.txt",b"fixture-independent-restore=NOT_VERIFIED\n")
        self.mkfile("SHA256SUMS",
            (hashlib.sha256(self.dump.read_bytes()).hexdigest()+"  platform.dump\n").encode())

    def mkfile(self,relative,body):
        path=self.staged/relative
        path.write_bytes(body)
        path.chmod(0o600)
        return path

    def publish(self,**kw):
        return m.publish_after_separately_verified_remote_readback(
            self.staging,self.daily,self.stamp,self.sha,
            expected_uid=self.uid,allowed_uids=(self.uid,),**kw)

    def test_full_snapshot_atomically_committed_in_daily_root(self):
        expected=hashlib.sha256(self.dump.read_bytes()).hexdigest()
        receipt=self.publish()
        self.assertTrue(receipt["daily_snapshot_published"])
        self.assertEqual(receipt["platform_dump_sha256"],expected)
        self.assertFalse(receipt["independent_remote_restore_verified"])
        self.assertFalse(self.staged.exists())
        target=self.daily/self.stamp
        self.assertEqual((target/"platform.dump").read_bytes(),
                         b"PGDMP"+b"fake-disposable-database-bytes"*7)
        self.assertTrue((target/"platform-storage"/"framework").is_dir())
        self.assertTrue((target/"config"/"codebridge-stage").is_dir())

    def test_duplicate_timestamp_does_not_clobber(self):
        target=self.daily/self.stamp
        target.mkdir(mode=0o700);target.chmod(0o700)
        sentinel=target/"PRESERVE"
        sentinel.write_bytes(b"DO_NOT_TOUCH")
        with self.assertRaisesRegex(m.Deny,"DAILY_DESTINATION_ALREADY_EXISTS"):
            self.publish()
        self.assertEqual(sentinel.read_bytes(),b"DO_NOT_TOUCH")
        self.assertTrue(self.staged.exists())

    def test_fault_before_commit_leaves_daily_unmodified(self):
        with self.assertRaisesRegex(m.Deny,"INJECTED_PRECOMMIT_NO_MUTATION"):
            self.publish(fixture_fault_before_commit=True)
        self.assertTrue(self.staged.exists())
        self.assertFalse((self.daily/self.stamp).exists())

    def test_invalid_pgdmp_magic_denied(self):
        self.dump.write_bytes(b"NOTPG"+b"x"*80)
        with self.assertRaisesRegex(m.Deny,"DATABASE_DUMP_MAGIC_INVALID"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_platform_dump_manifest_digest_required(self):
        self.mkfile("SHA256SUMS",("a"*64+"  platform.dump\n").encode())
        with self.assertRaisesRegex(m.Deny,"MANIFEST_PLATFORM_DIGEST_MISSING_OR_WRONG"):
            self.publish()
        self.assertTrue(self.staged.exists())

    def test_missing_storage_and_config_subdirectories_are_denied(self):
        shutil.rmtree(self.staged/"platform-storage"/"logs")
        with self.assertRaises((OSError,m.Deny)):
            self.publish()
        (self.staged/"platform-storage"/"logs").mkdir(mode=0o700)
        (self.staged/"platform-storage"/"logs").chmod(0o700)
        shutil.rmtree(self.staged/"config"/"codebridge-stage")
        with self.assertRaises((OSError,m.Deny)):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_symlink_within_storage_rejected_nofollow(self):
        (self.staged/"platform-storage"/"app"/"outside").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_LINK_OR_SPECIAL_FILE"):
            self.publish()

    def test_hardlinked_dump_denied(self):
        os.link(self.dump,self.staged/"config"/"dup.dump")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_FILE_UNSAFE"):
            self.publish()

    def test_world_writable_config_directory_denied(self):
        (self.staged/"config"/"letsencrypt").chmod(0o777)
        with self.assertRaises((OSError,m.Deny)):
            self.publish()

    def test_stale_dump_is_rejected_not_healthy(self):
        old=time.time()-5*86400
        os.utime(self.dump,(old,old))
        with self.assertRaisesRegex(m.Deny,"DAILY_DUMP_NOT_CURRENT"):
            self.publish()

    def test_future_dated_dump_is_rejected(self):
        future=time.time()+3600
        os.utime(self.dump,(future,future))
        with self.assertRaisesRegex(m.Deny,"DAILY_DUMP_NOT_CURRENT"):
            self.publish()

    def test_stage_and_health_root_must_be_separate(self):
        with self.assertRaisesRegex(m.Deny,"STAGING_DAILY_ROOTS_NOT_SEPARATED"):
            m.publish_after_separately_verified_remote_readback(
                self.daily,self.daily,self.stamp,self.sha,expected_uid=self.uid)

    def test_symlink_to_staging_root_cannot_follow(self):
        alias=self.root/"staging-symlink"
        alias.symlink_to(self.staging,target_is_directory=True)
        with self.assertRaises(OSError):
            m.publish_after_separately_verified_remote_readback(
                alias,self.daily,self.stamp,self.sha,expected_uid=self.uid)

    def test_bad_remote_receipt_digest_rejected(self):
        with self.assertRaisesRegex(m.Deny,"INPUT_OR_RECEIPT_SHAPE_INVALID"):
            m.publish_after_separately_verified_remote_readback(
                self.staging,self.daily,self.stamp,"B"*64,expected_uid=self.uid)

    def test_low_disk_space_rejected_before_atomic_publish(self):
        class Space:
            f_bavail=0
            f_frsize=4096
        with mock.patch.object(m.os,"fstatvfs",return_value=Space()):
            with self.assertRaisesRegex(m.Deny,"DAILY_DISK_RESERVE_LOW"):
                self.publish()
        self.assertTrue(self.staged.exists())

    def test_regular_legacy_files_are_preserved(self):
        self.mkfile("config/sites-available/custom.conf",b"fixture-conf")
        self.mkfile("platform-storage/logs/old.txt",b"fixture-log")
        self.publish()
        self.assertEqual((self.daily/self.stamp/"config"/"sites-available"/"custom.conf").read_bytes(),b"fixture-conf")
        self.assertEqual((self.daily/self.stamp/"platform-storage"/"logs"/"old.txt").read_bytes(),b"fixture-log")


if __name__=="__main__":
    unittest.main()
