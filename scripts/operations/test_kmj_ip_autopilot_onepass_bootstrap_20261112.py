#!/usr/bin/env python3
"""Isolated root-private helper tests for the 20261112 onepass bootstrap.

No cloud accounts, package installs, live units, DNS edits, or secret prompts.
All file writes in these tests are inside disposable /run temp directories.
"""
import importlib.util
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("kmj-ip-autopilot-onepass-bootstrap-20261112.py")
spec = importlib.util.spec_from_file_location("kmj_ip_bootstrap", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OnepassBootstrapTests(unittest.TestCase):
    def test_exact_scope_and_pins(self):
        self.assertEqual(m.ZONE, "49f7523905736979a04e93497d8ccd43")
        self.assertEqual(m.TUNNEL_ID, "b18c637f-2700-442a-a12e-b225c43dfc72")
        self.assertEqual(len(m.FILES), 6)
        self.assertTrue(all(len(v) == 64 and all(c in "0123456789abcdef" for c in v)
                            for v in m.FILES.values()))
        self.assertEqual(m.CANARY, "https://tunnel-canary.kmjtechno.com/")

    def test_write_new_maintains_ownership_mode_and_readback(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            f = Path(td) / "f"
            m.write_new(f, b"safe-fixture", 0o600)
            self.assertEqual(f.read_bytes(), b"safe-fixture")
            self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
            self.assertEqual(f.stat().st_uid, 0)
            m.write_new(f, b"safe-fixture", 0o600)

    def test_write_new_rejects_content_drift(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            f = Path(td) / "f"
            m.write_new(f, b"original", 0o600)
            with self.assertRaisesRegex(m.Stop, "EXISTING_TARGET_NOT_PINNED"):
                m.write_new(f, b"mismatch", 0o600)
            self.assertEqual(f.read_bytes(), b"original")

    def test_symlink_sources_and_targets_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            target = Path(td) / "original"
            target.write_bytes(b"something")
            symlink = Path(td) / "link"
            symlink.symlink_to(target)
            with self.assertRaises(m.Stop):
                m.regular_nosymlink(symlink)
            with self.assertRaises(m.Stop):
                m.read_pinned(symlink, hashlib.sha256(target.read_bytes()).hexdigest())
            with self.assertRaises(m.Stop):
                m.write_new(symlink, b"replacement", 0o600)
            self.assertEqual(target.read_bytes(), b"something")

    def test_source_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            p = Path(td) / "source"
            p.write_bytes(b"test-string")
            with self.assertRaisesRegex(m.Stop, "QA_SOURCE_SHA256_MISMATCH"):
                m.read_pinned(p, "0"*64)
            self.assertEqual(m.read_pinned(p, hashlib.sha256(b"test-string").hexdigest()), b"test-string")

    def test_private_dir_rejects_symlinks_and_world_writable(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            root = Path(td) / "private"
            m.root_dir(root, 0o700)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            root.chmod(0o777)
            with self.assertRaisesRegex(m.Stop, "DIR_OWNER_OR_MODE_DRIFT"):
                m.root_dir(root, 0o700)
            root.chmod(0o700)
            link = Path(td) / "link"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(m.Stop, "PRIVATE_DIR_SYMLINK"):
                m.root_dir(link, 0o700)

    def test_existing_private_token_is_never_returned(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            p = Path(td) / "token"
            original = b"A" * 44
            m.write_new(p, original, 0o600)
            with patch.object(m, "report") as report:
                m.capture_token(p, prompt="unused", pattern=r"[A-Za-z0-9_-]{32,250}")
            report.assert_called_with("TOKEN", "PRIVATE_EXISTING")
            self.assertEqual(p.read_bytes(), original)

    def test_existing_token_bad_mode_blocks(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ip-bootstrap-test-", dir="/run") as td:
            p = Path(td) / "token"
            m.write_new(p, b"B" * 44, 0o600)
            p.chmod(0o644)
            with self.assertRaisesRegex(m.Stop, "TOKEN_FILE_OWNER_OR_MODE"):
                m.capture_token(p, prompt="unused", pattern=r"[A-Za-z0-9_-]{32,250}")

    def test_no_production_dns_or_service_override(self):
        source = SCRIPT.read_text("utf-8")
        self.assertNotIn("kmj-elite-health-check.service", source)
        self.assertNotIn("kmj-elite-offsite-backup.service", source)
        self.assertNotIn("/home/kmjprod/current", source)
        self.assertNotIn("systemctl restart nginx", source)
        self.assertNotIn("cloudflared service install", source)
        self.assertNotIn("CLOUDFLARE_API_TOKEN=", source)
        self.assertIn('read_agent_inspect()', source)
        self.assertIn('if not canary_ready()', source)
        self.assertIn('DNS_CUTOVER", "NOT_ATTEMPTED"', source)
        self.assertIn('PRODUCTION_DNS_CUTOVER", "NOT_ATTEMPTED"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
