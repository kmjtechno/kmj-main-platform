#!/usr/bin/env bash
# Non-deploying immutable source+frontend candidate builder on fixed KMJ-elite.
# It must NOT modify live current/previous, database, approval, nginx, PHP,
# backup, DNS, payment, entitlement or email.
set -Eeuo pipefail
umask 027
readonly SHA='8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b'
readonly PREFIX="$(printf '%s' "$SHA" | cut -c 1-12)"
readonly ROOT='/home/kmjprod'
readonly DEST="$ROOT/releases/platform-$PREFIX"
readonly SCRATCH="$ROOT/releases/.building-platform-$PREFIX"
readonly SOURCE='https://github.com/kmjtechno/kmj-main-platform.git'
notice() { printf '%s\n' "$1"; }
block() { notice "KMJ_CANDIDATE=BLOCKED REASON=$1"; exit 2; }
on_error() { notice 'KMJ_CANDIDATE=FAIL (current production unchanged)'; }
trap on_error ERR

[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || block WRONG_HOST
id kmjprod >/dev/null 2>&1 || block SERVICE_USER_MISSING
[[ -L "$ROOT/current" ]] || block CURRENT_RELEASE_NOT_SYMLINK
before="$(readlink -f "$ROOT/current")" || block CURRENT_RELEASE_MISSING
[[ "$before" == "$ROOT"/releases/* && -d "$before" ]] || block CURRENT_RELEASE_UNSAFE
[[ -d "$ROOT/releases" && ! -L "$ROOT/releases" ]] || block RELEASES_ROOT_MISSING
for bin in git php8.4 composer npm node runuser sha256sum; do
  command -v "$bin" >/dev/null 2>&1 || block "MISSING_$bin"
done
systemctl is-active --quiet nginx || block NGINX_NOT_ACTIVE
systemctl is-active --quiet php8.4-fpm || block PHP_FPM_NOT_ACTIVE
df -Pk "$ROOT" | awk 'END {exit !($4 > 3145728)}' || block INSUFFICIENT_DISK
[[ ! -e "$SCRATCH" && ! -L "$SCRATCH" ]] || block PREVIOUS_BUILD_SCRATCH_EXISTS
if [[ -e "$DEST" || -L "$DEST" ]]; then
  [[ -d "$DEST/.git" ]] || block CANDIDATE_ALREADY_EXISTS_UNVERIFIED
  existing="$(runuser -u kmjprod -- git -C "$DEST" rev-parse HEAD)" || block CANDIDATE_GIT_ERROR
  [[ "$existing" == "$SHA" ]] || block CANDIDATE_EXISTING_WRONG_SHA
  for file in apps/platform/vendor/autoload.php apps/platform/public/build/manifest.json apps/platform/public/assets/kmj-codebridge-icon.png; do
    [[ -s "$DEST/$file" ]] || block CANDIDATE_ARTIFACT_MISSING
  done
  notice "KMJ_CANDIDATE=EXISTING_SOURCE_ARTIFACTS_CHECK_PASS SHA=$SHA"
  notice 'PRODUCTION_ACTIVATION=NOT_ATTEMPTED'
  exit 0
fi
[[ -f "$before/apps/platform/.env" ]] || block CURRENT_APP_ENV_NOT_PRESENT
install -d -m 0750 -o kmjprod -g kmjprod "$SCRATCH"
runuser -u kmjprod -- env HOME="$ROOT" \
  bash -s -- "$SOURCE" "$SCRATCH" "$SHA" <<'PREPARE'
set -Eeuo pipefail
umask 027
source_url="$1"; out="$2"; sha="$3"
git clone --depth 16 --single-branch --branch main --no-tags "$source_url" "$out/repo"
cd "$out/repo"
git cat-file -e "$sha^{commit}" || { echo 'CANDIDATE_SHA_NOT_IN_FETCH'; exit 2; }
git checkout --detach "$sha"
[[ "$(git rev-parse HEAD)" == "$sha" ]] || exit 2
app="$PWD/apps/platform"
test -f "$app/composer.lock"
test -f "$app/package-lock.json"
cd "$app"
cp .env.example .env
chmod 600 .env
composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts --no-progress
npm ci --ignore-scripts --no-audit --no-fund
npm run build
test -s public/build/manifest.json
test -s public/assets/kmj-codebridge-icon.png
test -s vendor/autoload.php
rm -f .env
git status --porcelain --untracked-files=normal | grep -q . && {
  echo 'CANDIDATE_GIT_WORKTREE_DIRTY'; exit 2;
}
PREPARE
install -o kmjprod -g kmjprod -m 0600 "$before/apps/platform/.env" \
  "$SCRATCH/repo/apps/platform/.env"
runuser -u kmjprod -- git -C "$SCRATCH/repo" status --porcelain | grep -q . && \
  block CANDIDATE_FINAL_WORKTREE_DIRTY
[[ "$(runuser -u kmjprod -- git -C "$SCRATCH/repo" rev-parse HEAD)" == "$SHA" ]] ||
  block CANDIDATE_FINAL_SHA_MISMATCH
mv -T -- "$SCRATCH/repo" "$DEST"
rmdir -- "$SCRATCH"
chmod 0750 "$DEST"
[[ "$(readlink -f "$ROOT/current")" == "$before" ]] ||
  block PRODUCTION_POINTER_CHANGED
notice "KMJ_CANDIDATE=BUILT_SHA_$SHA"
notice 'PRODUCTION_SWITCH=NOT_ATTEMPTED'
notice 'BACKUP_AND_APPROVAL=STILL_REQUIRED'
