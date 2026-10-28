#!/usr/bin/env bash
# Read-only staging inventory for the verified root:root 0755 shared parent.
# Never changes customer uploads, staging release, nginx, database, or permissions.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { printf 'KMJ_STAGE_INVENTORY_V4=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 && $# -eq 0 ]] || fail HOST_OR_ARGS
qa=/srv/kmj-codebridge-projects/kmj-main-platform/work/qa
out="$qa/KMJ_STAGE_SHARED_INVENTORY_V4_20261028.txt"
[[ -d "$qa" && ! -L "$qa" && ! -e "$out" && ! -L "$out" ]] || fail RECEIPT_EXISTS_OR_UNSAFE
prod=/home/kmjprod/current
stage=/home/kmjstage/htdocs/staging.kmjtechno.com
old=9d15e14e39564ffb1e66085a483feb8331f9718f
expected_stage="/home/kmjstage/releases/$old/apps/platform"
expected_prod=/home/kmjprod/releases/platform-8070dad72c55
[[ -L "$prod" && "$(readlink -f -- "$prod")" == "$expected_prod" ]] || fail PRODUCTION_POINTER_DRIFT
[[ -L "$stage" && "$(readlink -f -- "$stage")" == "$expected_stage" ]] || fail STAGING_POINTER_DRIFT

shared=/home/kmjstage/shared
[[ -d "$shared" && ! -L "$shared" ]] || fail SHARED_PARENT_KIND
[[ "$(stat -c '%u:%g:%a' -- "$shared")" == '0:0:755' ]] || fail SHARED_PARENT_POLICY
stage_uid="$(id -u kmjstage)" || fail STAGING_USER
[[ "$stage_uid" =~ ^[1-9][0-9]{0,9}$ ]] || fail STAGING_USER

source_link="$expected_stage/storage/app"
[[ -L "$source_link" || -d "$source_link" ]] || fail OLD_UPLOAD_MISSING
source_dir="$(readlink -f -- "$source_link")" || fail SOURCE_RESOLUTION
case "$source_dir" in
 /home/kmjstage/releases/*/apps/platform/storage/app|/home/kmjstage/shared/*) ;;
 *) fail SOURCE_OUT_OF_SCOPE ;;
esac
[[ -d "$source_dir" && ! -L "$source_dir" ]] || fail SOURCE_KIND
if [[ "$source_dir" == /home/kmjstage/releases/* ]]; then scope=RELEASE_BOUND; else scope=PERSISTENT_SHARED; fi

files="$(find "$source_dir" -xdev -type f -printf '.' | wc -c)"
symlinks="$(find "$source_dir" -xdev -type l -printf '.' | wc -c)"
hardlinks="$(find "$source_dir" -xdev -type f -links +1 -printf '.' | wc -c)"
recent="$(find "$source_dir" -xdev -type f -mmin -10 -printf '.' | wc -c)"
bytes="$(du -sb -- "$source_dir" | awk '{print $1}')"
refs=0
for path in /home/kmjstage/releases/*/apps/platform/storage/app; do
 if [[ -L "$path" ]] && [[ "$(readlink -f -- "$path" 2>/dev/null || true)" == "$source_dir" ]]; then
   refs=$((refs + 1))
 fi
done

target="$shared/kmj-platform-uploads"
if [[ -L "$target" ]]; then target_kind=SYMLINK_REVIEW
elif [[ -d "$target" ]]; then target_kind=DIRECTORY_OCCUPIED
elif [[ -e "$target" ]]; then target_kind=OTHER_OCCUPIED
else target_kind=ABSENT; fi
if [[ "$(readlink -f -- "$source_link/private/product-artwork" 2>/dev/null || true)" == /home/kmjstage/shared/product-artwork ]]; then
 artwork=SHARED_EXACT
else
 artwork=REQUIRES_REVIEW
fi
if [[ -L "$expected_stage/public/storage" ]]; then public=SYMLINK
elif [[ -d "$expected_stage/public/storage" ]]; then public=DIRECTORY
elif [[ -e "$expected_stage/public/storage" ]]; then public=OTHER
else public=ABSENT; fi
free_kb="$(df -Pk -- "$shared" | awk 'END{print $4}')"
for number in "$files" "$symlinks" "$hardlinks" "$recent" "$bytes" "$refs" "$free_kb"; do
 [[ "$number" =~ ^[0-9]{1,20}$ ]] || fail INVALID_METRIC
done

tmp="$(mktemp "$qa/.stage-shared-inventory-v4.XXXXXXXX")" || fail TEMP
trap 'rm -f -- "$tmp"' EXIT
{
  printf 'SCHEMA=KMJ_STAGE_SHARED_INVENTORY_V4\n'
  printf 'SHARED_PARENT_POLICY=PASS_ROOT_OWNED_0755\n'
  printf 'SOURCE_SCOPE=%s\nSOURCE_OWNER_UID=%s\n' "$scope" "$(stat -c %u -- "$source_dir")"
  printf 'SOURCE_FILES=%s\nSOURCE_SYMLINKS=%s\nSOURCE_HARDLINKS=%s\nSOURCE_RECENT_WRITES_10M=%s\nSOURCE_BYTES=%s\nSOURCE_RELEASE_REFERENCES=%s\n' "$files" "$symlinks" "$hardlinks" "$recent" "$bytes" "$refs"
  printf 'TARGET_KIND=%s\nARTWORK_LINK=%s\nOLD_PUBLIC_KIND=%s\nFREE_KB=%s\n' "$target_kind" "$artwork" "$public" "$free_kb"
  printf 'PRODUCTION_POINTER=UNCHANGED\nSTAGING_POINTER=UNCHANGED\n'
  printf 'CUSTOMER_FILES_MODIFIED=NO\nSTAGING_RELEASE_MODIFIED=NO\nPRODUCTION_MODIFIED=NO\n'
  printf 'OWNER_APPROVAL=NOT_ATTESTED\nBACKUP_RESTORE=NOT_ATTESTED\n'
} >"$tmp"
chmod 0644 "$tmp"
ln -- "$tmp" "$out" || fail RECEIPT_COLLISION
echo 'KMJ_STAGE_INVENTORY_V4=PASS_READ_ONLY'
echo 'KMJ_STAGE_INVENTORY_V4_RECEIPT=work/qa/KMJ_STAGE_SHARED_INVENTORY_V4_20261028.txt'
