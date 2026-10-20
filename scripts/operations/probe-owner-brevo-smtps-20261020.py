#!/usr/bin/env python3
"""One-off Brevo SMTP transport acceptance probe; never activates Laravel.

Run interactively under the unprivileged kmjprod account on KMJ-elite after
fetching the exact GitHub blob and verifying git hash-object. Credentials are
collected from the owning terminal without echo and are never written to disk.
One email only, to an explicitly confirmed owner-controlled Gmail inbox.
"""
from __future__ import annotations

import getpass
import os
import re
import secrets
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

HOST = "smtp-relay.brevo.com"
PORT = 465
OLD_RELEASE = Path("/home/kmjprod/releases/platform-8070dad72c55")
CURRENT = Path("/home/kmjprod/current")
SENDER_PATTERN = re.compile(r"^[a-zA-Z0-9_.+%-]{1,64}@kmjtechno\.com$")
GMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+%-]{1,64}@gmail\.com$")
LOGIN_PATTERN = re.compile(r"^[a-zA-Z0-9_.+%-]{1,100}@[a-zA-Z0-9.-]{3,190}$")


def fail(reason: str) -> int:
    print("BREVO_SMTP_PREFLIGHT=BLOCKED")
    print("REASON=" + reason)
    print("SMTP_PROVIDER_ACCEPTED=NOT_VERIFIED")
    print("SMTP_INBOX_DELIVERY=NOT_VERIFIED")
    print("PRODUCTION_MAIL_CONFIG=UNCHANGED")
    return 2


def validated(address: str, pattern: re.Pattern[str]) -> str:
    candidate = address.strip()
    if not pattern.fullmatch(candidate) or "\n" in candidate or "\r" in candidate:
        raise ValueError("MAILBOX_NOT_ALLOWED")
    return candidate


def main() -> int:
    if sys.argv != [sys.argv[0]]:
        return fail("NO_CLI_ARGUMENTS_ALLOWED")
    if os.geteuid() == 0:
        return fail("RUN_AS_UNPRIVILEGED_KMJPROD")
    if socket.gethostname().split(".")[0] != "KMJ-elite":
        return fail("WRONG_HOST")
    if not CURRENT.is_symlink() or CURRENT.resolve() != OLD_RELEASE:
        return fail("LIVE_RELEASE_POINTER_CHANGED")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return fail("INTERACTIVE_OWNER_TERMINAL_REQUIRED")
    try:
        print("BREVO_SMTP_PREFLIGHT=INTERACTIVE_NO_CONFIG_CHANGE")
        print("Use the SMTP LOGIN and SMTP KEY from Brevo SMTP settings (NOT an API key).")
        print("Use an authenticated sender @kmjtechno.com and your own Gmail inbox.")
        sender = validated(input("Verified sender @kmjtechno.com: "), SENDER_PATTERN)
        recipient = validated(input("Your Gmail test inbox: "), GMAIL_PATTERN)
        repeat = validated(input("Confirm same Gmail test inbox: "), GMAIL_PATTERN)
        if recipient.casefold() != repeat.casefold():
            return fail("RECIPIENT_CONFIRMATION_MISMATCH")
        login = validated(getpass.getpass("Brevo SMTP login (hidden): "), LOGIN_PATTERN)
        key = getpass.getpass("Brevo SMTP key (hidden, not API key): ")
        if len(key) < 15 or len(key) > 512 or any(c in key for c in "\r\n"):
            return fail("INVALID_SMTP_KEY_LENGTH")
        if input("Type SEND ONE TEST to submit one message: ").strip() != "SEND ONE TEST":
            return fail("OWNER_SEND_NOT_CONFIRMED")

        nonce = secrets.token_hex(6).upper()
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = "KMJ Brevo SMTP Probe " + nonce
        message["Auto-Submitted"] = "auto-generated"
        message["X-Auto-Response-Suppress"] = "All"
        message.set_content(
            "KMJ TECHNO outbound SMTPS test only. No verification token, "
            "login link, password or account registration was created.\n"
            "Probe identifier: " + nonce + "\n"
            "If received, confirm the inbox separately before activating "
            "customer verification email.\n"
        )
        tls = ssl.create_default_context()
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            with smtplib.SMTP_SSL(HOST, PORT, timeout=12, context=tls) as smtp:
                smtp.login(login, key)
                refused = smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
            if refused:
                return fail("RECIPIENT_REJECTED")
        except smtplib.SMTPAuthenticationError as e:
            return fail("SMTP_AUTH_REJECTED_" + str(int(e.smtp_code)))
        except smtplib.SMTPResponseException as e:
            return fail("SMTP_RESPONSE_" + str(int(e.smtp_code)))
        except ssl.SSLError:
            return fail("TLS_CERTIFICATE_OR_HANDSHAKE_FAILED")
        except (OSError, smtplib.SMTPException):
            return fail("SMTP_CONNECTION_OR_SEND_FAILED")

        print("BREVO_SMTP_PREFLIGHT=PASS")
        print("SMTP_PROVIDER_ACCEPTED=PASS")
        print("PROBE_SUBJECT=KMJ Brevo SMTP Probe " + nonce)
        print("SMTP_INBOX_DELIVERY=NOT_VERIFIED")
        print("PRODUCTION_MAIL_CONFIG=UNCHANGED")
        print("CUSTOMER_REGISTRATION=NOT_ACTIVATED")
        return 0
    except (EOFError, KeyboardInterrupt):
        return fail("OWNER_CANCELLED")
    except ValueError:
        return fail("MAILBOX_FORMAT_NOT_ALLOWED")


if __name__ == "__main__":
    raise SystemExit(main())
