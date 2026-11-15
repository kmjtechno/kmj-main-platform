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
        self.mkfile("SHA256SUMS", (
            hashlib.sha256(self.dump.read_bytes()).hexdigest()+"  platform.dump\n"+
            hashlib.sha256((self.staged/"app.env").read_bytes()).hexdigest()+"  app.env\n"+
            hashlib.sha256((self.staged/"RECOVERY-METADATA.txt").read_bytes()).hexdigest()+
            "  RECOVERY-METADATA.txt\n"
        ).encode())

    def mkfile(self,relative,body):
        path=self.staged/relative
        path.write_bytes(body)
        path.chmod(0o600)
        manifest=self.staged/"SHA256SUMS"
        if relative!="SHA256SUMS" and manifest.is_file():
            with manifest.open("a",encoding="ascii") as sink:
                sink.write(hashlib.sha256(body).hexdigest()+"  "+relative+"\n")
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

    def certbot_fixture(self):
        base=self.staged/"config"/"letsencrypt"
        lineage="kmj-example.test"
        archive=base/"archive"/lineage
        live=base/"live"/lineage
        archive.mkdir(parents=True,mode=0o700)
        live.mkdir(parents=True,mode=0o700)
        archive.chmod(0o700)
        live.chmod(0o700)
        body=b"offline-certbot-archive-fixture"
        target=self.mkfile("config/letsencrypt/archive/"+lineage+"/cert1.pem",body)
        link=live/"cert.pem"
        link.symlink_to("../../archive/"+lineage+"/cert1.pem")
        digest=hashlib.sha256(body).hexdigest()
        manifest=self.staged/"SHA256SUMS"
        prior=manifest.read_text()
        manifest.write_text(
            prior+digest+"  config/letsencrypt/live/"+lineage+"/cert.pem\n",
            encoding="ascii")
        manifest.chmod(0o600)
        return link,target

    def test_certbot_link_preserved_across_atomic_publication(self):
        link,target=self.certbot_fixture()
        result=self.publish()
        self.assertTrue(result["daily_snapshot_published"])
        copied=self.daily/self.stamp/"config"/"letsencrypt"/"live"/"kmj-example.test"/"cert.pem"
        self.assertTrue(copied.is_symlink())
        self.assertEqual(os.readlink(copied),"../../archive/kmj-example.test/cert1.pem")
        self.assertEqual(copied.read_bytes(),b"offline-certbot-archive-fixture")
        self.assertFalse(target.exists())

    def test_certbot_symlink_tampered_manifest_blocks_publication(self):
        link,_=self.certbot_fixture()
        manifest=self.staged/"SHA256SUMS"
        original=manifest.read_text()
        manifest.write_text(original.replace(
            hashlib.sha256(b"offline-certbot-archive-fixture").hexdigest()
            +"  config/letsencrypt/live/kmj-example.test/cert.pem",
            "a"*64+"  config/letsencrypt/live/kmj-example.test/cert.pem"),
            encoding="ascii")
        manifest.chmod(0o600)
        with self.assertRaisesRegex(m.Deny,"CERTBOT_LINK_MANIFEST_SHA_MISMATCH"):
            self.publish()
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.daily/self.stamp).exists())

    def test_certbot_bad_link_target_never_published(self):
        for bad in ("/etc/passwd","../../../../etc/passwd",
                    "../../archive/other-lineage/cert1.pem",
                    "../../archive/kmj-example.test/cert999999.pem"):
            with self.subTest(bad=bad):
                if not (self.staged/"config"/"letsencrypt"/"live").exists():
                    self.certbot_fixture()
                link=self.staged/"config"/"letsencrypt"/"live"/"kmj-example.test"/"cert.pem"
                link.unlink()
                link.symlink_to(bad)
                with self.assertRaisesRegex(m.Deny,"CERTBOT_LINK_TARGET_NOT_PINNED_IN_TREE"):
                    self.publish()
                self.assertFalse((self.daily/self.stamp).exists())

    def test_certbot_dangling_target_never_published(self):
        link,target=self.certbot_fixture()
        target.unlink()
        with self.assertRaises(FileNotFoundError):
            self.publish()
        self.assertTrue(link.is_symlink())
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

    def test_modified_app_env_after_manifest_is_rejected(self):
        env=self.staged/"app.env"
        env.write_bytes(b"fixture-changed-after-manifest\n")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_FILE_HASH_MISMATCH"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_modified_optional_storage_file_is_rejected(self):
        path=self.mkfile("platform-storage/logs/old.txt",b"original")
        path.write_bytes(b"changed-content")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_FILE_HASH_MISMATCH"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_unlisted_file_is_rejected(self):
        rogue=self.staged/"platform-storage"/"app"/"unlisted.txt"
        rogue.write_bytes(b"this file has no manifest row")
        rogue.chmod(0o600)
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_MANIFEST_UNLISTED_FILE"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_manifest_orphan_reference_is_rejected(self):
        manifest=self.staged/"SHA256SUMS"
        with manifest.open("a",encoding="ascii") as sink:
            sink.write("b"*64+"  platform-storage/app/missing.txt\n")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_MANIFEST_COVERAGE_INCOMPLETE"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_manifest_cannot_self_reference(self):
        manifest=self.staged/"SHA256SUMS"
        with manifest.open("a",encoding="ascii") as sink:
            sink.write("a"*64+"  SHA256SUMS\n")
        with self.assertRaisesRegex(m.Deny,"SNAPSHOT_MANIFEST_COVERAGE_INCOMPLETE"):
            self.publish()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_regular_legacy_files_are_preserved(self):
        self.mkfile("config/sites-available/custom.conf",b"fixture-conf")
        self.mkfile("platform-storage/logs/old.txt",b"fixture-log")
        self.publish()
        self.assertEqual((self.daily/self.stamp/"config"/"sites-available"/"custom.conf").read_bytes(),b"fixture-conf")
        self.assertEqual((self.daily/self.stamp/"platform-storage"/"logs"/"old.txt").read_bytes(),b"fixture-log")


if __name__=="__main__":
    unittest.main()
