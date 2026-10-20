#!/usr/bin/env bash
# Owner-operated staging ONLY: do not start mail services or alter DNS/Laravel.
set -Eeuo pipefail
umask 077

DOMAIN=kmjtechno.com
IP=103.212.136.154
HOST=mail.kmjtechno.com
SELECTOR=kmj2026
ORIGINAL_DIR=/etc/opendkim/keys/kmjtechno.com
ORIGINAL_KEY=$ORIGINAL_DIR/kmj2026.private
ORIGINAL_TXT=$ORIGINAL_DIR/kmj2026.txt
ACTIVE_DIR=/etc/opendkim/kmj-active-reuse
STAGED=/etc/kmj-mail-selfhost-reuse-staged-20261021
PACKAGE_CONFIG_BACKUP=/etc/opendkim.conf.kmj-package-default-reuse-20261021

fail() { printf 'MAIL_STAGE=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
[ "${1:-}" = '--stage' ] && [ "$#" -eq 1 ] || fail ARGUMENT_MUST_BE_STAGE
[ "$(id -u)" -eq 0 ] || fail ROOT_REQUIRED
[ "$(hostname -s)" = 'KMJ-elite' ] || fail WRONG_HOST
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || fail OS_UNSUPPORTED
[ -t 0 ] && [ -t 1 ] || fail INTERACTIVE_TTY_REQUIRED
for cmd in apt-get debconf-set-selections dpkg-query openssl python3 ss getent systemctl find stat install sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || fail "TOOL_MISSING_$cmd"
done
[ ! -e "$STAGED" ] && [ ! -L "$STAGED" ] || fail ALREADY_STAGED
[ ! -e /etc/postfix/main.cf ] && [ ! -L /etc/postfix/main.cf ] || fail EXISTING_POSTFIX_CONFIG
[ ! -e /etc/opendkim.conf ] && [ ! -L /etc/opendkim.conf ] || fail EXISTING_OPENDKIM_CONFIG
[ ! -e "$ACTIVE_DIR" ] && [ ! -L "$ACTIVE_DIR" ] || fail EXISTING_ACTIVE_KEY_COPY
[ ! -e "$PACKAGE_CONFIG_BACKUP" ] && [ ! -L "$PACKAGE_CONFIG_BACKUP" ] || fail EXISTING_PACKAGE_BACKUP
[ ! -e /etc/opendkim/TrustedHosts ] && [ ! -L /etc/opendkim/TrustedHosts ] || fail EXISTING_TRUSTED_HOSTS
for p in /etc/opendkim /etc/opendkim/keys "$ORIGINAL_DIR"; do
  [ -d "$p" ] && [ ! -L "$p" ] || fail EXISTING_DKIM_TREE_UNSAFE
done
for p in "$ORIGINAL_KEY" "$ORIGINAL_TXT"; do
  [ -f "$p" ] && [ ! -L "$p" ] || fail EXISTING_DKIM_KEY_FILE_UNSAFE
  [ "$(stat -c %u "$p")" -eq 0 ] || fail EXISTING_DKIM_KEY_NOT_ROOT_OWNED
done
[ "$(stat -c %a "$ORIGINAL_KEY")" = 600 ] || fail PRIVATE_KEY_PERMISSIONS_UNEXPECTED
[ -z "$(find /etc/opendkim -mindepth 1 -maxdepth 1 ! -name keys -print -quit)" ] || fail EXISTING_OPENDKIM_CONTENT
[ -z "$(find /etc/opendkim/keys -mindepth 1 -maxdepth 1 ! -name kmjtechno.com -print -quit)" ] || fail EXISTING_OTHER_DOMAIN_KEYS
[ -z "$(find "$ORIGINAL_DIR" -mindepth 1 -maxdepth 1 ! -name kmj2026.private ! -name kmj2026.txt -print -quit)" ] || fail EXISTING_EXTRA_KEY_FILES
[ "$(getent ahostsv4 "$HOST" | awk 'NR==1 {print $1}')" = "$IP" ] || fail MAIL_A_RECORD_CHANGED
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail EXISTING_SMTP_LISTENER
fi
[ "$(df -Pk / | awk 'NR==2 {print $4}')" -ge 1048576 ] || fail INSUFFICIENT_DISK

# Derive public key from original WITHOUT exposing it; compare with existing
# server-side TXT and publicly published kmj2026 TXT. No private data leaves host.
if python3 - "$ORIGINAL_KEY" "$ORIGINAL_TXT" <<'PY'
import base64, json, re, subprocess, sys, urllib.request
private, txt = sys.argv[1:]
def key(raw):
    quoted = re.findall(r'"([^"]*)"', raw)
    val = ''.join(quoted) if quoted else raw
    match = re.search(r'(?:^|;)\s*p\s*=\s*([A-Za-z0-9+/=]+)', val)
    if not match:
        raise ValueError("DKIM key missing")
    return base64.b64decode(match.group(1), validate=True)
derived = subprocess.run(
    ["openssl", "pkey", "-in", private, "-pubout", "-outform", "DER"],
    stdin=subprocess.DEVNULL, check=True, capture_output=True, timeout=20
).stdout
if key(open(txt, encoding="utf-8").read()) != derived:
    sys.exit(21)
url = "https://dns.google/resolve?name=kmj2026._domainkey.kmjtechno.com&type=TXT"
with urllib.request.urlopen(url, timeout=15) as response:
    dns = json.load(response)
if dns.get("Status") != 0:
    sys.exit(22)
public = [a.get("data", "") for a in dns.get("Answer", []) if a.get("type") == 16]
if not any(key(r) == derived for r in public if "p=" in r):
    sys.exit(23)
PY
then echo 'PRIVATE_LOCAL_PUBLIC_DNS=PASS'
else fail PRIVATE_OR_PUBLIC_DKIM_MISMATCH
fi

echo 'KMJ_MAIL_REUSE=PREINSTALL_PREFLIGHT_PASS'
echo "MAIL_HOST=$HOST"
echo 'EXISTING_DKIM_KEY=REUSE_WITH_RESTRICTED_COPY'
echo 'CURRENT_EMAIL_DELIVERY=UNCHANGED'
echo 'PUBLIC_SMTP_LISTENERS=NONE'
echo 'LARAVEL_AND_MX_CONFIG=UNCHANGED'
printf 'Type REUSE KMJ2026 to stage local Postfix/OpenDKIM (no email sent): '
IFS= read -r answer
[ "$answer" = 'REUSE KMJ2026' ] || fail OWNER_CONFIRMATION_MISSING

cleanup() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    systemctl stop postfix opendkim >/dev/null 2>&1 || true
    systemctl disable postfix opendkim >/dev/null 2>&1 || true
    printf 'MAIL_STAGE=INCOMPLETE_EXIT_%s\nSERVICES_STOP_ATTEMPTED=YES\n' "$rc"
  fi
}
trap cleanup EXIT

# Do not allow apt to open an externally accessible SMTP listener.
printf '%s\n' \
  'postfix postfix/main_mailer_type select Local only' \
  "postfix postfix/mailname string $DOMAIN" | debconf-set-selections
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends postfix opendkim opendkim-tools
systemctl stop postfix opendkim >/dev/null 2>&1 || true
systemctl disable postfix opendkim >/dev/null 2>&1 || true
command -v postconf >/dev/null 2>&1 || fail POSTFIX_NOT_INSTALLED
[ "$(postconf -h inet_interfaces)" = loopback-only ] || fail POSTFIX_PACKAGE_BOUND_PUBLIC
id opendkim >/dev/null 2>&1 || fail OPENDKIM_USER_MISSING
[ ! -L /etc/opendkim.conf ] && [ -f /etc/opendkim.conf ] || fail PACKAGE_OPEN_DKIM_CONFIG_UNEXPECTED
[ ! -e "$PACKAGE_CONFIG_BACKUP" ] && [ ! -L "$PACKAGE_CONFIG_BACKUP" ] || fail PACKAGE_BACKUP_CONFLICT
[ ! -e /etc/opendkim/TrustedHosts ] && [ ! -L /etc/opendkim/TrustedHosts ] || fail PACKAGE_TRUSTED_HOSTS_CONFLICT
[ ! -e "$ACTIVE_DIR" ] && [ ! -L "$ACTIVE_DIR" ] || fail ACTIVE_DIR_CONFLICT

# Copy from immutable original; original ownership, permissions and bytes
# remain untouched. No private material is committed, logged or displayed.
original_digest=$(sha256sum "$ORIGINAL_KEY" | cut -d' ' -f1)
install -d -o opendkim -g opendkim -m 0700 "$ACTIVE_DIR"
install -o opendkim -g opendkim -m 0400 "$ORIGINAL_KEY" "$ACTIVE_DIR/kmj2026.private"
cmp -s "$ORIGINAL_KEY" "$ACTIVE_DIR/kmj2026.private" || fail DKIM_PRIVATE_COPY_MISMATCH
[ "$(sha256sum "$ORIGINAL_KEY" | cut -d' ' -f1)" = "$original_digest" ] || fail ORIGINAL_PRIVATE_KEY_CHANGED

cp -p --no-clobber /etc/opendkim.conf "$PACKAGE_CONFIG_BACKUP"
cat > /etc/opendkim.conf <<CONF
Syslog                  yes
UMask                   007
Mode                    s
Canonicalization        relaxed/simple
UserID                  opendkim
Socket                  inet:8891@127.0.0.1
Domain                  $DOMAIN
Selector                $SELECTOR
KeyFile                 $ACTIVE_DIR/kmj2026.private
InternalHosts           /etc/opendkim/TrustedHosts
CONF
cat > /etc/opendkim/TrustedHosts <<'HOSTS'
127.0.0.1
localhost
HOSTS
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
postconf -e "smtp_helo_name = $HOST"
postconf -e 'smtp_tls_security_level = may'
postconf -e 'smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt'
postconf -e 'smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'milter_default_action = tempfail'
postconf -e 'milter_protocol = 6'
postfix check || fail POSTFIX_CHECK_FAILED
systemctl stop postfix opendkim >/dev/null 2>&1 || true
systemctl disable postfix opendkim >/dev/null 2>&1 || true
for svc in postfix opendkim; do
  active=$(systemctl is-active "$svc" 2>/dev/null || true)
  [ "$active" != active ] && [ "$active" != activating ] || fail SERVICE_UNEXPECTEDLY_ACTIVE
  enabled=$(systemctl is-enabled "$svc" 2>/dev/null || true)
  case "$enabled" in
    enabled|enabled-runtime|linked|linked-runtime) fail SERVICE_UNEXPECTEDLY_AUTOSTARTED ;;
  esac
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail MAIL_LISTENER_UNEXPECTED
fi
[ "$(postconf -h inet_interfaces)" = loopback-only ] || fail POSTFIX_BIND_UNSAFE
[ "$(postconf -h mydestination)" = localhost ] || fail POSTFIX_DESTINATIONS_UNSAFE
[ -z "$(postconf -h relayhost)" ] || fail EXTERNAL_RELAY_UNEXPECTED
[ "$(stat -c %a "$ORIGINAL_KEY")" = 600 ] || fail ORIGINAL_KEY_PERMISSIONS_CHANGED
[ "$(sha256sum "$ORIGINAL_KEY" | cut -d' ' -f1)" = "$original_digest" ] || fail ORIGINAL_KEY_CHANGED
printf 'ORIGINAL_KMJ2026_KEY_PRESERVED=YES\n' > "$STAGED"
chmod 0600 "$STAGED"
echo 'MAIL_STAGE=PASS'
echo 'ORIGINAL_DKIM_KEY=UNCHANGED'
echo 'DKIM_SELECTOR=kmj2026'
echo 'MAIL_SERVICES=STOPPED_DISABLED'
echo 'POSTFIX=LOOPBACK_ONLY'
echo 'MX_AND_LARAVEL=UNCHANGED'
echo 'NO_EMAIL_SENT=YES'
echo 'NEXT=SEPARATE_APPROVED_CONTROLLED_ACTIVATION'
