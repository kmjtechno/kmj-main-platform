#!/bin/bash -p
# KMJ TECHNO P0: CE6 -> PR884 exact candidate preparation ONLY.
# Isolated source build, local DB/uploads restore, encrypted Google SFTP readback.
# No protected approval write, staging change, production cutover or rollback.
# Usage (operator on KMJ-elite): bash -p <this-file> --inspect | --prepare
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
unset DB_URL DATABASE_URL BACKUP_DATABASE_URL
fail() { printf 'KMJ_PR884_OWNER_PREPARE=BLOCKED_%s\n' "$1"; exit 2; }
mark() { printf '%s=%s\n' "$1" "$2"; }

[[ "$#" -eq 1 && ( "$1" == --inspect || "$1" == --prepare ) ]] || fail EXACT_MODE
[[ $- == *p* ]] || fail PRIVILEGED_BASH_REQUIRED
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail ROOT_ELITE_ONLY

readonly TARGET_SHA=4c9d59103b99a6cfe675bb7b8961fc956eb294f0
readonly PREVIOUS_SHA=ce6ad7dc9d898dce1ba9561a0e221f8ad750180f
readonly PREVIOUS_RELEASE=platform-ce6ad7dc9d89
readonly TARGET_RELEASE=platform-4c9d59103b99
readonly LIVE=/home/kmjprod/current
readonly ROOT=/home/kmjprod
readonly SOURCE_ROOT=/srv/kmj-codebridge-projects/kmj-main-platform
readonly ONEPASS_SOURCE="$SOURCE_ROOT/scripts/KMJ_B07_OWNER_ONEPASS_BUILD_BACKUP_OFFSITE_20261104.sh"
readonly ONEPASS_SHA256=0070697927babaa9a9035ebadcffe9a07311c12bcc4fbbd7a5a9d024cbc00dd3
readonly WITNESS="/var/backups/kmj-platform/pre-deploy-4c9d59103b99.json"
readonly BACKUP="/var/backups/kmj-platform/pre-deploy-4c9d59103b99.tar.gz"

[[ -L "$LIVE" ]] || fail LIVE_POINTER_MISSING
current="$(readlink -f -- "$LIVE")" || fail LIVE_POINTER_UNRESOLVED
[[ "$current" == "$ROOT/releases/$PREVIOUS_RELEASE" ]] || fail LIVE_PREDECESSOR_MISMATCH
[[ -d "$current/apps/platform" && ! -L "$current/apps/platform" ]] || fail LIVE_TREE_INVALID
live_sha="$(runuser -u kmjprod -- /usr/bin/git -C "$current" rev-parse HEAD 2>/dev/null)" ||
    fail LIVE_GIT_UNREADABLE
[[ "$live_sha" == "$PREVIOUS_SHA" ]] || fail LIVE_SHA_MISMATCH

mark LIVE_RELEASE "$PREVIOUS_RELEASE"
mark LIVE_SOURCE_SHA "$PREVIOUS_SHA"
mark CANDIDATE_SHA "$TARGET_SHA"
mark PREPARATION_MODE "$1"

# Even the read-only mode never equates existing backup files with a verified
# remote decrypt/restore. These require separate independent Google evidence.
if [[ "$1" == --inspect ]]; then
    [[ -f "$ONEPASS_SOURCE" && ! -L "$ONEPASS_SOURCE" ]] || fail ONEPASS_SOURCE_MISSING
    [[ "$(sha256sum -- "$ONEPASS_SOURCE" | cut -d ' ' -f1)" == "$ONEPASS_SHA256" ]] ||
        fail ONEPASS_SHA_MISMATCH
    mark ONEPASS_SOURCE_SHA256 PASS
    mark CANDIDATE_PRESENT "$([[ -e "$ROOT/releases/$TARGET_RELEASE" || -L "$ROOT/releases/$TARGET_RELEASE" ]] && echo YES || echo NO)"
    mark LOCAL_BACKUP_PRESENT "$([[ -f "$BACKUP" && -f "$WITNESS" ]] && echo YES || echo NO)"
    mark GOOGLE_INDEPENDENT_RESTORE NOT_VERIFIED
    mark PHYSICAL_ROLLBACK_DRILL NOT_VERIFIED
    mark PROTECTED_APPROVAL UNCHANGED
    mark PRODUCTION_ACTIVATION NOT_ATTEMPTED
    exit 0
fi

# No rebuilding/overwriting a partial candidate or old receipts. Existing data
# must be reconciled by the owner rather than silently destroyed or reused.
[[ ! -e "$ROOT/releases/$TARGET_RELEASE" && ! -L "$ROOT/releases/$TARGET_RELEASE" ]] ||
    fail EXISTING_CANDIDATE_REQUIRES_REVIEW
[[ ! -e "$WITNESS" && ! -L "$WITNESS" && ! -e "$BACKUP" && ! -L "$BACKUP" ]] ||
    fail EXISTING_BACKUP_REQUIRES_REVIEW
[[ -f "$ONEPASS_SOURCE" && ! -L "$ONEPASS_SOURCE" ]] || fail ONEPASS_SOURCE_MISSING
# The B07 build operator checks GitHub main itself. Require the same protected
# target here, while permitting the CodeBridge development checkout to lag main.
# Neither a PR SHA nor a local dirty branch may be treated as release authority.
remote_main="$(/usr/bin/git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/main 2>/dev/null | /usr/bin/awk '{print $1}')" ||
    fail REMOTE_MAIN_UNAVAILABLE
[[ "$remote_main" == "$TARGET_SHA" ]] || fail REMOTE_MAIN_MISMATCH
[[ "$(sha256sum -- "$ONEPASS_SOURCE" | cut -d ' ' -f1)" == "$ONEPASS_SHA256" ]] ||
    fail ONEPASS_SHA_MISMATCH
[[ -d /run && ! -L /run && "$(stat -c '%u' /run)" == 0 ]] || fail RUN_DIR_UNTRUSTED

# Copy and verify the executable bytes into a new root-only private scratch
# before invoking the already-reviewed bounded owner operator.
scratch="$(mktemp -d /run/kmj-pr884-prepare.XXXXXXXX)" || fail PRIVATE_SCRATCH
[[ -d "$scratch" && ! -L "$scratch" && "$(stat -c '%u:%a' "$scratch")" == 0:700 ]] ||
    fail SCRATCH_METADATA
cleanup() {
    [[ -n "$scratch" && -d "$scratch" && ! -L "$scratch" ]] || return 0
    [[ -f "$scratch/pinned-onepass.sh" && ! -L "$scratch/pinned-onepass.sh" ]] &&
        /usr/bin/rm -f -- "$scratch/pinned-onepass.sh"
    /usr/bin/rmdir -- "$scratch" 2>/dev/null || :
}
trap cleanup EXIT
install -o root -g root -m 0500 -T -- "$ONEPASS_SOURCE" "$scratch/pinned-onepass.sh" ||
    fail PRIVATE_COPY
[[ "$(sha256sum -- "$scratch/pinned-onepass.sh" | cut -d ' ' -f1)" == "$ONEPASS_SHA256" ]] ||
    fail PRIVATE_COPY_SHA

/bin/bash -p "$scratch/pinned-onepass.sh" --candidate-sha "$TARGET_SHA" --expected-release "$PREVIOUS_RELEASE" ||
    fail PINNED_PREPARATION_FAILED
[[ "$(readlink -f -- "$LIVE")" == "$ROOT/releases/$PREVIOUS_RELEASE" ]] ||
    fail LIVE_MOVED_DURING_PREPARATION
[[ -d "$ROOT/releases/$TARGET_RELEASE/.git" ]] || fail CANDIDATE_OUTPUT_MISSING
[[ "$(runuser -u kmjprod -- /usr/bin/git -C "$ROOT/releases/$TARGET_RELEASE" rev-parse HEAD 2>/dev/null)" == "$TARGET_SHA" ]] ||
    fail CANDIDATE_OUTPUT_SHA

# Independently hash the actual local archive against the root-only witness.
# No path follows symlinks, receipts or secrets are printed.
python3 -I -B - "$WITNESS" "$BACKUP" "$TARGET_SHA" "$PREVIOUS_RELEASE" <<'PY'
import hashlib, json, os, re, stat, sys
witness, archive, target, previous = sys.argv[1:]
def checked(path, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077 or not 0 < st.st_size <= maximum:
            raise ValueError("unsafe_file")
        h = hashlib.sha256()
        with os.fdopen(os.dup(fd), "rb") as src:
            while data := src.read(1024 * 1024):
                h.update(data)
        return h.hexdigest()
    finally:
        os.close(fd)
data_fd = os.open(witness, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
try:
    st = os.fstat(data_fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077 or not 0 < st.st_size <= 4096:
        raise ValueError("witness_metadata")
    body = os.read(data_fd, 4097)
finally:
    os.close(data_fd)
def unique(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise ValueError("duplicate_key")
        d[k] = v
    return d
record = json.loads(body.decode("utf-8"), object_pairs_hook=unique)
if (not isinstance(record, dict)
    or set(record) != {"approvedSha", "currentRelease", "backupSha256"}
    or record["approvedSha"] != target
    or record["currentRelease"] != previous
    or not isinstance(record["backupSha256"], str)
    or re.fullmatch("[0-9a-f]{64}", record["backupSha256"]) is None
    or checked(archive, 20 * 1024 ** 3) != record["backupSha256"]):
    raise ValueError("witness_mismatch")
print("KMJ_LOCAL_BACKUP_WITNESS=PASS")
PY
[[ "$(readlink -f -- "$LIVE")" == "$ROOT/releases/$PREVIOUS_RELEASE" ]] ||
    fail LIVE_MOVED_AFTER_BACKUP
mark CANDIDATE_PREPARATION LOCAL_BACKUP_AND_ENCRYPTED_SFTP_READBACK_ENGINE_PASS
mark GOOGLE_INDEPENDENT_RESTORE NOT_VERIFIED
mark PHYSICAL_ROLLBACK_DRILL NOT_VERIFIED
mark PROTECTED_APPROVAL UNCHANGED
mark PRODUCTION_ACTIVATION NOT_ATTEMPTED
mark KMJ_PR884_OWNER_PREPARE DONE_NO_CUTOVER
