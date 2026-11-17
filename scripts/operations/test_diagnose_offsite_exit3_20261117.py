import importlib.util
from pathlib import Path
import unittest

SRC=Path(__file__).with_name("diagnose-offsite-exit3-20261117.py")
spec=importlib.util.spec_from_file_location("kmj_exit3",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

BASE=(
"Id=kmj-elite-offsite-backup.service\n"
"LoadState=loaded\n"
"ActiveState=failed\n"
"SubState=failed\n"
"Result=exit-code\n"
"ExecMainStatus=3\n"
"InvocationID="+"a"*32+"\n"
)

class Exit3ClassifierTests(unittest.TestCase):
    def test_distinct_failure_classes(self):
        pairs=(
            ("SHA256 mismatch on local pinned source","PINNED_SOURCE_OR_IDENTITY_MISMATCH"),
            ("no space left on device","LOCAL_CAPACITY_OR_QUOTA"),
            ("Temporary failure in name resolution","REMOTE_NETWORK_OR_DNS"),
            ("Permission denied (publickey)","REMOTE_HOSTKEY_OR_SSH_AUTH"),
            ("remote sha readback mismatch","REMOTE_CIPHER_OR_READBACK_MISMATCH"),
            ("invalid recipient","RECIPIENT_OR_ENCRYPTION_INVALID"),
            ("permission denied opening root-only file","LOCAL_FILE_PERMISSIONS"),
            ("command not found","MISSING_TOOL_OR_RUNTIME"),
            ("missing dump artifact","LOCAL_BACKUP_OR_SOURCE_MISSING"),
        )
        for raw,expected in pairs:
            with self.subTest(expected=expected):
                self.assertEqual(m.exact_classify(BASE,raw),expected)

    def test_ambiguous_and_empty_are_unknown(self):
        self.assertEqual(m.exact_classify(BASE,"No distinct journal markers"),"UNKNOWN_EXIT3_NEEDS_OWNER_REVIEW")
        self.assertEqual(m.exact_classify(BASE,""),"UNKNOWN_NO_JOURNAL")

    def test_wrong_invocation_or_unit_never_reads_journal(self):
        for modified in (
            BASE.replace("ExecMainStatus=3","ExecMainStatus=255"),
            BASE.replace("Result=exit-code","Result=success"),
            BASE.replace("ActiveState=failed","ActiveState=active"),
            BASE.replace("InvocationID="+"a"*32,"InvocationID=malformed"),
            BASE.replace("Id=kmj-elite-offsite-backup.service","Id=other.service"),
            BASE+"Result=exit-code\n",
            BASE.replace("LoadState=loaded\n",""),
        ):
            with self.subTest(modified=modified[-80:]):
                with self.assertRaises(ValueError):
                    m.exact_classify(modified,"Permission denied")

    def test_no_privilege_needed_for_fixture_but_real_inspect_rejects_wrong_args(self):
        self.assertEqual(m.main([]),2)
        self.assertEqual(m.main(["--prepare"]),2)

    def test_bounded_vocabulary_only(self):
        self.assertTrue(all(name.isupper() and len(name)<65 for name,_ in m.RULES))
        self.assertNotIn("secret",m.classify("some arbitrary unrelated line"))
        self.assertEqual(m.classify("A"*200000),"UNKNOWN_EXIT3_NEEDS_OWNER_REVIEW")

if __name__=="__main__":
    unittest.main()
