#!/usr/bin/env bash
# Read-only staging release inventory for KMJ-elite. Never source .env,
# execute a worker, change a symlink, restart a service or read secrets.
set -Eeuo pipefail
umask 077

[[ "${#}" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || { echo 'STAGING_DOCTOR=INVALID_SHA'; exit 2; }
expected="$1"
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 ]] ||
  { echo 'STAGING_DOCTOR=WRONG_HOST_OR_USER'; exit 2; }

prod=/home/kmjprod/current
site=/home/kmjstage/htdocs/staging.kmjtechno.com
worker=/home/kmjstage/bin/kmj-stage-deploy.sh
[[ -L "$prod" ]] || { echo 'PRODUCTION_POINTER=INVALID'; exit 2; }
before="$(readlink -f "$prod")"
[[ "$before" == /home/kmjprod/releases/platform-* && -d "$before" ]] ||
  { echo 'PRODUCTION_POINTER=UNEXPECTED'; exit 2; }

echo 'STAGING_ORIGIN=https://staging.kmjtechno.com'
echo "APPROVED_EXPECTED_SHA=$expected"
for unit in kmj-stage-deploy.timer kmj-stage-deploy.service; do
  label="${unit//./_}"
  load="$(systemctl show "$unit" --property=LoadState --value 2>/dev/null || :)"
  active="$(systemctl show "$unit" --property=ActiveState --value 2>/dev/null || :)"
  echo "${label}_LOAD=${load:-unavailable}"
  echo "${label}_ACTIVE=${active:-unavailable}"
done

if [[ -f "$worker" && ! -L "$worker" ]]; then
  echo 'LEGACY_WORKER=PRESENT'
  if grep -Eq '^BRANCH="?staging-approved"?$' "$worker"; then
    echo 'LEGACY_WORKER_BRANCH=STAGING_APPROVED'
  else
    echo 'LEGACY_WORKER_BRANCH=UNVERIFIED'
  fi
else
  echo 'LEGACY_WORKER=MISSING'
fi

if [[ ! -L "$site" ]]; then
  echo 'STAGING_SITE=NOT_SYMLINK'
else
  target="$(readlink -f "$site" 2>/dev/null || :)"
  case "$target" in
    /home/kmjstage/releases/*/apps/platform)
      release="${target%/apps/platform}"
      echo 'STAGING_SITE=ISOLATED_RELEASE'
      base="${release##*/}"
      if [[ "$base" =~ ^(platform-)?[a-f0-9]{12,40}$ ]]; then
        echo "STAGING_RELEASE_NAME=$base"
      else
        echo 'STAGING_RELEASE_NAME=NON_SHA_NAMED'
      fi
      for name in artisan vendor/autoload.php public/build/manifest.json; do
        if [[ -f "$target/$name" ]]; then
          echo "STAGING_ARTIFACT_${name//\//_}=PRESENT"
        else
          echo "STAGING_ARTIFACT_${name//\//_}=MISSING"
        fi
      done
      [[ -f "$target/.env" ]] &&
        echo 'STAGING_RUNTIME_ENV=PRESENT_NOT_READ' ||
        echo 'STAGING_RUNTIME_ENV=MISSING'
      if [[ -e "$release/.git" || -L "$release/.git" ]]; then
        echo 'STAGING_GIT_METADATA=PRESENT'
      else
        echo 'STAGING_GIT_METADATA=ABSENT'
      fi
      # Always try as the stage account first: root git safe.directory errors
      # on foreign-owned checkouts can otherwise abort a valid diagnosis.
      revision="$(runuser -u kmjstage -- git -C "$release" rev-parse --verify HEAD 2>/dev/null || :)"
      if [[ "$revision" =~ ^[a-f0-9]{40}$ ]]; then
        echo "STAGING_LOCAL_GIT_SHA=$revision"
      else
        echo 'STAGING_LOCAL_GIT_SHA=UNAVAILABLE'
      fi
      ;;
    *)
      echo 'STAGING_SITE=UNEXPECTED_LINK'
      ;;
  esac
fi

for unit in nginx php8.4-fpm; do
  state="$(systemctl is-active "$unit" 2>/dev/null || :)"
  echo "STAGING_SHARED_${unit//./_}=${state:-unavailable}"
done
[[ -S /run/php/kmjstage-php84-fpm.sock ]] &&
  echo 'STAGING_DEDICATED_PHP_SOCKET=PRESENT' ||
  echo 'STAGING_DEDICATED_PHP_SOCKET=MISSING'

if [[ "$(readlink -f "$prod")" == "$before" ]]; then
  echo 'PRODUCTION_POINTER=UNCHANGED'
else
  echo 'PRODUCTION_POINTER=CHANGED_CONCURRENTLY'
  exit 3
fi
echo 'STAGING_DOCTOR=READ_ONLY_COMPLETE'
