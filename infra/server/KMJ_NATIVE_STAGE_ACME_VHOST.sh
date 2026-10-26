#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Stage-only ACME HTTP bootstrap on the existing production host.
# It does NOT create a Laravel deployment, issue a cert or alter production.
domain=staging.kmjtechno.com
public_ip=103.212.136.154
conf=/etc/nginx/conf.d/kmj-staging-acme.conf
webroot=/var/lib/kmj-staging-acme
site_dir=/home/kmjstage/htdocs/staging.kmjtechno.com

if [[ "$(hostname -s)" != KMJ-elite || "$EUID" -ne 0 ]]; then
  echo 'STAGING_ACME=BLOCKED WRONG_HOST_OR_USER'
  exit 2
fi
if [[ ! -d /home/kmjprod/current ]]; then
  echo 'STAGING_ACME=BLOCKED PRODUCTION_BASELINE_UNKNOWN'
  exit 2
fi
before="$(readlink -f /home/kmjprod/current)"
[[ -d "$before" ]] || exit 2
[[ "${1:-}" == --inspect || "${1:-}" == --apply ]] || {
  echo 'USAGE=KMJ_NATIVE_STAGE_ACME_VHOST.sh --inspect|--apply'
  exit 2
}
mode="$1"
if ! systemctl is-active --quiet nginx || ! nginx -t >/dev/null 2>&1; then
  echo 'STAGING_ACME=BLOCKED NGINX_NOT_HEALTHY'
  exit 3
fi
if [[ -e "$conf" || -L "$conf" ]]; then
  echo 'STAGING_ACME=BLOCKED CONFIG_ALREADY_EXISTS'
  exit 3
fi
if [[ -L "$webroot" || -L "$site_dir" ]]; then
  echo 'STAGING_ACME=BLOCKED STAGING_PATH_SYMLINK'
  exit 3
fi
if [[ -e "$webroot" && ! -d "$webroot" ]]; then
  echo 'STAGING_ACME=BLOCKED ACME_ROOT_NOT_DIRECTORY'
  exit 3
fi
if [[ -L "$webroot/.well-known" || -L "$webroot/.well-known/acme-challenge" ]]; then
  echo 'STAGING_ACME=BLOCKED ACME_PATH_SYMLINK'
  exit 3
fi
[[ ! -e "$site_dir" ]] || {
  echo 'STAGING_ACME=BLOCKED EXISTING_STAGE_SITE_REQUIRES_REVIEW'
  exit 3
}
if ! config="$(nginx -T 2>/dev/null)"; then
  echo 'STAGING_ACME=BLOCKED EFFECTIVE_CONFIG_UNREADABLE'
  exit 3
fi
if ! grep -Eq '^[[:space:]]*include[[:space:]]+/etc/nginx/conf[.]d/\*[.]conf[[:space:]]*;' <<< "$config"; then
  echo 'STAGING_ACME=BLOCKED CONF_D_NOT_INCLUDED'
  exit 3
fi
if grep -Eq '^[[:space:]]*server_name[[:space:]]+[^;]*staging[.]kmjtechno[.]com([[:space:];]|$)' <<< "$config"; then
  echo 'STAGING_ACME=BLOCKED STAGING_SERVER_ALREADY_DEFINED'
  exit 3
fi
unset config
[[ -d /etc/nginx/conf.d && ! -L /etc/nginx/conf.d ]] || {
  echo 'STAGING_ACME=BLOCKED CONFIG_DIRECTORY_UNSAFE'
  exit 3
}
if [[ ! -w /etc/nginx/conf.d ]]; then
  echo 'STAGING_ACME=BLOCKED CONFIG_DIRECTORY_NOT_WRITABLE'
  exit 3
fi
if ! command -v certbot >/dev/null 2>&1; then
  echo 'STAGING_ACME=BLOCKED CERTBOT_UNAVAILABLE'
  exit 3
fi
if [[ "$mode" == --inspect ]]; then
  echo 'STAGING_ACME=READY_FOR_OWNER_APPLY'
  echo 'STAGING_HTTP_BEHAVIOR=ACME_ONLY_503_OTHER_PATHS'
  echo 'STAGING_LARAVEL=NOT_INSTALLED'
  echo 'STAGING_TLS=NOT_ISSUED'
  echo 'PRODUCTION_POINTER=UNCHANGED'
  exit 0
fi

read -r -p 'Type STAGING_HTTP_ONLY to authorize new ACME vhost: ' answer </dev/tty
[[ "$answer" == STAGING_HTTP_ONLY ]] || {
  echo 'STAGING_ACME=BLOCKED OWNER_CONFIRMATION_REQUIRED'
  exit 4
}
server_ip="$(curl -4 --fail --silent --show-error --max-time 12 https://api.ipify.org)"
mapfile -t resolved < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
[[ "$server_ip" == "$public_ip" && "${#resolved[@]}" -eq 1 && "${resolved[0]}" == "$public_ip" ]] || {
  echo 'STAGING_ACME=BLOCKED DNS_OR_SERVER_IDENTITY_MISMATCH'
  exit 4
}
exec 9>/run/kmj-native-stage-acme.lock
flock -n 9 || {
  echo 'STAGING_ACME=BLOCKED LOCKED_BY_OTHER_OPERATOR'
  exit 4
}
[[ ! -e "$conf" && ! -L "$conf" ]] || exit 4
tmp="$(mktemp)"
added=0
complete=0
rollback() {
  if [[ "$added" == 1 && "$complete" != 1 ]]; then
    if [[ -f "$conf" && ! -L "$conf" && "$(sha256sum "$conf" | cut -d' ' -f1)" == "$expected_conf_hash" ]]; then
      rm -f -- "$conf"
      nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1 || true
    fi
    echo 'STAGING_ACME=ROLLED_BACK_OR_NEEDS_OPERATOR_REVIEW' >&2
  fi
  rm -f -- "$tmp"
}
trap rollback EXIT

cat >"$tmp" <<'NGINX'
# Staging ACME only: NOT a deployed Laravel site.
server {
    listen 80;
    server_name staging.kmjtechno.com;
    root /var/lib/kmj-staging-acme;
    autoindex off;
    location ^~ /.well-known/acme-challenge/ {
        default_type text/plain;
        try_files $uri =404;
    }
    location / { return 503; }
}
NGINX
expected_conf_hash="$(sha256sum "$tmp" | cut -d' ' -f1)"
install -d -o root -g root -m 0755 "$webroot"
install -d -o root -g root -m 0755 "$webroot/.well-known"
install -d -o root -g root -m 0755 "$webroot/.well-known/acme-challenge"
[[ ! -e "$conf" && ! -L "$conf" ]] || exit 4
install -o root -g root -m 0644 "$tmp" "$conf"
added=1
nginx -t
systemctl reload nginx
[[ "$(readlink -f /home/kmjprod/current)" == "$before" ]] || {
  echo 'STAGING_ACME=BLOCKED PRODUCTION_POINTER_CHANGED'
  exit 5
}
challenge="$webroot/.well-known/acme-challenge/kmj-preflight-$$"
[[ ! -e "$challenge" && ! -L "$challenge" ]] || exit 5
printf 'KMJ_STAGE_ACME_PROBE\n' > "$challenge"
chmod 0644 "$challenge"
set +e
response="$(curl --noproxy '*' --silent --show-error --connect-timeout 4 --max-time 10 --header "Host: $domain" "http://127.0.0.1/.well-known/acme-challenge/$(basename "$challenge")")"
status=$?
set -e
rm -f -- "$challenge"
[[ "$status" -eq 0 && "$response" == KMJ_STAGE_ACME_PROBE ]] || {
  echo 'STAGING_ACME=BLOCKED LOCAL_CHALLENGE_ROUTE_FAILED'
  exit 5
}
complete=1
echo 'STAGING_ACME=PASS_ACME_HTTP_ONLY'
echo 'STAGING_TLS=NOT_ISSUED'
echo 'STAGING_LARAVEL=NOT_INSTALLED'
echo 'PRODUCTION_POINTER=UNCHANGED'
echo 'NEXT=REVIEW_WEBROOT_CERTIFICATE_AND_SEPARATE_LARAVEL_RUNTIME'
