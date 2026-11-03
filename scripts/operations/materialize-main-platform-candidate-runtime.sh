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
unset BASH_ENV ENV CDPATH TMPDIR
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
for cmd in git runuser install cp find awk sha256sum flock python3 systemd-run setfacl sed; do
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
# The unprivileged body is kept in a variable so the SAME sandbox definition can
# also run the candidate-only rollback after a later root-side check fails.
IFS= read -r -d '' SANDBOX_BODY <<'KMJ_UNPRIVILEGED_MATERIALIZE' || true
set -Eeuo pipefail
umask 077
readonly SHA="$1" EXPECTED_CURRENT="$2" ROOT="$3" LIVE="$4" CAND="$5" ORIGIN_LINE="$6"
readonly LIVE_APP="$LIVE/apps/platform" CAND_APP="$CAND/apps/platform"
fail() { echo "KMJ_MATERIALIZE=BLOCKED $1"; exit 2; }
status() { printf '%s=%s\n' "$1" "$2"; }
[[ "$(id -u)" == "$(id -u kmjprod)" && "$(id -u)" != 0 ]] || fail SANDBOX_USER_MISMATCH
export GIT_OPTIONAL_LOCKS=0
git_as() { git -c core.fsmonitor=false -C "$CAND" "$@"; }

readonly MODE="${7:-materialize}" ROLLBACK_ENV_ID="${8:-}" ROLLBACK_LINK_ID="${9:-}"
[[ "$MODE" == materialize || "$MODE" == rollback ]] || fail BAD_SANDBOX_MODE

# Descriptor-anchored no-follow creation. NO unprivileged deletion is
# allowed: the sandbox has no trusted quarantine directory. The owner-attested
# root wrapper retires known inodes only under its private same-filesystem dir.
fs_op() {
  /usr/bin/python3 -I -S - "$@" <<'KMJ_FS_OP_PY'
import hashlib, os, stat, sys

MAX_ENV_BYTES = 1048576

def open_dir(path):
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in [p for p in path.split("/") if p]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise

def ident(info):
    return "%d:%d" % (info.st_dev, info.st_ino)

DETACH_PREFIX = ".kmj-detach-"

def assert_no_detach_leftover(dir_fd):
    # A SIGKILL between detach and unlink/restore can strand a quarantined
    # object. Never create new artifacts beside an unreviewed one.
    for entry in os.listdir(dir_fd):
        if entry.startswith(DETACH_PREFIX):
            raise ValueError("DETACH_LEFTOVER_OWNER_REVIEW")

def remove_exact(dir_fd, name, expected, kind, live_fd=None):
    # The sandbox cannot delete rollback objects: all removals require the
    # root-owned same-filesystem quarantine, whose ancestors it cannot write.
    # The former verify(q)->unlink(q) was unsafe in its writable directory.
    return "BLOCKED_UNPRIVILEGED"

def emit(created, handle, dir_fd, name, kind, live_fd=None):
    """Deliver the inode id to the parent; if that fails, self-clean right here."""
    try:
        sys.stdout.write(created + "\n")
        sys.stdout.flush()
    except BaseException:
        try:
            result = remove_exact(dir_fd, name, created, kind, live_fd)
            if result not in ("REMOVED", "ABSENT"):
                print("FS_OP_ROLLBACK=FAILED_OWNER_REVIEW", file=sys.stderr)
        except BaseException:
            print("FS_OP_ROLLBACK=FAILED_OWNER_REVIEW", file=sys.stderr)
        raise

def main(argv):
    op = argv[1]
    if op == "create-env":
        live, cand = open_dir(argv[2]), open_dir(argv[3])
        assert_no_detach_leftover(cand)
        src = os.open(".env", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=live)
        info = os.fstat(src)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ENV_BYTES:
            raise ValueError("LIVE_ENV_UNSAFE")
        # A pre-read stat is insufficient: the live file can grow mid-copy.
        # Bound both read volume and memory to MAX_ENV_BYTES + 1.
        data = bytearray()
        while len(data) <= MAX_ENV_BYTES:
            chunk = os.read(src, min(65536, MAX_ENV_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > MAX_ENV_BYTES:
            raise ValueError("LIVE_ENV_OVER_LIMIT")
        after = os.fstat(src)
        if (len(data) != info.st_size
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)):
            raise ValueError("LIVE_ENV_CHANGED")
        dst = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=cand)
        # The new file exists even if the first fstat fails. Without an
        # inode receipt, NEVER guess which candidate pathname can be unlinked.
        try:
            created = ident(os.fstat(dst))
        except BaseException:
            print("FS_OP_POST_CREATE_RECEIPT=UNATTESTED_OWNER_REVIEW", file=sys.stderr)
            raise
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(dst, view):]
            os.fsync(dst)
        except BaseException:
            remove_exact(cand, ".env", created, "f", live)
            raise
        emit(created, dst, cand, ".env", "f", live)
    elif op == "create-link":
        pub = open_dir(argv[2])
        assert_no_detach_leftover(pub)
        os.symlink("../storage/app/public", "storage", dir_fd=pub)
        # This name may have been replaced between symlink and lstat; if
        # attestation fails, leave it for owner review, not a blind unlink.
        try:
            info = os.stat("storage", dir_fd=pub, follow_symlinks=False)
            if not stat.S_ISLNK(info.st_mode):
                raise ValueError("CREATED_STORAGE_NOT_SYMLINK")
            created = ident(info)
            target = os.readlink("storage", dir_fd=pub)
            final = os.stat("storage", dir_fd=pub, follow_symlinks=False)
            if (target != "../storage/app/public" or not stat.S_ISLNK(final.st_mode)
                    or ident(final) != created):
                raise ValueError("CREATED_STORAGE_LINK_TARGET_CHANGED")
        except BaseException:
            print("FS_OP_POST_CREATE_RECEIPT=UNATTESTED_OWNER_REVIEW", file=sys.stderr)
            raise
        emit(created, None, pub, "storage", "l")
    elif op == "verify-link":
        pub = open_dir(argv[2])
        expected = argv[3]
        before = os.stat("storage", dir_fd=pub, follow_symlinks=False)
        if not stat.S_ISLNK(before.st_mode) or ident(before) != expected:
            raise ValueError("STORAGE_LINK_ID_CHANGED")
        target = os.readlink("storage", dir_fd=pub)
        after = os.stat("storage", dir_fd=pub, follow_symlinks=False)
        if (target != "../storage/app/public" or not stat.S_ISLNK(after.st_mode)
                or ident(after) != expected):
            raise ValueError("STORAGE_LINK_TARGET_CHANGED")
        print("STORAGE_LINK_ATTESTED=PASS")
    elif op == "remove":
        result = remove_exact(open_dir(argv[2]), argv[3], argv[4], argv[5],
                              open_dir(argv[6]) if argv[5] == "f" and len(argv) > 6 else None)
        print("ROLLBACK_" + argv[3].lstrip(".").upper() + "=" + result)
        if result in ("MISMATCH", "QUARANTINED", "BLOCKED_UNPRIVILEGED"):
            sys.exit(3)
    else:
        raise ValueError("BAD_OP")

try:
    main(sys.argv)
except (OSError, ValueError) as exc:
    print("FS_OP_FAILED=" + type(exc).__name__, file=sys.stderr)
    sys.exit(2)
KMJ_FS_OP_PY
}

env_id="$ROLLBACK_ENV_ID"
link_id="$ROLLBACK_LINK_ID"
# A creation helper can fail after O_EXCL/symlink but before its inode receipt.
# Never claim an empty receipt list proves successful rollback in that case.
receipt_uncertain=0
rollback_candidate() {
  # A sandbox-owned directory is never a safe location for a verified-then-
  # unlinked name. The parent root wrapper alone handles known inode receipts.
  # Missing receipts remain owner-review, never a guessed successful cleanup.
  status CANDIDATE_ROLLBACK FAILED_REVIEW
  return 1
}
if [[ "$MODE" == rollback ]]; then rollback_candidate; exit $?; fi
committed=0
on_exit() {
  local rc=$?
  if [[ "$rc" != 0 && "$committed" != 1 ]]; then rollback_candidate || true; fi
  exit "$rc"
}
trap 'exit 143' TERM INT HUP
trap on_exit EXIT

# 1. Runtime .env must stay byte-identical across the switch.
# Never add a URL or modify APP_KEY during production runtime materialization.
# It is installed last (step 4) so no later check can strand it in the candidate.
if grep -Eq '^[[:space:]]*CODEBRIDGE_AGENT_PUBLIC_URL[[:space:]]*=' "$LIVE_APP/.env"; then
  grep -Fxq "$ORIGIN_LINE" "$LIVE_APP/.env" || fail LIVE_AGENT_PUBLIC_URL_DIFFERS_REVIEW
  origin_state=PRESERVED
else
  origin_state=NOT_SET_IN_LIVE
fi

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

# 3. public/storage link: validate the live link now; create it in step 5.
if [[ -L "$LIVE_APP/public/storage" ]]; then
  [[ "$(readlink "$LIVE_APP/public/storage")" == ../storage/app/public ||
     "$(readlink -f "$LIVE_APP/public/storage")" == "$LIVE_APP/storage/app/public" ]] ||
    fail LIVE_PUBLIC_STORAGE_LINK_UNEXPECTED
  [[ ! -e "$CAND_APP/public/storage" && ! -L "$CAND_APP/public/storage" ]] || fail CANDIDATE_PUBLIC_STORAGE_EXISTS
  want_link=1
else
  want_link=0
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

# Every fallible read-only check above has passed. Create the only two
# candidate artifacts last (O_EXCL, inode-recorded) so any failure from here on
# removes exactly what this run created.
[[ -z "$(git_as status --porcelain --untracked-files=normal -- . ':(exclude)apps/platform/storage')" ]] || fail CANDIDATE_DIRTY_BEFORE_WRITE
env_id="$(fs_op create-env "$LIVE_APP" "$CAND_APP")" || { receipt_uncertain=1; fail ENV_CREATE_FAILED; }
[[ "$env_id" =~ ^[0-9]+:[0-9]+$ ]] || { env_id=""; receipt_uncertain=1; fail ENV_CREATE_FAILED; }
echo "MATERIALIZED_ENV_ID=$env_id"
[[ "$(sha256sum -- "$LIVE_APP/.env" | cut -d' ' -f1)" == "$(sha256sum -- "$CAND_APP/.env" | cut -d' ' -f1)" ]] || fail ENV_SHA_MISMATCH
status RUNTIME_ENV BYTE_IDENTICAL
status AGENT_PUBLIC_ORIGIN "$origin_state"
if [[ "$want_link" == 1 ]]; then
  link_id="$(fs_op create-link "$CAND_APP/public")" || { receipt_uncertain=1; fail LINK_CREATE_FAILED; }
  [[ "$link_id" =~ ^[0-9]+:[0-9]+$ ]] || { link_id=""; receipt_uncertain=1; fail LINK_CREATE_FAILED; }
  echo "MATERIALIZED_LINK_ID=$link_id"
  status PUBLIC_STORAGE_LINK MIRRORED
else
  status PUBLIC_STORAGE_LINK NOT_PRESENT_LIVE
fi

# Candidate must still be a clean exact checkout for the activation controller.
[[ -z "$(git_as status --porcelain --untracked-files=normal -- . ':(exclude)apps/platform/storage')" ]] || fail CANDIDATE_DIRTY_AFTER
[[ "$(git_as rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_SHA_CHANGED
# A matching inode receipt alone does not attest symlink contents. Re-open
# through no-follow directory fds and require the exact storage target before
# reporting success. Activation must independently reattest at cutover.
if [[ "$want_link" == 1 ]]; then
  fs_op verify-link "$CAND_APP/public" "$link_id" || fail CANDIDATE_PUBLIC_STORAGE_LINK_CHANGED
fi
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
committed=1
echo 'KMJ_MATERIALIZE_SHARED=PASS'
KMJ_UNPRIVILEGED_MATERIALIZE

# Root wrapper alone may detach and delete candidate-owned rollback objects.
# Python is immutable and embedded in this owner-attested Bash script, never
# loaded from kmjprod-writable candidate checkout.
root_retire() {
  /usr/bin/python3 -I -S - "$CAND_APP" "$LIVE_APP" "$1" "$2" <<'KMJ_ROOT_PROTECTED_RETIRE_PY'
#!/usr/bin/env python3
"""Fail-closed created-inode retirement via a ROOT-ONLY protected quarantine.

Integration candidate for PR #777. A writable candidate directory cannot host
the verified-but-not-yet-unlinked temporary pathname: another kmjprod process
can replace it. Only unlink AFTER atomic rename into a trusted root-only
directory on the SAME filesystem. Never execute this file as root from a
writable source tree; owner installation must pin and attest reviewed bytes.
No network, backup, service, approval, or production-pointer operations.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat

MAX_ENV_BYTES = 1 << 20
INODE = re.compile(r"[1-9][0-9]*:[1-9][0-9]*\Z")
KINDS = {"env": (".env", "f"), "storage": ("storage", "l")}


class Blocked(Exception):
    pass


def _ident(info: os.stat_result) -> str:
    return f"{info.st_dev}:{info.st_ino}"


def _validated_quarantine(qfd: int, source_fd: int, *, trusted_uid: int = 0) -> None:
    """The calling root wrapper must ALSO attest /root and every ancestor."""
    q = os.fstat(qfd)
    source = os.fstat(source_fd)
    if (not stat.S_ISDIR(q.st_mode) or q.st_uid != trusted_uid
            or stat.S_IMODE(q.st_mode) != 0o700
            or q.st_dev != source.st_dev):
        raise Blocked("PRIVATE_QUARANTINE_NOT_TRUSTED_OR_DIFFERENT_FILESYSTEM")


def _source_digest(handle: int) -> tuple[bytes, os.stat_result] | None:
    before = os.fstat(handle)
    if (not stat.S_ISREG(before.st_mode) or before.st_size < 1
            or before.st_size > MAX_ENV_BYTES):
        return None
    digest = hashlib.sha256()
    remaining = MAX_ENV_BYTES + 1
    while remaining > 0:
        data = os.read(handle, min(65536, remaining))
        if not data:
            break
        remaining -= len(data)
        digest.update(data)
    if remaining == 0:
        return None
    after = os.fstat(handle)
    stamp = lambda item: (
        item.st_dev, item.st_ino, item.st_size,
        item.st_mtime_ns, item.st_ctime_ns,
    )
    return (digest.digest(), after) if stamp(before) == stamp(after) else None


def _parked_is_ours(qfd: int, name: str, expected: str, kind: str,
                    live_fd: int | None, *, created_uid: int) -> bool:
    """qfd is protected against unprivileged pathname replacement."""
    try:
        observed = os.stat(name, dir_fd=qfd, follow_symlinks=False)
        if _ident(observed) != expected:
            return False
        if kind == "l":
            if (not stat.S_ISLNK(observed.st_mode)
                    or observed.st_uid != created_uid
                    or observed.st_nlink != 1):
                return False
            if os.readlink(name, dir_fd=qfd) != "../storage/app/public":
                return False
            again = os.stat(name, dir_fd=qfd, follow_symlinks=False)
            return (stat.S_ISLNK(again.st_mode)
                    and _ident(again) == expected
                    and again.st_ctime_ns == observed.st_ctime_ns)
        if kind != "f" or live_fd is None:
            return False
        with_owned = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=qfd)
        try:
            candidate = os.fstat(with_owned)
            if (not stat.S_ISREG(candidate.st_mode)
                    or candidate.st_uid != created_uid
                    or candidate.st_nlink != 1
                    or stat.S_IMODE(candidate.st_mode) != 0o600
                    or _ident(candidate) != expected):
                return False
            content = _source_digest(with_owned)
            source = os.open(".env", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=live_fd)
            try:
                baseline = _source_digest(source)
            finally:
                os.close(source)
            if content is None or baseline is None or content[0] != baseline[0]:
                return False
            fresh = os.stat(name, dir_fd=qfd, follow_symlinks=False)
            return (stat.S_ISREG(fresh.st_mode)
                    and _ident(fresh) == expected
                    and fresh.st_size == candidate.st_size
                    and fresh.st_mtime_ns == candidate.st_mtime_ns
                    and fresh.st_ctime_ns == candidate.st_ctime_ns)
        finally:
            os.close(with_owned)
    except OSError:
        return False


def retire_created(source_fd: int, quarantine_fd: int, *, name: str,
                   expected_inode: str, kind: str, created_uid: int,
                   live_fd: int | None = None, trusted_uid: int = 0) -> str:
    """Root wrapper supplies fixed descriptor-opened candidate and /root qdir.

    The only os.unlink targets the trusted qdir; never the writable candidate.
    If the candidate name swaps before rename, the foreign inode is parked but
    never deleted; owner reviews the protected quarantine manually.
    """
    if (name, kind) not in KINDS.values() or not INODE.fullmatch(expected_inode):
        raise Blocked("UNTRUSTED_FIXED_NAME_OR_INODE")
    _validated_quarantine(quarantine_fd, source_fd, trusted_uid=trusted_uid)
    try:
        initial = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "ABSENT"
    if _ident(initial) != expected_inode:
        return "MISMATCH"
    if kind == "f" and not stat.S_ISREG(initial.st_mode):
        return "MISMATCH"
    if kind == "l" and not stat.S_ISLNK(initial.st_mode):
        return "MISMATCH"
    ticket = "kmj-protected-" + os.urandom(20).hex()
    # O_EXCL semantics: mkdir must create a NEW root-only ticket, and rename
    # never replaces a preexisting user-owned or previous-review object.
    os.mkdir(ticket, mode=0o700, dir_fd=quarantine_fd)
    ticket_fd = os.open(ticket, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=quarantine_fd)
    try:
        _validated_quarantine(ticket_fd, source_fd, trusted_uid=trusted_uid)
        try:
            os.rename(name, "object", src_dir_fd=source_fd, dst_dir_fd=ticket_fd)
        except FileNotFoundError:
            os.rmdir(ticket, dir_fd=quarantine_fd)
            return "ABSENT"
        if not _parked_is_ours(ticket_fd, "object", expected_inode, kind,
                              live_fd, created_uid=created_uid):
            return "QUARANTINED_OWNER_REVIEW"
        try:
            # The only unlink targets an inode under a root-owned private dir.
            os.unlink("object", dir_fd=ticket_fd)
            os.rmdir(ticket, dir_fd=quarantine_fd)
        except OSError:
            return "QUARANTINED_OWNER_REVIEW"
        return "REMOVED"
    finally:
        os.close(ticket_fd)



import pwd, socket, sys

def open_dir(path, *, root_protected=False):
    if not path.startswith("/") or ".." in path.split("/"):
        raise Blocked("BAD_ABSOLUTE_DIRECTORY")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in [part for part in path.split("/") if part]:
            next_fd = os.open(part, flags, dir_fd=fd)
            if root_protected:
                info = os.fstat(next_fd)
                if (info.st_uid != 0 or not stat.S_ISDIR(info.st_mode)
                        or (info.st_mode & 0o022)):
                    os.close(next_fd)
                    raise Blocked("QUARANTINE_ANCESTOR_UNSAFE")
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def run(argv):
    if len(argv) != 5 or os.geteuid() != 0 or socket.gethostname().split(".")[0].lower() != "kmj-elite":
        raise Blocked("ROOT_HOST_OR_ARGS")
    candidate, live, key, inode = argv[1:]
    if key not in ("env", "storage") or not INODE.fullmatch(inode):
        raise Blocked("INVALID_RECEIPT")
    if (not candidate.startswith("/home/kmjprod/releases/platform-")
            or not candidate.endswith("/apps/platform")
            or live == candidate
            or not live.startswith("/home/kmjprod/releases/platform-")
            or not live.endswith("/apps/platform")):
        raise Blocked("RELEASE_PATH_INVALID")
    source_path = candidate if key == "env" else candidate + "/public"
    source = open_dir(source_path)
    live_fd = open_dir(live) if key == "env" else None
    parent = open_dir("/var/lib", root_protected=True)
    try:
        label = "kmj-main-platform-rollback-quarantine"
        try:
            os.mkdir(label, mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
        qfd = os.open(label, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                      dir_fd=parent)
        try:
            name, kind = KINDS[key]
            state = retire_created(source, qfd, name=name, expected_inode=inode,
                                   kind=kind, created_uid=pwd.getpwnam("kmjprod").pw_uid,
                                   live_fd=live_fd, trusted_uid=0)
            print(state)
            return 0 if state == "REMOVED" else 3
        finally:
            os.close(qfd)
    finally:
        os.close(parent)
        if live_fd is not None:
            os.close(live_fd)
        os.close(source)


try:
    raise SystemExit(run(sys.argv))
except (OSError, Blocked, KeyError, ValueError):
    print("BLOCKED_ROOT_OWNER_REVIEW")
    raise SystemExit(3)

KMJ_ROOT_PROTECTED_RETIRE_PY
}

run_sandbox() {
  systemd-run --quiet --wait --pipe --collect \
    --unit="kmj-materialize-$1-$SHORT" \
    -p User=kmjprod -p Group=kmjprod -p UMask=0077 \
    -p ProtectSystem=strict -p ProtectHome=read-only \
    -p PrivateTmp=yes -p NoNewPrivileges=yes \
    -p "ReadWritePaths=$CAND" -p "ReadOnlyPaths=$LIVE_APP" \
    /bin/bash -s -- "$SHA" "$EXPECTED_CURRENT" "$ROOT" "$LIVE" "$CAND" "$ORIGIN_LINE" "${@:2}" <<<"$SANDBOX_BODY"
}
# No temporary receipt file: output is held in memory, so there is no pathname
# for a hostile TMPDIR or a swapped symlink to redirect a root write.
sandbox_text=""
# A completed materializer must emit exactly one env inode receipt and either
# one matching link receipt or an explicit NOT_PRESENT_LIVE link outcome.
# A partial stdout transcript (e.g. SIGKILL between symlinkat and echo) is not
# a reliable account of what was created; never infer full cleanup from it.
receipt_contract_ok() {
  local env_count link_count mirrored absent env_id link_id line
  env_count="$(grep -c '^MATERIALIZED_ENV_ID=' <<<"$sandbox_text" || true)"
  link_count="$(grep -c '^MATERIALIZED_LINK_ID=' <<<"$sandbox_text" || true)"
  mirrored="$(grep -Fxc 'PUBLIC_STORAGE_LINK=MIRRORED' <<<"$sandbox_text" || true)"
  absent="$(grep -Fxc 'PUBLIC_STORAGE_LINK=NOT_PRESENT_LIVE' <<<"$sandbox_text" || true)"
  [[ "$env_count" == 1 && "$link_count" =~ ^[01]$ ]] || return 1
  [[ "$mirrored" == 1 && "$absent" == 0 && "$link_count" == 1 ||
     "$mirrored" == 0 && "$absent" == 1 && "$link_count" == 0 ]] || return 1
  while IFS= read -r line; do
    case "$line" in
      MATERIALIZED_ENV_ID=*) [[ "$line" =~ ^MATERIALIZED_ENV_ID=[0-9]+:[0-9]+$ ]] || return 1 ;;
      MATERIALIZED_LINK_ID=*) [[ "$line" =~ ^MATERIALIZED_LINK_ID=[0-9]+:[0-9]+$ ]] || return 1 ;;
    esac
  done <<<"$sandbox_text"
  env_id="$(sed -n 's/^MATERIALIZED_ENV_ID=\([0-9][0-9]*:[0-9][0-9]*\)$/\1/p' <<<"$sandbox_text")"
  link_id="$(sed -n 's/^MATERIALIZED_LINK_ID=\([0-9][0-9]*:[0-9][0-9]*\)$/\1/p' <<<"$sandbox_text")"
  [[ "$env_id" =~ ^[0-9]+:[0-9]+$ ]] || return 1
  [[ "$link_count" == 0 || "$link_id" =~ ^[0-9]+:[0-9]+$ ]] || return 1
  [[ "$sandbox_rc" == 0 ]] || return 1
  [[ "$(grep -Fxc 'KMJ_MATERIALIZE_SHARED=PASS' <<<"$sandbox_text" || true)" == 1 ]] || return 1
}
# The unprivileged sandbox can never certify cleanup. Only the actual
# protected root helper receipt may be used, with no ABSENT success credit.

post_fail() {
  local env_id="" link_id="" env_count link_count receipt_invalid=0 cleanup_rc=0 rollback_text=""
  # Count *all* raw receipt declarations; never choose the last of several.
  env_count="$(grep -c '^MATERIALIZED_ENV_ID=' <<<"$sandbox_text" || true)"
  link_count="$(grep -c '^MATERIALIZED_LINK_ID=' <<<"$sandbox_text" || true)"
  [[ "$env_count" =~ ^[01]$ && "$link_count" =~ ^[01]$ ]] || receipt_invalid=1
  if [[ "$env_count" == 1 ]]; then
    env_id="$(sed -n 's/^MATERIALIZED_ENV_ID=\([0-9][0-9]*:[0-9][0-9]*\)$/\1/p' <<<"$sandbox_text")"
    [[ "$env_id" =~ ^[0-9]+:[0-9]+$ ]] || receipt_invalid=1
  fi
  if [[ "$link_count" == 1 ]]; then
    link_id="$(sed -n 's/^MATERIALIZED_LINK_ID=\([0-9][0-9]*:[0-9][0-9]*\)$/\1/p' <<<"$sandbox_text")"
    [[ "$link_id" =~ ^[0-9]+:[0-9]+$ ]] || receipt_invalid=1
  fi
  receipt_contract_ok || receipt_invalid=1
  # Only root may retire the known inodes. A failed sandbox can no longer
  # unlink through its writable candidate directory. If a receipt is absent,
  # clean only proven inodes and retain FAILED_REVIEW for owner inspection.
  if [[ "$env_count" =~ ^[01]$ && "$link_count" =~ ^[01]$ ]]; then
    if [[ -n "$link_id" ]]; then
      link_state="$(root_retire storage "$link_id")" || cleanup_rc=1
      status ROLLBACK_STORAGE "$link_state"
    fi
    if [[ -n "$env_id" ]]; then
      env_state="$(root_retire env "$env_id")" || cleanup_rc=1
      status ROLLBACK_ENV "$env_state"
    fi
  else
    cleanup_rc=1
  fi
  if [[ "$receipt_invalid" == 0 && "$cleanup_rc" == 0 ]]; then
    status CANDIDATE_ROLLBACK DONE
  else
    status CANDIDATE_ROLLBACK FAILED_REVIEW
  fi
  fail "$1"
}

sandbox_rc=0
sandbox_text="$(run_sandbox materialize materialize)" || sandbox_rc=$?
# Child rollback messages are not authoritative. A TERM/SIGKILL receipt window
# can leave an unreported link while the child prints ROLLBACK=DONE for only
# the known env inode. Never forward that premature success to receipt parsers.
# Only the root wrapper may publish the final rollback verdict after validating
# the complete sandbox receipt contract and any best-effort cleanup.
while IFS= read -r line; do
  case "$line" in
    CANDIDATE_ROLLBACK=*) continue ;;
  esac
  printf '%s\n' "$line"
done <<<"$sandbox_text"
[[ "$sandbox_rc" == 0 ]] || post_fail "SANDBOX_FAILED_$sandbox_rc"
grep -Fxq 'KMJ_MATERIALIZE_SHARED=PASS' <<<"$sandbox_text" || post_fail SANDBOX_PASS_MISSING
receipt_contract_ok || post_fail SANDBOX_RECEIPTS_UNVERIFIED
# A SIGKILL between detach and unlink/restore strands a quarantined object.
shopt -s nullglob
detach_leftovers=("$CAND_APP"/.kmj-detach-* "$CAND_APP/public"/.kmj-detach-*)
shopt -u nullglob
[[ ${#detach_leftovers[@]} -eq 0 ]] || post_fail DETACH_LEFTOVER_REVIEW

runuser -u www-data -- test -r "$CAND_APP/public/index.php" || post_fail NGINX_PUBLIC_UNREADABLE
runuser -u www-data -- test -r "$CAND_APP/public/assets/kmj-codebridge-icon.png" || post_fail NGINX_ICON_UNREADABLE
runuser -u www-data -- test ! -r "$CAND_APP/.env" || post_fail NGINX_PRIVATE_ENV_EXPOSED
status NGINX_PUBLIC_ACL PASS
status NGINX_PRIVATE_ENV DENIED
echo "KMJ_MATERIALIZE=PASS"
