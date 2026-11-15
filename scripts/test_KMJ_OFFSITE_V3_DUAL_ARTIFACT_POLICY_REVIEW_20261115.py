"""Fixture-only tests. No use of actual /var/backups and no scheduled service."""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC=Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_ARTIFACT_POLICY_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_v3_dual_policy",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DualArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/"vault";self.root.mkdir(mode=0o700);self.root.chmod(0o700)
        self.uid=os.geteuid()
        self.fd=m.open_vault(self.root,expected_uid=self.uid)
        self.addCleanup(os.close,self.fd)
        self.stamp="20261111T091303Z";self.hash="a"*64

    def pair(self,stamp):
        cipher=self.root/m.cipher_name(stamp)
        cipher.write_bytes(b"dummy-age-cipher"*10);cipher.chmod(0o600)
        sidecar=self.root/(stamp+".sha256")
        sidecar.write_bytes(m.sidecar_bytes(stamp,hashlib.sha256(cipher.read_bytes()).hexdigest()))
        sidecar.chmod(0o600)
        return cipher,sidecar

    def test_legacy_sidecar_exactly_91_bytes_and_roundtrip(self):
        sidecar=m.sidecar_bytes(self.stamp,self.hash)
        self.assertEqual(len(sidecar),91)
        self.assertEqual(sidecar,(self.hash+"  20261111T091303Z.tar.age\n").encode())
        self.assertEqual(m.parse_legacy_sidecar(self.stamp,sidecar),self.hash)

    def test_reject_one_space_wrong_name_and_uppercase(self):
        good=m.sidecar_bytes(self.stamp,self.hash)
        for candidate in (good.replace(b"  ",b" "),
                          good.replace(b".tar.age",b".age    "),good.upper()):
            with self.subTest(candidate=candidate[:30]),self.assertRaises(m.Deny):
                m.parse_legacy_sidecar(self.stamp,candidate)

    def test_reject_bad_digest_and_stamp(self):
        for digest in ("A"*64,"a"*63,"z"*64,"../oops"):
            with self.assertRaises(m.Deny):m.sidecar_bytes(self.stamp,digest)
        for stamp in ("20260230T000000Z","../../etc","20261111T091303Z-extra"):
            with self.assertRaises(m.Deny):m.sidecar_bytes(stamp,self.hash)

    def test_provenance_separate_from_legacy_sidecar(self):
        data=m.format_metadata(self.stamp,self.hash)
        self.assertIn(b"cipher_format=GOOGLE_X25519_AGE_V2\n",data)
        self.assertIn(b"payload_format=TAR_GZ_4_MEMBERS\n",data)
        self.assertIn(b"remote_restore=NOT_VERIFIED\n",data)
        self.assertEqual(len(m.sidecar_bytes(self.stamp,self.hash)),91)

    def test_inventory_pairs_and_ignores_unrelated(self):
        self.pair(self.stamp);(self.root/"unrelated.txt").write_text("keep")
        report=m.vault_inventory(self.fd,expected_uid=self.uid)
        self.assertEqual(report["paired"],(self.stamp,))
        self.assertEqual(report["other_entries"],1)
        self.assertEqual(report["cipher_without_sidecar"],())
        self.assertEqual(report["sidecar_without_cipher"],())

    def test_orphan_pair_blocks_retention(self):
        self.pair(self.stamp)
        (self.root/(self.stamp+".sha256")).unlink()
        with self.assertRaisesRegex(m.Deny,"VAULT_ORPHAN_REVIEW_REQUIRED"):
            m.plan_retention(self.fd,keep_count=2,expected_uid=self.uid)

    def test_vault_matched_symlink_is_rejected(self):
        (self.root/(self.stamp+".tar.age")).symlink_to("/tmp/fake")
        with self.assertRaisesRegex(m.Deny,"VAULT_MATCHED_ENTRY_UNSAFE"):
            m.vault_inventory(self.fd,expected_uid=self.uid)

    def test_no_retention_delete_and_exact_stamp(self):
        for stamp in ("20261111T091303Z","20261112T091303Z","20261113T091303Z"):
            self.pair(stamp)
        (self.root/"20261110T091303Z.tar.age.extra").write_text("keep")
        self.assertEqual(m.plan_retention(self.fd,keep_count=2,expected_uid=self.uid),
                         ("20261111T091303Z",))
        self.assertTrue((self.root/"20261111T091303Z.tar.age").exists())
        self.assertTrue((self.root/"20261110T091303Z.tar.age.extra").exists())

    def test_invalid_retention_count_rejected(self):
        for n in (0,1,366,-1,True,2.0):
            with self.assertRaisesRegex(m.Deny,"RETENTION_NOT_APPROVED"):
                m.plan_retention(self.fd,keep_count=n,expected_uid=self.uid)

    def test_free_space_guard_rejects_invalid_sizes(self):
        for n in (0,59,-1,True,m.CIPHER_LIMIT+1):
            with self.assertRaisesRegex(m.Deny,"CIPHER_BYTES_NOT_BOUNDED"):
                m.check_free_space(self.fd,n)
        self.assertTrue(m.check_free_space(self.fd,256))

    def test_cipher_read_only_hash(self):
        cipher,_=self.pair(self.stamp)
        sha,size=m.read_private_cipher_hash(cipher,expected_uid=self.uid)
        self.assertEqual(sha,hashlib.sha256(cipher.read_bytes()).hexdigest())
        self.assertEqual(size,cipher.stat().st_size)

    def test_cipher_read_only_hash_rejects_hardlink(self):
        cipher,_=self.pair(self.stamp);os.link(cipher,self.root/"dup")
        with self.assertRaisesRegex(m.Deny,"CIPHER_SOURCE_UNSAFE"):
            m.read_private_cipher_hash(cipher,expected_uid=self.uid)

    @unittest.skipUnless(os.name=="posix","Linux renameat2 only")
    def test_atomic_noreplace_refuses_existing_file(self):
        source_dir=self.root/".stage";source_dir.mkdir(mode=0o700)
        stage=source_dir/"fresh.age";stage.write_bytes(b"a"*128);stage.chmod(0o600)
        destination=self.root/m.cipher_name(self.stamp)
        destination.write_bytes(b"ORIGINAL");destination.chmod(0o600)
        fd=os.open(source_dir,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            with self.assertRaisesRegex(m.Deny,"RENAME_DEST_ALREADY_EXISTS"):
                m.renameat2_noreplace(fd,"fresh.age",self.fd,destination.name)
        finally:os.close(fd)
        self.assertEqual(destination.read_bytes(),b"ORIGINAL")
        self.assertEqual(stage.read_bytes(),b"a"*128)

    @unittest.skipUnless(os.name=="posix","Linux renameat2 only")
    def test_atomic_noreplace_on_fixture_same_filesystem(self):
        source_dir=self.root/".stage";source_dir.mkdir(mode=0o700)
        stage=source_dir/"fresh.age";stage.write_bytes(b"b"*128);stage.chmod(0o600)
        fd=os.open(source_dir,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:m.renameat2_noreplace(fd,"fresh.age",self.fd,m.cipher_name(self.stamp))
        finally:os.close(fd)
        self.assertFalse(stage.exists())
        self.assertEqual((self.root/m.cipher_name(self.stamp)).read_bytes(),b"b"*128)

    def test_main_install_not_available(self):
        with mock.patch.object(m.sys,"argv",["script","--apply"]),\
             mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(m.socket,"gethostname",return_value="KMJ-elite"):
            self.assertEqual(m.main(),2)

if __name__=="__main__":unittest.main()
