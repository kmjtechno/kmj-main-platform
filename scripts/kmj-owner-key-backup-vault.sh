#!/usr/bin/env bash
# KMJ owner-key backup vault.
#
# Encrypts the newest checksum-verified daily snapshot to the OWNER's age
# public key, so a backup exists that the owner can decrypt on their own PC.
# It never touches the V3 Google-pinned vault, the timer, production data, or
# any existing backup, and it deletes nothing (retention is a separate,
# owner-approved decision). Output lines are status only: no secrets.
#
# Env (defaults are the production paths; tests override them):
#   KMJ_DAILY_DIR              /var/backups/kmj-elite-daily
#   KMJ_OWNER_VAULT_DIR        /var/backups/kmj-owner-vault
#   KMJ_OWNER_RECIPIENT_FILE   /root/kmj-bootstrap/owner-age-recipient.txt
set -Eeuo pipefail
umask 077

DAILY="${KMJ_DAILY_DIR:-/var/backups/kmj-elite-daily}"
OUT="${KMJ_OWNER_VAULT_DIR:-/var/backups/kmj-owner-vault}"
RCPT_FILE="${KMJ_OWNER_RECIPIENT_FILE:-/root/kmj-bootstrap/owner-age-recipient.txt}"

fail() { echo "OWNER_VAULT=FAIL:$1" >&2; exit "${2:-1}"; }

if [[ "$(id -u)" != 0 && "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" != 1 ]]; then
  fail ROOT_REQUIRED 2
fi
for tool in age tar sha256sum; do
  command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool" 2
done

[[ -f "$RCPT_FILE" && ! -L "$RCPT_FILE" ]] || fail RECIPIENT_FILE_MISSING 3
[[ "$(wc -l < "$RCPT_FILE")" -le 1 ]] || fail RECIPIENT_FILE_NOT_SINGLE_LINE 3
recipient="$(tr -d '[:space:]' < "$RCPT_FILE")"
[[ "$recipient" =~ ^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$ ]] || fail RECIPIENT_NOT_AGE_PUBLIC_KEY 3

[[ -d "$DAILY" && ! -L "$DAILY" ]] || fail DAILY_DIR_MISSING 4
stamp=""
while IFS= read -r name; do
  [[ "$name" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] && stamp="$name"
done < <(ls -1 "$DAILY" | LC_ALL=C sort)
[[ -n "$stamp" ]] || fail NO_DAILY_SNAPSHOT 4
snap="$DAILY/$stamp"
[[ -d "$snap" && ! -L "$snap" && -f "$snap/platform.dump" && -f "$snap/SHA256SUMS" ]] \
  || fail SNAPSHOT_INCOMPLETE 4

# The snapshot must match its own checksums before it is sealed.
( cd "$snap" && sha256sum -c --quiet SHA256SUMS ) >/dev/null 2>&1 || fail SNAPSHOT_CHECKSUM_MISMATCH 5

mkdir -p "$OUT"
chmod 700 "$OUT"
[[ ! -L "$OUT" ]] || fail VAULT_DIR_IS_SYMLINK 4

name="$stamp.tar.age"
if [[ -e "$OUT/$name" ]]; then
  echo "OWNER_VAULT=ALREADY_PRESENT"
  echo "STAMP=$stamp"
  exit 0
fi

tmp="$OUT/.tmp-$stamp.$$"
trap 'rm -f "$tmp" "$tmp.sha256"' EXIT
tar -C "$DAILY" -cf - "$stamp" | age -r "$recipient" -o "$tmp"

[[ -s "$tmp" ]] || fail CIPHER_EMPTY 6
[[ "$(head -c 21 "$tmp")" == "age-encryption.org/v1" ]] || fail CIPHER_HEADER_INVALID 6

sum="$(sha256sum "$tmp" | cut -d' ' -f1)"
printf '%s  %s\n' "$sum" "$name" > "$tmp.sha256"
chmod 600 "$tmp" "$tmp.sha256"

# No-clobber, sidecar first so a cipher never exists without its digest.
mv -n "$tmp.sha256" "$OUT/$name.sha256"
mv -n "$tmp" "$OUT/$name"
[[ -s "$OUT/$name" && -s "$OUT/$name.sha256" ]] || fail PUBLISH_INCOMPLETE 7

echo "OWNER_VAULT=PASS"
echo "STAMP=$stamp"
echo "CIPHER_SHA256=$sum"
echo "CIPHER_BYTES=$(stat -c %s "$OUT/$name")"
echo "RESTORE_PROVEN=NO (decrypt on the owner PC and run pg_restore --list)"
