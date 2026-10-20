#!/usr/bin/env python3
"""Static-only assertions: never execute installer or connect to any mail server."""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().with_name("stage-selfhosted-outbound-mail-20261021.sh")

class StageControls(unittest.TestCase):
    def test_fail_closed_host_and_operator(self):
        s = SCRIPT.read_text()
        for required in [
            "hostname -s", "ROOT_REQUIRED", "OWNER_TTY_REQUIRED",
            "STAGE LOCAL MAIL", "EXISTING_MAIL_CONFIG_DO_NOT_OVERWRITE",
            "EXISTING_OPENDKIM_CONFIG_DO_NOT_OVERWRITE", "MAIL_A_RECORD_MISMATCH",
            "INSUFFICIENT_DISK", "NO_TEST_EMAIL_WILL_BE_SENT",
        ]:
            self.assertIn(required, s)

    def test_only_local_send_submission(self):
        s = SCRIPT.read_text()
        for required in [
            "inet_interfaces = loopback-only", "mydestination = localhost",
            "mynetworks = 127.0.0.0/8", "relayhost =",
            "milter_default_action = tempfail",
            "non_smtpd_milters = inet:127.0.0.1:8891",
            "SERVICES=STOPPED_DISABLED", "DKIM_PUBLIC_TXT_BEGIN",
        ]:
            self.assertIn(required, s)

    def test_preserves_production(self):
        s = SCRIPT.read_text()
        for prohibited in [
            "artisan migrate", "systemctl restart nginx",
            "/home/kmjprod/current", "cloudflare.request",
            "MAIL_MAILER=smtp", "/etc/nginx", "ufw allow",
            "chmod 777", "opendkim-genkey -b 1024",
        ]:
            self.assertNotIn(prohibited, s)

if __name__ == "__main__":
    unittest.main()
