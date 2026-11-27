#!/bin/bash
# KMJ TECHNO 4C9 Google restore: nonroot, exact source, isolated, NO release.
# Staged in google-vps1's authorized CloudOS project. Source-only operator.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
unset DB_URL DATABASE_URL BACKUP_DATABASE_URL
blocked(){ printf 'KMJ_4C9_GOOGLE_RESTORE=BLOCKED_%s\n' "$1"; exit 2; }
mark(){ printf '%s=%s\n' "$1" "$2"; }

readonly CANDIDATE=4c9d59103b99a6cfe675bb7b8961fc956eb294f0
readonly PREDECESSOR=platform-ce6ad7dc9d89
readonly SHORT=4c9d59103b99
readonly SCRIPTS=/home/info/kmj-cloudos/scripts
readonly SCRATCH=/home/info/kmj-recovery-scratch
readonly CIPHER="$SCRATCH/offsite-$SHORT.tar.gz.age"
readonly KEY=/home/info/.local/share/kmj-recovery/google-vps-20261019.agekey
readonly RESTORE=operations/verify-main-platform-google-sftp-restore-20261030.sh
readonly RESTORE_SHA=adbb341ae298dcfb3ec3e017dcd7010ac4fde47b4a46042afcff6f36ef6a75f2
readonly BUNDLE=verify_backup_bundle.sh
readonly BUNDLE_SHA=4e0a7c61f317d1ecacfe6bf8a3c3199bb3fdaaf33b92c23b25e34f45c57de166
readonly PARITY=operations/verify-restored-storage-parity.py
readonly PARITY_SHA=a5cc97d5395f7ab4ed5a0a1f426f13a5dd26cfc575323b213276c5cee1bb9171
readonly IMPORTER=KMJ_4C9_GOOGLE_CIPHER_IMPORT_20261116.py
readonly IMPORTER_SHA=7229c1cdcacab3353a7566636ddd62e4bbdb48d74f65a755ff65c5dd1707be7b

mode=''
encrypted_sha=''
source_sha=''
if [[ "$#" == 1 && "$1" == --inspect ]]; then
    mode=inspect
elif [[ "$#" == 5 && "$1" == --restore && "$2" == --encrypted-sha256 && "$4" == --source-local-sha256 ]]; then
    mode=restore
    encrypted_sha=$3
    source_sha=$5
    [[ "$encrypted_sha" =~ ^[a-f0-9]{64}$ && "$source_sha" =~ ^[a-f0-9]{64}$ ]] ||
        blocked EXACT_DIGEST_ARGS
else
    blocked EXACT_MODE_AND_DIGEST_ARGS
fi

[[ "$(hostname -s)" == google-vps1 && "$(id -un)" == info && "$(id -u)" != 0 && "$HOME" == /home/info ]] ||
    blocked GOOGLE_NONROOT_IDENTITY
[[ -d /home/info && ! -L /home/info ]] || blocked HOME_UNSAFE
[[ -d "$SCRIPTS" && ! -L "$SCRIPTS" ]] || blocked SCRIPT_ROOT_MISSING
[[ -d "$SCRIPTS/operations" && ! -L "$SCRIPTS/operations" ]] || blocked OPERATIONS_ROOT_MISSING
[[ -d "$SCRATCH" && ! -L "$SCRATCH" && "$(stat -c '%u:%a' "$SCRATCH")" == "$(id -u):700" ]] ||
    blocked SCRATCH_NOT_USER_PRIVATE
[[ -f "$KEY" && ! -L "$KEY" && "$(stat -c '%u:%a:%h' "$KEY")" == "$(id -u):600:1" ]] ||
    blocked PRIVATE_IDENTITY_NOT_READY

checked(){
    local source="$1" digest="$2" mode owner links actual
    [[ -f "$source" && ! -L "$source" ]] || blocked SOURCE_MISSING_OR_SYMLINK
    owner="$(stat -c '%u' -- "$source")" || blocked SOURCE_METADATA
    mode="$(stat -c '%a' -- "$source")" || blocked SOURCE_METADATA
    links="$(stat -c '%h' -- "$source")" || blocked SOURCE_METADATA
    [[ "$owner" == "$(id -u)" && "$links" == 1 && "$mode" =~ ^[0-7]{3,4}$ ]] ||
        blocked SOURCE_OWNER_OR_LINKS
    (( (8#$mode & 8#022) == 0 )) || blocked SOURCE_WRITABLE_BY_OTHERS
    actual="$(sha256sum -- "$source" | cut -d' ' -f1)" || blocked SOURCE_SHA_READ
    [[ "$actual" == "$digest" ]] || blocked SOURCE_SHA_MISMATCH
}
checked "$SCRIPTS/$RESTORE" "$RESTORE_SHA"
checked "$SCRIPTS/$BUNDLE" "$BUNDLE_SHA"
checked "$SCRIPTS/$PARITY" "$PARITY_SHA"
checked "$SCRIPTS/$IMPORTER" "$IMPORTER_SHA"
mark KMJ_GOOGLE_SOURCE_HASHES 4_PASS
mark CANDIDATE_SHA "$CANDIDATE"
mark CURRENT_RELEASE_EXPECTED "$PREDECESSOR"

if [[ "$mode" == inspect ]]; then
    if [[ -f "$CIPHER" && ! -L "$CIPHER" && "$(stat -c '%u:%a:%h' "$CIPHER")" == "$(id -u):600:1" ]]; then
        mark IMPORTED_CIPHER PRESENT_UNATTESTED
    else
        mark IMPORTED_CIPHER MISSING_OR_UNSAFE
    fi
    mark ENCRYPTED_SHA EVIDENCE_REQUIRED
    mark SOURCE_LOCAL_SHA EVIDENCE_REQUIRED
    mark DISPOSABLE_GOOGLE_RESTORE NOT_ATTEMPTED
    mark PRODUCTION_ACTIVATION NOT_ATTEMPTED
    exit 0
fi

# Digest values must come from independently reviewed Elite seal + transfer
# receipts; caller input is NOT a trusted attestation by itself.
# Attempt only exact name+SHA no-overwrite import from Google's private vault.
/usr/bin/python3 -I -B "$SCRIPTS/$IMPORTER" --encrypted-sha256 "$encrypted_sha" ||
    blocked EXACT_VAULT_CIPHER_IMPORT
[[ -f "$CIPHER" && ! -L "$CIPHER" && "$(stat -c '%u:%a:%h' "$CIPHER")" == "$(id -u):600:1" ]] ||
    blocked CIPHER_IMPORT_NOT_PRIVATE
bytes="$(stat -c '%s' "$CIPHER")" || blocked CIPHER_SIZE
[[ "$bytes" =~ ^[0-9]+$ ]] && (( bytes >= 256 && bytes <= 10737418240 )) ||
    blocked CIPHER_SIZE_BOUNDS
actual="$(sha256sum -- "$CIPHER" | cut -d' ' -f1)" || blocked CIPHER_SHA_READ
[[ "$actual" == "$encrypted_sha" ]] || blocked CIPHER_SHA_MISMATCH
for tool in /usr/bin/age /usr/bin/bwrap /usr/bin/python3 /usr/bin/sha256sum /usr/bin/mktemp /usr/bin/install; do
    [[ -x "$tool" ]] || blocked RESTORE_DEPENDENCY_MISSING
done
free_kib="$(df -Pk "$SCRATCH" | awk 'END {print $4}')" || blocked SCRATCH_SPACE
[[ "$free_kib" =~ ^[0-9]+$ ]] && (( free_kib >= 12582912 )) ||
    blocked SCRATCH_SPACE_BELOW_12GIB

# Make one private repo-shaped snapshot so source cannot drift between SHA
# validation and inner isolated execution. Never copy AGE key or ciphertext.
work="$(mktemp -d "$SCRATCH/kmj-4c9-verify.XXXXXXXX")" || blocked PRIVATE_WORKDIR
[[ -d "$work" && ! -L "$work" && "$(stat -c '%u:%a' "$work")" == "$(id -u):700" ]] ||
    blocked PRIVATE_WORKDIR_METADATA
cleanup(){
    [[ -n "$work" && -d "$work" && ! -L "$work" ]] || return 0
    rm -f -- "$work/repo/scripts/operations/verify-main-platform-google-sftp-restore-20261030.sh" \
        "$work/repo/scripts/operations/verify-restored-storage-parity.py" \
        "$work/repo/scripts/verify_backup_bundle.sh"
    rmdir -- "$work/repo/scripts/operations" "$work/repo/scripts" "$work/repo" "$work" 2>/dev/null || :
}
trap cleanup EXIT
mkdir -m 0700 -- "$work/repo" "$work/repo/scripts" "$work/repo/scripts/operations"
install -m 0500 -T -- "$SCRIPTS/$RESTORE" "$work/repo/scripts/$RESTORE" || blocked SNAPSHOT_INSTALL
install -m 0500 -T -- "$SCRIPTS/$BUNDLE" "$work/repo/scripts/$BUNDLE" || blocked SNAPSHOT_INSTALL
install -m 0500 -T -- "$SCRIPTS/$PARITY" "$work/repo/scripts/$PARITY" || blocked SNAPSHOT_INSTALL
checked "$work/repo/scripts/$RESTORE" "$RESTORE_SHA"
checked "$work/repo/scripts/$BUNDLE" "$BUNDLE_SHA"
checked "$work/repo/scripts/$PARITY" "$PARITY_SHA"

mark CIPHER_SHA256 EXACT_MATCH
mark GOOGLE_SANDBOX_ENGINE STARTED_NO_PRODUCTION_DB
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/info TMPDIR="$SCRATCH" \
    KMJ_ACK_ISOLATED_RECOVERY=YES \
    KMJ_EXPECTED_ENCRYPTED_SHA256="$encrypted_sha" \
    KMJ_EXPECTED_SOURCE_LOCAL_SHA256="$source_sha" \
    /bin/bash "$work/repo/scripts/$RESTORE" --candidate-sha "$CANDIDATE" --expected-release "$PREDECESSOR" ||
    blocked ISOLATED_RESTORE_ENGINE_FAILED
mark KMJ_4C9_GOOGLE_RESTORE ISOLATED_ENGINE_EXIT_0
mark RECEIPT_IDENTITY OPERATOR_SUPPLIED_NOT_INDEPENDENTLY_ATTESTED
mark STAGING_APPROVAL UNCHANGED
mark PROTECTED_APPROVAL UNCHANGED
mark PRODUCTION_ACTIVATION NOT_ATTEMPTED
