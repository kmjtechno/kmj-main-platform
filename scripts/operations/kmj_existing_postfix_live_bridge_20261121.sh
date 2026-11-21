#!/usr/bin/env bash
# KMJ Main Platform: reuse ACTIVE KMJ-elite Postfix/OpenDKIM; never reinstall or edit it.
# Read-only by default. Apply ONLY with the actual exact live release and explicit owner token.
set -Eeuo pipefail
umask 077
fail() { printf 'KMJ_MAIL_BRIDGE=BLOCKED\nREASON=%s\n' "$1"; exit 2; }
MODE=${1:-}
EXPECTED=${2:-}
CONFIRM=${3:-}
[[ "$#" == 2 || "$#" == 3 ]] || fail ARGUMENTS
[[ "$MODE" == --inspect || "$MODE" == --apply ]] || fail MODE
[[ "$EXPECTED" =~ ^platform-[a-f0-9]{12}$ ]] || fail EXPECTED_RELEASE
[[ "$(hostname -s | tr '[:upper:]' '[:lower:]')" == kmj-elite ]] || fail HOST
[[ "$MODE" != --apply || ( "$(id -u)" == 0 && "$CONFIRM" == CONNECT_EXISTING_POSTFIX ) ]] || fail OWNER_CONFIRMATION
for cmd in readlink stat systemctl postconf ss python3 runuser php8.4 mktemp cp mv chown chmod; do
 command -v "$cmd" >/dev/null || fail "MISSING_TOOL_${cmd}"
done
RELEASE=/home/kmjprod/releases/$EXPECTED
CURRENT=/home/kmjprod/current
[[ -L "$CURRENT" && -d "$RELEASE" && -f "$RELEASE/apps/platform/artisan" ]] || fail ACTIVE_RELEASE_PATH
[[ "$(readlink -f -- "$CURRENT")" == "$(readlink -f -- "$RELEASE")" ]] || fail PRODUCTION_RELEASE_DRIFT
APP=$RELEASE/apps/platform
ENV=$APP/.env
CACHE=$APP/bootstrap/cache/config.php
[[ -f "$ENV" && ! -L "$ENV" && "$(stat -c %h "$ENV")" == 1 ]] || fail ENV_FILE_TRUST
[[ "$(stat -c %a "$ENV")" =~ ^(600|640)$ ]] || fail ENV_MODE
[[ ! -e "$CACHE" || ( -f "$CACHE" && ! -L "$CACHE" ) ]] || fail CACHE_TRUST
for svc in postfix opendkim php8.4-fpm; do
 [[ "$(systemctl is-active "$svc" || :)" == active ]] || fail "SERVICE_${svc}_INACTIVE"
done
for pair in 'inet_interfaces=loopback-only' 'inet_protocols=ipv4' 'myhostname=mail.kmjtechno.com' 'myorigin=kmjtechno.com' 'relayhost=' 'smtpd_milters=inet:127.0.0.1:8891' 'milter_default_action=tempfail'; do
 key=${pair%%=*}; value=${pair#*=}
 [[ "$(postconf -h "$key")" == "$value" ]] || fail "POSTFIX_${key}_DRIFT"
done
[[ "$(postconf -h smtpd_relay_restrictions)" == *reject_unauth_destination* ]] || fail RELAY_GUARD
# No public listener or alternate SMTP ports. Existing Postfix and DKIM remain untouched.
python3 -I -B - <<'PY' || fail SMTP_LOOPBACK_LISTENERS
import subprocess, socket, sys
r=subprocess.run(['/usr/bin/ss','-ltnH'],capture_output=True,text=True,timeout=8)
if r.returncode: sys.exit(2)
ports={}
for line in r.stdout.splitlines():
    bits=line.split()
    if len(bits)<4: continue
    try: host,port=bits[3].rsplit(':',1);port=int(port)
    except ValueError: continue
    if port in (25,465,587,8891): ports.setdefault(port,[]).append(host)
if ports!={25:['127.0.0.1'],8891:['127.0.0.1']}: sys.exit(3)
with socket.create_connection(('127.0.0.1',25),timeout=3) as s:
    s.settimeout(3)
    if not s.recv(128).startswith(b'220 '):sys.exit(4)
    s.sendall(b'QUIT\r\n')
PY
# Read only the established zero-secret diagnostic; it can return exit 1 for log-only.
set +e
DOCTOR=$(cd "$APP" && runuser -u kmjprod -- php8.4 artisan kmj:mail:doctor --json 2>/dev/null)
DOC_RC=$?
set -e
[[ "$DOC_RC" == 0 || "$DOC_RC" == 1 ]] || fail LIVE_MAIL_DOCTOR_UNAVAILABLE
printf '%s' "$DOCTOR" | python3 -I -B -c 'import json,sys; d=json.load(sys.stdin); assert d.get("environment")=="production"; print("LIVE_MAIL_TRANSPORT="+str(d.get("transport") or "missing")); print("LIVE_MAIL_ATTEMPT_READY="+("YES" if d.get("can_attempt_external_delivery") else "NO"))' || fail DOCTOR_OUTPUT
printf 'EXISTING_POSTFIX=ACTIVE_LOOPBACK\nEXISTING_OPENDKIM=ACTIVE\nCURRENT_RELEASE=%s\nMAIL_SENT=NO\n' "$EXPECTED"
if [[ "$MODE" == --inspect ]]; then echo 'KMJ_MAIL_BRIDGE=READ_ONLY_PASS'; exit 0; fi
# Never write to a stale/moved pointer or change an unrelated environment.
[[ "$(readlink -f -- "$CURRENT")" == "$(readlink -f -- "$RELEASE")" ]] || fail PRODUCTION_RELEASE_CHANGED
BACKUP_ROOT=/var/lib/kmj-main-platform-mail-recovery
[[ ! -L "$BACKUP_ROOT" ]] || fail BACKUP_PARENT_SYMLINK
install -d -m 0700 "$BACKUP_ROOT"
[[ "$(stat -c %u:%a "$BACKUP_ROOT")" == 0:700 ]] || fail BACKUP_PARENT_MODE
BKP=$(mktemp -d "$BACKUP_ROOT/mail-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
cp -a -- "$ENV" "$BKP/env.before"
if [[ -f "$CACHE" ]]; then cp -a -- "$CACHE" "$BKP/cache.before"; else touch "$BKP/cache.absent"; fi
CHANGED=0
rollback() {
 rc=$?
 if [[ "$rc" != 0 && "$CHANGED" == 1 ]]; then
   TMP=$(mktemp "$APP/.kmj-mail-rollback-XXXXXX")
   cp -a -- "$BKP/env.before" "$TMP" && mv -fT -- "$TMP" "$ENV" || echo 'ROLLBACK_ENV=FAILED'
   if [[ -f "$BKP/cache.before" ]]; then
     TMP=$(mktemp "$APP/bootstrap/cache/.kmj-mail-cache-XXXXXX")
     cp -a -- "$BKP/cache.before" "$TMP" && mv -fT -- "$TMP" "$CACHE" || echo 'ROLLBACK_CACHE=FAILED'
   elif [[ -f "$CACHE" && ! -L "$CACHE" ]]; then rm -f -- "$CACHE"; fi
   systemctl reload php8.4-fpm >/dev/null 2>&1 || :
   echo 'ROLLBACK=ATTEMPTED_VERIFY_REQUIRED'
 fi
}
trap rollback EXIT
TMP=$(mktemp "$APP/.kmj-mail-apply-XXXXXX")
# Preserve unrelated settings byte-for-byte, reject complex/duplicate dotenv keys.
python3 -I -B - "$ENV" "$TMP" <<'PY' || fail ENV_PARSE_UNSAFE
import sys,re
src,dst=sys.argv[1:]
raw=open(src,'rb').read()
if len(raw)>65536 or b'\r' in raw or b'\x00' in raw:sys.exit(2)
try: lines=raw.decode('utf8').splitlines(keepends=True)
except UnicodeError: sys.exit(3)
keys={}; parsed=[]
for line in lines:
    s=line.rstrip('\n')
    if not s.strip() or s.lstrip().startswith('#'):parsed.append((None,line));continue
    m=re.fullmatch(r'([A-Z][A-Z0-9_]*)=(.*)',s)
    if not m or m[1] in keys:sys.exit(4)
    keys[m[1]]=m[2];parsed.append((m[1],line))
fromaddr=keys.get('MAIL_FROM_ADDRESS','').strip().strip('"\'').lower() or 'info@kmjtechno.com'
if not re.fullmatch(r'[a-z0-9._%+\-]{1,64}@kmjtechno\.com',fromaddr):sys.exit(5)
values={'MAIL_MAILER':'smtp','MAIL_HOST':'127.0.0.1','MAIL_PORT':'25','MAIL_SCHEME':'smtp','MAIL_URL':'','MAIL_USERNAME':'','MAIL_PASSWORD':'','MAIL_EHLO_DOMAIN':'mail.kmjtechno.com','MAIL_FROM_ADDRESS':fromaddr}
if 'MAIL_FROM_NAME' not in keys: values['MAIL_FROM_NAME']='"KMJ TECHNO"'
new=''.join(f'{key}={values[key]}\n' if key in values else line for key,line in parsed)
if new and not new.endswith('\n'):new+='\n'
for k,v in values.items():
    if k not in keys:new+=f'{k}={v}\n'
open(dst,'wb').write(new.encode('utf8'))
PY
chown --reference="$ENV" "$TMP"
chmod --reference="$ENV" "$TMP"
mv -fT -- "$TMP" "$ENV"
CHANGED=1
(cd "$APP" && runuser -u kmjprod -- php8.4 artisan config:clear >/dev/null && runuser -u kmjprod -- php8.4 artisan config:cache >/dev/null) || fail CONFIG_CACHE_FAILED
set +e
AFTER=$(cd "$APP" && runuser -u kmjprod -- php8.4 artisan kmj:mail:doctor --json 2>/dev/null)
AFTER_RC=$?
set -e
[[ "$AFTER_RC" == 0 ]] || fail SMTP_DOCTOR_NOT_READY
printf '%s' "$AFTER" | python3 -I -B -c 'import json,sys; d=json.load(sys.stdin); assert d.get("environment")=="production" and d.get("transport")=="smtp" and d.get("can_attempt_external_delivery") is True' || fail SMTP_DOCTOR_NOT_READY
[[ "$(readlink -f -- "$CURRENT")" == "$(readlink -f -- "$RELEASE")" ]] || fail RELEASE_DRIFT_AFTER_CHANGE
systemctl reload php8.4-fpm >/dev/null || fail FPM_RELOAD_FAILED
[[ "$(systemctl is-active php8.4-fpm)" == active ]] || fail FPM_NOT_ACTIVE
CHANGED=0
printf 'KMJ_MAIL_BRIDGE=CONFIGURED\nLARAVEL_EXTERNAL_ATTEMPT=READY_NOT_INBOX_PROOF\nBACKUP_CREATED=YES\nMAIL_SENT=NO\nPOSTFIX_DKIM_DNS=UNCHANGED\n'
