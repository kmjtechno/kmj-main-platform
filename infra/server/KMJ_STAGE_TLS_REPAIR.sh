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

systemctl is-active --quiet nginx || {
  echo "STAGING_TLS_REPAIR=BLOCKED NGINX_NOT_ACTIVE" >&2
  exit 5
}
nginx -t >/dev/null 2>&1 || {
  echo "STAGING_TLS_REPAIR=BLOCKED NGINX_CONFIG_INVALID" >&2
  exit 5
}
# Production is never an approved target for the staging certificate repair.
production_before="$(readlink -f /home/kmjprod/current)" || exit 5
[[ -d "$production_before" ]] || {
  echo "STAGING_TLS_REPAIR=BLOCKED PRODUCTION_BASELINE_UNKNOWN" >&2
  exit 5
}

server_ip="$(curl -4 -fsS --max-time 10 https://api.ipify.org)"
resolved="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}')"
[[ -n "$server_ip" && "$resolved" == "$server_ip" ]] || {
  echo "DNS mismatch: $DOMAIN does not resolve to this VPS." >&2
  exit 6
}

if command -v clpctl >/dev/null 2>&1; then
  # Never install CloudPanel or rebuild the production host during certificate repair.
  if ! clpctl site:list 2>/dev/null | grep -Fq "$DOMAIN"; then
    echo "STAGING_TLS_REPAIR=BLOCKED STAGING_CLOUDPANEL_SITE_MISSING" >&2
    exit 7
  fi
  clpctl lets-encrypt:install:certificate --domainName="$DOMAIN"
else
  # Standalone Nginx installations may have no CloudPanel CLI. This path
  # requires an existing dedicated staging vhost and preinstalled certbot
  # Nginx plugin; it never creates or edits a production vhost directly.
  if ! command -v certbot >/dev/null 2>&1; then
    echo "STAGING_TLS_REPAIR=BLOCKED CERTBOT_UNAVAILABLE" >&2
    exit 7
  fi
  if ! nginx -T 2>/dev/null | grep -Eq '^[[:space:]]*server_name[[:space:]]+staging[.]kmjtechno[.]com([[:space:];]|$)'; then
    echo "STAGING_TLS_REPAIR=BLOCKED DEDICATED_STAGING_VHOST_MISSING" >&2
    exit 7
  fi
  if ! certbot plugins --text 2>/dev/null | grep -Eq 'nginx|Nginx'; then
    echo "STAGING_TLS_REPAIR=BLOCKED CERTBOT_NGINX_PLUGIN_MISSING" >&2
    exit 7
  fi
  # --nginx provisions only the staging hostname chosen above. Certbot
  # fails closed if no existing account or suitable challenge route exists.
  certbot --nginx --non-interactive --agree-tos --no-redirect -d "$DOMAIN"
fi
nginx -t
systemctl reload nginx
if [[ "$(readlink -f /home/kmjprod/current)" != "$production_before" ]]; then
  echo "STAGING_TLS_REPAIR=FAIL PRODUCTION_RELEASE_POINTER_CHANGED" >&2
  exit 10
fi

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
