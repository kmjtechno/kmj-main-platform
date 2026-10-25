#!/usr/bin/env bash
# Build a new immutable Main Platform candidate from exact GitHub main HEAD.
# No current/previous symlink changes, live .env, database or DNS operations.
set -Eeuo pipefail
umask 077

ROOT=/home/kmjprod
SOURCE=https://github.com/kmjtechno/kmj-main-platform.git
LIVE="$ROOT/current"
LOCK=/run/lock/kmj-main-platform-production-release.lock

block() { printf 'KMJ_FAST_STAGE=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$#" -eq 1 ]] || block EXACT_SHA_REQUIRED
sha="$1"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || block EXACT_SHA_REQUIRED
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || block WRONG_HOST
[[ -L "$LIVE" && -d "$ROOT/releases" && ! -L "$ROOT/releases" ]] || block LIVE_PATH_INVALID
before="$(readlink -f "$LIVE")" || block LIVE_POINTER_UNAVAILABLE
case "$before" in "$ROOT"/releases/platform-*) ;; *) block LIVE_POINTER_UNSAFE;; esac
[[ -d "$before" ]] || block LIVE_TARGET_MISSING
id kmjprod >/dev/null 2>&1 || block SERVICE_USER_MISSING
for bin in git runuser composer npm node php8.4 flock sha256sum; do
  command -v "$bin" >/dev/null 2>&1 || block "MISSING_$bin"
done
systemctl is-active --quiet nginx || block NGINX_NOT_ACTIVE
systemctl is-active --quiet php8.4-fpm || block PHP_FPM_NOT_ACTIVE
df -Pk "$ROOT" | awk 'END {exit !($4 >= 4194304)}' || block INSUFFICIENT_SPACE_4GB

# Refuse arbitrary PR/branch commits or a stale main tip.
remote="$(git ls-remote --exit-code "$SOURCE" refs/heads/main 2>/dev/null | awk '{print $1}')" || block REMOTE_MAIN_UNAVAILABLE
[[ "$remote" == "$sha" ]] || block REMOTE_MAIN_SHA_CHANGED

short="$(printf '%s' "$sha" | cut -c1-12)"
dest="$ROOT/releases/platform-$short"
[[ ! -L "$dest" ]] || block CANDIDATE_SYMLINK
exec 9>"$LOCK"
flock -n 9 || block PRODUCTION_RELEASE_BUSY
[[ "$(readlink -f "$LIVE")" == "$before" ]] || block LIVE_POINTER_CHANGED

verify() {
  local tree="$1"
  [[ -d "$tree/.git" && ! -L "$tree" ]] || block CANDIDATE_NOT_GIT
  [[ "$(runuser -u kmjprod -- git -C "$tree" rev-parse HEAD 2>/dev/null)" == "$sha" ]] || block CANDIDATE_HEAD_WRONG
  [[ -z "$(runuser -u kmjprod -- git -C "$tree" status --porcelain --untracked-files=normal 2>/dev/null)" ]] || block CANDIDATE_DIRTY
  [[ ! -e "$tree/apps/platform/.env" && ! -L "$tree/apps/platform/.env" ]] || block RUNTIME_ENV_REQUIRES_REVIEW
  for item in apps/platform/vendor/autoload.php apps/platform/public/build/manifest.json apps/platform/public/assets/kmj-codebridge-icon.png; do
    [[ -s "$tree/$item" && ! -L "$tree/$item" ]] || block BUILD_ARTIFACT_MISSING
  done
}
if [[ -e "$dest" ]]; then
  verify "$dest"
  echo "KMJ_FAST_STAGE=EXISTING_VERIFIED"
  echo "KMJ_CANDIDATE_SHA=$sha"
  echo 'KMJ_PRODUCTION=UNCHANGED'
  exit 0
fi

scratch="$(mktemp -d "$ROOT/releases/.kmj-fast-stage-$short.XXXXXXXX")" || block SCRATCH_CREATE_FAILED
cleanup() {
  # Only this invocation's newly created scratch may be cleaned up.
  case "$scratch" in
    "$ROOT/releases/.kmj-fast-stage-$short."*)
      if [[ -d "$scratch" && ! -L "$scratch" ]]; then rm -rf -- "$scratch"; fi;;
  esac
}
trap cleanup EXIT
chown kmjprod:kmjprod "$scratch"
chmod 0700 "$scratch"

runuser -u kmjprod -- env HOME="$ROOT" bash -s -- "$SOURCE" "$scratch/repo" "$sha" <<'BUILD'
set -Eeuo pipefail
umask 077
source_url="$1"; dest="$2"; exact="$3"
git init -q "$dest"
git -C "$dest" remote add origin "$source_url"
git -C "$dest" -c protocol.version=2 fetch --depth 1 --no-tags origin "$exact"
git -C "$dest" checkout --detach -q FETCH_HEAD
[[ "$(git -C "$dest" rev-parse HEAD)" == "$exact" ]] || exit 2
app="$dest/apps/platform"
[[ -s "$app/composer.lock" && -s "$app/package-lock.json" && -f "$app/.env.example" ]] || exit 2
cd "$app"
cp -- .env.example .env
chmod 0600 .env
trap 'rm -f -- .env' EXIT
composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts --no-progress
npm ci --ignore-scripts --no-audit --no-fund
npm run build
[[ -s public/build/manifest.json && -s vendor/autoload.php ]] || exit 2
rm -f -- .env
trap - EXIT
[[ -z "$(git -C "$dest" status --porcelain --untracked-files=normal)" ]] || exit 2
echo 'KMJ_ISOLATED_COMPOSER_NPM_VITE=PASS'
BUILD

verify "$scratch/repo"
[[ ! -e "$dest" && ! -L "$dest" ]] || block RACE_CANDIDATE_EXISTS
[[ "$(readlink -f "$LIVE")" == "$before" ]] || block LIVE_POINTER_CHANGED
mv -T -- "$scratch/repo" "$dest"
chmod 0750 "$dest"
verify "$dest"
[[ "$(readlink -f "$LIVE")" == "$before" ]] || block LIVE_POINTER_CHANGED
echo 'KMJ_FAST_STAGE=PASS'
echo "KMJ_CANDIDATE_SHA=$sha"
echo 'KMJ_PUBLIC_ORIGIN=https://kmjtechno.com'
echo 'KMJ_PUBLIC_STAGING_REQUIRED=NO'
echo 'KMJ_PRODUCTION=UNCHANGED'
echo 'KMJ_NEXT=NEW_BACKUP_RESTORE_OWNER_APPROVAL_AND_GUARDED_ACTIVATION'
