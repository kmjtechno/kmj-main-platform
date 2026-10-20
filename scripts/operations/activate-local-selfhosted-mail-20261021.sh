#!/usr/bin/env bash
# Owner-approved local-only activation. NEVER sends mail or changes MX/Laravel.
set -Eeuo pipefail
umask 077
fail() { printf 'LOCAL_MAIL_ACTIVATION=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
[[ "${1:-}" == --activate && "$#" -eq 1 ]] || fail EXPECTED_ACTIVATE_ARGUMENT
[[ "$(id -u)" -eq 0 ]] || fail ROOT_REQUIRED
[[ "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
[[ -t 0 && -t 1 ]] || fail OWNER_TTY_REQUIRED
for cmd in postconf postfix postqueue opendkim systemctl cmp stat ss awk grep wc python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "TOOL_MISSING_$cmd"
done

STAGE=/etc/kmj-mail-selfhost-reuse-staged-20261021
BACKUP=/etc/postfix/main.cf.kmj-outbound-before-20261021.bak
KEY=/etc/opendkim/keys/kmjtechno.com/kmj2026.private
COPY=/etc/opendkim/kmj-active-reuse/kmj2026.private

[[ -f "$STAGE" && ! -L "$STAGE" ]] || fail STAGE_STAMP_MISSING
grep -Fqx 'ORIGINAL_KMJ2026_KEY_PRESERVED=YES' "$STAGE" || fail STAGE_STAMP_UNTRUSTED
[[ -f "$BACKUP" && ! -L "$BACKUP" ]] || fail ROUTE_BACKUP_MISSING
for p in /etc/postfix/main.cf /etc/opendkim.conf "$KEY" "$COPY"; do
  [[ -f "$p" && ! -L "$p" ]] || fail CONFIG_OR_KEY_MISSING_OR_UNSAFE
done
[[ "$(stat -c %a "$KEY")" == 600 ]] || fail ORIGINAL_KEY_MODE
[[ "$(stat -c %a "$COPY")" == 400 ]] || fail ACTIVE_KEY_MODE
[[ "$(stat -c %U "$COPY")" == opendkim ]] || fail ACTIVE_KEY_OWNER
cmp -s "$KEY" "$COPY" || fail DKIM_KEY_COPY_MISMATCH

check_setting() {
  local actual
  actual=$(postconf -h "$1") || fail POSTCONF_ERROR
  [[ "$actual" == "$2" ]] || fail "UNEXPECTED_SETTING_$1"
}
check_setting myhostname mail.kmjtechno.com
check_setting mydomain kmjtechno.com
check_setting myorigin kmjtechno.com
check_setting mydestination localhost
check_setting inet_interfaces loopback-only
check_setting inet_protocols ipv4
check_setting default_transport smtp
check_setting relay_transport smtp
check_setting relayhost ''
check_setting mynetworks 127.0.0.0/8
check_setting smtpd_milters inet:127.0.0.1:8891
check_setting non_smtpd_milters inet:127.0.0.1:8891
check_setting milter_default_action tempfail
[[ "$(postconf -h smtpd_relay_restrictions)" == *reject_unauth_destination* ]] || fail RELAY_PROTECTION_MISSING
grep -Eq '^Socket[[:space:]]+inet:8891@127[.]0[.]0[.]1[[:space:]]*$' /etc/opendkim.conf || fail DKIM_SOCKET_UNSAFE
grep -Eq '^KeyFile[[:space:]]+/etc/opendkim/kmj-active-reuse/kmj2026[.]private[[:space:]]*$' /etc/opendkim.conf || fail DKIM_KEY_PATH_UNSAFE
opendkim -n -x /etc/opendkim.conf >/dev/null 2>&1 || fail OPENDKIM_SYNTAX
postfix check >/dev/null || fail POSTFIX_SYNTAX
[[ "$(postqueue -j 2>/dev/null | wc -l)" -eq 0 ]] || fail QUEUE_NOT_EMPTY
for svc in opendkim postfix; do
  [[ "$(systemctl is-active "$svc" 2>/dev/null || true)" == inactive ]] || fail "SERVICE_ALREADY_ACTIVE_$svc"
  [[ "$(systemctl is-enabled "$svc" 2>/dev/null || true)" == disabled ]] || fail "SERVICE_ENABLED_$svc"
done
[[ -z "$(ss -ltnH | awk '{print $4}' | grep -E ':(25|465|587|8891)$' || true)" ]] || fail MAIL_PORT_OCCUPIED
echo 'LOCAL_MAIL_ACTIVATION_PREFLIGHT=PASS'
echo 'NO_EMAIL_WILL_BE_SENT=YES'
echo 'POSTFIX_AND_OPENDKIM=INACTIVE_DISABLED'
printf 'Type START LOCAL MAIL to start loopback-only services: '
IFS= read -r confirmation
[[ "$confirmation" == 'START LOCAL MAIL' ]] || fail OWNER_NOT_CONFIRMED

# If any post-start check fails, immediately return both services to stopped.
cleanup() {
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    systemctl stop postfix opendkim >/dev/null 2>&1 || true
    printf 'LOCAL_MAIL_ACTIVATION=INCOMPLETE_EXIT_%s\n' "$rc"
    echo 'SERVICES_STOP_ATTEMPTED=YES'
  fi
}
trap cleanup EXIT
systemctl start opendkim || fail OPENDKIM_START
systemctl start postfix || fail POSTFIX_START
for svc in postfix opendkim; do
  [[ "$(systemctl is-active "$svc" 2>/dev/null || true)" == active ]] || fail "SERVICE_NOT_ACTIVE_$svc"
  [[ "$(systemctl is-enabled "$svc" 2>/dev/null || true)" == disabled ]] || fail "SERVICE_BECAME_ENABLED_$svc"
done

# Validate only 127.0.0.1 listeners on ports 25 and 8891; no public SMTP.
python3 - <<'PY'
import socket, subprocess, sys
r = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True, timeout=8, check=True)
listeners = {}
for line in r.stdout.splitlines():
    cols = line.split()
    if len(cols) < 4: continue
    try:
        addr, port = cols[3].rsplit(":", 1)
        port = int(port)
    except (ValueError, IndexError):
        continue
    if port in (25, 465, 587, 8891):
        listeners.setdefault(port, []).append(addr)
if listeners != {25: ["127.0.0.1"], 8891: ["127.0.0.1"]}:
    print("MAIL_SOCKET_GUARD=FAIL")
    sys.exit(20)
for port in (25, 8891):
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        if port == 25:
            sock.settimeout(5)
            if not sock.recv(256).startswith(b"220 "):
                sys.exit(21)
            sock.sendall(b"QUIT\r\n")
print("SMTP_LOOPBACK_BANNER=PASS")
print("OPENDKIM_LOOPBACK_SOCKET=PASS")
PY

[[ "$(postqueue -j 2>/dev/null | wc -l)" -eq 0 ]] || fail QUEUE_NOT_EMPTY_AFTER_START
echo 'LOCAL_MAIL_ACTIVATION=PASS'
echo 'SERVICES=ACTIVE_BUT_DISABLED'
echo 'PUBLIC_MAIL_LISTENERS=NONE'
echo 'NO_EMAIL_SENT=YES'
echo 'LARAVEL_AND_MX=UNCHANGED'
echo 'NEXT=SEPARATE_OWNER_APPROVED_TEST_MESSAGE'
