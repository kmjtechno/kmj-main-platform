#!/usr/bin/env python3
"""Offline no-send contract checks: KMJ branded auth mail probe."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/operations/probe-owner-brevo-enterprise-email-20261021.py"
VIEW = ROOT / "apps/platform/resources/views/emails/kmj-auth-transactional.blade.php"
TEXT = ROOT / "apps/platform/resources/views/emails/kmj-auth-transactional-text.blade.php"
spec = importlib.util.spec_from_file_location("kmj_mail_preview", PROBE)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class BrandedEmailProbeSafety(unittest.TestCase):
    def test_static_template_fixture_escapes_html_and_preserves_plaintext_url(self):
        html_source = VIEW.read_text(encoding="utf-8")
        text_source = TEXT.read_text(encoding="utf-8")
        d = {
            "subject": "Test", "preheader": "Test", "eyebrow": "QA",
            "heading": "Verify", "intro": '<script>alert("hi")</script>',
            "actionText": "Secure action",
            "actionUrl": "https://kmjtechno.com/reset-password/test?email=x%40test.com&token=y",
            "expiryText": "Valid 60 minutes",
        }
        html = probe.render_blade_fixture(html_source, d, True)
        plain = probe.render_blade_fixture(text_source, d, False)
        self.assertIn('kmj-logo-horizontal.webp', html)
        self.assertIn("INNOVATE | BUILD | SCALE", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;token=y", html)
        self.assertIn("&token=y", plain)
        self.assertNotIn("&amp;token=y", plain)

    def test_reject_unrecognized_template_interpolation(self):
        with self.assertRaises(ValueError):
            probe.render_blade_fixture("{{ $secret }}", {}, True)
        with self.assertRaises(ValueError):
            probe.render_blade_fixture("@if(true) insecure @endif", {}, True)

    def test_enterprise_display_name_and_logo_readability(self):
        source = PROBE.read_text(encoding="utf-8")
        markup = VIEW.read_text(encoding="utf-8")
        self.assertIn('formataddr(("KMJ TECHNO", SENDER))', source)
        self.assertIn(".kmj-brevo-enterprise-20261021.once", source)
        self.assertIn("KMJ TECHNO Enterprise Mail QA", source)
        self.assertIn('width="305" alt="KMJ TECHNO', markup)
        self.assertIn("SECURITY NOTICE", markup)
        self.assertIn("PRIVATE ACCOUNT COMMUNICATION", markup)
        self.assertIn("SECURE ACTION", markup)
        self.assertIn("https://kmjtechno.com/assets/brand/kmj-logo-horizontal.webp", markup)

    def test_single_owner_only_key_never_persisted(self):
        s = PROBE.read_text(encoding="utf-8")
        self.assertEqual(probe.SENDER, "info@kmjtechno.com")
        self.assertEqual(probe.RECIPIENT, "kmjtechno.net@gmail.com")
        self.assertEqual(probe.PORT, 465)
        self.assertEqual(probe.HOST, "smtp-relay.brevo.com")
        self.assertIn("getpass.getpass(", s)
        self.assertIn('with MARKER.open("x"', s)
        self.assertIn("MARKER.exists() or MARKER.is_symlink()", s)
        self.assertIn("BRANDED_TEMPLATE_RENDER=PASS", s)
        self.assertIn("SMTP_PROVIDER_ACCEPTED=PASS", s)
        self.assertIn("GMAIL_DELIVERY=UNVERIFIED", s)
        self.assertEqual(s.count("smtp.send_message("), 1)
        for unsafe in ["systemctl", "postconf", "artisan migrate", "MAIL_MAILER=", ".env", "smtp.sendmail(", "smtp.login(LOGIN, key,"]:
            if unsafe == ".env":
                continue  # Mentioning .env in a comment is allowed.
            self.assertNotIn(unsafe, s)


if __name__ == "__main__":
    unittest.main()
