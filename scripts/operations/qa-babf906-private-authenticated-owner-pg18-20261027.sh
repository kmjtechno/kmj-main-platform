#!/usr/bin/env bash
# P0 exact babf906 locked-design owner/authenticated Chrome vs disposable PostgreSQL18; no production DB.
set -Eeuo pipefail
umask 077
export PATH=/opt/kmj-codebridge-node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
SHA=babf9060684d15b6188384386149466816140a98
REPO=/srv/kmj-codebridge-projects/kmj-main-platform
USER_NAME=kmjprod
PG_BIN=/usr/lib/postgresql/18/bin
SOURCE=/home/kmjprod/releases/platform-babf9060684d
BROWSER="$REPO/work/qa/KMJ_OWNER_CURRENT_AUTH_BROWSER_20261027.mjs"
BROWSER_SHA=84aeddbcb3bc3e40051d5077763870649f864e61b550eba1733f55d36ea4ca83
test "$(hostname)" = KMJ-elite && test "$(id -u)" -eq 0
test -d "$REPO/.git" && test -f "$BROWSER" && test ! -L "$BROWSER"
printf '%s  %s\n' "$BROWSER_SHA" "$BROWSER" | sha256sum -c -
for b in initdb pg_ctl psql createdb; do
 test -x "$PG_BIN/$b" || { echo "PG18_$b=NOT_INSTALLED"; exit 2; }
done
php -r 'exit(extension_loaded("pdo_pgsql") ? 0 : 2);' || { echo "PHP_PDO_PGSQL=NOT_INSTALLED"; exit 2; }
for c in git tar composer php node npm runuser flock python3 curl; do command -v "$c" >/dev/null || { echo "MISSING=$c"; exit 2; }; done
id "$USER_NAME" >/dev/null
echo PG18_BINARIES=PASS
echo PHP_PDO_PGSQL=PASS
exec 9>/run/lock/kmj-locked449-qa.lock
flock -n 9 || { echo ANOTHER_QA_RUNNING; exit 2; }
test -d "$SOURCE/.git" && test ! -L "$SOURCE"
test "$(readlink -f /home/kmjprod/current)" = /home/kmjprod/releases/platform-8070dad72c55 || { echo "LIVE_POINTER_MISMATCH"; exit 2; }
test ! -e "$SOURCE/apps/platform/.env" && test ! -L "$SOURCE/apps/platform/.env" || { echo "CANDIDATE_SECRET_CONFIG_PRESENT"; exit 2; }
ACTUAL="$(runuser -u "$USER_NAME" -- git -C "$SOURCE" rev-parse HEAD)"
test "$ACTUAL" = "$SHA" || { echo CANDIDATE_SHA=FAIL; exit 3; }
test -z "$(runuser -u "$USER_NAME" -- git -C "$SOURCE" status --porcelain)" || { echo CANDIDATE_DIRTY=BLOCKED; exit 3; }
WORK="$(mktemp -d /var/tmp/kmj-owner-pg18.XXXXXXXX)"
OUT="$REPO/work/qa/pg18-owner-e2e-$SHA-$(date -u +%Y%m%dT%H%M%SZ)"
cleanup() {
 local rc=$?
 trap - EXIT
 mkdir -p "$OUT"
 cp -a "$WORK/report/." "$OUT/" 2>/dev/null || true
 chown -R --reference="$REPO/work/qa" "$OUT" 2>/dev/null || true
 # Stop any ephemeral PostgreSQL process before removing its temporary PGDATA.
 if test -e "$WORK/pgdata/postmaster.pid"; then
  runuser -u "$USER_NAME" -- "$PG_BIN/pg_ctl" -D "$WORK/pgdata" -m immediate -w -t 15 stop >/dev/null 2>&1 || true
 fi
 if test -e "$WORK/pgdata/postmaster.pid"; then
  echo PG18_EPHEMERAL_CLEANUP=BLOCKED_RUNNING
  echo "QA_REPORT_DIRECTORY=$OUT"
  exit 5
 fi
 rm -rf -- "$WORK"
 echo PG18_EPHEMERAL_CLEANUP=PASS
 echo "QA_REPORT_DIRECTORY=$OUT"
 echo PRODUCTION_MUTATION=NONE
 exit "$rc"
}
trap cleanup EXIT
mkdir -p "$WORK/repo" "$WORK/report" "$WORK/home" "$WORK/composer" "$WORK/cache" "$WORK/npm" "$WORK/pgsocket"
runuser -u "$USER_NAME" -- git -C "$SOURCE" archive "$SHA" | tar -xf - -C "$WORK/repo"
APP="$WORK/repo/apps/platform"
for dir in vendor node_modules; do
 test -d "$SOURCE/apps/platform/$dir" && test ! -L "$SOURCE/apps/platform/$dir" || { echo CANDIDATE_DEPENDENCIES=MISSING; exit 2; }
 cp -a -- "$SOURCE/apps/platform/$dir" "$APP/$dir"
done
python3 - "$WORK/repo" <<'LINKCHECK'
import os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True)
for folder,dirs,files in os.walk(root,followlinks=False):
 for name in dirs+files:
  p=Path(folder)/name;s=p.lstat()
  if stat.S_ISLNK(s.st_mode):
   try: target=p.resolve(strict=True)
   except (OSError,RuntimeError):raise SystemExit('QA_DEPENDENCY_LINK=BLOCKED_DANGLING')
   if not target.is_relative_to(root):raise SystemExit('QA_DEPENDENCY_LINK=BLOCKED_ESCAPE')
  elif not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)):
   raise SystemExit('QA_DEPENDENCY_ENTRY=BLOCKED_SPECIAL')
print('QA_DEPENDENCY_LINK_ISOLATION=PASS')
LINKCHECK
echo CANDIDATE_DEPENDENCIES=REUSED_NO_INSTALL
cp -- "$BROWSER" "$APP/scripts/_kmj_owner_pg18_temporary.mjs"
printf '%s  %s\n' "$BROWSER_SHA" "$APP/scripts/_kmj_owner_pg18_temporary.mjs" | sha256sum -c -
HTTP_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
PG_PORT="$(python3 -c 'import secrets; print(20000+secrets.randbelow(30000))')"
APPKEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
cat > "$APP/.env" <<EOF
APP_NAME="KMJ Private PG18 Browser QA"
APP_ENV=testing
APP_DEBUG=false
APP_KEY=$APPKEY
APP_URL=http://127.0.0.1:$HTTP_PORT
DB_CONNECTION=pgsql
DB_HOST=$WORK/pgsocket
DB_PORT=$PG_PORT
DB_DATABASE=kmj_private_qa
DB_USERNAME=$USER_NAME
DB_SSLMODE=disable
CACHE_STORE=file
SESSION_DRIVER=file
QUEUE_CONNECTION=sync
MAIL_MAILER=array
LOG_CHANNEL=single
EOF
python3 - "$WORK" <<'PY'
import json,sys,secrets,os
folder=sys.argv[1]
data={}
for role in ('owner','customer'):
 data[role]={
  'email':'qa-'+role+'-'+secrets.token_hex(8)+'@invalid.kmj',
  'password':secrets.token_urlsafe(32),
  'displayName':'KMJ Isolated Owner' if role=='owner' else 'KMJ Isolated Customer'
 }
f=folder+'/creds.json'
with open(f,'x') as out: json.dump(data,out)
os.chmod(f,0o600)
PY
cat > "$WORK/seed.php" <<'PHP'
<?php
declare(strict_types=1);
$c=json_decode(file_get_contents($argv[1]),true,512,JSON_THROW_ON_ERROR);
$root=$argv[2];
require $root.'/vendor/autoload.php';
$app=require $root.'/bootstrap/app.php';
$app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
foreach (['owner','customer'] as $role) {
 $record=$c[$role];
 $user=\App\Models\User::query()->create(['name'=>$record['displayName'],'email'=>$record['email'],'password'=>$record['password']]);
 $fields=['email_verified_at'=>now()];
 if($role==='owner') { $fields['is_platform_owner']=true; $fields['platform_owner_granted_at']=now(); }
 $user->forceFill($fields)->save();
 if($role==='owner') {
  \Illuminate\Support\Facades\DB::table('passkeys')->insert([
    'user_id'=>$user->getKey(), 'name'=>'PG18 isolated QA passkey',
    'credential_id'=>'pg18-test-'.bin2hex(random_bytes(16)),
    'credential'=>'{}','created_at'=>now(),'updated_at'=>now()
  ]);
 }
}
echo "PRIVATE_USERS_SEEDED=2\n";
PHP
chown -R "$USER_NAME:$USER_NAME" "$WORK"
echo "SOURCE_SHA=$SHA"
echo "QA_MODE=EPHEMERAL_POSTGRESQL18_UNIX_SOCKET_ONLY"
echo "PRODUCTION_DB=NOT_CONNECTED"
echo "PRODUCTION_RELEASE=NOT_ACTIVATED"
runuser -u "$USER_NAME" -- env -i \
 PATH="$PATH" HOME="$WORK/home" COMPOSER_HOME="$WORK/composer" COMPOSER_CACHE_DIR="$WORK/cache" npm_config_cache="$WORK/npm" \
 bash -s -- "$APP" "$WORK" "$HTTP_PORT" "$PG_PORT" "$PG_BIN" "$USER_NAME" <<'RUN'
set -Eeuo pipefail
# The root wrapper owns flock FD 9. Never allow subprocesses to inherit it.
exec 9>&-
APP="$1"; WORK="$2"; HTTP_PORT="$3"; PG_PORT="$4"; PG_BIN="$5"; PGUSER="$6"
cd "$APP"
test -f vendor/autoload.php || { echo COMPOSER_DEPENDENCIES=MISSING; exit 2; }
echo COMPOSER_DEPENDENCIES=REUSED
test -d node_modules/playwright || { echo PLAYWRIGHT_DEPENDENCY=MISSING; exit 2; }
echo NPM_DEPENDENCIES=REUSED
if php artisan wayfinder:generate --with-form --no-ansi > "$WORK/report/wayfinder.log" 2>&1; then echo WAYFINDER=PASS; else echo WAYFINDER=FAIL; exit 1; fi
if npm run build > "$WORK/report/build.log" 2>&1; then echo BUILD=PASS; else echo BUILD=FAIL; exit 1; fi
if "$PG_BIN/initdb" -D "$WORK/pgdata" -U "$PGUSER" --encoding=UTF8 --auth-local=trust --auth-host=reject --no-instructions > "$WORK/report/initdb.log" 2>&1; then echo PG18_INITDB=PASS; else echo PG18_INITDB=FAIL; exit 1; fi
if "$PG_BIN/pg_ctl" -D "$WORK/pgdata" -o "-c listen_addresses='' -c unix_socket_directories=$WORK/pgsocket -c unix_socket_permissions=0700 -c port=$PG_PORT" -l "$WORK/pg.log" -w -t 30 start > "$WORK/report/pgstart.log" 2>&1; then echo PRIVATE_PG18_STARTED=PASS; else echo PRIVATE_PG18_STARTED=FAIL; exit 1; fi
trap '"$PG_BIN/pg_ctl" -D "$WORK/pgdata" -m immediate -w -t 15 stop >/dev/null 2>&1 || true' EXIT
if "$PG_BIN/createdb" -h "$WORK/pgsocket" -p "$PG_PORT" -U "$PGUSER" kmj_private_qa > "$WORK/report/createdb.log" 2>&1; then echo PRIVATE_DATABASE=PASS; else echo PRIVATE_DATABASE=FAIL; exit 1; fi
VERSION="$("$PG_BIN/psql" -X -A -t -h "$WORK/pgsocket" -p "$PG_PORT" -U "$PGUSER" -d kmj_private_qa -c 'SHOW server_version_num;')"
case "$VERSION" in 18*) echo PG18_ENGINE=PASS;; *) echo PG18_ENGINE=FAIL; exit 1;; esac
if php artisan migrate --force --no-ansi > "$WORK/report/migrate.log" 2>&1; then echo PG18_MIGRATIONS=PASS; else echo PG18_MIGRATIONS=FAIL; tail -n 12 "$WORK/report/migrate.log"; exit 1; fi
if php "$WORK/seed.php" "$WORK/creds.json" "$APP" > "$WORK/report/seed.log" 2>&1; then echo PRIVATE_OWNER_CUSTOMER=PASS; else echo PRIVATE_OWNER_CUSTOMER=FAIL; exit 1; fi
router="$APP/vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php"
test -f "$router" || { echo LARAVEL_ROUTER_SCRIPT=MISSING; exit 1; }
# Single PHP built-in server PID is reaped in EXIT trap (no orphan artisan child).
(
 cd "$APP/public"
 exec php -S "127.0.0.1:$HTTP_PORT" -t "$APP/public" "$router"
) > "$WORK/report/laravel-server.log" 2>&1 &
SERVER_PID="$!"
trap 'kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; "$PG_BIN/pg_ctl" -D "$WORK/pgdata" -m immediate -w -t 15 stop >/dev/null 2>&1 || true' EXIT
READY=NO
for n in $(seq 1 70); do
 if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
 code="$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' --max-time 2 "http://127.0.0.1:$HTTP_PORT/login" 2>/dev/null || true)"
 if [ "$code" = 200 ]; then READY=YES; break; fi
 sleep 0.3
done
test "$READY" = YES || { echo LOOPBACK_LARAVEL_START=FAIL; exit 1; }
echo LOOPBACK_LARAVEL_START=PASS
chrome=""
for candidate in /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser; do
 if [ -x "$candidate" ]; then chrome="$candidate"; break; fi
done
test -n "$chrome" || { echo CHROME_BINARY=NOT_FOUND; exit 1; }
KMJ_LOOPBACK_ORIGIN="http://127.0.0.1:$HTTP_PORT" \
 KMJ_TEST_CREDS_PATH="$WORK/creds.json" \
 KMJ_QA_REPORT_DIR="$WORK/report" KMJ_CHROMIUM_EXECUTABLE="$chrome" \
 node scripts/_kmj_owner_pg18_temporary.mjs > "$WORK/report/browser.log" 2>&1 || {
  echo AUTHENTICATED_BROWSER=FAIL
  tail -n 12 "$WORK/report/browser.log"
  exit 1
 }
tail -n 8 "$WORK/report/browser.log"
RUN
echo "EXACT_SOURCE_PG18_BROWSER=$SHA"
echo "PUBLIC_STAGING_ACCEPTANCE=NOT_RUN"
echo "REAL_OWNER_ACCEPTANCE=NOT_ATTESTED"
echo "PRODUCTION_APPROVAL=UNCHANGED"
test "$(readlink -f /home/kmjprod/current)" = /home/kmjprod/releases/platform-8070dad72c55 || { echo "LIVE_RELEASE_CHANGED"; exit 2; }
echo "PRODUCTION_CUTOVER=NOT_ATTEMPTED"

