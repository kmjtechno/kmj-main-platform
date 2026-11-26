#!/usr/bin/env bash
# One-command owner launcher for the read-only backup checks.
#
# Takes the two check scripts from the shared checkout's origin/main, verifies
# each against a pinned SHA-256 BEFORE running it, runs them as root, and writes
# a counts-only summary where CodeBridge can read it (work/qa/kmj-receipts/ in
# the project checkout) so nobody has to paste terminal output.
#
# Never edits the working tree or HEAD, never pushes, restores only into a
# disposable scratch database, deletes nothing but that scratch database.
# Env (tests override): KMJ_REPO, KMJ_SKIP_FETCH, KMJ_PIN_DRILL, KMJ_PIN_STORAGE
set -Eeuo pipefail
umask 022

REPO="${KMJ_REPO:-/srv/kmj-codebridge-projects/kmj-main-platform}"
PIN_DRILL="${KMJ_PIN_DRILL:-0d812e0f947b83dd7d47084269683dcd6f64bff752d1388627fae3011ec0524f}"
PIN_STORAGE="${KMJ_PIN_STORAGE:-5f2dc9179962a5d8886a8977034a7324e4f1d80bb380d83ce77ec7c9bb21ea1d}"
ENV_FILE="${KMJ_ENV_FILE:-/home/kmjprod/current/apps/platform/.env}"
OUT="$REPO/work/qa/kmj-receipts"

fail() { echo "BACKUP_CHECKS=BLOCKED_$1" >&2; exit "${2:-2}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED
[[ -d "$REPO/.git" ]] || fail REPO_MISSING
G=(git -c safe.directory='*' -C "$REPO")

if [[ "${KMJ_SKIP_FETCH:-}" != 1 ]]; then
  owner="$(stat -c %U "$REPO")"
  runuser -u "$owner" -- git -C "$REPO" fetch -q origin main || fail FETCH_FAILED
fi

tmp="$(mktemp -d)"; trap 'rm -rf -- "$tmp"' EXIT
chmod 700 "$tmp"
get() { # name pin dest
  "${G[@]}" show "origin/main:scripts/$1" > "$3" 2>/dev/null || fail "SCRIPT_NOT_ON_ORIGIN_MAIN_$1"
  [[ "$(sha256sum "$3" | cut -d' ' -f1)" == "$2" ]] || fail "HASH_MISMATCH_$1"
}
get kmj-backup-restore-rowcount-drill.sh "$PIN_DRILL" "$tmp/drill.sh"
get kmj-backup-storage-completeness-check.sh "$PIN_STORAGE" "$tmp/storage.sh"

[[ -f "$ENV_FILE" ]] || fail ENV_NOT_FOUND
DB="$(grep -m1 '^DB_DATABASE=' "$ENV_FILE" | cut -d= -f2- | tr -d '\042\047\015 ')"

mkdir -p "$OUT"; chmod 755 "$OUT"
summary="$OUT/summary.$(date -u +%Y%m%dT%H%M%SZ).txt"
rc_d=0; rc_s=0
{
  echo "schema=KMJ_BACKUP_CHECKS_SUMMARY_V1"
  echo "origin_main=$("${G[@]}" rev-parse origin/main)"
  echo "drill_pin=$PIN_DRILL"
  echo "storage_pin=$PIN_STORAGE"
  echo "--- restore row-count drill"
  KMJ_DRILL_LIVE_DB="$DB" KMJ_DRILL_RECEIPT_DIR="$OUT" bash "$tmp/drill.sh" 2>&1 || rc_d=$?
  echo "drill_exit=$rc_d"
  echo "--- storage completeness"
  KMJ_STORAGE_RECEIPT_DIR="$OUT" bash "$tmp/storage.sh" 2>&1 || rc_s=$?
  echo "storage_exit=$rc_s"
} > "$summary"
chmod 644 "$summary" "$OUT"/*.txt 2>/dev/null || true
echo "BACKUP_CHECKS=DONE drill_exit=$rc_d storage_exit=$rc_s"
echo "SUMMARY=$summary"
