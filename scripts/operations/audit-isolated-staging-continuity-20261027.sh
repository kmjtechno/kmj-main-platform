#!/usr/bin/env bash
# Staging-only, read-only continuity check for an already prepared exact candidate.
# No symlink, database, runtime or production writes.
set -Eeuo pipefail
umask 077
block() { echo "KMJ_STAGE_AUDIT=BLOCKED_$1"; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || block INVALID_SHA
sha="$1"
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 ]] || block WRONG_HOST
prod=/home/kmjprod/current
site=/home/kmjstage/htdocs/staging.kmjtechno.com
base=/home/kmjstage/releases
[[ -L "$prod" && -L "$site" && -d "$base" && ! -L "$base" ]] || block LAYOUT
p_before="$(readlink -f "$prod")"
s_before="$(readlink -f "$site")"
[[ "$p_before" == /home/kmjprod/releases/platform-* ]] || block PRODUCTION_PATH
[[ "$s_before" == /home/kmjstage/releases/*/apps/platform ]] || block STAGING_PATH
old="$(dirname "$(dirname "$s_before")")"
new="$base/$sha/apps/platform"
[[ -d "$base/$sha/.git" && ! -L "$base/$sha" && -f "$new/.env" && -f "$s_before/.env" ]] || block SOURCE_MISSING
[[ ! -L "$new/.env" && ! -L "$s_before/.env" ]] || block ENV_LINK
[[ "$(stat -c %U "$new/.env")" == kmjstage && "$(stat -c %U "$s_before/.env")" == kmjstage ]] || block ENV_OWNER
[[ "$(runuser -u kmjstage -- git -C "$base/$sha" rev-parse HEAD 2>/dev/null)" == "$sha" ]] || block CANDIDATE_SHA
[[ "$(runuser -u kmjstage -- git -C "$old" rev-parse HEAD 2>/dev/null)" == "$(basename "$old")" ]] || block OLD_SHA
[[ -s "$new/public/build/manifest.json" && -f "$new/vendor/autoload.php" ]] || block BUILD
approved="$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/staging-approved 2>/dev/null | awk '{print $1}')" || block APPROVAL_UNAVAILABLE
[[ "$approved" == "$sha" ]] || block APPROVED_SHA_MOVED
echo "STAGING_AUDITED_SHA=$sha"

python3 - "$s_before" "$new" <<'PY'
import hashlib
from pathlib import Path
import sys

old, new = [Path(arg) for arg in sys.argv[1:]]
a, b = (old / '.env').read_bytes(), (new / '.env').read_bytes()
same = hashlib.sha256(a).digest() == hashlib.sha256(b).digest()
print('STAGING_ENV_PARITY=' + ('PASS' if same else 'BLOCKED_DIFFERENT'))
if not same:
    raise SystemExit(2)
values = {}
for line in a.decode('utf-8').splitlines():
    if line.lstrip().startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    if key in {'APP_ENV', 'APP_URL', 'DB_CONNECTION', 'DB_HOST', 'DB_DATABASE', 'DB_URL', 'SESSION_DRIVER', 'CACHE_STORE'}:
        values[key] = value.strip().strip('"').strip("'")
safe = (
    values.get('APP_ENV') == 'staging'
    and values.get('APP_URL') == 'https://staging.kmjtechno.com'
    and values.get('DB_CONNECTION') == 'pgsql'
    and values.get('DB_HOST') in {'127.0.0.1', 'localhost'}
    and (values.get('DB_DATABASE', '').startswith('kmj_stage_') or values.get('DB_DATABASE') == 'kmj_platform_staging')
    and not values.get('DB_URL')
)
print('STAGING_DB_SCOPE=' + ('STAGING_ONLY' if safe else 'BLOCKED_UNVERIFIED'))
print('STAGING_SESSION=' + ('DATABASE' if values.get('SESSION_DRIVER', 'database') == 'database' else 'OTHER'))
print('STAGING_CACHE=' + ('DATABASE' if values.get('CACHE_STORE', 'database') == 'database' else 'OTHER'))
if not safe:
    raise SystemExit(2)

for name in ('storage', 'public/storage'):
    x, y = old / name, new / name
    first, second = x.resolve(strict=False), y.resolve(strict=False)
    scoped = str(first).startswith('/home/kmjstage/') and str(second).startswith('/home/kmjstage/')
    if not scoped:
        status = 'BLOCKED_OUTSIDE_STAGE'
    elif not x.exists() or not y.exists():
        status = 'BLOCKED_MISSING'
    elif first == second:
        status = 'PASS_SHARED'
    else:
        status = 'BLOCKED_SEPARATE'
    print('STAGING_' + name.upper().replace('/', '_') + '_CONTINUITY=' + status)
PY

for path in "$s_before/storage" "$new/storage"; do
  if [[ -d "$path" ]]; then
    kib="$(du -sk -- "$path" 2>/dev/null | awk '{print $1}' || :)"
    if [[ "$path" == "$s_before/storage" ]]; then
      echo "STAGING_OLD_STORAGE_KIB=$kib"
    else
      echo "STAGING_NEW_STORAGE_KIB=$kib"
    fi
  fi
done

tmp="$(mktemp)"
trap 'rm -f -- "$tmp"' EXIT
if runuser -u kmjstage -- bash -c 'cd "$1" && php8.4 artisan migrate:status --no-interaction --no-ansi' _ "$new" >"$tmp" 2>/dev/null; then
  pending="$(grep -ic Pending "$tmp" || :)"
  echo "STAGING_PENDING_MIGRATIONS=$pending"
  if [[ "$pending" == 0 ]]; then
    echo STAGING_MIGRATION_READBACK=NO_PENDING_REPORTED
  else
    echo STAGING_MIGRATION_READBACK=PENDING_BLOCKS_CUTOVER
  fi
else
  echo STAGING_MIGRATION_READBACK=UNAVAILABLE_BLOCKS_CUTOVER
fi
[[ "$(readlink -f "$prod")" == "$p_before" && "$(readlink -f "$site")" == "$s_before" ]] || block LINK_CHANGED
echo PRODUCTION_POINTER=UNCHANGED
echo STAGING_POINTER=UNCHANGED
echo KMJ_STAGE_AUDIT=READ_ONLY_COMPLETE
