#!/usr/bin/python3
"""Source-only V3 dual-local and health onepass regressions; never touches host.

No live backup, root, storage, SFTP, service, database, timer, secret or release.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest import mock

TARGET=Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py")
spec=importlib.util.spec_from_file_location("kmj_v3_dual_local_review", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("MODULE_LOAD_FAILED")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SOURCE=TARGET.read_text(encoding="utf-8")


class V3DualLocalHealthSourceTests(unittest.TestCase):
    def test_offline_selftest_is_nonmutating(self):
        result=subprocess.run([sys.executable,"-I","-B",str(TARGET),"--selftest"],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=15,check=False)
        self.assertEqual(result.returncode,0,result.stderr.decode("utf-8","replace"))
        self.assertIn(b"KMJ_V3_HEALTH_ONEPASS_20261117_OFFLINE_SELFTEST=PASS",result.stdout)
        self.assertIn(b"HOST_OR_SERVICE_MUTATION=NONE",result.stdout)

    def test_no_legacy_v2_installed_service_admission(self):
        self.assertNotIn("admit_exact_installed_v2()",SOURCE)
        self.assertNotIn("v2.inspect(",SOURCE)
        self.assertNotIn("v2.encrypt(",SOURCE)
        self.assertIn("admit_exact_installed_v3()",SOURCE)
        self.assertIn("v3.inspect(transport,scheduled=True)",SOURCE)

    def test_installed_v3_source_and_transport_are_exact_pinned(self):
        self.assertEqual(m.V3_INSTALLED.name,"kmj-offsite-fresh-x25519-v3-20261112.py")
        self.assertEqual(m.V3_PARENT.name,"KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py")
        self.assertEqual(m.V3_INSTALLED_SHA,"b594d46d2dc2dd8dec3feaea829934c34b72bde45cb836fe23d3066a9eb5f880")
        self.assertEqual(m.V3_PARENT_SHA,"8f9165714774758a6bef05abff7bf72d655518ab7ed1c3cdd8dc588d3c85c13c")
        self.assertIn("V3_RUNTIME_IMPORT_CONTRACT_DRIFT",SOURCE)
        self.assertIn("V3_RUNTIME_PARENT_UNTRUSTED",SOURCE)
        self.assertIn("V3_RUNTIME_METADATA_DRIFT",SOURCE)
        self.assertIn("v3.schedule_unit_preflight(transport)",SOURCE)
        self.assertIn("private_bytes(V3_INSTALLED,V3_INSTALLED_SHA,uid=0)",SOURCE)

    def test_runtime_is_validated_before_dangerous_operations(self):
        routine=SOURCE.split("def run_once():",1)[1].split("\ndef selftest():",1)[0]
        self.assertIn("runtime_sources()",routine)
        self.assertLess(routine.index("runtime_sources()"),routine.index("install_bundle(buf)"))
        self.assertLess(routine.index("v3.create_fresh("),routine.index("v3.encrypt("))
        self.assertLess(routine.index("v3.encrypt("),
                        routine.index("tx.commit_after_same_invocation_v2_readback("))
        self.assertLess(routine.index("tx.commit_after_same_invocation_v2_readback("),
                        routine.index("verify_health_service_once()"))
        self.assertIn('receipt["remote_sha_readback_same_invocation"]',routine)
        self.assertIn('receipt["local_cipher_sidecar_verified"]',routine)
        self.assertIn('receipt["local_daily_snapshot_verified"]',routine)
        self.assertIn('if v3.LIVE.resolve(strict=True)!=release:',routine)

    def test_health_unchanged_and_exact_own_invocation_pass(self):
        self.assertIn('HEALTH_SHA="2a8cb007acaea2ef8d240ee82a95b13314799dcea36c0cac594e7e5d32acca20"',SOURCE)
        self.assertIn("NATIVE_HEALTH_OWN_INVOCATION_NOT_PASS",SOURCE)
        self.assertIn('after["InvocationID"]==before.get("InvocationID")',SOURCE)
        self.assertIn('print("HEALTH_UNIT_OWN_INVOCATION=SUCCESS_EXIT0")',SOURCE)
        self.assertNotIn("os.replace(HEALTH",SOURCE)
        self.assertNotIn('systemctl","daemon-reload',SOURCE)

    def test_mode_gate_does_not_default_to_backup(self):
        self.assertIn('("--selftest","--preflight","--run-once")',SOURCE)
        self.assertIn('if sys.argv[1]=="--preflight":',SOURCE)
        self.assertIn('print("BACKUP_TRANSFER_EXECUTED=NO")',SOURCE)
        self.assertIn('print("RESULT=BLOCKED_FAIL_CLOSED")',SOURCE)
        self.assertNotIn("subprocess.Popen(" ,SOURCE)
        self.assertIn('if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":',SOURCE)

    def test_dual_local_no_clobber_contract(self):
        self.assertIn("commit_after_same_invocation_v2_readback",SOURCE)
        self.assertIn("publish",SOURCE)
        self.assertIn("existing_private_directory(DAILY)",SOURCE)
        self.assertIn("CERTBOT_LINEAGES=3_VERIFIED",SOURCE)
        self.assertIn('stage=STAGE/("stage-"+stamp)',SOURCE)
        self.assertIn('DAILY=Path("/var/backups/kmj-elite-daily")',SOURCE)
        self.assertIn('VAULT=Path("/var/backups/kmj-elite-offsite-encrypted")',SOURCE)

    def test_admission_aborts_on_untrusted_ancestor_without_import(self):
        with mock.patch.object(m,"root_owner") as owner,\
             mock.patch.object(m.os,"lstat",side_effect=OSError("UNTRUSTED")) as ls,\
             mock.patch.object(m,"private_bytes") as reader:
            with self.assertRaises(OSError):
                m.admit_exact_installed_v3()
            owner.assert_called_once()
            ls.assert_called()
            reader.assert_not_called()

    def test_health_legacy_find_requires_exact_bounded_shape(self):
        good="find /var/backups/kmj-elite-daily -mindepth 2 -maxdepth 2 -name '*.tar.gz' -type f -mtime -2 | grep -q ."
        self.assertEqual(m.parse_exact_find(good),
                         ("/var/backups/kmj-elite-daily","2","2","*.tar.gz"))
        for bad in (good.replace("-mtime -2","-mtime +2"),
                    good.replace("-maxdepth 2","-maxdepth 100"),
                    good+" ; touch /tmp/unsafe"):
            with self.assertRaises(m.Deny):
                m.parse_exact_find(bad)

    def test_no_unrestricted_root_or_release_switch(self):
        for forbidden in ("git reset","git clean","systemctl restart",
                          "systemctl enable","os.system(","eval(","shell=True",
                          "rm -rf","unlink(", "rmtree("):
            self.assertNotIn(forbidden,SOURCE)
        self.assertIn("ROOT=Path",SOURCE)
        self.assertIn('print("LIVE_SERVICE_AND_RELEASE_CONFIG_CHANGED=NO")',SOURCE)


if __name__=="__main__":
    unittest.main()
