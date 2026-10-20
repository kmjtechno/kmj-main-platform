#!/usr/bin/env python3
"""Offline-only activation contract checks; never starts services or connects to SMTP."""
import ast
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).with_name("activate-local-selfhosted-mail-20261021.sh")

class LocalMailActivationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_exact_argument_guard_executes_without_starting_services(self):
        s = self.source
        line = next(line for line in s.splitlines() if 'EXPECTED_ACTIVATE_ARGUMENT' in line)
        # Only the argument check; never execute any more of the installer.
        check = 'set -euo pipefail\nfail() { exit 2; }\n' + line
        for args, expected in ((("--activate",), 0), ((), 2), (("--start",), 2),
                               (("--activate", "extra"), 2)):
            r = subprocess.run(["bash", "-c", check, "args-test", *args],
                               capture_output=True, text=True, timeout=4)
            self.assertEqual(r.returncode, expected, r.stderr)

    def test_fail_closed_preflight_before_explicit_owner_confirmation(self):
        s = self.source
        self.assertNotIn(chr(92) + chr(36) + "{", s)
        for check in ("STAGE_STAMP_MISSING", "ROUTE_BACKUP_MISSING",
                      "DKIM_KEY_COPY_MISMATCH", "ROOT_REQUIRED", "WRONG_HOST",
                      "OWNER_TTY_REQUIRED", "QUEUE_NOT_EMPTY",
                      "PUBLIC_MAIL_LISTENERS=NONE", "NO_EMAIL_SENT=YES",
                      "OWNER_NOT_CONFIRMED"):
            self.assertIn(check, s)
        self.assertLess(s.index("postfix check >/dev/null"),
                        s.index("START LOCAL MAIL"))
        self.assertLess(s.index("START LOCAL MAIL"),
                        s.index("systemctl start opendkim"))
        self.assertLess(s.index("systemctl start opendkim"),
                        s.index("systemctl start postfix"))

    def test_no_production_changes_and_bounded_listeners(self):
        s = self.source
        self.assertIn("inet_interfaces loopback-only", s)
        self.assertIn("mynetworks 127.0.0.0/8", s)
        self.assertIn("milter_default_action tempfail", s)
        self.assertIn('listeners != {25: ["127.0.0.1"], 8891: ["127.0.0.1"]}', s)
        self.assertIn("SOCKET", s)
        self.assertIn("systemctl stop postfix opendkim", s)
        self.assertIn("SERVICE_BECAME_ENABLED", s)
        for prohibited in ("systemctl enable", "postconf -e", "sendmail",
                           "artisan", "ufw allow", "opendkim-genkey",
                           "systemctl restart", "mailx ", "smtp.sendmail"):
            self.assertNotIn(prohibited, s)

    def test_embedded_read_only_socket_check_syntax(self):
        s = self.source
        lines = s.splitlines()
        start = lines.index("python3 - <<'PY'") + 1
        end = lines.index("PY", start)
        compile("\n".join(lines[start:end]), str(SCRIPT) + ":python", "exec")

if __name__ == "__main__":
    unittest.main()
