#!/usr/bin/env bash
# KMJ backup storage completeness check (read-only, counts only).
#
# Compares the newest checksum-verified daily snapshot's platform-storage/
# tree with the live application storage tree by relative path and SHA-256.
# Reads both trees, writes nothing except a counts-only receipt. Never prints
# or stores file names or contents (customer data may live there).
#
# Verdict rules (fail closed):
#   PASS = every snapshot file exists live with the same content OR was
#          changed live after the snapshot (reported), and no live file that
#          existed at snapshot time is missing from the snapshot dir.
# Because the snapshot is older than live, files created after the snapshot are
# reported as live_only and are NOT a failure. Files in the snapshot that are
# gone live are reported as snapshot_only (informational). A snapshot with ZERO
# files while live has files FAILS. Equality is not claimed.
#
# Env: KMJ_DAILY_DIR, KMJ_LIVE_STORAGE, KMJ_STORAGE_RECEIPT_DIR, KMJ_STORAGE_MAX_BYTES
set -Eeuo pipefail
umask 077

DAILY="${KMJ_DAILY_DIR:-/var/backups/kmj-elite-daily}"
LIVE="${KMJ_LIVE_STORAGE:-/home/kmjprod/current/apps/platform/storage/app}"
RECEIPT_DIR="${KMJ_STORAGE_RECEIPT_DIR:-/var/lib/kmj-restore-drill}"
MAX="${KMJ_STORAGE_MAX_BYTES:-536870912}"

fail() { echo "STORAGE_CHECK=FAIL:$1" >&2; exit "${2:-1}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED 2
for t in sha256sum find sort comm du; do command -v "$t" >/dev/null 2>&1 || fail "MISSING_$t" 2; done
[[ -d "$DAILY" && ! -L "$DAILY" ]] || fail DAILY_DIR_MISSING 4

stamp=""
while IFS= read -r n; do [[ "$n" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] && stamp="$n"; done < <(ls -1 "$DAILY" | LC_ALL=C sort)
[[ -n "$stamp" ]] || fail NO_DAILY_SNAPSHOT 4
snap="$DAILY/$stamp"
[[ -d "$snap" && ! -L "$snap" && -f "$snap/SHA256SUMS" ]] || fail SNAPSHOT_INCOMPLETE 4
( cd "$snap" && sha256sum -c --quiet SHA256SUMS ) >/dev/null 2>&1 || fail SNAPSHOT_CHECKSUM_MISMATCH 5
sroot="$snap/platform-storage"
[[ -d "$sroot" && ! -L "$sroot" ]] || fail SNAPSHOT_STORAGE_DIR_MISSING 4

live_real="$(readlink -f -- "$LIVE")"
[[ -d "$live_real" ]] || fail LIVE_STORAGE_MISSING 4
live_bytes="$(du -sb -- "$live_real" | cut -f1)"
(( live_bytes <= MAX )) || fail LIVE_STORAGE_TOO_LARGE 4

# If the snapshot mirrors storage/ (has app/ inside) compare against storage/.
if [[ -d "$sroot/app" && "$(basename "$live_real")" == app ]]; then
  live_root="$(dirname "$live_real")"; layout="storage_root"
else
  live_root="$live_real"; layout="storage_app"
fi

manifest() { ( cd "$1" && find . -xdev -type f ! -type l -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum ) ; }
tmp="$(mktemp -d)"; trap 'rm -rf -- "$tmp"' EXIT
manifest "$sroot" > "$tmp/snap.txt"
manifest "$live_root" > "$tmp/live.txt"
awk '{print substr($0,67)}' "$tmp/snap.txt" | LC_ALL=C sort > "$tmp/snap.paths"
awk '{print substr($0,67)}' "$tmp/live.txt" | LC_ALL=C sort > "$tmp/live.paths"

snap_n="$(wc -l < "$tmp/snap.paths")"; live_n="$(wc -l < "$tmp/live.paths")"
both="$(LC_ALL=C comm -12 "$tmp/snap.paths" "$tmp/live.paths" | wc -l)"
live_only="$(LC_ALL=C comm -13 "$tmp/snap.paths" "$tmp/live.paths" | wc -l)"
snap_only="$(LC_ALL=C comm -23 "$tmp/snap.paths" "$tmp/live.paths" | wc -l)"
same="$(LC_ALL=C sort "$tmp/snap.txt" "$tmp/live.txt" | uniq -d | wc -l)"
changed=$(( both - same ))

verdict=PASS
if (( snap_n == 0 && live_n > 0 )); then verdict=FAIL; fi

mkdir -p "$RECEIPT_DIR"; chmod 755 "$RECEIPT_DIR"
receipt="$RECEIPT_DIR/storage-$stamp.$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "schema=KMJ_STORAGE_COMPLETENESS_V1"
  echo "snapshot_stamp=$stamp layout=$layout"
  echo "verdict=$verdict"
  echo "snapshot_files=$snap_n live_files=$live_n"
  echo "identical=$same changed_since_snapshot=$changed live_only=$live_only snapshot_only=$snap_only"
  echo "names_recorded=no content_recorded=no equality_claimed=no"
} > "$receipt"
chmod 644 "$receipt"
echo "STORAGE_CHECK=$verdict"
echo "STAMP=$stamp"
echo "COUNTS snapshot=$snap_n live=$live_n identical=$same changed=$changed live_only=$live_only snapshot_only=$snap_only"
echo "RECEIPT=$receipt"
[[ "$verdict" == PASS ]]
