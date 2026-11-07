#!/bin/bash -p
# Exact-SHA cd958 isolated migration up / old-release-compat / down / up rehearsal on KMJ-elite.
# Adapted from the reviewed B2 drill (work/qa/KMJ_B2_MIGRATION_REHEARSAL_SOURCE_20261029.sh).
# Restores ONLY the database.dump member of the exact pre-deploy backup into a disposable,
# socket-only PostgreSQL. Laravel's RESOLVED connection is verified before any write.
# Never connects to production PostgreSQL. No live DB write, symlink switch, approval flag,
# service reload or storage change. Prints fixed markers only (no SQL values, secrets or logs).
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
readonly SHA='cd9580701d3cea19d7d4e4c96ebe70c0553fbf37'
readonly SHORT='cd9580701d3c'
readonly LIVE='/home/kmjprod/current'
readonly EXPECTED_LIVE='/home/kmjprod/releases/platform-574e443a2c75'
readonly OLD_APP="$EXPECTED_LIVE/apps/platform"
readonly CANDIDATE="/home/kmjprod/releases/platform-$SHORT"
readonly SHARED='/home/kmjprod/shared/storage'
readonly BACKUP="/var/backups/kmj-platform/pre-deploy-$SHORT.tar.gz"
readonly WITNESS="/var/backups/kmj-platform/pre-deploy-$SHORT.json"
readonly LOCK='/run/lock/kmj-main-platform-production-release.lock'
readonly PORT=55489
readonly DATABASE='kmj_migration_rehearsal'
readonly ROLE='kmj_restore_drill'

block() { printf 'ISOLATED_MIGRATION_DRILL=BLOCKED_%s\n' "$1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }

[[ $- == *p* ]] || block PRIVILEGED_BASH_REQUIRED
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == KMJ-elite ]] || block WRONG_OPERATOR_OR_HOST
[[ -L "$LIVE" && "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
[[ -d "$CANDIDATE/.git" && ! -L "$CANDIDATE" ]] || block CANDIDATE_NOT_STAGED
[[ -s "$OLD_APP/vendor/autoload.php" && -s "$OLD_APP/bootstrap/app.php" ]] || block OLD_APP_RUNTIME_MISSING
[[ -s "$CANDIDATE/apps/platform/.env" && ! -L "$CANDIDATE/apps/platform/.env" ]] || block CANDIDATE_ENV_MISSING
[[ ! -e "$CANDIDATE/apps/platform/bootstrap/cache/config.php" ]] || block CANDIDATE_CONFIG_CACHED
for cmd in python3 runuser git tar flock df php8.4; do
  command -v "$cmd" >/dev/null 2>&1 || block "MISSING_$cmd"
done

# Candidate identity + cleanliness through the SAME protected attestor the materializer uses:
# exact HEAD, and the only permitted untracked path is the journal-attested preserved storage dir.
source_attestation() {
  /usr/bin/python3 -I -B - "$CANDIDATE" "$SHA" "$SHARED" <<'KMJ_ROOT_SNAPSHOT_ATTEST'
import hashlib, os, pathlib, re, stat, sys, types
helper = pathlib.Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py")
scanner = pathlib.Path("/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py")
def checked(path, digest):
    if str(path) != os.path.realpath(path):
        raise ValueError("noncanonical dependency")
    for parent in path.parents:
        s = os.lstat(parent)
        if s.st_uid != 0 or s.st_mode & 0o022 and not s.st_mode & stat.S_ISVTX:
            raise ValueError("unprotected dependency ancestor")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != 0 or s.st_mode & 0o022 or s.st_size > 1048576:
            raise ValueError("unprotected dependency")
        with os.fdopen(os.dup(fd), "rb") as source:
            raw = source.read(1048577)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("dependency hash mismatch")
        return raw
    finally:
        os.close(fd)
try:
    raw = checked(helper, "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6")
    checked(scanner, "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba")
    candidate, sha, shared = sys.argv[1:]
    app = pathlib.Path(candidate) / "apps/platform"
    module = types.ModuleType("protected_snapshot_attestor")
    module.__file__ = str(helper)
    exec(compile(raw, str(helper), "exec"), module.__dict__)
    names = [p.name for p in app.iterdir() if p.name.startswith("storage.pre-shared-")]
    if len(names) != 1 or not re.fullmatch(r"storage\.pre-shared-\d{8}T\d{6}Z", names[0]):
        raise ValueError("one exact snapshot required")
    permitted = module.check_source(release_root=candidate, app_dir=str(app), expected_sha=sha,
        shared_dir=shared, snapshot_name=names[0], state_dir="/var/lib/kmj-main-platform-storage-switch",
        scanner_path=str(scanner))
    if permitted != "apps/platform/" + names[0] + "/":
        raise ValueError("unexpected attested path")
    print("CANDIDATE_SOURCE_ATTESTED=PASS")
except Exception:
    print("CANDIDATE_SOURCE_ATTESTED=BLOCKED")
    raise SystemExit(2)
KMJ_ROOT_SNAPSHOT_ATTEST
}
source_attestation || block CANDIDATE_SOURCE_UNATTESTED

[[ -d /var/backups/kmj-platform && ! -L /var/backups/kmj-platform ]] || block BACKUP_DIRECTORY_MISSING
[[ -f "$BACKUP" && -f "$WITNESS" && ! -L "$BACKUP" && ! -L "$WITNESS" ]] || block BACKUP_OR_WITNESS_MISSING
df -Pk /tmp | awk 'END { exit !($4 > 12582912) }' || block INSUFFICIENT_SCRATCH_DISK_12GB

# Revalidate the exact witness and archive from the owner-run backup (no new backup is taken).
python3 -I - "$BACKUP" "$WITNESS" "$SHA" "$(basename "$EXPECTED_LIVE")" <<'PY'
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

exec 9<"$LOCK"
[[ "$(stat -Lc '%u:%h:%a' -- /proc/self/fd/9)" == "0:1:600" ]] || block RELEASE_LOCK_UNSAFE
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
  if [[ -e "$scratch/restore/pgdata/postmaster.pid" ]]; then
    echo ISOLATED_PG_CLEANUP=BLOCKED_PROCESS_STILL_PRESENT
    return 1
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

cat >"$scratch/verify.php" <<'PHP'
<?php
try {
    $phase = $argv[1] ?? '';
    $root = $argv[2] ?? '';
    require $root.'/vendor/autoload.php';
    $app = require $root.'/bootstrap/app.php';
    $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    if ($app->environment() !== 'testing' || $app->isProduction()) {
        throw new RuntimeException('ISOLATED_ENV_REQUIRED');
    }
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
        '2026_10_29_120000_create_codebridge_workspace_tables',
        '2026_10_30_000000_create_omnidesk_renewal_challenges',
        '2026_10_30_120000_create_codebridge_workspace_jobs',
        '2026_10_31_120000_create_codebridge_workspace_tool_proposals',
    ];
    $tables = ['codebridge_workspace_conversations', 'codebridge_workspace_messages',
        'codebridge_workspace_events', 'omnidesk_renewal_challenges', 'codebridge_workspace_jobs',
        'codebridge_workspace_job_events', 'codebridge_workspace_tool_proposals'];
    $ran = \Illuminate\Support\Facades\DB::table('migrations')->pluck('migration')->all();
    $all = array_map(fn($p) => basename($p, '.php'), glob($root.'/database/migrations/*.php'));
    $pending = array_values(array_diff($all, $ran));
    sort($pending);
    $present = array_values(array_filter($tables, fn($t) => \Illuminate\Support\Facades\Schema::hasTable($t)));
    if ($phase === 'before' || $phase === 'rollback') {
        if ($pending !== $expected || $present !== []) {
            // Migration file names are public source identifiers, safe to print for diagnosis.
            fwrite(STDOUT, "ISOLATED_PENDING_".$phase."=".implode(',', array_map(fn($m) => preg_replace('/[^A-Za-z0-9_]/', '', $m), $pending))."\n");
            fwrite(STDOUT, "ISOLATED_NEW_TABLES_PRESENT_".$phase."=".count($present)."\n");
            throw new RuntimeException('MIGRATION_BASELINE_MISMATCH');
        }
    } elseif ($phase === 'after') {
        if ($pending !== [] || $present !== $tables) {
            fwrite(STDOUT, "ISOLATED_PENDING_after=".count($pending)."\n");
            throw new RuntimeException('MIGRATION_AFTER_MISMATCH');
        }
    } else {
        throw new RuntimeException('UNKNOWN_PHASE');
    }
    echo "ISOLATED_LARAVEL_$phase=PASS\n";
} catch (Throwable $e) {
    $reason = preg_match('/\A[A-Z_]{3,80}\z/', $e->getMessage()) === 1 ? $e->getMessage() : 'RUNTIME_FAILURE';
    fwrite(STDOUT, "ISOLATED_LARAVEL_REASON=".$reason."\n");
    exit(2);
}
PHP
chown root:kmjprod "$scratch/verify.php"
chmod 0640 "$scratch/verify.php"

readonly SOCKET="$scratch/restore/socket"
# Force config-cache bypass so no cached production DSN can be reused.
readonly ISOLATED_CONFIG_CACHE="$scratch/restore/kmj-isolated-config-cache.php"
[[ ! -e "$ISOLATED_CONFIG_CACHE" && ! -L "$ISOLATED_CONFIG_CACHE" ]] || block ISOLATED_CONFIG_CACHE_EXISTS
app() {
  # Non-production Laravel environment ONLY for this disposable Unix-socket database.
  runuser -u kmjprod -- env \
    APP_CONFIG_CACHE="$ISOLATED_CONFIG_CACHE" \
    APP_ENV=testing APP_DEBUG=false MAIL_MAILER=log QUEUE_CONNECTION=sync LOG_CHANNEL=stderr \
    CACHE_STORE=array SESSION_DRIVER=array APP_URL=http://localhost \
    DB_CONNECTION=pgsql DB_URL= DB_HOST="$SOCKET" DB_PORT="$PORT" \
    DB_DATABASE="$DATABASE" DB_USERNAME="$ROLE" DB_PASSWORD= \
    PGHOST="$SOCKET" PGPORT="$PORT" PGUSER="$ROLE" PGDATABASE="$DATABASE" \
    "$@"
}

app php8.4 "$scratch/verify.php" before "$CANDIDATE/apps/platform" || block LARAVEL_PRECHECK_FAILED
status ONLY_FOUR_EXPECTED_PENDING PASS

(
  cd "$CANDIDATE/apps/platform"
  app php8.4 artisan migrate --force --no-interaction --no-ansi \
    >"$scratch/migrate.log" 2>&1 || block ISOLATED_MIGRATE_FAILED
)
app php8.4 "$scratch/verify.php" after "$CANDIDATE/apps/platform" || block MIGRATED_SCHEMA_INVALID
status ISOLATED_FOUR_MIGRATIONS PASS

# OLD production code (574e) against the EXPANDED disposable schema: bootstrap/connection/read smoke.
cat >"$scratch/verify-old.php" <<'PHP_OLD'
<?php
try {
    $root = $argv[1] ?? '';
    require $root.'/vendor/autoload.php';
    $app = require $root.'/bootstrap/app.php';
    $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    if ($app->environment() !== 'testing' || $app->isProduction()) {
        throw new RuntimeException('OLD_APP_ISOLATION_ENV_INVALID');
    }
    $db = config('database.connections.'.config('database.default'));
    if (config('database.default') !== 'pgsql' || !is_array($db)
        || ($db['driver'] ?? null) !== 'pgsql'
        || (string) ($db['host'] ?? '') !== getenv('DB_HOST')
        || (string) ($db['port'] ?? '') !== getenv('DB_PORT')
        || (string) ($db['database'] ?? '') !== 'kmj_migration_rehearsal'
        || (string) ($db['username'] ?? '') !== 'kmj_restore_drill'
        || !str_starts_with((string) ($db['host'] ?? ''), '/tmp/kmj-schema-drill.')
        || !str_ends_with((string) ($db['host'] ?? ''), '/restore/socket')
        || (string) ($db['port'] ?? '') !== '55489'
        || !empty($db['url']) || !empty($db['read']) || !empty($db['write'])) {
        throw new RuntimeException('OLD_APP_DISPOSABLE_DB_TARGET_INVALID');
    }
    foreach (['users', 'organizations', 'entitlements', 'customer_profiles', 'omnidesk_activation_bindings'] as $table) {
        if (!\Illuminate\Support\Facades\Schema::hasTable($table)) {
            throw new RuntimeException('OLD_APP_REQUIRED_SCHEMA_ABSENT');
        }
    }
    $query = \Illuminate\Support\Facades\DB::select('SELECT 1 AS readiness');
    if (count($query) !== 1 || (int) ($query[0]->readiness ?? 0) !== 1) {
        throw new RuntimeException('OLD_APP_READ_ONLY_QUERY_FAILED');
    }
    $users = \Illuminate\Support\Facades\DB::table('users')->count();
    if (!is_int($users) || $users < 1) {
        throw new RuntimeException('OLD_APP_USERS_UNREADABLE');
    }
    echo "OLD_RELEASE_EXPANDED_SCHEMA_BOOTSTRAP=PASS\n";
    echo "OLD_RELEASE_DISPOSABLE_DB_READ=PASS\n";
} catch (Throwable $e) {
    $reason = preg_match('/\A[A-Z_]{3,80}\z/', $e->getMessage()) === 1 ? $e->getMessage() : 'RUNTIME_FAILURE';
    fwrite(STDOUT, "OLD_RELEASE_EXPANDED_SCHEMA=FAIL_".$reason."\n");
    exit(2);
}
PHP_OLD
chown root:kmjprod "$scratch/verify-old.php"
chmod 0640 "$scratch/verify-old.php"
app php8.4 "$scratch/verify-old.php" "$OLD_APP" || block OLD_RELEASE_COMPATIBILITY_SMOKE_FAILED

if ! (
  cd "$CANDIDATE/apps/platform"
  app php8.4 artisan migrate:rollback --step=4 --force --no-interaction --no-ansi \
    >"$scratch/rollback.log" 2>&1
); then
  grep -oE 'SQLSTATE\[[A-Z0-9]{5}\]' "$scratch/rollback.log" | tail -1 | sed 's/^/ISOLATED_ROLLBACK_SQLSTATE=/' || :
  block ISOLATED_ROLLBACK_FAILED
fi
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
source_attestation || block CANDIDATE_SOURCE_CHANGED_AFTER_DRILL
status PRODUCTION_DATABASE_WRITES NONE
status PRODUCTION_MIGRATIONS NOT_ATTEMPTED
status PRODUCTION_ACTIVATION NOT_ATTEMPTED
status ISOLATED_MIGRATION_DRILL PASS
