"""Offline tests for metadata-only source failure classifier."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock

SRC=Path(__file__).with_name("KMJ_CERTBOT_LINK_METADATA_CLASSIFIER_READONLY_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_certbot_link_meta_readonly",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MetadataFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"root"
        self.root.mkdir(mode=0o700)
        self.live=self.root/"live"
        self.live.mkdir(mode=0o700)
        self.lineage=self.live/"kmj.example.test"
        self.lineage.mkdir(mode=0o700)
        self.uid=os.geteuid()

    def test_metadata_classifier_three_failures(self):
        s=types.SimpleNamespace(st_mode=stat.S_IFLNK|0o777,st_uid=self.uid,st_nlink=1)
        self.assertEqual(m.link_verdict(s,self.uid),"METADATA_PASS")
        s.st_uid+=1
        self.assertEqual(m.link_verdict(s,self.uid),"NONEXPECTED_OWNER")
        s.st_uid-=1;s.st_nlink=2
        self.assertEqual(m.link_verdict(s,self.uid),"LINK_COUNT_NOT_ONE")
        s.st_nlink=1;s.st_mode=stat.S_IFREG|0o600
        self.assertEqual(m.link_verdict(s,self.uid),"NOT_SYMLINK")

    def test_real_disposable_symlinks_without_follow(self):
        (self.lineage/"cert.pem").symlink_to("../../archive/kmj.example.test/cert1.pem")
        (self.lineage/"chain.pem").symlink_to("../../archive/kmj.example.test/chain1.pem")
        (self.lineage/"fullchain.pem").symlink_to("../../archive/kmj.example.test/fullchain1.pem")
        (self.lineage/"privkey.pem").symlink_to("../../archive/kmj.example.test/privkey1.pem")
        result,owners=m.scan(self.root,expected_uid=self.uid)
        self.assertEqual(result["LINEAGES"],1)
        self.assertEqual(result["EXPECTED_ENTRIES"],4)
        self.assertEqual(result["VERDICT_METADATA_PASS"],4)
        self.assertEqual(result["SHAPE_STANDARD_SAME_LINEAGE"],4)
        self.assertEqual(owners[self.uid],4)
        self.assertNotIn("MISSING_EXPECTED_ENTRY",result)

    def test_regular_file_in_live_reports_not_symlink(self):
        (self.lineage/"cert.pem").write_text("fixture",encoding="utf-8")
        results,_=m.scan(self.root,expected_uid=self.uid)
        self.assertEqual(results["VERDICT_NOT_SYMLINK"],1)
        self.assertEqual(results["MISSING_EXPECTED_ENTRY"],3)

    def test_symlink_to_external_is_reported_but_not_followed(self):
        (self.lineage/"cert.pem").symlink_to("/etc/passwd")
        results,_=m.scan(self.root,expected_uid=self.uid)
        self.assertEqual(results["SHAPE_TARGET_ABSOLUTE"],1)
        self.assertEqual(results["VERDICT_METADATA_PASS"],1)

    def test_symlink_live_root_denied_nofollow(self):
        other=self.root/"archive"
        other.mkdir(mode=0o700)
        self.live.rmdir()
        self.live.symlink_to(other,target_is_directory=True)
        with self.assertRaises(OSError):
            m.scan(self.root,expected_uid=self.uid)

    def test_owner_root_guard_fails_closed(self):
        with self.assertRaisesRegex(m.Deny,"ROOT_DIRECTORY_METADATA_UNTRUSTED"):
            m.scan(self.root,expected_uid=self.uid+1)

    def test_target_string_no_traversal(self):
        self.assertEqual(m.target_shape("../../archive/example.test/cert1.pem",
                                        "example.test","cert.pem"),"STANDARD_SAME_LINEAGE")
        self.assertEqual(m.target_shape("../../archive/other.test/cert1.pem",
                                        "example.test","cert.pem"),"TARGET_OTHER_RELATIVE")
        self.assertEqual(m.target_shape("/etc/passwd","example.test","cert.pem"),
                         "TARGET_ABSOLUTE")

    def test_selftest_no_production_root_access(self):
        with mock.patch.object(m,"scan") as scan:
            with mock.patch.object(m.sys,"argv",[str(SRC),"--selftest"]):
                self.assertEqual(m.main(),0)
            scan.assert_not_called()

if __name__=="__main__":
    unittest.main()
