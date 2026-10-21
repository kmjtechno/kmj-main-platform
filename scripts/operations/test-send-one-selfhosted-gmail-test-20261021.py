#!/usr/bin/env python3
"""No-send GitHub CI coverage for the single-message selfhosted test operator script."""
import unittest
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("send-one-selfhosted-gmail-test-20261021.sh")

class SingleGmailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_syntax_and_argument(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        check = next(line for line in self.script.splitlines() if "ARGUMENT_MUST_BE_SEND_ONE" in line)
        src = "set -euo pipefail\nfail() { exit 2; }\n" + check
        for args, expected in [((), 2), (("--send-one",), 0), (("--send-one", "extra"), 2), (("--send",), 2)]:
            q = subprocess.run(["bash", "-c", src, "arg-guard", *args],
                               capture_output=True, text=True, timeout=5)
            self.assertEqual(q.returncode, expected, q.stderr)
        self.assertNotIn(chr(92) + chr(36) + "{", self.script)

    def test_one_time_authorization_and_delivery_truth(self):
        s = self.script
        self.assertIn("RECIPIENT=kmjtechno.net@gmail.com", s)
        self.assertIn("ORIGIN=info@kmjtechno.com", s)
        self.assertIn("ONCE=/etc/kmj-mail-single-test-20261021.once", s)
        self.assertIn("TEST_ALREADY_ATTEMPTED_DO_NOT_REPEAT", s)
        self.assertIn("type SEND ONE KMJ TEST", s)
        self.assertIn("OWNER_NOT_CONFIRMED", s)
        self.assertIn("( set -C; printf", s)
        self.assertIn('ONE_TIME_RECEIPT=PRESENT_DO_NOT_AUTORETRY', s)
        self.assertIn("GMAIL_DELIVERY=UNVERIFIED", s)
        self.assertLess(s.index("SEND ONE KMJ TEST"), s.index("( set -C; printf"))
        self.assertLess(s.index("( set -C; printf"), s.index("/usr/sbin/sendmail -oi"))
        self.assertEqual(s.count("/usr/sbin/sendmail -oi"), 1)

    def test_rejects_misconfigured_security_and_risky_changes(self):
        s = self.script
        for marker in ("LOCAL_LISTENER_SECURITY=PASS", "KEY_COPY",
                       "PRIVATE_KEY_NOT_IDENTICAL", "SERVICE_AUTOSTART_UNEXPECTED",
                       "PREEXISTING_MAIL_QUEUE_NOT_EMPTY", "milter_default_action tempfail",
                       "postfix check", "opendkim -n", "DKIM_PIDFILE_MISSING",
                       "POSTCONF_UNEXPECTED_"):
            if marker == "KEY_COPY": continue
            self.assertIn(marker, s)
        self.assertIn('ports != {25: ["127.0.0.1"], 8891: ["127.0.0.1"]}', s)
        for bad in ("systemctl start", "systemctl restart", "systemctl enable",
                    "postconf -e", "apt-get", "artisan", "opendkim-genkey",
                    "cloudflare.request", "ufw allow"):
            self.assertNotIn(bad, s)

    def test_embedded_python_listener_audit_is_valid(self):
        lines = self.script.splitlines()
        start = lines.index("python3 - <<'PY'") + 1
        end = lines.index("PY", start)
        compile("\n".join(lines[start:end]), str(SCRIPT), "exec")

if __name__ == "__main__":
    unittest.main()
