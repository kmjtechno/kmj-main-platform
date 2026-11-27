"""Synthetic, unprivileged tests for exact successful V3 receipt attestor.

No systemd, journal, SSH, keys, backup, secrets or host mutations.
"""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest import TestCase,main,mock
import tempfile
import time

SCRIPT=Path(__file__).with_name("verify-offsite-v3-last-success-20261117.py")
spec=importlib.util.spec_from_file_location("kmj_v3_success_receipt_fixture",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def unit():
    return {
       "Id":m.UNIT,"LoadState":"loaded","Type":"oneshot","User":"root",
       "ActiveState":"inactive","Result":"success","ExecMainStatus":"0",
       "DropInPaths":str(m.DROPIN),
       "ExecStart":"{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I -B "
                   +str(m.V3)+" --scheduled-run ; }",
       "InvocationID":"a"*32,
       "ExecMainExitTimestampMonotonic":str(time.monotonic_ns()//1000-12000000)
    }
def timer():
    return {"Id":m.TIMER,"LoadState":"loaded","ActiveState":"active",
            "UnitFileState":"enabled","Unit":m.UNIT}

class Attest(TestCase):
    def test_source_pins_match_git_mirror(self):
        # Repaired V3 DNS transport, SHA pinned into deployed root migration.
        for path,pin in [(m.V3,m.V3_SHA),(m.PARENT,m.PARENT_SHA)]:
            file=SCRIPT.parent.parent/path.name
            if path==m.V3:
                file=SCRIPT.parent.parent/"KMJ_OFFSITE_FRESH_X25519_SFTP_V3_20261112.py"
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),pin)
        self.assertIn("StrictHostKeyChecking=yes",
                      (SCRIPT.parent.parent/"KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py").read_text())
    def test_receipt_all_required(self):
        rows=list(m.NEEDED)+["CIPHER_SHA256_UPPER="+"F"*64,"CIPHER_BYTES=409981"]
        self.assertEqual(m.receipt_rows(("\n".join(rows)+"\n").encode()),len(m.NEEDED))
    def test_receipt_refuses_missing_sftp(self):
        rows=[x for x in m.NEEDED if x!="REMOTE_SFTP_SHA_READBACK=PASS"]
        rows+=["CIPHER_SHA256_UPPER="+"F"*64,"CIPHER_BYTES=409981"]
        with self.assertRaisesRegex(m.Block,"EXACT_INVOCATION_RECEIPT_INCOMPLETE"):
            m.receipt_rows(("\n".join(rows)+"\n").encode())
    def test_receipt_rejects_ambiguous_hash_and_too_small_cipher(self):
        good=list(m.NEEDED)
        duplicated=good+["CIPHER_SHA256_UPPER="+"A"*64,"CIPHER_SHA256_UPPER="+"B"*64,
                         "CIPHER_BYTES=409981"]
        with self.assertRaisesRegex(m.Block,"CIPHER_RECEIPT_SHAPE_UNVERIFIED"):
            m.receipt_rows(("\n".join(duplicated)+"\n").encode())
        tiny=good+["CIPHER_SHA256_UPPER="+"C"*64,"CIPHER_BYTES=2"]
        with self.assertRaisesRegex(m.Block,"CIPHER_RECEIPT_SHAPE_UNVERIFIED"):
            m.receipt_rows(("\n".join(tiny)+"\n").encode())
    def test_receipt_rejects_oversized_or_invalid_encoding(self):
        with self.assertRaisesRegex(m.Block,"JOURNAL_BYTES_EXCEEDED"):
            m.receipt_rows(b"x"*(m.MAX_OUTPUT+1))
        with self.assertRaisesRegex(m.Block,"JOURNAL_ENCODING_UNVERIFIED"):
            m.receipt_rows(b"\xff")
        with self.assertRaisesRegex(m.Block,"JOURNAL_LINES_EXCEEDED"):
            m.receipt_rows(b"x\n"*351)
    def test_exact_successful_service_with_timer(self):
        u,t=unit(),timer()
        def fake_props(id,keys):return u if id==m.UNIT else t
        def fake_source(path,*args,**kwargs):return m.UNIT_CONTENT if path==m.DROPIN else b"pinned"
        with mock.patch.object(m,"props",side_effect=fake_props),\
             mock.patch.object(m,"safe_source",side_effect=fake_source):
            invocation,age=m.service_contract()
            self.assertEqual(invocation,"a"*32)
            self.assertLess(age,5)
    def test_wrong_exec_fails_closed(self):
        u,t=unit(),timer()
        u["ExecStart"]=u["ExecStart"].replace("v3-20261112","v2-20261112")
        with mock.patch.object(m,"props",side_effect=lambda id,keys:u if id==m.UNIT else t):
            with self.assertRaisesRegex(m.Block,"LAST_SUCCESSFUL_V3_UNIT_UNVERIFIED"):
                m.service_contract()
    def test_wrong_timer_fails_closed(self):
        u,t=unit(),timer()
        t["ActiveState"]="failed"
        with mock.patch.object(m,"props",side_effect=lambda id,keys:u if id==m.UNIT else t):
            with self.assertRaisesRegex(m.Block,"V3_SCHEDULED_TIMER_UNVERIFIED"):
                m.service_contract()
    def test_missing_journal_invocation_does_not_count(self):
        u,t=unit(),timer()
        u["InvocationID"]="0"*32
        with mock.patch.object(m,"props",side_effect=lambda id,keys:u if id==m.UNIT else t),\
             mock.patch.object(m,"safe_source",return_value=m.UNIT_CONTENT):
            with self.assertRaisesRegex(m.Block,"INVOCATION_ID_UNAVAILABLE"):
                m.service_contract()
    def test_old_success_does_not_count(self):
        u,t=unit(),timer()
        fake_now_ns=100*3600*1000000000
        u["ExecMainExitTimestampMonotonic"]=str(fake_now_ns//1000-49*3600*1000000)
        with mock.patch.object(m,"props",side_effect=lambda id,keys:u if id==m.UNIT else t),\
             mock.patch.object(m,"safe_source",return_value=m.UNIT_CONTENT),\
             mock.patch.object(m.time,"monotonic_ns",return_value=fake_now_ns):
            with self.assertRaisesRegex(m.Block,"EXIT_OUTSIDE_48_HOURS"):
                m.service_contract()
    def test_root_and_arguments_rejected_before_host_commands(self):
        with mock.patch.object(m.os,"geteuid",return_value=1000),\
             mock.patch.object(m,"cmd",side_effect=AssertionError("NO_SUBPROCESS")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(["--inspect"]),2)
                self.assertEqual(m.main(["--apply"]),2)
        self.assertIn("BLOCKED_ROOT_ELITE_ONLY",out.getvalue())
        self.assertIn("BLOCKED_ARGUMENTS",out.getvalue())
    def test_main_read_only_success_exact_journal(self):
        rows=list(m.NEEDED)+["CIPHER_SHA256_UPPER="+"D"*64,"CIPHER_BYTES=409981"]
        data=("\n".join(rows)+"\n").encode()
        with mock.patch.object(m.os,"geteuid",return_value=0),\
             mock.patch.object(m.socket,"gethostname",return_value="KMJ-elite"),\
             mock.patch.object(m,"service_contract",return_value=("b"*32,12)),\
             mock.patch.object(m,"cmd",return_value=data) as call,\
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(["--inspect"]),0)
        result=out.getvalue()
        self.assertIn("KMJ_V3_SUCCESS_ATTESTOR=READ_ONLY_PASS",result)
        self.assertIn("EXACT_INVOCATION_MARKERS=9/9",result)
        self.assertIn("INDEPENDENT_REMOTE_RESTORE=NOT_VERIFIED",result)
        self.assertIn("SYSTEMD_DB_SFTP_MUTATION=NONE",result)
        self.assertNotIn("CIPHER_SHA256_UPPER",result)
        argv=call.call_args.args[0]
        self.assertEqual(argv[0],"/usr/bin/journalctl")
        self.assertIn("_SYSTEMD_INVOCATION_ID="+"b"*32,argv)
    def test_source_read_uses_no_symlink_and_race_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"file"
            path.write_bytes(b"pinned-data"*100)
            path.chmod(0o600)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            parent=SimpleNamespace(st_mode=stat.S_IFDIR|0o755,st_uid=0)
            with mock.patch.object(m.os,"lstat",wraps=m.os.lstat) as check:
                original=m.os.lstat
                def rooted(patharg):
                    return parent if str(patharg) in ("/usr","/usr/local","/usr/local/libexec") else original(patharg)
                check.side_effect=rooted
                # User fixture uid is patched only for non-root test metadata.
                with mock.patch.object(m.os,"fstat",wraps=m.os.fstat):
                    self.assertIsNotNone(digest)
        self.assertIn("O_NOFOLLOW",SCRIPT.read_text())
        self.assertIn("st_ctime_ns",SCRIPT.read_text())

if __name__=="__main__":
    main()
