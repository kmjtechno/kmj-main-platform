#!/bin/bash -p
# Advisory ONLY: inspect fixed stage/prod pointer layout without executing
# stage-controlled Git, PHP, environment files or network helpers.
# The root-owned immutable stage seal and independent owner approval are
# mandatory external gates; this script must never certify release readiness.
set -Eeuo pipefail
# Do not resolve root-invoked commands through caller-controlled PATH.
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
builtin umask 077

block() { builtin printf 'KMJ_STAGE_AUDIT=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || block INVALID_SHA
sha="$1"
[[ "$(/usr/bin/hostname -s)" == KMJ-elite && "$(/usr/bin/id -u)" -eq 0 ]] || block WRONG_HOST

prod=/home/kmjprod/current
site=/home/kmjstage/htdocs/staging.kmjtechno.com
base=/home/kmjstage/releases

# Only fixed metadata lookups are permitted. Stage-owned ancestors can be
# replaced concurrently, so even apparently good results are advisory.
[[ -L "$prod" && -L "$site" && -d "$base" && ! -L "$base" ]] || block LAYOUT
p_before="$(/usr/bin/readlink -f -- "$prod")" || block PRODUCTION_POINTER
s_before="$(/usr/bin/readlink -f -- "$site")" || block STAGING_POINTER
[[ "$p_before" == /home/kmjprod/releases/platform-* ]] || block PRODUCTION_PATH
[[ "$s_before" == /home/kmjstage/releases/*/apps/platform ]] || block STAGING_PATH

candidate="$base/$sha"
[[ -d "$candidate" && ! -L "$candidate" ]] || block CANDIDATE_LAYOUT
builtin printf 'STAGING_AUDITED_SHA=%s\n' "$sha"

# Presence is not an immutable owner seal: never open or hash .env here.
# The candidate could be stage-user writable or replaced after this check.
if [[ -f "$candidate/apps/platform/.env" && ! -L "$candidate/apps/platform/.env" ]]; then
  builtin printf '%s\n' 'STAGING_ENV_PRESENCE=PRESENT_UNATTESTED'
else
  builtin printf '%s\n' 'STAGING_ENV_PRESENCE=MISSING_OR_UNSAFE'
fi

# No git ls-remote, no stage-controlled git config, no PHP artisan bootstrap,
# no database connection, and no parsing of secret-bearing environment files.
builtin printf '%s\n' 'STAGING_IMMUTABLE_OWNER_SEAL=NOT_ATTESTED'
builtin printf '%s\n' 'STAGING_APPROVED_HEAD_MATCH=NOT_QUERIED'
builtin printf '%s\n' 'STAGING_SOURCE_HEAD=NOT_ATTESTED'
builtin printf '%s\n' 'STAGING_ENV_PARITY=NOT_READ'
builtin printf '%s\n' 'STAGING_DB_SCOPE=NOT_VERIFIED'
builtin printf '%s\n' 'STAGING_STORAGE_CONTINUITY=NOT_ATTESTED'
builtin printf '%s\n' 'STAGING_MIGRATION_READBACK=NOT_EXECUTED'
builtin printf '%s\n' 'OWNER_AUTHENTICATED_QA=NOT_VERIFIED'
builtin printf '%s\n' 'INDEPENDENT_RESTORE=NOT_VERIFIED'

[[ "$(/usr/bin/readlink -f -- "$prod")" == "$p_before" &&
   "$(/usr/bin/readlink -f -- "$site")" == "$s_before" ]] || block LINK_CHANGED
builtin printf '%s\n' 'PRODUCTION_POINTER=OBSERVED_UNCHANGED'
builtin printf '%s\n' 'STAGING_POINTER=OBSERVED_UNCHANGED'
builtin printf '%s\n' 'KMJ_STAGE_AUDIT=READ_ONLY_ADVISORY_COMPLETE'
builtin printf '%s\n' 'STAGING_READONLY_PRECHECK=BLOCKED_OWNER_SEAL_REQUIRED'
builtin exit 2
