#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/platform" && pwd)}"
failed=0

check_command() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "PASS command:$name"
  else
    echo "FAIL command:$name" >&2
    failed=1
  fi
}

check_env() {
  local name="$1"
  if [ -n "${!name:-}" ]; then
    echo "PASS env:$name"
  else
    echo "FAIL env:$name" >&2
    failed=1
  fi
}

for command in pg_dump pg_restore tar sha256sum age rclone; do
  check_command "$command"
done

for name in BACKUP_DATABASE_URL BACKUP_REMOTE BACKUP_AGE_RECIPIENT; do
  check_env "$name"
done

if [ -d "$APP_ROOT/storage/app" ]; then
  echo 'PASS storage:application'
else
  echo "FAIL storage:$APP_ROOT/storage/app" >&2
  failed=1
fi

if [ "$failed" -ne 0 ]; then
  echo 'Backup preflight FAILED. No secret values were printed.' >&2
  exit 1
fi

echo 'Backup preflight PASS. Runtime dependencies and required configuration are present.'
