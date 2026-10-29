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
for cmd in git runuser install cp find awk sha256sum flock python3 systemd-run; do
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

# Root holds the release lock while a private mount namespace pins writable
# candidate storage. Live runtime and all other host paths stay read-only even
# if kmjprod replaces a candidate parent with a symlink during the copy.
systemd-run --quiet --wait --pipe --collect \
  --unit="kmj-materialize-$SHORT" \
  -p User=kmjprod -p Group=kmjprod -p UMask=0077 \
  -p ProtectSystem=strict -p ProtectHome=read-only \
  -p PrivateTmp=yes -p NoNewPrivileges=yes \
  -p "ReadWritePaths=$CAND_APP" -p "ReadOnlyPaths=$LIVE_APP" \
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
# Inlined verify-main-platform-storage-manifest.py.
# Embedded in the independently pinned operator script; never execute candidate code as root.
storage_manifest() {
  /usr/bin/python3 -I -S - "$1" <<'KMJ_STORAGE_MANIFEST_PY'
#!/usr/bin/env python3
"""Fail-closed, no-dereference storage inventory for exact release materialization.

Prints a deterministic manifest digest of regular-file bytes, metadata, paths,
and raw symlink targets. Does NOT attest linked target bytes, writer quiescence,
or independent offsite restore. Ignores only regular .gitignore placeholders.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


def inventory(root: Path) -> dict[str, object]:
    root = Path(root)
    root_stat = os.lstat(root)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError("STORAGE_ROOT_NOT_REAL_DIRECTORY")

    entries: list[list[object]] = []
    counts = {"regular": 0, "symlinks": 0, "directories": 0}

    def visit(directory: Path, prefix: str) -> None:
        before = os.lstat(directory)
        if not stat.S_ISDIR(before.st_mode):
            raise ValueError("DIRECTORY_REPLACED")
        with os.scandir(directory) as scan:
            children = sorted(scan, key=lambda item: item.name)
        for child in children:
            path = directory / child.name
            relative = f"{prefix}/{child.name}" if prefix else child.name
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                entries.append(["d", relative])
                counts["directories"] += 1
                visit(path, relative)
            elif stat.S_ISREG(info.st_mode):
                if child.name == ".gitignore":
                    continue
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(path, flags)
                try:
                    opened = os.fstat(fd)
                    if not stat.S_ISREG(opened.st_mode) or (
                        opened.st_dev, opened.st_ino
                    ) != (info.st_dev, info.st_ino):
                        raise ValueError("FILE_REPLACED_DURING_SCAN")
                    digest = hashlib.sha256()
                    while chunk := os.read(fd, 1024 * 1024):
                        digest.update(chunk)
                    after = os.fstat(fd)
                    now = os.lstat(path)
                    if (opened.st_dev, opened.st_ino, opened.st_size,
                        opened.st_mtime_ns, opened.st_ctime_ns) != (
                        after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns
                    ) or (now.st_dev, now.st_ino) != (opened.st_dev, opened.st_ino):
                        raise ValueError("FILE_CHANGED_DURING_SCAN")
                finally:
                    os.close(fd)
                entries.append(["f", relative, opened.st_size, digest.hexdigest(),
                                stat.S_IMODE(opened.st_mode), opened.st_uid,
                                opened.st_gid, opened.st_mtime_ns])
                counts["regular"] += 1
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                now = os.lstat(path)
                if (info.st_dev, info.st_ino, info.st_mtime_ns) != (
                    now.st_dev, now.st_ino, now.st_mtime_ns
                ):
                    raise ValueError("SYMLINK_CHANGED_DURING_SCAN")
                entries.append(["l", relative, target, info.st_uid, info.st_gid,
                                info.st_mtime_ns])
                counts["symlinks"] += 1
            else:
                raise ValueError("UNSUPPORTED_STORAGE_ENTRY")
        after = os.lstat(directory)
        if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_mtime_ns
        ):
            raise ValueError("DIRECTORY_CHANGED_DURING_SCAN")

    visit(root, "")
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
[[ -d "$CAND_APP/storage/app" && ! -L "$CAND_APP/storage/app" ]] || fail CANDIDATE_STORAGE_UNSAFE
source_before="$(storage_manifest "$LIVE_APP/storage/app")" || fail SOURCE_STORAGE_SCAN_FAILED
cp -a --no-clobber -- "$LIVE_APP/storage/app/." "$CAND_APP/storage/app/"
source_after="$(storage_manifest "$LIVE_APP/storage/app")" || fail SOURCE_STORAGE_RESCAN_FAILED
candidate_after="$(storage_manifest "$CAND_APP/storage/app")" || fail CANDIDATE_STORAGE_SCAN_FAILED
[[ "$source_before" == "$source_after" ]] || fail SOURCE_STORAGE_CHANGED_DURING_COPY
[[ "$source_after" == "$candidate_after" ]] || fail STORAGE_PARITY_MISMATCH
count="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["regular"])' "$candidate_after")"
links="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["symlinks"])' "$candidate_after")"
digest="$(/usr/bin/python3 -I -S -c 'import json,sys; print(json.loads(sys.argv[1])["sha256"])' "$candidate_after")"
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
  ln -s ../storage/app/public "$CAND_APP/public/storage"
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

KMJ_UNPRIVILEGED_MATERIALIZE
