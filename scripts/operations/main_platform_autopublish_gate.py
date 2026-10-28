#!/usr/bin/env python3
"""Guarded unattended release activation of *previously owner-approved* versions.

The owner creates per-release, root-protected approval AND independent acceptance
evidence. This automation never manufactures approval or releases new code.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
RELEASE_RE = re.compile(r"platform-[0-9a-f]{12}\Z")
APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
ADMISSION_DIR = Path("/etc/kmj-codebridge")
LIVE = Path("/home/kmjprod/current")
RELEASES = Path("/home/kmjprod/releases")
LOCK = Path("/run/lock/kmj-main-platform-autopublish.lock")
UNIT = "kmj-main-platform-production-release.service"
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
URL = "https://kmjtechno.com/login"
ACCEPTANCE_KEYS = (
    "ownerAuthenticatedQaPass",
    "stagingExactShaPass",
    "independentOffsiteRestorePass",
    "rollbackRehearsalPass",
    "migrationAndStorageContinuityPass",
    "publicOriginQaPass",
)
APPROVAL_KEYS = {"approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"}
ADMISSION_KEYS = {
    "schema", "approvedSha", "expectedCurrentRelease", "stagingSha",
    "standingOwnerAuthorization", *ACCEPTANCE_KEYS,
}

def decision(approval, admission, current_release, approved_remote_sha, candidate_sha):
    """Pure fail-closed gate. Tests exercise all boundary conditions."""
    if not isinstance(approval, dict) or set(approval) != APPROVAL_KEYS:
        return "BLOCKED_APPROVAL_SCHEMA"
    sha = approval.get("approvedSha")
    expected = approval.get("expectedCurrentRelease")
    if (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
            or not isinstance(expected, str) or not RELEASE_RE.fullmatch(expected)
            or approval.get("backupVerified") is not True
            or approval.get("rollbackVerified") is not True):
        return "BLOCKED_PROTECTED_APPROVAL"
    if current_release != expected and current_release != "platform-" + sha[:12]:
        return "BLOCKED_CURRENT_RELEASE_DRIFT"
    if approved_remote_sha != sha:
        return "BLOCKED_STAGING_APPROVAL_DRIFT"
    if candidate_sha != sha:
        return "BLOCKED_CANDIDATE_IDENTITY"
    if not isinstance(admission, dict) or set(admission) != ADMISSION_KEYS:
        return "BLOCKED_ACCEPTANCE_SCHEMA"
    if (admission.get("schema") != "kmj.autopublish.release-admission.v1"
            or admission.get("approvedSha") != sha
            or admission.get("expectedCurrentRelease") != expected
            or admission.get("stagingSha") != sha):
        return "BLOCKED_ACCEPTANCE_IDENTITY"
    if admission.get("standingOwnerAuthorization") is not True:
        return "BLOCKED_OWNER_AUTHORIZATION"
    if any(admission.get(key) is not True for key in ACCEPTANCE_KEYS):
        return "BLOCKED_ACCEPTANCE_EVIDENCE"
    if current_release == "platform-" + sha[:12]:
        return "ALREADY_LIVE"
    return "READY_APPROVED_RELEASE"

def protected_json(path):
    """Read one root-protected inode, never a re-resolved path after lstat."""
    try:
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
                or (stat.S_IMODE(parent.st_mode) & 0o022)):
            return None
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or info.st_nlink != 1
                    or (stat.S_IMODE(info.st_mode) & 0o077)
                    or not 2 <= info.st_size <= 4096):
                return None
            data = os.read(fd, 4097)
            after = os.fstat(fd)
            if (len(data) != info.st_size or after.st_size != info.st_size
                    or after.st_mtime_ns != info.st_mtime_ns):
                return None
            return json.loads(data)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError):
        return None

def fixed_run(argv, timeout=15, return_success=False):
    try:
        p = subprocess.run(
            argv, cwd="/", env={
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/root", "LANG": "C", "GIT_TERMINAL_PROMPT": "0",
            },
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, check=False, timeout=timeout,
        )
        if return_success:
            return p.returncode == 0
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return False if return_success else ""

def live_release():
    if not LIVE.is_symlink():
        return ""
    try:
        target = LIVE.resolve(strict=True)
        if target.parent != RELEASES or not RELEASE_RE.fullmatch(target.name):
            return ""
        return target.name
    except OSError:
        return ""

def remote_sha():
    output = fixed_run(["/usr/bin/git", "ls-remote", "--exit-code", REMOTE,
                        "refs/heads/staging-approved"], timeout=18)
    parts = output.split()
    return parts[0] if len(parts) == 2 and parts[1] == "refs/heads/staging-approved" and SHA_RE.fullmatch(parts[0]) else ""

def candidate_sha(target):
    folder = RELEASES / ("platform-" + target[:12])
    if folder.is_symlink() or not folder.is_dir():
        return ""
    result = fixed_run(["/usr/sbin/runuser", "-u", "kmjprod", "--",
                        "/usr/bin/git", "-C", str(folder), "rev-parse", "--verify", "HEAD"])
    return result if SHA_RE.fullmatch(result) else ""

def exact_https_sha_ok(response, target):
    """Require one HTTP 200 response and one matching public deploy SHA."""
    if not SHA_RE.fullmatch(target) or not isinstance(response, str):
        return False
    lines = response.splitlines()
    if not lines or lines[-1] != "KMJ_HTTP_STATUS=200":
        return False
    statuses = [line for line in lines if line.startswith("HTTP/")]
    if len(statuses) != 1 or not re.fullmatch(
            r"HTTP/(?:1[.]0|1[.]1|2|3) 200(?: .*)?", statuses[0]):
        return False
    values = [line.split(":", 1)[1].strip() for line in lines
              if line.lower().startswith("x-kmj-deploy-sha:")]
    return values == [target]

def public_https_response():
    """Read only the canonical public origin, with no redirects or shell."""
    return fixed_run([
        "/usr/bin/curl", "--proto", "=https", "--silent",
        "--show-error", "--connect-timeout", "5", "--max-time", "18",
        "--max-redirs", "0", "--dump-header", "-",
        "--output", "/dev/null", "--write-out",
        "KMJ_HTTP_STATUS=%{http_code}", URL,
    ], timeout=23)

def run(mode):
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("KMJ_AUTOPUBLISH=BLOCKED_OPERATOR_HOST")
        return 2
    # /run/lock can be writable to less-privileged users: never follow links.
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(LOCK, flags, 0o600)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            os.close(fd)
            print("KMJ_AUTOPUBLISH=BLOCKED_LOCK_IDENTITY")
            return 2
    except OSError:
        print("KMJ_AUTOPUBLISH=BLOCKED_LOCK_SAFETY")
        return 2
    with os.fdopen(fd, "r+", encoding="ascii") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("KMJ_AUTOPUBLISH=BLOCKED_CONCURRENT_RUN")
            return 2
        approval = protected_json(APPROVAL)
        target = approval.get("approvedSha", "") if isinstance(approval, dict) else ""
        admissible = bool(SHA_RE.fullmatch(target))
        admission = protected_json(
            ADMISSION_DIR / ("main-platform-autopublish-" + target[:12] + ".json")
        ) if admissible else None
        current = live_release()
        remote = remote_sha() if admissible else ""
        candidate = candidate_sha(target) if admissible else ""
        result = decision(approval, admission, current, remote, candidate)
        print("KMJ_AUTOPUBLISH=" + result)
        if result == "ALREADY_LIVE":
            if not exact_https_sha_ok(public_https_response(), target):
                print("KMJ_AUTOPUBLISH=BLOCKED_ALREADY_LIVE_HEALTH")
                return 2
            print("KMJ_AUTOPUBLISH=ALREADY_LIVE_SHA_VERIFIED")
            return 0
        if result != "READY_APPROVED_RELEASE":
            return 2
        if mode == "check":
            return 0
        # Only the already-installed privileged owner-reviewed unit may mutate
        # production. That unit independently rechecks backup digest, pointers,
        # identity, nginx health and rollback; this launcher cannot override it.
        if not fixed_run(["/usr/bin/systemctl", "start", UNIT],
                         timeout=150, return_success=True):
            print("KMJ_AUTOPUBLISH=BLOCKED_RELEASE_UNIT_FAILED")
            return 2
        if live_release() != "platform-" + target[:12]:
            print("KMJ_AUTOPUBLISH=BLOCKED_RELEASE_NOT_LIVE")
            return 2
        response = public_https_response()
        if not exact_https_sha_ok(response, target):
            print("KMJ_AUTOPUBLISH=BLOCKED_POST_ACTIVATION_SHA_HTTP")
            return 2
        print("KMJ_AUTOPUBLISH=LIVE_SHA_VERIFIED")
        print("KMJ_AUTOPUBLISH_SHA=" + target)
        return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run("activate" if args.activate else "check"))
