#!/usr/bin/env bash
# KMJ TECHNO: operator-only, non-deploying outgoing mail staging on KMJ-elite.
# No production Laravel configuration, DNS/MX, firewall, licensing or payment edits.
# Installs fixed distro packages, creates private DKIM key on host, and keeps
# both services disabled/stopped until public DKIM + end-to-end checks pass.
set -Eeuo pipefail
umask 077

DOMAIN=kmjtechno.com
IP=103.212.136.154
HOST=mail.kmjtechno.com
SELECTOR=kmjmail2026
STAMP=/etc/kmj-mail-selfhost-stage-v1
KEYDIR=/etc/opendkim/keys/kmjtechno.com

fail() { echo "MAIL_STAGE=BLOCKED"; echo "REASON=$1"; exit 2; }

if [[ "${1:-}" != --stage ]] || [[ $# -ne 1 ]]; then
  echo 'USAGE=bash script.sh --stage'; exit 2
fi
[[ $(id -u) -eq 0 ]] || fail ROOT_REQUIRED
[[ $(hostname -s) == KMJ-elite ]] || fail WRONG_HOST
[[ -f /etc/os-release ]] || fail OS_UNKNOWN
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == '24.04' ]] || fail UNSUPPORTED_OS
[[ -t 0 && -t 1 ]] || fail OWNER_TTY_REQUIRED
[[ ! -e "$STAMP" && ! -L "$STAMP" ]] || fail ALREADY_STAGED
[[ ! -e /etc/postfix/main.cf && ! -L /etc/postfix/main.cf ]] || fail EXISTING_MAIL_CONFIG_DO_NOT_OVERWRITE
[[ ! -e /etc/opendkim.conf && ! -L /etc/opendkim.conf ]] || fail EXISTING_OPENDKIM_CONFIG_DO_NOT_OVERWRITE

# Existing /etc/opendkim/keys/kmjtechno.com may be an *empty* scaffold
# from an aborted setup. Read metadata only. Reject any existing files,
# extra key directories, symlinks or objects that would be overwritten.
check_preexisting_dkim_tree() {
  local dir="$1" keys="$1/keys" keydir="$1/keys/kmjtechno.com" p found
  for p in "$dir" "$keys" "$keydir"; do
    [[ ! -L "$p" ]] || fail EXISTING_DKIM_SYMLINK
    [[ ! -e "$p" || -d "$p" ]] || fail EXISTING_DKIM_NON_DIRECTORY
  done
  if [[ -d "$dir" ]]; then
    found=$(find "$dir" -mindepth 1 -maxdepth 1 ! -name keys -print -quit) || fail DKIM_TREE_READ_FAILED
    [[ -z "$found" ]] || fail EXISTING_OPENDKIM_CONFIG_DO_NOT_OVERWRITE
  fi
  if [[ -d "$keys" ]]; then
    found=$(find "$keys" -mindepth 1 -maxdepth 1 ! -name kmjtechno.com -print -quit) || fail DKIM_TREE_READ_FAILED
    [[ -z "$found" ]] || fail EXISTING_OTHER_DKIM_KEYS_DO_NOT_OVERWRITE
  fi
  if [[ -d "$keydir" ]]; then
    found=$(find "$keydir" -mindepth 1 -print -quit) || fail DKIM_TREE_READ_FAILED
    [[ -z "$found" ]] || fail EXISTING_DKIM_KEY_MATERIAL_DO_NOT_OVERWRITE
  fi
}
check_preexisting_dkim_tree /etc/opendkim
[[ ! -e /etc/opendkim.conf.kmj-package-default-20261021 && ! -L /etc/opendkim.conf.kmj-package-default-20261021 ]] || fail EXISTING_BACKUP_DO_NOT_OVERWRITE
[[ $(getent ahostsv4 "$HOST" | awk 'NR==1 {print $1}') == "$IP" ]] || fail MAIL_A_RECORD_MISMATCH
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|993)$'; then
  fail EXISTING_MAIL_LISTENER
fi
[[ $(df -Pk / | awk 'NR==2 {print $4}') -ge 1048576 ]] || fail INSUFFICIENT_DISK
for cmd in apt-get dpkg-query debconf-set-selections ss getent openssl systemctl; do
  command -v "$cmd" >/dev/null 2>&1 || fail "MISSING_TOOL_$cmd"
done

printf '%s\n' \
  'KMJ_SELFHOSTED_MAIL=STAGE_ONLY' \
  'PKGS=postfix,opendkim,opendkim-tools' \
  "MAIL_HOST=$HOST" \
  'PUBLIC_SMTP_LISTENER=DISALLOWED' \
  'LARAVEL_MAIL_CONFIG=UNCHANGED' \
  'MX_AND_DNS=UNCHANGED' \
  'NO_TEST_EMAIL_WILL_BE_SENT'
printf 'Type STAGE LOCAL MAIL to install packages and stage stopped services: '
IFS= read -r confirmation
[[ "$confirmation" == 'STAGE LOCAL MAIL' ]] || fail OWNER_NOT_CONFIRMED

# Preseed "Local only" so an apt post-install auto-start, if any, never
# exposes an inbound/public SMTP listener. No global system service policy edits.
cleanup() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    systemctl stop postfix opendkim >/dev/null 2>&1 || true
    systemctl disable postfix opendkim >/dev/null 2>&1 || true
    echo "MAIL_STAGE=INCOMPLETE_EXIT_$rc"
    echo 'NO_PRODUCTION_CUTOVER_ATTEMPTED'
  fi
}
trap cleanup EXIT

printf '%s\n' \
  "postfix postfix/main_mailer_type select Local only" \
  "postfix postfix/mailname string $DOMAIN" | debconf-set-selections
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends postfix opendkim opendkim-tools
command -v postconf >/dev/null 2>&1 || fail POSTCONF_NOT_INSTALLED
# Fail if package preseed did not apply: stop services without affecting web.
if [[ $(postconf -h inet_interfaces) != 'loopback-only' ]]; then
  systemctl stop postfix opendkim >/dev/null 2>&1 || true
  fail POSTFIX_INSTALL_BOUND_PUBLIC
fi
systemctl stop postfix opendkim >/dev/null 2>&1 || true

# Validate again because package installation may have created defaults.
# Never overwrite package-provided /etc/opendkim/TrustedHosts or existing keys.
check_preexisting_dkim_tree /etc/opendkim
command -v opendkim-genkey >/dev/null 2>&1 || fail OPENDKIM_GENERATOR_MISSING
id opendkim >/dev/null 2>&1 || fail OPENDKIM_USER_MISSING
install -d -o opendkim -g opendkim -m 0750 "$KEYDIR"
( cd "$KEYDIR" && opendkim-genkey -b 2048 -s "$SELECTOR" -d "$DOMAIN" )
chown opendkim:opendkim "$KEYDIR/$SELECTOR.private"
chmod 0600 "$KEYDIR/$SELECTOR.private"
chmod 0644 "$KEYDIR/$SELECTOR.txt"

if [[ -f /etc/opendkim.conf ]]; then
  cp -p /etc/opendkim.conf /etc/opendkim.conf.kmj-package-default-20261021
fi
cat > /etc/opendkim.conf <<DKIM
Syslog                  yes
UMask                   007
Mode                    s
Canonicalization        relaxed/simple
UserID                  opendkim
Socket                  inet:8891@127.0.0.1
Domain                  $DOMAIN
Selector                $SELECTOR
KeyFile                 $KEYDIR/$SELECTOR.private
InternalHosts           /etc/opendkim/TrustedHosts
DKIM
install -d -m 0755 /etc/opendkim
cat > /etc/opendkim/TrustedHosts <<'TRUSTED'
127.0.0.1
localhost
TRUSTED
chown root:opendkim /etc/opendkim.conf /etc/opendkim/TrustedHosts
chmod 0640 /etc/opendkim.conf /etc/opendkim/TrustedHosts

postconf -e "myhostname = $HOST"
postconf -e "mydomain = $DOMAIN"
postconf -e "myorigin = $DOMAIN"
postconf -e 'mydestination = localhost'
postconf -e 'inet_interfaces = loopback-only'
postconf -e 'inet_protocols = ipv4'
postconf -e 'mynetworks = 127.0.0.0/8'
postconf -e 'smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination'
postconf -e 'relayhost ='
postconf -e 'smtp_helo_name = mail.kmjtechno.com'
postconf -e 'smtp_tls_security_level = may'
postconf -e 'smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt'
postconf -e 'smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'milter_default_action = tempfail'
postconf -e 'milter_protocol = 6'
postfix check || fail POSTFIX_CHECK_FAILED

systemctl stop postfix opendkim >/dev/null 2>&1 || true
systemctl disable postfix opendkim >/dev/null 2>&1 || true
# Do not claim stopped/disabled unless actually checked. "static" is
# permitted because it cannot start automatically via enablement alone.
for service in postfix opendkim; do
  active=$(systemctl is-active "$service" 2>/dev/null || true)
  [[ "$active" != active && "$active" != activating ]] || fail MAIL_SERVICE_STILL_ACTIVE
  enabled=$(systemctl is-enabled "$service" 2>/dev/null || true)
  case "$enabled" in
    enabled|enabled-runtime|linked|linked-runtime)
      fail MAIL_SERVICE_AUTOSTART_NOT_DISABLED ;;
  esac
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|993|8891)$'; then
  fail UNEXPECTED_MAIL_LISTENER
fi
[[ $(postconf -h inet_interfaces) == 'loopback-only' ]] || fail POSTFIX_BIND_UNSAFE
[[ $(postconf -h mydestination) == 'localhost' ]] || fail POSTFIX_LOCAL_DOMAINS_UNSAFE
[[ $(postconf -h relayhost) == '' ]] || fail RELAYHOST_UNEXPECTED

printf '%s\n' 'STAGED_NO_PRODUCTION_CUTOVER=YES' > "$STAMP"
chmod 0600 "$STAMP"
echo 'MAIL_STAGE=PASS'
echo 'POSTFIX_CONFIG=LOOPBACK_ONLY'
echo 'SERVICES=STOPPED_DISABLED'
echo 'NO_EMAIL_SENT=YES'
echo 'LARAVEL_CONFIG=UNCHANGED'
echo 'MX_AND_DNS=UNCHANGED'
echo "DKIM_PUBLIC_NAME=$SELECTOR._domainkey.$DOMAIN"
echo 'DKIM_PUBLIC_TXT_BEGIN'
cat "$KEYDIR/$SELECTOR.txt"
echo 'DKIM_PUBLIC_TXT_END'
echo 'NEXT=VERIFY_AND_PUBLISH_PUBLIC_DKIM_BEFORE_SERVICE_ACTIVATION'
