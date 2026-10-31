#!/usr/bin/env bash
# Guarded staging ACTIVATION runner. No arguments, no environment input, fixed paths.
# It only repoints the STAGING link to an already-prepared release whose SHA is in the root-protected
# approval. It never builds, deploys, restarts services, or touches production; any doubt => BLOCKED.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH GIT_DIR GIT_WORK_TREE

APPROVAL=/etc/kmj-codebridge/main-platform-staging-approval.json
SITE=/home/kmjstage/htdocs/staging.kmjtechno.com
PROD=/home/kmjprod/current
RELEASES=/home/kmjstage/releases
LOCKFILE=/run/lock/kmj-main-platform-staging-deploy.lock
UNIT_FILE=/etc/systemd/system/kmj-main-platform-staging-deploy.service
EXEC_LINE="ExecStart=/usr/bin/bash /usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh"
REQUIRE_UID=0
ANCHOR=/
STAGE_USER=kmjstage
EXPECTED_HOST=KMJ-elite

block() { echo "KMJ_STAGE_ACTIVATE=BLOCKED_$1"; exit 2; }
[[ "$#" -eq 0 ]] || block ARGUMENTS
[[ "$(id -u)" == "$REQUIRE_UID" && "$(hostname -s)" == "$EXPECTED_HOST" ]] || block HOST

# Root-owned path helpers. Every ancestor up to ANCHOR must be a real directory, owned by the required
# uid, not group/other-writable (so nothing can be swapped or planted underneath a checked path).
protected_dir_chain() {  # $2=stage: staging-owned directories (not only root) are acceptable, never g/o-writable
  local d="$1" owner stage_uid
  stage_uid="$(id -u -- "$STAGE_USER")" || return 1
  while :; do
    [[ -d "$d" && ! -L "$d" ]] || return 1
    owner="$(stat -c %u "$d")"
    [[ "$owner" == "$REQUIRE_UID" || ( "${2:-}" == stage && "$owner" == "$stage_uid" ) ]] || return 1
    (( (8#$(stat -c %a "$d") & 8#022) == 0 )) || return 1
    [[ "$d" == "$ANCHOR" || "$d" == / ]] && return 0
    d="$(dirname -- "$d")"
  done
}
protected_file() {  # regular, not a link, required owner, single link, no group/other write, non-empty
  local f="$1"
  [[ -f "$f" && ! -L "$f" ]] || return 1
  [[ "$(stat -c %u:%h "$f")" == "$REQUIRE_UID:1" ]] || return 1
  (( (8#$(stat -c %a "$f") & 8#022) == 0 )) || return 1
  [[ -s "$f" ]]
}

# Lock: created atomically (O_EXCL, never follows or truncates), then validated BEFORE it is opened
# read-only on the same path (no truncation of any planted target is possible).
( set -o noclobber; : >"$LOCKFILE" ) 2>/dev/null || :
[[ -f "$LOCKFILE" && ! -L "$LOCKFILE" && "$(stat -c %u:%h "$LOCKFILE")" == "$REQUIRE_UID:1" ]] || block LOCK
chmod 0600 -- "$LOCKFILE" || block LOCK
exec 9<"$LOCKFILE" || block LOCK
flock -n 9 || block LOCK_BUSY

# Strict, root-protected approval (same rules as the Supervisor attestation).
fields="$(python3 -I - "$APPROVAL" "$REQUIRE_UID" "$ANCHOR" <<'PY'
import hashlib, json, os, re, stat, sys
path, owner, anchor = sys.argv[1], int(sys.argv[2]), sys.argv[3]
KEYS = ["schema","approvedSha","expectedCurrentSha","expectedProductionRelease","runnerSha256",
        "unitSha256","backupVerified","rollbackVerified","storageVerified","zeroAdditionalCostVerified"]
def die(code):
    print("ERR " + code); sys.exit(0)
def pairs(items):
    out = {}
    for k, v in items:
        if k in out: die("APPROVAL_DUPLICATE_KEY")
        out[k] = v
    return out
d = os.path.dirname(path)
while True:
    st = os.lstat(d)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != owner or st.st_mode & 0o022: die("APPROVAL_ANCESTOR")
    if d == anchor or os.path.dirname(d) == d: break
    d = os.path.dirname(d)
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
except OSError:
    die("APPROVAL_MISSING")
st = os.fstat(fd)
if (not stat.S_ISREG(st.st_mode) or st.st_uid != owner or st.st_nlink != 1
        or st.st_mode & 0o022 or not 0 < st.st_size <= 4096): die("APPROVAL_FILE")
raw = os.read(fd, 4097)
try:
    v = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
except Exception:
    die("APPROVAL_JSON")
sha, rel, dig = re.compile(r"[a-f0-9]{40}\Z"), re.compile(r"[a-z0-9][a-z0-9_-]{3,100}\Z"), re.compile(r"[a-f0-9]{64}\Z")
if not isinstance(v, dict) or sorted(v) != sorted(KEYS): die("APPROVAL_KEYS")
ok = (v["schema"] == "kmj.main-platform.staging-approval.v1"
      and isinstance(v["approvedSha"], str) and sha.match(v["approvedSha"])
      and isinstance(v["expectedCurrentSha"], str) and sha.match(v["expectedCurrentSha"])
      and v["approvedSha"] != v["expectedCurrentSha"]
      and isinstance(v["expectedProductionRelease"], str) and rel.match(v["expectedProductionRelease"])
      and isinstance(v["runnerSha256"], str) and dig.match(v["runnerSha256"])
      and isinstance(v["unitSha256"], str) and dig.match(v["unitSha256"])
      and all(v[k] is True for k in ("backupVerified","rollbackVerified","storageVerified","zeroAdditionalCostVerified")))
if not ok: die("APPROVAL_VALUES")
print("OK", v["approvedSha"], v["expectedCurrentSha"], v["expectedProductionRelease"], v["runnerSha256"], v["unitSha256"])
PY
)"
read -r status approved expected_stage expected_prod runner_sha unit_sha <<<"$fields"
[[ "$status" == OK ]] || block "${fields#ERR }"
[[ "$(sha256sum -- "${BASH_SOURCE[0]}" | cut -d' ' -f1)" == "$runner_sha" ]] || block RUNNER_DIGEST

# Installed unit must be exactly the approved bytes at ACTUATION time (not just schema-valid in the approval).
# Honest scope: this proves the unit FILE on disk now; the Supervisor separately attests it by SHA-256.
protected_dir_chain "$(dirname -- "$UNIT_FILE")" || block UNIT_CHAIN
protected_file "$UNIT_FILE" || block UNIT_FILE
[[ ! -e "$UNIT_FILE.d" && ! -L "$UNIT_FILE.d" ]] || block UNIT_DROPIN
[[ "$(sha256sum -- "$UNIT_FILE" | cut -d' ' -f1)" == "$unit_sha" ]] || block UNIT_DIGEST
[[ "$(grep -c '^ExecStart=' "$UNIT_FILE")" == 1 ]] && grep -Fxq "$EXEC_LINE" "$UNIT_FILE" || block UNIT_EXEC

prod_target="$(readlink -- "$PROD")" || block PRODUCTION_POINTER
[[ -L "$PROD" && "$prod_target" == "/home/kmjprod/releases/$expected_prod" ]] || block PRODUCTION_DRIFT
[[ -L "$SITE" ]] || block STAGING_POINTER
cur_target="$(readlink -- "$SITE")"
new_target="$RELEASES/$approved/apps/platform"
old_target="$RELEASES/$expected_stage/apps/platform"

# The prepared candidate is verified in EVERY path (including already-active): a real, immutable-enough,
# staging-configured tree for exactly the approved SHA, reached through root/stage-owned non-linked parents.
rel_dir="$RELEASES/$approved"
protected_dir_chain "$(dirname -- "$SITE")" stage || block SITE_CHAIN
protected_dir_chain "$RELEASES" stage || block RELEASES_CHAIN
[[ -d "$rel_dir" && ! -L "$rel_dir" && -d "$new_target" && ! -L "$new_target" ]] || block CANDIDATE_MISSING
[[ "$(realpath -e -- "$new_target")" == "$new_target" ]] || block CANDIDATE_PATH_LINKED
[[ "$(stat -c %U "$rel_dir")" == "$STAGE_USER" && "$(stat -c %U "$new_target")" == "$STAGE_USER" ]] || block CANDIDATE_OWNER
for d in "$rel_dir" "$new_target" "$new_target/public" "$new_target/public/build"; do
  [[ -d "$d" && ! -L "$d" ]] || block CANDIDATE_MISSING
  (( (8#$(stat -c %a "$d") & 8#022) == 0 )) || block CANDIDATE_WRITABLE
done
candidate_checks() {
  [[ "$(git -c safe.directory="$rel_dir" -C "$rel_dir" rev-parse HEAD 2>/dev/null)" == "$approved" ]] || return 11
  [[ -f "$new_target/artisan" && ! -L "$new_target/artisan" && -s "$new_target/public/build/manifest.json" && ! -L "$new_target/public/build/manifest.json" ]] || return 12
  local env_file="$new_target/.env"
  [[ -f "$env_file" && ! -L "$env_file" && "$(stat -c %U "$env_file")" == "$STAGE_USER" && "$(stat -c %h "$env_file")" == 1 ]] || return 13
  case "$(stat -c %a "$env_file")" in 400|600) ;; *) return 14 ;; esac
  grep -Fxq APP_ENV=staging "$env_file" || return 15
  grep -Fxq APP_URL=https://staging.kmjtechno.com "$env_file" || return 16
}
verify_candidate() {
  candidate_checks && return 0
  case "$?" in
    11) block CANDIDATE_SHA ;; 12) block CANDIDATE_ARTIFACT ;; 13) block CANDIDATE_ENV ;;
    14) block CANDIDATE_ENV_MODE ;; 15) block CANDIDATE_NOT_STAGING ;; *) block CANDIDATE_URL ;;
  esac
}
verify_candidate

if [[ "$cur_target" == "$new_target" ]]; then echo "KMJ_STAGE_ACTIVATE=ALREADY_ACTIVE sha=$approved"; exit 0; fi
[[ "$cur_target" == "$old_target" ]] || block STAGING_BASELINE_DRIFT

tmp="$SITE.new.$$"
rollback() { ln -sfn "$old_target" "$tmp" && chown -h "$STAGE_USER" "$tmp" && mv -T -- "$tmp" "$SITE" || true; }
ln -s "$new_target" "$tmp" || block SWAP
chown -h "$STAGE_USER":"$STAGE_USER" "$tmp" 2>/dev/null || chown -h "$STAGE_USER" "$tmp" || { rm -f -- "$tmp"; block SWAP_OWNER; }
mv -T -- "$tmp" "$SITE" || { rm -f -- "$tmp"; block SWAP; }
# Post-swap: pointer, the whole chain it resolves through, the candidate itself and production are re-verified;
# any failure restores the previous staging target.
if [[ "$(readlink -- "$SITE")" != "$new_target" ]]; then rollback; block READBACK; fi
if [[ "$(realpath -e -- "$SITE")" != "$new_target" ]]; then rollback; block READBACK_PATH; fi
if ! candidate_checks; then rollback; block CANDIDATE_CHANGED; fi
if [[ "$(readlink -- "$PROD")" != "/home/kmjprod/releases/$expected_prod" ]]; then rollback; block PRODUCTION_CHANGED; fi
echo "KMJ_STAGE_ACTIVATE=ACTIVATED sha=$approved previous=$expected_stage"
