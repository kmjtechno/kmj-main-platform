"""No-root, no-network regressions for P0 exact-pinned V3 source bundle."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

SRC=Path(__file__).with_name("KMJ_V3_CERTBOT_MIXED_ROOT_BUNDLE_GUARDED_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_guarded_private_bundle",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SourceBundleOfflineFixtures(unittest.TestCase):
    def test_pinned_six_sources_distinct_and_owner_root_new(self):
        self.assertEqual(len(m.PINS),6)
        self.assertEqual(len(m.PINS.values()),len(set(m.PINS.values())))
        self.assertEqual(m.PINS[m.PUB_NAME],m.PUB_REVIEWED_SHA)
        self.assertIn("certbot-20261115",str(m.PRIVATE))
        self.assertEqual(m.selftest(),0)

    def test_rename_only_six_publisher_keywords_hash_fenced(self):
        source=(b"secret"+b"=legacy "+b"secret parameter\n"*4+b"secret end")
        self.assertEqual(source.count(b"secret"),6)
        expected=source.replace(b"secret",b"restricted")
        with mock.patch.object(m,"PUB_SOURCE_SHA",m.digest(source)),mock.patch.object(
            m,"PUB_REVIEWED_SHA",m.digest(expected)):
            self.assertEqual(m.convert_publisher(source),expected)
            with self.assertRaisesRegex(m.Deny,"PUBLISHER_LOCAL_SOURCE_CHANGED"):
                m.convert_publisher(source+b"extra")

    def test_publisher_semantics_cannot_change_even_if_source_fingerprint_forged(self):
        source=b"secret one secret two secret three secret four secret five secret six"
        with mock.patch.object(m,"PUB_SOURCE_SHA",m.digest(source)),mock.patch.object(
            m,"PUB_REVIEWED_SHA","a"*64):
            with self.assertRaisesRegex(m.Deny,"PUBLISHER_REVIEWED_SOURCE_SHA_MISMATCH"):
                m.convert_publisher(source)

    def test_owner_api_rename_exact_and_digest_fenced(self):
        call=(b'daily.regular(fd,"SHA256SUMS",{0},'+b"secret"+b'=True)')
        source=b"header\n"+call+b"\nfooter\n"
        expected=source.replace(call,b'daily.regular(fd,"SHA256SUMS",{0},restricted=True)')
        with mock.patch.object(m,"OWNER_SOURCE_SHA",m.digest(source)),mock.patch.object(
                m,"OWNER_REVIEWED_SHA",m.digest(expected)):
            self.assertEqual(m.convert_owner(source),expected)
            with self.assertRaisesRegex(m.Deny,"OWNER_LOCAL_SOURCE_CHANGED"):
                m.convert_owner(source+b"changed")

    def test_owner_duplicate_call_signature_rejected(self):
        call=(b'daily.regular(fd,"SHA256SUMS",{0},'+b"secret"+b'=True)')
        source=call+b"\n"+call
        with mock.patch.object(m,"OWNER_SOURCE_SHA",m.digest(source)):
            with self.assertRaisesRegex(m.Deny,"OWNER_REVIEWED_API_SHAPE_CHANGED"):
                m.convert_owner(source)

    def test_source_bundle_rejects_any_pinned_missing_before_root_write(self):
        with mock.patch.object(m,"build_immutable_files",side_effect=m.Deny("BAD_SHA")):
            with mock.patch.object(m,"checked_root_source_dir") as root:
                with self.assertRaisesRegex(m.Deny,"BAD_SHA"):
                    m.prepare()
                root.assert_not_called()

    def test_owner_call_never_issues_os_command_when_bundle_invalid(self):
        with mock.patch.object(m,"check_installed_source_set",side_effect=m.Deny("BAD_SHA")):
            with mock.patch.object(m.subprocess,"run") as execute:
                with self.assertRaisesRegex(m.Deny,"BAD_SHA"):
                    m.owner_call("--run-once")
                execute.assert_not_called()

    def test_owner_preflight_does_not_credit_exit0_without_receipt(self):
        result=types.SimpleNamespace(returncode=0,stdout=b"INSPECT=PASS\n")
        with mock.patch.object(m,"check_installed_source_set",return_value=True):
            with mock.patch.object(m.subprocess,"run",return_value=result):
                with self.assertRaisesRegex(m.Deny,"OWNER_PREFLIGHT_RECEIPT_MISSING"):
                    m.owner_call("--preflight")

    def test_owner_live_receipts_all_required_before_success(self):
        result=types.SimpleNamespace(
            returncode=0,stdout=b"FRESH_REMOTE_SFTP_SHA_READBACK=PASS\n"
            b"HEALTH_UNIT_OWN_INVOCATION=SUCCESS_EXIT0\n")
        with mock.patch.object(m,"check_installed_source_set",return_value=True):
            with mock.patch.object(m.subprocess,"run",return_value=result):
                with self.assertRaisesRegex(m.Deny,"OWNER_RECOVERY_RECEIPT_MISSING"):
                    m.owner_call("--run-once")

    def test_owner_nonzero_never_claims_backup_success(self):
        result=types.SimpleNamespace(returncode=3,stdout=b"BLOCKER=ROOT_UNTRUSTED\n")
        with mock.patch.object(m,"check_installed_source_set",return_value=True):
            with mock.patch.object(m.subprocess,"run",return_value=result):
                with self.assertRaisesRegex(m.Deny,"OWNER_RECOVERY_BLOCKED"):
                    m.owner_call("--run-once")

    def test_existing_source_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            name="immutable.py"
            path=root/name
            path.write_bytes(b"retain")
            before=path.read_bytes()
            fd=os.open(root,m.F_DIR)
            try:
                with mock.patch.object(m,"PRIVATE",root):
                    with mock.patch.object(m,"read_pinned",return_value=before):
                        self.assertFalse(m.write_fresh_only(fd,name,b"NEW",m.digest(before)))
            finally:os.close(fd)
            self.assertEqual(path.read_bytes(),before)

    def test_read_pinned_symlink_rejected_even_correct_target_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/"target"
            target.write_bytes(b"x"*256)
            link=root/"link"
            link.symlink_to(target)
            with self.assertRaisesRegex(m.Deny,"PINNED_FILE_METADATA_DRIFT"):
                m.read_pinned(link,m.digest(target.read_bytes()))

    def test_no_unrestricted_root_shell_or_unsafe_cleanup_api(self):
        src=SRC.read_text(encoding="utf8")
        for forbidden in ("shell=True","os.system(","shutil.rmtree(","git reset","git clean",
                          "systemctl stop","systemctl disable","subprocess.Popen("):
            self.assertNotIn(forbidden,src)

if __name__=="__main__":
    unittest.main()
