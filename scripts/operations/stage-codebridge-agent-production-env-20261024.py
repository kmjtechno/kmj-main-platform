#!/usr/bin/env python3
"""Fail-closed candidate-only secret-preserving KMJ public agent origin staging.

Operator must review pinned source, archive/witness and approve. No live edits,
no database queries, no network calls, no production cutover, no secrets printed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

BASE = Path("/home/kmjprod")
CURRENT = BASE / "current"
SHA = "b1d672bbc83a51ca3f8271435692825072444c8e"
OLD = "platform-8070dad72c55"
CANDIDATE = BASE / "releases" / ("platform-" + SHA[:12])
ARCHIVE = Path("/var/backups/kmj-platform") / ("pre-deploy-" + SHA[:12] + ".tar.gz")
WITNESS = ARCHIVE.with_suffix("").with_suffix(".json")
ORIGIN_LINE = "CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com"


def fail(code):
    raise RuntimeError(code)


def secure_file(path, root_only=False):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022:
        fail("UNSAFE_FILE")
    if root_only and (info.st_uid != 0 or info.st_mode & 0o077):
        fail("BACKUP_PERMISSIONS_UNSAFE")
    return info


def pin_public_origin(original):
    """Preserve every existing byte except necessary terminal newline + new key."""
    try:
        contents = original.decode("utf-8")
    except UnicodeError:
        fail("LIVE_DOTENV_NOT_UTF8")
    if "\x00" in contents or "\r" in contents or len(original) > 524288:
        fail("LIVE_DOTENV_FORMAT_UNSUPPORTED")
    lines = contents.splitlines()
    seen = [line for line in lines if re.match(r"^\s*CODEBRIDGE_AGENT_PUBLIC_URL\s*=", line)]
    if len(seen) > 1:
        fail("DUPLICATE_PUBLIC_AGENT_ORIGIN")
    if seen:
        if seen[0].strip() != ORIGIN_LINE:
            fail("PUBLIC_AGENT_ORIGIN_CONFLICT")
        return original
    separator = "" if not original or original.endswith(b"\n") else "\n"
    return original + (separator + ORIGIN_LINE + "\n").encode("utf-8")


def check_backup():
    secure_file(ARCHIVE, root_only=True)
    secure_file(WITNESS, root_only=True)
    if WITNESS.stat().st_size > 4096:
        fail("BACKUP_WITNESS_TOO_LARGE")
    data = json.loads(WITNESS.read_text("utf-8"))
    if not isinstance(data, dict) or set(data) != {"approvedSha", "currentRelease", "backupSha256"}:
        fail("BACKUP_WITNESS_FIELDS")
    if data["approvedSha"] != SHA or data["currentRelease"] != OLD:
        fail("BACKUP_WITNESS_IDENTITY")
    digest = data["backupSha256"]
    if not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest):
        fail("BACKUP_WITNESS_DIGEST_FORMAT")
    h = hashlib.sha256()
    with ARCHIVE.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != digest:
        fail("BACKUP_WITNESS_DIGEST_MISMATCH")


def read_candidate_head():
    result = subprocess.run(
        ["runuser", "-u", "kmjprod", "--", "git", "-C", str(CANDIDATE),
         "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    if result.stdout.strip() != SHA:
        fail("CANDIDATE_SHA_MISMATCH")
    state = subprocess.run(
        ["runuser", "-u", "kmjprod", "--", "git", "-C", str(CANDIDATE),
         "status", "--porcelain", "--untracked-files=normal"],
        capture_output=True, text=True, check=True
    )
    if state.stdout.strip():
        fail("CANDIDATE_DIRTY")


def main():
    os.umask(0o077)
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "KMJ-elite":
        fail("WRONG_OPERATOR_OR_HOST")
    if not CURRENT.is_symlink() or CURRENT.resolve() != BASE / "releases" / OLD:
        fail("CURRENT_RELEASE_CHANGED")
    if not (CANDIDATE / ".git").is_dir() or CANDIDATE.is_symlink():
        fail("CANDIDATE_NOT_STAGED")
    read_candidate_head()
    if (CANDIDATE / "apps/platform/bootstrap/cache/config.php").exists():
        fail("CANDIDATE_ALREADY_CACHED")
    live_env = CURRENT / "apps/platform/.env"
    dest = CANDIDATE / "apps/platform/.env"
    if live_env.is_symlink() or dest.exists() or dest.is_symlink():
        fail("ENV_SOURCE_LINK_OR_CANDIDATE_PRESENT")
    metadata = secure_file(live_env)
    if metadata.st_mode & 0o007:
        fail("LIVE_DOTENV_WORLD_ACCESSIBLE")
    source_bytes = live_env.read_bytes()
    configured_bytes = pin_public_origin(source_bytes)
    check_backup()
    print("CANDIDATE_SHA=PASS", flush=True)
    print("EXACT_BACKUP_WITNESS=PASS", flush=True)
    print("LIVE_ENV_SOURCE=VALIDATED_SECRET_NOT_PRINTED", flush=True)

    # Exclusive creation protects an existing candidate config against overwrite.
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, metadata.st_uid, metadata.st_gid)
        os.fchmod(fd, metadata.st_mode & 0o600)  # no other users gain read access
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(configured_bytes)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if fd >= 0:
            os.close(fd)
        dest.unlink(missing_ok=True)
        raise

    if CURRENT.resolve() != BASE / "releases" / OLD:
        fail("CURRENT_RELEASE_CHANGED_REVIEW_CANDIDATE_CONFIG")
    print("CANDIDATE_ENV=STAGED_PROTECTED", flush=True)
    print("PUBLIC_AGENT_ORIGIN=PINNED_CANONICAL", flush=True)
    print("LIVE_ENV=UNCHANGED", flush=True)
    print("LIVE_POINTER=UNCHANGED", flush=True)
    print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED", flush=True)
    print("ROLLBACK_DRILL=NOT_VERIFIED_BY_THIS_SCRIPT", flush=True)
    print("OFFSITE_INDEPENDENT_RESTORE=NOT_VERIFIED_BY_THIS_SCRIPT", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        label = str(exc)
        if re.fullmatch("[A-Z_]{3,100}", label) is None:
            label = "CANDIDATE_CONFIG_BLOCKED"
        print("CANDIDATE_CONFIG=BLOCKED " + label, file=sys.stderr)
        sys.exit(2)
