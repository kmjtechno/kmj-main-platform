#!/usr/bin/env bash
# Operator-run real offsite download + disposable PostgreSQL recovery drill.
# No production DB connection, deployment, DNS, application or secret mutation.
set -Eeuo pipefail
umask 077
status() { printf '%s=%s\n' "$1" "$2"; }
block() { status "$1" BLOCKED; exit 2; }

[[ "$(id -u)" != 0 ]] || block UNPRIVILEGED_OPERATOR
[[ "${KMJ_ACK_ISOLATED_RECOVERY:-}" == YES ]] || block OPERATOR_CONSENT
[[ -n "${BACKUP_REMOTE_OBJECT:-}" ]] || block REMOTE_OBJECT_SELECTION
[[ "$BACKUP_REMOTE_OBJECT" != *[[ -n "${BACKUP_AGE_IDENTITY:-}" ]] || block AGE_IDENTITY
[[ -f "$BACKUP_AGE_IDENTITY" && ! -L "$BACKUP_AGE_IDENTITY" ]] || block AGE_IDENTITY
case "$(hostname -s | tr '[:upper:]' '[:lower:]')" in
  kmj-elite|kmj-main-prod-01) block INDEPENDENT_HOST_REQUIRED ;;
esac
for tool in rclone age python3 tar df mktemp; do
  command -v "$tool" >/dev/null 2>&1 || block "MISSING_$tool"
done
# An unqualified local file path is not evidence of a remote backup.
rclone listremotes 2>/dev/null | grep -Fxq "$remote_name:" || block CONFIGURED_REMOTE_REQUIRED
# Never inherit connection settings that could reference a production DB.
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
unset DB_URL DATABASE_URL BACKUP_DATABASE_URL
pgbin=''
for dir in /usr/lib/postgresql/*/bin /usr/local/pgsql/bin; do
  if [[ -x "$dir/initdb" && -x "$dir/pg_ctl" && -x "$dir/createdb" &&
        -x "$dir/psql" && -x "$dir/pg_restore" ]]; then
    pgbin="$dir"
  fi
done
if [[ -z "$pgbin" ]] && command -v initdb >/dev/null 2>&1; then
  pgbin="$(dirname "$(command -v initdb)")"
fi
[[ -n "$pgbin" ]] || block DISPOSABLE_POSTGRES_TOOLS
for tool in initdb pg_ctl createdb psql pg_restore; do
  [[ -x "$pgbin/$tool" ]] || block DISPOSABLE_POSTGRES_TOOLS
done
free_kib="$(df -Pk /tmp | awk 'END {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] || block RECOVERY_FREE_SPACE
(( free_kib >= 12582912 )) || block RECOVERY_FREE_SPACE_12GIB
repo="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
[[ -f "$repo/scripts/verify_backup_bundle.sh" ]] || block ARCHIVE_VERIFIER
tmp="$(mktemp -d /tmp/kmj-real-offsite-restore.XXXXXXXX)"
chmod 700 "$tmp"
pg_started=0
cleanup() {
  if (( pg_started )); then
    "$pgbin/pg_ctl" -D "$tmp/pgdata" -m immediate -w stop >/dev/null 2>&1 || :
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
mkdir -m 700 "$tmp/socket" "$tmp/extracted" "$tmp/restored-storage"
status OFFSITE_RETRIEVAL STARTED
if ! rclone copyto "$BACKUP_REMOTE_OBJECT" "$tmp/encrypted.age" \
    --retries 1 --low-level-retries 1 >/dev/null 2>&1; then
  status OFFSITE_RETRIEVAL FAIL; exit 1
fi
[[ -s "$tmp/encrypted.age" ]] || { status OFFSITE_RETRIEVAL FAIL; exit 1; }
status OFFSITE_RETRIEVAL PASS
if ! BACKUP_AGE_IDENTITY="$BACKUP_AGE_IDENTITY" \
    bash "$repo/scripts/verify_backup_bundle.sh" "$tmp/encrypted.age" >/dev/null 2>&1; then
  status BACKUP_ARCHIVE_INTEGRITY FAIL; exit 1
fi
status BACKUP_ARCHIVE_INTEGRITY PASS
if ! age -d -i "$BACKUP_AGE_IDENTITY" -o "$tmp/bundle.tar.gz" \
    "$tmp/encrypted.age" >/dev/null 2>&1; then
  status BUNDLE_DECRYPTION FAIL; exit 1
fi
# A second strict extraction guard limits the decrypted outer archive to
# four regular files. The verifier additionally checks inner tar safety.
if ! python3 - "$tmp/bundle.tar.gz" "$tmp/extracted" <<'PY'
import shutil
import sys
import tarfile
from pathlib import Path
source, dest = Path(sys.argv[1]), Path(sys.argv[2])
expected = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
with tarfile.open(source, "r:gz") as archive:
    members = archive.getmembers()
    if len(members) != 4 or {m.name for m in members} != expected:
        raise SystemExit(1)
    if any(not m.isfile() or m.size <= 0 for m in members):
        raise SystemExit(1)
    for member in members:
        stream = archive.extractfile(member)
        if stream is None:
            raise SystemExit(1)
        with stream, (dest / member.name).open("xb") as output:
            shutil.copyfileobj(stream, output, 1024 * 1024)
PY
then
  status BUNDLE_EXTRACTION FAIL; exit 1
fi
if ! "$pgbin/initdb" -D "$tmp/pgdata" -U kmj_restore_drill \
    --auth-local=trust --auth-host=reject --no-instructions \
    >"$tmp/initdb.log" 2>&1; then
  status DISPOSABLE_POSTGRES_INIT FAIL; exit 1
fi
port=55479
if ! "$pgbin/pg_ctl" -D "$tmp/pgdata" -l "$tmp/postgres.log" \
    -o "-c listen_addresses='' -c unix_socket_directories='$tmp/socket' -c unix_socket_permissions=0700 -c port=$port" \
    -w start >/dev/null 2>&1; then
  status DISPOSABLE_POSTGRES_START FAIL; exit 1
fi
pg_started=1
[[ -S "$tmp/socket/.s.PGSQL.$port" ]] || { status PRIVATE_SOCKET FAIL; exit 1; }
if ! "$pgbin/createdb" -h "$tmp/socket" -p "$port" -U kmj_restore_drill kmj_recovered >/dev/null 2>&1; then
  status DISPOSABLE_DATABASE_CREATION FAIL; exit 1
fi
if ! "$pgbin/pg_restore" --exit-on-error --no-owner --no-acl \
    -h "$tmp/socket" -p "$port" -U kmj_restore_drill -d kmj_recovered \
    "$tmp/extracted/database.dump" >"$tmp/restore.log" 2>&1; then
  status DISPOSABLE_POSTGRES_RESTORE FAIL; exit 1
fi
tables="$("$pgbin/psql" -X -A -t -h "$tmp/socket" -p "$port" \
  -U kmj_restore_drill -d kmj_recovered -v ON_ERROR_STOP=1 \
  -c "select (to_regclass('public.users') is not null and to_regclass('public.organizations') is not null and to_regclass('public.entitlements') is not null)::int" 2>/dev/null)" || {
  status RECOVERED_APP_SCHEMA FAIL; exit 1;
}
[[ "$tables" == 1 ]] || { status RECOVERED_APP_SCHEMA FAIL; exit 1; }
# Storage extraction occurs only after archive integrity and bounded-member verification.
if ! tar -xzf "$tmp/extracted/storage.tar.gz" -C "$tmp/restored-storage" >/dev/null 2>&1; then
  status RECOVERED_STORAGE FAIL; exit 1
fi
[[ -d "$tmp/restored-storage/storage/app" ]] || { status RECOVERED_STORAGE FAIL; exit 1; }
status DISPOSABLE_POSTGRES_RESTORE PASS
status RECOVERED_APP_SCHEMA PASS
status RECOVERED_STORAGE PASS
status POSTGRES_NETWORK_LISTENER DISABLED
status PRODUCTION_DATABASE_MODIFIED NO
status RECOVERED_APP_FUNCTIONAL_QA NOT_VERIFIED
status SMTP_INBOX_DELIVERY NOT_VERIFIED
status OWNER_VISUAL_SIGNOFF NOT_VERIFIED
status MATCHING_PRODUCTION_APPROVAL NOT_VERIFIED
status SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN
\n'* ]] || block REMOTE_OBJECT_SELECTION
remote_name="${BACKUP_REMOTE_OBJECT%%:*}"
remote_path="${BACKUP_REMOTE_OBJECT#*:}"
[[ "$BACKUP_REMOTE_OBJECT" == *:* && "$remote_name" =~ ^[A-Za-z][A-Za-z0-9_-]*$ && -n "$remote_path" ]] || block REMOTE_OBJECT_SELECTION
[[ -n "${BACKUP_AGE_IDENTITY:-}" ]] || block AGE_IDENTITY
[[ -f "$BACKUP_AGE_IDENTITY" && ! -L "$BACKUP_AGE_IDENTITY" ]] || block AGE_IDENTITY
case "$(hostname -s | tr '[:upper:]' '[:lower:]')" in
  kmj-elite|kmj-main-prod-01) block INDEPENDENT_HOST_REQUIRED ;;
esac
for tool in rclone age python3 tar df mktemp; do
  command -v "$tool" >/dev/null 2>&1 || block "MISSING_$tool"
done
# Never inherit connection settings that could reference a production DB.
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
unset DB_URL DATABASE_URL BACKUP_DATABASE_URL
pgbin=''
for dir in /usr/lib/postgresql/*/bin /usr/local/pgsql/bin; do
  if [[ -x "$dir/initdb" && -x "$dir/pg_ctl" && -x "$dir/createdb" &&
        -x "$dir/psql" && -x "$dir/pg_restore" ]]; then
    pgbin="$dir"
  fi
done
if [[ -z "$pgbin" ]] && command -v initdb >/dev/null 2>&1; then
  pgbin="$(dirname "$(command -v initdb)")"
fi
[[ -n "$pgbin" ]] || block DISPOSABLE_POSTGRES_TOOLS
for tool in initdb pg_ctl createdb psql pg_restore; do
  [[ -x "$pgbin/$tool" ]] || block DISPOSABLE_POSTGRES_TOOLS
done
free_kib="$(df -Pk /tmp | awk 'END {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] || block RECOVERY_FREE_SPACE
(( free_kib >= 12582912 )) || block RECOVERY_FREE_SPACE_12GIB
repo="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
[[ -f "$repo/scripts/verify_backup_bundle.sh" ]] || block ARCHIVE_VERIFIER
tmp="$(mktemp -d /tmp/kmj-real-offsite-restore.XXXXXXXX)"
chmod 700 "$tmp"
pg_started=0
cleanup() {
  if (( pg_started )); then
    "$pgbin/pg_ctl" -D "$tmp/pgdata" -m immediate -w stop >/dev/null 2>&1 || :
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
mkdir -m 700 "$tmp/socket" "$tmp/extracted" "$tmp/restored-storage"
status OFFSITE_RETRIEVAL STARTED
if ! rclone copyto "$BACKUP_REMOTE_OBJECT" "$tmp/encrypted.age" \
    --retries 1 --low-level-retries 1 >/dev/null 2>&1; then
  status OFFSITE_RETRIEVAL FAIL; exit 1
fi
[[ -s "$tmp/encrypted.age" ]] || { status OFFSITE_RETRIEVAL FAIL; exit 1; }
status OFFSITE_RETRIEVAL PASS
if ! BACKUP_AGE_IDENTITY="$BACKUP_AGE_IDENTITY" \
    bash "$repo/scripts/verify_backup_bundle.sh" "$tmp/encrypted.age" >/dev/null 2>&1; then
  status BACKUP_ARCHIVE_INTEGRITY FAIL; exit 1
fi
status BACKUP_ARCHIVE_INTEGRITY PASS
if ! age -d -i "$BACKUP_AGE_IDENTITY" -o "$tmp/bundle.tar.gz" \
    "$tmp/encrypted.age" >/dev/null 2>&1; then
  status BUNDLE_DECRYPTION FAIL; exit 1
fi
# A second strict extraction guard limits the decrypted outer archive to
# four regular files. The verifier additionally checks inner tar safety.
if ! python3 - "$tmp/bundle.tar.gz" "$tmp/extracted" <<'PY'
import shutil
import sys
import tarfile
from pathlib import Path
source, dest = Path(sys.argv[1]), Path(sys.argv[2])
expected = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
with tarfile.open(source, "r:gz") as archive:
    members = archive.getmembers()
    if len(members) != 4 or {m.name for m in members} != expected:
        raise SystemExit(1)
    if any(not m.isfile() or m.size <= 0 for m in members):
        raise SystemExit(1)
    for member in members:
        stream = archive.extractfile(member)
        if stream is None:
            raise SystemExit(1)
        with stream, (dest / member.name).open("xb") as output:
            shutil.copyfileobj(stream, output, 1024 * 1024)
PY
then
  status BUNDLE_EXTRACTION FAIL; exit 1
fi
if ! "$pgbin/initdb" -D "$tmp/pgdata" -U kmj_restore_drill \
    --auth-local=trust --auth-host=reject --no-instructions \
    >"$tmp/initdb.log" 2>&1; then
  status DISPOSABLE_POSTGRES_INIT FAIL; exit 1
fi
port=55479
if ! "$pgbin/pg_ctl" -D "$tmp/pgdata" -l "$tmp/postgres.log" \
    -o "-c listen_addresses='' -c unix_socket_directories='$tmp/socket' -c unix_socket_permissions=0700 -c port=$port" \
    -w start >/dev/null 2>&1; then
  status DISPOSABLE_POSTGRES_START FAIL; exit 1
fi
pg_started=1
[[ -S "$tmp/socket/.s.PGSQL.$port" ]] || { status PRIVATE_SOCKET FAIL; exit 1; }
if ! "$pgbin/createdb" -h "$tmp/socket" -p "$port" -U kmj_restore_drill kmj_recovered >/dev/null 2>&1; then
  status DISPOSABLE_DATABASE_CREATION FAIL; exit 1
fi
if ! "$pgbin/pg_restore" --exit-on-error --no-owner --no-acl \
    -h "$tmp/socket" -p "$port" -U kmj_restore_drill -d kmj_recovered \
    "$tmp/extracted/database.dump" >"$tmp/restore.log" 2>&1; then
  status DISPOSABLE_POSTGRES_RESTORE FAIL; exit 1
fi
tables="$("$pgbin/psql" -X -A -t -h "$tmp/socket" -p "$port" \
  -U kmj_restore_drill -d kmj_recovered -v ON_ERROR_STOP=1 \
  -c "select (to_regclass('public.users') is not null and to_regclass('public.organizations') is not null and to_regclass('public.entitlements') is not null)::int" 2>/dev/null)" || {
  status RECOVERED_APP_SCHEMA FAIL; exit 1;
}
[[ "$tables" == 1 ]] || { status RECOVERED_APP_SCHEMA FAIL; exit 1; }
# Storage extraction occurs only after archive integrity and bounded-member verification.
if ! tar -xzf "$tmp/extracted/storage.tar.gz" -C "$tmp/restored-storage" >/dev/null 2>&1; then
  status RECOVERED_STORAGE FAIL; exit 1
fi
[[ -d "$tmp/restored-storage/storage/app" ]] || { status RECOVERED_STORAGE FAIL; exit 1; }
status DISPOSABLE_POSTGRES_RESTORE PASS
status RECOVERED_APP_SCHEMA PASS
status RECOVERED_STORAGE PASS
status POSTGRES_NETWORK_LISTENER DISABLED
status PRODUCTION_DATABASE_MODIFIED NO
status RECOVERED_APP_FUNCTIONAL_QA NOT_VERIFIED
status SMTP_INBOX_DELIVERY NOT_VERIFIED
status OWNER_VISUAL_SIGNOFF NOT_VERIFIED
status MATCHING_PRODUCTION_APPROVAL NOT_VERIFIED
status SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN
