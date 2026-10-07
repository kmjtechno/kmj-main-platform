#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

DOMAIN="${KMJ_STAGE_DOMAIN:-staging.kmjtechno.com}"
PRODUCTION_DOMAIN="${KMJ_PRODUCTION_DOMAIN:-kmjtechno.com}"

[[ $EUID -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
[[ "$DOMAIN" == "staging.kmjtechno.com" ]] || {
  echo "Refusing non-canonical staging domain: $DOMAIN" >&2
  exit 2
}
[[ "$DOMAIN" != "$PRODUCTION_DOMAIN" ]] || {
  echo "Refusing production domain." >&2
  exit 3
}

command -v clpctl >/dev/null 2>&1 || {
  echo "CloudPanel CLI is not installed." >&2
  exit 4
}
systemctl is-active --quiet nginx || {
  echo "nginx is not active." >&2
  exit 5
}

server_ip="$(curl -4 -fsS --max-time 10 https://api.ipify.org)"
resolved="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}')"
[[ -n "$server_ip" && "$resolved" == "$server_ip" ]] || {
  echo "DNS mismatch: $DOMAIN does not resolve to this VPS." >&2
  exit 6
}

if ! clpctl site:list 2>/dev/null | grep -Fq "$DOMAIN"; then
  echo "CloudPanel site for $DOMAIN is missing; rerun /root/KMJ_SERVER_BOOTSTRAP.sh." >&2
  exit 7
fi

clpctl lets-encrypt:install:certificate --domainName="$DOMAIN"
systemctl reload nginx

cert="$(mktemp)"
trap 'rm -f "$cert"' EXIT
timeout 20 openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN" -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM >"$cert"

openssl x509 -in "$cert" -noout -ext subjectAltName | grep -Fq "DNS:$DOMAIN" || {
  openssl x509 -in "$cert" -noout -subject -issuer -dates -ext subjectAltName >&2 || true
  echo "Installed certificate still does not cover $DOMAIN." >&2
  exit 8
}

headers="$(curl -sSI --max-time 10 -H "Host: $DOMAIN" http://127.0.0.1/ || true)"
location="$(printf '%s\n' "$headers" | awk -F': *' 'tolower($1)=="location" {gsub("\r","",$2); print $2; exit}')"
case "$location" in
  ""|"https://$DOMAIN"|"https://$DOMAIN/"|"https://$DOMAIN/"*) ;;
  *)
    echo "Staging vhost routes to unexpected location: $location" >&2
    exit 9
    ;;
esac

curl --fail --silent --show-error --location --max-time 20 "https://$DOMAIN/" >/dev/null
echo "PASS: $DOMAIN TLS certificate and nginx vhost are valid."
