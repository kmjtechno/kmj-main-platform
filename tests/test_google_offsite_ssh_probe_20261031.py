"""Offline adversarial fixtures for pinned Google/ELITE single-key SSH proof."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/operations/verify-google-offsite-ssh-20261031.py"
spec = importlib.util.spec_from_file_location("kmj_ssh_probe", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ProbeTests(unittest.TestCase):
    def test_client_fingerprint_exact_verified_public_blob(self):
        m.identity  # preflight is separately tested by mocks
        self.assertEqual(m.CLIENT_KEY_FP, "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk")

    def test_rejects_malformed_or_truncated_ssh_wire_key(self):
        valid = base64.b64encode(
            b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"A" * 32
        ).decode()
        self.assertTrue(m.ed25519_fp(valid).startswith("SHA256:"))
        for other in ["not base64!!",
                      base64.b64encode(b"wrong").decode(),
                      base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"A" * 31).decode()]:
            with self.subTest(other=other), self.assertRaises(m.Blocked):
                m.ed25519_fp(other)

    def test_hostkey_pin_known_fixture_matches_expected(self):
        with tempfile.TemporaryDirectory(prefix="kmj-ed25519-host-fixture-") as tmp:
            import subprocess
            k = Path(tmp) / "host_ed25519"
            r = subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519",
                                "-N", "", "-f", str(k)],
                capture_output=True, timeout=12, check=False)
            self.assertEqual(r.returncode, 0)
            raw = k.with_suffix(".pub").read_text().split()
            actual = m.ed25519_fp(raw[1])
            with patch.object(m, "HOST_KEY_FP", actual):
                self.assertEqual(
                    m.parse_scan(("34.63.5.14 ssh-ed25519 " + raw[1] + "\n").encode()),
                    "34.63.5.14 ssh-ed25519 " + raw[1],
                )

    def test_mismatched_or_duplicate_or_extra_scanned_host_rejected(self):
        blob = base64.b64encode(
            b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"B" * 32
        ).decode()
        line = ("34.63.5.14 ssh-ed25519 " + blob + "\n").encode()
        with self.assertRaisesRegex(m.Blocked, "HOSTKEY_PIN_MISMATCH"):
            m.parse_scan(line)
        with patch.object(m, "HOST_KEY_FP", m.ed25519_fp(blob)):
            for wrong in [line + b"attacker extra\n",
                          line + b"unknown.example ssh-ed25519 " + blob.encode() + b"\n",
                          b"garbage", b""]:
                with self.subTest(wrong=wrong), self.assertRaises(m.Blocked):
                    m.parse_scan(wrong)

    def test_never_connect_before_hostkey_and_identity_verified(self):
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(m, "identity", side_effect=m.Blocked("key unsafe")), \
             patch.object(m, "host_key", side_effect=AssertionError("network before identity")):
            self.assertEqual(m.main([]), 3)
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="KMJ-elite"), \
             patch.object(m, "identity"), \
             patch.object(m, "host_key", side_effect=m.Blocked("bad host pin")), \
             patch.object(m, "ssh_probe", side_effect=AssertionError("ssh before host pin")):
            self.assertEqual(m.main([]), 3)

    def test_root_host_and_zero_argv_gates(self):
        for uid, host, args in [(1000, "KMJ-elite", []), (0, "different-host", []),
                                (0, "KMJ-elite", ["--connect"]), (0, "KMJ-elite", ["-h"])]:
            with patch.object(m.os, "geteuid", return_value=uid), \
                 patch.object(m.socket, "gethostname", return_value=host), \
                 patch.object(m, "identity", side_effect=AssertionError("must not read identity")):
                self.assertEqual(m.main(args), 2)

    def test_real_ssh_argv_fixed_and_private_hostfile_ephemeral(self):
        captured = []
        def fake_run(argv, **kwargs):
            captured.append(argv)
            return type("P", (), {"returncode": 0, "stderr": b"", "stdout": b""})()
        with patch.object(m, "run", side_effect=fake_run):
            self.assertEqual(m.ssh_probe("34.63.5.14 ssh-ed25519 AAAA"), "SSH_READONLY_AUTH_PASS")
        self.assertEqual(len(captured), 1)
        cmd = captured[0]
        self.assertEqual(cmd[0:2], ["/usr/bin/ssh", "-F"])
        self.assertEqual(cmd[-2:], ["info@34.63.5.14", "/bin/true"])
        self.assertEqual(cmd.count("-i"), 1)
        self.assertIn(str(m.PRIV), cmd)
        self.assertIn("IdentityAgent=none", cmd)
        self.assertIn("StrictHostKeyChecking=yes", cmd)
        self.assertIn("BatchMode=yes", cmd)
        self.assertIn("ClearAllForwardings=yes", cmd)
        self.assertFalse(any("StrictHostKeyChecking=no" in z for z in cmd))
        self.assertFalse(os.path.exists(next(z.split("=", 1)[1] for z in cmd if z.startswith("UserKnownHostsFile="))))

    def test_failed_auth_never_claims_pass(self):
        for stderr, expected in [
            (b"Permission denied (publickey).", "SSH_PUBLICKEY_REJECTED"),
            (b"Host key verification failed", "SSH_HOSTKEY_REJECTED"),
            (b"Connection timed out", "SSH_NETWORK_FAILURE"),
            (b"not a recognized failure", "SSH_NO_SUCCESS_UNCLASSIFIED"),
        ]:
            result = type("P", (), {"returncode": 255, "stderr": stderr, "stdout": b""})()
            with patch.object(m, "run", return_value=result):
                self.assertEqual(
                    m.ssh_probe("34.63.5.14 ssh-ed25519 AAAA"), expected
                )

    def test_no_secrets_or_ssh_session_commands_in_script(self):
        source = SOURCE.read_text()
        for forbidden in ["shell=True", "ssh-copy-id", "authorized_keys", "systemctl",
                          "sshpass", "StrictHostKeyChecking=no", "AutoAddPolicy",
                          "os.system(", "os.unlink(", "shutil.rmtree"]:
            self.assertNotIn(forbidden, source)
        self.assertIn('"info@" + HOST, "/bin/true"', source)
        self.assertIn("BACKUP_STARTED=NO", source)
        self.assertIn("PRODUCTION_CHANGED=NO", source)


if __name__ == "__main__":
    unittest.main()
