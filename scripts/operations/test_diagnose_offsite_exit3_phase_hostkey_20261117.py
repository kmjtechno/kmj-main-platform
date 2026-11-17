import base64
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

FILE=Path(__file__).with_name("diagnose-offsite-exit3-phase-hostkey-20261117.py")
spec=importlib.util.spec_from_file_location("kmj_offsite_exact_phase",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ID="c"*32
UNIT_META={
  "Id":m.UNIT, "LoadState":"loaded","ActiveState":"failed",
  "Result":"exit-code","ExecMainStatus":"3","InvocationID":ID,
  "ExecStart":"{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "
    +m.SRC["V3"][0]+" --scheduled-run ; ignore_errors=no }",
  "DropInPaths":m.DROPIN,
}
def rawmeta(overrides=None):
    data=dict(UNIT_META)
    if overrides:data.update(overrides)
    return "".join(f"{k}={v}\n" for k,v in data.items()).encode()
def journal(v="V3",hostkey=False,inspect=True):
    x=["SCHEMA=KMJ_OFFSITE_FRESH_PGDUMP_X25519_GOOGLE_SFTP_"+v,
       "RESULT=BLOCKED_SAFE"]
    if inspect:x.append("RESULT=INSPECT_PASS")
    if hostkey:x.append("SFTP_HOSTKEY=PIN_MATCH")
    return ("\n".join(x)+"\n").encode()

class Tests(unittest.TestCase):
    def test_phase_exact_stage_and_no_fabricated_cause(self):
        self.assertEqual(m.phase(journal()),("V3","AFTER_PREFLIGHT_BEFORE_HOSTKEY_PASS"))
        self.assertEqual(m.phase(journal("V2")),("V2","AFTER_PREFLIGHT_BEFORE_HOSTKEY_PASS"))
        self.assertEqual(m.phase(journal(hostkey=True)),("V3","AFTER_HOSTKEY"))
        self.assertEqual(m.phase(journal(inspect=False)),("V3","PREFLIGHT_NOT_COMPLETE"))
        self.assertEqual(m.phase(b"RESULT=BLOCKED_SAFE\n"),("OTHER","SCHEMA_NOT_MATCHED"))
        self.assertEqual(m.phase(journal().replace(b"BLOCKED_SAFE",b"BLOCKED_OTHER")),
                         ("V3","BLOCKED_SAFE_NOT_OBSERVED"))
    def test_invalid_systemd_exact_state_blocks_before_journal(self):
        for bad in [
            {"Id":"ssh.service"},{"LoadState":"not-found"},
            {"ActiveState":"active"},{"ExecMainStatus":"0"},
            {"Result":"success"},{"InvocationID":"0"*32},
        ]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):m.snapshot(rawmeta(bad))
        with self.assertRaises(ValueError):m.snapshot(rawmeta()+b"Id=ssh.service\n")
    def test_v3_source_identity_fail_closed_no_caller_args(self):
        good=m.snapshot(rawmeta())
        with patch.object(m.os,"lstat",side_effect=OSError("absent")):
            self.assertEqual(m.attest_source(good,"V3"),"SOURCE_FILE_UNREADABLE")
        self.assertEqual(m.attest_source({**good,"DropInPaths":"/other"},"V3"),
                         "EXECSTART_OR_DROPIN_MISMATCH")
        self.assertEqual(m.attest_source(good,"OTHER"),"NO_REVIEWED_VERSION")
        self.assertEqual(m.attest_source({**good,"ExecStart":"path=/bin/bash; argv[]=sh -c evil;"},"V3"),
                         "EXECSTART_OR_DROPIN_MISMATCH")
    def test_pinned_file_hash_with_descriptor_race_and_nofollow(self):
        source=b"# immutable synthetic script\n"
        import os
        pin=hashlib.sha256(source).hexdigest()
        before=m.SRC["V3"]
        m.SRC["V3"]=("/usr/local/libexec/TEST_SAFE_SYNTHETIC_V3.py",pin)
        good=m.snapshot(rawmeta({
          "ExecStart":"{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "
          +m.SRC["V3"][0]+" --scheduled-run ; ignore_errors=no }"
        }))
        st=SimpleNamespace(st_mode=0o100500,st_uid=0,st_nlink=1,
                st_size=len(source),st_dev=1,st_ino=2,st_mtime_ns=3)
        closed=[]
        try:
            with patch.object(m.os,"lstat",return_value=st),\
                 patch.object(m.os,"open",return_value=12) as opening,\
                 patch.object(m.os,"fstat",side_effect=[st,st]),\
                 patch.object(m.os,"read",return_value=source),\
                 patch.object(m.os,"close",side_effect=closed.append):
                self.assertEqual(m.attest_source(good,"V3"),"EXACT_SOURCE_SHA_PASS")
                self.assertTrue(opening.call_args.args[1] & os.O_NOFOLLOW)
                self.assertEqual(closed,[12])
            changed=SimpleNamespace(**{**vars(st),"st_mtime_ns":4})
            with patch.object(m.os,"lstat",return_value=st),\
                 patch.object(m.os,"open",return_value=15),\
                 patch.object(m.os,"fstat",side_effect=[st,changed]),\
                 patch.object(m.os,"read",return_value=source),\
                 patch.object(m.os,"close"):
                self.assertEqual(m.attest_source(good,"V3"),"SOURCE_FILE_UNTRUSTED")
        finally:
            m.SRC["V3"]=before
    def test_public_hostkey_pin_pass_and_mismatch_no_ssh_auth(self):
        host=m.PUBLIC_HOST
        address=[(m.socket.AF_INET,m.socket.SOCK_STREAM,6,"",("34.63.5.14",22))]
        raw_key=b"synthetic ED25519 public hostkey material only"
        b64=base64.b64encode(raw_key).decode()
        output=f"{host} ssh-ed25519 {b64}\n".encode()
        expected="SHA256:"+base64.b64encode(hashlib.sha256(raw_key).digest()).decode().rstrip("=")
        previous=m.HOSTKEY_PIN
        m.HOSTKEY_PIN=expected
        try:
            with patch.object(m.socket,"getaddrinfo",return_value=address),\
                 patch.object(m,"call",return_value=(0,output)) as run:
                self.assertEqual(m.probe(),"SSH_HOSTKEY_PIN_PASS")
                argv=run.call_args.args[0]
                self.assertEqual(argv[0],"/usr/bin/ssh-keyscan")
                self.assertNotIn("sftp"," ".join(argv))
            m.HOSTKEY_PIN="SHA256:DIFFERENT"
            with patch.object(m.socket,"getaddrinfo",return_value=address),\
                 patch.object(m,"call",return_value=(0,output)):
                self.assertEqual(m.probe(),"SSH_HOSTKEY_PIN_MISMATCH")
        finally:
            m.HOSTKEY_PIN=previous
    def test_remote_down_and_private_dns_fail_without_credential(self):
        valid=[(m.socket.AF_INET,m.socket.SOCK_STREAM,6,"",("34.63.5.14",22))]
        private=[(m.socket.AF_INET,m.socket.SOCK_STREAM,6,"",("127.0.0.1",22))]
        with patch.object(m.socket,"getaddrinfo",return_value=valid),\
             patch.object(m,"call",return_value=(1,b"")):
            self.assertEqual(m.probe(),"SSH_HOSTKEY_SCAN_FAILED")
        with patch.object(m.socket,"getaddrinfo",return_value=private),\
             patch.object(m,"call",side_effect=AssertionError("should not run")):
            self.assertEqual(m.probe(),"DNS_ADDRESS_UNSAFE")
        with patch.object(m.socket,"getaddrinfo",side_effect=OSError("secret")):
            self.assertEqual(m.probe(),"DNS_RESOLUTION_FAILED")
    def test_main_fixed_read_only_receipt_and_changed_invocation(self):
        unit=rawmeta()
        j=journal()
        called=[]
        def runner(args,timeout=12):
            called.append(args)
            if args[0]=="/usr/bin/systemctl":return (0,unit)
            if args[0]=="/usr/bin/journalctl":
                self.assertEqual(args[-1],"_SYSTEMD_INVOCATION_ID="+ID)
                return (0,j)
            raise AssertionError("unexpected subprocess")
        output=io.StringIO()
        with patch.object(m.os,"geteuid",return_value=0),\
             patch.object(m.socket,"gethostname",return_value="KMJ-elite"),\
             patch.object(m,"call",side_effect=runner),\
             patch.object(m,"attest_source",return_value="EXACT_SOURCE_SHA_PASS"),\
             patch.object(m,"probe",return_value="SSH_HOSTKEY_SCAN_FAILED"),\
             redirect_stdout(output):
            self.assertEqual(m.main(["--inspect"]),0)
        self.assertIn("PUBLIC_HOSTKEY_PROBE=SSH_HOSTKEY_SCAN_FAILED",output.getvalue())
        for secret in ("34.63.","/root","ssh-ed25519","argv[]","privatekey"):
            self.assertNotIn(secret,output.getvalue())
        self.assertEqual(len(called),3)
        self.assertEqual(called[0],called[2])
    def test_wrong_arg_or_root_does_not_touch_units(self):
        output=io.StringIO()
        with patch.object(m,"call",side_effect=AssertionError("should not run")):
            with redirect_stdout(output):
                self.assertEqual(m.main(["--send-once"]),2)
                with patch.object(m.os,"geteuid",return_value=1000):
                    self.assertEqual(m.main(["--inspect"]),2)

if __name__=="__main__":
    unittest.main()
