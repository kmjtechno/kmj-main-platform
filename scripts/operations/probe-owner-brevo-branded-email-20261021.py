#!/usr/bin/env python3
"""One-time on-owner-terminal branded HTML+text probe via authenticated Brevo.

Uses the actual branded Blade HTML/text source as a *static* rendering fixture;
it never boots or changes the production Laravel application, service or .env.
The only approved recipient is the KMJ owner Gmail test inbox.
"""
from __future__ import annotations

import getpass
import html
import os
from pathlib import Path
import secrets
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage

HOST = "smtp-relay.brevo.com"
PORT = 465
LOGIN = "bed580001@smtp-brevo.com"
SENDER = "info@kmjtechno.com"
RECIPIENT = "kmjtechno.net@gmail.com"
MARKER = Path("/home/kmjprod/.kmj-brevo-branded-20261021.once")
RELEASE = Path("/home/kmjprod/releases/platform-8070dad72c55")
CURRENT = Path("/home/kmjprod/current")
HTML = Path(__file__).with_name("kmj-auth-transactional.blade.php")
TEXT = Path(__file__).with_name("kmj-auth-transactional-text.blade.php")


def fail(reason: str) -> int:
    print("BRANDED_TEST=BLOCKED_" + reason)
    print("PRODUCTION_MAIL_CONFIG=UNCHANGED")
    return 2


def render_blade_fixture(source: str, data: dict[str, str], escape: bool) -> str:
    """ONLY replace known scalar view vars; fail on unknown Blade syntax."""
    for name, value in data.items():
        source = source.replace(
            "{{ $" + name + " }}", html.escape(value, quote=True) if escape else value
        )
        source = source.replace("{!! $" + name + " !!}", value)
    source = source.replace("{{ date('Y') }}", "2026")
    if "{{" in source or "{!!" in source or "@if" in source or "@foreach" in source:
        raise ValueError("UNEXPECTED_TEMPLATE_SYNTAX")
    return source


def main() -> int:
    if sys.argv != [sys.argv[0]]:
        return fail("UNEXPECTED_ARGUMENT")
    if os.geteuid() == 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        return fail("UNPRIVILEGED_KMJ_ELITE_REQUIRED")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return fail("INTERACTIVE_TTY_REQUIRED")
    if not CURRENT.is_symlink() or CURRENT.resolve() != RELEASE:
        return fail("LIVE_RELEASE_CHANGED")
    if MARKER.exists() or MARKER.is_symlink():
        return fail("ALREADY_ATTEMPTED")
    try:
        token = secrets.token_hex(6)
        subject = "KMJ TECHNO Branded Email QA " + token
        data = {
            "subject": subject,
            "preheader": "Premium KMJ TECHNO transactional email layout test.",
            "eyebrow": "MAIL DELIVERY & DESIGN QA",
            "heading": "Secure communication, thoughtfully designed.",
            "intro": "This is a one-time delivery and email-template rendering test for KMJ TECHNO. No account, password or verification token has been created.",
            "actionText": "Visit KMJ TECHNO",
            "actionUrl": "https://kmjtechno.com",
            "expiryText": "Test reference: " + token + ". This message requires no action.",
        }
        html_body = render_blade_fixture(HTML.read_text(encoding="utf-8"), data, True)
        text_body = render_blade_fixture(TEXT.read_text(encoding="utf-8"), data, False)
        if 'kmj-email-lockup-dark.png' not in html_body or token not in html_body or token not in text_body:
            return fail("BRANDING_OR_CONTENT_MISSING")
        message = EmailMessage()
        message["From"] = SENDER
        message["To"] = RECIPIENT
        message["Subject"] = subject
        message["Auto-Submitted"] = "auto-generated"
        message["X-Auto-Response-Suppress"] = "All"
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        print("BRANDED_TEMPLATE_RENDER=PASS")
        print("SENDER=" + SENDER)
        print("RECIPIENT=" + RECIPIENT)
        print("PRODUCTION_MAIL_CONFIG=UNCHANGED")
        key = getpass.getpass("Brevo SMTP key (hidden): ")
        if not 15 <= len(key) <= 512 or any(c in key for c in "\r\n"):
            return fail("INVALID_SMTP_KEY")
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        with smtplib.SMTP_SSL(HOST, PORT, timeout=20, context=ctx) as smtp:
            smtp.login(LOGIN, key)
            key = ""
            print("BREVO_SMTP_AUTH=PASS")
            try:
                with MARKER.open("x", encoding="utf-8") as record:
                    record.write("SUBJECT=" + subject + "\n")
                MARKER.chmod(0o600)
            except FileExistsError:
                return fail("ALREADY_ATTEMPTED")
            rejected = smtp.send_message(message, from_addr=SENDER, to_addrs=[RECIPIENT])
            if rejected:
                return fail("SMTP_RECIPIENT_REJECTED")
        print("SMTP_PROVIDER_ACCEPTED=PASS")
        print("TEST_SUBJECT=" + subject)
        print("GMAIL_DELIVERY=UNVERIFIED")
        print("PRODUCTION_MAIL_CONFIG=UNCHANGED")
        return 0
    except smtplib.SMTPAuthenticationError as error:
        return fail("SMTP_AUTH_" + str(error.smtp_code))
    except smtplib.SMTPResponseException as error:
        return fail("SMTP_RESPONSE_" + str(error.smtp_code))
    except (ValueError, OSError, ssl.SSLError, smtplib.SMTPException) as error:
        return fail("TRANSPORT_OR_TEMPLATE_" + type(error).__name__)
    except (KeyboardInterrupt, EOFError):
        return fail("OWNER_CANCELLED")


if __name__ == "__main__":
    raise SystemExit(main())
