import importlib.util
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/operations/install-elite-a892-stage-storage-attestation-20261128.py"
spec=importlib.util.spec_from_file_location("stage_storage_install",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StorageAttestationTests(unittest.TestCase):
    def test_create_no_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"marker"
            inode=m.create(p,b"original\n",0o444)
            self.assertEqual(m.identity(p),inode)
            self.assertEqual(p.stat().st_mode & 0o777,0o444)
            with self.assertRaises(FileExistsError):
                m.create(p,b"replacement",0o444)
            self.assertEqual(p.read_bytes(),b"original\n")

    def test_create_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"a",Path(d)/"b"
            a.write_bytes(b"preserved")
            b.symlink_to(a)
            with self.assertRaises(OSError):
                m.create(b,b"changed",0o644)
            self.assertEqual(a.read_bytes(),b"preserved")

    def test_exact_mount_plan_pin(self):
        self.assertEqual(m.UNIT_SHA,"dab5cc217ee4180f63ec3526a53c7f9a183720e2862067469be57c6905641338")
        self.assertEqual(set(m.PINS),{"attest","repair","builder","rehearsal","plan"})


if __name__=="__main__":
    unittest.main()
