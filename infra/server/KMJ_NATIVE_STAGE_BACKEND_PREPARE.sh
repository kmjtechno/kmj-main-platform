#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
# Prepare an isolated Laravel staging backend on KMJ-elite.
# NO Nginx vhost, production pointer, DNS, firewall or cert changes.
# An initialized backend is not live until a separate approved route gate.
SITE=staging.kmjtechno.com
SOURCE=/srv/kmj-codebridge-projects/kmj-main-platform
USER=kmjstage
HOME_STAGE=/home/kmjstage
BASE=/home/kmjstage/releases
SITE_LINK=/home/kmjstage/htdocs/staging.kmjtechno.com
DATABASE=kmj_stage_2026
DBROLE=kmjstage_2026
POOL=/etc/php/8.4/fpm/pool.d/kmjstage.conf
SOCKET=/run/php/kmjstage-php84-fpm.sock
VHOST=/etc/nginx/sites-enabled/staging.kmjtechno.com.conf
CRED=/root/.kmj-stage-native-credentials

blocked() { echo "KMJ_STAGE_BACKEND=BLOCKED $1" >&2; exit 1; }
[[ "$(hostname -s)" == KMJ-elite && "$EUID" -eq 0 ]] || blocked WRONG_HOST_OR_USER
[[ "${1:-}" == --inspect || "${1:-}" == --prepare ]] || blocked INSPECT_OR_PREPARE_REQUIRED
mode="$1"
if [[ "$mode" == --prepare ]]; then
  [[ "${2:-}" =~ ^[a-f0-9]{40}$ && "${3:-}" == STAGING_ONLY ]] || blocked EXACT_SHA_SCOPE_REQUIRED
  SHA="$2"
fi
prod="$(readlink -f /home/kmjprod/current)" || blocked PRODUCTION_BASELINE_MISSING
[[ -d "$prod" && -d "$SOURCE/.git" && ! -L "$SOURCE" ]] || blocked PRODUCTION_OR_SOURCE_MISSING
# Ubuntu convention: sites-enabled is often a symlink to sites-available.
# Follow only an exact staging config within /etc/nginx/sites-available;
# no scripts or mutable production vhosts are written through this path.
if [[ -L "$VHOST" ]]; then
  vhost_target="$(readlink -f -- "$VHOST")" || blocked STAGING_VHOST_SYMLINK_UNRESOLVED
  [[ "$vhost_target" == /etc/nginx/sites-available/staging.kmjtechno.com.conf &&
     -f "$vhost_target" && ! -L "$vhost_target" ]] || blocked STAGING_VHOST_SYMLINK_OUTSIDE_APPROVED_PATH
else
  [[ -f "$VHOST" ]] || blocked DEDICATED_VHOST_FILE_MISSING
fi
vhost_hash="$(sha256sum "$VHOST" | cut -d' ' -f1)"
[[ ! -e "$SITE_LINK" && ! -L "$SITE_LINK" ]] || blocked STAGING_SITE_ALREADY_PRESENT
[[ ! -e "$BASE" && ! -L "$BASE" ]] || blocked STAGING_RELEASE_ALREADY_PRESENT
[[ ! -e "$POOL" && ! -L "$POOL" ]] || blocked STAGING_FPM_POOL_ALREADY_PRESENT
[[ ! -e "$CRED" && ! -L "$CRED" ]] || blocked STAGING_SECRETS_ALREADY_PRESENT
[[ ! -L "$HOME_STAGE" ]] || blocked STAGING_HOME_SYMLINK
[[ -d /etc/php/8.4/fpm/pool.d && ! -L /etc/php/8.4/fpm/pool.d ]] || blocked FPM_POOL_DIRECTORY_UNSAFE
[[ -x /usr/bin/php8.4 && -S /run/php/php8.4-fpm.sock ]] || blocked PHP84_RUNTIME_MISSING
for bin in git composer node npm psql createdb runuser php-fpm8.4 pg_isready; do
  command -v "$bin" >/dev/null || blocked "DEPENDENCY_MISSING_$bin"
done
nginx -t >/dev/null 2>&1 || blocked NGINX_INVALID
[[ "$(systemctl is-active nginx)" == active && "$(systemctl is-active php8.4-fpm)" == active ]] || blocked SERVICES_INACTIVE
for mod in PDO pdo_pgsql mbstring openssl xml curl; do
  grep -Fxq "$mod" <<< "$(php8.4 -m)" || blocked "PHP84_MODULE_MISSING_$mod"
done
pg_isready -h 127.0.0.1 -p 5432 >/dev/null || blocked LOCAL_POSTGRES_UNAVAILABLE
grep -Eq '^[[:space:]]*server_name[[:space:]]+staging[.]kmjtechno[.]com[[:space:]]*;' "$VHOST" || blocked STAGING_DOMAIN_NOT_ISOLATED
grep -Eq '^[[:space:]]*return[[:space:]]+503[[:space:]]*;' "$VHOST" || blocked STAGING_PLACEHOLDER_NOT_PRESENT
role_exists="$(runuser -u postgres -- psql -h /var/run/postgresql -p 5432 -XAtq -v ON_ERROR_STOP=1 -d postgres -c "SELECT 1 FROM pg_roles WHERE rolname='$DBROLE'")" || blocked ROLE_LOOKUP_FAILED
db_exists="$(runuser -u postgres -- psql -h /var/run/postgresql -p 5432 -XAtq -v ON_ERROR_STOP=1 -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$DATABASE'")" || blocked DATABASE_LOOKUP_FAILED
[[ -z "$role_exists" && -z "$db_exists" ]] || blocked STAGING_DB_OR_ROLE_ALREADY_PRESENT
if id "$USER" >/dev/null 2>&1; then
  [[ "$(getent passwd "$USER" | cut -d: -f6)" == "$HOME_STAGE" && "$(id -u "$USER")" != 0 ]] || blocked EXISTING_STAGE_USER_UNSAFE
  runuser -u www-data -- test -x "$HOME_STAGE" || blocked EXISTING_STAGE_HOME_NOT_TRAVERSABLE
else
  [[ ! -e "$HOME_STAGE" && ! -L "$HOME_STAGE" ]] || blocked UNOWNED_STAGE_HOME_ALREADY_PRESENT
fi
[[ "$(readlink -f /home/kmjprod/current)" == "$prod" && "$(sha256sum "$VHOST" | cut -d' ' -f1)" == "$vhost_hash" ]] || blocked PRODUCTION_OR_STAGE_CONFIG_CHANGED
if [[ "$mode" == --inspect ]]; then
  echo 'KMJ_STAGE_BACKEND=READY_FOR_ISOLATED_PREPARATION'
  echo 'STAGING_RUNTIME=PHP8.4'
  echo 'STAGING_POSTGRES=NEW_RESTRICTED_DATABASE_AVAILABLE'
  echo 'STAGING_HTTP=UNMODIFIED_503'
  echo 'PRODUCTION_POINTER=UNCHANGED'
  exit 0
fi
remote_sha="$(git -C "$SOURCE" ls-remote --exit-code origin refs/heads/staging-approved | awk '{print $1}')" || blocked APPROVED_REMOTE_UNREACHABLE
[[ "$remote_sha" == "$SHA" ]] || blocked CURRENT_STAGING_APPROVED_SHA_MISMATCH
git -C "$SOURCE" cat-file -e "$SHA^{commit}" 2>/dev/null || blocked APPROVED_SOURCE_OBJECT_NOT_LOCAL
read -r -p 'Type PREPARE_ISOLATED_STAGING: ' answer </dev/tty
[[ "$answer" == PREPARE_ISOLATED_STAGING ]] || blocked OWNER_CONFIRMATION_REQUIRED
exec 9>/run/kmj-stage-native-backend.lock
flock -n 9 || blocked CONCURRENT_STAGE_JOB
[[ ! -e "$BASE" && ! -e "$SITE_LINK" && ! -e "$POOL" && ! -e "$CRED" ]] || blocked STAGING_RESOURCES_CREATED_CONCURRENTLY
[[ "$(sha256sum "$VHOST" | cut -d' ' -f1)" == "$vhost_hash" && "$(readlink -f /home/kmjprod/current)" == "$prod" ]] || blocked PREPARE_HOST_CHANGED
# A failed new-stage build leaves ONLY isolated resources for supervised
# recovery. Do not automatically drop data or reset any working tree.
if ! id "$USER" >/dev/null 2>&1; then
  useradd --system --user-group --create-home --home-dir "$HOME_STAGE" --shell /usr/sbin/nologin "$USER"
  chgrp www-data "$HOME_STAGE"
  chmod 0750 "$HOME_STAGE"
fi
install -d -o "$USER" -g www-data -m 0750 "$BASE"
install -d -o "$USER" -g "$USER" -m 0755 "$HOME_STAGE/htdocs"
release="$BASE/$SHA"
git clone --quiet --no-local --no-checkout -- "$SOURCE" "$release"
git -C "$release" checkout --quiet --detach "$SHA"
[[ "$(git -C "$release" rev-parse HEAD)" == "$SHA" ]] || blocked CANDIDATE_SHA_INCORRECT
chown -R "$USER:$USER" "$release"
app="$release/apps/platform"
[[ -f "$app/artisan" && -f "$app/composer.lock" && -f "$app/package-lock.json" ]] || blocked APP_FILES_INCOMPLETE
password="$(openssl rand -hex 32)"
appkey="base64:$(openssl rand -base64 32 | tr -d '\n')"
# Root-only durable recovery secret; never print or commit.
printf 'DB_NAME=%s\nDB_USER=%s\nDB_PASSWORD=%s\n' "$DATABASE" "$DBROLE" "$password" > "$CRED"
chmod 0600 "$CRED"
printf "CREATE ROLE $DBROLE LOGIN PASSWORD '%s' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;\n" "$password" |
  runuser -u postgres -- psql -h /var/run/postgresql -p 5432 -X -v ON_ERROR_STOP=1 -d postgres >/dev/null
runuser -u postgres -- createdb -h /var/run/postgresql -p 5432 --owner="$DBROLE" "$DATABASE"
export KMJ_STAGE_DB_PASSWORD="$password" KMJ_STAGE_APP_KEY="$appkey"
python3 - "$app/.env" <<'PY'
import os,pathlib,sys
p=pathlib.Path(sys.argv[1])
values={
"APP_NAME":'"KMJ TECHNO STAGING"',"APP_ENV":"staging","APP_DEBUG":"false",
"APP_URL":"https://staging.kmjtechno.com","APP_KEY":os.environ["KMJ_STAGE_APP_KEY"],
"DB_CONNECTION":"pgsql","DB_HOST":"127.0.0.1","DB_PORT":"5432",
"DB_DATABASE":"kmj_stage_2026","DB_USERNAME":"kmjstage_2026",
"DB_PASSWORD":os.environ["KMJ_STAGE_DB_PASSWORD"],
"SESSION_DRIVER":"database","SESSION_DOMAIN":"null","SESSION_COOKIE":"kmj_staging_session",
"CACHE_STORE":"database","QUEUE_CONNECTION":"database","MAIL_MAILER":"log",
"PUBLIC_INDEXING_ENABLED":"false","CODEBRIDGE_OAUTH_ENABLED":"false",
"CODEBRIDGE_AGENT_PUBLIC_URL":"","LOG_LEVEL":"warning"
}
lines=(p.parent/'.env.example').read_text().splitlines()
out=[];used=set()
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key=line.split('=',1)[0]
        if key in values:
            out.append(key+'='+values[key]);used.add(key);continue
    out.append(line)
for key,value in values.items():
    if key not in used:out.append(key+'='+value)
p.write_text('\n'.join(out)+'\n')
p.chmod(0o600)
PY
unset KMJ_STAGE_DB_PASSWORD KMJ_STAGE_APP_KEY password appkey
chown "$USER:$USER" "$app/.env"
# Only run dependency scripts/migrations as restricted stage user and in
# new stage database. No production .env, DB rows or checkout is reused.
runuser -u "$USER" -- bash -c 'set -Eeuo pipefail; cd "$1"; COMPOSER_MEMORY_LIMIT=-1 composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-progress --no-ansi' _ "$app"
runuser -u "$USER" -- bash -c 'set -Eeuo pipefail; cd "$1"; npm ci --no-audit --no-fund && npm run build' _ "$app"
runuser -u "$USER" -- bash -c 'set -Eeuo pipefail; cd "$1"; php8.4 artisan migrate --force --no-interaction && php8.4 artisan about --no-ansi >/dev/null && php8.4 artisan optimize:clear' _ "$app"
cat > "$POOL" <<'POOL'
[kmjstage]
user = kmjstage
group = kmjstage
listen = /run/php/kmjstage-php84-fpm.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660
pm = ondemand
pm.max_children = 3
pm.process_idle_timeout = 10s
pm.max_requests = 250
php_admin_value[expose_php] = Off
php_admin_value[display_errors] = Off
php_admin_value[log_errors] = On
POOL
chmod 0644 "$POOL"
php-fpm8.4 -t >/dev/null || blocked STAGING_FPM_POOL_INVALID
systemctl reload php8.4-fpm
[[ -S /run/php/kmjstage-php84-fpm.sock ]] || blocked STAGING_FPM_SOCKET_MISSING
ln -s "$app" "$SITE_LINK"
[[ "$(readlink -f "$SITE_LINK")" == "$app" ]] || blocked STAGING_SITE_LINK_INVALID
[[ "$(git -C "$release" rev-parse HEAD)" == "$SHA" ]] || blocked STAGING_CANDIDATE_CHANGED
[[ "$(readlink -f /home/kmjprod/current)" == "$prod" && "$(sha256sum "$VHOST" | cut -d' ' -f1)" == "$vhost_hash" ]] || blocked PRODUCTION_OR_NGINX_CHANGED
remote_after="$(git -C "$SOURCE" ls-remote --exit-code origin refs/heads/staging-approved | awk '{print $1}')" || blocked FINAL_APPROVED_SOURCE_UNREACHABLE
[[ "$remote_after" == "$SHA" ]] || blocked PROMOTION_MOVED_DURING_PREPARE
echo 'KMJ_STAGE_BACKEND=PREPARED_ISOLATED'
echo "STAGING_SOURCE_SHA=$SHA"
echo 'STAGING_PHP_FPM=DEDICATED_SOCKET'
echo 'STAGING_HTTP=STILL_503_NOT_LIVE'
echo 'PRODUCTION_POINTER=UNCHANGED'
echo 'NEXT=GUARDED_NGINX_ACTIVATION_AND_INDEPENDENT_HTTP_QA'
