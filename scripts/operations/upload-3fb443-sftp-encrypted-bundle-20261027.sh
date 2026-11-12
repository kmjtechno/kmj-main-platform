#!/usr/bin/env bash
# KMJ P0 exact-SHA encrypted backup upload to Google VPS via a strictly pinned SFTP host.
# Only sends a 239040-byte age encrypted file to a NEW incoming filename.
# A successful upload is NOT remote SHA verification or an independent restore.
set -Eeuo pipefail
umask 077
block() { echo "KMJ_OFFSITE_SFTP=BLOCKED_$1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }

test "$(hostname -s)" = KMJ-elite && test "$(id -u)" -eq 0 || block WRONG_OPERATOR_OR_HOST
sourcefile=/var/backups/kmj-platform/offsite-3fb443d135f0.tar.gz.age
expected=8ec0fc1ef637a683dc7fe0493394c3c6d1613c8e233a36964fa7ab1dc33c6124
host=34.63.5.14
port=22
user=info
fingerprint=SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU
incoming=kmj-recovery-scratch/offsite-3fb443d135f0.tar.gz.age.incoming-8ec0fc1e
test "$(readlink -f /home/kmjprod/current)" = /home/kmjprod/releases/platform-8070dad72c55 || block LIVE_RELEASE_CHANGED
test -f "$sourcefile" && test ! -L "$sourcefile" || block SOURCE_NOT_REGULAR
test "$(stat -c '%u' "$sourcefile")" = 0 || block SOURCE_NOT_ROOT
test "$(stat -c '%a' "$sourcefile")" = 600 || block SOURCE_NOT_0600
test "$(stat -c '%h' "$sourcefile")" = 1 || block SOURCE_HARDLINKED
test "$(stat -c '%s' "$sourcefile")" = 239040 || block SIZE_MISMATCH
test "$(sha256sum "$sourcefile" | awk '{print $1}')" = "$expected" || block ENCRYPTED_DIGEST_MISMATCH
for cmd in sftp ssh-keyscan ssh-keygen sha256sum mktemp awk grep stat; do
  command -v "$cmd" >/dev/null 2>&1 || block "MISSING_TOOL"
done
scratch="$(mktemp -d /root/.kmj-p0-sftp-XXXXXXXX)"
chmod 700 "$scratch"
trap 'rm -rf -- "$scratch"' EXIT
known="$scratch/known_hosts"
ssh-keyscan -T 12 -p "$port" -t ed25519 "$host" >"$known" 2>/dev/null || block SSH_HOST_KEY_SCAN
test -s "$known" || block SSH_HOST_KEY_EMPTY
test "$(grep -c ' ssh-ed25519 ' "$known")" = 1 || block SSH_HOST_KEY_COUNT
ssh-keygen -E sha256 -lf "$known" >"$scratch/fingerprint"
grep -Fq -- "$fingerprint" "$scratch/fingerprint" || block SSH_HOST_KEY_MISMATCH
status SSH_HOST_KEY_PIN PASS

key=''
for candidate in /root/.ssh/kmj-google-offsite-20261021 /root/.ssh/kmj_pg16_offsite_20261017; do
  test -f "$candidate" && test ! -L "$candidate" || continue
  test "$(stat -c '%u' "$candidate")" = 0 || continue
  test "$(stat -c '%a' "$candidate")" = 600 || continue
  # Existing owner-approved private key only; no new authorization and no passwords.
  if printf 'pwd\n' | sftp -q -F /dev/null -P "$port" -i "$candidate" -b - \
     -o BatchMode=yes -o StrictHostKeyChecking=yes \
     -o UserKnownHostsFile="$known" -o GlobalKnownHostsFile=/dev/null \
     -o HostKeyAlgorithms=ssh-ed25519 -o PubkeyAuthentication=yes \
     -o PreferredAuthentications=publickey -o IdentitiesOnly=yes \
     -o IdentityAgent=none -o NumberOfPasswordPrompts=0 \
     -o ConnectTimeout=12 "$user@$host" >"$scratch/auth.log" 2>&1; then
    key="$candidate"
    break
  fi
done
test -n "$key" || block SSH_PUBLICKEY_AUTH_NEEDS_OWNER_REAUTH
status SSH_AUTH PASS
# Never knowingly overwrite an earlier encrypted upload. A failed file ls means
# the chosen new incoming filename was not reported as an existing remote file.
if printf 'ls %s\n' "$incoming" | sftp -q -F /dev/null -P "$port" -i "$key" -b - \
   -o BatchMode=yes -o StrictHostKeyChecking=yes \
   -o UserKnownHostsFile="$known" -o GlobalKnownHostsFile=/dev/null \
   -o HostKeyAlgorithms=ssh-ed25519 -o PubkeyAuthentication=yes \
   -o PreferredAuthentications=publickey -o IdentitiesOnly=yes \
   -o IdentityAgent=none -o NumberOfPasswordPrompts=0 \
   -o ConnectTimeout=12 "$user@$host" >"$scratch/exists.log" 2>&1; then
  block ENCRYPTED_REMOTE_INCOMING_ALREADY_EXISTS
fi
# Upload to a hash-qualified incoming name, NOT the final immutable file.
printf 'put %s %s\nchmod 600 %s\n' "$sourcefile" "$incoming" "$incoming" |
  sftp -q -F /dev/null -P "$port" -i "$key" -b - \
   -o BatchMode=yes -o StrictHostKeyChecking=yes \
   -o UserKnownHostsFile="$known" -o GlobalKnownHostsFile=/dev/null \
   -o HostKeyAlgorithms=ssh-ed25519 -o PubkeyAuthentication=yes \
   -o PreferredAuthentications=publickey -o IdentitiesOnly=yes \
   -o IdentityAgent=none -o NumberOfPasswordPrompts=0 \
   -o ConnectTimeout=12 "$user@$host" >"$scratch/transfer.log" 2>&1 ||
   block SFTP_UPLOAD_FAILED
status SFTP_ENCRYPTED_UPLOAD PASS_PENDING_GOOGLE_SHA256
status ENCRYPTED_SHA256_EXPECTED "$expected"
status GOOGLE_PENDING_FILENAME "$incoming"
status INDEPENDENT_GOOGLE_RESTORE NOT_ATTEMPTED
status PRODUCTION_ACTIVATION NOT_ATTEMPTED
