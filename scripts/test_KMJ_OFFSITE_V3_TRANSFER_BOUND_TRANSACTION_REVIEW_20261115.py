"""Disposable transaction-order and crash-window tests for V3 source-only wiring.

No real network or SFTP, no production service, no root, no live credentials.
FakeTransport is deliberately NOT trusted production authentication evidence.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).parent
SRC=HERE/"KMJ_OFFSITE_V3_TRANSFER_BOUND_TRANSACTION_REVIEW_20261115.py"
spec=importlib.util.spec_from_file_location("kmj_v3_transfer_transaction_review",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeTransport:
    def __init__(self,fixture):
        self.fixture=fixture
        self.calls=[]
        self.error=None
        self.digest_override=None
        self.return_value=None
        self.after_transfer=None

    def digest_cipher(self,path):
        self.calls.append("digest")
        return self.digest_override or self.fixture.cipher_sha

    def host_key(self):
        self.calls.append("host_key")
        return "OFFLINE_HOST_KEY_FIXTURE_ONLY"

    def transfer(self,path,sha,hostkey):
        self.calls.append("transfer")
        if path!=self.fixture.cipher or sha!=self.fixture.cipher_sha:
            raise AssertionError("wrong source or digest")
        if hostkey!="OFFLINE_HOST_KEY_FIXTURE_ONLY":
            raise AssertionError("wrong host key fixture")
        # The coordinator MUST not publish local artifacts before this point.
        self.fixture.assertFalse((self.fixture.vault/(self.fixture.stamp+".tar.age")).exists())
        self.fixture.assertFalse((self.fixture.daily_root/self.fixture.stamp).exists())
        if self.after_transfer is not None:
            self.after_transfer()
        if self.error:
            raise RuntimeError("SIMULATED_REMOTE_READBACK_FAILURE")
        return self.return_value


class V3SameInvocationReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.vault=self.base/"vault"
        self.stage_root=self.base/"staging-outside-daily"
        self.daily_root=self.base/"daily"
        for directory in (self.vault,self.stage_root,self.daily_root):
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        self.work=Path(tempfile.mkdtemp(prefix=".kmj-fresh-x25519-",dir=self.vault))
        self.work.chmod(0o700)
        self.cipher=self.work/"fresh.age"
        self.payload=b"OFFLINE_AGE_CIPHER_FIXTURE_NO_REAL_KEY"*9
        self.cipher.write_bytes(self.payload)
        self.cipher.chmod(0o600)
        self.cipher_sha=hashlib.sha256(self.payload).hexdigest()
        self.stamp="20261115T081551Z"
        self.snapshot=self.stage_root/("stage-"+self.stamp)
        self.snapshot.mkdir(mode=0o700);self.snapshot.chmod(0o700)
        self.dump=b"PGDMP"+b"MOCK_POSTGRES_ARCHIVE_NO_DB"*8
        self._file("platform.dump",self.dump)
        self._file("app.env",b"OFFLINE_FIXTURE_NO_SECRET\n")
        self._file("RECOVERY-METADATA.txt",b"offline_fixture_only\n")
        self._file("SHA256SUMS",(
            hashlib.sha256(self.dump).hexdigest()+"  platform.dump\n"+
            hashlib.sha256(b"OFFLINE_FIXTURE_NO_SECRET\n").hexdigest()+"  app.env\n"+
            hashlib.sha256(b"offline_fixture_only\n").hexdigest()+"  RECOVERY-METADATA.txt\n"
        ).encode("ascii"))
        for folder in ("platform-storage","config"):
            sub=self.snapshot/folder
            sub.mkdir(mode=0o700);sub.chmod(0o700)
        for name in m.daily.STORAGE_DIRS:
            sub=self.snapshot/"platform-storage"/name
            sub.mkdir(mode=0o700);sub.chmod(0o700)
            self._file("platform-storage/"+name+"/fixture.dat",b"STORAGE_"+name.encode())
        for name in m.daily.CONFIG_DIRS:
            sub=self.snapshot/"config"/name
            sub.mkdir(mode=0o700);sub.chmod(0o700)
            self._file("config/"+name+"/fixture.conf",b"CONFIG_"+name.encode())
        self.uid=os.geteuid()
        self.release="review-release-20261115"
        self.live=[self.release]
        self.transport=FakeTransport(self)

    def _file(self,name,body):
        file=self.snapshot/name
        file.write_bytes(body)
        file.chmod(0o600)
        manifest=self.snapshot/"SHA256SUMS"
        if name!="SHA256SUMS" and manifest.is_file():
            with manifest.open("a",encoding="ascii") as out:
                out.write(hashlib.sha256(body).hexdigest()+"  "+name+"\n")
        return file

    def commit(self,**kwargs):
        args=dict(
            transport=self.transport,
            pinned_live_release_probe=lambda:self.live[0],
            expected_release=self.release,
            vault=self.vault,
            fresh_cipher=self.cipher,
            stage_root=self.stage_root,
            daily_root=self.daily_root,
            stamp=self.stamp,
            expected_uid=self.uid,
        )
        args.update(kwargs)
        return m.commit_after_same_invocation_v2_readback(**args)

    def test_success_requires_simulated_sftp_return_before_local_commits(self):
        result=self.commit()
        self.assertEqual(self.transport.calls,["digest","host_key","transfer"])
        self.assertTrue(result["remote_sha_readback_same_invocation"])
        self.assertTrue(result["local_cipher_sidecar_verified"])
        self.assertTrue(result["local_daily_snapshot_verified"])
        self.assertFalse(result["independent_remote_decrypt_restore_verified"])
        self.assertEqual((self.vault/(self.stamp+".tar.age")).read_bytes(),self.payload)
        self.assertEqual(
            (self.vault/(self.stamp+".sha256")).read_bytes(),
            m.policy.sidecar_bytes(self.stamp,self.cipher_sha),
        )
        self.assertEqual((self.daily_root/self.stamp/"platform.dump").read_bytes(),self.dump)
        self.assertFalse(self.snapshot.exists())

    def test_remote_readback_failure_blocks_all_local_commits(self):
        self.transport.error=True
        with self.assertRaisesRegex(RuntimeError,"SIMULATED_REMOTE_READBACK_FAILURE"):
            self.commit()
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())
        self.assertFalse((self.daily_root/self.stamp).exists())
        self.assertTrue(self.snapshot.exists())

    def test_transport_digest_mismatch_blocks_remote_call(self):
        self.transport.digest_override="0"*64
        with self.assertRaisesRegex(m.Deny,"TRANSPORT_CIPHER_SHA_MISMATCH"):
            self.commit()
        self.assertEqual(self.transport.calls,["digest"])
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())

    def test_non_none_transport_result_blocks_local_publish(self):
        self.transport.return_value=True
        with self.assertRaisesRegex(m.Deny,"V2_TRANSFER_RETURN_CONTRACT_CHANGED"):
            self.commit()
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())
        self.assertFalse((self.daily_root/self.stamp).exists())

    def test_release_mismatch_before_remote_does_not_call_transport(self):
        self.live[0]="different-release"
        with self.assertRaisesRegex(m.Deny,"LIVE_RELEASE_CHANGED_BEFORE_TRANSFER"):
            self.commit()
        self.assertEqual(self.transport.calls,[])

    def test_release_change_immediately_after_remote_never_publishes_locally(self):
        self.transport.after_transfer=lambda:self.live.__setitem__(0,"different-release")
        with self.assertRaises(m.IncompleteTransaction) as ctx:
            self.commit()
        self.assertEqual(ctx.exception.phase,"REMOTE_ONLY")
        self.assertFalse((self.vault/(self.stamp+".tar.age")).exists())
        self.assertFalse((self.daily_root/self.stamp).exists())

    def test_missing_daily_manifest_rejected_before_remote_call(self):
        (self.snapshot/"SHA256SUMS").unlink()
        with self.assertRaises((FileNotFoundError,m.daily.Deny)):
            self.commit()
        self.assertEqual(self.transport.calls,[])

    def test_existing_vault_stamp_rejected_before_remote_call(self):
        existing=self.vault/(self.stamp+".tar.age")
        existing.write_bytes(b"EXISTING_NEVER_TOUCH");existing.chmod(0o600)
        with self.assertRaisesRegex(m.pair.PublishError,"DESTINATION_ALREADY_EXISTS"):
            self.commit()
        self.assertEqual(self.transport.calls,[])
        self.assertEqual(existing.read_bytes(),b"EXISTING_NEVER_TOUCH")

    def test_existing_daily_stamp_rejected_before_remote_call(self):
        target=self.daily_root/self.stamp
        target.mkdir(mode=0o700)
        with self.assertRaisesRegex(m.Deny,"DAILY_TIMESTAMP_ALREADY_PUBLISHED"):
            self.commit()
        self.assertEqual(self.transport.calls,[])

    def test_stale_pgdmp_denied_before_network(self):
        import time
        stamp=time.time()-4*86400
        os.utime(self.snapshot/"platform.dump",(stamp,stamp))
        with self.assertRaisesRegex(m.Deny,"DAILY_PGDMP_NOT_FRESH"):
            self.commit()
        self.assertEqual(self.transport.calls,[])

    def test_cipher_pair_failure_after_readback_does_not_publish_daily(self):
        with mock.patch.object(m.pair,"publish_after_verified_remote_readback",
                               side_effect=m.pair.PublishError("MOCK_PAIR_FAILURE")):
            with self.assertRaises(m.IncompleteTransaction) as ctx:
                self.commit()
        self.assertEqual(ctx.exception.phase,"REMOTE_VERIFIED_LOCAL_NOT_COMMITTED")
        self.assertFalse((self.daily_root/self.stamp).exists())

    def test_daily_failure_after_cipher_commit_is_partial_not_complete(self):
        with mock.patch.object(m.daily,"publish_after_separately_verified_remote_readback",
                               side_effect=m.daily.Deny("INJECTED_DAILY_FAIL")):
            with self.assertRaises(m.IncompleteTransaction) as ctx:
                self.commit()
        self.assertEqual(ctx.exception.phase,"REMOTE_AND_CIPHER_PAIR_COMMITTED")
        self.assertTrue((self.vault/(self.stamp+".tar.age")).is_file())
        self.assertTrue((self.vault/(self.stamp+".sha256")).is_file())
        self.assertFalse((self.daily_root/self.stamp).exists())
        self.assertTrue(self.snapshot.exists())

    def test_release_change_during_daily_commit_is_incomplete_not_success(self):
        real_publish=m.daily.publish_after_separately_verified_remote_readback
        def publish_then_change_release(*args,**kwargs):
            receipt=real_publish(*args,**kwargs)
            self.live[0]="different-release-after-daily-commit"
            return receipt
        with mock.patch.object(m.daily,"publish_after_separately_verified_remote_readback",
                               side_effect=publish_then_change_release):
            with self.assertRaises(m.IncompleteTransaction) as ctx:
                self.commit()
        self.assertEqual(
            ctx.exception.phase,
            "REMOTE_CIPHER_AND_DAILY_COMMITTED_RELEASE_UNVERIFIED",
        )
        self.assertEqual(self.transport.calls,["digest","host_key","transfer"])
        self.assertTrue((self.vault/(self.stamp+".tar.age")).is_file())
        self.assertTrue((self.vault/(self.stamp+".sha256")).is_file())
        self.assertTrue((self.daily_root/self.stamp/"platform.dump").is_file())

    def test_cannot_repeat_after_success_without_overwriting(self):
        self.commit()
        with self.assertRaisesRegex(m.Deny,"DAILY_TIMESTAMP_ALREADY_PUBLISHED"):
            self.commit()
        self.assertEqual(self.transport.calls.count("transfer"),1)

    def test_policy_rejects_path_overlap_and_bad_utc_stamp(self):
        with self.assertRaisesRegex(m.Deny,"DAILY_AND_STAGE_ROOTS_NOT_SEPARATED"):
            self.commit(stage_root=self.daily_root)
        with self.assertRaisesRegex(m.Deny,"TRANSACTION_INPUTS_UNVERIFIED"):
            self.commit(stamp="../../etc")

    def test_source_only_has_no_service_installer(self):
        self.assertFalse(hasattr(m,"install_service"))
        self.assertFalse(hasattr(m,"run_scheduled"))
        self.assertFalse(hasattr(m,"test_remote_restore"))
        self.assertEqual(m.__name__,"kmj_v3_transfer_transaction_review")


if __name__=="__main__":
    unittest.main()
