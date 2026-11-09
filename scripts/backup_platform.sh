#!/usr/bin/env bash
set -euo pipefail

: "${BACKUP_DATABASE_URL:?BACKUP_DATABASE_URL is required}"
: "${BACKUP_REMOTE:?BACKUP_REMOTE is required, e.g. r2:kmj-platform/staging}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT is required}"

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/platform" && pwd)}"
BACKUP_TIER="${BACKUP_TIER:-daily}"
# Validate before allocating temporary files or constructing a remote path.
case "$BACKUP_TIER" in daily|weekly|monthly) ;; *) echo "ERROR: invalid BACKUP_TIER" >&2; exit 2;; esac
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
HOST_ID="$(hostname -s 2>/dev/null || hostname)"
GIT_SHA="$(git -C "$APP_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
NAME="kmj-platform-${BACKUP_TIER}-${HOST_ID}-${STAMP}"
WORKDIR="$(mktemp -d)"
STATUS_DIR="${BACKUP_STATUS_DIR:-$APP_ROOT/storage/app/private/ops}"
STATUS_TMP=""

cleanup() {
  if [[ -n "$STATUS_TMP" && -f "$STATUS_TMP" ]]; then rm -f -- "$STATUS_TMP"; fi
  rm -rf -- "$WORKDIR"
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
REMOTE_OBJECT="${BACKUP_REMOTE%/}/$BACKUP_TIER/$NAME.tar.gz.age"
LOCAL_CIPHERTEXT="$WORKDIR/$NAME.tar.gz.age"

# A successful copy operation alone cannot prove that the encrypted object
# is retrievable or byte-identical. Read it back into the private scratch
# directory and verify before publishing any success/freshness marker.
if ! rclone copyto "$LOCAL_CIPHERTEXT" "$REMOTE_OBJECT" --checksum >/dev/null 2>&1; then
  echo "ERROR: offsite encrypted upload failed" >&2
  exit 4
fi
if ! rclone copyto "$REMOTE_OBJECT" "$WORKDIR/remote-readback.age" \
  --retries 1 --low-level-retries 1 >/dev/null 2>&1; then
  echo "ERROR: offsite encrypted readback failed" >&2
  exit 4
fi
LOCAL_SHA="$(sha256sum "$LOCAL_CIPHERTEXT" | cut -d ' ' -f1)"
REMOTE_SHA="$(sha256sum "$WORKDIR/remote-readback.age" | cut -d ' ' -f1)"
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  echo "ERROR: offsite encrypted readback checksum mismatch" >&2
  exit 4
fi

# The Ops Command Center marker is strictly a successful readback timestamp.
# It is NOT proof that a PostgreSQL restore or all customer uploads recovered.
mkdir -p -- "$STATUS_DIR"
if [[ -L "$STATUS_DIR" || ! -d "$STATUS_DIR" ]]; then
  echo "ERROR: unsafe backup status directory" >&2
  exit 4
fi
chmod 700 -- "$STATUS_DIR"
STATUS_TMP="$(mktemp "$STATUS_DIR/.backup-status-$BACKUP_TIER.XXXXXXXX")"
STATUS_FILE="$STATUS_DIR/backup-status-$BACKUP_TIER.status"
COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  printf 'status=success\n'
  printf 'tier=%s\n' "$BACKUP_TIER"
  printf 'completed_at_utc=%s\n' "$COMPLETED_AT"
  printf 'git_sha=%s\n' "$GIT_SHA"
} > "$STATUS_TMP"
chmod 600 -- "$STATUS_TMP"
mv -f -- "$STATUS_TMP" "$STATUS_FILE"
STATUS_TMP=""

echo "Backup encrypted upload and SHA-256 readback verified: $BACKUP_TIER/$NAME.tar.gz.age"
