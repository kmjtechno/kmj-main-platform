#!/bin/bash -p
# Materialize live runtime state into an already staged, clean Main Platform
# candidate so the fixed activation controller can switch to it safely.
#
# Usage (root on KMJ-elite, immediately before backup + activation):
#   materialize-main-platform-candidate-runtime.sh <approved-40-hex-sha> <expected-current-release>
#
# It copies ONLY the exact live .env bytes (0600 kmjprod), without adding
# or changing values, and verifies a pre-arranged shared storage link in BOTH
# current and candidate releases. Never copy uploads: live writers may change
# a copy during cutover. The approved shared directory must already exist
# outside releases at /home/kmjprod/shared/storage and be owner-prepared.
# The public/storage link is mirrored only when the live release has one.
# It reports pending migrations by file diff. It NEVER touches the live
# release, database, approval file, symlinks current/previous, services or DNS.
set -Eeuo pipefail
umask 077
# Root execution must not inherit caller PATH or Bash startup hooks.
# /bin/bash -p ignores BASH_ENV; plain `bash script` is rejected below.
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
fail() { echo "KMJ_MATERIALIZE=BLOCKED $1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }
[[ $- == *p* ]] || fail PRIVILEGED_BASH_REQUIRED
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
id www-data >/dev/null 2>&1 || fail WEB_USER_MISSING
for cmd in git runuser install cp find awk sha256sum flock python3 systemd-run setfacl; do
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
readonly SHARED="$ROOT/shared/storage"
[[ -f "$LIVE_APP/.env" && ! -L "$LIVE_APP/.env" ]] || fail LIVE_ENV_MISSING
[[ -d "$SHARED/app" && ! -L "$SHARED" && ! -L "$SHARED/app" ]] || fail SHARED_STORAGE_NOT_PREPARED
# Owner must first migrate uploads to a protected root outside ANY release.
# Do not create, replace or modify that link on behalf of a root operator.
[[ -L "$LIVE_APP/storage" && "$(readlink -f -- "$LIVE_APP/storage")" == "$SHARED" ]] || fail LIVE_STORAGE_NOT_SHARED
[[ -L "$CAND_APP/storage" && "$(readlink -f -- "$CAND_APP/storage")" == "$SHARED" ]] || fail CANDIDATE_STORAGE_NOT_SHARED
[[ -d "$LIVE_APP/storage/app" && -d "$CAND_APP/storage/app" ]] || fail SHARED_UPLOADS_MISSING
[[ ! -e "$CAND_APP/.env" && ! -L "$CAND_APP/.env" ]] || fail CANDIDATE_ALREADY_MATERIALIZED_REVIEW
git_as() { runuser -u kmjprod -- git -c core.fsmonitor=false -C "$CAND" "$@"; }
[[ "$(git_as rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_SHA_MISMATCH
# Runtime storage is the one owner-verified external symlink, not source code.
# All OTHER source paths remain subject to exact clean Git attestation.
[[ -z "$(git_as status --porcelain --untracked-files=normal -- . ':(exclude)apps/platform/storage')" ]] || fail CANDIDATE_DIRTY_BEFORE
for item in vendor/autoload.php public/build/manifest.json public/assets/kmj-codebridge-icon.png; do
  [[ -s "$CAND_APP/$item" && ! -L "$CAND_APP/$item" ]] || fail CANDIDATE_ARTIFACT_MISSING
done
# The release controller lock prevents racing an activation.
# Root must never create/truncate through a pre-planted symlink in the sticky /run/lock:
# O_EXCL create (noclobber) never follows a symlink; then require a root-owned 0600 single-link file.
readonly RELEASE_LOCK=/run/lock/kmj-main-platform-production-release.lock
# Only an atomic new 0600 inode is created. Never chmod an existing inode:
# a hostile hardlink or file replacement must fail instead of being repaired.
( umask 077; set -o noclobber; : >"$RELEASE_LOCK" ) 2>/dev/null || :
[[ -f "$RELEASE_LOCK" && ! -L "$RELEASE_LOCK" ]] || fail RELEASE_LOCK_UNSAFE
[[ "$(stat -c '%u:%h:%a' -- "$RELEASE_LOCK")" == "0:1:600" ]] || fail RELEASE_LOCK_UNSAFE
# Read-only open cannot truncate any swapped path. Reattest the actual open
# descriptor and compare its inode with the fixed lock path before/after flock.
exec 9<"$RELEASE_LOCK"
release_lock_fingerprint="$(stat -Lc '%u:%h:%a:%d:%i' -- /proc/self/fd/9)" || fail RELEASE_LOCK_FD_UNSAFE
[[ "$release_lock_fingerprint" == "0:1:600:$(stat -c '%d:%i' -- "$RELEASE_LOCK")" ]] || fail RELEASE_LOCK_FD_UNSAFE
flock -n 9 || fail PRODUCTION_RELEASE_IN_PROGRESS
[[ "$release_lock_fingerprint" == "0:1:600:$(stat -c '%d:%i' -- "$RELEASE_LOCK")" ]] || fail RELEASE_LOCK_CHANGED

# Root holds the release lock while a private mount namespace pins writable
# candidate storage. Live runtime and all other host paths stay read-only even
# if kmjprod replaces a candidate parent with a symlink during the copy.
systemd-run --quiet --wait --pipe --collect \
  --unit="kmj-materialize-$SHORT" \
  -p User=kmjprod -p Group=kmjprod -p UMask=0077 \
  -p ProtectSystem=strict -p ProtectHome=read-only \
  -p PrivateTmp=yes -p NoNewPrivileges=yes \
  -p "ReadWritePaths=$CAND" -p "ReadOnlyPaths=$LIVE_APP" \
  /bin/bash -s -- "$SHA" "$EXPECTED_CURRENT" "$ROOT" "$LIVE" "$CAND" "$ORIGIN_LINE" <<'KMJ_UNPRIVILEGED_MATERIALIZE'
set -Eeuo pipefail
umask 077
readonly SHA="$1" EXPECTED_CURRENT="$2" ROOT="$3" LIVE="$4" CAND="$5" ORIGIN_LINE="$6"
readonly LIVE_APP="$LIVE/apps/platform" CAND_APP="$CAND/apps/platform"
fail() { echo "KMJ_MATERIALIZE=BLOCKED $1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }
[[ "$(id -u)" == "$(id -u kmjprod)" && "$(id -u)" != 0 ]] || fail SANDBOX_USER_MISMATCH
export GIT_OPTIONAL_LOCKS=0
git_as() { git -c core.fsmonitor=false -C "$CAND" "$@"; }

# 1. Runtime .env must stay byte-identical across the switch.
# Never add a URL or modify APP_KEY during production runtime materialization.
if grep -Eq '^[[:space:]]*CODEBRIDGE_AGENT_PUBLIC_URL[[:space:]]*=' "$LIVE_APP/.env"; then
  grep -Fxq "$ORIGIN_LINE" "$LIVE_APP/.env" || fail LIVE_AGENT_PUBLIC_URL_DIFFERS_REVIEW
  origin_state=PRESERVED
else
  origin_state=NOT_SET_IN_LIVE
fi
install -o kmjprod -g kmjprod -m 0600 "$LIVE_APP/.env" "$CAND_APP/.env"
[[ "$(sha256sum -- "$LIVE_APP/.env" | cut -d' ' -f1)" == "$(sha256sum -- "$CAND_APP/.env" | cut -d' ' -f1)" ]] || fail ENV_SHA_MISMATCH
status RUNTIME_ENV BYTE_IDENTICAL
status AGENT_PUBLIC_ORIGIN "$origin_state"

# 2. Uploads: copy without clobbering tracked placeholders. A size+path
# inventory is NOT content equality (equal-length different bytes can pass).
# Inlined verify-main-platform-storage-manifest.py.
# Embedded in the independently pinned operator script; never execute candidate code as root.
storage_manifest() {
  /usr/bin/python3 -I -S - "$1" <<'KMJ_STORAGE_MANIFEST_PY'
#!/usr/bin/env python3
"""Descriptor-relative, no-follow storage inventory with access metadata."""
from __future__ import annotations
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

def _directory(path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for name in Path(os.path.abspath(path)).parts[1:]:
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError as error:
        os.close(fd)
        raise ValueError("STORAGE_ROOT_NOT_REAL_DIRECTORY") from error

def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def inventory(root: Path) -> dict[str, object]:
    root_fd = _directory(root)
    entries = []
    counts = {"regular": 0, "symlinks": 0, "directories": 0}
    def visit(fd, prefix):
        before = os.fstat(fd)
        entries.append(["d", prefix, stat.S_IMODE(before.st_mode), before.st_uid, before.st_gid])
        for name in sorted(os.listdir(fd)):
            relative = prefix + "/" + name if prefix else name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if _stamp(os.fstat(child)) != _stamp(info):
                        raise ValueError("DIRECTORY_REPLACED")
                    counts["directories"] += 1
                    visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if name == ".gitignore":
                    continue
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    if not stat.S_ISREG(opened.st_mode) or _stamp(opened) != _stamp(info):
                        raise ValueError("FILE_REPLACED_DURING_SCAN")
                    digest = hashlib.sha256()
                    while chunk := os.read(child, 1024 * 1024):
                        digest.update(chunk)
                    if _stamp(os.fstat(child)) != _stamp(opened):
                        raise ValueError("FILE_CHANGED_DURING_SCAN")
                finally:
                    os.close(child)
                entries.append(["f", relative, opened.st_size, digest.hexdigest(),
                    stat.S_IMODE(opened.st_mode), opened.st_uid, opened.st_gid, opened.st_mtime_ns])
                counts["regular"] += 1
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(name, dir_fd=fd)
                entries.append(["l", relative, target, info.st_uid, info.st_gid, info.st_mtime_ns])
                counts["symlinks"] += 1
            else:
                raise ValueError("UNSUPPORTED_STORAGE_ENTRY")
            if _stamp(os.stat(name, dir_fd=fd, follow_symlinks=False)) != _stamp(info):
                raise ValueError("ENTRY_CHANGED_DURING_SCAN")
        if _stamp(os.fstat(fd)) != _stamp(before):
            raise ValueError("DIRECTORY_CHANGED_DURING_SCAN")
    try:
        visit(root_fd, "")
        current = _directory(root)
        try:
            if _stamp(os.fstat(current)) != _stamp(os.fstat(root_fd)):
                raise ValueError("STORAGE_ROOT_REPLACED")
        finally:
            os.close(current)
    finally:
        os.close(root_fd)
    payload = json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(payload).hexdigest(), **counts}

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("STORAGE_MANIFEST=BLOCKED_USAGE", file=sys.stderr)
        return 2
    try:
        result = inventory(Path(argv[1]))
    except (OSError, ValueError) as exc:
        print(f"STORAGE_MANIFEST=BLOCKED_{type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

KMJ_STORAGE_MANIFEST_PY
}
# 2. Both releases MUST already resolve to the same, owner-prepared
# persistent shared directory. No copying, changing upload paths or deploying
# storage symlinks from this script. All writes remain outside source releases.
[[ -L "$LIVE_APP/storage" && -L "$CAND_APP/storage" ]] || fail STORAGE_SYMLINK_MISSING
[[ "$(readlink -f -- "$LIVE_APP/storage")" == "$ROOT/shared/storage" ]] || fail LIVE_STORAGE_NOT_SHARED
[[ "$(readlink -f -- "$CAND_APP/storage")" == "$ROOT/shared/storage" ]] || fail CANDIDATE_STORAGE_NOT_SHARED
source_before="$(storage_manifest "$ROOT/shared/storage/app")" || fail SHARED_STORAGE_SCAN_FAILED
source_after="$(storage_manifest "$ROOT/shared/storage/app")" || fail SHARED_STORAGE_RESCAN_FAILED
[[ "$source_before" == "$source_after" ]] || fail SHARED_STORAGE_MOVING_TARGET
count="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["regular"])' "$source_after")"
links="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["symlinks"])' "$source_after")"
digest="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["sha256"])' "$source_after")"
status STORAGE_MODE VERIFIED_SHARED
status STORAGE_APP_PARITY "SHARED_FILES_$count"
status STORAGE_SYMLINKS_PRESERVED "$links"
status STORAGE_MANIFEST_SHA256 "$digest"
status STORAGE_WRITER_QUIESCENCE NOT_ATTESTED

# 3. public/storage link: mirror the live release only.
if [[ -L "$LIVE_APP/public/storage" ]]; then
  [[ "$(readlink "$LIVE_APP/public/storage")" == ../storage/app/public ||
     "$(readlink -f "$LIVE_APP/public/storage")" == "$LIVE_APP/storage/app/public" ]] ||
    fail LIVE_PUBLIC_STORAGE_LINK_UNEXPECTED
  [[ ! -e "$CAND_APP/public/storage" ]] || fail CANDIDATE_PUBLIC_STORAGE_EXISTS
  ln -s ../storage/app/public "$CAND_APP/public/storage"
  status PUBLIC_STORAGE_LINK MIRRORED
else
  status PUBLIC_STORAGE_LINK NOT_PRESENT_LIVE
fi

# 4. Nginx (www-data) must read public/ exactly like the live release, via a
#    minimal ACL: traverse-only on ancestors, read on public/. The candidate is
#    built with umask 077, so without this the activation health check fails
#    (403 on static assets) and the controller rolls back. .env stays private.
for dir in "$CAND" "$CAND/apps" "$CAND_APP"; do
  [[ -d "$dir" && ! -L "$dir" ]] || fail PUBLIC_ANCESTOR_UNSAFE
  setfacl -m 'u:www-data:--x' "$dir" || fail ANCESTOR_ACL_FAILED
done
setfacl -R -m 'u:www-data:rX' "$CAND_APP/public" || fail PUBLIC_TREE_ACL_FAILED

# Candidate must still be a clean exact checkout for the activation controller.
[[ -z "$(git_as status --porcelain --untracked-files=normal -- . ':(exclude)apps/platform/storage')" ]] || fail CANDIDATE_DIRTY_AFTER
[[ "$(git_as rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_SHA_CHANGED
[[ "$(readlink -f "$ROOT/current")" == "$LIVE" ]] || fail CURRENT_RELEASE_CHANGED_DURING_RUN

# 5. Pending migrations (file diff only; no database access).
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
echo 'KMJ_MATERIALIZE_SHARED=PASS'

KMJ_UNPRIVILEGED_MATERIALIZE

runuser -u www-data -- test -r "$CAND_APP/public/index.php" || fail NGINX_PUBLIC_UNREADABLE
runuser -u www-data -- test -r "$CAND_APP/public/assets/kmj-codebridge-icon.png" || fail NGINX_ICON_UNREADABLE
runuser -u www-data -- test ! -r "$CAND_APP/.env" || fail NGINX_PRIVATE_ENV_EXPOSED
status NGINX_PUBLIC_ACL PASS
status NGINX_PRIVATE_ENV DENIED
echo "KMJ_MATERIALIZE=PASS"
