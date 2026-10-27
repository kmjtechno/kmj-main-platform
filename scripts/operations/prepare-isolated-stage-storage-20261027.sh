#!/usr/bin/env bash
# Prepare an existing isolated staging candidate to share the CURRENT staging
# storage root. Do not copy or mutate live storage. Old release is the storage
# anchor and MUST be retained until a separate verified shared-storage migration.
set -Eeuo pipefail
umask 077
block() { echo "KMJ_STAGE_STORAGE=BLOCKED_$1"; exit 2; }
[[ "$#" == 2 ]] || block ARGUMENTS
case "$1" in --inspect|--prepare) mode="$1" ;; *) block MODE ;; esac
sha="$2"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || block SHA
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" == 0 ]] || block HOST
prod=/home/kmjprod/current
stage=/home/kmjstage/htdocs/staging.kmjtechno.com
base=/home/kmjstage/releases
[[ -L "$prod" && -L "$stage" && -d "$base" && ! -L "$base" ]] || block LAYOUT
prod_before="$(readlink -f "$prod")" || block PROD_READLINK
stage_before="$(readlink -f "$stage")" || block STAGE_READLINK
[[ "$prod_before" == /home/kmjprod/releases/platform-* ]] || block PROD_SCOPE
[[ "$stage_before" == /home/kmjstage/releases/*/apps/platform ]] || block STAGE_SCOPE
old="$stage_before"
candidate="$base/$sha"
new="$candidate/apps/platform"
[[ -d "$candidate/.git" && ! -L "$candidate" && -d "$new/public" && ! -L "$new/public" ]] || block CANDIDATE_LAYOUT
[[ "$new" != "$old" ]] || block CANDIDATE_LIVE
old_release="$(dirname "$(dirname "$old")")"
[[ "$(basename "$old_release")" =~ ^[a-f0-9]{40}$ ]] || block OLD_NAME
[[ "$(runuser -u kmjstage -- git -C "$old_release" rev-parse HEAD 2>/dev/null)" == "$(basename "$old_release")" ]] || block OLD_SHA
[[ "$(runuser -u kmjstage -- git -C "$candidate" rev-parse HEAD 2>/dev/null)" == "$sha" ]] || block NEW_SHA
for e in "$old/.env" "$new/.env"; do
  [[ -f "$e" && ! -L "$e" && "$(stat -c %U "$e")" == kmjstage ]] || block STAGE_ENV
done
[[ "$(sha256sum "$old/.env" | awk '{print $1}')" == "$(sha256sum "$new/.env" | awk '{print $1}')" ]] || block ENV_MISMATCH
[[ -d "$old/storage" && ! -L "$old/storage" && "$(stat -c %U "$old/storage")" == kmjstage ]] || block OLD_STORAGE
[[ "$(find "$old/storage" -type l -print -quit)" == "" ]] || block OLD_STORAGE_LINKS
[[ -d "$old/storage/app/public" && ! -L "$old/storage/app/public" ]] || block OLD_PUBLIC_STORAGE_MISSING
[[ "$(stat -c %U "$candidate")" == kmjstage ]] || block CANDIDATE_OWNER
[[ -d "$new/storage" && ! -L "$new/storage" && "$(stat -c %U "$new/storage")" == kmjstage ]] || block CANDIDATE_STORAGE
[[ ! -e "$new/public/storage" && ! -L "$new/public/storage" ]] || block PUBLIC_LINK_ALREADY_EXISTS
archive="$candidate/.kmj-pre-shared-build-storage"
[[ ! -e "$archive" && ! -L "$archive" ]] || block STORAGE_ARCHIVE_EXISTS
approved="$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/staging-approved 2>/dev/null | awk '{print $1}')" || block APPROVED_UNAVAILABLE
[[ "$sha" == "$approved" ]] || block APPROVED_SHA_MOVED
echo "STAGING_CANDIDATE_SHA=$sha"
echo "STAGING_LIVE_SOURCE_SHA=$(basename "$old_release")"
echo 'STAGING_STORAGE_STRATEGY=SHARE_CURRENT_STAGE_STORAGE'
echo 'STAGING_OLD_RELEASE=RETAIN_AS_STORAGE_ANCHOR'
echo 'STAGING_DATABASE=UNCHANGED'
[[ "$(readlink -f "$stage")" == "$stage_before" && "$(readlink -f "$prod")" == "$prod_before" ]] || block POINTER_CHANGED
if [[ "$mode" == --inspect ]]; then
  echo 'KMJ_STAGE_STORAGE=INSPECT_PASS_NO_CHANGES'
  exit 0
fi
exec 9>/run/lock/kmj-stage-storage-preparation.lock
flock -n 9 || block LOCK_BUSY
[[ "$(readlink -f "$stage")" == "$stage_before" && "$(readlink -f "$prod")" == "$prod_before" ]] || block POINTER_CHANGED
[[ -d "$new/storage" && ! -L "$new/storage" && ! -e "$archive" && ! -L "$archive" ]] || block CANDIDATE_CHANGED
[[ ! -e "$new/public/storage" && ! -L "$new/public/storage" ]] || block PUBLIC_PATH_CHANGED
moved=0
linked=0
public_linked=0
restore_on_failure() {
  code=$?
  if [[ "$code" != 0 ]]; then
    if [[ "$public_linked" == 1 && -L "$new/public/storage" && "$(readlink "$new/public/storage")" == ../storage/app/public ]]; then
      rm -- "$new/public/storage"
    fi
    if [[ "$linked" == 1 && -L "$new/storage" && "$(readlink "$new/storage")" == "$old/storage" ]]; then
      rm -- "$new/storage"
    fi
    if [[ "$moved" == 1 && ! -e "$new/storage" && -d "$archive" ]]; then
      mv -T -- "$archive" "$new/storage"
    fi
  fi
}
trap restore_on_failure EXIT
mv -T -- "$new/storage" "$archive"
moved=1
runuser -u kmjstage -- ln -s -- "$old/storage" "$new/storage"
linked=1
runuser -u kmjstage -- ln -s -- ../storage/app/public "$new/public/storage"
public_linked=1
[[ "$(readlink -f "$new/storage")" == "$old/storage" ]] || block STORAGE_LINK_VERIFY
[[ "$(readlink -f "$new/public/storage")" == "$old/storage/app/public" ]] || block PUBLIC_LINK_VERIFY
[[ "$(readlink -f "$stage")" == "$stage_before" && "$(readlink -f "$prod")" == "$prod_before" ]] || block POINTER_CHANGED
echo 'KMJ_STAGE_STORAGE=PREPARED_SHARED_OLD_RELEASE_RETAIN_REQUIRED'
echo 'STAGING_POINTER=UNCHANGED'
echo 'PRODUCTION_POINTER=UNCHANGED'
echo 'STAGING_BACKUP_AND_RESTORE=NOT_YET_VERIFIED'
echo 'STAGING_ACTIVATION=NOT_ATTEMPTED'
