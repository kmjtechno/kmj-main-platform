"""KMJ TECHNO: disposable, no-root negative tests for the cert link target inspector."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import unittest

FILE = Path(__file__).with_name("KMJ_LETSENCRYPT_INTERNAL_LINK_TARGET_READONLY_20261115.py")
spec = importlib.util.spec_from_file_location("kmj_cert_link_target_readonly", FILE)
m = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(m)

class CertLinkTargetTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="kmj-cert-links-test-")
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        for name in ("archive", "archive/site", "live", "live/site"):
            (self.root / name).mkdir(mode=0o700)
        (self.root / "archive/site/cert1.pem").write_bytes(b"fixture-certificate\n")
        self.symlink = self.root / "live/site/cert.pem"
        self.uid = os.geteuid()

    def check(self, expected=1):
        return m.inspect_tree(self.root, self.uid, expected=expected)

    def test_single_certbot_style_in_tree_link(self):
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        x = self.check()
        self.assertEqual(x["links"], 1)
        self.assertEqual(x["targets"], 1)
        self.assertEqual(x["special"], 0)

    def test_reject_absolute_target(self):
        self.symlink.symlink_to("/etc/passwd")
        with self.assertRaisesRegex(m.Block, "LINK_ABSOLUTE_OR_INVALID"):
            self.check()

    def test_reject_escaping_relative_target(self):
        self.symlink.symlink_to("../../../../etc/passwd")
        with self.assertRaisesRegex(m.Block, "LINK_TARGET_ESCAPES_ROOT"):
            self.check()

    def test_reject_target_file_symlink_indirection(self):
        (self.root / "archive/site/cert1.pem").unlink()
        (self.root / "archive/site/cert1.pem").symlink_to("/etc/passwd")
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaises(m.Block):
            self.check()

    def test_reject_target_parent_symlink_indirection(self):
        (self.root / "archive/site/cert1.pem").unlink()
        (self.root / "archive/site").rmdir()
        (self.root / "archive/site").symlink_to("/tmp")
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaises(m.Block):
            self.check()

    def test_reject_missing_target(self):
        self.symlink.symlink_to("../../archive/site/missing.pem")
        with self.assertRaises(m.Block):
            self.check()

    def test_reject_special_target(self):
        target = self.root / "archive/site/cert1.pem"
        target.unlink()
        os.mkfifo(target)
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaises(m.Block):
            self.check()

    def test_reject_world_writable_certificate(self):
        target = self.root / "archive/site/cert1.pem"
        target.chmod(0o666)
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaises(m.Block):
            self.check()

    def test_reject_hardlinked_cert(self):
        os.link(self.root / "archive/site/cert1.pem",
                self.root / "archive/site/cert2.pem")
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaisesRegex(m.Block, "TARGET_FILE_UNTRUSTED"):
            self.check()

    def test_reject_link_count_drift(self):
        self.symlink.symlink_to("../../archive/site/cert1.pem")
        with self.assertRaisesRegex(m.Block, "LINK_COUNT_NOT_EXPECTED"):
            self.check(expected=8)

    def test_reject_special_source_entry(self):
        sk = socket.socket(socket.AF_UNIX)
        try:
            sk.bind(str(self.root / "archive/site/live.sock"))
            self.symlink.symlink_to("../../archive/site/cert1.pem")
            with self.assertRaisesRegex(m.Block, "SOURCE_SPECIAL_ENTRY"):
                self.check()
        finally:
            sk.close()

    def test_reject_invalid_expected_link_count(self):
        for count in (-1, 65, True):
            with self.subTest(count=count), self.assertRaisesRegex(
                m.Block, "LINK_EXPECTATION_INVALID"
            ):
                self.check(expected=count)

    def test_selftest_uses_only_disposable_fixture(self):
        self.assertEqual(m.main.__name__, "main")
        m.selftest()

if __name__ == "__main__":
    unittest.main()
