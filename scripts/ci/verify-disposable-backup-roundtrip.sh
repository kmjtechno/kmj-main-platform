#!/usr/bin/env bash
# Synthetic encrypted backup -> offsite -> verify -> PostgreSQL and storage restore.
# Never accepts external database targets, production backup paths or secrets.
set -Eeuo pipefail
umask 077
if [[ "$(id -u)" == 0 ]]; then
  echo 'BLOCKED: unprivileged CI account required' >&2; exit 2
fi
for tool in git age age-keygen rclone tar sha256sum find cmp; do
  command -v "$tool" >/dev/null || { echo "BLOCKED: missing $tool" >&2; exit 2; }
done
pgbin=''
for dir in /usr/lib/postgresql/*/bin /usr/local/pgsql/bin; do
  if [[ -x "$dir/initdb" && -x "$dir/pg_ctl" && -x "$dir/pg_dump" && -x "$dir/pg_restore" && -x "$dir/psql" && -x "$dir/createdb" ]]; then
    pgbin="$dir"
  fi
done
[[ -n "$pgbin" ]] || { echo 'BLOCKED: PostgreSQL test binaries missing' >&2; exit 2; }
repo="$(git rev-parse --show-toplevel)"
test -f "$repo/scripts/backup_platform.sh"
test -f "$repo/scripts/verify_backup_bundle.sh"
if [[ -v GITHUB_SHA && -n "$GITHUB_SHA" ]]; then
  [[ "$(git -C "$repo" rev-parse HEAD)" == "$GITHUB_SHA" ]] || {
    echo 'BLOCKED: exact SHA mismatch' >&2; exit 2;
  }
fi
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS DB_URL DATABASE_URL
unset BACKUP_DATABASE_URL BACKUP_REMOTE BACKUP_AGE_RECIPIENT BACKUP_AGE_IDENTITY
tmp="$(mktemp -d /tmp/kmj-backup-roundtrip.XXXXXXXX)"
pg_started=0
cleanup() {
  if (( pg_started )); then
    "$pgbin/pg_ctl" -D "$tmp/pgdata" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
mkdir -m 700 "$tmp/socket" "$tmp/app" "$tmp/restore" "$tmp/ops"
mkdir -p "$tmp/app/storage/app"
printf 'kmj-synthetic-storage-proof\n' > "$tmp/app/storage/app/proof.txt"
"$pgbin/initdb" -D "$tmp/pgdata" -U kmj_qa --auth-local=trust --auth-host=reject --no-instructions > "$tmp/initdb.log" 2>&1 || {
  echo 'FAIL: temporary initdb' >&2; exit 1;
}
port=55439
"$pgbin/pg_ctl" -D "$tmp/pgdata" -l "$tmp/postgres.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$tmp/socket' -c unix_socket_permissions=0700 -c port=$port" \
  -w start >/dev/null 2>&1 || {
  echo 'FAIL: Unix-socket-only PostgreSQL startup' >&2; exit 1;
}
pg_started=1
test -S "$tmp/socket/.s.PGSQL.$port"
"$pgbin/createdb" -h "$tmp/socket" -p "$port" -U kmj_qa kmj_backup_source
"$pgbin/createdb" -h "$tmp/socket" -p "$port" -U kmj_qa kmj_backup_recovered
psql_local() {
  "$pgbin/psql" -X -A -t -h "$tmp/socket" -p "$port" -U kmj_qa -v ON_ERROR_STOP=1 "$@"
}
psql_local -d kmj_backup_source -c 'CREATE TABLE public.kmj_backup_roundtrip (id integer PRIMARY KEY, marker text NOT NULL)' >/dev/null
psql_local -d kmj_backup_source -c "INSERT INTO public.kmj_backup_roundtrip VALUES (1, 'kmj-synthetic-restore-proof')" >/dev/null
age-keygen -o "$tmp/age.key" >/dev/null 2>&1
export BACKUP_DATABASE_URL="host=$tmp/socket port=$port user=kmj_qa dbname=kmj_backup_source"
export BACKUP_REMOTE="$tmp/offsite"
export BACKUP_AGE_RECIPIENT
BACKUP_AGE_RECIPIENT="$(age-keygen -y "$tmp/age.key")"
export BACKUP_AGE_IDENTITY="$tmp/age.key"
export BACKUP_STATUS_DIR="$tmp/ops"
export APP_ROOT="$tmp/app"
export BACKUP_TIER=daily
bash "$repo/scripts/backup_platform.sh" >/dev/null
bundle="$(find "$tmp/offsite/daily" -maxdepth 1 -type f -name '*.tar.gz.age' -print -quit)"
[[ -n "$bundle" && -f "$bundle" ]] || { echo 'FAIL: encrypted synthetic backup missing' >&2; exit 1; }
bash "$repo/scripts/verify_backup_bundle.sh" "$bundle" >/dev/null
# This archive is generated from test-only files and verified before extraction.
age -d -i "$tmp/age.key" "$bundle" | tar -xzf - -C "$tmp/restore"
"$pgbin/pg_restore" --exit-on-error --no-owner --no-acl \
  -h "$tmp/socket" -p "$port" -U kmj_qa -d kmj_backup_recovered "$tmp/restore/database.dump"
actual="$(psql_local -d kmj_backup_recovered -c 'SELECT marker FROM public.kmj_backup_roundtrip WHERE id = 1')"
[[ "$actual" == 'kmj-synthetic-restore-proof' ]] || {
  echo 'FAIL: recovered PostgreSQL data mismatch' >&2; exit 1;
}
mkdir -m 700 "$tmp/recovered-storage"
tar -xzf "$tmp/restore/storage.tar.gz" -C "$tmp/recovered-storage"
cmp "$tmp/app/storage/app/proof.txt" "$tmp/recovered-storage/storage/app/proof.txt"
echo "DISPOSABLE_BACKUP_ROUNDTRIP=PASS SOURCE_SHA=$(git -C "$repo" rev-parse HEAD)"
echo 'POSTGRESQL=PRIVATE_UNIX_SOCKET_ONLY'
echo 'BACKUP_SOURCE=SYNTHETIC; LIVE_DATABASE_AND_SECRETS=UNTOUCHED'
echo 'PRODUCTION_BACKUP_RESTORE=NOT_VERIFIED'
