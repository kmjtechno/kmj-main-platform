#!/usr/bin/env bash
# KMJ TECHNO — PostgreSQL 18 isolated compatibility gate.
# NEVER run against a production database; require exact CI identity.
set -Eeuo pipefail
umask 077

fail() { printf 'KMJ_PG18_PARITY=FAIL:%s\n' "$1" >&2; exit 2; }
[[ "$APP_ENV" == "testing" ]] || fail APP_ENV_NOT_TESTING
[[ "$DB_CONNECTION" == "pgsql" ]] || fail DB_CONNECTION_NOT_PGSQL
[[ "$DB_HOST" == "127.0.0.1" ]] || fail NONLOOPBACK_DATABASE
[[ "$DB_PORT" == "5432" ]] || fail DB_PORT_UNEXPECTED
[[ "$DB_DATABASE" == "kmj_pg18_parity_ci" ]] || fail DATABASE_NAME_UNEXPECTED
[[ "$DB_USERNAME" == "kmj_pg18_ci" ]] || fail DATABASE_USER_UNEXPECTED
[[ -n "$DB_PASSWORD" ]] || fail DATABASE_PASSWORD_MISSING
[[ -z "$DB_URL" ]] || fail DB_URL_OVERRIDE_FORBIDDEN
[[ "$MAIL_MAILER" == "array" ]] || fail LIVE_MAILER_FORBIDDEN
[[ "$QUEUE_CONNECTION" == "sync" ]] || fail QUEUE_CONNECTION_UNEXPECTED
[[ "$SESSION_DRIVER" == "array" ]] || fail SESSION_DRIVER_UNEXPECTED
[[ -n "$APP_KEY" ]] || fail TEST_KEY_MISSING
[[ -d apps/platform/vendor && -f apps/platform/artisan ]] || fail DEPENDENCIES_UNAVAILABLE

# Connect ONLY to the disposable loopback CI database; never log credentials.
php <<'PHP'
<?php
if (!in_array('pgsql', PDO::getAvailableDrivers(), true)) {
    fwrite(STDERR, "KMJ_PG18_PARITY=FAIL:PDO_PGSQL_MISSING\n");
    exit(2);
}
$dsn = 'pgsql:host=127.0.0.1;port=5432;dbname=kmj_pg18_parity_ci';
$ready = false;
for ($i = 0; $i < 40; $i++) {
    try {
        $pdo = new PDO($dsn, getenv('DB_USERNAME'), getenv('DB_PASSWORD'), [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_TIMEOUT => 2,
        ]);
        $row = $pdo->query(
            "SELECT current_setting('server_version_num')::integer AS version_num, " .
            "current_database() AS db, current_user AS db_user"
        )->fetch(PDO::FETCH_ASSOC);
        if ((int) $row['version_num'] < 180000 || (int) $row['version_num'] >= 190000) {
            fwrite(STDERR, "KMJ_PG18_PARITY=FAIL:WRONG_SERVER_MAJOR\n");
            exit(2);
        }
        if ($row['db'] !== 'kmj_pg18_parity_ci' || $row['db_user'] !== 'kmj_pg18_ci') {
            fwrite(STDERR, "KMJ_PG18_PARITY=FAIL:WRONG_DATABASE_IDENTITY\n");
            exit(2);
        }
        echo "KMJ_PG18_SERVER_CHECK=PASS\n";
        $ready = true;
        break;
    } catch (PDOException $e) {
        usleep(250000);
    }
}
if (!$ready) {
    fwrite(STDERR, "KMJ_PG18_PARITY=FAIL:SERVER_UNAVAILABLE\n");
    exit(2);
}
PHP

cd apps/platform
php artisan migrate --force --no-interaction --no-ansi >/dev/null
printf 'KMJ_PG18_MIGRATIONS=PASS\n'

# Representative catalog and owner HTTP contracts, no test filtering in full gate.
php artisan test --filter='KmjProductCatalogTest|PublicProductHubTest|OwnerProductManagementWorkspaceTest' --no-ansi
printf 'KMJ_PG18_CATALOG_FOCUSED=PASS\n'

# A red baseline is never mislabelled a release PASS.
php artisan test --no-ansi
printf 'KMJ_PG18_FULL_LARAVEL_SUITE=PASS\n'
printf 'KMJ_PG18_PARITY=PASS\n'
