#!/usr/bin/env bash
# Owner-operated, single-purpose Postfix outbound transport correction.
# Never starts mail services, sends mail, edits MX/DNS, or modifies Laravel.
set -Eeuo pipefail
umask 077

HOST=KMJ-elite
STAGE_STAMP=/etc/kmj-mail-selfhost-reuse-staged-20261021
MAINCF=/etc/postfix/main.cf
BACKUP=/etc/postfix/main.cf.kmj-outbound-before-20261021.bak
KEY_ORIG=/etc/opendkim/keys/kmjtechno.com/kmj2026.private
KEY_ACTIVE=/etc/opendkim/kmj-active-reuse/kmj2026.private
CHANGED=0
ORIGINAL_MODE=''

fail() { printf 'ROUTING_FIX=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
[[ "${1:-}" == "--apply" && "$#" -eq 1 ]] || fail EXPECTED_APPLY_ARGUMENT
[[ "$(id -u)" -eq 0 ]] || fail ROOT_REQUIRED
[[ "$(hostname -s)" == "$HOST" ]] || fail WRONG_HOST
[[ -t 0 && -t 1 ]] || fail INTERACTIVE_TTY_REQUIRED

for cmd in postconf postfix postqueue systemctl ss cmp cp stat chmod awk grep wc; do
  command -v "$cmd" >/dev/null 2>&1 || fail "TOOL_MISSING_$cmd"
done

[[ -f "$STAGE_STAMP" && ! -L "$STAGE_STAMP" ]] || fail REUSE_STAGE_STAMP_MISSING
grep -Fqx 'ORIGINAL_KMJ2026_KEY_PRESERVED=YES' "$STAGE_STAMP" || fail STAGE_STAMP_MISMATCH
[[ -f "$MAINCF" && ! -L "$MAINCF" ]] || fail POSTFIX_CONFIG_UNSAFE
[[ ! -e "$BACKUP" && ! -L "$BACKUP" ]] || fail BACKUP_ALREADY_EXISTS
[[ -f /etc/opendkim.conf && ! -L /etc/opendkim.conf ]] || fail OPENDKIM_CONFIG_UNSAFE
for p in "$KEY_ORIG" "$KEY_ACTIVE"; do
  [[ -f "$p" && ! -L "$p" ]] || fail KEY_UNSAFE_OR_MISSING
done
cmp -s "$KEY_ORIG" "$KEY_ACTIVE" || fail ACTIVE_DKIM_KEY_NOT_IDENTICAL
[[ "$(stat -c %a "$KEY_ORIG")" == 600 ]] || fail ORIGINAL_PRIVATE_KEY_MODE_UNSAFE
[[ "$(stat -c %a "$KEY_ACTIVE")" == 400 ]] || fail ACTIVE_PRIVATE_KEY_MODE_UNSAFE
grep -Eq '^KeyFile[[:space:]]+/etc/opendkim/kmj-active-reuse/kmj2026[.]private[[:space:]]*$' /etc/opendkim.conf \
  || fail OPENDKIM_KEYFILE_MISMATCH

for svc in postfix opendkim; do
  active=$(systemctl is-active "$svc" 2>/dev/null || true)
  enabled=$(systemctl is-enabled "$svc" 2>/dev/null || true)
  [[ "$active" == inactive && "$enabled" == disabled ]] || fail "SERVICE_NOT_STOPPED_DISABLED_$svc"
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail UNEXPECTED_MAIL_LISTENER
fi
[[ "$(postconf -h myhostname)" == 'mail.kmjtechno.com' ]] || fail HOSTNAME_MISMATCH
[[ "$(postconf -h myorigin)" == 'kmjtechno.com' ]] || fail ORIGIN_MISMATCH
[[ "$(postconf -h mydestination)" == localhost ]] || fail LOCAL_DESTINATION_MISMATCH
[[ "$(postconf -h inet_interfaces)" == loopback-only ]] || fail PUBLIC_LISTENER_RISK
[[ -z "$(postconf -h relayhost)" ]] || fail EXTERNAL_RELAY_UNEXPECTED
[[ "$(postconf -h default_transport)" == error ]] || fail DEFAULT_TRANSPORT_UNEXPECTED
[[ "$(postconf -h relay_transport)" == error ]] || fail RELAY_TRANSPORT_UNEXPECTED
[[ "$(postconf -h smtpd_milters)" == 'inet:127.0.0.1:8891' ]] || fail DKIM_MILTER_MISMATCH
[[ "$(postconf -h non_smtpd_milters)" == 'inet:127.0.0.1:8891' ]] || fail DKIM_LOCAL_MILTER_MISMATCH
[[ "$(postconf -h milter_default_action)" == tempfail ]] || fail DKIM_FAIL_CLOSED_MISMATCH
[[ "$(postconf -h smtpd_relay_restrictions)" == *reject_unauth_destination* ]] || fail RELAY_RESTRICTIONS_MISSING
[[ "$(postqueue -j | wc -l)" -eq 0 ]] || fail QUEUED_MAIL_NOT_EMPTY
postfix check >/dev/null || fail POSTFIX_PRECHECK_FAILED

echo 'MAIL_ROUTING_PREFLIGHT=PASS'
echo 'EXISTING_DKIM_KEY=UNCHANGED'
echo 'DEFAULT_TRANSPORT=error'
echo 'RELAY_TRANSPORT=error'
echo 'QUEUED_MAIL=0'
echo 'SERVICES=STOPPED_DISABLED'
echo 'NO_MAIL_WILL_BE_SENT=YES'
printf 'Type FIX OUTBOUND TRANSPORT to stage SMTP routing without starting services: '
IFS= read -r answer
[[ "$answer" == 'FIX OUTBOUND TRANSPORT' ]] || fail OWNER_NOT_CONFIRMED

# Roll back only the transport edit on failure, using a protected backup.
# A pre-existing backup path makes a repeated run block before modification.
rollback() {
  local rc=$?
  if [[ $rc -ne 0 && $CHANGED -eq 1 && -f "$BACKUP" && ! -L "$BACKUP" ]]; then
    if cp -p -- "$BACKUP" "$MAINCF"; then
      chmod "$ORIGINAL_MODE" "$MAINCF" || true
      echo 'POSTFIX_MAINCF_ROLLBACK=ATTEMPTED'
    else
      echo 'POSTFIX_MAINCF_ROLLBACK=FAILED'
    fi
  fi
  if [[ $rc -ne 0 ]]; then
    printf 'ROUTING_FIX=INCOMPLETE_EXIT_%s\n' "$rc"
  fi
}
trap rollback EXIT

ORIGINAL_MODE=$(stat -c %a "$MAINCF")
cp -p -- "$MAINCF" "$BACKUP" || fail BACKUP_COPY_FAILED
chmod 0600 "$BACKUP" || fail BACKUP_MODE_FAILED
# Explicitly only update these two parameters; preserve all other main.cf.
CHANGED=1
postconf -e 'default_transport = smtp' 'relay_transport = smtp'
[[ "$(postconf -h default_transport)" == smtp ]] || fail DEFAULT_TRANSPORT_NOT_SMTP
[[ "$(postconf -h relay_transport)" == smtp ]] || fail RELAY_TRANSPORT_NOT_SMTP
[[ "$(postconf -h inet_interfaces)" == loopback-only ]] || fail BIND_CHANGED
[[ "$(postconf -h mydestination)" == localhost ]] || fail DESTINATION_CHANGED
[[ -z "$(postconf -h relayhost)" ]] || fail RELAYHOST_CHANGED
[[ "$(postconf -h milter_default_action)" == tempfail ]] || fail MILTER_SAFETY_CHANGED
[[ "$(postqueue -j | wc -l)" -eq 0 ]] || fail QUEUE_CHANGED
postfix check >/dev/null || fail POSTFIX_POSTCHECK_FAILED
for svc in postfix opendkim; do
  [[ "$(systemctl is-active "$svc" 2>/dev/null || true)" == inactive ]] || fail MAIL_SERVICE_STARTED
  [[ "$(systemctl is-enabled "$svc" 2>/dev/null || true)" == disabled ]] || fail MAIL_SERVICE_ENABLED
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail UNEXPECTED_MAIL_LISTENER_POSTCHANGE
fi

echo 'ROUTING_FIX=PASS'
echo 'DEFAULT_TRANSPORT=smtp'
echo 'RELAY_TRANSPORT=smtp'
echo 'POSTFIX_CHECK=PASS'
echo 'SERVICES=STOPPED_DISABLED'
echo 'QUEUE=0'
echo 'MX_AND_LARAVEL=UNCHANGED'
echo 'NO_EMAIL_SENT=YES'
echo 'NEXT=EXPLICIT_TEST_ACTIVATION_ONLY'
