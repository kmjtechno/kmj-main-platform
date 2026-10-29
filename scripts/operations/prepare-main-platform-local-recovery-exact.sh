#!/usr/bin/env bash
# KMJ-elite exact-release local pre-deploy recovery (parameterized): real pg_dump, app storage, disposable
# PostgreSQL restore, integrity checks and root-owned evidence.
# NO production DB writes, no site switch, no approval flag changes, no offsite claim.
set -Eeuo pipefail
umask 077
# Usage (root on KMJ-elite, after the exact candidate is staged):
#   prepare-main-platform-local-recovery-exact.sh <approved-40-hex-sha> <expected-current-release>
# Both values are explicit owner inputs; nothing is inferred from the network.
fail() { echo "KMJ_LOCAL_RECOVERY=BLOCKED $1"; exit 2; }
[[ "$#" -eq 2 ]] || fail EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED
[[ "$1" =~ ^[a-f0-9]{40}$ ]] || fail EXACT_SHA_REQUIRED
[[ "$2" =~ ^platform-[a-f0-9]{12}$ ]] || fail EXPECTED_CURRENT_RELEASE_INVALID
readonly TARGET_SHA="$1"
readonly SHORT_SHA="${TARGET_SHA:0:12}"
readonly EXPECTED_CURRENT="$2"
[[ "platform-$SHORT_SHA" != "$EXPECTED_CURRENT" ]] || fail TARGET_ALREADY_CURRENT
readonly ROOT=/home/kmjprod
readonly BACKUP_DIR=/var/backups/kmj-platform
readonly ARCHIVE="$BACKUP_DIR/pre-deploy-$SHORT_SHA.tar.gz"
readonly WITNESS="$BACKUP_DIR/pre-deploy-$SHORT_SHA.json"
status() { printf '%s=%s\n' "$1" "$2"; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
[[ -L "$ROOT/current" ]] || fail CURRENT_NOT_SYMLINK
readonly OLD="$(readlink -f "$ROOT/current")"
[[ "$OLD" == "$ROOT"/releases/* && -d "$OLD" ]] || fail CURRENT_RELEASE_UNSAFE
readonly OLD_NAME="$(basename "$OLD")"
[[ "$OLD_NAME" == "$EXPECTED_CURRENT" ]] || fail CURRENT_RELEASE_CHANGED
[[ -d "$ROOT/releases/platform-$SHORT_SHA/.git" ]] || fail CANDIDATE_MISSING
[[ "$(runuser -u kmjprod -- git -C "$ROOT/releases/platform-$SHORT_SHA" rev-parse HEAD)" == "$TARGET_SHA" ]] || fail WRONG_CANDIDATE_SHA
[[ -f "$OLD/apps/platform/.env" && -f "$OLD/apps/platform/vendor/autoload.php" && -d "$OLD/apps/platform/storage/app" ]] || fail SOURCE_APP_MISSING
for cmd in git php8.4 pg_dump pg_restore tar sha256sum python3 runuser; do
  command -v "$cmd" >/dev/null 2>&1 || fail "MISSING_$cmd"
done
[[ -d "$BACKUP_DIR" && ! -L "$BACKUP_DIR" ]] || fail BACKUP_DIR_MISSING
[[ ! -e "$ARCHIVE" && ! -L "$ARCHIVE" && ! -e "$WITNESS" && ! -L "$WITNESS" ]] || fail EXISTING_EVIDENCE_REQUIRES_MANUAL_REVIEW
[[ "$(stat -c %U "$BACKUP_DIR")" == root ]] || fail BACKUP_DIR_OWNER
systemctl is-active --quiet nginx || fail NGINX_NOT_ACTIVE
systemctl is-active --quiet php8.4-fpm || fail FPM_NOT_ACTIVE
df -Pk /tmp | awk 'END {exit !($4 > 12582912)}' || fail LOW_FREE_SPACE
pgdir=''
for dir in /usr/lib/postgresql/*/bin; do
  [[ -x "$dir/initdb" && -x "$dir/pg_ctl" && -x "$dir/psql" && -x "$dir/pg_restore" && -x "$dir/createdb" ]] && pgdir="$dir"
done
[[ -n "$pgdir" ]] || fail POSTGRES_RESTORE_BINARIES_MISSING
exec 9>/run/lock/kmj-main-platform-production-release.lock
flock -n 9 || fail PRODUCTION_RELEASE_IN_PROGRESS
scratch="$(mktemp -d /tmp/kmj-local-recovery.XXXXXXXX)"
# Root owns the parent and all archival outputs; only a narrow child workdir
# is writable by the app user. Never write root files in app-writable directories.
chown root:kmjprod "$scratch"
chmod 0750 "$scratch"
install -d -o kmjprod -g kmjprod -m 0700 "$scratch/restore"
started=0
cleanup() {
  if [[ "$started" == 1 ]]; then
    runuser -u kmjprod -- "$pgdir/pg_ctl" -D "$scratch/restore/pgdata" -m immediate -w stop >/dev/null 2>&1 || :
  fi
  rm -rf -- "$scratch"
}
trap cleanup EXIT
# Real production config is read via Laravel as the non-root app user.
# Credentials are passed only in the isolated child process environment.
cat >"$scratch/dump.php" <<'PHP'
<?php
try {
    $root = $argv[1];
    $destination = $argv[2];
    require $root . '/vendor/autoload.php';
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    $name = config('database.default');
    $db = config('database.connections.' . $name);
    if (!is_array($db) || ($db['driver'] ?? null) !== 'pgsql' ||
        !empty($db['url']) || !empty($db['read']) || !empty($db['write'])) {
        throw new RuntimeException('DB_CONFIG_NOT_SUPPORTED');
    }
    $host = $db['host'] ?? '';
    if (!in_array($host, ['127.0.0.1', 'localhost', '::1', '/var/run/postgresql', '/run/postgresql'], true)) {
        throw new RuntimeException('DB_NOT_LOCAL');
    }
    $port = (string)($db['port'] ?? '5432');
    $database = $db['database'] ?? null;
    $username = $db['username'] ?? null;
    $password = $db['password'] ?? '';
    if (!preg_match('/^[0-9]{2,5}$/', $port) || !is_string($database) ||
        $database === '' || !is_string($username) || $username === '') {
        throw new RuntimeException('DB_FIELDS_MISSING');
    }
    $command = [
        '/usr/bin/pg_dump', '--format=custom', '--no-owner', '--no-acl',
        '--host=' . $host, '--port=' . $port,
        '--username=' . $username, '--dbname=' . $database,
        '--file=' . $destination,
    ];
    $pipes = [];
    $process = proc_open($command, [
        0 => ['file', '/dev/null', 'r'],
        1 => ['file', '/dev/null', 'w'],
        2 => ['file', '/dev/null', 'w'],
    ], $pipes, $root, [
        'PATH' => '/usr/bin:/bin',
        'PGPASSWORD' => (string)$password,
        'PGCONNECT_TIMEOUT' => '12',
        'PGOPTIONS' => '-c statement_timeout=300000',
    ]);
    if (!is_resource($process) || proc_close($process) !== 0 || !is_file($destination) || filesize($destination) <= 0) {
        throw new RuntimeException('PG_DUMP_FAILED');
    }
    echo "PRODUCTION_DATABASE_DUMP=PASS\n";
} catch (Throwable $error) {
    fwrite(STDERR, "PRODUCTION_DATABASE_DUMP=FAIL\n");
    exit(2);
}
PHP
chown root:kmjprod "$scratch/dump.php"
chmod 0640 "$scratch/dump.php"
status LOCAL_BACKUP STARTED
runuser -u kmjprod -- php8.4 "$scratch/dump.php" "$OLD/apps/platform" "$scratch/restore/database.dump" || fail REAL_DATABASE_DUMP_FAILED
[[ -f "$scratch/restore/database.dump" && ! -L "$scratch/restore/database.dump" ]] || fail DUMP_NOT_REGULAR
[[ "$(stat -c %U "$scratch/restore/database.dump")" == kmjprod ]] || fail DUMP_OWNER
[[ -s "$scratch/restore/database.dump" ]] || fail DUMP_EMPTY
install -o root -g root -m 0600 "$scratch/restore/database.dump" "$scratch/database.dump"
"$pgdir/pg_restore" --list "$scratch/database.dump" >/dev/null || fail DUMP_UNREADABLE
tar -czf "$scratch/storage.tar.gz" -C "$OLD/apps/platform" storage/app .env || fail STORAGE_BACKUP
[[ -s "$scratch/storage.tar.gz" ]] || fail STORAGE_EMPTY
(
  cd "$scratch"
  printf 'current_release=%s\napproved_sha=%s\nbackup_kind=local_unencrypted_root_only\n' "$OLD_NAME" "$TARGET_SHA" >metadata.txt
  sha256sum database.dump storage.tar.gz metadata.txt > SHA256SUMS
  tar -czf bundle.tar.gz database.dump storage.tar.gz metadata.txt SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
tar -tzf "$scratch/bundle.tar.gz" >/dev/null || fail ARCHIVE_UNREADABLE
status LOCAL_BACKUP_INTEGRITY PASS

# Actual restore into separately initialized local PostgreSQL cluster.
# Never connects to the production socket, network or database.
runuser -u kmjprod -- "$pgdir/initdb" -D "$scratch/restore/pgdata" \
  -U kmj_restore_drill --auth-local=trust --auth-host=reject \
  --no-instructions >"$scratch/initdb.log" 2>&1 || fail DISPOSABLE_INITDB
install -d -o kmjprod -g kmjprod -m 0700 "$scratch/restore/socket"
runuser -u kmjprod -- "$pgdir/pg_ctl" -D "$scratch/restore/pgdata" \
  -l "$scratch/restore/pg-server.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$scratch/restore/socket' -c unix_socket_permissions=0700 -c port=55479" \
  -w start >/dev/null 2>&1 || fail DISPOSABLE_PG_START
started=1
[[ -S "$scratch/restore/socket/.s.PGSQL.55479" ]] || fail PRIVATE_SOCKET_ABSENT
runuser -u kmjprod -- "$pgdir/createdb" \
  -h "$scratch/restore/socket" -p 55479 -U kmj_restore_drill kmj_recovered >/dev/null 2>&1 || fail RESTORE_CREATE_DB
runuser -u kmjprod -- "$pgdir/pg_restore" --exit-on-error --no-owner --no-acl \
  -h "$scratch/restore/socket" -p 55479 -U kmj_restore_drill -d kmj_recovered \
  "$scratch/restore/database.dump" >"$scratch/restore.log" 2>&1 || fail DATABASE_RESTORE_FAILED
schema="$(runuser -u kmjprod -- "$pgdir/psql" -X -A -t \
  -h "$scratch/restore/socket" -p 55479 -U kmj_restore_drill -d kmj_recovered \
  -v ON_ERROR_STOP=1 -c \
  "select (to_regclass('public.users') is not null and to_regclass('public.organizations') is not null and to_regclass('public.entitlements') is not null)::int" \
  2>/dev/null)" || fail SCHEMA_QUERY_FAILED
[[ "$schema" == 1 ]] || fail RECOVERED_SCHEMA_INCOMPLETE
tar -tzf "$scratch/storage.tar.gz" >/dev/null || fail STORAGE_ARCHIVE_UNREADABLE
status LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS
status LOCAL_SCHEMA_VERIFICATION PASS
status OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED
status ROLLBACK_DRILL NOT_VERIFIED
runuser -u kmjprod -- "$pgdir/pg_ctl" -D "$scratch/restore/pgdata" -m immediate -w stop >/dev/null 2>&1 || fail DISPOSABLE_SHUTDOWN_FAILED
started=0

# Publish evidence only after real successful restore. Never overwrite.
digest="$(sha256sum "$scratch/bundle.tar.gz" | awk '{print $1}')"
python3 - "$scratch/bundle.tar.gz" "$ARCHIVE" "$WITNESS" "$TARGET_SHA" "$OLD_NAME" "$digest" <<'PY'
import json, os, shutil, sys
source, archive, witness, sha, previous, digest = sys.argv[1:]
fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as output, open(source, 'rb') as stream:
    shutil.copyfileobj(stream, output, 1024 * 1024)
    output.flush()
    os.fsync(output.fileno())
record = {"approvedSha": sha, "currentRelease": previous, "backupSha256": digest}
fd = os.open(witness, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'w') as output:
    json.dump(record, output, separators=(',', ':'))
    output.write('\n')
    output.flush()
    os.fsync(output.fileno())
PY
printf '%s  %s\n' "$digest" "$ARCHIVE" | sha256sum -c >/dev/null || fail PUBLISHED_BACKUP_DIGEST
[[ "$(readlink -f "$ROOT/current")" == "$OLD" ]] || fail CURRENT_RELEASE_CHANGED
status LOCAL_BACKUP_WITNESS PASS
status PRODUCTION_SWITCH NOT_ATTEMPTED
status OFFSITE_BACKUP NOT_VERIFIED
status ROLLBACK_VERIFIED NOT_YET
status APPROVAL_UPDATED NO
