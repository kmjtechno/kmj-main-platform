"""Synthetic, non-root-only tests for owner-gated V2->DNS-aware V3 continuity.

No service, SSH, Cloudflare, backup transfer, root or production mutation.
"""
import base64
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import stat
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

PATH=Path(__file__).with_name("guarded-offsite-v2-v3-dns-continuity-20261117.py")
S=importlib.util.spec_from_file_location("kmj_v3_owner_guard",PATH)
m=importlib.util.module_from_spec(S)
S.loader.exec_module(m)

class Cases(unittest.TestCase):
    def test_fixed_sources_host_pin_and_ip_exact(self):
        self.assertEqual(len(m.SOURCES),3)
        self.assertEqual(m.EXPECTED_IP,"34.132.7.161")
        self.assertEqual(m.HOST,"offsite.kmjtechno.com")
        self.assertTrue(m.HOSTKEY_PIN.startswith("SHA256:"))
        self.assertEqual(m.V2.name,"kmj-offsite-fresh-x25519-v2-20261112.py")
        self.assertEqual(m.V3.name,"kmj-offsite-fresh-x25519-v3-20261112.py")
        self.assertEqual(m.V3PARENT.name,"KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py")
        self.assertIn(str(m.V2),m.OLD_DROPIN.decode())
        self.assertIn(str(m.V3),m.NEW_DROPIN.decode())
        self.assertNotEqual(m.NEW_DROPIN,m.OLD_DROPIN)
    def test_fixed_modes_and_root_only(self):
        out=io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(m.main(["--shell"]),2)
            with patch.object(m.os,"geteuid",return_value=1000):
                self.assertEqual(m.main(["--apply"]),2)
        self.assertIn("BLOCKED_EXACT_MODE_ONLY",out.getvalue())
        self.assertIn("BLOCKED_ROOT_ELITE_ONLY",out.getvalue())
    def test_sha_read_and_symlink_rejection_without_root(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"sample"
            f.write_bytes(b"x"*1024)
            f.chmod(0o600)
            digest=hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(m.safe_read(f,digest),b"x"*1024)
            with self.assertRaisesRegex(m.Guard,"SOURCE_SHA_MISMATCH"):
                m.safe_read(f,"a"*64)
            link=Path(folder)/"symlink"
            link.symlink_to(f)
            with self.assertRaisesRegex(m.Guard,"SOURCE_METADATA_CHANGED"):
                m.safe_read(link,digest)
            duplicate=Path(folder)/"hardlink"
            os.link(f,duplicate)
            with self.assertRaisesRegex(m.Guard,"SOURCE_METADATA_CHANGED"):
                m.safe_read(f,digest)
    def test_wrong_public_ip_blocks_without_network_connection(self):
        record=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("34.63.5.14",22))]
        with patch.object(m.socket,"getaddrinfo",return_value=record),\
             patch.object(m,"run",side_effect=AssertionError("NO_SCAN")):
            with self.assertRaisesRegex(m.Guard,"DNS_NOT_VERIFIED_NEW_GCE_IP"):
                m.public_hostkey()
    def test_new_public_ip_and_out_of_band_original_pin_pass(self):
        record=[(socket.AF_INET,socket.SOCK_STREAM,6,"",(m.EXPECTED_IP,22))]
        key=b"synthetic public only ED25519 key"
        enc=base64.b64encode(key).decode()
        raw=f"{m.HOST} ssh-ed25519 {enc}\n".encode()
        pin="SHA256:"+base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        with patch.object(m.socket,"getaddrinfo",return_value=record),\
             patch.object(m,"run",return_value=SimpleNamespace(returncode=0,stdout=raw)) as run,\
             patch.object(m,"HOSTKEY_PIN",pin):
            self.assertIsNone(m.public_hostkey())
            cmd=run.call_args.args[0]
            self.assertEqual(cmd[0],"/usr/bin/ssh-keyscan")
            self.assertNotIn("sftp"," ".join(cmd))
            self.assertNotIn("sshpass"," ".join(cmd))
    def test_mismatched_remote_hostkey_stays_blocked(self):
        record=[(socket.AF_INET,socket.SOCK_STREAM,6,"",(m.EXPECTED_IP,22))]
        raw=f"{m.HOST} ssh-ed25519 {base64.b64encode(b'wrong key').decode()}\n".encode()
        with patch.object(m.socket,"getaddrinfo",return_value=record),\
             patch.object(m,"run",return_value=SimpleNamespace(returncode=0,stdout=raw)):
            with self.assertRaisesRegex(m.Guard,"PUBLIC_HOSTKEY_PIN_MISMATCH"):
                m.public_hostkey()
    def test_old_v2_service_exact_contract(self):
        unit={
            "Id":m.UNIT,"LoadState":"loaded","Type":"oneshot",
            "User":"root","ActiveState":"failed","Result":"exit-code",
            "ExecMainStatus":"3","InvocationID":"a"*32,
            "DropInPaths":str(m.DROPIN),
            "ExecStart":"{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "
                +str(m.V2)+" --scheduled-run ; ignore_errors=no }",
        }
        timer={"Id":m.TIMER,"LoadState":"loaded","ActiveState":"active",
               "UnitFileState":"enabled","Unit":m.UNIT}
        fake_root=SimpleNamespace(st_mode=stat.S_IFDIR|0o755,st_uid=0)
        def read(target,props):return unit if target==m.UNIT else timer
        with patch.object(m,"read_unit",side_effect=read),\
             patch.object(m,"safe_read",return_value=m.OLD_DROPIN),\
             patch.object(m.os,"lstat",return_value=fake_root):
            accepted=m.validate_systemd()
            self.assertEqual(accepted["InvocationID"],"a"*32)
            unit["ExecMainStatus"]="255"
            with self.assertRaisesRegex(m.Guard,"INSTALLED_V2_UNIT_DRIFT"):
                m.validate_systemd()
            unit["ExecMainStatus"]="3"
            unit["ExecStart"]="argv[]=python3 malicious.py"
            with self.assertRaisesRegex(m.Guard,"INSTALLED_V2_UNIT_DRIFT"):
                m.validate_systemd()
    def test_sealed_legacy_dropin_only_exact_bytes(self):
        self.assertTrue(m.OLD_DROPIN.startswith(b"[Service]\nExecStart=\n"))
        self.assertTrue(m.NEW_DROPIN.startswith(b"[Service]\nExecStart=\n"))
        self.assertEqual(m.OLD_DROPIN.count(b"ExecStart="),2)
        self.assertEqual(m.NEW_DROPIN.count(b"ExecStart="),2)
        self.assertEqual(m.NEW_DROPIN.count(b"TimeoutStartSec="),1)
    def test_atomic_dropin_mode_0644_under_private_umask(self):
        with tempfile.TemporaryDirectory() as root:
            scratch=Path(root)/"scratch"
            scratch.mkdir()
            target=Path(root)/"target.conf"
            target.write_bytes(m.OLD_DROPIN)
            old=os.umask(0o077)
            reader=m.safe_read
            def unprivileged_test_reader(path,sha=None,**kwargs):
                return reader(path,sha,require_root=False,
                              mode=kwargs.get("mode"),maximum=kwargs.get("maximum",131072))
            try:
                with patch.object(m,"DROPIN",target),\
                     patch.object(m,"safe_read",side_effect=unprivileged_test_reader) as rd:
                    m.atomic_dropin(m.NEW_DROPIN,scratch)
                    self.assertGreaterEqual(rd.call_count,1)
            finally:os.umask(old)
            self.assertEqual(target.read_bytes(),m.NEW_DROPIN)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o644)
    def test_receipt_requires_remote_sha_and_pg_dump(self):
        unit=["FRESH_PGDMP=PASS","SOURCE_MANIFEST=PASS",
              "REMOTE_SFTP_SHA_READBACK=PASS",
              "RESULT=FRESH_PGDUMP_X25519_GOOGLE_TRANSFER_PASS"]
        with patch.object(m,"run",return_value=SimpleNamespace(returncode=0,stdout=("\n".join(unit)+"\n").encode())):
            self.assertTrue(m.classified_receipt("a"*32))
        unit.remove("REMOTE_SFTP_SHA_READBACK=PASS")
        with patch.object(m,"run",return_value=SimpleNamespace(returncode=0,stdout=("\n".join(unit)+"\n").encode())):
            with self.assertRaisesRegex(m.Guard,"REMOTE_READBACK_MARKERS_INCOMPLETE"):
                m.classified_receipt("b"*32)
    def test_preflight_failure_blocks_service_mutation(self):
        called=[]
        with patch.object(m,"validate_systemd",side_effect=m.Guard("INSTALLED_V2_UNIT_DRIFT")),\
             patch.object(m,"exclusive_install",side_effect=lambda *args:called.append("install")),\
             patch.object(m,"run",side_effect=AssertionError("MUST_NOT_START")):
            with tempfile.TemporaryDirectory() as scratch:
                with self.assertRaisesRegex(m.Guard,"INSTALLED_V2_UNIT_DRIFT"):
                    m.guarded_apply({},{"InvocationID":"a"*32},Path(scratch))
        self.assertEqual(called,[])
    def test_offline_v3_inspect_requires_two_explicit_pass_markers(self):
        ok=[
            SimpleNamespace(returncode=0,stdout=b"OK"),
            SimpleNamespace(returncode=0,stdout=b"RESULT=SELFTEST_PASS"),
            SimpleNamespace(returncode=0,stdout=b"GOOGLE_ENDPOINT=DNS_ONLY_STRICT_PINNED_HOSTKEY\nRESULT=INSPECT_PASS"),
        ]
        with patch.object(m,"run",side_effect=ok):
            with tempfile.TemporaryDirectory() as x:
                self.assertTrue(m.offline_and_inspect(Path(x)))
        bad=ok.copy()
        bad[-1]=SimpleNamespace(returncode=0,stdout=b"RESULT=INSPECT_PASS\n")
        with patch.object(m,"run",side_effect=bad):
            with tempfile.TemporaryDirectory() as x:
                with self.assertRaisesRegex(m.Guard,"V3_READONLY_PREFLIGHT_FAILED"):
                    m.offline_and_inspect(Path(x))
    def test_preflight_bounded_reason_from_child_marker(self):
        cases=[
          (b"SCHEMA=KMJ_OFFSITE\nRESULT=BLOCKED_DNS_UNIQUE_IPV4_REQUIRED\n",
           "V3_PREFLIGHT_BLOCKED_DNS_UNIQUE_IPV4_REQUIRED"),
          (b"SCHEMA=KMJ_OFFSITE\nRESULT=BLOCKED_SAFE\n",
           "V3_PREFLIGHT_MASKED_TRANSPORT_PINNED_CONFIG_DRIFT"),
        ]
        for receipt,expected in cases:
            with self.subTest(expected=expected),\
                 patch.object(m,"run",side_effect=[
                   SimpleNamespace(returncode=0,stdout=b"OK"),
                   SimpleNamespace(returncode=0,stdout=b"RESULT=SELFTEST_PASS"),
                   SimpleNamespace(returncode=3,stdout=receipt)
                 ]),\
                 patch.object(m,"v3_safe_direct_category",
                              return_value="TRANSPORT_PINNED_CONFIG_DRIFT") as direct:
                with tempfile.TemporaryDirectory() as x:
                    with self.assertRaisesRegex(m.Guard,expected):
                        m.offline_and_inspect(Path(x))
                self.assertEqual(direct.call_count,
                                 int(expected.startswith("V3_PREFLIGHT_MASKED_")))
    def test_v3_inspect_marker_does_not_leak_paths_secrets(self):
        self.assertEqual(m.safe_v3_inspect_marker(
          b"SECRET=/root/.ssh/private\nRESULT=BLOCKED_MIGRATION_UNIT_DRIFT\n"),
          "BLOCKED_MIGRATION_UNIT_DRIFT")
        self.assertEqual(m.safe_v3_inspect_marker(
          b"RESULT=BLOCKED_X\nRESULT=BLOCKED_Y\n"),"UNKNOWN")
        self.assertEqual(m.safe_v3_inspect_marker(
          b"RESULT=BLOCKED_/root/password\n"),"UNKNOWN")
        self.assertEqual(m.safe_v3_inspect_marker(b"x"*(m.MAX_OUTPUT+1)),"OUTPUT_OVERSIZE")
    def test_v3_direct_import_errors_fail_closed_categorically(self):
        with tempfile.TemporaryDirectory() as dir:
            scratch=Path(dir)
            with patch.object(m,"safe_read",return_value=b"pinned"),\
                 patch("importlib.util.spec_from_file_location",
                       side_effect=OSError("secret path that must not print")):
                # A failed import must never be transformed into a path leak.
                with self.assertRaises(OSError):
                    m.v3_safe_direct_category(scratch)
    def test_root_script_does_not_weaken_security_or_delete_old_assets(self):
        text=PATH.read_text()
        self.assertNotIn("StrictHostKeyChecking=no",text)
        self.assertNotIn("ssh-keygen -R",text)
        self.assertNotIn("known_hosts.unlink()",text)
        self.assertNotIn("shutil.rmtree(V2)",text)
        self.assertNotIn("git reset",text)
        self.assertNotIn("cloudflare.request",text)
        self.assertIn('["/usr/bin/systemctl","start",UNIT]',text)
        self.assertIn('"REMOTE_DISPOSABLE_RESTORE=NOT_VERIFIED"',text)

if __name__=="__main__":
    unittest.main()
