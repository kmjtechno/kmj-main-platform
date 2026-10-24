#!/usr/bin/env bash
# Exact-SHA KMJ-elite isolated migration up/down/up rehearsal.
# Never connects to production PostgreSQL: verifies Laravel's resolved DSN
# against the disposable Unix socket BEFORE issuing any write command.
# No live DB writes, live symlink switch, approval flags or service reload.
set -Eeuo pipefail
umask 077
readonly SHA='b1d672bbc83a51ca3f8271435692825072444c8e'
readonly SHORT='b1d672bbc83a'
readonly LIVE='/home/kmjprod/current'
readonly EXPECTED_LIVE='/home/kmjprod/releases/platform-8070dad72c55'
readonly CANDIDATE="/home/kmjprod/releases/platform-$SHORT"
readonly BACKUP="/var/backups/kmj-platform/pre-deploy-$SHORT.tar.gz"
readonly WITNESS="/var/backups/kmj-platform/pre-deploy-$SHORT.json"
readonly LOCK='/run/lock/kmj-main-platform-production-release.lock'
readonly PORT=55489
readonly DATABASE='kmj_migration_rehearsal'
readonly ROLE='kmj_restore_drill'

block() { printf 'ISOLATED_MIGRATION_DRILL=BLOCKED_%s\n' "$1" >&2; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }

[[ "$(id -u)" -eq 0 && "$(hostname -s)" == KMJ-elite ]] || block WRONG_OPERATOR_OR_HOST
[[ -L "$LIVE" && "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
[[ -d "$CANDIDATE/.git" && ! -L "$CANDIDATE" ]] || block CANDIDATE_NOT_STAGED
[[ -s "$CANDIDATE/apps/platform/.env" && ! -L "$CANDIDATE/apps/platform/.env" ]] || block CANDIDATE_ENV_MISSING
[[ ! -e "$CANDIDATE/apps/platform/bootstrap/cache/config.php" ]] || block CANDIDATE_CONFIG_CACHED
[[ "$(runuser -u kmjprod -- git -C "$CANDIDATE" rev-parse HEAD)" == "$SHA" ]] || block CANDIDATE_WRONG_SHA
[[ -z "$(runuser -u kmjprod -- git -C "$CANDIDATE" status --porcelain --untracked-files=normal)" ]] || block CANDIDATE_DIRTY

for cmd in python3 runuser git tar pg_restore flock df php8.4; do
  command -v "$cmd" >/dev/null 2>&1 || block "MISSING_$cmd"
done
[[ -d /var/backups/kmj-platform && ! -L /var/backups/kmj-platform ]] || block BACKUP_DIRECTORY_MISSING
[[ -f "$BACKUP" && -f "$WITNESS" && ! -L "$BACKUP" && ! -L "$WITNESS" ]] || block BACKUP_OR_WITNESS_MISSING
df -Pk /tmp | awk 'END { exit !($4 > 12582912) }' || block INSUFFICIENT_SCRATCH_DISK_12GB

# Revalidate the exact witness and archive from the successful owner-run backup.
python3 - "$BACKUP" "$WITNESS" "$SHA" "$(basename "$EXPECTED_LIVE")" <<'PY'
import hashlib, json, os, re, stat, sys
archive, witness, sha, release = sys.argv[1:]
for path in (archive, witness):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o077:
        raise SystemExit("ROOT_ONLY_BACKUP_REQUIRED")
if os.path.getsize(witness) > 4096:
    raise SystemExit("WITNESS_TOO_LARGE")
data = json.load(open(witness, encoding="utf-8"))
if not isinstance(data, dict) or set(data) != {"approvedSha", "currentRelease", "backupSha256"}:
    raise SystemExit("WITNESS_INVALID")
if data["approvedSha"] != sha or data["currentRelease"] != release:
    raise SystemExit("WITNESS_IDENTITY_MISMATCH")
if not isinstance(data["backupSha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", data["backupSha256"]):
    raise SystemExit("WITNESS_SHA_INVALID")
h = hashlib.sha256()
with open(archive, "rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        h.update(chunk)
if h.hexdigest() != data["backupSha256"]:
    raise SystemExit("BACKUP_CHECKSUM_MISMATCH")
PY
status BACKUP_WITNESS_RECHECK PASS

pgdir=''
for d in /usr/lib/postgresql/*/bin; do
  [[ -x "$d/initdb" && -x "$d/pg_ctl" && -x "$d/pg_restore" && -x "$d/createdb" && -x "$d/psql" ]] && pgdir="$d"
done
[[ -n "$pgdir" ]] || block RESTORE_BINARIES_MISSING

exec 9>"$LOCK"
flock -n 9 || block RELEASE_OPERATION_BUSY
[[ "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED

scratch="$(mktemp -d /tmp/kmj-schema-drill.XXXXXXXX)"
chown root:kmjprod "$scratch"
chmod 0750 "$scratch"
install -d -o kmjprod -g kmjprod -m 0700 "$scratch/restore"
install -d -o kmjprod -g kmjprod -m 0700 "$scratch/restore/socket"
started=0
cleanup() {
  if [[ "$started" == 1 ]]; then
    runuser -u kmjprod -- "$pgdir/pg_ctl" -D "$scratch/restore/pgdata" -m immediate -w stop >/dev/null 2>&1 || :
  fi
  if [[ "$scratch" == /tmp/kmj-schema-drill.* && -d "$scratch" && ! -L "$scratch" ]]; then
    rm -rf -- "$scratch"
  fi
}
trap cleanup EXIT

# Stream only the known database.dump member; never extract .env or arbitrary tar members.
tar -xOzf "$BACKUP" database.dump > "$scratch/restore/database.dump" || block BACKUP_MEMBER_UNREADABLE
chown kmjprod:kmjprod "$scratch/restore/database.dump"
chmod 0600 "$scratch/restore/database.dump"
[[ -s "$scratch/restore/database.dump" ]] || block EMPTY_DUMP
"$pgdir/pg_restore" --list "$scratch/restore/database.dump" >/dev/null || block PG_DUMP_UNREADABLE
runuser -u kmjprod -- "$pgdir/initdb" -D "$scratch/restore/pgdata" -U "$ROLE" \
  --auth-local=trust --auth-host=reject --no-instructions >"$scratch/initdb.log" 2>&1 || block INITDB_FAILED
runuser -u kmjprod -- "$pgdir/pg_ctl" -D "$scratch/restore/pgdata" \
  -l "$scratch/restore/pg-server.log" -o "-c listen_addresses='' -c unix_socket_directories='$scratch/restore/socket' -c unix_socket_permissions=0700 -c port=$PORT" \
  -w start >/dev/null 2>&1 || block ISOLATED_POSTGRES_START_FAILED
started=1
[[ -S "$scratch/restore/socket/.s.PGSQL.$PORT" ]] || block PRIVATE_SOCKET_MISSING

runuser -u kmjprod -- "$pgdir/createdb" -h "$scratch/restore/socket" -p "$PORT" -U "$ROLE" "$DATABASE" \
  >"$scratch/createdb.log" 2>&1 || block CREATEDB_FAILED
runuser -u kmjprod -- "$pgdir/pg_restore" --exit-on-error --no-owner --no-acl \
  -h "$scratch/restore/socket" -p "$PORT" -U "$ROLE" -d "$DATABASE" \
  "$scratch/restore/database.dump" >"$scratch/restore.log" 2>&1 || block RESTORE_FAILED
status DISPOSABLE_POSTGRES_RESTORE PASS

# Every artisan invocation gets a fixed database connection override.
# The PHP script validates Laravel's RESOLVED configuration including DSN
# before migrate can be invoked, rather than assuming dotenv precedence.
cat >"$scratch/verify.php" <<'PHP'
<?php
try {
    $phase = $argv[1] ?? '';
    $root = $argv[2] ?? '';
    require $root.'/vendor/autoload.php';
    $app = require $root.'/bootstrap/app.php';
    $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    $name = config('database.default');
    $db = config('database.connections.'.$name);
    if ($name !== 'pgsql' || !is_array($db) ||
        ($db['driver'] ?? null) !== 'pgsql' ||
        (string) ($db['host'] ?? '') !== getenv('DB_HOST') ||
        (string) ($db['port'] ?? '') !== getenv('DB_PORT') ||
        (string) ($db['database'] ?? '') !== getenv('DB_DATABASE') ||
        (string) ($db['username'] ?? '') !== getenv('DB_USERNAME') ||
        $db['database'] !== 'kmj_migration_rehearsal' ||
        $db['username'] !== 'kmj_restore_drill' ||
        !str_starts_with((string) $db['host'], '/tmp/kmj-schema-drill.') ||
        !str_ends_with((string) $db['host'], '/restore/socket') ||
        (string) $db['port'] !== '55489' ||
        !empty($db['url']) || !empty($db['read']) || !empty($db['write'])) {
        throw new RuntimeException('ISOLATED_CONNECTION_INVALID');
    }
    $expected = [
        '2026_10_20_070000_create_customer_profiles_table',
        '2026_10_21_020500_create_omnidesk_activation_bindings',
        '2026_10_21_030000_add_current_nonce_to_omnidesk_activation_bindings',
    ];
    $ran = \Illuminate\Support\Facades\DB::table('migrations')->pluck('migration')->all();
    $all = array_map(fn($p) => basename($p, '.php'), glob($root.'/database/migrations/*.php'));
    $pending = array_values(array_diff($all, $ran));
    sort($pending);
    $hasCustomer = \Illuminate\Support\Facades\Schema::hasTable('customer_profiles');
    $hasOmnidesk = \Illuminate\Support\Facades\Schema::hasTable('omnidesk_activation_bindings');
    $hasNonce = $hasOmnidesk && \Illuminate\Support\Facades\Schema::hasColumn('omnidesk_activation_bindings', 'current_nonce');
    if ($phase === 'before' || $phase === 'rollback') {
        if ($pending !== $expected || $hasCustomer || $hasOmnidesk || $hasNonce) {
            throw new RuntimeException('MIGRATION_BASELINE_MISMATCH');
        }
    } elseif ($phase === 'after') {
        if ($pending !== [] || !$hasCustomer || !$hasOmnidesk || !$hasNonce) {
            throw new RuntimeException('MIGRATION_AFTER_MISMATCH');
        }
    } else {
        throw new RuntimeException('UNKNOWN_PHASE');
    }
    echo "ISOLATED_LARAVEL_$phase=PASS\n";
} catch (Throwable $e) {
    fwrite(STDERR, "ISOLATED_LARAVEL_CHECK=FAIL\n");
    exit(2);
}
PHP
chown root:kmjprod "$scratch/verify.php"
chmod 0640 "$scratch/verify.php"

readonly SOCKET="$scratch/restore/socket"
app() {
  runuser -u kmjprod -- env \
    DB_CONNECTION=pgsql DB_URL= DB_HOST="$SOCKET" DB_PORT="$PORT" \
    DB_DATABASE="$DATABASE" DB_USERNAME="$ROLE" DB_PASSWORD= \
    PGHOST="$SOCKET" PGPORT="$PORT" PGUSER="$ROLE" PGDATABASE="$DATABASE" \
    "$@"
}

# Validate immutable candidate migrations and strictly constrained connection.
app php8.4 "$scratch/verify.php" before "$CANDIDATE/apps/platform" || block LARAVEL_PRECHECK_FAILED
status ONLY_THREE_EXPECTED_PENDING PASS

# DB writes are strictly confined to the disposable PostgreSQL instance.
(
  cd "$CANDIDATE/apps/platform"
  app php8.4 artisan migrate --force --no-interaction --no-ansi \
    >"$scratch/migrate.log" 2>&1 || block ISOLATED_MIGRATE_FAILED
)
app php8.4 "$scratch/verify.php" after "$CANDIDATE/apps/platform" || block MIGRATED_SCHEMA_INVALID
status ISOLATED_THREE_MIGRATIONS PASS

(
  cd "$CANDIDATE/apps/platform"
  app php8.4 artisan migrate:rollback --step=3 --force --no-interaction --no-ansi \
    >"$scratch/rollback.log" 2>&1 || block ISOLATED_ROLLBACK_FAILED
)
app php8.4 "$scratch/verify.php" rollback "$CANDIDATE/apps/platform" || block ISOLATED_ROLLBACK_SCHEMA_INVALID
status ISOLATED_SCHEMA_ROLLBACK PASS

(
  cd "$CANDIDATE/apps/platform"
  app php8.4 artisan migrate --force --no-interaction --no-ansi \
    >"$scratch/remigrate.log" 2>&1 || block ISOLATED_REMIGRATE_FAILED
)
app php8.4 "$scratch/verify.php" after "$CANDIDATE/apps/platform" || block ISOLATED_REMIGRATION_SCHEMA_INVALID
status ISOLATED_FORWARD_REPLAY PASS

[[ "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
[[ -z "$(runuser -u kmjprod -- git -C "$CANDIDATE" status --porcelain --untracked-files=normal)" ]] || block CANDIDATE_DIRTY_AFTER_DRILL
status PRODUCTION_DATABASE_WRITES NONE
status PRODUCTION_MIGRATIONS NOT_ATTEMPTED
status PRODUCTION_ACTIVATION NOT_ATTEMPTED
status PRODUCTION_ROLLBACK NOT_VERIFIED
status OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED
status ISOLATED_MIGRATION_DRILL PASS
