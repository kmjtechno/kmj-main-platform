#!/usr/bin/env python3
"""No-install tests for owner-only OpenDKIM PID alignment."""
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).with_name("fix-opendkim-pidfile-20261021.sh")

class OpenDkimPidFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SOURCE.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        proc = subprocess.run(["bash", "-n", str(SOURCE)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_actual_argument_validation_without_running_script(self):
        line = next(x for x in self.content.splitlines() if "EXACT_APPLY_ARGUMENT_REQUIRED" in x)
        check = "set -euo pipefail\nfail() { exit 2; }\n" + line
        for args, expected in [((), 2), (("--apply",), 0), (("--apply", "extra"), 2), (("--start",), 2)]:
            proc = subprocess.run(["bash", "-c", check, "test-arg", *args],
                                  capture_output=True, text=True, timeout=4)
            self.assertEqual(proc.returncode, expected, proc.stderr)
        self.assertNotIn(chr(92) + chr(36) + "{", self.content)

    def test_exact_systemd_and_config_alignment(self):
        s = self.content
        for marker in (
            "SYSTEMD_NOT_FORKING", "SYSTEMD_PIDFILE_UNEXPECTED",
            "opendkim/opendkim.pid", "PidFile",
            "EXISTING_PIDFILE_DIRECTIVE", "USER_ID_UNEXPECTED",
            "SIGNING_SOCKET_UNEXPECTED", "KEY_FILE_UNEXPECTED",
            "RUNTIME_DIRECTORY_OWNER_UNEXPECTED",
            "OPENDKIM_PRECHECK_FAILED", "OPENDKIM_POSTCHECK_FAILED",
        ):
            self.assertIn(marker, s)
        self.assertLess(s.index("OPENDKIM_PRECHECK_FAILED"), s.index("FIX DKIM PIDFILE"))
        self.assertLess(s.index("FIX DKIM PIDFILE"), s.index("changed=1"))

    def test_backup_rollback_and_inactive_service_safety(self):
        s = self.content
        for marker in (
            "BACKUP_EXISTS_REVIEW_BEFORE_RETRY",
            'cp -p -- "$CONFIG" "$BACKUP"',
            'chmod 0600 "$BACKUP"',
            'cp -p -- "$BACKUP" "$CONFIG"',
            "OPENDKIM_CONFIG_ROLLBACK",
            "SERVICE_NOT_INACTIVE_", "SERVICE_NOT_DISABLED_",
            "MAIL_SERVICES=STOPPED_DISABLED",
            "NO_EMAIL_SENT=YES",
            "NEW_MAIL_LISTENER",
        ):
            self.assertIn(marker, s)

    def test_no_mail_activation_or_broad_changes(self):
        s = self.content
        for banned in (
            "systemctl start", "systemctl restart", "systemctl enable",
            "postconf -e", "sendmail ", "swaks ", "opendkim-genkey",
            "ufw ", "artisan", "cloudflare.request", "apt-get",
        ):
            self.assertNotIn(banned, s)
        self.assertIn("POSTFIX_AND_DNS=UNCHANGED", s)

if __name__ == "__main__":
    unittest.main()
