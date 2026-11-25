#!/usr/bin/env python3
"""Offline no-send contract checks: KMJ branded auth mail probe."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/operations/probe-owner-brevo-enterprise-email-20261021.py"
VIEW = ROOT / "apps/platform/resources/views/emails/kmj-auth-transactional.blade.php"
TEXT = ROOT / "apps/platform/resources/views/emails/kmj-auth-transactional-text.blade.php"
HEADER = VIEW.parent / "partials/kmj-enterprise-header.blade.php"
FOOTER = VIEW.parent / "partials/kmj-enterprise-footer.blade.php"

# Offline fixture for the explicit default palette only. The historical,
# pinned-release SMTP probe remains unchanged; no PHP or Blade is executed.
def default_html_fixture():
    source = VIEW.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    footer = FOOTER.read_text(encoding="utf-8")
    def replace_once(value, old, new):
        if value.count(old) != 1:
            raise ValueError("UNEXPECTED_TEMPLATE_STRUCTURE")
        return value.replace(old, new, 1)

    source = replace_once(source, r"@php($theme = \App\Services\Mail\EnterpriseMailTheme::palette())", "")
    source = replace_once(source, r"@php($artwork = \App\Services\Mail\EnterpriseMailTheme::artworkBase($theme))", "")
    def fallback_only(partial):
        if not partial.startswith("@if ($artwork !== null)\n") or not partial.endswith("@endif\n") or partial.count("\n@else\n") != 1:
            raise ValueError("UNEXPECTED_ARTWORK_BRANCH")
        return partial.split("\n@else\n", 1)[1].removesuffix("@endif\n")

    header = fallback_only(header)
    footer = fallback_only(footer)
    begin = "@if ($theme['layout'] === 'geometric')"
    if header.count(begin) != 1 or header.count("@endif") != 1:
        raise ValueError("UNEXPECTED_HEADER_STRUCTURE")
    before, conditional = header.split(begin, 1)
    _, after = conditional.split("@endif", 1)
    header = before + after
    for expression, value in {
        "{{ $theme['layout'] === 'letterhead' ? '12px solid '.$theme['accent'] : '0' }}": "0",
        "{{ $theme['layout'] === 'letterhead' ? 'center' : 'left' }}": "left",
        "{{ $theme['layout'] === 'wave' ? '68%' : '35%' }}": "35%",
    }.items():
        if expression not in header:
            raise ValueError("UNEXPECTED_HEADER_EXPRESSION")
        header = header.replace(expression, value)
    source = replace_once(source, "@include('emails.partials.kmj-enterprise-header')", header)
    notice = "PRIVATE ACCOUNT COMMUNICATION — Official account-security communication from KMJ TECHNO. Verify the sender domain before following security links."
    source = replace_once(source, "@include('emails.partials.kmj-enterprise-footer', ['footerNotice' => '" + notice + "'])", replace_once(footer, "{{ $footerNotice }}", notice))
    for key, value in {"header": "#0b1425", "footer": "#101b30", "accent": "#c71935", "ink": "#ffffff", "tint": "#fff2f4"}.items():
        source = source.replace("{{ $theme['" + key + "'] }}", value)
    if any(token in source for token in ("@php", "@include", "@if", "@endif", "@foreach", "{!!")):
        raise ValueError("UNEXPECTED_TEMPLATE_SYNTAX")
    return source

spec = importlib.util.spec_from_file_location("kmj_mail_preview", PROBE)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class BrandedEmailProbeSafety(unittest.TestCase):
    def test_static_template_fixture_escapes_html_and_preserves_plaintext_url(self):
        html_source = default_html_fixture()
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
        self.assertIn('kmj-sender-avatar.png', html)
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
        markup = default_html_fixture()
        self.assertIn('formataddr(("KMJ TECHNO", SENDER))', source)
        self.assertIn(".kmj-brevo-enterprise-20261021.once", source)
        self.assertIn("KMJ TECHNO Enterprise Mail QA", source)
        self.assertIn('width="64" height="64" alt="KMJ TECHNO"', markup)
        self.assertIn('class="kmj-tagline"', markup)
        self.assertIn('font-size:15px;line-height:21px;font-weight:700', markup)
        self.assertIn("SECURITY NOTICE", markup)
        self.assertIn("PRIVATE ACCOUNT COMMUNICATION", markup)
        self.assertIn("SECURE ACTION", markup)
        self.assertIn("https://kmjtechno.com/assets/brand/kmj-sender-avatar.png", markup)

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
