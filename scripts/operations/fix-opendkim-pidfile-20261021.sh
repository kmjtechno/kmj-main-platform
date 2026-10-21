#!/usr/bin/env bash
# KMJ TECHNO operator-only OpenDKIM PID file alignment.
# Do NOT start services, send emails, change DNS/MX, Laravel or Postfix routing.
set -Eeuo pipefail
umask 077

CONFIG=/etc/opendkim.conf
BACKUP=/etc/opendkim.conf.kmj-before-pidfile-20261021.bak
PID_PATH=/run/opendkim/opendkim.pid

fail() { printf 'DKIM_PID_FIX=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
[[ "${1:-}" == "--apply" && "$#" -eq 1 ]] || fail EXACT_APPLY_ARGUMENT_REQUIRED
[[ "$(id -u)" -eq 0 ]] || fail ROOT_REQUIRED
[[ "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
[[ -t 0 && -t 1 ]] || fail OWNER_TTY_REQUIRED
for command_name in systemctl opendkim postconf postfix grep stat cp chmod ss awk; do
  command -v "$command_name" >/dev/null 2>&1 || fail "TOOL_MISSING_$command_name"
done

[[ -f "$CONFIG" && ! -L "$CONFIG" ]] || fail CONFIG_NOT_REGULAR_FILE
[[ ! -e "$BACKUP" && ! -L "$BACKUP" ]] || fail BACKUP_EXISTS_REVIEW_BEFORE_RETRY
[[ -d /run/opendkim && ! -L /run/opendkim ]] || fail RUNTIME_DIRECTORY_UNSAFE
[[ "$(stat -c '%U:%G' /run/opendkim)" == opendkim:opendkim ]] || fail RUNTIME_DIRECTORY_OWNER_UNEXPECTED
[[ "$(systemctl show --value -p Type opendkim.service)" == forking ]] || fail SYSTEMD_NOT_FORKING
[[ "$(systemctl show --value -p PIDFile opendkim.service)" == "$PID_PATH" ]] || fail SYSTEMD_PIDFILE_UNEXPECTED
[[ ! -e "$PID_PATH" && ! -L "$PID_PATH" ]] || fail PIDFILE_ALREADY_PRESENT
if grep -Eiq '^[[:space:]]*PidFile[[:space:]]+' "$CONFIG"; then
  fail EXISTING_PIDFILE_DIRECTIVE
fi
grep -Eq '^UserID[[:space:]]+opendkim[[:space:]]*$' "$CONFIG" || fail USER_ID_UNEXPECTED
grep -Eq '^Socket[[:space:]]+inet:8891@127[.]0[.]0[.]1[[:space:]]*$' "$CONFIG" || fail SIGNING_SOCKET_UNEXPECTED
grep -Eq '^KeyFile[[:space:]]+/etc/opendkim/kmj-active-reuse/kmj2026[.]private[[:space:]]*$' "$CONFIG" || fail KEY_FILE_UNEXPECTED
[[ "$(postconf -h inet_interfaces)" == loopback-only ]] || fail POSTFIX_BOUND_PUBLIC
[[ "$(postconf -h default_transport)" == smtp ]] || fail ROUTING_NOT_READY
[[ "$(postconf -h relay_transport)" == smtp ]] || fail RELAY_ROUTING_NOT_READY
[[ "$(postconf -h milter_default_action)" == tempfail ]] || fail DKIM_NOT_FAIL_CLOSED
for service in postfix opendkim; do
  [[ "$(systemctl is-active "$service" 2>/dev/null || true)" == inactive ]] || fail "SERVICE_NOT_INACTIVE_$service"
  [[ "$(systemctl is-enabled "$service" 2>/dev/null || true)" == disabled ]] || fail "SERVICE_NOT_DISABLED_$service"
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail MAIL_LISTENER_ALREADY_PRESENT
fi
opendkim -n -x "$CONFIG" >/dev/null 2>&1 || fail OPENDKIM_PRECHECK_FAILED

echo 'DKIM_PID_PREFLIGHT=PASS'
echo 'SYSTEMD_TYPE=forking'
echo "SYSTEMD_EXPECTED_PIDFILE=$PID_PATH"
echo 'OPENDKIM_CONFIG_PIDFILE=MISSING'
echo 'SERVICES=STOPPED_DISABLED'
echo 'NO_EMAIL_SENT=YES'
printf 'Type FIX DKIM PIDFILE to append one config directive, without starting services: '
IFS= read -r confirmation
[[ "$confirmation" == 'FIX DKIM PIDFILE' ]] || fail OWNER_NOT_CONFIRMED

changed=0
original_mode=$(stat -c %a "$CONFIG")
cleanup() {
  local rc=$?
  if [[ "$rc" -ne 0 && "$changed" -eq 1 ]]; then
    if cp -p -- "$BACKUP" "$CONFIG" && chmod "$original_mode" "$CONFIG"; then
      echo 'OPENDKIM_CONFIG_ROLLBACK=PASS'
    else
      echo 'OPENDKIM_CONFIG_ROLLBACK=FAILED'
    fi
  fi
  if [[ "$rc" -ne 0 ]]; then
    printf 'DKIM_PID_FIX=INCOMPLETE_EXIT_%s\n' "$rc"
  fi
}
trap cleanup EXIT

cp -p -- "$CONFIG" "$BACKUP" || fail BACKUP_FAILED
chmod 0600 "$BACKUP" || fail BACKUP_PERMISSIONS_FAILED
changed=1
printf '\nPidFile                 %s\n' "$PID_PATH" >> "$CONFIG"
[[ "$(grep -Eic '^[[:space:]]*PidFile[[:space:]]+' "$CONFIG")" == 1 ]] || fail PIDFILE_DIRECTIVE_COUNT
grep -Eq '^PidFile[[:space:]]+/run/opendkim/opendkim[.]pid[[:space:]]*$' "$CONFIG" || fail PIDFILE_DIRECTIVE_VALUE
opendkim -n -x "$CONFIG" >/dev/null 2>&1 || fail OPENDKIM_POSTCHECK_FAILED
[[ "$(systemctl show --value -p PIDFile opendkim.service)" == "$PID_PATH" ]] || fail SYSTEMD_PIDFILE_CHANGED
for service in postfix opendkim; do
  [[ "$(systemctl is-active "$service" 2>/dev/null || true)" == inactive ]] || fail SERVICE_STARTED_UNEXPECTEDLY
  [[ "$(systemctl is-enabled "$service" 2>/dev/null || true)" == disabled ]] || fail SERVICE_ENABLED_UNEXPECTEDLY
done
if ss -ltnH | awk '{print $4}' | grep -Eq '(^|:)(25|465|587|8891)$'; then
  fail NEW_MAIL_LISTENER
fi
echo 'DKIM_PID_FIX=PASS'
echo "PIDFILE_CONFIG=$PID_PATH"
echo 'OPENDKIM_SYNTAX=PASS'
echo 'MAIL_SERVICES=STOPPED_DISABLED'
echo 'POSTFIX_AND_DNS=UNCHANGED'
echo 'NO_EMAIL_SENT=YES'
echo 'NEXT=RETRY_PINNED_GUARDED_ACTIVATION'
