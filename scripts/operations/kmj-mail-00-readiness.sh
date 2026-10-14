#!/usr/bin/env bash
# MAIL-00: read-only preflight. No mail, DNS, firewall, or account mutations.
set -euo pipefail
DOMAIN="kmjtechno.com"
HOST="mail.kmjtechno.com"
IP="${MAIL_PUBLIC_IPV4:-}"
POLICY="${MAIL_HOST_POLICY_APPROVED:-no}"
if [[ -z "$IP" ]]; then
  echo "PUBLIC_SENDER_IPV4=BLOCKED (set MAIL_PUBLIC_IPV4 after confirming egress IP)"
  exit 2
fi
python3 - "$IP" <<'PY'
import ipaddress, sys
address = ipaddress.ip_address(sys.argv[1])
if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
    raise SystemExit("PUBLIC_SENDER_IPV4=INVALID")
PY
command -v dig >/dev/null || { echo "DNS_TOOLS=BLOCKED"; exit 2; }
echo "PUBLIC_SENDER_IPV4=VALID_FORMAT"
if [[ "$POLICY" == "yes" ]]; then
  echo "HOSTING_MAIL_POLICY=OPERATOR_ATTESTED"
else
  echo "HOSTING_MAIL_POLICY=BLOCKED (provider written permission needed)"
fi
A_RECORD="$(dig +short A "$HOST" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)"
PTR="$(dig +short -x "$IP" | tr '[:upper:]' '[:lower:]' | sed 's/\.$//' || true)"
if grep -Fxq "$IP" <<< "$A_RECORD" && [[ "$PTR" == "$HOST" ]]; then
  echo "FORWARD_REVERSE_DNS=PASS"
else
  echo "FORWARD_REVERSE_DNS=BLOCKED (DNS A and provider PTR must agree)"
fi
SPF="$(dig +short TXT "$DOMAIN" | tr -d '"' | grep '^v=spf1 ' || true)"
if [[ "$(wc -l <<< "$SPF")" -eq 1 ]] && [[ " $SPF " == *"ip4:$IP"* ]]; then
  echo "SPF_SENDER_IP=PASS"
else
  echo "SPF_SENDER_IP=BLOCKED (merge ip4 into ONE root SPF record; keep Cloudflare include)"
fi
DMARC="$(dig +short TXT "_dmarc.$DOMAIN" | tr -d '"' | grep '^v=DMARC1;' || true)"
if [[ -n "$DMARC" ]]; then
  echo "DMARC_PRESENT=PASS"
else
  echo "DMARC_PRESENT=BLOCKED"
fi
if dig +short TXT "kmj2026._domainkey.$DOMAIN" | grep -q 'v=DKIM1'; then
  echo "DKIM_DNS_PRESENT=PASS (must still verify it matches local signing key)"
else
  echo "DKIM_DNS_PRESENT=BLOCKED (run MAIL-01 bootstrap to generate public key)"
fi
echo "OUTBOUND_25_TO_GMAIL_MX=SEE_OPERATOR_PROBE (one destination, not delivery proof)"
echo "ACTIVATION=NOT_ATTEMPTED"
