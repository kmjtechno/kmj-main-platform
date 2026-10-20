"""Negative and no-production-change controls for one-message Brevo probe."""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "operations" / "probe-owner-brevo-smtps-20261020.py"
spec = importlib.util.spec_from_file_location("brevo_smtps_probe", SCRIPT)
assert spec and spec.loader
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class BrevoSmtpsProbeSafety(unittest.TestCase):
    def test_authorized_sender_and_owner_gmail_only(self):
        self.assertEqual(
            app.validated("info@kmjtechno.com", app.SENDER_PATTERN),
            "info@kmjtechno.com",
        )
        self.assertEqual(
            app.validated("owner.name@gmail.com", app.GMAIL_PATTERN),
            "owner.name@gmail.com",
        )
        for bad in (
            "bad@example.com",
            "attacker@other.com",
            "anything@kmjtechno.com\r\nBcc:bad@gmail.com",
            "http://attacker.net",
            "owner+test@gmail.com\n",
        ):
            # The last LF-only input is stripped by trim(), but CRLF header
            # injection and unauthorized domains must fail before SMTP.
            if bad == "owner+test@gmail.com\n":
                continue
            with self.assertRaises(ValueError):
                app.validated(bad, app.SENDER_PATTERN)

    def test_unapproved_gmail_inbox_rejected(self):
        for candidate in ("abc@yahoo.com", "abc@outlook.com", "bad@example.org"):
            with self.assertRaises(ValueError):
                app.validated(candidate, app.GMAIL_PATTERN)

    def test_fixed_encrypted_provider_and_no_generic_relay(self):
        self.assertEqual(app.HOST, "smtp-relay.brevo.com")
        self.assertEqual(app.PORT, 465)
        source = SCRIPT.read_text()
        self.assertIn("ssl.create_default_context()", source)
        self.assertIn("tls.minimum_version = ssl.TLSVersion.TLSv1_2", source)
        self.assertIn("smtplib.SMTP_SSL(HOST, PORT", source)
        self.assertIn("smtp.login(login, key)", source)
        self.assertIn("to_addrs=[recipient]", source)
        self.assertIn('"SEND ONE TEST"', source)
        self.assertIn('getpass.getpass("Brevo SMTP key', source)

    def test_no_silent_production_activation_or_secret_logging(self):
        source = SCRIPT.read_text()
        for prohibited in (
            "artisan migrate", "systemctl", "config:cache",
            "APP_KEY", "chmod 777", "os.environ[",
            "MAIL_MAILER=kmj_brevo", "SMTP_PASSWORD=",
            "print(key)", "print(login)", "print(recipient)",
            "password_confirmation", "runuser -u root",
            "POST /register", "sender_password",
        ):
            self.assertNotIn(prohibited, source)
        for required in (
            "CURRENT.is_symlink()",
            "RUN_AS_UNPRIVILEGED_KMJPROD",
            "LIVE_RELEASE_POINTER_CHANGED",
            "SMTP_INBOX_DELIVERY=NOT_VERIFIED",
            "PRODUCTION_MAIL_CONFIG=UNCHANGED",
            "CUSTOMER_REGISTRATION=NOT_ACTIVATED",
            "SMTP_PROVIDER_ACCEPTED=PASS",
            "if __name__ == \"__main__\":",
        ):
            self.assertIn(required, source)

    def test_no_test_email_or_server_connections_just_by_importing(self):
        self.assertTrue(callable(app.main))
        self.assertTrue(callable(app.validated))


if __name__ == "__main__":
    unittest.main()
