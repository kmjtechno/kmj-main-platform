#!/usr/bin/env bash
# Stage-only PostgreSQL and storage recovery witness. Root-only local backup,
# disposable restore rehearsal, then cleanup of ONLY the created scratch DB.
# Never touches the production DB or changes live staging/production pointers.
set -Eeuo pipefail
umask 077
block() { echo "KMJ_STAGE_RECOVERY=BLOCKED_$1"; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || block SHA
sha="$1"
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 ]] || block HOST
prod=/home/kmjprod/current
site=/home/kmjstage/htdocs/staging.kmjtechno.com
[[ -L "$prod" && -L "$site" ]] || block LINKS
prod_before="$(readlink -f "$prod")" || block PROD_POINTER
old="$(readlink -f "$site")" || block STAGE_POINTER
[[ "$prod_before" == /home/kmjprod/releases/platform-* ]] || block PROD_SCOPE
[[ "$old" == /home/kmjstage/releases/*/apps/platform ]] || block STAGE_SCOPE
candidate="/home/kmjstage/releases/$sha/apps/platform"
[[ -d "$candidate" && -f "$candidate/artisan" && -f "$candidate/.env" && ! -L "$candidate/.env" ]] || block CANDIDATE
[[ "$(runuser -u kmjstage -- git -C "$(dirname "$(dirname "$candidate")")" rev-parse HEAD 2>/dev/null)" == "$sha" ]] || block CANDIDATE_HEAD
[[ -L "$candidate/storage" && "$(readlink -f "$candidate/storage")" == "$old/storage" ]] || block SHARED_STORAGE_NOT_PREPARED
[[ -L "$candidate/public/storage" && "$(readlink -f "$candidate/public/storage")" == "$old/storage/app/public" ]] || block PUBLIC_STORAGE
[[ -d "$old/storage" && ! -L "$old/storage" && "$(find "$old/storage" -type l -print -quit)" == "" ]] || block STORAGE_SAFETY
[[ "$(sha256sum "$old/.env" | awk '{print $1}')" == "$(sha256sum "$candidate/.env" | awk '{print $1}')" ]] || block ENV_MISMATCH
[[ "$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/staging-approved 2>/dev/null | awk '{print $1}')" == "$sha" ]] || block APPROVAL_DRIFT
for cmd in pg_dump pg_restore createdb dropdb psql tar sha256sum runuser flock; do
  command -v "$cmd" >/dev/null 2>&1 || block "MISSING_$cmd"
done
dbname="$(python3 - "$old/.env" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text()
config = {}
for line in raw.splitlines():
    if line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    if key in ('DB_DATABASE','DB_CONNECTION','DB_HOST','APP_ENV','APP_URL','DB_URL'):
        config[key] = value.strip().strip('"').strip("'")
name = config.get('DB_DATABASE','')
safe = (
    config.get('DB_CONNECTION') == 'pgsql'
    and config.get('DB_HOST') in ('127.0.0.1','localhost')
    and config.get('APP_ENV') == 'staging'
    and config.get('APP_URL') == 'https://staging.kmjtechno.com'
    and not config.get('DB_URL')
    and (re.fullmatch(r'kmj_stage_[a-z0-9_]{1,40}', name) or name == 'kmj_platform_staging')
)
if not safe:
    raise SystemExit(2)
print(name)
PY
)" || block DB_SCOPE
[[ -n "$dbname" ]] || block DB_NAME
# Bound temporary disk load; limit only staging DB, not production.
size="$(runuser -u postgres -- psql -XAtq -d "$dbname" -c 'SELECT pg_database_size(current_database())' 2>/dev/null)" || block DB_SIZE_UNAVAILABLE
[[ "$size" =~ ^[0-9]+$ && "$size" -lt 1073741824 ]] || block DB_TOO_LARGE_FOR_LOCAL_REHEARSAL
[[ "$(readlink -f "$site")" == "$old" && "$(readlink -f "$prod")" == "$prod_before" ]] || block POINTER_DRIFT
exec 9>/run/lock/kmj-stage-recovery.lock
flock -n 9 || block LOCK_BUSY
backup_root=/root/kmj-stage-backups
install -d -o root -g root -m 0700 "$backup_root"
receipt_dir="$(mktemp -d "$backup_root/$sha.XXXXXXXX")" || block BACKUP_DIR
chmod 0700 "$receipt_dir"
dbdump="$receipt_dir/staging-db.pgdump"
archive="$receipt_dir/staging-storage.tar"
echo "STAGING_RECOVERY_CANDIDATE_SHA=$sha"
# Read-only snapshots of the staging database and current upload/storage tree.
runuser -u postgres -- pg_dump --format=custom --no-owner --no-privileges --dbname="$dbname" > "$dbdump" || block DB_DUMP
[[ -s "$dbdump" ]] || block DB_DUMP_EMPTY
pg_restore --list "$dbdump" >/dev/null || block DB_DUMP_INVALID
tar --create --file "$archive" --directory "$old" -- storage || block STORAGE_TAR
[[ -s "$archive" ]] || block STORAGE_ARCHIVE_EMPTY
tar --list --file "$archive" >/dev/null || block STORAGE_ARCHIVE_INVALID
scratch="kmj_stg_probe_$(printf '%s' "$sha" | cut -c1-8)_$(openssl rand -hex 5)"
[[ "$scratch" =~ ^kmj_stg_probe_[a-f0-9]{8}_[a-f0-9]{10}$ ]] || block SCRATCH_NAME
# Never remove a database that this command did not create.
created=0
cleanup() {
  if [[ "$created" == 1 ]]; then
    runuser -u postgres -- dropdb --if-exists -- "$scratch" >/dev/null 2>&1 || echo 'STAGING_SCRATCH_CLEANUP=MANUAL_REVIEW_REQUIRED'
  fi
}
trap cleanup EXIT
exists="$(runuser -u postgres -- psql -XAtq -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$scratch'" 2>/dev/null)" || block SCRATCH_PREFLIGHT
[[ -z "$exists" ]] || block SCRATCH_PREEXISTS
runuser -u postgres -- createdb --template=template0 --owner=postgres -- "$scratch" || block SCRATCH_CREATE
created=1
# Stream backup from root into the postgres process, without loosening permissions.
runuser -u postgres -- pg_restore --exit-on-error --no-owner --no-privileges --dbname="$scratch" < "$dbdump" || block SCRATCH_RESTORE
source_tables="$(runuser -u postgres -- psql -XAtq -d "$dbname" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null)" || block SOURCE_TABLE_COUNT
restored_tables="$(runuser -u postgres -- psql -XAtq -d "$scratch" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null)" || block RESTORED_TABLE_COUNT
[[ "$source_tables" =~ ^[0-9]+$ && "$source_tables" -gt 0 && "$source_tables" == "$restored_tables" ]] || block TABLE_COUNT_MISMATCH
sha256sum "$dbdump" "$archive" > "$receipt_dir/sha256sums.txt"
chmod 0600 "$dbdump" "$archive" "$receipt_dir/sha256sums.txt"
[[ "$(readlink -f "$site")" == "$old" && "$(readlink -f "$prod")" == "$prod_before" ]] || block POINTER_DRIFT
echo 'STAGING_DB_SNAPSHOT=PASS'
echo 'STAGING_DB_DISPOSABLE_RESTORE=PASS'
echo 'STAGING_DB_TABLE_COUNT_MATCH=PASS'
echo 'STAGING_STORAGE_SNAPSHOT=PASS'
echo 'STAGING_BACKUP_LOCAL_ROOT_ONLY=PASS'
echo 'STAGING_OFFSITE_BACKUP=NOT_VERIFIED'
echo 'STAGING_POINTER=UNCHANGED'
echo 'PRODUCTION_POINTER=UNCHANGED'
echo 'KMJ_STAGE_RECOVERY=PASS_STAGING_ONLY_NO_ACTIVATION'
