#!/usr/bin/env python3
"""Prepare an exact-SHA, detached Main Platform CI lane without touching the shared checkout.

A source-only developer helper, NOT a deployment/backup/approval gate. Run as a nonroot
trusted repository operator. With --fetch, only the canonical GitHub HTTPS origin is
accepted and a private cache ref is updated; origin/main and the shared working tree
are never checked out, reset, cleaned, or merged. A missing or stale exact SHA fails
closed. Never reuses/removes an existing lane, even if its checkout is clean.
"""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
LANE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")
ALLOWED_ORIGINS = frozenset({
    "https://github.com/kmjtechno/kmj-main-platform",
    "https://github.com/kmjtechno/kmj-main-platform.git",
})
CACHE_REF = "refs/kmj-fresh-main-cache/main"


class Blocked(Exception):
    pass


def git(repo: Path, *args: str, extra_config=()):
    cmd = ["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
           "-c", "credential.helper=", *extra_config, "-C", str(repo), *args]
    # Ignore inherited Git overrides (GIT_DIR, config injection, SSH helpers, etc.).
    # Only the authorized repository-local config is consulted.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(PATH="/usr/bin:/bin", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False, timeout=180)
    if result.returncode:
        raise Blocked("GIT_COMMAND_FAILED")
    return result.stdout.strip()


def verify_private_directory(path: Path, *, create: bool):
    """Only use a non-symlink directory owned by the caller and mode 0700."""
    try:
        st = path.lstat()
    except FileNotFoundError:
        if not create:
            raise Blocked("CACHE_DIRECTORY_MISSING")
        try:
            path.mkdir(mode=0o700)
        except OSError:
            raise Blocked("CACHE_DIRECTORY_CREATE_FAILED") from None
        st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or (stat.S_IMODE(st.st_mode) != 0o700):
        raise Blocked("CACHE_DIRECTORY_UNSAFE")


def verify_git_config(repo: Path):
    """Reject local Git settings that can redirect HTTPS or execute hooks/filters.

    A canonical remote.origin.url alone is insufficient: url.*.insteadOf can
    transparently rewrite it to another HTTPS host. Read local configuration
    (including local includes) before status/fetch/worktree operations.
    """
    config = git(repo, "config", "--local", "--list", "--includes")
    for item in config.splitlines():
        key = item.partition("=")[0].lower()
        unsafe = (
            (key.startswith("url.") and key.endswith(".insteadof"))
            or key.startswith(("include.", "includeif."))
            or key in {"remote.origin.vcs", "remote.origin.uploadpack",
                       "remote.origin.proxy", "core.fsmonitor",
                       "credential.helper", "http.extraheader"}
            or (key.startswith("http.") and key.endswith(".extraheader"))
            or (key.startswith("filter.") and key.endswith((".smudge", ".process")))
        )
        if unsafe:
            raise Blocked("GIT_LOCAL_CONFIG_UNSAFE")


def prepare(repo: Path, expected: str, lane: str, *, fetch: bool):
    if os.geteuid() == 0:
        raise Blocked("ROOT_NOT_ALLOWED")
    if not SHA.fullmatch(expected) or not LANE.fullmatch(lane):
        raise Blocked("INVALID_ARGUMENT")
    if not repo.is_dir() or repo.is_symlink():
        raise Blocked("REPOSITORY_PATH_UNSAFE")
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo.resolve():
        raise Blocked("REPOSITORY_ROOT_MISMATCH")
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if not common.is_dir() or common.is_symlink() or common.resolve() != common:
        raise Blocked("GIT_COMMON_DIR_UNSAFE")
    if common.stat().st_uid != os.geteuid():
        raise Blocked("GIT_COMMON_DIR_OWNER")
    verify_git_config(repo)
    before = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    cache = common / "kmj-fresh-main-lanes"
    # Trusted repository-operator state, never a root/system directory.
    verify_private_directory(cache, create=True)
    target = cache / lane
    if target.exists() or target.is_symlink():
        raise Blocked("LANE_ALREADY_EXISTS")
    if fetch:
        origin = git(repo, "config", "--get-all", "remote.origin.url")
        if origin not in ALLOWED_ORIGINS:
            raise Blocked("ORIGIN_NOT_CANONICAL_HTTPS")
        # HTTPS-only, no implicit SSH, tags or submodules.
        # --refmap= avoids updating origin/main; only a private cache ref moves.
        git(repo, "fetch", "--no-tags", "--no-recurse-submodules", "--refmap=",
            "origin", f"refs/heads/main:{CACHE_REF}",
            extra_config=("-c", "protocol.allow=never", "-c", "protocol.https.allow=always"))
        observed = git(repo, "rev-parse", "--verify", CACHE_REF)
    else:
        # Offline mode: no claim of a fresh remote read.
        observed = git(repo, "rev-parse", "--verify", "refs/remotes/origin/main")
    if observed != expected:
        raise Blocked("REMOTE_MAIN_SHA_MISMATCH")
    git(repo, "cat-file", "-e", expected + "^{commit}")
    # No --force, --prune, --clean, reset, or deletion of preexisting paths.
    # Checkout hooks disabled; filters still require a trusted repository.
    git(repo, "worktree", "add", "--detach", "--", str(target), expected,
        extra_config=("-c", "core.hooksPath=/dev/null"))
    actual = git(target, "rev-parse", "HEAD")
    if actual != expected:
        raise Blocked("NEW_WORKTREE_SHA_MISMATCH")
    if git(target, "status", "--porcelain=v1", "--untracked-files=all"):
        raise Blocked("NEW_WORKTREE_DIRTY")
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all") != before:
        raise Blocked("SHARED_CHECKOUT_CHANGED")
    return {"status": "PREPARED_SOURCE_ONLY", "expectedSha": expected,
            "actualSha": actual, "lane": lane, "path": str(target),
            "remoteRefreshed": fetch, "sharedCheckoutPreserved": True,
            "productionReleaseAttested": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--fetch", action="store_true", help="HTTPS-only remote refresh (default: cached-only)")
    args = parser.parse_args(argv)
    try:
        result = prepare(args.repo, args.expected_main_sha, args.lane, fetch=args.fetch)
    except (Blocked, OSError) as exc:
        code = str(exc) if isinstance(exc, Blocked) else "IO_ERROR"
        print(json.dumps({"status": "BLOCKED", "reason": code, "productionReleaseAttested": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
