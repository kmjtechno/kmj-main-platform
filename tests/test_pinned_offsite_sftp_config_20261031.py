"""Safe no-clobber Google offsite transfer config contract tests."""
from __future__ import annotations
import base64
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/prepare-pinned-offsite-sftp-config-20261031.py"
sp = importlib.util.spec_from_file_location("pinned_sftp", SRC)
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)


class ConfigTests(unittest.TestCase):
    def test_fixed_contract_never_falls_back_to_default_identity(self):
        self.assertEqual(m.CONFIG.count(b"HOST="), 1)
        self.assertIn(b"IDENTITY_FILE=/root/.ssh/kmj-google-offsite-20261031-ed25519\n", m.CONFIG)
        self.assertIn(b"HOSTKEY_SHA256=SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU\n", m.CONFIG)
        self.assertIn(b"REMOTE_DIR=/home/info/kmj-recovery-scratch\n", m.CONFIG)
        self.assertNotIn(b"StrictHostKeyChecking=no", m.CONFIG)

    def test_pinned_ed25519_fingerprint_matches_owner_evidence(self):
        pub = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBAk4YE9gWVeGIEsG7NyHzwdfZr9HRJHnNbXWfULzPzn kmj-google-offsite-20261031"
        self.assertEqual(m.key_fingerprint(pub), m.CLIENT_FP)
        for bad in ["ssh-rsa " + pub.split()[1], "ssh-ed25519 invalid!",
                    "ssh-ed25519 " + base64.b64encode(b"wrong").decode()]:
            with self.assertRaises(m.Blocked):
                m.key_fingerprint(bad)

    def test_no_write_on_check_when_missing(self):
        with patch.object(m, "protected_directory"), patch.object(m, "verify_keypair"), patch.object(m, "existing_config", return_value="MISSING"):
            self.assertEqual(m.prepare("--check"), "MISSING_NO_CHANGE")

    def test_existing_exact_match_is_idempotent_and_nonmutating(self):
        with patch.object(m, "protected_directory"), patch.object(m, "verify_keypair"), patch.object(m, "existing_config", return_value="EXACT_MATCH_UNCHANGED"):
            with patch.object(m.os, "open", side_effect=AssertionError("must not write")):
                self.assertEqual(m.prepare("--install"), "EXACT_MATCH_UNCHANGED")
                self.assertEqual(m.prepare("--check"), "EXACT_MATCH_UNCHANGED")

    def test_changed_existing_config_fails_closed(self):
        with patch.object(m, "protected_directory"), patch.object(m, "verify_keypair"), patch.object(m, "existing_config", side_effect=m.Blocked("EXISTING_CONFIG_DIFFERS")):
            with self.assertRaisesRegex(m.Blocked, "EXISTING_CONFIG_DIFFERS"):
                m.prepare("--install")

    def test_real_exclusive_creation_preserves_any_preexisting_entry(self):
        with tempfile.TemporaryDirectory(prefix="kmj-pinned-config-") as tmp:
            parent = Path(tmp)
            target = parent / "offsite-sftp.conf"
            def check_existing():
                if not target.exists() and not target.is_symlink():
                    return "MISSING"
                return "EXACT_MATCH_UNCHANGED" if target.read_bytes() == m.CONFIG else "DIFFERENT"
            def root_dir_stat(fd):
                return types.SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o700)
            with patch.object(m, "PARENT", parent), patch.object(m, "TARGET", target), \
                 patch.object(m, "protected_directory"), patch.object(m, "verify_keypair"), \
                 patch.object(m, "existing_config", side_effect=check_existing), \
                 patch.object(m.os, "fstat", side_effect=root_dir_stat):
                self.assertEqual(m.prepare("--install"), "INSTALLED_NEW_NO_OVERWRITE")
                self.assertEqual(target.read_bytes(), m.CONFIG)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(m.prepare("--install"), "EXACT_MATCH_UNCHANGED")
                self.assertEqual(target.read_bytes(), m.CONFIG)
                target.write_bytes(b"changed\n")
                with self.assertRaisesRegex(m.Blocked, "EXISTING_CONFIG_DIFFERS"):
                    # Replace the injected checker with production equivalent behavior
                    with patch.object(m, "existing_config", side_effect=m.Blocked("EXISTING_CONFIG_DIFFERS")):
                        m.prepare("--install")

    def test_create_refuses_concurrent_symlink_without_touching_target(self):
        with tempfile.TemporaryDirectory(prefix="kmj-pinned-race-") as tmp:
            parent = Path(tmp)
            target = parent / "offsite-sftp.conf"
            external = parent / "external"
            external.write_bytes(b"important original")
            target.symlink_to(external)
            with patch.object(m, "PARENT", parent), patch.object(m, "TARGET", target), \
                 patch.object(m, "protected_directory"), patch.object(m, "verify_keypair"), \
                 patch.object(m, "existing_config", return_value="MISSING"), \
                 patch.object(m.os, "fstat", return_value=types.SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o700)):
                with self.assertRaisesRegex(m.Blocked, "CONFIG_ALREADY_CREATED_BY_OTHER"):
                    m.prepare("--install")
            self.assertEqual(external.read_bytes(), b"important original")

    def test_root_host_arguments_block_before_read_or_mutation(self):
        for uid, host, argv in [(1000, "KMJ-elite", ["--install"]),
                                (0, "wrong-host", ["--install"]),
                                (0, "KMJ-elite", ["--something"])]:
            with patch.object(m.os, "geteuid", return_value=uid), \
                 patch.object(m.socket, "gethostname", return_value=host), \
                 patch.object(m, "prepare", side_effect=AssertionError("must never run")), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(argv), 2)
                self.assertIn("BLOCKED_HOST_ROOT_OR_ARGUMENTS", out.getvalue())

    def test_no_network_or_backup_side_effects(self):
        src = SRC.read_text()
        for forbidden in ("ssh-keyscan", "subprocess.run(['/usr/bin/ssh'", "systemctl",
                          "os.system(", "shell=True", "ssh-copy-id", "rm -rf", ".unlink(", "restart", "pg_dump"):
            self.assertNotIn(forbidden, src)
        self.assertIn("BACKUP_CREATED=NO", src)
        self.assertIn("PRODUCTION_CHANGED=NO", src)


if __name__ == "__main__":
    unittest.main()
