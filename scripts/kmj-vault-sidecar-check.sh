#!/usr/bin/env bash
# KMJ vault cipher vs sidecar check (read-only, counts only).
#
# For every <stamp>.tar.age in the vault with a <stamp>.sha256 sidecar (V3 naming: "<sha256>  <stamp>.tar.age\n"), recompute
# the cipher's SHA-256 and compare it with the sidecar. Never decrypts, never reads a
# key, never prints names or hashes, deletes nothing. Closes only the gap
# "cipherDigestComparedToSidecar"; it does not prove the cipher can be decrypted or restored.
#
# Env: KMJ_VAULT_DIR, KMJ_VAULT_RECEIPT_DIR, KMJ_ALLOW_NONROOT_FOR_TESTS
set -Eeuo pipefail
umask 077

VAULT="${KMJ_VAULT_DIR:-/var/backups/kmj-elite-offsite-encrypted}"
RECEIPT_DIR="${KMJ_VAULT_RECEIPT_DIR:-/var/lib/kmj-restore-drill}"
fail() { echo "VAULT_SIDECAR_CHECK=FAIL:$1" >&2; exit "${2:-1}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED 2
command -v sha256sum >/dev/null 2>&1 || fail MISSING_sha256sum 2
[[ -d "$VAULT" && ! -L "$VAULT" ]] || fail VAULT_DIR_MISSING 4

total=0; ok=0; mismatch=0; bad_format=0; missing_sidecar=0
for c in "$VAULT"/*.tar.age; do
  [[ -e "$c" ]] || continue
  [[ -f "$c" && ! -L "$c" ]] || { bad_format=$((bad_format+1)); continue; }
  total=$((total+1))
  s="${c%.tar.age}.sha256"
  if [[ ! -f "$s" || -L "$s" ]]; then missing_sidecar=$((missing_sidecar+1)); continue; fi
  line="$(head -n1 "$s")"
  want="${line%% *}"
  named="${line#*  }"
  if [[ ! "$want" =~ ^[a-f0-9]{64}$ || "$named" != "$(basename "$c")" ]]; then bad_format=$((bad_format+1)); continue; fi
  have="$(sha256sum "$c" | cut -d' ' -f1)"
  if [[ "$have" == "$want" ]]; then ok=$((ok+1)); else mismatch=$((mismatch+1)); fi
done

verdict=PASS
(( total > 0 && mismatch == 0 && bad_format == 0 && missing_sidecar == 0 )) || verdict=FAIL
mkdir -p "$RECEIPT_DIR"; chmod 755 "$RECEIPT_DIR"
receipt="$RECEIPT_DIR/vault-sidecar.$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "schema=KMJ_VAULT_SIDECAR_CHECK_V1"
  echo "verdict=$verdict"
  echo "ciphers=$total sidecar_match=$ok sidecar_mismatch=$mismatch bad_format=$bad_format missing_sidecar=$missing_sidecar"
  echo "decrypted=no recipient_verified=no restore_proven=no names_recorded=no"
} > "$receipt"
chmod 644 "$receipt"
echo "VAULT_SIDECAR_CHECK=$verdict"
echo "COUNTS ciphers=$total match=$ok mismatch=$mismatch bad_format=$bad_format missing_sidecar=$missing_sidecar"
echo "RECEIPT=$receipt"
[[ "$verdict" == PASS ]]
