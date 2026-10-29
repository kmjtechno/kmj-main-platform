#!/usr/bin/env bash
# Materialize live runtime state into an already staged, clean Main Platform
# candidate so the fixed activation controller can switch to it safely.
#
# Usage (root on KMJ-elite, immediately before backup + activation):
#   materialize-main-platform-candidate-runtime.sh <approved-40-hex-sha> <expected-current-release>
#
# It COPIES (never moves or edits) from the live release into the candidate:
#   * apps/platform/.env (0600 kmjprod), pinning only the owner-approved
#     CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com when it is absent;
#   * apps/platform/storage/app uploads (verified by file bytes, metadata and raw link text);
#   * the public/storage link, only when the live release has one.
# It reports pending migrations by file diff. It NEVER touches the live
# release, database, approval file, symlinks current/previous, services or DNS.
set -Eeuo pipefail
umask 077
fail() { echo "KMJ_MATERIALIZE=BLOCKED $1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }
[[ "$#" -eq 2 ]] || fail EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED
[[ "$1" =~ ^[a-f0-9]{40}$ ]] || fail EXACT_SHA_REQUIRED
[[ "$2" =~ ^platform-[a-f0-9]{12}$ ]] || fail EXPECTED_CURRENT_RELEASE_INVALID
readonly SHA="$1"
readonly SHORT="${SHA:0:12}"
readonly EXPECTED_CURRENT="$2"
[[ "platform-$SHORT" != "$EXPECTED_CURRENT" ]] || fail TARGET_ALREADY_CURRENT
readonly ROOT=/home/kmjprod
readonly ORIGIN_LINE='CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com'
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail WRONG_HOST
id kmjprod >/dev/null 2>&1 || fail SERVICE_USER_MISSING
for cmd in git runuser install cp find awk sha256sum flock python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "MISSING_$cmd"
done
[[ -L "$ROOT/current" ]] || fail CURRENT_NOT_SYMLINK
readonly LIVE="$(readlink -f "$ROOT/current")"
[[ "$LIVE" == "$ROOT"/releases/* && -d "$LIVE" ]] || fail CURRENT_RELEASE_UNSAFE
[[ "$(basename "$LIVE")" == "$EXPECTED_CURRENT" ]] || fail CURRENT_RELEASE_CHANGED
readonly CAND="$ROOT/releases/platform-$SHORT"
[[ -d "$CAND/.git" && ! -L "$CAND" ]] || fail CANDIDATE_NOT_STAGED
readonly LIVE_APP="$LIVE/apps/platform"
readonly CAND_APP="$CAND/apps/platform"
[[ -f "$LIVE_APP/.env" && ! -L "$LIVE_APP/.env" ]] || fail LIVE_ENV_MISSING
[[ -d "$LIVE_APP/storage/app" && ! -L "$LIVE_APP/storage/app" ]] || fail LIVE_STORAGE_MISSING
[[ ! -e "$CAND_APP/.env" && ! -L "$CAND_APP/.env" ]] || fail CANDIDATE_ALREADY_MATERIALIZED_REVIEW
git_as() { runuser -u kmjprod -- git -c core.fsmonitor=false -C "$CAND" "$@"; }
[[ "$(git_as rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_SHA_MISMATCH
[[ -z "$(git_as status --porcelain --untracked-files=normal)" ]] || fail CANDIDATE_DIRTY_BEFORE
for item in vendor/autoload.php public/build/manifest.json public/assets/kmj-codebridge-icon.png; do
  [[ -s "$CAND_APP/$item" && ! -L "$CAND_APP/$item" ]] || fail CANDIDATE_ARTIFACT_MISSING
done
# The release controller lock prevents racing an activation.
exec 9>/run/lock/kmj-main-platform-production-release.lock
flock -n 9 || fail PRODUCTION_RELEASE_IN_PROGRESS

# 1. Runtime environment: exact live bytes, plus the owner-approved public
#    agent origin only when absent. A different existing value needs review.
if grep -Eq '^[[:space:]]*CODEBRIDGE_AGENT_PUBLIC_URL[[:space:]]*=' "$LIVE_APP/.env"; then
  grep -Fxq "$ORIGIN_LINE" "$LIVE_APP/.env" || fail LIVE_AGENT_PUBLIC_URL_DIFFERS_REVIEW
  origin_state=PRESERVED
else
  origin_state=PINNED_IN_CANDIDATE_ONLY
fi
install -o kmjprod -g kmjprod -m 0600 "$LIVE_APP/.env" "$CAND_APP/.env"
if [[ "$origin_state" == PINNED_IN_CANDIDATE_ONLY ]]; then
  [[ -z "$(tail -c1 "$CAND_APP/.env")" ]] || printf '\n' >>"$CAND_APP/.env"
  printf '%s\n' "$ORIGIN_LINE" >>"$CAND_APP/.env"
fi
status RUNTIME_ENV COPIED
status AGENT_PUBLIC_ORIGIN "$origin_state"

# 2. Uploads: copy without clobbering tracked placeholders. A size+path
# inventory is NOT content equality (equal-length different bytes can pass).
# The verifier is tracked by the exact candidate SHA and never follows links.
readonly STORAGE_VERIFIER="$CAND/scripts/operations/verify-main-platform-storage-manifest.py"
[[ -f "$STORAGE_VERIFIER" && ! -L "$STORAGE_VERIFIER" ]] || fail STORAGE_VERIFIER_MISSING
[[ -d "$CAND_APP/storage/app" && ! -L "$CAND_APP/storage/app" ]] || fail CANDIDATE_STORAGE_UNSAFE
source_before="$(python3 -B "$STORAGE_VERIFIER" "$LIVE_APP/storage/app")" || fail SOURCE_STORAGE_SCAN_FAILED
cp -a --no-clobber -- "$LIVE_APP/storage/app/." "$CAND_APP/storage/app/"
source_after="$(python3 -B "$STORAGE_VERIFIER" "$LIVE_APP/storage/app")" || fail SOURCE_STORAGE_RESCAN_FAILED
candidate_after="$(python3 -B "$STORAGE_VERIFIER" "$CAND_APP/storage/app")" || fail CANDIDATE_STORAGE_SCAN_FAILED
[[ "$source_before" == "$source_after" ]] || fail SOURCE_STORAGE_CHANGED_DURING_COPY
[[ "$source_after" == "$candidate_after" ]] || fail STORAGE_PARITY_MISMATCH
count="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["regular"])' "$candidate_after")"
links="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["symlinks"])' "$candidate_after")"
digest="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["sha256"])' "$candidate_after")"
status STORAGE_APP_PARITY "PASS_FILES_$count"
status STORAGE_SYMLINKS_PRESERVED "$links"
status STORAGE_MANIFEST_SHA256 "$digest"
status STORAGE_SYMLINK_TARGET_CONTENT NOT_DEREFERENCED
status STORAGE_WRITER_QUIESCENCE NOT_ATTESTED

# 3. public/storage link: mirror the live release only.
if [[ -L "$LIVE_APP/public/storage" ]]; then
  [[ "$(readlink "$LIVE_APP/public/storage")" == ../storage/app/public ||
     "$(readlink -f "$LIVE_APP/public/storage")" == "$LIVE_APP/storage/app/public" ]] ||
    fail LIVE_PUBLIC_STORAGE_LINK_UNEXPECTED
  [[ ! -e "$CAND_APP/public/storage" ]] || fail CANDIDATE_PUBLIC_STORAGE_EXISTS
  runuser -u kmjprod -- ln -s ../storage/app/public "$CAND_APP/public/storage"
  status PUBLIC_STORAGE_LINK MIRRORED
else
  status PUBLIC_STORAGE_LINK NOT_PRESENT_LIVE
fi

# Candidate must still be a clean exact checkout for the activation controller.
[[ -z "$(git_as status --porcelain --untracked-files=normal)" ]] || fail CANDIDATE_DIRTY_AFTER
[[ "$(git_as rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_SHA_CHANGED
[[ "$(readlink -f "$ROOT/current")" == "$LIVE" ]] || fail CURRENT_RELEASE_CHANGED_DURING_RUN

# 4. Pending migrations (file diff only; no database access).
pending=0
for file in "$CAND_APP"/database/migrations/*.php; do
  name="$(basename "$file")"
  if [[ ! -e "$LIVE_APP/database/migrations/$name" ]]; then
    pending=$((pending + 1))
    echo "PENDING_MIGRATION=$name"
  fi
done
status PENDING_MIGRATIONS "$pending"
status LIVE_RELEASE UNCHANGED
status DATABASE NOT_TOUCHED
status APPROVAL_UPDATED NO
status PRODUCTION_SWITCH NOT_ATTEMPTED
echo 'KMJ_MATERIALIZE=PASS'
