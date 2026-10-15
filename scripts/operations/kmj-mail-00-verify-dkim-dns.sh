#!/usr/bin/env bash
# MAIL-00 read-only: compare the public DNS DKIM selector to the local private key.
# Prints only PASS/BLOCKED; never displays or exports private key material.
set -euo pipefail
DOMAIN=kmjtechno.com
SELECTOR=kmj2026
KEYFILE="/etc/opendkim/keys/$DOMAIN/$SELECTOR.private"

[[ "$(id -u)" -eq 0 ]] || { echo "DKIM_KEY_CHECK=BLOCKED_ROOT_REQUIRED"; exit 2; }
for command in openssl dig python3 base64; do
  command -v "$command" >/dev/null || { echo "DKIM_KEY_CHECK=BLOCKED_MISSING_TOOL"; exit 2; }
done
[[ -f "$KEYFILE" && ! -L "$KEYFILE" ]] || {
  echo "DKIM_KEY_CHECK=BLOCKED_MISSING_OR_SYMLINKED_KEY"
  exit 2
}
PUBLIC_DER="$(openssl pkey -in "$KEYFILE" -pubout -outform DER 2>/dev/null | base64 -w0)"
[[ "${#PUBLIC_DER}" -ge 300 ]] || { echo "DKIM_KEY_CHECK=BLOCKED_BAD_PUBLIC_KEY"; exit 2; }
DNS_RESPONSE="$(dig +time=3 +tries=1 +short TXT "$SELECTOR._domainkey.$DOMAIN")"
if [[ -z "$DNS_RESPONSE" ]]; then
  echo "DKIM_DNS=BLOCKED_MISSING_TXT"
  exit 1
fi
python3 - "$PUBLIC_DER" "$DNS_RESPONSE" <<'PY'
import re
import shlex
import sys

expected, dns_output = sys.argv[1:]
matches = []
for raw in dns_output.splitlines():
    if not raw.strip():
        continue
    try:
        value = ''.join(shlex.split(raw))
    except ValueError:
        print("DKIM_DNS=BLOCKED_INVALID_TXT")
        raise SystemExit(1)
    if value.lower().startswith("v=dkim1;"):
        matches.append(value)
if len(matches) != 1:
    print("DKIM_DNS=BLOCKED_MISSING_OR_DUPLICATE_SELECTOR")
    raise SystemExit(1)
params = {}
for param in matches[0].split(';'):
    if '=' in param:
        key, value = param.split('=', 1)
        params[key.strip().lower()] = value.strip().replace(' ', '')
if params.get('v', '').upper() != 'DKIM1' or params.get('k', 'rsa').lower() != 'rsa':
    print("DKIM_DNS=BLOCKED_INVALID_PROTOCOL_OR_ALGORITHM")
    raise SystemExit(1)
if not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', params.get('p', '')):
    print("DKIM_DNS=BLOCKED_INVALID_PUBLIC_KEY")
    raise SystemExit(1)
if params['p'] != expected:
    print("DKIM_DNS=BLOCKED_PUBLIC_PRIVATE_KEY_MISMATCH")
    raise SystemExit(1)
print("DKIM_DNS_PUBLISHED=PASS")
print("DKIM_PUBLIC_PRIVATE_KEY_MATCH=PASS")
print("DKIM_SMTP_SIGNING=NOT_TESTED")
print("DKIM_INBOX_DELIVERY=NOT_TESTED")
PY
