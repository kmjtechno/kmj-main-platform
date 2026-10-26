#!/usr/bin/env bash
# KMJ Main Platform exact-SHA PostgreSQL staging verification.
# Creates a fresh local cluster with a PRIVATE UNIX SOCKET, no TCP listener.
# Never use production PostgreSQL or production credentials as a fallback.
set -Eeuo pipefail
umask 077

[[ ${1:-} =~ ^[0-9a-f]{40}$ ]] || { echo 'Usage: verify-postgres-staging.sh <exact-commit-SHA>' >&2; exit 2; }
sha="$1"
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: run as unprivileged repository owner, not root' >&2; exit 2; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == 'kmj-main-platform' ]] || { echo 'BLOCKED: wrong checkout' >&2; exit 2; }
git -C "$repo" cat-file -e "${sha}^{commit}" || { echo 'BLOCKED: fetch exact PR head first' >&2; exit 3; }

pgbin=''
if command -v initdb >/dev/null 2>&1; then
  pgbin="$(dirname "$(command -v initdb)")"
else
  for candidate in /usr/lib/postgresql/*/bin /usr/local/pgsql/bin; do
    if [[ -x "$candidate/initdb" && -x "$candidate/pg_ctl" && -x "$candidate/createdb" && -x "$candidate/psql" ]]; then
      pgbin="$candidate"
    fi
  done
fi
[[ -n "$pgbin" ]] || { echo 'BLOCKED: local initdb/pg_ctl/psql unavailable; production DB forbidden' >&2; exit 3; }
for bin in initdb pg_ctl createdb psql; do
  [[ -x "$pgbin/$bin" ]] || { echo "BLOCKED: missing $pgbin/$bin" >&2; exit 3; }
done
php -r 'exit(extension_loaded("pdo_pgsql") ? 0 : 1);' || { echo 'BLOCKED: missing pdo_pgsql' >&2; exit 3; }
[[ -f "$repo/apps/platform/vendor/autoload.php" && -x "$repo/apps/platform/vendor/bin/phpunit" ]] || {
  echo 'BLOCKED: preinstalled Composer test dependencies unavailable' >&2; exit 3;
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-pg-release.XXXXXXXX")"
mkdir -m 700 "$tmp/socket"
pg_started=0
cleanup() {
  if (( pg_started )); then
    "$pgbin/pg_ctl" -D "$tmp/pgdata" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  git -C "$repo" worktree remove --force "$tmp/tree" >/dev/null 2>&1 || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM

git -C "$repo" worktree add --detach "$tmp/tree" "$sha" >/dev/null
[[ "$(git -C "$tmp/tree" rev-parse HEAD)" == "$sha" ]] || exit 3
cp -a "$repo/apps/platform/vendor" "$tmp/tree/apps/platform/vendor"
"$pgbin/initdb" -D "$tmp/pgdata" -U kmj_qa --auth-local=trust --auth-host=reject --no-instructions >"$tmp/initdb.log" 2>&1 || {
  echo 'FAIL: temp initdb' >&2; tail -n 20 "$tmp/initdb.log" >&2; exit 1;
}
port=55432
"$pgbin/pg_ctl" -D "$tmp/pgdata" -l "$tmp/postgres.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$tmp/socket' -c unix_socket_permissions=0700 -c port=$port" \
  -w start >/dev/null 2>&1 || {
  echo 'FAIL: temporary PostgreSQL startup; no production fallback' >&2
  tail -n 20 "$tmp/postgres.log" >&2
  exit 1
}
pg_started=1
"$pgbin/createdb" -h "$tmp/socket" -p "$port" -U kmj_qa kmj_release_qa
cd "$tmp/tree/apps/platform"
printf '# disposable test environment; NO production credentials\n' >.env
chmod 600 .env
export APP_ENV=testing APP_DEBUG=false APP_URL=http://localhost
export DB_CONNECTION=pgsql DB_HOST="$tmp/socket" DB_PORT="$port"
export DB_DATABASE=kmj_release_qa DB_USERNAME=kmj_qa DB_PASSWORD='' DB_URL=''
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
export CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync
export MAIL_MAILER=log BROADCAST_CONNECTION=log FILESYSTEM_DISK=local
export TELESCOPE_ENABLED=false PULSE_ENABLED=false NIGHTWATCH_ENABLED=false
export KMJ_PG_STAGING_VERIFY=1 KMJ_PG_VERIFY_SOCKET="$tmp/socket"

[[ "$DB_HOST" == "$tmp/socket" && -S "$DB_HOST/.s.PGSQL.$port" ]] || {
  echo 'BLOCKED: private PostgreSQL socket missing' >&2; exit 3;
}
query() { "$pgbin/psql" -X -A -t -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" -v ON_ERROR_STOP=1 -c "$1"; }
[[ "$(query "select count(*) from pg_catalog.pg_tables where schemaname = 'public'")" == 0 ]] || {
  echo 'BLOCKED: expected brand-new empty staging database' >&2; exit 3;
}
echo "PG_STAGING_SHA=$sha"
echo 'PG_STAGING_CLUSTER=private local Unix socket; NO production DB or network listener'
php artisan migrate --force --no-interaction --no-ansi || { echo 'FAIL: PostgreSQL migration apply' >&2; exit 1; }
check_sql="select (to_regclass('public.payment_gateway_settings') is not null and to_regclass('public.kslp_license_keys') is not null)::int"
[[ "$(query "$check_sql")" == 1 ]] || { echo 'FAIL: required product/payment schema absent' >&2; exit 1; }
echo 'PASS: fresh PostgreSQL migration apply and both new schema tables'
# Bytebase-inspired drift guard, isolated PostgreSQL metadata only.
# The CI schema may run on PG16 even though production target is PG18:
# report the ACTUAL server major, never claim cross-version parity.
schema_sql="$tmp/tree/scripts/ci/postgres_schema_metadata.sql"
schema_compare="$tmp/tree/scripts/ci/compare_postgres_schema_metadata.py"
test -f "$schema_sql" && test -f "$schema_compare" || {
  echo 'BLOCKED: immutable schema review scripts absent'; exit 3;
}
schema_snapshot() {
  "$pgbin/psql" -X -q -A -t -v ON_ERROR_STOP=1 \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" \
    -f "$schema_sql" > "$1"
  test -s "$1" || { echo 'BLOCKED: empty PostgreSQL metadata'; exit 3; }
}
schema_before="$tmp/schema-before.json"
schema_same="$tmp/schema-same.json"
schema_changed="$tmp/schema-changed.json"
schema_restored="$tmp/schema-restored.json"
schema_snapshot "$schema_before"
schema_snapshot "$schema_same"
python3 -B "$schema_compare" --expected "$schema_before" --actual "$schema_same" \
  || { echo 'FAIL: read-only PostgreSQL metadata stable replay'; exit 1; }
# Controlled negative test: the only DB is the temporary private Unix socket.
query 'CREATE TABLE public.kmj_schema_drift_probe_ci (id bigint)' >/dev/null
schema_snapshot "$schema_changed"
set +e
python3 -B "$schema_compare" --expected "$schema_before" --actual "$schema_changed"
schema_drift_rc=$?
set -e
[[ "$schema_drift_rc" -eq 1 ]] || {
  echo "FAIL: injected PostgreSQL schema drift was not detected ($schema_drift_rc)"; exit 1;
}
query 'DROP TABLE public.kmj_schema_drift_probe_ci' >/dev/null
schema_snapshot "$schema_restored"
python3 -B "$schema_compare" --expected "$schema_before" --actual "$schema_restored" \
  || { echo 'FAIL: PostgreSQL schema not restored after negative control'; exit 1; }
echo 'KMJ_PG_SCHEMA_DRIFT_FAULT_INJECTION=PASS; PRIVATE_SOCKET_ONLY=YES'
failures=0
# An explicit regression test must prove PHPUnit did not fall back to SQLite
# from its default phpunit.xml configuration.
if php artisan test --filter='PostgresReleaseGateTest|PlatformOwnerConsoleTest|OwnerPaymentGatewaySettingsTest|KslpDeveloperAppsTest|KslpDeveloperActivationApiTest|KslpLifecycleTest' --display-warnings --fail-on-warning --no-ansi; then
  echo 'PASS: selected PostgreSQL feature tests'
else
  echo 'FAIL: selected PostgreSQL feature tests'
  failures=$((failures + 1))
fi
# Optional exhaustive PostgreSQL feature pass on the same private cluster.
# Build the exact candidate's Vite manifest first. Normal CI builds assets
# before testing; skipping that step gives false HTTP 500 failures.
if [[ "${KMJ_PG_FULL_FEATURE_SUITE:-0}" == 1 ]]; then
  command -v npm >/dev/null || { echo 'BLOCKED: npm not installed'; exit 3; }
  npm ci --no-audit --no-fund
  npm run build
  test -s public/build/manifest.json || { echo 'BLOCKED: Vite manifest missing after build'; exit 3; }
  echo 'PASS: exact-SHA frontend manifest prepared for full PostgreSQL tests'
fi
# Optional exhaustive PostgreSQL feature pass on the same private cluster.
# No production credentials, network listener or database fallback.
if [[ "${KMJ_PG_FULL_FEATURE_SUITE:-0}" == 1 ]]; then
  echo 'PG_FEATURE_MODE=ALL_TESTS_DISPOSABLE_POSTGRESQL'
  if php artisan test --testsuite=Feature --display-warnings --fail-on-warning --no-ansi; then
    echo 'PASS: full PostgreSQL Feature suite'
  else
    echo 'FAIL: full PostgreSQL Feature suite'
    failures=$((failures + 1))
  fi
fi
if php artisan migrate:rollback --force --no-interaction --no-ansi; then
  if [[ "$(query "$check_sql")" == 0 ]]; then
    echo 'PASS: PostgreSQL rollback; both new tables removed'
  else
    echo 'FAIL: PostgreSQL rollback left required schema behind'
    failures=$((failures + 1))
  fi
else
  echo 'FAIL: PostgreSQL rollback command'
  failures=$((failures + 1))
fi
echo "PG_STAGING_FAILURES=$failures SHA=$sha"
if (( failures )); then exit 1; fi
echo 'PASS: disposable PostgreSQL migration, focused tests and rollback'
echo 'NOT VERIFIED: protected GitHub Actions, commercial signed SDKs, payment settlement, production canary'
