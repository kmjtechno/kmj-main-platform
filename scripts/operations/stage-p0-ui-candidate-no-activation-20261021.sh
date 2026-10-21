#!/usr/bin/env bash
# Build SHA-pinned Main Platform P0 candidate; no production activation or credentials.
set -Eeuo pipefail
umask 027
readonly TARGET_SHA='f4b6d3ff96b0e27a0f17f38653873c10b0ce41a0'
readonly SHORT_SHA="$(printf '%s' "$TARGET_SHA" | cut -c1-12)"
readonly ROOT='/home/kmjprod'
readonly EXPECTED_ACTIVE="$ROOT/releases/platform-8070dad72c55"
readonly DEST="$ROOT/releases/platform-$SHORT_SHA"
readonly SOURCE='https://github.com/kmjtechno/kmj-main-platform.git'

notice() { printf '%s\n' "$1"; }
block() { notice "STAGE_P0=BLOCKED REASON=$1"; exit 2; }
trap 'notice "STAGE_P0=FAIL_OR_INTERRUPTED (live pointer unchanged)"' ERR

[[ "$(id -u)" -eq 0 && "$(hostname -s)" == KMJ-elite ]] || block WRONG_SERVER
id kmjprod >/dev/null 2>&1 || block SERVICE_USER_MISSING
[[ -L "$ROOT/current" && ! -L "$ROOT/releases" ]] || block RELEASE_PATH_UNSAFE
active="$(readlink -f "$ROOT/current")" || block CURRENT_RELEASE_UNREADABLE
[[ "$active" == "$EXPECTED_ACTIVE" && -d "$active" ]] || block CURRENT_RELEASE_CHANGED
[[ -d "$ROOT/releases" ]] || block RELEASE_DIRECTORY_MISSING
[[ ! -L "$DEST" ]] || block CANDIDATE_SYMLINK
for cmd in git php8.4 composer node npm runuser flock; do
    command -v "$cmd" >/dev/null 2>&1 || block "MISSING_$cmd"
done
systemctl is-active --quiet nginx || block NGINX_NOT_ACTIVE
systemctl is-active --quiet php8.4-fpm || block PHP_FPM_NOT_ACTIVE
df -Pk "$ROOT" | awk 'END { exit !($4 >= 4194304) }' ||
    block INSUFFICIENT_FREE_DISK_4GB
exec 9>/run/lock/kmj-main-platform-production-release.lock
flock -n 9 || block RELEASE_OPERATION_BUSY

verify_artifacts() {
    local dir="$1" artifact
    [[ -d "$dir/.git" && ! -L "$dir" ]] || block CANDIDATE_NOT_GIT
    [[ "$(runuser -u kmjprod -- git -C "$dir" rev-parse HEAD)" == "$TARGET_SHA" ]] ||
        block CANDIDATE_WRONG_SHA
    [[ -z "$(runuser -u kmjprod -- git -C "$dir" status --porcelain --untracked-files=normal)" ]] ||
        block CANDIDATE_DIRTY
    [[ ! -e "$dir/apps/platform/.env" && ! -L "$dir/apps/platform/.env" ]] ||
        block CANDIDATE_CONTAINS_ENV
    for artifact in \
        apps/platform/vendor/autoload.php \
        apps/platform/public/build/manifest.json \
        apps/platform/public/assets/kmj-codebridge-icon.png \
        apps/platform/database/migrations/2026_10_20_070000_create_customer_profiles_table.php
    do
        [[ -s "$dir/$artifact" && ! -L "$dir/$artifact" ]] ||
            block "MISSING_ARTIFACT_$(basename "$artifact")"
    done
}

if [[ -e "$DEST" ]]; then
    verify_artifacts "$DEST"
    [[ "$(readlink -f "$ROOT/current")" == "$active" ]] || block POINTER_CHANGED
    notice "CANDIDATE_EXISTING=SOURCE_ARTIFACTS_PASS SHA=$TARGET_SHA"
    notice "PRODUCTION_ACTIVATION=NOT_ATTEMPTED"
    exit 0
fi

stage="$(mktemp -d "$ROOT/releases/.kmj-p0-candidate-$SHORT_SHA.XXXXXXXX")" ||
    block CANNOT_CREATE_SCRATCH
cleanup() {
    if [[ "$stage" == "$ROOT/releases/.kmj-p0-candidate-$SHORT_SHA."* &&
          -d "$stage" && ! -L "$stage" ]]; then
        rm -rf -- "$stage"
    fi
}
trap cleanup EXIT
chown kmjprod:kmjprod "$stage"
chmod 0700 "$stage"

runuser -u kmjprod -- env HOME="$ROOT" \
    bash -s -- "$SOURCE" "$stage/repo" "$TARGET_SHA" <<'BUILD'
set -Eeuo pipefail
umask 027
source_url="$1"; dest="$2"; sha="$3"
git init -q "$dest"
git -C "$dest" remote add origin "$source_url"
git -C "$dest" -c protocol.version=2 fetch --depth 1 --no-tags origin "$sha"
git -C "$dest" checkout --detach -q FETCH_HEAD
[[ "$(git -C "$dest" rev-parse HEAD)" == "$sha" ]] ||
    { echo 'CANDIDATE_FETCH_SHA_MISMATCH'; exit 2; }
cd "$dest/apps/platform"
[[ -s composer.lock && -s package-lock.json && -f .env.example ]] ||
    { echo 'CANDIDATE_DEPENDENCIES_UNAVAILABLE'; exit 2; }
# .env.example is temporary for compile time. Never copy a production secret.
cp -- .env.example .env
chmod 0600 .env
trap 'rm -f -- .env' EXIT
composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts --no-progress
npm ci --ignore-scripts --no-audit --no-fund
npm run build
rm -f -- .env
trap - EXIT
[[ -s public/build/manifest.json && -s vendor/autoload.php ]] ||
    { echo 'CANDIDATE_BUILD_ARTIFACT_MISSING'; exit 2; }
[[ -z "$(git -C "$dest" status --porcelain --untracked-files=normal)" ]] ||
    { echo 'CANDIDATE_DIRTY_AFTER_BUILD'; exit 2; }
echo 'OFFLINE_CANDIDATE_BUILD=PASS'
BUILD

verify_artifacts "$stage/repo"
[[ "$(readlink -f "$ROOT/current")" == "$active" ]] || block CURRENT_POINTER_CHANGED
mv -T -- "$stage/repo" "$DEST"
chmod 0750 "$DEST"
verify_artifacts "$DEST"
[[ "$(readlink -f "$ROOT/current")" == "$active" ]] || block CURRENT_POINTER_CHANGED

notice "CANDIDATE_STAGED=PASS SHA=$TARGET_SHA"
notice "PRODUCTION_ACTIVATION=NOT_ATTEMPTED"
notice "LIVE_POINTER=UNCHANGED"
notice "LIVE_ENV=UNTOUCHED"
notice "CANDIDATE_ENV=ABSENT"
notice "LIVE_DB_AND_PAYMENTS=UNTOUCHED"
notice "MAIL_SERVICES=UNTOUCHED"
notice "NO_EMAIL_SENT=YES"
notice "NEXT=SEPARATE_RECOVERY_APPROVAL_AND_SAFE_ACTIVATION"
