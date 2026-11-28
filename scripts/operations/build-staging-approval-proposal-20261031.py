#!/usr/bin/env python3
"""Read-only: print a staging-approval PROPOSAL bound to the committed runner/unit bytes.

It never writes to /etc, never installs a unit and never sets a verification flag to true: the four
*Verified fields are emitted as false, so the Supervisor rejects the proposal until the OWNER has
independently proven each one and edits the root-protected file by hand.
"""
import argparse
import hashlib
import json
import os
import socket
import stat
import subprocess
import re
import sys
from pathlib import Path

def repository_inputs():
    """Resolve checkout paths only in offline mode; Elite mode is standalone."""
    parents = Path(__file__).resolve().parents
    if len(parents) < 3:
        raise SystemExit("BLOCKED_OFFLINE_CHECKOUT_REQUIRED")
    root = parents[2]
    runner = root / "deploy/staging/kmj-main-platform-staging-deploy.sh"
    unit = root / "deploy/staging/kmj-main-platform-staging-deploy.service"
    if not runner.is_file() or not unit.is_file():
        raise SystemExit("BLOCKED_OFFLINE_CHECKOUT_REQUIRED")
    return runner.read_bytes(), unit.read_bytes()


SHA = re.compile(r"[a-f0-9]{40}\Z")
RELEASE = re.compile(r"[a-z0-9][a-z0-9_-]{3,100}\Z")


ELITE_RUNNER = Path("/usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh")
ELITE_UNIT = Path("/etc/systemd/system/kmj-main-platform-staging-deploy.service")
RUNNER_BLOB = "2fa8ef2631f48b4fd902e644cd2f7948615ffc55"
UNIT_BLOB = "07d77b4e2ec9b2e3cd73d4a8aa4c4786e5927eb1"
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD = Path("/home/kmjprod/current")
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin", "HOME": "/root",
       "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_TERMINAL_PROMPT": "0"}


def require(ok, label):
    if not ok:
        raise SystemExit("BLOCKED_" + label)


def pinned_bytes(path, pin):
    for parent in path.parents:
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "INSTALLED_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        s = os.fstat(handle.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                and not s.st_mode & 0o022 and 0 < s.st_size <= 100000,
                "INSTALLED_FILE")
        raw = handle.read(100001)
        after = os.fstat(handle.fileno())
        require(len(raw) == s.st_size and (s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "INSTALLED_RACE")
    obj = b"blob " + str(len(raw)).encode() + b"\0" + raw
    require(hashlib.sha1(obj).hexdigest() == pin, "INSTALLED_SOURCE_PIN")
    return raw


def remote_approved():
    out = subprocess.run(["/usr/bin/git", "-c", "core.hooksPath=/dev/null",
                          "ls-remote", "--exit-code", REMOTE, "refs/heads/staging-approved"],
                         env=ENV, cwd="/root", capture_output=True, text=True,
                         timeout=30, check=True).stdout.split()
    require(len(out) == 2 and SHA.fullmatch(out[0]) and
            out[1] == "refs/heads/staging-approved", "REMOTE_REF")
    return out[0]


def exact_pointer(path, target):
    # Staging remains absolute (the guarded runner's contract). Production
    # supports exactly its canonical absolute or releases/platform-... link.
    try:
        allowed = {str(target)}
        if path == PROD:
            allowed.add("releases/" + target.name)
        if not path.is_symlink() or not target.is_dir() or target.is_symlink():
            return False
        raw = os.readlink(path)
        return (raw in allowed and path.resolve(strict=True) == target
                and os.readlink(path) == raw)
    except (OSError, RuntimeError):
        return False


def verify_live_inputs(approved, expected_current, production_release):
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "ELITE_ROOT")
    require(re.fullmatch(r"platform-[a-f0-9]{12}", production_release), "LIVE_RELEASE_FORMAT")
    stage_target = Path("/home/kmjstage/releases") / expected_current / "apps/platform"
    prod_target = Path("/home/kmjprod/releases") / production_release
    require(exact_pointer(STAGE, stage_target), "STAGE_POINTER_DRIFT")
    require(exact_pointer(PROD, prod_target), "PRODUCTION_POINTER_DRIFT")
    require(remote_approved() == approved, "REMOTE_APPROVED_SHA_DRIFT")
    runner = pinned_bytes(ELITE_RUNNER, RUNNER_BLOB)
    unit = pinned_bytes(ELITE_UNIT, UNIT_BLOB)
    require(exact_pointer(STAGE, stage_target) and exact_pointer(PROD, prod_target),
            "POINTER_DRIFT_DURING_INSPECTION")
    require(remote_approved() == approved, "REMOTE_APPROVED_SHA_DRIFT")
    return runner, unit


def proposal(approved, expected_current, production_release, *, inspect_elite=False):
    if not SHA.match(approved) or not SHA.match(expected_current) or approved == expected_current:
        raise SystemExit("BLOCKED_SHA")
    if not RELEASE.match(production_release):
        raise SystemExit("BLOCKED_PRODUCTION_RELEASE")
    runner, unit = (verify_live_inputs(approved, expected_current, production_release)
                    if inspect_elite else repository_inputs())
    return {
        "schema": "kmj.main-platform.staging-approval.v1",
        "approvedSha": approved,
        "expectedCurrentSha": expected_current,
        "expectedProductionRelease": production_release,
        "runnerSha256": hashlib.sha256(runner).hexdigest(),
        "unitSha256": hashlib.sha256(unit).hexdigest(),
        "backupVerified": False,
        "rollbackVerified": False,
        "storageVerified": False,
        "zeroAdditionalCostVerified": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-sha", required=True)
    p.add_argument("--expected-current-sha", required=True)
    p.add_argument("--expected-production-release", required=True)
    p.add_argument("--inspect-elite", action="store_true",
                   help="read-only exact live pointer, remote staging ref and installed source pins; flags remain false")
    a = p.parse_args(argv)
    try:
        result = proposal(a.approved_sha, a.expected_current_sha, a.expected_production_release,
                          inspect_elite=a.inspect_elite)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise SystemExit("BLOCKED_READ_ONLY_INSPECTION") from None
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
