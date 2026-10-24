#!/usr/bin/env bash
# KMJ-elite: grant Nginx/www-data only minimal traversal/public read on staged
# CodeBridge agent-origin candidate. Does NOT deploy or alter live release/data.
set -Eeuo pipefail
umask 077

readonly SHA='b1d672bbc83a51ca3f8271435692825072444c8e'
readonly CANDIDATE="/home/kmjprod/releases/platform-${SHA:0:12}"
readonly EXPECTED_LIVE='/home/kmjprod/releases/platform-8070dad72c55'
readonly LIVE='/home/kmjprod/current'
readonly LOCK='/run/lock/kmj-main-platform-production-release.lock'
readonly ENVFILE="$CANDIDATE/apps/platform/.env"

block() { printf 'CANDIDATE_PUBLIC_ACL=BLOCKED %s\n' "$1"; exit 2; }

[[ "$(id -u)" == 0 && "$(hostname -s)" == 'KMJ-elite' ]] || block WRONG_HOST
for cmd in setfacl getfacl runuser git flock; do
  command -v "$cmd" >/dev/null 2>&1 || block "MISSING_$cmd"
done
id www-data >/dev/null 2>&1 || block WWW_DATA_MISSING
[[ -L "$LIVE" && "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
[[ -d "$CANDIDATE/.git" && ! -L "$CANDIDATE" ]] || block CANDIDATE_NOT_STAGED
[[ "$(runuser -u kmjprod -- git -C "$CANDIDATE" rev-parse HEAD)" == "$SHA" ]] || block CANDIDATE_SHA_MISMATCH
[[ -z "$(runuser -u kmjprod -- git -C "$CANDIDATE" status --porcelain --untracked-files=normal)" ]] || block CANDIDATE_GIT_DIRTY
[[ -s "$ENVFILE" && ! -L "$ENVFILE" ]] || block CANDIDATE_ENV_MISSING
[[ -d "$CANDIDATE/apps/platform/public" && ! -L "$CANDIDATE/apps/platform/public" ]] || block PUBLIC_DIR_UNSAFE
[[ -s "$CANDIDATE/apps/platform/public/index.php" ]] || block PUBLIC_INDEX_MISSING
[[ -s "$CANDIDATE/apps/platform/public/build/manifest.json" ]] || block PUBLIC_MANIFEST_MISSING
[[ ! -e "$CANDIDATE/apps/platform/public/storage" && ! -L "$CANDIDATE/apps/platform/public/storage" ]] || block PUBLIC_STORAGE_REQUIRES_REVIEW

# Private .env stays denied to the web worker; PHP-FPM user compatibility needs independent QA.
[[ "$(stat -c %U "$ENVFILE")" == kmjprod ]] || block ENV_OWNER_UNEXPECTED
runuser -u www-data -- test ! -r "$ENVFILE" || block NGINX_PRIVATE_ENV_ALREADY_EXPOSED

exec 9>"$LOCK"
flock -n 9 || block RELEASE_OPERATION_BUSY
[[ "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
for dir in "$CANDIDATE" "$CANDIDATE/apps" "$CANDIDATE/apps/platform"; do
  [[ -d "$dir" && ! -L "$dir" ]] || block PUBLIC_ANCESTOR_UNSAFE
  setfacl -m 'u:www-data:--x' "$dir" || block ANCESTOR_ACL_FAILED
done
setfacl -R -m 'u:www-data:rX' "$CANDIDATE/apps/platform/public" || block PUBLIC_TREE_ACL_FAILED

runuser -u www-data -- test -r "$CANDIDATE/apps/platform/public/index.php" || block PUBLIC_INDEX_UNREADABLE
runuser -u www-data -- test -r "$CANDIDATE/apps/platform/public/build/manifest.json" || block PUBLIC_MANIFEST_UNREADABLE
runuser -u www-data -- test ! -r "$ENVFILE" || block NGINX_PRIVATE_ENV_EXPOSED
[[ -z "$(runuser -u kmjprod -- git -C "$CANDIDATE" status --porcelain --untracked-files=normal)" ]] || block CANDIDATE_DIRTY_AFTER_ACL
[[ "$(readlink -f "$LIVE")" == "$EXPECTED_LIVE" ]] || block LIVE_RELEASE_CHANGED
echo 'CANDIDATE_PUBLIC_ACL=PASS'
echo 'NGINX_PUBLIC_FILES=READABLE'
echo 'NGINX_PRIVATE_ENV=DENIED'
echo 'STORAGE_CONTINUITY=NOT_ATTESTED'
echo 'PRODUCTION_SWITCH=NOT_ATTEMPTED'
echo 'LIVE_ENV_AND_DATABASE=UNTOUCHED'
