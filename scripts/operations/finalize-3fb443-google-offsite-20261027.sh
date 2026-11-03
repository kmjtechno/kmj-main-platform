#!/usr/bin/env bash
# Owner-run on google-vps1 as user info: commit ONLY verified age-encrypted incoming archive.
# Does not decrypt, run PostgreSQL, connect to KMJ-elite, or alter remote backups.
set -Eeuo pipefail
umask 077
fail() { printf 'KMJ_OFFSITE_IMPORT=BLOCKED_%s\n' "$1"; exit 2; }
mark() { printf '%s=%s\n' "$1" "$2"; }
test "$(hostname -s)" = google-vps1 && test "$(id -un)" = info && test "$(id -u)" -ne 0 || fail WRONG_HOST_OR_USER
scratch="$HOME/kmj-recovery-scratch"
identity="$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey"
incoming="$scratch/offsite-3fb443d135f0.tar.gz.age.incoming-8ec0fc1e"
final="$scratch/offsite-3fb443d135f0.tar.gz.age"
expected=8ec0fc1ef637a683dc7fe0493394c3c6d1613c8e233a36964fa7ab1dc33c6124
recipient=age1952vsyz25elfzn8slyhuc4k586dhw0er45yy26myhvv3lcp9qeps8mj7f5
test -d "$scratch" && test ! -L "$scratch" || fail SCRATCH_MISSING_OR_LINK
test "$(stat -c '%u' "$scratch")" = "$(id -u)" || fail SCRATCH_OWNER
test "$(stat -c '%a' "$scratch")" = 700 || fail SCRATCH_PERMISSIONS
test -f "$identity" && test ! -L "$identity" || fail IDENTITY_MISSING_OR_LINK
test "$(stat -c '%u' "$identity")" = "$(id -u)" || fail IDENTITY_OWNER
test "$(stat -c '%a' "$identity")" = 600 || fail IDENTITY_PERMISSIONS
test "$(age-keygen -y "$identity" 2>/dev/null)" = "$recipient" || fail WRONG_RECOVERY_AGE_RECIPIENT
validate() {
  test -f "$1" && test ! -L "$1" &&
  test "$(stat -c '%u' "$1")" = "$(id -u)" &&
  test "$(stat -c '%a' "$1")" = 600 &&
  test "$(stat -c '%s' "$1")" = 239040 &&
  test "$(sha256sum "$1" | awk '{print $1}')" = "$expected"
}
if test -e "$final" || test -L "$final"; then
  validate "$final" || fail EXISTING_FINAL_MISMATCH
  mark GOOGLE_ENCRYPTED_ARCHIVE ALREADY_VERIFIED
  mark GOOGLE_ENCRYPTED_SHA256 "$expected"
  mark GOOGLE_INDEPENDENT_RESTORE NOT_ATTEMPTED
  exit 0
fi
validate "$incoming" || fail INCOMING_SHA256_OWNER_MODE_SIZE
# Hard link is exclusive and atomic; refuses any existing destination.
ln -- "$incoming" "$final" || fail FINAL_EXCLUSIVE_CREATE
validate "$final" || fail FINAL_READBACK
# Remove only the uniquely hashed temporary incoming name, after immutable final exists.
rm -- "$incoming"
mark GOOGLE_ENCRYPTED_ARCHIVE VERIFIED
mark GOOGLE_ENCRYPTED_SHA256 "$expected"
mark GOOGLE_INDEPENDENT_RESTORE NOT_ATTEMPTED
