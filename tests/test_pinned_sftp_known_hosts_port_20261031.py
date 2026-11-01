"""Regression: default-port SSH host-key pin must use bare known_hosts alias."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/push-offsite-pinned-sftp-20261030.sh"
SOURCE = SCRIPT.read_text()


def alias(host: str, port: str) -> str:
    start = SOURCE.index("known_hosts_host() {")
    end = SOURCE.index("\n}", start) + 2
    fn = SOURCE[start:end]
    result = subprocess.run(
        ["bash", "-c", fn + '\nknown_hosts_host "$1" "$2"', "offsite-test", host, port],
        capture_output=True, text=True, timeout=5, check=True,
    )
    return result.stdout


def port_is_valid(port: str) -> bool:
    start = SOURCE.index("valid_port() {")
    end = SOURCE.index("\\n}", start) + 2
    fn = SOURCE[start:end]
    result = subprocess.run(
        ["bash", "-c", fn + '\\nvalid_port "$1"', "offsite-port-test", port],
        capture_output=True, text=True, timeout=5, check=False,
    )
    return result.returncode == 0


class KnownHostsPortTests(unittest.TestCase):
    def test_config_port_is_canonical_decimal(self):
        # Noncanonical 00022 used to pass CONFIG_PORT yet be treated as
        # default port 22 by OpenSSH, recreating the host-key alias bug.
        for good in ("1", "22", "2222", "65535"):
            with self.subTest(port=good):
                self.assertTrue(port_is_valid(good))
        for bad in ("", "0", "00", "022", "00022", "08", "65536",
                    "99999", "-22", "+22", "22 ", "22x"):
            with self.subTest(port=bad):
                self.assertFalse(port_is_valid(bad))

    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=5)

    def test_port22_default_uses_bare_host_not_bracket_port(self):
        self.assertEqual(alias("34.63.5.14", "22"), "34.63.5.14")
        self.assertNotEqual(alias("34.63.5.14", "22"), "[34.63.5.14]:22")

    def test_nondefault_port_keeps_bracketed_name(self):
        self.assertEqual(alias("34.63.5.14", "2222"), "[34.63.5.14]:2222")

    def test_real_openssh_host_lookup_default_port(self):
        with tempfile.TemporaryDirectory(prefix="kmj-host-key-alias-") as tmp:
            key = Path(tmp) / "host_key"
            p = subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                capture_output=True, timeout=10, check=False,
            )
            self.assertEqual(p.returncode, 0, "fixture host key generation")
            pub = key.with_suffix(".pub").read_text().strip().split()
            self.assertEqual(pub[0], "ssh-ed25519")
            known = Path(tmp) / "known_hosts"
            known.write_text(alias("34.63.5.14", "22") + " " + " ".join(pub[:2]) + "\n")
            hit = subprocess.run(
                ["ssh-keygen", "-F", "34.63.5.14", "-f", str(known)],
                capture_output=True, timeout=5, check=False,
            )
            self.assertEqual(hit.returncode, 0)
            # The original bug: [host]:22 is not the lookup name for port 22.
            miss = subprocess.run(
                ["ssh-keygen", "-F", "[34.63.5.14]:22", "-f", str(known)],
                capture_output=True, timeout=5, check=False,
            )
            self.assertNotEqual(miss.returncode, 0)

    def test_real_openssh_host_lookup_nondefault_port(self):
        with tempfile.TemporaryDirectory(prefix="kmj-host-key-altport-") as tmp:
            key = Path(tmp) / "host_key"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                check=True, timeout=10, capture_output=True,
            )
            pub = key.with_suffix(".pub").read_text().strip().split()
            known = Path(tmp) / "known_hosts"
            known.write_text(alias("34.63.5.14", "2222") + " " + " ".join(pub[:2]) + "\n")
            hit = subprocess.run(
                ["ssh-keygen", "-F", "[34.63.5.14]:2222", "-f", str(known)],
                capture_output=True, timeout=5, check=False,
            )
            self.assertEqual(hit.returncode, 0)

    def test_script_prechecks_alias_and_retains_security_flags(self):
        self.assertIn('host_alias="$(known_hosts_host "$host" "$port")"', SOURCE)
        self.assertIn('ssh-keygen -F "$host_alias" -f "$tmp/known_hosts"', SOURCE)
        self.assertIn("StrictHostKeyChecking=yes", SOURCE)
        self.assertIn("IdentitiesOnly=yes", SOURCE)
        self.assertIn("IdentityAgent=none", SOURCE)
        self.assertIn("GlobalKnownHostsFile=/dev/null", SOURCE)
        # The Google independent verifier requires the offsite ciphertext
        # to be mode 0600; put -p preserves the protected local file mode.
        self.assertIn("printf 'put -p %s %s\\n'", SOURCE)
        self.assertIn("protected_file \"$LOCAL\"", SOURCE)
        self.assertIn("REMOTE_COMMIT_NO_CLOBBER PASS", SOURCE)
        self.assertIn("REMOTE_READBACK_SHA256 PASS", SOURCE)
        self.assertNotIn("StrictHostKeyChecking=no", SOURCE)
        self.assertNotIn("UserKnownHostsFile=/dev/null", SOURCE)
        self.assertNotIn("ln -sf", SOURCE)
        self.assertNotIn("rsync --delete", SOURCE)


if __name__ == "__main__":
    unittest.main()
