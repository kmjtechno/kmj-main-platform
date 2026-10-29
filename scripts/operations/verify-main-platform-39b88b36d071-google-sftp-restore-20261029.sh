#!/usr/bin/env bash
# Google VPS operator-only, SHA-pinned encrypted SFTP import + disposable PostgreSQL restore.
# No production DB connection, deployment, DNS, application or secret mutation.
set -Eeuo pipefail
umask 077
status() { printf '%s=%s\n' "$1" "$2"; }
block() { status "$1" BLOCKED; exit 2; }

[[ "$(id -u)" != 0 && "$(id -un)" == info ]] || block NONROOT_INFO_REQUIRED
[[ "$(hostname -s)" == google-vps1 ]] || block GOOGLE_RECOVERY_HOST_REQUIRED
[[ "${KMJ_ACK_ISOLATED_RECOVERY:-}" == YES ]] || block OPERATOR_CONSENT
[[ -n "${HOME:-}" && -d "$HOME" && ! -L "$HOME" ]] || block RECOVERY_HOME_UNSAFE
# The expected SHA-256 comes from the KMJ-elite sealing receipt
# (ENCRYPTED_SHA256=...) and must be evidenced independently of this host.
# It is a 64-hex value only; anything else blocks. The operator must first
# SFTP-import the encrypted bytes over trusted SSH.
expected_hash="${KMJ_EXPECTED_ENCRYPTED_SHA256:-}"
[[ "$expected_hash" =~ ^[0-9a-f]{64}$ ]] || block EXPECTED_ENCRYPTED_SHA256
encrypted="$HOME/kmj-recovery-scratch/offsite-39b88b36d071.tar.gz.age"
BACKUP_AGE_IDENTITY="$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey"
[[ -f "$BACKUP_AGE_IDENTITY" && ! -L "$BACKUP_AGE_IDENTITY" ]] || block AGE_IDENTITY
[[ "$(stat -c '%u' -- "$BACKUP_AGE_IDENTITY")" == "$(id -u)" ]] || block AGE_IDENTITY_OWNER
[[ "$(stat -c '%a' -- "$BACKUP_AGE_IDENTITY")" == 600 ]] || block AGE_IDENTITY_MODE
# pg_restore/SQL from a dump can run programs and open files as this user (the
# disposable role is a superuser), and a disabled TCP listener is not OS
# isolation. The whole database phase therefore runs inside a bubblewrap
# sandbox: no network namespace access, read-only filesystem, home hidden,
# only this run's scratch directory writable. No sandbox => BLOCKED.
for tool in age python3 tar df mktemp sha256sum bwrap; do
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
repo="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
[[ -f "$repo/scripts/verify_backup_bundle.sh" ]] || block ARCHIVE_VERIFIER
tmp="$(mktemp -d "$scratch/kmj-real-offsite-restore.XXXXXXXX")"
chmod 700 "$tmp"
cleanup() {
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
# Bind the decrypted bundle to THIS candidate before trusting its contents:
# exact metadata keys, target/current release, env exclusion and the digest of
# the root-witnessed local source archive (from the sealing receipt).
expected_source_sha=bbf95ca55df0b031f8e875540a476973c5a58bad1ec89fea8e9e2a5a7cc45cdd
if ! python3 - "$tmp/extracted/metadata.txt" "$expected_source_sha" <<'PY'
import sys
lines = open(sys.argv[1], encoding="ascii").read().splitlines()
want = {
    "backup_kind": "offsite_sanitized_local_witness",
    "source_local_sha256": sys.argv[2],
    "target_sha": "39b88b36d071d3f78f2392d609d3febc2c530165",
    "current_release": "platform-574e443a2c75",
    "production_env_excluded": "YES",
}
got = {}
for line in lines:
    key, sep, value = line.partition("=")
    if not sep or key in got:
        raise SystemExit(1)
    got[key] = value
raise SystemExit(0 if got == want else 1)
PY
then
  status BUNDLE_METADATA_BINDING FAIL; exit 1
fi
status BUNDLE_METADATA_BINDING PASS

cat >"$tmp/db-phase.sh" <<'INNER'
#!/usr/bin/env bash
set -Eeuo pipefail
pgbin=$1; work=$2; port=$3
stage() { printf 'STAGE=%s\n' "$1" >"$work/db.stage"; }
trap '"$pgbin/pg_ctl" -D "$work/pgdata" -m immediate -w stop >/dev/null 2>&1 || :' EXIT
stage DISPOSABLE_POSTGRES_INIT
"$pgbin/initdb" -D "$work/pgdata" -U kmj_restore_drill --auth-local=trust --auth-host=reject --no-instructions >"$work/initdb.log" 2>&1
stage DISPOSABLE_POSTGRES_START
"$pgbin/pg_ctl" -D "$work/pgdata" -l "$work/postgres.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$work/socket' -c unix_socket_permissions=0700 -c port=$port" \
  -w start >/dev/null 2>&1
[[ -S "$work/socket/.s.PGSQL.$port" ]]
stage DISPOSABLE_DATABASE_CREATION
"$pgbin/createdb" -h "$work/socket" -p "$port" -U kmj_restore_drill kmj_recovered >/dev/null 2>&1
stage DISPOSABLE_POSTGRES_RESTORE
"$pgbin/pg_restore" --exit-on-error --no-owner --no-acl -h "$work/socket" -p "$port" \
  -U kmj_restore_drill -d kmj_recovered "$work/extracted/database.dump" >"$work/restore.log" 2>&1
stage RECOVERED_APP_SCHEMA
tables=$("$pgbin/psql" -X -A -t -h "$work/socket" -p "$port" -U kmj_restore_drill -d kmj_recovered -v ON_ERROR_STOP=1 \
  -c "select (to_regclass('public.users') is not null and to_regclass('public.organizations') is not null and to_regclass('public.entitlements') is not null)::int" 2>/dev/null)
[[ "$tables" == 1 ]]
stage DONE
INNER
chmod 700 "$tmp/db-phase.sh"
sandbox=(bwrap --unshare-all --die-with-parent --new-session --cap-drop ALL
  --ro-bind / / --proc /proc --dev /dev --tmpfs "$HOME" --bind "$tmp" "$tmp")
if ! "${sandbox[@]}" bash "$tmp/db-phase.sh" "$pgbin" "$tmp" 55479 >/dev/null 2>&1; then
  stage_name="$(sed -n 's/^STAGE=//p' "$tmp/db.stage" 2>/dev/null | tail -1)"
  [[ "$stage_name" =~ ^[A-Z_]+$ ]] || stage_name=DISPOSABLE_POSTGRES_SANDBOX
  status "$stage_name" FAIL; exit 1
fi
[[ "$(sed -n 's/^STAGE=//p' "$tmp/db.stage" 2>/dev/null | tail -1)" == DONE ]] ||
  { status DISPOSABLE_POSTGRES_SANDBOX FAIL; exit 1; }
status DATABASE_PHASE_OS_SANDBOX PASS
# Storage extraction occurs only after archive integrity and bounded-member verification.
if ! tar -xzf "$tmp/extracted/storage.tar.gz" --no-same-owner --no-same-permissions -C "$tmp/restored-storage" >/dev/null 2>&1; then
  status RECOVERED_STORAGE FAIL; exit 1
fi
[[ -d "$tmp/restored-storage/storage/app" ]] || { status RECOVERED_STORAGE FAIL; exit 1; }
# Extraction parity: every regular file and directory listed in the archive
# exists on disk with the same size, and nothing else (no symlinks/specials,
# no extra or missing entries). Counts only; no file names or contents printed.
if ! parity="$(python3 - "$tmp/extracted/storage.tar.gz" "$tmp/restored-storage" <<'PY'
import hashlib, os, stat, sys, tarfile
archive, root = sys.argv[1], sys.argv[2]
def sha(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()
expected = {}
with tarfile.open(archive, "r:gz") as tar:
    for m in tar:
        if m.isdir():
            expected[m.name.rstrip("/")] = ("d", 0)
        elif m.isfile():
            with tar.extractfile(m) as stream:
                expected[m.name] = ("f", m.size, sha(stream))
        else:
            raise SystemExit(1)
# tar -C app storage/app has no "storage" entry; parents are implicit.
for name in list(expected):
    parent = os.path.dirname(name)
    while parent:
        expected.setdefault(parent, ("d", 0))
        parent = os.path.dirname(parent)
found = {}
for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    for name in dirnames + filenames:
        full = os.path.join(dirpath, name)
        rel = os.path.relpath(full, root)
        info = os.lstat(full)
        if stat.S_ISDIR(info.st_mode):
            found[rel] = ("d", 0)
        elif stat.S_ISREG(info.st_mode):
            with open(full, "rb") as stream:
                found[rel] = ("f", info.st_size, sha(stream))
        else:
            raise SystemExit(1)
if found != expected:
    raise SystemExit(1)
files = sum(1 for v in found.values() if v[0] == "f")
print(f"{files} {sum(v[1] for v in found.values())}")
PY
)"; then
  status STORAGE_EXTRACTION_PARITY_CONTENT_SHA256 FAIL; exit 1
fi
status STORAGE_EXTRACTION_PARITY_CONTENT_SHA256 PASS
status STORAGE_REGULAR_FILES "${parity% *}"
status STORAGE_BYTES "${parity#* }"
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
status RESTORE_CANDIDATE_SHA 39b88b36d071d3f78f2392d609d3febc2c530165
