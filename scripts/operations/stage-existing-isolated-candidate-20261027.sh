#!/usr/bin/env bash
# Exact approved SHA only. Isolated staging build; NEVER changes a live link.
set -Eeuo pipefail
umask 077

block() { echo "KMJ_STAGE_CANDIDATE=BLOCKED_$1"; exit 2; }
[[ "$#" -eq 2 ]] || block ARGUMENTS
case "$1" in --inspect|--prepare) mode="$1" ;; *) block MODE ;; esac
sha="$2"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || block SHA
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" == 0 ]] || block HOST

remote=https://github.com/kmjtechno/kmj-main-platform.git
base=/home/kmjstage/releases
site=/home/kmjstage/htdocs/staging.kmjtechno.com
prod=/home/kmjprod/current
[[ -L "$prod" && -L "$site" && -d "$base" && ! -L "$base" ]] || block LAYOUT
prod_before="$(readlink -f "$prod")" || block PRODUCTION_PATH
[[ "$prod_before" == /home/kmjprod/releases/platform-* ]] || block PRODUCTION_PATH
stage_app="$(readlink -f "$site")" || block STAGING_PATH
[[ "$stage_app" == /home/kmjstage/releases/*/apps/platform ]] || block STAGING_PATH
release="$(dirname "$(dirname "$stage_app")")"
[[ -d "$release/.git" ]] || block CURRENT_STAGE_GIT
[[ -f "$stage_app/.env" && ! -L "$stage_app/.env" ]] || block STAGING_ENV
[[ "$(stat -c %U "$stage_app/.env")" == kmjstage ]] || block ENV_OWNER
case "$(stat -c %a "$stage_app/.env")" in 400|600) ;; *) block ENV_MODE ;; esac
grep -Fxq APP_ENV=staging "$stage_app/.env" || block ENV_NOT_STAGING
grep -Fxq APP_URL=https://staging.kmjtechno.com "$stage_app/.env" || block ENV_URL
[[ "$(id -u kmjstage)" -ne 0 ]] || block STAGING_USER
[[ "$(stat -c %U "$base")" == kmjstage ]] || block RELEASE_OWNER
[[ -S /run/php/kmjstage-php84-fpm.sock ]] || block STAGING_FPM_SOCKET
[[ "$(systemctl is-active nginx)" == active ]] || block NGINX
[[ "$(systemctl is-active php8.4-fpm)" == active ]] || block PHP_FPM
for bin in git runuser composer npm node php8.4 flock; do
  command -v "$bin" >/dev/null 2>&1 || block "MISSING_$bin"
done
before_sha="$(runuser -u kmjstage -- git -C "$release" rev-parse HEAD 2>/dev/null)" || block STAGING_GIT_SHA
[[ "$before_sha" =~ ^[a-f0-9]{40}$ ]] || block STAGING_GIT_SHA
[[ "$(basename "$release")" == "$before_sha" ]] || block STAGING_RELEASE_NAME
[[ -f "$stage_app/artisan" && -s "$stage_app/public/build/manifest.json" ]] || block STAGING_ARTIFACT
approved="$(git ls-remote --exit-code "$remote" refs/heads/staging-approved 2>/dev/null | awk '{print $1}')" || block REMOTE_APPROVAL
[[ "$approved" == "$sha" ]] || block APPROVAL_DRIFT
candidate="$base/$sha"
[[ ! -L "$candidate" ]] || block CANDIDATE_SYMLINK

echo "STAGING_CURRENT_SHA=$before_sha"
echo "STAGING_APPROVED_SHA=$approved"
if [[ -L "$stage_app/storage" ]]; then echo STAGING_STORAGE=LINK_NEEDS_ATTESTATION; else echo STAGING_STORAGE=LOCAL_NEEDS_CONTINUITY_PLAN; fi
if [[ -e "$candidate" ]]; then echo STAGING_CANDIDATE=EXISTS; else echo STAGING_CANDIDATE=AVAILABLE; fi
[[ "$(readlink -f "$prod")" == "$prod_before" && "$(readlink -f "$site")" == "$stage_app" ]] || block LIVE_POINTER_CHANGED
if [[ "$mode" == --inspect ]]; then echo 'KMJ_STAGE_CANDIDATE=INSPECT_PASS_NO_CHANGES'; exit 0; fi

[[ "$before_sha" != "$sha" ]] || block ALREADY_LIVE_ON_STAGE
[[ ! -e "$candidate" ]] || block CANDIDATE_ALREADY_EXISTS
df -Pk "$base" | awk 'END {exit !($4 >= 2097152)}' || block LOW_DISK
exec 9>/run/lock/kmj-stage-candidate.lock
flock -n 9 || block LOCK_BUSY
[[ "$(readlink -f "$prod")" == "$prod_before" && "$(readlink -f "$site")" == "$stage_app" ]] || block LIVE_POINTER_CHANGED
[[ ! -e "$candidate" ]] || block CANDIDATE_CREATED
short="$(printf '%s' "$sha" | cut -c1-12)"
scratch="$(mktemp -d "$base/.kmj-stage-candidate-$short.XXXXXXXX")" || block SCRATCH
cleanup() {
  case "$scratch" in "$base/.kmj-stage-candidate-$short."*)
    if [[ -d "$scratch" && ! -L "$scratch" ]]; then rm -rf -- "$scratch"; fi ;;
  esac
}
trap cleanup EXIT
chown kmjstage:kmjstage "$scratch"
chmod 0700 "$scratch"
tree="$scratch/repo"
runuser -u kmjstage -- git clone --quiet --depth 1 --single-branch --branch staging-approved -- "$remote" "$tree"
[[ "$(runuser -u kmjstage -- git -C "$tree" rev-parse HEAD)" == "$sha" ]] || block FETCHED_HEAD
app="$tree/apps/platform"
[[ -f "$app/composer.lock" && -f "$app/package-lock.json" && ! -e "$app/.env" ]] || block APPROVED_APP
install -o kmjstage -g kmjstage -m 0600 "$stage_app/.env" "$app/.env"
runuser -u kmjstage -- bash -c '
  set -Eeuo pipefail
  cd "$1"
  COMPOSER_MEMORY_LIMIT=-1 composer install --no-dev --no-scripts --no-interaction --prefer-dist --optimize-autoloader --no-progress --no-ansi
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
  php8.4 artisan route:list --path=api/codebridge --no-ansi >/dev/null
' _ "$app"
[[ -s "$app/vendor/autoload.php" && -s "$app/public/build/manifest.json" ]] || block BUILD_MISSING
[[ "$(runuser -u kmjstage -- git -C "$tree" rev-parse HEAD)" == "$sha" ]] || block BUILD_HEAD_CHANGED
[[ -z "$(runuser -u kmjstage -- git -C "$tree" status --porcelain --untracked-files=normal)" ]] || block SOURCE_DIRTY
now="$(git ls-remote --exit-code "$remote" refs/heads/staging-approved 2>/dev/null | awk '{print $1}')" || block APPROVAL_RECHECK
[[ "$now" == "$sha" ]] || block APPROVAL_MOVED
[[ "$(readlink -f "$prod")" == "$prod_before" && "$(readlink -f "$site")" == "$stage_app" ]] || block LIVE_POINTER_CHANGED
[[ ! -e "$candidate" && ! -L "$candidate" ]] || block CANDIDATE_CREATED
mv -T -- "$tree" "$candidate"
[[ "$(runuser -u kmjstage -- git -C "$candidate" rev-parse HEAD)" == "$sha" ]] || block FINAL_SHA
[[ "$(readlink -f "$prod")" == "$prod_before" && "$(readlink -f "$site")" == "$stage_app" ]] || block LIVE_POINTER_CHANGED
echo KMJ_STAGE_CANDIDATE=PREPARED_ISOLATED_NOT_LIVE
echo "STAGING_CANDIDATE_SHA=$sha"
echo STAGING_STORAGE_CONTINUITY=NOT_VERIFIED
echo STAGING_DATABASE_MIGRATIONS=NOT_PERFORMED
echo STAGING_NGINX_PHP_SYSTEMD=UNCHANGED
echo PRODUCTION_POINTER=UNCHANGED
