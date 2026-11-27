#!/usr/bin/env bash
# Google VPS operator-only, SHA-pinned encrypted SFTP import + disposable PostgreSQL restore.
# No production DB connection, deployment, DNS, application or secret mutation.
set -Eeuo pipefail
umask 077
export GIT_OPTIONAL_LOCKS=0
status() { printf '%s=%s\n' "$1" "$2"; }
block() { status "$1" BLOCKED; exit 2; }

[[ "$(id -u)" != 0 && "$(id -un)" == info ]] || block NONROOT_INFO_REQUIRED
[[ "$(hostname -s)" == google-vps1 ]] || block GOOGLE_RECOVERY_HOST_REQUIRED
[[ "${KMJ_ACK_ISOLATED_RECOVERY:-}" == YES ]] || block OPERATOR_CONSENT
[[ -n "${HOME:-}" && -d "$HOME" && ! -L "$HOME" ]] || block RECOVERY_HOME_UNSAFE
# This exact SHA-256 is independently evidenced by owner KMJ-elite on 2026-10-27.
# The operator must first SFTP-import the encrypted bytes over trusted SSH.
expected_hash=ea4fd973d4bdc678fae6df5368956be283f8bd335788d68d268dd448218d7d8f
encrypted="$HOME/kmj-recovery-scratch/offsite-fe4045acd08d.tar.gz.age"
BACKUP_AGE_IDENTITY="$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey"
[[ -f "$BACKUP_AGE_IDENTITY" && ! -L "$BACKUP_AGE_IDENTITY" ]] || block AGE_IDENTITY
[[ "$(stat -c '%u' -- "$BACKUP_AGE_IDENTITY")" == "$(id -u)" ]] || block AGE_IDENTITY_OWNER
[[ "$(stat -c '%a' -- "$BACKUP_AGE_IDENTITY")" == 600 ]] || block AGE_IDENTITY_MODE
for tool in age python3 tar df mktemp sha256sum; do
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
# /tmp can be a small RAM-backed tmpfs on cloud VMs. Use ONLY an
# operator-prepared private persistent scratch directory. This is also passed
# to the nested archive verifier, whose mktemp must use the same disk.
[[ -n "${HOME:-}" && -d "$HOME" && ! -L "$HOME" ]] || block RECOVERY_HOME_UNSAFE
scratch="$HOME/kmj-recovery-scratch"
[[ -d "$scratch" && ! -L "$scratch" ]] || block RECOVERY_SCRATCH_NOT_READY
[[ "$(stat -c '%u' -- "$scratch")" == "$(id -u)" ]] || block RECOVERY_SCRATCH_OWNER
[[ "$(stat -c '%a' -- "$scratch")" == 700 ]] || block RECOVERY_SCRATCH_MODE_700
[[ "$(stat -c '%d' -- "$scratch")" == "$(stat -c '%d' -- "$HOME")" ]] ||
  block RECOVERY_SCRATCH_DEVICE_MISMATCH
free_kib="$(df -Pk "$scratch" | awk 'END {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] || block RECOVERY_FREE_SPACE
(( free_kib >= 12582912 )) || block RECOVERY_FREE_SPACE_12GIB
export TMPDIR="$scratch"
readonly verify_script="$(cd -- "$(dirname -- "$0")" && pwd)/KMJ_P0_FE4045_VERIFY_BACKUP_BUNDLE_20261027.sh"
[[ -s "$verify_script" && ! -L "$verify_script" ]] || block ARCHIVE_VERIFIER
tmp="$(mktemp -d "$scratch/kmj-real-offsite-restore.XXXXXXXX")"
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
# Local SFTP-import mode. Never label a local import a remote rclone retrieval.
[[ -f "$encrypted" && ! -L "$encrypted" && -s "$encrypted" ]] || block SFTP_IMPORT_MISSING
[[ "$(stat -c '%u' -- "$encrypted")" == "$(id -u)" ]] || block SFTP_IMPORT_OWNER
[[ "$(stat -c '%a' -- "$encrypted")" == 600 ]] || block SFTP_IMPORT_MODE
digest="$(sha256sum -- "$encrypted" | cut -d' ' -f1)"
[[ "$digest" == "$expected_hash" ]] || block SFTP_IMPORT_DIGEST
status SFTP_IMPORTED_ENCRYPTED_SHA256 PASS
if ! cp --no-preserve=all -- "$encrypted" "$tmp/encrypted.age"; then
  status SFTP_IMPORT_COPY FAIL; exit 1
fi
[[ "$(sha256sum -- "$tmp/encrypted.age" | cut -d' ' -f1)" == "$expected_hash" ]] ||
  block SFTP_IMPORT_COPY_DIGEST
status SFTP_IMPORT_COPY PASS
status OFFSITE_RCLONE_RETRIEVAL NOT_ATTEMPTED
if ! BACKUP_AGE_IDENTITY="$BACKUP_AGE_IDENTITY" \
    bash "$verify_script" "$tmp/encrypted.age" >/dev/null 2>&1; then
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
status GOOGLE_VPS_INDEPENDENT_RESTORE PASS
status OFFSITE_REMOTE_ARCHIVE_RETENTION NOT_VERIFIED
status RESTORE_CANDIDATE_SHA fe4045acd08d50a7438dbfc6fee0610b02e1df50
