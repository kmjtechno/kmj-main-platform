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
REQUIRE_UID=0
ANCHOR=/
STAGE_USER=kmjstage
EXPECTED_HOST=KMJ-elite

block() { echo "KMJ_STAGE_ACTIVATE=BLOCKED_$1"; exit 2; }
[[ "$#" -eq 0 ]] || block ARGUMENTS
[[ "$(id -u)" == "$REQUIRE_UID" && "$(hostname -s)" == "$EXPECTED_HOST" ]] || block HOST

exec 9>"$LOCKFILE" || block LOCK
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
print("OK", v["approvedSha"], v["expectedCurrentSha"], v["expectedProductionRelease"], v["runnerSha256"])
PY
)"
read -r status approved expected_stage expected_prod runner_sha <<<"$fields"
[[ "$status" == OK ]] || block "${fields#ERR }"
[[ "$(sha256sum -- "${BASH_SOURCE[0]}" | cut -d' ' -f1)" == "$runner_sha" ]] || block RUNNER_DIGEST

prod_target="$(readlink -- "$PROD")" || block PRODUCTION_POINTER
[[ -L "$PROD" && "$prod_target" == "/home/kmjprod/releases/$expected_prod" ]] || block PRODUCTION_DRIFT
[[ -L "$SITE" ]] || block STAGING_POINTER
cur_target="$(readlink -- "$SITE")"
new_target="$RELEASES/$approved/apps/platform"
old_target="$RELEASES/$expected_stage/apps/platform"
if [[ "$cur_target" == "$new_target" ]]; then echo "KMJ_STAGE_ACTIVATE=ALREADY_ACTIVE sha=$approved"; exit 0; fi
[[ "$cur_target" == "$old_target" ]] || block STAGING_BASELINE_DRIFT

# The prepared candidate must be a real, staging-configured tree for exactly the approved SHA.
rel_dir="$RELEASES/$approved"
[[ -d "$rel_dir" && ! -L "$rel_dir" && -d "$new_target" && ! -L "$new_target" ]] || block CANDIDATE_MISSING
[[ "$(stat -c %U "$rel_dir")" == "$STAGE_USER" && "$(stat -c %U "$new_target")" == "$STAGE_USER" ]] || block CANDIDATE_OWNER
[[ "$(git -c safe.directory="$rel_dir" -C "$rel_dir" rev-parse HEAD 2>/dev/null)" == "$approved" ]] || block CANDIDATE_SHA
[[ -f "$new_target/artisan" && -s "$new_target/public/build/manifest.json" ]] || block CANDIDATE_ARTIFACT
env_file="$new_target/.env"
[[ -f "$env_file" && ! -L "$env_file" && "$(stat -c %U "$env_file")" == "$STAGE_USER" ]] || block CANDIDATE_ENV
case "$(stat -c %a "$env_file")" in 400|600) ;; *) block CANDIDATE_ENV_MODE ;; esac
grep -Fxq APP_ENV=staging "$env_file" || block CANDIDATE_NOT_STAGING
grep -Fxq APP_URL=https://staging.kmjtechno.com "$env_file" || block CANDIDATE_URL

tmp="$SITE.new.$$"
rollback() { ln -sfn "$old_target" "$tmp" && chown -h "$STAGE_USER" "$tmp" && mv -T -- "$tmp" "$SITE" || true; }
ln -s "$new_target" "$tmp" || block SWAP
chown -h "$STAGE_USER":"$STAGE_USER" "$tmp" 2>/dev/null || chown -h "$STAGE_USER" "$tmp" || { rm -f -- "$tmp"; block SWAP_OWNER; }
mv -T -- "$tmp" "$SITE" || { rm -f -- "$tmp"; block SWAP; }
if [[ "$(readlink -- "$SITE")" != "$new_target" ]]; then rollback; block READBACK; fi
if [[ "$(readlink -- "$PROD")" != "/home/kmjprod/releases/$expected_prod" ]]; then rollback; block PRODUCTION_CHANGED; fi
echo "KMJ_STAGE_ACTIVATE=ACTIVATED sha=$approved previous=$expected_stage"
