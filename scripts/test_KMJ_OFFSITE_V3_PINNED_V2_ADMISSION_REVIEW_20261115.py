"""Offline unit/source admission fixtures. No root, unit mutation or network."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock

FILE=Path(__file__).with_name("KMJ_OFFSITE_V3_PINNED_V2_ADMISSION_REVIEW_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_v3_pinned_v2_admission_review",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FixedV2SourceAdmissionFixtures(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"v2-fixture.py"
        self.raw=b"#!/usr/bin/python3\n"+b"# OFFLINE NONPRODUCTION FIXTURE\n"*25
        self.path.write_bytes(self.raw)
        self.path.chmod(0o600)
        self.sha=hashlib.sha256(self.raw).hexdigest()
        self.uid=os.geteuid()
        self.props=dict(
            Id=m.UNIT,LoadState="loaded",Type="oneshot",
            User="",DropInPaths=m.DROPIN,
            ExecStart="{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "
            +str(m.V2)+" --scheduled-run ; ignore_errors=no ; }",
        )

    def source(self):
        return m.pinned_source_bytes(
            self.path,self.sha,uid=self.uid,minimum=100,maximum=6000,
        )

    def test_exact_private_regular_file_and_sha_admitted(self):
        self.assertEqual(self.source(),self.raw)

    def test_changed_source_sha_rejected(self):
        self.path.write_bytes(self.raw+b"# code change")
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_SHA_CHANGED"):
            self.source()

    def test_mode_group_or_other_read_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_METADATA_CHANGED"):
            self.source()

    def test_world_writable_file_rejected(self):
        self.path.chmod(0o666)
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_METADATA_CHANGED"):
            self.source()

    def test_hardlinked_source_rejected(self):
        os.link(self.path,Path(self.temp.name)/"duplicate.py")
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_METADATA_CHANGED"):
            self.source()

    def test_symlink_source_rejected(self):
        other=Path(self.temp.name)/"original.py"
        self.path.rename(other)
        self.path.symlink_to(other)
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_METADATA_CHANGED"):
            self.source()

    def test_digest_argument_must_be_exact_hex64(self):
        with self.assertRaisesRegex(m.Deny,"PINNED_FILE_INPUT_INVALID"):
            m.pinned_source_bytes(self.path,"not-a-hash",uid=self.uid)

    def test_exact_oneshot_unit_identity_pass(self):
        self.assertTrue(m.validate_unit(self.props))

    def test_wrong_user_is_refused(self):
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit(dict(self.props,User="kmjprod"))

    def test_additional_or_different_dropin_refused(self):
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit(dict(self.props,DropInPaths=m.DROPIN+" /tmp/unsafe.conf"))

    def test_changed_argv_refused(self):
        value=self.props["ExecStart"].replace("--scheduled-run","--send-once")
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_EXEC_IDENTITY_CHANGED"):
            m.validate_unit(dict(self.props,ExecStart=value))

    def test_duplicate_installed_argv_refused(self):
        value=self.props["ExecStart"]+" ; argv[]=/usr/bin/python3 -I -B "+str(m.V2)+" --scheduled-run"
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_EXEC_IDENTITY_CHANGED"):
            m.validate_unit(dict(self.props,ExecStart=value))

    def test_unexpected_field_or_missing_field_refused(self):
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit({**self.props,"ExecMainStatus":"0"})
        gone=dict(self.props)
        gone.pop("Type")
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit(gone)

    def test_non_oneshot_unit_refused(self):
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit(dict(self.props,Type="simple"))

    def test_fixed_systemctl_output_parse_and_verify(self):
        text="\n".join(f"{key}={value}" for key,value in self.props.items())+"\n"
        fake=types.SimpleNamespace(returncode=0,stdout=text.encode())
        with mock.patch.object(m.subprocess,"run",return_value=fake) as command:
            self.assertEqual(m.fixed_unit_info(),self.props)
        argv=command.call_args.args[0]
        self.assertEqual(argv[0:3],["/usr/bin/systemctl","show","--no-pager"])
        self.assertEqual(argv[-1],m.UNIT)
        self.assertNotIn("start",argv)
        self.assertNotIn("sudo",argv)

    def test_repeated_unit_field_denied(self):
        text="\n".join(f"{key}={value}" for key,value in self.props.items())
        text+="\nId=other-unit\n"
        fake=types.SimpleNamespace(returncode=0,stdout=text.encode())
        with mock.patch.object(m.subprocess,"run",return_value=fake):
            with self.assertRaisesRegex(m.Deny,"SCHEDULED_UNIT_OUTPUT_NOT_TRUSTED"):
                m.fixed_unit_info()

    def test_unit_not_loaded_or_no_exact_exec_rejected(self):
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_UNIT_ADMISSION_FAILED"):
            m.validate_unit(dict(self.props,LoadState="not-found"))
        with self.assertRaisesRegex(m.Deny,"SCHEDULED_V2_EXEC_IDENTITY_CHANGED"):
            m.validate_unit(dict(self.props,ExecStart="argv[]=/usr/bin/python3 /tmp/not-v2.py"))

    def test_bad_parent_link_or_mode_refused(self):
        fake=types.SimpleNamespace(st_mode=stat.S_IFLNK|0o777,st_uid=0)
        with mock.patch.object(m.os,"lstat",return_value=fake):
            with self.assertRaisesRegex(m.Deny,"ROOT_PARENT_CHAIN_UNTRUSTED"):
                m.root_parent_chain()

    def test_running_as_nonroot_blocks_real_admission_before_any_files(self):
        with mock.patch.object(m.os,"geteuid",return_value=1000):
            with self.assertRaisesRegex(m.Deny,"OWNER_HOST_ROOT_REQUIRED"):
                m.admit_exact_installed_v2()

    def test_source_only_selftest_has_no_service_side_effect(self):
        self.assertEqual(m.admission_selftest(),0)
        self.assertFalse(hasattr(m,"install_service"))
        self.assertFalse(hasattr(m,"send_once"))
        self.assertFalse(hasattr(m,"run_scheduled"))
        self.assertNotIn("transfer",m.admission_selftest.__code__.co_names)


if __name__=="__main__":
    unittest.main()
