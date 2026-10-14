#!/usr/bin/env bash
# MAIL-01 bootstrap only: local-only Postfix SMTP + OpenDKIM signing.
# Does NOT change Laravel MAIL_MAILER, public DNS, PTR, or existing MX.
set -euo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo "ROOT_REQUIRED"; exit 2; }
[[ "${MAIL_BOOTSTRAP_APPROVED:-no}" == "yes" ]] || {
  echo "BLOCKED: set MAIL_BOOTSTRAP_APPROVED=yes to install and configure system packages"
  exit 2
}
# Installation may start the local MTA: require independent policy and DNS gates.
# These are explicit operator attestations after verified MAIL-00 evidence.
[[ "${MAIL_HOST_POLICY_APPROVED:-no}" == "yes" ]] || {
  echo "BLOCKED: written hosting-provider mail permission not confirmed"
  exit 2
}
[[ "${MAIL_DNS_AND_PTR_VERIFIED:-no}" == "yes" ]] || {
  echo "BLOCKED: forward/reverse DNS, SPF and matching public DKIM not confirmed"
  exit 2
}
[[ -f /etc/os-release ]] || exit 2
. /etc/os-release
[[ "$ID" == "ubuntu" && "$VERSION_ID" == "24.04" ]] || {
  echo "BLOCKED: audited for Ubuntu 24.04 only"
  exit 2
}
DOMAIN="kmjtechno.com"
HOST="mail.kmjtechno.com"
SELECTOR="kmj2026"
KEYDIR="/etc/opendkim/keys/$DOMAIN"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/kmj-mail/bootstrap-$STAMP"
mkdir -p "$BACKUP"
chmod 0700 "$BACKUP"

# Preserve original configs before any package/configuration mutation.
for path in /etc/postfix/main.cf /etc/opendkim.conf; do
  if [[ -f "$path" ]]; then
    cp -a -- "$path" "$BACKUP/$(basename "$(dirname "$path")")-$(basename "$path")"
  fi
done
if [[ -f /etc/opendkim.conf ]] && grep -Eq '^[[:space:]]*(KeyTable|SigningTable|MultipleSignatures)[[:space:]]' /etc/opendkim.conf; then
  echo "BLOCKED: existing multi-key OpenDKIM configuration requires manual preservation"
  exit 3
fi

# Preseed restricted mode before Postfix package's first service startup.
echo "postfix postfix/mailname string $HOST" | debconf-set-selections
echo "postfix postfix/main_mailer_type select Local only" | debconf-set-selections
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postfix opendkim opendkim-tools dnsutils
systemctl stop postfix 2>/dev/null || true

install -d -o opendkim -g opendkim -m 0700 "$KEYDIR"
if [[ ! -f "$KEYDIR/$SELECTOR.private" ]]; then
  opendkim-genkey -D "$KEYDIR" -d "$DOMAIN" -s "$SELECTOR" -b 2048
fi
chown opendkim:opendkim "$KEYDIR/$SELECTOR.private" "$KEYDIR/$SELECTOR.txt"
chmod 0600 "$KEYDIR/$SELECTOR.private"
chmod 0644 "$KEYDIR/$SELECTOR.txt"

cat > /etc/opendkim.conf <<EOF
Syslog yes
UMask 007
Mode s
Canonicalization relaxed/relaxed
OversignHeaders From
Domain $DOMAIN
Selector $SELECTOR
KeyFile $KEYDIR/$SELECTOR.private
Socket inet:8891@127.0.0.1
UserID opendkim:opendkim
InternalHosts 127.0.0.1
EOF
chmod 0644 /etc/opendkim.conf

postconf -e "myhostname = $HOST"
postconf -e "mydomain = $DOMAIN"
postconf -e "myorigin = $DOMAIN"
postconf -e 'mydestination = localhost'
postconf -e 'inet_interfaces = loopback-only'
postconf -e 'inet_protocols = ipv4'
postconf -e 'mynetworks = 127.0.0.0/8'
postconf -e 'relayhost ='
postconf -e 'smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination'
postconf -e 'smtpd_recipient_restrictions = reject_unauth_destination'
postconf -e 'smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'milter_protocol = 6'
postconf -e 'milter_default_action = tempfail'
postconf -e 'smtp_tls_security_level = may'
postconf -e 'smtp_helo_name = $myhostname'
postconf -e 'smtpd_client_message_rate_limit = 60'
postconf -e 'anvil_rate_time_unit = 3600s'
postconf -e 'message_size_limit = 10485760'
postconf -e 'maximal_queue_lifetime = 2d'
postconf -e 'bounce_queue_lifetime = 2d'
postfix check
systemctl enable --now opendkim
systemctl enable --now postfix
systemctl restart opendkim postfix

# Never change the production app mailer automatically.
echo "POSTFIX_CONFIG=INSTALLED"
echo "POSTFIX_ACTIVE=$(systemctl is-active postfix || true)"
echo "OPENDKIM_ACTIVE=$(systemctl is-active opendkim || true)"
if ss -ltn | awk '$4 ~ /:25$/ {print $4}' | grep -Eq '^127\.0\.0\.1:25$'; then
  echo "SMTP_LOOPBACK=PASS"
else
  echo "SMTP_LOOPBACK=CHECK_REQUIRED"
fi
if ss -ltn | awk '$4 ~ /:25$/ {print $4}' | grep -Eq '^(0\.0\.0\.0:25|\[::\]:25|\*:25)$'; then
  echo "SMTP_PUBLIC_BIND=FAIL"
  systemctl stop postfix
  exit 3
fi
echo "DKIM_PUBLIC_DNS_RECORD_BEGIN"
cat "$KEYDIR/$SELECTOR.txt"
echo "DKIM_PUBLIC_DNS_RECORD_END"
echo "LARAVEL_MAILER=UNCHANGED"
echo "DNS_AND_PTR=REQUIRE_SEPARATE_VERIFICATION"
echo "BACKUP=$BACKUP"
