#!/usr/bin/env bash
# Exact-head Laravel / PostgreSQL 18 isolated migration, feature and rollback QA.
# Runs ONLY in GitHub Actions. No production DB, TCP service or credentials.
set -Eeuo pipefail
umask 077

(( $# == 1 )) || { echo 'BLOCKED: expected one commit SHA'; exit 2; }
sha="$1"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'BLOCKED: invalid source SHA'; exit 2; }
[[ "$GITHUB_ACTIONS" == true && -n "$RUNNER_TEMP" ]] || {
  echo 'BLOCKED: GitHub-hosted CI context required'; exit 2;
}
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: root runner not allowed'; exit 2; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == kmj-main-platform ]] || {
  echo 'BLOCKED: unexpected repository'; exit 2;
}
[[ "$(git -C "$repo" rev-parse HEAD)" == "$sha" ]] || {
  echo 'BLOCKED: wrong candidate SHA'; exit 2;
}
[[ -z "$(git -C "$repo" status --porcelain)" ]] || {
  echo 'BLOCKED: dirty candidate checkout'; exit 2;
}
test ! -e "$repo/apps/platform/.env" && test ! -L "$repo/apps/platform/.env" || {
  echo 'BLOCKED: existing .env must not be touched'; exit 2;
}
test -f "$repo/apps/platform/vendor/autoload.php" || {
  echo 'BLOCKED: locked Composer dependencies missing'; exit 3;
}
php -r 'exit(extension_loaded("pdo_pgsql") ? 0 : 1);' || {
  echo 'BLOCKED: php pgsql PDO driver missing'; exit 3;
}
for tool in docker php python3 npm; do
  command -v "$tool" >/dev/null || { echo "BLOCKED: missing $tool"; exit 3; }
done

image='postgres:18.6-alpine3.24@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5'
tmp="$(mktemp -d "$RUNNER_TEMP/kmj-pg18-qa.XXXXXXXX")"
socket="$tmp/socket"
mkdir -m 0700 "$socket"
container_name="kmj-pg18-laravel-ci"
created_env=0
cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  if (( created_env )) && [[ -f "$repo/apps/platform/.env" ]] &&
    grep -qx '# KMJ disposable PG18 CI only' "$repo/apps/platform/.env"; then
    rm -- "$repo/apps/platform/.env"
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT

# Pin official PG18 CI image to the previously verified registry digest.
docker pull "$image" >/dev/null
pg_uid="$(docker run --rm --network none --entrypoint id "$image" -u postgres)"
[[ "$pg_uid" =~ ^[0-9]{1,6}$ ]] || {
  echo 'BLOCKED: unrecognized PostgreSQL image UID'; exit 3;
}
# Host runner accesses socket through its private group. Container may write
# as its PostgreSQL UID. No network port and no public host socket directory.
chmod 0770 "$socket"
sudo chown "$pg_uid:$(id -g)" "$socket"
docker run --rm -d --name "$container_name" --network none \
  -e POSTGRES_USER=kmj_qa \
  -e POSTGRES_DB=kmj_release_qa \
  -e POSTGRES_PASSWORD=ephemeral-ci-only \
  -e POSTGRES_INITDB_ARGS='--auth-local=trust --auth-host=reject' \
  --mount "type=bind,src=$socket,dst=/kmj-socket" \
  "$image" -c listen_addresses='' -c unix_socket_directories=/kmj-socket \
  -c unix_socket_permissions=0777 >/dev/null

ready=0
for _ in $(seq 1 90); do
  if [[ -S "$socket/.s.PGSQL.5432" ]] &&
    docker exec -u postgres "$container_name" psql -X -qAt \
      -v ON_ERROR_STOP=1 -U kmj_qa -d kmj_release_qa -c 'SELECT 1' \
      >/dev/null 2>&1; then
    ready=1
    break
  fi
  if [[ "$(docker inspect --format '{{.State.Running}}' "$container_name" 2>/dev/null || echo false)" != true ]]; then
    echo 'PG18_CONTAINER_STOPPED_DURING_STARTUP'
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo 'PG18_CI_START=FAIL'
  if docker inspect "$container_name" >/dev/null 2>&1; then
    echo 'PG18_CONTAINER_START_LOG_TAIL_BEGIN'
    # Only disposable CI setup: no customer data or production credentials.
    docker logs --tail 60 "$container_name" 2>&1 | tail -n 60 || true
    echo 'PG18_CONTAINER_START_LOG_TAIL_END'
    docker exec -u postgres "$container_name" psql -X -qAt -v ON_ERROR_STOP=1 -U kmj_qa -d kmj_release_qa -c 'SELECT 1' 2>&1 | tail -n 4 || true
  fi
  [[ -S "$socket/.s.PGSQL.5432" ]] && echo 'PG18_UNIX_SOCKET=PRESENT' || echo 'PG18_UNIX_SOCKET=MISSING'
  exit 1
fi
query() {
  docker exec -u postgres "$container_name" psql -X -qAt \
    -v ON_ERROR_STOP=1 -U kmj_qa -d kmj_release_qa -c "$1"
}
server_version="$(query 'SHOW server_version_num')"
[[ "$server_version" =~ ^[0-9]+$ ]] && (( server_version / 10000 == 18 )) || {
  echo 'BLOCKED: server is not PostgreSQL major 18'; exit 3;
}
[[ "$(query "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'")" == 0 ]] || {
  echo 'BLOCKED: disposable PostgreSQL not empty'; exit 3;
}
echo "PG18_LARAVEL_SOURCE_SHA=$sha"
echo 'PG18_DATABASE=ISOLATED_PRIVATE_UNIX_SOCKET NETWORK=NONE HOST_PORTS=NONE'

cd "$repo/apps/platform"
printf '# KMJ disposable PG18 CI only\n' > .env
chmod 600 .env
created_env=1
export APP_ENV=testing APP_DEBUG=false APP_URL=http://localhost
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
export DB_CONNECTION=pgsql DB_HOST="$socket" DB_PORT=5432
export DB_DATABASE=kmj_release_qa DB_USERNAME=kmj_qa DB_PASSWORD='' DB_URL=''
export CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync
export MAIL_MAILER=log BROADCAST_CONNECTION=log FILESYSTEM_DISK=local
export TELESCOPE_ENABLED=false PULSE_ENABLED=false NIGHTWATCH_ENABLED=false
export KMJ_PG_STAGING_VERIFY=1 KMJ_PG_VERIFY_SOCKET="$socket"

# Fail independently if PHP cannot reach the private PG18 socket.
php -r '
  $pdo = new PDO("pgsql:host=" . getenv("DB_HOST")
    . ";port=5432;dbname=kmj_release_qa", "kmj_qa", "");
  $v = (int) $pdo->query("SHOW server_version_num")->fetchColumn();
  exit(intdiv($v, 10000) === 18 ? 0 : 3);
' || { echo 'PG18_PDO_PRIVATE_SOCKET=FAIL'; exit 1; }
echo 'PG18_PDO_PRIVATE_SOCKET=PASS'

php artisan migrate --force --no-interaction --no-ansi || {
  echo 'PG18_LARAVEL_MIGRATE=FAIL'; exit 1;
}
check_sql="SELECT (to_regclass('public.payment_gateway_settings') IS NOT NULL AND to_regclass('public.kslp_license_keys') IS NOT NULL)::integer"
[[ "$(query "$check_sql")" == 1 ]] || {
  echo 'PG18_APPLICATION_SCHEMA=FAIL'; exit 1;
}
echo 'PG18_LARAVEL_MIGRATE=PASS'

npm ci --no-audit --no-fund
npm run build
test -s public/build/manifest.json || {
  echo 'PG18_FRONTEND_MANIFEST=FAIL'; exit 1;
}
echo 'PG18_FRONTEND_MANIFEST=PASS'

failures=0
if php artisan test --filter='PostgresReleaseGateTest|PlatformOwnerConsoleTest|OwnerPaymentGatewaySettingsTest|KslpDeveloperAppsTest|KslpDeveloperActivationApiTest|KslpLifecycleTest' --display-warnings --fail-on-warning --no-ansi; then
  echo 'PG18_POSTGRES_SPECIFIC_FEATURE_TESTS=PASS'
else
  echo 'PG18_POSTGRES_SPECIFIC_FEATURE_TESTS=FAIL'
  failures=$((failures + 1))
fi
if [[ "$failures" == 0 ]] && php artisan test --testsuite=Feature --display-warnings --fail-on-warning --no-ansi; then
  echo 'PG18_FULL_LARAVEL_FEATURE_SUITE=PASS'
else
  echo 'PG18_FULL_LARAVEL_FEATURE_SUITE=FAIL_OR_SKIPPED'
  failures=$((failures + 1))
fi
if php artisan migrate:rollback --force --no-interaction --no-ansi &&
  [[ "$(query "$check_sql")" == 0 ]]; then
  echo 'PG18_LARAVEL_ROLLBACK=PASS'
else
  echo 'PG18_LARAVEL_ROLLBACK=FAIL'
  failures=$((failures + 1))
fi
echo "PG18_LARAVEL_REHEARSAL_FAILURES=$failures"
echo 'PRODUCTION_DATABASE_TOUCHED=NO PRODUCTION_DEPLOYMENT=NONE'
(( failures == 0 )) || exit 1
echo 'PG18_LARAVEL_ISOLATED_ACCEPTANCE=PASS'
