#!/usr/bin/env python3
"""Static regression contract for existing DKIM reuse; never execute installer."""
import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("stage-existing-kmj2026-mail-20261021.sh")

class SafeMailReuse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_expected_reuse_and_no_leaked_private_key(self):
        s = self.text
        for marker in (
            "SELECTOR=kmj2026",
            "ORIGINAL_KEY=$ORIGINAL_DIR/kmj2026.private",
            "ORIGINAL_TXT=$ORIGINAL_DIR/kmj2026.txt",
            "PRIVATE_LOCAL_PUBLIC_DNS=PASS",
            "dns.google/resolve?name=kmj2026._domainkey.kmjtechno.com&type=TXT",
            "install -o opendkim -g opendkim -m 0400",
            "cmp -s",
            "ORIGINAL_DKIM_KEY=UNCHANGED",
            "MAIL_STAGE=PASS",
        ):
            self.assertIn(marker, s)
        for unsafe in ("chmod 0644 \"$ORIGINAL_KEY\"", "chown opendkim \"$ORIGINAL_KEY\"",
                       "cat \"$ORIGINAL_KEY\"", "echo \"$original_digest\"", "MAIL_MAILER=smtp",
                       "artisan migrate", "ufw allow", "systemctl restart nginx"):
            self.assertNotIn(unsafe, s)

    def test_no_package_install_before_owner_confirmation(self):
        s = self.text
        self.assertLess(s.index("PRIVATE_LOCAL_PUBLIC_DNS=PASS"), s.index("REUSE KMJ2026"))
        self.assertLess(s.index("REUSE KMJ2026"), s.index("apt-get install -y"))
        self.assertIn("[ -t 0 ] && [ -t 1 ]", s)
        self.assertIn("'--stage'", s)
        self.assertNotIn(chr(92) + chr(36) + "{", s)
        self.assertNotIn("@{", s)

    def test_no_public_smtp_or_unauthenticated_relay(self):
        s = self.text
        for item in (
            "postfix postfix/main_mailer_type select Local only",
            "POSTFIX_PACKAGE_BOUND_PUBLIC",
            "inet_interfaces = loopback-only",
            "mynetworks = 127.0.0.0/8",
            "reject_unauth_destination",
            "mydestination = localhost",
            "relayhost =",
            "milter_default_action = tempfail",
            "Socket                  inet:8891@127.0.0.1",
            "NO_EMAIL_SENT=YES",
            "MX_AND_LARAVEL=UNCHANGED",
        ):
            self.assertIn(item, s)

    def test_failure_cleanup_and_key_unchanged_contract(self):
        s = self.text
        for marker in (
            "systemctl stop postfix opendkim",
            "systemctl disable postfix opendkim",
            "ORIGINAL_PRIVATE_KEY_CHANGED_DURING_INSTALL",
            "ORIGINAL_KEY_CHANGED",
            "EXISTING_EXTRA_KEY_FILES",
            "EXISTING_ACTIVE_KEY_COPY",
            "PACKAGE_BACKUP_CONFLICT",
            "STAGED=/etc/kmj-mail-selfhost-reuse-staged-20261021",
            "SERVICE_UNEXPECTEDLY_AUTOSTARTED",
            "MAIL_LISTENER_UNEXPECTED",
            "PRIVATE_KEY_PERMISSIONS_UNEXPECTED",
        ):
            self.assertIn(marker, s)
        self.assertGreaterEqual(s.count('original_digest'), 3)

    def test_selector_never_rotates(self):
        s = self.text
        self.assertNotIn("opendkim-genkey", s)
        self.assertNotIn("kmjmail2026.private", s)
        self.assertTrue(re.search(r"KeyFile\s+\$ACTIVE_DIR/kmj2026\.private", s))

if __name__ == "__main__":
    unittest.main()
