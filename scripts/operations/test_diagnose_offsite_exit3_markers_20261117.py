import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

PATH=Path(__file__).resolve().with_name("diagnose-offsite-exit3-markers-20261117.py")
SPEC=importlib.util.spec_from_file_location("marker_diag",PATH)
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

ID="a"*32
BEFORE="".join(f"{key}={value}\n" for key,value in dict(
    Id=m.UNIT,LoadState="loaded",ActiveState="failed",SubState="failed",
    Result="exit-code",ExecMainStatus="3",InvocationID=ID
).items())
AFTER=BEFORE.replace(ID,"b"*32)

class Runner:
    def __init__(self,log,before=BEFORE,after=BEFORE,journal_return=0):
        self.log=log
        self.before=before
        self.after=after
        self.journal_return=journal_return
        self.calls=[]
    def __call__(self,argv,**kwargs):
        self.calls.append(argv)
        self_kwargs=kwargs
        assert self_kwargs.get("check") is False
        assert self_kwargs.get("stderr") is not None
        if argv[0]=="/usr/bin/systemctl":
            content=self.before if len(self.calls)==1 else self.after
            return SimpleNamespace(returncode=0,stdout=content.encode())
        if argv[0]=="/usr/bin/journalctl":
            assert argv[-1]=="_SYSTEMD_INVOCATION_ID="+ID
            return SimpleNamespace(returncode=self.journal_return,stdout=self.log.encode())
        raise AssertionError("UNEXPECTED_COMMAND")

class Cases(unittest.TestCase):
    def test_distinct_guard_classifications_without_raw_markers(self):
        fixtures=[
            ("KMJ_BACKUP=BLOCKED_SHA_MISMATCH","SOURCE_PIN_OR_IDENTITY_GUARD"),
            ("KMJ_OFFSITE=BLOCKED_DATABASE_DUMP","DATABASE_OR_DUMP_GUARD"),
            ("KMJ_OFFSITE=BLOCKED_STORAGE_NOT_SHARED","STORAGE_OR_UPLOADS_GUARD"),
            ("RESULT=BLOCKED_SFTP_REMOTE_READBACK","REMOTE_TRANSFER_OR_READBACK_GUARD"),
            ("STATUS=BLOCKED_X25519_RECIPIENT","CRYPTO_OR_RECIPIENT_GUARD"),
            ("KMJ_OFFSITE=BLOCKED_OWNER_MODE","PERMISSION_OR_OWNERSHIP_GUARD"),
            ("KMJ_OFFSITE=BLOCKED_FRESHNESS","RESOURCE_OR_FRESHNESS_GUARD"),
            ("RESULT=BLOCKED_RUNTIME","CONFIG_OR_RUNTIME_GUARD"),
            ("RESULT=BLOCKED_APPROVAL","APPROVAL_OR_POLICY_GUARD"),
            ("BLOCKED_UNRECOGNIZED_SAFE_TOKEN","OTHER_PROTECTED_GUARD"),
            ("Host key verification failed","REMOTE_HOSTKEY_MESSAGE"),
            ("No space left on device","CAPACITY_MESSAGE"),
        ]
        for raw,expected in fixtures:
            with self.subTest(raw=raw):
                kind,category,nlines,count=m.triage(raw)
                self.assertEqual(category,expected)
                self.assertEqual(nlines,1)
                self.assertEqual(count>0,raw.startswith("BLOCKED_") or "BLOCKED_" in raw)
    def test_no_log_or_no_marker_do_not_fabricate_cause(self):
        self.assertEqual(m.triage(""),("NO_GUARD_MARKERS","EMPTY_JOURNAL",0,0))
        self.assertEqual(m.triage("systemd status 3\n"),("NO_GUARD_MARKERS","NO_CLASSIFIABLE_MARKER",1,0))
    def test_reject_wrong_exit_unit_duplicate_or_invocation(self):
        invalid=[
            BEFORE.replace("ExecMainStatus=3","ExecMainStatus=0"),
            BEFORE.replace(ID,"0"*32),
            BEFORE.replace("ActiveState=failed","ActiveState=active"),
            BEFORE.replace("Id="+m.UNIT,"Id=ssh.service"),
            BEFORE.replace("Result=exit-code","Result=success"),
            BEFORE+"Result=exit-code\n",
        ]
        for bad in invalid:
            with self.subTest(head=bad[:30]):
                with self.assertRaises(ValueError):
                    m.snapshot(bad)
    def test_exact_invocation_unchanged_attestation(self):
        runner=Runner("KMJ_OFFSITE=BLOCKED_STORAGE_NOT_SHARED")
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner):
            status=m.inspect()
        self.assertEqual(status[1],"STORAGE_OR_UPLOADS_GUARD")
        self.assertEqual(len(runner.calls),3)
        self.assertEqual(runner.calls[0],runner.calls[-1])
    def test_changed_invocation_fails_closed(self):
        runner=Runner("KMJ_BACKUP=BLOCKED_REMOTE",after=AFTER)
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"INVOCATION_CHANGED"):
                m.inspect()
    def test_root_required_before_systemd_access(self):
        runner=Runner("KMJ_BACKUP=BLOCKED_REMOTE")
        with patch.object(m.os,"geteuid",return_value=1000), \
             patch.object(m.subprocess,"run",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"ROOT_ELITE_REQUIRED"):
                m.inspect()
        self.assertEqual(runner.calls,[])
    def test_output_only_allowlisted_metadata(self):
        runner=Runner("SECRET key path /root/.ssh/authorized_keys\nKMJ_OFFSITE=BLOCKED_STORAGE_NOT_SHARED")
        out=io.StringIO()
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner), \
             redirect_stdout(out):
            self.assertEqual(m.main(["--inspect"]),0)
        response=out.getvalue()
        self.assertIn("GUARD_REASON_CLASS=STORAGE_OR_UPLOADS_GUARD",response)
        for secret in ("SECRET","/root/",".ssh","authorized_keys","BLOCKED_STORAGE_NOT_SHARED"):
            self.assertNotIn(secret,response)
        self.assertIn("BACKUP_REPAIR=NOT_ATTEMPTED",response)
        self.assertIn("PRODUCTION_APPROVAL=UNCHANGED",response)
    def test_bounded_journal_and_failed_read(self):
        with self.assertRaises(ValueError):
            m.triage("x"*(m.MAX_BYTES+1))
        runner=Runner("KMJ_OFFSITE=BLOCKED_STORAGE",journal_return=1)
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner):
            with self.assertRaises(ValueError):
                m.inspect()
    def test_no_caller_controlled_commands(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(m.main(["--execute"]),2)
        self.assertIn("BLOCKED_EXACT_INSPECT_ONLY",output.getvalue())
    def test_only_secret_free_receipt_fields(self):
        lines=io.StringIO()
        r=Runner("source=%n %p \nKMJ_OFFSITE=BLOCKED_OTHER_TOKEN")
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=r), \
             redirect_stdout(lines):
            self.assertEqual(m.main(["--inspect"]),0)
        self.assertNotIn("source=",lines.getvalue())
        self.assertNotIn("BLOCKED_OTHER_TOKEN",lines.getvalue())

if __name__=="__main__":
    unittest.main()
