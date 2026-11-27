#!/usr/bin/env bash
# KMJ: source-only isolated staging snapshot; no approval, .env, DB or activation.
set -Eeuo pipefail
umask 077
export PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH GIT_DIR GIT_WORK_TREE
SHA=a9796a25a2801cd303a69f5ad468aa9a704e5fff
OLD=b2e69decab3acd861e94e11992cd8a4cff4f2b94
SHORT=a9796a25a280
RELEASES=/home/kmjstage/releases
STAGE_SITE=/home/kmjstage/htdocs/staging.kmjtechno.com
PROD_SITE=/home/kmjprod/current
TARGET=$RELEASES/$SHA
SOURCE=https://github.com/kmjtechno/kmj-main-platform.git
LOCK=/root/.kmj-stage-source-prep.lock
block() { printf 'KMJ_STAGE_SOURCE_PREP=BLOCKED_%s\n' "$1"; exit 2; }

[[ $# -eq 0 && $(id -u) -eq 0 && $(hostname -s) == KMJ-elite ]] || block ROOT_HOST_ARGS
for command_name in git runuser composer npm node python3 flock; do
  command -v "$command_name" >/dev/null 2>&1 || block "MISSING_TOOL_$command_name"
done
id kmjstage >/dev/null || block STAGE_USER
[[ -L $PROD_SITE && -L $STAGE_SITE ]] || block CURRENT_POINTERS
prod_link="$(readlink -- "$PROD_SITE")"
stage_link="$(readlink -- "$STAGE_SITE")"
[[ $prod_link == /home/kmjprod/releases/platform-574e443a2c75 || $prod_link == releases/platform-574e443a2c75 ]] || block PRODUCTION_POINTER
[[ $stage_link == "$RELEASES/$OLD/apps/platform" || $stage_link == "../releases/$OLD/apps/platform" ]] || block STAGING_POINTER
[[ -d $RELEASES && ! -L $RELEASES ]] || block RELEASES_DIR
[[ $(stat -c %u -- "$RELEASES") == 0 ]] || block RELEASES_PARENT_NOT_ROOT_OWNED
bits="$(stat -c %a -- "$RELEASES")"
[[ $bits =~ ^[0-7]{3,4}$ ]] || block RELEASES_MODE
(( (8#$bits & 8#022) == 0 )) || block RELEASES_WRITABLE
[[ ! -e $TARGET && ! -L $TARGET ]] || block ALREADY_EXISTS_NO_OVERWRITE
df -Pk -- "$RELEASES" | awk 'END {exit !($4 >= 4194304)}' || block SPACE_LT_4GB

( set -o noclobber; : > "$LOCK" ) 2>/dev/null || :
[[ -f $LOCK && ! -L $LOCK && $(stat -c '%u:%h' -- "$LOCK") == 0:1 ]] || block LOCK
chmod 0600 -- "$LOCK"
exec 9<"$LOCK"
flock -n 9 || block BUSY
scratch="$(mktemp -d "$RELEASES/.kmj-source-$SHORT.XXXXXXXX")" || block SCRATCH
cleanup() {
  case "$scratch" in "$RELEASES/.kmj-source-$SHORT."*)
    [[ ! -L $scratch && -d $scratch ]] && rm -rf -- "$scratch" || : ;;
  esac
}
trap cleanup EXIT
chown kmjstage:kmjstage -- "$scratch"
chmod 0700 -- "$scratch"

# Only the unprivileged staging user may run PHP/Node/composer build code.
runuser -u kmjstage -- env HOME=/home/kmjstage bash -s -- "$SOURCE" "$scratch/repo" "$SHA" <<'BUILD'
set -Eeuo pipefail
umask 077
src="$1"; dest="$2"; exact="$3"
git init -q "$dest"
git -C "$dest" remote add origin "$src"
git -C "$dest" -c protocol.version=2 fetch --depth 1 --no-tags origin "$exact"
git -C "$dest" checkout --detach -q FETCH_HEAD
[[ "$(git -C "$dest" rev-parse HEAD)" == "$exact" ]] || exit 2
app="$dest/apps/platform"
[[ -s "$app/composer.lock" && -s "$app/package-lock.json" && -f "$app/.env.example" ]] || exit 2
cd "$app"
[[ ! -e .env && ! -L .env ]] || exit 2
cp -- .env.example .env
chmod 0600 -- .env
trap 'rm -f -- .env' EXIT
composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts --no-progress
npm ci --ignore-scripts --no-audit --no-fund
npm run build
# node_modules is build-only and contains legitimate symlinks; it must not be
# published as a root-owned served candidate.
[[ -d node_modules && ! -L node_modules ]] || exit 2
rm -rf -- node_modules
rm -f -- .env
trap - EXIT
python3 - "$app" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
m = p / "public/build/manifest.json"
if not m.is_file() or m.is_symlink(): raise SystemExit(2)
manifest = json.loads(m.read_text())
row = manifest.get("resources/js/pages/services/codebridge-workspace.tsx")
if not isinstance(row, dict): raise SystemExit(2)
asset = row.get("file")
if (not isinstance(asset, str) or not asset.startswith("assets/")
    or ".." in pathlib.PurePosixPath(asset).parts or
    not (p / "public/build" / asset).is_file() or
    not (p / "vendor/autoload.php").is_file()): raise SystemExit(2)
print("KMJ_STAGE_BUILT_AI_WORKSPACE=PASS")
PY
[[ -z "$(git -C "$dest" status --porcelain --untracked-files=normal)" ]] || exit 2
echo 'KMJ_STAGE_BUILD=EXACT_SHA_PASS'
BUILD

# Revoke stage-user directory control before root verifies and publishes.
chown root:root -- "$scratch"
chmod 0700 -- "$scratch"
[[ -d "$scratch/repo" && ! -L "$scratch/repo" ]] || block OUTPUT_MISSING
chown -hR root:root -- "$scratch/repo"
chmod -R go-w -- "$scratch/repo"
[[ ! -e "$scratch/repo/apps/platform/.env" && ! -L "$scratch/repo/apps/platform/.env" ]] || block ENV_NOT_REMOVED
unsafe_objects="$(find "$scratch/repo/apps/platform" -xdev \( -type l -o -type p -o -type s -o -type c -o -type b \) -print -quit)" || block SCAN_UNAVAILABLE
[[ -z "$unsafe_objects" ]] || block UNSAFE_OBJECT_IN_SERVED_TREE
[[ "$(cat -- "$scratch/repo/.git/HEAD")" == "$SHA" ]] || block HEAD_DRIFT
[[ "$(readlink -- "$PROD_SITE")" == "$prod_link" && "$(readlink -- "$STAGE_SITE")" == "$stage_link" ]] || block POINTER_DRIFT
# No overwrite even on a concurrent name collision (Linux renameat2).
python3 -I - "$RELEASES" "$scratch/repo" "$SHA" <<'PUBLISH'
import ctypes, errno, os, stat, sys
parent, src, sha = sys.argv[1:]
fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
try:
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise SystemExit("KMJ_STAGE_PUBLISH=BLOCKED_PARENT")
    if os.stat(src, follow_symlinks=False).st_dev != st.st_dev:
        raise SystemExit("KMJ_STAGE_PUBLISH=BLOCKED_FILESYSTEM")
    libc = ctypes.CDLL(None, use_errno=True)
    fun = getattr(libc, "renameat2", None)
    if fun is None:
        raise SystemExit("KMJ_STAGE_PUBLISH=BLOCKED_NO_ATOMIC_NOREPLACE")
    fun.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fun.restype = ctypes.c_int
    if fun(-100, os.fsencode(src), fd, sha.encode(), 1) != 0:
        raise SystemExit("KMJ_STAGE_PUBLISH=BLOCKED_" + errno.errorcode.get(ctypes.get_errno(), "IO"))
finally:
    os.close(fd)
print("KMJ_STAGE_PUBLISH=EXACT_SHA_ATOMIC_NO_OVERWRITE")
PUBLISH
[[ -d $TARGET/apps/platform && ! -L $TARGET ]] || block READBACK_MISSING
[[ "$(readlink -- "$PROD_SITE")" == "$prod_link" && "$(readlink -- "$STAGE_SITE")" == "$stage_link" ]] || block POST_POINTER_CHANGED
printf '%s\n' 'STAGING_EXACT_CANDIDATE=SOURCE_PREPARED_UNSEALED' \
 'STAGING_RUNTIME_ENV=NOT_COPIED' 'STAGING_SEAL=NOT_CREATED' \
 'STAGING_APPROVAL=NOT_CREATED' 'STAGING_ACTIVATION=NOT_ATTEMPTED' \
 'PRODUCTION_POINTER=UNCHANGED' 'KMJ_STAGE_SOURCE_PREP=PASS_SOURCE_ONLY'
