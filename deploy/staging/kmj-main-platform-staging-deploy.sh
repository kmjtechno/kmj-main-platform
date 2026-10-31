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
LOCKFILE=/run/kmj-main-platform-staging/deploy.lock
SEAL_DIR=/etc/kmj-codebridge
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

# Lock. A tiny fixed Python helper opens the lock with O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC (creating it with O_EXCL
# when absent; never truncating), then fstat/fchmod/flock on that SAME descriptor and re-executes this runner with
# the descriptor as fd 9. No pathname chmod, no second open. The lock directory chain is protected first.
protected_dir_chain "$(dirname -- "$LOCKFILE")" || block LOCK_CHAIN
if [[ ! -e /proc/self/fd/9 ]]; then
  exec python3 -I -c '
import fcntl, os, stat, sys
path, owner, bash, script = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
def die(code):
    print("KMJ_STAGE_ACTIVATE=BLOCKED_" + code); sys.exit(2)
flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
try:
    fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    try:
        fd = os.open(path, flags)
    except OSError:
        die("LOCK")
except OSError:
    die("LOCK")
st = os.fstat(fd)
if not stat.S_ISREG(st.st_mode) or st.st_uid != owner or st.st_nlink != 1:
    die("LOCK")
os.fchmod(fd, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    die("LOCK_BUSY")
os.dup2(fd, 9, inheritable=True)
os.close(fd)
os.execv(bash, [bash, script])
' "$LOCKFILE" "$REQUIRE_UID" "$BASH" "${BASH_SOURCE[0]}" || block LOCK
fi
# Re-entered (or invoked with an unexpected fd 9): fd 9 must BE the lock file at the fixed path, same inode.
fd_id="$(stat -L -c '%d:%i:%u:%h' /proc/self/fd/9)" || block LOCK
path_id="$(stat -c '%d:%i:%u:%h:%F' -- "$LOCKFILE")" || block LOCK
[[ "$path_id" == "$fd_id":*regular* ]] || block LOCK
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
# staging-configured tree for exactly the approved SHA, reached through ROOT-owned non-linked parents.
# A stage-user-owned directory is writable by its owner even when mode is 0755; never trust it.
rel_dir="$RELEASES/$approved"
protected_dir_chain "$(dirname -- "$SITE")" || block SITE_CHAIN
protected_dir_chain "$RELEASES" || block RELEASES_CHAIN
[[ -d "$rel_dir" && ! -L "$rel_dir" && -d "$new_target" && ! -L "$new_target" ]] || block CANDIDATE_MISSING
[[ "$(realpath -e -- "$new_target")" == "$new_target" ]] || block CANDIDATE_PATH_LINKED
[[ "$(stat -c %u "$rel_dir")" == "$REQUIRE_UID" && "$(stat -c %u "$new_target")" == "$REQUIRE_UID" ]] || block CANDIDATE_OWNER
for d in "$rel_dir" "$new_target" "$new_target/public" "$new_target/public/build"; do
  [[ -d "$d" && ! -L "$d" ]] || block CANDIDATE_MISSING
  (( (8#$(stat -c %a "$d") & 8#022) == 0 )) || block CANDIDATE_WRITABLE
done
# Digest of the SERVED tree (apps/platform minus .env, storage, bootstrap/cache, node_modules). One algorithm,
# embedded here so runnerSha256 covers it; the owner seal tool extracts and runs exactly this program.
tree_digest() {
  python3 -I - "$1" <<'DIGEST_PY'
import hashlib, os, stat, sys
root = sys.argv[1]
SKIP = {".env", "storage", "bootstrap/cache", "node_modules", ".git"}
lines, count = [], 0
def die(code):
    print("ERR " + code); sys.exit(0)
for cur, dirs, files in os.walk(root, followlinks=False):
    rel = os.path.relpath(cur, root).replace(os.sep, "/")
    rel = "" if rel == "." else rel
    dirs[:] = sorted(d for d in dirs if (rel + "/" + d).lstrip("/") not in SKIP)
    for name in sorted(files) + dirs:
        r = (rel + "/" + name).lstrip("/")
        if r in SKIP:
            continue
        st = os.lstat(os.path.join(cur, name))
        count += 1
        if count > 400000: die("TOO_MANY")
        if st.st_uid != os.getuid(): die("OWNER")
        if st.st_mode & 0o022: die("WRITABLE")
        if stat.S_ISLNK(st.st_mode):
            die("LINK")
        elif stat.S_ISDIR(st.st_mode):
            lines.append("d:%s:%o" % (r, st.st_mode & 0o7777))
        elif stat.S_ISREG(st.st_mode):
            if st.st_nlink != 1: die("HARDLINK")
            h = hashlib.sha256()
            with open(os.path.join(cur, name), "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
            lines.append("f:%s:%o:%s" % (r, st.st_mode & 0o7777, h.hexdigest()))
        else:
            die("SPECIAL")
print("OK " + hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest())
DIGEST_PY
}

candidate_checks() {
  [[ "$(git -c safe.directory="$rel_dir" -C "$rel_dir" rev-parse HEAD 2>/dev/null)" == "$approved" ]] || return 11
  [[ -f "$new_target/artisan" && ! -L "$new_target/artisan" && -s "$new_target/public/build/manifest.json" && ! -L "$new_target/public/build/manifest.json" ]] || return 12
  local env_file="$new_target/.env"
  [[ -f "$env_file" && ! -L "$env_file" && "$(stat -c %u "$env_file")" == "$REQUIRE_UID" && "$(stat -c %h "$env_file")" == 1 ]] || return 13
  # Owner-sealed configuration: root owns it; the PHP stage group may READ but never write.
  [[ "$(stat -c %g "$env_file")" == "$(id -g -- "$STAGE_USER")" ]] || return 13
  [[ "$(stat -c %a "$env_file")" == 640 ]] || return 14
  grep -Fxq APP_ENV=staging "$env_file" || return 15
  grep -Fxq APP_URL=https://staging.kmjtechno.com "$env_file" || return 16
  # Tracked files must equal HEAD, and the whole served tree must match the root-protected owner seal.
  [[ -z "$(git -c safe.directory="$rel_dir" -C "$rel_dir" status --porcelain --untracked-files=no 2>/dev/null)" ]] || return 17
  local seal="$SEAL_DIR/main-platform-staging-seal-$approved.sha256" got
  protected_file "$seal" || return 18
  got="$(tree_digest "$new_target")"
  case "$got" in "ERR WRITABLE") return 19 ;; OK\ *) ;; *) return 20 ;; esac
  [[ "${got#OK }" == "$(head -c 64 -- "$seal")" && "$(stat -c %s -- "$seal")" -le 65 ]] || return 20
}
verify_candidate() {
  candidate_checks && return 0
  case "$?" in
    11) block CANDIDATE_SHA ;; 12) block CANDIDATE_ARTIFACT ;; 13) block CANDIDATE_ENV ;;
    14) block CANDIDATE_ENV_MODE ;; 15) block CANDIDATE_NOT_STAGING ;; 16) block CANDIDATE_URL ;;
    17) block CANDIDATE_DIRTY ;; 18) block CANDIDATE_SEAL_MISSING ;; 19) block CANDIDATE_WRITABLE ;; *) block CANDIDATE_SEAL ;;
  esac
}
protected_dir_chain "$SEAL_DIR" || block SEAL_CHAIN
verify_candidate

if [[ "$cur_target" == "$new_target" ]]; then echo "KMJ_STAGE_ACTIVATE=ALREADY_ACTIVE sha=$approved"; exit 0; fi
[[ "$cur_target" == "$old_target" ]] || block STAGING_BASELINE_DRIFT

tmp="$SITE.new.$$"
rollback() { ln -sfn "$old_target" "$tmp" && mv -T -- "$tmp" "$SITE" || true; }
ln -s "$new_target" "$tmp" || block SWAP
mv -T -- "$tmp" "$SITE" || { rm -f -- "$tmp"; block SWAP; }
# Post-swap: pointer, the whole chain it resolves through, the candidate itself and production are re-verified;
# any failure restores the previous staging target.
if [[ "$(readlink -- "$SITE")" != "$new_target" ]]; then rollback; block READBACK; fi
if [[ "$(realpath -e -- "$SITE")" != "$new_target" ]]; then rollback; block READBACK_PATH; fi
if ! candidate_checks; then rollback; block CANDIDATE_CHANGED; fi
if [[ "$(readlink -- "$PROD")" != "/home/kmjprod/releases/$expected_prod" ]]; then rollback; block PRODUCTION_CHANGED; fi
echo "KMJ_STAGE_ACTIVATE=ACTIVATED sha=$approved previous=$expected_stage"
