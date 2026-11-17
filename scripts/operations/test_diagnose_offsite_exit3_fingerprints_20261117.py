import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

PATH=Path(__file__).with_name("diagnose-offsite-exit3-fingerprints-20261117.py")
SPEC=importlib.util.spec_from_file_location("offsite_exit3_fingerprint",PATH)
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

ID="a"*32
PROPS={"Id":m.UNIT,"LoadState":"loaded","ActiveState":"failed",
       "SubState":"failed","Result":"exit-code","ExecMainStatus":"3",
       "InvocationID":ID}
UNIT="".join(f"{k}={v}\n" for k,v in PROPS.items())
class Runner:
    def __init__(self,log="",after=UNIT,rc=0):
        self.log=log
        self.after=after
        self.rc=rc
        self.calls=[]
    def __call__(self,command,**kwargs):
        self.calls.append(command)
        assert kwargs["check"] is False
        if command[0]=="/usr/bin/systemctl":
            raw=UNIT if len(self.calls)==1 else self.after
            return SimpleNamespace(returncode=0,stdout=raw.encode())
        if command[0]=="/usr/bin/journalctl":
            assert command[-1]=="_SYSTEMD_INVOCATION_ID="+ID
            return SimpleNamespace(returncode=self.rc,stdout=self.log.encode())
        raise AssertionError("UNSUPPORTED_COMMAND")

class Fingerprints(unittest.TestCase):
    def test_keyed_marker_is_not_double_counted(self):
        result=m.scan("KMJ_OFFSITE=BLOCKED_UNKNOWN_SAFE_REASON\n")
        self.assertEqual(result,(1,[("KEYED","KMJ_OFFSITE","BLOCKED_UNKNOWN_SAFE_REASON")]))
    def test_repeat_same_marker_counts_appearances_but_only_one_unique(self):
        appearances,unique=m.scan("STATUS=BLOCKED_SOURCE\nSTATUS=BLOCKED_SOURCE\n")
        self.assertEqual(appearances,2)
        self.assertEqual(unique,[("KEYED","STATUS","BLOCKED_SOURCE")])
    def test_mixed_keyed_loose_deduplicated(self):
        appearances,unique=m.scan("STATUS=BLOCKED_SOURCE\nBLOCKED_OTHER\nRESULT=FAILED_UNSUPPORTED\n")
        self.assertEqual(appearances,3)
        self.assertEqual(len(unique),3)
        self.assertEqual([x[0] for x in unique],["KEYED","STANDALONE","KEYED"])
    def test_digest_is_fixed_ascii_sha256(self):
        self.assertEqual(m.digest("STATUS"),
                         "f799f958bd2dc580608a2bca53e4f7d1805222ca277d1b3500429175bd708042")
    def test_empty_journal_no_fabricated_guards(self):
        self.assertEqual(m.scan(""),(0,[]))
    def test_wrong_unit_status_or_invocation_fails_closed(self):
        for raw in [
            UNIT.replace(m.UNIT,"ssh.service"),
            UNIT.replace("ExecMainStatus=3","ExecMainStatus=255"),
            UNIT.replace("InvocationID="+ID,"InvocationID="+"0"*32),
            UNIT.replace("ActiveState=failed","ActiveState=active"),
            UNIT.replace("Result=exit-code","Result=success"),
            UNIT+"Result=exit-code\n",
        ]:
            with self.subTest(raw=raw[:35]):
                with self.assertRaises(ValueError):
                    m.parse_systemd(raw)
    def test_exact_command_identity_and_stability(self):
        runner=Runner("KMJ_OFFSITE=BLOCKED_UNRECOGNIZED\n")
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner):
            result=m.inspect()
        self.assertEqual(result[0],1)
        self.assertEqual(len(runner.calls),3)
        self.assertEqual(runner.calls[0],runner.calls[2])
    def test_concurrent_restart_is_refused(self):
        runner=Runner("STATUS=BLOCKED_X\n",after=UNIT.replace(ID,"b"*32))
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"INVOCATION_CHANGED"):
                m.inspect()
    def test_no_root_no_subprocess(self):
        runner=Runner("STATUS=BLOCKED_X\n")
        with patch.object(m.os,"geteuid",return_value=1000), \
             patch.object(m.subprocess,"run",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"ROOT_ELITE_REQUIRED"):
                m.inspect()
        self.assertEqual(runner.calls,[])
    def test_no_secrets_or_raw_guard_names_in_receipt(self):
        journal="KMJ_OFFSITE=BLOCKED_ALPHANUMERICTOKEN\nSensitive /root/.ssh/private\n"
        runner=Runner(journal)
        output=io.StringIO()
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.os,"uname",return_value=SimpleNamespace(nodename="KMJ-elite")), \
             patch.object(m.subprocess,"run",side_effect=runner), \
             redirect_stdout(output):
            self.assertEqual(m.main(["--inspect"]),0)
        out=output.getvalue()
        self.assertIn("DISTINCT_MARKERS_BOUND=1",out)
        self.assertIn("MARKER_1_KIND=KEYED",out)
        self.assertIn("RAW_JOURNAL_EXPOSED=NO",out)
        self.assertIn("BACKUP_REPAIR=NOT_ATTEMPTED",out)
        for secret in ("BLOCKED_ALPHANUMERICTOKEN","KMJ_OFFSITE",
                       "Sensitive","/root/",".ssh","private"):
            self.assertNotIn(secret,out)
    def test_no_argument_injection(self):
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(m.main(["--backup"]),2)
        self.assertIn("BLOCKED_EXACT_INSPECT_ONLY",output.getvalue())
    def test_journal_oversize_rejected(self):
        with self.assertRaisesRegex(ValueError,"OVERSIZED_JOURNAL"):
            m.scan("x"*(m.MAX_BYTES+1))

if __name__=="__main__":
    unittest.main()
