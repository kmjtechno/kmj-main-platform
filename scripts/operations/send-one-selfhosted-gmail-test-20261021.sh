#!/usr/bin/env bash
# KMJ TECHNO — ONE explicitly authorized Gmail test via local Postfix.
# The successful local submission DOES NOT prove Gmail accepted the message.
# This script changes no daemon settings, MX/DNS, Laravel, payments or firewall.
set -Eeuo pipefail
umask 077

ORIGIN=info@kmjtechno.com
RECIPIENT=kmjtechno.net@gmail.com
ONCE=/etc/kmj-mail-single-test-20261021.once
STAGE=/etc/kmj-mail-selfhost-reuse-staged-20261021
KEY=/etc/opendkim/keys/kmjtechno.com/kmj2026.private
COPY=/etc/opendkim/kmj-active-reuse/kmj2026.private
BIND_PORTS='25,8891'

fail() { printf 'SMTP_TEST=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
[[ "${1:-}" == '--send-one' && "$#" -eq 1 ]] || fail ARGUMENT_MUST_BE_SEND_ONE
[[ "$(id -u)" -eq 0 ]] || fail ROOT_REQUIRED
[[ "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
[[ -t 0 && -t 1 ]] || fail OWNER_TTY_REQUIRED
for tool in postconf postfix postqueue opendkim systemctl ss python3 cmp stat grep date; do
  command -v "$tool" >/dev/null 2>&1 || fail "MISSING_TOOL_$tool"
done
[[ -x /usr/sbin/sendmail ]] || fail SENDMAIL_MISSING
[[ -f "$STAGE" && ! -L "$STAGE" ]] || fail STAGE_STAMP_MISSING
grep -Fqx ORIGINAL_KMJ2026_KEY_PRESERVED=YES "$STAGE" || fail STAGE_STAMP_MISMATCH
[[ ! -e "$ONCE" && ! -L "$ONCE" ]] || fail TEST_ALREADY_ATTEMPTED_DO_NOT_REPEAT
for p in /etc/postfix/main.cf /etc/opendkim.conf "$KEY" "$COPY"; do
  [[ -f "$p" && ! -L "$p" ]] || fail UNTRUSTED_CONFIG_OR_KEY
done
cmp -s "$KEY" "$COPY" || fail PRIVATE_KEY_NOT_IDENTICAL
[[ "$(stat -c %a "$KEY")" == 600 ]] || fail ORIGINAL_KEY_PERMISSIONS
[[ "$(stat -c %a "$COPY")" == 400 ]] || fail COPY_KEY_PERMISSIONS
[[ "$(stat -c %U "$COPY")" == opendkim ]] || fail COPY_KEY_OWNER
for svc in postfix opendkim; do
  [[ "$(systemctl is-active "$svc" 2>/dev/null || true)" == active ]] || fail "SERVICE_INACTIVE_$svc"
  [[ "$(systemctl is-enabled "$svc" 2>/dev/null || true)" == disabled ]] || fail "SERVICE_AUTOSTART_UNEXPECTED_$svc"
done
check_setting() {
  local value
  value=$(postconf -h "$1") || fail POSTCONF_ERROR
  [[ "$value" == "$2" ]] || fail "POSTCONF_UNEXPECTED_$1"
}
check_setting myhostname mail.kmjtechno.com
check_setting myorigin kmjtechno.com
check_setting mydestination localhost
check_setting inet_interfaces loopback-only
check_setting inet_protocols ipv4
check_setting default_transport smtp
check_setting relay_transport smtp
check_setting relayhost ''
check_setting smtpd_milters inet:127.0.0.1:8891
check_setting non_smtpd_milters inet:127.0.0.1:8891
check_setting milter_default_action tempfail
[[ "$(postconf -h smtpd_relay_restrictions)" == *reject_unauth_destination* ]] || fail SMTP_RELAY_UNPROTECTED
grep -Eq '^PidFile[[:space:]]+/run/opendkim/opendkim[.]pid[[:space:]]*$' /etc/opendkim.conf || fail DKIM_PIDFILE_MISSING
grep -Eq '^KeyFile[[:space:]]+/etc/opendkim/kmj-active-reuse/kmj2026[.]private[[:space:]]*$' /etc/opendkim.conf || fail DKIM_KEYFILE_UNEXPECTED
opendkim -n -x /etc/opendkim.conf >/dev/null 2>&1 || fail DKIM_CONFIG_INVALID
postfix check >/dev/null || fail POSTFIX_CONFIG_INVALID

# Exactly two loopback-only mail ports. This does not send a message.
python3 - <<'PY'
import subprocess, sys
raw = subprocess.run(["ss", "-ltnH"], text=True, capture_output=True, check=True, timeout=8).stdout
ports = {}
for line in raw.splitlines():
    cells = line.split()
    if len(cells) < 4: continue
    try:
        addr, port = cells[3].rsplit(':', 1)
        port = int(port)
    except ValueError:
        continue
    if port in (25, 465, 587, 8891):
        ports.setdefault(port, []).append(addr)
if ports != {25: ["127.0.0.1"], 8891: ["127.0.0.1"]}:
    print("LOCAL_LISTENER_SECURITY=FAIL")
    sys.exit(22)
print("LOCAL_LISTENER_SECURITY=PASS")
PY
[[ "$(postqueue -j 2>/dev/null | wc -l)" -eq 0 ]] || fail PREEXISTING_MAIL_QUEUE_NOT_EMPTY

token=$(python3 -c 'import secrets; print(secrets.token_hex(6))')
subject="KMJ TECHNO selfhosted mail QA $token"
msgid="<kmj-selfhost-$token@kmjtechno.com>"
echo SMTP_TEST_PREFLIGHT=PASS
echo "TEST_RECIPIENT=$RECIPIENT"
echo "TEST_FROM=$ORIGIN"
echo "TEST_SUBJECT=$subject"
echo 'QUEUE_BEFORE_SEND=0'
echo 'MX_AND_LARAVEL=UNCHANGED'
echo 'ONE_EMAIL_ONLY=YES'
echo 'GMAIL_DELIVERY=NOT_YET_VERIFIED'
printf 'To authorize ONE email, type SEND ONE KMJ TEST: '
IFS= read -r answer
[[ "$answer" == 'SEND ONE KMJ TEST' ]] || fail OWNER_NOT_CONFIRMED

# Create one-time receipt before send, atomically, to prevent duplicates after
# connection loss or delayed queue processing. Never auto-delete the marker.
if ( set -C; printf 'DATE=%s\nRECIPIENT=%s\nSUBJECT=%s\n' \
  "$(date -u +%FT%TZ)" "$RECIPIENT" "$subject" > "$ONCE" ); then
  chmod 0600 "$ONCE"
else
  fail COULD_NOT_CREATE_ONE_TIME_RECEIPT
fi

if /usr/sbin/sendmail -oi -f "$ORIGIN" -t <<MAIL
From: KMJ TECHNO Mail QA <info@kmjtechno.com>
To: $RECIPIENT
Subject: $subject
Date: $(date -R)
Message-ID: $msgid
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
X-KMJ-Mail-Test: $token

KMJ TECHNO self-hosted outbound mail test.
Expected sending host: mail.kmjtechno.com.
Expected DKIM selector: kmj2026.
Please verify SPF, DKIM and DMARC in Gmail original message headers.
This is a single authorized infrastructure test.
MAIL
then
  echo 'LOCAL_SENDMAIL_SUBMISSION=PASS'
  echo "TEST_SUBJECT=$subject"
  echo "TEST_MESSAGE_ID=$msgid"
  echo 'GMAIL_DELIVERY=UNVERIFIED'
  echo 'NEXT=CHECK_POSTFIX_QUEUE_AND_GMAIL_AUTHENTICATION_RESULTS'
else
  echo 'LOCAL_SENDMAIL_SUBMISSION=FAIL'
  echo 'ONE_TIME_RECEIPT=PRESENT_DO_NOT_AUTORETRY'
  exit 3
fi
