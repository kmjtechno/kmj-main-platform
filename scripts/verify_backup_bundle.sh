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

# Validate the decrypted outer archive BEFORE any extraction. GNU tar -x
# can honor traversal, symlinks and hardlinks in a malicious backup. Only
# files emitted by scripts/backup_platform.sh are part of this contract.
python3 - "$WORKDIR/bundle.tar.gz" "$WORKDIR" <<'PY'
import re
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

source, destination = Path(sys.argv[1]), Path(sys.argv[2])
expected = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
try:
    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        names = [item.name for item in members]
        if len(names) != len(expected) or set(names) != expected:
            raise ValueError("unexpected, missing or duplicate archive entries")
        free = shutil.disk_usage(destination).free
        # Leave headroom for verification and prevent declared-size disk exhaustion.
        total = sum(item.size for item in members)
        if any(not item.isfile() or item.size <= 0 for item in members):
            raise ValueError("nonregular or empty outer archive member")
        if total > free // 2:
            raise ValueError("archive larger than half remaining disk capacity")
        if any(item.size > 1024 * 1024 for item in members if item.name in ("SHA256SUMS", "metadata.txt")):
            raise ValueError("unbounded backup metadata")
        for item in members:
            payload = archive.extractfile(item)
            if payload is None:
                raise ValueError("unreadable archive member")
            with payload, (destination / item.name).open("xb") as target:
                shutil.copyfileobj(payload, target, 1024 * 1024)

    # sha256sum --check is intentionally retained, but only after constraining
    # the manifest to the three expected relative filenames.
    manifest = (destination / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    required = {"database.dump", "storage.tar.gz", "metadata.txt"}
    filenames = []
    for line in manifest:
        match = re.fullmatch(
            r"[0-9a-fA-F]{64}  (database\.dump|storage\.tar\.gz|metadata\.txt)",
            line,
        )
        if match is None:
            raise ValueError("unexpected checksum manifest entry")
        filenames.append(match.group(1))
    if len(filenames) != 3 or set(filenames) != required:
        raise ValueError("missing or duplicate checksum entries")

    # This is archive validation, not a restore. Nevertheless, a tiny
    # compressed inner tar can advertise huge sparse members or millions of
    # entries and exhaust resources when a later recovery extracts it.
    # Use fixed, non-overridable limits so the verifier fails closed.
    max_storage_entries = 100_000
    max_storage_bytes = 256 * 1024 * 1024 * 1024
    storage_entries = 0
    storage_bytes = 0
    seen_storage_paths = set()
    with tarfile.open(destination / "storage.tar.gz", "r:gz") as storage:
        for item in storage:
            storage_entries += 1
            storage_bytes += item.size
            if (
                storage_entries > max_storage_entries
                or item.size < 0
                or storage_bytes > max_storage_bytes
                or item.name in seen_storage_paths
            ):
                raise ValueError("storage archive limits or uniqueness violated")
            seen_storage_paths.add(item.name)
            name = PurePosixPath(item.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or name.parts[:2] != ("storage", "app")
                or not (item.isfile() or item.isdir())
                or item.sparse is not None
            ):
                raise ValueError("unsafe storage archive member")
except (OSError, ValueError, UnicodeError, tarfile.TarError) as exc:
    # Avoid printing archive member paths or private source details.
    print("ERROR: unsafe or invalid decrypted backup archive", file=sys.stderr)
    sys.exit(3)
print("PASS: bounded backup archive member and checksum manifest validation")
PY

(
  cd "$WORKDIR"
  sha256sum --check SHA256SUMS
)

pg_restore --list "$WORKDIR/database.dump" >/dev/null
tar -tzf "$WORKDIR/storage.tar.gz" >/dev/null

# This verifier only checks archive readability and integrity. It never
# restores PostgreSQL, independently downloads the remote object, or validates
# a recovered application's behavior. Do not promote this result to a release
# recovery signoff.
echo 'Backup verification PASS: encrypted archive decrypts, checksums match, and archives are readable.'
echo 'BACKUP_ARCHIVE_INTEGRITY=PASS'
echo 'INDEPENDENT_OFFSITE_RETRIEVAL=NOT_VERIFIED'
echo 'DATABASE_RESTORE=NOT_RUN'
echo 'APPLICATION_RECOVERY=NOT_VERIFIED'
