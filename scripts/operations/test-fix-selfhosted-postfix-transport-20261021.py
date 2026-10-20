#!/usr/bin/env python3
"""Safety assertions for operator-only Postfix routing correction; never executes it."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).with_name("fix-selfhosted-postfix-transport-20261021.sh")

class RoutingRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = SCRIPT.read_text(encoding="utf-8")

    def test_syntax(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_requires_exact_state_and_confirmation(self):
        s = self.s
        for check in (
            '"@{1:-}" == "--apply"',
            "ROOT_REQUIRED",
            "WRONG_HOST",
            "INTERACTIVE_TTY_REQUIRED",
            "REUSE_STAGE_STAMP_MISSING",
            "DEFAULT_TRANSPORT_UNEXPECTED",
            "RELAY_TRANSPORT_UNEXPECTED",
            "QUEUED_MAIL_NOT_EMPTY",
            "OWNER_NOT_CONFIRMED",
            "FIX OUTBOUND TRANSPORT",
        ):
            self.assertIn(check.replace("@{", chr(36) + "{"), s)
        self.assertNotIn(chr(92) + chr(36) + "{", s)

    def test_does_not_activate_server_or_send_mail(self):
        s = self.s
        for forbidden in (
            "systemctl start",
            "systemctl restart",
            "systemctl enable",
            "postfix start",
            "sendmail -",
            "swaks",
            "artisan",
            "opendkim-genkey",
            "ufw allow",
        ):
            self.assertNotIn(forbidden, s)
        for guard in (
            'inet_interfaces)" == loopback-only',
            'mydestination)" == localhost',
            'milter_default_action)" == tempfail',
            'postqueue -j | wc -l',
            "reject_unauth_destination",
            "cmp -s",
            "ORIGINAL_PRIVATE_KEY_MODE_UNSAFE",
            "POSTFIX_POSTCHECK_FAILED",
        ):
            self.assertIn(guard, s)

    def test_backup_rollback_and_only_two_modifications(self):
        s = self.s
        self.assertIn("BACKUP=/etc/postfix/main.cf.kmj-outbound-before-20261021.bak", s)
        self.assertIn("BACKUP_ALREADY_EXISTS", s)
        self.assertIn('cp -p -- "$MAINCF" "$BACKUP"', s)
        self.assertIn('chmod 0600 "$BACKUP"', s)
        self.assertIn('cp -p -- "$BACKUP" "$MAINCF"', s)
        self.assertIn("CHANGED=1", s)
        self.assertIn("postconf -e 'default_transport = smtp' 'relay_transport = smtp'", s)
        self.assertEqual(s.count("postconf -e "), 1)
        self.assertIn("MAIL_SERVICE_ENABLED", s)
        self.assertIn("MAIL_SERVICE_STARTED", s)
        self.assertIn("ROUTING_FIX=PASS", s)

if __name__ == "__main__":
    unittest.main()
