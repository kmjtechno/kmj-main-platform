#!/usr/bin/env bash
set -euo pipefail

: "${BACKUP_AGE_IDENTITY:?BACKUP_AGE_IDENTITY must point to an age identity file}"

BUNDLE_PATH="${1:?usage: verify_backup_bundle.sh <encrypted-backup.age>}"
WORKDIR="$(mktemp -d)"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT
chmod 700 "$WORKDIR"

for command in age tar sha256sum pg_restore; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $command" >&2
    exit 2
  }
done

test -f "$BUNDLE_PATH" || {
  echo "ERROR: backup bundle not found: $BUNDLE_PATH" >&2
  exit 3
}

age -d -i "$BACKUP_AGE_IDENTITY" -o "$WORKDIR/bundle.tar.gz" "$BUNDLE_PATH"
tar -C "$WORKDIR" -xzf "$WORKDIR/bundle.tar.gz"

(
  cd "$WORKDIR"
  sha256sum --check SHA256SUMS
)

pg_restore --list "$WORKDIR/database.dump" >/dev/null
tar -tzf "$WORKDIR/storage.tar.gz" >/dev/null

echo 'Backup verification PASS: encryption, checksums, database archive, and storage archive are readable.'
