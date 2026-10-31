#!/usr/bin/env bash
# P0: candidate + real local PG/uploads restore + AGE encrypted Google SFTP evidence.
# NO production pointer change, service change, DNS change, migrations or release approval.
# Fixed vetted exact-Git-commit sources verified by SHA256; no arbitrary code paths.
set -Eeuo pipefail
umask 077
blocked(){ printf 'KMJ_OFFSITE_RECOVERY=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$#" == 4 && "$1" == '--candidate-sha' && "$3" == '--expected-release' ]] ||
  blocked EXACT_ARGS
[[ "$2" =~ ^[0-9a-f]{40}$ ]] || blocked CANDIDATE_SHA
[[ "$4" =~ ^platform-[0-9a-f]{12}$ ]] || blocked EXPECTED_RELEASE
readonly CANDIDATE="$2" EXPECTED="$4"
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || blocked OWNER_ELITE_ROOT
[[ "platform-$(printf '%s' "$CANDIDATE" | cut -c1-12)" != "$EXPECTED" ]] || blocked NEW_RELEASE_EQUALS_CURRENT
readonly LIVE=/home/kmjprod/current
[[ -L "$LIVE" ]] || blocked LIVE_POINTER_ABSENT
[[ "$(readlink -f "$LIVE")" == "/home/kmjprod/releases/$EXPECTED" ]] || blocked LIVE_POINTER_CHANGED
[[ -d "/home/kmjprod/releases/$EXPECTED" ]] || blocked CURRENT_RELEASE_MISSING
[[ -d /var/backups/kmj-platform && ! -L /var/backups/kmj-platform ]] || blocked BACKUP_ROOT_MISSING
[[ -f /etc/kmj-codebridge/offsite-sftp.conf && ! -L /etc/kmj-codebridge/offsite-sftp.conf ]] ||
  blocked SFTP_OWNER_CONFIG_MISSING
[[ "$(stat -c '%u:%a:%h' /etc/kmj-codebridge/offsite-sftp.conf)" == '0:600:1' ]] ||
  blocked SFTP_OWNER_CONFIG_PERMISSIONS
for command in curl sha256sum git python3 bash stat mktemp readlink rm; do
  command -v "$command" >/dev/null 2>&1 || blocked "MISSING_$command"
done
# Immutable source baseline. Independently SHA256-verified from GitHub contents.
readonly SOURCE_COMMIT=5da955a03ccf9b98afc62e138325d454a65dca6d
readonly BASE="https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/$SOURCE_COMMIT/scripts/operations"
readonly STAGE_SHA=ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24
readonly LOCAL_SHA=9812f831841ede684cc7a62c378ca35f43fb557dbc402c881785e506b508ff6f
readonly SEAL_SHA=410f4348a4a0bbb7101f36345c1df09162660cb72a7aaf13ed35337951ae18ef
readonly PUSH_SHA=547e624cc031045406add6b653d5925a46aa5d1aa6563a12f13dedc3c2aebdff
readonly STAGE_SCRIPT=stage-fast-main-candidate-no-activation.sh
readonly LOCAL_SCRIPT=prepare-main-platform-local-recovery-exact.sh
readonly SEAL_SCRIPT=seal-main-platform-offsite-20261030.py
readonly PUSH_SCRIPT=push-offsite-pinned-sftp-20261030.sh
work=$(mktemp -d /root/kmj-evidence.XXXXXXXX) || blocked OWNER_SCRATCH
[[ -d "$work" && ! -L "$work" && "$(stat -c '%u:%a' "$work")" == "0:700" ]] ||
  blocked OWNER_SCRATCH_UNSAFE
cleanup(){
  # Only this invocation's known, new root-owned private scratch is cleaned.
  case "$work" in
    /root/kmj-evidence.*)
      [[ -d "$work" && ! -L "$work" ]] && rm -rf -- "$work" ;;
  esac
}
trap cleanup EXIT
download(){
  local name=$1 digest=$2
  curl -fsSL --proto '=https' --tlsv1.2 --max-time 45 \
    "$BASE/$name" -o "$work/$name" || blocked SOURCE_FETCH
  printf '%s  %s\n' "$digest" "$work/$name" | sha256sum -c - >/dev/null ||
    blocked IMMUTABLE_SOURCE_DIGEST
}
download "$STAGE_SCRIPT" "$STAGE_SHA"
download "$LOCAL_SCRIPT" "$LOCAL_SHA"
download "$SEAL_SCRIPT" "$SEAL_SHA"
download "$PUSH_SCRIPT" "$PUSH_SHA"
printf 'KMJ_PINNED_OPERATOR_SCRIPTS=4_SHA256_VERIFIED\n'
# First creates only an isolated candidate; verifies exact origin/main itself.
printf 'KMJ_PHASE=ISOLATED_CANDIDATE_BUILD\n'
bash "$work/$STAGE_SCRIPT" "$CANDIDATE"
[[ "$(readlink -f "$LIVE")" == "/home/kmjprod/releases/$EXPECTED" ]] ||
  blocked LIVE_CHANGED_AFTER_STAGE
printf 'KMJ_PHASE=REAL_LOCAL_DATABASE_AND_UPLOADS_BACKUP_RESTORE\n'
# Real pg_dump + storage/app + .env, private root-only archive, disposable
# isolated PostgreSQL restore, schema verification, SHA witness.
bash "$work/$LOCAL_SCRIPT" "$CANDIDATE" "$EXPECTED"
[[ "$(readlink -f "$LIVE")" == "/home/kmjprod/releases/$EXPECTED" ]] ||
  blocked LIVE_CHANGED_AFTER_LOCAL_RESTORE
printf 'KMJ_PHASE=AGE_ENCRYPTION_OF_SANITIZED_BACKUP\n'
# Removes .env from offsite bundle, fixed age recipient, root-only ciphertext.
python3 -I "$work/$SEAL_SCRIPT" --candidate-sha "$CANDIDATE" --expected-release "$EXPECTED"
[[ "$(readlink -f "$LIVE")" == "/home/kmjprod/releases/$EXPECTED" ]] ||
  blocked LIVE_CHANGED_AFTER_ENCRYPTION
printf 'KMJ_PHASE=PINNED_GOOGLE_SFTP_NO_CLOBBER_AND_READBACK\n'
# Exact owner config, strict host pin, key, no-clobber, remote readback SHA.
bash "$work/$PUSH_SCRIPT" --candidate-sha "$CANDIDATE"
[[ "$(readlink -f "$LIVE")" == "/home/kmjprod/releases/$EXPECTED" ]] ||
  blocked LIVE_CHANGED_AFTER_UPLOAD
printf 'KMJ_OFFSITE_RECOVERY=LOCAL_BACKUP_ENCRYPTED_OFFSITE_READBACK_COMPLETE\n'
printf 'GOOGLE_INDEPENDENT_RESTORE=NOT_VERIFIED\n'
printf 'STAGING_APPROVAL=NOT_MODIFIED\n'
printf 'PRODUCTION_RELEASE=UNCHANGED\n'
