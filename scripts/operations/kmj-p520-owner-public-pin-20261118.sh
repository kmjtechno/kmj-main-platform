#!/usr/bin/env bash
# KMJ TECHNO: fixed, owner-observed P520 PUBLIC identity installation.
# --inspect is read-only; --apply installs ONLY new public Ed25519 PEM and AGE recipient.
# NEVER signs releases, edits approval manifests, touches databases, or imports private keys.
set -Eeuo pipefail
umask 077

mode=''
if [[ $# -eq 1 ]]; then mode="$1"; fi
if [[ $# -ne 1 || ( "$mode" != '--inspect' && "$mode" != '--apply' ) ]]; then
  echo "KMJ_P520_PUBLIC_PIN=BLOCKED_EXACT_MODE" ; exit 2
fi
if [[ "$(hostname -s)" != 'KMJ-elite' || "$EUID" -ne 0 ]]; then
  echo "KMJ_P520_PUBLIC_PIN=BLOCKED_OWNER_ELITE_ROOT_REQUIRED" ; exit 2
fi
root='/etc/kmj-p520-restore-trust'
key="$root/p520-receipt-ed25519-public.pem"
age="$root/p520-age-recipient.txt"
expected_sha='6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4'
recipient='age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u'
pem_b64='LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQUdsejV2cnE2Snk4NVF4TzFTSEhxOTlCbmtORllEVFZKeHh3K2NseFg2bzQ9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo='

fail(){ echo "KMJ_P520_PUBLIC_PIN=BLOCKED_$1"; echo "PRODUCTION_APPROVAL=NOT_GRANTED"; exit 2; }
check_dir(){
  [[ -d "$root" && ! -L "$root" ]] || fail 'PRIVATE_TRUST_DIR_NOT_ORDINARY'
  [[ "$(stat -c '%u:%g:%a' -- "$root")" == '0:0:700' ]] || fail 'PRIVATE_TRUST_DIR_ACL'
}
check_file(){
  local file="$1"
  [[ -f "$file" && ! -L "$file" ]] || fail 'PUBLIC_TRUST_FILE_NOT_ORDINARY'
  [[ "$(stat -c '%u:%g:%a:%h' -- "$file")" == '0:0:600:1' ]] || fail 'PUBLIC_TRUST_FILE_OWNER_OR_MODE'
}
verify_pin(){
  check_file "$key"
  check_file "$age"
  local actual
  actual="$(sha256sum -- "$key" | cut -d' ' -f1)"
  [[ "$actual" == "$expected_sha" ]] || fail 'PUBLIC_KEY_SHA256_MISMATCH'
  openssl pkey -pubin -in "$key" -noout >/dev/null 2>&1 || fail 'PUBLIC_KEY_PARSE_FAILED'
  [[ "$(cat -- "$age")" == "$recipient" ]] || fail 'PUBLIC_AGE_RECIPIENT_MISMATCH'
  [[ "$(wc -c < "$age")" -eq 63 ]] || fail 'PUBLIC_AGE_RECIPIENT_BYTES'
  echo "P520_ELITE_ED25519_PUBLIC_PEM_SHA256=PASS"
  echo "P520_ELITE_AGE_PUBLIC_RECIPIENT=PASS"
  echo "ELITE_PUBLIC_KEYS_OWNER_PIN=PASS_PUBLIC_ONLY"
  echo "P520_CANDIDATE_BACKUP_RESTORE=NOT_EXECUTED"
  echo "PRODUCTION_APPROVAL=NOT_GRANTED"
  echo "KMJ_P520_PUBLIC_PIN=PASS"
}
if [[ "$mode" == '--inspect' ]]; then
  if [[ ! -e "$root" && ! -L "$root" ]]; then
    echo 'KMJ_P520_PUBLIC_PIN=NOT_INSTALLED'
    echo 'PRODUCTION_APPROVAL=NOT_GRANTED'
    exit 0
  fi
  check_dir
  verify_pin
  exit 0
fi

# Trusted-only public identity installation. Existing paths are never overwritten.
if [[ -e "$root" || -L "$root" ]]; then
  check_dir
else
  [[ -d /etc && ! -L /etc ]] || fail 'ETC_PARENT_UNTRUSTED'
  install -d -o root -g root -m 0700 -- "$root"
  check_dir
fi

tmp="$(mktemp -d -- "$root/.p520-pub.XXXXXXXX")" || fail 'PRIVATE_STAGING_UNAVAILABLE'
trap 'rm -f -- "$tmp/key" "$tmp/age"; rmdir -- "$tmp" 2>/dev/null || true' EXIT
printf '%s' "$pem_b64" | base64 -d > "$tmp/key" || fail 'PUBLIC_PEM_DECODE'
printf '%s\n' "$recipient" > "$tmp/age"
chmod 0600 -- "$tmp/key" "$tmp/age"
[[ "$(sha256sum -- "$tmp/key" | cut -d' ' -f1)" == "$expected_sha" ]] || fail 'OWNER_PUBLIC_PEM_PIN_MISMATCH'
openssl pkey -pubin -in "$tmp/key" -noout >/dev/null 2>&1 || fail 'OWNER_PUBLIC_PEM_PARSE'

# ln(2) is no-clobber; root-only directory prevents hostile replacement.
for staged in key age; do
  if [[ "$staged" == key ]]; then dest="$key"; else dest="$age"; fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    check_file "$dest"
    cmp -s -- "$tmp/$staged" "$dest" || fail 'EXISTING_PUBLIC_KEY_CONFLICT'
  else
    ln -- "$tmp/$staged" "$dest" || fail 'PUBLIC_PIN_CREATE_COLLISION'
  fi
done
rm -f -- "$tmp/key" "$tmp/age"
rmdir -- "$tmp"
trap - EXIT
verify_pin
