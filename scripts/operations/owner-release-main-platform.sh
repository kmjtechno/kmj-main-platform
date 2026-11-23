#!/usr/bin/env bash
# One-command owner release helper for the Elite host: stage -> storage switch -> materialize -> recovery ->
# owner approval. It replaces copy/pasting a multi-block script. It NEVER activates production: activation
# stays the separate guarded Supervisor/broker step, and the owner approval flags below are the owner's own
# explicit attestation by running this script as root.
#
# Usage (root, on KMJ-elite):
#   bash owner-release-main-platform.sh <40-hex-main-sha>                  full chain (unchanged behaviour)
#   bash owner-release-main-platform.sh --prepare-only <40-hex-main-sha>   stage..approval, then STOP (no wait)
#   bash owner-release-main-platform.sh --post-activation <40-hex-main-sha> migrate the LIVE candidate only
# The caller pins THIS file by sha256 (given out of band) before running it. The helpers it downloads are
# pinned below by sha256 and fetched from the same exact commit; a mismatch aborts before anything runs.
set -Eeuo pipefail
umask 077

ROOT=/home/kmjprod
HELPERS_REPO=kmjtechno/kmj-main-platform
APPROVAL_URL=https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/51ef2734ea5b77db044234aeaa7bcf9c73a5f1c9/scripts/production/owner_main_platform_production_approval.py
APPROVAL_SHA256=45b28a2d912c5e5b748ee4ec7c9df76e4b28e0ef32a23cc831169fe315136200
PIN_STAGE=ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24
PIN_SWITCH=281893b277fb4dfabf174b7baaa49801f6b0a4c2dc83c2c711115f45225ea8ef
PIN_MATERIALIZE=fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f
PIN_RECOVERY=d3f977dbd68bd986e888c720c2bcc49e1c02e884878bfc4e4c0903f53bdf3212

fail() { printf 'KMJ_OWNER_RELEASE=BLOCKED_%s\n' "$1"; exit 2; }
MODE=full
if [[ "$#" -eq 2 && ( "$1" == --prepare-only || "$1" == --post-activation ) ]]; then
  MODE="${1#--}"
  shift
fi
[[ "$#" -eq 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || fail EXACT_SHA_REQUIRED
SHA="$1"
S12="${SHA:0:12}"
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
[[ -L "$ROOT/current" ]] || fail LIVE_POINTER_MISSING
LIVE="$(basename "$(readlink -f "$ROOT/current")")"
[[ "$LIVE" =~ ^platform-[a-f0-9]{12}$ ]] || fail LIVE_NAME_UNEXPECTED
if [[ "$MODE" == post-activation ]]; then
  # Only the migration of the candidate that is ALREADY live. Nothing is staged, approved or switched here.
  [[ "$LIVE" == "platform-$S12" ]] || fail CANDIDATE_NOT_LIVE
  runuser -u kmjprod -- php8.4 "$ROOT/current/apps/platform/artisan" migrate --force
  echo POST_ACTIVATION_MIGRATE_DONE
  echo CHAIN_EXIT=0
  exit 0
fi
[[ "$LIVE" != "platform-$S12" ]] || fail ALREADY_LIVE

MP="https://raw.githubusercontent.com/$HELPERS_REPO/$SHA/scripts/operations"
D="$(mktemp -d)"
trap 'rm -rf -- "$D"' EXIT
cd "$D"

get() { # url file sha256
  curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 120 "$1" -o "$2"
  printf '%s  %s\n' "$3" "$2" | sha256sum -c - >/dev/null || { printf 'KMJ_OWNER_RELEASE=HASH_MISMATCH_%s\n' "$2"; exit 2; }
}
get "$MP/stage-fast-main-candidate-no-activation.sh" stage.sh "$PIN_STAGE"
get "$MP/main_platform_storage_switch.py" switch.py "$PIN_SWITCH"
get "$MP/materialize-main-platform-candidate-runtime.sh" materialize.sh "$PIN_MATERIALIZE"
get "$MP/prepare-main-platform-local-recovery-exact.sh" recovery.sh "$PIN_RECOVERY"
get "$APPROVAL_URL" approval.py "$APPROVAL_SHA256"
echo "KMJ_OWNER_RELEASE=HELPERS_VERIFIED candidate=$S12 live=$LIVE"

bash stage.sh "$SHA"
APP="$ROOT/releases/platform-$S12/apps/platform"
SH="$ROOT/shared/storage"
PID="$(python3 switch.py plan --app-dir "$APP" --shared "$SH" | python3 -c 'import sys,json;print(json.load(sys.stdin)["plan_id"])')"
python3 switch.py switch --apply --plan-id "$PID" --app-dir "$APP" --shared "$SH"
/bin/bash -p materialize.sh "$SHA" "$LIVE"
bash recovery.sh "$SHA" "$LIVE"
python3 approval.py --sha="$SHA" --live="$LIVE" --apply --attest-backup --attest-rollback
if [[ "$MODE" == prepare-only ]]; then
  echo APPROVAL_DONE_PREPARE_ONLY_ACTIVATE_THEN_RUN_POST_ACTIVATION
  exit 0
fi
echo APPROVAL_DONE_WAITING_FOR_ACTIVATION

for _ in $(seq 1 180); do
  if [[ "$(basename "$(readlink -f "$ROOT/current")")" == "platform-$S12" ]]; then break; fi
  sleep 5
done
[[ "$(basename "$(readlink -f "$ROOT/current")")" == "platform-$S12" ]] || { echo NOT_ACTIVATED_YET_RERUN_ONLY_THE_MIGRATE_LINE_LATER; exit 3; }
runuser -u kmjprod -- php8.4 "$ROOT/current/apps/platform/artisan" migrate --force
echo CHAIN_EXIT=0
