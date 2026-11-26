#!/usr/bin/env python3
"""Source-only single-recipient Postfix delivery adapter; never edits host configuration."""
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import stat
import sys
import time
import uuid

RECIPIENT = "mail-pilot@kmjtechno.com"
RECIPIENTS = frozenset({RECIPIENT, "info@kmjtechno.com"})
HOST = "kmjtechno.com"
PATH = "/api/kmj-mail/inbound/pilot"
SECRET_PATH = "/etc/kmj-mail-inbound/pilot.hex"
MAX_BYTES = 262144
MAX_RECEIPT = 1024
OK = 0
TEMPFAIL = 75
DATAERR = 65


def load_key():
    # Root-owned, group-readable only; never accept a secret from argv or env.
    fd = os.open(SECRET_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o640):
            raise ValueError("invalid key file")
        encoded = stream.read(66)
    if not re.fullmatch(rb"[0-9a-f]{64}\n?", encoded):
        raise ValueError("invalid key format")
    return bytes.fromhex(encoded.decode("ascii").strip())


def headers_for(raw, sender, key, event=None, timestamp=None, *, recipient=RECIPIENT):
    if recipient not in RECIPIENTS:
        raise ValueError("unsupported recipient")
    event = event or str(uuid.uuid4())
    timestamp = timestamp or str(int(time.time()))
    digest = hashlib.sha256(raw).hexdigest()
    signed = "\n".join(("kmj-inbound-v1", event, timestamp, recipient, sender, digest))
    signature = hmac.new(key, signed.encode("ascii"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "message/rfc822",
        "X-KMJ-Mail-Event": event,
        "X-KMJ-Mail-Timestamp": timestamp,
        "X-KMJ-Mail-Recipient": recipient,
        "X-KMJ-Mail-Envelope-From": sender,
        "X-KMJ-Mail-Signature": signature,
    }


def submit(raw, headers):
    # Direct HTTPS, default CA and hostname validation, no redirects/proxies.
    conn = http.client.HTTPSConnection(HOST, timeout=10, context=ssl.create_default_context())
    try:
        conn.request("POST", PATH, body=raw, headers=headers)
        response = conn.getresponse()
        return response.status, response.read(MAX_RECEIPT + 1)
    finally:
        conn.close()


def unique_json_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate receipt key")
        obj[key] = value
    return obj


def deliver(args, stream, key_loader=load_key, receiver=submit):
    # Postfix supplies exactly two single argv values (no shell).
    # Null reverse-path is the literal empty value, not a fabricated sender.
    if (len(args) != 2 or not args[0].startswith("sender=")
            or not args[1].startswith("recipient=")):
        return TEMPFAIL
    recipient = args[1][len("recipient="):]
    if recipient not in RECIPIENTS:
        return TEMPFAIL
    sender = args[0][len("sender="):]
    if len(sender) > 254 or (sender and not re.fullmatch(
            r"[!-~]+@[A-Za-z0-9.-]+", sender)):
        return DATAERR
    try:
        raw = stream.read(MAX_BYTES + 1)
        if not raw or len(raw) > MAX_BYTES:
            return DATAERR
        key = key_loader()
        if not isinstance(key, bytes) or len(key) != 32:
            return TEMPFAIL
        status, receipt = receiver(raw, headers_for(raw, sender, key, recipient=recipient))
        if status not in (200, 201) or len(receipt) > MAX_RECEIPT:
            return TEMPFAIL
        # Acknowledge only the exact controller receipt. Duplicate JSON keys,
        # extra fields or ambiguous responses must not remove queued mail.
        parsed = json.loads(receipt, object_pairs_hook=unique_json_object)
        expected = {"state": "quarantined" if status == 201 else "duplicate"}
        return OK if isinstance(parsed, dict) and parsed == expected else TEMPFAIL
    except Exception:
        # Never emit MIME, sender, signature, secret, response or tracebacks.
        return TEMPFAIL


def main():
    code = deliver(sys.argv[1:], sys.stdin.buffer)
    if code == OK:
        print("KMJ_INBOUND_DURABLE_RECEIPT")
    elif code == DATAERR:
        print("5.6.0 KMJ pilot message outside accepted bounds")
    else:
        print("4.3.0 KMJ pilot intake temporarily unavailable")
    return code


if __name__ == "__main__":
    sys.exit(main())
