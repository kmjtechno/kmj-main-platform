#!/usr/bin/env bash
# Owner-only, SHA-pinned installer for ONE read-only offsite failure diagnostic.
# Installing does not read the journal, modify backup data or start any service.
set -Eeuo pipefail
umask 077

block() { printf 'KMJ_OFFSITE_DIAGNOSTIC_INSTALL=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$#" -eq 1 && ( "$1" == --inspect || "$1" == --install ) ]] || block ARGUMENTS
mode="$1"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
source="$script_dir/diagnose-offsite-backup-unit-20261029.sh"
target=/usr/local/libexec/kmj-main-platform-diagnose-offsite-backup-unit-20261029.sh
expected_sha=3ac8127f8e66ac4579330ae7671c2a2b31f68f6865c2a7c67e376adb475f6e32
[[ -f "$source" && ! -L "$source" ]] || block SOURCE_MISSING_OR_SYMLINK
[[ "$(sha256sum "$source" | cut -d' ' -f1)" == "$expected_sha" ]] || block SOURCE_HASH

if [[ "$mode" == --inspect ]]; then
  printf 'KMJ_OFFSITE_DIAGNOSTIC_SOURCE=HASH_VERIFIED\n'
  printf 'KMJ_OFFSITE_DIAGNOSTIC_INSTALL=INSPECT_ONLY\n'
  exit 0
fi

[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || block OWNER_HOST
root="$(dirname "$(dirname "$script_dir")")"
[[ "$root" =~ ^/root/kmj-approved/[a-f0-9]{40}$ ]] || block IMMUTABLE_SOURCE_PATH
[[ "$script_dir" == "$root/scripts/operations" ]] || block SOURCE_DIR
for component in /root /root/kmj-approved "$root" "$root/scripts" "$script_dir" "$source" "$0"; do
  [[ -e "$component" && ! -L "$component" ]] || block SOURCE_CHAIN
  [[ "$(stat -c '%u' -- "$component")" == 0 ]] || block SOURCE_OWNER
  mode_bits="$(stat -c '%a' -- "$component")"
  (( (8#$mode_bits & 8#7022) == 0 )) || block SOURCE_PERMISSIONS
done

[[ -d /usr/local/libexec && ! -L /usr/local/libexec ]] || block TARGET_DIR
[[ "$(stat -c '%u' /usr/local/libexec)" == 0 ]] || block TARGET_DIR_OWNER
target_mode="$(stat -c '%a' /usr/local/libexec)"
(( (8#$target_mode & 8#022) == 0 )) || block TARGET_DIR_PERMISSIONS
# Absolutely no overwrite, including an existing broken symlink.
[[ ! -e "$target" && ! -L "$target" ]] || block EXISTING_TARGET_REQUIRES_REVIEW

# Stage privately; use atomic hardlink creation so an unexpected concurrent
# target cannot be overwritten between the precheck and publish.
tmp="$(mktemp /usr/local/libexec/.kmj-offsite-diagnostic.XXXXXXXX)" || block STAGE_CREATE
cleanup() { rm -f -- "$tmp"; }
trap cleanup EXIT
install -o root -g root -m 0750 -T -- "$source" "$tmp" || block STAGE_COPY
[[ "$(sha256sum "$tmp" | cut -d' ' -f1)" == "$expected_sha" ]] || block STAGE_HASH
ln -T -- "$tmp" "$target" || block TARGET_EXISTS_OR_LINK_FAILED
# Drop the temporary hardlink; the final file must have exactly one link.
cleanup
trap - EXIT
# Do not claim a ready diagnostic unless the installed bytes and metadata match.
[[ -f "$target" && ! -L "$target" ]] || block TARGET_FILE
[[ "$(stat -c '%u:%g:%a:%h' -- "$target")" == "0:0:750:1" ]] || block TARGET_METADATA
[[ "$(sha256sum "$target" | cut -d' ' -f1)" == "$expected_sha" ]] || block TARGET_HASH
printf 'KMJ_OFFSITE_DIAGNOSTIC_INSTALL=PINNED_INACTIVE_ONLY\n'
printf 'KMJ_OFFSITE_DIAGNOSTIC_EXECUTION=NOT_ATTEMPTED\n'
printf 'KMJ_OFFSITE_BACKUP=NOT_VERIFIED\n'
printf 'KMJ_PRODUCTION=UNCHANGED\n'
