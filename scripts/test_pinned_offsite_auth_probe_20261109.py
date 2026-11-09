#!/usr/bin/env python3
"""Offline regression tests: no actual SSH endpoint or production key is contacted."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parent / "operations/probe-pinned-offsite-auth-readonly-20261109.py"
spec = importlib.util.spec_from_file_location("kmj_pinned_auth_probe", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BLOB = mod.WIRE_PREFIX + bytes(range(32))
PUB = "ssh-ed25519 " + base64.b64encode(BLOB).decode("ascii")
FP = "SHA256:" + base64.b64encode(hashlib.sha256(BLOB).digest()).decode("ascii").rstrip("=")


class PinnedAuthProbeTests(unittest.TestCase):
    def test_strict_ed25519_wire_fingerprint(self):
        self.assertEqual(mod.fingerprint_public_line(PUB), FP)
        with self.assertRaises(mod.Blocked):
            mod.fingerprint_public_line(PUB.replace("ed25519", "rsa"))
        with self.assertRaises(mod.Blocked):
            mod.fingerprint_public_line("ssh-ed25519 !!invalid")
        with self.assertRaises(mod.Blocked):
            mod.fingerprint_public_line("ssh-ed25519 " + base64.b64encode(b"short").decode("ascii"))

    def test_host_pin_requires_single_exact_host_and_fingerprint(self):
        with patch.object(mod, "SERVER_PIN", FP):
            self.assertEqual(mod.pinned_scan(mod.HOST + " " + PUB + "\n"),
                             mod.HOST + " " + PUB + "\n")
            for data in (mod.HOST + " " + PUB + "\n" + mod.HOST + " " + PUB + "\n",
                         "8.8.8.8 " + PUB,
                         mod.HOST + " ssh-rsa abcd",
                         mod.HOST + " " + PUB + "\nextra",
                         ""):
                with self.assertRaises(mod.Blocked, msg=data):
                    mod.pinned_scan(data)
        with self.assertRaises(mod.Blocked):
            mod.pinned_scan(mod.HOST + " " + PUB)

    def test_fixed_config_cannot_be_overridden_from_environment(self):
        self.assertEqual(mod.CONFIG_BYTES, (
            "HOST=" + mod.HOST + "\nPORT=" + mod.PORT + "\nUSER=" + mod.USER
            + "\nREMOTE_DIR=" + mod.REMOTE_DIR
            + "\nIDENTITY_FILE=" + str(mod.IDENTITY)
            + "\nHOSTKEY_SHA256=" + mod.SERVER_PIN + "\n"
        ).encode("ascii"))
        self.assertNotIn("SSH_AUTH_SOCK", mod.ENV)
        self.assertNotIn("BASH_ENV", mod.ENV)
        self.assertEqual(mod.IDENTITY.as_posix(), "/root/.ssh/kmj-google-offsite-20261031-ed25519")

    def test_sftp_uses_only_explicit_identity_and_private_pinned_hostfile(self):
        known = Path("/run/valid/known_hosts")
        batch = Path("/run/valid/batch")
        args = mod.sftp_args(known, batch)
        self.assertEqual(args[0], "/usr/bin/sftp")
        self.assertIn("-F", args)
        self.assertIn("/dev/null", args)
        self.assertIn("IdentityAgent=none", args)
        self.assertIn("IdentitiesOnly=yes", args)
        self.assertIn("BatchMode=yes", args)
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertIn("PasswordAuthentication=no", args)
        self.assertIn("KbdInteractiveAuthentication=no", args)
        self.assertIn("GSSAPIAuthentication=no", args)
        self.assertIn("UpdateHostKeys=no", args)
        self.assertIn("GlobalKnownHostsFile=/dev/null", args)
        self.assertIn("UserKnownHostsFile=" + str(known), args)
        self.assertEqual(args[-1], mod.USER + "@" + mod.HOST)
        self.assertNotIn("StrictHostKeyChecking=no", args)

    def test_local_preflight_blocks_wrong_config_and_key(self):
        with patch.object(mod.os, "geteuid", return_value=0), \
             patch.object(mod.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(mod.sys, "argv", [str(SOURCE)]), \
             patch.object(mod, "read_protected", return_value=b"wrong"):
            with self.assertRaisesRegex(mod.Blocked, "PINNED_CONFIG_MISMATCH"):
                mod.preflight()
        with patch.object(mod.os, "geteuid", return_value=1000), \
             patch.object(mod.sys, "argv", [str(SOURCE)]):
            with self.assertRaisesRegex(mod.Blocked, "HOST_ROOT_OR_ARGUMENTS"):
                mod.preflight()

    def test_no_network_on_wrong_host_and_no_raw_secret_printing(self):
        with patch.object(mod.os, "geteuid", return_value=0), \
             patch.object(mod.socket, "gethostname", return_value="not-elite"), \
             patch.object(mod, "run") as fake_run:
            with self.assertRaises(mod.Blocked):
                mod.preflight()
            fake_run.assert_not_called()
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("shell=True", text)
        self.assertNotIn("print(auth.stderr", text)
        self.assertNotIn("print(derived.stdout", text)
        self.assertIn("BACKUP_RESTORE=NOT_VERIFIED", text)
        self.assertIn("LEGACY_OFFSITE_SERVICE=UNCHANGED", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
