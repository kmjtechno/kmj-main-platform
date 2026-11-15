"""Disposable fixtures for V3 complete local daily staging builder; no live sources."""
from __future__ import annotations
import datetime as dt
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=Path(__file__).parent
SOURCE=HERE/"KMJ_OFFSITE_V3_DAILY_SOURCE_BUILDER_REVIEW_20261115.py"
spec=importlib.util.spec_from_file_location("kmj_daily_staging_review",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CompleteDailyStagingFixtures(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.staging=base/"staging"
        self.daily=base/"daily"
        self.storage=base/"platform-storage"
        self.cfgbase=base/"configuration"
        for root in (self.staging,self.daily,self.storage,self.cfgbase):
            root.mkdir(mode=0o700)
            root.chmod(0o700)
        self.cfg={}
        for name in m.CONFIG:
            p=self.cfgbase/name
            p.mkdir(mode=0o700)
            p.chmod(0o700)
            self.cfg[name]=p
            self.file(p/"fixture.conf",b"offline-config-"+name.encode())
        for name in m.STORAGE:
            p=self.storage/name
            p.mkdir(mode=0o700)
            p.chmod(0o700)
            self.file(p/"content.txt",b"offline-storage-"+name.encode())
        self.dump=self.file(base/"database.dump",b"PGDMP"+b"offline-dump-fixture"*8)
        self.env=self.file(base/"app.env",b"TEST_ONLY_FROZEN_ENV=1\n")
        self.stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.uid=os.geteuid()

    def file(self,path,body):
        path.write_bytes(body)
        path.chmod(0o600)
        return path

    def build(self,**kwargs):
        return m.build_preverified_snapshot(
            self.staging,self.daily,self.stamp,self.dump,self.storage,
            self.cfg,self.env,expected_uid=self.uid,storage_owner_uid=self.uid,
            **kwargs,
        )

    def snapshot(self):
        return self.staging/("stage-"+self.stamp)

    def test_complete_legacy_layout_prepared_outside_monitored_daily_root(self):
        record=self.build()
        self.assertTrue(record["private_staging_written"])
        self.assertFalse(record["daily_published"])
        self.assertFalse(record["offsite_readback_verified"])
        self.assertFalse(record["independent_restore_verified"])
        self.assertFalse((self.daily/self.stamp).exists())
        candidate=self.snapshot()
        self.assertEqual((candidate/"platform.dump").read_bytes(),self.dump.read_bytes())
        self.assertEqual((candidate/"app.env").read_bytes(),self.env.read_bytes())
        self.assertTrue((candidate/"platform-storage"/"framework"/"content.txt").exists())
        self.assertTrue((candidate/"config"/"sites-available"/"fixture.conf").exists())
        sha=hashlib.sha256(self.dump.read_bytes()).hexdigest()
        self.assertIn(f"{sha}  platform.dump\n", (candidate/"SHA256SUMS").read_text())
        fd=m.daily.private_dir_fd(candidate,self.uid)
        try:
            check,counts=m.daily.verify_snapshot(fd,self.uid,{self.uid})
            self.assertEqual(check,sha)
            self.assertGreater(counts["entries"],10)
        finally:os.close(fd)

    def test_build_then_atomic_publish_in_disposable_daily_root(self):
        self.build()
        receipt=m.daily.publish_after_separately_verified_remote_readback(
            self.staging,self.daily,self.stamp,"a"*64,
            expected_uid=self.uid,allowed_uids=(self.uid,),
        )
        self.assertTrue(receipt["daily_snapshot_published"])
        self.assertFalse(receipt["independent_remote_restore_verified"])
        self.assertFalse(self.snapshot().exists())
        self.assertTrue((self.daily/self.stamp/"platform.dump").is_file())

    def test_duplicate_stage_denied_without_overwrite(self):
        first=self.build()
        expected=(self.snapshot()/"platform.dump").read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual((self.snapshot()/"platform.dump").read_bytes(),expected)
        self.assertTrue(first["private_staging_written"])

    def test_partial_fault_keeps_stage_outside_health_root(self):
        with self.assertRaisesRegex(m.Deny,"INJECTED_PARTIAL_STAGING_NO_HEALTH_CREDIT"):
            self.build(fixture_fault_after_dump=True)
        self.assertTrue((self.snapshot()/"platform.dump").is_file())
        self.assertFalse((self.daily/self.stamp).exists())

    def test_source_dump_must_be_custom_pgdmp(self):
        self.dump.write_bytes(b"TEXT"+b"not-a-pgdump"*9)
        with self.assertRaisesRegex(m.Deny,"SOURCE_PGDMP_MAGIC_INVALID"):
            self.build()
        self.assertFalse(self.snapshot().exists())

    def test_config_matrix_must_be_complete(self):
        self.cfg.pop("letsencrypt")
        with self.assertRaisesRegex(m.Deny,"CONFIG_SOURCE_MATRIX_INCOMPLETE"):
            self.build()
        self.assertFalse(self.snapshot().exists())

    def test_symlink_inside_platform_storage_blocked(self):
        (self.storage/"app"/"jump").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(m.Deny,"SOURCE_LINK_OR_SPECIAL_ENTRY"):
            self.build()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_intermediate_symlink_in_config_parent_is_denied(self):
        alias=self.root_alias()
        self.cfg["letsencrypt"]=alias/"letsencrypt"
        with self.assertRaisesRegex(m.Deny,"SOURCE_PATH_COMPONENT_NOT_TRUSTED"):
            self.build()
        self.assertFalse((self.daily/self.stamp).exists())

    def root_alias(self):
        alias=Path(self.temp.name)/"config-parent-alias"
        alias.symlink_to(self.cfgbase,target_is_directory=True)
        return alias

    def test_world_writable_intermediate_parent_denied(self):
        outer=Path(self.temp.name)/"public-config-base"
        outer.mkdir(mode=0o700)
        actual=outer/"allowed"
        actual.mkdir(mode=0o700)
        config=actual/"sites-available"
        config.mkdir(mode=0o700)
        outer.chmod(0o777)
        self.cfg["sites-available"]=config
        with self.assertRaisesRegex(m.Deny,"SOURCE_DIRECTORY_MODE_OR_OWNER"):
            self.build()
        self.assertFalse((self.daily/self.stamp).exists())

    def test_intermediate_symlink_in_dump_source_is_denied(self):
        alias=Path(self.temp.name)/"dump-parent-alias"
        alias.symlink_to(Path(self.temp.name),target_is_directory=True)
        self.dump=alias/"database.dump"
        with self.assertRaisesRegex(m.Deny,"SOURCE_PATH_COMPONENT_NOT_TRUSTED"):
            self.build()
        self.assertFalse(self.snapshot().exists())

    def test_hardlink_inside_config_denied(self):
        target=self.cfg["sites-available"]/"fixture.conf"
        os.link(target,self.cfg["sites-available"]/"again.conf")
        with self.assertRaisesRegex(m.Deny,"SOURCE_FILE_MODE_OWNER_OR_LINK"):
            self.build()

    def test_world_writable_config_denied(self):
        self.cfg["codebridge-stage"].chmod(0o777)
        with self.assertRaisesRegex(m.Deny,"SOURCE_DIRECTORY_MODE_OR_OWNER"):
            self.build()

    def test_world_readable_env_not_allowed(self):
        self.env.chmod(0o644)
        with self.assertRaisesRegex(m.Deny,"SOURCE_FILE_MODE_OWNER_OR_LINK"):
            self.build()

    def test_missing_storage_subfolder_denied(self):
        shutil.rmtree(self.storage/"logs")
        with self.assertRaises((FileNotFoundError,m.Deny)):
            self.build()

    def test_stage_cannot_be_inside_daily(self):
        inside=self.daily/"private-stage"
        inside.mkdir(mode=0o700)
        with self.assertRaisesRegex(m.Deny,"STAGING_ROOT_INSIDE_HEALTH_MONITOR"):
            m.build_preverified_snapshot(
                inside,self.daily,self.stamp,self.dump,self.storage,self.cfg,
                self.env,expected_uid=self.uid,storage_owner_uid=self.uid,
            )

    def test_no_remote_receipt_or_implicit_install_interface(self):
        self.assertFalse(hasattr(m,"install"))
        self.assertFalse(hasattr(m,"run_scheduled"))
        self.assertFalse(hasattr(m,"verify_remote_readback"))
        self.assertEqual(m.build_preverified_snapshot.__name__,"build_preverified_snapshot")

    def test_reject_unsafe_special_storage_entry(self):
        import socket
        sock=socket.socket(socket.AF_UNIX)
        try:
            sock.bind(str(self.storage/"logs"/"special.sock"))
            with self.assertRaisesRegex(m.Deny,"SOURCE_LINK_OR_SPECIAL_ENTRY"):
                self.build()
        finally:sock.close()


if __name__=="__main__":
    unittest.main()
