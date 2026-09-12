#!/usr/bin/env bash
set -euo pipefail

: "${BACKUP_DATABASE_URL:?BACKUP_DATABASE_URL is required}"
: "${BACKUP_REMOTE:?BACKUP_REMOTE is required, e.g. r2:kmj-platform/staging}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT is required}"

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/platform" && pwd)}"
BACKUP_TIER="${BACKUP_TIER:-daily}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOST_ID="$(hostname -s 2>/dev/null || hostname)"
GIT_SHA="$(git -C "$APP_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
NAME="kmj-platform-${BACKUP_TIER}-${HOST_ID}-${STAMP}"
WORKDIR="$(mktemp -d)"
STATUS_DIR="${BACKUP_STATUS_DIR:-$APP_ROOT/storage/app/private/ops}"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT
chmod 700 "$WORKDIR"

for command in pg_dump tar sha256sum age rclone; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $command" >&2
    exit 2
  }
done

test -d "$APP_ROOT/storage/app" || {
  echo "ERROR: application storage not found at $APP_ROOT/storage/app" >&2
  exit 3
}

pg_dump --dbname="$BACKUP_DATABASE_URL" --format=custom --file="$WORKDIR/database.dump"
tar -C "$APP_ROOT" -czf "$WORKDIR/storage.tar.gz" storage/app

{
  printf 'created_at_utc=%s\n' "$STAMP"
  printf 'host=%s\n' "$HOST_ID"
  printf 'tier=%s\n' "$BACKUP_TIER"
  printf 'git_sha=%s\n' "$GIT_SHA"
} > "$WORKDIR/metadata.txt"

(
  cd "$WORKDIR"
  sha256sum database.dump storage.tar.gz metadata.txt > SHA256SUMS
  tar -czf bundle.tar.gz database.dump storage.tar.gz metadata.txt SHA256SUMS
)

age -r "$BACKUP_AGE_RECIPIENT" -o "$WORKDIR/$NAME.tar.gz.age" "$WORKDIR/bundle.tar.gz"
rclone copyto "$WORKDIR/$NAME.tar.gz.age" "${BACKUP_REMOTE%/}/$BACKUP_TIER/$NAME.tar.gz.age" --checksum

# Publish a local, non-secret freshness marker only after the remote upload succeeds.
# The Ops Command Center reads this evidence; it never receives backup credentials or remote URLs.
mkdir -p "$STATUS_DIR"
chmod 700 "$STATUS_DIR"
STATUS_TMP="$STATUS_DIR/backup-status-$BACKUP_TIER.status.tmp"
STATUS_FILE="$STATUS_DIR/backup-status-$BACKUP_TIER.status"
{
  printf 'status=success\n'
  printf 'tier=%s\n' "$BACKUP_TIER"
  printf 'completed_at_utc=%s\n' "$COMPLETED_AT"
  printf 'git_sha=%s\n' "$GIT_SHA"
} > "$STATUS_TMP"
chmod 600 "$STATUS_TMP"
mv -f "$STATUS_TMP" "$STATUS_FILE"

echo "Backup uploaded successfully: $BACKUP_TIER/$NAME.tar.gz.age"
