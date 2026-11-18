#!/usr/bin/python3
"""Offline-only safety gates for the 18 Nov optional recurring V3 timer."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
TARGET=HERE/"KMJ_V3_DUAL_LOCAL_RECURRING_TIMER_OWNER_20261118.py"
SPEC=importlib.util.spec_from_file_location("kmj_v3_timer_owner_review",TARGET)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("MODULE_LOAD")
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
BODY=TARGET.read_text(encoding="utf-8")


class OwnerV3TimerTests(unittest.TestCase):
    def test_offline_selftest_does_not_request_root_or_service(self):
        run=subprocess.run([sys.executable,"-I","-B",str(TARGET),"--selftest"],
                           capture_output=True,check=False,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr.decode("utf-8","replace"))
        self.assertIn(b"KMJ_V3_RECURRING_TIMER_OFFLINE_SELFTEST=PASS",run.stdout)
        self.assertIn(b"HOST_OR_SERVICE_MUTATION=NONE",run.stdout)

    def test_timer_source_pins_exact_prev_verified_runner(self):
        verified=HERE/"KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py"
        self.assertEqual(hashlib.sha256(verified.read_bytes()).hexdigest(),m.PIN)
        self.assertEqual(m.CHECKSUM_TEXT,m.PIN+"  "+str(m.RUNNER)+"\n")
        self.assertTrue(m.RUNNER.is_relative_to("/usr/local/libexec/"))

    def test_new_timer_does_not_edit_original_offsite_unit(self):
        self.assertNotIn(m.ORIGINAL_SERVICE,m.SERVICE_TEXT)
        self.assertNotIn(m.ORIGINAL_TIMER,m.SERVICE_TEXT)
        self.assertNotIn(m.ORIGINAL_TIMER,m.TIMER_TEXT)
        self.assertIn("ExecStart=/usr/bin/python3 -I -B "+str(m.RUNNER)+" --run-once",
                      m.SERVICE_TEXT)
        self.assertIn("ExecStartPre=/usr/bin/sha256sum --check --status "+str(m.SIDECAR),
                      m.SERVICE_TEXT)
        self.assertIn("NoNewPrivileges=true",m.SERVICE_TEXT)
        self.assertIn("ProtectSystem=strict",m.SERVICE_TEXT)
        self.assertIn("PrivateTmp=true",m.SERVICE_TEXT)
        self.assertNotIn("ExecStartPost=",m.SERVICE_TEXT)

    def test_calendar_is_twice_daily_no_immediate_catchup(self):
        self.assertIn("OnCalendar=*-*-* 03:45:00",m.TIMER_TEXT)
        self.assertIn("OnCalendar=*-*-* 15:45:00",m.TIMER_TEXT)
        self.assertIn("Persistent=false",m.TIMER_TEXT)
        self.assertIn("Unit="+m.SERVICE,m.TIMER_TEXT)
        self.assertNotIn("OnBootSec=",m.TIMER_TEXT)
        self.assertNotIn("OnUnitActiveSec=",m.TIMER_TEXT)

    def test_only_explicit_owner_install_mode(self):
        self.assertIn('("--selftest","--inspect","--install","--disable")',BODY)
        self.assertIn('if sys.argv[1]=="--inspect":inspect();return 0',BODY)
        self.assertIn('if sys.argv[1]=="--install":return install()',BODY)
        self.assertIn('host_root()',BODY)
        self.assertIn('SOURCE_SHA_MISMATCH',BODY)
        self.assertIn('RECURRING_UNIT_COLLISION',BODY)
        self.assertNotIn("subprocess.Popen(",BODY)
        self.assertNotIn("shell=True",BODY)
        self.assertNotIn("git reset",BODY)
        self.assertNotIn("git clean",BODY)

    def test_inspection_has_no_unit_enable(self):
        with mock.patch.object(m,"verify_existing_baseline",return_value=b"source"),\
             mock.patch.object(m,"pinned_runner_preflight") as probe,\
             mock.patch.object(m,"sysrun") as system:
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                m.inspect()
            probe.assert_called_once_with(b"source")
            system.assert_not_called()
            self.assertIn("OWNER_APPROVAL_REQUIRED",output.getvalue())

    def test_stale_source_denies_before_unit_install(self):
        ready={(m.ORIGINAL_SERVICE,"LoadState"):"loaded",
               (m.ORIGINAL_SERVICE,"Type"):"oneshot",
               (m.ORIGINAL_TIMER,"LoadState"):"loaded",
               (m.ORIGINAL_TIMER,"ActiveState"):"active",
               (m.ORIGINAL_HEALTH,"LoadState"):"loaded",
               (m.ORIGINAL_HEALTH,"Result"):"success",
               (m.ORIGINAL_HEALTH,"ExecMainStatus"):"0",
               (m.SERVICE,"LoadState"):"not-found",
               (m.TIMER,"LoadState"):"not-found"}
        with mock.patch.object(m,"guard_dir"),\
             mock.patch.object(m,"prop",side_effect=lambda u,k:ready[(u,k)]),\
             mock.patch.object(m.os.path,"lexists",return_value=False),\
             mock.patch.object(m,"read_exact",side_effect=m.Deny("SOURCE_SHA_MISMATCH")),\
             mock.patch.object(m,"no_clobber_install") as writer:
            with self.assertRaisesRegex(m.Deny,"SOURCE_SHA_MISMATCH"):
                m.verify_existing_baseline()
            writer.assert_not_called()

    def test_source_is_opened_without_following_symlinks(self):
        self.assertIn("os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC",BODY)
        self.assertIn("SOURCE_CHANGED_DURING_READ",BODY)
        self.assertIn("SOURCE_METADATA_INVALID",BODY)
        self.assertIn("os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW",BODY)

    def test_new_timer_rollback_is_separate_and_preserves_files(self):
        self.assertIn('["/usr/bin/systemctl","disable","--now",TIMER]',BODY)
        self.assertIn("BACKUP_FILES_AND_RUNNER=RETAINED_FOR_REVIEW",BODY)
        self.assertIn("EXISTING_OFFSITE_TIMER=UNCHANGED",BODY)
        self.assertNotIn('["/usr/bin/systemctl","stop",ORIGINAL_SERVICE]',BODY)
        self.assertNotIn('["/usr/bin/systemctl","disable","--now",ORIGINAL_TIMER]',BODY)

    def test_original_service_health_checks_before_new_install(self):
        self.assertIn('prop(ORIGINAL_SERVICE,"LoadState")!="loaded"',BODY)
        self.assertIn('prop(ORIGINAL_TIMER,"ActiveState")!="active"',BODY)
        self.assertIn('prop(ORIGINAL_HEALTH,"ExecMainStatus")!="0"',BODY)
        self.assertIn('prop(SERVICE,"LoadState")!="not-found"',BODY)

    def test_health_pipeline_gates_install_before_write(self):
        routine=BODY.split("def install():",1)[1].split("\ndef inspect():",1)[0]
        self.assertLess(routine.index("verify_existing_baseline()"),
                        routine.index("pinned_runner_preflight(source)"))
        self.assertLess(routine.index("pinned_runner_preflight(source)"),
                        routine.index("no_clobber_install(path,body,mode)"))
        self.assertLess(routine.index("verify_new_installation_bytes()"),
                        routine.index('["/usr/bin/systemctl","enable","--now",TIMER]'))
        self.assertIn("FIRST_SCHEDULED_DUAL_LOCAL_BACKUP=NOT_YET_VERIFIED",routine)

    def test_new_unit_bytes_and_modes_attested_before_timer_activation(self):
        self.assertIn("def verify_new_installation_bytes():",BODY)
        self.assertIn("if path==RUNNER:",BODY)
        self.assertIn("read_exact(path,PIN,expected_uid=0)",BODY)
        self.assertIn("NEW_INSTALL_METADATA_UNTRUSTED",BODY)
        self.assertIn("NEW_INSTALL_BYTES_MISMATCH",BODY)
        self.assertIn("NEW_INSTALL_INODE_CHANGED",BODY)
        self.assertIn("os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC",BODY)

    def test_systemd_service_is_not_claimed_pass_before_first_run(self):
        self.assertIn("FIRST_SCHEDULED_DUAL_LOCAL_BACKUP=NOT_YET_VERIFIED",BODY)
        self.assertIn("NoNewPrivileges=true",m.SERVICE_TEXT)
        self.assertNotIn("FRESH_REMOTE_SFTP_SHA_READBACK=PASS",BODY)


if __name__=="__main__":
    unittest.main()
