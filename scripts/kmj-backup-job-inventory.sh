#!/usr/bin/env bash
# KMJ backup job inventory (read-only, counts and unit state only).
#
# Answers: which scheduled jobs actually create daily snapshots, when did they last
# run, and how many storage files does each recent snapshot hold? Never prints file
# names or contents, never changes any unit, timer or backup.
#
# Env: KMJ_DAILY_DIR, KMJ_INVENTORY_RECEIPT_DIR, KMJ_ALLOW_NONROOT_FOR_TESTS
set -Eeuo pipefail
umask 077

DAILY="${KMJ_DAILY_DIR:-/var/backups/kmj-elite-daily}"
RECEIPT_DIR="${KMJ_INVENTORY_RECEIPT_DIR:-/var/lib/kmj-restore-drill}"
fail() { echo "BACKUP_INVENTORY=FAIL:$1" >&2; exit "${2:-1}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED 2
command -v systemctl >/dev/null 2>&1 || fail MISSING_systemctl 2
[[ -d "$DAILY" && ! -L "$DAILY" ]] || fail DAILY_DIR_MISSING 4

mkdir -p "$RECEIPT_DIR"
out="$RECEIPT_DIR/backup-job-inventory.$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "schema=kmj.backup.job.inventory.v1"
  echo "now_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "--- timers (name, next, last) ---"
  systemctl list-timers --all --no-pager --no-legend 2>/dev/null \
    | grep -iE 'kmj|backup' | awk '{print $NF" next="$1" "$2" last="$(NF-4)" "$(NF-3)}' || echo "none"
  echo "--- units (result, exit, last start) ---"
  for u in $(systemctl list-units --all --type=service --no-pager --no-legend 2>/dev/null \
      | awk '{print $1}' | grep -iE 'kmj.*(backup|daily|vault|health)|backup' || true); do
    printf '%s result=%s exit=%s started=%s\n' "$u" \
      "$(systemctl show -p Result --value "$u" 2>/dev/null)" \
      "$(systemctl show -p ExecMainStatus --value "$u" 2>/dev/null)" \
      "$(systemctl show -p ExecMainStartTimestamp --value "$u" 2>/dev/null)"
  done
  echo "--- newest daily snapshots (stamp, storage_files, schema) ---"
  for s in $(ls -1 "$DAILY" | grep -E '^[0-9]{8}T[0-9]{6}Z$' | LC_ALL=C sort | tail -5); do
    d="$DAILY/$s"
    n=0; [[ -d "$d/platform-storage" ]] && n=$(find "$d/platform-storage" -type f | wc -l)
    schema=$(grep -rhm1 '^schema=' "$d" --include='*' 2>/dev/null | head -1 || true)
    echo "$s storage_files=$n ${schema:-schema=unknown}"
  done
} > "$out"
echo "BACKUP_INVENTORY=DONE RECEIPT=$out"
