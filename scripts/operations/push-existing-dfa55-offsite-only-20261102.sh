#!/bin/bash -p
# P0 owner-only transfer of the EXISTING dfa55 AGE ciphertext; no fresh backup.
# Fixed candidate, source bytes, archive digest, size and current production.
# The pinned uploader enforces host-key fingerprint, one SSH identity, SFTP
# no-clobber publication, mode 0600 and downloaded SHA-256 readback.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
block() { printf 'KMJ_EXISTING_OFFSITE_ONLY=BLOCKED_%s\n' "$1"; exit 2; }
[[ $- == *p* ]] || block PRIVILEGED_BASH_REQUIRED
[[ $# -eq 0 ]] || block NO_ARGUMENTS
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || block OWNER_HOST

readonly CANDIDATE=dfa55d24b7cc5a0d1e0b0f28832d1f46acc9d031
readonly ARCHIVE=/var/backups/kmj-platform/offsite-dfa55d24b7cc.tar.gz.age
readonly ARCHIVE_SHA=fb333fd5fba4b64a8619e405b914ba171235318f435053e2203d1353407de5cc
readonly EXPECTED_PROD=/home/kmjprod/releases/platform-574e443a2c75
readonly LIVE=/home/kmjprod/current
readonly UPLOADER_COMMIT=68151bcf135991a610ff7eceac25bacf6114b8d9
readonly UPLOADER_SHA=c2fbaa2e969ff0fdfcf0ce88b4edb32e3260e59d568ef1411721026a28ef45dc

protected_chain() {
  local d="$1" mode
  while :; do
    [[ -d "$d" && ! -L "$d" && "$(stat -c %u -- "$d")" == 0 ]] || return 1
    mode="$(stat -c %a -- "$d")" || return 1
    (( (8#$mode & 8#022) == 0 )) || return 1
    [[ "$d" == / ]] && return 0
    d="$(dirname -- "$d")"
  done
}
protected_chain "$(dirname -- "$ARCHIVE")" || block ARCHIVE_PATH_CHAIN
protected_chain /etc/kmj-codebridge || block CONFIG_PATH_CHAIN
[[ -f "$ARCHIVE" && ! -L "$ARCHIVE" ]] || block ARCHIVE_MISSING_OR_LINKED
[[ "$(stat -c '%u:%a:%h:%s' -- "$ARCHIVE")" == '0:600:1:290397' ]] || block ARCHIVE_METADATA
[[ -f /etc/kmj-codebridge/offsite-sftp.conf && ! -L /etc/kmj-codebridge/offsite-sftp.conf ]] || block CONFIG_MISSING
[[ "$(stat -c '%u:%a:%h' -- /etc/kmj-codebridge/offsite-sftp.conf)" == '0:600:1' ]] || block CONFIG_METADATA
[[ -L "$LIVE" && "$(readlink -f -- "$LIVE")" == "$EXPECTED_PROD" ]] || block PRODUCTION_POINTER_DRIFT
[[ "$(sha256sum -- "$ARCHIVE" | cut -d ' ' -f1)" == "$ARCHIVE_SHA" ]] || block ARCHIVE_SHA256_MISMATCH
printf 'KMJ_EXISTING_ARCHIVE_SHA256=PASS\n'

work="$(mktemp -d /root/kmj-existing-offsite.XXXXXXXX)" || block SCRATCH_CREATE
[[ -d "$work" && ! -L "$work" && "$(stat -c '%u:%a' -- "$work")" == '0:700' ]] || block SCRATCH_METADATA
trap 'rm -rf -- "$work"' EXIT
readonly SOURCE="https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/$UPLOADER_COMMIT/scripts/operations/push-offsite-pinned-sftp-20261030.sh"
curl -fsSL --proto '=https' --tlsv1.2 --max-time 45 --retry 2 "$SOURCE" -o "$work/uploader.sh" || block UPLOADER_FETCH
[[ "$(sha256sum -- "$work/uploader.sh" | cut -d ' ' -f1)" == "$UPLOADER_SHA" ]] || block UPLOADER_SHA256
printf 'KMJ_PINNED_SFTP_UPLOADER_SHA256=PASS\n'
# Only the transfer is run. No candidate build, pg_dump, seal or restore.
# /bin/bash -p is required; a plain bash invocation rejects privileged mode.
/bin/bash -p "$work/uploader.sh" --candidate-sha "$CANDIDATE"
[[ -L "$LIVE" && "$(readlink -f -- "$LIVE")" == "$EXPECTED_PROD" ]] || block PRODUCTION_POINTER_CHANGED
printf 'KMJ_EXISTING_OFFSITE_ONLY=TRANSFER_READBACK_VERIFIED\n'
printf 'GOOGLE_INDEPENDENT_RESTORE=NOT_VERIFIED\n'
printf 'PRODUCTION_CHANGED=NO\n'
