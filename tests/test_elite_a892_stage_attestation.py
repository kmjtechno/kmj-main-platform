import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/operations/attest-elite-a892-stage-source-20261128.py"
spec=importlib.util.spec_from_file_location("stage_attestation",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AttestationTests(unittest.TestCase):
    def test_git_blob_pin(self):
        raw=b"abc"
        self.assertTrue(m.pin(raw,hashlib.sha1(b"blob 3\0abc").hexdigest()))
        self.assertFalse(m.pin(raw,"0"*40))

    def test_no_clobber_and_readonly_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"marker"
            inode=m.install_marker(p,m.SHA)
            self.assertEqual(p.read_bytes(),(m.SHA+"\n").encode())
            self.assertEqual(p.stat().st_mode & 0o777,0o444)
            with self.assertRaises(FileExistsError):
                m.install_marker(p,m.SHA)
            m.remove_own(p,inode)
            self.assertFalse(p.exists())

    def test_refuse_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"a",Path(tmp)/"b"
            a.write_text("original")
            b.symlink_to(a)
            with self.assertRaises(OSError):
                m.install_marker(b,m.SHA)
            self.assertEqual(a.read_text(),"original")

    def test_refuse_invalid_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"marker"
            with self.assertRaisesRegex(ValueError,"MARKER_SHA"):
                m.install_marker(p,"fake")
            self.assertFalse(p.exists())

    def test_rollback_refuses_wrong_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"marker"
            inode=m.install_marker(p,m.SHA)
            with self.assertRaisesRegex(ValueError,"MARKER_ROLLBACK_DRIFT"):
                m.remove_own(p,(inode[0],inode[1]+1))
            self.assertTrue(p.exists())


if __name__=="__main__":
    unittest.main()
