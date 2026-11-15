"""Disposable metadata-only tests for KMJ P0 source-link classifier."""
import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

NAME=Path(__file__).with_name("KMJ_HEALTH_SOURCE_ENTRY_CLASSIFIER_READONLY_20261115.py")
spec=importlib.util.spec_from_file_location("kmj_source_entry_classifier",NAME)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SourceEntryClassifierFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/"root"
        self.root.mkdir(mode=0o700)

    def test_fixtures_symlink_types_without_follow(self):
        (self.root/"archive").mkdir()
        (self.root/"live").mkdir()
        (self.root/"archive"/"source.pem").write_bytes(b"fixture")
        (self.root/"live"/"valid.pem").symlink_to("../archive/source.pem")
        (self.root/"live"/"unsafe-abs").symlink_to("/etc/passwd")
        (self.root/"live"/"unsafe-escape").symlink_to("../../../../etc/passwd")
        result=m.scan_tree(self.root)
        self.assertEqual(result["counts"]["symlinks"],3)
        self.assertEqual(result["counts"]["regular"],1)
        self.assertEqual(result["kinds"]["RELATIVE_LINK_LEXICALLY_IN_TREE"],1)
        self.assertEqual(result["kinds"]["RELATIVE_LINK_ESCAPES_SOURCE_ROOT"],1)
        self.assertEqual(result["kinds"]["ABSOLUTE_LINK"],1)

    def test_socket_does_not_trigger_file_read_or_follow(self):
        sock=socket.socket(socket.AF_UNIX)
        try:
            sock.bind(str(self.root/"runtime.sock"))
            results=m.scan_tree(self.root)
            self.assertEqual(results["kinds"]["UNIX_SOCKET"],1)
            self.assertEqual(results["counts"]["special"],1)
        finally:
            sock.close()

    def test_fifo_is_classified_without_open(self):
        os.mkfifo(self.root/"fifo")
        report=m.scan_tree(self.root)
        self.assertEqual(report["kinds"]["FIFO"],1)

    def test_reject_unbounded_scans(self):
        with self.assertRaisesRegex(m.Blocked,"SCANNER_BOUND_INVALID"):
            m.scan_tree(self.root,cap=0)
        (self.root/"a").write_text("safe")
        (self.root/"b").write_text("safe")
        with self.assertRaisesRegex(m.Blocked,"SCAN_ENTRY_LIMIT"):
            m.scan_tree(self.root,cap=1)

    def test_reject_symlink_source_root(self):
        alt=self.base/"alias"
        alt.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):
            m.scan_tree(alt)

    def test_scanner_does_not_open_regular_file_data(self):
        (self.root/"db.env").write_text("fixture-no-real-secrets")
        real_open=os.open
        def intercept(path,flags,*args,**kwargs):
            if str(path).endswith("db.env"):
                raise AssertionError("DANGEROUS_FILE_CONTENT_READ")
            return real_open(path,flags,*args,**kwargs)
        with mock.patch.object(m.os,"open",side_effect=intercept):
            self.assertEqual(m.scan_tree(self.root)["counts"]["regular"],1)

    def test_relative_lexical_path_is_not_declared_safe(self):
        self.assertNotIn("SAFE",m._relative_link_class("live","../archive/file"))
        self.assertEqual(m._relative_link_class("live","../../outside"),"RELATIVE_LINK_ESCAPES_SOURCE_ROOT")

    def test_runtime_inspection_is_not_a_backup(self):
        self.assertFalse(hasattr(m,"backup"))
        self.assertFalse(hasattr(m,"run_once"))
        self.assertEqual(m.selftest(),0)

if __name__=="__main__":
    unittest.main()
