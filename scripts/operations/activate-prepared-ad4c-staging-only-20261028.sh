#!/usr/bin/env bash
# Production is immutable. This is ONLY a guarded, reversible staging-vhost
# switch to an already prepared and independently verified exact SHA.
set -Eeuo pipefail
umask 077
export PATH=/opt/kmj-codebridge-node/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

fail() { printf 'KMJ_AD4C_STAGE_ACTIVATION=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 ]] || fail HOST
[[ "$#" -eq 1 && "$1" == DEPLOY_APPROVED_STAGING_ONLY ]] || fail OWNER_SCOPE

sha=ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe
old=9d15e14e39564ffb1e66085a483feb8331f9718f
root=/home/kmjstage/releases
link=/home/kmjstage/htdocs/staging.kmjtechno.com
previous="$root/$old"
candidate="$root/$sha"
oldapp="$previous/apps/platform"
app="$candidate/apps/platform"
conf=/etc/nginx/sites-enabled/staging.kmjtechno.com.conf
prod=/home/kmjprod/current
expected_prod=/home/kmjprod/releases/platform-8070dad72c55

[[ -L "$prod" && "$(readlink -f "$prod")" == "$expected_prod" ]] || fail PROD_POINTER
[[ -L "$link" && "$(readlink -f "$link")" == "$oldapp" ]] || fail STAGING_BASELINE
[[ -d "$candidate/.git" && ! -L "$candidate" ]] || fail CANDIDATE_MISSING
[[ "$(runuser -u kmjstage -- git -C "$candidate" rev-parse HEAD 2>/dev/null)" == "$sha" ]] || fail CANDIDATE_SHA
[[ -z "$(runuser -u kmjstage -- git -C "$candidate" status --porcelain --untracked-files=normal 2>/dev/null)" ]] || fail SOURCE_DIRTY
[[ -f "$app/.env" && ! -L "$app/.env" && "$(stat -c %U "$app/.env")" == kmjstage ]] || fail CANDIDATE_ENV
grep -Fxq APP_ENV=staging "$app/.env" || fail CANDIDATE_ENV_KIND
grep -Fxq DB_DATABASE=kmj_stage_2026 "$app/.env" || fail DB_ISOLATION
grep -Fxq DB_USERNAME=kmjstage_2026 "$app/.env" || fail DB_ROLE
[[ -s "$app/vendor/autoload.php" && -s "$app/public/build/manifest.json" ]] || fail BUILD_ASSETS
[[ -S /run/php/kmjstage-php84-fpm.sock ]] || fail STAGING_PHP_SOCKET
[[ "$(systemctl is-active nginx)" == active ]] || fail NGINX_SERVICE
[[ "$(systemctl is-active php8.4-fpm)" == active ]] || fail FPM_SERVICE
[[ ! -L "$app/storage/app" && -d "$app/storage/app" ]] || fail SCAFFOLD
[[ ! -e "$app/storage/app.pre-stage-ad4c" && ! -L "$app/storage/app.pre-stage-ad4c" ]] || fail SCAFFOLD_SNAPSHOT_CONFLICT
[[ ! -e "$app/public/storage" && ! -L "$app/public/storage" ]] || fail CANDIDATE_PUBLIC_STORAGE_COLLISION
[[ -f "$conf" ]] || fail STAGING_VHOST
target="$(readlink -f "$conf")"
[[ "$target" == /etc/nginx/sites-available/staging.kmjtechno.com.conf || "$target" == "$conf" ]] || fail CONFIG_PATH
[[ -f "$target" && ! -L "$target" && "$(stat -c %u "$target")" -eq 0 ]] || fail CONFIG_OWNER
nginx -t >/dev/null 2>&1 || fail NGINX_CONFIG

old_upload="$(readlink -f "$oldapp/storage/app")"
# A previous release directory is disposable: never make new uploads depend on
# its lifetime. Require an independently provisioned, persistent shared target.
case "$old_upload" in
  /home/kmjstage/shared/*) ;;
  /home/kmjstage/releases/*) fail UPLOAD_RELEASE_BOUND ;;
  *) fail UPLOAD_TARGET ;;
esac
[[ -d "$old_upload" ]] || fail UPLOAD_MISSING
[[ "$(readlink -f "$oldapp/storage/app/private/product-artwork")" == /home/kmjstage/shared/product-artwork ]] || fail PRODUCT_ARTWORK
[[ -d /home/kmjstage/shared/product-artwork && ! -L /home/kmjstage/shared/product-artwork ]] || fail SHARED_ARTWORK
# No candidate data may be silently discarded or hidden during symlink switch.
if find "$app/storage/app" -mindepth 1 -type f ! -name .gitignore -print -quit | grep -q .; then
  fail NEW_UPLOAD_DATA
fi
# public/storage is optional: Laravel can serve a healthy staging site with
# no public upload symlink. If old public/storage is a real directory, refuse
# to silently replace it with a link (manual data-continuity review needed).
public_action=absent
old_public=""
if [[ -L "$oldapp/public/storage" ]]; then
  public_action=link
  old_public="$(readlink -f "$oldapp/public/storage")"
  case "$old_public" in
    /home/kmjstage/shared/*) ;;
    /home/kmjstage/releases/*) fail PUBLIC_UPLOAD_RELEASE_BOUND ;;
    *) fail PUBLIC_UPLOAD_TARGET ;;
  esac
  [[ -d "$old_public" ]] || fail OLD_PUBLIC_UPLOAD_MISSING
elif [[ -e "$oldapp/public/storage" ]]; then
  fail OLD_PUBLIC_STORAGE_DIRECTORY_REQUIRES_REVIEW
fi
echo "KMJ_AD4C_OLD_PUBLIC_STORAGE=$public_action"
# Prevent a future staging-approved promotion from silently replacing this target.
remote="$(runuser -u kmjcode -- env GIT_TERMINAL_PROMPT=0 git -C /srv/kmj-codebridge-projects/kmj-main-platform ls-remote origin refs/heads/staging-approved 2>/dev/null | awk '{print $1}')"
[[ "$remote" == "$sha" ]] || fail APPROVED_SHA_CHANGED

exec 9>/run/kmj-stage-native-backend.lock
flock -n 9 || fail CONCURRENT_STAGING
[[ "$(readlink -f "$prod")" == "$expected_prod" && "$(readlink -f "$link")" == "$oldapp" ]] || fail CONCURRENT_POINTER_DRIFT
cfg_hash="$(sha256sum "$target" | cut -d' ' -f1)"
work="$(mktemp -d /root/.kmj-stage-ad4c.XXXXXXXX)"
install -m 0600 "$target" "$work/original.conf"
python3 - "$work/original.conf" "$work/next.conf" "$oldapp/public" "$app/public" <<'PY'
from pathlib import Path
import sys
before,after,old,new=sys.argv[1:]
text=Path(before).read_text()
if text.count(old) != 1 or new in text:
    raise SystemExit("STAGING_CONFIG_BASELINE_MISMATCH")
Path(after).write_text(text.replace(old,new))
PY

activated=0
candidate_scaffold_moved=0
candidate_storage_link_created=0
candidate_public_link_created=0
completed=0
rollback() {
  rc=$?
  trap - EXIT
  if [[ "$activated" == 1 ]]; then
    install -m 0644 "$work/original.conf" "$target"
    rb="$link.rollback-ad4c-$"
    ln -s "$oldapp" "$rb"
    mv -Tf "$rb" "$link"
    if nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1; then
      echo KMJ_AD4C_STAGING_ROLLBACK=RESTORED_PREVIOUS
    else
      echo KMJ_AD4C_STAGING_ROLLBACK=OPERATOR_ATTENTION_REQUIRED
    fi
  fi
  # A failed attempt never leaves hidden candidate storage scaffolding.
  # Only undo links CREATED by this run with the exact expected targets.
  if [[ "$completed" != 1 ]]; then
    if [[ "$candidate_public_link_created" == 1 ]] &&
       [[ -L "$app/public/storage" ]] &&
       [[ "$(readlink -f "$app/public/storage")" == "$old_public" ]]; then
      unlink -- "$app/public/storage"
    fi
    if [[ "$candidate_storage_link_created" == 1 ]] &&
       [[ -L "$app/storage/app" ]] &&
       [[ "$(readlink -f "$app/storage/app")" == "$old_upload" ]]; then
      unlink -- "$app/storage/app"
    fi
    if [[ "$candidate_scaffold_moved" == 1 ]] &&
       [[ ! -e "$app/storage/app" && ! -L "$app/storage/app" ]] &&
       [[ -d "$app/storage/app.pre-stage-ad4c" ]]; then
      mv -- "$app/storage/app.pre-stage-ad4c" "$app/storage/app"
      echo KMJ_AD4C_CANDIDATE_SCAFFOLD=RESTORED
    fi
  fi
  echo KMJ_AD4C_PRODUCTION_POINTER=UNCHANGED_EXPECTED
  exit "$rc"
}
trap rollback EXIT

# Keep the prepared candidate's scaffold intact for forensic recovery.
mv "$app/storage/app" "$app/storage/app.pre-stage-ad4c"
candidate_scaffold_moved=1
ln -s "$old_upload" "$app/storage/app"
candidate_storage_link_created=1
chown -h kmjstage:www-data "$app/storage/app"
if [[ "$public_action" == link ]]; then
  ln -s "$old_public" "$app/public/storage"
  candidate_public_link_created=1
  chown -h kmjstage:www-data "$app/public/storage"
fi
[[ "$(readlink -f "$app/storage/app/private/product-artwork")" == /home/kmjstage/shared/product-artwork ]] || fail NEW_ARTWORK_CONTINUITY
runuser -u www-data -- test -r "$app/public/build/manifest.json" || fail ASSET_ACCESS
[[ "$(sha256sum "$target" | cut -d' ' -f1)" == "$cfg_hash" ]] || fail CONCURRENT_NGINX_CHANGE
[[ "$(readlink -f "$prod")" == "$expected_prod" && "$(readlink -f "$link")" == "$oldapp" ]] || fail CONCURRENT_POINTER_CHANGE

activated=1
install -m 0644 "$work/next.conf" "$target"
nginx -t >/dev/null 2>&1 || fail NEW_NGINX_CONFIG
tmp_link="$link.new-ad4c-$$"
[[ ! -e "$tmp_link" && ! -L "$tmp_link" ]] || fail TEMP_LINK_COLLISION
ln -s "$app" "$tmp_link"
mv -Tf "$tmp_link" "$link"
systemctl reload nginx >/dev/null || fail NGINX_RELOAD

for path in / /products /login /company /capabilities /trust; do
  headfile="$work/headers"
  code="$(curl --noproxy '*' --proto '=https' --silent --show-error --connect-timeout 5 --max-time 25 --resolve staging.kmjtechno.com:443:127.0.0.1 --dump-header "$headfile" --output /dev/null --write-out '%{http_code}' "https://staging.kmjtechno.com$path")" || fail STAGING_HTTPS
  [[ "$code" == 200 ]] || fail STAGING_HTTP_STATUS
  python3 - "$headfile" "$sha" <<'PY'
from pathlib import Path
import sys
lines=Path(sys.argv[1]).read_text().splitlines()
values=[x.partition(':')[2].strip().lower() for x in lines if x.lower().startswith('x-kmj-deploy-sha:')]
if values != [sys.argv[2]]:
    raise SystemExit("STAGING_HEADER_SHA_MISMATCH")
PY
done
[[ "$(readlink -f "$link")" == "$app" && "$(readlink -f "$prod")" == "$expected_prod" ]] || fail FINAL_POINTER
activated=0
completed=1
echo KMJ_AD4C_STAGE_ACTIVATION=PASS_EXACT_SHA_HTTPS
echo "KMJ_AD4C_STAGE_SHA=$sha"
echo KMJ_AD4C_PRODUCTION=UNCHANGED
echo KMJ_AD4C_STAGING_OWNER_QA=PENDING
echo KMJ_AD4C_OFFSITE_RESTORE=NOT_VERIFIED
