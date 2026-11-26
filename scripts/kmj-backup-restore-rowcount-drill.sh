#!/usr/bin/env bash
# KMJ backup restore drill with per-table row-count comparison.
#
# Restores the newest checksum-verified daily snapshot's platform.dump into a
# DISPOSABLE scratch database, compares per-table row counts against the live
# database (read-only), drops the scratch database, and writes a counts-only
# receipt (no row data, no secrets). Never writes to the production database,
# never touches backups, deletes nothing except its own scratch database.
#
# The snapshot is older than the live database, so counts are expected to
# drift upward in live. Verdict rules (fail closed):
#   PASS  = restore ok with ON_ERROR_STOP, same table set, and no table where
#           snapshot rows > live rows by more than KMJ_DRILL_SHRINK_TOLERANCE.
#   Equality is NOT claimed; drift is reported per table.
#
# Env (defaults = production paths; tests override):
#   KMJ_DAILY_DIR, KMJ_DRILL_PG_RESTORE, KMJ_DRILL_LIVE_DB, KMJ_DRILL_RECEIPT_DIR
set -Eeuo pipefail
umask 077

DAILY="${KMJ_DAILY_DIR:-/var/backups/kmj-elite-daily}"
PG_RESTORE="${KMJ_DRILL_PG_RESTORE:-/usr/lib/postgresql/18/bin/pg_restore}"
LIVE_DB="${KMJ_DRILL_LIVE_DB:-}"
RECEIPT_DIR="${KMJ_DRILL_RECEIPT_DIR:-/var/lib/kmj-restore-drill}"
TOL="${KMJ_DRILL_SHRINK_TOLERANCE:-0}"
RUNAS_PG="${KMJ_DRILL_PG_USER:-postgres}"

fail() { echo "RESTORE_DRILL=FAIL:$1" >&2; exit "${2:-1}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED 2
[[ -n "$LIVE_DB" ]] || fail LIVE_DB_NAME_REQUIRED 2
[[ "$LIVE_DB" =~ ^[A-Za-z0-9_]{1,63}$ ]] || fail LIVE_DB_NAME_INVALID 2
[[ -x "$PG_RESTORE" ]] || fail PG_RESTORE_MISSING 2
for t in sha256sum psql runuser date; do command -v "$t" >/dev/null 2>&1 || fail "MISSING_$t" 2; done
[[ -d "$DAILY" && ! -L "$DAILY" ]] || fail DAILY_DIR_MISSING 4

stamp=""
while IFS= read -r n; do [[ "$n" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] && stamp="$n"; done < <(ls -1 "$DAILY" | LC_ALL=C sort)
[[ -n "$stamp" ]] || fail NO_DAILY_SNAPSHOT 4
snap="$DAILY/$stamp"
[[ -d "$snap" && ! -L "$snap" && -f "$snap/platform.dump" && -f "$snap/SHA256SUMS" ]] || fail SNAPSHOT_INCOMPLETE 4
( cd "$snap" && sha256sum -c --quiet SHA256SUMS ) >/dev/null 2>&1 || fail SNAPSHOT_CHECKSUM_MISMATCH 5

scratch="kmj_drill_$(date -u +%Y%m%d%H%M%S)_$$"
[[ "$scratch" != "$LIVE_DB" ]] || fail SCRATCH_EQUALS_LIVE 6
pg() { runuser -u "$RUNAS_PG" -- psql -X -q -At -v ON_ERROR_STOP=1 "$@"; }
cleanup() { pg -d postgres -c "DROP DATABASE IF EXISTS \"$scratch\"" >/dev/null 2>&1 || true; }
trap cleanup EXIT

pg -d postgres -c "CREATE DATABASE \"$scratch\"" >/dev/null || fail SCRATCH_CREATE 7

"$PG_RESTORE" --no-owner --no-privileges -f - "$snap/platform.dump" \
  | sed '/^SET transaction_timeout = 0;$/d' \
  | pg -d "$scratch" >/dev/null || fail RESTORE_FAILED 8

list_tables() { pg -d "$1" -c "select tablename from pg_tables where schemaname='public' order by 1"; }
count_rows() { pg -d "$1" -c "select count(*) from public.\"$2\""; }

mapfile -t snap_tables < <(list_tables "$scratch")
mapfile -t live_tables < <(list_tables "$LIVE_DB")
[[ "${#snap_tables[@]}" -gt 0 ]] || fail NO_TABLES_RESTORED 9

verdict=PASS; missing_in_live=0; extra_in_live=0; shrunk=0; drift_up=0; equal=0
rows=""
declare -A live_set=()
for t in "${live_tables[@]}"; do live_set["$t"]=1; done
declare -A snap_set=()
for t in "${snap_tables[@]}"; do snap_set["$t"]=1; done
for t in "${live_tables[@]}"; do [[ -n "${snap_set[$t]:-}" ]] || extra_in_live=$((extra_in_live+1)); done
for t in "${snap_tables[@]}"; do
  [[ "$t" =~ ^[A-Za-z0-9_]+$ ]] || fail TABLE_NAME_UNSAFE 9
  s="$(count_rows "$scratch" "$t")"
  if [[ -z "${live_set[$t]:-}" ]]; then missing_in_live=$((missing_in_live+1)); rows+="$t snapshot=$s live=MISSING"$'\n'; continue; fi
  l="$(count_rows "$LIVE_DB" "$t")"
  if (( s > l + TOL )); then shrunk=$((shrunk+1)); rows+="$t snapshot=$s live=$l SHRUNK"$'\n'
  elif (( s == l )); then equal=$((equal+1))
  else drift_up=$((drift_up+1)); rows+="$t snapshot=$s live=$l drift=+$((l-s))"$'\n'; fi
done
(( missing_in_live == 0 && shrunk == 0 )) || verdict=FAIL
(( extra_in_live == 0 )) || verdict=FAIL

cleanup
scratch_left="$(pg -d postgres -c "select count(*) from pg_database where datname='$scratch'")"
[[ "$scratch_left" == 0 ]] || fail SCRATCH_NOT_DROPPED 10
trap - EXIT

mkdir -p "$RECEIPT_DIR"; chmod 755 "$RECEIPT_DIR"
receipt="$RECEIPT_DIR/$stamp.$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "schema=KMJ_RESTORE_ROWCOUNT_DRILL_V1"
  echo "snapshot_stamp=$stamp"
  echo "verdict=$verdict"
  echo "tables_snapshot=${#snap_tables[@]} tables_live=${#live_tables[@]}"
  echo "equal=$equal drift_up=$drift_up shrunk=$shrunk missing_in_live=$missing_in_live extra_in_live=$extra_in_live"
  echo "restore_on_error_stop=yes scratch_dropped=yes row_level_equality_claimed=no"
  printf '%s' "$rows"
} > "$receipt"
chmod 644 "$receipt"
echo "RESTORE_DRILL=$verdict"
echo "STAMP=$stamp"
echo "RECEIPT=$receipt"
[[ "$verdict" == PASS ]]
