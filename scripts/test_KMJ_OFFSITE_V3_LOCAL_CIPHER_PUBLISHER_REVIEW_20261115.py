"""Disposable fixture-only tests for the V3 local X25519 pair publisher.

Never invokes live backup service, root privileges, network, prod DB or vault.
"""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC=Path(__file__).with_name("KMJ_OFFSITE_V3_LOCAL_CIPHER_PUBLISHER_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_v3_local_publisher",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CipherLocalPublishFixtures(unittest.TestCase):
    def setUp(self):
        self.sandbox=tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.vault=Path(self.sandbox.name)/"vault"
        self.vault.mkdir(mode=0o700)
        self.vault.chmod(0o700)
        self.work=Path(tempfile.mkdtemp(prefix=".kmj-fresh-x25519-",dir=self.vault))
        self.work.chmod(0o700)
        self.src=self.work/"fresh.age"
        self.payload=b"age-encrypted-v2-fixture-not-a-real-cipher"*8
        self.src.write_bytes(self.payload)
        self.src.chmod(0o600)
        self.sha=hashlib.sha256(self.payload).hexdigest()
        self.stamp="20261115T071512Z"
        self.uid=os.geteuid()

    def publish(self,**kwargs):
        return m.publish_after_verified_remote_readback(
            self.vault,self.src,self.stamp,self.sha,len(self.payload),
            expected_uid=self.uid,**kwargs)

    def test_pair_committed_after_digest_match_and_source_preserved(self):
        result=self.publish()
        self.assertEqual(result["bytes"],len(self.payload))
        self.assertTrue(result["local_cipher_committed"])
        self.assertTrue(result["sidecar_pair_verified"])
        self.assertFalse(result["remote_restore_verified"])
        self.assertEqual(self.src.read_bytes(),self.payload)
        cipher=self.vault/(self.stamp+".tar.age")
        sidecar=self.vault/(self.stamp+".sha256")
        self.assertEqual(cipher.read_bytes(),self.payload)
        self.assertEqual(len(sidecar.read_bytes()),91)
        self.assertEqual(sidecar.read_bytes(),m.policy.sidecar_bytes(self.stamp,self.sha))
        fd=m.policy.open_vault(self.vault,expected_uid=self.uid)
        try:
            self.assertEqual(
                m.policy.vault_inventory(fd,expected_uid=self.uid)["paired"],
                (self.stamp,),
            )
        finally:
            os.close(fd)
        self.assertFalse((self.vault/(".kmj-v3-publish-"+self.stamp)).exists())

    def test_wrong_remote_hash_refuses_without_new_pair(self):
        with self.assertRaisesRegex(m.PublishError,"REMOTE_LOCAL_CIPHER_DIGEST_MISMATCH"):
            m.publish_after_verified_remote_readback(
                self.vault,self.src,self.stamp,"a"*64,len(self.payload),expected_uid=self.uid)
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())

    def test_wrong_remote_length_refuses_without_new_pair(self):
        with self.assertRaisesRegex(m.PublishError,"REMOTE_LOCAL_CIPHER_DIGEST_MISMATCH"):
            m.publish_after_verified_remote_readback(
                self.vault,self.src,self.stamp,self.sha,len(self.payload)-1,expected_uid=self.uid)
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())

    def test_bad_stamp_or_bad_digest_is_denied_before_staging(self):
        for stamp in ("20260230T000000Z","../../etc","20261115T071512Z-extra"):
            with self.subTest(stamp=stamp),self.assertRaisesRegex(m.PublishError,"REMOTE_RECEIPT_ARGUMENTS_INVALID"):
                m.publish_after_verified_remote_readback(
                    self.vault,self.src,stamp,self.sha,len(self.payload),expected_uid=self.uid)
        with self.assertRaisesRegex(m.PublishError,"REMOTE_RECEIPT_ARGUMENTS_INVALID"):
            m.publish_after_verified_remote_readback(
                self.vault,self.src,self.stamp,self.sha.upper(),len(self.payload),expected_uid=self.uid)

    def test_duplicate_cipher_never_overwritten(self):
        old=self.vault/(self.stamp+".tar.age")
        old.write_bytes(b"OLD_CIPHER_DO_NOT_TOUCH");old.chmod(0o600)
        with self.assertRaisesRegex(m.PublishError,"DESTINATION_ALREADY_EXISTS"):
            self.publish()
        self.assertEqual(old.read_bytes(),b"OLD_CIPHER_DO_NOT_TOUCH")

    def test_duplicate_sidecar_never_overwritten(self):
        old=self.vault/(self.stamp+".sha256")
        old.write_bytes(b"OLD_SIDECAR_DO_NOT_TOUCH");old.chmod(0o600)
        with self.assertRaisesRegex(m.PublishError,"DESTINATION_ALREADY_EXISTS"):
            self.publish()
        self.assertEqual(old.read_bytes(),b"OLD_SIDECAR_DO_NOT_TOUCH")

    def test_crash_after_cipher_leaves_detectable_orphan_no_silent_success(self):
        with self.assertRaisesRegex(m.PublishError,"INJECTED_AFTER_CIPHER_COMMIT_REVIEW_REQUIRED"):
            self.publish(fixture_fault_after_cipher=True)
        self.assertTrue((self.vault/(self.stamp+".tar.age")).is_file())
        self.assertFalse((self.vault/(self.stamp+".sha256")).exists())
        fd=m.policy.open_vault(self.vault,expected_uid=self.uid)
        try:
            inventory=m.policy.vault_inventory(fd,expected_uid=self.uid)
            self.assertEqual(inventory["cipher_without_sidecar"],(self.stamp,))
            with self.assertRaisesRegex(m.policy.Deny,"VAULT_ORPHAN_REVIEW_REQUIRED"):
                m.policy.plan_retention(fd,keep_count=2,expected_uid=self.uid)
        finally:os.close(fd)
        self.assertTrue((self.vault/(".kmj-v3-publish-"+self.stamp)).is_dir())

    def test_symlink_and_hardlinked_source_rejected(self):
        self.src.unlink()
        target=self.work/"other.age"
        target.write_bytes(self.payload);target.chmod(0o600)
        self.src.symlink_to(target)
        with self.assertRaises((OSError,m.PublishError,m.policy.Deny)):
            self.publish()
        self.src.unlink()
        os.link(target,self.src)
        with self.assertRaises((OSError,m.PublishError,m.policy.Deny)):
            self.publish()

    def test_unsafe_source_or_parent_mode_rejected(self):
        self.src.chmod(0o644)
        with self.assertRaises((OSError,m.PublishError,m.policy.Deny)):
            self.publish()
        self.src.chmod(0o600)
        self.work.chmod(0o777)
        with self.assertRaisesRegex(m.PublishError,"UNTRUSTED_DIR"):
            self.publish()

    def test_source_outside_exact_v2_ephemeral_layout_rejected(self):
        different=self.vault/"standalone.age"
        different.write_bytes(self.payload);different.chmod(0o600)
        with self.assertRaisesRegex(m.PublishError,"FRESH_CIPHER_SOURCE_OUTSIDE_PINNED_LAYOUT"):
            m.publish_after_verified_remote_readback(
                self.vault,different,self.stamp,self.sha,len(self.payload),expected_uid=self.uid)

    def test_low_free_space_guard_fails_without_publish(self):
        with mock.patch.object(m.policy,"check_free_space",side_effect=m.policy.Deny("SPACE_RESERVE_FAILED")):
            with self.assertRaisesRegex(m.policy.Deny,"SPACE_RESERVE_FAILED"):
                self.publish()
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())


if __name__=="__main__":
    unittest.main()
