#!/usr/bin/env bash
# Advisory ONLY: inspect fixed stage/prod pointer layout without executing
# stage-controlled Git, PHP, environment files or network helpers.
# The root-owned immutable stage seal and independent owner approval are
# mandatory external gates; this script must never certify release readiness.
set -Eeuo pipefail
umask 077

block() { printf 'KMJ_STAGE_AUDIT=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || block INVALID_SHA
sha="$1"
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" -eq 0 ]] || block WRONG_HOST

prod=/home/kmjprod/current
site=/home/kmjstage/htdocs/staging.kmjtechno.com
base=/home/kmjstage/releases

# Only fixed metadata lookups are permitted. Stage-owned ancestors can be
# replaced concurrently, so even apparently good results are advisory.
[[ -L "$prod" && -L "$site" && -d "$base" && ! -L "$base" ]] || block LAYOUT
p_before="$(readlink -f -- "$prod")" || block PRODUCTION_POINTER
s_before="$(readlink -f -- "$site")" || block STAGING_POINTER
[[ "$p_before" == /home/kmjprod/releases/platform-* ]] || block PRODUCTION_PATH
[[ "$s_before" == /home/kmjstage/releases/*/apps/platform ]] || block STAGING_PATH

candidate="$base/$sha"
[[ -d "$candidate" && ! -L "$candidate" ]] || block CANDIDATE_LAYOUT
printf 'STAGING_AUDITED_SHA=%s\n' "$sha"

# Presence is not an immutable owner seal: never open or hash .env here.
# The candidate could be stage-user writable or replaced after this check.
if [[ -f "$candidate/apps/platform/.env" && ! -L "$candidate/apps/platform/.env" ]]; then
  echo STAGING_ENV_PRESENCE=PRESENT_UNATTESTED
else
  echo STAGING_ENV_PRESENCE=MISSING_OR_UNSAFE
fi

# No git ls-remote, no stage-controlled git config, no PHP artisan bootstrap,
# no database connection, and no parsing of secret-bearing environment files.
echo STAGING_IMMUTABLE_OWNER_SEAL=NOT_ATTESTED
echo STAGING_APPROVED_HEAD_MATCH=NOT_QUERIED
echo STAGING_SOURCE_HEAD=NOT_ATTESTED
echo STAGING_ENV_PARITY=NOT_READ
echo STAGING_DB_SCOPE=NOT_VERIFIED
echo STAGING_STORAGE_CONTINUITY=NOT_ATTESTED
echo STAGING_MIGRATION_READBACK=NOT_EXECUTED
echo OWNER_AUTHENTICATED_QA=NOT_VERIFIED
echo INDEPENDENT_RESTORE=NOT_VERIFIED

[[ "$(readlink -f -- "$prod")" == "$p_before" &&
   "$(readlink -f -- "$site")" == "$s_before" ]] || block LINK_CHANGED
echo PRODUCTION_POINTER=OBSERVED_UNCHANGED
echo STAGING_POINTER=OBSERVED_UNCHANGED
echo KMJ_STAGE_AUDIT=READ_ONLY_ADVISORY_COMPLETE
echo STAGING_READONLY_PRECHECK=BLOCKED_OWNER_SEAL_REQUIRED
exit 2
